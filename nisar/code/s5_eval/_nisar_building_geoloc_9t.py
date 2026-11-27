"""Radar placement checked against lidar building walls, 9t. Set 2026-11-26 (secondary analysis, Track 2A).

Why
  The placement of the lidar-placed SLC stack has never been checked against an independent point.
  Buildings are the best stand-in for corner reflectors on 9t. A wall and the ground make a
  dihedral, so the brightest return sits at the foot of the wall that faces the radar.
  NISAR looks left. Track 26 (descending) looks east, so it lights the WEST wall.
  Tracks 90 and 162 (ascending) look west, so they light the EAST wall.
  If placement is right, the descending peak sits near the west wall and the ascending peak near
  the east wall, and both sit at the building's north-south centre.

Method
  1. Building footprint from lidar: DSM minus DEM above 2.5 m, the connected patch nearest the
     NAIP-confirmed point (9 buildings, nisar_top_targets_naip_classes_9t.csv). Moved into the
     radar frame with the same datum shift the tests use (_nisar_area.radar_shift).
  2. Radar peak: mean HH power over all dates of a track, brightest pixel within 15 m of the
     footprint centroid, refined by a 3-point parabola in x and y (sub-pixel).
  3. Error east-west = peak x minus the lit wall's x. Error north-south = peak y minus centroid y.
  The same is reported with no datum shift, to show which frame fits.

Output
  nisar/results/9t/nisar_building_geoloc_per_building_9t_slc.csv
  nisar/results/9t/nisar_building_geoloc_summary_9t_slc.json

Run
  python nisar/code/s5_eval/_nisar_building_geoloc_9t.py --slc
"""
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
ifg = importlib.import_module("_nisar_gslc_interferogram_pits_9t")
st = ifg.st
A = importlib.import_module("_nisar_area")
OUT = st.OUT
D1 = A.NISAR_ROOT.parent / "data" / "9t" / "derived" / "1m"
LIT_WALL = {26: "west", 90: "east", 162: "east"}  # left-looking: descending looks east, ascending west
SEARCH_M = 15.0
ND_MIN = 2.5


def footprint(x, y, dsm, dem):
    """Connected nDSM > 2.5 m patch nearest (x, y) in the lidar frame; None if outside the tile."""
    b = dsm.bounds
    if not (b.left + 30 < x < b.right - 30 and b.bottom + 30 < y < b.top - 30):
        return None
    w = from_bounds(x - 30, y - 30, x + 30, y + 30, dsm.transform).round_offsets().round_lengths()
    s, g = dsm.read(1, window=w).astype(float), dem.read(1, window=w).astype(float)
    nd = np.where((s > -9000) & (g > -9000), s - g, 0)
    lab, n = ndimage.label(nd > ND_MIN)
    if n == 0:
        return None
    tf = dsm.window_transform(w)
    rr, cc = np.indices(lab.shape)
    X, Y = tf.c + (cc + 0.5) * tf.a, tf.f + (rr + 0.5) * tf.e
    d = np.where(lab > 0, np.hypot(X - x, Y - y), np.inf)
    k = lab.flat[np.argmin(d)]
    m = lab == k
    return dict(cx=X[m].mean(), cy=Y[m].mean(), west=X[m].min() - 0.5, east=X[m].max() + 0.5,
                area_m2=int(m.sum()), height_m=float(np.percentile(nd[m], 90)), near_m=float(d.min()))


def subpix(v, i):
    """3-point parabola vertex offset in pixels around index i of 1-D array v."""
    if i <= 0 or i >= len(v) - 1:
        return 0.0
    a, b, c = v[i - 1], v[i], v[i + 1]
    den = a - 2 * b + c
    return 0.0 if den >= 0 else float(np.clip(0.5 * (a - c) / den, -0.5, 0.5))


def main():
    idx, stack, tf, shape = ifg.load_complex()
    mean_db = {}
    for t, g in idx.groupby("track"):
        p = np.mean([np.abs(stack[f][0]).astype(np.float64) ** 2 for f in g.file], axis=0)
        mean_db[int(t)] = 10 * np.log10(np.where(p > 0, p, np.nan))
    b = pd.read_csv(OUT / "nisar_top_targets_naip_classes_9t.csv")
    b = b[b["class"] == "building"].reset_index(drop=True)
    dsm, dem = rasterio.open(D1 / "dsm_9t_1m.tif"), rasterio.open(D1 / "dem_9t_1m.tif")
    rows = []
    for r in b.itertuples():
        dx, dy = A.radar_shift(r.x, r.y)
        fp = footprint(r.x - dx, r.y - dy, dsm, dem)  # NAIP points are in the radar frame
        if fp is None:
            rows.append(dict(chip=r.chip, status="outside lidar tile or no patch"))
            continue
        for frame, sx, sy in (("shifted", dx, dy), ("no_shift", 0.0, 0.0)):
            cx, cy = fp["cx"] + sx, fp["cy"] + sy
            wall = {"west": fp["west"] + sx, "east": fp["east"] + sx}
            for t, img in mean_db.items():
                c0, r0 = int((cx - tf.c) // tf.a), int((cy - tf.f) // tf.e)
                h = int(np.ceil(SEARCH_M / tf.a))
                chip = img[r0 - h:r0 + h + 1, c0 - h:c0 + h + 1]
                if chip.size == 0 or not np.isfinite(chip).any():
                    continue
                i, j = np.unravel_index(np.nanargmax(chip), chip.shape)
                px = tf.c + (c0 - h + j + 0.5 + subpix(chip[i], j)) * tf.a
                py = tf.f + (r0 - h + i + 0.5 + subpix(chip[:, j], i)) * tf.e
                rows.append(dict(chip=r.chip, status="ok", frame=frame, track=t, lit_wall=LIT_WALL[t],
                                 area_m2=fp["area_m2"], height_m=round(fp["height_m"], 1),
                                 width_ew_m=round(fp["east"] - fp["west"], 1), near_m=round(fp["near_m"], 1),
                                 peak_db=round(float(chip[i, j]), 1),
                                 err_ew_m=round(px - wall[LIT_WALL[t]], 2), err_ns_m=round(py - cy, 2),
                                 err_ew_centroid_m=round(px - cx, 2)))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "nisar_building_geoloc_per_building_9t_slc.csv", index=False)
    ok = df[df.status == "ok"]
    summ = {}
    for (frame, t), g in ok.groupby(["frame", "track"]):
        summ[f"{frame}_t{t}"] = dict(n=len(g), median_err_ew_m=round(float(g.err_ew_m.median()), 2),
                                     median_err_ns_m=round(float(g.err_ns_m.median()), 2),
                                     median_abs_ew_m=round(float(g.err_ew_m.abs().median()), 2),
                                     median_abs_ns_m=round(float(g.err_ns_m.abs().median()), 2))
    for frame, g in ok.groupby("frame"):
        summ[f"{frame}_all"] = dict(n=len(g), rms_ew_m=round(float(np.sqrt((g.err_ew_m ** 2).mean())), 2),
                                    rms_ns_m=round(float(np.sqrt((g.err_ns_m ** 2).mean())), 2))
    out = dict(params=dict(search_m=SEARCH_M, ndsm_min_m=ND_MIN, pixel_m=float(tf.a), lit_wall=LIT_WALL),
               n_buildings=int(len(b)), n_in_lidar=int(ok.chip.nunique()),
               skipped=df[df.status != "ok"].chip.tolist(), summary=summ)
    (OUT / "nisar_building_geoloc_summary_9t_slc.json").write_text(json.dumps(out, indent=1))
    print(ok[ok.frame == "shifted"].to_string())
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
