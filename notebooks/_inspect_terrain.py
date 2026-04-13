"""Visual inspection: full-subarea overview + 12 zoom windows at well hotspots.

Purpose: give us something to look at with our eyes instead of iterating on
threshold numbers. If the terrain has pads, they should be visible in the
hillshade at ~200 m zoom when we center on locations where historic wells
cluster tightly.
"""
from pathlib import Path
from collections import Counter
import numpy as np
import rasterio
import geopandas as gpd
from shapely.geometry import box
import matplotlib.pyplot as plt

DATA = Path(r"C:/Users/colto/Documents/GitHub/lidar_project/data")
SUB = DATA / "derivatives" / "subarea"
HSHADE = SUB / "hillshade.tif"
SLOPE = SUB / "slope.tif"
LRM = SUB / "lrm.tif"
WELLS_PATH = DATA / "wells_with_features.shp"

SUB_BBOX = (619500.0, 4594000.0, 624500.0, 4599000.0)
TARGET_CRS = "EPSG:26917"

# Load rasters
with rasterio.open(HSHADE) as src:
    HS = src.read(1).astype("float32")
    TRANSFORM = src.transform

with rasterio.open(SLOPE) as src:
    SL = src.read(1).astype("float32")
    if src.nodata is not None:
        SL[SL == src.nodata] = np.nan

with rasterio.open(LRM) as src:
    LRMA = src.read(1).astype("float32")
    if src.nodata is not None:
        LRMA[LRMA == src.nodata] = np.nan

# Load wells in subarea
wells_all = gpd.read_file(WELLS_PATH).to_crs(TARGET_CRS)
wells_sub = wells_all[wells_all.geometry.within(box(*SUB_BBOX))].copy().reset_index(drop=True)
print(f"{len(wells_sub)} wells in subarea")

inv = ~TRANSFORM

# ───────────────────────────────────────────────────────────────────────────
# Figure A: full-subarea overview
# ───────────────────────────────────────────────────────────────────────────
print("Building overview figure...")

wells_px = np.array([inv * (p.x, p.y) for p in wells_sub.geometry])

fig, ax = plt.subplots(figsize=(14, 14))
ax.imshow(HS, cmap="gray")
ax.scatter(wells_px[:, 0], wells_px[:, 1], s=5, c="cyan",
           alpha=0.65, edgecolor="black", linewidth=0.15, label=f"{len(wells_sub)} historic wells")
ax.set_title("Calibration subarea — hillshade with historic wells (5 × 5 km)", fontsize=13)
ax.legend(loc="upper right", fontsize=10)
ax.axis("off")

# Scale bar (500 m)
bar_len_m = 500
bar_px = bar_len_m  # 1 m per px
h, w = HS.shape
ax.plot([w - 50 - bar_px, w - 50], [h - 60] * 2, color="white", linewidth=4, zorder=10)
ax.text(w - 50 - bar_px / 2, h - 80, "500 m",
        color="white", fontsize=11, ha="center", va="bottom",
        fontweight="bold", zorder=10)

plt.tight_layout()
out_a = SUB / "inspection_overview.png"
plt.savefig(out_a, dpi=110, bbox_inches="tight")
plt.close()
print(f"  Saved: {out_a}")


# ───────────────────────────────────────────────────────────────────────────
# Figure B: zoom grid at 12 well-density hotspots
# ───────────────────────────────────────────────────────────────────────────
print("Finding well hotspots...")

CELL_SIZE = 60  # meters — a coarse bin to find well clusters
N_HOTSPOTS = 12
ZOOM_SIZE_M = 200

xs = wells_sub.geometry.x.values
ys = wells_sub.geometry.y.values
cell_x = (xs // CELL_SIZE).astype(int)
cell_y = (ys // CELL_SIZE).astype(int)
cell_ids = list(zip(cell_x, cell_y))
cnt = Counter(cell_ids)

hotspots = []
for (cx, cy), c in cnt.most_common(N_HOTSPOTS):
    mask = (cell_x == cx) & (cell_y == cy)
    centroid_x = xs[mask].mean()
    centroid_y = ys[mask].mean()
    hotspots.append((c, centroid_x, centroid_y))

print(f"Top {N_HOTSPOTS} hotspots by well count in a {CELL_SIZE} m grid cell:")
for c, x, y in hotspots:
    print(f"  {c} wells at ({x:.0f}, {y:.0f})")

print("\nBuilding zoom figure...")

ncols = 4
nrows = int(np.ceil(N_HOTSPOTS / ncols))
fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 5 * nrows))
axes_flat = axes.flat

for i, ax in enumerate(axes_flat):
    if i >= N_HOTSPOTS:
        ax.axis("off")
        continue
    n_wells, cx_map, cy_map = hotspots[i]

    # Zoom window bounds (map coords)
    half = ZOOM_SIZE_M / 2
    minx = cx_map - half
    maxx = cx_map + half
    miny = cy_map - half
    maxy = cy_map + half

    # Convert to pixel slices
    col_tl, row_tl = inv * (minx, maxy)
    col_br, row_br = inv * (maxx, miny)
    r0 = int(max(0, np.floor(row_tl)))
    r1 = int(min(HS.shape[0], np.ceil(row_br)))
    c0 = int(max(0, np.floor(col_tl)))
    c1 = int(min(HS.shape[1], np.ceil(col_br)))
    if r1 <= r0 or c1 <= c0:
        ax.axis("off"); continue

    # Hillshade base
    hs_crop = HS[r0:r1, c0:c1]
    ax.imshow(hs_crop, cmap="gray")

    # LRM overlay — this is the "flat vs offset" signal, coolwarm diverging
    lrm_crop = LRMA[r0:r1, c0:c1]
    ax.imshow(lrm_crop, cmap="coolwarm_r", vmin=-1.0, vmax=1.0, alpha=0.35)

    # Wells inside the window
    window_poly = box(minx, miny, maxx, maxy)
    wells_in = wells_sub[wells_sub.geometry.within(window_poly)]
    if len(wells_in) > 0:
        wpx = np.array([inv * (p.x, p.y) for p in wells_in.geometry])
        wpx[:, 0] -= c0
        wpx[:, 1] -= r0
        ax.scatter(wpx[:, 0], wpx[:, 1], s=80, c="cyan",
                   edgecolor="black", linewidth=1.0, zorder=5)

    # Scale bar (50 m)
    ax.plot([10, 60], [hs_crop.shape[0] - 15] * 2,
            color="white", linewidth=4, zorder=6)
    ax.text(35, hs_crop.shape[0] - 20, "50 m",
            color="white", fontsize=10, ha="center", va="bottom",
            zorder=6, fontweight="bold")

    ax.set_title(
        f"#{i+1}  {n_wells} wells in {CELL_SIZE} m cell  /  {len(wells_in)} in view\n"
        f"center ≈ ({cx_map:.0f}, {cy_map:.0f})",
        fontsize=10,
    )
    ax.set_xticks([]); ax.set_yticks([])

plt.suptitle(
    "Terrain inspection — 200 × 200 m zoom at top-12 well density hotspots\n"
    "Hillshade (gray) + LRM overlay (blue = below local mean, red = above) + wells (cyan)",
    fontsize=13, y=0.995,
)
plt.tight_layout()
out_b = SUB / "inspection_zooms.png"
plt.savefig(out_b, dpi=120, bbox_inches="tight")
plt.close()
print(f"  Saved: {out_b}")
