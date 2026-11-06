"""Site map of tile 9t for the CIVE 6359 checkpoint deck.

Inputs
    data/9t/derived/1m/hillshade_9t_1m.tif   lidar hillshade, EPSG:6346 (base map)
    qgis/annotations/pad.shp, pit_full.shp  project annotations (pads and pit exteriors)
Output
    nisar_writeup/figures/nisar_site_map_9t.png
Run
    python nisar_writeup/_make_checkpoint_map.py

Palette. Pads #1F5FA8 and pits #D97706 are the project's validated lost/found pair (CLAUDE.md colourblind rule,
worst pair dE 21.1 deutan, all-pairs check). Pads are outlines and pits are filled, so shape also separates them.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.patches import FancyArrow, Patch, Rectangle  # noqa: E402
from pyproj import Transformer  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from shapely.geometry import box  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HS = ROOT / "data/9t/derived/1m/hillshade_9t_1m.tif"
OUT = ROOT / "nisar_writeup/figures/nisar_site_map_9t.png"
PAD, PIT = "#1F5FA8", "#D97706"


def main() -> None:
    with rasterio.open(HS) as r:
        f = 4
        hs = r.read(1, out_shape=(r.height // f, r.width // f), resampling=Resampling.average).astype(float)
        b, crs = r.bounds, r.crs
        if r.nodata is not None:
            hs[hs == r.nodata] = np.nan
    tile = box(b.left, b.bottom, b.right, b.top)
    pads = gpd.read_file(ROOT / "qgis/annotations/pad.shp").to_crs(crs)
    pits = gpd.read_file(ROOT / "qgis/annotations/pit_full.shp").to_crs(crs)
    pads, pits = pads[pads.intersects(tile)], pits[pits.intersects(tile)]

    fig, ax = plt.subplots(figsize=(7.2, 4.5), dpi=250)
    ax.imshow(hs, cmap="gray", extent=(b.left, b.right, b.bottom, b.top), vmin=np.nanpercentile(hs, 1),
              vmax=np.nanpercentile(hs, 99))
    pads.boundary.plot(ax=ax, color=PAD, linewidth=0.8)
    pits.plot(ax=ax, color=PIT, edgecolor=PIT, linewidth=0.4)
    ax.add_patch(Rectangle((b.left, b.bottom), b.right - b.left, b.top - b.bottom, fill=False, ec="black", lw=1.6))
    ax.set_xlim(b.left - 150, b.right + 2900)
    ax.set_ylim(b.bottom - 100, b.top + 100)
    ax.set_axis_off()

    # scale bar 1 km and north arrow (grid north, UTM 17N, convergence under 1 degree here)
    x0, y0 = b.right + 300, b.bottom + 250
    ax.add_patch(Rectangle((x0, y0), 500, 70, fc="black", ec="black"))
    ax.add_patch(Rectangle((x0 + 500, y0), 500, 70, fc="white", ec="black"))
    for x, t in ((x0, "0"), (x0 + 1000, "1 km")):
        ax.text(x, y0 + 140, t, ha="center", va="bottom", fontsize=11)
    ax.add_patch(FancyArrow(b.right + 800, b.top - 900, 0, 550, width=90, head_width=260, head_length=260,
                            length_includes_head=True, fc="black", ec="black"))
    ax.text(b.right + 800, b.top - 1050, "N", ha="center", va="top", fontsize=15, weight="bold")

    lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform((b.left + b.right) / 2,
                                                                                (b.top + b.bottom) / 2)
    ax.legend(handles=[Patch(fc="none", ec=PAD, lw=1.2, label=f"Well pad ({len(pads)})"),
                       Patch(fc=PIT, ec=PIT, label=f"Pit ({len(pits)})"),
                       Patch(fc="none", ec="black", lw=1.6, label="Tile 9t, 4.5 km x 4.5 km")],
              loc="center left", bbox_to_anchor=(0.66, 0.55), fontsize=10.5, frameon=False)
    ax.text(b.right + 150, b.bottom + 900, f"Venango County, PA\n{lat:.3f} N, {abs(lon):.3f} W", fontsize=11,
            va="bottom")
    fig.text(0.01, 0.01, "Base map: hillshade of 2019 USGS 3DEP QL2 lidar (1 m DEM). Pads and pits: project "
             "annotations. EPSG:6346.", fontsize=8, color="#444444")
    fig.subplots_adjust(0, 0.04, 1, 1)
    fig.savefig(OUT, dpi=250)
    print(OUT, len(pads), len(pits), f"{lat:.4f} {lon:.4f}")


if __name__ == "__main__":
    main()
