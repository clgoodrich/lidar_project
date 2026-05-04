"""Cross-tile pit detection: train on output3, apply to sep area (6 km x 6 km).

No ground truth exists for sep, so we train WITHOUT pad/road priors.
Templates are learned from output3's 90 annotated pits, then applied
to the sep LRM_5 for candidate generation.

Outputs (data/derivatives/):
  pit_candidates_sep.gpkg
  pit_sep_overview.png
  pit_sep_metrics.txt
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
RES19 = 0.5; RES08 = 1.0
HALF19, INNER19, OUTER19 = 15, 5, 12
HALF08, INNER08, OUTER08 =  8, 3,  6
SNAP_R = 4; POS_DIST_M = 10.0

# output3 tile (training)
O3 = dict(X0=621000.0, Y0=4594500.0, X1=622500.0, Y1=4596000.0, sfx='', sfx08='_2008_1m')
O3['W19'] = int((O3['X1']-O3['X0'])/RES19); O3['H19'] = int((O3['Y1']-O3['Y0'])/RES19)
O3['W08'] = int((O3['X1']-O3['X0'])/RES08); O3['H08'] = int((O3['Y1']-O3['Y0'])/RES08)

# sep tile (inference)
SEP = dict(X0=562500.0, Y0=4464000.0, X1=568500.0, Y1=4470000.0, sfx='_sep', sfx08='_sep_2008_1m')
SEP['W19'] = int((SEP['X1']-SEP['X0'])/RES19); SEP['H19'] = int((SEP['Y1']-SEP['Y0'])/RES19)
SEP['W08'] = int((SEP['X1']-SEP['X0'])/RES08); SEP['H08'] = int((SEP['Y1']-SEP['Y0'])/RES08)


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
RADIAL_BINS = [(0,2),(2,5),(5,10),(10,15)]


def stats_window(z, inner, rim):
    zi = z[inner]; zr = z[rim]
    if np.isfinite(zi).any() and np.isfinite(zr).any():
        return (np.nanmin(zi), np.nanmean(zi), np.nanmean(zr),
                np.nanmean(zr) - np.nanmin(zi), np.nanstd(zi))
    return (np.nan,)*5


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
    tr = vx+vy; det = vx*vy - cxy*cxy; disc = max(tr*tr/4-det, 0)
    lam1 = tr/2+np.sqrt(disc); lam2 = tr/2-np.sqrt(disc)
    sig_maj = float(np.sqrt(max(lam1,1e-6))); sig_min = float(np.sqrt(max(lam2,1e-6)))
    out = {'morph_depth': float(-np.nanmin(w)), 'morph_sigma_major': sig_maj,
           'morph_sigma_minor': sig_min, 'morph_aspect': sig_min/sig_maj,
           'morph_compactness': total/(np.pi*sig_maj*sig_min+1e-6)}
    prof = []
    for (rmin,rmax) in RADIAL_BINS:
        m = (RAD_19>=rmin)&(RAD_19<rmax); vals = w[m]
        prof.append(float(vals.mean()) if len(vals) else np.nan)
    out['morph_prof_r0'],out['morph_prof_r1']=prof[0],prof[1]
    out['morph_prof_r2'],out['morph_prof_r3']=prof[2],prof[3]
    radii = np.array([np.mean(b) for b in RADIAL_BINS])
    out['morph_radial_rho'] = float(spearmanr(radii,prof)[0]) if not np.any(np.isnan(prof)) else np.nan
    theta = 0.0 if (cxy==0 and vx==vy) else 0.5*np.arctan2(2*cxy,(vx-vy))
    ct,st = np.cos(theta),np.sin(theta); A = out['morph_depth']
    gx = xxg-cx; gy = yyg-cy
    gxr = ct*gx+st*gy; gyr = -st*gx+ct*gy
    g = -A*np.exp(-0.5*((gxr/sig_maj)**2+(gyr/sig_min)**2))
    out['morph_fit_residual'] = float(np.sqrt(np.nanmean((w-g)**2)))/(A+1e-6)
    return out


# =========================================================================
# 1. Build sub-type templates from output3 pits
# =========================================================================
print('=== building templates from output3 ===', flush=True)
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x, g.y] for g in pits.geometry])
tree_pit = cKDTree(pit_xy)

lrm5_o3 = read('lrm_5_05.tif')
def rc19(x, y, tile):
    return int(round((tile['Y1']-y)/RES19)), int(round((x-tile['X0'])/RES19))
def rc08(x, y, tile):
    return int(round((tile['Y1']-y)/RES08)), int(round((x-tile['X0'])/RES08))

snapped = []
for (x,y) in pit_xy:
    r0,c0 = rc19(x,y,O3)
    r1,r2 = max(0,r0-SNAP_R),min(O3['H19'],r0+SNAP_R+1)
    c1,c2 = max(0,c0-SNAP_R),min(O3['W19'],c0+SNAP_R+1)
    win = lrm5_o3[r1:r2,c1:c2]
    if np.isnan(win).all(): snapped.append((r0,c0)); continue
    f = np.nanargmin(win); dr,dc = divmod(f,win.shape[1])
    snapped.append((r1+dr,c1+dc))

cutouts = []
for (r,c) in snapped:
    r1,r2 = r-HALF19,r+HALF19+1; c1,c2 = c-HALF19,c+HALF19+1
    if r1<0 or c1<0 or r2>O3['H19'] or c2>O3['W19']: continue
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
# 2. Generate candidates on BOTH tiles
# =========================================================================
def gen_candidates(tile, label):
    sfx = tile['sfx']
    lrm5 = read(f'lrm_5{sfx}_05.tif')
    valid = ~np.isnan(lrm5); img = np.where(valid,lrm5,0).astype(np.float32)
    print(f'\n=== {label}: template matching ({lrm5.shape}) ===', flush=True)
    t0 = time.time()
    per_tmp = [match_template(img, templates[k].astype(np.float32), pad_input=True) for k in range(3)]
    for s in per_tmp: s[~valid] = np.nan
    score_max = np.nanmax(np.stack(per_tmp), axis=0)
    print(f'  match_template done in {time.time()-t0:.1f}s', flush=True)
    THR = 0.148
    peaks = peak_local_max(np.nan_to_num(score_max,nan=-1),
                           min_distance=int(round(5.0/RES19)), threshold_abs=THR)
    rows,cols = peaks[:,0],peaks[:,1]
    xs = tile['X0'] + (cols+0.5)*RES19
    ys = tile['Y1'] - (rows+0.5)*RES19
    print(f'  candidates: {len(peaks)}', flush=True)
    return per_tmp, score_max, xs, ys

per_tmp_o3, sm_o3, x3, y3 = gen_candidates(O3, 'output3')
per_tmp_sep, sm_sep, xs, ys = gen_candidates(SEP, 'sep')


# =========================================================================
# 3. Load rasters for both tiles
# =========================================================================
CHANS_D = ['lrm_5','lrm_11','lrm_25','tpi_05','tpi_15','openness_neg']
CHANS_S = ['slope','roughness_11','local_relief_10','chm']
CHANS_D08 = ['lrm_5','lrm_11','tpi_15','openness_neg']

def load_rasters(tile):
    sfx = tile['sfx']; sfx08 = tile['sfx08']
    R19 = {}
    for ch in CHANS_D + CHANS_S:
        R19[ch] = read(f'{ch}{sfx}_05.tif')
    R19['dem'] = read(f'dem{sfx}_05.tif')
    R19['intensity_ground'] = read(f'intensity_ground{sfx}_05.tif')
    R19['ground_density'] = read(f'ground_density{sfx}_05.tif')
    R08 = {}
    for ch in CHANS_D08:
        R08[ch] = read(f'{ch}{sfx08}.tif')
    R08['dem'] = read(f'dem{sfx08}.tif')
    R08['slope'] = read(f'slope{sfx08}.tif')
    R08['chm'] = read(f'chm{sfx08}.tif')
    R08['ground_density'] = read(f'ground_density{sfx08}.tif')
    return R19, R08

print('\n=== loading rasters ===', flush=True)
R19_o3, R08_o3 = load_rasters(O3)
R19_sep, R08_sep = load_rasters(SEP)


# =========================================================================
# 4. Feature extraction
# =========================================================================
def feats_for(x, y, tile, R19, R08, per_tmp, score_max):
    r19,c19 = rc19(x,y,tile); r08,c08 = rc08(x,y,tile)
    H19,W19 = tile['H19'],tile['W19']; H08,W08 = tile['H08'],tile['W08']
    r1,r2 = r19-HALF19, r19+HALF19+1; c1,c2 = c19-HALF19, c19+HALF19+1
    r1b,r2b = r08-HALF08, r08+HALF08+1; c1b,c2b = c08-HALF08, c08+HALF08+1
    if r1<0 or c1<0 or r2>H19 or c2>W19: return None
    if r1b<0 or c1b<0 or r2b>H08 or c2b>W08: return None
    out = {}
    for ch in CHANS_D:
        w = R19[ch][r1:r2,c1:c2]
        mni,mi,mr,diff,_ = stats_window(w,RING_IN_19,RING_RIM_19)
        out[f'{ch}_05_imin']=mni; out[f'{ch}_05_imean']=mi; out[f'{ch}_05_rmean']=mr
        out[f'{ch}_05_rdiff']=diff; out[f'{ch}_05_sym']=radial_std(w,HALF19,INNER19)
    for ch in CHANS_S:
        w = R19[ch][r1:r2,c1:c2]; wi = w[RING_IN_19]
        out[f'{ch}_05_imean'] = float(np.nanmean(wi)) if np.isfinite(wi).any() else np.nan
        out[f'{ch}_05_wmax'] = float(np.nanmax(w)) if np.isfinite(w).any() else np.nan
    wi = R19['intensity_ground'][r1:r2,c1:c2]
    out['int_imean'] = float(np.nanmean(wi[RING_IN_19])) if np.isfinite(wi[RING_IN_19]).any() else np.nan
    out['int_rmean'] = float(np.nanmean(wi[RING_RIM_19])) if np.isfinite(wi[RING_RIM_19]).any() else np.nan
    out['int_nanfrac'] = float(np.isnan(wi).mean())
    dens = R19['ground_density'][r1:r2,c1:c2]
    out['dens_imean'] = float(np.nanmean(dens[RING_IN_19]))
    out['dens_wmean'] = float(np.nanmean(dens))
    dem_w = R19['dem'][r1:r2,c1:c2]
    _,_,_,dem_cut,_ = stats_window(dem_w,RING_IN_19,RING_RIM_19)
    out['dem_cut_m'] = dem_cut
    out['match_center'] = float(score_max[r19,c19])
    for ch in CHANS_D08:
        w = R08[ch][r1b:r2b,c1b:c2b]
        mni,mi,mr,diff,_ = stats_window(w,RING_IN_08,RING_RIM_08)
        tag = ch+'_08'
        out[f'{tag}_imin']=mni; out[f'{tag}_imean']=mi; out[f'{tag}_rmean']=mr
        out[f'{tag}_rdiff']=diff; out[f'{tag}_sym']=radial_std(w,HALF08,INNER08)
    dem08 = R08['dem'][r1b:r2b,c1b:c2b]
    _,_,_,dc08,_ = stats_window(dem08,RING_IN_08,RING_RIM_08)
    out['dem_cut_08_m'] = dc08
    sl08 = R08['slope'][r1b:r2b,c1b:c2b][RING_IN_08]
    out['slope_08_imean'] = float(np.nanmean(sl08)) if np.isfinite(sl08).any() else np.nan
    chm08 = R08['chm'][r1b:r2b,c1b:c2b]
    out['chm_08_wmax'] = float(np.nanmax(chm08)) if np.isfinite(chm08).any() else np.nan
    d08 = R08['ground_density'][r1b:r2b,c1b:c2b][RING_IN_08]
    out['dens_08_imean'] = float(np.nanmean(d08))
    out['both_depths'] = -min(out.get('lrm_5_05_imin',0) or 0,
                              out.get('lrm_5_08_imin',0) or 0)
    out.update(morphology_feats(R19['lrm_5'][r1:r2,c1:c2]))
    out['tmpl0_score'] = float(per_tmp[0][r19,c19])
    out['tmpl1_score'] = float(per_tmp[1][r19,c19])
    out['tmpl2_score'] = float(per_tmp[2][r19,c19])
    out['tmpl_max'] = float(score_max[r19,c19])
    return out

def extract_all(xs, ys, tile, R19, R08, per_tmp, sm, label):
    print(f'\n=== {label}: extracting features ({len(xs)} candidates) ===', flush=True)
    t0 = time.time()
    feats, keep = [], []
    for i,(x,y) in enumerate(zip(xs,ys)):
        f = feats_for(x,y,tile,R19,R08,per_tmp,sm)
        if f is not None: feats.append(f); keep.append(i)
        if (i+1) % 50000 == 0:
            print(f'  {i+1}/{len(xs)} ({time.time()-t0:.0f}s)', flush=True)
    print(f'  done: {len(feats)} valid in {time.time()-t0:.1f}s', flush=True)
    return pd.DataFrame(feats), np.array(keep)

X3_df, k3 = extract_all(x3, y3, O3, R19_o3, R08_o3, per_tmp_o3, sm_o3, 'output3')
Xs_df, ks = extract_all(xs, ys, SEP, R19_sep, R08_sep, per_tmp_sep, sm_sep, 'sep')

# align columns
common = sorted(set(X3_df.columns) & set(Xs_df.columns))
X3_df = X3_df[common]; Xs_df = Xs_df[common]
X3 = X3_df.fillna(0).to_numpy(dtype=np.float32)
Xs = Xs_df.fillna(0).to_numpy(dtype=np.float32)

# labels for output3
o3_xy = np.c_[x3[k3], y3[k3]]
dn3,near3 = tree_pit.query(o3_xy, k=1)
y3_lbl = (dn3 <= POS_DIST_M).astype(np.int8)
print(f'\ntrain: {X3.shape}  pos={y3_lbl.sum()}   test: {Xs.shape}', flush=True)


# =========================================================================
# 5. Train ensemble on output3 (no priors)
# =========================================================================
print('\n=== training ensemble ===', flush=True)
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

# refit on all output3
final_xgb = make_xgb(); final_xgb.fit(X3, y3_lbl)
final_lgb = make_lgb(); final_lgb.fit(X3, y3_lbl)
ps_xgb = final_xgb.predict_proba(Xs)[:,1]
ps_lgb = final_lgb.predict_proba(Xs)[:,1]
ps_raw = (ps_xgb+ps_lgb)/2
ps_cal = iso.predict(ps_raw).astype(np.float32)


# =========================================================================
# 6. Output
# =========================================================================
sep_xy = np.c_[xs[ks], ys[ks]]
out = gpd.GeoDataFrame({
    'proba': ps_cal, 'proba_raw': ps_raw,
    'geometry': [Point(x,y) for x,y in sep_xy],
}, crs=CRS).sort_values('proba', ascending=False).reset_index(drop=True)
out.to_file(DERIV / 'pit_candidates_sep.gpkg', driver='GPKG')
print(f'\nwrote pit_candidates_sep.gpkg ({len(out)} rows)', flush=True)

print(f'\n{"thr":>5} {"n":>6}')
with open(DERIV / 'pit_sep_metrics.txt', 'w') as f:
    f.write(f'Cross-tile: trained on output3, applied to sep (6x6 km)\n')
    f.write(f'Train: {X3.shape}  pos={int(y3_lbl.sum())}\n')
    f.write(f'Test: {Xs.shape}\n\n')
    f.write(f'{"thr":>5} {"n":>6}\n')
    for thr in [0.20,0.30,0.40,0.50,0.60,0.70,0.80,0.90]:
        n = int((out['proba']>=thr).sum())
        f.write(f'{thr:5.2f} {n:6d}\n')
        print(f'{thr:5.2f} {n:6d}')

# overview (downsampled hillshade for memory)
print('\n=== overview PNG ===', flush=True)
with rasterio.open(DERIV / 'hillshade_sep_05.tif') as ds:
    DS = 4
    hs = ds.read(1, out_shape=(ds.height//DS, ds.width//DS)).astype(np.float32)
    nd = ds.nodata
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
ax.set_title(f'sep area pit predictions (model trained on output3, no priors)\n'
             f'total candidates: {len(out)}', fontsize=12)
ax.legend(loc='lower left', fontsize=9)
ax.set_xlim(SEP['X0'],SEP['X1']); ax.set_ylim(SEP['Y0'],SEP['Y1'])
fig.savefig(DERIV / 'pit_sep_overview.png', dpi=140, bbox_inches='tight')
plt.close(fig)
print('wrote pit_sep_overview.png', flush=True)
print('\nDONE.', flush=True)
