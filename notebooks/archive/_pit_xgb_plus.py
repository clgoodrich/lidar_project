"""Stage 2c: XGBoost + 2008 temporal features + pad/road priors.

Superset of _pit_xgb_on_template.py.  Adds two new feature groups:

  (a) 2008 1 m derivatives at each candidate's location.  A real pit is
      present in BOTH 2019 AND 2008 — tree throws and recent debris are not.
      New features: depth/rim/symmetry on lrm_5_2008_1m, lrm_11_2008_1m,
      openness_neg_2008_1m, tpi_15_2008_1m, plus absolute dem_cut_2008_m
      and the 2019-2008 depth *change*.

  (b) Pad/road proximity priors.  in_pad (binary), dist_to_pad_m,
      dist_to_road_m — pits cluster inside pads and near old haul roads.

Outputs use `_plus` suffix so they don't overwrite the pure-XGB results:
  pit_candidates_xgb_plus.gpkg / .png
  pit_xgb_plus_feature_importance.png
  pit_xgb_plus_metrics.txt
  pit_xgb_plus_thrXX.png x7
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
X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0
CRS = 'EPSG:6346'
POS_DIST_M = 10.0

# 2019 0.5 m grid
RES19 = 0.5
W19 = int((X1 - X0) / RES19); H19 = int((Y1 - Y0) / RES19)
HALF19, INNER19, OUTER19 = 15, 5, 12

# 2008 1 m grid
RES08 = 1.0
W08 = int((X1 - X0) / RES08); H08 = int((Y1 - Y0) / RES08)
HALF08, INNER08, OUTER08 = 8, 3, 6   # ~ same metric windows as 2019


def read(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a


def make_rings(HALF, INNER, OUTER):
    yy, xx = np.ogrid[-HALF:HALF+1, -HALF:HALF+1]
    rad = np.sqrt(xx*xx + yy*yy)
    return rad <= INNER, (rad >= OUTER) & (rad <= HALF)

RING_IN_19, RING_RIM_19 = make_rings(HALF19, INNER19, OUTER19)
RING_IN_08, RING_RIM_08 = make_rings(HALF08, INNER08, OUTER08)


def stats_window(z, inner, rim):
    zi = z[inner]; zr = z[rim]
    if np.isfinite(zi).any() and np.isfinite(zr).any():
        return (np.nanmin(zi), np.nanmean(zi), np.nanmean(zr),
                np.nanmean(zr) - np.nanmin(zi), np.nanstd(zi))
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


# ---- load candidates + pits
cand = gpd.read_file(DERIV / 'pit_candidates_template.gpkg').to_crs(CRS)
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pads = gpd.read_file(ANNO / 'pads_truth.gpkg').to_crs(CRS)
roads = gpd.read_file(ANNO / 'roads_truth.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x, g.y] for g in pits.geometry])
tree_pit = cKDTree(pit_xy)
cxy = np.array([[g.x, g.y] for g in cand.geometry])
dn, nearest_pit = tree_pit.query(cxy, k=1)
y_full = (dn <= POS_DIST_M).astype(np.int8)
print(f'{len(cand)} candidates,  positives={y_full.sum()} ({y_full.mean():.2%})')

# ---- 2019 rasters
RAST19 = {name: read(name) for name in [
    'dem_05.tif',
    'lrm_5_05.tif', 'lrm_11_05.tif', 'lrm_25_05.tif',
    'tpi_05_05.tif', 'tpi_15_05.tif',
    'openness_neg_05.tif', 'openness_pos_05.tif',
    'slope_05.tif', 'roughness_11_05.tif', 'local_relief_10_05.tif',
    'chm_05.tif', 'intensity_ground_05.tif', 'ground_density_05.tif',
    'hillshade_05.tif',
    'pit_match_score_05.tif',
]}

# ---- 2008 rasters (1 m)
RAST08 = {name: read(name) for name in [
    'dem_2008_1m.tif',
    'lrm_5_2008_1m.tif', 'lrm_11_2008_1m.tif',
    'tpi_15_2008_1m.tif',
    'openness_neg_2008_1m.tif',
    'slope_2008_1m.tif',
    'chm_2008_1m.tif', 'ground_density_2008_1m.tif',
]}

# ---- coord converters
def rc19(x, y):
    return int(round((Y1 - y) / RES19)), int(round((x - X0) / RES19))

def rc08(x, y):
    return int(round((Y1 - y) / RES08)), int(round((x - X0) / RES08))

# ---- 2019 feature channels
CHANS_D_19 = ['lrm_5_05.tif', 'lrm_11_05.tif', 'lrm_25_05.tif',
              'tpi_05_05.tif', 'tpi_15_05.tif', 'openness_neg_05.tif']
CHANS_S_19 = ['slope_05.tif', 'roughness_11_05.tif',
              'local_relief_10_05.tif', 'chm_05.tif']
CHANS_D_08 = ['lrm_5_2008_1m.tif', 'lrm_11_2008_1m.tif',
              'tpi_15_2008_1m.tif', 'openness_neg_2008_1m.tif']


def feats_for(x, y):
    r19, c19 = rc19(x, y)
    r1, r2 = r19 - HALF19, r19 + HALF19 + 1
    c1, c2 = c19 - HALF19, c19 + HALF19 + 1
    if r1 < 0 or c1 < 0 or r2 > H19 or c2 > W19: return None
    r08, c08 = rc08(x, y)
    r1b, r2b = r08 - HALF08, r08 + HALF08 + 1
    c1b, c2b = c08 - HALF08, c08 + HALF08 + 1
    if r1b < 0 or c1b < 0 or r2b > H08 or c2b > W08: return None

    out = {}
    # 2019 depth channels
    for ch in CHANS_D_19:
        w = RAST19[ch][r1:r2, c1:c2]
        mni, mi, mr, diff, sdi = stats_window(w, RING_IN_19, RING_RIM_19)
        tag = ch.replace('.tif', '')
        out[f'{tag}_imin']  = mni
        out[f'{tag}_imean'] = mi
        out[f'{tag}_rmean'] = mr
        out[f'{tag}_rdiff'] = diff
        out[f'{tag}_sym']   = radial_std(w, HALF19, INNER19)
    # 2019 surface
    for ch in CHANS_S_19:
        w = RAST19[ch][r1:r2, c1:c2]; wi = w[RING_IN_19]
        tag = ch.replace('.tif', '')
        out[f'{tag}_imean'] = float(np.nanmean(wi)) if np.isfinite(wi).any() else np.nan
        out[f'{tag}_wmax']  = float(np.nanmax(w))   if np.isfinite(w).any()  else np.nan
    # 2019 extras
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
    out['match_center'] = float(RAST19['pit_match_score_05.tif'][r19, c19])

    # 2008 depth channels
    for ch in CHANS_D_08:
        w = RAST08[ch][r1b:r2b, c1b:c2b]
        mni, mi, mr, diff, sdi = stats_window(w, RING_IN_08, RING_RIM_08)
        tag = ch.replace('.tif', '').replace('_2008_1m', '_08')
        out[f'{tag}_imin']  = mni
        out[f'{tag}_imean'] = mi
        out[f'{tag}_rmean'] = mr
        out[f'{tag}_rdiff'] = diff
        out[f'{tag}_sym']   = radial_std(w, HALF08, INNER08)
    # 2008 extras
    dem_w08 = RAST08['dem_2008_1m.tif'][r1b:r2b, c1b:c2b]
    _, _, _, dem_cut_08, _ = stats_window(dem_w08, RING_IN_08, RING_RIM_08)
    out['dem_cut_08_m'] = dem_cut_08
    slope08 = RAST08['slope_2008_1m.tif'][r1b:r2b, c1b:c2b][RING_IN_08]
    out['slope_08_imean'] = float(np.nanmean(slope08)) if np.isfinite(slope08).any() else np.nan
    chm08 = RAST08['chm_2008_1m.tif'][r1b:r2b, c1b:c2b]
    out['chm_08_wmax'] = float(np.nanmax(chm08)) if np.isfinite(chm08).any() else np.nan
    dens08 = RAST08['ground_density_2008_1m.tif'][r1b:r2b, c1b:c2b][RING_IN_08]
    out['dens_08_imean'] = float(np.nanmean(dens08))

    # temporal persistence: |2019 depth| vs |2008 depth|
    # (large + both times -> real pit)
    out['both_depths'] = -min(out.get('lrm_5_05_imin', 0) or 0,
                              out.get('lrm_5_08_imin', 0) or 0)
    return out


# ---- pad / road priors via vectorized nearest-distance
#  (convert pads to boundary + interior-contains, roads to geometry)
from shapely import make_valid
pads_clean = gpd.GeoSeries([make_valid(g) for g in pads.geometry], crs=CRS)
roads_clean = gpd.GeoSeries([make_valid(g) for g in roads.geometry], crs=CRS)
pad_union = pads_clean.union_all()
road_union = roads_clean.union_all()

def pad_road_priors(xy):
    pts = gpd.GeoSeries([Point(x, y) for x, y in xy], crs=CRS)
    in_pad   = pts.within(pad_union).astype(np.int8).values
    dist_pad  = pts.distance(pad_union).values.astype(np.float32)
    dist_road = pts.distance(road_union).values.astype(np.float32)
    return in_pad, dist_pad, dist_road


# ---- extract all features
print('extracting features...')
feat_list, keep_idx = [], []
for i, g in enumerate(cand.geometry):
    f = feats_for(g.x, g.y)
    if f is not None:
        feat_list.append(f); keep_idx.append(i)
keep_idx = np.array(keep_idx)
X = pd.DataFrame(feat_list)

# add pad/road priors for kept candidates
kept_xy = cxy[keep_idx]
in_pad, d_pad, d_road = pad_road_priors(kept_xy)
X['in_pad']       = in_pad
X['dist_pad_m']   = d_pad
X['dist_road_m']  = d_road

y = y_full[keep_idx]
cand = cand.iloc[keep_idx].reset_index(drop=True)
nearest_pit = nearest_pit[keep_idx]
print(f'features: {X.shape},  positives kept: {y.sum()}')

# ---- spatial groups as before
N_GROUPS = 8
agg = AgglomerativeClustering(n_clusters=N_GROUPS).fit(pit_xy)
pit_group = agg.labels_
groups = pit_group[nearest_pit]

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

X_arr = X.fillna(0).to_numpy(dtype=np.float32)

def oof_fit(X_arr, y_arr, groups_arr):
    oof = np.zeros(len(y_arr), dtype=np.float32)
    gkf = GroupKFold(n_splits=min(5, N_GROUPS))
    for tr, te in gkf.split(X_arr, y_arr, groups=groups_arr):
        clf = xgb.XGBClassifier(**base_params, scale_pos_weight=scale_pos)
        clf.fit(X_arr[tr], y_arr[tr], verbose=False)
        oof[te] = clf.predict_proba(X_arr[te])[:, 1]
    return oof

print('fitting XGBoost (GroupKFold OOF, 2019+2008 features + pad/road priors)...')
proba = oof_fit(X_arr, y, groups)
print(f'  ROC-AUC {roc_auc_score(y, proba):.4f}   PR-AUC {average_precision_score(y, proba):.4f}')

final = xgb.XGBClassifier(**base_params, scale_pos_weight=scale_pos)
final.fit(X_arr, y, verbose=False)

# ---- PR + feature importance
fig, ax = plt.subplots(1, 2, figsize=(14, 5))
p, r, _ = precision_recall_curve(y, proba)
ax[0].plot(r, p)
ax[0].set_xlabel('recall'); ax[0].set_ylabel('precision')
ax[0].set_title(f'XGB-plus OOF PR curve  (AP={average_precision_score(y, proba):.3f})')
ax[0].set_xlim(0, 1); ax[0].set_ylim(0, 1); ax[0].grid(alpha=0.3)
imp = pd.Series(final.feature_importances_, index=X.columns).sort_values(ascending=True).tail(25)
imp.plot(kind='barh', ax=ax[1])
ax[1].set_title('top-25 feature importance (gain)'); ax[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(DERIV / 'pit_xgb_plus_feature_importance.png', dpi=130, bbox_inches='tight')
plt.close(fig)

# ---- ranked candidates
cand = cand.copy()
cand['proba'] = proba
cand = cand.sort_values('proba', ascending=False).reset_index(drop=True)
cand.to_file(DERIV / 'pit_candidates_xgb_plus.gpkg', driver='GPKG')

# ---- summary table
summary = []
for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
    sub = cand[cand['proba'] >= thr]
    if len(sub) == 0:
        summary.append((thr, 0, 0, 0, 0, 0.0)); continue
    sxy = np.c_[sub.geometry.x, sub.geometry.y]
    dn2, _ = tree_pit.query(sxy, k=1)
    hit10 = int((dn2 <= 10).sum())
    _, idx = tree_pit.query(sxy[dn2 <= 10], k=1) if hit10 else (None, np.array([]))
    pits_cov = len(np.unique(idx))
    summary.append((thr, len(sub), hit10, pits_cov, len(sub) - hit10, hit10 / max(len(sub), 1)))

print()
print(f'{"thr":>5} {"n":>6} {"hits10":>7} {"pits_cov":>9} {"fp":>6} {"prec":>7}')
for thr, n, h, p, fp, pr in summary:
    print(f'{thr:5.2f} {n:6d} {h:7d} {p:9d} {fp:6d} {pr:7.2%}')

with open(DERIV / 'pit_xgb_plus_metrics.txt', 'w') as f:
    f.write(f'XGBoost+2008+priors   GroupKFold OOF  (features: {X.shape[1]})\n')
    f.write(f'ROC-AUC {roc_auc_score(y, proba):.4f}\n')
    f.write(f'PR-AUC  {average_precision_score(y, proba):.4f}\n\n')
    f.write(f'{"thr":>5} {"n":>6} {"hits10":>7} {"pits_cov":>9} {"fp":>6} {"prec":>7}\n')
    for thr, n, h, p, fp, pr in summary:
        f.write(f'{thr:5.2f} {n:6d} {h:7d} {p:9d} {fp:6d} {pr:7.2%}\n')

# ---- per-threshold overlays
hs = read('hillshade_05.tif')
for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
    sub = cand[cand['proba'] >= thr]
    if len(sub) == 0: continue
    sxy = np.c_[sub.geometry.x, sub.geometry.y]
    dn2, _ = tree_pit.query(sxy, k=1)
    tp_xy = sxy[dn2 <= 10]
    fig, ax = plt.subplots(figsize=(14, 14))
    ax.imshow(hs, cmap='gray', extent=[X0, X1, Y0, Y1])
    ax.scatter(pit_xy[:, 0], pit_xy[:, 1], s=40, c='red', marker='o',
               linewidths=0, label=f'annotated pits ({len(pit_xy)})')
    if len(tp_xy):
        ax.scatter(tp_xy[:, 0], tp_xy[:, 1], s=70, c='lime', marker='X',
                   linewidths=0, label=f'found pits ({len(tp_xy)})')
    prec = (dn2 <= 10).mean() if len(dn2) else 0
    _, idx = tree_pit.query(tp_xy, k=1) if len(tp_xy) else (None, np.array([]))
    pits_cov = len(np.unique(idx)) if len(tp_xy) else 0
    ax.set_title(f'pit XGB-plus @ proba>={thr:.2f}   '
                 f'n={len(sub)}  TP={len(tp_xy)}  FP={len(sub)-len(tp_xy)}  '
                 f'pits_covered={pits_cov}/{len(pit_xy)}   '
                 f'precision={prec:.0%}  recall={pits_cov/len(pit_xy):.0%}')
    ax.legend(loc='lower left', fontsize=9)
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    fig.savefig(DERIV / f'pit_xgb_plus_thr{int(thr*100):02d}.png',
                dpi=130, bbox_inches='tight')
    plt.close(fig)
print('\nwrote pit_candidates_xgb_plus.{gpkg}, pit_xgb_plus_feature_importance.png, '
      'pit_xgb_plus_metrics.txt, pit_xgb_plus_thrXX.png x7')
