"""
Feature Type B — Access Roads and Haul Trails detector (first draft).

Per CLAUDE.md: linear concavities visible in negative openness, flanked by
parallel positive-openness berms, low slope along the road bed, traversing
otherwise steep hillslopes. Discriminators against natural features: stream
channels have high flow accumulation and follow convergent topography;
road cuts occur at positions that don't align with natural drainage.

Strategy:
  1. Seed = local z-score(neg openness) > 1.0 AND flow accum < stream threshold
  2. Clean with morphological open/close
  3. Connected components
  4. Filter by area, linearity (skeleton length / bbox diagonal), length >= 30 m
  5. Buffer skeleton → polygon, attach attributes, write GeoPackage

This is a first draft — thresholds will be tuned after visual inspection.
"""
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes as rio_shapes
from scipy import ndimage as ndi
from skimage.morphology import skeletonize, remove_small_objects, binary_closing, disk
from skimage.measure import label, regionprops

import geopandas as gpd
from shapely.geometry import shape, LineString, Point, box
from shapely.ops import unary_union

SUB = Path(r"C:/Users/colto/Documents/GitHub/lidar_project/data/derivatives/subarea")
OUT_GPKG = SUB / "features_B_roads.gpkg"


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
        transform = s.transform
        crs = s.crs
    if nd is not None:
        d[d == nd] = np.nan
    return d, prof, transform, crs


NEG_OP, PROF, TRANSFORM, CRS = _load(SUB / "openness_negative.tif")
POS_OP, *_ = _load(SUB / "openness_positive.tif")
SLOPE, *_ = _load(SUB / "slope.tif")
TPI15, *_ = _load(SUB / "tpi_15m.tif")
HAND, *_ = _load(SUB / "hand.tif")

with rasterio.open(SUB / "point_density_mask.tif") as s:
    QMASK = s.read(1)   # uint8: 1 = pass, 0 = fail, 255 = nodata

with rasterio.open(SUB / "d8_accum.tif") as s:
    FLOW_ACCUM = s.read(1).astype("float32")

log(f"Arrays: {NEG_OP.shape}")


# ───────────────────────────────────────────────────────────────────────────
# Step 1 — Seed mask: locally concave, not a natural drainage
# ───────────────────────────────────────────────────────────────────────────
log("Computing local z-score of negative openness (201 px window)...")
nd_mask = np.isnan(NEG_OP)
filled = np.where(nd_mask, 0.0, NEG_OP).astype("float32")
mean = ndi.uniform_filter(filled, size=201, mode="reflect")
sq = ndi.uniform_filter(filled * filled, size=201, mode="reflect")
std = np.sqrt(np.maximum(sq - mean * mean, 1e-6))
neg_z = (filled - mean) / std
neg_z[nd_mask] = np.nan

log("Building seed mask...")
# Primary concavity signal
seed_concave = np.nan_to_num(neg_z, nan=-99) > 1.0

# Exclude natural streams: log(d8_accum) > log(5000) means cell has 5000+ upstream cells
# which is where we originally drew streams. Those are natural channels.
log_accum = np.log10(np.maximum(FLOW_ACCUM, 1.0))
stream_mask = log_accum > np.log10(5000)
# Dilate stream mask to exclude the immediate stream corridor
stream_corridor = ndi.binary_dilation(stream_mask, iterations=5)

# Quality gate
qgood = QMASK == 1

seed = seed_concave & ~stream_corridor & qgood

# Also clip to cells where HAND > 0 (exclude stream cells where HAND=0 exactly)
seed &= ~np.isnan(HAND)
seed &= HAND > 0.5

log(f"Seed cells: {seed.sum():,} ({seed.mean()*100:.3f}%)")


# ───────────────────────────────────────────────────────────────────────────
# Step 2 — Morphological cleanup
# ───────────────────────────────────────────────────────────────────────────
log("Morphological cleanup (close 2, remove <20 cells)...")
cleaned = binary_closing(seed, disk(2))
cleaned = remove_small_objects(cleaned, min_size=20)
log(f"After cleanup: {cleaned.sum():,}")


# ───────────────────────────────────────────────────────────────────────────
# Step 3 — Skeletonize and label connected components
# ───────────────────────────────────────────────────────────────────────────
log("Skeletonizing and labeling components...")
skeleton = skeletonize(cleaned)
labels = label(cleaned, connectivity=2)
n_comp = labels.max()
log(f"  components: {n_comp}")


# ───────────────────────────────────────────────────────────────────────────
# Step 4 — Filter components by shape + length
# ───────────────────────────────────────────────────────────────────────────
log("Filtering components by shape...")

MIN_AREA   = 50         # cells (50 m² minimum)
MIN_LENGTH = 30         # meters (major axis of bbox)
MIN_LINEAR = 2.0        # major_axis / minor_axis
MAX_WIDTH  = 15         # meters — reject blobby features

