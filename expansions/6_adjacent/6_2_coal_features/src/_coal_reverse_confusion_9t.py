"""6.2 S5. Reverse confusion. How often the mine-class model calls 9t well pits a mine feature at K.

Purpose
    Score the S4 mine-class model on 9t. --predict writes the any-mine probability (1 minus P(background))
    from each fold checkpoint, a GPU user step. The default scores saved rasters. Candidates use the fw_00 rule
    per 9t block (mean over the fold rasters, 0.10 floor, 4 m2, mean-probability score). The top K = 40 per km2
    over the complete 9t blocks are matched to the annotated pit floors (IoU 0.3, one to one). A second, looser
    count uses a candidate centroid inside the floor. Primary is the share of annotated 9t pits hit by a
    top-K mine candidate, with a block-bootstrap interval (375 m blocks, B = 2000). Evidence level a.
Inputs
    expansions/6_adjacent/6_2_coal_features/models/unet_coal_cv5/mine/seed<s>/fold<k>/best.pt  (S4)
    or mine_prob_any_cvfold<k>_9t_05.tif rasters beside them
    data/9t/derived/05/features_pit_9t_05.tif, pit_blocks_9t.gpkg, qgis/annotations/annotations_proj.gpkg (held)
Outputs
    expansions/6_adjacent/6_2_coal_features/results/tables/coal_reverse_confusion_9t.json
    expansions/6_adjacent/6_2_coal_features/results/tables/coal_reverse_hits_9t.csv
Run
    python expansions/6_adjacent/6_2_coal_features/src/_coal_reverse_confusion_9t.py [--seed 0] [--predict]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _coal_common as K
from _coal_common import C, ek


def predict_any_mine(ck_path: Path, feats: Path, out_tif: Path, patch: int, overlap: int) -> Path:
    import torch
    import _confuser_unet_cv5_9t as TR
    _dl, _ = TR.import_trainers()
    ck = torch.load(ck_path, map_location="cpu", weights_only=False)
    with __import__("rasterio").open(feats) as r:
        n_ch = r.count
    model = _dl.UNet(in_ch=n_ch, n_classes=4, base=32)
    model.load_state_dict(ck["state_dict"])
    prob, _, prof = _dl.predict_full_tile(model, feats, np.asarray(ck["mu"]), np.asarray(ck["sd"]), patch=patch,
                                          overlap=overlap, n_classes=4)
    import sys
    sys.path.insert(0, str(C.TRAIN_DIR.parent))
    from _common import write_tif
    write_tif(out_tif, (1.0 - prob[0]).astype(np.float32), transform=prof["transform"], crs=prof["crs"])
    return out_tif


def reverse_hits(cands, pits, blocks, iou: float, k_per_km2: float):
    km2 = float(blocks.area.sum() / 1e6)
    top, k = C.top_k(cands, km2, k_per_km2)
    top = top.reset_index(drop=True)
    m = C.greedy_match(pits, top, iou, truth_id="truth_id")
    hit_iou = set(x for x in m if x is not None)
    cen = top.geometry.centroid
    hit_in = set()
    for r in pits.itertuples():
        if cen.within(r.geometry).any():
            hit_in.add(r.truth_id)
    p = pits.assign(hit_iou=pits.truth_id.isin(hit_iou), hit_centroid=pits.truth_id.isin(hit_in))
    return p, k


def summarise(p: pd.DataFrame, blocks, B: int, seed: int) -> dict:
    bl = sorted(blocks.block_id.astype(int))
    n = p.groupby("block_id").size()
    h = p.groupby("block_id").hit_iou.sum()

    def share(L):
        d = sum(n.get(b, 0) for b in L)
        return sum(h.get(b, 0) for b in L) / d if d else np.nan
    pt, lo, hi, _ = ek.block_bootstrap(share, bl, B=B, seed=seed)
    return {"n_pits": int(len(p)), "hits_iou": int(p.hit_iou.sum()), "hits_centroid": int(p.hit_centroid.sum()),
            "share_pits_called_mine": pt, "lo95": lo, "hi95": hi, "n_blocks": len(bl), "evidence_level": "a",
            "note": "Drawn pits on 9t labelled mine by the mine model at K. Not a statement about wells."}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--seed", type=int, default=0, help="mine-model seed index to score")
    ap.add_argument("--predict", action="store_true", help="write the 9t any-mine rasters from checkpoints (GPU)")
    ap.add_argument("--B", type=int, default=None)
    a = ap.parse_args()
    cfg = K.load_config(a.config)
    root = ek.sub("6.2", "models") / "unet_coal_cv5" / "mine" / f"seed{a.seed}"
    feats = C.input_path(cfg, "features_9t")
    if a.predict:
        for ck in sorted(root.glob("fold*/best.pt")):
            k = ck.parent.name.replace("fold", "")
            print(predict_any_mine(ck, feats, ck.parent / f"mine_prob_any_cvfold{k}_9t_05.tif",
                                   cfg["train"]["patch"], cfg["train"]["overlap"]))
    paths = sorted(root.glob("fold*/mine_prob_any_cvfold*_9t_05.tif"))
    if not paths:
        raise K.MissingInput(f"no 9t mine rasters under {root}. Train S4 and run with --predict first.")
    blocks = C.read_vector(C.input_path(cfg, "blocks_9t"), cfg["crs"], layer="blocks")
    import _confuser_pooled_score_9t as PS
    cands = PS.arm_candidates(paths, blocks, cfg["crs"], cfg["score"])
    t = cfg["inputs"]["truth"]
    pits = C.read_vector(C.input_path(cfg, "truth"), cfg["crs"], layer=t["layer"])
    pits = pits[[t["id"], "geometry"]].dissolve(by=t["id"]).reset_index().rename(columns={t["id"]: "truth_id"})
    pits["block_id"] = C.block_of_points(np.column_stack([pits.geometry.centroid.x, pits.geometry.centroid.y]), blocks)
    pits = pits[pits.block_id.notna()].reset_index(drop=True)
    p, k = reverse_hits(cands, pits, blocks, cfg["score"]["iou"], cfg["score"]["k_per_km2"])
    res = summarise(p, blocks, a.B or cfg["score"]["B"], ek.child_seed(cfg["train"]["master_seed"], 0, 50)) | {"K": k}
    out = ek.sub("6.2", "results/tables")
    p.drop(columns="geometry").to_csv(out / "coal_reverse_hits_9t.csv", index=False)
    (out / "coal_reverse_confusion_9t.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
