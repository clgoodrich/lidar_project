"""How the hollow detector treats the drawn pits, 9t. Set 2026-11-27.

Why
  The hollows are lidar dips sized like pits, kept away from pits. Running the same dip finder
  with no exclusions shows how many drawn pits it finds, i.e. whether "pit-shaped dip" fairly
  describes the pits the hollows are compared with.

Method
  Same DEM fill and 0.2 m depth as _nisar_hollows_9t.py. Each drawn pit_outside polygon gets the
  largest depression floor touching it, the deepest fill depth inside it, and whether it would
  pass the hollow size rules (floor 30-300 m2, grown outline 75-500 m2).

Output
  nisar/results/9t/v2/nisar_hollows_pit_overlap_9t.csv   (one row per drawn pit)

Run
  python nisar/code/s5_eval/_nisar_hollows_pit_overlap_9t.py
"""
import importlib
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from scipy import ndimage
from skimage.morphology import reconstruction

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
h = importlib.import_module("_nisar_hollows_9t")
st, A = h.st, h.A
OUT = A.NISAR_ROOT / "results" / "9t" / "v2" / "nisar_hollows_pit_overlap_9t.csv"


def main():
    with rasterio.open(h.DEM) as r:
        z = r.read(1).astype(np.float64)
        tf, crs = r.transform, r.crs
    bad = z < -9000
    z[bad] = np.nanmax(z[~bad]) + 10
    seed = z.copy()
    seed[1:-1, 1:-1] = z.max()
    depth = reconstruction(seed, z, method="erosion") - z
    depth[bad] = 0
    dep = depth > h.DEPTH_M
    lab, n = ndimage.label(dep)
    area = np.r_[0, ndimage.sum(dep, lab, range(1, n + 1))]
    pits = st.read_layer(st.ANN, "pit_outside").to_crs(crs).reset_index(drop=True)
    rows = []
    for i, g in enumerate(pits.geometry):
        m = ~geometry_mask([g], z.shape, tf, all_touched=True) & ~bad
        if not m.any():
            continue
        ids = np.unique(lab[m & dep])
        fl = float(area[ids].max()) if len(ids) else 0.0
        out_a = 0.0
        if len(ids):
            big = ids[np.argmax(area[ids])]
            from rasterio.features import shapes
            from shapely.geometry import shape
            from shapely.ops import unary_union
            mm = lab == big
            out_a = unary_union([shape(s) for s, v in shapes(mm.astype(np.uint8), mask=mm, transform=tf)]).buffer(h.GROW_M).area
        rows.append(dict(pit=i, pit_area_m2=round(g.area, 1), max_depth_m=round(float(depth[m].max()), 2),
                         floor_m2=fl, outline_m2=round(out_a, 1),
                         found=fl > 0,
                         passes_size=(h.FLOOR_MIN <= fl <= h.FLOOR_MAX) and (h.OUT_MIN <= out_a <= h.OUT_MAX)))
    d = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT, index=False)
    print(f"pits {len(d)}; any dip >{h.DEPTH_M} m: {d.found.sum()} ({d.found.mean():.0%}); "
          f"passes hollow size rules: {d.passes_size.sum()} ({d.passes_size.mean():.0%})")
    print("floor m2 of found:", d.loc[d.found, 'floor_m2'].describe().round(0).to_dict())
    print("max depth m quartiles:", d.max_depth_m.quantile([.25, .5, .75]).round(2).to_dict())
    print("too small:", int((d.found & (d.floor_m2 < h.FLOOR_MIN)).sum()), "too big:", int((d.floor_m2 > h.FLOOR_MAX).sum()))
    print("->", OUT)


if __name__ == "__main__":
    main()
