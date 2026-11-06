"""NAIP aerial photo chips at one pit, with the pit_full and pit_inside outlines drawn on top.

Source: USDA NAIP via Microsoft Planetary Computer STAC (0.6 m for 2019 and 2022, 1.0 m for 2013 to 2017), windowed read.
Default pit: pit_inside_id 288, pit_full_id 495, pad_id 818.

Run:
  python notebooks/wellsight_v2/s5_eval/_pit_naip_chip_9t.py
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import rasterio
import requests
from matplotlib import pyplot as plt
from pyproj import Transformer
from rasterio.windows import from_bounds

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"
PIT_INSIDE = 288
HALF = 40.0
YEARS = ["20220619", "20190917", "20170515", "20150728"]
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"


def sign(href):
    r = requests.get(f"https://planetarycomputer.microsoft.com/api/sas/v1/sign?href={href}", timeout=60)
    return r.json()["href"]


def main():
    pi = gpd.read_file(G, layer="pit_inside").set_index("pit_inside_id")
    pf = gpd.read_file(G, layer="pit_full")
    inner = pi.loc[PIT_INSIDE].geometry
    full = pf[pf.pit_inside_id == PIT_INSIDE].geometry.iloc[0]
    ll = gpd.GeoSeries([inner.centroid], crs=6346).to_crs(4326).iloc[0]
    items = requests.post(f"{STAC}/search", json={"collections": ["naip"], "intersects": {"type": "Point", "coordinates": [ll.x, ll.y]}, "limit": 20}, timeout=60).json()["features"]
    by = {f["properties"]["datetime"][:10].replace("-", ""): f for f in items}
    cx, cy = inner.centroid.coords[0]
    fig, axes = plt.subplots(1, len(YEARS), figsize=(4.2 * len(YEARS), 4.6))
    for ax, y in zip(axes, YEARS):
        f = by[y]
        with rasterio.open(sign(f["assets"]["image"]["href"])) as s:
            t = Transformer.from_crs(6346, s.crs, always_xy=True)
            x0, y0 = t.transform(cx, cy)
            win = from_bounds(x0 - HALF, y0 - HALF, x0 + HALF, y0 + HALF, transform=s.transform)
            a = s.read([1, 2, 3], window=win, boundless=True, fill_value=0)
        ax.imshow(np.moveaxis(a, 0, -1), extent=(-HALF, HALF, -HALF, HALF))
        for g, col in ((full, "#D97706"), (inner, "white")):
            for p in getattr(g, "geoms", [g]):
                xs, ys = zip(*[t.transform(*q) for q in p.exterior.coords])
                ax.plot(np.array(xs) - x0, np.array(ys) - y0, color=col, lw=1.3)
        ax.set_title(f"NAIP {y[:4]}-{y[4:6]}-{y[6:]}  {f['properties'].get('gsd')} m", fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(f"pit_inside {PIT_INSIDE} (white), pit_full 495 (orange), pad 818; 80 m chips", fontsize=10)
    fig.tight_layout()
    out = ROOT / "data/9t/results/pit/pit_naip_chip_288_9t.png"
    fig.savefig(out, dpi=120)
    print(out)


if __name__ == "__main__":
    main()
