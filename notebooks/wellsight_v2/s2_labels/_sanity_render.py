"""Render a grid of sample pits with label overlay for visual QC.

Picks 4 pits from each split (train/val/test), shows hillshade + label mask side-by-side.
Output: data/derivatives/tiles/9t/sanity_pit_labels.png
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import ListedColormap
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T as D
HS = D / "hillshade_9t_05.tif"
LRM = D / "lrm_25_9t_05.tif"
LBL = D / "labels_pit_9t_05.tif"
MAN = D / "pit_dataset_manifest.csv"
OUT = D / "sanity_pit_labels.png"

PATCH_M = 30.0  # half-side in meters around centroid (so 60 m total)
N_PER_SPLIT = 4


def read_window(path, cx, cy, half_m):
    with rasterio.open(path) as r:
        win = from_bounds(cx - half_m, cy - half_m, cx + half_m, cy + half_m, r.transform)
        return r.read(1, window=win), r.window_transform(win)


def main():
    man = pd.read_csv(MAN)
    rng = np.random.default_rng(7)
    rows = []
    for split in ("train", "val", "test"):
        sub = man[man.split == split]
        pick = sub.sample(min(N_PER_SPLIT, len(sub)), random_state=7)
        rows.append(pick.assign(_split=split))
    sample = pd.concat(rows).reset_index(drop=True)
    n = len(sample)
    print(f"Rendering {n} pits ({sample['_split'].value_counts().to_dict()})")

    fig, axes = plt.subplots(n, 3, figsize=(9, 3 * n))
    if n == 1:
        axes = axes[None, :]

    label_cmap = ListedColormap(["#00000000", "#ff3333aa", "#3399ffaa"])  # bg/floor/wall

    for i, row in sample.iterrows():
        cx, cy = float(row.centroid_x), float(row.centroid_y)
        hs, _ = read_window(HS, cx, cy, PATCH_M)
        lrm, _ = read_window(LRM, cx, cy, PATCH_M)
        lbl, _ = read_window(LBL, cx, cy, PATCH_M)

        for ax in axes[i]:
            ax.set_xticks([]); ax.set_yticks([])

        axes[i, 0].imshow(hs, cmap="gray")
        axes[i, 0].imshow(lbl, cmap=label_cmap, vmin=0, vmax=2, interpolation="nearest")
        axes[i, 0].set_title(f"pit {int(row.pit_inside_id)} [{row._split}]  hillshade + label", fontsize=8)

        # LRM with diverging colormap
        v = np.nanpercentile(np.abs(lrm), 98)
        axes[i, 1].imshow(lrm, cmap="RdBu_r", vmin=-v, vmax=v)
        axes[i, 1].imshow(lbl, cmap=label_cmap, vmin=0, vmax=2, interpolation="nearest")
        axes[i, 1].set_title("LRM25 + label", fontsize=8)

        axes[i, 2].imshow(lbl, cmap=ListedColormap(["#222222", "#ff3333", "#3399ff"]),
                          vmin=0, vmax=2, interpolation="nearest")
        axes[i, 2].set_title(f"label  (floor=red, wall=blue)", fontsize=8)

    plt.tight_layout()
    plt.savefig(OUT, dpi=110, bbox_inches="tight")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
