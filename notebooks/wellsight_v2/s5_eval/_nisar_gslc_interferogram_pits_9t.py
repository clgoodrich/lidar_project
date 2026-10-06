"""NISAR interferograms over 9t from the saved GSLC windows: coherence and phase at well pits.

Option 2 of the 2026-09-30 NISAR reappraisal ("coherence from the saved complex windows").
The reappraisal dropped individual-pit InSAR: a pit is about one 5 m pixel, and coherence needs
averaging over several pixels. This run tests that directly instead of assuming it.

Interferogram
  * NISAR GSLC is geocoded and phase-flattened against the processing DEM, so two GSLCs from the
    same track on the same grid form an interferogram by s1 * conj(s2). Checked on the
    2025-10-28 -> 11-09 track 162 pair: the interferogram spectrum peaks at zero frequency
    (no residual fringe ramp), and HH coherence is 0.43 at a 9 x 9 window, matching the 0.50
    GUNW measured at 80 m.
  * Pairs: consecutive dates on one track, at most MAX_DT_DAYS apart.
  * Coherence and multilooked phase use a WIN x WIN boxcar (3 x 3 = 15 m, 9 looks). A 9-look
    estimate is biased high on low coherence; the bias is the same for pits, rings and decoys.

Pit test (same design as _nisar_gslc_stack_pad_pit_seasonal_9t.py)
  * Pit pixels: 5 m pixels whose centre lies in the whole pit (pit_outside); the centroid
    pixel when none does. Ring 10-30 m outside, 5 m clear of every pit and road.
  * Decoys: 5 same-shape copies per pit, moved 150-600 m onto background.
  * Coherence excess = (pit - ring) - median(decoy - ring).
  * Phase: pit minus ring of the multilooked interferogram, as line-of-sight displacement in mm
    (lambda / 4 pi per radian, lambda = 24.2 cm). Same decoy correction.
  * Registration: as delivered (primary), and with each track's best canopy shift from the
    brightness stack (--force-best-shift), because a 10-15 m offset is 2-3 pixels at pit scale.

  python notebooks/wellsight_v2/s5_eval/_nisar_gslc_interferogram_pits_9t.py
  python notebooks/wellsight_v2/s5_eval/_nisar_gslc_interferogram_pits_9t.py --force-best-shift
"""
import argparse
import importlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject, transform_bounds
from scipy.ndimage import uniform_filter
from scipy.stats import wilcoxon
from shapely.affinity import translate

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
st = importlib.import_module("_nisar_gslc_stack_pad_pit_seasonal_9t")   # paths + pixel/decoy helpers
from _common import path_for, read_layer  # noqa: E402

SRC, INDEX, ANN, OUT, FIG, CRS = st.SRC, st.INDEX, st.ANN, st.OUT, st.FIG, st.CRS
HILL = path_for("data") / "9t" / "derived" / "1m" / "hillshade_9t_1m.tif"
SHIFT_JSON = OUT / "nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_forcedshift_9t_5m.json"
MAX_DT_DAYS = 24
WIN = 3
LAMBDA_M = 299_792_458 / 1.239e9
MM_PER_RAD = LAMBDA_M / (4 * np.pi) * 1000
N_DECOY, SEED, B = 5, 20261005, 2000
# pit #1F5FA8 vs decoy #D97706: the lost/found pair, dataviz validate_palette.js --mode light
# --pairs all, worst pair dE 21.1 deutan, 22.6 normal. Markers differ too (circle vs square).
# Maps: greyscale for amplitude and coherence; "twilight" (cyclic purple-white-orange, no green)
# for wrapped phase. Pit outlines in #D97706 on greyscale.
PIT_C, DEC_C, INK, MUTED = "#1F5FA8", "#D97706", "#2B2F36", "#5B6168"


def load_complex():
    idx = pd.read_csv(INDEX)
    idx = idx[idx.valid_fraction >= 0.5].reset_index(drop=True)
    stack, tf = {}, None
    for row in idx.itertuples():
        with rasterio.open(SRC / row.file) as r:
            stack[row.file] = r.read()
            tf = r.transform if tf is None else tf
            assert r.transform == tf, row.file
    return idx, stack, tf, next(iter(stack.values())).shape[1:]


