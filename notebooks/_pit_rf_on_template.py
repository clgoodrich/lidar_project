"""Stage 2 of pit detection: RF classifier on top of template candidates.

Inputs:
  pit_candidates_template.gpkg   (13k candidates from stage 1)
  wellhead_pits.gpkg             (90 annotated pits as ground truth)
  0.5 m derivative stack

Per candidate extract a 15-cell (7.5 m) half-window from each channel and
compute a compact feature vector (depth, rim, symmetry, CHM stats,
intensity NaN fraction, etc).  Label = within 10 m of an annotated pit.
Train a balanced Random Forest with OOB scoring, rank by proba, write
ranked candidates to disk.

Outputs:
  pit_candidates_rf.gpkg       (ranked candidates with proba + features)
  pit_candidates_rf.png        (hillshade overlay)
  pit_rf_feature_importance.png
  pit_rf_metrics.txt
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Point
from rasterio.transform import from_origin
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, precision_recall_curve, average_precision_score
import matplotlib.pyplot as plt

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
RES   = 0.5
X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0
W = int((X1 - X0) / RES); H = int((Y1 - Y0) / RES)
CRS = 'EPSG:6346'
HALF = 15            # 7.5 m half-window (full = 31 cells ~ 15.5 m)
INNER = 5            # center ring radius (cells) for "pit bottom"
OUTER = 12           # outer ring inner radius for "rim"
POS_DIST_M = 10.0    # a candidate is positive if within this many m of an annotated pit

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
print(f'{len(cand)} candidates, {len(pits)} annotated pits')

pit_xy = np.array([[g.x, g.y] for g in pits.geometry])
tree = cKDTree(pit_xy)
cxy = np.array([[g.x, g.y] for g in cand.geometry])
dn, _ = tree.query(cxy, k=1)
y = (dn <= POS_DIST_M).astype(np.int8)
print(f'positives: {y.sum()} / {len(y)}  ({y.mean():.2%})')

# ---- rasters
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

# ---- ring masks once
yy, xx = np.ogrid[-HALF:HALF+1, -HALF:HALF+1]
rad = np.sqrt(xx*xx + yy*yy)
inner_mask = rad <= INNER
rim_mask   = (rad >= OUTER) & (rad <= HALF)

def stats_window(z, inner, rim):
    """Return (min_inner, mean_inner, mean_rim, rim_minus_inner, std_inner)."""
    zi = z[inner]; zr = z[rim]
    if np.isfinite(zi).any() and np.isfinite(zr).any():
        mni = np.nanmin(zi); mi = np.nanmean(zi); mr = np.nanmean(zr)
        sdi = np.nanstd(zi)
        return mni, mi, mr, mr - mni, sdi
    return np.nan, np.nan, np.nan, np.nan, np.nan

def radial_std(z):
    """Axial symmetry proxy: std of z across angular bins at the inner ring."""
    if not np.isfinite(z).any():
        return np.nan
    # sample 8 angles at r = INNER
    angs = np.linspace(0, 2*np.pi, 8, endpoint=False)
    zs = []
    for a in angs:
        r = INNER
        r_row = int(round(HALF + r * np.sin(a)))
        r_col = int(round(HALF + r * np.cos(a)))
        v = z[r_row, r_col] if 0 <= r_row < z.shape[0] and 0 <= r_col < z.shape[1] else np.nan
        if np.isfinite(v): zs.append(v)
    return float(np.std(zs)) if len(zs) >= 4 else np.nan

CHANS_FOR_DEPTH = ['lrm_5_05.tif', 'lrm_11_05.tif', 'lrm_25_05.tif',
                   'tpi_05_05.tif', 'tpi_15_05.tif', 'openness_neg_05.tif']
CHANS_FOR_SURFACE = ['slope_05.tif', 'roughness_11_05.tif',
                     'local_relief_10_05.tif', 'chm_05.tif']

def feats_for(r_c, c_c):
    r1, r2 = r_c - HALF, r_c + HALF + 1
    c1, c2 = c_c - HALF, c_c + HALF + 1
    out = {}
    if r1 < 0 or c1 < 0 or r2 > H or c2 > W:
        return None
    # depth channels: inner/rim/ring-diff
    for ch in CHANS_FOR_DEPTH:
        w = rasters[ch][r1:r2, c1:c2]
        mni, mi, mr, diff, sdi = stats_window(w, inner_mask, rim_mask)
        tag = ch.replace('.tif', '')
        out[f'{tag}_inner_min']  = mni
        out[f'{tag}_inner_mean'] = mi
        out[f'{tag}_rim_mean']   = mr
        out[f'{tag}_rim_minus']  = diff
        out[f'{tag}_sym']        = radial_std(w)
    # surface / canopy at the candidate
    for ch in CHANS_FOR_SURFACE:
        w = rasters[ch][r1:r2, c1:c2]
        wi = w[inner_mask]
        tag = ch.replace('.tif', '')
        out[f'{tag}_inner_mean'] = float(np.nanmean(wi)) if np.isfinite(wi).any() else np.nan
        out[f'{tag}_window_max'] = float(np.nanmax(w))   if np.isfinite(w).any()  else np.nan
    # intensity stats + NaN fraction (pits often have poor returns -> sparse intensity)
    wi = rasters['intensity_ground_05.tif'][r1:r2, c1:c2]
    out['intensity_inner_mean'] = float(np.nanmean(wi[inner_mask])) if np.isfinite(wi[inner_mask]).any() else np.nan
    out['intensity_rim_mean']   = float(np.nanmean(wi[rim_mask]))   if np.isfinite(wi[rim_mask]).any()   else np.nan
    out['intensity_nanfrac']    = float(np.isnan(wi).mean())
    # ground density
    dens = rasters['ground_density_05.tif'][r1:r2, c1:c2]
    out['density_inner_mean'] = float(np.nanmean(dens[inner_mask]))
    out['density_window_mean'] = float(np.nanmean(dens))
    # DEM cut (center min vs rim mean) in absolute metres
    dem_w = rasters['dem_05.tif'][r1:r2, c1:c2]
    _, _, _, dem_cut, _ = stats_window(dem_w, inner_mask, rim_mask)
    out['dem_cut_m'] = dem_cut
    # template match scores
    out['match_score_center'] = float(rasters['pit_match_score_05.tif'][r_c, c_c])
    return out

print('extracting features...')
rows, cols = [], []
valid_mask = []
for geom in cand.geometry:
    r, c = rc(geom.x, geom.y)
    rows.append(r); cols.append(c)
rows = np.array(rows); cols = np.array(cols)

feat_list = []
keep_idx = []
for i, (r, c) in enumerate(zip(rows, cols)):
    f = feats_for(r, c)
    if f is not None:
        feat_list.append(f); keep_idx.append(i)
keep_idx = np.array(keep_idx)
X = pd.DataFrame(feat_list)
y = y[keep_idx]
cand = cand.iloc[keep_idx].reset_index(drop=True)
print(f'features: {X.shape},  positives kept: {y.sum()}')

# fill remaining NaNs with 0 for RF (tree handles zeros fine for our scale)
X_arr = X.fillna(0).to_numpy(dtype=np.float32)

# ---- RF
rf = RandomForestClassifier(
    n_estimators=600, max_features='sqrt',
    class_weight='balanced', oob_score=True,
    n_jobs=-1, random_state=0,
)
rf.fit(X_arr, y)
proba = rf.oob_decision_function_[:, 1]
print(f'OOB accuracy:     {rf.oob_score_:.4f}')
print(f'OOB ROC-AUC:      {roc_auc_score(y, proba):.4f}')
print(f'OOB PR-AUC:       {average_precision_score(y, proba):.4f}')

# ---- precision/recall trade curve (against annotated pits, hit = <=10m)
prec, rec, thr = precision_recall_curve(y, proba)
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
ax[0].plot(rec, prec); ax[0].set_xlabel('recall'); ax[0].set_ylabel('precision')
ax[0].set_title(f'PR curve  (AP={average_precision_score(y,proba):.3f})')
ax[0].set_xlim(0, 1); ax[0].set_ylim(0, 1); ax[0].grid(alpha=0.3)
# Feature importance
imp = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=True).tail(20)
imp.plot(kind='barh', ax=ax[1])
ax[1].set_title('top-20 feature importance'); ax[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(DERIV / 'pit_rf_feature_importance.png', dpi=130, bbox_inches='tight')
plt.close(fig)

# ---- write ranked candidates
cand = cand.copy()
cand['proba'] = proba
cand = cand.sort_values('proba', ascending=False).reset_index(drop=True)
cand.to_file(DERIV / 'pit_candidates_rf.gpkg', driver='GPKG')

# ---- summary table at a few probability cutoffs
summary = []
for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]:
    sub = cand[cand['proba'] >= thr]
    if len(sub) == 0:
        summary.append((thr, 0, 0, 0, 0, 0.0)); continue
    sxy = np.c_[sub.geometry.x, sub.geometry.y]
    dn2, _ = tree.query(sxy, k=1)
    hit10 = int((dn2 <= 10).sum())
    # distinct pits covered within 10m
    _, idx = tree.query(sxy[dn2 <= 10], k=1) if hit10 else (None, np.array([]))
    pits_cov = len(np.unique(idx))
    summary.append((thr, len(sub), hit10, pits_cov, len(sub) - hit10, hit10 / max(len(sub), 1)))

with open(DERIV / 'pit_rf_metrics.txt', 'w') as f:
    f.write(f'OOB acc      {rf.oob_score_:.4f}\n')
    f.write(f'OOB ROC-AUC  {roc_auc_score(y, proba):.4f}\n')
    f.write(f'OOB PR-AUC   {average_precision_score(y, proba):.4f}\n\n')
    f.write(f'{"thr":>5} {"n":>6} {"hits10":>7} {"pits_cov":>9} {"fp":>6} {"prec":>7}\n')
    for thr, n, h, p, fp, pr in summary:
        f.write(f'{thr:5.2f} {n:6d} {h:7d} {p:9d} {fp:6d} {pr:7.2%}\n')

print()
print(f'{"thr":>5} {"n":>6} {"hits10":>7} {"pits_cov":>9} {"fp":>6} {"prec":>7}')
for thr, n, h, p, fp, pr in summary:
    print(f'{thr:5.2f} {n:6d} {h:7d} {p:9d} {fp:6d} {pr:7.2%}')

# ---- overlay PNG using a sensible threshold (pick smallest thr with precision >= 40%)
good = [s for s in summary if s[5] >= 0.4 and s[1] >= 50]
THR_VIZ = good[0][0] if good else 0.5
top = cand[cand['proba'] >= THR_VIZ]
print(f'\nvisualising at thr={THR_VIZ}: n={len(top)}')

hs = read('hillshade_05.tif')
fig, ax = plt.subplots(figsize=(14, 14))
ax.imshow(hs, cmap='gray', extent=[X0, X1, Y0, Y1])
ax.scatter(pit_xy[:, 0], pit_xy[:, 1], s=45, facecolors='none', edgecolors='red',
           linewidths=1.5, label=f'annotated pits ({len(pit_xy)})')
ax.scatter(top.geometry.x, top.geometry.y, s=18, c=top['proba'], cmap='plasma',
           vmin=THR_VIZ, vmax=1.0, label=f'RF candidates thr>={THR_VIZ} (n={len(top)})')
ax.set_title(f'pit RF — candidates thr>={THR_VIZ}')
ax.legend(loc='lower left')
ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
fig.savefig(DERIV / 'pit_candidates_rf.png', dpi=130, bbox_inches='tight')
plt.close(fig)
print('wrote pit_candidates_rf.{png,gpkg}, pit_rf_feature_importance.png, pit_rf_metrics.txt')
