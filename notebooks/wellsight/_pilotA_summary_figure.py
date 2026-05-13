"""Pilot A: one-page summary figure — distributions + a worked example pad."""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from shapely import wkt
from shapely.geometry import box as shp_box

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
DERIV = ROOT / "data/derivatives/pilot_A"
PADS_CSV = ROOT / "data/external/ramachandran_2024/permian_denver_data/deployment/permian_well_pads.csv"

df = pd.read_csv(DERIV / "terrain_stats_pads_vs_controls.csv")

# Pick example tile with most pads
example_tile = df[df.kind == "pad"].tile.value_counts().idxmax()
dem_path = DERIV / f"{example_tile}_dem_1m.tif"
hs_path = DERIV / f"{example_tile}_hs_1m.tif"

pads = pd.read_csv(PADS_CSV)
pads["geometry"] = pads["geometry"].map(wkt.loads)
pads_gdf = gpd.GeoDataFrame(pads, geometry="geometry", crs=4326)

with rasterio.open(hs_path) as src:
    hs = src.read(1)
    bounds = src.bounds
    crs = src.crs
pads_local = pads_gdf.to_crs(crs)
in_tile = pads_local[pads_local.intersects(shp_box(*bounds))]

# Pick the densest pad cluster center → zoom 800x800m
cx = in_tile.geometry.centroid.x.median()
cy = in_tile.geometry.centroid.y.median()
zoom = 400  # meters half-width
zx0, zx1 = cx - zoom, cx + zoom
zy0, zy1 = cy - zoom, cy + zoom

fig = plt.figure(figsize=(15, 10), dpi=120)
gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.2], hspace=0.35, wspace=0.3)

# Row 1: distribution plots
metrics = [("elev_std", "Elevation std (m)"),
           ("slope_std", "Slope std (deg)"),
           ("slope_p95", "Slope 95th pct (deg)")]
for i, (m, lbl) in enumerate(metrics):
    ax = fig.add_subplot(gs[0, i])
    a = df[df.kind == "pad"][m].dropna()
    b = df[df.kind == "control"][m].dropna()
    bins = np.linspace(0, max(a.quantile(0.98), b.quantile(0.98)), 30)
    ax.hist(b, bins=bins, alpha=0.5, color="gray", label=f"control n={len(b)}", density=True)
    ax.hist(a, bins=bins, alpha=0.6, color="red", label=f"pad n={len(a)}", density=True)
    ax.set_xlabel(lbl); ax.set_ylabel("density")
    ax.legend(fontsize=8)
    ax.set_title(lbl, fontsize=10)

# Row 2 left: full-tile hillshade with pads
ax_full = fig.add_subplot(gs[1, 0:2])
ax_full.imshow(hs, cmap="gray", vmin=0, vmax=255,
               extent=(bounds.left, bounds.right, bounds.bottom, bounds.top))
in_tile.boundary.plot(ax=ax_full, edgecolor="red", linewidth=1.0)
ax_full.add_patch(plt.Rectangle((zx0, zy0), 2*zoom, 2*zoom,
                                fill=False, edgecolor="yellow", linewidth=1.5))
ax_full.set_title(f"{example_tile}\n{len(in_tile)} pads", fontsize=9)
ax_full.set_xlabel("Easting (m)"); ax_full.set_ylabel("Northing (m)")
ax_full.set_aspect("equal")

# Row 2 right: zoomed inset
ax_zoom = fig.add_subplot(gs[1, 2])
ax_zoom.imshow(hs, cmap="gray", vmin=0, vmax=255,
               extent=(bounds.left, bounds.right, bounds.bottom, bounds.top))
in_tile.boundary.plot(ax=ax_zoom, edgecolor="red", linewidth=1.5)
in_tile.plot(ax=ax_zoom, facecolor="red", alpha=0.15)
ax_zoom.set_xlim(zx0, zx1); ax_zoom.set_ylim(zy0, zy1)
ax_zoom.set_title("Zoomed pad cluster\n(yellow box at left)", fontsize=9)
ax_zoom.set_aspect("equal")
ax_zoom.set_xlabel("Easting (m)")

fig.suptitle("Pilot A: Ramachandran well-pad polygons on USGS 3DEP LiDAR\n"
             "Pads show distinct LiDAR signature: flat interior + sharp edges (all p<0.005)",
             fontsize=12, y=0.995)
out = DERIV / "pilot_A_summary.png"
plt.savefig(out, dpi=120, bbox_inches="tight")
print(f"Saved {out}")
