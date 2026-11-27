"""Branch 2 steel screen at lidar pads, 9t. Set 2026-11-27 (secondary analysis, Track 2C).

Why
  The baseline screen (_nisar_steel_pads_9t.py) passes ~17% of control spots, so a 3-6% hardware rate
  has no power. It also pools tracks, matches controls on canopy only, and uses a pooled Fisher test
  although pad classes get different numbers of controls. This version keeps the baseline untouched
  and changes five things, each reported separately so its effect is visible.

Changes
  1. Controls matched on canopy (within 0.15) AND mean lidar slope (within 5 degrees). 5 per pad.
  2. Each track scored on its own, plus any-track. Track 162 (47 deg) is not pooled blindly.
  3. Variants of the per-pixel screen:
       raw    baseline rule (D_A < 0.25, brightness >= 3 robust SD over the 250 m median), dates scaled
       flat   brightness from terrain-flattened amplitude (divided by sqrt of the lidar-simulated area
              factor); shadow/layover cells dropped. Removes bright fore-slopes.
       pol    flat rule AND co/cross ratio HH/HV above the tile's 90th percentile. Metal dihedrals are
              HH-strong; forest volume raises HV.
  4. Continuous composite per pixel: robust z of flat brightness - z of D_A + z of HH/HV ratio
     + z of HH-HV multi-date coherence |sum HH HV*| / sqrt(sum|HH|^2 sum|HV|^2) (single pixel,
     across dates; volume is random, canonical scatterers are stable). Site score = max inside.
  5. Tests: matched swap test (each pad and its 5 controls exchangeable; null by drawing one of six),
     Cochran-Mantel-Haenszel over size x canopy strata, AUC, and top-K share of pads.
  Bonferroni count is reported with every table.

Outputs (Branch 2 folder, baseline untouched)
  nisar/results/9t/v2/nisar_steel_pads_v2_tests_9t_slc.csv
  nisar/results/9t/v2/nisar_steel_pads_v2_summary_9t_slc.json
  nisar/results/9t/v2/nisar_steel_pads_v2_units_9t_slc.csv   (every pad and control, per-track scores)

Run
  python nisar/code/s5_eval/_nisar_steel_pads_v2_9t.py --slc
"""
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
from scipy.ndimage import median_filter
from scipy.stats import chi2, mannwhitneyu
from shapely.affinity import translate

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _nisar_steel_9t as S  # noqa: E402
import _nisar_steel_pads_9t as P  # noqa: E402
fl = importlib.import_module("_nisar_flatten_gain_test_9t")

OUT = S.OUT / "v2"
OUT.mkdir(parents=True, exist_ok=True)
BUF_M, N_CTRL, SEED, N_PERM = 5.0, 5, 20261127, 20000
SLOPE_MATCH, COVER_MATCH = 5.0, 0.15
SLOPE = S.AREA.NISAR_ROOT.parent / "data" / "9t" / "derived" / "1m" / "slope_9t_1m.tif"


def slope_grid(tf, shape):
    """Mean lidar slope (deg) per 5 m pixel, lidar frame moved onto the radar grid."""
    dx, dy = S.AREA.radar_shift(tf.c + shape[1] * 2.5, tf.f - shape[0] * 2.5)
    with rasterio.open(SLOPE) as r:
        a = r.read(1, masked=True)
        src = np.where(a.mask, np.nan, a.filled(0)).astype(np.float32)
        dst = np.full(shape, np.nan, np.float32)
        t = rasterio.Affine(tf.a, 0, tf.c - dx, 0, tf.e, tf.f - dy)  # radar pixel -> lidar frame
        reproject(src, dst, src_transform=r.transform, src_crs=r.crs, src_nodata=np.nan,
                  dst_transform=t, dst_crs=r.crs, dst_nodata=np.nan, resampling=Resampling.average)
    return dst


def rz(x, ok):
    v = x[ok & np.isfinite(x)]
    med = np.median(v)
    return (x - med) / (1.4826 * np.median(np.abs(v - med)))


