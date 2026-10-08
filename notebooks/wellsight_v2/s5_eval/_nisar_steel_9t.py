"""NISAR GSLC stack over 9t: do bright, steady radar targets sit at DEP wells? (steel test)

Option 1 of the 2026-10-05 "what L-band can do for wells" list.
Standing casing, pumpjacks, tanks and pipe are steel. Steel corners give strong echoes that stay
the same from pass to pass. Forest echoes flicker. A pixel that is bright and steady over the
whole stack is a persistent-scatterer candidate (Ferretti et al. 2001).

Per track (one viewing geometry), from the HH amplitude A of every date:
  * amplitude dispersion D_A = std(A) / mean(A). Ferretti et al. 2001 keep D_A < 0.25.
  * brightness above local background = mean HH dB minus the 250 m median of mean HH dB.
  * a pixel is a steady bright target (SBT) on a track when D_A < DA_MAX and brightness >= BRIGHT_DB.
The well score is the number of tracks (0-3) with an SBT within R_M of the well point.

Groups from the DEP April 2026 export (data/_source/reference/dep_wells/venango_wells_all.gpkg):
  active      Active
  plugged     Plugged OG Well, DEP Plugged
  abandoned   DEP Abandoned List, DEP Orphan List, Abandoned
  not_drilled Operator Reported Not Drilled, Proposed But Never Materialized  (negative control)
Decoys: N_DECOY points per well, 150-600 m away, at least 60 m from every DEP well and pad.
Decoys are drawn from the same canopy-cover band as the well (+-0.15), because open ground and
forest give different brightness.

Registration: the hit rate of active wells is recomputed with the stack shifted -20..+20 m.
A clear peak away from zero is a point-target estimate of the radar-to-lidar offset.

  python notebooks/wellsight_v2/s5_eval/_nisar_steel_9t.py
"""
import importlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import maximum_filter, median_filter
from scipy.stats import fisher_exact, mannwhitneyu

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ifg = importlib.import_module("_nisar_gslc_interferogram_pits_9t")
st = ifg.st
from _common import path_for, read_layer  # noqa: E402

OUT, FIG, CRS, ANN = st.OUT, st.FIG, st.CRS, st.ANN
DER = st.SRC
WELLS = path_for("data") / "_source" / "reference" / "dep_wells" / "venango_wells_all.gpkg"
DA_MAX, BRIGHT_DB, R_M, BG_M = 0.25, 6.0, 15.0, 250.0
N_DECOY, SEED = 5, 20261007
GROUPS = {"active": ["Active"], "plugged": ["Plugged OG Well", "DEP Plugged"],
          "abandoned": ["DEP Abandoned List", "DEP Orphan List", "Abandoned"],
          "not_drilled": ["Operator Reported Not Drilled", "Proposed But Never Materialized"]}
# Group colours: active #1F5FA8, plugged #D97706, abandoned #A31515 (lost/found palette,
# dataviz validate_palette.js --mode light --pairs all, worst pair dE 21.1 deutan, 22.6 normal),
# not_drilled and decoys in neutral greys #5B6168 / #8E959B.
# All five, dataviz validate_palette.js --mode light --pairs all (2026-10-07): CVD worst #5B6168-#A31515
# dE 10.9 deutan; normal-vision worst #5B6168-#1F5FA8 dE 12.0 (below 15) and greys fail the chroma
# floor by design (controls, not categories). Every bar carries its group name on the x axis and decoys
# are hatched, so identity is never colour alone. No red/green pair.
COL = {"active": "#1F5FA8", "plugged": "#D97706", "abandoned": "#A31515",
       "not_drilled": "#5B6168", "decoy": "#8E959B"}
MRK = {"active": "o", "plugged": "s", "abandoned": "^", "not_drilled": "D", "decoy": "x"}
INK = "#2B2F36"


