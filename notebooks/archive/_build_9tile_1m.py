"""Build full 1 m derivative stack for the 9-tile mosaic (4.5 km x 4.5 km).

Uses the already-merged output3_9tile.las.  4500x4500 grid @ 1 m.
Outputs suffixed _9t_1m.
"""
import json, subprocess, shutil, time
import numpy as np, laspy, rasterio
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from scipy.ndimage import uniform_filter
from pathlib import Path
import matplotlib.pyplot as plt

DATA  = Path('data/files'); DERIV = Path('data/derivatives')
PDAL  = shutil.which('pdal') or 'pdal'
LAS   = DATA / 'output3_9tile.las'
SFX   = '9t_1m'

X0, Y0, X1, Y1 = 619500.0, 4593000.0, 624000.0, 4597500.0
RES = 1.0
W = int((X1 - X0) / RES); H = int((Y1 - Y0) / RES)
T = from_origin(X0, Y1, RES, RES)
CRS = 'EPSG:6346'
print(f'grid: {W} x {H} cells @ {RES} m')

def run_pipeline(pl, label, timeout=3600):
    tmp = DERIV / f'_tmp_{label}.json'
    with open(tmp, 'w') as f: json.dump(pl, f, indent=2)
    t0 = time.time()
    r = subprocess.run([PDAL, 'pipeline', str(tmp)], capture_output=True, text=True, timeout=timeout)
    print(f'[{label}] rc={r.returncode} in {time.time()-t0:.1f}s')
    if r.returncode != 0:
        print(r.stderr[-2000:]); raise RuntimeError(label)
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

