"""NAIP and lidar chips for NISAR steady-bright targets and for open lidar pads, 9t. Set 2026-11-25.

Why
  The steel test asks whether steady bright pixels fall at wells. This asks the reverse: what are
  the steady bright pixels? Looking at the strongest ones on aerial photos and lidar shows whether
  NISAR locks onto buildings, tanks, pumpjacks, towers or bare radar-facing slopes, with no DEP
  assumptions. The same chips of open pads let equipment be tagged by eye for a verified
  hardware set.

Inputs
  NAIP 2022-06-19, 0.6 m, Microsoft Planetary Computer (public STAC, anonymous SAS token).
  Newest NAIP over 9t; leaf-on. NAIP is NAD83 UTM 17N, within about 1 m of the WGS84 grid used here.
  Lidar RRIM 0.5 m, data/9t/derived/05/rrim_openness_9t_05.tif (2019).
  Targets: nisar/results/9t/nisar_bright_targets_points_9t_slc.gpkg (post-June, lidar-placed stack).
  Pads: nisar/results/9t/nisar_steel_pads_sites_9t_slc.gpkg.

Outputs (nisar/results/9t/figures/)
  nisar_naip_chips_targets_p<k>_9t.png   top 40 targets, ranked by tracks then brightness, 10 per page
  nisar_naip_chips_open_pads_p<k>_9t.png every open pad (canopy < 0.30), 10 per page
  nisar/results/9t/nisar_naip_chips_index_9t.csv  chip number -> target or pad id

Run
  python nisar/code/s7_analysis/_nisar_naip_chips_9t.py
"""
import json
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nisar" / "code"))
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
import _nisar_fig_style as S  # noqa: E402
from _common import path_for  # noqa: E402

RES = ROOT / "nisar" / "results" / "9t"
FIG = RES / "figures"
RRIM = path_for("derived") / "9t" / "derived" / "05" / "rrim_openness_9t_05.tif"
import _nisar_area as A  # noqa: E402
WELLS = A.WELLS
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
BBOX = "-79.5687,41.4797,-79.5139,41.5195"
HALF = 40.0   # chip half-width, m


def naip_urls():
    q = f"{STAC}?collections=naip&bbox={BBOX}&datetime=2022-06-01/2022-06-30&limit=20"
    feats = json.load(urllib.request.urlopen(q))["features"]
    tok = json.load(urllib.request.urlopen(
        "https://planetarycomputer.microsoft.com/api/sas/v1/token/naip"))["token"]
    return ["/vsicurl/" + f["assets"]["image"]["href"] + "?" + tok for f in feats]


def read(srcs, x, y):
    for s in srcs:
        b = s.bounds
        if b.left <= x - HALF and x + HALF <= b.right and b.bottom <= y - HALF and y + HALF <= b.top:
            w = from_bounds(x - HALF, y - HALF, x + HALF, y + HALF, s.transform)
            a = s.read([1, 2, 3], window=w, boundless=True)
            return np.moveaxis(a, 0, -1)
    return None


def page(items, srcs, rrim, wells, pads, stem, k):
    S.apply()
    fig, ax = plt.subplots(4, 5, figsize=(7.2, 6.4))
    for j in range(10):
        a_n, a_r = ax[(j // 5) * 2, j % 5], ax[(j // 5) * 2 + 1, j % 5]
        S.map_axes(a_n); S.map_axes(a_r)
        if j >= len(items):
            a_n.axis("off"); a_r.axis("off"); continue
        it = items[j]
        ext = (-HALF, HALF, -HALF, HALF)
        n = read(srcs, it["x"], it["y"])
        if n is not None:
            a_n.imshow(n, extent=ext)
        r = read([rrim], it["x"], it["y"])
        if r is not None:
            a_r.imshow(r, extent=ext)
        for a in (a_n, a_r):
            pc = pads.cx[it["x"] - HALF:it["x"] + HALF, it["y"] - HALF:it["y"] + HALF]
            for g in pc.geometry:
                for poly in getattr(g, "geoms", [g]):
                    xs, ys = poly.exterior.xy
                    a.plot(np.array(xs) - it["x"], np.array(ys) - it["y"], color="white", lw=0.6)
            wc = wells.cx[it["x"] - HALF:it["x"] + HALF, it["y"] - HALF:it["y"] + HALF]
            a.scatter(wc.geometry.x - it["x"], wc.geometry.y - it["y"], s=10, marker="^",
                      facecolor=S.ORANGE, edgecolor="k", lw=0.4)
            if it["mark"]:
                a.scatter([0], [0], s=40, marker="o", facecolor="none", edgecolor=S.BLUE, lw=1.0)
            a.set_xlim(-HALF, HALF); a.set_ylim(-HALF, HALF)
        a_n.text(0.03, 0.97, it["label"], transform=a_n.transAxes, va="top", fontsize=6,
                 color="k", bbox=dict(fc="white", ec="none", pad=0.6))
    fig.text(0.5, 0.005, "Top of each pair NAIP June 2022, bottom lidar RRIM 2019. 80 m chips, north up. "
             "Blue circle NISAR target, orange triangle DEP well, white line lidar pad.",
             ha="center", fontsize=6.5)
    fig.subplots_adjust(wspace=0.04, hspace=0.04, bottom=0.03)
    p = FIG / f"{stem}_p{k}_9t.png"
    S.save(fig, p)


def main():
    srcs = [rasterio.open(u) for u in naip_urls()]
    rrim = rasterio.open(RRIM)
    wells = gpd.read_file(WELLS).to_crs("EPSG:32617")
    t = gpd.read_file(RES / "nisar_bright_targets_points_9t_slc.gpkg")
    pads = gpd.read_file(RES / "nisar_steel_pads_sites_9t_slc.gpkg")
    t = t.sort_values(["n_tracks", "bright_db"], ascending=False).head(40).reset_index(drop=True)
    rows = []
    items = []
    for i, r in t.iterrows():
        items.append(dict(x=r.geometry.x, y=r.geometry.y, mark=True,
                          label=f"T{i + 1} {r.n_tracks}tr {r.bright_db:.0f}dB {r.context}"))
        rows.append(dict(set="target", chip=f"T{i + 1}", id=int(r.target_id), n_tracks=int(r.n_tracks),
                         bright_db=round(r.bright_db, 1), context=r.context, x=r.geometry.x, y=r.geometry.y))
    for k in range(4):
        page(items[k * 10:(k + 1) * 10], srcs, rrim, wells, pads, "nisar_naip_chips_targets", k + 1)

    op = pads[pads.cover_cls == "open"].reset_index()
    items = []
    for i, r in op.iterrows():
        c = r.geometry.centroid
        hit = sum(int(r[f"t{t}"]) for t in (26, 90, 162))
        items.append(dict(x=c.x, y=c.y, mark=False, label=f"P{i + 1} {r.status_cls[:6]} hit{hit}"))
        rows.append(dict(set="open_pad", chip=f"P{i + 1}", id=int(r["site"]), status=r.status_cls,
                         hit_tracks=hit, x=c.x, y=c.y))
    for k in range(int(np.ceil(len(items) / 10))):
        page(items[k * 10:(k + 1) * 10], srcs, rrim, wells, pads, "nisar_naip_chips_open_pads", k + 1)
    pd.DataFrame(rows).to_csv(RES / "nisar_naip_chips_index_9t.csv", index=False)
    print("wrote", RES / "nisar_naip_chips_index_9t.csv")


if __name__ == "__main__":
    main()
