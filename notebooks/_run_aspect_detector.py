"""Run the aspect-alignment-enhanced pad detector and regenerate the zoom preview."""
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
SUB_BBOX = (619500.0, 4594000.0, 624500.0, 4599000.0)
TARGET_CRS = "EPSG:26917"

def log(msg): print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def _load(path):
    with rasterio.open(path) as src:
        d = src.read(1).astype("float32")
        nd = src.nodata; t = src.transform; crs = src.crs
    if nd is not None: d[d == nd] = np.nan
    return d, t, crs

dem_arr, TRANSFORM, CRS = _load(SUB / "dem.tif")
slope_arr, _, _ = _load(SUB / "slope.tif")
rough_arr, _, _ = _load(SUB / "roughness.tif")
relief_arr, _, _ = _load(SUB / "local_relief.tif")
hand_arr, _, _ = _load(SUB / "hand.tif")
lrm_arr, _, _ = _load(SUB / "lrm.tif")
with rasterio.open(SUB / "point_density_mask.tif") as src:
    qmask_arr = src.read(1)
log("Arrays loaded")

# ── The detector (with aspect-alignment) ──────────────────────────────────
def detect_pad_scars(dem, slope, roughness, local_relief, hand, lrm,
                     quality_mask, transform, crs, *,
                     slope_max=5.0, roughness_max=1.0, relief_max=1.5,
                     lrm_max=0.3, hand_min=1.0, hand_max=60.0,
                     surround_inner_m=10, surround_outer_m=40,
                     lrm_ring_std_min=0.30,
                     area_min_m2=100, area_max_m2=5000,
                     elong_max=4.0, compact_min=0.15,
                     aspect_align_min=0.3):

    # Step 1 — Flat-patch seeds
    seed = (
        (slope < slope_max) & (roughness < roughness_max) &
        (local_relief < relief_max) & (np.abs(lrm) < lrm_max) &
        (hand >= hand_min) & (hand <= hand_max) & (quality_mask == 1)
    )
    seed &= ~np.isnan(slope) & ~np.isnan(hand) & ~np.isnan(lrm)
    log(f"  step 1 seed: {seed.sum():,}")

    # Step 2 — LRM ring contrast
    lrm_filled = np.where(np.isnan(lrm), 0.0, lrm).astype("float32")
    valid_mask = (~np.isnan(lrm)).astype("float32")
    sq = lrm_filled * lrm_filled
    def _ring_std(arr, mask_arr, r_in, r_out, sq_arr):
        w_o = 2*r_out+1; w_i = 2*r_in+1
        os_ = ndi.uniform_filter(arr, size=w_o, mode="reflect")*w_o**2
        is_ = ndi.uniform_filter(arr, size=w_i, mode="reflect")*w_i**2
        oc = ndi.uniform_filter(mask_arr, size=w_o, mode="reflect")*w_o**2
        ic = ndi.uniform_filter(mask_arr, size=w_i, mode="reflect")*w_i**2
        mn = np.where(oc-ic>0, (os_-is_)/np.maximum(oc-ic,1e-6), 0.0)
        osq = ndi.uniform_filter(sq_arr, size=w_o, mode="reflect")*w_o**2
        isq = ndi.uniform_filter(sq_arr, size=w_i, mode="reflect")*w_i**2
        sqm = np.where(oc-ic>0, (osq-isq)/np.maximum(oc-ic,1e-6), 0.0)
        return np.sqrt(np.maximum(sqm - mn*mn, 0.0)).astype("float32")

    lrm_ring_std = _ring_std(lrm_filled, valid_mask,
                             surround_inner_m, surround_outer_m, sq)
    seed &= lrm_ring_std > lrm_ring_std_min
    log(f"  step 2 (LRM ring std): {seed.sum():,}")

    # Step 2b — Aspect-alignment rasters
    dem_filled = np.where(np.isnan(dem), np.nanmean(dem), dem).astype("float32")
    dy_dem = ndi.sobel(dem_filled, axis=0, mode="nearest") / 8.0
    dx_dem = ndi.sobel(dem_filled, axis=1, mode="nearest") / 8.0
    aspect = np.arctan2(-dy_dem, -dx_dem)

    tpi = dem_filled - ndi.uniform_filter(dem_filled, size=15, mode="reflect")
    dy_tpi = ndi.sobel(tpi, axis=0, mode="nearest") / 8.0
    dx_tpi = ndi.sobel(tpi, axis=1, mode="nearest") / 8.0
    tpi_grad_dir = np.arctan2(dy_tpi, dx_tpi)

    angle_diff = np.abs(tpi_grad_dir - aspect)
    angle_diff = np.minimum(angle_diff, 2*np.pi - angle_diff)
    aspect_alignment = np.cos(angle_diff)

    # Step 3 — Morphological cleanup (opening first per literature)
    cleaned = opening(seed, disk(1))
    cleaned = closing(cleaned, disk(2))
    cleaned = remove_small_objects(cleaned, min_size=int(area_min_m2*0.6))
    log(f"  step 3 morphology: {cleaned.sum():,}")

    # Step 4 — Shape + aspect-alignment filter
    labels = label(cleaned, connectivity=2)
    log(f"  components: {labels.max()}")
    kept_ids = []
    rejected_aspect = 0
    for r in regionprops(labels):
        if not (area_min_m2 <= r.area <= area_max_m2): continue
        elong = r.axis_major_length / r.axis_minor_length if r.axis_minor_length > 0 else np.inf
        if elong > elong_max: continue
        compactness = (4*np.pi*r.area)/(r.perimeter**2) if r.perimeter > 0 else 0
        if compactness < compact_min: continue

        # Aspect-alignment: only enforce where surroundings have slope > 3°
        rmask = (labels == r.label)
        dilated = ndi.binary_dilation(rmask, disk(15))
        surr_mask = dilated & ~rmask
        if surr_mask.any():
            mean_surr_slope = float(np.nanmean(slope[surr_mask]))
        else:
            mean_surr_slope = 0.0
        mean_align = float(np.nanmean(aspect_alignment[rmask]))
        if mean_surr_slope > 3.0 and mean_align < aspect_align_min:
            rejected_aspect += 1
            continue

        kept_ids.append(r.label)

    log(f"  kept: {len(kept_ids)} (rejected {rejected_aspect} by aspect alignment)")
    keep_mask = np.isin(labels, kept_ids)

    # Step 5 — Vectorize + attributes
    records = []
    for geom_json, _ in rio_shapes(keep_mask.astype("uint8"), mask=keep_mask,
                                    transform=transform, connectivity=8):
        geom = shape(geom_json)
        if not geom.is_valid or geom.area < area_min_m2: continue
        cx, cy = geom.centroid.x, geom.centroid.y
        col, row = ~transform * (cx, cy)
        row, col = int(round(row)), int(round(col))
        H, W = slope.shape
        if not (0 <= row < H and 0 <= col < W): continue
        perim = geom.length
        compact = (4*np.pi*geom.area)/(perim**2) if perim > 0 else 0
        def _get(arr):
            v = arr[row, col]
            return float(v) if np.isfinite(v) else None
        poly_label = labels[row, col]
        rmask = (labels == poly_label) if poly_label > 0 else np.zeros_like(labels, dtype=bool)
        mean_align = float(np.nanmean(aspect_alignment[rmask])) if rmask.any() else _get(aspect_alignment)

        records.append({
            "geometry": geom, "area_m2": float(geom.area),
            "perimeter_m": float(perim), "compactness": float(compact),
            "slope": _get(slope), "roughness": _get(roughness),
            "local_relief": _get(local_relief), "hand": _get(hand),
            "lrm": _get(lrm), "lrm_ring_std": float(lrm_ring_std[row, col]),
            "aspect_align": mean_align,
        })
    return gpd.GeoDataFrame(records, crs=crs)


