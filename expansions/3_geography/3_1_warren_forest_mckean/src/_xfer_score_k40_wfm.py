"""3.1 S7b. Score a transfer arm once. Recall at K = 40 per km2, target minus 9t, with sensitivities.

Purpose
    The primary statistic of fw_3_1 and fw_3_2. Candidates come from the frozen ensemble
    probability raster, read only inside eligible test blocks (plus a 40 m context buffer),
    cut at the frozen proposal cutoff, scored by mean probability, credited to a block by
    representative point, ranked, and cut at round(40 x test km2). Matching to the blind
    truth floors is greedy one-to-one by IoU 0.3. The difference against the 9t reference
    table uses independent block bootstraps (B = 2000) and ek.decide against minus Δ.
    Fewer than 15 test blocks adds a permutation p-value and the unreliable-bootstrap note.
    Secondary. Density-scaled K (c fixed from 9t), K = 30, super-block resampling, the
    low-density stratum, calibration of candidate scores (Brier, log loss, ECE), and
    target feature density.

Guards
    Refuses to run without the committed preregistration (assumed.prereg) unless
    --not-preregistered, which stamps every output NOT A PREREGISTERED SCORE.
    Refuses a second scoring run for the same prereg hash unless --allow-rescore.

Inputs
    prob      data/processed/<area>/05/pit_prob_ens_<area>_05.tif (S7a)
    roles     results/tables/<area>/xfer_blocks_roles_<area>.gpkg (S1)
    truth     assumed.truth layer pit_inside (S6)
    reference config reference.blocks_csv and summary_json (provisional 3.3 S1 rebuild)

Outputs (run folder expansions/3_geography/3_1_warren_forest_mckean/results/<run_id>/)
    xfer_score_k40_<area>.json          primary, secondaries, decision, hashes
    xfer_score_blocks_<area>.csv        per test block hits, n_truth, kept
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

CFG = HERE.parent / "config_3_1.json"
CTX_BUF_M = 40.0


def candidates_in_blocks(prob_path, blocks, thr, min_area):
    """Blobs read block by block (+40 m), kept when the representative point is in the block."""
    import geopandas as gpd
    import rasterio
    from rasterio.windows import from_bounds
    parts = []
    with rasterio.open(prob_path) as r:
        ek.assert_crs(r)
        for bid, g in zip(blocks.block_id, blocks.geometry):
            w = from_bounds(*g.buffer(CTX_BUF_M).bounds, transform=r.transform).round_offsets().round_lengths()
            p = r.read(1, window=w, boundless=True, fill_value=0).astype(np.float32)
            p[~np.isfinite(p) | (p < 0)] = 0
            c = xl.candidates_from_prob(p, r.window_transform(w), r.crs, thr=thr, min_area=min_area)
            if len(c):
                c = c[c.geometry.representative_point().within(g)]
                parts.append(c)
    if not parts:
        return gpd.GeoDataFrame({"score": [], "area_m2": []}, geometry=[], crs=ek.DST_CRS)
    out = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=ek.DST_CRS)
    out["cand_id"] = np.arange(len(out))
    return out


def score_transfer(cands, truth, test_blocks, ref: pd.DataFrame, *, margin, B, seed, k=40.0, k_sens=30.0,
                   superblock_side=None, ref_blocks_geo=None):
    """All statistics for one arm. Pure function of its inputs (testable on synthetic data)."""
    res = {}
    s40, per40, sc, st = xl.score_area(cands, truth, test_blocks, k_per_km2=k)
    s30, per30, _, _ = xl.score_area(cands, truth, test_blocks, k_per_km2=k_sens)
    ref_rows40 = list(zip(ref.hits, ref.n_truth))
    res["primary"] = {**s40, **xl.diff_vs_reference(list(zip(per40.hits, per40.n_truth)), ref_rows40,
                                                     margin=margin, B=B, seed=seed)}
    if "hits_k30" in ref:
        res["k30"] = {**s30, **xl.diff_vs_reference(list(zip(per30.hits, per30.n_truth)),
                                                     list(zip(ref.hits_k30, ref.n_truth)), margin=margin, B=B, seed=seed)}
    ref_density = float(ref.n_truth.sum() / ref.area_km2.sum())
    k_ds = xl.density_scaled_k(k, ref_density, s40["truth_density_per_km2"]) if s40["n_truth"] else np.nan
    if np.isfinite(k_ds) and k_ds > 0:
        sds, perds, _, _ = xl.score_area(cands, truth, test_blocks, k_per_km2=k_ds)
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
    return res, per40, sc, st


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--task", default="pit")
    ap.add_argument("--prob", default=None)
    ap.add_argument("--truth", default=None, help="override assumed.truth")
    ap.add_argument("--layer", default="pit_inside")
    ap.add_argument("--superblock-side", type=int, default=None, help="super-block side in blocks (sensitivity)")
    ap.add_argument("--not-preregistered", action="store_true")
    ap.add_argument("--allow-rescore", action="store_true")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    import geopandas as gpd
    from _common import read_layer
    prereg_hash = None
    try:
        pp = xl.assumed_path(cfg, "prereg", a.area)
        prereg_hash = ek.sha256(pp)
    except xl.MissingInput:
        if not a.not_preregistered:
            raise
    ledger = ctx["tables"] / f"xfer_score_ledger_{a.area}.csv"
    if prereg_hash and ledger.exists() and not a.allow_rescore:
        if prereg_hash in set(pd.read_csv(ledger).prereg_sha256):
            raise RuntimeError("this preregistration was already scored once; --allow-rescore to override")
    prob = Path(a.prob) if a.prob else ctx["heavy"] / f"{a.task}_prob_ens_{a.area}_05.tif"
    xl.need(prob, "S7a probability raster", "run _xfer_frozen_infer_wfm.py")
    roles = gpd.read_file(xl.need(ctx["tables"] / f"xfer_blocks_roles_{a.area}.gpkg", "S1 roles"), layer="blocks")
    tp = Path(a.truth) if a.truth else xl.assumed_path(cfg, "truth", a.area)
    truth = read_layer(tp, a.layer).to_crs(ek.DST_CRS)
    idc = "pit_inside_id" if a.layer != "pad" else "pad_id"
    truth = truth[[idc, "geometry"]].dissolve(by=idc).reset_index().rename(columns={idc: "truth_id"})
    ref = pd.read_csv(xl.need(xl.resolve_path(cfg["reference"]["blocks_csv"]), "9t reference blocks"))
    rs = json.loads(xl.need(xl.resolve_path(cfg["reference"]["summary_json"]), "9t reference summary").read_text())
    thr = rs["frozen_target_proposal_thr"]
    ref_geo = gpd.read_file(xl.resolve_path(cfg["reference"]["blocks_9t"]), layer="blocks")
    margin = (cfg.get("margin_delta") or {}).get(a.area)
    test = roles[(roles.role == "test") & roles.eligible.astype(bool)]
    low = roles[(roles.role == "test") & roles.low_density.fillna(False).astype(bool)]
    run = ek.new_run(cfg["exp_id"], f"xfer_score_{a.area}", {"area": a.area, "prereg": prereg_hash, "thr": thr,
                                                             "margin": margin, "superblock": a.superblock_side},
                     why="S7b one scoring run per preregistration.")
    cands = candidates_in_blocks(prob, test, thr, cfg["min_blob_m2"])
    res, per, sc, st = score_transfer(cands, truth, test, ref, margin=margin, B=cfg["bootstrap_B"],
                                      seed=cfg["master_seed"], superblock_side=a.superblock_side, ref_blocks_geo=ref_geo)
    if len(low):
        cl = candidates_in_blocks(prob, low, thr, cfg["min_blob_m2"])
        res["low_density_stratum"] = xl.score_area(cl, truth, low)[0]
    res.update({"area": a.area, "evidence_level": "(a) drawn features", "prereg_sha256": prereg_hash,
                "stamp": None if prereg_hash else "NOT A PREREGISTERED SCORE",
                "prob": str(prob), "prob_sha256": ek.sha256(prob)[:16], "truth": str(tp), "proposal_thr": thr,
                "reference_csv": str(xl.resolve_path(cfg["reference"]["blocks_csv"]))})
    js = run / f"xfer_score_k40_{a.area}.json"
    js.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    bc = run / f"xfer_score_blocks_{a.area}.csv"
    per.to_csv(bc, index=False)
    gp = run / f"xfer_found_missed_{a.area}.gpkg"
    st.to_file(gp, layer="truth_scored", driver="GPKG")
    sc[sc.kept].assign(matched=sc.matched.astype(str)).to_file(gp, layer="candidates_kept", driver="GPKG")
    row = pd.DataFrame([{"run": run.name, "prereg_sha256": prereg_hash or "none"}])
    (pd.concat([pd.read_csv(ledger), row]) if ledger.exists() else row).to_csv(ledger, index=False)
    ek.write_provenance(run, inputs=[prob, tp, xl.resolve_path(cfg["reference"]["blocks_csv"])],
                        outputs=[js, bc, gp], params={"thr": thr, "margin": margin}, seeds={"B": cfg["master_seed"]},
                        hash_limit_mb=500)
    print(json.dumps(res["primary"], indent=2, default=float))
    print(f"wrote {js}\n      {bc}\n      {gp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
