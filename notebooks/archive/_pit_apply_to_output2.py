"""Cross-tile pit detection: train on output3, apply to output2.

Output2 has no annotations (no wellhead_pits, no pads_truth, no roads_truth)
and zero documented wells from output_wells_2.csv.  So we strip pad/road
priors from the model and run blind on the new tile.

Pipeline:
  1.  Build candidates on output2 by running the 3 sub-type templates
      (learned from output3's annotated pits) over output2's lrm_5_o2_05.tif
      and finding local maxima of the max-score raster.
  2.  Extract the same 85 features (everything except pad/road priors) for
      output2 candidates.
  3.  Re-train the XGB+LGBM ensemble on output3 candidates with the priors
      removed, isotonic-calibrate, and apply to output2.
  4.  Save ranked output2 candidates + discovery map.

Outputs (data/derivatives/):
  pit_candidates_output2.gpkg
  pit_output2_overview.png
  pit_output2_metrics.txt
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Point
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.isotonic import IsotonicRegression
from skimage.feature import match_template, peak_local_max
import xgboost as xgb
import lightgbm as lgb
import matplotlib.pyplot as plt

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'
RES19 = 0.5;  RES08 = 1.0
HALF19, INNER19, OUTER19 = 15, 5, 12
HALF08, INNER08, OUTER08 =  8, 3,  6
SNAP_R = 4
POS_DIST_M = 10.0

# ---- per-tile geometry
TILE_O3 = dict(name='o3', X0=621000.0, Y0=4594500.0, X1=622500.0, Y1=4596000.0,
               sfx='', sfx08='_2008_1m')
TILE_O2 = dict(name='o2', X0=622500.0, Y0=4594500.0, X1=624000.0, Y1=4596000.0,
               sfx='_o2', sfx08='_o2_2008_1m')


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


def morphology_feats(win):
    keys = ['morph_depth', 'morph_sigma_major', 'morph_sigma_minor',
            'morph_aspect', 'morph_compactness',
            'morph_prof_r0', 'morph_prof_r1', 'morph_prof_r2', 'morph_prof_r3',
            'morph_radial_rho', 'morph_fit_residual']
    if not np.isfinite(win).any():
        return {k: np.nan for k in keys}
    w = np.where(np.isnan(win), 0, win).astype(np.float64)
    mass = np.clip(-w, 0, None); total = mass.sum()
    if total < 1e-6:
        return {k: np.nan for k in keys}
    yy, xx = np.mgrid[0:win.shape[0], 0:win.shape[1]]
    cy = (mass * yy).sum() / total; cx = (mass * xx).sum() / total
    vy = (mass * (yy - cy)**2).sum() / total
    vx = (mass * (xx - cx)**2).sum() / total
    cxy = (mass * (yy - cy) * (xx - cx)).sum() / total
    tr = vx + vy; det = vx * vy - cxy * cxy
    disc = max(tr*tr/4 - det, 0)
    lam1 = tr/2 + np.sqrt(disc); lam2 = tr/2 - np.sqrt(disc)
    sig_maj = float(np.sqrt(max(lam1, 1e-6)))
    sig_min = float(np.sqrt(max(lam2, 1e-6)))
    out = {'morph_depth': float(-np.nanmin(w)),
           'morph_sigma_major': sig_maj, 'morph_sigma_minor': sig_min,
           'morph_aspect': sig_min/sig_maj,
           'morph_compactness': total / (np.pi*sig_maj*sig_min + 1e-6)}
    radii_bins = [(0,2),(2,5),(5,10),(10,15)]
    prof = []
    for (rmin, rmax) in radii_bins:
        m = (RAD_19 >= rmin) & (RAD_19 < rmax)
        vals = w[m]; prof.append(float(vals.mean()) if len(vals) else np.nan)
    out['morph_prof_r0'], out['morph_prof_r1'] = prof[0], prof[1]
    out['morph_prof_r2'], out['morph_prof_r3'] = prof[2], prof[3]
    radii = np.array([np.mean(b) for b in radii_bins])
    out['morph_radial_rho'] = float(spearmanr(radii, prof)[0]) if not np.any(np.isnan(prof)) else np.nan
    theta = 0.0 if (cxy == 0 and vx == vy) else 0.5 * np.arctan2(2*cxy, (vx-vy))
    ct, st = np.cos(theta), np.sin(theta)
    A = out['morph_depth']
    gx = xx - cx; gy = yy - cy
    gxr =  ct*gx + st*gy; gyr = -st*gx + ct*gy
    g = -A * np.exp(-0.5 * ((gxr/sig_maj)**2 + (gyr/sig_min)**2))
    out['morph_fit_residual'] = float(np.sqrt(np.nanmean((w - g)**2))) / (A + 1e-6)
    return out


# =============================================================================
# STEP 1 — build the 3 sub-type templates from output3 pits
# =============================================================================
print('=== building sub-type templates from output3 pits ===')
T = TILE_O3
X0o3, Y0o3, X1o3, Y1o3 = T['X0'], T['Y0'], T['X1'], T['Y1']
W19o3 = int((X1o3-X0o3)/RES19); H19o3 = int((Y1o3-Y0o3)/RES19)
lrm5_o3 = read('lrm_5_05.tif')
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x, g.y] for g in pits.geometry])

def rc19(x, y, X0, Y1):
    return int(round((Y1 - y)/RES19)), int(round((x - X0)/RES19))

snapped_rc = []
for (x, y) in pit_xy:
    r0, c0 = rc19(x, y, X0o3, Y1o3)
    r1, r2 = max(0, r0-SNAP_R), min(H19o3, r0+SNAP_R+1)
    c1, c2 = max(0, c0-SNAP_R), min(W19o3, c0+SNAP_R+1)
    win = lrm5_o3[r1:r2, c1:c2]
    if np.isnan(win).all(): snapped_rc.append((r0, c0)); continue
    f = np.nanargmin(win); dr, dc = divmod(f, win.shape[1])
    snapped_rc.append((r1+dr, c1+dc))

cutouts = []
for (r, c) in snapped_rc:
    r1, r2 = r-HALF19, r+HALF19+1; c1, c2 = c-HALF19, c+HALF19+1
    if r1 < 0 or c1 < 0 or r2 > H19o3 or c2 > W19o3: continue
    w = lrm5_o3[r1:r2, c1:c2].astype(np.float32)
    if np.isnan(w).mean() > 0.2: continue
    cutouts.append(w - np.nanmean(w))
cutouts = np.stack(cutouts, axis=0)
flat = np.nan_to_num(cutouts.reshape(len(cutouts), -1), nan=0)
Z = PCA(n_components=5, random_state=0).fit_transform(flat)
km = KMeans(n_clusters=3, n_init=10, random_state=0).fit(Z)
templates = np.stack([np.nanmedian(cutouts[km.labels_ == k], axis=0) for k in range(3)], axis=0)
templates = np.nan_to_num(templates, nan=0)
print(f'templates: {templates.shape}  cluster sizes={np.bincount(km.labels_).tolist()}')


# =============================================================================
# STEP 2 — per-tile candidate generation (template -> peaks)
# =============================================================================
def build_per_tile_candidates(tile):
    print(f"\n=== {tile['name']}: template match + candidate peaks ===")
    sfx = tile['sfx']
    lrm5_path = f'lrm_5{sfx}_05.tif'
    lrm5 = read(lrm5_path)
    valid = ~np.isnan(lrm5); img = np.where(valid, lrm5, 0).astype(np.float32)
    per_tmp = [match_template(img, templates[k].astype(np.float32), pad_input=True) for k in range(3)]
    for s in per_tmp: s[~valid] = np.nan
    score_max = np.nanmax(np.stack(per_tmp, axis=0), axis=0)
    H, W = lrm5.shape

    # pick threshold: the same calibration we used on output3 (pit p25)
    # Apply the same threshold (0.148) we used on output3 — keeps comparable
    # candidate density across tiles.
    THR_PEAK = 0.148
    min_dist_cells = int(round(5.0 / RES19))
    peaks = peak_local_max(np.nan_to_num(score_max, nan=-1),
                           min_distance=min_dist_cells, threshold_abs=THR_PEAK)
    print(f'  candidates: {len(peaks)}')
    rows, cols = peaks[:, 0], peaks[:, 1]
    xs = tile['X0'] + (cols + 0.5) * RES19
    ys = tile['Y1'] - (rows + 0.5) * RES19
    return per_tmp, score_max, xs, ys


per_tmp_o3, score_max_o3, x3, y3 = build_per_tile_candidates(TILE_O3)
per_tmp_o2, score_max_o2, x2, y2 = build_per_tile_candidates(TILE_O2)


# =============================================================================
# STEP 3 — feature extraction (per-tile) — NO pad/road priors, NO match_center
# =============================================================================
CHANS_D_19 = ['lrm_5', 'lrm_11', 'lrm_25', 'tpi_05', 'tpi_15', 'openness_neg']
CHANS_S_19 = ['slope', 'roughness_11', 'local_relief_10', 'chm']
CHANS_D_08 = ['lrm_5', 'lrm_11', 'tpi_15', 'openness_neg']

def load_tile_rasters(tile):
    sfx = tile['sfx']; sfx08 = tile['sfx08']
    R19 = {f'{ch}{sfx}_05.tif': read(f'{ch}{sfx}_05.tif')
           for ch in CHANS_D_19 + CHANS_S_19}
    R19[f'dem{sfx}_05.tif']            = read(f'dem{sfx}_05.tif')
    R19[f'intensity_ground{sfx}_05.tif'] = read(f'intensity_ground{sfx}_05.tif')
    R19[f'ground_density{sfx}_05.tif'] = read(f'ground_density{sfx}_05.tif')
    R08 = {f'{ch}{sfx08}.tif': read(f'{ch}{sfx08}.tif') for ch in CHANS_D_08}
    R08[f'dem{sfx08}.tif']            = read(f'dem{sfx08}.tif')
    R08[f'slope{sfx08}.tif']          = read(f'slope{sfx08}.tif')
    R08[f'chm{sfx08}.tif']            = read(f'chm{sfx08}.tif')
    R08[f'ground_density{sfx08}.tif'] = read(f'ground_density{sfx08}.tif')
    return R19, R08


def feats_for_xy(x, y, tile, R19, R08, per_tmp, score_max):
    sfx, sfx08 = tile['sfx'], tile['sfx08']
    X0, Y1 = tile['X0'], tile['Y1']
    r19, c19 = int(round((Y1-y)/RES19)), int(round((x-X0)/RES19))
    r08, c08 = int(round((Y1-y)/RES08)), int(round((x-X0)/RES08))
    H19, W19 = R19[f'dem{sfx}_05.tif'].shape
    H08, W08 = R08[f'dem{sfx08}.tif'].shape
    r1, r2 = r19-HALF19, r19+HALF19+1; c1, c2 = c19-HALF19, c19+HALF19+1
    r1b, r2b = r08-HALF08, r08+HALF08+1; c1b, c2b = c08-HALF08, c08+HALF08+1
    if r1 < 0 or c1 < 0 or r2 > H19 or c2 > W19: return None
    if r1b < 0 or c1b < 0 or r2b > H08 or c2b > W08: return None
    out = {}
    # 2019 depth/symmetry
    for ch in CHANS_D_19:
        w = R19[f'{ch}{sfx}_05.tif'][r1:r2, c1:c2]
        mni, mi, mr, diff, _ = stats_window(w, RING_IN_19, RING_RIM_19)
        # standardize feature names to the output3 baseline (no o2 in name)
        tag = ch + '_05'
        out[f'{tag}_imin']=mni; out[f'{tag}_imean']=mi; out[f'{tag}_rmean']=mr
        out[f'{tag}_rdiff']=diff; out[f'{tag}_sym']=radial_std(w, HALF19, INNER19)
    for ch in CHANS_S_19:
        w = R19[f'{ch}{sfx}_05.tif'][r1:r2, c1:c2]; wi = w[RING_IN_19]
        tag = ch + '_05'
        out[f'{tag}_imean'] = float(np.nanmean(wi)) if np.isfinite(wi).any() else np.nan
        out[f'{tag}_wmax']  = float(np.nanmax(w))   if np.isfinite(w).any()  else np.nan
    wi = R19[f'intensity_ground{sfx}_05.tif'][r1:r2, c1:c2]
    out['int_imean']   = float(np.nanmean(wi[RING_IN_19])) if np.isfinite(wi[RING_IN_19]).any() else np.nan
    out['int_rmean']   = float(np.nanmean(wi[RING_RIM_19])) if np.isfinite(wi[RING_RIM_19]).any() else np.nan
    out['int_nanfrac'] = float(np.isnan(wi).mean())
    dens = R19[f'ground_density{sfx}_05.tif'][r1:r2, c1:c2]
    out['dens_imean'] = float(np.nanmean(dens[RING_IN_19]))
    out['dens_wmean'] = float(np.nanmean(dens))
    dem_w = R19[f'dem{sfx}_05.tif'][r1:r2, c1:c2]
    _, _, _, dem_cut_19, _ = stats_window(dem_w, RING_IN_19, RING_RIM_19)
    out['dem_cut_m'] = dem_cut_19
    # NOTE: match_center used to be from pit_match_score_05.tif. We omit it
    # because it's only built for output3 — we use tmpl_max instead which
    # we recompute per tile.

    # 2008
    for ch in CHANS_D_08:
        w = R08[f'{ch}{sfx08}.tif'][r1b:r2b, c1b:c2b]
        mni, mi, mr, diff, _ = stats_window(w, RING_IN_08, RING_RIM_08)
        tag = ch + '_08'
        out[f'{tag}_imin']=mni; out[f'{tag}_imean']=mi; out[f'{tag}_rmean']=mr
        out[f'{tag}_rdiff']=diff; out[f'{tag}_sym']=radial_std(w, HALF08, INNER08)
    dem_w08 = R08[f'dem{sfx08}.tif'][r1b:r2b, c1b:c2b]
    _, _, _, dem_cut_08, _ = stats_window(dem_w08, RING_IN_08, RING_RIM_08)
    out['dem_cut_08_m'] = dem_cut_08
    slope08 = R08[f'slope{sfx08}.tif'][r1b:r2b, c1b:c2b][RING_IN_08]
    out['slope_08_imean'] = float(np.nanmean(slope08)) if np.isfinite(slope08).any() else np.nan
    chm08 = R08[f'chm{sfx08}.tif'][r1b:r2b, c1b:c2b]
    out['chm_08_wmax'] = float(np.nanmax(chm08)) if np.isfinite(chm08).any() else np.nan
    dens08 = R08[f'ground_density{sfx08}.tif'][r1b:r2b, c1b:c2b][RING_IN_08]
    out['dens_08_imean'] = float(np.nanmean(dens08))
    out['both_depths'] = -min(out.get('lrm_5_05_imin', 0) or 0,
                              out.get('lrm_5_08_imin', 0) or 0)
    out.update(morphology_feats(R19[f'lrm_5{sfx}_05.tif'][r1:r2, c1:c2]))
    out['tmpl0_score'] = float(per_tmp[0][r19, c19])
    out['tmpl1_score'] = float(per_tmp[1][r19, c19])
    out['tmpl2_score'] = float(per_tmp[2][r19, c19])
    out['tmpl_max']    = float(score_max[r19, c19])
    return out


# extract for both tiles
print('\n=== extracting features ===')
R19_o3, R08_o3 = load_tile_rasters(TILE_O3)
R19_o2, R08_o2 = load_tile_rasters(TILE_O2)

def extract(xs, ys, tile, R19, R08, per_tmp, score_max):
    feats, keep = [], []
    for i, (x, y) in enumerate(zip(xs, ys)):
        f = feats_for_xy(x, y, tile, R19, R08, per_tmp, score_max)
        if f is not None: feats.append(f); keep.append(i)
    return pd.DataFrame(feats), np.array(keep)

X3_df, k3 = extract(x3, y3, TILE_O3, R19_o3, R08_o3, per_tmp_o3, score_max_o3)
X2_df, k2 = extract(x2, y2, TILE_O2, R19_o2, R08_o2, per_tmp_o2, score_max_o2)
print(f'output3 candidates with valid features: {len(X3_df)}')
print(f'output2 candidates with valid features: {len(X2_df)}')

# y for output3 (positive if within 10m of an annotated pit)
tree_pit = cKDTree(pit_xy)
o3_xy = np.c_[x3[k3], y3[k3]]
dn3, _ = tree_pit.query(o3_xy, k=1)
y3 = (dn3 <= POS_DIST_M).astype(np.int8)
print(f'output3 positives: {y3.sum()} / {len(y3)}')

# Align columns
X3_df = X3_df[X2_df.columns]   # ensure same column order
X3 = X3_df.fillna(0).to_numpy(dtype=np.float32)
X2 = X2_df.fillna(0).to_numpy(dtype=np.float32)
print(f'feature matrix: train {X3.shape},  test {X2.shape}')


# =============================================================================
# STEP 4 — train ensemble on output3 (group-aware OOF for calibration)
# =============================================================================
print('\n=== training ensemble on output3 (no pad/road priors) ===')
N_GROUPS = 8
agg = AgglomerativeClustering(n_clusters=N_GROUPS).fit(pit_xy)
pit_group = agg.labels_
# nearest pit per output3 candidate -> group
_, near_pit_o3 = tree_pit.query(o3_xy, k=1)
groups = pit_group[near_pit_o3]
scale_pos = (len(y3) - y3.sum()) / max(y3.sum(), 1)

def make_xgb():
    return xgb.XGBClassifier(
        objective='binary:logistic', tree_method='hist',
        n_estimators=500, max_depth=5, learning_rate=0.05,
        min_child_weight=2, subsample=0.8, colsample_bytree=0.8,
        reg_lambda=1.0, scale_pos_weight=scale_pos,
        random_state=0, n_jobs=-1)

def make_lgb():
    return lgb.LGBMClassifier(
        objective='binary', n_estimators=500, learning_rate=0.05,
        num_leaves=31, min_child_samples=5, subsample=0.8, colsample_bytree=0.8,
        reg_lambda=1.0, scale_pos_weight=scale_pos,
        random_state=0, n_jobs=-1, verbose=-1)

def oof_fit(make_clf, X, y, g):
    oof = np.zeros(len(y), dtype=np.float32)
    gkf = GroupKFold(n_splits=min(5, N_GROUPS))
    for tr, te in gkf.split(X, y, groups=g):
        clf = make_clf(); clf.fit(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])[:, 1]
    return oof

p_xgb = oof_fit(make_xgb, X3, y3, groups)
p_lgb = oof_fit(make_lgb, X3, y3, groups)
print(f'  XGB  ROC {roc_auc_score(y3, p_xgb):.4f}  PR {average_precision_score(y3, p_xgb):.4f}')
print(f'  LGBM ROC {roc_auc_score(y3, p_lgb):.4f}  PR {average_precision_score(y3, p_lgb):.4f}')
p_avg_o3 = (p_xgb + p_lgb) / 2
print(f'  AVG  ROC {roc_auc_score(y3, p_avg_o3):.4f}  PR {average_precision_score(y3, p_avg_o3):.4f}')
iso = IsotonicRegression(out_of_bounds='clip').fit(p_avg_o3, y3)

# refit final on all output3 data, then apply to output2
final_xgb = make_xgb(); final_xgb.fit(X3, y3)
final_lgb = make_lgb(); final_lgb.fit(X3, y3)
p2_xgb = final_xgb.predict_proba(X2)[:, 1]
p2_lgb = final_lgb.predict_proba(X2)[:, 1]
p2_raw = (p2_xgb + p2_lgb) / 2
p2_cal = iso.predict(p2_raw).astype(np.float32)


# =============================================================================
# STEP 5 — ranked output + discovery map
# =============================================================================
print('\n=== output2 candidate ranking ===')
o2_xy = np.c_[x2[k2], y2[k2]]
out = gpd.GeoDataFrame({
    'proba':     p2_cal,
    'proba_raw': p2_raw,
    'geometry': [Point(x, y) for x, y in o2_xy],
}, crs=CRS).sort_values('proba', ascending=False).reset_index(drop=True)
out.to_file(DERIV / 'pit_candidates_output2.gpkg', driver='GPKG')

# summary table
print()
print(f'{"thr":>5} {"n":>6}')
with open(DERIV / 'pit_output2_metrics.txt', 'w') as f:
    f.write('Cross-tile pit detection: trained on output3 (no pad/road priors), applied to output2.\n')
    f.write(f'Train candidates: {len(X3)}  positives: {int(y3.sum())}\n')
    f.write(f'Train OOF: XGB ROC {roc_auc_score(y3, p_xgb):.4f}  PR {average_precision_score(y3, p_xgb):.4f}\n')
    f.write(f'           LGBM ROC {roc_auc_score(y3, p_lgb):.4f}  PR {average_precision_score(y3, p_lgb):.4f}\n')
    f.write(f'           AVG ROC {roc_auc_score(y3, p_avg_o3):.4f}  PR {average_precision_score(y3, p_avg_o3):.4f}\n\n')
    f.write(f'Test candidates: {len(X2)}\n')
    f.write(f'{"thr":>5} {"n":>6}\n')
    for thr in [0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
        n = int((out['proba'] >= thr).sum())
        f.write(f'{thr:5.2f} {n:6d}\n')
        print(f'{thr:5.2f} {n:6d}')

# overview map
hs = read('hillshade_o2_05.tif')
fig, ax = plt.subplots(figsize=(15, 15))
ax.imshow(hs, cmap='gray', extent=[TILE_O2['X0'], TILE_O2['X1'], TILE_O2['Y0'], TILE_O2['Y1']])
THR_VIZ = 0.50
viz = out[out['proba'] >= THR_VIZ]
print(f'\nshowing {len(viz)} candidates at proba >= {THR_VIZ}')
if len(viz):
    sc = ax.scatter(viz.geometry.x, viz.geometry.y, s=70, c=viz['proba'],
                    cmap='YlOrRd', vmin=THR_VIZ, vmax=1.0,
                    edgecolors='black', linewidths=0.4)
    cb = plt.colorbar(sc, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label('calibrated proba')
ax.set_title(f'output2 pit predictions (model trained on output3, no pad/road priors)\n'
             f'{len(viz)} candidates at proba >= {THR_VIZ}', fontsize=12)
ax.set_xlim(TILE_O2['X0'], TILE_O2['X1']); ax.set_ylim(TILE_O2['Y0'], TILE_O2['Y1'])
fig.savefig(DERIV / 'pit_output2_overview.png', dpi=140, bbox_inches='tight')
plt.close(fig)
print('wrote pit_candidates_output2.gpkg, pit_output2_overview.png, pit_output2_metrics.txt')
