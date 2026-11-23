"""Real imagery for the slides: lidar beside NISAR, whole tile and close-ups (9t). Made 2026-11-23.

Why: the deck needed actual images, not only charts. Lidar shows what the features are. The NISAR
panels show what the radar sees at the same place. Descending and ascending panels side by side show
why two viewing directions matter: a slope bright from one side is dark from the other.

Inputs (post-June dates only; the seasonal script writes these summer means from 2026-06-01 to 09-30)
  nisar/derived/9t/nisar_slc_lidar_5m/nisar_{hh,hv}_summer_2026_track{026,162}_9t_slc_5m.tif  (dB, EPSG:32617)
  data/9t/derived/1m/hillshade_9t_1m.tif, data/9t/derived/05/rrim_openness_9t_05.tif  (EPSG:6346)
  qgis/annotations/pad.shp, pit_full.shp
Writes nisar/docs/figures/
  nisar_tile_lidar_radar_9t.png     lidar hillshade beside NISAR summer HV, whole tile
  nisar_site_views_<site>_9t.png    lidar RRIM, NISAR descending, NISAR ascending, one site
Run
  python nisar/code/s7_analysis/_nisar_slide_imagery.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nisar" / "code"))
import _nisar_fig_style as S  # noqa: E402
S.apply()

OUT = ROOT / "nisar" / "docs" / "figures"
STK = ROOT / "nisar" / "derived" / "9t" / "nisar_slc_lidar_5m"
HILL = ROOT / "data" / "9t" / "derived" / "1m" / "hillshade_9t_1m.tif"
RRIM = ROOT / "data" / "9t" / "derived" / "05" / "rrim_openness_9t_05.tif"
ANN = ROOT / "qgis" / "annotations"
to_radar = Transformer.from_crs(6346, 32617, always_xy=True)
to_lidar = Transformer.from_crs(4326, 6346, always_xy=True)
SITES = {"pad303": (41.502850, -79.551054, 150), "point5": (41.502787, -79.519712, 120),
         "pit295": (41.498405, -79.518304, 150)}


def radar(name, b):
    """Window of a NISAR dB raster for lidar-CRS bounds b, with its extent in lidar coordinates."""
    x0, y0 = to_radar.transform(b[0], b[1])
    x1, y1 = to_radar.transform(b[2], b[3])
    with rasterio.open(STK / name) as r:
        w = from_bounds(x0, y0, x1, y1, r.transform)
        a = r.read(1, window=w, boundless=True, fill_value=np.nan)
    return a


def outlines(ax, b, lw=0.9):
    for f, col in (("pad.shp", S.K), ("pit_full.shp", S.BLUE)):
        g = gpd.read_file(ANN / f).to_crs(6346).cx[b[0]:b[2], b[1]:b[3]]
        if len(g):
            g.boundary.plot(ax=ax, color=col, lw=lw)


def tile():
    with rasterio.open(HILL) as r:
        h = r.read(1, out_shape=(r.height // 4, r.width // 4), resampling=Resampling.average).astype(float)
        b = r.bounds
    rv = radar("nisar_hv_summer_2026_track162_9t_slc_5m.tif", b)
    ext = (b.left, b.right, b.bottom, b.top)
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.5))
    ax[0].imshow(h, cmap="gray", extent=ext, vmin=np.nanpercentile(h, 2), vmax=np.nanpercentile(h, 98))
    lo, hi = np.nanpercentile(rv, [2, 98])
    ax[1].imshow(rv, cmap="gray", extent=ext, vmin=lo, vmax=hi, interpolation="nearest")
    S.panel(ax[0], "a", "Lidar bare-earth hillshade, 1 m")
    S.panel(ax[1], "b", "NISAR HV, summer 2026 mean, 5 m")
    for a in ax:
        S.map_axes(a)
        a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
    L = 1000
    ax[0].plot([ext[0] + 200, ext[0] + 200 + L], [ext[2] + 200] * 2, color="white", lw=2.5)
    ax[0].text(ext[0] + 200 + L / 2, ext[2] + 280, "1 km", color="white", ha="center", fontsize=8)
    S.save(fig, OUT / "nisar_tile_lidar_radar_9t.png")


def site(name):
    lat, lon, H = SITES[name]
    x, y = to_lidar.transform(lon, lat)
    b = (x - H, y - H, x + H, y + H)
    ext = (b[0], b[2], b[1], b[3])
    with rasterio.open(RRIM) as r:
        w = from_bounds(*b, r.transform)
        rgb = np.moveaxis(r.read([1, 2, 3], window=w, boundless=True, fill_value=0), 0, -1)
    d = radar("nisar_hh_summer_2026_track026_9t_slc_5m.tif", b)
    a = radar("nisar_hh_summer_2026_track162_9t_slc_5m.tif", b)
    lo, hi = np.nanpercentile(np.r_[d.ravel(), a.ravel()], [2, 98])
    fig, ax = plt.subplots(1, 3, figsize=(9.6, 3.4))
    ax[0].imshow(rgb, extent=ext)
    ax[1].imshow(d, cmap="gray", extent=ext, vmin=lo, vmax=hi, interpolation="nearest")
    im = ax[2].imshow(a, cmap="gray", extent=ext, vmin=lo, vmax=hi, interpolation="nearest")
    S.panel(ax[0], "a", "Lidar relief image, 0.5 m")
    S.panel(ax[1], "b", "NISAR HH, track 26 descending")
    S.panel(ax[2], "c", "NISAR HH, track 162 ascending")
    for k in ax:
        outlines(k, b)
        S.map_axes(k)
        k.set_xlim(ext[0], ext[1]); k.set_ylim(ext[2], ext[3])
    L = 50
    ax[0].plot([b[0] + 0.08 * 2 * H, b[0] + 0.08 * 2 * H + L], [b[1] + 0.08 * 2 * H] * 2, color="white", lw=2.5)
    ax[0].text(b[0] + 0.08 * 2 * H + L / 2, b[1] + 0.12 * 2 * H, "50 m", color="white", ha="center", fontsize=8)
    fig.colorbar(im, ax=list(ax), fraction=0.015, pad=0.01).set_label("Summer 2026 mean (dB)")
    S.save(fig, OUT / f"nisar_site_views_{name}_9t.png")


if __name__ == "__main__":
    tile()
    for s in SITES:
        site(s)
