"""Full pit detection pipeline on 1m tiles.

Stages:
  1. Template learning + NCC matching (per tile)
  2. Feature extraction (ring stats, morphology, radial profiles)
  3. XGBoost classifier with GroupKFold CV
  4. Ensemble (XGB + LightGBM + HistGB) + isotonic calibration

Uses ALL 1m tiles that have a full derivative stack.
Annotations: wellhead_pits.gpkg (861 points as of 2026-04-20)

Outputs (data/derivatives/):
  pit_1m_candidates_template.gpkg
  pit_1m_template_cutouts.png
  pit_1m_template_mean.png
  pit_1m_match_score_<tile>.tif
  pit_1m_candidates_ensemble.gpkg
  pit_1m_ensemble_metrics.txt
  pit_1m_ensemble_feature_importance.png
  pit_1m_ensemble_thrXX.png
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Point
from shapely import make_valid
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, precision_recall_curve, average_precision_score
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA as skPCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from skimage.feature import match_template, peak_local_max
import xgboost as xgb
import lightgbm as lgb
import matplotlib.pyplot as plt
import glob, warnings
warnings.filterwarnings('ignore')

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'
RES = 1.0
POS_DIST_M = 10.0
HALF = 8        # 8 m half-window at 1m res
INNER = 3       # inner ring radius (cells)
OUTER = 6       # rim ring inner radius (cells)
SNAP_R = 3      # snap radius in cells
MIN_DIST_PEAKS = 5  # minimum distance between NCC peaks (cells = metres at 1m)

# Tiles to process - need DEM + LRM + TPI + openness + slope + hillshade
TILES = {}
for dem_path in sorted(glob.glob(str(DERIV / 'dem_*_1m.tif'))):
    p = Path(dem_path)
    suffix = p.name.replace('dem', '')  # e.g. _9t_1m.tif
    tag = suffix.replace('_1m.tif', '').strip('_')  # e.g. 9t
    # Check required channels exist
    required = ['lrm_5', 'lrm_11', 'tpi_05', 'openness_neg', 'slope', 'hillshade',
                'lrm_25', 'tpi_15', 'chm', 'ground_density', 'roughness_5',
                'local_relief_10', 'openness_pos']
    all_exist = all((DERIV / f'{r}{suffix}').exists() for r in required)
    if all_exist:
        TILES[tag] = suffix

print(f'Tiles with full stacks: {list(TILES.keys())}')


def read_tile(suffix, prefix):
    path = DERIV / f'{prefix}{suffix}'
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            a = np.where(a == nd, np.nan, a)
        return a


def get_tile_meta(suffix):
    path = DERIV / f'dem{suffix}'
    with rasterio.open(path) as ds:
        return ds.bounds, ds.shape


# Load annotations
pits_all = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
print(f'Total annotated pits: {len(pits_all)}')

# ============================================================
# STAGE 1: Template learning + NCC matching
# ============================================================
print('\n' + '='*70)
print('STAGE 1: Template learning + NCC matching')
print('='*70)

TEMPLATE_CHANNELS = ['lrm_5', 'lrm_11', 'tpi_05', 'openness_neg', 'hillshade']
WIN = 2 * HALF + 1  # 17 cells

# Collect cutouts from all tiles
all_cutouts = {ch: [] for ch in TEMPLATE_CHANNELS}
snapped_count = 0

for tag, suffix in TILES.items():
    bounds, shape = get_tile_meta(suffix)
    H, W = shape
    X0, Y0, X1, Y1 = bounds.left, bounds.bottom, bounds.right, bounds.top

    # Pits in this tile
    tile_pits = pits_all.cx[X0:X1, Y0:Y1]
    if len(tile_pits) == 0:
        continue

    lrm5 = read_tile(suffix, 'lrm_5')
    rasters = {ch: read_tile(suffix, ch) for ch in TEMPLATE_CHANNELS}

    for _, row in tile_pits.iterrows():
        x, y = row.geometry.x, row.geometry.y
        r = int(round((Y1 - y) / RES))
        c = int(round((x - X0) / RES))

        # Snap to local min in LRM5
        sr1, sr2 = max(0, r - SNAP_R), min(H, r + SNAP_R + 1)
        sc1, sc2 = max(0, c - SNAP_R), min(W, c + SNAP_R + 1)
        snap_win = lrm5[sr1:sr2, sc1:sc2]
        if not np.isfinite(snap_win).any():
            continue
        fmin = np.nanargmin(snap_win)
        dr, dc = divmod(fmin, snap_win.shape[1])
        r_s, c_s = sr1 + dr, sc1 + dc

        # Extract window
        r1, r2 = r_s - HALF, r_s + HALF + 1
        c1, c2 = c_s - HALF, c_s + HALF + 1
        if r1 < 0 or c1 < 0 or r2 > H or c2 > W:
            continue

        valid = True
        for ch in TEMPLATE_CHANNELS:
            win = rasters[ch][r1:r2, c1:c2]
            if np.isnan(win).mean() > 0.2:
                valid = False
                break
            m = np.nanmean(win)
            all_cutouts[ch].append(win - m)

        if valid:
            snapped_count += 1

print(f'Snapped cutouts collected: {snapped_count}')

# Build median templates
templates = {}
for ch in TEMPLATE_CHANNELS:
    arr = np.stack(all_cutouts[ch], axis=0)
    templates[ch] = np.nanmedian(arr, axis=0)
    print(f'  {ch}: {arr.shape[0]} cutouts -> template {templates[ch].shape}')

# Multi-template clustering (3 sub-types)
lrm5_cuts = np.stack(all_cutouts['lrm_5'], axis=0)
flat = lrm5_cuts.reshape(len(lrm5_cuts), -1)
flat_clean = np.nan_to_num(flat, nan=0.0)
pca_sub = skPCA(n_components=5)
pca_scores = pca_sub.fit_transform(flat_clean)
km = KMeans(n_clusters=3, random_state=42, n_init=10)
labels = km.fit_predict(pca_scores)
print(f'  Sub-type cluster sizes: {np.bincount(labels)}')

cluster_templates = {}
for k in range(3):
    mask = labels == k
    cluster_templates[k] = {ch: np.nanmedian(np.stack(all_cutouts[ch], axis=0)[mask], axis=0)
                            for ch in ['lrm_5']}

# Save template visualizations
fig, axes = plt.subplots(2, len(TEMPLATE_CHANNELS), figsize=(3*len(TEMPLATE_CHANNELS), 6))
for j, ch in enumerate(TEMPLATE_CHANNELS):
    arr = np.stack(all_cutouts[ch], axis=0)
    axes[0, j].imshow(np.nanmean(arr, axis=0), cmap='RdBu_r')
    axes[0, j].set_title(f'{ch}\nmean', fontsize=8)
    axes[0, j].axis('off')
    axes[1, j].imshow(np.nanmedian(arr, axis=0), cmap='RdBu_r')
    axes[1, j].set_title('median', fontsize=8)
    axes[1, j].axis('off')
fig.tight_layout()
fig.savefig(DERIV / 'pit_1m_template_mean.png', dpi=130, bbox_inches='tight')
plt.close(fig)

# Run NCC matching per tile and collect candidates
all_candidates = []

for tag, suffix in TILES.items():
    bounds, shape = get_tile_meta(suffix)
    H, W = shape
    X0, Y0, X1, Y1 = bounds.left, bounds.bottom, bounds.right, bounds.top

    lrm5 = read_tile(suffix, 'lrm_5')

    # Multi-channel NCC
    per_scores = {}
    for ch in ['lrm_5', 'lrm_11', 'tpi_05', 'openness_neg']:
        raster = read_tile(suffix, ch)
        raster_clean = np.nan_to_num(raster, nan=0.0)
        tmpl = templates[ch].copy()
        tmpl = np.nan_to_num(tmpl, nan=0.0)
        tmpl_std = tmpl.std()
        if tmpl_std < 1e-6:
            continue
        ncc = match_template(raster_clean, tmpl, pad_input=True, mode='constant')
        per_scores[ch] = ncc

    if not per_scores:
        continue

    score = np.nanmean(np.stack(list(per_scores.values()), axis=0), axis=0)

    # Also compute multi-template max score
    multi_scores = []
    for k in range(3):
        tmpl_k = cluster_templates[k]['lrm_5']
        tmpl_k = np.nan_to_num(tmpl_k, nan=0.0)
        if tmpl_k.std() < 1e-6:
            continue
        ncc_k = match_template(np.nan_to_num(lrm5, nan=0.0), tmpl_k,
                               pad_input=True, mode='constant')
        multi_scores.append(ncc_k)
    multi_max = np.max(np.stack(multi_scores, axis=0), axis=0) if multi_scores else score

    # Save match score raster
    with rasterio.open(DERIV / f'dem{suffix}') as ref:
        profile = ref.profile.copy()
    profile.update(dtype='float32', count=1, nodata=-9999)
    with rasterio.open(DERIV / f'pit_1m_match_score_{tag}.tif', 'w', **profile) as dst:
        dst.write(score.astype(np.float32), 1)

    # Determine threshold from annotated pits in this tile
    tile_pits = pits_all.cx[X0:X1, Y0:Y1]
    if len(tile_pits) > 5:
        pit_scores = []
        for _, row in tile_pits.iterrows():
            r = int(round((Y1 - row.geometry.y) / RES))
            c = int(round((row.geometry.x - X0) / RES))
            if 0 <= r < H and 0 <= c < W:
                pit_scores.append(score[r, c])
        if pit_scores:
            thr = np.percentile(pit_scores, 25)
        else:
            thr = np.percentile(score[np.isfinite(score)], 95)
    else:
        thr = np.percentile(score[np.isfinite(score)], 95)

    thr = max(thr, 0.05)  # floor

    # Peak detection
    score_clean = np.nan_to_num(score, nan=-1.0)
    coords = peak_local_max(score_clean, min_distance=MIN_DIST_PEAKS,
                            threshold_abs=thr, exclude_border=HALF)

    print(f'  {tag}: thr={thr:.3f}, {len(coords)} peaks')

    for (r, c) in coords:
        x = X0 + (c + 0.5) * RES
        y = Y1 - (r + 0.5) * RES
        all_candidates.append({
            'x': x, 'y': y,
            'score': float(score[r, c]),
            'multi_score': float(multi_max[r, c]),
            'tile': tag,
        })

cand_df = pd.DataFrame(all_candidates)
cand_gdf = gpd.GeoDataFrame(
    cand_df.drop(columns=['x', 'y']),
    geometry=[Point(x, y) for x, y in zip(cand_df['x'], cand_df['y'])],
    crs=CRS
)
cand_gdf.to_file(DERIV / 'pit_1m_candidates_template.gpkg', driver='GPKG')
print(f'\nTotal template candidates: {len(cand_gdf)}')

# ============================================================
# STAGE 2: Feature extraction
# ============================================================
print('\n' + '='*70)
print('STAGE 2: Feature extraction')
print('='*70)

yy, xx = np.ogrid[-HALF:HALF+1, -HALF:HALF+1]
rad = np.sqrt(xx*xx + yy*yy)
inner_mask = rad <= INNER
rim_mask = (rad >= OUTER) & (rad <= HALF)

DEPTH_CHANNELS = ['lrm_5', 'lrm_11', 'lrm_25', 'tpi_05', 'tpi_15', 'openness_neg']
SURFACE_CHANNELS = ['slope', 'roughness_5', 'local_relief_10', 'chm']


def stats_window(z, inner, rim):
    zi = z[inner]; zr = z[rim]
    if np.isfinite(zi).any() and np.isfinite(zr).any():
        return (np.nanmin(zi), np.nanmean(zi), np.nanmean(zr),
                np.nanmean(zr) - np.nanmin(zi), np.nanstd(zi))
    return (np.nan,) * 5


def radial_std(z):
    angs = np.linspace(0, 2*np.pi, 8, endpoint=False)
    zs = []
    for a in angs:
        r_row = int(round(HALF + INNER * np.sin(a)))
        r_col = int(round(HALF + INNER * np.cos(a)))
        if 0 <= r_row < z.shape[0] and 0 <= r_col < z.shape[1]:
            v = z[r_row, r_col]
            if np.isfinite(v):
                zs.append(v)
    return float(np.std(zs)) if len(zs) >= 4 else np.nan


def morphology_feats(lrm_win):
    """Gaussian-bowl morphology on LRM window."""
    out = {}
    center = lrm_win[HALF, HALF]
    out['morph_center_depth'] = float(center) if np.isfinite(center) else np.nan
    # Radial profile in rings
    for rmin, rmax, label in [(0, 2, 'r0_2'), (2, 5, 'r2_5'), (5, 8, 'r5_8')]:
        ring = (rad >= rmin) & (rad < rmax)
        vals = lrm_win[ring]
        out[f'morph_ring_{label}'] = float(np.nanmean(vals)) if np.isfinite(vals).any() else np.nan
    # Radial monotonicity
    ring_means = []
    for rr in range(1, HALF + 1):
        ring = (rad >= rr - 0.5) & (rad < rr + 0.5)
        vals = lrm_win[ring]
        if np.isfinite(vals).any():
            ring_means.append(np.nanmean(vals))
    if len(ring_means) >= 4:
        rho, _ = spearmanr(range(len(ring_means)), ring_means)
        out['morph_radial_monotonicity'] = float(rho)
    else:
        out['morph_radial_monotonicity'] = np.nan
    # Compactness
    inner_sum = np.nansum(np.abs(lrm_win[inner_mask]))
    total_sum = np.nansum(np.abs(lrm_win))
    out['morph_compactness'] = float(inner_sum / total_sum) if total_sum > 0 else np.nan
    return out


def extract_features_for_tile(tag, suffix, candidates_in_tile):
    bounds, shape = get_tile_meta(suffix)
    H, W = shape
    X0, Y0, X1, Y1 = bounds.left, bounds.bottom, bounds.right, bounds.top

    # Load all channels
    rasters = {}
    for ch in DEPTH_CHANNELS + SURFACE_CHANNELS + ['ground_density', 'dem']:
        rasters[ch] = read_tile(suffix, ch)

    # Match score
    match_path = DERIV / f'pit_1m_match_score_{tag}.tif'
    if match_path.exists():
        with rasterio.open(match_path) as ds:
            rasters['match_score'] = ds.read(1).astype(np.float32)
    else:
        rasters['match_score'] = np.zeros(shape, dtype=np.float32)

    feat_list = []
    for idx, row in candidates_in_tile.iterrows():
        x, y = row.geometry.x, row.geometry.y
        r = int(round((Y1 - y) / RES))
        c = int(round((x - X0) / RES))

        r1, r2 = r - HALF, r + HALF + 1
        c1, c2 = c - HALF, c + HALF + 1
        if r1 < 0 or c1 < 0 or r2 > H or c2 > W:
            feat_list.append(None)
            continue

        out = {}

        # Depth channels: ring stats + symmetry
        for ch in DEPTH_CHANNELS:
            w = rasters[ch][r1:r2, c1:c2]
            mni, mi, mr, diff, sdi = stats_window(w, inner_mask, rim_mask)
            out[f'{ch}_inner_min'] = mni
            out[f'{ch}_inner_mean'] = mi
            out[f'{ch}_rim_mean'] = mr
            out[f'{ch}_rim_minus'] = diff
            out[f'{ch}_sym'] = radial_std(w)

        # Surface channels
        for ch in SURFACE_CHANNELS:
            w = rasters[ch][r1:r2, c1:c2]
            wi = w[inner_mask]
            out[f'{ch}_inner_mean'] = float(np.nanmean(wi)) if np.isfinite(wi).any() else np.nan
            out[f'{ch}_window_max'] = float(np.nanmax(w)) if np.isfinite(w).any() else np.nan

        # Ground density
        dens = rasters['ground_density'][r1:r2, c1:c2]
        out['density_inner_mean'] = float(np.nanmean(dens[inner_mask]))
        out['density_window_mean'] = float(np.nanmean(dens))

        # DEM cut
        dem_w = rasters['dem'][r1:r2, c1:c2]
        _, _, _, dem_cut, _ = stats_window(dem_w, inner_mask, rim_mask)
        out['dem_cut_m'] = dem_cut

        # Match score at center
        out['match_score_center'] = float(rasters['match_score'][r, c])

        # Morphology features from LRM_5
        lrm5_w = rasters['lrm_5'][r1:r2, c1:c2]
        morph = morphology_feats(lrm5_w)
        out.update(morph)

        feat_list.append(out)

    return feat_list


# Extract features for all candidates
print('Extracting features per tile...')
all_feats = []
valid_indices = []

for tag, suffix in TILES.items():
    bounds, _ = get_tile_meta(suffix)
    X0, Y0, X1, Y1 = bounds.left, bounds.bottom, bounds.right, bounds.top
    tile_mask = cand_gdf['tile'] == tag
    tile_cands = cand_gdf[tile_mask]
    if len(tile_cands) == 0:
        continue

    print(f'  {tag}: {len(tile_cands)} candidates...')
    feats = extract_features_for_tile(tag, suffix, tile_cands)

    for i, (idx, f) in enumerate(zip(tile_cands.index, feats)):
        if f is not None:
            all_feats.append(f)
            valid_indices.append(idx)

X = pd.DataFrame(all_feats)
cand_valid = cand_gdf.loc[valid_indices].reset_index(drop=True)
X = X.reset_index(drop=True)
print(f'Feature matrix: {X.shape}')

# Label candidates
pit_xy = np.array([[g.x, g.y] for g in pits_all.geometry])
tree = cKDTree(pit_xy)
cxy = np.array([[g.x, g.y] for g in cand_valid.geometry])
dn, _ = tree.query(cxy, k=1)
y = (dn <= POS_DIST_M).astype(np.int8)
cand_valid['nearest_pit_m'] = dn
print(f'Positives: {y.sum()} / {len(y)} ({y.mean():.2%})')

# Group by spatial proximity for CV (avoid data leakage)
group_res = 500  # 500m grid cells
gx = (cxy[:, 0] // group_res).astype(int)
gy = (cxy[:, 1] // group_res).astype(int)
groups = gx * 10000 + gy

# ============================================================
# STAGE 3: Ensemble training
# ============================================================
print('\n' + '='*70)
print('STAGE 3: Ensemble (XGB + LightGBM + HistGB) + calibration')
print('='*70)

X_arr = X.fillna(0).to_numpy(dtype=np.float32)
feat_names = list(X.columns)

# GroupKFold CV
n_splits = 5
gkf = GroupKFold(n_splits=n_splits)
oof_xgb = np.zeros(len(y), dtype=np.float64)
oof_lgb = np.zeros(len(y), dtype=np.float64)
oof_hgb = np.zeros(len(y), dtype=np.float64)

for fold, (train_idx, val_idx) in enumerate(gkf.split(X_arr, y, groups)):
    Xtr, Xval = X_arr[train_idx], X_arr[val_idx]
    ytr, yval = y[train_idx], y[val_idx]
    scale = (ytr == 0).sum() / max((ytr == 1).sum(), 1)

    # XGBoost
    dtrain = xgb.DMatrix(Xtr, label=ytr, feature_names=feat_names)
    dval = xgb.DMatrix(Xval, label=yval, feature_names=feat_names)
    params_xgb = dict(
        objective='binary:logistic', eval_metric='aucpr',
        tree_method='hist', max_depth=5, eta=0.05,
        scale_pos_weight=scale, subsample=0.8, colsample_bytree=0.8,
        verbosity=0
    )
    bst = xgb.train(params_xgb, dtrain, num_boost_round=500,
                    evals=[(dval, 'val')], early_stopping_rounds=50, verbose_eval=False)
    oof_xgb[val_idx] = bst.predict(dval)

    # LightGBM
    dtrain_lgb = lgb.Dataset(Xtr, label=ytr)
    params_lgb = dict(
        objective='binary', metric='average_precision',
        num_leaves=31, learning_rate=0.05,
        scale_pos_weight=scale, subsample=0.8, colsample_bytree=0.8,
        verbosity=-1
    )
    bst_lgb = lgb.train(params_lgb, dtrain_lgb, num_boost_round=500,
                        valid_sets=[lgb.Dataset(Xval, label=yval)],
                        callbacks=[lgb.early_stopping(50, verbose=False)])
    oof_lgb[val_idx] = bst_lgb.predict(Xval)

    # HistGradientBoosting
    hgb = HistGradientBoostingClassifier(
        max_depth=5, learning_rate=0.05, max_iter=500,
        early_stopping=True, validation_fraction=0.15,
        class_weight='balanced', random_state=42
    )
    hgb.fit(Xtr, ytr)
    oof_hgb[val_idx] = hgb.predict_proba(Xval)[:, 1]

    print(f'  Fold {fold+1}: XGB={roc_auc_score(yval, oof_xgb[val_idx]):.4f}  '
          f'LGB={roc_auc_score(yval, oof_lgb[val_idx]):.4f}  '
          f'HGB={roc_auc_score(yval, oof_hgb[val_idx]):.4f}')

# Average ensemble
oof_avg = (oof_xgb + oof_lgb + oof_hgb) / 3.0

# Isotonic calibration
iso = IsotonicRegression(out_of_bounds='clip')
iso.fit(oof_avg, y)
proba_cal = iso.predict(oof_avg)

print(f'\nEnsemble OOF metrics:')
print(f'  ROC-AUC:  {roc_auc_score(y, oof_avg):.4f}')
print(f'  PR-AUC:   {average_precision_score(y, oof_avg):.4f}')
print(f'  Calibrated ROC-AUC: {roc_auc_score(y, proba_cal):.4f}')

# ============================================================
# STAGE 4: Save results
# ============================================================
print('\n' + '='*70)
print('STAGE 4: Saving results')
print('='*70)

cand_valid['proba_raw'] = oof_avg
cand_valid['proba'] = proba_cal
cand_valid['is_hit_10m'] = (dn <= 10.0)
cand_valid['is_hit_25m'] = (dn <= 25.0)

cand_out = cand_valid.sort_values('proba', ascending=False).reset_index(drop=True)
cand_out.to_file(DERIV / 'pit_1m_candidates_ensemble.gpkg', driver='GPKG')
print(f'Wrote pit_1m_candidates_ensemble.gpkg ({len(cand_out)} rows)')

# Metrics summary
summary = []
for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
    sub = cand_out[cand_out['proba'] >= thr]
    if len(sub) == 0:
        summary.append((thr, 0, 0, 0, 0, 0.0))
        continue
    sxy = np.c_[sub.geometry.x, sub.geometry.y]
    dn2, _ = tree.query(sxy, k=1)
    hit10 = int((dn2 <= 10).sum())
    _, idx2 = tree.query(sxy[dn2 <= 10], k=1) if hit10 else (None, np.array([]))
    pits_cov = len(np.unique(idx2)) if hit10 else 0
    fp = len(sub) - hit10
    prec = hit10 / max(len(sub), 1)
    summary.append((thr, len(sub), hit10, pits_cov, fp, prec))

with open(DERIV / 'pit_1m_ensemble_metrics.txt', 'w') as f:
    f.write(f'Ensemble OOF ROC-AUC:  {roc_auc_score(y, oof_avg):.4f}\n')
    f.write(f'Ensemble OOF PR-AUC:   {average_precision_score(y, oof_avg):.4f}\n\n')
    f.write(f'{"thr":>5} {"n":>7} {"hits10":>7} {"pits_cov":>9} {"fp":>7} {"prec":>7}\n')
    for thr, n, h, p, fp, pr in summary:
        f.write(f'{thr:5.2f} {n:7d} {h:7d} {p:9d} {fp:7d} {pr:7.2%}\n')

print(f'\n{"thr":>5} {"n":>7} {"hits10":>7} {"pits_cov":>9} {"fp":>7} {"prec":>7}')
for thr, n, h, p, fp, pr in summary:
    print(f'{thr:5.2f} {n:7d} {h:7d} {p:9d} {fp:7d} {pr:7.2%}')

# Feature importance (retrain full XGB for importance)
dtrain_full = xgb.DMatrix(X_arr, label=y, feature_names=feat_names)
bst_full = xgb.train(params_xgb, dtrain_full, num_boost_round=300, verbose_eval=False)
imp = bst_full.get_score(importance_type='gain')
imp_s = pd.Series(imp).sort_values(ascending=True).tail(25)

fig, ax = plt.subplots(figsize=(8, 8))
imp_s.plot(kind='barh', ax=ax)
ax.set_title('Top-25 feature importance (XGB gain)')
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(DERIV / 'pit_1m_ensemble_feature_importance.png', dpi=130, bbox_inches='tight')
plt.close(fig)

# Threshold maps
for thr in [0.30, 0.50, 0.70]:
    sub = cand_out[cand_out['proba'] >= thr]
    if len(sub) == 0:
        continue

    # Use the largest tile's hillshade for viz
    biggest_tag = max(TILES.keys(), key=lambda t: get_tile_meta(TILES[t])[1][0] * get_tile_meta(TILES[t])[1][1])
    biggest_suffix = TILES[biggest_tag]
    bounds, shape = get_tile_meta(biggest_suffix)
    X0v, Y0v, X1v, Y1v = bounds.left, bounds.bottom, bounds.right, bounds.top

    hs = read_tile(biggest_suffix, 'hillshade')
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.imshow(hs, cmap='gray', extent=[X0v, X1v, Y0v, Y1v], origin='upper', alpha=0.8)

    sub_in = sub.cx[X0v:X1v, Y0v:Y1v]
    if len(sub_in) > 0:
        ax.scatter(sub_in.geometry.x, sub_in.geometry.y, c=sub_in['proba'],
                   cmap='YlOrRd', s=15, edgecolors='k', linewidths=0.3, vmin=thr, vmax=1.0)

    # Annotated pits in this extent
    pits_in = pits_all.cx[X0v:X1v, Y0v:Y1v]
    if len(pits_in) > 0:
        ax.scatter(pits_in.geometry.x, pits_in.geometry.y, marker='x', c='cyan', s=20, linewidths=0.8)

    ax.set_title(f'Pit candidates proba >= {thr:.2f} ({len(sub_in)} shown, cyan=annotated)')
    ax.set_xlim(X0v, X1v); ax.set_ylim(Y0v, Y1v)
    fig.tight_layout()
    fig.savefig(DERIV / f'pit_1m_ensemble_thr{int(thr*100)}.png', dpi=130, bbox_inches='tight')
    plt.close(fig)

print('\nDone. All outputs written to data/derivatives/pit_1m_*')
