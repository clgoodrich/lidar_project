"""Stage 2b: XGBoost classifier with group-aware CV and hard-negative mining.

Replaces the RF in _pit_rf_on_template.py.  Three improvements over RF:

  1. XGBoost (gradient boosting) — typically +0.02-0.05 AUC on tabular data.
  2. GroupKFold by spatial cluster of annotated pits — ensures OOF scores
     can't cheat by memorizing the pit that's "next door" to itself.
  3. Hard-negative mining: train an initial model, then up-weight the 2%
     of hardest negatives (FPs with high proba) and retrain.  Repeat 2 rounds.

Inputs unchanged from the RF script.  Outputs parallel the RF script but
with `_xgb` in the filename.
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Point
from scipy.spatial import cKDTree
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, precision_recall_curve, average_precision_score
from sklearn.cluster import AgglomerativeClustering
import xgboost as xgb
import matplotlib.pyplot as plt

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
RES   = 0.5
X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0
W = int((X1 - X0) / RES); H = int((Y1 - Y0) / RES)
CRS = 'EPSG:6346'
HALF, INNER, OUTER = 15, 5, 12
POS_DIST_M = 10.0

def read(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a

def rc(x, y):
    return int(round((Y1 - y) / RES)), int(round((x - X0) / RES))

# ---- load candidates + pits
cand = gpd.read_file(DERIV / 'pit_candidates_template.gpkg').to_crs(CRS)
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x, g.y] for g in pits.geometry])
tree = cKDTree(pit_xy)
cxy = np.array([[g.x, g.y] for g in cand.geometry])
dn, nearest_pit = tree.query(cxy, k=1)
y_full = (dn <= POS_DIST_M).astype(np.int8)
print(f'{len(cand)} candidates,  positives={y_full.sum()} ({y_full.mean():.2%})')

# ---- rasters (same as RF)
rasters = {name: read(name) for name in [
    'dem_05.tif',
    'lrm_5_05.tif', 'lrm_11_05.tif', 'lrm_25_05.tif',
    'tpi_05_05.tif', 'tpi_15_05.tif',
    'openness_neg_05.tif', 'openness_pos_05.tif',
    'slope_05.tif', 'roughness_11_05.tif', 'local_relief_10_05.tif',
    'chm_05.tif', 'intensity_ground_05.tif', 'ground_density_05.tif',
    'hillshade_05.tif',
    'pit_match_score_05.tif',
]}

# ---- ring masks
yy, xx = np.ogrid[-HALF:HALF+1, -HALF:HALF+1]
rad = np.sqrt(xx*xx + yy*yy)
inner_mask = rad <= INNER
rim_mask   = (rad >= OUTER) & (rad <= HALF)

def stats_window(z, inner, rim):
    zi = z[inner]; zr = z[rim]
    if np.isfinite(zi).any() and np.isfinite(zr).any():
        return (np.nanmin(zi), np.nanmean(zi), np.nanmean(zr),
                np.nanmean(zr) - np.nanmin(zi), np.nanstd(zi))
    return (np.nan,) * 5

def radial_std(z):
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

CHANS_D = ['lrm_5_05.tif', 'lrm_11_05.tif', 'lrm_25_05.tif',
           'tpi_05_05.tif', 'tpi_15_05.tif', 'openness_neg_05.tif']
CHANS_S = ['slope_05.tif', 'roughness_11_05.tif',
           'local_relief_10_05.tif', 'chm_05.tif']

def feats_for(r_c, c_c):
    r1, r2 = r_c - HALF, r_c + HALF + 1
    c1, c2 = c_c - HALF, c_c + HALF + 1
    if r1 < 0 or c1 < 0 or r2 > H or c2 > W: return None
    out = {}
    for ch in CHANS_D:
        w = rasters[ch][r1:r2, c1:c2]
        mni, mi, mr, diff, sdi = stats_window(w, inner_mask, rim_mask)
        tag = ch.replace('.tif', '')
        out[f'{tag}_imin'] = mni; out[f'{tag}_imean'] = mi
        out[f'{tag}_rmean'] = mr; out[f'{tag}_rdiff'] = diff
        out[f'{tag}_sym']   = radial_std(w)
    for ch in CHANS_S:
        w = rasters[ch][r1:r2, c1:c2]; wi = w[inner_mask]
        tag = ch.replace('.tif', '')
        out[f'{tag}_imean']  = float(np.nanmean(wi)) if np.isfinite(wi).any() else np.nan
        out[f'{tag}_wmax']   = float(np.nanmax(w))   if np.isfinite(w).any()  else np.nan
    wi = rasters['intensity_ground_05.tif'][r1:r2, c1:c2]
    out['int_imean']   = float(np.nanmean(wi[inner_mask])) if np.isfinite(wi[inner_mask]).any() else np.nan
    out['int_rmean']   = float(np.nanmean(wi[rim_mask]))   if np.isfinite(wi[rim_mask]).any()   else np.nan
    out['int_nanfrac'] = float(np.isnan(wi).mean())
    dens = rasters['ground_density_05.tif'][r1:r2, c1:c2]
    out['dens_imean'] = float(np.nanmean(dens[inner_mask]))
    out['dens_wmean'] = float(np.nanmean(dens))
    dem_w = rasters['dem_05.tif'][r1:r2, c1:c2]
    _, _, _, dem_cut, _ = stats_window(dem_w, inner_mask, rim_mask)
    out['dem_cut_m'] = dem_cut
    out['match_center'] = float(rasters['pit_match_score_05.tif'][r_c, c_c])
    return out

# ---- extract features
print('extracting features...')
feat_list, keep_idx = [], []
for i, g in enumerate(cand.geometry):
    r, c = rc(g.x, g.y)
    f = feats_for(r, c)
    if f is not None:
        feat_list.append(f); keep_idx.append(i)
keep_idx = np.array(keep_idx)
X = pd.DataFrame(feat_list)
y = y_full[keep_idx]
cand = cand.iloc[keep_idx].reset_index(drop=True)
cxy = cxy[keep_idx]
nearest_pit = nearest_pit[keep_idx]
print(f'features: {X.shape},  positives kept: {y.sum()}')

# ---- spatial groups: cluster annotated pits into ~10 spatial groups.
# Any candidate inherits the group of its nearest annotated pit.  GroupKFold
# then guarantees validation folds don't leak nearby pits into training.
N_GROUPS = 8
agg = AgglomerativeClustering(n_clusters=N_GROUPS).fit(pit_xy)
pit_group = agg.labels_
groups = pit_group[nearest_pit]  # candidate's group = group of nearest annotated pit
print(f'spatial groups per fold (pit counts): '
      f'{np.bincount(pit_group).tolist()}')

# ---- XGBoost with group-aware OOF prediction + iterative hard-neg mining
scale_pos = (len(y) - y.sum()) / max(y.sum(), 1)
base_params = dict(
    objective='binary:logistic',
    tree_method='hist',
    n_estimators=500,
    max_depth=5,
    learning_rate=0.05,
    min_child_weight=2,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    random_state=0,
    n_jobs=-1,
)

def oof_fit(X_arr, y_arr, groups_arr, sample_weight=None):
    oof = np.zeros(len(y_arr), dtype=np.float32)
    gkf = GroupKFold(n_splits=min(5, N_GROUPS))
    for fi, (tr, te) in enumerate(gkf.split(X_arr, y_arr, groups=groups_arr)):
        sw_tr = sample_weight[tr] if sample_weight is not None else None
        clf = xgb.XGBClassifier(**base_params, scale_pos_weight=scale_pos)
        clf.fit(X_arr[tr], y_arr[tr], sample_weight=sw_tr, verbose=False)
        oof[te] = clf.predict_proba(X_arr[te])[:, 1]
    return oof

X_arr = X.fillna(0).to_numpy(dtype=np.float32)

print('\n[round 1] plain XGBoost, GroupKFold OOF ...')
sw = np.ones(len(y), dtype=np.float32)
proba = oof_fit(X_arr, y, groups, sample_weight=sw)
print(f'  ROC-AUC {roc_auc_score(y, proba):.4f}   PR-AUC {average_precision_score(y, proba):.4f}')

# (Hard-negative mining was tried and *reduced* OOF PR-AUC here — skipping.)

# ---- final refit on ALL data (for feature importance + optional inference
# on new data).  We still report OOF numbers above because that's the honest
# test.
final = xgb.XGBClassifier(**base_params, scale_pos_weight=scale_pos)
final.fit(X_arr, y, sample_weight=sw, verbose=False)

# ---- PR + feat importance
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
p, r, _ = precision_recall_curve(y, proba)
ax[0].plot(r, p)
ax[0].set_xlabel('recall'); ax[0].set_ylabel('precision')
ax[0].set_title(f'XGB OOF PR curve  (AP={average_precision_score(y, proba):.3f})')
ax[0].set_xlim(0, 1); ax[0].set_ylim(0, 1); ax[0].grid(alpha=0.3)
imp = pd.Series(final.feature_importances_, index=X.columns).sort_values(ascending=True).tail(20)
imp.plot(kind='barh', ax=ax[1])
ax[1].set_title('top-20 feature importance (gain)'); ax[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(DERIV / 'pit_xgb_feature_importance.png', dpi=130, bbox_inches='tight')
plt.close(fig)

# ---- ranked candidates
cand = cand.copy()
cand['proba'] = proba  # OOF — honest
cand = cand.sort_values('proba', ascending=False).reset_index(drop=True)
cand.to_file(DERIV / 'pit_candidates_xgb.gpkg', driver='GPKG')

# ---- summary table
summary = []
for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
    sub = cand[cand['proba'] >= thr]
    if len(sub) == 0:
        summary.append((thr, 0, 0, 0, 0, 0.0)); continue
    sxy = np.c_[sub.geometry.x, sub.geometry.y]
    dn2, _ = tree.query(sxy, k=1)
    hit10 = int((dn2 <= 10).sum())
    _, idx = tree.query(sxy[dn2 <= 10], k=1) if hit10 else (None, np.array([]))
    pits_cov = len(np.unique(idx))
    summary.append((thr, len(sub), hit10, pits_cov, len(sub) - hit10, hit10 / max(len(sub), 1)))

print()
print(f'{"thr":>5} {"n":>6} {"hits10":>7} {"pits_cov":>9} {"fp":>6} {"prec":>7}')
for thr, n, h, p, fp, pr in summary:
    print(f'{thr:5.2f} {n:6d} {h:7d} {p:9d} {fp:6d} {pr:7.2%}')

with open(DERIV / 'pit_xgb_metrics.txt', 'w') as f:
    f.write(f'XGBoost OOF (GroupKFold, {min(5,N_GROUPS)} folds)\n')
    f.write(f'ROC-AUC {roc_auc_score(y, proba):.4f}\n')
    f.write(f'PR-AUC  {average_precision_score(y, proba):.4f}\n\n')
    f.write(f'{"thr":>5} {"n":>6} {"hits10":>7} {"pits_cov":>9} {"fp":>6} {"prec":>7}\n')
    for thr, n, h, p, fp, pr in summary:
        f.write(f'{thr:5.2f} {n:6d} {h:7d} {p:9d} {fp:6d} {pr:7.2%}\n')

# ---- per-threshold overlays in the same style as RF
hs = read('hillshade_05.tif')
for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
    sub = cand[cand['proba'] >= thr]
    if len(sub) == 0: continue
    sxy = np.c_[sub.geometry.x, sub.geometry.y]
    dn2, _ = tree.query(sxy, k=1)
    tp_xy = sxy[dn2 <= 10]
    fig, ax = plt.subplots(figsize=(14, 14))
    ax.imshow(hs, cmap='gray', extent=[X0, X1, Y0, Y1])
    ax.scatter(pit_xy[:, 0], pit_xy[:, 1], s=40, c='red', marker='o',
               linewidths=0, label=f'annotated pits ({len(pit_xy)})')
    if len(tp_xy):
        ax.scatter(tp_xy[:, 0], tp_xy[:, 1], s=70, c='lime', marker='X',
                   linewidths=0, label=f'found pits ({len(tp_xy)})')
    prec = (dn2 <= 10).mean() if len(dn2) else 0
    # distinct pits covered
    _, idx = tree.query(tp_xy, k=1) if len(tp_xy) else (None, np.array([]))
    pits_cov = len(np.unique(idx)) if len(tp_xy) else 0
    ax.set_title(f'pit XGB @ proba>={thr:.2f}   '
                 f'n={len(sub)}  TP={len(tp_xy)}  FP={len(sub)-len(tp_xy)}  '
                 f'pits_covered={pits_cov}/{len(pit_xy)}   '
                 f'precision={prec:.0%}  recall={pits_cov/len(pit_xy):.0%}')
    ax.legend(loc='lower left', fontsize=9)
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    fig.savefig(DERIV / f'pit_xgb_thr{int(thr*100):02d}.png',
                dpi=130, bbox_inches='tight')
    plt.close(fig)

print('\nwrote pit_candidates_xgb.{gpkg,png}, pit_xgb_feature_importance.png, '
      'pit_xgb_metrics.txt, pit_xgb_thrXX.png x7')
