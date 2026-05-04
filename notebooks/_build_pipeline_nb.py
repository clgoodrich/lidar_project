"""Construct the consolidated WellSight pipeline notebook via nbformat
(avoids JSON escaping issues with direct file writes)."""
import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))


def code(text):
    cells.append(nbf.v4.new_code_cell(text))


# =============================================================================
md("""# WellSight — Consolidated Pipeline

End-to-end orphaned wellhead-pit detection, from raw LiDAR to ranked candidates.

**Inputs**
- `data/files/output3.las` — 2019 USGS 3DEP tile (1.5 km × 1.5 km, 9 M points)
- `data/files/older_files/USGS_LPC_PA_STATEWIDE_N_2006_2008_*.laz` — 2008 PAMAP tiles
- `data/derivatives/annotations/wellhead_pits.gpkg` — 90 expert pit annotations
- `data/derivatives/annotations/pads_truth.gpkg` — 88 pad polygons
- `data/derivatives/annotations/roads_truth.gpkg` — 96 road lines

**Stages**
1. Build clean 2008 merged LAS (reproject, unit convert, clip)
2. Generate 0.5 m derivative stack from 2019 LAS
3. Generate 1 m derivative stack from 2008 LAS
4. Load ground-truth annotations
5. Learn 3 morphological pit templates (PCA + KMeans on cutouts)
6. Generate ~13 k candidates via multi-template NCC + peak finding
7. Extract 88 features per candidate (2019 + 2008 stats, morphology, NCC, priors)
8. Train XGBoost + LightGBM ensemble with GroupKFold spatial CV, isotonic calibration
9. Save ranked candidates + per-threshold overlay PNGs

**Outputs**
- `data/files/output3_2008.las`
- 22 × `*_05.tif` + 8 × `*_2008_1m.tif` in `data/derivatives/`
- `pit_candidates_ensemble.gpkg` — ranked candidates with calibrated probability
- `pit_ensemble_thr{30..90}.png` — visual overlays per threshold
""")


# =============================================================================
md("## 1. Setup — paths, grid, helpers")

code("""import json, subprocess, shutil, time
from pathlib import Path

import numpy as np
import pandas as pd
import laspy
import rasterio
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from scipy.ndimage import uniform_filter
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from shapely.geometry import Point
from shapely import make_valid
import geopandas as gpd

from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score, precision_recall_curve
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.isotonic import IsotonicRegression
from skimage.feature import match_template, peak_local_max
import xgboost as xgb
import lightgbm as lgb
import matplotlib.pyplot as plt

DATA   = Path('data/files')
OLD    = DATA / 'older_files'
DERIV  = Path('data/derivatives')
ANNO   = Path('data/derivatives/annotations')
DERIV.mkdir(parents=True, exist_ok=True)

PDAL = shutil.which('pdal') or 'pdal'

# Pinned grid (output3 footprint, UTM 17N, metres)
X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0
CRS = 'EPSG:6346'

# 2019 0.5 m grid
RES19 = 0.5
W19 = int((X1 - X0) / RES19)
H19 = int((Y1 - Y0) / RES19)
T19 = from_origin(X0, Y1, RES19, RES19)

# 2008 1 m grid (PAMAP is too sparse for 0.5 m)
RES08 = 1.0
W08 = int((X1 - X0) / RES08)
H08 = int((Y1 - Y0) / RES08)
T08 = from_origin(X0, Y1, RES08, RES08)

LAS_2019 = DATA / 'output3.las'
LAS_2008 = DATA / 'output3_2008.las'

print(f'2019 grid: {W19}x{H19} @ {RES19} m   2008 grid: {W08}x{H08} @ {RES08} m')
""")


code("""def run_pipeline(pl, label, timeout=1800):
    \"\"\"Serialize a PDAL pipeline dict to a temp JSON and invoke the PDAL CLI.
    (The PDAL Python bindings do not function in this environment.)\"\"\"
    tmp = DERIV / f'_tmp_{label}.json'
    with open(tmp, 'w') as f:
        json.dump(pl, f, indent=2)
    t0 = time.time()
    r = subprocess.run([PDAL, 'pipeline', str(tmp)],
                       capture_output=True, text=True, timeout=timeout)
    print(f'[{label}] rc={r.returncode} in {time.time()-t0:.1f}s')
    if r.returncode != 0:
        print('STDERR:', r.stderr[-2000:])
        raise RuntimeError(label)
    tmp.unlink(missing_ok=True)


def write_tif(name, arr, T, W, H, dtype='float32', nd=-9999.0):
    a = arr.astype(dtype)
    if dtype.startswith('float'):
        a = np.where(np.isnan(a), nd, a).astype(dtype)
    with rasterio.open(DERIV / name, 'w', driver='GTiff',
                       height=H, width=W, count=1, dtype=dtype,
                       crs=CRS, transform=T, nodata=nd,
                       tiled=True, compress='deflate',
                       predictor=(3 if dtype.startswith('float') else 2)) as ds:
        ds.write(a, 1)


def read_tif(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32)
        nd = ds.nodata
    if nd is not None:
        a = np.where(a == nd, np.nan, a)
    return a
""")


# =============================================================================
md("""## 2. Build clean 2008 merged LAS

Merges the four PAMAP 2006–2008 tiles that intersect the output3 footprint,
reprojects EPSG:2271 (PA State Plane N, US ft) → EPSG:6346 (UTM 17N, m),
converts Z from US survey feet to metres, and crops to the tile bounds.
No vertical-alignment offset is applied; the 2008 and 2019 datasets are
kept independent.""")

