"""QC overlay for the 613590 drainage review package.

Renders hillshade + vectorized drainage over the block plus a zoom, so the
package can be eyeballed before it goes into QGIS. Existing road predictions are
drawn faintly for context — drainage and roads should not be tracing the same
lines.

Output: <block>/review_drainage/drainage_review_overlay_613590_1m.png
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import rasterio
from rasterio.plot import plotting_extent

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV  # noqa: E402

KEY = "613590"
BLK = DERIV / "tiles" / "data_3x3" / "westernpa_d20" / KEY
RD = BLK / "review_drainage"


def draw(ax, hs, ext, drain, roads, title, win=None):
    ax.imshow(hs, cmap="gray", extent=ext, origin="upper",
              vmin=np.nanpercentile(hs, 2), vmax=np.nanpercentile(hs, 98))
    if roads is not None and len(roads):
        roads.plot(ax=ax, color="#c86400", linewidth=0.4, zorder=2, alpha=0.7)
    if len(drain):
        drain.plot(ax=ax, color="#1f78dc", linewidth=1.2, zorder=4)
    if win:
        ax.set_xlim(win[0], win[2])
        ax.set_ylim(win[1], win[3])
    else:
        ax.set_xlim(ext[0], ext[1])
        ax.set_ylim(ext[2], ext[3])
    ax.set_title(title, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])


def main() -> int:
    with rasterio.open(BLK / f"hillshade_{KEY}_1m.tif") as r:
        hs = r.read(1).astype(np.float32)
        hs[hs < 0] = np.nan
        ext = plotting_extent(r)

    drain = gpd.read_file(RD / f"review_drainage_{KEY}.gpkg")
    rp = BLK / "review" / f"review_roads_{KEY}.gpkg"
    roads = gpd.read_file(rp).to_crs(drain.crs) if rp.exists() else None

    # zoom on the densest drainage cluster
    c = drain.geometry.centroid
    H, xe, ye = np.histogram2d(c.x, c.y, bins=10)
    i, j = np.unravel_index(np.argmax(H), H.shape)
    cx, cy = (xe[i] + xe[i + 1]) / 2, (ye[j] + ye[j + 1]) / 2
    half = 550.0
    win = (cx - half, cy - half, cx + half, cy + half)

    km = drain.length.sum() / 1000
    fig, axes = plt.subplots(1, 2, figsize=(17, 8.6))
    draw(axes[0], hs, ext, drain, roads,
         f"613590 full block — vectorized drainage {km:.1f} km "
         f"({km/20.25:.2f} km/km²), {len(drain)} segments")
    draw(axes[1], hs, ext, drain, roads,
         "zoom 1.1x1.1 km — do the blue lines sit in the valley bottoms?",
         win=win)
    handles = [
        plt.Line2D([], [], color="#1f78dc", lw=1.8, label="vectorized drainage"),
        plt.Line2D([], [], color="#c86400", lw=1.2, label="predicted roads (context)"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
               fontsize=9)
    fig.suptitle(
        "Drainage review package QC — dedicated drainage U-Net, extraction "
        "calibrated on 9t GT (comp 0.824 / corr 0.737 / F1 0.778)", fontsize=11)
    fig.tight_layout(rect=[0, 0.035, 1, 0.96])
    out = RD / f"drainage_review_overlay_{KEY}_1m.png"
    fig.savefig(out, dpi=135)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