def pairs_of(idx):
    out = []
    for t, g in idx.sort_values("date").groupby("track"):
        d = pd.to_datetime(g.date).tolist()
        f = g.file.tolist()
        for i in range(len(f) - 1):
            dt = (d[i + 1] - d[i]).days
            if dt <= MAX_DT_DAYS:
                out.append(dict(track=int(t), direction=g.direction.iloc[0], d1=d[i].date().isoformat(),
                                d2=d[i + 1].date().isoformat(), dt_days=dt, f1=f[i], f2=f[i + 1]))
    return pd.DataFrame(out)


def interferogram(s1, s2, w=WIN):
    i = s1 * np.conj(s2)
    ok = np.isfinite(i)
    i0 = np.where(ok, i, 0)
    num = uniform_filter(i0.real, w) + 1j * uniform_filter(i0.imag, w)
    p1 = uniform_filter(np.where(ok, np.abs(s1) ** 2, 0), w)
    p2 = uniform_filter(np.where(ok, np.abs(s2) ** 2, 0), w)
    coh = np.abs(num) / np.sqrt(p1 * p2)
    coh[~ok] = np.nan
    num[~ok] = np.nan
    return coh.astype(np.float32), num.astype(np.complex64)


def pit_pixels(g, tf, shape):
    px = st.pixel_index(g, tf, shape)
    if len(px):
        return px
    c = g.centroid
    col, row = int((c.x - tf.c) / tf.a), int((c.y - tf.f) / tf.e)
    return np.array([row * shape[1] + col]) if 0 <= row < shape[0] and 0 <= col < shape[1] else px


