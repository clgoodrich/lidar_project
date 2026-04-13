"""Build pad_detection.ipynb — a minimal, focused notebook for pad detection only."""
import json
from pathlib import Path

NB = Path(r"C:/Users/colto/Documents/GitHub/lidar_project/notebooks/pad_detection.ipynb")


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": text.splitlines(keepends=True)}


cells = []

cells.append(md("""# Pad Detection — Minimal Pipeline

Self-contained pipeline for identifying historic well pad scars in bare-earth LiDAR derivatives over a 5 × 5 km calibration subarea in western Pennsylvania.

**Scope:** just pad detection. No roads, no borehole collapses, no validation framework, no point-cloud-only derivatives (CHM / intensity / canopy density). Those all live elsewhere. This notebook does one job end-to-end:

1. Clip the full DEM to the calibration subarea
2. Load the historic wells layer and clip it to the subarea
3. Build the five derivatives the pad detector needs (slope, roughness, local relief, HAND, quality mask)
4. Run the pad-scar detector
5. Visualize candidates over a hillshade with the wells overlaid

Re-running the notebook is cheap: every step checks for its cached output on disk and skips if found. Delete files under `data/derivatives/subarea/` to force a rebuild.
"""))

# ─── Setup ─────────────────────────────────────────────────────────────────
cells.append(md("""## 1. Setup"""))

cells.append(code('''from pathlib import Path
import struct

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.merge import merge as rio_merge
from rasterio.features import shapes as rio_shapes

from scipy import ndimage as ndi

from skimage.morphology import closing, opening, disk, remove_small_objects
from skimage.measure import label, regionprops

import geopandas as gpd
from shapely.geometry import box, shape

import matplotlib.pyplot as plt

import whitebox
wbt = whitebox.WhiteboxTools()
wbt.set_verbose_mode(False)
'''))

cells.append(code('''# ── Paths ─────────────────────────────────────────────────────────────────
ROOT       = Path(r"C:/Users/colto/Documents/GitHub/lidar_project")
DATA       = ROOT / "data"
LAZ_DIR    = DATA / "files"
DEM_MOSAIC = DATA / "full_dem.tif"
WELLS_PATH = DATA / "wells_with_features.shp"

SUB = DATA / "derivatives" / "subarea"
SUB.mkdir(parents=True, exist_ok=True)

# ── Constants ────────────────────────────────────────────────────────────
TARGET_CRS = "EPSG:26917"                              # UTM zone 17N

# 5 × 5 km calibration subarea (selected by max well density within the full DEM)
SUB_BBOX = (619500.0, 4594000.0, 624500.0, 4599000.0)  # (xmin, ymin, xmax, ymax)
'''))

# ─── DEM clip ──────────────────────────────────────────────────────────────
cells.append(md("""## 2. Clip the DEM to the subarea

The full bare-earth DEM is ~1.6 GB covering 21 × 19.5 km. The calibration subarea is 5 × 5 km (~75 MB). Every subsequent step operates on the clip."""))

cells.append(code('''SUB_DEM = SUB / "dem.tif"

if not SUB_DEM.exists():
    with rasterio.open(DEM_MOSAIC) as src:
        window = from_bounds(*SUB_BBOX, transform=src.transform)
        window = window.round_offsets().round_lengths()
        data = src.read(1, window=window)
        transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(
            height=data.shape[0], width=data.shape[1],
            transform=transform, crs=TARGET_CRS,
            compress="deflate", tiled=True,
            blockxsize=256, blockysize=256,
        )
    with rasterio.open(SUB_DEM, "w", **profile) as dst:
        dst.write(data, 1)

with rasterio.open(SUB_DEM) as src:
    print(f"Subarea DEM: {src.width} × {src.height} cells @ 1 m")
    d = src.read(1)
    valid = d[d != src.nodata]
    print(f"  Elevation: {valid.min():.1f} – {valid.max():.1f} m")
    print(f"  Nodata:    {(d == src.nodata).mean()*100:.2f}%")
'''))

# ─── Wells ─────────────────────────────────────────────────────────────────
cells.append(md("""## 3. Load the wells layer

Loads all historic wells inside the subarea polygon. Used for visualization only in this notebook — validation against well positions is a separate concern handled elsewhere."""))

cells.append(code('''wells = gpd.read_file(WELLS_PATH).to_crs(TARGET_CRS)
wells_sub = wells[wells.geometry.within(box(*SUB_BBOX))].copy().reset_index(drop=True)
print(f"Wells in subarea: {len(wells_sub)} (of {len(wells)} total in the full dataset)")
'''))

