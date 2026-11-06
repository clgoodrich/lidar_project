"""3.1 S7b. Score a transfer arm once. Recall at K = 40 per km2, target minus 9t, with sensitivities.

Purpose
    The primary statistic of fw_3_1 and fw_3_2, scored by the 3.0 reference scorer (review F02 / G-03).
    Candidates come from the frozen ensemble probability raster, extracted once on a shared window over all
    test blocks (no seam clipping or duplicates, review F03), cut at ek.policy_for(task) (pit 0.35, pad 0.525),
    scored by mean probability, credited to a block by centroid, deduped, ranked, and cut at
    round(40 x test km2). Matching to the blind truth floors is greedy one-to-one at IoU 0.3 in score order.
    The difference against the 3.0 reference tables uses independent block bootstraps (B = 2000) and ek.decide
    against minus the margin. Fewer than 15 test blocks adds a permutation p-value and the unreliable-bootstrap
    note. Secondary. Density-scaled K (c fixed from 9t), K = 30, super-block resampling, the low-density stratum
    (or an explicit "empty" record with its reason), calibration of candidate scores, target feature density.

Guards (review F08 / G-06)
    The preregistration's json prereg block must declare cutoff, IoU, dedupe, K and checkpoint. They are compared
    with this run's policy and the inference record before scoring. The reference tables' stamped policy must
    equal the run's (ek.assert_same_policy) and their footprint must be all blocks.
    The inference record (written by _xfer_frozen_infer_wfm.py) is required. Its provisional_cv5 flag and the
    reference's lineage are carried into every output. A historical or provisional checkpoint on either side
    gives decision "descriptive", never a transfer verdict.
    --not-preregistered stamps every output NOT A PREREGISTERED SCORE. A second scoring run for the same
    prereg hash is refused unless --allow-rescore.

Inputs
    prob      data/processed/<area>/05/<task>_prob_ens_<area>_05.tif (S7a)
    infer     results/tables/<area>/xfer_infer_record_<task>_<area>.json (S7a)
    roles     results/tables/<area>/xfer_blocks_roles_<area>.gpkg (S1)
    truth     assumed.truth layer pit_inside (S6)
    reference config reference.tables.<task> (3.0 xfer_ref_block_tables_9t.json, all 144 blocks)

Outputs (run folder expansions/3_geography/3_1_warren_forest_mckean/results/<run_id>/)
    xfer_score_k40_<area>.json          primary, secondaries, decision, policy, lineage, provisional
    xfer_score_blocks_<area>.csv        per test block hits, n_truth, kept, provisional
    xfer_found_missed_<area>.gpkg       layers truth_scored, candidates_kept

Run
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_score_k40_wfm.py --area warren
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_score_k40_wfm.py --area mckean --superblock-side 3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek
tl = xl.tl

CFG = HERE.parent / "config_3_1.json"
CTX_BUF_M = 40.0
DESCRIPTIVE = "descriptive"


def candidates_in_blocks(prob_path, blocks, thr=None, min_area=None, *, policy=None, task="pit"):
    """Blobs extracted once on a shared window over all blocks (xl.candidates_for_blocks), one block each.
    thr / min_area are legacy arguments and must equal the policy."""
    pol = policy or xl.policy(task)
    if thr is not None and not tl.same_number(thr, pol["cutoff"]):
        raise ValueError(f"cutoff {thr} differs from policy cutoff {pol['cutoff']}")
    if min_area is not None and not tl.same_number(min_area, pol["min_area_m2"]):
        raise ValueError(f"min area {min_area} differs from policy {pol['min_area_m2']}")
    return xl.candidates_for_blocks(prob_path, blocks, pol, halo_m=CTX_BUF_M)


def reference_counts(tables_path: Path, policy: dict, k: float, k_sens: float) -> tuple[pd.DataFrame, dict]:
    """Per-block hits at K and K30 from the 3.0 reference tables, after the compatibility checks."""
    blocks, rpol, meta = tl.read_ref_tables(tables_path)
    if rpol is None:
        raise AssertionError(f"{tables_path} has no policy stamp (old schema). Rebuild it with 3.0 _transfer_ref_tables_9t.py")
    ek.assert_same_policy(rpol, policy, keys=tl.POLICY_KEYS)
    if meta.get("footprint") != "all_blocks":
        raise AssertionError(f"reference footprint {meta.get('footprint')} is not all blocks (review G-02). "
                             "Targets are scored on every test block. Refusing")
    rule = meta.get("k_rule_reference", "global")
    ref = tl.ref_block_counts(blocks, k, rule)
    ref["hits_k30"] = tl.ref_block_counts(blocks, k_sens, rule).hits.to_numpy()
    return ref, meta


def score_transfer(cands, truth, test_blocks, ref: pd.DataFrame, *, margin, B, seed, k=40.0, k_sens=30.0,
                   superblock_side=None, ref_blocks_geo=None, policy=None):
    """All statistics for one arm. Pure function of its inputs (testable on synthetic data)."""
    pol = policy or xl.policy("pit")
    res = {}
    s40, per40, sc, st = xl.score_area(cands, truth, test_blocks, k_per_km2=k, policy=pol)
    s30, per30, _, _ = xl.score_area(cands, truth, test_blocks, k_per_km2=k_sens, policy=pol)
    ref_rows40 = list(zip(ref.hits, ref.n_truth))
    res["primary"] = {**s40, **xl.diff_vs_reference(list(zip(per40.hits, per40.n_truth)), ref_rows40,
                                                     margin=margin, B=B, seed=seed)}
    if "hits_k30" in ref:
        res["k30"] = {**s30, **xl.diff_vs_reference(list(zip(per30.hits, per30.n_truth)),
                                                     list(zip(ref.hits_k30, ref.n_truth)), margin=margin, B=B, seed=seed)}
    ref_density = float(ref.n_truth.sum() / ref.area_km2.sum())
    k_ds = xl.density_scaled_k(k, ref_density, s40["truth_density_per_km2"]) if s40["n_truth"] else np.nan
    if np.isfinite(k_ds) and k_ds > 0:
        sds, perds, _, _ = xl.score_area(cands, truth, test_blocks, k_per_km2=k_ds, policy=pol)
        res["density_scaled"] = {**sds, "c": k / ref_density,
                                 **xl.diff_vs_reference(list(zip(perds.hits, perds.n_truth)), ref_rows40,
                                                        margin=margin, B=B, seed=seed)}
    if superblock_side and {"ix", "iy"} <= set(test_blocks.columns):
        sbt = per40.merge(test_blocks[["block_id", "ix", "iy"]], on="block_id")
        sbt["sb"] = xl.superblock_ids(sbt, superblock_side)
        tgt = sbt.groupby("sb")[["hits", "n_truth"]].sum()
        if ref_blocks_geo is not None:
            sbr = ref.merge(ref_blocks_geo[["block_id", "ix", "iy"]], on="block_id")
            sbr["sb"] = xl.superblock_ids(sbr, superblock_side)
            rr = sbr.groupby("sb")[["hits", "n_truth"]].sum()
        else:
            rr = ref[["hits", "n_truth"]]
        res["superblock"] = {"side_blocks": superblock_side,
                             **xl.diff_vs_reference(list(zip(tgt.hits, tgt.n_truth)), list(zip(rr.hits, rr.n_truth)),
                                                    margin=margin, B=B, seed=seed)}
    if len(sc):
        res["calibration"] = ek.calibration(sc.matched.notna().astype(int).to_numpy(), sc.score.to_numpy())
    res["reference"] = {"recall": xl.pooled_recall(ref_rows40), "n_blocks": len(ref), "density_per_km2": ref_density}
    res["policy"] = pol
    return res, per40, sc, st


def low_density_stratum(roles, cands_fn, truth, policy) -> dict:
    """Review G-07. Scored when it has test blocks, else an explicit empty record with the reason."""
    ld = roles.low_density.fillna(False).astype(bool)
    usable = roles.get("complete", True) & roles.get("void_ok", True)
    low = roles[(roles.role == "test") & ld & usable]
    if len(low):
        return {"status": "scored", **xl.score_area(cands_fn(low), truth, low, policy=policy)[0]}
    counts = roles[ld].role.value_counts().to_dict()
    if not ld.any():
        why = "no block falls under the density rule"
    elif not (roles.role[ld] == "test").any():
        why = f"low-density blocks hold no test role (roles {counts}). Rebuild S1 roles with this version"
    else:
        why = "low-density test blocks are incomplete or over the void cap"
    return {"status": "empty", "reason": why, "n_low_density_blocks": int(ld.sum()), "roles": counts}


def apply_lineage(res: dict, ok: bool, why: list[str]) -> None:
    """Without a confirmatory lineage every decision becomes descriptive (the would-be decision is kept)."""
    res["confirmatory"], res["not_confirmatory"] = ok, why
    res["provisional"] = not ok
    if ok:
        return
    for key in ("primary", "k30", "density_scaled", "superblock"):
        if key in res and "decision" in res[key]:
            res[key]["decision_if_confirmatory"] = res[key]["decision"]
            res[key]["decision"] = DESCRIPTIVE


def read_infer_record(ctx, task, area, prob: Path) -> dict:
    p = xl.need(ctx["tables"] / f"xfer_infer_record_{task}_{area}.json", "S7a inference record",
                "run _xfer_frozen_infer_wfm.py. It writes the record next to the score tables")
    rec = json.loads(p.read_text(encoding="utf-8"))
    if rec.get("prob_sha256") and rec["prob_sha256"] != ek.sha256(prob):
        raise AssertionError(f"inference record {p.name} names a different probability raster (sha256 differs)")
    if "checkpoint" not in rec:
        raise AssertionError(f"inference record {p.name} has no checkpoint lineage. Re-run S7a with this version")
    rec["checkpoint"]["provisional"] = bool(rec["checkpoint"].get("provisional") or rec.get("provisional_cv5"))
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--task", default="pit", choices=["pit", "pad"])
    ap.add_argument("--prob", default=None)
    ap.add_argument("--truth", default=None, help="override assumed.truth")
    ap.add_argument("--layer", default=None, help="truth layer (default pit_inside or pad)")
    ap.add_argument("--superblock-side", type=int, default=None, help="super-block side in blocks (sensitivity)")
    ap.add_argument("--not-preregistered", action="store_true")
    ap.add_argument("--allow-rescore", action="store_true")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    import geopandas as gpd
    from _common import read_layer
    pol = xl.policy(a.task)
    prob = Path(a.prob) if a.prob else ctx["heavy"] / f"{a.task}_prob_ens_{a.area}_05.tif"
    xl.need(prob, "S7a probability raster", "run _xfer_frozen_infer_wfm.py")
    infer = read_infer_record(ctx, a.task, a.area, prob)
    prereg_hash, pr = None, None
    try:
        pp = xl.assumed_path(cfg, "prereg", a.area)
        prereg_hash, pr = ek.sha256(pp), tl.read_prereg(pp)
    except xl.MissingInput:
        if not a.not_preregistered:
            raise
    if pr is not None:                        # declared cutoff, IoU, dedupe, K, checkpoint must equal this run
        tl.check_prereg_against(pr, pol, "truth_matched", infer["checkpoint"], "3.1 scoring run")
    ledger = ctx["tables"] / f"xfer_score_ledger_{a.area}.csv"
    if prereg_hash and ledger.exists() and not a.allow_rescore:
        if prereg_hash in set(pd.read_csv(ledger).prereg_sha256):
            raise RuntimeError("this preregistration was already scored once; --allow-rescore to override")
    roles = gpd.read_file(xl.need(ctx["tables"] / f"xfer_blocks_roles_{a.area}.gpkg", "S1 roles"), layer="blocks")
    tp = Path(a.truth) if a.truth else xl.assumed_path(cfg, "truth", a.area)
    layer = a.layer or ("pad" if a.task == "pad" else "pit_inside")
    truth = read_layer(tp, layer).to_crs(ek.DST_CRS)
    idc = "pad_id" if a.task == "pad" else "pit_inside_id"
    truth = truth[[idc, "geometry"]].dissolve(by=idc).reset_index().rename(columns={idc: "truth_id"})
    ref_p = xl.need(xl.resolve_path(cfg["reference"]["tables"][a.task]), "3.0 reference tables")
    ref, ref_meta = reference_counts(ref_p, pol, cfg["k_per_km2"], cfg["k_sensitivity_per_km2"])
    ok, why = tl.confirmatory_ok(ref_meta.get("checkpoint"), infer["checkpoint"])
    ref_geo = gpd.read_file(xl.resolve_path(cfg["reference"]["blocks_9t"]), layer="blocks")
    margin = (cfg.get("margin_delta") or {}).get(a.area)
    test = roles[(roles.role == "test") & roles.eligible.astype(bool)]
    run = ek.new_run(cfg["exp_id"], f"xfer_score_{a.area}", {"area": a.area, "prereg": prereg_hash, "policy": pol,
                                                             "margin": margin, "superblock": a.superblock_side},
                     why="S7b one scoring run per preregistration.")
    cands = candidates_in_blocks(prob, test, policy=pol)
    res, per, sc, st = score_transfer(cands, truth, test, ref, margin=margin, B=cfg["bootstrap_B"],
                                      seed=cfg["master_seed"], superblock_side=a.superblock_side, ref_blocks_geo=ref_geo,
                                      policy=pol)
    res["low_density_stratum"] = low_density_stratum(roles, lambda b: candidates_in_blocks(prob, b, policy=pol), truth, pol)
    apply_lineage(res, ok, why)
    stamp = [] if prereg_hash else ["NOT A PREREGISTERED SCORE"]
    if res["provisional"]:
        stamp.append("PROVISIONAL")
    res.update({"area": a.area, "task": a.task, "evidence_level": "(a) drawn features", "prereg_sha256": prereg_hash,
                "stamp": " ".join(stamp) or None, "policy_hash": pol["policy_hash"],
                "scorer": {"module": "3.0 _transfer_score_lib", "module_sha256": tl.module_sha256(), "dedupe": "truth_matched",
                           "block_point": "centroid", "extraction": "shared window, no seam clipping"},
                "checkpoint_target": infer["checkpoint"], "checkpoint_reference": ref_meta.get("checkpoint"),
                "provisional_cv5": bool(infer.get("provisional_cv5")),
                "prob": str(prob), "prob_sha256": ek.sha256(prob)[:16], "truth": str(tp), "proposal_thr": pol["cutoff"],
                "reference_tables": str(ref_p), "reference_footprint": ref_meta.get("footprint")})
    js = run / f"xfer_score_k40_{a.area}.json"
    js.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    bc = run / f"xfer_score_blocks_{a.area}.csv"
    per.assign(provisional=res["provisional"], policy_hash=pol["policy_hash"]).to_csv(bc, index=False)
    gp = run / f"xfer_found_missed_{a.area}.gpkg"
    st.assign(provisional=res["provisional"]).to_file(gp, layer="truth_scored", driver="GPKG")
    sc[sc.kept].assign(matched=sc.matched.astype(str), provisional=res["provisional"]).to_file(
        gp, layer="candidates_kept", driver="GPKG")
    row = pd.DataFrame([{"run": run.name, "prereg_sha256": prereg_hash or "none", "provisional": res["provisional"]}])
    (pd.concat([pd.read_csv(ledger), row]) if ledger.exists() else row).to_csv(ledger, index=False)
    ek.write_provenance(run, inputs=[prob, tp, ref_p], outputs=[js, bc, gp],
                        params={"policy": pol, "margin": margin, "provisional": res["provisional"]},
                        seeds={"B": cfg["master_seed"]}, hash_limit_mb=500)
    print(json.dumps(res["primary"], indent=2, default=float))
    print(f"wrote {js}\n      {bc}\n      {gp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
