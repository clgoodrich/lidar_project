"""Map the CV5 pit predictions at threshold 0.50 that match no annotated pit.

At thr 0.50 the pooled centroid-matched result is 587 predictions against 424
annotated pits, of which 385 match 1:1. This script exports the residue so the
failures can be looked at rather than summarised:

    unmatched_pred  prediction whose centroid is in no annotated rim  (FP)
    matched_pred    prediction greedy-matched to a rim                (TP)
    missed_rim      annotated rim holding no prediction centroid      (FN)
    matched_rim     annotated rim that was located

Every prediction comes from the fold model that did NOT train on the block it
falls in, so the false positives are honest held-out failures, not memorisation
residue.

`near_rim_m` on unmatched predictions is the distance to the nearest annotated
rim. It separates the two failure modes that matter: a few metres means the
model found the pit but its blob centroid drifted outside the rim, tens of
metres means it fired on something else entirely.

Outputs (data/derivatives/eval_9t_centroid_matching/):
    pit_cv5_centroid_match_thr0p50_9t_05.gpkg   4 layers, EPSG:6346
    pit_cv5_unmatched_map_thr0p50_9t_05.png     overview + 4 zoom panels
    _pit_cv5_unmatched_thr0p50_9t.json          counts and distance stats

Reproduce:
  python notebooks/wellsight_v2/eval/_map_cv5_unmatched_pit_thr0p50_9t.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio

matplotlib.use("Agg")
import matplotlib.pyplot as plt                                  # noqa: E402
from matplotlib.patches import Patch                             # noqa: E402
from rasterio.features import rasterize as _rast                 # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "notebooks" / "wellsight_v2"),
                str(ROOT / "notebooks" / "wellsight_v2" / "pits"),
                str(ROOT / "notebooks" / "wellsight_v2" / "eval")]

from _common import DERIV_9T                                     # noqa: E402
from _pit_unet_cv5 import assign_folds, polygonize               # noqa: E402
from _cv5_centroid_precision_pit_pad_9t import (ANN_GPKG, CRS,   # noqa: E402
                                                CV_SEED)

OUT = ROOT / "data" / "derivatives" / "eval_9t_centroid_matching"
HILLSHADE = DERIV_9T / "hillshade_9t_05.tif"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"

THR = 0.50
MIN_AREA_M2 = 4.0
SCORE_BUF_M = 40.0
K = 5
N_ZOOM = 4
ZOOM_HALF_M = 60.0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    man = pd.read_csv(DERIV_9T / "pit_dataset_manifest.csv")
    blocks = gpd.read_file(DERIV_9T / "pit_blocks_9t.gpkg",
                           layer="blocks").to_crs(CRS)
    nper = man.groupby("block_id").size().rename("n_pits").reset_index()
    fo = assign_folds(nper[["block_id", "n_pits"]], K, CV_SEED)
    man["fold"] = man.block_id.map(fo)
    blocks["fold"] = blocks.block_id.map(fo)

    rims = gpd.read_file(ANN_GPKG, layer="pit_outside").to_crs(CRS)
    rims = (rims[["pit_id", "geometry"]].dissolve(by="pit_id").reset_index()
            .merge(man[["pit_id", "fold"]], on="pit_id", how="inner"))

    with rasterio.open(FEATURES) as r:
        tf, rcrs = r.transform, r.crs

    pred_parts, rim_parts = [], []
    for k in range(K):
        tif = DERIV_9T / f"pit_unet_cv5/fold{k}/pit_prob_floor_cvfold{k}_9t_05.tif"
        with rasterio.open(tif) as r:
            prob = r.read(1).astype(np.float32)
        hb = sorted(man.loc[man.fold == k, "block_id"].unique())
        foot = blocks.loc[blocks.block_id.isin(hb)].geometry.union_all()
        keep = _rast([(foot.buffer(SCORE_BUF_M), 1)], out_shape=prob.shape,
                     transform=tf, fill=0, dtype="uint8").astype(bool)
        allp = polygonize(np.where(keep, prob, 0.0).astype(np.float32),
                          tf, rcrs, THR, min_area=MIN_AREA_M2)
        hp = (allp[allp.geometry.centroid.within(foot)].reset_index(drop=True)
              if len(allp) else allp)
        gt = rims[rims.fold == k].reset_index(drop=True)

        # greedy 1:1 centroid matching, highest-scoring prediction first
        cents = hp.geometry.centroid
        sidx = hp.sindex
        pairs = []
        for gi, r_ in enumerate(gt.itertuples()):
            for pj in sidx.intersection(r_.geometry.bounds):
                if r_.geometry.contains(cents.iloc[int(pj)]):
                    pairs.append((gi, int(pj), float(hp["score"].iloc[int(pj)])))
        ug, up = set(), set()
        for gi, pj, _ in sorted(pairs, key=lambda t: -t[2]):
            if gi in ug or pj in up:
                continue
            ug.add(gi); up.add(pj)

        hp = hp.copy()
        hp["fold"] = k
        hp["matched"] = [i in up for i in range(len(hp))]
        hp["area_m2"] = hp.geometry.area.round(1)
        gt = gt.copy()
        gt["fold"] = k
        gt["located"] = [i in ug for i in range(len(gt))]
        pred_parts.append(hp)
        rim_parts.append(gt)
        print(f"  fold {k}: {len(hp):4d} pred ({int(hp.matched.sum())} matched), "
              f"{len(gt):3d} rims ({int(gt.located.sum())} located)")

    pred = gpd.GeoDataFrame(pd.concat(pred_parts, ignore_index=True), crs=CRS)
    rim = gpd.GeoDataFrame(pd.concat(rim_parts, ignore_index=True), crs=CRS)
    unm = pred[~pred.matched].reset_index(drop=True)
    mis = rim[~rim.located].reset_index(drop=True)

    # distance from each unmatched prediction to the nearest annotated rim
    if len(unm):
        allrim = rim.geometry.union_all()
        unm["near_rim_m"] = [round(g.centroid.distance(allrim), 1)
                             for g in unm.geometry]

    gpkg = OUT / "pit_cv5_centroid_match_thr0p50_9t_05.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    for nm, g in (("unmatched_pred", unm),
                  ("matched_pred", pred[pred.matched]),
                  ("missed_rim", mis),
                  ("matched_rim", rim[rim.located])):
        if len(g):
            g.reset_index(drop=True).to_file(gpkg, layer=nm, driver="GPKG")

    print(f"\nthr {THR}: {len(pred)} predictions, {int(pred.matched.sum())} matched, "
          f"{len(unm)} UNMATCHED")
    print(f"          {len(rim)} rims, {int(rim.located.sum())} located, "
          f"{len(mis)} MISSED")
    stats = {}
    if len(unm):
        d = unm.near_rim_m
        for lo, hi in ((0, 5), (5, 15), (15, 50), (50, 1e9)):
            n = int(((d >= lo) & (d < hi)).sum())
            lab = f"{lo}-{hi:g} m" if hi < 1e9 else f">{lo} m"
            print(f"   unmatched within {lab:>10s} of a rim: {n:4d} "
                  f"({100*n/len(unm):.1f}%)")
            stats[lab] = n
        print(f"   median distance to nearest rim: {d.median():.1f} m")

    # ---- figure: overview + zooms on the worst offenders ----
    with rasterio.open(HILLSHADE) as r:
        hs = r.read(1).astype(np.float32)
        hb = r.bounds
    ext = (hb.left, hb.right, hb.bottom, hb.top)

    fig = plt.figure(figsize=(17, 9))
    gs = fig.add_gridspec(2, 3, width_ratios=[2.2, 1, 1])
    ax = fig.add_subplot(gs[:, 0])
    ax.imshow(hs, cmap="gray", extent=ext, origin="upper")
    if len(pred[pred.matched]):
        pred[pred.matched].plot(ax=ax, facecolor="none", edgecolor="#2ca02c",
                                linewidth=0.6)
    if len(unm):
        unm.plot(ax=ax, facecolor="none", edgecolor="#d62728", linewidth=0.9)
    if len(mis):
        mis.plot(ax=ax, facecolor="none", edgecolor="#1f77b4", linewidth=1.1,
                 linestyle="--")
    ax.set_title(f"9t held-out CV5 pit predictions at threshold {THR:.2f}\n"
                 f"{int(pred.matched.sum())} matched, {len(unm)} unmatched, "
                 f"{len(mis)} pits missed", fontsize=11)
    ax.set_xlim(hb.left, hb.right); ax.set_ylim(hb.bottom, hb.top)
    ax.set_xticks([]); ax.set_yticks([])
    ax.legend(handles=[
        Patch(facecolor="none", edgecolor="#2ca02c", label="matched prediction"),
        Patch(facecolor="none", edgecolor="#d62728", label="UNMATCHED prediction"),
        Patch(facecolor="none", edgecolor="#1f77b4", label="missed pit (rim)")],
        loc="lower left", fontsize=8, framealpha=0.9)

    # zoom on the largest unmatched predictions far from any rim
    if len(unm):
        far = unm[unm.near_rim_m > 15].sort_values("area_m2", ascending=False)
        pick = (far if len(far) >= N_ZOOM else unm.sort_values(
            "area_m2", ascending=False)).head(N_ZOOM)
        with rasterio.open(HILLSHADE) as r:
            slots = [(0, 1), (0, 2), (1, 1), (1, 2)]
            for i, (_, row) in enumerate(pick.iterrows()):
                axz = fig.add_subplot(gs[slots[i][0], slots[i][1]])
                c = row.geometry.centroid
                w = ZOOM_HALF_M
                win = rasterio.windows.from_bounds(
                    c.x - w, c.y - w, c.x + w, c.y + w, transform=r.transform)
                sub = r.read(1, window=win).astype(np.float32)
                axz.imshow(sub, cmap="gray",
                           extent=(c.x - w, c.x + w, c.y - w, c.y + w),
                           origin="upper")
                gpd.GeoSeries([row.geometry], crs=CRS).plot(
                    ax=axz, facecolor="none", edgecolor="#d62728", linewidth=1.6)
                near = rim[rim.geometry.centroid.distance(c) < w * 1.6]
                if len(near):
                    near.plot(ax=axz, facecolor="none", edgecolor="#1f77b4",
                              linewidth=1.0, linestyle="--")
                axz.set_title(f"P={row.score:.2f}  {row.area_m2:.0f} m$^2$\n"
                              f"{row.near_rim_m:.0f} m to nearest pit",
                              fontsize=8)
                axz.set_xticks([]); axz.set_yticks([])

    fig.suptitle("Unmatched pit predictions, 5-fold cross-validated, "
                 "centroid matching", fontsize=13)
    fig.tight_layout()
    png = OUT / "pit_cv5_unmatched_map_thr0p50_9t_05.png"
    fig.savefig(png, dpi=140, bbox_inches="tight")
    plt.close(fig)

    summ = {"threshold": THR, "n_pred": len(pred),
            "n_matched": int(pred.matched.sum()), "n_unmatched": len(unm),
            "n_rims": len(rim), "n_located": int(rim.located.sum()),
            "n_missed": len(mis),
            "precision": int(pred.matched.sum()) / max(len(pred), 1),
            "recall": int(rim.located.sum()) / max(len(rim), 1),
            "unmatched_distance_bins_m": stats,
            "unmatched_median_dist_m": float(unm.near_rim_m.median())
            if len(unm) else None}
    (OUT / "_pit_cv5_unmatched_thr0p50_9t.json").write_text(
        json.dumps(summ, indent=2, default=float))
    print(f"\nwrote {gpkg}\nwrote {png}\n"
          f"wrote {OUT / '_pit_cv5_unmatched_thr0p50_9t.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