# ─── Derivatives: slope, roughness, local relief ──────────────────────────
cells.append(md("""## 4. Build the derivatives

The pad detector needs five rasters:

| Raster | What it measures | Why the detector uses it |
|---|---|---|
| **slope** | degrees of tilt per cell | pads are flat surfaces (`slope < 5°`) |
| **roughness** | std-dev of slope in a 5 m window | engineered surfaces are smooth (`roughness < 1°`) |
| **local relief** | elev range in an 11 m window | flat surfaces have low internal relief (`< 1.5 m`) |
| **HAND** | height above nearest drainage | excludes stream cells (HAND ≈ 0) and ridge tops (HAND > 60) |
| **quality mask** | binary: is ground density ≥ 1 pt/m² | flags cells where the DEM is interpolated, not measured |

All five are built via WhiteboxTools. Each cell is idempotent and fast on re-run."""))

cells.append(code('''SLOPE        = SUB / "slope.tif"
ROUGHNESS    = SUB / "roughness.tif"
LOCAL_RELIEF = SUB / "local_relief.tif"

# Slope in degrees
if not SLOPE.exists():
    wbt.slope(dem=str(SUB_DEM), output=str(SLOPE), units="degrees")

# Roughness = stddev of slope in a 5×5 window
if not ROUGHNESS.exists():
    wbt.standard_deviation_filter(
        i=str(SLOPE), output=str(ROUGHNESS),
        filterx=5, filtery=5,
    )

# Local relief = max − min in an 11×11 window (~10 m radius)
if not LOCAL_RELIEF.exists():
    _max = SUB / "_max.tif"
    _min = SUB / "_min.tif"
    wbt.maximum_filter(i=str(SUB_DEM), output=str(_max), filterx=11, filtery=11)
    wbt.minimum_filter(i=str(SUB_DEM), output=str(_min), filterx=11, filtery=11)
    with rasterio.open(_max) as a, rasterio.open(_min) as b:
        lr = a.read(1).astype("float32") - b.read(1).astype("float32")
        prof = a.profile.copy()
    # Restore nodata from source DEM
    with rasterio.open(SUB_DEM) as s:
        dem_raw = s.read(1)
        dem_nd = s.nodata
    lr[dem_raw == dem_nd] = -9999.0
    prof.update(dtype="float32", nodata=-9999.0, compress="deflate",
                tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(LOCAL_RELIEF, "w", **prof) as dst:
        dst.write(lr.astype("float32"), 1)
    _max.unlink(); _min.unlink()

print(f"slope:        {SLOPE.exists()}")
print(f"roughness:    {ROUGHNESS.exists()}")
print(f"local_relief: {LOCAL_RELIEF.exists()}")
'''))

# ─── HAND ──────────────────────────────────────────────────────────────────
cells.append(md("""### HAND (Height Above Nearest Drainage)

Computed on a DEM buffered 1.5 km beyond the subarea so flow paths near the boundary reach a stream instead of running off the edge. Low stream threshold (100 cells upstream area) produces a dense drainage network, giving HAND coverage for >90% of subarea cells. The result is clipped back to the subarea."""))

