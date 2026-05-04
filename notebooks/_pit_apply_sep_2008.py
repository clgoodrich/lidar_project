"""Pit detection on the sep 2008 PAMAP data ONLY (single epoch, 1 m).

Templates re-learned from output3's 2008 1m LRM_5 (not 2019 0.5m).
Model trained on output3 2008 features, applied to sep 2008.
No cross-epoch features, no pad/road priors.

Outputs:
  pit_candidates_sep_2008.gpkg
  pit_sep_2008_overview.png
  pit_sep_2008_metrics.txt
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
import time

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
CRS   = 'EPSG:6346'
RES   = 1.0
HALF, INNER, OUTER = 8, 3, 6
SNAP_R = 3; POS_DIST_M = 10.0

# Tile definitions (both at 1 m)
O3  = dict(X0=621000.0, Y0=4594500.0, X1=622500.0, Y1=4596000.0, sfx='_2008_1m')
SEP = dict(X0=562500.0, Y0=4464000.0, X1=568500.0, Y1=4470000.0, sfx='_sep_2008_1m')
for t in [O3, SEP]:
    t['W'] = int((t['X1']-t['X0'])/RES); t['H'] = int((t['Y1']-t['Y0'])/RES)


def read(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a


def make_rings():
    yy, xx = np.ogrid[-HALF:HALF+1, -HALF:HALF+1]
    rad = np.sqrt(xx*xx + yy*yy)
    return rad <= INNER, (rad >= OUTER) & (rad <= HALF), rad

RING_IN, RING_RIM, RAD = make_rings()
RADIAL_BINS = [(0,1),(1,3),(3,5),(5,8)]


def stats_window(z, inner, rim):
    zi = z[inner]; zr = z[rim]
    if np.isfinite(zi).any() and np.isfinite(zr).any():
        return (np.nanmin(zi), np.nanmean(zi), np.nanmean(zr),
                np.nanmean(zr)-np.nanmin(zi), np.nanstd(zi))
    return (np.nan,)*5


def radial_std(z):
    if not np.isfinite(z).any(): return np.nan
    angs = np.linspace(0, 2*np.pi, 8, endpoint=False)
    zs = []
    for a in angs:
        r_row = int(round(HALF + INNER*np.sin(a)))
        r_col = int(round(HALF + INNER*np.cos(a)))
        if 0<=r_row<z.shape[0] and 0<=r_col<z.shape[1]:
            v = z[r_row, r_col]
            if np.isfinite(v): zs.append(v)
    return float(np.std(zs)) if len(zs)>=4 else np.nan


def morphology_feats(win):
    keys = ['morph_depth','morph_sigma_major','morph_sigma_minor','morph_aspect',
            'morph_compactness','morph_prof_r0','morph_prof_r1','morph_prof_r2',
            'morph_prof_r3','morph_radial_rho','morph_fit_residual']
    if not np.isfinite(win).any(): return {k: np.nan for k in keys}
    w = np.where(np.isnan(win), 0, win).astype(np.float64)
    mass = np.clip(-w, 0, None); total = mass.sum()
    if total < 1e-6: return {k: np.nan for k in keys}
    yyg, xxg = np.mgrid[0:win.shape[0], 0:win.shape[1]]
    cy = (mass*yyg).sum()/total; cx = (mass*xxg).sum()/total
    vy = (mass*(yyg-cy)**2).sum()/total; vx = (mass*(xxg-cx)**2).sum()/total
    cxy = (mass*(yyg-cy)*(xxg-cx)).sum()/total
    tr = vx+vy; det = vx*vy-cxy*cxy; disc = max(tr*tr/4-det, 0)
    lam1 = tr/2+np.sqrt(disc); lam2 = tr/2-np.sqrt(disc)
    sig_maj = float(np.sqrt(max(lam1,1e-6))); sig_min = float(np.sqrt(max(lam2,1e-6)))
    out = {'morph_depth': float(-np.nanmin(w)), 'morph_sigma_major': sig_maj,
           'morph_sigma_minor': sig_min, 'morph_aspect': sig_min/sig_maj,
           'morph_compactness': total/(np.pi*sig_maj*sig_min+1e-6)}
    prof = []
    for (rmin,rmax) in RADIAL_BINS:
        m = (RAD>=rmin)&(RAD<rmax); vals = w[m]
        prof.append(float(vals.mean()) if len(vals) else np.nan)
    out['morph_prof_r0'],out['morph_prof_r1']=prof[0],prof[1]
    out['morph_prof_r2'],out['morph_prof_r3']=prof[2],prof[3]
    radii = np.array([np.mean(b) for b in RADIAL_BINS])
    out['morph_radial_rho'] = float(spearmanr(radii,prof)[0]) if not np.any(np.isnan(prof)) else np.nan
    theta = 0.0 if (cxy==0 and vx==vy) else 0.5*np.arctan2(2*cxy,(vx-vy))
    ct,st = np.cos(theta),np.sin(theta); A = out['morph_depth']
    gx = xxg-cx; gy = yyg-cy; gxr = ct*gx+st*gy; gyr = -st*gx+ct*gy
    g = -A*np.exp(-0.5*((gxr/sig_maj)**2+(gyr/sig_min)**2))
    out['morph_fit_residual'] = float(np.sqrt(np.nanmean((w-g)**2)))/(A+1e-6)
    return out


def rc(x, y, tile):
    return int(round((tile['Y1']-y)/RES)), int(round((x-tile['X0'])/RES))


# =========================================================================
# 1. Templates from output3 2008 LRM_5 at 1 m
# =========================================================================
print('=== building 1m templates from output3 2008 ===', flush=True)
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x, g.y] for g in pits.geometry])
tree_pit = cKDTree(pit_xy)

lrm5_o3 = read('lrm_5_2008_1m.tif')
snapped = []
for (x,y) in pit_xy:
    r0,c0 = rc(x,y,O3)
    r1,r2 = max(0,r0-SNAP_R),min(O3['H'],r0+SNAP_R+1)
    c1,c2 = max(0,c0-SNAP_R),min(O3['W'],c0+SNAP_R+1)
    win = lrm5_o3[r1:r2,c1:c2]
    if np.isnan(win).all(): snapped.append((r0,c0)); continue
    f = np.nanargmin(win); dr,dc = divmod(f,win.shape[1])
    snapped.append((r1+dr,c1+dc))

WIN = 2*HALF+1
cutouts = []
for (r,c) in snapped:
    r1,r2 = r-HALF,r+HALF+1; c1,c2 = c-HALF,c+HALF+1
    if r1<0 or c1<0 or r2>O3['H'] or c2>O3['W']: continue
    w = lrm5_o3[r1:r2,c1:c2].astype(np.float32)
    if np.isnan(w).mean()>0.2: continue
    cutouts.append(w - np.nanmean(w))
cutouts = np.stack(cutouts)
flat = np.nan_to_num(cutouts.reshape(len(cutouts),-1),nan=0)
Z = PCA(n_components=5, random_state=0).fit_transform(flat)
km = KMeans(n_clusters=3, n_init=10, random_state=0).fit(Z)
templates = np.stack([np.nanmedian(cutouts[km.labels_==k],axis=0) for k in range(3)])
templates = np.nan_to_num(templates, nan=0)
print(f'templates: {templates.shape}  clusters: {np.bincount(km.labels_).tolist()}', flush=True)
del lrm5_o3


# =========================================================================
# 2. Candidate generation on both tiles (1m LRM_5)
# =========================================================================
CHANS_D = ['lrm_5','lrm_11','tpi_15','openness_neg']

def gen_candidates(tile, label):
    sfx = tile['sfx']
    lrm5 = read(f'lrm_5{sfx}.tif')
    valid = ~np.isnan(lrm5); img = np.where(valid,lrm5,0).astype(np.float32)
    print(f'\n=== {label}: template matching ({lrm5.shape}) ===', flush=True)
    t0 = time.time()
    per_tmp = [match_template(img, templates[k].astype(np.float32), pad_input=True) for k in range(3)]
    for s in per_tmp: s[~valid] = np.nan
    score_max = np.nanmax(np.stack(per_tmp), axis=0)
    print(f'  done in {time.time()-t0:.1f}s', flush=True)
    THR = 0.148
    peaks = peak_local_max(np.nan_to_num(score_max,nan=-1),
                           min_distance=int(round(5.0/RES)), threshold_abs=THR)
    rows,cols = peaks[:,0],peaks[:,1]
    xs = tile['X0'] + (cols+0.5)*RES; ys = tile['Y1'] - (rows+0.5)*RES
    print(f'  candidates: {len(peaks)}', flush=True)
    return per_tmp, score_max, xs, ys

per_tmp_o3, sm_o3, x3, y3 = gen_candidates(O3, 'output3_2008')
per_tmp_sep, sm_sep, xs, ys = gen_candidates(SEP, 'sep_2008')


# =========================================================================
# 3. Load rasters + extract features (2008-only, 1m)
# =========================================================================
def load_rasters(tile):
    sfx = tile['sfx']
    R = {}
    for ch in CHANS_D:
        R[ch] = read(f'{ch}{sfx}.tif')
    R['dem'] = read(f'dem{sfx}.tif')
    R['slope'] = read(f'slope{sfx}.tif')
    R['chm'] = read(f'chm{sfx}.tif')
    R['ground_density'] = read(f'ground_density{sfx}.tif')
    return R

print('\n=== loading rasters ===', flush=True)
R_o3 = load_rasters(O3)
R_sep = load_rasters(SEP)


def feats_for(x, y, tile, R, per_tmp, score_max):
    r,c = rc(x,y,tile)
    H,W = tile['H'],tile['W']
    r1,r2 = r-HALF,r+HALF+1; c1,c2 = c-HALF,c+HALF+1
    if r1<0 or c1<0 or r2>H or c2>W: return None
    out = {}
    for ch in CHANS_D:
        w = R[ch][r1:r2,c1:c2]
        mni,mi,mr,diff,_ = stats_window(w,RING_IN,RING_RIM)
        out[f'{ch}_imin']=mni; out[f'{ch}_imean']=mi; out[f'{ch}_rmean']=mr
        out[f'{ch}_rdiff']=diff; out[f'{ch}_sym']=radial_std(w)
    # slope, chm
    sl = R['slope'][r1:r2,c1:c2][RING_IN]
    out['slope_imean'] = float(np.nanmean(sl)) if np.isfinite(sl).any() else np.nan
    out['slope_wmax'] = float(np.nanmax(R['slope'][r1:r2,c1:c2])) if np.isfinite(R['slope'][r1:r2,c1:c2]).any() else np.nan
    chm = R['chm'][r1:r2,c1:c2]
    out['chm_imean'] = float(np.nanmean(chm[RING_IN])) if np.isfinite(chm[RING_IN]).any() else np.nan
    out['chm_wmax'] = float(np.nanmax(chm)) if np.isfinite(chm).any() else np.nan
    dens = R['ground_density'][r1:r2,c1:c2]
    out['dens_imean'] = float(np.nanmean(dens[RING_IN]))
    out['dens_wmean'] = float(np.nanmean(dens))
    dem_w = R['dem'][r1:r2,c1:c2]
    _,_,_,dem_cut,_ = stats_window(dem_w,RING_IN,RING_RIM)
    out['dem_cut_m'] = dem_cut
    out['match_center'] = float(score_max[r,c])
    out.update(morphology_feats(R['lrm_5'][r1:r2,c1:c2]))
    out['tmpl0_score'] = float(per_tmp[0][r,c])
    out['tmpl1_score'] = float(per_tmp[1][r,c])
    out['tmpl2_score'] = float(per_tmp[2][r,c])
    out['tmpl_max'] = float(score_max[r,c])
    return out


def extract_all(xs, ys, tile, R, per_tmp, sm, label):
    print(f'\n=== {label}: extracting features ({len(xs)} candidates) ===', flush=True)
    t0 = time.time()
    feats, keep = [], []
    for i,(x,y) in enumerate(zip(xs,ys)):
        f = feats_for(x,y,tile,R,per_tmp,sm)
        if f is not None: feats.append(f); keep.append(i)
        if (i+1) % 50000 == 0:
            print(f'  {i+1}/{len(xs)} ({time.time()-t0:.0f}s)', flush=True)
    print(f'  done: {len(feats)} valid in {time.time()-t0:.1f}s', flush=True)
    return pd.DataFrame(feats), np.array(keep)

X3_df, k3 = extract_all(x3, y3, O3, R_o3, per_tmp_o3, sm_o3, 'output3_2008')
Xs_df, ks = extract_all(xs, ys, SEP, R_sep, per_tmp_sep, sm_sep, 'sep_2008')

common = sorted(set(X3_df.columns) & set(Xs_df.columns))
X3_df = X3_df[common]; Xs_df = Xs_df[common]
X3 = X3_df.fillna(0).to_numpy(dtype=np.float32)
Xs = Xs_df.fillna(0).to_numpy(dtype=np.float32)

o3_xy = np.c_[x3[k3], y3[k3]]
dn3,near3 = tree_pit.query(o3_xy, k=1)
y3_lbl = (dn3 <= POS_DIST_M).astype(np.int8)
print(f'\ntrain: {X3.shape}  pos={y3_lbl.sum()}   test: {Xs.shape}', flush=True)


# =========================================================================
# 4. Train + apply
# =========================================================================
print('\n=== training ===', flush=True)
N_GROUPS = 8
agg = AgglomerativeClustering(n_clusters=N_GROUPS).fit(pit_xy)
groups = agg.labels_[near3]
scale_pos = (len(y3_lbl)-y3_lbl.sum()) / max(y3_lbl.sum(),1)

def make_xgb():
    return xgb.XGBClassifier(objective='binary:logistic', tree_method='hist',
        n_estimators=500, max_depth=5, learning_rate=0.05,
        min_child_weight=2, subsample=0.8, colsample_bytree=0.8,
        reg_lambda=1.0, scale_pos_weight=scale_pos, random_state=0, n_jobs=-1)

def make_lgb():
    return lgb.LGBMClassifier(objective='binary', n_estimators=500, learning_rate=0.05,
        num_leaves=31, min_child_samples=5, subsample=0.8, colsample_bytree=0.8,
        reg_lambda=1.0, scale_pos_weight=scale_pos, random_state=0, n_jobs=-1, verbose=-1)

def oof_fit(make_clf, X, y, g):
    oof = np.zeros(len(y), dtype=np.float32)
    gkf = GroupKFold(n_splits=min(5, N_GROUPS))
    for tr,te in gkf.split(X, y, groups=g):
        clf = make_clf(); clf.fit(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])[:,1]
    return oof

p_xgb = oof_fit(make_xgb, X3, y3_lbl, groups)
p_lgb = oof_fit(make_lgb, X3, y3_lbl, groups)
p_avg = (p_xgb+p_lgb)/2
print(f'XGB  ROC {roc_auc_score(y3_lbl,p_xgb):.4f}  PR {average_precision_score(y3_lbl,p_xgb):.4f}', flush=True)
print(f'LGBM ROC {roc_auc_score(y3_lbl,p_lgb):.4f}  PR {average_precision_score(y3_lbl,p_lgb):.4f}', flush=True)
print(f'AVG  ROC {roc_auc_score(y3_lbl,p_avg):.4f}  PR {average_precision_score(y3_lbl,p_avg):.4f}', flush=True)
iso = IsotonicRegression(out_of_bounds='clip').fit(p_avg, y3_lbl)

final_xgb = make_xgb(); final_xgb.fit(X3, y3_lbl)
final_lgb = make_lgb(); final_lgb.fit(X3, y3_lbl)
ps_raw = (final_xgb.predict_proba(Xs)[:,1] + final_lgb.predict_proba(Xs)[:,1])/2
ps_cal = iso.predict(ps_raw).astype(np.float32)


# =========================================================================
# 5. Output
# =========================================================================
sep_xy = np.c_[xs[ks], ys[ks]]
out = gpd.GeoDataFrame({
    'proba': ps_cal, 'proba_raw': ps_raw,
    'geometry': [Point(x,y) for x,y in sep_xy],
}, crs=CRS).sort_values('proba', ascending=False).reset_index(drop=True)
out.to_file(DERIV / 'pit_candidates_sep_2008.gpkg', driver='GPKG')
print(f'\nwrote pit_candidates_sep_2008.gpkg ({len(out)} rows)', flush=True)

print(f'\n{"thr":>5} {"n":>6}')
with open(DERIV / 'pit_sep_2008_metrics.txt', 'w') as f:
    f.write(f'Cross-tile: trained on output3 2008 1m, applied to sep 2008 1m\n')
    f.write(f'Train: {X3.shape}  pos={int(y3_lbl.sum())}\nTest: {Xs.shape}\n\n')
    f.write(f'{"thr":>5} {"n":>6}\n')
    for thr in [0.20,0.30,0.40,0.50,0.60,0.70,0.80,0.90]:
        n = int((out['proba']>=thr).sum())
        f.write(f'{thr:5.2f} {n:6d}\n')
        print(f'{thr:5.2f} {n:6d}')

# overview
print('\n=== overview PNG ===', flush=True)
with rasterio.open(DERIV / 'hillshade_sep_2008_1m.tif') as ds:
    hs = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: hs = np.where(hs==nd, np.nan, hs)

fig, ax = plt.subplots(figsize=(15, 15))
ax.imshow(hs, cmap='gray', extent=[SEP['X0'],SEP['X1'],SEP['Y0'],SEP['Y1']])
for thr, color, sz, lbl in [(0.50,'yellow',25,'0.50-0.70'),
                              (0.70,'orange',40,'0.70-0.90'),
                              (0.90,'red',60,'>=0.90')]:
    if thr == 0.50:
        sub = out[(out['proba']>=0.50)&(out['proba']<0.70)]
    elif thr == 0.70:
        sub = out[(out['proba']>=0.70)&(out['proba']<0.90)]
    else:
        sub = out[out['proba']>=0.90]
    if len(sub):
        ax.scatter(sub.geometry.x, sub.geometry.y, s=sz, c=color,
                   edgecolors='black', linewidths=0.3,
                   label=f'proba {lbl} (n={len(sub)})')
ax.set_title(f'sep area pit predictions (2008 PAMAP only, 1m)\n'
             f'total candidates: {len(out)}', fontsize=12)
ax.legend(loc='lower left', fontsize=9)
ax.set_xlim(SEP['X0'],SEP['X1']); ax.set_ylim(SEP['Y0'],SEP['Y1'])
fig.savefig(DERIV / 'pit_sep_2008_overview.png', dpi=140, bbox_inches='tight')
plt.close(fig)
print('wrote pit_sep_2008_overview.png', flush=True)
print('\nDONE.', flush=True)
