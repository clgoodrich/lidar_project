"""What one NISAR pixel covers, against the pits we actually detect.

WHY THIS FIGURE EXISTS
----------------------
The obvious question about NISAR is "can it find pits?" and the honest answer is
no, for a reason that is purely geometric and worth showing rather than
asserting. The reconnaissance in docs/nisar_lidar_supplement_proposal.md
measured the products over this very tile:

    GCOV  (backscatter)          10 m pixel
    GUNW  (InSAR displacement)   80 m pixel
    our LiDAR derivatives        1 m cell

and the annotations give the other half:

    pit_inside   mean  32.1 m2   ->  ~6 m across
    pit_full     mean 210.7 m2   -> ~16 m across

So a pit is roughly a third of one GCOV pixel and a four-hundredth of one GUNW
pixel. Drawing both grids over a real cluster of annotated pits makes that
instant, and it stops the NISAR slide from over-claiming before it starts.

The figure is the argument FOR the slide, not against it: once the scale is
clear, the useful NISAR question is not "where is the pit" but "is the ground
over the pits we already found moving", which is a per-80-m-cell question and
therefore well matched to GUNW.

COLOUR
------
No new colours. Reuses the repo's already-validated pair from the lost/found
figures -- #1F5FA8 and #D97706, worst pair dE 21.1 deutan / 22.6 normal, both
>= 3:1 against the paper -- over a greyscale hillshade. Nothing green appears,
so the red/green rule cannot be violated. The two grids are additionally
separated by line weight and dash, so colour is never the only encoding.

Run:
    python docs/presentation/figures_30to45min/_nisar_vs_lidar_pit_scale_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/nisar_pixel_vs_pit_scale_9t.png
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import Rectangle

#: backing box so labels stay legible over both black and white hillshade
BOX = dict(boxstyle="round,pad=0.30", fc="#F7F8F6", ec="none", alpha=0.90)
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
HILL = ROOT / "data/9t/derived/1m/hillshade_9t_1m.tif"
ANN = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"
OUT = ROOT / "docs/presentation/figures_30to45min/v6/nisar_pixel_vs_pit_scale_9t.png"

#: densest cluster of annotated interior pits inside the 9t hillshade
CX, CY = 620752.5, 4595843.5
SIDE = 200.0

GCOV_M, GUNW_M = 10.0, 80.0

# validated palette, reused -- see COLOUR above
PIT = "#1F5FA8"      # what the lidar resolves
NISAR = "#D97706"    # what NISAR resolves
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def main() -> int:
    h = SIDE / 2.0
    b = (CX - h, CY - h, CX + h, CY + h)

    with rasterio.open(HILL) as src:
        w = from_bounds(*b, transform=src.transform)
        img = src.read(1, window=w).astype("float32")
        img[img == src.nodata] = np.nan

    pits = gpd.read_file(ANN, layer="pit_inside", bbox=b)
    pads = gpd.read_file(ANN, layer="pad", bbox=b)

    fig, ax = plt.subplots(figsize=(10.6, 9.4))
    fig.patch.set_facecolor(PAPER)
    ax.imshow(img, cmap="gray", extent=(b[0], b[2], b[1], b[3]),
              vmin=np.nanpercentile(img, 2), vmax=np.nanpercentile(img, 98))

    pads.boundary.plot(ax=ax, color=PIT, lw=1.4, ls=":", alpha=0.85)
    pits.boundary.plot(ax=ax, color=PIT, lw=2.6)

    # GCOV grid -- thin, dashed
    for v in np.arange(np.ceil(b[0] / GCOV_M) * GCOV_M, b[2], GCOV_M):
        ax.plot([v, v], [b[1], b[3]], color=NISAR, lw=0.55, ls=(0, (4, 3)),
                alpha=0.75)
    for v in np.arange(np.ceil(b[1] / GCOV_M) * GCOV_M, b[3], GCOV_M):
        ax.plot([b[0], b[2]], [v, v], color=NISAR, lw=0.55, ls=(0, (4, 3)),
                alpha=0.75)

    # one GUNW cell -- heavy, solid, centred on the pit cluster rather than
    # snapped to a multiple of 80 m: NISAR's grid origin is arbitrary against
    # ours, and snapping put the pits on the cell edge, where the comparison
    # reads as a near miss instead of a containment.
    pc = pits.geometry.union_all().centroid
    gx, gy = pc.x - GUNW_M / 2, pc.y - GUNW_M / 2
    ax.add_patch(Rectangle((gx, gy), GUNW_M, GUNW_M, fill=False,
                           edgecolor=NISAR, lw=3.4))
    # label inside the cell, clear of the outlines it would otherwise cross
    ax.annotate("one NISAR InSAR pixel  80 m × 80 m",
                xy=(gx + GUNW_M / 2, gy + GUNW_M - 5), ha="center", va="top",
                fontsize=17, fontweight="bold", color=NISAR, bbox=BOX)
    ax.annotate("NISAR backscatter grid, 10 m",
                xy=(b[0] + 6, b[3] - 10), ha="left", va="top",
                fontsize=16, color=NISAR, fontweight="bold", bbox=BOX)
    ax.annotate(f"{len(pits)} annotated pits, mean 32 m²  —  "
                "hand-drawn on the lidar",
                xy=(b[0] + 6, b[1] + 8), ha="left", va="bottom",
                fontsize=16, color=PIT, fontweight="bold", bbox=BOX)

    ax.set_xlim(b[0], b[2]); ax.set_ylim(b[1], b[3])
    ax.set_xlabel("UTM 17N easting (m)", fontsize=13, color=MUTED)
    ax.set_ylabel("UTM 17N northing (m)", fontsize=13, color=MUTED)
    ax.tick_params(colors=MUTED, labelsize=11.5)
    ax.set_title("A pit is a third of one NISAR pixel",
                 loc="left", fontsize=24, fontweight="bold", color=INK, pad=14)

    # No caption baked into the image: explanatory text belongs in the
    # slide's own left-hand column, not burned into the PNG where it
    # cannot be edited, re-wrapped or read at presentation size.
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=170, facecolor=PAPER)
    plt.close(fig)
    print(f"  {len(pits)} pits, {len(pads)} pads in the window")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