code("""TILES_2008 = [
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_002958.laz',
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_002959.laz',
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003111.laz',
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003112.laz',
]
for t in TILES_2008:
    assert t.exists(), f'missing tile: {t}'

if not LAS_2008.exists():
    stages = []
    for t in TILES_2008:
        stages.append({'type': 'readers.las', 'filename': str(t),
                       'override_srs': 'EPSG:2271'})
    stages.extend([
        {'type': 'filters.reprojection', 'out_srs': 'EPSG:6346'},
        {'type': 'filters.assign', 'value': 'Z = Z * 0.3048006096'},
        {'type': 'filters.crop', 'bounds': f'([{X0},{X1}],[{Y0},{Y1}])'},
        {'type': 'writers.las', 'filename': str(LAS_2008),
         'a_srs': 'EPSG:6346', 'minor_version': 4,
         'dataformat_id': 6, 'forward': 'all', 'compression': 'false'},
    ])
    run_pipeline({'pipeline': stages}, 'build_output3_2008')
else:
    print(f'{LAS_2008} already exists; skipping merge')
""")


# =============================================================================
md("""## 3. 2019 derivative stack (0.5 m)

PDAL TIN-rasters for DEM + DSM, laspy binning for ground density and mean
intensity, WhiteboxTools for hillshade and slope, and scipy for the
curvature / terrain-position derivatives (LRM, TPI, roughness, local
relief, Yokoyama openness).""")


code("""def dem_pipeline(in_las, out_tif, RES, W, H):
    return {'pipeline': [
        {'type': 'readers.las', 'filename': str(in_las)},
        {'type': 'filters.range', 'limits': 'Classification[2:2]'},
        {'type': 'filters.delaunay'},
        {'type': 'filters.faceraster',
         'resolution': RES, 'origin_x': X0, 'origin_y': Y0,
         'width': W, 'height': H},
        {'type': 'writers.raster',
         'filename': str(DERIV / out_tif), 'data_type': 'float32'},
    ]}

# DEM: TIN over ground returns
run_pipeline(dem_pipeline(LAS_2019, 'dem_05.tif', RES19, W19, H19), 'dem_05')
dem = read_tif('dem_05.tif')
print(f'DEM: nan {100*np.isnan(dem).mean():.2f}%   z {np.nanmin(dem):.1f}..{np.nanmax(dem):.1f} m')

# DSM: max of first returns
run_pipeline({'pipeline': [
    {'type': 'readers.las', 'filename': str(LAS_2019)},
    {'type': 'filters.range', 'limits': 'ReturnNumber[1:1]'},
    {'type': 'writers.gdal', 'filename': str(DERIV / 'dsm_05.tif'),
     'output_type': 'max', 'resolution': RES19,
     'origin_x': X0, 'origin_y': Y0, 'width': W19, 'height': H19,
     'data_type': 'float32'},
]}, 'dsm_05')
dsm = read_tif('dsm_05.tif')

# CHM
chm = np.where(np.isnan(dsm) | np.isnan(dem), np.nan,
               np.maximum(dsm - dem, 0)).astype(np.float32)
write_tif('chm_05.tif', chm, T19, W19, H19)
""")


code("""# Ground density and mean intensity via laspy + bincount
print('reading LAS for density + intensity...')
las = laspy.read(str(LAS_2019))
xs = np.asarray(las.x); ys = np.asarray(las.y)
cls = np.asarray(las.classification)
ints = np.asarray(las.intensity).astype(np.float64)
gmask = (cls == 2)

col = np.floor((xs[gmask] - X0)/RES19).astype(np.int64)
row = np.floor((Y1 - ys[gmask])/RES19).astype(np.int64)
ok = (col >= 0)&(col < W19)&(row >= 0)&(row < H19)
flat_idx = (row[ok]*W19 + col[ok])

density = np.bincount(flat_idx, minlength=H19*W19).reshape(H19, W19).astype(np.uint16)
write_tif('ground_density_05.tif', density, T19, W19, H19, dtype='uint16', nd=0)

iv = ints[gmask][ok]
sum_i = np.bincount(flat_idx, weights=iv, minlength=H19*W19)
cnt   = np.bincount(flat_idx, minlength=H19*W19).astype(np.float64)
mean_i = np.full(H19*W19, np.nan, dtype=np.float32)
with np.errstate(invalid='ignore'):
    np.divide(sum_i, cnt, out=mean_i, where=cnt > 0)
write_tif('intensity_ground_05.tif', mean_i.reshape(H19, W19), T19, W19, H19)
del las, xs, ys, cls, ints
""")


code("""# Hillshade + slope via WhiteboxTools
import whitebox
wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(str(DERIV.resolve()))
wbt.set_verbose_mode(False)
wbt.hillshade(dem='dem_05.tif', output='hillshade_05.tif',
              azimuth=315.0, altitude=45.0)
wbt.slope(dem='dem_05.tif', output='slope_05.tif', units='degrees')
print('wrote hillshade_05, slope_05')
""")


