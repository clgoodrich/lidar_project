"""Find the straight survey seams in the 2019 minus 2006-2008 change field, and score every change patch against them.

Why. On the evidence sheets, most "non-erosional" patches are not earthworks. They are small clumps inside a broad block of
raised or lowered ground that ends on a ruler-straight east-west or north-south line. That is a swath or tile seam in the older
survey. Part 4 of docs/iterations/icp_change_9t.md named it "band-local striping" and left it unfixed.

Method. In the high-passed change field, take the mean over 3 x 25 cells (6 m x 50 m) on each side of every row, and the same
across columns. A seam is a thin line where that step is at least 0.10 m and runs at least 60 cells (120 m) straight.
Each patch gets three numbers.
  seam_dist_m     distance from the patch to the nearest seam
  step_m          size of the step across that seam
  ring_contrast_m patch mean minus the median of a 12 to 40 m ring around it. A real earthwork stands out from its surroundings.
                  A noise clump inside a biased block does not.

Outputs (data/9t/results/change/): change_seams_9t_2m.tif (1 = row seam, 2 = column seam), change_patch_evidence_9t.csv

Run:
  python notebooks/wellsight_v2/s7_analysis/_change_seams_9t.py
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[3]
ICP = ROOT / "data/_experiments/icp/change_9t"
OUT = ROOT / "data/9t/results/change"
STEP, MINRUN = 0.10, 60


def seams(f):
    z = np.nan_to_num(f, nan=0.0)
    My = ndi.uniform_filter(z, size=(3, 25), mode="nearest")
    Mx = ndi.uniform_filter(z, size=(25, 3), mode="nearest")
    Sy = np.zeros_like(z)
    Sx = np.zeros_like(z)
    Sy[3:-3] = My[6:] - My[:-6]        # step going down the rows
    Sx[:, 3:-3] = Mx[:, 6:] - Mx[:, :-6]
    out = np.zeros(z.shape, np.uint8)
    steps = np.zeros(z.shape, np.float32)
    for code, S, size in ((1, Sy, (7, 1)), (2, Sx, (1, 7))):
        A = np.abs(S)
        peak = (A == ndi.maximum_filter(A, size=size)) & (A >= STEP)
        lab, n = ndi.label(peak, structure=np.ones((3, 3)))
        for i, sl in enumerate(ndi.find_objects(lab), 1):
            h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
            long_ok = (w >= MINRUN and h <= 8) if code == 1 else (h >= MINRUN and w <= 8)
            if long_ok:
                m = lab[sl] == i
                out[sl][m] = code
                steps[sl][m] = S[sl][m]
    return out, steps


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(ICP / "dod_9t_singleicp_highpass_2m.tif") as s:
        f = s.read(1).astype(float)
        T, prof = s.transform, s.profile
    sm, st = seams(f)
    prof.update(dtype="uint8", count=1, nodata=0, compress="deflate")
    with rasterio.open(OUT / "change_seams_9t_2m.tif", "w", **prof) as d:
        d.write(sm, 1)
    print("seam cells", int((sm == 1).sum()), "row-seam,", int((sm == 2).sum()), "column-seam")
    dist, idx = ndi.distance_transform_edt(sm == 0, sampling=2.0, return_indices=True)
    g = gpd.read_file(ICP / "change_patches_9t_singleicp.gpkg")
    rows = []
    for r in g.itertuples():
        m = ~geometry_mask([r.geometry], out_shape=f.shape, transform=T)
        rr, cc = np.where(m)
        sd = float(dist[m].min())
        j = np.argmin(dist[m])
        ir, ic = idx[0][m][j], idx[1][m][j]
        step = float(st[ir, ic])
        ring = ndi.binary_dilation(m, iterations=20) & ~ndi.binary_dilation(m, iterations=6)
        ring &= np.isfinite(f)
        rc = float(np.nanmean(f[m]) - np.nanmedian(f[ring])) if ring.sum() > 20 else np.nan
        rows.append(dict(patch_id=r.patch_id, cls=r.cls, sign=r.sign, area_m2=r.area_m2, mean_dz_m=r.mean_dz_m, seam_dist_m=round(sd, 1),
                         step_m=round(step, 3), ring_contrast_m=round(rc, 3)))
    D = pd.DataFrame(rows)
    D["seam_touch"] = D.seam_dist_m <= 10
    D.to_csv(OUT / "change_patch_evidence_9t.csv", index=False)
    print(D.groupby("cls").agg(n=("patch_id", "size"), seam_touch=("seam_touch", "sum"), med_contrast=("ring_contrast_m", lambda v: np.nanmedian(np.abs(v)))).to_string())
    a = D[D.cls == "anthropogenic"].sort_values("area_m2", ascending=False)
    print(a[["patch_id", "sign", "area_m2", "mean_dz_m", "seam_dist_m", "step_m", "ring_contrast_m"]].to_string(index=False))


if __name__ == "__main__":
    main()
