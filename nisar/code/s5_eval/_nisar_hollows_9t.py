"""Natural hollows on 9t: well-free closed depressions to test pit specificity. Set 2026-11-27 (Track 2C).

Why
  Pits read brighter than their ring in summer HV (+0.16 dB). That could be a well marker, or any
  small closed depression (wetter floor, sheltered rim). Running the same test on well-free hollows
  separates the two: if hollows show the same excess, the pit signal is generic terrain.

Method
  1. 1 m lidar DEM; depressions = morphological fill minus DEM above 0.2 m.
  2. Connected depressions of 30 to 300 m2 floor area, then grown 3 m to take in the rim, so the
     outline matches `pit_outside` (pit plus rim, 75 to 500 m2, median 197 m2).
  3. Keep only those 40 m or more from any DEP well and 20 m or more from any drawn pit, pad or road.
     Road ditches and culvert pools are the main lookalikes, so the road gap matters.
  4. Keep outlines between 75 and 500 m2 (the pit range).

Output
  nisar/derived/9t/nisar_hollows_polygons_9t.gpkg   (lidar frame, EPSG:6346, like the annotations)

Run
  python nisar/code/s5_eval/_nisar_hollows_9t.py --slc
"""
import importlib
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from scipy import ndimage
from skimage.morphology import reconstruction
from shapely.geometry import shape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
st = importlib.import_module("_nisar_gslc_stack_pad_pit_seasonal_9t")
A = st.A
DEM = A.NISAR_ROOT.parent / "data" / "9t" / "derived" / "1m" / "dem_9t_1m.tif"
OUT = A.NISAR_DERIVED / "nisar_hollows_polygons_9t.gpkg"
DEPTH_M, FLOOR_MIN, FLOOR_MAX, GROW_M = 0.2, 30, 300, 3.0
OUT_MIN, OUT_MAX = 75, 500


def main():
    with rasterio.open(DEM) as r:
        z = r.read(1).astype(np.float64)
        tf, crs = r.transform, r.crs
    bad = z < -9000
    z[bad] = np.nanmax(z[~bad]) + 10  # nodata acts as a high wall, so it never makes a depression
    seed = z.copy()
    seed[1:-1, 1:-1] = z.max()
    filled = reconstruction(seed, z, method="erosion")
    dep = (filled - z > DEPTH_M) & ~bad
    lab, n = ndimage.label(dep)
    area = ndimage.sum(dep, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = (area >= FLOOR_MIN) & (area <= FLOOR_MAX)
    m = keep[lab]
    print(f"{n} depressions, {keep.sum()} with floor {FLOOR_MIN}-{FLOOR_MAX} m2", flush=True)
    geoms = [shape(g).buffer(GROW_M) for g, v in shapes(m.astype(np.uint8), mask=m, transform=tf) if v == 1]
    h = gpd.GeoDataFrame(geometry=geoms, crs=crs)
    wells = gpd.read_file(A.WELLS).to_crs(crs)
    avoid = [wells.buffer(40)] + [st.read_layer(st.ANN, k).to_crs(crs).buffer(20) for k in ("pit_outside", "plat", "roads")]
    bad_zone = gpd.GeoSeries(np.concatenate([a.values for a in avoid]), crs=crs).union_all()
    h = h[~h.intersects(bad_zone)]
    h = h[(h.area >= OUT_MIN) & (h.area <= OUT_MAX)].reset_index(drop=True)
    h["hollow_id"] = np.arange(len(h))
    h["area_m2"] = h.area.round(1)
    h.to_file(OUT, driver="GPKG")
    print(f"{len(h)} hollows kept, area median {h.area.median():.0f} m2 -> {OUT}")


if __name__ == "__main__":
    main()