code("""# scipy-based derivatives
def disk_kernel(r_cells):
    r = int(round(r_cells))
    y, x = np.ogrid[-r:r+1, -r:r+1]
    return (x*x + y*y) <= r*r


def nanmean_filter(a, kernel):
    valid = np.isfinite(a).astype(np.float32)
    a0 = np.where(valid.astype(bool), a, 0).astype(np.float32)
    kf = kernel.astype(np.float32)
    s = ndi.convolve(a0, kf, mode='nearest')
    c = ndi.convolve(valid, kf, mode='nearest')
    out = np.full_like(a, np.nan, dtype=np.float32)
    np.divide(s, c, out=out, where=c > 0)
    return out


def nanmax_disk(a, kernel):
    big = np.where(np.isfinite(a), a, -np.inf)
    r = ndi.maximum_filter(big, footprint=kernel, mode='nearest')
    return np.where(np.isfinite(r), r, np.nan).astype(np.float32)


def nanmin_disk(a, kernel):
    small = np.where(np.isfinite(a), a, np.inf)
    r = ndi.minimum_filter(small, footprint=kernel, mode='nearest')
    return np.where(np.isfinite(r), r, np.nan).astype(np.float32)


# Roughness: sigma(z) in 11x11 window (~5.5 m diameter)
WIN = 11
k = np.ones((WIN, WIN), dtype=np.float32)
v = np.isfinite(dem).astype(np.float32)
z0 = np.where(v.astype(bool), dem, 0).astype(np.float32)
s  = ndi.convolve(z0,    k, mode='nearest')
s2 = ndi.convolve(z0*z0, k, mode='nearest')
n  = ndi.convolve(v,     k, mode='nearest')
var = np.where(n > 1, (s2 - s*s/np.maximum(n,1))/np.maximum(n-1,1), np.nan)
roughness = np.sqrt(np.clip(var, 0, None)).astype(np.float32)
roughness[n < (WIN*WIN)] = np.nan
write_tif('roughness_11_05.tif', roughness, T19, W19, H19)

# Local relief in a 10 m disk
rk = disk_kernel(10 / RES19)
local_relief = (nanmax_disk(dem, rk) - nanmin_disk(dem, rk)).astype(np.float32)
write_tif('local_relief_10_05.tif', local_relief, T19, W19, H19)
""")


code("""# Local Relief Model at 4 scales
for size in (5, 11, 25, 51):
    valid = np.isfinite(dem).astype(np.float32)
    z0 = np.where(valid.astype(bool), dem, 0).astype(np.float32)
    sm = uniform_filter(z0, size=size, mode='nearest')
    sc = uniform_filter(valid, size=size, mode='nearest')
    smooth = np.where(sc > 0, sm/sc, np.nan)
    lrm = (dem - smooth).astype(np.float32)
    write_tif(f'lrm_{size}_05.tif', lrm, T19, W19, H19)


def tpi(z, radius_m):
    return (z - nanmean_filter(z, disk_kernel(radius_m / RES19))).astype(np.float32)


tpi_05 = tpi(dem,  5.0)
tpi_15 = tpi(dem, 15.0)
tpi_51 = tpi(dem, 25.5)
write_tif('tpi_05_05.tif', tpi_05, T19, W19, H19)
write_tif('tpi_15_05.tif', tpi_15, T19, W19, H19)
write_tif('tpi_51_05.tif', tpi_51, T19, W19, H19)

gy, gx = np.gradient(tpi_15, RES19)
write_tif('tpi_grad_mag_05.tif', np.hypot(gx, gy).astype(np.float32), T19, W19, H19)
write_tif('tpi_grad_dir_05.tif',
          (np.degrees(np.arctan2(gx, -gy)) % 360).astype(np.float32), T19, W19, H19)
""")


code("""# Yokoyama topographic openness, L = 25 m (50 cells at 0.5 m)
def openness(z, L_cells, cellsize):
    L = int(L_cells)
    dirs = [(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
    valid = np.isfinite(z)
    z0 = np.where(valid, z, 0).astype(np.float32)
    phi_sum = np.zeros_like(z, dtype=np.float32)
    psi_sum = np.zeros_like(z, dtype=np.float32)
    for dr, dc in dirs:
        step = cellsize * np.hypot(dr, dc)
        max_tan_up = np.full_like(z, -np.inf, dtype=np.float32)
        min_tan_dn = np.full_like(z,  np.inf, dtype=np.float32)
        for k in range(1, L+1):
            zs = np.roll(z0,    shift=(dr*k, dc*k), axis=(0,1))
            vs = np.roll(valid, shift=(dr*k, dc*k), axis=(0,1))
            if dr > 0:   vs[:dr*k, :] = False
            elif dr < 0: vs[dr*k:, :] = False
            if dc > 0:   vs[:, :dc*k] = False
            elif dc < 0: vs[:, dc*k:] = False
            tan_a = np.where(vs, (zs - z0)/(k*step), np.nan).astype(np.float32)
            np.fmax(max_tan_up, tan_a, out=max_tan_up, where=vs)
            np.fmin(min_tan_dn, tan_a, out=min_tan_dn, where=vs)
        a_max = np.arctan(np.where(np.isfinite(max_tan_up), max_tan_up, 0))
        a_min = np.arctan(np.where(np.isfinite(min_tan_dn), min_tan_dn, 0))
        phi_sum += (np.pi/2 - a_max).astype(np.float32)
        psi_sum += (np.pi/2 + a_min).astype(np.float32)
    phi = np.degrees(phi_sum/8).astype(np.float32)
    psi = np.degrees(psi_sum/8).astype(np.float32)
    phi[~valid] = np.nan
    psi[~valid] = np.nan
    return phi, psi


print('computing openness (slowest derivative)...')
op_pos, op_neg = openness(dem, L_cells=int(25/RES19), cellsize=RES19)
write_tif('openness_pos_05.tif', op_pos, T19, W19, H19)
write_tif('openness_neg_05.tif', op_neg, T19, W19, H19)
""")


