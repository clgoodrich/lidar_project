"""Build 2008 PAMAP 1 m derivative stack for the separate-sections area.

Source: 6 PAMAP Statewide South LAZ tiles in EPSG:2272 (PA South, US ft).
  -> reproject to EPSG:6346, Z *= 0.3048006096, crop to sep extent.
  -> merge into sep_2008_merged.las
  -> build 1 m derivatives (suffix _sep_2008_1m)
"""
import json, subprocess, shutil, time
import numpy as np, laspy, rasterio
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from scipy.ndimage import uniform_filter
from pathlib import Path
import matplotlib.pyplot as plt

DATA    = Path('data/files'); DERIV = Path('data/derivatives')
SRC_DIR = DATA / 'seperate sections'
PDAL    = shutil.which('pdal') or 'pdal'

LAS_OUT = DATA / 'sep_2008_merged.las'
SFX = 'sep_2008_1m'

X0, Y0, X1, Y1 = 562500.0, 4464000.0, 568500.0, 4470000.0
RES = 1.0
W = int((X1 - X0) / RES); H = int((Y1 - Y0) / RES)
T = from_origin(X0, Y1, RES, RES)
CRS = 'EPSG:6346'
print(f'grid: {W} x {H} cells @ {RES} m')

TILES = sorted(SRC_DIR.glob('*Statewide*2006-2008*.laz'))
print(f'source tiles: {len(TILES)}')
for t in TILES: print(f'  {t.name}')


def run_pipeline(pl, label, timeout=3600):
    tmp = DERIV / f'_tmp_{label}.json'
    with open(tmp, 'w') as f: json.dump(pl, f, indent=2)
    t0 = time.time()
    r = subprocess.run([PDAL, 'pipeline', str(tmp)], capture_output=True, text=True, timeout=timeout)
    print(f'[{label}] rc={r.returncode} in {time.time()-t0:.1f}s', flush=True)
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
    print('wrote', name, flush=True)


