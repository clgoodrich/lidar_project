"""Build the full 0.5 m raster stack from the stacked (2019 + 2008) LAS,
plus per-mission DEMs and the temporal-change channel.

Outputs (all 1 m grid origin (621000, 4596000), 3000x3000 cells, EPSG:6346):
  data/derivatives/dem_2019_05.tif
  data/derivatives/dem_2008_05.tif
  data/derivatives/dem_diff_05.tif         (2019 - 2008 ground; positive=higher in 2019, negative=subsidence)
  data/derivatives/dem_05.tif              (TIN over stacked cloud)
  data/derivatives/dsm_05.tif              (first-return max from 2019 only — DSM is meaningless across dates)
  data/derivatives/chm_05.tif
  data/derivatives/ground_density_05.tif   (stacked, ground returns per cell)
  data/derivatives/intensity_ground_05.tif (stacked ground returns mean intensity)
  data/derivatives/hillshade_05.tif        (WBT, az=315 alt=45)
  data/derivatives/slope_05.tif            (WBT)
  data/derivatives/roughness_11_05.tif     (Python sigma elev, 11x11 cells)
  data/derivatives/local_relief_10_05.tif  (max-min, 10 m disk)
  data/derivatives/lrm_5_05.tif, lrm_11_05.tif, lrm_25_05.tif, lrm_51_05.tif (uniform_filter, kernel size in cells)
  data/derivatives/tpi_05_05.tif, tpi_15_05.tif, tpi_51_05.tif  (circular kernels, radius in metres)
  data/derivatives/tpi_grad_mag_05.tif, tpi_grad_dir_05.tif    (gradient of tpi_15_05)
  data/derivatives/openness_pos_05.tif, openness_neg_05.tif    (Yokoyama, L=25 m)
"""
import json, subprocess, shutil, time
import numpy as np
import laspy
import rasterio
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from scipy.ndimage import uniform_filter
from pathlib import Path

DATA  = Path('data/files'); DERIV = Path('data/derivatives')
PDAL  = shutil.which('pdal') or 'pdal'
LAS_2019    = DATA / 'output3.las'
LAS_2008    = DATA / 'output3_2008.las'
LAS_STACKED = DATA / 'output3_stacked.las'

# Pinned grid: identical to the 1 m grid but 0.5 m cells
X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0
RES = 0.5
W = int((X1 - X0) / RES); H = int((Y1 - Y0) / RES)
T = from_origin(X0, Y1, RES, RES)
CRS = 'EPSG:6346'
print(f'grid: {W} x {H} cells @ {RES} m, snap=({X0},{Y0})-({X1},{Y1})')

def run_pipeline(pl, label, timeout=900):
    tmp = DERIV / f'_tmp_{label}.json'
    with open(tmp, 'w') as f: json.dump(pl, f, indent=2)
    t0 = time.time()
    r = subprocess.run([PDAL, 'pipeline', str(tmp)], capture_output=True, text=True, timeout=timeout)
    print(f'[{label}] rc={r.returncode} in {time.time()-t0:.1f}s')
    if r.returncode != 0:
        print('STDERR:', r.stderr[-2000:]); raise RuntimeError(label)
    tmp.unlink(missing_ok=True)

def write_tif(name, arr, dtype='float32', nd=-9999.0):
    a = arr.astype(dtype)
    if dtype.startswith('float'):
        a = np.where(np.isnan(a), nd, a).astype(dtype)
    with rasterio.open(DERIV / name, 'w', driver='GTiff', height=H, width=W, count=1,
                       dtype=dtype, crs=CRS, transform=T, nodata=nd,
                       tiled=True, compress='deflate',
                       predictor=(3 if dtype.startswith('float') else 2)) as ds:
        ds.write(a, 1)
    print('wrote', name)

