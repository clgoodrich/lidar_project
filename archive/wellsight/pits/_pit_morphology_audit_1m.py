"""Pit morphology + anomaly scoring for updated 861 pits on 1m tiles only."""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from scipy.spatial.distance import mahalanobis as mah_dist
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from shapely.geometry import Point

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'
RES = 1.0

TILES = {
    '9t': '_9t_1m.tif',
    'mk5': '_mk5_1m.tif',
    'mk': '_mk_1m.tif',
    'mkf': '_mkf_1m.tif',
}

pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
print(f'Annotated pits: {len(pits)}')


def read_raster(path):
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            a = np.where(a == nd, np.nan, a)
        return a, ds.bounds, ds.shape


def measure_pit(x, y, dem, lrm5, lrm11, slope, bounds, shape):
    H, W = shape
    X0, Y1 = bounds.left, bounds.top
    r = int(round((Y1 - y) / RES))
    c = int(round((x - X0) / RES))
    HALF = 8

    r1, r2 = r - HALF, r + HALF + 1
    c1, c2 = c - HALF, c + HALF + 1
    if r1 < 0 or c1 < 0 or r2 > H or c2 > W:
        return None

    dem_win = dem[r1:r2, c1:c2]
    if np.isnan(dem_win).mean() > 0.5:
        return None

    snap_r = 3
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
    dist = np.sqrt(xx*xx + yy*yy) * RES

    rim_elevs = []
    for ring_r in np.arange(1.0, 8.0, 0.5):
        ring_mask = (dist >= ring_r - 0.5) & (dist <= ring_r + 0.5)
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

    half_elev = pit_bottom + depth_mean / 2.0
    half_mask = dem_win >= half_elev
    half_dists = dist[half_mask & (dist < 8.0)]
    eff_radius = float(np.median(half_dists)) if len(half_dists) > 0 else np.nan

    angs = np.linspace(0, 2*np.pi, 8, endpoint=False)
    rim_samples = []
    for a in angs:
        sr = int(round(cr + rim_radius/RES * np.sin(a)))
        sc = int(round(cc + rim_radius/RES * np.cos(a)))
        if 0 <= sr < dem_win.shape[0] and 0 <= sc < dem_win.shape[1]:
            v = dem_win[sr, sc]
            if np.isfinite(v):
                rim_samples.append(v)
    sym_std = float(np.std(rim_samples)) if len(rim_samples) >= 4 else np.nan

    diameter = 2.0 * rim_radius
    aspect = depth_mean / diameter if diameter > 0 else np.nan
    volume = (1/3) * np.pi * rim_radius**2 * depth_mean

    lrm5_win = lrm5[r1:r2, c1:c2]
    lrm11_win = lrm11[r1:r2, c1:c2]
    lrm5_val = float(lrm5_win[cr, cc]) if cr < lrm5_win.shape[0] and cc < lrm5_win.shape[1] else np.nan
    lrm11_val = float(lrm11_win[cr, cc]) if cr < lrm11_win.shape[0] and cc < lrm11_win.shape[1] else np.nan

    slope_win = slope[r1:r2, c1:c2]
    inner_slope = slope_win[dist <= 2.0]
    slope_val = float(np.nanmean(inner_slope)) if np.isfinite(inner_slope).any() else np.nan

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


# Process all tiles
all_results = []
for tag, suffix in TILES.items():
    dem_path = DERIV / f'dem{suffix}'
    lrm5_path = DERIV / f'lrm_5{suffix}'
    lrm11_path = DERIV / f'lrm_11{suffix}'
    slope_path = DERIV / f'slope{suffix}'

    dem, bounds, shape = read_raster(str(dem_path))
    lrm5, _, _ = read_raster(str(lrm5_path))
    lrm11, _, _ = read_raster(str(lrm11_path))
    slp, _, _ = read_raster(str(slope_path))

    bx0, by0, bx1, by1 = bounds
    in_tile = pits.cx[bx0:bx1, by0:by1]
    if len(in_tile) == 0:
        continue
    print(f'  {tag}: {len(in_tile)} pits')

    for idx, row in in_tile.iterrows():
        m = measure_pit(row.geometry.x, row.geometry.y, dem, lrm5, lrm11, slp, bounds, shape)
        if m is not None:
            m['original_index'] = idx
            m['x'] = row.geometry.x
            m['y'] = row.geometry.y
            m['tile'] = tag
            m['notes'] = row.get('notes', '')
            all_results.append(m)