def track_layers(g, stack, tf, shape):
    hh = np.stack([stack[f][0] for f in g.file]).astype(np.complex64)
    hv = np.stack([stack[f][1] for f in g.file]).astype(np.complex64)
    A, B = np.abs(hh), np.abs(hv)
    ok = np.all(np.isfinite(A) & (A > 0) & np.isfinite(B) & (B > 0), axis=0)
    for X in (A, B):
        med = np.array([np.median(a[ok]) for a in X], np.float32)
        X *= (np.median(med) / med)[:, None, None]
    mA = A.mean(0)
    da = A.std(0, ddof=1) / np.where(mA > 0, mA, np.nan)
    k = int(S.BG_M / 5) | 1

    def bright_of(p):
        mdb = 10 * np.log10(np.where(ok, p, np.nan))
        return mdb - median_filter(np.where(ok, mdb, np.nanmedian(mdb)), size=k)
    p_hh = (A ** 2).mean(0)
    bright_raw = bright_of(p_hh)
    af, fok = fl.sim_layers(int(g.track.iloc[0]), tf, shape)
    okf = ok & fok
    bright_flat = bright_of(np.where(okf, p_hh / af, np.nan))
    ratio = 10 * np.log10(p_hh / np.where(ok, (B ** 2).mean(0), np.nan))
    cross = np.abs((hh * np.conj(hv)).sum(0)) / np.sqrt((np.abs(hh) ** 2).sum(0) * (np.abs(hv) ** 2).sum(0))
    cut = lambda b, m: S.BRIGHT_SD * 1.4826 * float(np.median(np.abs(b[m] - np.median(b[m]))))
    c_raw, c_flat = cut(bright_raw, ok & np.isfinite(bright_raw)), cut(bright_flat, okf & np.isfinite(bright_flat))
    r90 = float(np.percentile(ratio[okf & np.isfinite(ratio)], 90))
    raw = ok & (da < S.DA_MAX) & (bright_raw >= c_raw)
    flat = okf & (da < S.DA_MAX) & (bright_flat >= c_flat)
    pol = flat & (ratio >= r90)
    comp = rz(bright_flat, okf) - rz(da, okf) + rz(ratio, okf) + rz(cross.astype(np.float32), okf)
    info = dict(n_dates=len(g), cut_raw_db=round(c_raw, 2), cut_flat_db=round(c_flat, 2), ratio_p90_db=round(r90, 2),
                pass_raw=round(float(raw[ok].mean()), 5), pass_flat=round(float(flat[okf].mean()), 5),
                pass_pol=round(float(pol[okf].mean()), 5), valid_flat_share=round(float(okf.sum() / ok.sum()), 3))
    return dict(ok=okf, raw=raw, flat=flat, pol=pol, comp=np.where(okf, comp, np.nan)), info


def swap_p(x, n_ctrl=N_CTRL, rng=None):
    """x: array (n_sets, 1 + n_ctrl), column 0 the pad. One-sided p that pads exceed their controls."""
    obs = x[:, 0].sum()
    pick = rng.integers(0, 1 + n_ctrl, size=(N_PERM, len(x)))
    null = x[np.arange(len(x))[None, :], pick].sum(1)
    return float((1 + (null >= obs).sum()) / (N_PERM + 1))


def cmh(units, col):
    """Cochran-Mantel-Haenszel (no continuity correction) over strata; pad vs control, hit vs not."""
    num = var = 0.0
    a_sum = e_sum = 0.0
    for _, g in units.groupby("stratum"):
        a = int(((g.is_pad == 1) & (g[col] > 0)).sum())
        n1, n0 = int((g.is_pad == 1).sum()), int((g.is_pad == 0).sum())
        m1 = int((g[col] > 0).sum())
        n = n1 + n0
        if n < 2 or m1 in (0, n):
            continue
        a_sum += a
        e_sum += n1 * m1 / n
        var += n1 * n0 * m1 * (n - m1) / (n ** 2 * (n - 1))
    if var == 0:
        return np.nan, np.nan
    stat = (a_sum - e_sum) ** 2 / var
    return round(float(stat), 2), float(f"{chi2.sf(stat, 1):.3g}")