# ── Run ───────────────────────────────────────────────────────────────────
log("Running detector with aspect-alignment...")
OUT = SUB / "features_A_pads.gpkg"
if OUT.exists(): OUT.unlink()

pads = detect_pad_scars(
    dem_arr, slope_arr, rough_arr, relief_arr, hand_arr, lrm_arr, qmask_arr,
    TRANSFORM, CRS,
)
if len(pads) > 0:
    pads.to_file(OUT, layer="pads", driver="GPKG")
log(f"{len(pads)} candidates")
if len(pads) > 0:
    print(pads[["area_m2","compactness","slope","lrm","lrm_ring_std","aspect_align"]]
          .describe().round(2).to_string())


# ── Zoom preview ──────────────────────────────────────────────────────────
log("Zoom preview...")
N = min(9, len(pads))
if N == 0:
    log("No candidates to zoom"); exit()

top = pads.sort_values("area_m2", ascending=False).head(N).reset_index(drop=True)
wells_all = gpd.read_file(DATA / "wells_with_features.shp").to_crs(TARGET_CRS)
wells_sub = wells_all[wells_all.geometry.within(box(*SUB_BBOX))].copy()
with rasterio.open(SUB / "hillshade.tif") as s: hs = s.read(1).astype("float32")
with rasterio.open(SUB / "slope.tif") as s:
    sl = s.read(1).astype("float32")
    if s.nodata: sl[sl == s.nodata] = np.nan
