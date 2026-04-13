"""
Build lidar_project_anomaly.ipynb scaffold.

Run once; regeneration overwrites the notebook. Intended to be run from the
project root or the notebooks directory — paths inside the notebook are absolute.
"""
import json
from pathlib import Path

NB_PATH = Path(r'C:/Users/colto/Documents/GitHub/lidar_project/notebooks/lidar_project_anomaly.ipynb')


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": text.splitlines(keepends=True)}


cells = []

# ─── Title + pivot rationale ───────────────────────────────────────────────
cells.append(md("""# Orphan Well Terrain Anomaly Detection — Western PA

**Pivot from point-based classification to feature-based anomaly detection.**

The earlier Random Forest / XGBoost / FFN pipeline converged at ~57% accuracy because the WPA-era well coordinates carry 30–100+ m positional error. Point extractions landed on approach slopes rather than pad surfaces, and the models learned the inverse signature (rougher, steeper terrain at well locations). See `lidar_project_characterization.ipynb` for the diagnosis.

This notebook inverts the logic: instead of asking "what does the terrain look like at this coordinate," it asks "where are the anomalous pad scars, access roads, borehole collapses, and other well-site features, and do they cluster near well records at rates above chance?" The well records are no longer per-sample labels — they are a spatial prior used to validate feature layers via association testing.

Feature types (from `CLAUDE.md`):

| | Feature | Priority |
|-|---------|----------|
| A | Pad Scars                              | Tier 1 |
| B | Access Roads and Haul Trails           | Tier 1 (first detector — negative openness is the single most effective derivative for linear anthropogenic features under forest) |
| C | Borehole Collapse Depressions          | Tier 2 |
| D | Cellar Pits                            | Tier 2 |
| E | Waste Pits                             | Tier 3 (co-location with A) |
| F | Tank Battery Foundations               | Tier 3 (co-location with A) |
| G | Spoil Piles                            | Tier 3 (co-location with A) |
| H | Canopy Disturbance                     | Tier 2 |
| I | Metallic Surface Signatures            | Tier 4 (waveform path unavailable — point format 6) |
| J | Drainage Disruptions                   | Tier 3 (co-location with A/B) |
| K | Absence of Expected Natural Features   | **disabled by default** |

Every feature type gets its own output layer. Layers are not fused into a single likelihood score — they are validated independently.
"""))

# ─── Phase 0 setup ─────────────────────────────────────────────────────────
cells.append(md("""## Phase 0 — Setup, Subarea, and Derivatives

### 0.0 Imports and paths"""))

cells.append(code('''# Core imports
import os
import json
import struct
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

import rasterio
from rasterio.windows import Window, from_bounds
from rasterio.transform import from_origin
from rasterio.merge import merge as rio_merge

import geopandas as gpd
from shapely.geometry import box, Point, Polygon

from scipy import ndimage as ndi

import whitebox

# ── Paths ─────────────────────────────────────────────────────────────────
ROOT = Path(r"C:/Users/colto/Documents/GitHub/lidar_project")
DATA = ROOT / "data"
LAZ_DIR     = DATA / "files"
DEM_MOSAIC  = DATA / "full_dem.tif"
WELLS_PATH  = DATA / "wells_with_features.shp"

# Derivatives root, split by scope (subarea for calibration, full for later)
DERIV = DATA / "derivatives"
SUB   = DERIV / "subarea"
FULL  = DERIV / "full"
SUB.mkdir(parents=True, exist_ok=True)
FULL.mkdir(parents=True, exist_ok=True)

# WhiteboxTools
wbt = whitebox.WhiteboxTools()
wbt.set_verbose_mode(False)
wbt.set_working_dir(str(DATA))

# Target CRS — UTM 17N
TARGET_CRS = "EPSG:26917"

# Colorblind-safe palettes (user is red-green colorblind — see CLAUDE.md)
CMAP_SEQ = "cividis"
CMAP_DIV = "coolwarm_r"  # blue depressions, warm ridges
'''))