def read_tif(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a


# (1) Merge + reproject + clip
if not LAS_OUT.exists():
    print('\n=== merging 2008 tiles ===', flush=True)
    stages = []
    for t in TILES:
        stages.append({'type': 'readers.las', 'filename': str(t),
                       'override_srs': 'EPSG:2272'})
    stages.extend([
        {'type': 'filters.reprojection', 'out_srs': 'EPSG:6346'},
        {'type': 'filters.assign', 'value': 'Z = Z * 0.3048006096'},
        {'type': 'filters.crop', 'bounds': f'([{X0},{X1}],[{Y0},{Y1}])'},
        {'type': 'writers.las', 'filename': str(LAS_OUT),
         'a_srs': 'EPSG:6346', 'minor_version': 4,
         'dataformat_id': 6, 'forward': 'all', 'compression': 'false'},
    ])
    run_pipeline({'pipeline': stages}, 'merge_sep_2008')
    # verify
    info = subprocess.run([PDAL, 'info', str(LAS_OUT), '--metadata'],
                          capture_output=True, text=True, timeout=120).stdout
    meta = json.loads(info)['metadata']
    print(f'points: {meta["count"]:,}  z: {meta["minz"]:.1f}..{meta["maxz"]:.1f}', flush=True)
else:
    print(f'{LAS_OUT} already exists', flush=True)


# (2) DEM + DSM + CHM
print('\n=== DEM ===', flush=True)
run_pipeline({'pipeline': [
    {'type': 'readers.las', 'filename': str(LAS_OUT)},
    {'type': 'filters.range', 'limits': 'Classification[2:2]'},
    {'type': 'filters.delaunay'},
    {'type': 'filters.faceraster',
     'resolution': RES, 'origin_x': X0, 'origin_y': Y0, 'width': W, 'height': H},
    {'type': 'writers.raster', 'filename': str(DERIV / f'dem_{SFX}.tif'), 'data_type': 'float32'},
]}, f'dem_{SFX}')
dem = read_tif(f'dem_{SFX}.tif')
print(f'DEM: nan {100*np.isnan(dem).mean():.2f}%   z {np.nanmin(dem):.1f}..{np.nanmax(dem):.1f}', flush=True)

run_pipeline({'pipeline': [
    {'type': 'readers.las', 'filename': str(LAS_OUT)},
    {'type': 'filters.range', 'limits': 'ReturnNumber[1:1]'},
    {'type': 'writers.gdal', 'filename': str(DERIV / f'dsm_{SFX}.tif'),
     'output_type': 'max', 'resolution': RES,
     'origin_x': X0, 'origin_y': Y0, 'width': W, 'height': H,
     'data_type': 'float32'},
]}, f'dsm_{SFX}')
dsm = read_tif(f'dsm_{SFX}.tif')
chm = np.where(np.isnan(dsm)|np.isnan(dem), np.nan, np.maximum(dsm-dem, 0)).astype(np.float32)
write_tif(f'chm_{SFX}.tif', chm)

# (3) Density
print('=== density ===', flush=True)
las = laspy.read(str(LAS_OUT))
xs = np.asarray(las.x); ys = np.asarray(las.y); cls = np.asarray(las.classification)
gmask = (cls == 2)
col = np.floor((xs[gmask] - X0)/RES).astype(np.int64)
row = np.floor((Y1 - ys[gmask])/RES).astype(np.int64)
ok = (col >= 0)&(col < W)&(row >= 0)&(row < H)
flat_idx = (row[ok]*W + col[ok])
density = np.bincount(flat_idx, minlength=H*W).reshape(H, W).astype(np.uint16)
write_tif(f'ground_density_{SFX}.tif', density, dtype='uint16', nd=0)
del las

# (4) Slope
import whitebox
wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(str(DERIV.resolve()))
wbt.set_verbose_mode(False)
wbt.hillshade(dem=f'dem_{SFX}.tif', output=f'hillshade_{SFX}.tif', azimuth=315.0, altitude=45.0)
wbt.slope(dem=f'dem_{SFX}.tif', output=f'slope_{SFX}.tif', units='degrees')
print(f'wrote hillshade + slope', flush=True)

# (5) Derivatives needed by the classifier
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

# LRM 5 + 11
for size in (5, 11):
    valid = np.isfinite(dem).astype(np.float32)
    z0 = np.where(valid.astype(bool), dem, 0).astype(np.float32)
    sm = uniform_filter(z0, size=size, mode='nearest')
    sc = uniform_filter(valid, size=size, mode='nearest')
    smooth = np.where(sc > 0, sm/sc, np.nan)
    lrm = (dem - smooth).astype(np.float32)
    write_tif(f'lrm_{size}_{SFX}.tif', lrm)

# TPI 15
def tpi(z, radius_m):
    return (z - nanmean_filter(z, disk_kernel(radius_m / RES))).astype(np.float32)
write_tif(f'tpi_15_{SFX}.tif', tpi(dem, 15.0))

# Openness neg
def openness(z, L_cells, cellsize):
    L = int(L_cells)
    dirs = [(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
    valid = np.isfinite(z); z0 = np.where(valid, z, 0).astype(np.float32)
    psi_sum = np.zeros_like(z, dtype=np.float32)
    for dr, dc in dirs:
        step = cellsize * np.hypot(dr, dc)
        min_tan_dn = np.full_like(z, np.inf, dtype=np.float32)
        for k in range(1, L+1):
            zs = np.roll(z0,    shift=(dr*k, dc*k), axis=(0,1))
            vs = np.roll(valid, shift=(dr*k, dc*k), axis=(0,1))
            if dr > 0:   vs[:dr*k, :] = False
            elif dr < 0: vs[dr*k:, :] = False
            if dc > 0:   vs[:, :dc*k] = False
            elif dc < 0: vs[:, dc*k:] = False
            tan_a = np.where(vs, (zs - z0)/(k*step), np.nan).astype(np.float32)
            np.fmin(min_tan_dn, tan_a, out=min_tan_dn, where=vs)
        a_min = np.arctan(np.where(np.isfinite(min_tan_dn), min_tan_dn, 0))
        psi_sum += (np.pi/2 + a_min).astype(np.float32)
    psi = np.degrees(psi_sum/8).astype(np.float32)
    psi[~valid] = np.nan
    return psi

print('=== openness_neg ===', flush=True)
op_neg = openness(dem, L_cells=int(25/RES), cellsize=RES)
write_tif(f'openness_neg_{SFX}.tif', op_neg)

# (6) Overview
print('=== overview ===', flush=True)
panels = [
    (f'hillshade_{SFX}.tif', 'hillshade', 'gray', (None,None)),
    (f'dem_{SFX}.tif',       'DEM (m)',   'terrain', (None,None)),
    (f'slope_{SFX}.tif',     'slope',     'magma', (0,30)),
    (f'lrm_5_{SFX}.tif',     'LRM 5',     'RdBu_r', (-0.6,0.6)),
    (f'lrm_11_{SFX}.tif',    'LRM 11',    'RdBu_r', (-0.8,0.8)),
    (f'tpi_15_{SFX}.tif',    'TPI 15',    'RdBu_r', (-0.5,0.5)),
]
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
for ax, (fname, title, cmap, lim) in zip(axes.ravel(), panels):
    a = read_tif(fname)
    kw = dict(cmap=cmap, extent=[X0, X1, Y0, Y1])
    if lim[0] is not None: kw.update(vmin=lim[0], vmax=lim[1])
    im = ax.imshow(a, **kw)
    ax.set_title(title, fontsize=10); ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
fig.suptitle('separate sections — 2008 PAMAP — 1 m derivatives', fontsize=14)
fig.tight_layout(rect=[0,0,1,0.97])
fig.savefig(DERIV / f'tile_overview_{SFX}.png', dpi=120, bbox_inches='tight')
plt.close(fig)
print(f'wrote tile_overview_{SFX}.png', flush=True)
print('\nDONE.', flush=True)
