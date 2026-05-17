"""Standalone: compute LRM, run new detector, regenerate zoom preview."""
from pathlib import Path
import time
import numpy as np
import rasterio
from rasterio.features import shapes as rio_shapes
from scipy import ndimage as ndi
from skimage.morphology import closing, opening, disk, remove_small_objects
from skimage.measure import label, regionprops
import geopandas as gpd
from shapely.geometry import box, shape
import matplotlib.pyplot as plt

DATA = Path(r"C:/Users/colto/Documents/GitHub/lidar_project/data")
SUB = DATA / "derivatives" / "subarea"
SUB_DEM = SUB / "dem.tif"
SLOPE = SUB / "slope.tif"
ROUGHNESS = SUB / "roughness.tif"
LOCAL_RELIEF = SUB / "local_relief.tif"
HAND = SUB / "hand.tif"
LRM = SUB / "lrm.tif"
QMASK = SUB / "point_density_mask.tif"
HSHADE = SUB / "hillshade.tif"
WELLS_PATH = DATA / "wells_with_features.shp"
OUT_GPKG = SUB / "features_A_pads.gpkg"
SUB_BBOX = (619500.0, 4594000.0, 624500.0, 4599000.0)
TARGET_CRS = "EPSG:26917"


def log(msg): print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ───────────────────────────────────────────────────────────────────────────
# 1. Compute LRM if not cached
# ───────────────────────────────────────────────────────────────────────────
LRM_KERNEL = 25
if not LRM.exists():
    log(f"Computing LRM (kernel={LRM_KERNEL} m)...")
    with rasterio.open(SUB_DEM) as src:
        dem = src.read(1).astype("float32")
        dem_nd = src.nodata
        prof = src.profile.copy()
    nd_mask = (dem == dem_nd) if dem_nd is not None else np.isnan(dem)
    mean_elev = float(np.nanmean(dem[~nd_mask])) if (~nd_mask).any() else 0.0
    filled = np.where(nd_mask, mean_elev, dem).astype("float32")
    smoothed = ndi.uniform_filter(filled, size=LRM_KERNEL, mode="reflect")
    lrm_arr = dem - smoothed
    lrm_arr[nd_mask] = np.nan
    prof.update(dtype="float32", nodata=-9999.0, compress="deflate",
                tiled=True, blockxsize=256, blockysize=256)
    out = lrm_arr.copy()
    out[np.isnan(out)] = -9999.0
    with rasterio.open(LRM, "w", **prof) as dst:
        dst.write(out.astype("float32"), 1)

with rasterio.open(LRM) as src:
    lrm_check = src.read(1).astype("float32")
    nd = src.nodata
if nd is not None:
    lrm_check[lrm_check == nd] = np.nan
log(f"LRM stats: p2={np.nanpercentile(lrm_check, 2):.2f}  "
    f"p50={np.nanpercentile(lrm_check, 50):.2f}  "
    f"p98={np.nanpercentile(lrm_check, 98):.2f}  "
    f"|LRM|<0.3: {(np.abs(lrm_check) < 0.3).mean()*100:.1f}%")


# ───────────────────────────────────────────────────────────────────────────
# 2. Load all arrays
# ───────────────────────────────────────────────────────────────────────────
def _load(path):
    with rasterio.open(path) as src:
        d = src.read(1).astype("float32")
        nd = src.nodata
        t = src.transform
        crs = src.crs
    if nd is not None:
        d[d == nd] = np.nan
    return d, t, crs

slope_arr, TRANSFORM, CRS = _load(SLOPE)
rough_arr, _, _ = _load(ROUGHNESS)
relief_arr, _, _ = _load(LOCAL_RELIEF)
hand_arr, _, _ = _load(HAND)
lrm_arr, _, _ = _load(LRM)
with rasterio.open(QMASK) as src:
    qmask_arr = src.read(1)
log(f"Arrays loaded: {slope_arr.shape}")


