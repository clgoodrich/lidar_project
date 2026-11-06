"""5.6 S0. Build the full detector output for pits and pads on 9t (input contract, protocol section 4 rule 1).

Purpose
    The handoff to 5.4, 6.1 and 6.4. Membership and det_id depend on predictions only (review F15, 5.6-01).

    Pits. Every size-plausible held-out blob at the policy cutoff (0.35, ek.policy_for("pit")), read from both
    layers (matched and undecided) of the re-cut file built by _records_policy_recut_9t.py. The layer split is a truth label and is kept only as the evaluation
    columns source and novel. Dedupe (config dedupe.rule) "geometric" merges blobs whose polygons lie within
    dedupe.gap_m of each other and keeps the highest-scoring one. It reads geometry and score only.
    "keep_all" is the sensitivity. The truth flag dup_on_pit stays as an evaluation column and is never used.
    Pads. Every pad polygon at the policy cutoff 0.525 (layer model_geometry of the re-cut file). No dedupe. They are matched to annotated pads
    (plat) greedy by score with IoU >= 0.3 for the evaluation columns only, after the ids are fixed.

    Contract (both files)
        det_id  int, unique across both files. Pits 1..n_pit, pads 1000001..1000000+n_pad. A seeded random
                permutation of a prediction-only canonical order, so it encodes neither match status nor score.
        kind    'pit' or 'pad'
        score   mean probability inside the blob
        cx, cy  centroid (EPSG:6346 m). Read them as df["cx"], never df.cx (GeoDataFrame.cx is an indexer).
        block_id, area_m2, evidence_level = a, and n_merged on pits
        evaluation only (truth-derived, never used to build the set): source, novel, near_pit_m, dup_on_pit,
                matched_plat, iou
    The seeds and the id policy go into the provenance JSON and the tracked id policy table.

Inputs (config_5_6.json)
    pit_candidates  @exp:5.6/data/interim/records_pit_recut_policy_9t.gpkg (matched, undecided)
    pad_products    @exp:5.6/data/interim/records_pad_recut_policy_9t.gpkg (model_geometry)
    Both carry thr_used. S0 refuses a product whose thr_used differs from cutoff_used, and a cutoff_used that
    differs from ek.policy_for.
    annotations     @truth/annotations_proj.gpkg (plat), evaluation columns only
    pit_blocks, pad_blocks  @nine_t/pit_blocks_9t.gpkg, @nine_t/pad_blocks_9t.gpkg
Outputs
    expansions/5_tasks/5_6_record_association/data/processed/detector_output_pit_full_9t.gpkg
    expansions/5_tasks/5_6_record_association/data/processed/detector_output_pad_full_9t.gpkg
    expansions/5_tasks/5_6_record_association/data/processed/_PROVENANCE_detector_output.json
    expansions/5_tasks/5_6_record_association/results/tables/records_detector_row_counts_9t.csv
    expansions/5_tasks/5_6_record_association/results/tables/records_detector_id_policy_9t.json
Run
    python expansions/5_tasks/5_6_record_association/src/_records_full_detector_output_9t.py [--dedupe keep_all]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _records_assoc_core as core  # noqa: E402

ek = th.ek


def match_pads(pred, truth, iou_min: float = 0.3):
    """Greedy one-to-one by descending score, accept IoU >= iou_min. Returns (truth_id or -1, iou) per pred row."""
    sidx = truth.sindex
    tg = truth.geometry.values
    order = np.argsort(-pred["score"].to_numpy(), kind="stable")
    used = set()
    tid = np.full(len(pred), -1, int)
    best = np.zeros(len(pred))
    for i in order:
        g = pred.geometry.iloc[i]
        cands = []
        for j in sidx.query(g, predicate="intersects"):
            if j in used:
                continue
            inter = g.intersection(tg[j]).area
            u = g.area + tg[j].area - inter
            iou = inter / u if u > 0 else 0.0
            if iou >= iou_min:
                cands.append((iou, int(j)))
        if cands:
            iou, j = max(cands)
            used.add(j)
            tid[i], best[i] = j, iou
    return tid, best


def combine_pit_layers(parts):
    """Concatenate the candidate layers into one prediction set. Truth-derived columns become evaluation columns."""
    import geopandas as gpd
    full = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=th.CRS)
    if "source" not in full:
        full["source"] = "unknown"
    for c in ("near_pit_m", "dup_on_pit"):
        if c not in full:
            full[c] = np.nan
    c = full.geometry.centroid
    full["cx"], full["cy"] = c.x.round(2), c.y.round(2)
    full["area_m2"] = full.geometry.area.round(1)
    return full


def finish(full, kind: str, seed: int, blocks):
    """Stamp the contract columns. det_id (seeded permutation), kind, block_id, evidence_level."""
    full = full.reset_index(drop=True)
    full["det_id"] = core.assign_det_ids(full, kind, seed)
    full["kind"] = kind
    full["block_id"] = th.block_id_of(np.c_[full["cx"].to_numpy(), full["cy"].to_numpy()], blocks)
    full["evidence_level"] = "a"
    ek.assert_unique(full, "det_id")
    return full.sort_values("det_id").reset_index(drop=True)


def check_cutoff(df, cfg, kind: str, label: str) -> None:
    """The product must be cut at the config cutoff, and the config cutoff must be the policy cutoff."""
    want = float(cfg["cutoff_used"][kind])
    pol = float(ek.policy_for(kind)["cutoff"])
    if abs(want - pol) > 1e-9:
        raise SystemExit(f"CUTOFF MISMATCH [{label}]: cutoff_used {want} is not the policy cutoff {pol}")
    if "thr_used" not in df.columns:
        raise SystemExit(f"CUTOFF UNKNOWN [{label}]: no thr_used column. Rebuild with _records_policy_recut_9t.py")
    got = sorted(set(np.round(df["thr_used"].astype(float), 6)))
    if got != [round(want, 6)]:
        raise SystemExit(f"CUTOFF MISMATCH [{label}]: product cut at {got}, config wants {want}")


def read_pit_layers(cfg):
    p = th.inp(cfg, "pit_candidates")
    layers = []
    for layer in ("matched", "undecided"):
        g = th.read_vector(p, layer=layer)
        check_cutoff(g, cfg, "pit", f"pit_candidates/{layer}")
        g["source"] = layer
        layers.append(g)
    return layers


def build_pit(cfg, rule: str, layers=None):
    """layers: optional list of GeoDataFrames (tests). Default reads matched + undecided from pit_candidates."""
    full = combine_pit_layers(read_pit_layers(cfg) if layers is None else layers)
    full = full.drop(columns=[c for c in ("cand_id", "status") if c in full])   # cand_id is a per-layer score rank
    raw_n = len(full)
    if cfg["pit"].get("expected_predictions") is not None:
        ek.assert_rows(full, cfg["pit"]["expected_predictions"], "pit predictions (matched + undecided)")
    full = core.dedupe(full, rule, gap_m=cfg["dedupe"]["gap_m"])
    full["novel"] = (full["source"] != "matched").astype(int)
    full["dedupe_rule"] = rule
    blocks = th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")
    full = finish(full, "pit", cfg["det_id"]["seed_pit"], blocks)
    flag = full["dup_on_pit"].fillna(0).astype(int) == 1
    counts = [dict(modality="pit", layer="predictions", rows_in=raw_n),
              dict(modality="pit", layer=f"after_dedupe_{rule}", rows_in=len(full)),
              dict(modality="pit", layer="dropped_by_dedupe", rows_in=raw_n - len(full)),
              dict(modality="pit", layer="eval_matched_after_dedupe", rows_in=int((full.source == "matched").sum())),
              dict(modality="pit", layer="eval_novel_after_dedupe", rows_in=int(full.novel.sum())),
              dict(modality="pit", layer="eval_unmatched_with_truth_dup_flag",
                   rows_in=int(((full.source != "matched") & flag).sum()))]
    return full, counts


def build_pad(cfg):
    ent = cfg["inputs"]["pad_products"]
    layer = ent.get("layer", "model_geometry") if isinstance(ent, dict) else "model_geometry"
    pred = th.read_vector(th.inp(cfg, "pad_products"), layer=layer)
    th.require_columns(pred, ["score"], "pad model_geometry")
    check_cutoff(pred, cfg, "pad", "pad_products/model_geometry")
    pred = pred[~pred.geometry.is_empty].reset_index(drop=True)
    c = pred.geometry.centroid
    pred["cx"], pred["cy"] = c.x.round(2), c.y.round(2)
    pred["area_m2"] = pred.geometry.area.round(1)
    blocks = th.read_vector(th.inp(cfg, "pad_blocks"), layer="blocks")
    pred = finish(pred, "pad", cfg["det_id"]["seed_pad"], blocks)
    plat = th.read_vector(th.inp(cfg, "annotations"), layer="plat")      # evaluation columns only
    plat["geometry"] = plat.geometry.buffer(0)
    plat = plat[~plat.geometry.is_empty].reset_index(drop=True)
    tid, iou = match_pads(pred, plat, cfg["pad"]["match_iou"])
    pred["matched_plat"] = [int(plat.pad_id.iloc[j]) if j >= 0 and "pad_id" in plat else int(j) for j in tid]
    pred["iou"] = iou.round(3)
    pred["source"] = np.where(tid >= 0, "matched", "unmatched")
    pred["novel"] = (tid < 0).astype(int)
    counts = [dict(modality="pad", layer="model_geometry", rows_in=len(pred)),
              dict(modality="pad", layer="eval_matched_iou>=%.2f" % cfg["pad"]["match_iou"], rows_in=int((tid >= 0).sum())),
              dict(modality="pad", layer="eval_unmatched", rows_in=int((tid < 0).sum())),
              dict(modality="pad", layer="eval_plat_annotations", rows_in=len(plat))]
    return pred, counts


def id_policy(cfg, rule, pit, pad, files) -> dict:
    return dict(det_id_policy=core.DET_ID_POLICY, det_id_base=core.DET_ID_BASE,
                seed_pit=cfg["det_id"]["seed_pit"], seed_pad=cfg["det_id"]["seed_pad"],
                dedupe=dict(rule=rule, gap_m=cfg["dedupe"]["gap_m"],
                            reads="predicted geometry and score only. Truth columns are evaluation only."),
                cutoff_used=cfg["cutoff_used"], proposal_policy_pit=ek.policy_for("pit"),
                proposal_policy_pad=ek.policy_for("pad"),
                cutoff_note=("Products re-cut at the policy cutoffs by _records_policy_recut_9t.py. "
                             "User accepted on 2026-11-06."),
                rows=dict(pit=int(len(pit)), pad=int(len(pad))),
                det_id_range=dict(pit=[int(pit.det_id.min()), int(pit.det_id.max())],
                                  pad=[int(pad.det_id.min()), int(pad.det_id.max())]),
                files={k: dict(path=th.rel(v), sha256=ek.sha256(v)) for k, v in files.items()})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--dedupe", choices=("geometric", "keep_all"))
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    rule = a.dedupe or cfg["dedupe"]["rule"]
    pit, c1 = build_pit(cfg, rule)
    pad, c2 = build_pad(cfg)
    if set(pit.det_id) & set(pad.det_id):
        raise AssertionError("det_id collides across pit and pad files")
    op, od = th.outp(cfg, "full_pit"), th.outp(cfg, "full_pad")
    if rule != cfg["dedupe"]["rule"]:
        op = op.with_name(op.stem + f"_{rule}" + op.suffix)
    for path, g in ((op, pit), (od, pad)):
        if path.exists():
            path.unlink()
        g.to_file(path, layer=path.stem, driver="GPKG")
    tab = pd.DataFrame(c1 + c2)
    rc = th.outp(cfg, "row_counts")
    if rule == cfg["dedupe"]["rule"]:
        tab.to_csv(rc, index=False)
    policy = id_policy(cfg, rule, pit, pad, {"pit": op, "pad": od})
    pj = th.outp(cfg, "id_policy")
    if rule != cfg["dedupe"]["rule"]:
        pj = pj.with_name(pj.stem + f"_{rule}" + pj.suffix)
    th.write_json(pj, policy)
    ek.write_provenance(op.parent, inputs=[th.inp(cfg, k) for k in ("pit_candidates", "pad_products", "annotations",
                                                                    "pit_blocks", "pad_blocks")],
                        outputs=[op, od, rc, pj], params=policy,
                        seeds={"det_id_pit": cfg["det_id"]["seed_pit"], "det_id_pad": cfg["det_id"]["seed_pad"]},
                        name="detector_output" if rule == cfg["dedupe"]["rule"] else f"detector_output_{rule}")
    print(tab.to_string(index=False))
    for p in (op, od, rc, pj):
        print("wrote", th.rel(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
