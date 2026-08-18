"""Unified spatial-block split for the MULTITASK U-Net (pit + road + pad heads).

The multitask model samples one set of patches whose pixels are supervised by all
three heads, so every head MUST share ONE consistent block split or a patch
centered on (say) a pad in a pad-"train" block could overlap a pit-"test" block ->
cross-head leakage. The standalone trainers each use their own feature-appropriate
split (pit->pit blocks, pad->pad blocks); those are fine in isolation but
inconsistent with each other.

This builds a single split where a block is train/val/test if it contains ANY
annotated feature (pit OR pad OR road), assigned by greedy balance on TOTAL
feature count (RNG_SEED=42, 70/15/15). It reuses the existing 12x12 block grid
geometry and the per-feature block_id already recorded in each manifest, so it
just RE-LABELS the split column consistently -- no re-chunking, no re-running the
standalone models.

Outputs (under data/derivatives/tiles/9t/), all multitask-only (standalone files
untouched):
    blocks_unified_9t.gpkg
    pit_dataset_manifest_unified.csv
    pad_dataset_manifest_unified.csv
    road_dataset_manifest_unified.csv

Run:  python notebooks/wellsight/annotations/_build_unified_split.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T as D

PIT_BLOCKS = D / "pit_blocks_9t.gpkg"
MAN = {
    "pit":  D / "pit_dataset_manifest.csv",
    "pad": D / "pad_dataset_manifest.csv",
    "road": D / "road_dataset_manifest.csv",
}
SPLIT_FRACS = {"train": 0.70, "val": 0.15, "test": 0.15}
RNG_SEED = 42


def main() -> int:
    blocks = gpd.read_file(PIT_BLOCKS, layer="blocks")[["block_id", "geometry"]].copy()

    # Count features per block across all three manifests (each row has block_id).
    counts = {}
    mans = {}
    for k, p in MAN.items():
        m = pd.read_csv(p)
        mans[k] = m
        bc = m.dropna(subset=["block_id"]).groupby("block_id").size()
        for bid, n in bc.items():
            counts[int(bid)] = counts.get(int(bid), 0) + int(n)
    blocks["n_feat"] = blocks["block_id"].map(counts).fillna(0).astype(int)

    # Greedy fill by TOTAL feature count (mirrors the other split builders).
    total = int(blocks["n_feat"].sum())
    active = (blocks[blocks.n_feat > 0][["block_id", "n_feat"]]
              .sample(frac=1, random_state=RNG_SEED).values)
    targets = {s: total * f for s, f in SPLIT_FRACS.items()}
    running = {s: 0 for s in SPLIT_FRACS}
    split_of = {}
    for bid, n in active:
        chosen = max(SPLIT_FRACS, key=lambda s: targets[s] - running[s])
        split_of[int(bid)] = chosen
        running[chosen] += n
    blocks["split"] = blocks["block_id"].map(split_of).fillna("unused")
    blocks.to_file(D / "blocks_unified_9t.gpkg", layer="blocks", driver="GPKG")

    print("Unified block split (any feature):")
    for s in ["train", "val", "test", "unused"]:
        sub = blocks[blocks.split == s]
        print(f"  {s:8s} blocks={len(sub):3d}  features={int(sub.n_feat.sum()):5d}")

    # Re-label each manifest's split column from the unified block map.
    for k, m in mans.items():
        m = m.copy()
        m["split"] = m["block_id"].map(split_of).fillna("unused")
        out = D / f"{ 'pit' if k=='pit' else 'pad' if k=='pad' else 'road' }_dataset_manifest_unified.csv"
        m.to_csv(out, index=False)
        used = m[m.split.isin(["train", "val", "test"])]
        print(f"  {k:4s}: {len(used)}/{len(m)} used  splits={used['split'].value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
