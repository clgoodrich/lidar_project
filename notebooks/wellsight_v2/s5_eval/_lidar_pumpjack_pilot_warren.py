"""Pumpjack pilot on the Warren/Sheffield 2019 lidar: what does a well pad look like in the points?

Wells: DEP live layer, active, type OIL or COMB. OIL&GAS, spud 1980-2015 (so they stood in 2019),
inside the seven tiles in data/_source/lidar/warren_sheffield/ and 70 m from a tile edge.
Query saved by the caller as swath_wells.json (DEP OG_Well_Data layer 0, outSR 26917).

Per well: points in a 120 m box, height above ground (HAG) from the class-2 ground by linear
interpolation. Output: per-well clips (npz) and a contact sheet of top-down max-HAG and mean
intensity of non-ground points, to see by eye whether a compact object sits at the DEP point
before any detector is written. DEP positions can be tens of metres off, so the box is wide.

  python notebooks/wellsight_v2/s5_eval/_lidar_pumpjack_pilot_warren.py <wells.json> [n_wells]
"""
import datetime as dt
import glob
import json
import sys
from pathlib import Path

import laspy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import LinearNDInterpolator

ROOT = Path(__file__).resolve().parents[3]
import os
TILES = Path(os.environ.get("PJ_TILES", ROOT / "data/_source/lidar/warren_sheffield"))
TAG = os.environ.get("PJ_TAG", "warren")
PAT = os.environ.get("PJ_PAT", "*.laz")
OUT = ROOT / "data" / TAG / "derived/pumpjack_pilot"
RES = ROOT / "data" / TAG / "results/pumpjack"
HALF, EDGE, SEED = 60.0, 70.0, 20261021


def yr(ms):
    return None if ms is None else (dt.datetime(1970, 1, 1) + dt.timedelta(milliseconds=ms)).year


def pick(path, n):
    fs = json.load(open(path))
    rows = []
    for f in fs:
        a, g = f["attributes"], f["geometry"]
        y = yr(a["SPUD_DATE"])
        if a["WELL_STATUS"] == "Active" and a["WELL_TYPE"] in ("OIL", "COMB. OIL&GAS") and y and 1980 <= y <= 2015:
            rows.append(dict(permit=a["PERMIT_NUMBER"], x=g["x"], y=g["y"], spud=y, wtype=a["WELL_TYPE"]))
    rng = np.random.default_rng(SEED)
    return [rows[i] for i in rng.permutation(len(rows))][:n * 3]


def tile_of(x, y):
    return f"17TPG{int((x - 649500) // 1500) * 0 + int(x // 1500 * 1500 // 1000 * 0)}"  # placeholder, replaced below


def main():
    wells_json, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 12
    cand = pick(wells_json, n)
    tiles = {}
    for f in glob.glob(str(TILES / PAT)):
        h = laspy.open(f).header
        tiles[f] = (h.mins[0], h.mins[1], h.maxs[0], h.maxs[1])
    chosen = []
    for w in cand:
        for f, (x0, y0, x1, y1) in tiles.items():
            if x0 + EDGE < w["x"] < x1 - EDGE and y0 + EDGE < w["y"] < y1 - EDGE:
                w["tile"] = f
                chosen.append(w)
                break
        if len(chosen) == n:
            break
    print(len(chosen), "wells chosen")
    cache = {}
    fig, axs = plt.subplots(3, 8, figsize=(32, 12))
    for i, w in enumerate(chosen):
        if w["tile"] not in cache:
            cache.clear()
            las = laspy.read(w["tile"])
            cache[w["tile"]] = (np.asarray(las.x), np.asarray(las.y), np.asarray(las.z),
                                np.asarray(las.intensity), np.asarray(las.classification), np.asarray(las.return_number))
        X, Y, Z, I, C, R = cache[w["tile"]]
        m = (abs(X - w["x"]) <= HALF + 20) & (abs(Y - w["y"]) <= HALF + 20)
        x, y, z, it, c = X[m], Y[m], Z[m], I[m], C[m]
        g = c == 2
        interp = LinearNDInterpolator(np.c_[x[g], y[g]], z[g])
        hag = z - interp(np.c_[x, y])
        keep = np.isfinite(hag) & (abs(x - w["x"]) <= HALF) & (abs(y - w["y"]) <= HALF)
        x, y, hag, it, c = x[keep], y[keep], hag[keep], it[keep], c[keep]
        np.savez_compressed(OUT / f"clip_{w['permit'].replace('-', '_')}.npz", x=x - w["x"], y=y - w["y"], hag=hag, intensity=it, cls=c)
        ng = c != 2
        e = np.arange(-HALF, HALF + 1, 1.0)
        ix, iy = np.digitize(x - w["x"], e) - 1, np.digitize(y - w["y"], e) - 1
        mx = np.full((len(e) - 1,) * 2, np.nan)
        mi = np.full_like(mx, np.nan)
        for k in np.flatnonzero(ng & (hag > 0.5)):
            if 0 <= ix[k] < 120 and 0 <= iy[k] < 120:
                a, b = iy[k], ix[k]
                mx[a, b] = hag[k] if np.isnan(mx[a, b]) else max(mx[a, b], hag[k])
        cnt = np.zeros_like(mx)
        sm = np.zeros_like(mx)
        for k in np.flatnonzero(ng & (hag > 0.5)):
            if 0 <= ix[k] < 120 and 0 <= iy[k] < 120:
                cnt[iy[k], ix[k]] += 1
                sm[iy[k], ix[k]] += it[k]
        mi = np.where(cnt > 0, sm / np.maximum(cnt, 1), np.nan)
        r, col = divmod(i, 8)
        ext = [-HALF, HALF, -HALF, HALF]
        a0 = axs[0, col] if i < 8 else None
        for row, (img, cm, lab, vmax) in enumerate([(mx, "viridis", "max HAG m", 20), (mi, "magma", "mean intensity", None)]):
            pass
        if i < 8:
            ax = axs[0, i]
            ax.imshow(mx, origin="lower", extent=ext, cmap="viridis", vmin=0, vmax=15)
            ax.plot(0, 0, "w+", ms=14)
            ax.set_title(f"{w['permit']} spud {w['spud']}\nmax HAG (m)", fontsize=9)
            ax = axs[1, i]
            ax.imshow(mi, origin="lower", extent=ext, cmap="magma", vmin=np.nanpercentile(mi, 2), vmax=np.nanpercentile(mi, 98))
            ax.plot(0, 0, "c+", ms=14)
            ax.set_title("mean intensity, non-ground", fontsize=9)
            ax = axs[2, i]
            near = (abs(x - w["x"] + w["x"]) < 1e9)
            xs = x - w["x"]
            ys = hag
            sel = ng & (abs(y - w["y"]) < 15)
            ax.scatter(xs[sel], ys[sel], s=2, c=it[sel], cmap="magma", vmin=np.percentile(it, 2), vmax=np.percentile(it, 98))
            ax.axvline(0, color="grey", lw=0.5)
            ax.set_ylim(-1, 20)
            ax.set_title("side view, +/-15 m N-S, x = E-W", fontsize=9)
    plt.tight_layout()
    RES.mkdir(parents=True, exist_ok=True)
    out = RES / f"pumpjack_pilot_contact_sheet_{TAG}.png"
    plt.savefig(out, dpi=70)
    print("wrote", out)
    json.dump(chosen, open(RES / f"pumpjack_pilot_wells_{TAG}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