cells.append(code('''HAND    = SUB / "hand.tif"
STREAMS = SUB / "streams.tif"

if not HAND.exists():
    BUFFER = 1500.0  # meters

    # Clip the buffer to the full DEM edge
    with rasterio.open(DEM_MOSAIC) as src:
        fb = src.bounds
    bx0 = max(SUB_BBOX[0] - BUFFER, fb.left)
    by0 = max(SUB_BBOX[1] - BUFFER, fb.bottom)
    bx1 = min(SUB_BBOX[2] + BUFFER, fb.right)
    by1 = min(SUB_BBOX[3] + BUFFER, fb.top)

    TMP = SUB / "_hand_tmp"
    TMP.mkdir(exist_ok=True)
    BUF_DEM = TMP / "dem_buffered.tif"

    # 1. Clip the buffered DEM
    with rasterio.open(DEM_MOSAIC) as src:
        w = from_bounds(bx0, by0, bx1, by1, transform=src.transform)
        w = w.round_offsets().round_lengths()
        data = src.read(1, window=w)
        tr = src.window_transform(w)
        prof = src.profile.copy()
        prof.update(height=data.shape[0], width=data.shape[1], transform=tr,
                    crs=TARGET_CRS, compress="deflate", tiled=True,
                    blockxsize=256, blockysize=256)
    with rasterio.open(BUF_DEM, "w", **prof) as dst:
        dst.write(data, 1)

    # 2. HAND pipeline
    BREACHED = TMP / "breached.tif"
    D8_PTR   = TMP / "d8_ptr.tif"
    D8_ACC   = TMP / "d8_acc.tif"
    ST_BUF   = TMP / "streams.tif"
    HAND_BUF = TMP / "hand.tif"

    wbt.breach_depressions_least_cost(dem=str(BUF_DEM), output=str(BREACHED), dist=200, fill=True)
    wbt.d8_pointer(dem=str(BREACHED), output=str(D8_PTR))
    wbt.d8_flow_accumulation(i=str(BREACHED), output=str(D8_ACC), out_type="cells")
    wbt.extract_streams(flow_accum=str(D8_ACC), output=str(ST_BUF), threshold=100)
    wbt.elevation_above_stream(dem=str(BUF_DEM), streams=str(ST_BUF), output=str(HAND_BUF))

    # 3. Clip HAND and streams back to the subarea
    def _clip_to_subarea(src_path, out_path):
        with rasterio.open(src_path) as src:
            w = from_bounds(*SUB_BBOX, transform=src.transform)
            w = w.round_offsets().round_lengths()
            data = src.read(1, window=w)
            tr = src.window_transform(w)
            prof = src.profile.copy()
            prof.update(height=data.shape[0], width=data.shape[1], transform=tr,
                        crs=TARGET_CRS, compress="deflate", tiled=True,
                        blockxsize=256, blockysize=256)
        with rasterio.open(out_path, "w", **prof) as dst:
            dst.write(data, 1)

    _clip_to_subarea(HAND_BUF, HAND)
    _clip_to_subarea(ST_BUF,   STREAMS)

with rasterio.open(HAND) as src:
    h = src.read(1)
    nd = src.nodata
    valid = (h != nd).mean() if nd is not None else (~np.isnan(h)).mean()
    print(f"HAND valid cells: {valid*100:.1f}%")
'''))

# ─── Quality mask ──────────────────────────────────────────────────────────
cells.append(md("""### Ground return point density (quality mask)

Built from the raw LAZ tiles: grid class-2 (ground) returns at 1 m, threshold at 1 pt/m². Cells below the threshold are interpolated — the DEM value is a guess, not a measurement — so the pad detector excludes them from seed candidates."""))

cells.append(code('''# Identify the 16 LAZ tiles that cover the subarea
# (read bounds from each LAS 1.4 public header block directly — faster than lidar_info)
def _las_bbox(path):
    with open(path, "rb") as fp:
        hdr = fp.read(256)
    assert hdr[:4] == b"LASF"
    max_x, min_x, max_y, min_y = struct.unpack_from("<dddd", hdr, 179)
    return (min_x, min_y, max_x, max_y)

sub_laz = []
for f in sorted(LAZ_DIR.glob("*.laz")):
    mnx, mny, mxx, mxy = _las_bbox(f)
    if mxx > SUB_BBOX[0] and mnx < SUB_BBOX[2] and mxy > SUB_BBOX[1] and mny < SUB_BBOX[3]:
        sub_laz.append(f)
print(f"{len(sub_laz)} LAZ tiles intersect the subarea")

PTD_GROUND = SUB / "point_density_ground.tif"
QMASK      = SUB / "point_density_mask.tif"

EXCLUDE_NOT_GROUND = "0,1,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18"  # keep class 2 only

if not PTD_GROUND.exists():
    TMP = SUB / "_ptd_tiles"
    TMP.mkdir(exist_ok=True)
    per_tile = []
    for laz in sub_laz:
        out = TMP / f"ptd_{laz.stem}.tif"
        if not out.exists():
            wbt.lidar_point_density(
                i=str(laz), output=str(out),
                returns="all", resolution=1.0, radius=2.5,
                exclude_cls=EXCLUDE_NOT_GROUND,
            )
        per_tile.append(out)

    srcs = [rasterio.open(p) for p in per_tile]
    data, tr = rio_merge(srcs, bounds=SUB_BBOX, res=(1.0, 1.0), nodata=-9999.0)
    prof = srcs[0].profile.copy()
    for s in srcs:
        s.close()
    prof.update(height=data.shape[1], width=data.shape[2], transform=tr,
                crs=TARGET_CRS, compress="deflate", tiled=True, count=1,
                dtype="float32", nodata=-9999.0,
                blockxsize=256, blockysize=256)
    with rasterio.open(PTD_GROUND, "w", **prof) as dst:
        dst.write(data[0].astype("float32"), 1)

if not QMASK.exists():
    with rasterio.open(PTD_GROUND) as src:
        dens = src.read(1)
        prof = src.profile.copy()
    mask_arr = (dens >= 1.0).astype("uint8")
    mask_arr[dens < 0] = 255
    prof.update(dtype="uint8", nodata=255, compress="deflate", tiled=True,
                blockxsize=256, blockysize=256)
    with rasterio.open(QMASK, "w", **prof) as dst:
        dst.write(mask_arr, 1)

with rasterio.open(QMASK) as src:
    m = src.read(1)
print(f"Quality mask: {(m == 1).mean()*100:.1f}% of cells pass (≥ 1 ground pt/m²)")
'''))

