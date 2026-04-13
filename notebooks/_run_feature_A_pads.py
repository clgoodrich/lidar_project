"""
Feature Type A — Pad Scars detector (first draft).

Per CLAUDE.md: compact patches of low slope + low roughness + low local relief,
embedded within steeper surrounding terrain, at mid-slope HAND values. Cut-and-
fill geometry shows asymmetric TPI dipole (uphill negative, downhill positive).

Strategy:
  1. Candidate cells: slope < 5°  AND  local_relief < p25_local  AND  roughness < p25_local
  2. HAND filter: 1–50 m (exclude immediate stream cells and very-high ridges)
  3. Surrounding-terrain contrast: mean slope in a 20–50 m annulus > 10°
  4. Connected components, filter by area (100–5000 m²) and compactness
  5. Rank by contrast with surroundings
  6. Polygon output with attributes → GeoPackage

A key innovation for this subarea (which is mostly open agricultural land):
the detector REQUIRES the surrounding terrain to be non-flat. That rejects
agricultural fields (which are flat in a flat valley) and keeps engineered
flat patches (pads) that sit in contrast to steeper surroundings.
"""
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes as rio_shapes
from scipy import ndimage as ndi
from skimage.morphology import (
    remove_small_objects, closing, opening, disk,
)
from skimage.measure import label, regionprops

import geopandas as gpd
from shapely.geometry import shape

SUB = Path(r"C:/Users/colto/Documents/GitHub/lidar_project/data/derivatives/subarea")
OUT_GPKG = SUB / "features_A_pads.gpkg"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ───────────────────────────────────────────────────────────────────────────
# Load derivatives
# ───────────────────────────────────────────────────────────────────────────
log("Loading derivatives...")
def _load(path):
    with rasterio.open(path) as s:
        d = s.read(1).astype("float32")
        nd = s.nodata
        prof = s.profile.copy()
        t = s.transform
        crs = s.crs
    if nd is not None:
        d[d == nd] = np.nan
    return d, prof, t, crs


SLOPE, PROF, TRANSFORM, CRS = _load(SUB / "slope.tif")
ROUGHNESS, *_ = _load(SUB / "roughness.tif")
LOCAL_RELIEF, *_ = _load(SUB / "local_relief.tif")
HAND, *_ = _load(SUB / "hand.tif")
TPI15, *_ = _load(SUB / "tpi_15m.tif")
PLANC, *_ = _load(SUB / "plan_curvature.tif")

with rasterio.open(SUB / "point_density_mask.tif") as s:
    QMASK = s.read(1)

log(f"Arrays: {SLOPE.shape}")


# ───────────────────────────────────────────────────────────────────────────
# Step 1 — Flat-patch seeds
# ───────────────────────────────────────────────────────────────────────────
log("Building seed mask (slope<5 & roughness<1 & relief<1.5 & quality & HAND 1-50)...")

# Absolute thresholds
SLOPE_THRESH   = 5.0      # degrees
ROUGH_THRESH   = 1.0      # the roughness stats earlier showed p25=0.9, p50=1.5
RELIEF_THRESH  = 1.5      # meters — stats showed p25=0.85, p50=1.35
HAND_MIN       = 1.0
HAND_MAX       = 60.0

seed = (
    (SLOPE < SLOPE_THRESH) &
    (ROUGHNESS < ROUGH_THRESH) &
    (LOCAL_RELIEF < RELIEF_THRESH) &
    (HAND >= HAND_MIN) &
    (HAND <= HAND_MAX) &
    (QMASK == 1)
)
seed &= ~np.isnan(SLOPE) & ~np.isnan(HAND) & ~np.isnan(ROUGHNESS)

log(f"Seed cells: {seed.sum():,} ({seed.mean()*100:.2f}%)")


# ───────────────────────────────────────────────────────────────────────────
# Step 2 — Surrounding-terrain contrast (reject flat fields)
# ───────────────────────────────────────────────────────────────────────────
log("Computing surrounding-terrain slope in 40 m annulus...")