df = pd.DataFrame(all_results)
df = df.drop_duplicates(subset=['original_index'], keep='first').reset_index(drop=True)
print(f'\nTotal unique pits measured: {len(df)}')

# ---- Anomaly scoring ----
feat_cols = ['depth_from_rim_mean_m', 'depth_from_rim_max_m', 'rim_radius_m',
             'effective_radius_m', 'diameter_m', 'aspect_ratio',
             'rim_symmetry_std_m', 'volume_approx_m3', 'lrm5_depth_m', 'lrm11_depth_m',
             'slope_inner_deg']
X = df[feat_cols].fillna(df[feat_cols].median())
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

df['max_zscore'] = np.abs(X_scaled).max(axis=1)
df['mean_zscore'] = np.abs(X_scaled).mean(axis=1)

cov = np.cov(X_scaled.T)
cov_inv = np.linalg.pinv(cov)
center = X_scaled.mean(axis=0)
df['mahalanobis'] = [mah_dist(row, center, cov_inv) for row in X_scaled]

iso = IsolationForest(n_estimators=200, contamination=0.1, random_state=42)
iso.fit(X)
df['iso_anomaly_score'] = -iso.score_samples(X)

# PCA
pca = PCA()
scores = pca.fit_transform(X_scaled)
df['PC1_depth_volume'] = scores[:, 0]
df['PC2_size_vs_slope'] = scores[:, 1]
df['PC3_rim_asymmetry'] = scores[:, 2]

# Per-feature z-scores
for i, col in enumerate(feat_cols):
    df[f'z_{col}'] = X_scaled[:, i]

# Anomaly reason
z_arr = np.abs(X_scaled)
worst_idx = np.argmax(z_arr, axis=1)
df['anomaly_reason'] = [feat_cols[i] for i in worst_idx]
df['anomaly_reason_zscore'] = [X_scaled[row, worst_idx[row]] for row in range(len(df))]
df['anomaly_rank'] = df['mahalanobis'].rank(ascending=False).astype(int)

# Sort and save
df_sorted = df.sort_values('mahalanobis', ascending=False).reset_index(drop=True)

geometry = [Point(x, y) for x, y in zip(df_sorted['x'], df_sorted['y'])]
gdf = gpd.GeoDataFrame(df_sorted.drop(columns=['x', 'y']), geometry=geometry, crs=CRS)
gdf.to_file(DERIV / 'pit_1m_morphology_audit.gpkg', driver='GPKG')
gdf.drop(columns='geometry').to_csv(DERIV / 'pit_1m_morphology_audit.csv', index=False, float_format='%.4f')

print(f'\nSaved: pit_1m_morphology_audit.gpkg ({len(gdf)} features, {len(gdf.columns)} columns)')
print(f'Saved: pit_1m_morphology_audit.csv')

print('\n' + '='*80)
print('OVERALL MORPHOLOGY STATS')
print('='*80)
print(df[feat_cols].describe().round(3).to_string())

print('\n' + '='*80)
print('TOP 15 MOST ANOMALOUS')
print('='*80)
show = ['original_index', 'tile', 'depth_from_rim_mean_m', 'rim_radius_m', 'diameter_m',
        'aspect_ratio', 'slope_inner_deg', 'mahalanobis', 'anomaly_reason', 'anomaly_reason_zscore']
pd.set_option('display.width', 160)
print(df_sorted[show].head(15).round(3).to_string(index=False))

print('\n' + '='*80)
print(f'PCA variance explained: PC1={pca.explained_variance_ratio_[0]:.1%}, '
      f'PC2={pca.explained_variance_ratio_[1]:.1%}, '
      f'PC3={pca.explained_variance_ratio_[2]:.1%}')
print('='*80)