# ============================================================================
# 1.  PDAL TIN DEMs at 0.5 m: per-mission and per-stacked
# ============================================================================
def dem_pipeline(in_las, out_tif):
    return {'pipeline': [
        {'type': 'readers.las', 'filename': str(in_las)},
        {'type': 'filters.range', 'limits': 'Classification[2:2]'},
        {'type': 'filters.delaunay'},
        {'type': 'filters.faceraster',
         'resolution': RES, 'origin_x': X0, 'origin_y': Y0, 'width': W, 'height': H},
        {'type': 'writers.raster', 'filename': str(DERIV / out_tif), 'data_type': 'float32'},
    ]}

run_pipeline(dem_pipeline(LAS_2019,    'dem_2019_05.tif'), 'dem_2019_05')
run_pipeline(dem_pipeline(LAS_2008,    'dem_2008_05.tif'), 'dem_2008_05')
run_pipeline(dem_pipeline(LAS_STACKED, 'dem_05.tif'),      'dem_stacked_05')

def read_tif(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a

dem_19 = read_tif('dem_2019_05.tif')
dem_08 = read_tif('dem_2008_05.tif')
dem_st = read_tif('dem_05.tif')
print(f'DEM 2019:    nan {100*np.isnan(dem_19).mean():.2f}%   z range {np.nanmin(dem_19):.1f}..{np.nanmax(dem_19):.1f}')
print(f'DEM 2008:    nan {100*np.isnan(dem_08).mean():.2f}%   z range {np.nanmin(dem_08):.1f}..{np.nanmax(dem_08):.1f}')
print(f'DEM stacked: nan {100*np.isnan(dem_st).mean():.2f}%   z range {np.nanmin(dem_st):.1f}..{np.nanmax(dem_st):.1f}')

# ============================================================================
# 2.  Temporal-change channel
# ============================================================================
diff = (dem_19 - dem_08).astype(np.float32)
write_tif('dem_diff_05.tif', diff)
print(f'dem_diff (2019-2008) p1/p50/p99: {np.nanpercentile(diff,1):+.2f} / {np.nanpercentile(diff,50):+.2f} / {np.nanpercentile(diff,99):+.2f} m')

# ============================================================================
# 3.  DSM (2019 only — DSM across dates is meaningless because canopy changed)
# ============================================================================
run_pipeline({'pipeline': [
    {'type': 'readers.las', 'filename': str(LAS_2019)},
    {'type': 'filters.range', 'limits': 'ReturnNumber[1:1]'},
    {'type': 'writers.gdal', 'filename': str(DERIV / 'dsm_05.tif'),
     'output_type': 'max', 'resolution': RES,
     'origin_x': X0, 'origin_y': Y0, 'width': W, 'height': H,
     'data_type': 'float32'},
]}, 'dsm_05')
dsm = read_tif('dsm_05.tif')
chm = np.where(np.isnan(dsm) | np.isnan(dem_st), np.nan, np.maximum(dsm - dem_st, 0)).astype(np.float32)
write_tif('chm_05.tif', chm)

# ============================================================================
# 4.  Ground density and intensity from STACKED cloud (Python bincount, exact)
# ============================================================================
print('reading stacked LAS for density+intensity...')
las = laspy.read(str(LAS_STACKED))
xs = np.asarray(las.x); ys = np.asarray(las.y)
cls = np.asarray(las.classification); ints = np.asarray(las.intensity).astype(np.float64)
gmask = (cls == 2)
col = np.floor((xs[gmask] - X0)/RES).astype(np.int64)
row = np.floor((Y1 - ys[gmask])/RES).astype(np.int64)
ok = (col >= 0)&(col < W)&(row >= 0)&(row < H)
flat_idx = (row[ok]*W + col[ok])
density = np.bincount(flat_idx, minlength=H*W).reshape(H, W).astype(np.uint16)
write_tif('ground_density_05.tif', density, dtype='uint16', nd=0)

iv = ints[gmask][ok]
sum_i = np.bincount(flat_idx, weights=iv, minlength=H*W)
cnt   = np.bincount(flat_idx, minlength=H*W).astype(np.float64)
mean_i = np.full(H*W, np.nan, dtype=np.float32)
with np.errstate(invalid='ignore'):
    np.divide(sum_i, cnt, out=mean_i, where=cnt > 0)
write_tif('intensity_ground_05.tif', mean_i.reshape(H, W))
del las

# ============================================================================
# 5.  WhiteboxTools hillshade + slope (on stacked DEM)
# ============================================================================
import whitebox
wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(str(DERIV.resolve()))
wbt.set_verbose_mode(False)
wbt.hillshade(dem='dem_05.tif', output='hillshade_05.tif', azimuth=315.0, altitude=45.0)
wbt.slope(dem='dem_05.tif', output='slope_05.tif', units='degrees')
print('wrote hillshade_05 + slope_05 (WBT)')
slope = read_tif('slope_05.tif')

# ============================================================================
# 6.  Python-side derivatives
# ============================================================================
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

# Roughness (sigma elev in 11 cells = 5.5 m diameter)
WIN = 11
k = np.ones((WIN, WIN), dtype=np.float32)
v = np.isfinite(dem_st).astype(np.float32)
z0 = np.where(v.astype(bool), dem_st, 0).astype(np.float32)
s = ndi.convolve(z0, k, mode='nearest'); s2 = ndi.convolve(z0*z0, k, mode='nearest')
n = ndi.convolve(v, k, mode='nearest')
var = np.where(n > 1, (s2 - s*s/np.maximum(n,1))/np.maximum(n-1,1), np.nan)
roughness = np.sqrt(np.clip(var, 0, None)).astype(np.float32)
roughness[n < (WIN*WIN)] = np.nan
write_tif('roughness_11_05.tif', roughness)

# Local relief in 10 m disk -> radius 20 cells at 0.5 m
rk = disk_kernel(10 / RES)
local_relief = (nanmax_disk(dem_st, rk) - nanmin_disk(dem_st, rk)).astype(np.float32)
write_tif('local_relief_10_05.tif', local_relief)

# LRM at multiple kernel sizes (size in cells; matches earlier convention)
for size in (5, 11, 25, 51):
    valid = np.isfinite(dem_st).astype(np.float32)
    z0 = np.where(valid.astype(bool), dem_st, 0).astype(np.float32)
    sm = uniform_filter(z0, size=size, mode='nearest'); sc = uniform_filter(valid, size=size, mode='nearest')
    smooth = np.where(sc > 0, sm/sc, np.nan)
    lrm = (dem_st - smooth).astype(np.float32)
    write_tif(f'lrm_{size}_05.tif', lrm)

# TPI at 5/15/51 m radius (circular kernels)
def tpi(z, radius_m):
    return (z - nanmean_filter(z, disk_kernel(radius_m / RES))).astype(np.float32)

tpi_05 = tpi(dem_st,  5.0)
tpi_15 = tpi(dem_st, 15.0)
tpi_51 = tpi(dem_st, 25.5)
write_tif('tpi_05_05.tif', tpi_05)
write_tif('tpi_15_05.tif', tpi_15)
write_tif('tpi_51_05.tif', tpi_51)

# TPI gradient (from tpi_15 at 0.5 m)
gy, gx = np.gradient(tpi_15, RES)
tpi_grad_mag = np.hypot(gx, gy).astype(np.float32)
tpi_grad_dir = (np.degrees(np.arctan2(gx, -gy)) % 360).astype(np.float32)
write_tif('tpi_grad_mag_05.tif', tpi_grad_mag)
write_tif('tpi_grad_dir_05.tif', tpi_grad_dir)

# Openness (Yokoyama) at L = 25 m -> 50 cells at 0.5 m
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
            zs = np.roll(z0, shift=(dr*k, dc*k), axis=(0,1))
            vs = np.roll(valid, shift=(dr*k, dc*k), axis=(0,1))
            if dr > 0: vs[:dr*k, :] = False
            elif dr < 0: vs[dr*k:, :] = False
            if dc > 0: vs[:, :dc*k] = False
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

print('computing openness at 0.5 m, L=25 m (50 cells, slowest step)...')
op_pos, op_neg = openness(dem_st, L_cells=int(25/RES), cellsize=RES)
write_tif('openness_pos_05.tif', op_pos)
write_tif('openness_neg_05.tif', op_neg)
print('done.')
