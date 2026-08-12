"""Shared utilities for active WellSight scripts.

This is the small, focused replacement for the previously-archived ``wsight``
package. Everything in here is actually imported by sibling scripts; nothing
here is speculative scaffolding.

Provides:
  * Project paths and CRS constants (``ROOT``, ``DERIV``, ``DERIV_9T``, ``DST_CRS``)
  * PDAL CLI helper (``run_pdal``) — single source of truth for the
    write-JSON-then-subprocess pattern documented in ``CLAUDE.md``.
  * Raster I/O helpers (``read_tif``, ``write_tif``, ``make_profile``).

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
# Kept in step with config/paths.toml by hand. The config wins; this is only the
# fallback for a missing or unparseable file, so a config typo degrades to the
# last-known-good layout instead of taking the pipeline down.
_DEFAULTS: dict[str, str] = {
    "data": "data",
    # 01 source -- immutable
    "source": "data/source_laz",
    "source_laz": "data/source_laz",
    "reference": "data/external",
    "external": "data/external",
    "landcover": "data/external/landcover",
    # 02 truth -- hand-drawn, irreplaceable
    "truth": "data/derivatives/annotations",
    "annotations": "data/derivatives/annotations",
    "truth_grids": "label_grids",
    "truth_history": "data/derivatives/annotations",
    # 03 derived -- regenerable by definition
    "derived": "data/derivatives/tiles",
    "derivatives": "data/derivatives",
    "tiles": "data/derivatives/tiles",
    "nine_t": "data/derivatives/tiles/9t",
    "nine_t_1m": "data/derivatives",
    "data_3x3": "data/derivatives/tiles/data_3x3",
    "label_grids": "label_grids",
    # 04 models
    "models": "data/derivatives/tiles/9t",
    "pretrained": "models/pretrained",
    "models_retired": "data/derivatives/tiles/9t/iterations",
    # 05 results
    "results": "data/derivatives",
    "candidates": "data/derivatives/experiments/candidates",
    "validation": "data/derivatives/validation",
    # 06 experiments / 99 archive
    "experiments": "data/derivatives/experiments",
    "archive": "data/99_archive",
    # repo-level
    "literature": "literature",
    "docs": "docs",
    "ledgers": "docs/_ledgers",
    "figures": "docs/figures",
    "qgis": "qgis",
    "tools": "tools",
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
DERIV: Path = PATHS["derivatives"]
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


def write_tif(
    path: Path,
    arr: np.ndarray,
    *,
    transform: Affine,
    crs: str | rasterio.crs.CRS,
    dtype: str | None = None,
    nodata: float | int | None = -9999.0,
    **extra: Any,
) -> None:
    """Write a 2-D array as a single-band GeoTIFF with project-standard
    compression. Float arrays have NaNs replaced with ``nodata`` automatically.
    """
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
