"""Independent check of the radar-to-lidar registration from point-like objects (outside-review follow-up 4, 2026-10-27, 9t).

The registration (about 10 m) was never confirmed independently: the best-shift search with wells found no peak, and the
lidar-simulation match uses the canopy. Here the targets are objects the lidar can place and the radar can see as points.
Radar points: the steady bright targets of _nisar_bright_targets_9t.py (single-track ones, so each keeps its own track).
Lidar objects: compact connected components of canopy-height model above 3 m, 6 to 150 m2, in open surroundings (under 25%
of the 31 m window above 2 m): buildings, tanks, towers, equipment.
For every shift (dx, dy) of the lidar objects within +-SEARCH_M, the hit rate is the share of lidar objects with a radar point within
HIT_M. The null is the hit rate at shifts of 60 to 150 m. A real registration offset appears as a peak whose z-score against
that null is large. Objects are split by height (3 to 6 m, above 6 m) because tall objects lay over toward the radar.
Output: hit-rate grids per track and height class, the best shift, its z-score, and the hit rate at zero shift.

  NISAR_STACK=slc python _nisar_registration_points_9t.py
"""
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from scipy.ndimage import label, uniform_filter, center_of_mass, maximum
from scipy.spatial import cKDTree

import _nisar_feat_common as C

SEARCH_M, STEP_M, HIT_M = 40.0, 2.5, 7.5


def lidar_objects():
    with rasterio.open(C.A.lidar("chm")) as r:
        chm = r.read(1, masked=True).filled(0).astype(np.float32)
        tf = r.transform
    tall = chm > 3.0
    lab, n = label(tall)
    idx = np.arange(1, n + 1)
    area = np.bincount(lab.ravel(), minlength=n + 1)[1:]
    keep = idx[(area >= 6) & (area <= 150)]
    hmax = np.asarray(maximum(chm, lab, keep))
    com = np.array(center_of_mass(tall, lab, keep))
    frac = uniform_filter((chm > 2.0).astype(np.float32), 31)[com[:, 0].astype(int), com[:, 1].astype(int)]
    ok = frac < 0.25
    x, y = rasterio.transform.xy(tf, com[ok, 0], com[ok, 1])
    return pd.DataFrame(dict(x=np.array(x), y=np.array(y), hmax=hmax[ok], area=area[keep][ok]))


def hit_grid(obj_xy, tree, shifts):
    out = np.zeros(len(shifts))
    for i, (dx, dy) in enumerate(shifts):
        d, _ = tree.query(obj_xy + np.array([dx, dy]), distance_upper_bound=HIT_M)
        out[i] = np.isfinite(d).mean()
    return out


def main():
    objs = lidar_objects()
    print(f"lidar objects: {len(objs)} (height 3-6 m: {int((objs.hmax <= 6).sum())}, above 6 m: {int((objs.hmax > 6).sum())})", flush=True)
    pts = gpd.read_file(C.OUT / f"nisar_bright_targets_points_{C.A.TAG}.gpkg")
    pts = pts[pts.n_tracks == 1]
    g = np.arange(-SEARCH_M, SEARCH_M + 1e-6, STEP_M)
    shifts = np.array([(a, b) for a in g for b in g])
    rng = np.random.default_rng(20261027)
    ang = rng.uniform(0, 2 * np.pi, 400)
    rad = rng.uniform(60, 150, 400)
    null_shifts = np.c_[rad * np.cos(ang), rad * np.sin(ang)]
    rows = []
    grids = {}
    for t in (26, 90, 162):
        p = pts[pts.tracks.astype(str) == str(t)]
        xy = np.c_[p.geometry.x, p.geometry.y]
        tree = cKDTree(xy)
        for hc, m in (("3-6 m", objs.hmax <= 6), ("above 6 m", objs.hmax > 6), ("all", np.ones(len(objs), bool))):
            oxy = np.c_[objs.x[m], objs.y[m]]
            h = hit_grid(oxy, tree, shifts)
            nul = hit_grid(oxy, tree, null_shifts)
            z = (h - nul.mean()) / max(nul.std(ddof=1), 1e-9)
            k = int(np.argmax(z))
            zero = int(np.argmin(np.hypot(shifts[:, 0], shifts[:, 1])))
            rows.append(dict(track=t, objects=int(m.sum()), radar_points=len(xy), height_class=hc, null_hit_rate=round(nul.mean(), 4),
                             null_sd=round(nul.std(ddof=1), 4), zero_shift_hit_rate=round(h[zero], 4), zero_shift_z=round(z[zero], 2),
                             best_dx_m=shifts[k, 0], best_dy_m=shifts[k, 1], best_hit_rate=round(h[k], 4), best_z=round(z[k], 2)))
            grids[f"t{t}_{hc.replace(' ', '')}"] = h.reshape(len(g), len(g))
            print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(res.to_string(index=False))
    res.to_csv(C.OUT / f"nisar_registration_points_shift_{C.A.TAG}.csv", index=False)
    np.savez_compressed(C.OUT / f"nisar_registration_points_grids_{C.A.TAG}.npz", axis_m=g, **grids)


if __name__ == "__main__":
    main()