def main():
    rng = np.random.default_rng(SEED)
    idx, stack, tf, shape = S.ifg.load_complex()
    cover = S.st.canopy_cover(tf, shape)
    slope = slope_grid(tf, shape)
    layers, info = {}, {}
    for t, g in idx.groupby("track"):
        layers[int(t)], info[int(t)] = track_layers(g, stack, tf, shape)
        print(t, info[int(t)], flush=True)
    for t, L in layers.items():  # sub-look coherence from _nisar_sublook_9t.py, if it has been run
        sp = S.AREA.NISAR_DERIVED / "v2" / f"nisar_sublook_coherence_t{t:03d}_9t.tif"
        if sp.exists():
            with rasterio.open(sp) as r:
                assert r.transform == tf and r.shape == tuple(shape), "sub-look grid differs from the stack"
                L["sub"] = r.read(1)
    has_sub = all("sub" in L for L in layers.values())
    valid = np.isfinite(cover) & np.isfinite(slope) & np.all([L["ok"] for L in layers.values()], axis=0)

    x0, y1 = tf.c, tf.f
    x1, y0 = x0 + shape[1] * 5, y1 - shape[0] * 5
    pads = S.read_layer(S.ANN, "plat").pipe(S.AREA.to_radar).cx[x0:x1, y0:y1].reset_index(drop=True)
    wells = P.gpd.read_file(S.WELLS).pipe(S.AREA.to_radar).cx[x0 - 100:x1 + 100, y0 - 100:y1 + 100]
    away = (rasterize([(g, 1) for g in list(wells.buffer(60)) + list(pads.buffer(30))],
                      out_shape=shape, transform=tf, fill=0, dtype="uint8") == 0) & valid

    def score(px):
        r = {}
        for t, L in layers.items():
            for v in ("raw", "flat", "pol"):
                r[f"{v}_t{t}"] = int(L[v][px].any())
            r[f"comp_t{t}"] = float(np.nanmax(L["comp"][px]))
            if "sub" in L:
                r[f"sub_t{t}"] = float(np.nanmax(L["sub"][px]))
        return r

    units = []
    for i, p in pads.iterrows():
        g = p.geometry.buffer(BUF_M)
        px = P.pix(g, tf, shape)
        if px is None or not valid[px].all():
            continue
        cv, sl = float(np.nanmean(cover[px])), float(np.nanmean(slope[px]))
        ctr, tries = [], 0
        while len(ctr) < N_CTRL and tries < 600:
            tries += 1
            a, r = rng.uniform(0, 2 * np.pi), rng.uniform(150, 600)
            q = P.pix(translate(g, r * np.cos(a), r * np.sin(a)), tf, shape)
            if q is None or not away[q].all():
                continue
            if abs(np.nanmean(cover[q]) - cv) > COVER_MATCH or abs(np.nanmean(slope[q]) - sl) > SLOPE_MATCH:
                continue
            ctr.append(q)
        if len(ctr) < N_CTRL:
            continue  # only complete sets, so the swap test is exact
        base = dict(set=i, pad_id=p.pad_id, area=g.area, cover=cv, slope=sl)
        units.append(dict(base, is_pad=1, **score(px)))
        units += [dict(base, is_pad=0, **score(q)) for q in ctr]
    U = pd.DataFrame(units)
    pad_rows = U[U.is_pad == 1]
    size = pd.qcut(pad_rows.area, 3, labels=["small", "mid", "large"]).astype(str)
    U["stratum"] = U.set.map(dict(zip(pad_rows.set, size))) + "_" + np.where(U.cover < 0.30, "open", "canopy")
    tracks = sorted(layers)
    for v in ("raw", "flat", "pol"):
        U[f"{v}_any"] = U[[f"{v}_t{t}" for t in tracks]].max(1)
    U["comp_mean"] = U[[f"comp_t{t}" for t in tracks]].mean(1)
    if has_sub:
        U["sub_mean"] = U[[f"sub_t{t}" for t in tracks]].mean(1)
    U.to_csv(OUT / f"nisar_steel_pads_v2_units_{S.OTAG}.csv", index=False)
    n_sets = U.set.nunique()
    print(n_sets, "complete pad sets", flush=True)

    rows = []
    for v in ("raw", "flat", "pol"):
        for t in [*tracks, "any"]:
            col = f"{v}_t{t}" if t != "any" else f"{v}_any"
            X = U.pivot_table(index="set", columns=U.groupby("set").cumcount(), values=col).values
            stat, p_cmh = cmh(U, col)
            rows.append(dict(variant=v, track=t, kind="hit", n_sets=n_sets,
                             pads=round(float(U[U.is_pad == 1][col].mean()), 3),
                             ctrls=round(float(U[U.is_pad == 0][col].mean()), 3),
                             p_swap=swap_p(X, rng=rng), cmh_chi2=stat, p_cmh=p_cmh))
    for t, var in [(t, v) for v in (["comp", "sub"] if has_sub else ["comp"]) for t in [*tracks, "mean"]]:
        col = f"{var}_t{t}" if t != "mean" else f"{var}_mean"
        X = U.pivot_table(index="set", columns=U.groupby("set").cumcount(), values=col).values
        a = U[U.is_pad == 1][col].values
        b = U[U.is_pad == 0][col].values
        order = U.sort_values(col, ascending=False)
        top = {f"top{k}_pad_share": round(float(order.head(k).is_pad.mean()), 3) for k in (20, 50, 100)}
        rows.append(dict(variant="composite" if var == "comp" else "sublook", track=t, kind="score", n_sets=n_sets,
                         pads=round(float(np.median(a)), 3), ctrls=round(float(np.median(b)), 3),
                         auc=round(float(mannwhitneyu(a, b).statistic / (len(a) * len(b))), 3),
                         p_swap=float(f"{_rank_swap(X, rng):.3g}"),
                         base_share=round(1 / (1 + N_CTRL), 3), **top))
    R = pd.DataFrame(rows)
    R["n_tests"] = len(R)
    R["bonferroni_pass"] = R[["p_swap"]].min(1) * len(R) < 0.05
    print(R.to_string(index=False))
    R.to_csv(OUT / f"nisar_steel_pads_v2_tests_{S.OTAG}.csv", index=False)
    json.dump(dict(params=dict(buffer_m=BUF_M, n_ctrl=N_CTRL, seed=SEED, n_perm=N_PERM, slope_match_deg=SLOPE_MATCH,
                               cover_match=COVER_MATCH, da_max=S.DA_MAX, bright_sd=S.BRIGHT_SD, bg_m=S.BG_M,
                               flat_mask_frac=fl.MASK_FRAC, pol_ratio_pct=90),
                   per_track=info, n_sets=int(n_sets), n_pads_in_tile=int(len(pads)), tests=rows),
              open(OUT / f"nisar_steel_pads_v2_summary_{S.OTAG}.json", "w"), indent=1, default=float)
    print("wrote", OUT)


def _rank_swap(X, rng):
    """Swap test on a continuous score: statistic = sum over sets of the pad's within-set rank."""
    R = np.argsort(np.argsort(X, axis=1), axis=1).astype(float)  # ties broken by order; scores are continuous
    obs = R[:, 0].sum()
    pick = rng.integers(0, X.shape[1], size=(N_PERM, len(X)))
    null = R[np.arange(len(X))[None, :], pick].sum(1)
    return (1 + (null >= obs).sum()) / (N_PERM + 1)


if __name__ == "__main__":
    main()