# We want: for each cell, the mean slope in a RING from ~10 m to ~40 m away.
# Compute inner and outer uniform-filter means, subtract.
# (uniform_filter * radius² = sum, so difference of sums = annulus sum.)
slope_filled = np.where(np.isnan(SLOPE), 0.0, SLOPE).astype("float32")
mask_filled = (~np.isnan(SLOPE)).astype("float32")

def _ring_mean(arr, mask_arr, inner_radius, outer_radius):
    """Mean of `arr` inside an annulus [inner_radius, outer_radius] around each
    cell, computed as difference of two square uniform filters. Cheap and good
    enough for a bulk contrast signal."""
    # Use square windows of side 2r+1 (approximation of a disk, fine at this scale)
    outer = ndi.uniform_filter(arr, size=2 * outer_radius + 1, mode="reflect")
    outer_n = ndi.uniform_filter(mask_arr, size=2 * outer_radius + 1, mode="reflect")
    inner = ndi.uniform_filter(arr, size=2 * inner_radius + 1, mode="reflect")
    inner_n = ndi.uniform_filter(mask_arr, size=2 * inner_radius + 1, mode="reflect")
    # Difference: (outer_sum - inner_sum) / (outer_n - inner_n)
    num = outer * (2 * outer_radius + 1) ** 2 - inner * (2 * inner_radius + 1) ** 2
    den = outer_n * (2 * outer_radius + 1) ** 2 - inner_n * (2 * inner_radius + 1) ** 2
    result = np.where(den > 0, num / np.maximum(den, 1e-6), 0.0)
    return result.astype("float32")


surrounding_slope = _ring_mean(slope_filled, mask_filled, inner_radius=10, outer_radius=40)

CONTRAST_THRESH = 7.0  # degrees — the surrounding terrain must average >7° slope
seed_contrast = seed & (surrounding_slope > CONTRAST_THRESH)
log(f"After contrast filter (surrounding slope > {CONTRAST_THRESH}°): {seed_contrast.sum():,}")


# ───────────────────────────────────────────────────────────────────────────
# Step 3 — Morphological cleanup
# ───────────────────────────────────────────────────────────────────────────
log("Morphological cleanup...")
cleaned = closing(seed_contrast, disk(2))
cleaned = opening(cleaned, disk(1))
cleaned = remove_small_objects(cleaned, min_size=60)
log(f"After cleanup: {cleaned.sum():,}")


# ───────────────────────────────────────────────────────────────────────────
# Step 4 — Component filter by area and compactness
# ───────────────────────────────────────────────────────────────────────────
log("Labeling and filtering components...")

MIN_AREA = 100    # m² — smaller than smallest cable-tool pad (8×8 = 64 m²; give headroom)
MAX_AREA = 5000   # m² — larger than mid-20th-century rotary pad (20×30 = 600 m²)
MAX_ELONG = 4.0   # reject very-elongated patches (they're probably road beds, not pads)

labels = label(cleaned, connectivity=2)
n_comp = labels.max()
log(f"  components: {n_comp}")

kept = []
for region in regionprops(labels, intensity_image=SLOPE):
    if not (MIN_AREA <= region.area <= MAX_AREA):
        continue
    if region.axis_minor_length > 0:
        elong = region.axis_major_length / region.axis_minor_length
    else:
        elong = float("inf")
    if elong > MAX_ELONG:
        continue
    # Compactness = (4π * area) / perimeter²  — 1 for circle, lower for elongated
    if region.perimeter > 0:
        compactness = (4 * np.pi * region.area) / (region.perimeter ** 2)
    else:
        compactness = 0
    if compactness < 0.15:
        continue
    kept.append(region)

log(f"  kept {len(kept)} / {n_comp}")


# ───────────────────────────────────────────────────────────────────────────
# Step 5 — Vectorize + attribute + write
# ───────────────────────────────────────────────────────────────────────────
log("Building polygon layer...")

keep_mask = np.zeros_like(labels, dtype=bool)
for region in kept:
    keep_mask[labels == region.label] = True

shapes_gen = rio_shapes(
    keep_mask.astype("uint8"),
    mask=keep_mask,
    transform=TRANSFORM,
    connectivity=8,
)

