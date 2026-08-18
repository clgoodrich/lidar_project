"""Shared utilities for active WellSight scripts.

This is the small, focused replacement for the previously-archived ``wsight``
package. Everything in here is actually imported by sibling scripts; nothing
here is speculative scaffolding.

Provides:
  * Project paths and CRS constants (``ROOT``, ``DERIV``, ``DERIV_9T``, ``DST_CRS``)
  * PDAL CLI helper (``run_pdal``) — single source of truth for the
    write-JSON-then-subprocess pattern documented in ``CLAUDE.md``.
  * Raster I/O helpers (``read_tif``, ``write_tif``, ``make_profile``).
    ``write_tif(..., rgb_bool=True)`` writes a 3-band uint8 RGB GeoTIFF.

Other internal modules: ``_dl.py`` (deep-learning building blocks).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import numpy as np
import rasterio
from rasterio.transform import Affine

__all__ = [
    "ROOT", "DERIV", "DERIV_9T", "DST_CRS", "PDAL_EXE",
    "PATHS", "CONFIG", "path_for",
    "run_pdal",
    "read_tif", "write_tif", "make_profile",
]

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------
# Read from config/paths.toml so a directory move is one edit in one file
# instead of a hunt through 92 scripts. ROOT was hardcoded to one username's
# home directory until 2026-08-12.
#
# EVERY LEGACY NAME IS PRESERVED. ROOT, DERIV, DERIV_9T, DST_CRS and PDAL_EXE
# mean exactly what they meant before, so all 67 importing scripts keep working
# with no change. If the config is missing or unreadable, the old values are
# reconstructed from __file__ -- a broken config must never take the pipeline
# down.

#
# GENERATED FROM config/paths.toml -- do not hand-edit, and do not let it drift.
# The config wins at runtime; this is the fallback for a missing or unparseable
# file. It went stale across the 2026-08-13 move and would have silently sent a
# broken-config run at data/derivatives, a directory that no longer exists.
# tests/test_paths_config.py asserts the two stay identical.
_DEFAULTS: dict[str, str] = {
    'data': 'data',
    'source': 'data/_source/lidar',
    'source_laz': 'data/_source/lidar',
    'reference': 'data/_source/reference',
    'external': 'data/_source/reference',
    'landcover': 'data/_source/reference/landcover',
    'dep_wells': 'data/_source/reference/dep_wells',
    'pretrained': 'data/_pretrained',
    'experiments': 'data/_experiments',
    'shared_results': 'data/_results',
    'candidates': 'data/_results/candidates',
    'validation': 'data/_results/validation',
    'archive': 'data/_archive',
    'truth': 'qgis/annotations',
    'annotations': 'qgis/annotations',
    'truth_grids': 'qgis/annotations/grids',
    'truth_history': 'qgis/annotations/_history',
    'nine_t': 'data/9t/derived/05',
    'nine_t_1m': 'data/9t/derived/1m',
    'models': 'data/9t/models',
    'models_retired': 'data/9t/models/_retired',
    'results_9t': 'data/9t/results',
    'results_613590': 'data/613590/results',
    'derived': 'data',
    'tiles': 'data',
    'data_3x3': 'data',
    'label_grids': 'data/grids',
    'results': 'data/_results',
    'literature': 'literature',
    'docs': 'docs',
    'ledgers': 'docs/_ledgers',
    'figures': 'docs/figures',
    'qgis': 'qgis',
    'tools': 'tools',
}



def _load_config() -> tuple[Path, dict]:
    """Resolve ROOT and read config/paths.toml. Never raises."""
    import os

    # 1. auto-detect: notebooks/wellsight_v2/_common.py -> repo root
    root = Path(__file__).resolve().parents[2]
    cfg: dict = {}
    try:
        import tomllib
        cfg_path = root / "config" / "paths.toml"
        if cfg_path.is_file():
            cfg = tomllib.loads(cfg_path.read_text(encoding="utf8"))
    except Exception:                      # noqa: BLE001 - config is optional
        cfg = {}

    # 2. root_override in the config file beats auto-detection
    override = cfg.get("root_override")
    if override:
        root = Path(override)
    # 3. the environment beats everything, for CI and second machines
    env = os.environ.get("WELLSIGHT_ROOT")
    if env:
        root = Path(env)
    return root, cfg


ROOT, CONFIG = _load_config()

#: Named project directories, resolved to absolute paths.
PATHS: dict[str, Path] = {
    k: ROOT / v for k, v in {**_DEFAULTS, **CONFIG.get("paths", {})}.items()
}


def path_for(name: str) -> Path:
    """Look up a configured directory by name, e.g. ``path_for("annotations")``.

    Prefer this over hand-assembling ``ROOT / "data" / "derivatives" / ...`` in
    new code. Raises KeyError with the valid names rather than silently
    returning a path that does not exist.
    """
    try:
        return PATHS[name]
    except KeyError:
        raise KeyError(
            f"unknown path {name!r}; configured names: {sorted(PATHS)}") from None


# --- Legacy names, unchanged in meaning ------------------------------------
#: LEGACY. Before the 2026-08-13 area-major move this was data/derivatives, the
#: catch-all that held rasters, models, results and ground truth at one depth.
#: That directory no longer exists. DERIV now means the DATA ROOT, and it is
#: kept only so the ~20 scripts with `from _common import DERIV` still import.
#: There are zero remaining `DERIV / ...` uses -- new code must not add one.
#: Use path_for("derived") / <area> / "derived", or the specific key.
DERIV: Path = PATHS["data"]
DERIV_9T: Path = PATHS["nine_t"]
DST_CRS: str = CONFIG.get("crs", {}).get("project", "EPSG:6346")
PDAL_EXE: str = (shutil.which("pdal")
                 or CONFIG.get("tools", {}).get("pdal", "pdal"))


# ---------------------------------------------------------------------------
# PDAL helper
# ---------------------------------------------------------------------------

def run_pdal(
    pipeline_stages: Iterable[Any],
    *,
    label: str = "pipeline",
    tmp_dir: Optional[Path] = None,
    capture_meta: bool = False,
    timeout: int = 3600,
    verbose: bool = True,
) -> Optional[Path]:
    """Run a PDAL pipeline via the CLI; return path to the metadata JSON if
    ``capture_meta`` is True, else None.

    The pipeline JSON is written into ``tmp_dir`` (default: ``DERIV``) and
    cleaned up on success. On non-zero exit, raises ``RuntimeError`` with the
    tail of stderr — keeping with the project's existing failure mode.

    Args:
        pipeline_stages: Iterable of PDAL pipeline stage dicts (or input-file
            strings, which PDAL treats as ``readers.las``).
        label: Short tag for logs / temp file names.
        tmp_dir: Directory for ``_tmp_<label>.json`` (default: ``DERIV``).
        capture_meta: If True, request ``--metadata _meta_<label>.json`` and
            return that path on success.
        timeout: ``subprocess.run`` timeout, seconds.
        verbose: Print rc + duration line on completion.

    Raises:
        RuntimeError: PDAL exited non-zero (stderr tail in message).
    """
    if tmp_dir is None:
        tmp_dir = DERIV
    tmp_dir.mkdir(parents=True, exist_ok=True)
    pipeline_json = tmp_dir / f"_tmp_{label}.json"
    meta_json = tmp_dir / f"_meta_{label}.json" if capture_meta else None
    pipeline_json.write_text(json.dumps({"pipeline": list(pipeline_stages)}, indent=2))

    cmd = [PDAL_EXE, "pipeline"]
    if meta_json is not None:
        cmd += ["--metadata", str(meta_json)]
    cmd.append(str(pipeline_json))

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    dt = time.time() - t0
    if verbose:
        print(f"  [{label}] rc={result.returncode} in {dt:.1f}s")
    if result.returncode != 0:
        # Mirror existing project convention: surface tail of stderr.
        raise RuntimeError(
            f"PDAL pipeline failed (rc={result.returncode}) for {label}:\n"
            f"{result.stderr[-2000:]}"
        )
    pipeline_json.unlink(missing_ok=True)
    return meta_json


# ---------------------------------------------------------------------------
# Raster I/O
# ---------------------------------------------------------------------------

def read_tif(path: Path, *, band: int = 1, with_nan: bool = True) -> np.ndarray:
    """Read a single-band raster as float32, mapping nodata to NaN.

    Args:
        path: GeoTIFF path.
        band: 1-indexed band number.
        with_nan: When True, replace ``nodata`` with NaN. When False, return
            the raw values (useful for int rasters).
    """
    with rasterio.open(path) as ds:
        arr = ds.read(band)
        if with_nan:
            arr = arr.astype(np.float32, copy=False)
            nd = ds.nodata
            if nd is not None:
                arr = np.where(arr == nd, np.nan, arr)
    return arr


def make_profile(
    *,
    width: int,
    height: int,
    transform: Affine,
    crs: str | rasterio.crs.CRS,
    dtype: str = "float32",
    nodata: float | int | None = -9999.0,
    count: int = 1,
    compress: str = "deflate",
    predictor: int | None = None,
    tiled: bool = True,
    blocksize: int = 512,
    bigtiff: bool = False,
) -> dict:
    """Build a rasterio profile dict with the project's standard compression."""
    if predictor is None:
        predictor = 3 if dtype.startswith("float") else 2
    profile: dict[str, Any] = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": count,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": compress,
        "predictor": predictor,
        "tiled": tiled,
        "blockxsize": blocksize,
        "blockysize": blocksize,
    }
    if bigtiff:
        profile["BIGTIFF"] = "YES"
    return profile