cells.append(md("""### 0.1 Calibration subarea

Selected by scanning 5×5 km windows at 500 m stride across the full DEM interior, picking the window with the highest historic-well count. The chosen window contains **803 wells** in 25 km² (32 wells/km²), 0.08% nodata, and 174 m local relief (elevation 350–524 m) — plenty of Appalachian mixed terrain.

**Limitation documented:** CLAUDE.md asks for ≥50 GPS-quality post-1990 DEP wells in the subarea for positive-control validation. The DEP current wells dataset lives at `C:\\sp\\OilGasLocations_*.shp` per the characterization notebook — but that path does not exist on this machine. The subarea is currently selected by historic-well density alone. When the DEP dataset is available, re-run the selection with the GPS-quality constraint added."""))

cells.append(code('''# ── Calibration subarea bounding box (EPSG:26917) ────────────────────────
SUB_X0, SUB_Y0 = 619500.0, 4594000.0   # bottom-left
SUB_X1, SUB_Y1 = 624500.0, 4599000.0   # top-right
SUB_BBOX = (SUB_X0, SUB_Y0, SUB_X1, SUB_Y1)

# Clip the full DEM to the subarea and write a local copy for all subarea work
SUB_DEM = SUB / "dem.tif"

def clip_dem_to_subarea(src_path: Path, out_path: Path, bbox: tuple):
    """Clip a raster to the subarea bbox, preserving CRS and writing as a fresh GeoTIFF."""
    with rasterio.open(src_path) as src:
        window = from_bounds(*bbox, transform=src.transform)
        window = window.round_offsets().round_lengths()
        data = src.read(1, window=window)
        transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(
            height=data.shape[0],
            width=data.shape[1],
            transform=transform,
            crs=TARGET_CRS,
            compress="deflate",
            tiled=True,
        )
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data, 1)
    return out_path

if not SUB_DEM.exists():
    clip_dem_to_subarea(DEM_MOSAIC, SUB_DEM, SUB_BBOX)

with rasterio.open(SUB_DEM) as src:
    print(f"Subarea DEM:  {src.width} x {src.height} @ {src.res} m")
    print(f"  CRS:       {src.crs}")
    print(f"  Bounds:    {src.bounds}")
    print(f"  Nodata:    {src.nodata}")
    d = src.read(1)
    valid = d[d != src.nodata]
    print(f"  Elev:      {valid.min():.1f} – {valid.max():.1f} m")
    print(f"  Nodata %:  {(d == src.nodata).mean()*100:.2f}%")

# Wells in subarea
wells_all = gpd.read_file(WELLS_PATH).to_crs(TARGET_CRS)
sub_poly = box(*SUB_BBOX)
wells_sub = wells_all[wells_all.geometry.within(sub_poly)].copy()
print(f"\\nWells in subarea: {len(wells_sub)} (of {len(wells_all)} total)")
'''))

cells.append(md("""### 0.2 LAZ tile inventory

The project contains 176 LAZ tiles covering 21 × 19.5 km in western PA. **All tiles are LAS 1.4 point format 6** — so waveform derivatives (Feature Type I pulse width / echo ratio / rise time) are NOT available. Intensity-anomaly and angular-dependence signals are still available.

Tile size: **1500 × 1500 m** at ~10.2 pts/m² total return density. Generating software: QSI LiDAR Suite (2019 delivery). Intensity is NOT pre-normalized by scan angle — if we want to use intensity signals we'll need to normalize ourselves."""))

