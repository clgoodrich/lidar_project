"""Before-and-after evidence sheets for the 2006-2008 to 2019 lidar change patches on 9t.

One row per patch, five panels. Left to right: 2003-2006 statewide aerial photo, 2020 leaf-off aerial photo, 2006-2008 hillshade,
2019 hillshade, change (2019 minus 2006-2008, high-passed). The patch outline is drawn on every panel.
The point is to tell WHAT changed, since the DoD alone only says where.

Sources
  patches   data/_experiments/icp/change_9t/change_patches_9t_singleicp.gpkg (240 patches, EPSG:6346)
  DEMs      2006-2008 single-ICP DEM (2 m) and 2019 dem_9t_05.tif resampled to 2 m
  photo A   PASDA Aerials0306StateWide (PAMAP 2003-2006 statewide aerial). Flight date at the patch not yet confirmed.
  photo B   PASDA PEMAImagery2018 layer 242 (Venango mosaic 2020), layer 110 (Forest mosaic 2020) where Venango is blank.

Run:
  python notebooks/wellsight_v2/s7_analysis/_change_evidence_sheets_9t.py anthropogenic
  python notebooks/wellsight_v2/s7_analysis/_change_evidence_sheets_9t.py mass_wasting
  python notebooks/wellsight_v2/s7_analysis/_change_evidence_sheets_9t.py ids 267 836 899
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import rasterio
import requests
from matplotlib import pyplot as plt
from PIL import Image
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[3]
ICP = ROOT / "data/_experiments/icp/change_9t"
OUT = ROOT / "data/9t/results/change/sheets"
PER_SHEET = 5
SVC_OLD = "https://services.pasda.psu.edu/server/rest/services/pasda/Aerials0306StateWide/MapServer/export"
SVC_NEW = "https://services.pasda.psu.edu/server/rest/services/pasda/PEMAImagery2018/MapServer/export"


def hillshade(z, res, az=315.0, alt=40.0):
    gy, gx = np.gradient(z, res)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(gy, -gx)
    a, h = np.radians(360 - az + 90), np.radians(alt)
    hs = np.sin(h) * np.cos(slope) + np.cos(h) * np.sin(slope) * np.cos(a - aspect)
    return np.clip(hs, 0, 1)


def read(path, b, res=2.0, resample=Resampling.average):
    n = int(round((b[2] - b[0]) / res))
    with rasterio.open(path) as s:
        w = from_bounds(*b, transform=s.transform)
        a = s.read(1, window=w, out_shape=(n, n), boundless=True, fill_value=np.nan, resampling=resample).astype(float)
        nd = s.nodata
    if nd is not None and not np.isnan(nd):
        a[a == nd] = np.nan
    return a


def photo(url, b, layers=None, size=420):
    p = dict(bbox=",".join(f"{v:.2f}" for v in b), bboxSR=6346, imageSR=6346, size=f"{size},{size}", format="png", f="image")
    if layers:
        p["layers"] = layers
    r = requests.get(url, params=p, timeout=90)
    return np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"))


def photo_new(b):
    for lay in ("show:242", "show:110"):
        a = photo(SVC_NEW, b, lay)
        if a.mean() < 240:
            return a
    return a


def draw(ax, g, b, col="white"):
    for p in getattr(g, "geoms", [g]):
        x, y = p.exterior.xy
        ax.plot(np.array(x), np.array(y), color=col, lw=1.1)
    ax.set_xlim(b[0], b[2])
    ax.set_ylim(b[1], b[3])
    ax.set_xticks([])
    ax.set_yticks([])


# PATCHSET=v2_z (default singleicp) reads the patches, change field and both DEMs of the 2026-11-03 rebuild (_change_rebuild_v2_9t.py).
import os
PATCHSET = os.environ.get("PATCHSET", "singleicp")


def main(args):
    g = gpd.read_file(ICP / f"change_patches_9t_{PATCHSET}.gpkg")
    sel = args[0] if args else "anthropogenic"
    if sel == "ids":
        g = g[g.patch_id.isin([int(v) for v in args[1:]])]
    elif sel == "fluvial_top":
        g = g[g.cls == "fluvial"].sort_values("abs_volume_m3", ascending=False).head(int(args[1]) if len(args) > 1 else 10)
    else:
        g = g[g.cls == sel].sort_values("abs_volume_m3", ascending=False)
    OUT.mkdir(parents=True, exist_ok=True)
    hp = ICP / "dod_9t_singleicp_highpass_2m.tif"
    old, new = ICP / "dem_2006_singleicp_9t_2m.tif", ROOT / "data/9t/derived/05/dem_9t_05.tif"
    if PATCHSET == "v2_z":
        V2 = ROOT / "data/9t/derived/lidar_2006_2008"
        hp, old, new = V2 / "dod_v2_highpass_9t_2m.tif", V2 / "dem_2006_v2_9t_2m.tif", V2 / "dem_2019_v2_9t_2m.tif"
    rows = list(g.itertuples())
    for k in range(0, len(rows), PER_SHEET):
        chunk = rows[k:k + PER_SHEET]
        fig, axes = plt.subplots(len(chunk), 5, figsize=(15, 3.1 * len(chunk)), squeeze=False)
        for i, r in enumerate(chunk):
            c = r.geometry.centroid
            x0, y0, x1, y1 = r.geometry.bounds
            half = float(np.clip(max(x1 - x0, y1 - y0) * 0.9 + 25, 55, 130))
            b = (c.x - half, c.y - half, c.x + half, c.y + half)
            zo, zn = read(old, b), read(new, b)
            d = read(hp, b)
            panels = [(photo(SVC_OLD, b), None), (photo_new(b), None),
                      (hillshade(np.nan_to_num(zo, nan=np.nanmean(zo)), 2.0), "gray"), (hillshade(np.nan_to_num(zn, nan=np.nanmean(zn)), 2.0), "gray"), (d, "d")]
            titles = ["2003-06 aerial", "2020 aerial", "2006-08 hillshade", "2019 hillshade", "change (blue cut, orange fill)"]
            for j, (a, kind) in enumerate(panels):
                ax = axes[i, j]
                if kind is None:
                    ax.imshow(a, extent=(b[0], b[2], b[1], b[3]))
                elif kind == "gray":
                    ax.imshow(a, cmap="gray", vmin=0, vmax=1, extent=(b[0], b[2], b[1], b[3]), origin="upper")
                else:
                    ax.imshow(a, cmap="PuOr_r", vmin=-1.0, vmax=1.0, extent=(b[0], b[2], b[1], b[3]), origin="upper")
                draw(ax, r.geometry, b, "white" if kind != "d" else "#2B2F36")
                if i == 0:
                    ax.set_title(titles[j], fontsize=10)
            axes[i, 0].set_ylabel(f"#{r.patch_id}  {r.cls}\n{r.sign} {r.mean_dz_m:+.2f} m\n{r.area_m2:,.0f} m2\nslope {r.slope_deg:.0f} deg\nchan {r.chan_dist_m:.0f} m\nroad {r.road_dist_m:.0f} m",
                                  rotation=0, ha="right", va="center", fontsize=8.5, labelpad=8)
        fig.tight_layout()
        f = OUT / f"change_evidence_sheet_{sel}_{k // PER_SHEET + 1}_9t{'_v2z' if PATCHSET == 'v2_z' else ''}.png"
        fig.savefig(f, dpi=100)
        plt.close(fig)
        print(f)


if __name__ == "__main__":
    main(sys.argv[1:])