# ─── LRM ───────────────────────────────────────────────────────────────────
cells.append(md("""### Local Relief Model (LRM)

`LRM = DEM − uniform_filter(DEM, 25)`. A high-pass filter on the DEM that strips the regional topographic trend and leaves only features smaller than the kernel. Hesse (2010) introduced it for archaeological site detection; the review in `filtering_methods_wellpad.md` flags it as the **missing first stage** for our problem and the standard primitive for pad-like feature detection in the 90–97% accuracy literature.

Kernel choice: **25 cells (25 m)**. Larger than Hesse's 11 m because our target features (well pads, ~15–30 m) are larger than burial mounds. At 25 m:
- Pads **smaller** than the kernel → the filter mean picks up surrounding terrain, so LRM shows the pad's elevation **offset** from its neighborhood (positive if fill-dominant, negative if cut-dominant).
- Pads **larger** than the kernel → LRM ≈ 0 at the pad center (filter window is entirely inside the pad), with strong LRM values at the pad **edges** (cut bank and fill edge).

Both regimes are useful. Note that a linear hillside gives LRM ≈ 0 because the mean filter cancels linear trends — so LRM alone cannot distinguish flat pads from tilted ground, and the slope criterion still has to stay in the seed."""))

cells.append(code('''LRM = SUB / "lrm.tif"

LRM_KERNEL = 25  # cells (also meters, at 1 m resolution)

if not LRM.exists():
    with rasterio.open(SUB_DEM) as src:
        dem = src.read(1).astype("float32")
        dem_nd = src.nodata
        prof = src.profile.copy()
    nd_mask = (dem == dem_nd) if dem_nd is not None else np.isnan(dem)

    # Use mean elevation as the fill value for nodata so the uniform_filter
    # doesn't pull the smoothed surface toward zero near gaps.
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
print(f"LRM: kernel={LRM_KERNEL} m")
print(f"  p2 ={np.nanpercentile(lrm_check, 2):6.2f} m")
print(f"  p50={np.nanpercentile(lrm_check, 50):6.2f} m")
print(f"  p98={np.nanpercentile(lrm_check, 98):6.2f} m")
print(f"  cells with |LRM| < 0.3 m: {(np.abs(lrm_check) < 0.3).mean()*100:.1f}%")
'''))

# ─── Load arrays ───────────────────────────────────────────────────────────
cells.append(md("""## 5. Load all derivatives into memory"""))

cells.append(code('''def _load(path):
    with rasterio.open(path) as src:
        data = src.read(1).astype("float32")
        nd = src.nodata
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
    if nd is not None:
        data[data == nd] = np.nan
    return data, profile, transform, crs


slope_arr,  PROF, TRANSFORM, CRS = _load(SLOPE)
rough_arr,  *_                    = _load(ROUGHNESS)
relief_arr, *_                    = _load(LOCAL_RELIEF)
hand_arr,   *_                    = _load(HAND)
lrm_arr,    *_                    = _load(LRM)

# Quality mask is uint8 — read as-is
with rasterio.open(QMASK) as src:
    qmask_arr = src.read(1)

print(f"Loaded arrays: shape={slope_arr.shape}")
print(f"  slope       — p50={np.nanpercentile(slope_arr, 50):.2f}°   p98={np.nanpercentile(slope_arr, 98):.2f}°")
print(f"  roughness   — p50={np.nanpercentile(rough_arr, 50):.2f}    p98={np.nanpercentile(rough_arr, 98):.2f}")
print(f"  relief      — p50={np.nanpercentile(relief_arr, 50):.2f} m  p98={np.nanpercentile(relief_arr, 98):.2f} m")
print(f"  HAND        — p50={np.nanpercentile(hand_arr, 50):.2f} m    p98={np.nanpercentile(hand_arr, 98):.2f} m")
print(f"  LRM         — p50={np.nanpercentile(lrm_arr, 50):.2f} m    p98={np.nanpercentile(lrm_arr, 98):.2f} m")
print(f"  quality     — pass={(qmask_arr == 1).mean()*100:.1f}%")
'''))

# ─── Detector ──────────────────────────────────────────────────────────────
cells.append(md("""## 6. The pad-scar detector

Five steps, each encoding one physical claim. See the docstring for rationale.

**This is the function to iterate on.** The rest of the notebook is plumbing."""))