inv = ~TRANSFORM; BUF = 50

ncols = 3; nrows = (N + ncols - 1) // ncols
fig, axes = plt.subplots(nrows, ncols, figsize=(5.2*ncols, 5.2*nrows))
for i, ax in enumerate(axes.flat if hasattr(axes,'flat') else [axes]):
    if i >= N: ax.axis("off"); continue
    row = top.iloc[i]; geom = row.geometry
    if geom is None or geom.is_empty: ax.axis("off"); continue
    mnx, mny, mxx, mxy = geom.bounds
    mnx -= BUF; mxx += BUF; mny -= BUF; mxy += BUF
    ct, rt = inv*(mnx, mxy); cb, rb = inv*(mxx, mny)
    r0 = int(max(0,np.floor(rt))); r1 = int(min(hs.shape[0],np.ceil(rb)))
    c0 = int(max(0,np.floor(ct))); c1 = int(min(hs.shape[1],np.ceil(cb)))
    if r1<=r0 or c1<=c0: ax.axis("off"); continue
    ax.imshow(hs[r0:r1, c0:c1], cmap="gray")
    ax.imshow(sl[r0:r1, c0:c1], cmap="cividis", alpha=0.35, vmin=0, vmax=20)
    xs, ys = geom.exterior.xy
    pp = np.array([inv*(x,y) for x,y in zip(xs,ys)])
    pp[:,0] -= c0; pp[:,1] -= r0
    ax.plot(pp[:,0], pp[:,1], color="orange", lw=2, zorder=4)
    ax.fill(pp[:,0], pp[:,1], color="orange", alpha=0.15, zorder=3)
    wi = wells_sub[wells_sub.geometry.within(box(mnx,mny,mxx,mxy))]
    if len(wi):
        wp = np.array([inv*(p.x,p.y) for p in wi.geometry])
        wp[:,0] -= c0; wp[:,1] -= r0
        ax.scatter(wp[:,0], wp[:,1], s=45, c="cyan", edgecolor="black", lw=0.7, zorder=5)
    ax.plot([5,25], [hs[r0:r1,c0:c1].shape[0]-10]*2, c="white", lw=3, zorder=6)
    ax.text(15, hs[r0:r1,c0:c1].shape[0]-14, "20 m", c="white", fontsize=8,
            ha="center", va="bottom", zorder=6, fontweight="bold")
    ax.set_title(
        f"#{i+1}  area={row.area_m2:.0f} m\u00b2  compact={row.compactness:.2f}\n"
        f"slope={row.slope:.1f}\u00b0  align={row.aspect_align:.2f}  {len(wi)} wells",
        fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
plt.suptitle(f"Aspect-aligned detector: top {N} by area", fontsize=12, y=0.995)
plt.tight_layout()
out = SUB / "zoom_preview_aspect.png"
plt.savefig(out, dpi=120, bbox_inches="tight")
plt.close()
log(f"Saved: {out}")