# =============================================================================
md("""## 4. 2008 derivative stack (1 m)

Only the channels actually consumed by the classifier are built: DEM, DSM,
CHM, ground density, slope, LRM 5/11, TPI 15, negative openness. At 1 m
the 2008 PAMAP has ~0.35 ground pts/cell (vs 0.09 at 0.5 m).""")


code("""run_pipeline(dem_pipeline(LAS_2008, 'dem_2008_1m.tif', RES08, W08, H08),
             'dem_2008_1m')
dem08 = read_tif('dem_2008_1m.tif')

run_pipeline({'pipeline': [
    {'type': 'readers.las', 'filename': str(LAS_2008)},
    {'type': 'filters.range', 'limits': 'ReturnNumber[1:1]'},
    {'type': 'writers.gdal', 'filename': str(DERIV / 'dsm_2008_1m.tif'),
     'output_type': 'max', 'resolution': RES08,
     'origin_x': X0, 'origin_y': Y0, 'width': W08, 'height': H08,
     'data_type': 'float32'},
]}, 'dsm_2008_1m')
dsm08 = read_tif('dsm_2008_1m.tif')
chm08 = np.where(np.isnan(dsm08) | np.isnan(dem08), np.nan,
                 np.maximum(dsm08 - dem08, 0)).astype(np.float32)
write_tif('chm_2008_1m.tif', chm08, T08, W08, H08)

# Ground density (2008)
las = laspy.read(str(LAS_2008))
xs = np.asarray(las.x); ys = np.asarray(las.y); cls = np.asarray(las.classification)
gmask = (cls == 2)
col = np.floor((xs[gmask] - X0)/RES08).astype(np.int64)
row = np.floor((Y1 - ys[gmask])/RES08).astype(np.int64)
ok = (col >= 0)&(col < W08)&(row >= 0)&(row < H08)
flat_idx = (row[ok]*W08 + col[ok])
density = np.bincount(flat_idx, minlength=H08*W08).reshape(H08, W08).astype(np.uint16)
write_tif('ground_density_2008_1m.tif', density, T08, W08, H08, dtype='uint16', nd=0)
del las

wbt.slope(dem='dem_2008_1m.tif', output='slope_2008_1m.tif', units='degrees')

# LRM 5 + 11 at 1 m
for size in (5, 11):
    valid = np.isfinite(dem08).astype(np.float32)
    z0 = np.where(valid.astype(bool), dem08, 0).astype(np.float32)
    sm = uniform_filter(z0, size=size, mode='nearest')
    sc = uniform_filter(valid, size=size, mode='nearest')
    smooth = np.where(sc > 0, sm/sc, np.nan)
    lrm = (dem08 - smooth).astype(np.float32)
    write_tif(f'lrm_{size}_2008_1m.tif', lrm, T08, W08, H08)

# TPI 15 m at 1 m
def tpi_1m(z, radius_m):
    return (z - nanmean_filter(z, disk_kernel(radius_m / RES08))).astype(np.float32)
write_tif('tpi_15_2008_1m.tif', tpi_1m(dem08, 15.0), T08, W08, H08)

# Negative openness at 1 m, L = 25 cells
_, op_neg08 = openness(dem08, L_cells=int(25/RES08), cellsize=RES08)
write_tif('openness_neg_2008_1m.tif', op_neg08, T08, W08, H08)
""")


# =============================================================================
md("## 5. Load annotations (pits, pads, roads)")

code("""pits  = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pads  = gpd.read_file(ANNO / 'pads_truth.gpkg').to_crs(CRS)
roads = gpd.read_file(ANNO / 'roads_truth.gpkg').to_crs(CRS)
print(f'pits: {len(pits)}  pads: {len(pads)}  roads: {len(roads)}')

pit_xy   = np.array([[g.x, g.y] for g in pits.geometry])
tree_pit = cKDTree(pit_xy)
pads_clean  = gpd.GeoSeries([make_valid(g) for g in pads.geometry],  crs=CRS)
roads_clean = gpd.GeoSeries([make_valid(g) for g in roads.geometry], crs=CRS)
pad_union   = pads_clean.union_all()
road_union  = roads_clean.union_all()
""")


# =============================================================================
md("""## 6. Template learning — 3 morphological sub-types

Auto-snap each annotated pit to the local LRM_5 minimum (±2 m search),
extract 31×31 cutouts, mean-normalize, then cluster with PCA(5) +
KMeans(3) to produce one median template per sub-type.""")