cells.append(code('''# Build LAZ tile index by reading LAS 1.4 public header blocks directly.
# Byte offsets (LAS 1.4 spec):
#   104: point_data_format_id (u8, low 6 bits — upper 2 are LAZ compression flags)
#   179: max_x, 187: min_x, 195: max_y, 203: min_y, 211: max_z, 219: min_z  (all f64)

def read_las_header_bbox(path: Path):
    with open(path, "rb") as fp:
        hdr = fp.read(256)
    assert hdr[:4] == b"LASF", f"not a LAS file: {path}"
    pt_fmt = hdr[104] & 0x3F
    max_x, min_x, max_y, min_y = struct.unpack_from("<dddd", hdr, 179)
    return (min_x, min_y, max_x, max_y, pt_fmt)

TILE_INDEX_CSV = DATA / "laz_tile_index.csv"
if not TILE_INDEX_CSV.exists():
    rows = []
    for f in sorted(LAZ_DIR.glob("*.laz")):
        mnx, mny, mxx, mxy, pf = read_las_header_bbox(f)
        rows.append((f.name, mnx, mny, mxx, mxy, pf))
    pd.DataFrame(rows, columns=["filename", "min_x", "min_y", "max_x", "max_y", "point_format"]).to_csv(TILE_INDEX_CSV, index=False)

tiles = pd.read_csv(TILE_INDEX_CSV)
print(f"N tiles: {len(tiles)}")
print(f"Point formats: {sorted(tiles.point_format.unique())}")

# Tiles intersecting subarea
mask = (tiles.max_x > SUB_X0) & (tiles.min_x < SUB_X1) & (tiles.max_y > SUB_Y0) & (tiles.min_y < SUB_Y1)
sub_tiles = tiles[mask].reset_index(drop=True)
print(f"\\nTiles intersecting subarea: {len(sub_tiles)}")
SUB_LAZ_PATHS = [LAZ_DIR / n for n in sub_tiles.filename]
'''))

# ─── 0.3 Quality mask ──────────────────────────────────────────────────────
cells.append(md("""### 0.3 Ground return point density quality mask

Built **before** any feature derivative. Cells with sparse ground returns have unreliable DEM interpolation, and every downstream detector consults this mask before flagging candidates. Not a detection feature — it is a per-cell confidence gate.

Uses WhiteboxTools `lidar_point_density` on ground-classified returns (class 2)."""))

cells.append(code('''# Ground point density raster: 1 m cells, class-2 returns only
PTD_RAW  = SUB / "point_density_raw.tif"
PTD_MASK = SUB / "point_density_mask.tif"

def mosaic_tile_rasters(tile_paths, out_path, bbox, nodata=-9999.0, res=1.0):
    """Mosaic a list of tile rasters to a single output, clipped to bbox."""
    srcs = [rasterio.open(p) for p in tile_paths]
    data, transform = rio_merge(srcs, bounds=bbox, res=(res, res), nodata=nodata)
    base_profile = srcs[0].profile.copy()
    for s in srcs:
        s.close()
    base_profile.update(
        height=data.shape[1], width=data.shape[2], transform=transform,
        crs=TARGET_CRS, compress="deflate", tiled=True, count=1,
        dtype="float32", nodata=nodata,
    )
    with rasterio.open(out_path, "w", **base_profile) as dst:
        dst.write(data[0].astype("float32"), 1)
    return out_path

if not PTD_RAW.exists():
    tile_rasters = []
    for laz in SUB_LAZ_PATHS:
        out = SUB / f"ptd_ground_{laz.stem}.tif"
        if not out.exists():
            # Keep class 2 (ground) only; exclude all others
            wbt.lidar_point_density(
                i=str(laz),
                output=str(out),
                returns="all",
                resolution=1.0,
                exclude_cls="0,1,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18",
            )
        tile_rasters.append(out)
    mosaic_tile_rasters(tile_rasters, PTD_RAW, SUB_BBOX)

# Build quality mask: ground point density >= threshold is "reliable"
DENSITY_THRESHOLD = 1.0  # ground pts per m² — tune visually in 0.6
with rasterio.open(PTD_RAW) as src:
    dens = src.read(1)
    profile = src.profile.copy()
    profile.update(dtype="uint8", nodata=255)
mask_arr = (dens >= DENSITY_THRESHOLD).astype("uint8")
mask_arr[dens < 0] = 255
with rasterio.open(PTD_MASK, "w", **profile) as dst:
    dst.write(mask_arr, 1)

valid_frac = (mask_arr == 1).mean()
print(f"Quality mask: {valid_frac*100:.1f}% of cells pass density threshold ({DENSITY_THRESHOLD} pts/m²)")
'''))

