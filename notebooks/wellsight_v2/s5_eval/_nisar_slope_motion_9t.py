"""NISAR GSLC summer 2026 stack over 9t: is there slope motion at 25 m, and is it at wells?

Option 3 of the 2026-10-05 "what L-band can do for wells" list.
Slow creep on colluvial slopes can shear a well casing. InSAR averaged over tens of metres can see
creep of millimetres per month when coherence holds (Berardino et al. 2002 is the time-series
standard; this is a simple chain version of it).

Per track, snow-free chain only (2026-06 to 2026-09):
  * consecutive pairs at most MAX_DT_DAYS apart, interferogram s1 * conj(s2) in HH.
  * multilook ML x ML (5 x 5 = 25 m), decimated to a 25 m grid.
  * long-wavelength phase (atmosphere, orbit) removed by subtracting the phase of a
    coherence-weighted LP_M boxcar of the multilooked interferogram.
  * cumulative phase = sum of the wrapped pair phases. This assumes under half a cycle (6 mm)
    of motion per pair, which holds for slow creep.
  * LOS displacement, mm, positive = toward the satellite. Pixels with mean coherence < COH_MIN
    are masked.

Is it real? Tracks 090 and 162 are both ascending with similar look directions, but different
dates. Real ground motion appears in both. Atmosphere and noise do not. So the test is the
correlation between the 090 and 162 displacement maps, by slope class, with a 500 m block
bootstrap for the confidence interval (neighbouring pixels are not independent).
Track 026 is descending. Its correlation with the ascending tracks is reported too; for
downslope motion its sign depends on slope aspect, so it is a weaker check.

  python notebooks/wellsight_v2/s5_eval/_nisar_slope_motion_9t.py
"""
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
from rasterio.warp import Resampling, reproject
from scipy.ndimage import uniform_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ifg = importlib.import_module("_nisar_gslc_interferogram_pits_9t")
st = ifg.st
from _common import path_for  # noqa: E402

OUT, FIG, CRS, DER = st.OUT, st.FIG, st.CRS, st.SRC
SLOPE = path_for("data") / "9t" / "derived" / "1m" / "slope_9t_1m.tif"
DEM = path_for("data") / "9t" / "derived" / "1m" / "dem_9t_1m.tif"
WELLS = path_for("data") / "_source" / "reference" / "dep_wells" / "venango_wells_all.gpkg"
ML, LP_M, COH_MIN, SUMMER_FROM, BLOCK_M, B, SEED = 5, 1000.0, 0.45, "2026-06-01", 500.0, 1000, 20261007
SLOPE_BINS = [(0, 5, "flat_lt5deg"), (5, 15, "moderate_5to15deg"), (15, 90, "steep_ge15deg")]
MM_PER_RAD = ifg.MM_PER_RAD
# Maps: displacement in "PuOr" (purple-white-orange, diverging, no green); slope classes as
# greys #2B2F36 / #5B6168 / #8E959B with distinct markers (dataviz validate_palette.js --mode light
# --pairs all, 2026-10-07: worst #8E959B-#5B6168 dE 17.6 deutan and normal; neutral by design).
# Scatter in #1F5FA8.
INK, DOT = "#2B2F36", "#1F5FA8"


