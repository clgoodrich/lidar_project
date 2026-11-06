"""Render a grid of sample pits with label overlay for visual QC.

WHY BOTHER
----------
The label pipeline has two silent failure modes and neither one errors:

  * `rasterize()` returns an all-zero array for an empty shape list. A label
    raster of nine million zeros writes and opens like a good one.
  * a transform that is off by a fraction of a cell puts every label a metre
    from the pit it describes. Training still runs. It just learns nothing.

Both are obvious in a picture and invisible in a log. Two minutes here saves
ninety minutes of training on garbage.

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
    """Read a square of ground around a map coordinate, not around a pixel.

    from_bounds() converts metres to a pixel window using that raster's own
    transform, so the same call returns the matching patch from rasters on
    different grids. If two of the three panels below look shifted from each
    other, that is a real grid mismatch, not a plotting artefact.
    """
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

    # bg is fully transparent (the trailing 00) so the terrain shows through;
    # floor and wall are half-opaque (aa) so you can still see what is under them.
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

        # LRM with a diverging colormap, scaled to the 98th percentile of this
        # patch. Local relief is signed -- red for above the local surface, blue
        # for below -- so a pit floor should read blue and its rim red. Clipping
        # at p98 stops one extreme cell from flattening the whole patch to grey.
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