# ─── 0.4 Terrain-only derivatives ──────────────────────────────────────────
cells.append(md("""### 0.4 New terrain-only derivatives

- **Topographic openness** (positive + negative), Yokoyama et al. 2002 — WhiteboxTools `topographic_openness`. Negative openness is the single most effective derivative for linear anthropogenic features in forested terrain (road cuts, pipeline corridors, haul trails).
- **TPI gradient** at 15 m scale — spatial gradient magnitude + direction of TPI. Captures the asymmetric cut-and-fill geometry of pad scars that standard TPI averages to zero at a single scale.
- **HAND (Height Above Nearest Drainage)** — hydrologic conditioning → D8 pointer → flow accumulation → stream extraction → elevation above stream. Stratifies landscape by hydrologic position so "flat" means different things on a floodplain vs a hillslope.

Every moving-window operation uses the scipy-nan fill/restore pattern from the existing Stage 3 pipeline to avoid NaN propagation across nodata areas."""))

cells.append(code('''# ── Helpers ───────────────────────────────────────────────────────────────
def read_dem(path: Path):
    with rasterio.open(path) as src:
        dem = src.read(1).astype("float32")
        nodata = src.nodata
        profile = src.profile.copy()
    nd_mask = (dem == nodata) if nodata is not None else np.zeros_like(dem, dtype=bool)
    return dem, nd_mask, profile

def write_raster(path: Path, data: np.ndarray, profile_like: dict, dtype="float32", nodata=-9999.0):
    p = profile_like.copy()
    p.update(dtype=dtype, nodata=nodata, compress="deflate", tiled=True, count=1)
    out = data.copy()
    if np.issubdtype(out.dtype, np.floating):
        out[np.isnan(out)] = nodata
    with rasterio.open(path, "w", **p) as dst:
        dst.write(out.astype(dtype), 1)
'''))

cells.append(code('''# ── Topographic openness (WhiteboxTools) ──────────────────────────────────
OPEN_POS = SUB / "openness_positive.tif"
OPEN_NEG = SUB / "openness_negative.tif"

if not OPEN_POS.exists() or not OPEN_NEG.exists():
    wbt.topographic_openness(
        dem=str(SUB_DEM),
        pos_output=str(OPEN_POS),
        neg_output=str(OPEN_NEG),
        dist=50,  # 50-cell radius = 50 m at 1 m resolution — captures road cuts and pad edges
    )
print(f"Openness (pos): {OPEN_POS.exists()}")
print(f"Openness (neg): {OPEN_NEG.exists()}")
'''))

cells.append(code('''# ── TPI at 15 m scale + its gradient ──────────────────────────────────────
TPI15 = SUB / "tpi_15m.tif"
TPI15_GRAD_MAG = SUB / "tpi_15m_gradient_magnitude.tif"
TPI15_GRAD_DIR = SUB / "tpi_15m_gradient_direction.tif"

if not TPI15.exists():
    wbt.relative_topographic_position(
        dem=str(SUB_DEM),
        output=str(TPI15),
        filterx=15,
        filtery=15,
    )

if not TPI15_GRAD_MAG.exists() or not TPI15_GRAD_DIR.exists():
    tpi, tpi_nd, prof = read_dem(TPI15)
    tpi_filled = np.where(tpi_nd, 0.0, tpi).astype("float32")
    gy = ndi.sobel(tpi_filled, axis=0, mode="nearest") / 8.0
    gx = ndi.sobel(tpi_filled, axis=1, mode="nearest") / 8.0
    grad_mag = np.sqrt(gx**2 + gy**2)
    grad_dir = np.arctan2(gy, gx)  # radians in -pi..pi
    grad_mag[tpi_nd] = np.nan
    grad_dir[tpi_nd] = np.nan
    write_raster(TPI15_GRAD_MAG, grad_mag, prof)
    write_raster(TPI15_GRAD_DIR, grad_dir, prof)

print(f"TPI 15m gradient built")
'''))

