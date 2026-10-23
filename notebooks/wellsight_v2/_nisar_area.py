"""Which lidar area the NISAR scripts run on: 9t (default), 613590, mkf (McKean) or warren.

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
    "warren": ("warren", "warren_1m"),
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


def _pick_stack() -> str:
    """`--slc` reads the lidar-placed SLC stack instead of NASA's GSLC (9t and 613590).
    Not `--stack`: the lidar-match script already owns that flag."""
    if "--slc" in sys.argv:
        sys.argv.remove("--slc")
        os.environ["NISAR_STACK"] = "slc"
        return "slc"
    return os.environ.get("NISAR_STACK", "gslc")


STACK = _pick_stack()
if STACK not in ("gslc", "slc"):
    raise SystemExit(f"unknown stack {STACK!r}; use gslc or slc")
if STACK == "slc" and TAG in ("mkf", "warren"):
    raise SystemExit("the lidar-placed SLC stack exists for 9t and 613590 only")
DATA = path_for("data") / AREAS[TAG][0]
D1M = DATA / "derived" / "1m" / ("full" if TAG == "warren" else "")
SFX = AREAS[TAG][1]
GSLC = DATA / "derived" / ("nisar_slc_lidar_5m" if STACK == "slc" else "nisar_gslc_5m")
# Window index of the stack in use. The lidar-placed stack has its own index and its outputs
# carry the tag `9t_slc`, so they sit beside the GSLC results without overwriting them.
INDEX = GSLC / (f"nisar_slc_lidar_index_{TAG}.csv" if STACK == "slc" else f"nisar_gslc_window_index_{TAG}_5m.csv")
if STACK == "slc":
    TAG = f"{TAG}_slc"
RSLC = DATA / "derived" / "nisar_rslc_window"
RESULTS = DATA / "results" / "nisar"
# DEP oil and gas locations. Venango areas keep the Venango export the 9t results used;
# McKean takes the statewide export of the same date (2026-04, same columns).
_DEP = path_for("data") / "_source" / "reference" / "dep_wells"
WELLS = _DEP / ("oil_gas_locations.gpkg" if TAG in ("mkf", "warren") else "venango_wells_all.gpkg")
# NASA granules that sit far from where the rest of their track puts the ground. Each one
# matches no other date of its track at any shift inside the window, in every area that
# holds it (checked 2026-10-13, docs/iterations/nisar_regeocode_plan_9t.md). (date, track).
BAD_DATES = {("2026-07-22", 26), ("2026-09-08", 26)}


def usable(idx):
    """Rows of a NISAR window index worth using: at least half valid and not in BAD_DATES."""
    bad = idx.apply(lambda r: (str(r.date), int(r.track)) in BAD_DATES, axis=1)
    return idx[(idx.valid_fraction >= 0.5) & ~bad]


def usable_stack(idx):
    """Rows to analyse: half-valid dates, and on the lidar-placed stack (and Warren) also not a bad granule."""
    return usable(idx) if (STACK == "slc" or TAG == "warren") else idx[idx.valid_fraction >= 0.5]


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