code("""HALF19, INNER19, OUTER19 = 15, 5, 12
HALF08, INNER08, OUTER08 =  8, 3,  6
SNAP_R = 4
WIN_SIZE = 2*HALF19 + 1


def rc19(x, y):
    return int(round((Y1 - y)/RES19)), int(round((x - X0)/RES19))


def rc08(x, y):
    return int(round((Y1 - y)/RES08)), int(round((x - X0)/RES08))


lrm5 = read_tif('lrm_5_05.tif')

snapped_rc = []
for (x, y) in pit_xy:
    r0, c0 = rc19(x, y)
    r1, r2 = max(0, r0-SNAP_R), min(H19, r0+SNAP_R+1)
    c1, c2 = max(0, c0-SNAP_R), min(W19, c0+SNAP_R+1)
    win = lrm5[r1:r2, c1:c2]
    if np.isnan(win).all():
        snapped_rc.append((r0, c0)); continue
    f = np.nanargmin(win)
    dr, dc = divmod(f, win.shape[1])
    snapped_rc.append((r1+dr, c1+dc))

cutouts = []
for (r, c) in snapped_rc:
    r1, r2 = r-HALF19, r+HALF19+1
    c1, c2 = c-HALF19, c+HALF19+1
    if r1 < 0 or c1 < 0 or r2 > H19 or c2 > W19: continue
    w = lrm5[r1:r2, c1:c2].astype(np.float32)
    if np.isnan(w).mean() > 0.2: continue
    cutouts.append(w - np.nanmean(w))
cutouts = np.stack(cutouts, axis=0)
print(f'usable cutouts for clustering: {len(cutouts)}')

flat = np.nan_to_num(cutouts.reshape(len(cutouts), -1), nan=0)
Z   = PCA(n_components=5, random_state=0).fit_transform(flat)
km  = KMeans(n_clusters=3, n_init=10, random_state=0).fit(Z)

templates = np.stack([np.nanmedian(cutouts[km.labels_ == k], axis=0)
                      for k in range(3)], axis=0)
templates = np.nan_to_num(templates, nan=0)
print('cluster sizes:', np.bincount(km.labels_).tolist())
""")


# =============================================================================
md("""## 7. Candidate generation — multi-template NCC + peak finding

Run normalized cross-correlation for each of the 3 sub-type templates
across the full-tile LRM_5, take the per-pixel maximum, then use
`skimage.feature.peak_local_max` with NMS radius 5 m. Threshold is the
25th percentile of NCC scores at annotated pit locations.""")

code("""valid = ~np.isnan(lrm5)
img_f = np.where(valid, lrm5, 0).astype(np.float32)

per_tmp_scores = []
for kidx in range(3):
    s = match_template(img_f, templates[kidx].astype(np.float32), pad_input=True)
    s[~valid] = np.nan
    per_tmp_scores.append(s)
score_max = np.nanmax(np.stack(per_tmp_scores, axis=0), axis=0)

# Calibrate threshold from scores at annotated pits
ref = []
for (r, c) in snapped_rc:
    if 0 <= r < H19 and 0 <= c < W19:
        v = score_max[r, c]
        if np.isfinite(v): ref.append(v)
ref = np.array(ref)
THR = float(np.percentile(ref, 25))
print(f'pit-referenced NCC threshold (p25): {THR:.3f}')

peaks = peak_local_max(np.nan_to_num(score_max, nan=-1),
                       min_distance=int(round(5.0 / RES19)),
                       threshold_abs=THR)
rows, cols = peaks[:, 0], peaks[:, 1]
cand_xy = np.c_[X0 + (cols + 0.5) * RES19,
                Y1 - (rows + 0.5) * RES19]
print(f'candidates: {len(cand_xy)}')
""")


# =============================================================================
md("""## 8. Feature extraction (88 features per candidate)

Features are grouped into twelve blocks: 2019 depth/symmetry (6 channels ×
5 stats), 2019 surface/density/intensity, 2008 depth/symmetry (4 channels
× 5 stats), 2008 surface, temporal persistence, Gaussian-bowl morphology
on LRM_5, per-sub-type NCC scores, and pad/road priors.""")

code("""RAST19 = {name: read_tif(name) for name in [
    'dem_05.tif',
    'lrm_5_05.tif', 'lrm_11_05.tif', 'lrm_25_05.tif',
    'tpi_05_05.tif', 'tpi_15_05.tif',
    'openness_neg_05.tif', 'openness_pos_05.tif',
    'slope_05.tif', 'roughness_11_05.tif', 'local_relief_10_05.tif',
    'chm_05.tif', 'intensity_ground_05.tif', 'ground_density_05.tif',
]}
RAST08 = {name: read_tif(name) for name in [
    'dem_2008_1m.tif',
    'lrm_5_2008_1m.tif', 'lrm_11_2008_1m.tif',
    'tpi_15_2008_1m.tif',
    'openness_neg_2008_1m.tif',
    'slope_2008_1m.tif',
    'chm_2008_1m.tif', 'ground_density_2008_1m.tif',
]}

CHANS_D_19 = ['lrm_5_05.tif', 'lrm_11_05.tif', 'lrm_25_05.tif',
              'tpi_05_05.tif', 'tpi_15_05.tif', 'openness_neg_05.tif']
CHANS_S_19 = ['slope_05.tif', 'roughness_11_05.tif',
              'local_relief_10_05.tif', 'chm_05.tif']
CHANS_D_08 = ['lrm_5_2008_1m.tif', 'lrm_11_2008_1m.tif',
              'tpi_15_2008_1m.tif', 'openness_neg_2008_1m.tif']

yy, xx = np.ogrid[-HALF19:HALF19+1, -HALF19:HALF19+1]
RAD_19 = np.sqrt(xx*xx + yy*yy)
RING_IN_19  = RAD_19 <= INNER19
RING_RIM_19 = (RAD_19 >= OUTER19) & (RAD_19 <= HALF19)

yy8, xx8 = np.ogrid[-HALF08:HALF08+1, -HALF08:HALF08+1]
RAD_08 = np.sqrt(xx8*xx8 + yy8*yy8)
RING_IN_08  = RAD_08 <= INNER08
RING_RIM_08 = (RAD_08 >= OUTER08) & (RAD_08 <= HALF08)

RADIAL_BINS = [(0, 2), (2, 5), (5, 10), (10, 15)]
""")


