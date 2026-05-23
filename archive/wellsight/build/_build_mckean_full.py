"""Build full McKean 48-tile mosaic at 1m + retrain with land cover.

48 tiles, ~9km x 9km, ~480M points.
UTM grid: 696000-706000 E, 4645000-4655000 N (10km x 10km, 10000x10000 cells)
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

DATA=Path('data/files');DERIV=Path('data/derivatives');ANNO=Path('data/derivatives/annotations')
MDIR=DATA/'mcKean';PDAL=shutil.which('pdal') or 'pdal'
CRS='EPSG:6346';RES=1.0
HALF,INNER,OUTER=8,3,6;SNAP_R=3;POS_DIST_M=10.0

# Full McKean grid
MK_LAS=DATA/'mckean_full.las'
X0mk,Y0mk,X1mk,Y1mk = 696000.0,4645000.0,706000.0,4655000.0
Wmk=int((X1mk-X0mk)/RES);Hmk=int((Y1mk-Y0mk)/RES)
Tmk=from_origin(X0mk,Y1mk,RES,RES)
SFX_MK='_mkf_1m'

# 9-tile (already built)
X0v,Y0v,X1v,Y1v = 619500.0,4593000.0,624000.0,4597500.0
Wv=int((X1v-X0v)/RES);Hv=int((Y1v-Y0v)/RES)
SFX_V='_9t_1m'

print(f'McKean full grid: {Wmk}x{Hmk} @ {RES}m',flush=True)

PA_TILES=sorted(MDIR.glob('*Northcentral*.laz'))
print(f'source tiles: {len(PA_TILES)}',flush=True)


def run_pipeline(pl,label,timeout=7200):
    tmp=DERIV/f'_tmp_{label}.json'
    with open(tmp,'w') as f:json.dump(pl,f,indent=2)
    t0=time.time()
    r=subprocess.run([PDAL,'pipeline',str(tmp)],capture_output=True,text=True,timeout=timeout)
    print(f'[{label}] rc={r.returncode} in {time.time()-t0:.1f}s',flush=True)
    if r.returncode!=0:print(r.stderr[-2000:]);raise RuntimeError(label)
    tmp.unlink(missing_ok=True)

def write_tif(name,arr,T,W,H,dtype='float32',nd=-9999.0):
    a=arr.astype(dtype)
    if dtype.startswith('float'):a=np.where(np.isnan(a),nd,a).astype(dtype)
    with rasterio.open(DERIV/name,'w',driver='GTiff',height=H,width=W,count=1,
                       dtype=dtype,crs=CRS,transform=T,nodata=nd,
                       tiled=True,compress='deflate',
                       predictor=(3 if dtype.startswith('float') else 2)) as ds:
        ds.write(a,1)
    print('wrote',name,flush=True)

def read_tif(name):
    with rasterio.open(DERIV/name) as ds:
        a=ds.read(1).astype(np.float32);nd=ds.nodata
    if nd is not None:a=np.where(a==nd,np.nan,a)
    return a


# =========================================================================
# STAGE 1: Merge + derivatives for full McKean
# =========================================================================
if not(DERIV/f'dem{SFX_MK}.tif').exists():
    print('\n=== STAGE 1: full McKean derivatives ===',flush=True)

    if not MK_LAS.exists():
        print('merging 48 tiles + reprojecting...',flush=True)
        stages=[{'type':'readers.las','filename':str(p)} for p in PA_TILES]
        stages.extend([
            {'type':'filters.reprojection','out_srs':CRS},
            {'type':'filters.crop','bounds':f'([{X0mk},{X1mk}],[{Y0mk},{Y1mk}])'},
            {'type':'writers.las','filename':str(MK_LAS),'a_srs':CRS,
             'minor_version':4,'dataformat_id':7,'forward':'all','compression':'false'},
        ])
        run_pipeline({'pipeline':stages},'merge_mkf',timeout=7200)
        print(f'merged: {MK_LAS.stat().st_size/1e9:.2f} GB',flush=True)

    # DEM
    run_pipeline({'pipeline':[
        {'type':'readers.las','filename':str(MK_LAS)},
        {'type':'filters.range','limits':'Classification[2:2]'},
        {'type':'filters.delaunay'},
        {'type':'filters.faceraster','resolution':RES,'origin_x':X0mk,'origin_y':Y0mk,
         'width':Wmk,'height':Hmk},
        {'type':'writers.raster','filename':str(DERIV/f'dem{SFX_MK}.tif'),'data_type':'float32'},
    ]},f'dem{SFX_MK}',timeout=7200)
    dem=read_tif(f'dem{SFX_MK}.tif')
    print(f'DEM: nan={100*np.isnan(dem).mean():.1f}%  z={np.nanmin(dem):.1f}..{np.nanmax(dem):.1f}',flush=True)

    # DSM+CHM
    run_pipeline({'pipeline':[
        {'type':'readers.las','filename':str(MK_LAS)},
        {'type':'filters.range','limits':'ReturnNumber[1:1]'},
        {'type':'writers.gdal','filename':str(DERIV/f'dsm{SFX_MK}.tif'),
         'output_type':'max','resolution':RES,'origin_x':X0mk,'origin_y':Y0mk,
         'width':Wmk,'height':Hmk,'data_type':'float32'},
    ]},f'dsm{SFX_MK}',timeout=7200)
    dsm=read_tif(f'dsm{SFX_MK}.tif')
    chm=np.where(np.isnan(dsm)|np.isnan(dem),np.nan,np.maximum(dsm-dem,0)).astype(np.float32)
    write_tif(f'chm{SFX_MK}.tif',chm,Tmk,Wmk,Hmk)

    # Density
    print('density...',flush=True)
    las=laspy.read(str(MK_LAS))
    xs=np.asarray(las.x);ys=np.asarray(las.y);cls=np.asarray(las.classification)
    gm=(cls==2)
    col=np.floor((xs[gm]-X0mk)/RES).astype(np.int64)
    row=np.floor((Y1mk-ys[gm])/RES).astype(np.int64)
    ok=(col>=0)&(col<Wmk)&(row>=0)&(row<Hmk)
    fi=(row[ok]*Wmk+col[ok])
    dens=np.bincount(fi,minlength=Hmk*Wmk).reshape(Hmk,Wmk).astype(np.uint16)
    write_tif(f'ground_density{SFX_MK}.tif',dens,Tmk,Wmk,Hmk,dtype='uint16',nd=0)
    del las

    # WBT
    import whitebox
    wbt=whitebox.WhiteboxTools();wbt.set_working_dir(str(DERIV.resolve()));wbt.set_verbose_mode(False)
    wbt.hillshade(dem=f'dem{SFX_MK}.tif',output=f'hillshade{SFX_MK}.tif',azimuth=315.0,altitude=45.0)
    wbt.slope(dem=f'dem{SFX_MK}.tif',output=f'slope{SFX_MK}.tif',units='degrees')
    print('wrote hillshade+slope',flush=True)

    # Python derivatives
    def disk_kernel(r_cells):
        r=int(round(r_cells));y,x=np.ogrid[-r:r+1,-r:r+1];return(x*x+y*y)<=r*r
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
    write_tif(f'roughness_5{SFX_MK}.tif',rough,Tmk,Wmk,Hmk)
    rk=disk_kernel(10/RES)
    lr=(nanmax_disk(dem,rk)-nanmin_disk(dem,rk)).astype(np.float32)
    write_tif(f'local_relief_10{SFX_MK}.tif',lr,Tmk,Wmk,Hmk)

    for size in(3,5,11,25):
        valid=np.isfinite(dem).astype(np.float32);z0=np.where(valid.astype(bool),dem,0).astype(np.float32)
        sm=uniform_filter(z0,size=size,mode='nearest');sc=uniform_filter(valid,size=size,mode='nearest')
        smooth=np.where(sc>0,sm/sc,np.nan);lrm=(dem-smooth).astype(np.float32)
        write_tif(f'lrm_{size}{SFX_MK}.tif',lrm,Tmk,Wmk,Hmk)

    def tpi(z,r_m):return(z-nanmean_filter(z,disk_kernel(r_m/RES))).astype(np.float32)
    write_tif(f'tpi_05{SFX_MK}.tif',tpi(dem,5.0),Tmk,Wmk,Hmk)
    t15=tpi(dem,15.0);write_tif(f'tpi_15{SFX_MK}.tif',t15,Tmk,Wmk,Hmk)
    write_tif(f'tpi_25{SFX_MK}.tif',tpi(dem,25.0),Tmk,Wmk,Hmk)
    gy,gx=np.gradient(t15,RES)
    write_tif(f'tpi_grad_mag{SFX_MK}.tif',np.hypot(gx,gy).astype(np.float32),Tmk,Wmk,Hmk)
    write_tif(f'tpi_grad_dir{SFX_MK}.tif',(np.degrees(np.arctan2(gx,-gy))%360).astype(np.float32),Tmk,Wmk,Hmk)

    def openness(z,L_cells,cellsize):
        L=int(L_cells);dirs=[(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
        valid=np.isfinite(z);z0=np.where(valid,z,0).astype(np.float32)
        phi=np.zeros_like(z,dtype=np.float32);psi=np.zeros_like(z,dtype=np.float32)
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
            phi+=(np.pi/2-np.arctan(np.where(np.isfinite(mtu),mtu,0))).astype(np.float32)
            psi+=(np.pi/2+np.arctan(np.where(np.isfinite(mtd),mtd,0))).astype(np.float32)
        phi=np.degrees(phi/8).astype(np.float32);psi=np.degrees(psi/8).astype(np.float32)
        phi[~valid]=np.nan;psi[~valid]=np.nan;return phi,psi
    print('openness...',flush=True)
    op,on=openness(dem,L_cells=int(25/RES),cellsize=RES)
    write_tif(f'openness_pos{SFX_MK}.tif',op,Tmk,Wmk,Hmk)
    write_tif(f'openness_neg{SFX_MK}.tif',on,Tmk,Wmk,Hmk)
    print('full McKean derivatives DONE',flush=True)
else:
    print('full McKean derivatives already exist',flush=True)

# Also clip the 2013 land cover to the expanded extent
lc_path=DERIV/'landcover_mckean_full_1m.tif'
if not lc_path.exists():
    print('clipping land cover for expanded McKean...',flush=True)
    lc_src='landcover_2013_pennsylvania_chb_drb/landcover_2013_pennsylvania_chb_drb.img'
    with rasterio.open(lc_src) as ds:
        t=pyproj.Transformer.from_crs(CRS,ds.crs,always_xy=True)
        corners=[(X0mk,Y0mk),(X0mk,Y1mk),(X1mk,Y0mk),(X1mk,Y1mk)]
        sxs=[t.transform(x,y)[0] for x,y in corners]
        sys_=[t.transform(x,y)[1] for x,y in corners]
        from rasterio.windows import from_bounds
        win=from_bounds(min(sxs)-500,min(sys_)-500,max(sxs)+500,max(sys_)+500,ds.transform)
        a=ds.read(1,window=win);wt=ds.window_transform(win);lc_crs=ds.crs
    with rasterio.open(lc_path,'w',driver='GTiff',height=a.shape[0],width=a.shape[1],
                       count=1,dtype='uint8',crs=lc_crs,transform=wt,nodata=0,compress='deflate') as ds:
        ds.write(a,1)
    print(f'wrote landcover_mckean_full_1m.tif ({a.shape})',flush=True)

print('\nSTAGE 1 complete. Run retrain separately if needed.',flush=True)
