"""Build full derivative stack for output2.las (the tile east of output3).

Outputs use suffix:
  0.5 m channels from output2.las  ->  *_o2_05.tif
  2008 1 m clipped+merged LAS      ->  data/files/output2_2008.las
  2008 1 m channels                ->  *_o2_2008_1m.tif
"""
import json, subprocess, shutil, time
import numpy as np, laspy, rasterio
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from scipy.ndimage import uniform_filter
from pathlib import Path

DATA  = Path('data/files'); DERIV = Path('data/derivatives')
OLD   = DATA / 'older_files'
PDAL  = shutil.which('pdal') or 'pdal'

# output2 footprint
X0, Y0, X1, Y1 = 622500.0, 4594500.0, 624000.0, 4596000.0
RES19 = 0.5
W19 = int((X1 - X0) / RES19); H19 = int((Y1 - Y0) / RES19)
T19 = from_origin(X0, Y1, RES19, RES19)
RES08 = 1.0
W08 = int((X1 - X0) / RES08); H08 = int((Y1 - Y0) / RES08)
T08 = from_origin(X0, Y1, RES08, RES08)
CRS = 'EPSG:6346'

LAS_2019 = DATA / 'output2.las'
LAS_2008 = DATA / 'output2_2008.las'

def run_pipeline(pl, label, timeout=1200):
    tmp = DERIV / f'_tmp_{label}.json'
    with open(tmp, 'w') as f: json.dump(pl, f, indent=2)
    t0 = time.time()
    r = subprocess.run([PDAL, 'pipeline', str(tmp)], capture_output=True, text=True, timeout=timeout)
    print(f'[{label}] rc={r.returncode} in {time.time()-t0:.1f}s')
    if r.returncode != 0:
        print(r.stderr[-1500:]); raise RuntimeError(label)
    tmp.unlink(missing_ok=True)


def write_tif(name, arr, T, W, H, dtype='float32', nd=-9999.0):
    a = arr.astype(dtype)
    if dtype.startswith('float'):
        a = np.where(np.isnan(a), nd, a).astype(dtype)
    with rasterio.open(DERIV / name, 'w', driver='GTiff', height=H, width=W, count=1,
                       dtype=dtype, crs=CRS, transform=T, nodata=nd,
                       tiled=True, compress='deflate',
                       predictor=(3 if dtype.startswith('float') else 2)) as ds:
        ds.write(a, 1)
    print('wrote', name)