code("""def stats_window(z, inner, rim):
    zi = z[inner]; zr = z[rim]
    if np.isfinite(zi).any() and np.isfinite(zr).any():
        mni = np.nanmin(zi); mi = np.nanmean(zi)
        mr  = np.nanmean(zr); sdi = np.nanstd(zi)
        return mni, mi, mr, mr - mni, sdi
    return (np.nan,) * 5


def radial_std(z, HALF, INNER):
    if not np.isfinite(z).any(): return np.nan
    angs = np.linspace(0, 2*np.pi, 8, endpoint=False)
    zs = []
    for a in angs:
        r_row = int(round(HALF + INNER * np.sin(a)))
        r_col = int(round(HALF + INNER * np.cos(a)))
        if 0 <= r_row < z.shape[0] and 0 <= r_col < z.shape[1]:
            v = z[r_row, r_col]
            if np.isfinite(v): zs.append(v)
    return float(np.std(zs)) if len(zs) >= 4 else np.nan


MORPH_KEYS = ['morph_depth', 'morph_sigma_major', 'morph_sigma_minor',
              'morph_aspect', 'morph_compactness',
              'morph_prof_r0', 'morph_prof_r1', 'morph_prof_r2', 'morph_prof_r3',
              'morph_radial_rho', 'morph_fit_residual']


def morphology_feats(win):
    if not np.isfinite(win).any():
        return {k: np.nan for k in MORPH_KEYS}
    w = np.where(np.isnan(win), 0, win).astype(np.float64)
    mass = np.clip(-w, 0, None); total = mass.sum()
    if total < 1e-6:
        return {k: np.nan for k in MORPH_KEYS}
    yyg, xxg = np.mgrid[0:win.shape[0], 0:win.shape[1]]
    cy = (mass * yyg).sum() / total
    cx = (mass * xxg).sum() / total
    vy = (mass * (yyg - cy)**2).sum() / total
    vx = (mass * (xxg - cx)**2).sum() / total
    cxy = (mass * (yyg - cy) * (xxg - cx)).sum() / total
    tr = vx + vy; det = vx*vy - cxy*cxy
    disc = max(tr*tr/4 - det, 0)
    lam1 = tr/2 + np.sqrt(disc); lam2 = tr/2 - np.sqrt(disc)
    sig_maj = float(np.sqrt(max(lam1, 1e-6)))
    sig_min = float(np.sqrt(max(lam2, 1e-6)))
    out = {
        'morph_depth': float(-np.nanmin(w)),
        'morph_sigma_major': sig_maj,
        'morph_sigma_minor': sig_min,
        'morph_aspect': sig_min/sig_maj,
        'morph_compactness': total / (np.pi*sig_maj*sig_min + 1e-6),
    }
    prof = []
    for (rmin, rmax) in RADIAL_BINS:
        m = (RAD_19 >= rmin) & (RAD_19 < rmax)
        vals = w[m]
        prof.append(float(vals.mean()) if len(vals) else np.nan)
    out['morph_prof_r0'], out['morph_prof_r1'] = prof[0], prof[1]
    out['morph_prof_r2'], out['morph_prof_r3'] = prof[2], prof[3]
    radii = np.array([np.mean(b) for b in RADIAL_BINS])
    out['morph_radial_rho'] = (float(spearmanr(radii, prof)[0])
                               if not np.any(np.isnan(prof)) else np.nan)
    theta = 0.0 if (cxy == 0 and vx == vy) else 0.5 * np.arctan2(2*cxy, (vx-vy))
    ct, st = np.cos(theta), np.sin(theta)
    A = out['morph_depth']
    gx = xxg - cx; gy = yyg - cy
    gxr =  ct*gx + st*gy; gyr = -st*gx + ct*gy
    g = -A * np.exp(-0.5 * ((gxr/sig_maj)**2 + (gyr/sig_min)**2))
    out['morph_fit_residual'] = float(np.sqrt(np.nanmean((w - g)**2))) / (A + 1e-6)
    return out


def feats_for(x, y):
    r19, c19 = rc19(x, y); r1, r2 = r19-HALF19, r19+HALF19+1; c1, c2 = c19-HALF19, c19+HALF19+1
    if r1 < 0 or c1 < 0 or r2 > H19 or c2 > W19: return None
    r08, c08 = rc08(x, y); r1b, r2b = r08-HALF08, r08+HALF08+1; c1b, c2b = c08-HALF08, c08+HALF08+1
    if r1b < 0 or c1b < 0 or r2b > H08 or c2b > W08: return None
    out = {}
    # 2019 depth channels (5 stats each)
    for ch in CHANS_D_19:
        w = RAST19[ch][r1:r2, c1:c2]
        mni, mi, mr, diff, _ = stats_window(w, RING_IN_19, RING_RIM_19)
        tag = ch.replace('.tif', '')
        out[f'{tag}_imin']=mni; out[f'{tag}_imean']=mi; out[f'{tag}_rmean']=mr
        out[f'{tag}_rdiff']=diff; out[f'{tag}_sym']=radial_std(w, HALF19, INNER19)
    # 2019 surface channels (2 stats each)
    for ch in CHANS_S_19:
        w = RAST19[ch][r1:r2, c1:c2]; wi = w[RING_IN_19]
        tag = ch.replace('.tif', '')
        out[f'{tag}_imean'] = float(np.nanmean(wi)) if np.isfinite(wi).any() else np.nan
        out[f'{tag}_wmax']  = float(np.nanmax(w))   if np.isfinite(w).any()  else np.nan
    wi = RAST19['intensity_ground_05.tif'][r1:r2, c1:c2]
    out['int_imean']   = float(np.nanmean(wi[RING_IN_19])) if np.isfinite(wi[RING_IN_19]).any() else np.nan
    out['int_rmean']   = float(np.nanmean(wi[RING_RIM_19])) if np.isfinite(wi[RING_RIM_19]).any() else np.nan
    out['int_nanfrac'] = float(np.isnan(wi).mean())
    dens = RAST19['ground_density_05.tif'][r1:r2, c1:c2]
    out['dens_imean'] = float(np.nanmean(dens[RING_IN_19]))
    out['dens_wmean'] = float(np.nanmean(dens))
    dem_w = RAST19['dem_05.tif'][r1:r2, c1:c2]
    _, _, _, dem_cut_19, _ = stats_window(dem_w, RING_IN_19, RING_RIM_19)
    out['dem_cut_m'] = dem_cut_19
    out['match_center'] = float(score_max[r19, c19])
    # 2008 depth channels
    for ch in CHANS_D_08:
        w = RAST08[ch][r1b:r2b, c1b:c2b]
        mni, mi, mr, diff, _ = stats_window(w, RING_IN_08, RING_RIM_08)
        tag = ch.replace('.tif', '').replace('_2008_1m', '_08')
        out[f'{tag}_imin']=mni; out[f'{tag}_imean']=mi; out[f'{tag}_rmean']=mr
        out[f'{tag}_rdiff']=diff; out[f'{tag}_sym']=radial_std(w, HALF08, INNER08)
    dem_w08 = RAST08['dem_2008_1m.tif'][r1b:r2b, c1b:c2b]
    _, _, _, dem_cut_08, _ = stats_window(dem_w08, RING_IN_08, RING_RIM_08)
    out['dem_cut_08_m'] = dem_cut_08
    slope08 = RAST08['slope_2008_1m.tif'][r1b:r2b, c1b:c2b][RING_IN_08]
    out['slope_08_imean'] = float(np.nanmean(slope08)) if np.isfinite(slope08).any() else np.nan
    chm08 = RAST08['chm_2008_1m.tif'][r1b:r2b, c1b:c2b]
    out['chm_08_wmax'] = float(np.nanmax(chm08)) if np.isfinite(chm08).any() else np.nan
    dens08 = RAST08['ground_density_2008_1m.tif'][r1b:r2b, c1b:c2b][RING_IN_08]
    out['dens_08_imean'] = float(np.nanmean(dens08))
    out['both_depths'] = -min(out.get('lrm_5_05_imin', 0) or 0,
                              out.get('lrm_5_08_imin', 0) or 0)
    out.update(morphology_feats(RAST19['lrm_5_05.tif'][r1:r2, c1:c2]))
    out['tmpl0_score'] = float(per_tmp_scores[0][r19, c19])
    out['tmpl1_score'] = float(per_tmp_scores[1][r19, c19])
    out['tmpl2_score'] = float(per_tmp_scores[2][r19, c19])
    out['tmpl_max']    = float(score_max[r19, c19])
    return out


print('extracting features (this takes a minute)...')
feat_list, keep_idx = [], []
for i, (x, y) in enumerate(cand_xy):
    f = feats_for(x, y)
    if f is not None:
        feat_list.append(f); keep_idx.append(i)
keep_idx = np.array(keep_idx)
X_df = pd.DataFrame(feat_list)
kept_xy = cand_xy[keep_idx]

pts_geo = gpd.GeoSeries([Point(x, y) for x, y in kept_xy], crs=CRS)
X_df['in_pad']      = pts_geo.within(pad_union).astype(np.int8).values
X_df['dist_pad_m']  = pts_geo.distance(pad_union).values.astype(np.float32)
X_df['dist_road_m'] = pts_geo.distance(road_union).values.astype(np.float32)
print(f'feature matrix: {X_df.shape}')
""")


