"""3.0 reference block tables. Export the 9t out-of-fold candidates per block for the 3.4 to 3.8 builds.

Purpose
    Score a 9t out-of-fold probability raster with the frozen scorer (`_transfer_score_lib.score`, policy
    ek.policy_for(task)) and write every ranked candidate per eligible block in the interface format the
    later geography builds read.
        {block_id: {"cands": [{"blob_id", "score", "area_m2", "truth_id"}], "n_truth": int, "km2": float, "fold": int},
         "policy": ek.policy_for(task) dict with policy_hash,
         "meta": {footprint, k_rule_reference, dedupe, checkpoint, fill, recall_at_k}}
    Old consumers keep working. Every block id key is unchanged. Read with `_transfer_score_lib.read_ref_tables`,
    which skips "policy" and "meta". truth_id is null for an unmatched candidate. Second pieces of a matched
    feature are already dropped (scorer dedupe rule). Every eligible block is written, including blocks with no
    candidates.

    Footprint (review G-02). The historical 9t mosaics hold predictions only for feature-bearing blocks. The
    29 pit-free (15 pad-free) blocks were in no fold of the historical split, and the trainers sampled patches
    centred on features inside train blocks only, so no fold model ever trained on them. Every fold model is
    therefore out of sample there. This script fills those blocks from the full-tile fold rasters
    (`fold_rasters`) under `zero_feature_fill` (round_robin by default, fold_mean as the sensitivity), quantised
    to DN / 254 for the uint8 pit mosaic so the feature-bearing blocks stay bit-identical. The tables then cover
    all 144 blocks (footprint "all_blocks").
    Pit default. The saved uint8 mosaic (historical CV5, provisional) at policy cutoff 0.35.
    Pad default. The float32 isolated out-of-fold mosaic built by `_transfer_baseline_repeat_9t.py`, cutoff 0.525
    (provisional, trained at buffer 0 on the P1 dry-run split).

Inputs
    --prob (defaults above), blocks and truth from config_3_0.json reference_9t.<task>, fold rasters and splits

Outputs
    expansions/3_geography/3_0_transfer_protocol/results/tables/xfer_ref_block_tables_9t.json      (pit)
    expansions/3_geography/3_0_transfer_protocol/results/tables/xfer_ref_block_tables_pad_9t.json  (pad)
    expansions/3_geography/3_0_transfer_protocol/data/interim/<task>_prob_oof_filled_9t.tif         (gitignored)
    Run record under expansions/3_geography/3_0_transfer_protocol/results/<run_id>/

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_ref_tables_9t.py --task pit
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_ref_tables_9t.py --task pad
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_ref_tables_9t.py --task pit --fill fold_mean --out-dir <scratch>
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
import _transfer_score_lib as tl  # noqa: E402
from _transfer_baseline_repeat_9t import ref_path, truth_spec  # noqa: E402
ek = tl.ek
CFG = json.loads((HERE.parent / "config_3_0.json").read_text(encoding="utf-8"))
OUT_NAME = {"pit": "xfer_ref_block_tables_9t.json", "pad": "xfer_ref_block_tables_pad_9t.json"}
N_FOLDS = 5


def fold_of_blocks(task: str) -> dict[int, int]:
    """Held-out fold of each feature-bearing block, from the split that made the mosaic."""
    R = CFG["reference_9t"][task]
    if task == "pit":
        df = ek.read_split_csv(ref_path("pit", "historical_split"))
        h = df[df.role == "held_out"]
        return {int(b): int(f) for b, f in zip(h.block_id, h.fold)}
    s = ek.path_for(R["split"]["key"]) / R["split"]["rel"]
    doc = json.loads(s.read_text(encoding="utf-8"))["tasks"][task]["folds"]
    return {int(b): int(f) for f, r in doc.items() for b in r["held_out"]}


def fill_assignment(fill_ids: list[int], rule: str) -> dict[int, int | str]:
    """round_robin: sorted position mod N_FOLDS. fold_mean: every block gets 'mean'."""
    if rule == "round_robin":
        return {b: i % N_FOLDS for i, b in enumerate(sorted(fill_ids))}
    if rule == "fold_mean":
        return {b: "mean" for b in fill_ids}
    raise ValueError(f"unknown fill rule {rule}")


def fill_mosaic(base, tf, blocks, assign: dict, fold_pattern: str, quantise: bool):
    """base float32 (NaN where no prediction). Cells of the assigned blocks take the named fold raster
    (or the fold mean). Only NaN cells inside those blocks are written."""
    import rasterio
    from rasterio.features import rasterize
    out = base.copy()
    folds = sorted({f for f in assign.values() if f != "mean"}) or []
    need_mean = any(f == "mean" for f in assign.values())
    load = sorted(set(folds) | (set(range(N_FOLDS)) if need_mean else set()))
    acc = None
    for k in load:
        p = Path(fold_pattern.format(k=k))
        with rasterio.open(p) as r:
            tl.assert_same_grid({"crs": r.crs, "transform": r.transform, "shape": (r.height, r.width)},
                                {"crs": r.crs, "transform": tf, "shape": base.shape}, f"fold raster {p.name} and mosaic")
            a = r.read(1).astype(np.float32)
            if r.nodata is not None:
                a[a == r.nodata] = np.nan
        if quantise:
            a = np.where(np.isfinite(a), np.round(a * 254.0) / 254.0, np.nan).astype(np.float32)
        ids = [b for b, f in assign.items() if f == k]
        if ids:
            m = rasterize([(g, 1) for g in blocks[blocks.block_id.isin(ids)].geometry], out_shape=base.shape,
                          transform=tf, fill=0, dtype="uint8").astype(bool) & ~np.isfinite(out)
            out[m] = a[m]
        if need_mean:
            acc = a.astype(np.float64) if acc is None else acc + a
    if need_mean:
        mean = (acc / len(load)).astype(np.float32)
        if quantise:
            mean = np.round(mean * 254.0) / 254.0
        ids = [b for b, f in assign.items() if f == "mean"]
        m = rasterize([(g, 1) for g in blocks[blocks.block_id.isin(ids)].geometry], out_shape=base.shape,
                      transform=tf, fill=0, dtype="uint8").astype(bool) & ~np.isfinite(out)
        out[m] = mean[m]
    return out


def write_float(dst: Path, a, tf, crs) -> Path:
    import rasterio
    dst.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype="float32",
                       crs=crs, transform=tf, nodata=np.nan, compress="deflate", predictor=2, tiled=True,
                       BIGTIFF="YES", blockxsize=256, blockysize=256) as d:
        d.write(a.astype(np.float32), 1)
    return dst


def tables(res: dict, fold: dict | None = None) -> dict:
    c, b = res["candidates"], res["blocks"]
    out = {}
    for r in b.itertuples():
        sub = c[c.block_id == r.block_id].sort_values(["score", "area_m2", "cand_id"], ascending=[False, False, True])
        e = {"cands": [{"blob_id": int(x.cand_id), "score": float(x.score), "area_m2": float(x.area_m2),
                        "truth_id": None if x.matched is None or x.matched != x.matched else int(x.matched)}
                       for x in sub.itertuples()],
             "n_truth": int(r.n_truth), "km2": float(r.area_km2)}
        if fold is not None and int(r.block_id) in fold:
            e["fold"] = fold[int(r.block_id)]
        out[str(int(r.block_id))] = e
    return out


def pooled(t: dict, k: float, rule: str) -> float:
    c = tl.ref_block_counts(t, k, rule)
    return float(c.hits.sum() / c.n_truth.sum())


def main(argv=None) -> int:
    d = CFG["scoring_defaults"]
    ap = argparse.ArgumentParser(description="3.0 export 9t reference block tables")
    ap.add_argument("--task", choices=("pit", "pad"), required=True)
    ap.add_argument("--prob", type=Path, default=None)
    ap.add_argument("--fill", choices=("round_robin", "fold_mean", "none"), default=d["zero_feature_fill"])
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--B", type=int, default=200)
    a = ap.parse_args(argv)
    import geopandas as gpd
    pol = tl.policy(a.task)
    base_p = a.prob or (ref_path("pit", "prob") if a.task == "pit"
                        else ek.sub("3.0", "data/interim") / "pad_prob_oof_mosaic_9t.tif")
    if not base_p.exists():
        raise SystemExit(f"probability raster missing: {base_p}. For pads run _transfer_baseline_repeat_9t.py --task pad first.")
    blocks_p = ref_path(a.task, "blocks")
    blocks = gpd.read_file(blocks_p, layer="blocks")
    blocks["block_id"] = blocks.block_id.astype(int)
    held = fold_of_blocks(a.task)
    fill_ids = sorted(set(blocks.block_id) - set(held))
    assign = fill_assignment(fill_ids, a.fill) if a.fill != "none" else {}
    prob_p = base_p
    if assign:
        base, tf, crs = tl.read_prob(base_p)
        pat = str(ref_path(a.task, "fold_rasters")).replace("%7Bk%7D", "{k}")
        filled = fill_mosaic(base, tf, blocks, assign, pat, quantise=(a.task == "pit"))
        tag = "" if a.fill == d["zero_feature_fill"] else f"_{a.fill}"
        prob_p = write_float(ek.sub("3.0", "data/interim") / f"{a.task}_prob_oof_filled{tag}_9t.tif", filled, tf, crs)
        del base, filled
    R = CFG["reference_9t"][a.task]
    md = ek.path_for(R["model_dir"]["key"]) / R["model_dir"]["rel"]
    ckpt = tl.checkpoint_record(md, "out_of_fold", a.task, provisional_reasons=R.get("provisional_reasons"))
    truth, tid = truth_spec(a.task)
    res = tl.score(prob_p, blocks_p, truth, pol["k_per_km2"], truth_id=tid, B=a.B, seed=d["seed"], task=a.task,
                   checkpoint=ckpt)
    fold = {**held, **{b: (f if f != "mean" else None) for b, f in assign.items()}}
    t = tables(res, fold if a.fill != "fold_mean" else None)
    n_with = sum(1 for v in t.values() if v["n_truth"] > 0)
    footprint = "all_blocks" if len(t) == len(blocks) else ("truth_bearing_blocks_only" if len(t) <= n_with else "partial")
    rule = "per_group" if all("fold" in v and v["fold"] is not None for v in t.values()) else "global"
    rec = {"global_k40": pooled(t, pol["k_per_km2"], "global")}
    if rule == "per_group":
        rec["per_group_k40"] = pooled(t, pol["k_per_km2"], "per_group")
    meta = {"task": a.task, "footprint": footprint, "n_blocks": len(t), "n_blocks_with_truth": n_with,
            "n_blocks_filled": len(assign), "fill_rule": a.fill if assign else "none",
            "fill_note": "feature-free blocks were in no training manifest. Fold predictions there are out of sample",
            "k_rule_reference": rule, "dedupe": res["summary"]["scorer"]["dedupe"],
            "edge_blocks": res["summary"]["edge_blocks"], "void_capped_blocks": res["summary"]["void_capped_blocks"],
            "checkpoint": ckpt, "provisional": ckpt["provisional"], "prob": str(prob_p),
            "recall_at_k": rec, "scorer_module_sha256": tl.module_sha256()}
    doc = {**t, "policy": pol, "meta": meta}
    out = a.out_dir or ek.sub("3.0", "results/tables")
    out.mkdir(parents=True, exist_ok=True)
    js = out / OUT_NAME[a.task]
    js.write_text(json.dumps(doc), encoding="utf-8")
    run = ek.new_run("3.0", f"ref_tables_{a.task}", {"prob": str(prob_p), "policy": pol, "fill": a.fill},
                     why="reference block tables, all blocks (review G-02).")
    ek.write_provenance(run, inputs=[prob_p, blocks_p], outputs=[js],
                        params={"policy": pol, "fill": a.fill, "module_sha256": tl.module_sha256()})
    n = sum(len(v["cands"]) for v in t.values())
    print(f"{a.task}: {len(t)} blocks ({len(assign)} filled, footprint {footprint}), {n} candidates, "
          f"{sum(v['n_truth'] for v in t.values())} truth features, cutoff {pol['cutoff']}, recall {rec}\n"
          f"wrote {js}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
