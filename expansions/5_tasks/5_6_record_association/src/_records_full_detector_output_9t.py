"""5.6 S0. Build the full detector output for pits and pads on 9t (input contract, protocol section 4 rule 1).

Purpose
    The withdrawn run used only the 204 unmatched pit leftovers and the unmatched pad leftovers. This script
    rebuilds the full output at the frozen 0.50 cutoff, matched and unmatched, with one deployment-compatible
    dedupe rule, and writes a row-count table so every later join can assert its counts.

    Pits. matched (481) + undecided (207) layers of the held-out candidate file. Dedupe (config
    open_decisions.dedupe_rule) "deployment" drops an undecided blob whose centroid sits inside an already-drawn
    pit (dup_on_pit = 1). "keep_all" is the sensitivity arm.
    Pads. Every held-out pad polygon at 0.50 (layer model_geometry), matched to annotated pads (plat) greedy by
    score with IoU >= 0.3, one to one. Matched and unmatched are both kept.
    Each row gets block_id (by centroid), novel = not matched, evidence_level = a.

Inputs (config_5_6.json)
    pit_candidates  @results_9t/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg (matched, undecided)
    pad_products    @results_9t/pad/thresholds/pad_heldout_found_vs_missed_thr0p50_9t.gpkg (model_geometry)
    annotations     @truth/annotations_proj.gpkg (plat)
    pit_blocks, pad_blocks  @nine_t/pit_blocks_9t.gpkg, @nine_t/pad_blocks_9t.gpkg
Outputs
    expansions/5_tasks/5_6_record_association/data/processed/detector_output_pit_full_9t.gpkg
    expansions/5_tasks/5_6_record_association/data/processed/detector_output_pad_full_9t.gpkg
    expansions/5_tasks/5_6_record_association/results/tables/records_detector_row_counts_9t.csv
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


def build_pit(cfg, rule: str):
    import geopandas as gpd
    p = th.inp(cfg, "pit_candidates")
    parts = []
    for layer in ("matched", "undecided"):
        g = th.read_vector(p, layer=layer)
        g["source"] = layer
        parts.append(g)
    n_m, n_u = len(parts[0]), len(parts[1])
    exp = cfg["pit"]
    ek.assert_rows(parts[0], exp["expected_matched"], "pit matched rows")
    ek.assert_rows(parts[1], exp["expected_undecided"], "pit undecided rows")
    full = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=th.CRS)
    raw_n = len(full)
    full = core.dedupe(full, rule)
    blocks = th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")
    xy = np.c_[full["cx"].to_numpy(), full["cy"].to_numpy()]
    full["block_id"] = th.block_id_of(xy, blocks)
    full["novel"] = (full.source != "matched").astype(int)
    full = full.reset_index(drop=True)
    full["det_id"] = np.arange(len(full))
    full["dedupe_rule"] = rule
    full["evidence_level"] = "a"
    ek.assert_unique(full, "det_id")
    counts = [dict(modality="pit", layer="matched", rows_in=n_m),
              dict(modality="pit", layer="undecided", rows_in=n_u),
              dict(modality="pit", layer="before_dedupe", rows_in=raw_n),
              dict(modality="pit", layer=f"after_dedupe_{rule}", rows_in=len(full)),
              dict(modality="pit", layer="dropped_by_dedupe", rows_in=raw_n - len(full)),
              dict(modality="pit", layer="novel_after_dedupe", rows_in=int(full.novel.sum()))]
    return full, counts


def build_pad(cfg):
    ent = cfg["inputs"]["pad_products"]
    pred = th.read_vector(th.inp(cfg, "pad_products"), layer=ent.get("layer", "model_geometry") if isinstance(ent, dict) else "model_geometry")
    th.require_columns(pred, ["score"], "pad model_geometry")
    pred = pred[~pred.geometry.is_empty].reset_index(drop=True)
    plat = th.read_vector(th.inp(cfg, "annotations"), layer="plat")
    plat["geometry"] = plat.geometry.buffer(0)
    plat = plat[~plat.geometry.is_empty].reset_index(drop=True)
    tid, iou = match_pads(pred, plat, cfg["pad"]["match_iou"])
    pred["matched_plat"] = [int(plat.pad_id.iloc[j]) if j >= 0 and "pad_id" in plat else int(j) for j in tid]
    pred["iou"] = iou.round(3)
    pred["source"] = np.where(tid >= 0, "matched", "unmatched")
    c = pred.geometry.centroid
    pred["cx"], pred["cy"] = c.x.round(2), c.y.round(2)
    blocks = th.read_vector(th.inp(cfg, "pad_blocks"), layer="blocks")
    pred["block_id"] = th.block_id_of(np.c_[pred["cx"].to_numpy(), pred["cy"].to_numpy()], blocks)
    pred["novel"] = (tid < 0).astype(int)
    pred["det_id"] = np.arange(len(pred))
    pred["area_m2"] = pred.geometry.area.round(1)
    pred["evidence_level"] = "a"
    counts = [dict(modality="pad", layer="model_geometry", rows_in=len(pred)),
              dict(modality="pad", layer="matched_iou>=%.2f" % cfg["pad"]["match_iou"], rows_in=int((tid >= 0).sum())),
              dict(modality="pad", layer="unmatched", rows_in=int((tid < 0).sum())),
              dict(modality="pad", layer="plat_annotations", rows_in=len(plat))]
    return pred, counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--dedupe", choices=("deployment", "keep_all"))
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    rule = a.dedupe or cfg["open_decisions"]["dedupe_rule"]
    pit, c1 = build_pit(cfg, rule)
    pad, c2 = build_pad(cfg)
    op, od = th.outp(cfg, "full_pit"), th.outp(cfg, "full_pad")
    if rule != cfg["open_decisions"]["dedupe_rule"]:
        op = op.with_name(op.stem + f"_{rule}" + op.suffix)
    for path, g in ((op, pit), (od, pad)):
        if path.exists():
            path.unlink()
        g.to_file(path, layer=path.stem, driver="GPKG")
    tab = pd.DataFrame(c1 + c2)
    rc = th.outp(cfg, "row_counts")
    tab.to_csv(rc, index=False)
    print(tab.to_string(index=False))
    for p in (op, od, rc):
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