cells.append(code('''def detect_pad_scars(
    dem,            # bare-earth elevation, meters, NaN where nodata
    slope,          # degrees, NaN where nodata
    roughness,      # std-dev of slope in ~5 m window
    local_relief,   # elev range in ~10 m window (meters)
    hand,           # height above nearest drainage (meters)
    lrm,            # Local Relief Model, meters (Hesse 2010)
    quality_mask,   # uint8: 1 = trustworthy, 0 = low density
    transform,      # rasterio affine transform
    crs,            # rasterio CRS
    *,
    slope_max          = 5.0,    # deg    — pad surface is flat
    roughness_max      = 1.0,    # stddev° — engineered surface is smooth
    relief_max         = 1.5,    # m      — pad has low internal relief
    lrm_max            = 0.3,    # m      — cell is within 30 cm of local mean elev
    hand_min           = 1.0,    # m      — exclude stream cells
    hand_max           = 60.0,   # m      — exclude ridge tops
    surround_inner_m   = 10,     # inner radius of contrast annulus
    surround_outer_m   = 40,     # outer radius of contrast annulus
    lrm_ring_std_min   = 0.30,   # m      — surrounding LRM std must exceed this
    area_min_m2        = 100,    # smallest plausible pad
    area_max_m2        = 5000,   # largest plausible pad
    elong_max          = 4.0,    # major/minor axis ratio
    compact_min        = 0.15,   # 4πA/P² — 1 is a circle
    aspect_align_min   = 0.3,    # min cos(angle) between TPI gradient and aspect
):
    """
    Detect pad-scar candidates from terrain derivatives.

    Architecture follows the 4-stage consensus from `filtering_methods_wellpad.md`:
    Stage 1 terrain normalization via LRM, Stage 2 candidate extraction via
    thresholding + connected components, Stage 3 morphometric characterization,
    Stage 4 classification (rule-based here, no training data yet).

    Returns a GeoDataFrame of candidate polygons with attributes.
    """

    # Step 1 — Flat-patch seeds.
    # Four physical claims:
    #  (a) pad surface is tilted <5° from horizontal     → slope
    #  (b) pad surface is smooth (no micro-topography)    → roughness
    #  (c) pad has low internal relief                    → local_relief
    #  (d) pad cell is within 30 cm of its local mean     → |LRM|
    # Claim (d) is the new one. Note that LRM alone cannot distinguish flat
    # ground from a linearly tilted hillside — a linear slope has LRM = 0 too,
    # because a mean filter cancels linear trends. So slope is still required.
    seed = (
        (slope        < slope_max)     &
        (roughness    < roughness_max) &
        (local_relief < relief_max)    &
        (np.abs(lrm)  < lrm_max)       &
        (hand >= hand_min) & (hand <= hand_max) &
        (quality_mask == 1)
    )
    seed &= ~np.isnan(slope) & ~np.isnan(hand) & ~np.isnan(lrm)

    # Step 2 — Surrounding-terrain contrast (the key discriminator).
    # The engineered signature of a pad is a flat interior surrounded by
    # cut-and-fill discontinuities — the cut bank on the uphill side produces
    # strongly negative LRM, the fill edge on the downhill side produces
    # strongly positive LRM. So the surrounding LRM has high standard
    # deviation, regardless of whether the pad is in open terrain or forest.
    #
    # This replaces the old surrounding-slope-mean criterion. We also ring
    # _around_ each cell (10–40 m) rather than including the cell itself,
    # because the cell's own LRM is ~0 (we just seeded on it).
    lrm_filled = np.where(np.isnan(lrm), 0.0, lrm).astype("float32")
    valid_mask = (~np.isnan(lrm)).astype("float32")

    def _ring_stat(arr, mask_arr, r_in, r_out, sq_arr=None):
        """
        Compute annular mean (and optionally annular mean of a second array,
        e.g., squared values for a variance calculation) via a pair of box
        filters. Square windows approximate disks well enough at this scale.
        """
        w_out = 2 * r_out + 1
        w_in  = 2 * r_in  + 1
        out_sum  = ndi.uniform_filter(arr,      size=w_out, mode="reflect") * w_out**2
        in_sum   = ndi.uniform_filter(arr,      size=w_in,  mode="reflect") * w_in**2
        out_cnt  = ndi.uniform_filter(mask_arr, size=w_out, mode="reflect") * w_out**2
        in_cnt   = ndi.uniform_filter(mask_arr, size=w_in,  mode="reflect") * w_in**2
        mean = np.where(out_cnt - in_cnt > 0,
                        (out_sum - in_sum) / np.maximum(out_cnt - in_cnt, 1e-6),
                        0.0)
        if sq_arr is None:
            return mean.astype("float32"), None
        out_sq = ndi.uniform_filter(sq_arr, size=w_out, mode="reflect") * w_out**2
        in_sq  = ndi.uniform_filter(sq_arr, size=w_in,  mode="reflect") * w_in**2
        sq_mean = np.where(out_cnt - in_cnt > 0,
                           (out_sq - in_sq) / np.maximum(out_cnt - in_cnt, 1e-6),
                           0.0)
        var = np.maximum(sq_mean - mean * mean, 0.0)
        return mean.astype("float32"), np.sqrt(var).astype("float32")

    _, lrm_ring_std = _ring_stat(
        lrm_filled, valid_mask,
        surround_inner_m, surround_outer_m,
        sq_arr=lrm_filled * lrm_filled,
    )
    seed &= lrm_ring_std > lrm_ring_std_min

    # Step 2b — Aspect-alignment rasters (computed once, used per-candidate).
    #
    # Physical claim: a pad's cut-and-fill geometry is aligned with the
    # hillslope aspect — the cut bank faces uphill, the fill faces downhill.
    # Natural benches, structural terraces, and DEM artifacts have no such
    # consistent relationship.
    #
    # Implementation: compute (a) aspect = direction of steepest descent
    # from the DEM, and (b) TPI gradient direction = direction of steepest
    # TPI increase (from cut toward fill). For a real pad the two should
    # agree. We measure agreement as cos(angle_diff) — 1.0 = perfect
    # alignment, 0 = perpendicular, -1 = anti-aligned.
    dem_filled = np.where(np.isnan(dem), np.nanmean(dem), dem).astype("float32")
    dy_dem = ndi.sobel(dem_filled, axis=0, mode="nearest") / 8.0
    dx_dem = ndi.sobel(dem_filled, axis=1, mode="nearest") / 8.0
    aspect = np.arctan2(-dy_dem, -dx_dem)  # direction of steepest DESCENT

    tpi = dem_filled - ndi.uniform_filter(dem_filled, size=15, mode="reflect")
    dy_tpi = ndi.sobel(tpi, axis=0, mode="nearest") / 8.0
    dx_tpi = ndi.sobel(tpi, axis=1, mode="nearest") / 8.0
    tpi_grad_dir = np.arctan2(dy_tpi, dx_tpi)  # direction of steepest TPI INCREASE

    angle_diff = np.abs(tpi_grad_dir - aspect)
    angle_diff = np.minimum(angle_diff, 2 * np.pi - angle_diff)
    aspect_alignment = np.cos(angle_diff)  # 1 = aligned, 0 = perp, -1 = anti

    # Step 3 — Morphological cleanup.
    # Opening first (remove noise), then closing (fill gaps) — per literature
    # recommendation, this avoids closing-first bridging noise into real features.
    cleaned = opening(seed, disk(1))
    cleaned = closing(cleaned, disk(2))
    cleaned = remove_small_objects(cleaned, min_size=int(area_min_m2 * 0.6))

    # Step 4 — Label and filter by shape + aspect alignment.
    # Area: 100–5000 m² (covers cable-tool pads through mid-century rotary pads).
    # Elongation: reject road beds (≤ 4 major/minor axis ratio).
    # Compactness: reject filamentous drainage features (≥ 0.15 of circle).
    # Aspect alignment: mean cos(TPI_grad_dir − aspect) over the candidate
    #   must exceed threshold. Candidates on flat terrain (mean slope < 3°
    #   in the ring) skip this check because aspect is undefined there.
    labels = label(cleaned, connectivity=2)
    kept_ids = []
    for r in regionprops(labels):
        if not (area_min_m2 <= r.area <= area_max_m2):
            continue
        if r.axis_minor_length > 0:
            elong = r.axis_major_length / r.axis_minor_length
        else:
            elong = np.inf
        if elong > elong_max:
            continue
        compactness = (4 * np.pi * r.area) / (r.perimeter ** 2) if r.perimeter > 0 else 0
        if compactness < compact_min:
            continue

        # Aspect-alignment check (per-candidate, not per-pixel)
        region_mask = (labels == r.label)
        mean_align = float(np.nanmean(aspect_alignment[region_mask]))
        # Only enforce if surrounding terrain has meaningful slope
        mean_surr_slope = float(np.nanmean(slope[
            ndi.binary_dilation(region_mask, disk(15)) & ~region_mask
        ])) if slope is not None else 0.0
        if mean_surr_slope > 3.0 and mean_align < aspect_align_min:
            continue

        kept_ids.append(r.label)

    keep_mask = np.isin(labels, kept_ids)

    # Step 5 — Vectorize and attach attributes sampled at each polygon centroid.
    records = []
    for geom_json, _ in rio_shapes(
        keep_mask.astype("uint8"),
        mask=keep_mask,
        transform=transform,
        connectivity=8,
    ):
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

        # Mean aspect alignment over the polygon pixels
        # (centroid-pixel approximation for scalar attrs, but alignment
        #  is averaged over the full region to get the feature-level signal)
        poly_label = labels[row, col]
        if poly_label > 0:
            rmask = (labels == poly_label)
            mean_align = float(np.nanmean(aspect_alignment[rmask]))
        else:
            mean_align = float(aspect_alignment[row, col])

        records.append({
            "geometry":      geom,
            "area_m2":       float(geom.area),
            "perimeter_m":   float(perim),
            "compactness":   float(compact),
            "slope":         _get(slope),
            "roughness":     _get(roughness),
            "local_relief":  _get(local_relief),
            "hand":          _get(hand),
            "lrm":           _get(lrm),
            "lrm_ring_std":  float(lrm_ring_std[row, col]),
            "aspect_align":  mean_align,
        })

    return gpd.GeoDataFrame(records, crs=crs)
'''))