def read_tif(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a


# =============================================================================
# (1) Build output2_2008.las — clean merge of 2008 PAMAP over output2 footprint
# =============================================================================
TILES = [
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_002959.laz',
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003112.laz',
]
for t in TILES: assert t.exists(), t

print('=== building output2_2008.las ===')
stages = []
for t in TILES:
    stages.append({'type': 'readers.las', 'filename': str(t),
                   'override_srs': 'EPSG:2271'})
stages.append({'type': 'filters.reprojection', 'out_srs': 'EPSG:6346'})
stages.append({'type': 'filters.assign', 'value': 'Z = Z * 0.3048006096'})
stages.append({'type': 'filters.crop', 'bounds': f'([{X0},{X1}],[{Y0},{Y1}])'})
stages.append({'type': 'writers.las', 'filename': str(LAS_2008),
               'a_srs': 'EPSG:6346', 'minor_version': 4,
               'dataformat_id': 6, 'forward': 'all', 'compression': 'false'})
run_pipeline({'pipeline': stages}, 'output2_2008_merge')

# =============================================================================
# (2) 0.5 m DEM, DSM, CHM from output2.las
# =============================================================================
print('\n=== output2 0.5 m stack ===')
def dem_pipeline(in_las, out_tif, RES, W, H):
    return {'pipeline': [
        {'type': 'readers.las', 'filename': str(in_las)},
        {'type': 'filters.range', 'limits': 'Classification[2:2]'},
        {'type': 'filters.delaunay'},
        {'type': 'filters.faceraster',
         'resolution': RES, 'origin_x': X0, 'origin_y': Y0, 'width': W, 'height': H},
        {'type': 'writers.raster', 'filename': str(DERIV / out_tif), 'data_type': 'float32'},
    ]}

run_pipeline(dem_pipeline(LAS_2019, 'dem_o2_05.tif', RES19, W19, H19), 'dem_o2_05')
dem = read_tif('dem_o2_05.tif')
print(f'DEM o2: nan {100*np.isnan(dem).mean():.2f}%   z {np.nanmin(dem):.1f}..{np.nanmax(dem):.1f}')

run_pipeline({'pipeline': [
    {'type': 'readers.las', 'filename': str(LAS_2019)},
    {'type': 'filters.range', 'limits': 'ReturnNumber[1:1]'},
    {'type': 'writers.gdal', 'filename': str(DERIV / 'dsm_o2_05.tif'),
     'output_type': 'max', 'resolution': RES19,
     'origin_x': X0, 'origin_y': Y0, 'width': W19, 'height': H19,
     'data_type': 'float32'},
]}, 'dsm_o2_05')
dsm = read_tif('dsm_o2_05.tif')
chm = np.where(np.isnan(dsm) | np.isnan(dem), np.nan,
               np.maximum(dsm - dem, 0)).astype(np.float32)
write_tif('chm_o2_05.tif', chm, T19, W19, H19)

# density + intensity
print('reading output2.las for density + intensity...')
las = laspy.read(str(LAS_2019))
xs = np.asarray(las.x); ys = np.asarray(las.y)
cls = np.asarray(las.classification); ints = np.asarray(las.intensity).astype(np.float64)
gmask = (cls == 2)
col = np.floor((xs[gmask] - X0)/RES19).astype(np.int64)
row = np.floor((Y1 - ys[gmask])/RES19).astype(np.int64)
ok = (col >= 0)&(col < W19)&(row >= 0)&(row < H19)
flat_idx = (row[ok]*W19 + col[ok])
density = np.bincount(flat_idx, minlength=H19*W19).reshape(H19, W19).astype(np.uint16)
write_tif('ground_density_o2_05.tif', density, T19, W19, H19, dtype='uint16', nd=0)
iv = ints[gmask][ok]
sum_i = np.bincount(flat_idx, weights=iv, minlength=H19*W19)
cnt   = np.bincount(flat_idx, minlength=H19*W19).astype(np.float64)
mean_i = np.full(H19*W19, np.nan, dtype=np.float32)
with np.errstate(invalid='ignore'):
    np.divide(sum_i, cnt, out=mean_i, where=cnt > 0)
write_tif('intensity_ground_o2_05.tif', mean_i.reshape(H19, W19), T19, W19, H19)
del las

# WBT hillshade + slope
import whitebox
wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(str(DERIV.resolve()))
wbt.set_verbose_mode(False)
wbt.hillshade(dem='dem_o2_05.tif', output='hillshade_o2_05.tif', azimuth=315.0, altitude=45.0)
wbt.slope(   dem='dem_o2_05.tif', output='slope_o2_05.tif', units='degrees')
print('wrote hillshade_o2_05 + slope_o2_05')

# Python-side derivatives
def disk_kernel(r_cells):
    r = int(round(r_cells)); y, x = np.ogrid[-r:r+1, -r:r+1]
    return (x*x + y*y) <= r*r
def nanmean_filter(a, kernel):
    valid = np.isfinite(a).astype(np.float32)
    a0 = np.where(valid.astype(bool), a, 0).astype(np.float32)
    kf = kernel.astype(np.float32)
    s = ndi.convolve(a0, kf, mode='nearest'); c = ndi.convolve(valid, kf, mode='nearest')
    out = np.full_like(a, np.nan, dtype=np.float32)
    np.divide(s, c, out=out, where=c > 0); return out
def nanmax_disk(a, kernel):
    big = np.where(np.isfinite(a), a, -np.inf)
    r = ndi.maximum_filter(big, footprint=kernel, mode='nearest')
    return np.where(np.isfinite(r), r, np.nan).astype(np.float32)
def nanmin_disk(a, kernel):
    small = np.where(np.isfinite(a), a, np.inf)
    r = ndi.minimum_filter(small, footprint=kernel, mode='nearest')
    return np.where(np.isfinite(r), r, np.nan).astype(np.float32)

WIN = 11
k = np.ones((WIN, WIN), dtype=np.float32)
v = np.isfinite(dem).astype(np.float32)
z0 = np.where(v.astype(bool), dem, 0).astype(np.float32)
s = ndi.convolve(z0, k, mode='nearest'); s2 = ndi.convolve(z0*z0, k, mode='nearest')
n = ndi.convolve(v, k, mode='nearest')
var = np.where(n > 1, (s2 - s*s/np.maximum(n,1))/np.maximum(n-1,1), np.nan)
roughness = np.sqrt(np.clip(var, 0, None)).astype(np.float32)
roughness[n < (WIN*WIN)] = np.nan
write_tif('roughness_11_o2_05.tif', roughness, T19, W19, H19)

rk = disk_kernel(10 / RES19)
local_relief = (nanmax_disk(dem, rk) - nanmin_disk(dem, rk)).astype(np.float32)
write_tif('local_relief_10_o2_05.tif', local_relief, T19, W19, H19)

for size in (5, 11, 25, 51):
    valid = np.isfinite(dem).astype(np.float32)
    z0 = np.where(valid.astype(bool), dem, 0).astype(np.float32)
    sm = uniform_filter(z0, size=size, mode='nearest')
    sc = uniform_filter(valid, size=size, mode='nearest')
    smooth = np.where(sc > 0, sm/sc, np.nan)
    lrm = (dem - smooth).astype(np.float32)
    write_tif(f'lrm_{size}_o2_05.tif', lrm, T19, W19, H19)

def tpi(z, radius_m, RES):
    return (z - nanmean_filter(z, disk_kernel(radius_m / RES))).astype(np.float32)

tpi_05 = tpi(dem,  5.0, RES19)
tpi_15 = tpi(dem, 15.0, RES19)
tpi_51 = tpi(dem, 25.5, RES19)
write_tif('tpi_05_o2_05.tif', tpi_05, T19, W19, H19)
write_tif('tpi_15_o2_05.tif', tpi_15, T19, W19, H19)
write_tif('tpi_51_o2_05.tif', tpi_51, T19, W19, H19)

gy, gx = np.gradient(tpi_15, RES19)
tpi_grad_mag = np.hypot(gx, gy).astype(np.float32)
tpi_grad_dir = (np.degrees(np.arctan2(gx, -gy)) % 360).astype(np.float32)
write_tif('tpi_grad_mag_o2_05.tif', tpi_grad_mag, T19, W19, H19)
write_tif('tpi_grad_dir_o2_05.tif', tpi_grad_dir, T19, W19, H19)

def openness(z, L_cells, cellsize):
    L = int(L_cells)
    dirs = [(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
    valid = np.isfinite(z); z0 = np.where(valid, z, 0).astype(np.float32)
    phi_sum = np.zeros_like(z, dtype=np.float32); psi_sum = np.zeros_like(z, dtype=np.float32)
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
    phi = np.degrees(phi_sum/8).astype(np.float32); psi = np.degrees(psi_sum/8).astype(np.float32)
    phi[~valid] = np.nan; psi[~valid] = np.nan
    return phi, psi

print('computing openness ...')
op_pos, op_neg = openness(dem, L_cells=int(25/RES19), cellsize=RES19)
write_tif('openness_pos_o2_05.tif', op_pos, T19, W19, H19)
write_tif('openness_neg_o2_05.tif', op_neg, T19, W19, H19)

# =============================================================================
# (3) 2008 1 m derivatives for output2
# =============================================================================
print('\n=== output2 2008 1 m stack ===')
run_pipeline(dem_pipeline(LAS_2008, 'dem_o2_2008_1m.tif', RES08, W08, H08), 'dem_o2_2008_1m')
dem08 = read_tif('dem_o2_2008_1m.tif')
print(f'DEM 2008 (o2 1m): nan {100*np.isnan(dem08).mean():.2f}%   z {np.nanmin(dem08):.1f}..{np.nanmax(dem08):.1f}')

run_pipeline({'pipeline': [
    {'type': 'readers.las', 'filename': str(LAS_2008)},
    {'type': 'filters.range', 'limits': 'ReturnNumber[1:1]'},
    {'type': 'writers.gdal', 'filename': str(DERIV / 'dsm_o2_2008_1m.tif'),
     'output_type': 'max', 'resolution': RES08,
     'origin_x': X0, 'origin_y': Y0, 'width': W08, 'height': H08,
     'data_type': 'float32'},
]}, 'dsm_o2_2008_1m')
dsm08 = read_tif('dsm_o2_2008_1m.tif')
chm08 = np.where(np.isnan(dsm08)|np.isnan(dem08), np.nan, np.maximum(dsm08-dem08,0)).astype(np.float32)
write_tif('chm_o2_2008_1m.tif', chm08, T08, W08, H08)

# density (only need density for ground)
las = laspy.read(str(LAS_2008))
xs = np.asarray(las.x); ys = np.asarray(las.y); cls = np.asarray(las.classification)
gmask = (cls == 2)
col = np.floor((xs[gmask] - X0)/RES08).astype(np.int64)
row = np.floor((Y1 - ys[gmask])/RES08).astype(np.int64)
ok = (col >= 0)&(col < W08)&(row >= 0)&(row < H08)
flat_idx = (row[ok]*W08 + col[ok])
density = np.bincount(flat_idx, minlength=H08*W08).reshape(H08, W08).astype(np.uint16)
write_tif('ground_density_o2_2008_1m.tif', density, T08, W08, H08, dtype='uint16', nd=0)
del las

wbt.slope(dem='dem_o2_2008_1m.tif', output='slope_o2_2008_1m.tif', units='degrees')
print('wrote slope_o2_2008_1m')

# 2008 derivatives we need: lrm_5, lrm_11, tpi_15, openness_neg
for size in (5, 11):
    valid = np.isfinite(dem08).astype(np.float32)
    z0 = np.where(valid.astype(bool), dem08, 0).astype(np.float32)
    sm = uniform_filter(z0, size=size, mode='nearest')
    sc = uniform_filter(valid, size=size, mode='nearest')
    smooth = np.where(sc > 0, sm/sc, np.nan)
    lrm = (dem08 - smooth).astype(np.float32)
    write_tif(f'lrm_{size}_o2_2008_1m.tif', lrm, T08, W08, H08)

tpi15_08 = tpi(dem08, 15.0, RES08)
write_tif('tpi_15_o2_2008_1m.tif', tpi15_08, T08, W08, H08)

print('computing 2008 openness ...')
op_pos08, op_neg08 = openness(dem08, L_cells=int(25/RES08), cellsize=RES08)
write_tif('openness_neg_o2_2008_1m.tif', op_neg08, T08, W08, H08)

print('\nDONE.  output2 derivative stack ready.')
