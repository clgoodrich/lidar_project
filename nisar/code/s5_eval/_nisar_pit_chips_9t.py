"""Look at the newest NISAR L-band scenes and the cleanest leaf-off scene at two pits (459 and 626), HH amplitude in dB.

Each chip is 200 m square at 5 m pixels. The pit_full outline (orange) and pit_inside outline (white) are drawn on top.
Printed: the HH level at the pit centre pixel against the median of a 20 to 100 m ring, in dB.

Scenes: 2026-10-14 (track 26 descending), 2026-10-11 (track 162), 2025-11-21 (track 162, leaf-off and snow-free).

Run:
  python nisar/code/s5_eval/_nisar_pit_chips_9t.py
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import rasterio
from matplotlib import pyplot as plt
from pyproj import Transformer
from rasterio.windows import from_bounds

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[3]
W = ROOT / "nisar/derived/9t/nisar_gslc_5m"
G = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"
SCENES = [("20261014", "t026D"), ("20261011", "t162A"), ("20251121", "t162A")]
PITS = {"459 (box)": ("pit_full", 459), "626 / 512 (water)": ("pit_full", 626)}
HALF = 100.0
T = Transformer.from_crs(6346, 32617, always_xy=True)


def main():
    pf = gpd.read_file(G, layer="pit_full").set_index("pit_full_id")
    pi = gpd.read_file(G, layer="pit_inside").set_index("pit_inside_id")
    fig, axes = plt.subplots(len(PITS), len(SCENES), figsize=(4.2 * len(SCENES), 4.2 * len(PITS)))
    for r, (label, (_, fid)) in enumerate(PITS.items()):
        full = pf.loc[fid].geometry
        inner = pi.loc[int(pf.loc[fid].pit_inside_id)].geometry if np.isfinite(pf.loc[fid].pit_inside_id) else None
        cx, cy = T.transform(*full.centroid.coords[0])
        for c, (d, tr) in enumerate(SCENES):
            f = next(W.glob(f"nisar_gslc_hh_hv_complex_{d}_{tr}_9t_5m.tif"))
            with rasterio.open(f) as s:
                win = from_bounds(cx - HALF, cy - HALF, cx + HALF, cy + HALF, transform=s.transform)
                a = s.read(1, window=win, boundless=True, fill_value=0)
            db = 20 * np.log10(np.abs(a) + 1e-9)
            n = db.shape[0]
            yy, xx = np.mgrid[:n, :n]
            dist = np.hypot(yy - n / 2 + 0.5, xx - n / 2 + 0.5) * 5
            centre = db[dist <= 5].mean()
            bg = np.median(db[(dist > 20) & (dist <= 100)])
            ax = axes[r, c]
            ax.imshow(db, cmap="gray", extent=(-HALF, HALF, -HALF, HALF), vmin=np.percentile(db, 2), vmax=np.percentile(db, 98))
            for g, col in ((full, "#D97706"), (inner, "white")):
                if g is None:
                    continue
                for p in getattr(g, "geoms", [g]):
                    x, y = zip(*[T.transform(*q) for q in p.exterior.coords])
                    ax.plot(np.array(x) - cx, np.array(y) - cy, color=col, lw=1.4)
            ax.set_title(f"{label}  {d[:4]}-{d[4:6]}-{d[6:]} {tr}\ncentre {centre - bg:+.1f} dB vs ring", fontsize=9)
            ax.set_xticks([]); ax.set_yticks([])
            print(f"{label:18s} {d} {tr}: centre {centre:.1f} dB, ring {bg:.1f} dB, diff {centre - bg:+.1f}")
    fig.suptitle("NISAR L-band HH amplitude, 200 m chips (orange pit_full, white pit_inside)", fontsize=10)
    fig.tight_layout()
    out = ROOT / "nisar/results/9t/nisar_pit_chips_latest_9t.png"
    fig.savefig(out, dpi=110)
    print(out)


if __name__ == "__main__":
    main()