kept = []
for region in regionprops(labels):
    if region.area < MIN_AREA:
        continue
    if region.major_axis_length < MIN_LENGTH:
        continue
    if region.minor_axis_length > 0:
        elong = region.major_axis_length / region.minor_axis_length
    else:
        elong = float("inf")
    if elong < MIN_LINEAR:
        continue
    # Approximate width = area / major axis length (aspect via perimeter would be nicer)
    est_width = region.area / max(region.major_axis_length, 1e-6)
    if est_width > MAX_WIDTH:
        continue
    kept.append(region)

log(f"  kept {len(kept)} of {n_comp}")


# ───────────────────────────────────────────────────────────────────────────
# Step 5 — Polygon output with attributes
# ───────────────────────────────────────────────────────────────────────────
log("Building polygon layer...")

# Rebuild a mask containing only the kept components
keep_mask = np.zeros_like(labels, dtype=bool)
for region in kept:
    keep_mask[labels == region.label] = True

# Vectorize: use rasterio.features.shapes to get one polygon per connected component
shapes_gen = rio_shapes(
    keep_mask.astype("uint8"),
    mask=keep_mask,
    transform=TRANSFORM,
    connectivity=8,
)

records = []
for geom_json, value in shapes_gen:
    geom = shape(geom_json)
    if not geom.is_valid or geom.area < 50:
        continue
    # Sample mean derivative values inside the polygon (via centroid — cheap first pass)
    cx, cy = geom.centroid.x, geom.centroid.y
    # Convert to pixel
    inv = ~TRANSFORM
    px, py = inv * (cx, cy)
    px = int(round(px)); py = int(round(py))
    if 0 <= py < NEG_OP.shape[0] and 0 <= px < NEG_OP.shape[1]:
        sampled = {
            "neg_op":    float(NEG_OP[py, px]) if np.isfinite(NEG_OP[py, px]) else None,
            "pos_op":    float(POS_OP[py, px]) if np.isfinite(POS_OP[py, px]) else None,
            "neg_op_z":  float(neg_z[py, px]) if np.isfinite(neg_z[py, px]) else None,
            "slope":     float(SLOPE[py, px]) if np.isfinite(SLOPE[py, px]) else None,
            "tpi15":     float(TPI15[py, px]) if np.isfinite(TPI15[py, px]) else None,
            "hand":      float(HAND[py, px]) if np.isfinite(HAND[py, px]) else None,
        }
    else:
        sampled = {}
    records.append({
        "geometry": geom,
        "area_m2": float(geom.area),
        "length_m": float(geom.length),
        **sampled,
    })

if records:
    gdf = gpd.GeoDataFrame(records, crs=CRS)
    gdf.to_file(OUT_GPKG, layer="roads", driver="GPKG")
    log(f"Wrote {len(gdf)} road candidates to {OUT_GPKG}")
    log(f"  area_m2:  p50={gdf['area_m2'].median():.0f}, p95={gdf['area_m2'].quantile(0.95):.0f}")
    log(f"  length_m: p50={gdf['length_m'].median():.0f}, p95={gdf['length_m'].quantile(0.95):.0f}")
else:
    log("No candidates passed filters")

# ───────────────────────────────────────────────────────────────────────────
# Quick visualization
# ───────────────────────────────────────────────────────────────────────────
log("Rendering detector visualization...")
import matplotlib.pyplot as plt
with rasterio.open(SUB / "hillshade.tif") as s:
    hs = s.read(1).astype("float32")

fig, axes = plt.subplots(1, 3, figsize=(21, 7))

ax = axes[0]
ax.imshow(hs, cmap="gray")
ax.imshow(neg_z, cmap="coolwarm_r", vmin=-2, vmax=2, alpha=0.55)
ax.set_title("Neg openness z-score (201 px window)")
ax.axis("off")

ax = axes[1]
ax.imshow(hs, cmap="gray")
ov = np.where(seed, 1, np.nan)
ax.imshow(ov, cmap="autumn", alpha=0.9)
ax.set_title(f"Seed cells (z>1.0, ~stream, HAND>0.5)  — {seed.sum():,}")
ax.axis("off")

ax = axes[2]
ax.imshow(hs, cmap="gray")
ov2 = np.where(keep_mask, 1, np.nan)
ax.imshow(ov2, cmap="autumn", alpha=0.9)
ax.set_title(f"Kept candidates — {len(kept)}")
ax.axis("off")

plt.tight_layout()
out_png = SUB / "feature_B_roads_preview.png"
plt.savefig(out_png, dpi=110, bbox_inches="tight")
plt.close()
log(f"Saved: {out_png}")
log("DONE")