cells.append(code('''# ── HAND: Height Above Nearest Drainage ───────────────────────────────────
BREACHED   = SUB / "dem_breached.tif"
D8_POINTER = SUB / "d8_pointer.tif"
D8_ACCUM   = SUB / "d8_accum.tif"
STREAMS    = SUB / "streams.tif"
HAND       = SUB / "hand.tif"

if not BREACHED.exists():
    wbt.breach_depressions_least_cost(
        dem=str(SUB_DEM),
        output=str(BREACHED),
        dist=100,
        fill=True,
    )

if not D8_POINTER.exists():
    wbt.d8_pointer(dem=str(BREACHED), output=str(D8_POINTER))

if not D8_ACCUM.exists():
    wbt.d8_flow_accumulation(
        i=str(BREACHED),
        output=str(D8_ACCUM),
        out_type="cells",
    )

if not STREAMS.exists():
    # 5000 cells upstream ≈ 5000 m² = 0.005 km² catchment.
    # Tune visually in 0.6 — too low gives dense networks, too high misses small drainages.
    wbt.extract_streams(
        flow_accum=str(D8_ACCUM),
        output=str(STREAMS),
        threshold=5000,
    )

if not HAND.exists():
    wbt.elevation_above_stream(
        dem=str(SUB_DEM),
        streams=str(STREAMS),
        output=str(HAND),
    )

print(f"HAND: {HAND.exists()}")
'''))

# ─── 0.5 Point-cloud-derived derivatives ───────────────────────────────────
cells.append(md("""### 0.5 Point-cloud-derived derivatives

- **Canopy Height Model (CHM)** — build a 1 m DSM from first returns, subtract the bare-earth DEM.
- **CHM anomaly** — local z-score of CHM in ~100 m window. Catches even-aged regrowth.
- **Canopy density** — fraction of returns above 2 m per cell. Short-dense regrowth and tall-sparse forest score differently.
- **Ground return intensity** — gridded all-return intensity (raw, not scan-angle normalized).
- **Intensity anomaly** — local z-score of intensity.
- **Single-return fraction** — clusters of single-return ground hits under forest canopy are candidates for specular surfaces (metal / water).

**Waveform derivatives (pulse width, echo ratio, rise time) are NOT available** — all 176 tiles are point format 6 without waveform packet data. Feature Type I must rely on intensity + single-return fraction alone."""))

cells.append(code('''# ── DSM and CHM ──────────────────────────────────────────────────────────
DSM_MOSAIC = SUB / "dsm_mosaic.tif"
CHM = SUB / "chm.tif"

if not CHM.exists():
    per_tile = []
    for laz in SUB_LAZ_PATHS:
        out = SUB / f"dsm_{laz.stem}.tif"
        if not out.exists():
            wbt.lidar_digital_surface_model(
                i=str(laz),
                output=str(out),
                resolution=1.0,
                radius=0.5,
            )
        per_tile.append(out)
    mosaic_tile_rasters(per_tile, DSM_MOSAIC, SUB_BBOX)
    with rasterio.open(DSM_MOSAIC) as sdsm, rasterio.open(SUB_DEM) as sdem:
        dsm = sdsm.read(1).astype("float32")
        dem = sdem.read(1).astype("float32")
        prof = sdsm.profile.copy()
    dem_nd = (dem == -32768.0)
    dsm_nd = (dsm == -9999.0) | np.isnan(dsm)
    chm = dsm - dem
    chm[dem_nd | dsm_nd] = np.nan
    chm[chm < 0] = 0  # treat below-ground noise as 0 m canopy
    write_raster(CHM, chm, prof)
print(f"CHM: {CHM.exists()}")
'''))

cells.append(code('''# ── CHM anomaly (local z-score, ~100 m window) ────────────────────────────
CHM_ANOM = SUB / "chm_anomaly.tif"
if not CHM_ANOM.exists():
    chm, chm_nd, prof = read_dem(CHM)
    win = 101  # ~100 m window at 1 m resolution
    chm_filled = np.where(chm_nd, 0.0, chm)
    local_mean = ndi.uniform_filter(chm_filled, size=win, mode="reflect")
    local_sq   = ndi.uniform_filter(chm_filled**2, size=win, mode="reflect")
    local_std  = np.sqrt(np.maximum(local_sq - local_mean**2, 1e-6))
    anom = (chm_filled - local_mean) / local_std
    anom[chm_nd] = np.nan
    write_raster(CHM_ANOM, anom, prof)
print(f"CHM anomaly: {CHM_ANOM.exists()}")
'''))

