"""Small-metal detection, first experiment: CFAR on Sentinel-1 mean intensity plus amplitude dispersion, against DEP wells.

Follows the "first experiment" of the SAR small-metal methodology note (user, 2026-11-12): one track, about 30
SLCs, CFAR on the stack mean intensity, then the steadiness test D_A, then the share of known wells that sit
within one resolution cell of a candidate. Here measured against random points and local decoys, by well status.

Data. OPERA CSLC-S1 V1 windows (VV), Sentinel-1A track 77 ascending, 32 dates 2025-04-03 to 2026-04-10 at
12 days, fetched by `_s1_cslc_window_fetch_9t.py --range 2025-04-01 2026-04-15 T077`. Window UTM 17N
E 613300-624200, N 4589800-4597700 (covers 9t and 613590).

Deviations from the note, and why.
  * No 2x oversampling. The geocoded CSLC spectrum already fills the band in both axes (5-95% of power at
    -0.45 to +0.45 cycles/pixel, with or without the azimuth carrier removed), so zero-padding cannot recover
    the pixel-fence loss. That needs radar-geometry IW SLCs. Peaks keep up to ~4 dB fence loss per axis.
  * No radiometric calibration. All dates share one track and geometry, and CFAR and D_A are ratios.
  * Water only is masked: pixels with mean intensity below WATER_FRAC x the window median (the Allegheny River),
    dilated by WATER_BUFFER_M. Water is left out of every background ring and no candidate may sit in the buffer.
    Without it, dark water in the ring makes ordinary bank pixels pass CFAR (first run: most of 569 candidates
    lined the river). Roads, buildings and other infrastructure are not masked; they cost precision, not recall.
  * Coregistration is OPERA's geocoding. Dates are cut to common pixels (whole-pixel shifts only).

CFAR. Resolution cell taken as 1 x 2.2 pixels (about 4.5 m ground range x 22 m azimuth; azimuth runs close to
grid north on this ascending track). Guard 3 x 3 cells = 3 x 7 pixels, background 15 x 15 cells = 15 x 33
pixels, both centred. SCR = mean intensity / mean of the background ring.
Threshold. Mean of N dates of speckle is Gamma with L looks. L is estimated as 1 / var(SCR) over the central
98% of pixels; T = Gamma(L, 1/L) inverse survival at P_fa 1e-6. A sweep of SCR thresholds is also reported.
Candidates are connected components of SCR > T; the peak pixel is the candidate, refined by a 3-point parabola.

D_A = std(A) / mean(A) over the 32 dates (ddof 1), per pixel.

Scoring. A well is hit when a candidate falls inside an ellipse of 10 m (x) by 20 m (y) around it: one cell in
range plus 5 m, half a cell in azimuth plus 9 m, for geocoding and DEP coordinate error. Baselines:
20,000 random points in the window, and one local decoy per well moved 150-600 m and kept 30 m from any well.

  python notebooks/wellsight_v2/s5_eval/_s1_metal_cfar_9t.py [--stack fullyear|april]
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from affine import Affine
from scipy import ndimage
from scipy.spatial import cKDTree
from scipy.stats import gamma

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
SRC = ROOT / "data" / "_source" / "s1_cslc_windows"
WELLS = ROOT / "data" / "_source" / "reference" / "dep_wells" / "venango_wells_all.gpkg"
OUT = ROOT / "data" / "9t" / "results" / "s1"
# --stack fullyear (default): 32 consecutive dates 2025-04-03 to 2026-04-10.
# --stack april: every April date on the track, 2017-2026 (22 dates, leaf-off, ten years).
STACK = sys.argv.pop(sys.argv.index("--stack") + 1) if "--stack" in sys.argv else "fullyear"
if "--stack" in sys.argv:
    sys.argv.remove("--stack")
if STACK not in ("fullyear", "april"):
    raise SystemExit(f"unknown --stack {STACK}")
TAG = f"{STACK}_9t613590"
D0, D1, TRACK = "2025-04-01", "2026-04-15", "T077"
GUARD = (3, 1)      # half-sizes in pixels (rows, cols): 7 x 3
BACK = (16, 7)      # 33 x 15
PFA = 1e-6
DA_MAX = 0.25
HIT_X, HIT_Y = 10.0, 20.0
SEED = 20261113
WATER_FRAC, WATER_BUFFER_M = 0.15, 30.0
# candidates #D97706 (orange, "+") and wells #1F5FA8 (blue, open circle): the lost/found pair, already
# validated in the repo with dataviz validate_palette.js --mode light --pairs all, worst pair dE 21.1 deutan,
# 22.6 normal. Marker shapes differ too, so colour is never the only cue. Background greyscale.
CAND_C, WELL_C, INK = "#D97706", "#1F5FA8", "#2B2F36"


def load():
    files = []
    for f in sorted(SRC.glob(f"OPERA_L2_CSLC-S1_{TRACK}-*.h5")):
        d = f.stem.split("_")[4]
        date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        if (date[5:7] == "04") if STACK == "april" else (D0 <= date <= D1):
            files.append((date, f))
    grids = []
    for date, f in files:
        with h5py.File(f, "r") as h:
            xs, ys = h["data/x_coordinates"][:], h["data/y_coordinates"][:]
            grids.append((xs[0], ys[0], len(xs), len(ys), float(h["data/x_spacing"][()]), float(h["data/y_spacing"][()])))
    dx, dy = grids[0][4], grids[0][5]
    x0 = max(g[0] for g in grids)
    x1 = min(g[0] + (g[2] - 1) * dx for g in grids)
    y0 = min(g[1] for g in grids)                      # top (dy < 0)
    y1 = max(g[1] + (g[3] - 1) * dy for g in grids)
    ncol, nrow = int(round((x1 - x0) / dx)) + 1, int(round((y1 - y0) / dy)) + 1
    s_i = np.zeros((nrow, ncol)); s_a = np.zeros((nrow, ncol)); s_a2 = np.zeros((nrow, ncol))
    n = np.zeros((nrow, ncol), np.int16)
    for (date, f), g in zip(files, grids):
        c0, r0 = (x0 - g[0]) / dx, (y0 - g[1]) / dy
        if abs(c0 - round(c0)) > 1e-6 or abs(r0 - round(r0)) > 1e-6:
            raise SystemExit(f"sub-pixel grid shift on {date}")
        c0, r0 = int(round(c0)), int(round(r0))
        with h5py.File(f, "r") as h:
            z = h["data/VV"][r0:r0 + nrow, c0:c0 + ncol]
        a = np.abs(z).astype(np.float64)
        ok = np.isfinite(a) & (a > 0)
        a = np.where(ok, a, 0)
        s_i += a * a; s_a += a; s_a2 += a * a; n += ok
    tf = Affine(dx, 0, x0 - dx / 2, 0, dy, y0 - dy / 2)
    full = n == len(files)
    mean_i = np.where(full, s_i / np.maximum(n, 1), np.nan)
    mu = s_a / np.maximum(n, 1)
    var = (s_a2 / np.maximum(n, 1) - mu ** 2) * n / np.maximum(n - 1, 1)
    da = np.where(full, np.sqrt(np.maximum(var, 0)) / np.where(mu > 0, mu, np.nan), np.nan)
    return [d for d, _ in files], tf, mean_i, da


def box_sum(a, hr, hc):
    """Sum over a (2hr+1) x (2hc+1) box centred on each pixel, zeros outside."""
    p = np.pad(a, ((hr + 1, hr), (hc + 1, hc)))
    c = p.cumsum(0).cumsum(1)
    r, k = 2 * hr + 1, 2 * hc + 1
    return c[r:, k:] - c[:-r, k:] - c[r:, :-k] + c[:-r, :-k]


def water_mask(mean_i):
    w = np.nan_to_num(mean_i, nan=np.inf) < WATER_FRAC * np.nanmedian(mean_i)
    w = ndimage.binary_opening(w, np.ones((3, 3)))          # drop single dark speckle pixels
    return w


def cfar_scr(mean_i, water):
    ok = np.isfinite(mean_i) & ~water
    v = np.where(ok, mean_i, 0)
    s = box_sum(v, *BACK) - box_sum(v, *GUARD)
    m = box_sum(ok.astype(float), *BACK) - box_sum(ok.astype(float), *GUARD)
    bg = np.where(m > 0.5 * ((2 * BACK[0] + 1) * (2 * BACK[1] + 1)), s / np.maximum(m, 1), np.nan)
    return np.where(ok, mean_i / bg, np.nan)


def candidates(scr, thr, tf):
    lab, n = ndimage.label(np.nan_to_num(scr) > thr, structure=np.ones((3, 3)))
    if n == 0:
        return pd.DataFrame(columns=["x", "y", "row", "col", "scr_db"])
    idx = ndimage.maximum_position(np.nan_to_num(scr), lab, range(1, n + 1))
    rows = []
    for r, c in idx:
        def para(a, b, cc):
            den = a - 2 * b + cc
            return 0.5 * (a - cc) / den if den != 0 else 0.0
        dr = para(scr[r - 1, c], scr[r, c], scr[r + 1, c]) if 0 < r < scr.shape[0] - 1 else 0.0
        dc = para(scr[r, c - 1], scr[r, c], scr[r, c + 1]) if 0 < c < scr.shape[1] - 1 else 0.0
        dr, dc = (np.clip(np.nan_to_num(dr), -0.5, 0.5), np.clip(np.nan_to_num(dc), -0.5, 0.5))
        x, y = tf * (c + 0.5 + dc, r + 0.5 + dr)
        rows.append(dict(x=x, y=y, row=r, col=c, scr_db=10 * np.log10(scr[r, c])))
    return pd.DataFrame(rows)


def hit(px, py, cx, cy):
    """For each point, is there a candidate inside the HIT_X x HIT_Y ellipse."""
    if len(cx) == 0:
        return np.zeros(len(px), bool)
    tree = cKDTree(np.c_[cx, cy / (HIT_Y / HIT_X)])
    d, _ = tree.query(np.c_[px, py / (HIT_Y / HIT_X)])
    return d <= HIT_X


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    dates, tf, mean_i, da = load()
    print(f"{len(dates)} dates {dates[0]} to {dates[-1]}, grid {mean_i.shape}")
    water = water_mask(mean_i)
    buf = ndimage.binary_dilation(water, np.ones((2 * int(WATER_BUFFER_M / 10) + 1, 2 * int(WATER_BUFFER_M / 5) + 1)))
    scr = cfar_scr(mean_i, water)
    scr[buf] = np.nan
    print(f"water {water.mean():.3%} of pixels, with buffer {buf.mean():.3%}")
    core = scr[np.isfinite(scr)]
    lo, hi = np.percentile(core, [1, 99])
    L = 1.0 / np.var(core[(core > lo) & (core < hi)])
    T = float(gamma.isf(PFA, L, scale=1 / L))
    print(f"ENL {L:.1f}, T {T:.3f} ({10*np.log10(T):.2f} dB) at P_fa {PFA}")

    W = gpd.read_file(WELLS).to_crs(32617)
    valid = np.isfinite(scr)
    inv = ~tf
    def inside(x, y):
        c, r = inv * (np.asarray(x), np.asarray(y))
        c, r = np.floor(c).astype(int), np.floor(r).astype(int)
        m = (r >= 0) & (r < scr.shape[0]) & (c >= 0) & (c < scr.shape[1])
        out = np.zeros(len(m), bool)
        out[m] = valid[r[m], c[m]]
        return out
    W = W[inside(W.geometry.x, W.geometry.y)].reset_index(drop=True)
    wx, wy = W.geometry.x.values, W.geometry.y.values
    status = W["WELL_STATU"].replace({"DEP Abandoned List": "Abandoned or orphan", "Abandoned": "Abandoned or orphan",
                                      "DEP Orphan List": "Abandoned or orphan", "Plugged OG Well": "Plugged",
                                      "DEP Plugged": "Plugged", "Plugged Unverified": "Plugged",
                                      "Operator Reported Not Drilled": "Never drilled",
                                      "Proposed But Never Materialized": "Never drilled"})
    # baselines
    x0, y1 = tf * (0, 0); x1, y0 = tf * (scr.shape[1], scr.shape[0])
    rx, ry = rng.uniform(x0, x1, 60000), rng.uniform(y0, y1, 60000)
    keep = inside(rx, ry)
    rx, ry = rx[keep][:20000], ry[keep][:20000]
    wtree = cKDTree(np.c_[wx, wy])
    dxs, dys = [], []
    for x, y in zip(wx, wy):
        for _ in range(50):
            ang, dist = rng.uniform(0, 2 * np.pi), rng.uniform(150, 600)
            qx, qy = x + dist * np.cos(ang), y + dist * np.sin(ang)
            if inside([qx], [qy])[0] and wtree.query([qx, qy])[0] > 30:
                break
        dxs.append(qx); dys.append(qy)
    dxs, dys = np.array(dxs), np.array(dys)

    def da_at(x, y):
        c, r = inv * (x, y)
        return da[np.floor(r).astype(int), np.floor(c).astype(int)]

    rows = []
    levels = [("P_fa 1e-6", T)] + [(f"{d} dB", 10 ** (d / 10)) for d in (3, 4, 5, 6, 8, 10)]
    cand_main = None
    for name, thr in levels:
        cand = candidates(scr, thr, tf)
        if len(cand):
            cand["da"] = da_at(cand.x.values, cand.y.values)
        steady = cand[cand.da < DA_MAX] if len(cand) else cand
        if name == "P_fa 1e-6":
            cand_main = cand
        for cname, cc in (("CFAR", cand), ("CFAR + D_A<0.25", steady)):
            cx, cy = (cc.x.values, cc.y.values) if len(cc) else (np.array([]), np.array([]))
            hw, hr, hd = hit(wx, wy, cx, cy), hit(rx, ry, cx, cy), hit(dxs, dys, cx, cy)
            row = dict(threshold=name, thr_db=round(10 * np.log10(thr), 2), test=cname, n_candidates=len(cc),
                       wells=round(hw.mean(), 4), random=round(hr.mean(), 4), local_decoys=round(hd.mean(), 4),
                       ratio_vs_random=round(hw.mean() / hr.mean(), 2) if hr.mean() > 0 else np.nan)
            for s in ("Active", "Plugged", "Abandoned or orphan", "Never drilled"):
                m = (status == s).values
                row[f"{s} (n={m.sum()})"] = round(hw[m].mean(), 4)
            rows.append(row)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / f"s1_metal_cfar_hit_rates_{TAG}.csv", index=False)
    with pd.option_context("display.width", 250):
        print(res.to_string())

    # per-well table at the main threshold
    cx, cy = cand_main.x.values, cand_main.y.values
    st = cand_main[cand_main.da < DA_MAX]
    W["status_group"] = status.values
    W["cfar_hit"] = hit(wx, wy, cx, cy)
    W["cfar_da_hit"] = hit(wx, wy, st.x.values, st.y.values)
    W["da_at_well"] = da_at(wx, wy)
    W["scr_db_at_well"] = 10 * np.log10(scr[np.floor((inv * (wx, wy))[1]).astype(int), np.floor((inv * (wx, wy))[0]).astype(int)])
    W[["PERMIT_NUM", "WELL_STATU", "status_group", "cfar_hit", "cfar_da_hit", "da_at_well", "scr_db_at_well", "geometry"]] \
        .to_file(OUT / f"s1_metal_cfar_wells_{TAG}.gpkg", driver="GPKG")
    cg = gpd.GeoDataFrame(cand_main, geometry=gpd.points_from_xy(cand_main.x, cand_main.y), crs=32617)
    cg["steady"] = cg.da < DA_MAX
    cg.to_file(OUT / f"s1_metal_cfar_candidates_{TAG}.gpkg", driver="GPKG")

    summary = dict(dates=len(dates), first=dates[0], last=dates[-1], track="Sentinel-1A T077 ascending, VV",
                   grid_px=list(mean_i.shape), enl=round(L, 2), threshold_scr=round(T, 3),
                   threshold_db=round(10 * np.log10(T), 2), pfa=PFA, n_candidates=int(len(cand_main)),
                   n_steady=int((cand_main.da < DA_MAX).sum()), wells=int(len(W)),
                   hit_ellipse_m=[HIT_X, HIT_Y], guard_px=GUARD, background_px=BACK,
                   speckle_da_median=round(float(np.nanmedian(da)), 3),
                   share_pixels_da_lt_0p25=round(float(np.nanmean(da < DA_MAX)), 5),
                   water_share=round(float(water.mean()), 4), water_buffer_share=round(float(buf.mean()), 4),
                   wells_in_water_buffer_dropped=True)
    json.dump(summary, open(OUT / f"s1_metal_cfar_summary_{TAG}.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))

    # figure: overview and a 1 km zoom on the densest active-well cell
    amp_db = 10 * np.log10(mean_i)
    vmin, vmax = np.nanpercentile(amp_db, [2, 99.5])
    act = W[W.status_group == "Active"]
    H, xe, ye = np.histogram2d(act.geometry.x, act.geometry.y, bins=[np.arange(x0, x1, 1000), np.arange(y0, y1, 1000)])
    i, j = np.unravel_index(H.argmax(), H.shape)
    zx, zy = xe[i], ye[j]
    fig, axs = plt.subplots(1, 2, figsize=(13, 6.2), gridspec_kw=dict(width_ratios=[1.45, 1]))
    ext = (x0, x1, y0, y1)
    for ax, lim in ((axs[0], None), (axs[1], (zx, zx + 1000, zy, zy + 1000))):
        ax.imshow(amp_db, cmap="gray", vmin=vmin, vmax=vmax, extent=ext, interpolation="nearest")
        ms = 4 if lim is None else 30
        ax.scatter(wx, wy, s=ms, facecolors="none", edgecolors=WELL_C, linewidths=0.6 if lim is None else 1.2,
                   label=f"DEP wells ({len(W)})")
        ax.scatter(cx, cy, s=ms * 2, marker="+", color=CAND_C, linewidths=0.8 if lim is None else 1.6,
                   label=f"CFAR candidates, P_fa 1e-6 ({len(cx)})")
        if lim:
            ax.set_xlim(lim[0], lim[1]); ax.set_ylim(lim[2], lim[3])
            ax.set_title("1 km zoom, densest active-well cell", fontsize=10, color=INK)
        else:
            ax.add_patch(plt.Rectangle((zx, zy), 1000, 1000, fill=False, ec=CAND_C, lw=1))
            ax.set_title(f"Mean VV amplitude, {len(dates)} dates", fontsize=10, color=INK)
        ax.set_xticks([]); ax.set_yticks([])
    axs[0].legend(loc="lower left", fontsize=8, framealpha=0.9)
    fig.suptitle(f"Sentinel-1 track 77, {dates[0]} to {dates[-1]} ({STACK}, {len(dates)} dates): bright-target candidates against DEP wells", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(OUT / f"s1_metal_cfar_map_{TAG}.png", dpi=170)


if __name__ == "__main__":
    main()
