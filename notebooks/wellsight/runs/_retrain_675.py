"""Retrain pit detection with 675 annotated pits across 2 regions.

Step 1: Rebuild 9-tile 1m derivatives (deleted earlier)
Step 2: Template learning from all 675 pits
Step 3: Candidate generation on both tiles
Step 4: Feature extraction
Step 5: XGB+LGBM ensemble with GroupKFold spatial CV
Step 6: Ranked output + per-threshold overlays for both tiles
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

DATA  = Path('data/files'); DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
PDAL  = shutil.which('pdal') or 'pdal'
CRS   = 'EPSG:6346'
RES   = 1.0
HALF, INNER, OUTER = 8, 3, 6
SNAP_R = 3; POS_DIST_M = 10.0

# Tile definitions
TILES = {
    '9tile': dict(
        X0=619500.0, Y0=4593000.0, X1=624000.0, Y1=4597500.0,
        sfx='_9t_1m',
        las=DATA / 'output3_9tile.las',
        src_lazs=[DATA / f'USGS_LPC_PA_WesternPA_2019_D20_17TPF{c}.laz'
                  for c in ['619593','619594','619596','621593','621594','621596',
                            '622593','622594','622596']],
    ),
    'mckean': dict(
        X0=697000.0, Y0=4646500.0, X1=701000.0, Y1=4650500.0,
        sfx='_mk_1m',
        las=DATA / 'mckean_merged.las',
        src_lazs=None,  # already merged
    ),
}
for k,t in TILES.items():
    t['W'] = int((t['X1']-t['X0'])/RES)
    t['H'] = int((t['Y1']-t['Y0'])/RES)
    t['T'] = from_origin(t['X0'], t['Y1'], RES, RES)


def run_pipeline(pl, label, timeout=3600):
    tmp = DERIV / f'_tmp_{label}.json'
    with open(tmp,'w') as f: json.dump(pl,f,indent=2)
    t0 = time.time()
    r = subprocess.run([PDAL,'pipeline',str(tmp)],capture_output=True,text=True,timeout=timeout)
    print(f'[{label}] rc={r.returncode} in {time.time()-t0:.1f}s',flush=True)
    if r.returncode != 0: print(r.stderr[-1500:]); raise RuntimeError(label)
    tmp.unlink(missing_ok=True)


def write_tif(name, arr, T, W, H, dtype='float32', nd=-9999.0):
    a = arr.astype(dtype)
    if dtype.startswith('float'): a = np.where(np.isnan(a),nd,a).astype(dtype)
    with rasterio.open(DERIV/name,'w',driver='GTiff',height=H,width=W,count=1,
                       dtype=dtype,crs=CRS,transform=T,nodata=nd,
                       tiled=True,compress='deflate',
                       predictor=(3 if dtype.startswith('float') else 2)) as ds:
        ds.write(a,1)
    print('wrote',name,flush=True)


def read_tif(name):
    with rasterio.open(DERIV/name) as ds:
        a=ds.read(1).astype(np.float32); nd=ds.nodata
    if nd is not None: a=np.where(a==nd,np.nan,a)
    return a


# =========================================================================
# STEP 1: Rebuild 9-tile derivatives if needed
# =========================================================================
t9 = TILES['9tile']
if not (DERIV / f'dem{t9["sfx"]}.tif').exists():
    print('=== rebuilding 9-tile 1m derivatives ===',flush=True)

    # Merge if needed
    if not t9['las'].exists():
        stages = [{'type':'readers.las','filename':str(p)} for p in t9['src_lazs']]
        stages.append({'type':'filters.merge'})
        stages.append({'type':'writers.las','filename':str(t9['las']),
                       'minor_version':4,'dataformat_id':7,'forward':'all','compression':'false'})
        run_pipeline({'pipeline':stages},'merge_9t')

    X0,Y0,X1,Y1 = t9['X0'],t9['Y0'],t9['X1'],t9['Y1']
    W,H,T = t9['W'],t9['H'],t9['T']
    sfx = t9['sfx']

    # DEM
    run_pipeline({'pipeline':[
        {'type':'readers.las','filename':str(t9['las'])},
        {'type':'filters.range','limits':'Classification[2:2]'},
        {'type':'filters.delaunay'},
        {'type':'filters.faceraster','resolution':RES,'origin_x':X0,'origin_y':Y0,'width':W,'height':H},
        {'type':'writers.raster','filename':str(DERIV/f'dem{sfx}.tif'),'data_type':'float32'},
    ]},f'dem{sfx}')
    dem = read_tif(f'dem{sfx}.tif')

    # DSM + CHM
    run_pipeline({'pipeline':[
        {'type':'readers.las','filename':str(t9['las'])},
        {'type':'filters.range','limits':'ReturnNumber[1:1]'},
        {'type':'writers.gdal','filename':str(DERIV/f'dsm{sfx}.tif'),
         'output_type':'max','resolution':RES,'origin_x':X0,'origin_y':Y0,'width':W,'height':H,
         'data_type':'float32'},
    ]},f'dsm{sfx}')
    dsm = read_tif(f'dsm{sfx}.tif')
    chm = np.where(np.isnan(dsm)|np.isnan(dem),np.nan,np.maximum(dsm-dem,0)).astype(np.float32)
    write_tif(f'chm{sfx}.tif',chm,T,W,H)

    # Density
    las = laspy.read(str(t9['las']))
    xs=np.asarray(las.x);ys=np.asarray(las.y);cls=np.asarray(las.classification)
    gm=(cls==2)
    col=np.floor((xs[gm]-X0)/RES).astype(np.int64)
    row=np.floor((Y1-ys[gm])/RES).astype(np.int64)
    ok=(col>=0)&(col<W)&(row>=0)&(row<H)
    fi=(row[ok]*W+col[ok])
    dens=np.bincount(fi,minlength=H*W).reshape(H,W).astype(np.uint16)
    write_tif(f'ground_density{sfx}.tif',dens,T,W,H,dtype='uint16',nd=0)
    del las

    # WBT
    import whitebox
    wbt=whitebox.WhiteboxTools();wbt.set_working_dir(str(DERIV.resolve()));wbt.set_verbose_mode(False)
    wbt.hillshade(dem=f'dem{sfx}.tif',output=f'hillshade{sfx}.tif',azimuth=315.0,altitude=45.0)
    wbt.slope(dem=f'dem{sfx}.tif',output=f'slope{sfx}.tif',units='degrees')

    # Scipy derivatives
    def disk_kernel(r_cells):
        r=int(round(r_cells));y,x=np.ogrid[-r:r+1,-r:r+1];return (x*x+y*y)<=r*r
    def nanmean_filter(a,kernel):
        valid=np.isfinite(a).astype(np.float32);a0=np.where(valid.astype(bool),a,0).astype(np.float32)
        kf=kernel.astype(np.float32)
        s=ndi.convolve(a0,kf,mode='nearest');c=ndi.convolve(valid,kf,mode='nearest')
        out=np.full_like(a,np.nan,dtype=np.float32);np.divide(s,c,out=out,where=c>0);return out
    def nanmax_disk(a,kernel):
        big=np.where(np.isfinite(a),a,-np.inf);r=ndi.maximum_filter(big,footprint=kernel,mode='nearest')
        return np.where(np.isfinite(r),r,np.nan).astype(np.float32)
    def nanmin_disk(a,kernel):
        small=np.where(np.isfinite(a),a,np.inf);r=ndi.minimum_filter(small,footprint=kernel,mode='nearest')
        return np.where(np.isfinite(r),r,np.nan).astype(np.float32)

    WIN=5;k=np.ones((WIN,WIN),dtype=np.float32)
    v=np.isfinite(dem).astype(np.float32);z0=np.where(v.astype(bool),dem,0).astype(np.float32)
    s=ndi.convolve(z0,k,mode='nearest');s2=ndi.convolve(z0*z0,k,mode='nearest')
    n=ndi.convolve(v,k,mode='nearest')
    var=np.where(n>1,(s2-s*s/np.maximum(n,1))/np.maximum(n-1,1),np.nan)
    rough=np.sqrt(np.clip(var,0,None)).astype(np.float32);rough[n<(WIN*WIN)]=np.nan
    write_tif(f'roughness_5{sfx}.tif',rough,T,W,H)

    rk=disk_kernel(10/RES)
    lr=(nanmax_disk(dem,rk)-nanmin_disk(dem,rk)).astype(np.float32)
    write_tif(f'local_relief_10{sfx}.tif',lr,T,W,H)

    for size in (3,5,11,25):
        valid=np.isfinite(dem).astype(np.float32);z0=np.where(valid.astype(bool),dem,0).astype(np.float32)
        sm=uniform_filter(z0,size=size,mode='nearest');sc=uniform_filter(valid,size=size,mode='nearest')
        smooth=np.where(sc>0,sm/sc,np.nan);lrm=(dem-smooth).astype(np.float32)
        write_tif(f'lrm_{size}{sfx}.tif',lrm,T,W,H)

    def tpi(z,r_m):return(z-nanmean_filter(z,disk_kernel(r_m/RES))).astype(np.float32)
    write_tif(f'tpi_05{sfx}.tif',tpi(dem,5.0),T,W,H)
    t15=tpi(dem,15.0);write_tif(f'tpi_15{sfx}.tif',t15,T,W,H)
    write_tif(f'tpi_25{sfx}.tif',tpi(dem,25.0),T,W,H)
    gy,gx=np.gradient(t15,RES)
    write_tif(f'tpi_grad_mag{sfx}.tif',np.hypot(gx,gy).astype(np.float32),T,W,H)
    write_tif(f'tpi_grad_dir{sfx}.tif',(np.degrees(np.arctan2(gx,-gy))%360).astype(np.float32),T,W,H)

    def openness(z,L_cells,cellsize):
        L=int(L_cells);dirs=[(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
        valid=np.isfinite(z);z0=np.where(valid,z,0).astype(np.float32)
        phi_sum=np.zeros_like(z,dtype=np.float32);psi_sum=np.zeros_like(z,dtype=np.float32)
        for dr,dc in dirs:
            step=cellsize*np.hypot(dr,dc)
            mtu=np.full_like(z,-np.inf,dtype=np.float32);mtd=np.full_like(z,np.inf,dtype=np.float32)
            for kk in range(1,L+1):
                zs=np.roll(z0,shift=(dr*kk,dc*kk),axis=(0,1))
                vs=np.roll(valid,shift=(dr*kk,dc*kk),axis=(0,1))
                if dr>0:vs[:dr*kk,:]=False
                elif dr<0:vs[dr*kk:,:]=False
                if dc>0:vs[:,:dc*kk]=False
                elif dc<0:vs[:,dc*kk:]=False
                ta=np.where(vs,(zs-z0)/(kk*step),np.nan).astype(np.float32)
                np.fmax(mtu,ta,out=mtu,where=vs);np.fmin(mtd,ta,out=mtd,where=vs)
            phi_sum+=(np.pi/2-np.arctan(np.where(np.isfinite(mtu),mtu,0))).astype(np.float32)
            psi_sum+=(np.pi/2+np.arctan(np.where(np.isfinite(mtd),mtd,0))).astype(np.float32)
        phi=np.degrees(phi_sum/8).astype(np.float32);psi=np.degrees(psi_sum/8).astype(np.float32)
        phi[~valid]=np.nan;psi[~valid]=np.nan;return phi,psi

    print('computing openness...',flush=True)
    op,on=openness(dem,L_cells=int(25/RES),cellsize=RES)
    write_tif(f'openness_pos{sfx}.tif',op,T,W,H)
    write_tif(f'openness_neg{sfx}.tif',on,T,W,H)
    print('9-tile derivatives done',flush=True)
else:
    print('9-tile derivatives already exist',flush=True)


# =========================================================================
# STEP 2: Load pits + rasters for both tiles
# =========================================================================
print('\n=== loading pits + rasters ===',flush=True)
pits = gpd.read_file(ANNO/'wellhead_pits.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x,g.y] for g in pits.geometry])
print(f'total pits: {len(pits)}')

CHANS_D = ['lrm_5','lrm_11','tpi_15','openness_neg']

def load_rasters(tile):
    sfx=tile['sfx']; R={}
    for ch in CHANS_D: R[ch]=read_tif(f'{ch}{sfx}.tif')
    R['dem']=read_tif(f'dem{sfx}.tif')
    R['slope']=read_tif(f'slope{sfx}.tif')
    R['chm']=read_tif(f'chm{sfx}.tif')
    R['ground_density']=read_tif(f'ground_density{sfx}.tif')
    return R

rasters = {k: load_rasters(t) for k,t in TILES.items()}


# =========================================================================
# STEP 3: Template learning from ALL 675 pits (using whichever tile they're on)
# =========================================================================
print('\n=== template learning ===',flush=True)

def rc(x,y,tile):
    return int(round((tile['Y1']-y)/RES)), int(round((x-tile['X0'])/RES))

def which_tile(x,y):
    for k,t in TILES.items():
        if t['X0']<=x<=t['X1'] and t['Y0']<=y<=t['Y1']: return k
    return None

cutouts = []
for (x,y) in pit_xy:
    tk = which_tile(x,y)
    if tk is None: continue
    t = TILES[tk]; lrm5 = rasters[tk]['lrm_5']
    r0,c0 = rc(x,y,t)
    r1,r2=max(0,r0-SNAP_R),min(t['H'],r0+SNAP_R+1)
    c1,c2=max(0,c0-SNAP_R),min(t['W'],c0+SNAP_R+1)
    win=lrm5[r1:r2,c1:c2]
    if np.isnan(win).all(): continue
    f=np.nanargmin(win);dr,dc=divmod(f,win.shape[1])
    sr,sc=r1+dr,c1+dc
    r1,r2=sr-HALF,sr+HALF+1;c1,c2=sc-HALF,sc+HALF+1
    if r1<0 or c1<0 or r2>t['H'] or c2>t['W']: continue
    w=lrm5[r1:r2,c1:c2].astype(np.float32)
    if np.isnan(w).mean()>0.2: continue
    cutouts.append(w-np.nanmean(w))

cutouts=np.stack(cutouts)
print(f'usable cutouts: {len(cutouts)}')
flat=np.nan_to_num(cutouts.reshape(len(cutouts),-1),nan=0)
Z=PCA(n_components=5,random_state=0).fit_transform(flat)
km=KMeans(n_clusters=3,n_init=10,random_state=0).fit(Z)
templates=np.stack([np.nanmedian(cutouts[km.labels_==k],axis=0) for k in range(3)])
templates=np.nan_to_num(templates,nan=0)
print(f'clusters: {np.bincount(km.labels_).tolist()}',flush=True)


# =========================================================================
# STEP 4: Candidate generation on both tiles
# =========================================================================
print('\n=== candidate generation ===',flush=True)
tree_pit = cKDTree(pit_xy)

def make_rings():
    yy,xx=np.ogrid[-HALF:HALF+1,-HALF:HALF+1];rad=np.sqrt(xx*xx+yy*yy)
    return rad<=INNER,(rad>=OUTER)&(rad<=HALF),rad
RING_IN,RING_RIM,RAD=make_rings()
RADIAL_BINS=[(0,1),(1,3),(3,5),(5,8)]

all_cands = []  # list of (tile_key, xs, ys, per_tmp, score_max)

for tk,t in TILES.items():
    lrm5=rasters[tk]['lrm_5']
    valid=~np.isnan(lrm5);img=np.where(valid,lrm5,0).astype(np.float32)
    print(f'{tk}: template matching ({lrm5.shape})...',flush=True)
    t0=time.time()
    per_tmp=[match_template(img,templates[k].astype(np.float32),pad_input=True) for k in range(3)]
    for s in per_tmp:s[~valid]=np.nan
    sm=np.nanmax(np.stack(per_tmp),axis=0)
    print(f'  done in {time.time()-t0:.1f}s',flush=True)
    peaks=peak_local_max(np.nan_to_num(sm,nan=-1),min_distance=int(round(5.0/RES)),threshold_abs=0.148)
    rows,cols=peaks[:,0],peaks[:,1]
    xs=t['X0']+(cols+0.5)*RES;ys=t['Y1']-(rows+0.5)*RES
    print(f'  candidates: {len(peaks)}',flush=True)
    all_cands.append((tk,xs,ys,per_tmp,sm))


# =========================================================================
# STEP 5: Feature extraction
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
    return out

# Extract features for ALL candidates across both tiles
feat_list,keep_idx,keep_xy,keep_tile=[],[],[],[]
global_i = 0
for tk,xs,ys,per_tmp,sm in all_cands:
    t0=time.time()
    n_before=len(feat_list)
    for i,(x,y) in enumerate(zip(xs,ys)):
        f=feats_for(x,y,tk,per_tmp,sm)
        if f is not None:
            feat_list.append(f);keep_idx.append(global_i)
            keep_xy.append((x,y));keep_tile.append(tk)
        global_i+=1
        if (i+1)%50000==0:print(f'  {tk}: {i+1}/{len(xs)} ({time.time()-t0:.0f}s)',flush=True)
    print(f'  {tk}: {len(feat_list)-n_before} valid features in {time.time()-t0:.1f}s',flush=True)

X_df = pd.DataFrame(feat_list)
keep_xy = np.array(keep_xy)
keep_tile = np.array(keep_tile)
X_arr = X_df.fillna(0).to_numpy(dtype=np.float32)

# Labels
dn,nearest = tree_pit.query(keep_xy, k=1)
y = (dn <= POS_DIST_M).astype(np.int8)
print(f'\ntotal features: {X_arr.shape}  positives: {y.sum()}',flush=True)


# =========================================================================
# STEP 6: Train ensemble
# =========================================================================
print('\n=== training XGB+LGBM ensemble ===',flush=True)
N_GROUPS = 15  # more groups for 675 pits
agg = AgglomerativeClustering(n_clusters=N_GROUPS).fit(pit_xy)
groups = agg.labels_[nearest]
scale_pos = (len(y)-y.sum())/max(y.sum(),1)

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

p_xgb=oof_fit(make_xgb)
p_lgb=oof_fit(make_lgb)
p_avg=(p_xgb+p_lgb)/2
print(f'XGB  ROC {roc_auc_score(y,p_xgb):.4f}  PR {average_precision_score(y,p_xgb):.4f}',flush=True)
print(f'LGBM ROC {roc_auc_score(y,p_lgb):.4f}  PR {average_precision_score(y,p_lgb):.4f}',flush=True)
print(f'AVG  ROC {roc_auc_score(y,p_avg):.4f}  PR {average_precision_score(y,p_avg):.4f}',flush=True)
iso=IsotonicRegression(out_of_bounds='clip').fit(p_avg,y)
p_cal=iso.predict(p_avg).astype(np.float32)


# =========================================================================
# STEP 7: Output — per-tile ranked candidates + overlays
# =========================================================================
print('\n=== output ===',flush=True)

for tk in ['9tile','mckean']:
    t=TILES[tk]
    mask = keep_tile == tk
    sub_xy = keep_xy[mask]
    sub_proba = p_cal[mask]
    sub_raw = p_avg[mask]

    gdf = gpd.GeoDataFrame({
        'proba':sub_proba, 'proba_raw':sub_raw,
        'geometry':[Point(x,y) for x,y in sub_xy]
    },crs=CRS).sort_values('proba',ascending=False).reset_index(drop=True)

    fname = f'pit_candidates_675_{tk}.gpkg'
    gdf.to_file(DERIV/fname,driver='GPKG')

    print(f'\n{tk}: wrote {fname} ({len(gdf)} rows)')
    print(f'{"thr":>5} {"n":>6} {"hits":>6} {"pits":>6} {"prec":>7}')

    # pits in this tile
    tile_pits = pit_xy[
        (pit_xy[:,0]>=t['X0'])&(pit_xy[:,0]<=t['X1'])&
        (pit_xy[:,1]>=t['Y0'])&(pit_xy[:,1]<=t['Y1'])
    ]
    tree_tile = cKDTree(tile_pits) if len(tile_pits)>0 else None

    with open(DERIV/f'pit_675_{tk}_metrics.txt','w') as f:
        f.write(f'675-pit retrain: {tk}\n')
        f.write(f'pits in tile: {len(tile_pits)}\n\n')
        for thr in [0.30,0.50,0.70,0.80,0.90]:
            sub=gdf[gdf['proba']>=thr]
            if len(sub)==0:
                print(f'{thr:5.2f} {0:6d} {0:6d} {0:6d} {"n/a":>7}')
                continue
            sxy=np.c_[sub.geometry.x,sub.geometry.y]
            if tree_tile is not None:
                dn2,_=tree_tile.query(sxy,k=1)
                hit=int((dn2<=10).sum())
                _,idx=tree_tile.query(sxy[dn2<=10],k=1) if hit else (None,np.array([]))
                pcov=len(np.unique(idx)) if hit else 0
                prec=hit/len(sub)
            else:
                hit=0;pcov=0;prec=0
            line=f'{thr:5.2f} {len(sub):6d} {hit:6d} {pcov:6d} {prec:7.2%}'
            print(line);f.write(line+'\n')

    # Overview PNG
    hs = read_tif(f'hillshade{t["sfx"]}.tif')
    fig,ax=plt.subplots(figsize=(14,14))
    ax.imshow(hs,cmap='gray',extent=[t['X0'],t['X1'],t['Y0'],t['Y1']])
    if len(tile_pits):
        ax.scatter(tile_pits[:,0],tile_pits[:,1],s=30,c='red',marker='o',linewidths=0,
                   label=f'annotated pits ({len(tile_pits)})')
    top=gdf[gdf['proba']>=0.50]
    if len(top):
        sxy=np.c_[top.geometry.x,top.geometry.y]
        if tree_tile is not None:
            dn2,_=tree_tile.query(sxy,k=1)
            tp=sxy[dn2<=10]
        else:
            tp=np.empty((0,2))
        if len(tp):
            ax.scatter(tp[:,0],tp[:,1],s=70,c='lime',marker='X',linewidths=0,
                       label=f'found (n={len(tp)})')
    ax.set_title(f'675-pit retrain: {tk}  (proba>=0.50)',fontsize=12)
    ax.legend(loc='lower left',fontsize=9)
    ax.set_xlim(t['X0'],t['X1']);ax.set_ylim(t['Y0'],t['Y1'])
    fig.savefig(DERIV/f'pit_675_{tk}_overview.png',dpi=130,bbox_inches='tight')
    plt.close(fig)
    print(f'wrote pit_675_{tk}_overview.png')

print('\nDONE.',flush=True)
