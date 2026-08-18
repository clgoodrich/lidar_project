"""Pad-aware spatial-block split for the STANDALONE pad/pad U-Net.

The pit dataset (`_build_pit_dataset.py`) assigns train/val/test by *pit* content,
leaving pit-free blocks "unused". `_build_pad_road_dataset.py` then inherits that
split for pads, so every pad in a pit-free block is dropped (~420 of ~995). For a
dedicated pad model that is pure waste -- a pit-free block is a perfectly good pad
block. This builds an independent split keyed on PAD content so the pad U-Net uses
all pads, reusing the exact same 12x12 block grid geometry as the pit split.

Reuses pit_blocks_9t.gpkg ONLY for the block polygons (geometry + block_id);
the split column is recomputed from pads. Mirrors the pit greedy-fill method
(balance by feature COUNT, RNG_SEED=42, 70/15/15).

Outputs (under data/derivatives/tiles/9t/):
    pad_blocks_9t.gpkg        12x12 grid, split assigned by pad content
    pad_dataset_manifest.csv  per-pad: pad_id, block_id, split, centroid_x/y
                               (OVERWRITES the pit-inherited version)

Run:  python notebooks/wellsight_v2/s2_labels/_build_pad_split.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T as D, path_for, read_layer

ANN = path_for("truth") / "annotations_proj.gpkg"
PIT_BLOCKS = D / "pit_blocks_9t.gpkg"
SPLIT_FRACS = {"train": 0.70, "val": 0.15, "test": 0.15}
RNG_SEED = 42


def main() -> int:
    blocks = gpd.read_file(PIT_BLOCKS, layer="blocks")[["block_id", "geometry"]].copy()
    pad = read_layer(ANN, "pad").copy()
    pad = pad[~pad.geometry.isna() & ~pad.geometry.is_empty].copy()
    pad["ctr_x"] = pad.geometry.centroid.x
    pad["ctr_y"] = pad.geometry.centroid.y

    # Count pads per block via centroid-in-block spatial join.
    cent = gpd.GeoDataFrame(
        pad[["pad_id", "ctr_x", "ctr_y"]],
        geometry=gpd.points_from_xy(pad["ctr_x"], pad["ctr_y"]), crs=pad.crs,
    )
    joined = gpd.sjoin(cent, blocks, how="left", predicate="within")
    n_per_block = joined.groupby("block_id").size()
    blocks["n_pads"] = blocks["block_id"].map(n_per_block).fillna(0).astype(int)

    # Greedy fill by PAD COUNT (mirrors _build_pit_dataset): shuffle pad-bearing
    # blocks, assign each to whichever split has the largest remaining deficit.
    total = int(blocks["n_pads"].sum())
    pad_blocks = (blocks[blocks.n_pads > 0][["block_id", "n_pads"]]
                  .sample(frac=1, random_state=RNG_SEED).values)
    targets = {s: total * f for s, f in SPLIT_FRACS.items()}
    running = {s: 0 for s in SPLIT_FRACS}
    split_of = {}
    for bid, n in pad_blocks:
        chosen = max(SPLIT_FRACS, key=lambda s: targets[s] - running[s])
        split_of[int(bid)] = chosen
        running[chosen] += n
    blocks["split"] = blocks["block_id"].map(split_of).fillna("unused")

    blocks.to_file(D / "pad_blocks_9t.gpkg", layer="blocks", driver="GPKG")

    print("Pad block split summary:")
    for s in ["train", "val", "test", "unused"]:
        sub = blocks[blocks.split == s]
        print(f"  {s:8s} blocks={len(sub):3d}  pads={int(sub.n_pads.sum()):4d}")

    # Per-pad manifest from the new block splits.
    joined["split"] = joined["block_id"].map(split_of).fillna("unused")
    man = joined[["pad_id", "block_id", "split", "ctr_x", "ctr_y"]].copy()
    man.columns = ["pad_id", "block_id", "split", "centroid_x", "centroid_y"]
    man = man.dropna(subset=["block_id"])
    man["block_id"] = man["block_id"].astype(int)
    man.to_csv(D / "pad_dataset_manifest.csv", index=False)
    print(f"\npad_dataset_manifest.csv  splits={man['split'].value_counts().to_dict()}")
    print(f"  total pads used (train+val+test): "
          f"{int((man.split != 'unused').sum())} / {len(man)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