def multilook(s1, s2):
    i = s1 * np.conj(s2)
    ok = np.isfinite(i)
    i = np.where(ok, i, 0)
    p1, p2 = np.where(ok, np.abs(s1) ** 2, 0), np.where(ok, np.abs(s2) ** 2, 0)
    h, w = (i.shape[0] // ML) * ML, (i.shape[1] // ML) * ML
    blk = lambda a: a[:h, :w].reshape(h // ML, ML, w // ML, ML).sum((1, 3))
    num, d1, d2 = blk(i), blk(p1), blk(p2)
    coh = np.abs(num) / np.sqrt(d1 * d2)
    return num, np.where(np.isfinite(coh), coh, 0)


def remove_longwave(num, coh):
    k = int(LP_M / (5 * ML)) | 1
    ph = num / np.where(np.abs(num) > 0, np.abs(num), 1)
    wgt = ph * coh
    lp = uniform_filter(wgt.real, k) + 1j * uniform_filter(wgt.imag, k)
    return np.angle(num * np.conj(lp))


def block_boot_r(a, b, rows, cols, rng):
    bs = int(BLOCK_M / (5 * ML))
    blk = (rows // bs) * 10000 + (cols // bs)
    ub = np.unique(blk)
    groups = [np.nonzero(blk == u)[0] for u in ub]
    rs = []
    for _ in range(B):
        sel = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        rs.append(np.corrcoef(a[sel], b[sel])[0, 1])
    return np.percentile(rs, [2.5, 97.5]).round(3).tolist()


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    idx, stack, tf, shape = ifg.load_complex()
    pairs = ifg.pairs_of(idx)
    pairs = pairs[pairs.d1 >= SUMMER_FROM].reset_index(drop=True)
    print(pairs[["track", "d1", "d2", "dt_days"]].to_string())
    tf25 = rasterio.Affine(5.0 * ML, 0, tf.c, 0, -5.0 * ML, tf.f)
    shp25 = (shape[0] // ML, shape[1] // ML)

    disp, cohm, span = {}, {}, {}
    for t, g in pairs.groupby("track"):
        cum = np.zeros(shp25)
        cs = []
        for p in g.itertuples():
            num, coh = multilook(stack[p.f1][0], stack[p.f2][0])
            cum += remove_longwave(num, coh)
            cs.append(coh)
        c = np.mean(cs, 0)
        d = -cum * MM_PER_RAD
        d[c < COH_MIN] = np.nan
        disp[int(t)], cohm[int(t)] = d, c
        span[int(t)] = dict(first=g.d1.iloc[0], last=g.d2.iloc[-1], n_pairs=len(g),
                            days=int((pd.to_datetime(g.d2.iloc[-1]) - pd.to_datetime(g.d1.iloc[0])).days),
                            coherent_share=round(float(np.mean(c >= COH_MIN)), 3),
                            disp_std_mm=round(float(np.nanstd(d)), 2))
        print(t, span[int(t)])

    with rasterio.open(SLOPE) as r:
        slope = np.full(shp25, np.nan, np.float32)
        src = r.read(1, masked=True).filled(np.nan).astype(np.float32)
        reproject(src, slope, src_transform=r.transform, src_crs=r.crs, src_nodata=np.nan,
                  dst_transform=tf25, dst_crs=CRS, dst_nodata=np.nan, resampling=Resampling.average)

    rows_, cols_ = np.indices(shp25)
    pairs_tr = [(90, 162), (90, 26), (162, 26)]
    res = []
    for a, b in pairs_tr:
        for lo, hi, lab in SLOPE_BINS + [(0, 90, "all")]:
            m = np.isfinite(disp[a]) & np.isfinite(disp[b]) & (slope >= lo) & (slope < hi)
            if m.sum() < 50:
                continue
            x, y = disp[a][m], disp[b][m]
            res.append(dict(tracks=f"{a}_vs_{b}", slope_class=lab, n_pixels_25m=int(m.sum()),
                            pearson_r=round(float(np.corrcoef(x, y)[0, 1]), 3),
                            r_ci95_block500m=block_boot_r(x, y, rows_[m], cols_[m], rng),
                            std_mm_a=round(float(x.std()), 2), std_mm_b=round(float(y.std()), 2)))
    res = pd.DataFrame(res)
    print(res.to_string())

    # spread of displacement by slope class (ascending mean of 090 and 162)
    asc = (disp[90] + disp[162]) / 2
    spread = []
    for lo, hi, lab in SLOPE_BINS:
        m = np.isfinite(asc) & (slope >= lo) & (slope < hi)
        v = asc[m]
        spread.append(dict(slope_class=lab, n_pixels_25m=int(m.sum()), asc_mean_std_mm=round(float(v.std()), 2),
                           asc_mean_p95_abs_mm=round(float(np.percentile(np.abs(v), 95)), 2)))
    spread = pd.DataFrame(spread)
    print(spread.to_string())

    # aspect test on steep slopes. Ascending, right-looking: the radar looks east from the west.
    # Downslope creep on a west-facing slope moves toward the satellite (positive), on an
    # east-facing slope away from it (negative). North- and south-facing creep is mostly unseen.
    with rasterio.open(DEM) as r:
        dem = np.full(shp25, np.nan, np.float32)
        reproject(r.read(1, masked=True).filled(np.nan).astype(np.float32), dem, src_transform=r.transform,
                  src_crs=r.crs, src_nodata=np.nan, dst_transform=tf25, dst_crs=CRS, dst_nodata=np.nan,
                  resampling=Resampling.average)
    gy, gx = np.gradient(dem, 25.0)            # rows run south, so gy is d(z)/d(south)
    east_down = gx < 0                          # z falls to the east: east-facing
    face_e = np.abs(gx) > np.abs(gy)
    aspect = []
    for lab, sel in (("west_facing", face_e & ~east_down), ("east_facing", face_e & east_down),
                     ("north_or_south_facing", ~face_e)):
        m = np.isfinite(asc) & (slope >= 15) & sel
        v = asc[m]
        bs = int(BLOCK_M / (5 * ML))
        blk = (rows_[m] // bs) * 10000 + cols_[m] // bs
        ub = np.unique(blk)
        grp = [v[blk == u] for u in ub]
        boot = [np.concatenate([grp[i] for i in rng.integers(0, len(grp), len(grp))]).mean() for _ in range(B)]
        aspect.append(dict(aspect=lab, n_pixels_25m=int(m.sum()), asc_mean_mm=round(float(v.mean()), 2),
                           ci95_block500m=np.percentile(boot, [2.5, 97.5]).round(2).tolist()))
    aspect = pd.DataFrame(aspect)
    print(aspect.to_string())

    # wells: displacement at DEP wells, and the ones both ascending tracks agree on
    x0, y1 = tf25.c, tf25.f
    x1, y0 = x0 + shp25[1] * 25, y1 - shp25[0] * 25
    w = gpd.read_file(WELLS).to_crs(CRS).cx[x0:x1, y0:y1].copy()
    cc = ((w.geometry.x - x0) / 25).astype(int).clip(0, shp25[1] - 1)
    rr = ((y1 - w.geometry.y) / 25).astype(int).clip(0, shp25[0] - 1)
    w["slope_deg_25m"] = slope[rr, cc]
    for t in disp:
        w[f"los_mm_t{t:03d}"] = disp[t][rr, cc]
    w["los_mm_asc_mean"] = asc[rr, cc]
    sd = float(np.nanstd(asc))
    w["both_asc_same_sign_gt2sd"] = (np.sign(w.los_mm_t090) == np.sign(w.los_mm_t162)) & \
                                    (w.los_mm_t090.abs() > 2 * np.nanstd(disp[90])) & \
                                    (w.los_mm_t162.abs() > 2 * np.nanstd(disp[162]))
    # expected count of that flag by chance, from all coherent pixels
    mm = np.isfinite(disp[90]) & np.isfinite(disp[162])
    chance = float(np.mean((np.sign(disp[90][mm]) == np.sign(disp[162][mm])) &
                           (np.abs(disp[90][mm]) > 2 * np.nanstd(disp[90])) &
                           (np.abs(disp[162][mm]) > 2 * np.nanstd(disp[162]))))
    wc = w[np.isfinite(w.los_mm_asc_mean)]
    well_summary = dict(n_wells_coherent=int(len(wc)), n_flagged=int(wc.both_asc_same_sign_gt2sd.sum()),
                        expected_by_chance=round(len(wc) * chance, 1), chance_rate=round(chance, 4),
                        abs_asc_mm_median_steep=round(float(wc[wc.slope_deg_25m >= 15].los_mm_asc_mean.abs().median()), 2),
                        abs_asc_mm_median_flat=round(float(wc[wc.slope_deg_25m < 5].los_mm_asc_mean.abs().median()), 2),
                        n_wells_steep=int((wc.slope_deg_25m >= 15).sum()), n_wells_flat=int((wc.slope_deg_25m < 5).sum()))
    print(well_summary)

    stem = "nisar_slope_motion"
    res.to_csv(OUT / f"{stem}_tracks_9t.csv", index=False)
    aspect.to_csv(OUT / f"{stem}_aspect_9t.csv", index=False)
    spread.to_csv(OUT / f"{stem}_spread_9t.csv", index=False)
    cols = ["PERMIT_NUM", "WELL_STATU", "OPERATOR", "slope_deg_25m", *[f"los_mm_t{t:03d}" for t in disp],
            "los_mm_asc_mean", "both_asc_same_sign_gt2sd", "geometry"]
    w[cols].to_file(OUT / f"{stem}_wells_9t.gpkg", layer="dep_wells_los_summer2026", driver="GPKG")
    json.dump(dict(params=dict(ml=ML, lp_m=LP_M, coh_min=COH_MIN, summer_from=SUMMER_FROM, block_m=BLOCK_M, B=B),
                   tracks={str(k): v for k, v in span.items()}, agreement=res.to_dict("records"),
                   spread=spread.to_dict("records"),
                   steep_aspect=aspect.to_dict("records"), wells=well_summary),
              open(OUT / f"{stem}_summary_9t.json", "w"), indent=2, default=float)
    prof = dict(driver="GTiff", height=shp25[0], width=shp25[1], count=1, dtype="float32", crs=CRS,
                transform=tf25, nodata=np.nan, compress="deflate")
    for t, d in disp.items():
        with rasterio.open(DER / f"{stem}_los_mm_t{t:03d}_9t.tif",
                           "w", **prof) as o:
            o.write(d.astype(np.float32), 1)

    # figure: three displacement maps, the 090-vs-162 scatter, and r by slope class
    fig = plt.figure(figsize=(15, 9))
    lim = np.nanpercentile(np.abs(np.concatenate([d[np.isfinite(d)] for d in disp.values()])), 98)
    ext = [x0, x1, y0, y1]
    for k, t in enumerate([90, 162, 26]):
        ax = fig.add_subplot(2, 3, k + 1)
        im = ax.imshow(disp[t], cmap="PuOr", vmin=-lim, vmax=lim, extent=ext)
        ax.set_title(f"track {t:03d} {'asc' if t != 26 else 'desc'}, {span[t]['first']} to {span[t]['last']}", fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    cb = fig.colorbar(im, ax=fig.axes, fraction=0.02, location="right")
    cb.set_label("LOS displacement, mm (positive toward satellite)")
    ax = fig.add_subplot(2, 3, 4)
    m = np.isfinite(disp[90]) & np.isfinite(disp[162])
    ax.scatter(disp[90][m], disp[162][m], s=2, color=DOT, alpha=0.25)
    ax.set_xlabel("track 090, mm"); ax.set_ylabel("track 162, mm")
    r_all = res[(res.tracks == "90_vs_162") & (res.slope_class == "all")].pearson_r.iloc[0]
    ax.set_title(f"both ascending tracks, r = {r_all}", fontsize=10)
    ax = fig.add_subplot(2, 3, 5)
    mk = {"90_vs_162": "o", "90_vs_26": "s", "162_vs_26": "^"}
    cl = {"90_vs_162": INK, "90_vs_26": "#5B6168", "162_vs_26": "#8E959B"}
    labs = [b[2] for b in SLOPE_BINS]
    for tr, g in res[res.slope_class != "all"].groupby("tracks"):
        g = g.set_index("slope_class").reindex(labs).dropna(subset=["pearson_r"])
        if not len(g):
            continue
        xs = np.array([labs.index(i) for i in g.index]) + {"90_vs_162": -0.15, "90_vs_26": 0, "162_vs_26": 0.15}[tr]
        lo = [r[0] for r in g.r_ci95_block500m]; hi = [r[1] for r in g.r_ci95_block500m]
        ax.errorbar(xs, g.pearson_r, yerr=[g.pearson_r - lo, np.array(hi) - g.pearson_r], fmt=mk[tr],
                    color=cl[tr], capsize=3, label=tr.replace("_vs_", " vs "))
    ax.axhline(0, color="#8E959B", lw=0.8)
    ax.set_xticks(range(len(labs)), [l.replace("_", " ") for l in labs], fontsize=8)
    ax.set_ylabel("correlation between tracks (95% block CI)")
    ax.legend(fontsize=8)
    ax = fig.add_subplot(2, 3, 6)
    ax.axis("off")
    ax.text(0, 0.95, "\n".join([
        f"Coherent share (mean coh ≥ {COH_MIN}):",
        *[f"  track {t:03d}: {span[t]['coherent_share']:.0%}, {span[t]['n_pairs']} pairs" for t in [90, 162, 26]],
        "",
        f"DEP wells on coherent pixels: {well_summary['n_wells_coherent']}",
        f"Flagged by both ascending tracks (> 2 SD, same sign): {well_summary['n_flagged']}",
        f"Expected by chance: {well_summary['expected_by_chance']}",
    ]), va="top", fontsize=10, family="monospace")
    fig.suptitle("NISAR L-band summer 2026 line-of-sight displacement, 25 m, 1 km trend removed, 9t", fontsize=12)
    fig.savefig(FIG / f"{stem}_maps_9t.png", dpi=140, bbox_inches="tight")
    print("done", stem)


if __name__ == "__main__":
    main()