records = []
for geom_json, _ in shapes_gen:
    geom = shape(geom_json)
    if not geom.is_valid or geom.area < MIN_AREA:
        continue
    # Sample derivatives at centroid
    cx, cy = geom.centroid.x, geom.centroid.y
    inv = ~TRANSFORM
    px, py = inv * (cx, cy)
    py = int(round(py))
    px = int(round(px))
    if not (0 <= py < SLOPE.shape[0] and 0 <= px < SLOPE.shape[1]):
        continue
    # Compactness
    perim = geom.length
    compact = (4 * np.pi * geom.area) / (perim ** 2) if perim > 0 else 0
    records.append({
        "geometry":       geom,
        "area_m2":        float(geom.area),
        "perimeter_m":    float(perim),
        "compactness":    float(compact),
        "slope":          float(SLOPE[py, px]) if np.isfinite(SLOPE[py, px]) else None,
        "roughness":      float(ROUGHNESS[py, px]) if np.isfinite(ROUGHNESS[py, px]) else None,
        "local_relief":   float(LOCAL_RELIEF[py, px]) if np.isfinite(LOCAL_RELIEF[py, px]) else None,
        "hand":           float(HAND[py, px]) if np.isfinite(HAND[py, px]) else None,
        "tpi15":          float(TPI15[py, px]) if np.isfinite(TPI15[py, px]) else None,
        "surr_slope":     float(surrounding_slope[py, px]),
    })

if records:
    gdf = gpd.GeoDataFrame(records, crs=CRS)
    gdf.to_file(OUT_GPKG, layer="pads", driver="GPKG")
    log(f"Wrote {len(gdf)} pad candidates to {OUT_GPKG}")
    log(f"  area_m2:     p50={gdf['area_m2'].median():.0f}, p95={gdf['area_m2'].quantile(0.95):.0f}")
    log(f"  compactness: p50={gdf['compactness'].median():.2f}, p95={gdf['compactness'].quantile(0.95):.2f}")
    log(f"  surr_slope:  p50={gdf['surr_slope'].median():.1f}°")
else:
    log("No candidates passed filters")


# ───────────────────────────────────────────────────────────────────────────
# Visualization
# ───────────────────────────────────────────────────────────────────────────
log("Rendering detector visualization...")
import matplotlib.pyplot as plt

with rasterio.open(SUB / "hillshade.tif") as s:
    hs = s.read(1).astype("float32")

fig, axes = plt.subplots(1, 3, figsize=(21, 7))

ax = axes[0]
ax.imshow(hs, cmap="gray")
ax.imshow(surrounding_slope, cmap="cividis", vmin=0, vmax=20, alpha=0.55)
ax.set_title("Surrounding slope (40 m ring mean)")
ax.axis("off")

ax = axes[1]
ax.imshow(hs, cmap="gray")
ov = np.where(seed_contrast, 1, np.nan)
ax.imshow(ov, cmap="autumn", alpha=0.9)
ax.set_title(f"Seed cells (flat + contrasting surrounds) — {seed_contrast.sum():,}")
ax.axis("off")

ax = axes[2]
ax.imshow(hs, cmap="gray")
ov2 = np.where(keep_mask, 1, np.nan)
ax.imshow(ov2, cmap="autumn", alpha=0.9)

# Overlay wells
import geopandas as gpd
from shapely.geometry import box as shp_box
wells_all = gpd.read_file(Path(r"C:/Users/colto/Documents/GitHub/lidar_project/data/wells_with_features.shp")).to_crs(CRS)
SUB_BBOX = (619500.0, 4594000.0, 624500.0, 4599000.0)
wells_sub = wells_all[wells_all.geometry.within(shp_box(*SUB_BBOX))].copy()
# Convert wells to image coordinates
inv = ~TRANSFORM
wells_px = np.array([inv * (p.x, p.y) for p in wells_sub.geometry])
ax.scatter(wells_px[:, 0], wells_px[:, 1], s=2, c="cyan", alpha=0.5, label=f"{len(wells_sub)} wells")
ax.set_title(f"Kept pad candidates — {len(kept)}  /  wells in cyan")
ax.axis("off")

plt.tight_layout()
out_png = SUB / "feature_A_pads_preview.png"
plt.savefig(out_png, dpi=110, bbox_inches="tight")
plt.close()
log(f"Saved: {out_png}")
log("DONE")
