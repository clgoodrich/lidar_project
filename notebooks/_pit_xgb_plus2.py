"""Stage 2d: XGB-plus2 = XGB-plus + morphological + multi-template features.

Two new feature groups on top of _pit_xgb_plus.py (which already has
2019 + 2008 window stats + pad/road priors):

  (A) Moment-based Gaussian-bowl morphology on the LRM_5 window:
      depth (pit amplitude),
      sigma_major / sigma_minor / aspect (shape),
      compactness (mass / pi*sigma_major*sigma_minor),
      radial depth profile in 4 rings (r<=2, 2-5, 5-10, 10-15 cells),
      radial monotonicity (Spearman rho between radius and mean).

  (B) Multi-template NCC.  Cluster the 90 annotated pit cutouts into 3
      morphological sub-types via PCA(5) + KMeans(3), build a median
      template per cluster, run skimage.feature.match_template for each,
      and add per-candidate scores: score_template_0/1/2 and score_max.

Outputs, all with `_plus2` suffix:
  pit_candidates_xgb_plus2.gpkg
  pit_xgb_plus2_feature_importance.png
  pit_xgb_plus2_metrics.txt
  pit_xgb_plus2_thrXX.png x7
  pit_templates_multi.png          (the 3 learned sub-type templates)
  pit_match_max_05.tif             (max of the 3 per-template scores)
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Point
from shapely import make_valid
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, precision_recall_curve, average_precision_score
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from skimage.feature import match_template
import xgboost as xgb
import matplotlib.pyplot as plt

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0
CRS = 'EPSG:6346'
POS_DIST_M = 10.0

RES19 = 0.5;  W19 = int((X1 - X0)/RES19); H19 = int((Y1 - Y0)/RES19)
RES08 = 1.0;  W08 = int((X1 - X0)/RES08); H08 = int((Y1 - Y0)/RES08)
HALF19, INNER19, OUTER19 = 15, 5, 12
HALF08, INNER08, OUTER08 =  8, 3,  6
SNAP_R = 4

def read(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a

def make_rings(HALF, INNER, OUTER):
    yy, xx = np.ogrid[-HALF:HALF+1, -HALF:HALF+1]
    rad = np.sqrt(xx*xx + yy*yy)
    return rad <= INNER, (rad >= OUTER) & (rad <= HALF), rad

RING_IN_19, RING_RIM_19, RAD_19 = make_rings(HALF19, INNER19, OUTER19)
RING_IN_08, RING_RIM_08, RAD_08 = make_rings(HALF08, INNER08, OUTER08)

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


# =============================================================================
# STEP A — load candidates, pits, pads, roads
# =============================================================================
cand = gpd.read_file(DERIV / 'pit_candidates_template.gpkg').to_crs(CRS)
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pads = gpd.read_file(ANNO / 'pads_truth.gpkg').to_crs(CRS)
roads = gpd.read_file(ANNO / 'roads_truth.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x, g.y] for g in pits.geometry])
tree_pit = cKDTree(pit_xy)
cxy = np.array([[g.x, g.y] for g in cand.geometry])
dn, nearest_pit = tree_pit.query(cxy, k=1)
y_full = (dn <= POS_DIST_M).astype(np.int8)
print(f'{len(cand)} candidates,  positives={y_full.sum()}')

pads_clean = gpd.GeoSeries([make_valid(g) for g in pads.geometry], crs=CRS)
roads_clean = gpd.GeoSeries([make_valid(g) for g in roads.geometry], crs=CRS)
pad_union = pads_clean.union_all()
road_union = roads_clean.union_all()


# =============================================================================
# STEP B — build 3 pit sub-type templates (PCA + KMeans)
# =============================================================================
lrm5 = read('lrm_5_05.tif')
def rc19(x, y): return int(round((Y1 - y)/RES19)), int(round((x - X0)/RES19))
def rc08(x, y): return int(round((Y1 - y)/RES08)), int(round((x - X0)/RES08))

# snap each pit to local LRM minimum
snapped_rc = []
for (x, y) in pit_xy:
    r0, c0 = rc19(x, y)
    r1, r2 = max(0, r0-SNAP_R), min(H19, r0+SNAP_R+1)
    c1, c2 = max(0, c0-SNAP_R), min(W19, c0+SNAP_R+1)
    win = lrm5[r1:r2, c1:c2]
    if np.isnan(win).all(): snapped_rc.append((r0, c0)); continue
    f = np.nanargmin(win); dr, dc = divmod(f, win.shape[1])
    snapped_rc.append((r1+dr, c1+dc))

cutouts = []
WIN = 2*HALF19 + 1
for (r, c) in snapped_rc:
    r1, r2 = r-HALF19, r+HALF19+1
    c1, c2 = c-HALF19, c+HALF19+1
    if r1 < 0 or c1 < 0 or r2 > H19 or c2 > W19: continue
    w = lrm5[r1:r2, c1:c2].astype(np.float32)
    if np.isnan(w).mean() > 0.2: continue
    cutouts.append(w - np.nanmean(w))
cutouts = np.stack(cutouts, axis=0)
print(f'usable pit cutouts for clustering: {len(cutouts)}')

flat = np.nan_to_num(cutouts.reshape(len(cutouts), -1), nan=0)
pca = PCA(n_components=5, random_state=0).fit(flat)
Z = pca.transform(flat)
km = KMeans(n_clusters=3, n_init=10, random_state=0).fit(Z)
print('cluster sizes:', np.bincount(km.labels_))

templates = np.stack([
    np.nanmedian(cutouts[km.labels_ == k], axis=0) for k in range(3)
], axis=0)
templates = np.nan_to_num(templates, nan=0)

fig, axes = plt.subplots(1, 3, figsize=(12, 4))
for k, ax in enumerate(axes):
    im = ax.imshow(templates[k], cmap='RdBu_r', vmin=-0.3, vmax=0.3)
    ax.set_title(f'sub-type {k}  (n={(km.labels_==k).sum()})')
    ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
fig.suptitle('pit sub-type templates (median LRM_5 cutout per cluster)')
fig.tight_layout(); fig.savefig(DERIV / 'pit_templates_multi.png', dpi=130, bbox_inches='tight')
plt.close(fig)


# =============================================================================
# STEP C — per-template match_template across the tile (for features)
# =============================================================================
print('running match_template for each sub-type template...')
valid = ~np.isnan(lrm5); img_f = np.where(valid, lrm5, 0).astype(np.float32)
per_tmp_scores = []
for k in range(3):
    t = templates[k].astype(np.float32)
    s = match_template(img_f, t, pad_input=True)
    s[~valid] = np.nan
    per_tmp_scores.append(s)
score_max = np.nanmax(np.stack(per_tmp_scores, axis=0), axis=0)

# save max score raster
from rasterio.transform import from_origin
T = from_origin(X0, Y1, RES19, RES19)
with rasterio.open(DERIV / 'pit_match_max_05.tif', 'w', driver='GTiff',
                   height=H19, width=W19, count=1, dtype='float32', crs=CRS,
                   transform=T, nodata=-9999, tiled=True, compress='deflate',
                   predictor=3) as ds:
    ds.write(np.where(np.isnan(score_max), -9999, score_max).astype(np.float32), 1)


# =============================================================================
# STEP D — load all rasters (2019 + 2008)
# =============================================================================
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
RAST08 = {name: read(name) for name in [
    'dem_2008_1m.tif',
    'lrm_5_2008_1m.tif', 'lrm_11_2008_1m.tif',
    'tpi_15_2008_1m.tif',
    'openness_neg_2008_1m.tif',
    'slope_2008_1m.tif',
    'chm_2008_1m.tif', 'ground_density_2008_1m.tif',
]}

CHANS_D_19 = ['lrm_5_05.tif', 'lrm_11_05.tif', 'lrm_25_05.tif',
              'tpi_05_05.tif', 'tpi_15_05.tif', 'openness_neg_05.tif']
CHANS_S_19 = ['slope_05.tif', 'roughness_11_05.tif',
              'local_relief_10_05.tif', 'chm_05.tif']
CHANS_D_08 = ['lrm_5_2008_1m.tif', 'lrm_11_2008_1m.tif',
              'tpi_15_2008_1m.tif', 'openness_neg_2008_1m.tif']


# =============================================================================
# STEP E — morphology: moment-based Gaussian-bowl + radial profile
# =============================================================================
# Rings for radial profile on the 2019 LRM_5 window (31x31)
RADIAL_BINS = [(0, 2), (2, 5), (5, 10), (10, 15)]

def morphology_feats(win):
    """Return dict of morphological features from a 31x31 LRM_5 window."""
    out = {}
    if not np.isfinite(win).any():
        return {k: np.nan for k in
                ['morph_depth', 'morph_sigma_major', 'morph_sigma_minor',
                 'morph_aspect', 'morph_compactness',
                 'morph_prof_r0', 'morph_prof_r1', 'morph_prof_r2', 'morph_prof_r3',
                 'morph_radial_rho', 'morph_fit_residual']}
    w = np.where(np.isnan(win), 0, win).astype(np.float64)
    # "bowl mass" — weight where value is negative (below local mean)
    mass = np.clip(-w, 0, None)
    total = mass.sum()
    if total < 1e-6:
        return {k: np.nan for k in
                ['morph_depth', 'morph_sigma_major', 'morph_sigma_minor',
                 'morph_aspect', 'morph_compactness',
                 'morph_prof_r0', 'morph_prof_r1', 'morph_prof_r2', 'morph_prof_r3',
                 'morph_radial_rho', 'morph_fit_residual']}
    yy, xx = np.mgrid[0:win.shape[0], 0:win.shape[1]]
    cy = (mass * yy).sum() / total
    cx = (mass * xx).sum() / total
    # second moments about centroid
    vy = (mass * (yy - cy)**2).sum() / total
    vx = (mass * (xx - cx)**2).sum() / total
    cxy = (mass * (yy - cy) * (xx - cx)).sum() / total
    # eigenvalues of covariance
    tr = vx + vy
    det = vx * vy - cxy * cxy
    disc = max(tr*tr/4 - det, 0)
    lam1 = tr/2 + np.sqrt(disc)
    lam2 = tr/2 - np.sqrt(disc)
    sig_maj = float(np.sqrt(max(lam1, 1e-6)))
    sig_min = float(np.sqrt(max(lam2, 1e-6)))
    out['morph_depth']       = float(-np.nanmin(w))       # deepest value
    out['morph_sigma_major'] = sig_maj
    out['morph_sigma_minor'] = sig_min
    out['morph_aspect']      = sig_min / sig_maj
    out['morph_compactness'] = total / (np.pi * sig_maj * sig_min + 1e-6)

    # radial profile: mean of w at each ring
    prof = []
    for k, (rmin, rmax) in enumerate(RADIAL_BINS):
        mask = (RAD_19 >= rmin) & (RAD_19 < rmax)
        vals = w[mask]
        prof.append(float(vals.mean()) if len(vals) else np.nan)
    out['morph_prof_r0'] = prof[0]
    out['morph_prof_r1'] = prof[1]
    out['morph_prof_r2'] = prof[2]
    out['morph_prof_r3'] = prof[3]
    # monotonicity: Spearman rho between radius and mean (higher rho = bowl)
    radii = np.array([np.mean(b) for b in RADIAL_BINS])
    if np.any(np.isnan(prof)):
        out['morph_radial_rho'] = np.nan
    else:
        rho, _ = spearmanr(radii, prof)
        out['morph_radial_rho'] = float(rho) if np.isfinite(rho) else np.nan
    # fit residual: how close to a Gaussian bowl?
    # Use the analytic Gaussian implied by the moments, compare to w
    A = out['morph_depth']
    gx = xx - cx; gy = yy - cy
    # rotate into principal axes
    if cxy == 0 and vx == vy:
        theta = 0.0
    else:
        theta = 0.5 * np.arctan2(2 * cxy, (vx - vy))
    ct, st = np.cos(theta), np.sin(theta)
    gxr =  ct*gx + st*gy
    gyr = -st*gx + ct*gy
    g = -A * np.exp(-0.5 * ((gxr/sig_maj)**2 + (gyr/sig_min)**2))
    resid = float(np.sqrt(np.nanmean((w - g)**2)))
    # normalize by pit amplitude so shallow and deep are comparable
    out['morph_fit_residual'] = resid / (A + 1e-6)
    return out


# =============================================================================
# STEP F — per-candidate full feature extraction
# =============================================================================
def feats_for(x, y):
    r19, c19 = rc19(x, y)
    r1, r2 = r19-HALF19, r19+HALF19+1
    c1, c2 = c19-HALF19, c19+HALF19+1
    if r1 < 0 or c1 < 0 or r2 > H19 or c2 > W19: return None
    r08, c08 = rc08(x, y)
    r1b, r2b = r08-HALF08, r08+HALF08+1
    c1b, c2b = c08-HALF08, c08+HALF08+1
    if r1b < 0 or c1b < 0 or r2b > H08 or c2b > W08: return None

    out = {}
    for ch in CHANS_D_19:
        w = RAST19[ch][r1:r2, c1:c2]
        mni, mi, mr, diff, _ = stats_window(w, RING_IN_19, RING_RIM_19)
        tag = ch.replace('.tif', '')
        out[f'{tag}_imin']=mni; out[f'{tag}_imean']=mi; out[f'{tag}_rmean']=mr
        out[f'{tag}_rdiff']=diff; out[f'{tag}_sym']=radial_std(w, HALF19, INNER19)
    for ch in CHANS_S_19:
        w = RAST19[ch][r1:r2, c1:c2]; wi = w[RING_IN_19]
        tag = ch.replace('.tif', '')
        out[f'{tag}_imean'] = float(np.nanmean(wi)) if np.isfinite(wi).any() else np.nan
        out[f'{tag}_wmax']  = float(np.nanmax(w))   if np.isfinite(w).any()  else np.nan
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

    # 2008
    for ch in CHANS_D_08:
        w = RAST08[ch][r1b:r2b, c1b:c2b]
        mni, mi, mr, diff, _ = stats_window(w, RING_IN_08, RING_RIM_08)
        tag = ch.replace('.tif', '').replace('_2008_1m', '_08')
        out[f'{tag}_imin']=mni; out[f'{tag}_imean']=mi; out[f'{tag}_rmean']=mr
        out[f'{tag}_rdiff']=diff; out[f'{tag}_sym']=radial_std(w, HALF08, INNER08)
    dem_w08 = RAST08['dem_2008_1m.tif'][r1b:r2b, c1b:c2b]
    _, _, _, dem_cut_08, _ = stats_window(dem_w08, RING_IN_08, RING_RIM_08)
    out['dem_cut_08_m'] = dem_cut_08
    slope08 = RAST08['slope_2008_1m.tif'][r1b:r2b, c1b:c2b][RING_IN_08]
    out['slope_08_imean'] = float(np.nanmean(slope08)) if np.isfinite(slope08).any() else np.nan
    chm08 = RAST08['chm_2008_1m.tif'][r1b:r2b, c1b:c2b]
    out['chm_08_wmax'] = float(np.nanmax(chm08)) if np.isfinite(chm08).any() else np.nan
    dens08 = RAST08['ground_density_2008_1m.tif'][r1b:r2b, c1b:c2b][RING_IN_08]
    out['dens_08_imean'] = float(np.nanmean(dens08))
    out['both_depths'] = -min(out.get('lrm_5_05_imin', 0) or 0,
                              out.get('lrm_5_08_imin', 0) or 0)

    # (A) morphology features on LRM_5
    lrm_win = RAST19['lrm_5_05.tif'][r1:r2, c1:c2]
    out.update(morphology_feats(lrm_win))

    # (B) multi-template NCC scores
    out['tmpl0_score'] = float(per_tmp_scores[0][r19, c19])
    out['tmpl1_score'] = float(per_tmp_scores[1][r19, c19])
    out['tmpl2_score'] = float(per_tmp_scores[2][r19, c19])
    out['tmpl_max']    = float(score_max[r19, c19])

    return out


print('extracting features (13k candidates x 82 features)...')
feat_list, keep_idx = [], []
for i, g in enumerate(cand.geometry):
    f = feats_for(g.x, g.y)
    if f is not None:
        feat_list.append(f); keep_idx.append(i)
keep_idx = np.array(keep_idx)
X = pd.DataFrame(feat_list)

# pad/road priors
kept_xy = cxy[keep_idx]
pts = gpd.GeoSeries([Point(x, y) for x, y in kept_xy], crs=CRS)
X['in_pad']      = pts.within(pad_union).astype(np.int8).values
X['dist_pad_m']  = pts.distance(pad_union).values.astype(np.float32)
X['dist_road_m'] = pts.distance(road_union).values.astype(np.float32)

y = y_full[keep_idx]
cand = cand.iloc[keep_idx].reset_index(drop=True)
nearest_pit = nearest_pit[keep_idx]
print(f'features: {X.shape}  positives kept: {y.sum()}')


# =============================================================================
# STEP G — training
# =============================================================================
N_GROUPS = 8
agg = AgglomerativeClustering(n_clusters=N_GROUPS).fit(pit_xy)
pit_group = agg.labels_
groups = pit_group[nearest_pit]

scale_pos = (len(y) - y.sum()) / max(y.sum(), 1)
base_params = dict(
    objective='binary:logistic', tree_method='hist',
    n_estimators=500, max_depth=5, learning_rate=0.05,
    min_child_weight=2, subsample=0.8, colsample_bytree=0.8,
    reg_lambda=1.0, random_state=0, n_jobs=-1,
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

print('fitting XGBoost-plus2 (GroupKFold OOF)...')
proba = oof_fit(X_arr, y, groups)
print(f'  ROC-AUC {roc_auc_score(y, proba):.4f}   PR-AUC {average_precision_score(y, proba):.4f}')

final = xgb.XGBClassifier(**base_params, scale_pos_weight=scale_pos)
final.fit(X_arr, y, verbose=False)

# ---- PR + feat importance
fig, ax = plt.subplots(1, 2, figsize=(14, 6))
p, r, _ = precision_recall_curve(y, proba)
ax[0].plot(r, p)
ax[0].set_xlabel('recall'); ax[0].set_ylabel('precision')
ax[0].set_title(f'XGB-plus2 OOF PR curve  (AP={average_precision_score(y, proba):.3f})')
ax[0].set_xlim(0, 1); ax[0].set_ylim(0, 1); ax[0].grid(alpha=0.3)
imp = pd.Series(final.feature_importances_, index=X.columns).sort_values(ascending=True).tail(30)
imp.plot(kind='barh', ax=ax[1])
ax[1].set_title('top-30 feature importance (gain)'); ax[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(DERIV / 'pit_xgb_plus2_feature_importance.png', dpi=130, bbox_inches='tight')
plt.close(fig)

# ---- ranked candidates
cand = cand.copy()
cand['proba'] = proba
cand = cand.sort_values('proba', ascending=False).reset_index(drop=True)
cand.to_file(DERIV / 'pit_candidates_xgb_plus2.gpkg', driver='GPKG')

# ---- summary
summary = []
for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
    sub = cand[cand['proba'] >= thr]
    if len(sub) == 0: summary.append((thr, 0, 0, 0, 0, 0.0)); continue
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

with open(DERIV / 'pit_xgb_plus2_metrics.txt', 'w') as f:
    f.write(f'XGB-plus2 (XGB+2008+priors+morphology+multi-template)  GroupKFold OOF  features: {X.shape[1]}\n')
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
    ax.scatter(pit_xy[:,0], pit_xy[:,1], s=40, c='red', marker='o',
               linewidths=0, label=f'annotated pits ({len(pit_xy)})')
    if len(tp_xy):
        ax.scatter(tp_xy[:,0], tp_xy[:,1], s=70, c='lime', marker='X',
                   linewidths=0, label=f'found pits ({len(tp_xy)})')
    prec = (dn2 <= 10).mean() if len(dn2) else 0
    _, idx = tree_pit.query(tp_xy, k=1) if len(tp_xy) else (None, np.array([]))
    pits_cov = len(np.unique(idx)) if len(tp_xy) else 0
    ax.set_title(f'pit XGB-plus2 @ proba>={thr:.2f}   '
                 f'n={len(sub)}  TP={len(tp_xy)}  FP={len(sub)-len(tp_xy)}  '
                 f'pits_covered={pits_cov}/{len(pit_xy)}   '
                 f'precision={prec:.0%}  recall={pits_cov/len(pit_xy):.0%}')
    ax.legend(loc='lower left', fontsize=9)
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    fig.savefig(DERIV / f'pit_xgb_plus2_thr{int(thr*100):02d}.png',
                dpi=130, bbox_inches='tight')
    plt.close(fig)
print('\nwrote pit_candidates_xgb_plus2.gpkg, pit_xgb_plus2_feature_importance.png, '
      'pit_xgb_plus2_metrics.txt, pit_xgb_plus2_thrXX.png x7, '
      'pit_templates_multi.png, pit_match_max_05.tif')
