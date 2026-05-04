"""Retrain with 675 pits + land cover features.

Adds per-candidate land cover stats from the 1m land cover clips:
  - lc_center: class at candidate center
  - lc_tree_frac: fraction tree canopy (class 3) in 15m window
  - lc_low_veg_frac: fraction low veg (class 5) in 15m window
  - lc_impervious_frac: fraction impervious (7+8+9) in 15m window
  - lc_agriculture_frac: fraction agriculture (class 15) in 15m window
  - lc_canopy_over_frac: fraction canopy-over-infrastructure (10+11+12)

Uses existing 9-tile + McKean 1m derivatives (already rebuilt).
"""
import json, subprocess, shutil, time
import numpy as np, laspy, rasterio, geopandas as gpd, pandas as pd
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from scipy.ndimage import uniform_filter
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from shapely.geometry import Point
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.isotonic import IsotonicRegression
from skimage.feature import match_template, peak_local_max
import xgboost as xgb
import lightgbm as lgb
import pyproj
import matplotlib.pyplot as plt
from pathlib import Path

DATA  = Path('data/files'); DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
CRS   = 'EPSG:6346'
RES   = 1.0
HALF, INNER, OUTER = 8, 3, 6
SNAP_R = 3; POS_DIST_M = 10.0

TILES = {
    '9tile': dict(X0=619500.0,Y0=4593000.0,X1=624000.0,Y1=4597500.0,sfx='_9t_1m',
                  lc_path='data/derivatives/landcover_venango_1m.tif'),
    'mckean': dict(X0=697000.0,Y0=4646500.0,X1=701000.0,Y1=4650500.0,sfx='_mk_1m',
                   lc_path='data/derivatives/landcover_mckean_1m.tif'),
}
for t in TILES.values():
    t['W']=int((t['X1']-t['X0'])/RES);t['H']=int((t['Y1']-t['Y0'])/RES)
    t['T']=from_origin(t['X0'],t['Y1'],RES,RES)


def read_tif(name):
    with rasterio.open(DERIV/name) as ds:
        a=ds.read(1).astype(np.float32);nd=ds.nodata
    if nd is not None: a=np.where(a==nd,np.nan,a)
    return a

CHANS_D=['lrm_5','lrm_11','tpi_15','openness_neg']

def load_rasters(tile):
    sfx=tile['sfx'];R={}
    for ch in CHANS_D:R[ch]=read_tif(f'{ch}{sfx}.tif')
    R['dem']=read_tif(f'dem{sfx}.tif');R['slope']=read_tif(f'slope{sfx}.tif')
    R['chm']=read_tif(f'chm{sfx}.tif');R['ground_density']=read_tif(f'ground_density{sfx}.tif')
    return R


# Load land cover rasters + build transformers
def load_lc(tile):
    with rasterio.open(tile['lc_path']) as ds:
        lc_data = ds.read(1)
        lc_transform = ds.transform
        lc_crs = ds.crs
        lc_shape = ds.shape
    transformer = pyproj.Transformer.from_crs(CRS, lc_crs, always_xy=True)
    return lc_data, lc_transform, lc_shape, transformer


def lc_features(x, y, lc_data, lc_transform, lc_shape, transformer, radius_m=15):
    """Extract land cover stats in a window around (x,y) UTM."""
    lx, ly = transformer.transform(x, y)
    cr, cc = rasterio.transform.rowcol(lc_transform, lx, ly)
    r_cells = int(round(radius_m))  # 1m LC resolution
    r1,r2 = max(0,cr-r_cells),min(lc_shape[0],cr+r_cells+1)
    c1,c2 = max(0,cc-r_cells),min(lc_shape[1],cc+r_cells+1)
    if r2<=r1 or c2<=c1:
        return {'lc_center':0,'lc_tree_frac':np.nan,'lc_low_veg_frac':np.nan,
                'lc_impervious_frac':np.nan,'lc_agriculture_frac':np.nan,
                'lc_canopy_over_frac':np.nan,'lc_barren_frac':np.nan}
    win = lc_data[r1:r2, c1:c2]
    n = win.size
    center = int(lc_data[min(cr,lc_shape[0]-1), min(cc,lc_shape[1]-1)]) if 0<=cr<lc_shape[0] and 0<=cc<lc_shape[1] else 0
    return {
        'lc_center': center,
        'lc_tree_frac': float((win==3).sum()/n),
        'lc_low_veg_frac': float((win==5).sum()/n),
        'lc_impervious_frac': float(np.isin(win,[7,8,9]).sum()/n),
        'lc_agriculture_frac': float((win==15).sum()/n),
        'lc_canopy_over_frac': float(np.isin(win,[10,11,12]).sum()/n),
        'lc_barren_frac': float((win==6).sum()/n),
    }