def boot_ci(v, rng):
    v = np.asarray(v)[np.isfinite(v)]
    if len(v) < 3:
        return (np.nan, np.nan)
    bs = np.median(rng.choice(v, (B, len(v))), axis=1)
    return tuple(np.percentile(bs, [2.5, 97.5]).round(4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-best-shift", action="store_true")
    force = ap.parse_args().force_best_shift
    sfx = "_forcedshift" if force else ""
    FIG.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    idx, stack, tf, shape = load_complex()
    pairs = pairs_of(idx)
    print(pairs[["track", "d1", "d2", "dt_days"]].to_string())
    shift_of = {int(k): v for k, v in json.load(open(SHIFT_JSON))["shift_applied_m"].items()} if force else {}

    pits = read_layer(ANN, "pit_outside").to_crs(CRS).reset_index(drop=True)
    pits["pit_row"] = range(len(pits))
    roads = read_layer(ANN, "roads").to_crs(CRS)
    pads = read_layer(ANN, "plat").to_crs(CRS)
    cover = st.canopy_cover(tf, shape)
    in_tile = np.isfinite(cover)
    pits = pits[[in_tile.ravel()[pit_pixels(g, tf, shape)].any() if len(pit_pixels(g, tf, shape)) else False
                 for g in pits.geometry]].reset_index(drop=True)
    feat_zone = rasterize([(g, 1) for g in pd.concat([pads.buffer(20), pits.buffer(20), roads.buffer(20)])],
                          out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
    ok_flat, bg_flat = in_tile.ravel(), (in_tile & ~feat_zone).ravel()
    excl = pd.concat([pits.buffer(st.PIT_EXCL), roads.buffer(st.PIT_EXCL)]).union_all()

    # pixel sets per pit and per track (the shift differs by track)
    sets = {}
    for t in sorted(pairs.track.unique()):
        sx, sy = shift_of.get(t, (0.0, 0.0))
        lst = []
        for g in pits.geometry:
            gg = translate(g, -sx, -sy)          # ground at g is seen at pixel g - shift
            core = pit_pixels(gg, tf, shape)
            core = core[ok_flat[core]]
            rg = st.pixel_index(st.ring_geom(gg, st.PIT_RING, excl), tf, shape)
            rg = rg[ok_flat[rg]]
            dec = st.placebo_sets(gg, 0, st.PIT_RING, excl, tf, shape, ok_flat, bg_flat, rng, N_DECOY)
            lst.append((core, rg, dec))
        sets[t] = lst
    pit_cover = np.array([np.nanmean(cover.ravel()[pit_pixels(g, tf, shape)]) for g in pits.geometry])

    rows, best = [], None
    for p in pairs.itertuples():
        for pol, pi in (("hh", 0), ("hv", 1)):
            coh, ifg = interferogram(stack[p.f1][pi], stack[p.f2][pi])
            cf, iff = coh.ravel(), ifg.ravel()
            tile_med = float(np.nanmedian(coh[in_tile]))
            if pol == "hh" and (best is None or tile_med > best[0]):
                best = (tile_med, p, coh, ifg)
            for k, (core, rg, dec) in enumerate(sets[p.track]):
                if len(core) == 0 or len(rg) < 10:
                    continue
                c_pit, c_ring = np.nanmean(cf[core]), np.nanmean(cf[rg])
                ph = np.angle(np.nansum(iff[core]) * np.conj(np.nansum(iff[rg])))
                dc = [np.nanmean(cf[a]) - np.nanmean(cf[b]) for a, b in dec]
                dp = [np.angle(np.nansum(iff[a]) * np.conj(np.nansum(iff[b]))) for a, b in dec]
                rows.append(dict(track=p.track, d1=p.d1, d2=p.d2, dt_days=p.dt_days, pol=pol, pit=k,
                                 pit_cover=pit_cover[k], tile_coh_median=tile_med,
                                 coh_pit=c_pit, coh_ring=c_ring, coh_pit_minus_ring=c_pit - c_ring,
                                 coh_decoy_minus_ring_median=np.median(dc) if dc else np.nan,
                                 los_pit_minus_ring_mm=-ph * MM_PER_RAD,
                                 los_decoy_minus_ring_mm_median=-np.median(dp) * MM_PER_RAD if dp else np.nan,
                                 los_decoy_abs_mm_median=np.median(np.abs(dp)) * MM_PER_RAD if dp else np.nan))
    df = pd.DataFrame(rows)
    df["coh_excess"] = df.coh_pit_minus_ring - df.coh_decoy_minus_ring_median
    df["los_excess_mm"] = df.los_pit_minus_ring_mm - df.los_decoy_minus_ring_mm_median
    stem = f"nisar_gslc_interferogram_pits_vs_decoys_win{WIN}{sfx}_9t_5m"
    df.to_csv(OUT / f"{stem}_per_pit_per_pair.csv", index=False)

    # per pair, and pooled per pit
    per_pair = []
    for (t, d1, d2, pol), g in df.groupby(["track", "d1", "d2", "pol"]):
        e = g.coh_excess.dropna()
        per_pair.append(dict(track=t, d1=d1, d2=d2, pol=pol, n_pits=len(e),
                             tile_coh_median=round(g.tile_coh_median.iloc[0], 3),
                             pit_coh_median=round(g.coh_pit.median(), 3),
                             ring_coh_median=round(g.coh_ring.median(), 3),
                             coh_excess_median=round(e.median(), 4), coh_excess_ci95=boot_ci(e, rng),
                             wilcoxon_p=float(wilcoxon(e).pvalue) if len(e) > 10 else np.nan,
                             los_excess_mm_median=round(g.los_excess_mm.median(), 2),
                             los_pit_minus_ring_abs_mm_median=round(g.los_pit_minus_ring_mm.abs().median(), 2),
                             los_decoy_abs_mm_median=round(g.los_decoy_abs_mm_median.median(), 2)))
    per_pair = pd.DataFrame(per_pair)
    per_pair.to_csv(OUT / f"{stem}_by_pair.csv", index=False)
    print(per_pair.drop(columns=["coh_excess_ci95"]).to_string())

    summary = {"window_px": WIN, "pairs": int(len(pairs)), "pits": int(len(pits)),
               "registration": "best canopy shift per track" if force else "as delivered",
               "shift_m": {str(k): v for k, v in shift_of.items()}}
    for pol in ("hh", "hv"):
        g = df[df.pol == pol]
        pooled = g.groupby("pit").agg(coh_excess=("coh_excess", "mean"), los=("los_excess_mm", "mean"),
                                      cover=("pit_cover", "first"))
        e = pooled.coh_excess.dropna()
        summary[pol] = {
            "tile_coherence_median_over_pairs": round(float(g.groupby(["track", "d1"]).tile_coh_median.first().median()), 3),
            "pit_coherence_median": round(float(g.coh_pit.median()), 3),
            "ring_coherence_median": round(float(g.coh_ring.median()), 3),
            "coh_excess_pooled_per_pit_median": round(float(e.median()), 4),
            "coh_excess_pooled_ci95": boot_ci(e, rng),
            "coh_excess_pooled_wilcoxon_p": float(wilcoxon(e).pvalue),
            "coh_excess_open_pits_cover_lt_0p3_median": round(float(pooled[pooled.cover < 0.3].coh_excess.median()), 4),
            "n_open_pits": int((pooled.cover < 0.3).sum()),
            "coh_excess_closed_pits_cover_gt_0p7_median": round(float(pooled[pooled.cover > 0.7].coh_excess.median()), 4),
            "n_closed_pits": int((pooled.cover > 0.7).sum()),
            "los_excess_mm_pooled_median": round(float(pooled.los.median()), 2),
            "los_excess_mm_pooled_ci95": boot_ci(pooled.los, rng),
            "single_pair_los_pit_minus_ring_abs_mm_median": round(float(g.los_pit_minus_ring_mm.abs().median()), 2),
            "single_pair_los_decoy_abs_mm_median": round(float(g.los_decoy_abs_mm_median.median()), 2),
        }
    summary["best_pair_hh"] = {"track": int(best[1].track), "d1": best[1].d1, "d2": best[1].d2,
                               "tile_coherence_median": round(best[0], 3)}
    with open(OUT / f"{stem}_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=float)
    print(json.dumps(summary, indent=2, default=float))

    # rasters for the best pair (as delivered grid)
    _, bp, bcoh, bifg = best
    prof = dict(driver="GTiff", height=shape[0], width=shape[1], count=1, crs=CRS, transform=tf,
                compress="deflate", dtype="float32", nodata=np.nan)
    tag = f"t{bp.track:03d}{bp.direction}_{bp.d1.replace('-', '')}_{bp.d2.replace('-', '')}"
    if not force:
        with rasterio.open(SRC / f"nisar_interferogram_coherence_hh_win{WIN}_{tag}_9t_5m.tif", "w", **prof) as d:
            d.write(bcoh, 1)
        with rasterio.open(SRC / f"nisar_interferogram_wrapped_phase_rad_hh_win{WIN}_{tag}_9t_5m.tif", "w", **prof) as d:
            d.write(np.angle(bifg).astype(np.float32), 1)

    # figure 1: per pair, pit and decoy coherence (minus ring), HH
    g = df[df.pol == "hh"]
    order = per_pair[per_pair.pol == "hh"].sort_values(["track", "d1"]).reset_index(drop=True)
    fig, axs = plt.subplots(2, 1, figsize=(12.5, 8.4), sharex=True, gridspec_kw={"hspace": 0.12})
    for i, r in order.iterrows():
        s = g[(g.track == r.track) & (g.d1 == r.d1)]
        for ax, col, dcol in ((axs[0], "coh_pit_minus_ring", "coh_decoy_minus_ring_median"),
                              (axs[1], "los_pit_minus_ring_mm", "los_decoy_minus_ring_mm_median")):
            for v, c, m, off in ((s[col], PIT_C, "o", -0.15), (s[dcol], DEC_C, "s", 0.15)):
                v = v.dropna()
                lo, hi = np.percentile(v, [25, 75])
                ax.plot([i + off] * 2, [lo, hi], color=c, lw=2)
                ax.plot(i + off, v.median(), marker=m, color=c, ms=7, mec="white", mew=0.8)
    for ax in axs:
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.grid(axis="y", color="#E3E5E8", lw=0.6)
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
    axs[0].set_ylabel("Coherence, minus ring", color=INK)
    axs[1].set_ylabel("Line-of-sight motion,\nminus ring (mm)", color=INK)
    axs[1].set_xticks(range(len(order)))
    axs[1].set_xticklabels([f"T{r.track:03d} {r.d1[2:]} to {r.d2[5:]}" for r in order.itertuples()],
                           fontsize=7.5, rotation=55, ha="right", rotation_mode="anchor")
    axs[0].plot([], [], "o", color=PIT_C, label="well pits (median, bar = middle half)")
    axs[0].plot([], [], "s", color=DEC_C, label="same-shape decoys on background")
    axs[0].legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2)
    fig.suptitle(f"NISAR interferograms, HH, every same-track pair over 9t: pits against decoys "
                 f"({'shifted onto the lidar' if force else 'as delivered'})", x=0.02, ha="left", fontsize=12, color=INK)
    fig.text(0.02, 0.008, "Each pit has one value per pair. Its decoy value is the median of 5 decoys, "
             "so the decoy bars are narrower by construction. Pairs are sorted by track, then date (yy-mm-dd).",
             fontsize=8.5, color=MUTED)
    fig.subplots_adjust(left=0.08, right=0.99, top=0.92, bottom=0.2)
    fig.savefig(FIG / f"{stem}_by_pair_hh.png", dpi=170, facecolor="white")

    # figure 2: sample pits on the best pair: hillshade, amplitude, coherence, phase
    if not force:
        cov_ok = np.isfinite(pit_cover)
        area = pits.area.values
        open_ids = [i for i in np.argsort(-area) if cov_ok[i] and pit_cover[i] < 0.3][:3]
        closed_ids = [i for i in np.argsort(-area) if cov_ok[i] and pit_cover[i] > 0.7][:3]
        pick = open_ids + closed_ids
        amp = 10 * np.log10(np.abs(stack[bp.f1][0]) ** 2 + 1e-12)
        half = 60.0
        fig, axs = plt.subplots(len(pick), 4, figsize=(11.2, 2.75 * len(pick)), squeeze=False)
        with rasterio.open(HILL) as hs:
            for row, k in enumerate(pick):
                c = pits.geometry.iloc[k].centroid
                bb = (c.x - half, c.y - half, c.x + half, c.y + half)
                hdst = np.full((120, 120), np.nan, np.float32)
                hw = rasterio.windows.from_bounds(*transform_bounds(CRS, hs.crs, *bb), transform=hs.transform)
                hw = hw.round_offsets().round_lengths()
                reproject(hs.read(1, window=hw, boundless=True).astype(np.float32), hdst,
                          src_transform=rasterio.windows.transform(hw, hs.transform), src_crs=hs.crs,
                          dst_transform=rasterio.Affine(1, 0, bb[0], 0, -1, bb[3]), dst_crs=CRS,
                          resampling=Resampling.bilinear)
                r0, c0 = int((tf.f - bb[3]) / 5), int((bb[0] - tf.c) / 5)
                sl = (slice(r0, r0 + 24), slice(c0, c0 + 24))
                ext = (tf.c + c0 * 5, tf.c + (c0 + 24) * 5, tf.f - (r0 + 24) * 5, tf.f - r0 * 5)
                panels = [(hdst, "gray", None, (bb[0], bb[2], bb[1], bb[3]), "Lidar hillshade, 1 m"),
                          (amp[sl], "gray", None, ext, "HH brightness (dB)"),
                          (bcoh[sl], "gray", (0, 1), ext, f"Coherence, {WIN}×{WIN} px"),
                          (np.angle(bifg)[sl], "twilight", (-np.pi, np.pi), ext, "Interferogram phase")]
                for j, (img, cm, vr, ex, title) in enumerate(panels):
                    ax = axs[row, j]
                    kw = dict(vmin=vr[0], vmax=vr[1]) if vr else {}
                    im = ax.imshow(img, cmap=cm, extent=ex, interpolation="nearest", **kw)
                    gpd.GeoSeries([pits.geometry.iloc[k]], crs=CRS).boundary.plot(ax=ax, color=DEC_C, lw=1.4)
                    ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3]); ax.set_xticks([]); ax.set_yticks([])
                    if row == 0:
                        ax.set_title(title, fontsize=9.5, color=INK)
                    if j == 0:
                        ax.set_ylabel(f"{'open' if pit_cover[k] < 0.3 else 'under canopy'}\n"
                                      f"canopy {pit_cover[k]:.0%}", fontsize=9, color=INK)
        fig.suptitle(f"Sample well pits on the most coherent pair, track {bp.track}, {bp.d1} → {bp.d2} "
                     f"(120 m windows)", x=0.02, ha="left", fontsize=12, color=INK)
        fig.text(0.02, 0.006, "Orange outline: annotated pit. Radar panels are 5 m pixels, as delivered. "
                 "Coherence: black 0, white 1. Phase: one full colour cycle = 12 mm of line-of-sight motion.",
                 fontsize=8.5, color=MUTED)
        fig.subplots_adjust(left=0.05, right=0.99, top=0.95, bottom=0.03, wspace=0.04, hspace=0.06)
        fig.savefig(FIG / f"nisar_gslc_interferogram_sample_pits_open_vs_canopy_hh_win{WIN}_{tag}_9t_5m.png",
                    dpi=160, facecolor="white")
    print("done")


if __name__ == "__main__":
    main()