def sbt_maps(idx, stack, shape):
    """Per track: steady-bright-target mask, D_A and brightness."""
    out = {}
    for t, g in idx.groupby("track"):
        A = np.stack([np.abs(stack[f][0]) for f in g.file]).astype(np.float32)
        ok = np.all(np.isfinite(A) & (A > 0), axis=0)
        mA = A.mean(0)
        da = A.std(0) / np.where(mA > 0, mA, np.nan)
        mdb = 10 * np.log10(np.where(ok, (A ** 2).mean(0), np.nan))
        k = int(BG_M / 5) | 1
        bg = median_filter(np.where(ok, mdb, np.nanmedian(mdb)), size=k)
        bright = mdb - bg
        sbt = ok & (da < DA_MAX) & (bright >= BRIGHT_DB)
        out[int(t)] = dict(sbt=sbt, da=da, bright=bright, n=len(g), ok=ok)
        print(f"track {t}: {len(g)} dates, SBT pixels {sbt.sum()} ({sbt[ok].mean():.4%} of valid)")
    return out


def hits(maps, pts, tf, shape, dx=0.0, dy=0.0):
    """Tracks (0-3) with an SBT within R_M of each point, the stack shifted by (dx, dy) m."""
    r = int(np.ceil(R_M / 5))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    fp = (xx ** 2 + yy ** 2) * 25 <= R_M ** 2
    col = ((pts.x.values - dx - tf.c) / tf.a).astype(int)
    row = ((pts.y.values - dy - tf.f) / tf.e).astype(int)
    inb = (row >= 0) & (row < shape[0]) & (col >= 0) & (col < shape[1])
    n = np.zeros(len(pts), int)
    for m in maps.values():
        near = maximum_filter(m["sbt"].astype(np.uint8), footprint=fp).astype(bool)
        n[inb] += near[row[inb], col[inb]]
    n[~inb] = -1
    return n