# def write_tif(
#     path: Path,
#     arr: np.ndarray,
#     *,
#     transform: Affine,
#     crs: str | rasterio.crs.CRS,
#     dtype: str | None = None,
#     nodata: float | int | None = -9999.0,
#     **extra: Any,
# ) -> None:
#     """Write a 2-D array as a single-band GeoTIFF with project-standard
#     compression. Float arrays have NaNs replaced with ``nodata`` automatically.
#     """
#     if dtype is None:
#         dtype = str(arr.dtype)
#     out = arr.astype(dtype, copy=False)
#     if dtype.startswith("float") and nodata is not None:
#         out = np.where(np.isnan(out), nodata, out).astype(dtype, copy=False)
#     profile = make_profile(
#         width=out.shape[1], height=out.shape[0],
#         transform=transform, crs=crs,
#         dtype=dtype, nodata=nodata,
#         **extra,
#     )
#     with rasterio.open(path, "w", **profile) as ds:
#         ds.write(out, 1)

def write_tif(
    path: Path,
    arr: np.ndarray,
    *,
    transform: Affine,
    rgb_bool: bool = False,
    crs: str | rasterio.crs.CRS,
    dtype: str | None = None,
    nodata: float | int | None = -9999.0,
    skip_existing: bool = False,
    **extra: Any,
) -> bool:
    """...  Returns True if the file was written, False if it already existed."""

    """Write a 2-D array as a single-band GeoTIFF with project-standard
    compression. Float arrays have NaNs replaced with ``nodata`` automatically.
    """
    if skip_existing and path.exists():
        with rasterio.open(path) as ds:
            if (ds.height, ds.width) == arr.shape[:2]:
                return False
        print(f"  {path.name} exists but shape differs -- rewriting")
    if not rgb_bool:
        if dtype is None:
            dtype = str(arr.dtype)
        out = arr.astype(dtype, copy=False)
        if dtype.startswith("float") and nodata is not None:
            out = np.where(np.isnan(out), nodata, out).astype(dtype, copy=False)
        profile = make_profile(
            width=out.shape[1], height=out.shape[0],
            transform=transform, crs=crs,
            dtype=dtype, nodata=nodata,
            **extra,
        )
        with rasterio.open(path, "w", **profile) as ds:
            ds.write(out, 1)
    else:
        print(arr)
        if arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError(f"expected an (H, W, 3) array, got {arr.shape}")
        out = arr.astype("uint8", copy=False)
        profile = make_profile(
            width=out.shape[1], height=out.shape[0],
            transform=transform, crs=crs,
            dtype="uint8", nodata=None, count=3, predictor=2,
            **extra,
        )
        # Without this QGIS opens the file as three grey bands instead of a colour image.
        profile["photometric"] = "RGB"
        with rasterio.open(path, "w", **profile) as ds:
            for b in range(3):
                ds.write(out[:, :, b], b + 1)



