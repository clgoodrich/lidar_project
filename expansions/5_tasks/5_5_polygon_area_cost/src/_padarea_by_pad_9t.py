"""5.5 S1. Per-pad area of model polygons against drawn pads, and a decomposition of the tile-level flagged area.

Purpose
    The review's "about 2 times" figure may be a tile-level flagged-area ratio, not a per-pad bias. This script
    reproduces the tile ratio from saved polygons and splits the flagged area into
        inside drawn pads           area the model put on drawn pads
        matched_overclaim           area of one-to-one matched polygons outside their pad
        merged_outside              area of polygons that cover two or more pads, outside those pads
        unmatched_touching          area of unmatched polygons that touch a drawn pad, outside pads
        false_positive_blobs        area of unmatched polygons that touch no drawn pad
    and reports the per-pad log ratio r = ln(A_hat / A_drawn) for matched pads. Pads are matched one to one by the
    config match_rule (overlap_any, any positive overlap, so the area error is never truncated). The IoU >= 0.3 gate
    is the sensitivity rule, reported in the JSON. The tile ratio does not depend on matching.
    Each pad also gets road_length_m, the annotated road length within road_window_m of its edge. Reference here is the annotators'
    drawing (level a). It is not a survey, so this is exploratory. Pits are removed from both sides when
    subtract_pits is set. Pads are scored by held-out polygons only (one CV fold model per block).

Inputs (config_5_5.json)
    pad_products  @results_9t/pad/thresholds/pad_heldout_found_vs_missed_thr0p50_9t.gpkg (model_geometry)
    annotations   @truth/annotations_proj.gpkg (plat, pit_inside)
    pad_blocks    @nine_t/pad_blocks_9t.gpkg
    pad_cover     @results_9t/pad/pad_cover_split_9t.gpkg (cover_class per pad_id, optional stratifier)
Outputs
    expansions/5_tasks/5_5_polygon_area_cost/results/tables/pad_area_by_pad_9t.csv
    expansions/5_tasks/5_5_polygon_area_cost/results/tables/pad_area_tile_decomposition_9t.json
Run
    python expansions/5_tasks/5_5_polygon_area_cost/src/_padarea_by_pad_9t.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _padarea_geometry_tools as gt  # noqa: E402

th, ek = gt.th, gt.ek


def decompose(pred, plat, T) -> dict:
    pu = plat.geometry.union_all()
    flagged = pred.geometry.union_all().area
    drawn = pu.area
    inside = pred.geometry.union_all().intersection(pu).area
    matched_rows = set(T.loc[T.matched == 1, "pred_row"].astype(int))
    merged_rows = set(T.loc[(T.matched == 1) & (T.merged == 1), "pred_row"].astype(int))
    parts = dict(matched_overclaim=0.0, merged_outside=0.0, unmatched_touching=0.0, false_positive_blobs=0.0)
    for i, g in enumerate(pred.geometry):
        out = g.difference(pu).area
        if i in merged_rows:
            parts["merged_outside"] += out
        elif i in matched_rows:
            parts["matched_overclaim"] += out
        elif g.intersects(pu):
            parts["unmatched_touching"] += out
        else:
            parts["false_positive_blobs"] += out
    return dict(flagged_ha=flagged / 1e4, drawn_ha=drawn / 1e4, tile_ratio=flagged / drawn if drawn else np.nan,
                inside_drawn_ha=inside / 1e4, **{k + "_ha": v / 1e4 for k, v in parts.items()},
                note="Tile-level flagged area over drawn area. Not a per-pad ratio. Overlapping polygons are unioned.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    pred = gt.load_pred(cfg)
    plat, pits = gt.load_drawn(cfg)
    if cfg.get("subtract_pits"):
        pred, plat = gt.remove_pits(pred, pits), gt.remove_pits(plat, pits)
    pol = ek.policy_for("pad")
    iou = pol["iou"]
    T = gt.per_pad(pred, plat, "pad_id", iou, cfg["merge_overlap_frac"], cfg["match_rule"])
    ek.assert_rows(T, len(plat), "one row per drawn pad")
    Ts = gt.per_pad(pred, plat, "pad_id", iou, cfg["merge_overlap_frac"], cfg["match_rule_sensitivity"])
    T["road_length_m"] = gt.road_length(plat, gt.load_roads(cfg), cfg["road_window_m"])
    c = plat.geometry.centroid
    blocks = th.read_vector(th.inp(cfg, "pad_blocks"), layer="blocks")
    T["block_id"] = th.block_id_of(np.c_[c.x, c.y], blocks)
    if th.has(cfg, "pad_cover"):
        cov = th.read_vector(th.inp(cfg, "pad_cover"))
        T = T.merge(pd.DataFrame(cov[["pad_id", "cover_class"]]).drop_duplicates("pad_id"), on="pad_id", how="left")
    T["size_tercile"] = pd.qcut(T.A_ref, 3, labels=["small", "medium", "large"]).astype(str)
    T["reference"] = "drawn"
    T = th.tag(T, "a", "exploratory_drawn_reference")
    out = th.outp(cfg, "by_pad")
    T.to_csv(out, index=False)
    D = decompose(pred, plat, T)
    m = T[T.matched == 1]
    ms = Ts[Ts.matched == 1]
    small = set(T.loc[T.size_tercile == "small", "ref_row"])
    D.update(match_rule=cfg["match_rule"], policy=pol,
             sensitivity=dict(match_rule=cfg["match_rule_sensitivity"], iou_min=iou, n_matched=len(ms),
                              n_small_matched=int(ms.ref_row.isin(small).sum()),
                              median_log_ratio_matched=float(ms.log_ratio.median()),
                              max_abs_log_ratio=float(ms.log_ratio.abs().max())),
             n_small=len(small), n_small_matched=int(m.ref_row.isin(small).sum()),
             max_abs_log_ratio_matched=float(m.log_ratio.abs().max()),
             cutoff_note=f"pad polygons are the 0.50 product; policy cutoff is {pol['cutoff']}",n_drawn=len(plat), n_pred=len(pred), n_matched=len(m), n_merged=int(m.merged.sum()),
             n_split=int(T.split.sum()), median_log_ratio_matched=float(m.log_ratio.median()),
             median_area_ratio_matched=float(np.exp(m.log_ratio.median())), subtract_pits=cfg.get("subtract_pits"))
    js = th.write_json(th.outp(cfg, "tile_decomp"), D)
    for k, v in D.items():
        print(f"{k:28s} {v}")
    print("wrote", out, "\nwrote", js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
