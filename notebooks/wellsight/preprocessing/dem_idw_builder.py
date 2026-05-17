"""IDW-based DEM builder — OpenTopography's published cornrow mitigation.

OpenTopography's official FAQ on linear "corduroy" striping in DEMs:

    "...there is nothing the user (or OpenTopography) can do to fix this as
     it is in the raw data that we receive. One option is to set a coarser
     grid resolution, and if the artifacts are still present at a coarser
     resolution, users may want to try the other gridding algorithm under
     'DEM Generation (local gridding)'."

The "local gridding" algorithm is Points2Grid (IDW), now integrated into
PDAL as ``writers.gdal output_type=idw``. IDW averages all ground returns
within ``radius`` of each cell centre, weighted by 1/d^power, which smooths
across strip-edge offsets that TIN+faceraster would render as long
stretched triangles.

This module is the canonical WellSight DEM-from-point-cloud entry point
when artifact suppression matters. The legacy TIN+faceraster pipeline used
in ``_build_9tile_1m.py`` remains valid for full-density, well-calibrated
data; this builder is preferred when the source delivery has visible
interswath inconsistency (e.g. PA_WesternPA_2019_D20, where the merged 9t
audit showed 19.6% of overlap cells exceed the USGS Delta-z = 8 cm spec).

Optional pre-DEM cleanup follows the PDAL Ground Filter Tutorial canonical
sequence: ``filters.elm`` (extended local minimum, removes low-noise
spikes) and ``filters.outlier`` (statistical isolation removal).
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]
BBox = tuple[float, float, float, float]  # (minx, miny, maxx, maxy)

logger = logging.getLogger(__name__)


def _pdal_binary() -> str:
    return shutil.which("pdal") or "pdal"


def build_dem_idw(
    input_path: PathLike,
    output_tif: PathLike,
    bbox: Optional[BBox] = None,
    resolution: float = 1.0,
    idw_radius: float = 2.0,
    idw_power: float = 2.0,
    apply_elm: bool = True,
    apply_outlier: bool = True,
    classification: int = 2,
    timeout: int = 3600,
) -> dict:
    """Build a single-channel float32 DEM via PDAL ``writers.gdal`` IDW.

    Pipeline stages (in order):

    1. ``readers.las`` — load the input.
    2. ``filters.crop`` — optional crop to ``bbox``.
    3. ``filters.range Classification[c:c]`` — keep only the requested class
       (default 2, ground).
    4. ``filters.elm`` — extended local minimum, removes low-noise spikes
       (optional).
    5. ``filters.outlier`` — statistical outlier removal, default 8
       neighbours + 3 sigma (optional).
    6. ``writers.gdal output_type=idw`` — IDW raster at ``resolution`` with
       the given ``idw_radius`` and ``idw_power``.

    Args:
        input_path: Source LAS/LAZ file (must exist).
        output_tif: Destination GeoTIFF path. Parent directory must exist.
        bbox: Optional ``(minx, miny, maxx, maxy)`` to crop the input to.
            When None, the writer uses the input's bounding box.
        resolution: Cell size in source CRS units (default 1.0 m).
        idw_radius: Search radius in source CRS units (default 2.0 m). The
            OpenTopography Points2Grid heuristic is ``radius >= 2 *
            resolution``; smaller radii leave more nodata, larger radii
            over-smooth real terrain.
        idw_power: Inverse-distance weighting exponent (default 2.0). Use
            higher values (3.0–4.0) to bias toward the nearest point
            without losing multi-point averaging.
        apply_elm: When True (default) include ``filters.elm`` before the
            writer.
        apply_outlier: When True (default) include ``filters.outlier``
            before the writer.
        classification: ASPRS class to retain (default 2 = ground).
        timeout: PDAL subprocess timeout in seconds (default 3600).

    Returns:
        A dict with ``output_path``, ``resolution``, ``idw_radius``,
        ``idw_power``, ``elapsed_seconds``, and (when bbox given)
        ``width`` / ``height``.

    Raises:
        FileNotFoundError: input path does not exist or output directory
            does not exist.
        RuntimeError: PDAL pipeline returned non-zero exit; the exception
            message includes the tail of PDAL's stderr.
    """
    in_path = Path(input_path)
    out_path = Path(output_tif)
    if not in_path.exists():
        raise FileNotFoundError(f"Input LAS/LAZ not found: {in_path}")
    if not out_path.parent.exists():
        raise FileNotFoundError(
            f"Output directory does not exist: {out_path.parent}"
        )

    stages: list = [{"type": "readers.las", "filename": str(in_path)}]

    if bbox is not None:
        minx, miny, maxx, maxy = bbox
        stages.append({
            "type": "filters.crop",
            "bounds": f"([{minx}, {maxx}], [{miny}, {maxy}])",
        })

    stages.append({
        "type": "filters.range",
        "limits": f"Classification[{classification}:{classification}]",
    })

    if apply_elm:
        # Extended local minimum: tags spurious low points as noise so they
        # don't appear in the IDW window. Conservative defaults.
        stages.append({"type": "filters.elm"})
        # filters.elm marks as Classification=7; drop them.
        stages.append({"type": "filters.range", "limits": "Classification![7:7]"})

    if apply_outlier:
        # Statistical: drop any point whose mean distance to its 8 nearest
        # neighbours is > mean + 3 * sigma across the cloud.
        stages.append({
            "type": "filters.outlier",
            "method": "statistical",
            "mean_k": 8,
            "multiplier": 3.0,
        })
        # filters.outlier also marks Classification=7; drop those too.
        stages.append({"type": "filters.range", "limits": "Classification![7:7]"})

    writer = {
        "type": "writers.gdal",
        "filename": str(out_path),
        "output_type": "idw",
        "resolution": resolution,
        "radius": idw_radius,
        "power": idw_power,
        "data_type": "float32",
    }
    if bbox is not None:
        minx, miny, maxx, maxy = bbox
        W = int(round((maxx - minx) / resolution))
        H = int(round((maxy - miny) / resolution))
        writer.update(origin_x=minx, origin_y=miny, width=W, height=H)
    stages.append(writer)

    pipeline = {"pipeline": stages}

    tmp_json = out_path.parent / f"_tmp_dem_idw_{int(time.time()*1000)}.json"
    tmp_json.write_text(json.dumps(pipeline, indent=2))
    logger.debug("wrote IDW pipeline JSON: %s", tmp_json)
    logger.info(
        "build_dem_idw: input=%s output=%s res=%g radius=%g power=%g elm=%s outlier=%s",
        in_path, out_path, resolution, idw_radius, idw_power,
        apply_elm, apply_outlier,
    )

    t0 = time.time()
    try:
        r = subprocess.run(
            [_pdal_binary(), "pipeline", str(tmp_json)],
            capture_output=True, text=True, timeout=timeout,
        )
    finally:
        tmp_json.unlink(missing_ok=True)
    elapsed = time.time() - t0

    if r.returncode != 0:
        raise RuntimeError(
            f"PDAL IDW pipeline failed (rc={r.returncode}) for {in_path.name}:\n"
            f"{r.stderr[-4096:]}"
        )

    logger.info("build_dem_idw done in %.1fs -> %s", elapsed, out_path)

    result = {
        "output_path":     str(out_path.resolve()),
        "resolution":      float(resolution),
        "idw_radius":      float(idw_radius),
        "idw_power":       float(idw_power),
        "elapsed_seconds": elapsed,
    }
    if bbox is not None:
        result["bbox"] = list(bbox)
        result["width"] = W
        result["height"] = H
    return result