# ─── Run detector ──────────────────────────────────────────────────────────
cells.append(md("""## 7. Run the detector"""))

cells.append(code('''with rasterio.open(SUB_DEM) as src:
    dem_arr = src.read(1).astype("float32")
    dem_arr[dem_arr == src.nodata] = np.nan

pads = detect_pad_scars(
    dem          = dem_arr,
    slope        = slope_arr,
    roughness    = rough_arr,
    local_relief = relief_arr,
    hand         = hand_arr,
    lrm          = lrm_arr,
    quality_mask = qmask_arr,
    transform    = TRANSFORM,
    crs          = CRS,
)

OUT_GPKG = SUB / "features_A_pads.gpkg"
if len(pads) > 0:
    pads.to_file(OUT_GPKG, layer="pads", driver="GPKG")

print(f"{len(pads)} pad candidates")
if len(pads) > 0:
    print()
    print(pads[["area_m2", "compactness", "slope", "lrm",
                "lrm_ring_std", "aspect_align"]].describe().round(2).to_string())
'''))

# ─── Visualize ─────────────────────────────────────────────────────────────
cells.append(md("""## 8. Visualize

Hillshade background, candidates outlined in orange, wells as cyan dots."""))

cells.append(code('''HSHADE = SUB / "hillshade.tif"
if not HSHADE.exists():
    wbt.multidirectional_hillshade(dem=str(SUB_DEM), output=str(HSHADE))

with rasterio.open(HSHADE) as src:
    hs = src.read(1).astype("float32")

inv = ~TRANSFORM
wells_px = np.array([inv * (p.x, p.y) for p in wells_sub.geometry])

fig, ax = plt.subplots(figsize=(12, 12))
ax.imshow(hs, cmap="gray")
ax.scatter(wells_px[:, 0], wells_px[:, 1], s=3, c="cyan", alpha=0.6,
           label=f"{len(wells_sub)} wells")

for _, row in pads.iterrows():
    if row.geometry is None or row.geometry.is_empty:
        continue
    xs, ys = row.geometry.exterior.xy
    px = [inv * (x, y) for x, y in zip(xs, ys)]
    ax.plot([p[0] for p in px], [p[1] for p in px], color="orange", linewidth=1.4)

ax.set_title(f"Pad-scar candidates — {len(pads)} polygons over {len(wells_sub)} wells")
ax.legend(loc="upper right")
ax.axis("off")
plt.tight_layout()
plt.show()
'''))

