"""Standalone runner for the zoom-in visualization cell."""
from pathlib import Path
import numpy as np
import rasterio
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import box

DATA = Path(r"C:/Users/colto/Documents/GitHub/lidar_project/data")
SUB = DATA / "derivatives" / "subarea"
SUB_DEM = SUB / "dem.tif"
SLOPE = SUB / "slope.tif"
HSHADE = SUB / "hillshade.tif"
WELLS_PATH = DATA / "wells_with_features.shp"
GPKG = SUB / "features_A_pads.gpkg"

SUB_BBOX = (619500.0, 4594000.0, 624500.0, 4599000.0)
TARGET_CRS = "EPSG:26917"

with rasterio.open(SUB_DEM) as src:
    TRANSFORM = src.transform
    CRS = src.crs

pads = gpd.read_file(GPKG, layer="pads")
wells_all = gpd.read_file(WELLS_PATH).to_crs(TARGET_CRS)
wells_sub = wells_all[wells_all.geometry.within(box(*SUB_BBOX))].copy()
print(f"{len(pads)} candidates, {len(wells_sub)} wells in subarea")

N_TO_SHOW = 9
BUFFER_M = 50

top = pads.sort_values("area_m2", ascending=False).head(N_TO_SHOW).reset_index(drop=True)

with rasterio.open(HSHADE) as src:
    hs_full = src.read(1).astype("float32")
with rasterio.open(SLOPE) as src:
    slope_full = src.read(1).astype("float32")
    slope_nd = src.nodata
if slope_nd is not None:
    slope_full[slope_full == slope_nd] = np.nan

ncols = 3
nrows = int(np.ceil(N_TO_SHOW / ncols))
fig, axes = plt.subplots(nrows, ncols, figsize=(5.2 * ncols, 5.2 * nrows))
axes_flat = axes.flat if hasattr(axes, "flat") else [axes]

inv = ~TRANSFORM

for i, ax in enumerate(axes_flat):
    if i >= len(top):
        ax.axis("off")
        continue
    row = top.iloc[i]
    geom = row.geometry
    if geom is None or geom.is_empty:
        ax.axis("off")
        continue

    minx, miny, maxx, maxy = geom.bounds
    minx -= BUFFER_M; maxx += BUFFER_M
    miny -= BUFFER_M; maxy += BUFFER_M

    col_tl, row_tl = inv * (minx, maxy)
    col_br, row_br = inv * (maxx, miny)
    r0 = int(max(0, np.floor(row_tl)))
    r1 = int(min(hs_full.shape[0], np.ceil(row_br)))
    c0 = int(max(0, np.floor(col_tl)))
    c1 = int(min(hs_full.shape[1], np.ceil(col_br)))
    if r1 <= r0 or c1 <= c0:
        ax.axis("off"); continue

    hs_crop = hs_full[r0:r1, c0:c1]
    ax.imshow(hs_crop, cmap="gray")

    sl_crop = slope_full[r0:r1, c0:c1]
    ax.imshow(sl_crop, cmap="cividis", alpha=0.35, vmin=0, vmax=20)

    xs, ys = geom.exterior.xy
    poly_px = np.array([inv * (x, y) for x, y in zip(xs, ys)])
    poly_px[:, 0] -= c0
    poly_px[:, 1] -= r0
    ax.plot(poly_px[:, 0], poly_px[:, 1], color="orange", linewidth=2.0, zorder=4)
    ax.fill(poly_px[:, 0], poly_px[:, 1], color="orange", alpha=0.15, zorder=3)

    window_poly = box(minx, miny, maxx, maxy)
    wells_in = wells_sub[wells_sub.geometry.within(window_poly)]
    if len(wells_in) > 0:
        wpx = np.array([inv * (p.x, p.y) for p in wells_in.geometry])
        wpx[:, 0] -= c0
        wpx[:, 1] -= r0
        ax.scatter(wpx[:, 0], wpx[:, 1], s=45, c="cyan",
                   edgecolor="black", linewidth=0.7, zorder=5)

    ax.plot([5, 25], [hs_crop.shape[0] - 10] * 2,
            color="white", linewidth=3, zorder=6)
    ax.text(15, hs_crop.shape[0] - 14, "20 m",
            color="white", fontsize=8, ha="center", va="bottom",
            zorder=6, fontweight="bold")

    ax.set_title(
        f"#{i+1}  area={row.area_m2:.0f} m\u00b2  compact={row.compactness:.2f}\n"
        f"slope={row.slope:.1f}\u00b0  surr_slope={row.surr_slope:.1f}\u00b0  "
        f"relief={row.local_relief:.2f} m  {len(wells_in)} wells",
        fontsize=9,
    )
    ax.set_xticks([]); ax.set_yticks([])

plt.suptitle(
    f"Top {min(N_TO_SHOW, len(top))} pad candidates by area - hillshade + slope overlay",
    fontsize=12, y=0.995,
)
plt.tight_layout()
out = SUB / "zoom_preview.png"
plt.savefig(out, dpi=120, bbox_inches="tight")
plt.close()
print(f"Saved: {out}")
