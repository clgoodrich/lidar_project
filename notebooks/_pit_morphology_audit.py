"""Pit morphology measurement + anomaly detection for ALL annotated pits.

Measures each annotated pit's physical parameters across all available DEM tiles,
then scores each pit for statistical anomaly to flag potential annotation errors.

Outputs:
  data/derivatives/pit_morphology_all_with_anomaly.csv
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from scipy.spatial.distance import mahalanobis
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import glob

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'

pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
print(f'Total annotated pits: {len(pits)}')

dem_files = sorted(glob.glob(str(DERIV / 'dem_*_1m.tif'))) + [str(DERIV / 'dem_05.tif')]
print(f'Available DEMs: {len(dem_files)}')


def read_raster(path):
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            a = np.where(a == nd, np.nan, a)
        return a, ds.bounds, ds.res[0], ds.shape


def get_matching_rasters(dem_path):
    p = Path(dem_path)
    name = p.name
    if '_05.tif' in name:
        suffix = '_05.tif'
    else:
        suffix = name.replace('dem', '')
    result = {}
    for key, prefix in [('dem', 'dem'), ('lrm5', 'lrm_5'), ('lrm11', 'lrm_11'),
                         ('lrm25', 'lrm_25'), ('slope', 'slope')]:
        fp = DERIV / f'{prefix}{suffix}'
        if fp.exists():
            result[key] = fp
    return result


def measure_pit(x, y, rasters_data, bounds, res, shape):
    H, W = shape
    X0 = bounds.left
    Y1 = bounds.top
    r = int(round((Y1 - y) / res))
    c = int(round((x - X0) / res))
    HALF = int(round(7.5 / res))

    r1, r2 = r - HALF, r + HALF + 1
    c1, c2 = c - HALF, c + HALF + 1
    if r1 < 0 or c1 < 0 or r2 > H or c2 > W:
        return None

    dem_win = rasters_data['dem'][r1:r2, c1:c2]
    if np.isnan(dem_win).mean() > 0.5:
        return None

    # Snap to local minimum in center region
    snap_r = int(round(2.0 / res))
    sr1, sr2 = HALF - snap_r, HALF + snap_r + 1
    snap_win = dem_win[sr1:sr2, sr1:sr2]
    if np.isfinite(snap_win).any():
        fmin = np.nanargmin(snap_win)
        dr, dc = divmod(fmin, snap_win.shape[1])
        cr, cc = sr1 + dr, sr1 + dc
    else:
        cr, cc = HALF, HALF

    pit_bottom = dem_win[cr, cc]

    yy, xx = np.ogrid[-cr:dem_win.shape[0]-cr, -cc:dem_win.shape[1]-cc]
    dist = np.sqrt(xx*xx + yy*yy) * res

    # Find rim
    rim_elevs = []
    for ring_r in np.arange(1.0, 7.5, 0.5):
        ring_mask = (dist >= ring_r - 0.3) & (dist <= ring_r + 0.3)
        ring_vals = dem_win[ring_mask]
        valid = ring_vals[np.isfinite(ring_vals)]
        if len(valid) > 0:
            rim_elevs.append((ring_r, np.mean(valid), np.max(valid)))

    if not rim_elevs:
        return None

    rim_arr = np.array(rim_elevs)
    best_idx = np.argmax(rim_arr[:, 1])
    rim_radius = rim_arr[best_idx, 0]
    rim_mean = rim_arr[best_idx, 1]
    rim_max = rim_arr[best_idx, 2]

    depth_mean = rim_mean - pit_bottom
    depth_max = rim_max - pit_bottom

    # Effective radius (half-depth contour)
    half_elev = pit_bottom + depth_mean / 2.0
    half_mask = dem_win >= half_elev
    half_dists = dist[half_mask & (dist < 7.5)]
    eff_radius = float(np.median(half_dists)) if len(half_dists) > 0 else np.nan

    # Symmetry (std of rim elevations at 8 angular samples)
    angs = np.linspace(0, 2*np.pi, 8, endpoint=False)
    rim_samples = []
    for a in angs:
        sr = int(round(cr + rim_radius/res * np.sin(a)))
        sc = int(round(cc + rim_radius/res * np.cos(a)))
        if 0 <= sr < dem_win.shape[0] and 0 <= sc < dem_win.shape[1]:
            v = dem_win[sr, sc]
            if np.isfinite(v):
                rim_samples.append(v)
    sym_std = float(np.std(rim_samples)) if len(rim_samples) >= 4 else np.nan

    diameter = 2.0 * rim_radius
    aspect = depth_mean / diameter if diameter > 0 else np.nan
    volume = (1/3) * np.pi * rim_radius**2 * depth_mean

    # LRM values at snapped center
    lrm5_val = np.nan
    lrm11_val = np.nan
    if 'lrm5' in rasters_data:
        lw = rasters_data['lrm5'][r1:r2, c1:c2]
        if cr < lw.shape[0] and cc < lw.shape[1]:
            lrm5_val = float(lw[cr, cc])
    if 'lrm11' in rasters_data:
        lw = rasters_data['lrm11'][r1:r2, c1:c2]
        if cr < lw.shape[0] and cc < lw.shape[1]:
            lrm11_val = float(lw[cr, cc])

    # Slope at inner 2m
    slope_val = np.nan
    if 'slope' in rasters_data:
        sw = rasters_data['slope'][r1:r2, c1:c2]
        inner = sw[dist <= 2.0]
        slope_val = float(np.nanmean(inner)) if np.isfinite(inner).any() else np.nan

    return {
        'pit_bottom_elev_m': float(pit_bottom),
        'rim_mean_elev_m': float(rim_mean),
        'rim_max_elev_m': float(rim_max),
        'depth_from_rim_mean_m': float(depth_mean),
        'depth_from_rim_max_m': float(depth_max),
        'rim_radius_m': float(rim_radius),
        'effective_radius_m': float(eff_radius),
        'diameter_m': float(diameter),
        'aspect_ratio': float(aspect),
        'rim_symmetry_std_m': float(sym_std),
        'volume_approx_m3': float(volume),
        'lrm5_depth_m': float(lrm5_val),
        'lrm11_depth_m': float(lrm11_val),
        'slope_inner_deg': float(slope_val),
    }


# ---- Process all tiles ----
all_results = []
for dem_path in dem_files:
    raster_paths = get_matching_rasters(dem_path)
    if 'dem' not in raster_paths:
        continue

    with rasterio.open(str(raster_paths['dem'])) as ds:
        bounds = ds.bounds
        res_val = ds.res[0]
        shape = ds.shape

    bx0, by0, bx1, by1 = bounds
    in_tile = pits.cx[bx0:bx1, by0:by1]
    if len(in_tile) == 0:
        continue

    print(f'  {Path(dem_path).name}: {len(in_tile)} pits')

    rasters_data = {}
    for key, rpath in raster_paths.items():
        rasters_data[key], _, _, _ = read_raster(str(rpath))

    for idx, row in in_tile.iterrows():
        m = measure_pit(row.geometry.x, row.geometry.y, rasters_data, bounds, res_val, shape)
        if m is not None:
            m['original_index'] = idx
            m['x'] = row.geometry.x
            m['y'] = row.geometry.y
            m['tile'] = Path(dem_path).stem
            m['notes'] = row.get('notes', '')
            all_results.append(m)

df = pd.DataFrame(all_results)
df = df.drop_duplicates(subset=['original_index'], keep='first').reset_index(drop=True)
print(f'\nTotal unique pits measured: {len(df)}')


# ---- ANOMALY SCORING ----
feat_cols = ['depth_from_rim_mean_m', 'depth_from_rim_max_m', 'rim_radius_m',
             'effective_radius_m', 'diameter_m', 'aspect_ratio',
             'rim_symmetry_std_m', 'volume_approx_m3', 'lrm5_depth_m', 'lrm11_depth_m',
             'slope_inner_deg']

X = df[feat_cols].copy()
X_filled = X.fillna(X.median())

# Z-scores
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_filled)
df['max_zscore'] = np.abs(X_scaled).max(axis=1)
df['mean_zscore'] = np.abs(X_scaled).mean(axis=1)

# Mahalanobis distance
cov = np.cov(X_scaled.T)
cov_inv = np.linalg.pinv(cov)
center = X_scaled.mean(axis=0)
df['mahalanobis'] = [mahalanobis(row, center, cov_inv) for row in X_scaled]

# Isolation Forest
iso = IsolationForest(n_estimators=200, contamination=0.1, random_state=42)
iso.fit(X_filled)
df['iso_anomaly_score'] = -iso.score_samples(X_filled)

# Rank by Mahalanobis
df['anomaly_rank'] = df['mahalanobis'].rank(ascending=False).astype(int)
df_sorted = df.sort_values('mahalanobis', ascending=False).reset_index(drop=True)

# ---- Print results ----
print('\n' + '='*100)
print('TOP 25 MOST ANOMALOUS PITS - review these annotations for possible errors')
print('='*100)
show_cols = ['original_index', 'tile', 'depth_from_rim_mean_m', 'rim_radius_m', 'diameter_m',
             'aspect_ratio', 'rim_symmetry_std_m', 'volume_approx_m3', 'slope_inner_deg',
             'mahalanobis', 'max_zscore', 'iso_anomaly_score']
pd.set_option('display.width', 180)
pd.set_option('display.max_columns', 15)
print(df_sorted[show_cols].head(25).round(3).to_string(index=False))

print('\n' + '='*100)
print('OVERALL MORPHOLOGY STATS')
print('='*100)
print(df[feat_cols].describe().round(3).to_string())

# Why each top-10 is flagged
print('\n' + '='*100)
print('WHY EACH TOP-10 IS FLAGGED (feature with highest abs z-score)')
print('='*100)
for i in range(min(10, len(df_sorted))):
    orig_idx = int(df_sorted.iloc[i]['original_index'])
    match_rows = df[df['original_index'] == orig_idx]
    if len(match_rows) == 0:
        continue
    loc = match_rows.index[0]
    zscores = X_scaled[loc]
    worst_feat_idx = np.argmax(np.abs(zscores))
    worst_feat = feat_cols[worst_feat_idx]
    worst_z = zscores[worst_feat_idx]
    val = df_sorted.iloc[i][worst_feat]
    tile = df_sorted.iloc[i]['tile']
    print(f'  Pit #{orig_idx:3d} ({tile}): {worst_feat} = {val:.3f} (z={worst_z:+.2f})')

# Save
out_path = DERIV / 'pit_morphology_all_with_anomaly.csv'
df_sorted.to_csv(out_path, index=False, float_format='%.4f')
print(f'\nSaved: {out_path}')
print(f'Total rows: {len(df_sorted)}, Columns: {list(df_sorted.columns)}')
