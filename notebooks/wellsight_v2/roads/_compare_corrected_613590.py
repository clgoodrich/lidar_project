"""Before/after visual for the 613590 road correction loop.

Champion (`road_unet_1m_recall`) vs corrected (`road_unet_1m_corrected`)
P(road) over the same hillshade, with the human corrections overlaid:
green = added roads (should light up AFTER), red = rejected segments (should
go dark AFTER). Renders a full-block pair plus a zoom on the correction-dense
NW quadrant.

Reproduce:
  python notebooks/wellsight_v2/roads/_compare_corrected_613590.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.lines import Line2D
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T

BLOCK = DERIV / "tiles" / "data_3x3" / "westernpa_d20" / "613590"
CORR = BLOCK / "corrections"
BEFORE = DERIV_9T / "road_unet_1m_recall" / "road_prob_613590_1m.tif"
AFTER = DERIV_9T / "road_unet_1m_corrected" / "road_prob_613590_1m.tif"
HILLSHADE = BLOCK / "hillshade_613590_1m.tif"
OUT = DERIV_9T / "road_unet_1m_corrected"


def read_win(path, bounds=None, band=1):
    with rasterio.open(path) as r:
        if bounds is None:
            arr = r.read(band)
            ext = (r.bounds.left, r.bounds.right, r.bounds.bottom, r.bounds.top)
        else:
            win = from_bounds(*bounds, r.transform)
            arr = r.read(band, window=win)
            ext = (bounds[0], bounds[2], bounds[1], bounds[3])
    return arr, ext


def panel(ax, hs, hs_ext, prob, prob_ext, title, added, rejected):
    ax.imshow(hs, cmap="gray", extent=hs_ext, origin="upper",
              vmin=np.percentile(hs[hs > 0], 2) if (hs > 0).any() else 0,
              vmax=np.percentile(hs[hs > 0], 98) if (hs > 0).any() else 255)
    m = np.ma.masked_where(prob < 0.3, prob)
    ax.imshow(m, cmap="viridis", extent=prob_ext, origin="upper",
              vmin=0.3, vmax=1.0, alpha=0.75)
    if len(rejected):
        rejected.plot(ax=ax, color="#e31a1c", linewidth=1.1)
    if len(added):
        added.plot(ax=ax, color="#33ff66", linewidth=1.4)
    ax.set_title(title, fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])


def main() -> int:
    if not AFTER.exists():
        print(f"missing {AFTER} — run the corrected trainer first")
        return 1
    added = gpd.read_file(CORR / "correction_lines_613590.gpkg", layer="added")
    rejected = gpd.read_file(CORR / "correction_lines_613590.gpkg",
                             layer="reject")
    add_test = added[added.split.isin(["val", "test"])]
    rej_test = rejected[rejected.split.isin(["val", "test"])]

    for tag, bounds in [("full", None),
                        ("zoom", (613550, 4591800, 616400, 4594500))]:
        hs, hs_ext = read_win(HILLSHADE, bounds)
        pb, pb_ext = read_win(BEFORE, bounds)
        pa, pa_ext = read_win(AFTER, bounds)
        fig, axes = plt.subplots(1, 2, figsize=(17, 8.6))
        panel(axes[0], hs, hs_ext, pb, pb_ext,
              "BEFORE — road_unet_1m_recall (champion)", add_test, rej_test)
        panel(axes[1], hs, hs_ext, pa, pa_ext,
              "AFTER — road_unet_1m_corrected (fine-tuned on corrections)",
              add_test, rej_test)
        handles = [
            Line2D([], [], color="#33ff66", lw=2,
                   label="human ADDED roads (held out) — should light up"),
            Line2D([], [], color="#e31a1c", lw=2,
                   label="human REJECTED segments (held out) — should darken")]
        fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
                   fontsize=10)
        fig.suptitle(f"613590 road probability, active-learning correction "
                     f"loop ({tag})", fontsize=13)
        fig.tight_layout(rect=[0, 0.04, 1, 1])
        p = OUT / f"compare_corrections_{tag}.png"
        fig.savefig(p, dpi=135)
        plt.close(fig)
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