# =========================================================================
# Load everything
# =========================================================================
print('=== loading ===',flush=True)
pits = gpd.read_file(ANNO/'wellhead_pits.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x,g.y] for g in pits.geometry])
tree_pit = cKDTree(pit_xy)
print(f'pits: {len(pits)}')

rasters = {k: load_rasters(t) for k,t in TILES.items()}
lc_data_dict = {}
for k,t in TILES.items():
    lc_data_dict[k] = load_lc(t)
    print(f'  {k} LC loaded: {lc_data_dict[k][0].shape}')


# =========================================================================
# Templates from all 675 pits
# =========================================================================
print('\n=== templates ===',flush=True)
def rc(x,y,tile): return int(round((tile['Y1']-y)/RES)),int(round((x-tile['X0'])/RES))
def which_tile(x,y):
    for k,t in TILES.items():
        if t['X0']<=x<=t['X1'] and t['Y0']<=y<=t['Y1']:return k
    return None

cutouts=[]
for(x,y)in pit_xy:
    tk=which_tile(x,y)
    if tk is None:continue
    t=TILES[tk];lrm5=rasters[tk]['lrm_5']
    r0,c0=rc(x,y,t)
    r1,r2=max(0,r0-SNAP_R),min(t['H'],r0+SNAP_R+1)
    c1,c2=max(0,c0-SNAP_R),min(t['W'],c0+SNAP_R+1)
    win=lrm5[r1:r2,c1:c2]
    if np.isnan(win).all():continue
    f=np.nanargmin(win);dr,dc=divmod(f,win.shape[1])
    sr,sc=r1+dr,c1+dc
    r1,r2=sr-HALF,sr+HALF+1;c1,c2=sc-HALF,sc+HALF+1
    if r1<0 or c1<0 or r2>t['H'] or c2>t['W']:continue
    w=lrm5[r1:r2,c1:c2].astype(np.float32)
    if np.isnan(w).mean()>0.2:continue
    cutouts.append(w-np.nanmean(w))
cutouts=np.stack(cutouts)
flat=np.nan_to_num(cutouts.reshape(len(cutouts),-1),nan=0)
Z=PCA(n_components=5,random_state=0).fit_transform(flat)
km=KMeans(n_clusters=3,n_init=10,random_state=0).fit(Z)
templates=np.stack([np.nanmedian(cutouts[km.labels_==k],axis=0) for k in range(3)])
templates=np.nan_to_num(templates,nan=0)
print(f'cutouts: {len(cutouts)}  clusters: {np.bincount(km.labels_).tolist()}',flush=True)


# =========================================================================
# Candidates
# =========================================================================
print('\n=== candidates ===',flush=True)
def make_rings():
    yy,xx=np.ogrid[-HALF:HALF+1,-HALF:HALF+1];rad=np.sqrt(xx*xx+yy*yy)
    return rad<=INNER,(rad>=OUTER)&(rad<=HALF),rad
RING_IN,RING_RIM,RAD=make_rings()
RADIAL_BINS=[(0,1),(1,3),(3,5),(5,8)]

all_cands=[]
for tk,t in TILES.items():
    lrm5=rasters[tk]['lrm_5']
    valid=~np.isnan(lrm5);img=np.where(valid,lrm5,0).astype(np.float32)
    t0=time.time()
    per_tmp=[match_template(img,templates[k].astype(np.float32),pad_input=True) for k in range(3)]
    for s in per_tmp:s[~valid]=np.nan
    sm=np.nanmax(np.stack(per_tmp),axis=0)
    peaks=peak_local_max(np.nan_to_num(sm,nan=-1),min_distance=int(round(5.0/RES)),threshold_abs=0.148)
    rows,cols=peaks[:,0],peaks[:,1]
    xs=t['X0']+(cols+0.5)*RES;ys=t['Y1']-(rows+0.5)*RES
    print(f'  {tk}: {len(peaks)} candidates in {time.time()-t0:.1f}s',flush=True)
    all_cands.append((tk,xs,ys,per_tmp,sm))


# =========================================================================
# Features (including land cover)
# =========================================================================
print('\n=== feature extraction ===',flush=True)

def stats_window(z,inner,rim):
    zi=z[inner];zr=z[rim]
    if np.isfinite(zi).any() and np.isfinite(zr).any():
        return(np.nanmin(zi),np.nanmean(zi),np.nanmean(zr),np.nanmean(zr)-np.nanmin(zi),np.nanstd(zi))
    return(np.nan,)*5

def radial_std_f(z):
    if not np.isfinite(z).any():return np.nan
    angs=np.linspace(0,2*np.pi,8,endpoint=False);zs=[]
    for a in angs:
        rr=int(round(HALF+INNER*np.sin(a)));cc=int(round(HALF+INNER*np.cos(a)))
        if 0<=rr<z.shape[0] and 0<=cc<z.shape[1]:
            v=z[rr,cc]
            if np.isfinite(v):zs.append(v)
    return float(np.std(zs)) if len(zs)>=4 else np.nan

def morphology_feats(win):
    keys=['morph_depth','morph_sigma_major','morph_sigma_minor','morph_aspect',
          'morph_compactness','morph_prof_r0','morph_prof_r1','morph_prof_r2',
          'morph_prof_r3','morph_radial_rho','morph_fit_residual']
    if not np.isfinite(win).any():return{k:np.nan for k in keys}
    w=np.where(np.isnan(win),0,win).astype(np.float64)
    mass=np.clip(-w,0,None);total=mass.sum()
    if total<1e-6:return{k:np.nan for k in keys}
    yyg,xxg=np.mgrid[0:win.shape[0],0:win.shape[1]]
    cy=(mass*yyg).sum()/total;cx=(mass*xxg).sum()/total
    vy=(mass*(yyg-cy)**2).sum()/total;vx=(mass*(xxg-cx)**2).sum()/total
    cxy=(mass*(yyg-cy)*(xxg-cx)).sum()/total
    tr=vx+vy;det=vx*vy-cxy*cxy;disc=max(tr*tr/4-det,0)
    lam1=tr/2+np.sqrt(disc);lam2=tr/2-np.sqrt(disc)
    sm_=float(np.sqrt(max(lam1,1e-6)));sn_=float(np.sqrt(max(lam2,1e-6)))
    out={'morph_depth':float(-np.nanmin(w)),'morph_sigma_major':sm_,'morph_sigma_minor':sn_,
         'morph_aspect':sn_/sm_,'morph_compactness':total/(np.pi*sm_*sn_+1e-6)}
    prof=[]
    for(rmin,rmax)in RADIAL_BINS:
        m=(RAD>=rmin)&(RAD<rmax);vals=w[m];prof.append(float(vals.mean()) if len(vals) else np.nan)
    out['morph_prof_r0'],out['morph_prof_r1']=prof[0],prof[1]
    out['morph_prof_r2'],out['morph_prof_r3']=prof[2],prof[3]
    radii=np.array([np.mean(b) for b in RADIAL_BINS])
    out['morph_radial_rho']=float(spearmanr(radii,prof)[0]) if not np.any(np.isnan(prof)) else np.nan
    theta=0.0 if(cxy==0 and vx==vy)else 0.5*np.arctan2(2*cxy,(vx-vy))
    ct,st=np.cos(theta),np.sin(theta);A=out['morph_depth']
    gx=xxg-cx;gy=yyg-cy;gxr=ct*gx+st*gy;gyr=-st*gx+ct*gy
    g=-A*np.exp(-0.5*((gxr/sm_)**2+(gyr/sn_)**2))
    out['morph_fit_residual']=float(np.sqrt(np.nanmean((w-g)**2)))/(A+1e-6)
    return out

def feats_for(x,y,tk,per_tmp,score_max):
    t=TILES[tk];R=rasters[tk]
    r,c=rc(x,y,t)
    r1,r2=r-HALF,r+HALF+1;c1,c2=c-HALF,c+HALF+1
    if r1<0 or c1<0 or r2>t['H'] or c2>t['W']:return None
    out={}
    for ch in CHANS_D:
        w=R[ch][r1:r2,c1:c2]
        mni,mi,mr,diff,_=stats_window(w,RING_IN,RING_RIM)
        out[f'{ch}_imin']=mni;out[f'{ch}_imean']=mi;out[f'{ch}_rmean']=mr
        out[f'{ch}_rdiff']=diff;out[f'{ch}_sym']=radial_std_f(w)
    sl=R['slope'][r1:r2,c1:c2][RING_IN]
    out['slope_imean']=float(np.nanmean(sl)) if np.isfinite(sl).any() else np.nan
    out['slope_wmax']=float(np.nanmax(R['slope'][r1:r2,c1:c2])) if np.isfinite(R['slope'][r1:r2,c1:c2]).any() else np.nan
    chm=R['chm'][r1:r2,c1:c2]
    out['chm_imean']=float(np.nanmean(chm[RING_IN])) if np.isfinite(chm[RING_IN]).any() else np.nan
    out['chm_wmax']=float(np.nanmax(chm)) if np.isfinite(chm).any() else np.nan
    dens=R['ground_density'][r1:r2,c1:c2]
    out['dens_imean']=float(np.nanmean(dens[RING_IN]))
    out['dens_wmean']=float(np.nanmean(dens))
    dem_w=R['dem'][r1:r2,c1:c2]
    _,_,_,dc,_=stats_window(dem_w,RING_IN,RING_RIM)
    out['dem_cut_m']=dc
    out['match_center']=float(score_max[r,c])
    out.update(morphology_feats(R['lrm_5'][r1:r2,c1:c2]))
    out['tmpl0_score']=float(per_tmp[0][r,c])
    out['tmpl1_score']=float(per_tmp[1][r,c])
    out['tmpl2_score']=float(per_tmp[2][r,c])
    out['tmpl_max']=float(score_max[r,c])
    # Land cover features
    lcd,lct,lcs,lc_trans = lc_data_dict[tk]
    out.update(lc_features(x, y, lcd, lct, lcs, lc_trans))
    return out

feat_list,keep_xy,keep_tile=[],[],[]
for tk,xs,ys,per_tmp,sm in all_cands:
    t0=time.time()
    n0=len(feat_list)
    for i,(x,y) in enumerate(zip(xs,ys)):
        f=feats_for(x,y,tk,per_tmp,sm)
        if f is not None:
            feat_list.append(f);keep_xy.append((x,y));keep_tile.append(tk)
        if(i+1)%50000==0:print(f'  {tk}: {i+1}/{len(xs)} ({time.time()-t0:.0f}s)',flush=True)
    print(f'  {tk}: {len(feat_list)-n0} features in {time.time()-t0:.1f}s',flush=True)

X_df=pd.DataFrame(feat_list)
keep_xy=np.array(keep_xy);keep_tile=np.array(keep_tile)
X_arr=X_df.fillna(0).to_numpy(dtype=np.float32)

dn,nearest=tree_pit.query(keep_xy,k=1)
y=(dn<=POS_DIST_M).astype(np.int8)
print(f'\nfeatures: {X_arr.shape}  positives: {y.sum()}  ({100*y.mean():.2f}%)',flush=True)
print(f'land cover columns: {[c for c in X_df.columns if "lc_" in c]}',flush=True)


# =========================================================================
# Train
# =========================================================================
print('\n=== training ===',flush=True)
N_GROUPS=15
agg=AgglomerativeClustering(n_clusters=N_GROUPS).fit(pit_xy)
groups=agg.labels_[nearest]
scale_pos=(len(y)-y.sum())/max(y.sum(),1)

def make_xgb():
    return xgb.XGBClassifier(objective='binary:logistic',tree_method='hist',
        n_estimators=500,max_depth=5,learning_rate=0.05,min_child_weight=2,
        subsample=0.8,colsample_bytree=0.8,reg_lambda=1.0,
        scale_pos_weight=scale_pos,random_state=0,n_jobs=-1)
def make_lgb():
    return lgb.LGBMClassifier(objective='binary',n_estimators=500,learning_rate=0.05,
        num_leaves=31,min_child_samples=5,subsample=0.8,colsample_bytree=0.8,
        reg_lambda=1.0,scale_pos_weight=scale_pos,random_state=0,n_jobs=-1,verbose=-1)
def oof_fit(make_clf):
    oof=np.zeros(len(y),dtype=np.float32)
    gkf=GroupKFold(n_splits=min(5,N_GROUPS))
    for tr,te in gkf.split(X_arr,y,groups=groups):
        clf=make_clf();clf.fit(X_arr[tr],y[tr])
        oof[te]=clf.predict_proba(X_arr[te])[:,1]
    return oof

p_xgb=oof_fit(make_xgb);p_lgb=oof_fit(make_lgb)
p_avg=(p_xgb+p_lgb)/2
print(f'XGB  ROC {roc_auc_score(y,p_xgb):.4f}  PR {average_precision_score(y,p_xgb):.4f}',flush=True)
print(f'LGBM ROC {roc_auc_score(y,p_lgb):.4f}  PR {average_precision_score(y,p_lgb):.4f}',flush=True)
print(f'AVG  ROC {roc_auc_score(y,p_avg):.4f}  PR {average_precision_score(y,p_avg):.4f}',flush=True)
iso=IsotonicRegression(out_of_bounds='clip').fit(p_avg,y)
p_cal=iso.predict(p_avg).astype(np.float32)

# Feature importance
final=make_xgb();final.fit(X_arr,y)
imp=pd.Series(final.feature_importances_,index=X_df.columns).sort_values(ascending=True)
fig,ax=plt.subplots(figsize=(8,10))
imp.tail(30).plot(kind='barh',ax=ax);ax.set_title('top-30 features (675 pits + land cover)')
ax.grid(alpha=0.3);fig.tight_layout()
fig.savefig(DERIV/'pit_675_lc_feature_importance.png',dpi=130,bbox_inches='tight')
plt.close(fig)


# =========================================================================
# Output per tile
# =========================================================================
print('\n=== output ===',flush=True)
for tk in ['9tile','mckean']:
    t=TILES[tk]
    mask=keep_tile==tk
    gdf=gpd.GeoDataFrame({
        'proba':p_cal[mask],'proba_raw':p_avg[mask],
        'geometry':[Point(x,y) for x,y in keep_xy[mask]]
    },crs=CRS).sort_values('proba',ascending=False).reset_index(drop=True)

    fname=f'pit_candidates_675lc_{tk}.gpkg'
    gdf.to_file(DERIV/fname,driver='GPKG')

    tile_pits=pit_xy[
        (pit_xy[:,0]>=t['X0'])&(pit_xy[:,0]<=t['X1'])&
        (pit_xy[:,1]>=t['Y0'])&(pit_xy[:,1]<=t['Y1'])]
    tree_t=cKDTree(tile_pits) if len(tile_pits)>0 else None

    print(f'\n{tk}: {fname} ({len(gdf)} rows)  pits_in_tile={len(tile_pits)}')
    print(f'{"thr":>5} {"n":>6} {"hits":>6} {"pits":>6} {"prec":>7}')
    with open(DERIV/f'pit_675lc_{tk}_metrics.txt','w') as f:
        f.write(f'675-pit + land cover: {tk}\npits: {len(tile_pits)}\n\n')
        for thr in [0.30,0.50,0.70,0.80,0.90]:
            sub=gdf[gdf['proba']>=thr]
            if len(sub)==0:
                line=f'{thr:5.2f} {0:6d} {0:6d} {0:6d} {"n/a":>7}'
            else:
                sxy=np.c_[sub.geometry.x,sub.geometry.y]
                if tree_t is not None:
                    dn2,_=tree_t.query(sxy,k=1);hit=int((dn2<=10).sum())
                    _,idx=tree_t.query(sxy[dn2<=10],k=1) if hit else(None,np.array([]))
                    pcov=len(np.unique(idx)) if hit else 0
                    prec=hit/len(sub)
                else:hit=0;pcov=0;prec=0
                line=f'{thr:5.2f} {len(sub):6d} {hit:6d} {pcov:6d} {prec:7.2%}'
            print(line);f.write(line+'\n')

    hs=read_tif(f'hillshade{t["sfx"]}.tif')
    fig,ax=plt.subplots(figsize=(14,14))
    ax.imshow(hs,cmap='gray',extent=[t['X0'],t['X1'],t['Y0'],t['Y1']])
    if len(tile_pits):
        ax.scatter(tile_pits[:,0],tile_pits[:,1],s=30,c='red',marker='o',linewidths=0,
                   label=f'annotated ({len(tile_pits)})')
    top=gdf[gdf['proba']>=0.50]
    if len(top) and tree_t is not None:
        sxy=np.c_[top.geometry.x,top.geometry.y]
        dn2,_=tree_t.query(sxy,k=1);tp=sxy[dn2<=10]
        if len(tp):
            ax.scatter(tp[:,0],tp[:,1],s=70,c='lime',marker='X',linewidths=0,label=f'found ({len(tp)})')
    ax.set_title(f'675 pits + land cover: {tk}',fontsize=12)
    ax.legend(loc='lower left',fontsize=9)
    ax.set_xlim(t['X0'],t['X1']);ax.set_ylim(t['Y0'],t['Y1'])
    fig.savefig(DERIV/f'pit_675lc_{tk}_overview.png',dpi=130,bbox_inches='tight')
    plt.close(fig)
    print(f'wrote pit_675lc_{tk}_overview.png')

print('\nDONE.',flush=True)