cells.append(code('''# ── Ground return intensity ───────────────────────────────────────────────
INTENSITY = SUB / "intensity.tif"
if not INTENSITY.exists():
    per_tile = []
    for laz in SUB_LAZ_PATHS:
        out = SUB / f"intensity_{laz.stem}.tif"
        if not out.exists():
            wbt.lidar_nearest_neighbour_gridding(
                i=str(laz),
                output=str(out),
                parameter="intensity",
                returns="all",
                resolution=1.0,
                radius=1.5,
                exclude_cls="0,1,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18",
            )
        per_tile.append(out)
    mosaic_tile_rasters(per_tile, INTENSITY, SUB_BBOX)
print(f"Intensity: {INTENSITY.exists()}")
'''))

cells.append(code('''# ── Intensity anomaly (local z-score) ─────────────────────────────────────
INT_ANOM = SUB / "intensity_anomaly.tif"
if not INT_ANOM.exists():
    ii, ii_nd, prof = read_dem(INTENSITY)
    win = 51  # ~50 m window
    ii_filled = np.where(ii_nd, 0.0, ii)
    local_mean = ndi.uniform_filter(ii_filled, size=win, mode="reflect")
    local_sq   = ndi.uniform_filter(ii_filled**2, size=win, mode="reflect")
    local_std  = np.sqrt(np.maximum(local_sq - local_mean**2, 1e-6))
    anom = (ii_filled - local_mean) / local_std
    anom[ii_nd] = np.nan
    write_raster(INT_ANOM, anom, prof)
print(f"Intensity anomaly: {INT_ANOM.exists()}")
'''))

cells.append(code('''# ── Single-return fraction ────────────────────────────────────────────────
SINGLE_RET_FRAC = SUB / "single_return_fraction.tif"
if not SINGLE_RET_FRAC.exists():
    per_tile_single = []
    per_tile_total = []
    for laz in SUB_LAZ_PATHS:
        o_single = SUB / f"ptd_single_{laz.stem}.tif"
        o_total  = SUB / f"ptd_total_{laz.stem}.tif"
        if not o_single.exists():
            wbt.lidar_point_density(i=str(laz), output=str(o_single),
                                    returns="single", resolution=1.0)
        if not o_total.exists():
            wbt.lidar_point_density(i=str(laz), output=str(o_total),
                                    returns="all", resolution=1.0)
        per_tile_single.append(o_single)
        per_tile_total.append(o_total)
    SINGLE_MOS = SUB / "ptd_single.tif"
    TOTAL_MOS  = SUB / "ptd_total.tif"
    mosaic_tile_rasters(per_tile_single, SINGLE_MOS, SUB_BBOX)
    mosaic_tile_rasters(per_tile_total, TOTAL_MOS, SUB_BBOX)
    with rasterio.open(SINGLE_MOS) as s, rasterio.open(TOTAL_MOS) as t:
        sr = s.read(1); tot = t.read(1); prof = s.profile.copy()
    frac = np.where(tot > 0, sr / np.maximum(tot, 1e-6), 0.0).astype("float32")
    frac[tot <= 0] = np.nan
    write_raster(SINGLE_RET_FRAC, frac, prof)
print(f"Single-return fraction: {SINGLE_RET_FRAC.exists()}")
'''))

cells.append(code('''# ── Canopy density (fraction of returns above 2 m per cell) ───────────────
# WhiteboxTools does not have a direct "fraction-above-N-m" tool.
# Stubbed here — Feature Type H will tighten this using a per-point height-above-ground
# pass (classify each return by height above the TIN bare earth, then grid the ratio).
CANOPY_DENSITY = SUB / "canopy_density.tif"
print(f"[TODO] Canopy density: Feature Type H will implement")
'''))

# ─── 0.6 sanity checks ─────────────────────────────────────────────────────
cells.append(md("""### 0.6 Derivative sanity check

Before any feature detector runs, render every new derivative on a hillshade and spot-check by eye. Confirm:
- No all-NaN layers (regression test for the scipy nan-propagation bug)
- No tile-seam artifacts
- Negative openness lights up roads and stream channels
- CHM shows sensible tree heights in forest, near-zero in clearings
- Intensity has reasonable dynamic range, not dominated by saturation"""))

