"""Combined pit detector: U-Net candidate generation → XGBoost classification.

Strategy:
  1. Use U-Net probability map to generate candidates (peak_local_max at low threshold)
  2. Extract the same features the XGBoost pipeline uses per candidate
  3. Add U-Net probability as an additional feature
  4. Train XGBoost ensemble with spatial cross-validation
  5. Compare recall/precision against standalone XGBoost and standalone U-Net

This should capture the U-Net's high recall while leveraging XGBoost's
precision filtering.
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Point
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from skimage.feature import peak_local_max
import xgboost as xgb
import lightgbm as lgb
import matplotlib.pyplot as plt
import warnings, time, glob
warnings.filterwarnings('ignore')

DERIV = Path('data/derivatives')
ANNO = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'
RES = 1.0
POS_DIST_M = 10.0
HALF = 8
INNER = 3
OUTER = 6
MIN_DIST_PEAKS = 5
UNET_CAND_THR = 0.20  # low threshold to cast a wide net

TILES = {}
for dem_path in sorted(glob.glob(str(DERIV / 'dem_*_1m.tif'))):
    p = Path(dem_path)
    suffix = p.name.replace('dem', '')
    tag = suffix.replace('_1m.tif', '').strip('_')
    required = ['lrm_5', 'lrm_11', 'tpi_05', 'openness_neg', 'slope', 'hillshade',
                'lrm_25', 'tpi_15', 'chm', 'ground_density', 'roughness_5',
                'local_relief_10', 'openness_pos']
    if all((DERIV / f'{r}{suffix}').exists() for r in required):
        TILES[tag] = suffix

print(f'Tiles: {list(TILES.keys())}')


def read_tile(suffix, prefix):
    path = DERIV / f'{prefix}{suffix}'
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            a = np.where(a == nd, np.nan, a)
        return a


def get_tile_meta(suffix):
    with rasterio.open(DERIV / f'dem{suffix}') as ds:
        return ds.bounds, ds.shape


# Load annotations
pits_all = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
print(f'Annotated pits: {len(pits_all)}')

# ============================================================
# STAGE 1: Generate candidates from U-Net probability maps
# ============================================================
print('\n' + '='*70)
print('STAGE 1: U-Net candidate generation')
print('='*70)

all_candidates = []
for tag, suffix in TILES.items():
    pred_path = DERIV / f'pit_unet_pred_{tag}.tif'
    if not pred_path.exists():
        print(f'  {tag}: no U-Net prediction, skipping')
        continue

    bounds, shape = get_tile_meta(suffix)
    H, W = shape
    X0, Y1 = bounds.left, bounds.top

    with rasterio.open(pred_path) as ds:
        prob = ds.read(1).astype(np.float32)

    prob_clean = np.where(prob >= 0, prob, 0.0)
    coords = peak_local_max(prob_clean, min_distance=MIN_DIST_PEAKS,
                            threshold_abs=UNET_CAND_THR, exclude_border=HALF)
    print(f'  {tag}: {len(coords)} candidates at thr={UNET_CAND_THR}')

    for (r, c) in coords:
        x = X0 + (c + 0.5) * RES
        y = Y1 - (r + 0.5) * RES
        all_candidates.append({
            'x': x, 'y': y,
            'unet_prob': float(prob[r, c]),
            'tile': tag,
        })

cand_df = pd.DataFrame(all_candidates)
cand_gdf = gpd.GeoDataFrame(
    cand_df.drop(columns=['x', 'y']),
    geometry=[Point(x, y) for x, y in zip(cand_df['x'], cand_df['y'])],
    crs=CRS
)
print(f'\nTotal U-Net candidates: {len(cand_gdf)}')

# ============================================================
# STAGE 2: Feature extraction (same as _pit_pipeline_1m.py)
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
    out = {}
    center = lrm_win[HALF, HALF]
    out['morph_center_depth'] = float(center) if np.isfinite(center) else np.nan
    for rmin, rmax, label in [(0, 2, 'r0_2'), (2, 5, 'r2_5'), (5, 8, 'r5_8')]:
        ring = (rad >= rmin) & (rad < rmax)
        vals = lrm_win[ring]
        out[f'morph_ring_{label}'] = float(np.nanmean(vals)) if np.isfinite(vals).any() else np.nan
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
    inner_sum = np.nansum(np.abs(lrm_win[inner_mask]))
    total_sum = np.nansum(np.abs(lrm_win))
    out['morph_compactness'] = float(inner_sum / total_sum) if total_sum > 0 else np.nan
    return out


def extract_features_for_tile(tag, suffix, candidates_in_tile):
    bounds, shape = get_tile_meta(suffix)
    H, W = shape
    X0, Y0, X1, Y1 = bounds.left, bounds.bottom, bounds.right, bounds.top

    rasters = {}
    for ch in DEPTH_CHANNELS + SURFACE_CHANNELS + ['ground_density', 'dem']:
        rasters[ch] = read_tile(suffix, ch)

    # Template match score
    match_path = DERIV / f'pit_1m_match_score_{tag}.tif'
    if match_path.exists():
        with rasterio.open(match_path) as ds:
            rasters['match_score'] = ds.read(1).astype(np.float32)
    else:
        rasters['match_score'] = np.zeros(shape, dtype=np.float32)

    # Geomorphon enclosure
    for lookup in [5, 8, 12]:
        enc_path = DERIV / f'geomorphon_enc_{lookup}{suffix}'
        if enc_path.exists():
            with rasterio.open(enc_path) as ds:
                enc = ds.read(1).astype(np.float32)
                enc[enc == 255] = np.nan
                rasters[f'enc_{lookup}'] = enc
        else:
            rasters[f'enc_{lookup}'] = np.full(shape, np.nan, dtype=np.float32)

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

        for ch in DEPTH_CHANNELS:
            w = rasters[ch][r1:r2, c1:c2]
            mni, mi, mr, diff, sdi = stats_window(w, inner_mask, rim_mask)
            out[f'{ch}_inner_min'] = mni
            out[f'{ch}_inner_mean'] = mi
            out[f'{ch}_rim_mean'] = mr
            out[f'{ch}_rim_minus'] = diff
            out[f'{ch}_sym'] = radial_std(w)

        for ch in SURFACE_CHANNELS:
            w = rasters[ch][r1:r2, c1:c2]
            wi = w[inner_mask]
            out[f'{ch}_inner_mean'] = float(np.nanmean(wi)) if np.isfinite(wi).any() else np.nan
            out[f'{ch}_window_max'] = float(np.nanmax(w)) if np.isfinite(w).any() else np.nan

        dens = rasters['ground_density'][r1:r2, c1:c2]
        out['density_inner_mean'] = float(np.nanmean(dens[inner_mask]))
        out['density_window_mean'] = float(np.nanmean(dens))

        dem_w = rasters['dem'][r1:r2, c1:c2]
        _, _, _, dem_cut, _ = stats_window(dem_w, inner_mask, rim_mask)
        out['dem_cut_m'] = dem_cut

        out['match_score_center'] = float(rasters['match_score'][r, c])

        for lookup in [5, 8, 12]:
            enc_r = rasters[f'enc_{lookup}']
            out[f'enc_{lookup}_center'] = float(enc_r[r, c]) if np.isfinite(enc_r[r, c]) else np.nan
            enc_win = enc_r[r1:r2, c1:c2]
            enc_inner = enc_win[inner_mask]
            out[f'enc_{lookup}_inner_mean'] = float(np.nanmean(enc_inner)) if np.isfinite(enc_inner).any() else np.nan

        lrm5_w = rasters['lrm_5'][r1:r2, c1:c2]
        morph = morphology_feats(lrm5_w)
        out.update(morph)

        # U-Net probability as a feature
        out['unet_prob'] = float(row['unet_prob'])

        feat_list.append(out)

    return feat_list


print('Extracting features per tile...')
all_feats = []
valid_indices = []

for tag, suffix in TILES.items():
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

# Spatial groups for CV
group_res = 500
gx = (cxy[:, 0] // group_res).astype(int)
gy = (cxy[:, 1] // group_res).astype(int)
groups = gx * 10000 + gy

# ============================================================
# STAGE 3: Ensemble training
# ============================================================
print('\n' + '='*70)
print('STAGE 3: Ensemble (XGB + LightGBM + HistGB) + calibration')
print('='*70)

feature_names = list(X.columns)
Xnp = X.values.astype(np.float32)
n_splits = 5
gkf = GroupKFold(n_splits=n_splits)

oof_xgb = np.zeros(len(y), dtype=np.float32)
oof_lgb = np.zeros(len(y), dtype=np.float32)
oof_hgb = np.zeros(len(y), dtype=np.float32)

for fold, (tri, vai) in enumerate(gkf.split(Xnp, y, groups)):
    Xt, yt = Xnp[tri], y[tri]
    Xv, yv = Xnp[vai], y[vai]

    scale = (yt == 0).sum() / max((yt == 1).sum(), 1)

    # XGBoost
    m_xgb = xgb.XGBClassifier(
        objective='binary:logistic', tree_method='hist',
        n_estimators=500, max_depth=5, learning_rate=0.05,
        min_child_weight=2, subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=scale, eval_metric='aucpr',
        early_stopping_rounds=30, verbosity=0)
    m_xgb.fit(Xt, yt, eval_set=[(Xv, yv)], verbose=False)
    oof_xgb[vai] = m_xgb.predict_proba(Xv)[:, 1]

    # LightGBM
    m_lgb = lgb.LGBMClassifier(
        objective='binary', metric='average_precision', num_leaves=31,
        n_estimators=500, learning_rate=0.05, min_child_samples=10,
        subsample=0.8, colsample_bytree=0.8, scale_pos_weight=scale,
        verbosity=-1, early_stopping_round=30)
    m_lgb.fit(Xt, yt, eval_set=[(Xv, yv)])
    oof_lgb[vai] = m_lgb.predict_proba(Xv)[:, 1]

    # HistGradientBoosting
    m_hgb = HistGradientBoostingClassifier(
        max_iter=500, max_depth=5, learning_rate=0.05,
        min_samples_leaf=10, early_stopping=True, validation_fraction=0.15,
        scoring='average_precision')
    m_hgb.fit(Xt, yt)
    oof_hgb[vai] = m_hgb.predict_proba(Xv)[:, 1]

    print(f'  fold {fold+1}/{n_splits}: pos={yt.sum()}, '
          f'xgb={roc_auc_score(yv, oof_xgb[vai]):.4f}, '
          f'lgb={roc_auc_score(yv, oof_lgb[vai]):.4f}, '
          f'hgb={roc_auc_score(yv, oof_hgb[vai]):.4f}')

# Ensemble average
p_avg = (oof_xgb + oof_lgb + oof_hgb) / 3.0

# Isotonic calibration
iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds='clip')
iso.fit(p_avg, y)
p_cal = iso.predict(p_avg)

roc = roc_auc_score(y, p_cal)
pr = average_precision_score(y, p_cal)
print(f'\nEnsemble OOF: ROC-AUC={roc:.4f}  PR-AUC={pr:.4f}')

# Save candidates with probabilities
cand_valid['proba'] = p_cal
cand_valid = cand_valid.sort_values('proba', ascending=False).reset_index(drop=True)
cand_valid.to_file(DERIV / 'pit_combined_candidates.gpkg', driver='GPKG')

# Threshold analysis
pit_tree = cKDTree(pit_xy)
print(f'\n{"thr":>5} {"n":>7} {"hits10":>7} {"pits_cov":>9} {"fp":>7} {"prec":>7}')
print('-' * 55)

lines = []
for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
    sub = cand_valid[cand_valid['proba'] >= thr]
    if len(sub) == 0:
        line = f'{thr:5.2f} {0:7d} {0:7d} {0:9d} {0:7d} {"N/A":>7}'
        print(line); lines.append(line); continue
    sxy = np.c_[sub.geometry.x, sub.geometry.y]
    dn2, idx2 = pit_tree.query(sxy, k=1)
    hit10 = int((dn2 <= 10).sum())
    matched = np.unique(idx2[dn2 <= 10])
    pits_cov = len(matched)
    fp = len(sub) - hit10
    prec = hit10 / len(sub)
    line = f'{thr:5.2f} {len(sub):7d} {hit10:7d} {pits_cov:9d} {fp:7d} {prec:7.2%}'
    print(line)
    lines.append(line)

# Feature importance
imp = m_xgb.feature_importances_
top_idx = np.argsort(imp)[::-1][:25]
fig, ax = plt.subplots(figsize=(10, 8))
ax.barh(range(len(top_idx)), imp[top_idx][::-1])
ax.set_yticks(range(len(top_idx)))
ax.set_yticklabels([feature_names[i] for i in top_idx][::-1])
ax.set_title('Top-25 feature importance — Combined U-Net + XGB')
ax.grid(axis='x', alpha=0.3)
fig.tight_layout()
fig.savefig(str(DERIV / 'pit_combined_feature_importance.png'), dpi=130, bbox_inches='tight')
plt.close(fig)

# Save metrics
with open(DERIV / 'pit_combined_metrics.txt', 'w') as f:
    f.write(f'Combined U-Net + XGBoost pipeline\n')
    f.write(f'U-Net candidate threshold: {UNET_CAND_THR}\n')
    f.write(f'Ensemble OOF ROC-AUC: {roc:.4f}\n')
    f.write(f'Ensemble OOF PR-AUC:  {pr:.4f}\n\n')
    f.write(f'{"thr":>5} {"n":>7} {"hits10":>7} {"pits_cov":>9} {"fp":>7} {"prec":>7}\n')
    for line in lines:
        f.write(line + '\n')
    f.write(f'\nComparison:\n')
    f.write(f'  XGBoost-only @0.80:   95 pits, 93.6% precision, 7 FP\n')
    f.write(f'  U-Net-only @0.80:    792 pits, 43.2% precision, 1331 FP\n')

print(f'\nSaved: pit_combined_candidates.gpkg, pit_combined_metrics.txt')
