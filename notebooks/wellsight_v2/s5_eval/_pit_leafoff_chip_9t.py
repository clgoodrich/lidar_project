"""Leaf-off aerial photo of one pit with the pit_full and pit_inside outlines on top.

Source: PEMA Venango County mosaic (PASDA map service PEMAImagery2018, layer 242, "PEMA_VenangoCounty_Mosaic2020"), exported
in EPSG:6346 so the outlines need no reprojection. Flight date not yet confirmed from metadata.
Default pit: pit_inside_id 288, pit_full_id 495, pad_id 818.

Run:
  python notebooks/wellsight_v2/s5_eval/_pit_leafoff_chip_9t.py [pit_inside_id]
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import requests
from matplotlib import pyplot as plt
from PIL import Image

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"
URL = "https://services.pasda.psu.edu/server/rest/services/pasda/PEMAImagery2018/MapServer/export"
HALF = 40.0


def main(pid=288):
    pi = gpd.read_file(G, layer="pit_inside").set_index("pit_inside_id")
    pf = gpd.read_file(G, layer="pit_full")
    inner = pi.loc[pid].geometry
    full = pf[pf.pit_inside_id == pid].geometry.iloc[0]
    cx, cy = inner.centroid.coords[0]
    r = requests.get(URL, params=dict(bbox=f"{cx-HALF},{cy-HALF},{cx+HALF},{cy+HALF}", bboxSR=6346, imageSR=6346,
                                      size="1000,1000", layers="show:242", format="png", f="image"), timeout=90)
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.5))
    for k, ax in enumerate(axes):
        ax.imshow(im, extent=(-HALF, HALF, -HALF, HALF))
        if k:
            for g, col in ((full, "#D97706"), (inner, "white")):
                for p in getattr(g, "geoms", [g]):
                    xs, ys = zip(*p.exterior.coords)
                    ax.plot([x - cx for x in xs], [y - cy for y in ys], color=col, lw=1.6)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title("leaf-off aerial photo" if not k else f"outlines: pit_inside {pid} (white), pit_full (orange)", fontsize=10)
    fig.suptitle("80 m chip, PEMA Venango leaf-off mosaic", fontsize=10)
    fig.tight_layout()
    out = ROOT / f"data/9t/results/pit/pit_leafoff_chip_{pid}_9t.png"
    fig.savefig(out, dpi=110)
    print(out)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 288)
