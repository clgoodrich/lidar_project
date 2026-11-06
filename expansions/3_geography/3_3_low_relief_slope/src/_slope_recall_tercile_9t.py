"""3.3 S1. Out-of-fold pit recall at K = 40 per km2, stratified by local slope and relief on 9t.

Purpose
    Question 1 of fw_3_3. Does out-of-fold recall depend on slope and relief? Uses no new data.
    For each CV5 fold k, the fold-k model's floor probability raster is read on one shared window
    over the fold-k held-out blocks (no seam clipping, review F03). Scoring is the 3.0 reference
    scorer through _geo_xfer_lib (review F02). Blobs are cut at ek.policy_for("pit") (0.35), scored by
    mean probability, credited to a block by centroid, deduped, and ranked within the fold. The top
    round(40 x held-out km2) candidates are kept (per-fold budget, as in the archival sweep). Matching
    to annotated floors is greedy one-to-one at IoU 0.3 in score order.
    Footprint (review G-02). The 29 pit-free 9t blocks were in no training manifest, so every fold
    model is out of sample there. They join the held-out footprint of one fold each by the 3.0
    round_robin rule, so the budget sees the same area a target would.
    Audit (P2). Audit blocks are removed from the footprint through ek.require_audit. Before P2 is
    frozen, --no-audit-list runs without it and labels the output "no audit exclusion, exploratory". Each floor gets a found flag plus slope, relief,
    area, depth and void covariates. Recall is reported per slope tercile, at the feature level
    and at the block level, with 95% block-bootstrap intervals (B = 2000). The primary statistic
    is lowest-tercile recall minus highest-tercile recall (feature level, paired draws).

Inputs (all held)
    data/9t/models/pit/unet_cv5/fold{k}/pit_prob_floor_cvfold{k}_9t_05.tif   per-fold probabilities
    data/9t/models/pit/unet_cv5/pit_cv5_fold_assignment_9t.csv               pit -> block -> fold
    data/9t/derived/05/pit_blocks_9t.gpkg (layer blocks)                      375 m blocks
    qgis/annotations/annotations_proj.gpkg (layer pit_inside)                 annotated floors
    data/9t/derived/1m/slope_9t_1m.tif, dem_9t_1m.tif                         slope, relief
    data/9t/derived/05/dem_9t_05.tif, ground_density_9t_05.tif                depth, void

Outputs (one run folder, ek.new_run)
    expansions/3_geography/3_3_low_relief_slope/results/<run_id>/
        slope_recall_features_9t.csv      one row per floor (found, slope, relief, area, depth, void)
        slope_recall_blocks_9t.csv        one row per held-out block (hits, n_truth, slope, relief)
        slope_recall_terciles_9t.csv      recall per tercile, feature and block level, with CI
        slope_recall_summary_9t.json      cut points, primary difference, decision, counts
        slope_recall_terciles_9t.png      figure (blue observed, grey overall)
        _CONFIG.json, _RUN.md, _PROVENANCE.json
    3.1 and 3.2 no longer score against this blocks CSV. They use the 3.0 reference tables.

Limits, stated
    The reference uses the original CV5 sampler (protocol section 3). Window reads can reach
    held-out ground, so 9t recall is optimistic. Swap fold_prob to the P1 isolated predictions
    when they exist. Pit-free blocks are scored with the fold model the round_robin rule names.
    Slope differences are associations, not slope causation.

Run
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_recall_tercile_9t.py
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_recall_tercile_9t.py --folds 0 --B 200
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
sys.path.insert(0, str(HERE.parents[2] / "3_1_warren_forest_mckean" / "src"))
import expkit as ek  # noqa: E402
import _geo_xfer_lib as xl  # noqa: E402

CFG = HERE.parent / "config_3_3.json"


# ----------------------------------------------------------------------------- terrain rasters
def nan_uniform(a, size):
    from scipy.ndimage import uniform_filter
    v = np.isfinite(a)
    z = np.where(v, a, 0).astype(np.float64)
    s = uniform_filter(z, size, mode="nearest")
    c = uniform_filter(v.astype(np.float64), size, mode="nearest")
    out = np.full(a.shape, np.nan)
    np.divide(s, c, out=out, where=c > 0.2)
    return out


def local_relief(dem, size):
    from scipy.ndimage import maximum_filter, minimum_filter
    v = np.isfinite(dem)
    hi = maximum_filter(np.where(v, dem, -np.inf), size, mode="nearest")
    lo = minimum_filter(np.where(v, dem, np.inf), size, mode="nearest")
    r = hi - lo
    r[~np.isfinite(r)] = np.nan
    return r


def read_masked(path):
    import rasterio
    with rasterio.open(path) as r:
        ek.assert_crs(r)
        a = r.read(1).astype(np.float64)
        if r.nodata is not None:
            a[a == r.nodata] = np.nan
        return a, r.transform


def sample(arr, transform, xs, ys):
    from rasterio.transform import rowcol
    rr, cc = rowcol(transform, xs, ys)
    rr, cc = np.asarray(rr), np.asarray(cc)
    ok = (rr >= 0) & (rr < arr.shape[0]) & (cc >= 0) & (cc < arr.shape[1])
    out = np.full(len(rr), np.nan)
    out[ok] = arr[rr[ok], cc[ok]]
    return out


def feature_depth_void(floors, dem05_path, gd05_path, ring_m, void_m):
    """Depth = median DEM in a ring outside the floor minus min DEM in the floor. Void = share of
    0.5 m cells with no ground return inside floor + void_m."""
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds
    depth, void = [], []
    with rasterio.open(dem05_path) as rd, rasterio.open(gd05_path) as rg:
        ek.assert_crs(rd); ek.assert_crs(rg)
        for g in floors.geometry:
            outer = g.buffer(max(ring_m, void_m))
            w = from_bounds(*outer.bounds, transform=rd.transform).round_offsets().round_lengths()
            z = rd.read(1, window=w, boundless=True, fill_value=np.nan).astype(np.float64)
            if rd.nodata is not None:
                z[z == rd.nodata] = np.nan
            tf = rd.window_transform(w)
            inside = ~geometry_mask([g], z.shape, tf)
            ring = ~geometry_mask([g.buffer(ring_m).difference(g)], z.shape, tf)
            zi, zr = z[inside], z[ring]
            depth.append(float(np.nanmedian(zr) - np.nanmin(zi)) if np.isfinite(zi).any() and np.isfinite(zr).any() else np.nan)
            wg = from_bounds(*outer.bounds, transform=rg.transform).round_offsets().round_lengths()
            d = rg.read(1, window=wg, boundless=True, fill_value=0)
            vm = ~geometry_mask([g.buffer(void_m)], d.shape, rg.window_transform(wg))
            void.append(float((d[vm] == 0).mean()) if vm.any() else np.nan)
    return np.array(depth), np.array(void)


# ----------------------------------------------------------------------------- per-fold scoring
def fold_path(spec, k):
    return xl.resolve_path({**spec, "rel": spec["rel"].format(k=k)})


def fold_candidates(prob_path, held_blocks, buf_m, policy):
    """Blobs from the fold raster on one shared window over the held-out blocks (xl.candidates_for_blocks).
    Each blob is credited to one block by centroid. No seam clipping or duplicates (review F03)."""
    c = xl.candidates_for_blocks(prob_path, held_blocks, policy, halo_m=buf_m)
    return c.rename(columns={"block_id": "src_block"}) if len(c) else c


def fold_candidates_blockwise_old(prob_path, held_blocks, buf_m, thr, min_area):
    """The pre-2026-11-06 blockwise reader, kept only so the seam regression test can show the defect."""
    import geopandas as gpd
    import rasterio
    from rasterio.windows import from_bounds
    parts = []
    with rasterio.open(prob_path) as r:
        ek.assert_crs(r)
        for bid, g in zip(held_blocks.block_id, held_blocks.geometry):
            w = from_bounds(*g.buffer(buf_m).bounds, transform=r.transform).round_offsets().round_lengths()
            p = r.read(1, window=w, boundless=True, fill_value=0).astype(np.float32)
            p[p < 0] = 0
            c = xl.candidates_from_prob(p, r.window_transform(w), r.crs, thr=thr, min_area=min_area)
            if not len(c):
                continue
            rp = c.geometry.representative_point()
            c = c[rp.within(g)].copy()
            c["src_block"] = bid
            parts.append(c)
    if not parts:
        return gpd.GeoDataFrame({"score": [], "area_m2": []}, geometry=[], crs=ek.DST_CRS)
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=ek.DST_CRS)


def proposal_cutoffs(cfg, folds):
    """Proposal cutoff per fold.

    policy_for      ek.policy_for("pit") cutoff for every fold (primary, 0.35).
    fixed           cfg proposal_thr for every fold (fw_00 section 4 text, 0.10).
    loo_max_recall  the archival rule. For fold k, the cutoff with the highest recall pooled over
                    the OTHER folds' held-out blocks at IoU 0.3, ties to the higher cutoff
                    (reuses _cv5_pr_calibration_pit_pad_9t.proposal_thr). Fold k labels unread.
    Also returns the frozen target cutoff, the same rule pooled over all folds (for 3.1 and 3.2).
    """
    mode = cfg.get("proposal_policy", "policy_for")
    if mode == "policy_for":                 # review F02. The one scoring policy
        t = float(xl.policy("pit")["cutoff"])
        return {k: t for k in folds}, t
    if mode == "fixed":
        t = float(cfg["proposal_thr"])
        return {k: t for k in folds}, t
    from _cv5_pr_calibration_pit_pad_9t import proposal_thr
    counts = pd.read_csv(xl.need(xl.resolve_path(cfg["inputs"]["sweep_counts"]), "archival sweep per-block counts"))
    per = {k: proposal_thr(counts, k)[0] for k in folds}
    h = counts[(counts.split == "heldout") & (counts.tau == 0.3)]
    g = h.groupby("thr")[["tp_gt", "n_gt"]].sum()
    r = (g.tp_gt / g.n_gt).to_numpy()
    frozen = float(g.index.to_numpy()[np.isclose(r, r.max())].max())
    return per, frozen


def run_folds(cfg, folds, blocks, floors, fold_of_block, cut):
    feats, per_blocks, fold_summ = [], [], []
    for k in folds:
        t0 = time.time()
        held_ids = sorted(b for b, f in fold_of_block.items() if f == k)
        hb = blocks[blocks.block_id.isin(held_ids)].copy()
        ek.assert_rows(hb, len(held_ids), f"fold {k} held-out blocks")
        prob_path = xl.need(fold_path(cfg["inputs"]["fold_prob"], k), f"fold {k} probability raster")
        pol = xl.policy("pit", cutoff=cut[k])
        cands = fold_candidates(prob_path, hb, cfg["score_buffer_m"], pol)
        tr = floors[floors.fold == k][["truth_id", "geometry"]]
        summ, per, sc, st = xl.score_area(cands, tr, hb, k_per_km2=cfg["k_per_km2"], policy=pol)
        summ30, per30, _, _ = xl.score_area(cands, tr, hb, k_per_km2=cfg["k_sensitivity_per_km2"], policy=pol)
        per["hits_k30"] = per.block_id.map(per30.set_index("block_id").hits).astype(int)
        n_lost = len(tr) - len(st)
        per["fold"] = k
        st = st.assign(fold=k)
        feats.append(st)
        per_blocks.append(per)
        fold_summ.append({"fold": k, "proposal_thr": cut[k], **summ, "recall_k30": summ30["recall"], "truth_outside_blocks": n_lost,
                          "sec": round(time.time() - t0, 1)})
        print(f"  fold {k}: {len(hb)} blocks, {len(cands)} blobs, K={summ['k']}, "
              f"recall@40 {summ['recall']:.3f} ({summ['hits']}/{summ['n_truth']}), "
              f"@30 {summ30['recall']:.3f}, {time.time() - t0:.0f}s")
    return pd.concat(feats, ignore_index=True), pd.concat(per_blocks, ignore_index=True), fold_summ


# ----------------------------------------------------------------------------- statistics
def tercile_table(feat, blk, B, seed):
    """Feature-level (paired block draws) and block-level (independent groups) tercile recall."""
    rows, out = [], {}
    bl = np.array(sorted(feat.block_id.unique()))
    pos = {b: i for i, b in enumerate(bl)}
    bi = feat.block_id.map(pos).to_numpy()
    idx = list(range(len(bl)))
    for col in ("slope_tercile", "relief_tercile"):
        H = np.zeros((len(bl), 3)); N = np.zeros((len(bl), 3))
        t = feat[col].to_numpy()
        ok = t >= 0
        np.add.at(N, (bi[ok], t[ok]), 1)
        np.add.at(H, (bi[ok], t[ok]), feat.found.to_numpy()[ok].astype(float))

        def rec(tt, H=H, N=N):
            return lambda bs: H[bs, tt].sum() / N[bs, tt].sum() if N[bs, tt].sum() else np.nan
        for tt in (0, 1, 2):
            p, lo, hi, _ = ek.block_bootstrap(rec(tt), idx, B=B, seed=seed)
            sub = feat[feat[col] == tt]
            rows.append({"level": "feature", "covariate": col.split("_")[0], "tercile": tt, "recall": p,
                         "lo": lo, "hi": hi, "n_features": len(sub), "n_found": int(sub.found.sum()),
                         "n_blocks": int(sub.block_id.nunique())})
        lowf, highf = rec(0), rec(2)
        d, lo, hi, dr = ek.block_bootstrap(lambda bs: lowf(bs) - highf(bs), idx, B=B, seed=seed)
        out[f"feature_{col}_low_minus_high"] = {"diff": d, "lo": lo, "hi": hi, "undefined_share": ek.undefined_share(dr),
                                                "_draws": dr}
    for col in ("slope_tercile", "relief_tercile"):
        groups = {}
        for tt in (0, 1, 2):
            g = blk[blk[col] == tt]
            rws = list(zip(g.hits, g.n_truth))
            p, lo, hi, _ = ek.block_bootstrap(xl.pooled_recall, rws, B=B, seed=seed)
            rows.append({"level": "block", "covariate": col.split("_")[0], "tercile": tt, "recall": p,
                         "lo": lo, "hi": hi, "n_features": int(g.n_truth.sum()), "n_found": int(g.hits.sum()),
                         "n_blocks": len(g)})
            groups[tt] = rws
        d, lo, hi = ek.bootstrap_diff(xl.pooled_recall, groups[0], xl.pooled_recall, groups[2], B=B, seed=seed)
        out[f"block_{col}_low_minus_high"] = {"diff": d, "lo": lo, "hi": hi}
    return pd.DataFrame(rows), out


def figure(tab, overall, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # ek.PALETTE lost/found set. Worst pair dE 21.1 deutan, 22.6 normal (dataviz validator,
    # --pairs all, CLAUDE.md). Only blue and grey are used here, and markers differ.
    blue, grey, ink = ek.PALETTE["blue"], ek.PALETTE["grey"], ek.PALETTE["charcoal"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, level in zip(axes, ("feature", "block")):
        d = tab[(tab.level == level) & (tab.covariate == "slope")].sort_values("tercile")
        x = d.tercile.to_numpy()
        ax.axhspan(overall[1], overall[2], color=grey, alpha=0.25, lw=0)
        ax.axhline(overall[0], color=grey, ls="--", lw=1.2, label="all features")
        ax.errorbar(x, d.recall, yerr=[d.recall - d.lo, d.hi - d.recall], fmt="o", color=blue,
                    capsize=4, ms=7, label="slope tercile")
        for xi, r, n in zip(x, d.recall, d.n_features):
            ax.annotate(f"n={n}", (xi, r), textcoords="offset points", xytext=(10, -4), fontsize=8, color=ink)
        ax.set_xticks([0, 1, 2], ["low", "middle", "high"])
        ax.set_xlabel(f"slope tercile ({level} level)")
        ax.set_xlim(-0.5, 2.7)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("recall at 40 per km2")
    axes[0].legend(frameon=False, fontsize=8, loc="lower left")
    fig.suptitle("9t out-of-fold pit recall by local slope, 95% block bootstrap", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------------- main
def footprint_folds(cfg, blocks, fa, fill: str, no_audit: bool):
    """Held-out fold of every scored block, the pit-free blocks added, the audit label and audit ids.
    Fold of a pit-bearing block comes from the historical split (ek.read_split_csv) and must agree with the
    fold assignment. Pit-free blocks get one fold each by the 3.0 round_robin rule (review G-02).
    Audit blocks leave the footprint (ek.require_audit, review P2-01)."""
    sys.path.insert(0, str(HERE.parents[2] / "3_0_transfer_protocol" / "src"))
    from _transfer_ref_tables_9t import fill_assignment
    sp = xl.need(xl.resolve_path(cfg["inputs"]["historical_split"]), "historical CV5 split CSV")
    sdf = ek.read_split_csv(sp)
    h = sdf[sdf.role == "held_out"]
    fold_of = {int(b): int(f) for b, f in zip(h.block_id, h.fold)}
    fa_fold = fa.groupby("block_id").fold.first().astype(int).to_dict()
    bad = {b: (f, fold_of.get(b)) for b, f in fa_fold.items() if fold_of.get(b) != f}
    if bad:
        raise AssertionError(f"split CSV and fold assignment disagree on blocks {list(bad)[:5]}")
    fill_ids = sorted(set(blocks.block_id.astype(int)) - set(fold_of)) if fill == "round_robin" else []
    fold_of.update(fill_assignment(fill_ids, "round_robin") if fill_ids else {})
    aud = ek.require_audit(xl.resolve_path(cfg["assumed"]["audit_blocks"]["spec"]), allow_missing=no_audit)
    if aud is None:
        label, ids = "no audit exclusion, exploratory (P2 audit set not frozen)", set()
    else:
        ids = ek.audit_ids(aud, roles=("audit",))
        label = f"P2 audit blocks excluded ({len(ids)})"
    fold_of = {b: f for b, f in fold_of.items() if b not in ids}
    return fold_of, fill_ids, label, ids


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--folds", type=int, nargs="*", default=None)
    ap.add_argument("--B", type=int, default=None, help="bootstrap draws (default from config)")
    ap.add_argument("--out-base", default=None, help="parent of the run folder (default expansion results/)")
    ap.add_argument("--no-audit-list", action="store_true",
                    help="run before P2 is frozen. Output is labelled no audit exclusion, exploratory")
    ap.add_argument("--fill", choices=("round_robin", "none"), default="round_robin",
                    help="pit-free blocks join one fold each (3.0 rule, review G-02), or are left out")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    B = a.B or cfg["bootstrap_B"]
    folds = a.folds if a.folds is not None else list(range(cfg["n_folds"]))
    seed = cfg["master_seed"]
    I = cfg["inputs"]
    import geopandas as gpd
    from _common import read_layer

    fa = pd.read_csv(xl.need(xl.resolve_path(I["fold_assignment"]), "CV5 fold assignment"))
    n0 = len(fa)
    fa = fa.dropna(subset=["block_id", "fold"])
    fa["block_id"] = fa.block_id.astype(int); fa["fold"] = fa.fold.astype(int)
    print(f"fold assignment: {n0} pits, {len(fa)} with a block (dropped {n0 - len(fa)} off-tile rows)")
    ek.assert_unique(fa, "pit_inside_id")
    blocks = gpd.read_file(xl.need(xl.resolve_path(I["blocks"]), "9t pit blocks"), layer="blocks")
    ek.assert_crs(blocks)
    fl = read_layer(xl.need(xl.resolve_path(I["truth_gpkg"]), "annotations"), I["truth_floor_layer"]).to_crs(ek.DST_CRS)
    fl = fl[["pit_inside_id", "geometry"]].dissolve(by="pit_inside_id").reset_index()
    floors = fl.merge(fa[["pit_inside_id", "block_id", "fold"]], on="pit_inside_id", how="inner")
    ek.assert_rows(floors, len(fa), "floors joined to fold assignment")
    floors = floors.rename(columns={"pit_inside_id": "truth_id"}).drop(columns="block_id")
    fold_of_block, fill_ids, audit_label, audit_ids = footprint_folds(cfg, blocks, fa, a.fill, a.no_audit_list)
    floors = floors[~floors.truth_id.isin(fa.loc[fa.block_id.isin(audit_ids), "pit_inside_id"])]

    run = ek.new_run("3.3", "slope_recall", {**cfg, "folds": folds, "B": B}, base=Path(a.out_base) if a.out_base else None,
                     why="S1 slope stratification of 9t out-of-fold recall at K=40 per km2.")
    print(f"run folder {run}")
    cut, frozen_cut = proposal_cutoffs(cfg, folds)
    print(f"proposal policy {cfg.get('proposal_policy', 'fixed')}: per fold {cut}, frozen target cutoff {frozen_cut}")
    feat, blk, fold_summ = run_folds(cfg, folds, blocks, floors, fold_of_block, cut)
    ek.assert_no_nan(blk.block_id, "block ids")
    ek.assert_unique(feat, "truth_id")

    # terrain covariates
    slope, tf1 = read_masked(xl.resolve_path(I["slope_1m"]))
    dem1, tf1d = read_masked(xl.resolve_path(I["dem_1m"]))
    s_win = nan_uniform(slope, cfg["slope_window_m"])
    rel = local_relief(dem1, cfg["relief_window_m"] + 1)
    rp = feat.geometry.representative_point()
    feat["x"], feat["y"] = rp.x.to_numpy(), rp.y.to_numpy()
    feat["slope_25m"] = sample(s_win, tf1, feat.x, feat.y)
    feat["relief_50m"] = sample(rel, tf1d, feat.x, feat.y)
    feat["area_m2"] = feat.geometry.area
    feat["depth_m"], feat["void_frac"] = feature_depth_void(
        feat, xl.resolve_path(I["dem_05"]), xl.resolve_path(I["ground_density_05"]), cfg["depth_ring_m"], cfg["void_buffer_m"])
    bsel = blocks.set_index("block_id").loc[blk.block_id.to_numpy()].reset_index()
    import rasterio
    from rasterio.features import geometry_mask
    bs, br = [], []
    for g in bsel.geometry:
        m = ~geometry_mask([g], slope.shape, tf1)
        bs.append(float(np.nanmean(slope[m]))); br.append(float(np.nanmean(rel[m])))
    blk["slope_mean"], blk["relief_mean"] = bs, br
    feat["slope_tercile"], cut_fs = xl.terciles(feat.slope_25m)
    feat["relief_tercile"], cut_fr = xl.terciles(feat.relief_50m)
    tb = blk.n_truth > 0                     # cut points on pit-bearing blocks, as before the G-02 fill
    _, cut_bs = xl.terciles(blk.slope_mean[tb])
    _, cut_br = xl.terciles(blk.relief_mean[tb])
    blk["slope_tercile"], _ = xl.terciles(blk.slope_mean, cut_bs)
    blk["relief_tercile"], _ = xl.terciles(blk.relief_mean, cut_br)

    tab, diffs = tercile_table(feat, blk, B, seed)
    overall = ek.block_bootstrap(xl.pooled_recall, list(zip(blk.hits, blk.n_truth)), B=B, seed=seed)[:3]
    draws = {k: v.pop("_draws", None) for k, v in diffs.items()}
    prim = dict(diffs["feature_slope_tercile_low_minus_high"])
    margin = cfg.get("margin_delta")
    if margin is None:
        raise SystemExit("config margin_delta is unset (user default 0.03 recall)")
    mult = cfg["multiplicity"]                    # Holm over the declared primary gates (one, Q1 feature slope)
    h = xl.hg.holm_input(mult["gate"], draws["feature_slope_tercile_low_minus_high"], prim["lo"], prim["hi"],
                         float(margin), "noninferiority", mult["family"])
    decision = h["decision_partial"]
    prim.update({"p_one_sided": h["p_one_sided"], "decision_basis": h["decision_partial_basis"],
                 "multiplicity": {"method": h["method"], "family": h["family"], "max_undefined": h["max_undefined"]}})
    for k, v in diffs.items():
        if k != "feature_slope_tercile_low_minus_high":
            v["decision"] = "not gated (secondary)"

    fcsv, bcsv, tcsv = run / "slope_recall_features_9t.csv", run / "slope_recall_blocks_9t.csv", run / "slope_recall_terciles_9t.csv"
    feat.drop(columns="geometry").to_csv(fcsv, index=False)
    blk.to_csv(bcsv, index=False)
    tab.to_csv(tcsv, index=False)
    png = run / "slope_recall_terciles_9t.png"
    figure(tab, overall, png)
    pol = xl.policy("pit")
    summ = {"evidence_level": "(a) drawn features, exploratory association",
            "policy": pol, "policy_hash": pol["policy_hash"],
            "footprint": {"rule": a.fill, "decided": cfg.get("_footprint_note"), "n_blocks": int(len(blk)), "n_pit_free_blocks_added": len(fill_ids),
                          "n_blocks_with_truth": int((blk.n_truth > 0).sum())},
            "audit": audit_label,
            "split_source": "historical trainer split read with ek.read_split_csv",
            "reference_caveat": "original CV5 sampler, not P1 isolated (protocol section 3)",
            "k_per_km2": cfg["k_per_km2"], "iou_tau": cfg["iou_tau"], "proposal_policy": cfg.get("proposal_policy", "fixed"),
            "proposal_thr_per_fold": cut, "frozen_target_proposal_thr": frozen_cut,
            "B": B, "seed": seed, "folds": folds, "per_fold": fold_summ,
            "overall_recall": {"recall": overall[0], "lo": overall[1], "hi": overall[2],
                               "hits": int(blk.hits.sum()), "n_truth": int(blk.n_truth.sum()),
                               "n_blocks": int(len(blk))},
            "cut_points": {"feature_slope_deg": cut_fs, "feature_relief_m": cut_fr,
                           "block_slope_deg": cut_bs, "block_relief_m": cut_br},
            "primary": {"statistic": "feature-level recall, lowest minus highest slope tercile", **prim,
                        "margin": margin, "decision": decision},
            "secondary": diffs, "n_features": int(len(feat)), "n_blocks": int(len(blk)),
            "n_feature_blocks_independent": int(feat.block_id.nunique())}
    js = run / "slope_recall_summary_9t.json"
    js.write_text(json.dumps(summ, indent=2, default=float), encoding="utf-8")
    ins = [xl.resolve_path(I["fold_assignment"]), xl.resolve_path(I["blocks"]), xl.resolve_path(I["truth_gpkg"]),
           xl.resolve_path(I["slope_1m"]), xl.resolve_path(I["dem_1m"])]
    ins += [fold_path(I["fold_prob"], k) for k in folds]
    ek.write_provenance(run, inputs=ins, outputs=[fcsv, bcsv, tcsv, js, png],
                        params={"B": B, "folds": folds}, seeds={"master": seed}, hash_limit_mb=100)
    print(tab.to_string(index=False))
    print(f"\nprimary low-high slope (feature): {prim['diff']:+.3f} [{prim['lo']:+.3f}, {prim['hi']:+.3f}] -> {decision}")
    print(f"outputs in {run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