cells.append(code('''HSHADE = SUB / "hillshade.tif"
if not HSHADE.exists():
    wbt.multidirectional_hillshade(dem=str(SUB_DEM), output=str(HSHADE))

def _show(ax, path, title, cmap=CMAP_SEQ, vmin=None, vmax=None, hillshade=None):
    with rasterio.open(path) as src:
        d = src.read(1).astype("float32")
        nd = src.nodata
    if nd is not None:
        d[d == nd] = np.nan
    if vmin is None or vmax is None:
        vmin, vmax = np.nanpercentile(d, [2, 98])
    if hillshade is not None:
        ax.imshow(hillshade, cmap="gray", alpha=0.6)
    im = ax.imshow(d, cmap=cmap, vmin=vmin, vmax=vmax,
                   alpha=0.75 if hillshade is not None else 1.0)
    ax.set_title(title, fontsize=10)
    ax.axis("off")
    plt.colorbar(im, ax=ax, fraction=0.046)

with rasterio.open(HSHADE) as src:
    hs = src.read(1).astype("float32")

panels = [
    (SUB_DEM,         "DEM",              CMAP_SEQ, None, None),
    (OPEN_POS,        "Openness (pos)",   CMAP_SEQ, None, None),
    (OPEN_NEG,        "Openness (neg)",   CMAP_DIV, None, None),
    (TPI15,           "TPI 15m",          CMAP_DIV, -3, 3),
    (TPI15_GRAD_MAG,  "TPI gradient mag", CMAP_SEQ, None, None),
    (HAND,            "HAND",             CMAP_SEQ, 0, 50),
    (CHM,             "CHM",              CMAP_SEQ, 0, 35),
    (CHM_ANOM,        "CHM anomaly",      CMAP_DIV, -3, 3),
    (INTENSITY,       "Intensity",        CMAP_SEQ, None, None),
    (INT_ANOM,        "Intensity anomaly",CMAP_DIV, -3, 3),
    (SINGLE_RET_FRAC, "Single-return frac",CMAP_SEQ, 0, 1),
    (PTD_RAW,         "Ground pt density",CMAP_SEQ, 0, 10),
]

fig, axes = plt.subplots(3, 4, figsize=(20, 15))
for (p, title, cmap, vmn, vmx), ax in zip(panels, axes.flat):
    if p.exists():
        _show(ax, p, title, cmap=cmap, vmin=vmn, vmax=vmx, hillshade=hs)
    else:
        ax.set_title(f"{title} (missing)"); ax.axis("off")
plt.tight_layout()
plt.savefig(SUB / "derivatives_preview.png", dpi=110, bbox_inches="tight")
plt.show()
'''))

# ─── Phase 1 stubs ─────────────────────────────────────────────────────────
cells.append(md("""## Phase 1 — Feature Detectors

Each detector produces a GeoPackage layer with: polygon geometry, feature type ID (A–K), area, mean values of contributing derivatives, geometric properties, nearest well distance, land-cover class (TODO, needs NLCD), slope class and HAND at centroid.

Layers are **never fused**."""))

cells.append(md("""### Feature Type B — Access Roads and Haul Trails (build first)

Threshold negative openness to isolate linear concavities, extract centerlines, filter by length / width / linearity, test for parallel positive-openness berms. First detector built because it exercises the full detection → candidate → validation loop, negative openness is the highest-value derivative for forested anthropogenic features, and roads are spatially larger and connective."""))

cells.append(code('''# ── Feature Type B: Access Road detector ──────────────────────────────────
# Implementation plan:
#   1. Read OPEN_NEG; compute robust z-score in a large window
#   2. Threshold at z < -1.5 (strongly concave relative to local terrain)
#   3. Require slope > 5° (exclude flat valley bottoms where channels dominate)
#   4. Skeletonize connected components → centerlines
#   5. Filter by length >= 30 m, width 2-6 m, linearity
#   6. Test for parallel positive-openness berms within 2-5 m perpendicular offset
#   7. Buffered-centerline polygons with attributes → GeoPackage
ROAD_CANDIDATES = SUB / "features_B_roads.gpkg"
print("[TODO] Feature Type B: Access Road detector — implement next")
'''))

