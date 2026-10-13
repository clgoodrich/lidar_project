"""Which lidar area the NISAR scripts run on: 9t (default), 613590 or mkf (McKean).

Every NISAR script imports this before it builds its paths. Pick the area with
`--area <tag>` on the command line (removed from sys.argv here, so each script's own
argparse never sees it) or with the NISAR_AREA environment variable.

    python notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py --area 613590

The script names keep their `_9t` ending (they were written for 9t). Output names carry
the area tag, so 9t outputs are named exactly as before.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from _common import path_for

# area tag -> (area directory under data/, 1 m derivative suffix)
AREAS = {
    "9t": ("9t", "9t_1m"),
    "613590": ("613590", "613590_1m"),
    "mkf": ("mckean/mkf", "mkf_1m"),
}


def _pick() -> str:
    if "--area" in sys.argv:
        i = sys.argv.index("--area")
        tag = sys.argv[i + 1]
        del sys.argv[i:i + 2]
        os.environ["NISAR_AREA"] = tag     # so modules imported later agree
        return tag
    return os.environ.get("NISAR_AREA", "9t")


TAG = _pick()
if TAG not in AREAS:
    raise SystemExit(f"unknown area {TAG!r}; use one of {sorted(AREAS)}")
DATA = path_for("data") / AREAS[TAG][0]
D1M = DATA / "derived" / "1m"
SFX = AREAS[TAG][1]
GSLC = DATA / "derived" / "nisar_gslc_5m"
RSLC = DATA / "derived" / "nisar_rslc_window"
RESULTS = DATA / "results" / "nisar"
# DEP oil and gas locations. Venango areas keep the Venango export the 9t results used;
# McKean takes the statewide export of the same date (2026-04, same columns).
_DEP = path_for("data") / "_source" / "reference" / "dep_wells"
WELLS = _DEP / ("oil_gas_locations.gpkg" if TAG == "mkf" else "venango_wells_all.gpkg")


def lidar(name: str) -> Path:
    """1 m lidar derivative of this area, e.g. lidar('chm') -> .../chm_9t_1m.tif."""
    return D1M / f"{name}_{SFX}.tif"


def bounds(crs: str = "EPSG:32617"):
    """Area extent (from its 1 m DEM, or slope while the DEM is being built) in crs."""
    import rasterio
    from rasterio.warp import transform_bounds
    ref = next(p for p in (lidar("dem"), lidar("slope"), lidar("hillshade")) if p.exists())
    with rasterio.open(ref) as r:
        return transform_bounds(r.crs, crs, *r.bounds)


def wells(crs: str = "EPSG:32617", pad_m: float = 0.0):
    """DEP well records inside the area plus pad_m, in crs."""
    import geopandas as gpd
    x0, y0, x1, y1 = bounds(crs)
    w = gpd.read_file(WELLS).to_crs(crs)
    return w.cx[x0 - pad_m:x1 + pad_m, y0 - pad_m:y1 + pad_m].reset_index(drop=True)