# ───────────────────────────────────────────────────────────────────────────
# 3. Detector (new LRM-based version)
# ───────────────────────────────────────────────────────────────────────────
def detect_pad_scars(slope, roughness, local_relief, hand, lrm, quality_mask,
                     transform, crs, *,
                     slope_max=5.0, roughness_max=1.0, relief_max=1.5,
                     lrm_max=0.3, hand_min=1.0, hand_max=60.0,
                     surround_inner_m=10, surround_outer_m=40,
                     lrm_ring_std_min=0.30,
                     area_min_m2=100, area_max_m2=5000,
                     elong_max=4.0, compact_min=0.15):
    seed = (
        (slope < slope_max) &
        (roughness < roughness_max) &
        (local_relief < relief_max) &
        (np.abs(lrm) < lrm_max) &
        (hand >= hand_min) & (hand <= hand_max) &
        (quality_mask == 1)
    )
    seed &= ~np.isnan(slope) & ~np.isnan(hand) & ~np.isnan(lrm)
    log(f"  seed after step 1: {seed.sum():,} cells ({seed.mean()*100:.2f}%)")

    lrm_filled = np.where(np.isnan(lrm), 0.0, lrm).astype("float32")
    valid_mask = (~np.isnan(lrm)).astype("float32")
    sq = lrm_filled * lrm_filled

    def _ring_stat(arr, mask_arr, r_in, r_out, sq_arr):
        w_out = 2 * r_out + 1
        w_in = 2 * r_in + 1
        out_sum = ndi.uniform_filter(arr, size=w_out, mode="reflect") * w_out**2
        in_sum  = ndi.uniform_filter(arr, size=w_in,  mode="reflect") * w_in**2
        out_cnt = ndi.uniform_filter(mask_arr, size=w_out, mode="reflect") * w_out**2
        in_cnt  = ndi.uniform_filter(mask_arr, size=w_in,  mode="reflect") * w_in**2
        mean = np.where(out_cnt - in_cnt > 0,
                        (out_sum - in_sum) / np.maximum(out_cnt - in_cnt, 1e-6), 0.0)
        out_sq = ndi.uniform_filter(sq_arr, size=w_out, mode="reflect") * w_out**2
        in_sq  = ndi.uniform_filter(sq_arr, size=w_in,  mode="reflect") * w_in**2
        sq_mean = np.where(out_cnt - in_cnt > 0,
                           (out_sq - in_sq) / np.maximum(out_cnt - in_cnt, 1e-6), 0.0)
        var = np.maximum(sq_mean - mean * mean, 0.0)
        return np.sqrt(var).astype("float32")

    lrm_ring_std = _ring_stat(lrm_filled, valid_mask,
                              surround_inner_m, surround_outer_m, sq)
    seed &= lrm_ring_std > lrm_ring_std_min
    log(f"  seed after step 2 (LRM ring std>{lrm_ring_std_min}): {seed.sum():,} cells")

    cleaned = closing(seed, disk(2))
    cleaned = opening(cleaned, disk(1))
    cleaned = remove_small_objects(cleaned, min_size=int(area_min_m2 * 0.6))
    log(f"  after morphology: {cleaned.sum():,} cells")

    labels = label(cleaned, connectivity=2)
    log(f"  components: {labels.max()}")
    kept_ids = []
    for r in regionprops(labels):
        if not (area_min_m2 <= r.area <= area_max_m2):
            continue
        elong = r.axis_major_length / r.axis_minor_length if r.axis_minor_length > 0 else np.inf
        if elong > elong_max:
            continue
        compactness = (4 * np.pi * r.area) / (r.perimeter ** 2) if r.perimeter > 0 else 0
        if compactness < compact_min:
            continue
        kept_ids.append(r.label)
    log(f"  kept: {len(kept_ids)}")

    keep_mask = np.isin(labels, kept_ids)
    records = []
    for geom_json, _ in rio_shapes(keep_mask.astype("uint8"), mask=keep_mask,
                                    transform=transform, connectivity=8):
        geom = shape(geom_json)
        if not geom.is_valid or geom.area < area_min_m2:
            continue
        cx, cy = geom.centroid.x, geom.centroid.y
        col, row = ~transform * (cx, cy)
        row, col = int(round(row)), int(round(col))
        H, W = slope.shape
        if not (0 <= row < H and 0 <= col < W):
            continue
        perim = geom.length
        compact = (4 * np.pi * geom.area) / (perim ** 2) if perim > 0 else 0
        def _get(arr):
            v = arr[row, col]
            return float(v) if np.isfinite(v) else None
        records.append({
            "geometry": geom,
            "area_m2": float(geom.area),
            "perimeter_m": float(perim),
            "compactness": float(compact),
            "slope": _get(slope),
            "roughness": _get(roughness),
            "local_relief": _get(local_relief),
            "hand": _get(hand),
            "lrm": _get(lrm),
            "lrm_ring_std": float(lrm_ring_std[row, col]),
        })
    return gpd.GeoDataFrame(records, crs=crs)


log("Running LRM-based detector...")
if OUT_GPKG.exists():
    OUT_GPKG.unlink()
pads = detect_pad_scars(
    slope_arr, rough_arr, relief_arr, hand_arr, lrm_arr, qmask_arr,
    TRANSFORM, CRS,
)
if len(pads) > 0:
    pads.to_file(OUT_GPKG, layer="pads", driver="GPKG")
log(f"{len(pads)} pad candidates")
if len(pads) > 0:
    print(pads[["area_m2", "compactness", "slope", "lrm", "lrm_ring_std"]]
          .describe().round(2).to_string())


# ───────────────────────────────────────────────────────────────────────────
# 4. Regenerate zoom preview
# ───────────────────────────────────────────────────────────────────────────
log("Regenerating zoom preview...")
N_TO_SHOW = 9
BUFFER_M = 50

wells_all = gpd.read_file(WELLS_PATH).to_crs(TARGET_CRS)
wells_sub = wells_all[wells_all.geometry.within(box(*SUB_BBOX))].copy()

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
        f"slope={row.slope:.1f}\u00b0  LRM={row.lrm:+.2f} m  "
        f"ring_std={row.lrm_ring_std:.2f} m  {len(wells_in)} wells",
        fontsize=9,
    )
    ax.set_xticks([]); ax.set_yticks([])

plt.suptitle(
    f"LRM-based detector: top {min(N_TO_SHOW, len(top))} pad candidates by area",
    fontsize=12, y=0.995,
)
plt.tight_layout()
out = SUB / "zoom_preview_lrm.png"
plt.savefig(out, dpi=120, bbox_inches="tight")
plt.close()
log(f"Saved: {out}")