cells.append(md("""### Feature Type A — Pad Scars"""))

cells.append(code('''# ── Feature Type A: Pad Scar detector ─────────────────────────────────────
# Implementation plan:
#   1. slope < 5°  AND  roughness < local 5th percentile  AND  local_relief < local 5th percentile
#   2. Connected components; filter area 100–5000 m² and compactness
#   3. HAND filter: mid-slope only (HAND > 5 m, exclude floodplains)
#   4. Cut-bank test: uphill edge should show high plan curvature (sharp concave break)
#   5. Polygon layer → GeoPackage
PAD_CANDIDATES = SUB / "features_A_pads.gpkg"
print("[TODO] Feature Type A: Pad Scar detector")
'''))

cells.append(md("""### Feature Types C–K (stubs)

Implement in priority tier order — see `outline.md`. Each follows the same pattern: apply detection criteria from CLAUDE.md § Feature Type N, build candidate polygons with attributes, run Phase 2 validation on the layer independently."""))

cells.append(code('''# Feature Type C — Borehole Collapse Depressions (Tier 2)
# Feature Type D — Cellar Pits                     (Tier 2)
# Feature Type H — Canopy Disturbance              (Tier 2)
# Feature Type E — Waste Pits                      (Tier 3, depends on A)
# Feature Type F — Tank Batteries                  (Tier 3, depends on A)
# Feature Type G — Spoil Piles                     (Tier 3, depends on A)
# Feature Type J — Drainage Disruptions            (Tier 3, depends on A/B)
# Feature Type I — Metallic Signatures             (Tier 4, waveform unavailable)
# Feature Type K — Absence of Natural Features     (disabled by default)
print("[TODO] Feature Types C–K")
'''))

# ─── Phase 2 ───────────────────────────────────────────────────────────────
cells.append(md("""## Phase 2 — Validation Framework

**Per feature type, not fused.** Do wells cluster near candidates of this type at rates above the covariate-matched null?

Procedure:
1. Search radii 50 / 100 / 150 / 200 m — find the radius at which association is strongest
2. Nearest-neighbor CDF + Ripley's cross-K as two independent test statistics
3. Covariate-matched null: background points stratified on slope class, HAND bin, (TODO: NLCD class)
4. Mandatory slicing: GPS-quality vs WPA, land cover, terrain class, decade
5. Positive control: GPS-quality DEP wells (missing — requires DEP dataset)
6. Negative control: well coordinates randomly offset by 500 m
7. Go / no-go decision per feature type"""))

cells.append(code('''# ── Validation framework stubs ────────────────────────────────────────────
def covariate_matched_null(wells, n_draw, stratify_rasters, subarea_bbox, seed=42):
    """Draw n_draw background points with covariate distributions matched to `wells`."""
    raise NotImplementedError("Phase 2")

def nearest_candidate_distance_cdf(wells, candidates):
    """For each well, distance to nearest candidate feature."""
    raise NotImplementedError("Phase 2")

def ripley_cross_k(wells, candidates, radii):
    """Cross-K function between wells and candidate features."""
    raise NotImplementedError("Phase 2")

def positive_control(detector_fn, gps_wells):
    """Run detector at known well locations, check candidate density."""
    raise NotImplementedError("Phase 2")

def negative_control(detector_fn, wells, offset_m=500, seed=42):
    """Run association test with randomly offset wells, expect null."""
    raise NotImplementedError("Phase 2")
'''))

# ─── Phase 3 + 4 ───────────────────────────────────────────────────────────
cells.append(md("""## Phase 3 — Output Product

Per-feature GeoPackage layers + a companion markdown/CSV summary table:

`feature_type | n_candidates | best_radius_m | p_value | pos_ctrl | neg_ctrl | notes`"""))

cells.append(md("""## Phase 4 — Scale to Full Mosaic

Only after the subarea produces a stable set of validated detectors. Thresholds are frozen at subarea calibration values — **do not tune against full-area results**."""))

# Serialize notebook
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.13"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NB_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Wrote notebook: {NB_PATH}")
print(f"  Cells: {len(cells)}")