# =============================================================================
md("""## 9. Labels and spatial groups

Positive: candidate within 10 m of any annotated pit. Spatial groups via
agglomerative clustering on the 90 pit points (GroupKFold prevents nearby
pits from leaking between train and test folds).""")

code("""POS_DIST_M = 10.0
N_GROUPS   = 8

dn, nearest_pit = tree_pit.query(kept_xy, k=1)
y = (dn <= POS_DIST_M).astype(np.int8)
print(f'positives: {y.sum()} / {len(y)}  ({y.mean():.2%})')

pit_group = AgglomerativeClustering(n_clusters=N_GROUPS).fit(pit_xy).labels_
groups = pit_group[nearest_pit]

X_arr = X_df.fillna(0).to_numpy(dtype=np.float32)
scale_pos = (len(y) - y.sum()) / max(y.sum(), 1)
""")


# =============================================================================
md("""## 10. Train ensemble — XGBoost + LightGBM, GroupKFold OOF, isotonic calibration""")

code("""def make_xgb():
    return xgb.XGBClassifier(
        objective='binary:logistic', tree_method='hist',
        n_estimators=500, max_depth=5, learning_rate=0.05,
        min_child_weight=2, subsample=0.8, colsample_bytree=0.8,
        reg_lambda=1.0, scale_pos_weight=scale_pos,
        random_state=0, n_jobs=-1)


def make_lgb():
    return lgb.LGBMClassifier(
        objective='binary', n_estimators=500, learning_rate=0.05,
        num_leaves=31, min_child_samples=5,
        subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
        scale_pos_weight=scale_pos, random_state=0, n_jobs=-1, verbose=-1)


def oof_fit(make_clf):
    oof = np.zeros(len(y), dtype=np.float32)
    gkf = GroupKFold(n_splits=min(5, N_GROUPS))
    for tr, te in gkf.split(X_arr, y, groups=groups):
        clf = make_clf()
        clf.fit(X_arr[tr], y[tr])
        oof[te] = clf.predict_proba(X_arr[te])[:, 1]
    return oof


p_xgb = oof_fit(make_xgb)
p_lgb = oof_fit(make_lgb)
print(f'XGB  ROC {roc_auc_score(y, p_xgb):.4f}   PR {average_precision_score(y, p_xgb):.4f}')
print(f'LGBM ROC {roc_auc_score(y, p_lgb):.4f}   PR {average_precision_score(y, p_lgb):.4f}')

p_avg = (p_xgb + p_lgb) / 2.0
iso   = IsotonicRegression(out_of_bounds='clip').fit(p_avg, y)
p_cal = iso.predict(p_avg).astype(np.float32)
print(f'AVG  ROC {roc_auc_score(y, p_avg):.4f}   PR {average_precision_score(y, p_avg):.4f}')
""")


