"""Bright compact object near DEP oil wells vs random control points, Warren/Sheffield 2019 lidar.

Pilot (_lidar_pumpjack_pilot_warren.py) saw one pad with objects ~6x canopy intensity. This scales it.
Wells: active OIL / COMB. OIL&GAS, spud 1980-2015, N_WELLS sampled; controls: N_CTRL random points
150-400 m from a random DEP well and >= 150 m from every DEP well in the query. Both need 70 m clearance from the tile edge. Controls are drawn 150-400 m from a random well, so they
share its setting; uniform random points fell in Warren town and scored higher (first run: wells 37%
vs controls 57% with a bright compact object, p 0.007; this product has no building class to filter).
Per point, inside R_M = 40 m: non-ground returns 2-7 m above ground (HAG from class-2 ground by
linear interpolation), in 1 m cells with no return above 8 m in the cell. Connected cells
(8-neighbour) of 6-120 cells are "compact objects". An object is "bright" when its median
intensity >= BRIGHT_X times the median intensity of >8 m returns in the 120 m box.
Tests: Fisher exact on share of points with a bright compact object; Mann-Whitney on the ratio.

  python notebooks/wellsight_v2/s5_eval/_lidar_pumpjack_metrics_warren.py <wells.json>
"""
import datetime as dt
import glob
import json
import sys
from pathlib import Path

import laspy
import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator
from scipy.ndimage import label
from scipy.stats import fisher_exact, mannwhitneyu

ROOT = Path(__file__).resolve().parents[3]
TILES = ROOT / "data/_source/lidar/warren_sheffield"
RES = ROOT / "data/warren/results/pumpjack"
HALF, EDGE, R_M, BRIGHT_X, N_WELLS, N_CTRL, SEED = 60.0, 70.0, 40.0, 2.0, 100, 100, 20261022


def yr(ms):
    return None if ms is None else (dt.datetime(1970, 1, 1) + dt.timedelta(milliseconds=ms)).year


def metrics(x, y, z, it, c, px, py):
    m = (abs(x - px) <= HALF + 20) & (abs(y - py) <= HALF + 20)
    x, y, z, it, c = x[m], y[m], z[m], it[m], c[m]
    g = c == 2
    if g.sum() < 50:
        return None
    hag = z - LinearNDInterpolator(np.c_[x[g], y[g]], z[g])(np.c_[x, y])
    k = np.isfinite(hag) & (abs(x - px) <= HALF) & (abs(y - py) <= HALF)
    x, y, hag, it, c = x[k] - px, y[k] - py, hag[k], it[k], c[k]
    ng = c != 2
    can = ng & (hag > 8)
    low = ng & (hag > 2) & (hag < 7) & (np.hypot(x, y) < R_M)
    if can.sum() < 30 or low.sum() == 0:
        return dict(n_obj=0, n_bright=0, max_ratio=np.nan, low_ratio=np.nan, can_n=int(can.sum()))
    ci = np.median(it[can])
    ix, iy = np.floor(x + HALF).astype(int), np.floor(y + HALF).astype(int)
    ok = (ix >= 0) & (ix < 120) & (iy >= 0) & (iy < 120)
    G = np.zeros((120, 120), bool)
    Cn = np.zeros((120, 120), bool)
    G[iy[low & ok], ix[low & ok]] = True
    Cn[iy[can & ok], ix[can & ok]] = True
    G &= ~Cn
    lab, n = label(G, structure=np.ones((3, 3)))
    ratios = []
    for q in range(1, n + 1):
        cells = lab == q
        if 6 <= cells.sum() <= 120:
            sel = low & ok & cells[np.clip(iy, 0, 119), np.clip(ix, 0, 119)]
            ratios.append(np.median(it[sel]) / ci)
    return dict(n_obj=len(ratios), n_bright=int(sum(r >= BRIGHT_X for r in ratios)),
                max_ratio=max(ratios) if ratios else np.nan, low_ratio=np.median(it[low]) / ci, can_n=int(can.sum()))


def main():
    fs = json.load(open(sys.argv[1]))
    allw = np.array([[f["geometry"]["x"], f["geometry"]["y"]] for f in fs])
    wells = [dict(permit=f["attributes"]["PERMIT_NUMBER"], x=f["geometry"]["x"], y=f["geometry"]["y"])
             for f in fs if f["attributes"]["WELL_STATUS"] == "Active"
             and f["attributes"]["WELL_TYPE"] in ("OIL", "COMB. OIL&GAS")
             and (yr(f["attributes"]["SPUD_DATE"]) or 0) in range(1980, 2016)]
    rng = np.random.default_rng(SEED)
    wells = [wells[i] for i in rng.permutation(len(wells))]
    tiles = {f: laspy.open(f).header for f in glob.glob(str(TILES / "*.laz"))}
    pts = [dict(kind="well", **w) for w in wells[:N_WELLS * 2]]
    while sum(p["kind"] == "ctrl" for p in pts) < N_CTRL * 2:
        a = allw[rng.integers(len(allw))]
        r_, th = rng.uniform(150, 400), rng.uniform(0, 2 * np.pi)
        x, y = a[0] + r_ * np.cos(th), a[1] + r_ * np.sin(th)
        if np.hypot(allw[:, 0] - x, allw[:, 1] - y).min() >= 150:
            pts.append(dict(kind="ctrl", permit="", x=x, y=y))
    for p in pts:
        p["tile"] = next((f for f, h in tiles.items() if h.mins[0] + EDGE < p["x"] < h.maxs[0] - EDGE
                          and h.mins[1] + EDGE < p["y"] < h.maxs[1] - EDGE), None)
    rows = []
    for f in tiles:
        sub = [p for p in pts if p["tile"] == f]
        if not sub:
            continue
        las = laspy.read(f)
        X, Y, Z, I, C = (np.asarray(las.x), np.asarray(las.y), np.asarray(las.z), np.asarray(las.intensity),
                         np.asarray(las.classification))
        for p in sub:
            r = metrics(X, Y, Z, I, C, p["x"], p["y"])
            if r:
                rows.append(dict(kind=p["kind"], permit=p["permit"], x=p["x"], y=p["y"], **r))
        print(Path(f).name, len(sub), flush=True)
    df = pd.DataFrame(rows)
    df = pd.concat([df[df.kind == k].head(N_WELLS if k == "well" else N_CTRL) for k in ("well", "ctrl")])
    RES.mkdir(parents=True, exist_ok=True)
    df.to_csv(RES / "pumpjack_metrics_per_point_warren.csv", index=False)
    w, c = df[df.kind == "well"], df[df.kind == "ctrl"]
    hw, hc = (w.n_bright >= 1), (c.n_bright >= 1)
    orr, p = fisher_exact([[hw.sum(), (~hw).sum()], [hc.sum(), (~hc).sum()]])
    pm = mannwhitneyu(w.max_ratio.dropna(), c.max_ratio.dropna()).pvalue
    out = dict(n_wells=len(w), n_ctrl=len(c), bright_x=BRIGHT_X, r_m=R_M, wells_with_bright=int(hw.sum()),
               ctrl_with_bright=int(hc.sum()), share_wells=round(hw.mean(), 3), share_ctrl=round(hc.mean(), 3),
               odds_ratio=round(orr, 2), p_fisher=float(f"{p:.2g}"), median_max_ratio_wells=float(w.max_ratio.median()),
               median_max_ratio_ctrl=float(c.max_ratio.median()), p_mwu_max_ratio=float(f"{pm:.2g}"))
    json.dump(out, open(RES / "pumpjack_metrics_summary_warren.json", "w"), indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
