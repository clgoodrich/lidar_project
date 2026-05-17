"""Run the full pipeline (derivatives + XGB) on 2 standalone LAZ tiles.

Tiles:
  17TPF607594 — 14 km west of training area
  17TPG610605 — 15 km north of training area

Each tile is 1.5 km x 1.5 km, processed independently at 1m.
Model trained on 9-tile (538 pits) at 1m, applied blind to each.
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
import matplotlib.pyplot as plt
from pathlib import Path

DATA=Path('data/files');DERIV=Path('data/derivatives');ANNO=Path('data/derivatives/annotations')
PDAL=shutil.which('pdal') or 'pdal';CRS='EPSG:6346';RES=1.0
HALF,INNER,OUTER=8,3,6;SNAP_R=3;POS_DIST_M=10.0

# Training tile (9-tile, already has derivatives)
TRAIN=dict(X0=619500.0,Y0=4593000.0,X1=624000.0,Y1=4597500.0,sfx='_9t_1m')
TRAIN['W']=int((TRAIN['X1']-TRAIN['X0'])/RES);TRAIN['H']=int((TRAIN['Y1']-TRAIN['Y0'])/RES)

# Test tiles
TEST_TILES=[
    dict(code='607594',path=DATA/'USGS_LPC_PA_WesternPA_2019_D20_17TPF607594.laz',
         X0=607500.0,Y0=4594500.0,X1=609000.0,Y1=4596000.0,sfx='_607594_1m',label='14km west'),
    dict(code='610605',path=DATA/'USGS_LPC_PA_WesternPA_2019_D20_17TPG610605.laz',
         X0=610500.0,Y0=4605000.0,X1=612000.0,Y1=4606500.0,sfx='_610605_1m',label='15km north'),
]
for t in TEST_TILES:
    t['W']=int((t['X1']-t['X0'])/RES);t['H']=int((t['Y1']-t['Y0'])/RES)
    t['T']=from_origin(t['X0'],t['Y1'],RES,RES)

def run_pipeline(pl,label,timeout=600):
    tmp=DERIV/f'_tmp_{label}.json'
    with open(tmp,'w') as f:json.dump(pl,f,indent=2)
    t0=time.time()
    r=subprocess.run([PDAL,'pipeline',str(tmp)],capture_output=True,text=True,timeout=timeout)
    print(f'[{label}] rc={r.returncode} in {time.time()-t0:.1f}s',flush=True)
    if r.returncode!=0:print(r.stderr[-1500:]);raise RuntimeError(label)
    tmp.unlink(missing_ok=True)

def write_tif(name,arr,T,W,H,dtype='float32',nd=-9999.0):
    a=arr.astype(dtype)
    if dtype.startswith('float'):a=np.where(np.isnan(a),nd,a).astype(dtype)
    with rasterio.open(DERIV/name,'w',driver='GTiff',height=H,width=W,count=1,
                       dtype=dtype,crs=CRS,transform=T,nodata=nd,
                       tiled=True,compress='deflate',
                       predictor=(3 if dtype.startswith('float') else 2)) as ds:
        ds.write(a,1)

def read_tif(name):
    with rasterio.open(DERIV/name) as ds:
        a=ds.read(1).astype(np.float32);nd=ds.nodata
    if nd is not None:a=np.where(a==nd,np.nan,a)
    return a

CHANS_D=['lrm_5','lrm_11','tpi_15','openness_neg']

def build_derivatives(tile):
    sfx=tile['sfx'];X0,Y0,X1,Y1=tile['X0'],tile['Y0'],tile['X1'],tile['Y1']
    W,H,T=tile['W'],tile['H'],tile['T'];src=str(tile['path'])
    print(f'\n=== building derivatives for {tile["code"]} ===',flush=True)
    # DEM
    run_pipeline({'pipeline':[
        {'type':'readers.las','filename':src},
        {'type':'filters.range','limits':'Classification[2:2]'},
        {'type':'filters.delaunay'},
        {'type':'filters.faceraster','resolution':RES,'origin_x':X0,'origin_y':Y0,'width':W,'height':H},
        {'type':'writers.raster','filename':str(DERIV/f'dem{sfx}.tif'),'data_type':'float32'},
    ]},f'dem{sfx}')
    dem=read_tif(f'dem{sfx}.tif')
    # DSM+CHM
    run_pipeline({'pipeline':[
        {'type':'readers.las','filename':src},
        {'type':'filters.range','limits':'ReturnNumber[1:1]'},
        {'type':'writers.gdal','filename':str(DERIV/f'dsm{sfx}.tif'),'output_type':'max','resolution':RES,
         'origin_x':X0,'origin_y':Y0,'width':W,'height':H,'data_type':'float32'},
    ]},f'dsm{sfx}')
    dsm=read_tif(f'dsm{sfx}.tif')
    chm=np.where(np.isnan(dsm)|np.isnan(dem),np.nan,np.maximum(dsm-dem,0)).astype(np.float32)
    write_tif(f'chm{sfx}.tif',chm,T,W,H)
    # Density
    las=laspy.read(src);xs=np.asarray(las.x);ys=np.asarray(las.y);cls=np.asarray(las.classification)
    gm=(cls==2);col=np.floor((xs[gm]-X0)/RES).astype(np.int64);row=np.floor((Y1-ys[gm])/RES).astype(np.int64)
    ok=(col>=0)&(col<W)&(row>=0)&(row<H);fi=(row[ok]*W+col[ok])
    dens=np.bincount(fi,minlength=H*W).reshape(H,W).astype(np.uint16)
    write_tif(f'ground_density{sfx}.tif',dens,T,W,H,dtype='uint16',nd=0);del las
    # WBT
    import whitebox;wbt=whitebox.WhiteboxTools();wbt.set_working_dir(str(DERIV.resolve()));wbt.set_verbose_mode(False)
    wbt.hillshade(dem=f'dem{sfx}.tif',output=f'hillshade{sfx}.tif',azimuth=315.0,altitude=45.0)
    wbt.slope(dem=f'dem{sfx}.tif',output=f'slope{sfx}.tif',units='degrees')
    # Python
    def dk(r):r=int(round(r));y,x=np.ogrid[-r:r+1,-r:r+1];return(x*x+y*y)<=r*r
    def nmf(a,k):
        v=np.isfinite(a).astype(np.float32);a0=np.where(v.astype(bool),a,0).astype(np.float32)
        s=ndi.convolve(a0,k.astype(np.float32),mode='nearest');c=ndi.convolve(v,k.astype(np.float32),mode='nearest')
        out=np.full_like(a,np.nan,dtype=np.float32);np.divide(s,c,out=out,where=c>0);return out
    for size in(5,11):
        v=np.isfinite(dem).astype(np.float32);z0=np.where(v.astype(bool),dem,0).astype(np.float32)
        sm=uniform_filter(z0,size=size,mode='nearest');sc=uniform_filter(v,size=size,mode='nearest')
        smooth=np.where(sc>0,sm/sc,np.nan);lrm=(dem-smooth).astype(np.float32)
        write_tif(f'lrm_{size}{sfx}.tif',lrm,T,W,H)
    t15=(dem-nmf(dem,dk(15/RES))).astype(np.float32)
    write_tif(f'tpi_15{sfx}.tif',t15,T,W,H)
    # Openness neg
    dirs=[(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
    valid=np.isfinite(dem);z0=np.where(valid,dem,0).astype(np.float32)
    psi=np.zeros_like(dem,dtype=np.float32);L=25
    for dr,dc in dirs:
        step=RES*np.hypot(dr,dc);mtd=np.full_like(dem,np.inf,dtype=np.float32)
        for kk in range(1,L+1):
            zs=np.roll(z0,shift=(dr*kk,dc*kk),axis=(0,1))
            vs=np.roll(valid,shift=(dr*kk,dc*kk),axis=(0,1))
            if dr>0:vs[:dr*kk,:]=False
            elif dr<0:vs[dr*kk:,:]=False
            if dc>0:vs[:,:dc*kk]=False
            elif dc<0:vs[:,dc*kk:]=False
            ta=np.where(vs,(zs-z0)/(kk*step),np.nan).astype(np.float32)
            np.fmin(mtd,ta,out=mtd,where=vs)
        psi+=(np.pi/2+np.arctan(np.where(np.isfinite(mtd),mtd,0))).astype(np.float32)
    on=np.degrees(psi/8).astype(np.float32);on[~valid]=np.nan
    write_tif(f'openness_neg{sfx}.tif',on,T,W,H)
    print(f'  derivatives done for {tile["code"]}',flush=True)
    return dem

# Build derivatives for both test tiles
for tile in TEST_TILES:
    build_derivatives(tile)

# =========================================================================
# Load training data (9-tile)
# =========================================================================
print('\n=== loading training rasters + pits ===',flush=True)
pits=gpd.read_file(ANNO/'wellhead_pits.gpkg').to_crs(CRS)
pit_xy=np.array([[g.x,g.y] for g in pits.geometry])
# Only pits in training tile
in_train=((pit_xy[:,0]>=TRAIN['X0'])&(pit_xy[:,0]<=TRAIN['X1'])&
          (pit_xy[:,1]>=TRAIN['Y0'])&(pit_xy[:,1]<=TRAIN['Y1']))
train_pits=pit_xy[in_train]
tree_pit=cKDTree(train_pits)
print(f'training pits: {len(train_pits)}',flush=True)

def load_rasters(sfx):
    R={};
    for ch in CHANS_D:R[ch]=read_tif(f'{ch}{sfx}.tif')
    R['dem']=read_tif(f'dem{sfx}.tif');R['slope']=read_tif(f'slope{sfx}.tif')
    R['chm']=read_tif(f'chm{sfx}.tif');R['ground_density']=read_tif(f'ground_density{sfx}.tif')
    return R

R_train=load_rasters(TRAIN['sfx'])

# Templates from training pits
lrm5_train=R_train['lrm_5']
def rc(x,y,X0,Y1):return int(round((Y1-y)/RES)),int(round((x-X0)/RES))

cutouts=[]
for(x,y)in train_pits:
    r0,c0=rc(x,y,TRAIN['X0'],TRAIN['Y1'])
    r1,r2=max(0,r0-SNAP_R),min(TRAIN['H'],r0+SNAP_R+1)
    c1,c2=max(0,c0-SNAP_R),min(TRAIN['W'],c0+SNAP_R+1)
    win=lrm5_train[r1:r2,c1:c2]
    if np.isnan(win).all():continue
    f=np.nanargmin(win);dr,dc=divmod(f,win.shape[1]);sr,sc=r1+dr,c1+dc
    r1,r2=sr-HALF,sr+HALF+1;c1,c2=sc-HALF,sc+HALF+1
    if r1<0 or c1<0 or r2>TRAIN['H'] or c2>TRAIN['W']:continue
    w=lrm5_train[r1:r2,c1:c2].astype(np.float32)
    if np.isnan(w).mean()>0.2:continue
    cutouts.append(w-np.nanmean(w))
cutouts=np.stack(cutouts)
flat=np.nan_to_num(cutouts.reshape(len(cutouts),-1),nan=0)
Z=PCA(n_components=5,random_state=0).fit_transform(flat)
km=KMeans(n_clusters=3,n_init=10,random_state=0).fit(Z)
templates=np.stack([np.nanmedian(cutouts[km.labels_==k],axis=0) for k in range(3)])
templates=np.nan_to_num(templates,nan=0)
print(f'templates: {templates.shape} clusters: {np.bincount(km.labels_).tolist()}',flush=True)

# Ring masks
yy,xx=np.ogrid[-HALF:HALF+1,-HALF:HALF+1];RAD=np.sqrt(xx*xx+yy*yy)
RING_IN=RAD<=INNER;RING_RIM=(RAD>=OUTER)&(RAD<=HALF)
RADIAL_BINS=[(0,1),(1,3),(3,5),(5,8)]

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

def feats_for(x,y,X0_t,Y1_t,H_t,W_t,R,per_tmp,sm):
    r,c=rc(x,y,X0_t,Y1_t)
    r1,r2=r-HALF,r+HALF+1;c1,c2=c-HALF,c+HALF+1
    if r1<0 or c1<0 or r2>H_t or c2>W_t:return None
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
    out['dens_imean']=float(np.nanmean(dens[RING_IN]));out['dens_wmean']=float(np.nanmean(dens))
    dem_w=R['dem'][r1:r2,c1:c2];_,_,_,dc,_=stats_window(dem_w,RING_IN,RING_RIM)
    out['dem_cut_m']=dc;out['match_center']=float(sm[r,c])
    out.update(morphology_feats(R['lrm_5'][r1:r2,c1:c2]))
    out['tmpl0_score']=float(per_tmp[0][r,c]);out['tmpl1_score']=float(per_tmp[1][r,c])
    out['tmpl2_score']=float(per_tmp[2][r,c]);out['tmpl_max']=float(sm[r,c])
    return out

# =========================================================================
# Candidates + features for training tile
# =========================================================================
print('\n=== training candidates ===',flush=True)
valid=~np.isnan(lrm5_train);img=np.where(valid,lrm5_train,0).astype(np.float32)
pt_train=[match_template(img,templates[k].astype(np.float32),pad_input=True) for k in range(3)]
for s in pt_train:s[~valid]=np.nan
sm_train=np.nanmax(np.stack(pt_train),axis=0)
peaks=peak_local_max(np.nan_to_num(sm_train,nan=-1),min_distance=int(5/RES),threshold_abs=0.148)
tx=TRAIN['X0']+(peaks[:,1]+0.5)*RES;ty=TRAIN['Y1']-(peaks[:,0]+0.5)*RES
print(f'  {len(peaks)} candidates',flush=True)

feat_list,keep_xy=[],[]
for x,y in zip(tx,ty):
    f=feats_for(x,y,TRAIN['X0'],TRAIN['Y1'],TRAIN['H'],TRAIN['W'],R_train,pt_train,sm_train)
    if f is not None:feat_list.append(f);keep_xy.append((x,y))
X_train_df=pd.DataFrame(feat_list);train_xy=np.array(keep_xy)
dn,nearest=tree_pit.query(train_xy,k=1)
y_train=(dn<=POS_DIST_M).astype(np.int8)
print(f'  features: {X_train_df.shape}  pos: {y_train.sum()}',flush=True)

# Train model
N_GROUPS=15;agg=AgglomerativeClustering(n_clusters=N_GROUPS).fit(train_pits)
groups=agg.labels_[nearest]
scale_pos=(len(y_train)-y_train.sum())/max(y_train.sum(),1)
X_train=X_train_df.fillna(0).to_numpy(dtype=np.float32)

def make_xgb():
    return xgb.XGBClassifier(objective='binary:logistic',tree_method='hist',
        n_estimators=500,max_depth=5,learning_rate=0.05,min_child_weight=2,
        subsample=0.8,colsample_bytree=0.8,reg_lambda=1.0,
        scale_pos_weight=scale_pos,random_state=0,n_jobs=-1)
def make_lgb():
    return lgb.LGBMClassifier(objective='binary',n_estimators=500,learning_rate=0.05,
        num_leaves=31,min_child_samples=5,subsample=0.8,colsample_bytree=0.8,
        reg_lambda=1.0,scale_pos_weight=scale_pos,random_state=0,n_jobs=-1,verbose=-1)

print('\n=== training ensemble ===',flush=True)
fxgb=make_xgb();fxgb.fit(X_train,y_train)
flgb=make_lgb();flgb.fit(X_train,y_train)
# Quick OOF for calibration
def oof_fit(make_clf):
    oof=np.zeros(len(y_train),dtype=np.float32)
    gkf=GroupKFold(n_splits=min(5,N_GROUPS))
    for tr,te in gkf.split(X_train,y_train,groups=groups):
        clf=make_clf();clf.fit(X_train[tr],y_train[tr])
        oof[te]=clf.predict_proba(X_train[te])[:,1]
    return oof
p_avg_oof=(oof_fit(make_xgb)+oof_fit(make_lgb))/2
iso=IsotonicRegression(out_of_bounds='clip').fit(p_avg_oof,y_train)
print(f'  OOF PR-AUC: {average_precision_score(y_train,p_avg_oof):.4f}',flush=True)

# =========================================================================
# Apply to each test tile
# =========================================================================
for tile in TEST_TILES:
    sfx=tile['sfx'];X0t,Y0t,X1t,Y1t=tile['X0'],tile['Y0'],tile['X1'],tile['Y1']
    Ht,Wt=tile['H'],tile['W']
    print(f'\n=== applying to {tile["code"]} ({tile["label"]}) ===',flush=True)
    R_test=load_rasters(sfx)
    lrm5=R_test['lrm_5']
    valid=~np.isnan(lrm5);img=np.where(valid,lrm5,0).astype(np.float32)
    pt=[match_template(img,templates[k].astype(np.float32),pad_input=True) for k in range(3)]
    for s in pt:s[~valid]=np.nan
    sm=np.nanmax(np.stack(pt),axis=0)
    peaks=peak_local_max(np.nan_to_num(sm,nan=-1),min_distance=int(5/RES),threshold_abs=0.148)
    xs=X0t+(peaks[:,1]+0.5)*RES;ys=Y1t-(peaks[:,0]+0.5)*RES
    print(f'  candidates: {len(peaks)}',flush=True)

    feat_list,keep_xy=[],[]
    for x,y in zip(xs,ys):
        f=feats_for(x,y,X0t,Y1t,Ht,Wt,R_test,pt,sm)
        if f is not None:feat_list.append(f);keep_xy.append((x,y))
    X_test_df=pd.DataFrame(feat_list)[X_train_df.columns]
    X_test=X_test_df.fillna(0).to_numpy(dtype=np.float32)
    test_xy=np.array(keep_xy)
    print(f'  features: {X_test.shape}',flush=True)

    p_raw=(fxgb.predict_proba(X_test)[:,1]+flgb.predict_proba(X_test)[:,1])/2
    p_cal=iso.predict(p_raw).astype(np.float32)

    gdf=gpd.GeoDataFrame({'proba':p_cal,'proba_raw':p_raw,
        'geometry':[Point(x,y) for x,y in test_xy]},crs=CRS
    ).sort_values('proba',ascending=False).reset_index(drop=True)
    fname=f'pit_candidates_{tile["code"]}.gpkg'
    gdf.to_file(DERIV/fname,driver='GPKG')

    print(f'  wrote {fname} ({len(gdf)} rows)')
    for thr in [0.30,0.50,0.70,0.90]:
        n=int((gdf['proba']>=thr).sum())
        print(f'    proba>={thr}: {n}')

    # Overview
    hs=read_tif(f'hillshade{sfx}.tif')
    fig,ax=plt.subplots(figsize=(12,12))
    ax.imshow(hs,cmap='gray',extent=[X0t,X1t,Y0t,Y1t])
    for thr,color,sz in [(0.50,'yellow',30),(0.70,'orange',50),(0.90,'red',70)]:
        sub=gdf[(gdf['proba']>=thr)&(gdf['proba']<(thr+0.20 if thr<0.90 else 1.1))]
        if len(sub):
            ax.scatter(sub.geometry.x,sub.geometry.y,s=sz,c=color,edgecolors='black',linewidths=0.3)
    ax.set_title(f'{tile["code"]} ({tile["label"]}) - pit predictions',fontsize=12)
    ax.set_xlim(X0t,X1t);ax.set_ylim(Y0t,Y1t)
    fig.savefig(DERIV/f'pit_{tile["code"]}_overview.png',dpi=130,bbox_inches='tight')
    plt.close(fig)
    print(f'  wrote pit_{tile["code"]}_overview.png')

print('\nDONE.',flush=True)