# =============================================================================
md("## 11. Ranked candidates + per-threshold overlays")

code("""cand = gpd.GeoDataFrame({
    'proba':     p_cal,
    'proba_raw': p_avg,
    'geometry':  [Point(x, y) for x, y in kept_xy],
}, crs=CRS).sort_values('proba', ascending=False).reset_index(drop=True)

cand.to_file(DERIV / 'pit_candidates_pipeline.gpkg', driver='GPKG')
print(f'wrote pit_candidates_pipeline.gpkg ({len(cand)} rows)')

summary_rows = []
for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
    sub = cand[cand['proba'] >= thr]
    if len(sub) == 0:
        summary_rows.append((thr, 0, 0, 0, 0, 0.0)); continue
    sxy = np.c_[sub.geometry.x, sub.geometry.y]
    dn2, _ = tree_pit.query(sxy, k=1)
    hit10 = int((dn2 <= POS_DIST_M).sum())
    _, idx = tree_pit.query(sxy[dn2 <= POS_DIST_M], k=1) if hit10 else (None, np.array([]))
    pits_cov = len(np.unique(idx)) if hit10 else 0
    summary_rows.append((thr, len(sub), hit10, pits_cov,
                         len(sub) - hit10, hit10 / max(len(sub), 1)))

print(f'\\n{"thr":>5} {"n":>6} {"hits10":>7} {"pits_cov":>9} {"fp":>6} {"prec":>7}')
for thr, n, h, p, fp, pr in summary_rows:
    print(f'{thr:5.2f} {n:6d} {h:7d} {p:9d} {fp:6d} {pr:7.2%}')
""")


code("""# Per-threshold hillshade overlay PNGs
hs = read_tif('hillshade_05.tif')
for thr in [0.30, 0.50, 0.70, 0.90]:
    sub = cand[cand['proba'] >= thr]
    if len(sub) == 0: continue
    sxy = np.c_[sub.geometry.x, sub.geometry.y]
    dn2, _ = tree_pit.query(sxy, k=1)
    tp_xy = sxy[dn2 <= POS_DIST_M]
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.imshow(hs, cmap='gray', extent=[X0, X1, Y0, Y1])
    ax.scatter(pit_xy[:, 0], pit_xy[:, 1], s=40, c='red', marker='o',
               linewidths=0, label=f'annotated pits ({len(pit_xy)})')
    if len(tp_xy):
        ax.scatter(tp_xy[:, 0], tp_xy[:, 1], s=70, c='lime', marker='X',
                   linewidths=0, label=f'found pits ({len(tp_xy)})')
    ax.set_title(f'pipeline @ proba>={thr:.2f}  n={len(sub)}  TP={len(tp_xy)}')
    ax.legend(loc='lower left', fontsize=9)
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    fig.savefig(DERIV / f'pit_pipeline_thr{int(thr*100):02d}.png',
                dpi=130, bbox_inches='tight')
    plt.close(fig)
print('wrote threshold overlay PNGs')
""")


md("""---

**Pipeline complete.** The ranked candidates are in
`data/derivatives/pit_candidates_pipeline.gpkg`, and the overview PNGs
are `pit_pipeline_thr{30,50,70,90}.png` in the same folder. Load them in
QGIS over `hillshade_05.tif` for visual review.""")


# =============================================================================
nb.cells = cells
nb.metadata = {
    'kernelspec': {
        'display_name': 'Python 3',
        'language': 'python',
        'name': 'python3',
    },
    'language_info': {
        'name': 'python',
        'version': '3.13',
    },
}

out_path = Path('notebooks/wellsight_pipeline.ipynb')
with open(out_path, 'w', encoding='utf-8') as f:
    nbf.write(nb, f)
print(f'wrote {out_path}')