# def write_rgb_tif(
#     path: Path,
#     rgb: np.ndarray,
#     *,
#     transform: Affine,
#     crs: str | rasterio.crs.CRS,
#     **extra: Any,
# ) -> None:
#     """Write an ``(H, W, 3)`` uint8 array as a 3-band RGB GeoTIFF.
#
#     ``write_tif`` is single-band only (it ends in ``ds.write(arr, 1)``), and its
#     default ``nodata=-9999`` is out of range for uint8, so colour products like
#     the RRIM need this instead. Bands are written one at a time to avoid
#     materialising a band-first copy of a full-tile array.
#     """
#     if rgb.ndim != 3 or rgb.shape[2] != 3:
#         raise ValueError(f"expected an (H, W, 3) array, got {rgb.shape}")
#     out = rgb.astype("uint8", copy=False)
#     profile = make_profile(
#         width=out.shape[1], height=out.shape[0],
#         transform=transform, crs=crs,
#         dtype="uint8", nodata=None, count=3, predictor=2,
#         **extra,
#     )
#     # Without this QGIS opens the file as three grey bands instead of a colour image.
#     profile["photometric"] = "RGB"
#     with rasterio.open(path, "w", **profile) as ds:
#         for b in range(3):
#             ds.write(out[:, :, b], b + 1)