def read_tif(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a

# 1. DEM
run_pipeline({'pipeline': [
    {'type': 'readers.las', 'filename': str(LAS)},
    {'type': 'filters.range', 'limits': 'Classification[2:2]'},
    {'type': 'filters.delaunay'},
    {'type': 'filters.faceraster',
     'resolution': RES, 'origin_x': X0, 'origin_y': Y0, 'width': W, 'height': H},
    {'type': 'writers.raster', 'filename': str(DERIV / f'dem_{SFX}.tif'), 'data_type': 'float32'},
]}, f'dem_{SFX}')
dem = read_tif(f'dem_{SFX}.tif')
print(f'DEM: nan {100*np.isnan(dem).mean():.2f}%   z {np.nanmin(dem):.1f}..{np.nanmax(dem):.1f}')

# 2. DSM / CHM
run_pipeline({'pipeline': [
    {'type': 'readers.las', 'filename': str(LAS)},
    {'type': 'filters.range', 'limits': 'ReturnNumber[1:1]'},
    {'type': 'writers.gdal', 'filename': str(DERIV / f'dsm_{SFX}.tif'),
     'output_type': 'max', 'resolution': RES,
     'origin_x': X0, 'origin_y': Y0, 'width': W, 'height': H,
     'data_type': 'float32'},
]}, f'dsm_{SFX}')
dsm = read_tif(f'dsm_{SFX}.tif')
chm = np.where(np.isnan(dsm)|np.isnan(dem), np.nan, np.maximum(dsm-dem, 0)).astype(np.float32)
write_tif(f'chm_{SFX}.tif', chm)

# 3. Density + intensity
print('reading LAS for density + intensity...')
las = laspy.read(str(LAS))
xs = np.asarray(las.x); ys = np.asarray(las.y)
cls = np.asarray(las.classification); ints = np.asarray(las.intensity).astype(np.float64)
gmask = (cls == 2)
col = np.floor((xs[gmask] - X0)/RES).astype(np.int64)
row = np.floor((Y1 - ys[gmask])/RES).astype(np.int64)
ok = (col >= 0)&(col < W)&(row >= 0)&(row < H)
flat_idx = (row[ok]*W + col[ok])
density = np.bincount(flat_idx, minlength=H*W).reshape(H, W).astype(np.uint16)
write_tif(f'ground_density_{SFX}.tif', density, dtype='uint16', nd=0)
iv = ints[gmask][ok]
sum_i = np.bincount(flat_idx, weights=iv, minlength=H*W)
cnt   = np.bincount(flat_idx, minlength=H*W).astype(np.float64)
mean_i = np.full(H*W, np.nan, dtype=np.float32)
with np.errstate(invalid='ignore'):
    np.divide(sum_i, cnt, out=mean_i, where=cnt > 0)
write_tif(f'intensity_ground_{SFX}.tif', mean_i.reshape(H, W))
del las, xs, ys, cls, ints, iv, sum_i, cnt, mean_i, density

# 4. WBT
import whitebox
wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(str(DERIV.resolve()))
wbt.set_verbose_mode(False)
wbt.hillshade(dem=f'dem_{SFX}.tif', output=f'hillshade_{SFX}.tif', azimuth=315.0, altitude=45.0)
wbt.slope(   dem=f'dem_{SFX}.tif', output=f'slope_{SFX}.tif', units='degrees')
print(f'wrote hillshade_{SFX} + slope_{SFX}')

# 5. Python derivatives
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

# Roughness 5-cell (5m at 1m ~ matches 11-cell at 0.5m)
WIN = 5
k = np.ones((WIN, WIN), dtype=np.float32)
v = np.isfinite(dem).astype(np.float32)
z0 = np.where(v.astype(bool), dem, 0).astype(np.float32)
s = ndi.convolve(z0, k, mode='nearest'); s2 = ndi.convolve(z0*z0, k, mode='nearest')
n = ndi.convolve(v, k, mode='nearest')
var = np.where(n > 1, (s2 - s*s/np.maximum(n,1))/np.maximum(n-1,1), np.nan)
roughness = np.sqrt(np.clip(var, 0, None)).astype(np.float32)
roughness[n < (WIN*WIN)] = np.nan
write_tif(f'roughness_5_{SFX}.tif', roughness)

rk = disk_kernel(10 / RES)
local_relief = (nanmax_disk(dem, rk) - nanmin_disk(dem, rk)).astype(np.float32)
write_tif(f'local_relief_10_{SFX}.tif', local_relief)

# LRM — halved cell sizes from 0.5m convention
for size in (3, 5, 11, 25):
    valid = np.isfinite(dem).astype(np.float32)
    z0 = np.where(valid.astype(bool), dem, 0).astype(np.float32)
    sm = uniform_filter(z0, size=size, mode='nearest')
    sc = uniform_filter(valid, size=size, mode='nearest')
    smooth = np.where(sc > 0, sm/sc, np.nan)
    lrm = (dem - smooth).astype(np.float32)
    write_tif(f'lrm_{size}_{SFX}.tif', lrm)

def tpi(z, radius_m):
    return (z - nanmean_filter(z, disk_kernel(radius_m / RES))).astype(np.float32)

tpi_05 = tpi(dem,  5.0); tpi_15 = tpi(dem, 15.0); tpi_25 = tpi(dem, 25.0)
write_tif(f'tpi_05_{SFX}.tif', tpi_05)
write_tif(f'tpi_15_{SFX}.tif', tpi_15)
write_tif(f'tpi_25_{SFX}.tif', tpi_25)
gy, gx = np.gradient(tpi_15, RES)
write_tif(f'tpi_grad_mag_{SFX}.tif', np.hypot(gx, gy).astype(np.float32))
write_tif(f'tpi_grad_dir_{SFX}.tif', (np.degrees(np.arctan2(gx, -gy)) % 360).astype(np.float32))

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

print('computing openness (L=25 cells at 1m)...')
op_pos, op_neg = openness(dem, L_cells=int(25/RES), cellsize=RES)
write_tif(f'openness_pos_{SFX}.tif', op_pos)
write_tif(f'openness_neg_{SFX}.tif', op_neg)

# 6. Overview PNG
panels = [
    (f'hillshade_{SFX}.tif',        'hillshade',           'gray',   (None,None)),
    (f'dem_{SFX}.tif',              'DEM (m)',             'terrain',(None,None)),
    (f'slope_{SFX}.tif',            'slope (deg)',         'magma',  (0, 30)),
    (f'intensity_ground_{SFX}.tif', 'ground intensity',    'cividis',(None,None)),
    (f'ground_density_{SFX}.tif',   'ground density',      'viridis',(0, 8)),
    (f'chm_{SFX}.tif',              'CHM (m)',             'Greens', (0, 30)),
    (f'lrm_5_{SFX}.tif',            'LRM 5',               'RdBu_r', (-0.6, 0.6)),
    (f'lrm_11_{SFX}.tif',           'LRM 11',              'RdBu_r', (-0.8, 0.8)),
    (f'tpi_15_{SFX}.tif',           'TPI 15 m',            'RdBu_r', (-0.5, 0.5)),
    (f'openness_pos_{SFX}.tif',     'openness_pos',        'viridis',(None,None)),
    (f'openness_neg_{SFX}.tif',     'openness_neg',        'viridis',(None,None)),
    (f'local_relief_10_{SFX}.tif',  'local relief (10 m)', 'magma',  (0, 3)),
]
fig, axes = plt.subplots(3, 4, figsize=(20, 18))
for ax, (fname, title, cmap, lim) in zip(axes.ravel(), panels):
    a = read_tif(fname)
    if lim[0] is None:
        im = ax.imshow(a, cmap=cmap, extent=[X0, X1, Y0, Y1])
    else:
        im = ax.imshow(a, cmap=cmap, vmin=lim[0], vmax=lim[1], extent=[X0, X1, Y0, Y1])
    ax.set_title(f'{title}', fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
fig.suptitle(f'9-tile (4.5 km x 4.5 km) — 1 m derivative stack', fontsize=14)
fig.tight_layout(rect=[0, 0, 1, 0.98])
fig.savefig(DERIV/f'tile_overview_{SFX}.png', dpi=120, bbox_inches='tight')
plt.close(fig)
print(f'wrote tile_overview_{SFX}.png')
print('\nDONE.')