# ─── Zoom-in ───────────────────────────────────────────────────────────────
cells.append(md("""## 9. Zoom in on individual candidates

Pulls the top-N candidates (by area, descending) and crops a 50 m window around each. Shows hillshade + candidate outline + any wells that fall inside the zoom window, with the candidate's key attributes in the title.

Change `N_TO_SHOW` or the `sort_values` key to inspect different subsets. The zoom is always pixel-space — no `extent` / `origin` gymnastics, so polygon and raster stay aligned regardless of axis orientation."""))

cells.append(code('''N_TO_SHOW = 9    # top candidates to display
BUFFER_M  = 50   # meters around each candidate for the zoom window

if len(pads) == 0:
    print("No candidates to show")
else:
    # Pick which candidates to zoom in on — change the sort key to inspect others
    top = (
        pads
        .sort_values("area_m2", ascending=False)
        .head(N_TO_SHOW)
        .reset_index(drop=True)
    )

    with rasterio.open(HSHADE) as src:
        hs_full = src.read(1).astype("float32")

    # Also load slope for the optional secondary overlay
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

        # Bounding box in map coords with buffer
        minx, miny, maxx, maxy = geom.bounds
        minx -= BUFFER_M; maxx += BUFFER_M
        miny -= BUFFER_M; maxy += BUFFER_M

        # Convert map bounds to pixel bounds (top-left = (minx, maxy) in map)
        col_tl, row_tl = inv * (minx, maxy)
        col_br, row_br = inv * (maxx, miny)
        r0 = int(max(0, np.floor(row_tl)))
        r1 = int(min(hs_full.shape[0], np.ceil(row_br)))
        c0 = int(max(0, np.floor(col_tl)))
        c1 = int(min(hs_full.shape[1], np.ceil(col_br)))
        if r1 <= r0 or c1 <= c0:
            ax.axis("off"); continue

        # Hillshade crop
        hs_crop = hs_full[r0:r1, c0:c1]
        ax.imshow(hs_crop, cmap="gray")

        # Slope crop overlaid semi-transparently to show where the pad sits
        sl_crop = slope_full[r0:r1, c0:c1]
        ax.imshow(sl_crop, cmap="cividis", alpha=0.35, vmin=0, vmax=20)

        # Candidate polygon → local pixel coords (relative to crop origin)
        xs, ys = geom.exterior.xy
        poly_px = np.array([inv * (x, y) for x, y in zip(xs, ys)])
        poly_px[:, 0] -= c0
        poly_px[:, 1] -= r0
        ax.plot(poly_px[:, 0], poly_px[:, 1], color="orange",
                linewidth=2.0, zorder=4)
        ax.fill(poly_px[:, 0], poly_px[:, 1], color="orange", alpha=0.15, zorder=3)

        # Any wells inside the window
        window_poly = box(minx, miny, maxx, maxy)
        wells_in = wells_sub[wells_sub.geometry.within(window_poly)]
        if len(wells_in) > 0:
            wpx = np.array([inv * (p.x, p.y) for p in wells_in.geometry])
            wpx[:, 0] -= c0
            wpx[:, 1] -= r0
            ax.scatter(wpx[:, 0], wpx[:, 1], s=45, c="cyan",
                       edgecolor="black", linewidth=0.7, zorder=5)

        # Scale bar: 20 m in the bottom-left corner
        ax.plot([5, 25], [hs_crop.shape[0] - 10] * 2,
                color="white", linewidth=3, zorder=6)
        ax.text(15, hs_crop.shape[0] - 14, "20 m",
                color="white", fontsize=8, ha="center", va="bottom",
                zorder=6, fontweight="bold")

        ax.set_title(
            f"#{i+1}  area={row.area_m2:.0f} m²  compact={row.compactness:.2f}\\n"
            f"slope={row.slope:.1f}°  LRM={row.lrm:+.2f} m  "
            f"align={row.aspect_align:.2f}  {len(wells_in)} wells",
            fontsize=9,
        )
        ax.set_xticks([]); ax.set_yticks([])

    plt.suptitle(
        f"Top {min(N_TO_SHOW, len(top))} pad candidates by area — hillshade + slope overlay, "
        f"outlined in orange, wells in cyan",
        fontsize=12, y=0.995,
    )
    plt.tight_layout()
    plt.show()
'''))

# ─── Next steps ────────────────────────────────────────────────────────────
cells.append(md("""## Next steps

This notebook stops at "we have pad candidates." Things explicitly NOT done here:

- **Validation** — is the candidate set actually closer to wells than a covariate-matched null? That's a separate notebook/script.
- **RANSAC plane fit in a moving window** as the new step 1 seed criterion (structural upgrade to the detector — instead of per-pixel thresholds, test whether a local 20 m × 20 m neighborhood lies on a single plane).
- **Douglas-Peucker + minimum-area bounding rectangle** as a smarter shape filter (replace the crude `compactness` threshold with a real rectangularity test).
- **Other feature types** (access roads, borehole collapses, cellar pits, canopy disturbance, etc.)

Pick one and extend. The detector function in section 6 is the only piece of this notebook worth editing — everything else is plumbing for getting derivatives onto disk."""))

# ─── Serialize ─────────────────────────────────────────────────────────────
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.13"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NB.parent.mkdir(parents=True, exist_ok=True)
with open(NB, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Wrote {NB}")
print(f"  Cells: {len(cells)}  ({sum(1 for c in cells if c['cell_type']=='code')} code, {sum(1 for c in cells if c['cell_type']=='markdown')} markdown)")
