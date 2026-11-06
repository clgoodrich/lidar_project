"""6.3 S5. Pooled blind scoring of the three arms on the audit blocks, and the gate.

Purpose
    pool   For every arm and seed, average the five fold models' floor probabilities over each audit block (no
           fold trained on an audit block), extract candidates by the fw_00 rule (0.10 floor, 4 m2, mean score),
           keep the top K = 40 per km2 of audit area, then pool all arms and seeds and deduplicate by centroid
           within 5 m. The pooled sheet list carries no arm. The arm membership file is kept from reviewers.
           The pooled list is written in the S1 sample format so _confuser_sheets_9t.py and
           _confuser_agreement_9t.py label it once, blind to arm.
    score  Per arm and seed per audit block, count labelled confuser detections and match the top K to drawn
           pit floors (IoU 0.3, one to one). Seeds are averaged per block. Block is the resampling unit
           (paired bootstrap, the same blocks for both arms, B = 2000).
           Primary 1. Reduction = random minus confuser, labelled-confuser detections per km2 at K.
           Primary 2. Drawn-feature recall at K, confuser minus baseline, non-inferiority against delta.
           Gate. Success when the reduction lower bound clears the useful reduction and the recall lower bound
           clears minus delta. Failure when the reduction upper bound is under it or the recall upper bound is
           under minus delta. Else inconclusive. Both margins must be set in config before scoring.
           Also reported. P and U detections the confuser arm suppresses compared with baseline, seed spread, and a
           sign-flip permutation p value when there are fewer than 15 audit blocks.
Inputs
    expansions/6_adjacent/6_3_confuser_classes/models/unet_confuser_cv5/<arm>/seed<s>/fold<k>/pit_prob_floor_cvfold<k>_9t_05.tif
    audit_blocks (P2, assumed), pit_blocks_9t.gpkg, annotations_proj.gpkg layer pit_inside (held)
    data/9t/results/confusers/confuser_labels_adjudicated_pooled_9t.csv (after blind labelling)
Outputs (data/9t/results/confusers/)
    confuser_pooled_sample_9t.csv, confuser_pooled_members_9t.gpkg (arm key, keep from reviewers),
    confuser_arm_scores_9t.csv, confuser_gate_9t.json
Run
    python expansions/6_adjacent/6_3_confuser_classes/src/_confuser_pooled_score_9t.py pool
    python expansions/6_adjacent/6_3_confuser_classes/src/_confuser_pooled_score_9t.py score
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _confuser_common_9t as C
from _confuser_common_9t import ek


def prob_paths(models_root: Path, arm: str, seed: int) -> list[Path]:
    return sorted((models_root / arm / f"seed{seed}").glob("fold*/pit_prob_floor_cvfold*_05.tif"))


def arm_candidates(paths: list[Path], audit_blocks, crs: str, sc: dict):
    """Mean-of-folds probability per block, candidates whose centroid lies in that block.

    The read window is padded by sc['edge_pad_m'] (default 100 m) so a blob that crosses a block edge is
    polygonised whole and counted once, in the block that covers its centroid (duplicates from two padded
    windows are dropped). Without the pad, per-block extraction splits such blobs in two."""
    import geopandas as gpd
    import rasterio
    from rasterio.windows import from_bounds
    if not paths:
        raise C.MissingInput("no fold probability rasters for this arm and seed (train with --predict first)")
    pad = float(sc.get("edge_pad_m", 100.0))
    srcs = [rasterio.open(p) for p in paths]
    try:
        for s in srcs[1:]:
            if s.transform != srcs[0].transform:
                raise AssertionError("fold probability rasters are on different grids")
        rows = []
        for b in audit_blocks.itertuples():
            x0, y0, x1, y1 = b.geometry.bounds
            win = from_bounds(x0 - pad, y0 - pad, x1 + pad, y1 + pad,
                              transform=srcs[0].transform).round_offsets().round_lengths()
            stack = []
            for s in srcs:
                a = s.read(1, window=win, boundless=True, fill_value=0).astype(np.float32)
                if s.nodata is not None:
                    a[a == s.nodata] = np.nan
                stack.append(a)
            prob = np.nanmean(np.stack(stack), axis=0)
            g = C.extract_candidates(prob, srcs[0].window_transform(win), crs, sc["prob_floor"], sc["min_area_m2"])
            if len(g):
                g = g[b.geometry.covers(g.geometry.centroid)]
                g["block_id"] = int(b.block_id)
                rows.append(g)
    finally:
        for s in srcs:
            s.close()
    if not rows:
        return gpd.GeoDataFrame({"score": [], "area_m2": [], "block_id": []}, geometry=[], crs=crs)
    g = gpd.GeoDataFrame(pd.concat(rows, ignore_index=True), crs=crs)
    c = g.geometry.centroid
    key = pd.DataFrame({"x": c.x.round(3), "y": c.y.round(3), "a": g.area_m2.round(3)})
    g = g[~key.duplicated().to_numpy()].reset_index(drop=True)
    g["cand_id"] = np.arange(len(g))
    return g


def pool(members, dedupe_m: float):
    """members: top-K rows of every arm and seed. Adds pooled_id. Returns members and the blind pooled list."""
    import geopandas as gpd
    m = members.reset_index(drop=True).copy()
    xy = np.column_stack([m.geometry.centroid.x, m.geometry.centroid.y])
    m["pooled_id"] = [f"PL{c:05d}" for c in C.dedupe_centroids(xy, dedupe_m)]
    rep = m.sort_values("score", ascending=False).drop_duplicates("pooled_id")
    c = rep.geometry.centroid
    blind = pd.DataFrame({"uid": rep.pooled_id.values, "cx": c.x.values, "cy": c.y.values, "band": 0,
                          "incl_prob": 1.0, "score": np.nan, "relabel": False})
    rng = np.random.default_rng(0)
    blind = blind.iloc[rng.permutation(len(blind))].reset_index(drop=True)
    return gpd.GeoDataFrame(m, crs=members.crs), blind


def per_block_table(members, labels: pd.DataFrame, truth, audit_blocks, cfg: dict) -> pd.DataFrame:
    """One row per arm x seed x block: n_confuser, n_P, n_U, hits, n_truth, km2.

    Only truth whose centroid lies in an audit block is in the denominator (review 6.3 minor, SH-02 pattern).
    Truth outside the audit set is still matched, so a detection on it cannot claim an eligible truth instead,
    but such a hit is never counted. A hit is counted in the block of the truth it matched, so per block
    hits never exceed n_truth.
    """
    conf = set(cfg["classes"]["confuser"])
    lab = labels.set_index("uid")["class"]
    missing = set(members.pooled_id) - set(lab.index)
    if missing:
        raise AssertionError(f"{len(missing)} pooled detections have no label (label all before scoring)")
    m = members.assign(cls=members.pooled_id.map(lab))
    tb = C.block_of_points(np.column_stack([truth.geometry.centroid.x, truth.geometry.centroid.y]), audit_blocks)
    truth = truth.assign(block_id=tb)
    eligible = truth[truth.block_id.notna()]
    n_truth = eligible.groupby("block_id").size()
    truth_block = dict(zip(eligible.truth_id, eligible.block_id.astype(int)))
    km2 = dict(zip(audit_blocks.block_id.astype(int), audit_blocks.area / 1e6))
    rows = []
    for (arm, seed), g in m.groupby(["arm", "seed"]):
        g = g.reset_index(drop=True)
        g["truth_id"] = C.greedy_match(truth, g, cfg["score"]["iou"], truth_id="truth_id")
        hit_blocks = pd.Series([truth_block.get(t) for t in g.truth_id.dropna().unique()], dtype=float)
        for b in sorted(km2):
            gb = g[g.block_id == b]
            rows.append({"arm": arm, "seed": seed, "block_id": b, "km2": km2[b],
                         "n_confuser": int(gb.cls.isin(conf).sum()), "n_P": int((gb.cls == "P").sum()),
                         "n_U": int((gb.cls == "U").sum()), "hits": int((hit_blocks == b).sum()),
                         "n_truth": int(n_truth.get(b, 0))})
    return pd.DataFrame(rows)


def sign_flip_p(d: np.ndarray, B: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    obs = abs(d.mean())
    flips = rng.choice([-1, 1], size=(B, len(d)))
    return float((np.abs((flips * d).mean(1)) >= obs - 1e-12).mean())


def score(cfg: dict, tab: pd.DataFrame, members, labels: pd.DataFrame, B: int | None = None) -> dict:
    sc = cfg["score"]
    if sc.get("recall_margin_delta") is None or sc.get("useful_reduction_per_km2") is None:
        raise C.MissingInput("score.recall_margin_delta and score.useful_reduction_per_km2 must be set in "
                             "config_6_3.json before scoring (prespecify both, protocol section 16).")
    B = B or sc["B"]
    blk = tab.groupby(["arm", "block_id"]).agg(n_confuser=("n_confuser", "mean"), hits=("hits", "mean"),
                                               n_truth=("n_truth", "first"), km2=("km2", "first")).reset_index()
    per = {arm: g.set_index("block_id") for arm, g in blk.groupby("arm")}
    blocks = sorted(blk.block_id.unique())

    def conf_rate(arm):
        return lambda bl: per[arm].loc[bl, "n_confuser"].sum() / per[arm].loc[bl, "km2"].sum()

    def recall(arm):
        def f(bl):
            n = per[arm].loc[bl, "n_truth"].sum()
            return per[arm].loc[bl, "hits"].sum() / n if n else np.nan
        return f
    res = {"n_audit_blocks": len(blocks), "B": B, "k_per_km2": sc["k_per_km2"],
           "margins": {"useful_reduction_per_km2": sc["useful_reduction_per_km2"], "delta": sc["recall_margin_delta"]}}
    seed0 = ek.child_seed(cfg["train"]["master_seed"], 9, 9)
    red = ek.bootstrap_diff(conf_rate("random"), blocks, conf_rate("confuser"), blocks, B=B, seed=seed0, paired=True)
    rec = ek.bootstrap_diff(recall("confuser"), blocks, recall("baseline"), blocks, B=B, seed=seed0 + 1, paired=True)
    res["primary_1_reduction"] = dict(zip(("point", "lo95", "hi95"), red))
    res["primary_2_recall_diff"] = dict(zip(("point", "lo95", "hi95"), rec))
    u, dlt = sc["useful_reduction_per_km2"], sc["recall_margin_delta"]
    if red[1] > u and rec[1] > -dlt:
        gate = "success"
    elif red[2] < u or rec[2] < -dlt:
        gate = "failure"
    else:
        gate = "inconclusive"
    # seed spread (training variance, not landscapes)
    seed_stats = tab.groupby(["arm", "seed"]).apply(
        lambda g: pd.Series({"confuser_per_km2": g.n_confuser.sum() / g.km2.sum(),
                             "recall": g.hits.sum() / g.n_truth.sum() if g.n_truth.sum() else np.nan}),
        include_groups=False).reset_index()
    spread = seed_stats.groupby("arm").confuser_per_km2.agg(lambda s: float(s.max() - s.min())).to_dict()
    res["seed_spread_confuser_per_km2"] = spread
    if gate == "inconclusive" or max(spread.values(), default=0) > abs(red[0]):
        res["seed_note"] = "seed spread is at least the effect. Add seeds."
    res["gate"] = gate
    res["action"] = {"success": "Adopt the confuser arm for the next model.",
                     "failure": "Keep the finding. One failed run does not retire the idea.",
                     "inconclusive": "Report and add seeds or blocks. Not 'no effect'."}[gate]
    # suppression of possible wells and uncertain detections
    lab = labels.set_index("uid")["class"]
    ids = {arm: set(members.loc[members.arm == arm, "pooled_id"]) for arm in members.arm.unique()}
    if "baseline" in ids and "confuser" in ids:
        gone = ids["baseline"] - ids["confuser"]
        res["suppressed_vs_baseline"] = {"P": int(sum(lab.get(i) == "P" for i in gone)),
                                         "U": int(sum(lab.get(i) == "U" for i in gone)), "all": len(gone)}
    if len(blocks) < 15:
        d = np.array([conf_rate("random")([b]) - conf_rate("confuser")([b]) for b in blocks])
        res["bootstrap_note"] = "fewer than 15 audit blocks. The bootstrap is unreliable."
        res["permutation_p_reduction"] = sign_flip_p(d, B, seed0 + 2)
    res["per_arm_seed"] = seed_stats.to_dict(orient="records")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["pool", "score"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None, help="default data/9t/results/confusers/")
    ap.add_argument("--models", default=None, help="default expansions/.../6_3_confuser_classes/models/unet_confuser_cv5/")
    ap.add_argument("--audit-blocks", default=None)
    ap.add_argument("--labels", default=None)
    ap.add_argument("--B", type=int, default=None)
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    out = C.results_dir(cfg, a.out)
    ar = cfg["area"]
    sc = cfg["score"]
    blocks = C.read_vector(C.input_path(cfg, "blocks"), cfg["crs"], layer=cfg["inputs"]["blocks"]["layer"])
    audit = C.audit_block_ids(cfg, a.audit_blocks, roles=("audit",))     # sealed scoring ground only
    ab = blocks[blocks.block_id.isin(audit)].reset_index(drop=True)
    ek.assert_rows(ab, len(audit), "audit blocks found in block layer")
    mem_p = out / f"confuser_pooled_members_{ar}.gpkg"
    if a.stage == "pool":
        import geopandas as gpd
        root = Path(a.models) if a.models else ek.sub(cfg["exp_id"], "models") / "unet_confuser_cv5"
        km2 = float(ab.area.sum() / 1e6)
        parts = []
        for arm in cfg["train"]["arms"]:
            for s in cfg["train"]["seeds"]:
                g = arm_candidates(prob_paths(root, arm, s), ab, cfg["crs"], sc)
                top, k = C.top_k(g, km2, sc["k_per_km2"])
                parts.append(top.assign(arm=arm, seed=s))
        mem, blind = pool(gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=cfg["crs"]), sc["dedupe_m"])
        if mem_p.exists():
            mem_p.unlink()
        mem.to_file(mem_p, driver="GPKG")
        bp = out / f"confuser_pooled_sample_{ar}.csv"
        blind.to_csv(bp, index=False)
        C.provenance(cfg, out, "confpool", outputs=[mem_p, bp], params=sc)
        print(f"{len(mem)} arm detections pooled into {len(blind)} sheets\nwrote {bp}\nwrote {mem_p} (keep from reviewers)")
        return 0
    mem = C.read_vector(mem_p, cfg["crs"])
    lab_p = Path(a.labels) if a.labels else out / f"confuser_labels_adjudicated_pooled_{ar}.csv"
    if not lab_p.exists():
        raise C.MissingInput(f"{lab_p} missing. Label the pooled sheets blind, then run _confuser_agreement_9t.py.")
    labels = pd.read_csv(lab_p)
    tspec = cfg["inputs"]["truth"]
    truth = C.read_vector(C.input_path(cfg, "truth"), cfg["crs"], layer=tspec["layer"])
    truth = truth[[tspec["id"], "geometry"]].dissolve(by=tspec["id"]).reset_index().rename(columns={tspec["id"]: "truth_id"})
    tab = per_block_table(mem, labels, truth, ab, cfg)
    tp = out / f"confuser_arm_scores_{ar}.csv"
    tab.to_csv(tp, index=False)
    res = score(cfg, tab, mem, labels, a.B)
    gp = out / f"confuser_gate_{ar}.json"
    gp.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    C.provenance(cfg, out, "confscore", inputs=[mem_p, lab_p], outputs=[tp, gp], params=sc)
    print(json.dumps({k: res[k] for k in ("primary_1_reduction", "primary_2_recall_diff", "gate")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