def local_scores(maps, pts, tf, shape):
    """Continuous scores within R_M: max brightness and min D_A, each averaged over tracks."""
    r = int(np.ceil(R_M / 5))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    fp = (xx ** 2 + yy ** 2) * 25 <= R_M ** 2
    col = ((pts.x.values - tf.c) / tf.a).astype(int)
    row = ((pts.y.values - tf.f) / tf.e).astype(int)
    b, d = [], []
    for m in maps.values():
        b.append(maximum_filter(np.nan_to_num(m["bright"], nan=-99), footprint=fp)[row, col])
        d.append(-maximum_filter(np.nan_to_num(-m["da"], nan=-9), footprint=fp)[row, col])
    return np.mean(b, 0), np.mean(d, 0)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    idx, stack, tf, shape = ifg.load_complex()
    maps = sbt_maps(idx, stack, shape)
    cover = st.canopy_cover(tf, shape)
    valid = np.isfinite(cover) & np.all([m["ok"] for m in maps.values()], axis=0)

    x0, y1 = tf.c, tf.f
    x1, y0 = x0 + shape[1] * 5, y1 - shape[0] * 5
    w = gpd.read_file(WELLS).to_crs(CRS).cx[x0 + R_M:x1 - R_M, y0 + R_M:y1 - R_M].copy()
    w["group"] = None
    for k, v in GROUPS.items():
        w.loc[w.WELL_STATU.isin(v), "group"] = k
    w = w[w.group.notna()].reset_index(drop=True)
    col = ((w.geometry.x - tf.c) / tf.a).astype(int)
    row = ((w.geometry.y - tf.f) / tf.e).astype(int)
    w = w[valid[row, col]].reset_index(drop=True)
    w["cover"] = cover[((w.geometry.y - tf.f) / tf.e).astype(int), ((w.geometry.x - tf.c) / tf.a).astype(int)]
    print(w.group.value_counts().to_string())

    # decoys: away from every DEP well (any status) and every annotated pad, matched on canopy
    allw = gpd.read_file(WELLS).to_crs(CRS).cx[x0 - 100:x1 + 100, y0 - 100:y1 + 100]
    pads = read_layer(ANN, "plat").to_crs(CRS)
    away = rasterize([(g, 1) for g in list(allw.buffer(60)) + list(pads.buffer(30))],
                     out_shape=shape, transform=tf, fill=0, dtype="uint8") == 0
    away &= valid
    dec = []
    for i, p in enumerate(w.itertuples()):
        got, tries = 0, 0
        while got < N_DECOY and tries < 200:
            tries += 1
            a, r = rng.uniform(0, 2 * np.pi), rng.uniform(150, 600)
            x, y = p.geometry.x + r * np.cos(a), p.geometry.y + r * np.sin(a)
            cc, rr = int((x - tf.c) / tf.a), int((y - tf.f) / tf.e)
            if not (3 <= rr < shape[0] - 3 and 3 <= cc < shape[1] - 3) or not away[rr, cc]:
                continue
            if abs(cover[rr, cc] - p.cover) > 0.15:
                continue
            dec.append(dict(well=i, group=p.group, x=x, y=y))
            got += 1
    dec = pd.DataFrame(dec)

    w["n_tracks_sbt"] = hits(maps, w.geometry, tf, shape)
    dpts = gpd.GeoSeries(gpd.points_from_xy(dec.x, dec.y), crs=CRS)
    dec["n_tracks_sbt"] = hits(maps, dpts, tf, shape)

    w["bright_max_db"], w["da_min"] = local_scores(maps, w.geometry, tf, shape)
    dec["bright_max_db"], dec["da_min"] = local_scores(maps, dpts, tf, shape)

    rows = []
    for gname in GROUPS:
        a = w[w.group == gname]
        d = dec[dec.group == gname]
        if not len(a):
            continue
        hw, hd = (a.n_tracks_sbt >= 1), (d.n_tracks_sbt >= 1)
        hw2, hd2 = (a.n_tracks_sbt >= 2), (d.n_tracks_sbt >= 2)
        orr, p = fisher_exact([[hw.sum(), (~hw).sum()], [hd.sum(), (~hd).sum()]])
        orr2, p2 = fisher_exact([[hw2.sum(), (~hw2).sum()], [hd2.sum(), (~hd2).sum()]])
        rows.append(dict(group=gname, n_wells=len(a), n_decoys=len(d),
                         canopy_cover_median=round(a.cover.median(), 2),
                         wells_sbt_any_track=round(hw.mean(), 3), decoys_sbt_any_track=round(hd.mean(), 3),
                         odds_ratio_any=round(orr, 2), p_any=float(f"{p:.2g}"),
                         wells_sbt_2plus_tracks=round(hw2.mean(), 3), decoys_sbt_2plus_tracks=round(hd2.mean(), 3),
                         odds_ratio_2plus=round(orr2, 2), p_2plus=float(f"{p2:.2g}"),
                         auc_brightness_wells_gt_decoys=round(st.auc(a.bright_max_db, d.bright_max_db), 3),
                         auc_steadiness_wells_gt_decoys=round(st.auc(-a.da_min, -d.da_min), 3),
                         p_brightness=float(f"{mannwhitneyu(a.bright_max_db, d.bright_max_db).pvalue:.2g}"),
                         bright_max_db_median_wells=round(float(a.bright_max_db.median()), 2),
                         bright_max_db_median_decoys=round(float(d.bright_max_db.median()), 2)))
    res = pd.DataFrame(rows)
    print(res.to_string())

    # open vs canopy, active vs abandoned, the comparison that matters
    by_cov = []
    for lab, sel in (("open_cover_lt0p30", w.cover < 0.30), ("canopy_cover_ge0p30", w.cover >= 0.30)):
        for gname in GROUPS:
            a = w[sel & (w.group == gname)]
            d = dec[dec.well.isin(a.index)]
            if len(a) >= 5:
                by_cov.append(dict(cover=lab, group=gname, n_wells=len(a),
                                   wells_sbt_any_track=round((a.n_tracks_sbt >= 1).mean(), 3),
                                   decoys_sbt_any_track=round((d.n_tracks_sbt >= 1).mean(), 3),
                                   auc_brightness=round(st.auc(a.bright_max_db, d.bright_max_db), 3),
                                   auc_steadiness=round(st.auc(-a.da_min, -d.da_min), 3)))
    by_cov = pd.DataFrame(by_cov)
    print(by_cov.to_string())

    # registration by point targets: active-well hit rate under shifts of the stack
    act = w[w.group == "active"].geometry
    shifts = range(-20, 21, 5)
    grid = np.array([[(hits(maps, act, tf, shape, dx, dy) >= 1).mean() for dx in shifts] for dy in shifts])
    iy, ix = np.unravel_index(grid.argmax(), grid.shape)
    reg = dict(best_shift_m=[list(shifts)[ix], list(shifts)[iy]], best_hit_rate=round(float(grid.max()), 3),
               zero_shift_hit_rate=round(float(grid[len(shifts) // 2, len(shifts) // 2]), 3),
               median_hit_rate_over_shifts=round(float(np.median(grid)), 3))
    print("registration", reg)

    stem = "nisar_steel"
    w_out = w[["PERMIT_NUM", "WELL_STATU", "group", "OPERATOR", "cover", "n_tracks_sbt", "bright_max_db",
               "da_min", "geometry"]]
    w_out.to_file(OUT / f"{stem}_wells_9t.gpkg", layer="dep_wells_sbt", driver="GPKG")
    res.to_csv(OUT / f"{stem}_by_status_9t.csv", index=False)
    by_cov.to_csv(OUT / f"{stem}_by_canopy_9t.csv", index=False)
    summ = dict(params=dict(da_max=DA_MAX, bright_db=BRIGHT_DB, radius_m=R_M, background_m=BG_M,
                            n_decoy=N_DECOY, seed=SEED),
                tracks={str(t): dict(n_dates=int(m["n"]), sbt_pixels=int(m["sbt"].sum())) for t, m in maps.items()},
                by_status=rows, by_status_and_canopy=by_cov.to_dict("records"), registration=reg,
                registration_grid_rows_dy_cols_dx=dict(shifts=list(shifts), hit_rate=grid.round(3).tolist()))
    json.dump(summ, open(OUT / f"{stem}_summary_9t.json", "w"), indent=2, default=float)

    # SBT count raster (0-3 tracks), gitignored derived
    cnt = np.sum([m["sbt"] for m in maps.values()], axis=0).astype(np.uint8)
    prof = dict(driver="GTiff", height=shape[0], width=shape[1], count=1, dtype="uint8", crs=CRS,
                transform=tf, compress="deflate")
    with rasterio.open(DER / f"{stem}_count_9t.tif", "w", **prof) as d:
        d.write(cnt, 1)

    # figure: hit rates by group (wells vs decoys), and the registration grid
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw=dict(width_ratios=[1.3, 1]))
    xs = np.arange(len(res))
    for j, r in res.iterrows():
        ax[0].bar(j - 0.2, r.wells_sbt_any_track, 0.38, color=COL[r.group], edgecolor=INK)
        ax[0].bar(j + 0.2, r.decoys_sbt_any_track, 0.38, color=COL["decoy"], edgecolor=INK, hatch="//")
        ax[0].text(j - 0.2, r.wells_sbt_any_track + 0.0004, f"{r.wells_sbt_any_track:.1%}", ha="center", va="bottom", fontsize=9)
        ax[0].text(j + 0.2, r.decoys_sbt_any_track + 0.0004, f"{r.decoys_sbt_any_track:.1%}", ha="center", va="bottom", fontsize=9)
    ax[0].set_xticks(xs, [f"{g}\nn = {n}" for g, n in zip(res.group, res.n_wells)])
    ax[0].set_ylabel(f"share with a steady bright target within {R_M:.0f} m")
    ax[0].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
    ax[0].set_ylim(0, max(res.wells_sbt_any_track.max(), res.decoys_sbt_any_track.max()) * 1.2)
    ax[0].set_title("DEP wells (solid) vs matched decoys (hatched)", fontsize=11)
    im = ax[1].imshow(grid, cmap="Greys", origin="upper", extent=[-22.5, 22.5, 22.5, -22.5])
    ax[1].plot(*reg["best_shift_m"], marker="o", mfc="none", mec="#D97706", ms=14, mew=2)
    ax[1].set_xlabel("stack shift east (m)")
    ax[1].set_ylabel("stack shift north (m)")
    ax[1].invert_yaxis()
    ax[1].set_title("Active-well hit rate vs shift", fontsize=11)
    plt.colorbar(im, ax=ax[1], fraction=0.046)
    fig.suptitle(f"NISAR HH steady bright targets (D_A < {DA_MAX}, ≥ {BRIGHT_DB:.0f} dB above 250 m background), 9t",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / f"{stem}_9t.png", dpi=150)
    print("done", stem)


if __name__ == "__main__":
    main()
