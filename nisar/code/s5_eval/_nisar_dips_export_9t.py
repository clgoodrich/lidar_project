"""Every pit-sized lidar dip on 9t, labelled by what it sits on, for review in QGIS. Set 2026-11-27.

Why
  The hollow detector finds dips on drawn pits, beside DEP wells with no drawn pit, near pads and
  roads, and far from all of them. This writes them all so they can be checked by eye.

Method
  Same fill and 0.2 m depth as _nisar_hollows_9t.py, floor 10-300 m2 (pit-sized), grown 3 m,
  outline 75-500 m2. Category, first match wins: drawn_pit (touches a drawn pit), near_well
  (<=40 m from a DEP well), near_pad (<=20 m), near_road (<=20 m), hollow (none of these).
  floor_ge30 marks dips that also pass the 30 m2 floor used in the first hollow run.

Output
  nisar/derived/9t/nisar_dips_by_category_9t.gpkg   (EPSG:6346, layer "dips")
  nisar/derived/9t/nisar_hollows_floor10_polygons_9t.gpkg   (hollows also 20 m from drawn pits)

Run
  python nisar/code/s5_eval/_nisar_dips_export_9t.py
"""
import importlib
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape
from skimage.morphology import reconstruction

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
h = importlib.import_module("_nisar_hollows_9t")
st, A = h.st, h.A
OUT = A.NISAR_DERIVED / "nisar_dips_by_category_9t.gpkg"
HOLLOWS = A.NISAR_DERIVED / "nisar_hollows_floor10_polygons_9t.gpkg"  # pit-sized hollows for the radar test
FLOOR_MIN = 10


def main():
    with rasterio.open(h.DEM) as r:
        z = r.read(1).astype(np.float64)
        tf, crs = r.transform, r.crs
    bad = z < -9000
    z[bad] = z[~bad].max() + 10
    seed = z.copy()
    seed[1:-1, 1:-1] = z.max()
    depth = reconstruction(seed, z, method="erosion") - z
    dep = (depth > h.DEPTH_M) & ~bad
    lab, n = ndimage.label(dep)
    area = np.r_[0, ndimage.sum(dep, lab, range(1, n + 1))]
    mx = np.r_[0, ndimage.maximum(depth, lab, range(1, n + 1))]
    keep = (area >= FLOOR_MIN) & (area <= h.FLOOR_MAX)
    keep[0] = False
    m = keep[lab]
    rows = []
    for g, v in shapes(np.where(m, lab, 0).astype(np.int32), mask=m, transform=tf):
        v = int(v)
        rows.append(dict(geometry=shape(g).buffer(h.GROW_M), floor_m2=float(area[v]), max_depth_m=round(float(mx[v]), 2)))
    d = gpd.GeoDataFrame(rows, crs=crs)
    d = d[(d.area >= h.OUT_MIN) & (d.area <= h.OUT_MAX)].reset_index(drop=True)
    zones = [("drawn_pit", st.read_layer(st.ANN, "pit_outside").to_crs(crs).union_all()),
             ("near_well", gpd.read_file(A.WELLS).to_crs(crs).buffer(40).union_all()),
             ("near_pad", st.read_layer(st.ANN, "plat").to_crs(crs).buffer(20).union_all()),
             ("near_road", st.read_layer(st.ANN, "roads").to_crs(crs).buffer(20).union_all())]
    d["category"] = "hollow"
    for name, zg in reversed(zones):
        d.loc[d.intersects(zg), "category"] = name
    d["floor_ge30"] = d.floor_m2 >= 30
    d["outline_m2"] = d.area.round(1)
    d.insert(0, "dip_id", np.arange(len(d)))
    d.to_file(OUT, layer="dips", driver="GPKG")
    pits20 = st.read_layer(st.ANN, "pit_outside").to_crs(crs).buffer(20).union_all()
    hol = d[(d.category == "hollow") & ~d.intersects(pits20)].copy()  # same 20 m pit gap as the first hollow run
    hol["hollow_id"] = np.arange(len(hol))
    hol["area_m2"] = hol.outline_m2
    hol[["hollow_id", "area_m2", "floor_m2", "max_depth_m", "geometry"]].to_file(HOLLOWS, driver="GPKG")
    print(f"{len(hol)} hollows (20 m from pits) -> {HOLLOWS}")
    print(d.category.value_counts().to_dict(), "| floor>=30:", d.groupby("category").floor_ge30.sum().to_dict())
    print("->", OUT)


if __name__ == "__main__":
    main()
