"""Build McKean 5x5 grid (23 tiles) at 1m.

Grid: e1423-1427 x n2235-2239 (23 of 25 available)
UTM: ~697000-703500, 4645000-4651500 (~6km x 6km)
Suffix: _mk5_1m
"""
import json, subprocess, shutil, time
import numpy as np, laspy, rasterio, pyproj
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from scipy import ndimage as ndi
from scipy.ndimage import uniform_filter
from pathlib import Path
import matplotlib.pyplot as plt

DATA=Path('data/files');DERIV=Path('data/derivatives');MDIR=DATA/'mcKean'
PDAL=shutil.which('pdal') or 'pdal'
CRS='EPSG:6346';RES=1.0;SFX='_mk5_1m'

# Snap UTM grid to round numbers
X0,Y0,X1,Y1 = 697000.0,4645000.0,703500.0,4651500.0
W=int((X1-X0)/RES);H=int((Y1-Y0)/RES)
T=from_origin(X0,Y1,RES,RES)
LAS_OUT=DATA/'mckean_5x5.las'

# Collect available tiles
tiles=[]
for e in range(1423,1428):
    for n in range(2235,2240):
        f=MDIR/f'USGS_LPC_PA_Northcentral_2019_B19_e{e}n{n}.laz'
        if f.exists():tiles.append(f)
print(f'grid: {W}x{H} @ {RES}m  tiles: {len(tiles)}',flush=True)


def run_pipeline(pl,label,timeout=7200):
    tmp=DERIV/f'_tmp_{label}.json'
    with open(tmp,'w') as f:json.dump(pl,f,indent=2)
    t0=time.time()
    r=subprocess.run([PDAL,'pipeline',str(tmp)],capture_output=True,text=True,timeout=timeout)
    print(f'[{label}] rc={r.returncode} in {time.time()-t0:.1f}s',flush=True)
    if r.returncode!=0:print(r.stderr[-2000:]);raise RuntimeError(label)
    tmp.unlink(missing_ok=True)

def write_tif(name,arr,dtype='float32',nd=-9999.0):
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

# Merge
if not LAS_OUT.exists():
    print('merging + reprojecting...',flush=True)
    stages=[{'type':'readers.las','filename':str(p)} for p in tiles]
    stages.extend([
        {'type':'filters.reprojection','out_srs':CRS},
        {'type':'filters.crop','bounds':f'([{X0},{X1}],[{Y0},{Y1}])'},
        {'type':'writers.las','filename':str(LAS_OUT),'a_srs':CRS,
         'minor_version':4,'dataformat_id':7,'forward':'all','compression':'false'},
    ])
    run_pipeline({'pipeline':stages},'merge_mk5',timeout=7200)
    print(f'merged: {LAS_OUT.stat().st_size/1e9:.2f} GB',flush=True)

# DEM
print('DEM...',flush=True)
run_pipeline({'pipeline':[
    {'type':'readers.las','filename':str(LAS_OUT)},
    {'type':'filters.range','limits':'Classification[2:2]'},
    {'type':'filters.delaunay'},
    {'type':'filters.faceraster','resolution':RES,'origin_x':X0,'origin_y':Y0,'width':W,'height':H},
    {'type':'writers.raster','filename':str(DERIV/f'dem{SFX}.tif'),'data_type':'float32'},
]},f'dem{SFX}',timeout=7200)
dem=read_tif(f'dem{SFX}.tif')
print(f'DEM: nan={100*np.isnan(dem).mean():.1f}%  z={np.nanmin(dem):.1f}..{np.nanmax(dem):.1f}',flush=True)

# DSM+CHM
run_pipeline({'pipeline':[
    {'type':'readers.las','filename':str(LAS_OUT)},
    {'type':'filters.range','limits':'ReturnNumber[1:1]'},
    {'type':'writers.gdal','filename':str(DERIV/f'dsm{SFX}.tif'),'output_type':'max','resolution':RES,
     'origin_x':X0,'origin_y':Y0,'width':W,'height':H,'data_type':'float32'},
]},f'dsm{SFX}',timeout=7200)
dsm=read_tif(f'dsm{SFX}.tif')
chm=np.where(np.isnan(dsm)|np.isnan(dem),np.nan,np.maximum(dsm-dem,0)).astype(np.float32)
write_tif(f'chm{SFX}.tif',chm)

# Density
print('density...',flush=True)
las=laspy.read(str(LAS_OUT))
xs=np.asarray(las.x);ys=np.asarray(las.y);cls=np.asarray(las.classification)
gm=(cls==2)
col=np.floor((xs[gm]-X0)/RES).astype(np.int64)
row=np.floor((Y1-ys[gm])/RES).astype(np.int64)
ok=(col>=0)&(col<W)&(row>=0)&(row<H)
fi=(row[ok]*W+col[ok])
dens=np.bincount(fi,minlength=H*W).reshape(H,W).astype(np.uint16)
write_tif(f'ground_density{SFX}.tif',dens,dtype='uint16',nd=0)
del las

# WBT
import whitebox
wbt=whitebox.WhiteboxTools();wbt.set_working_dir(str(DERIV.resolve()));wbt.set_verbose_mode(False)
wbt.hillshade(dem=f'dem{SFX}.tif',output=f'hillshade{SFX}.tif',azimuth=315.0,altitude=45.0)
wbt.slope(dem=f'dem{SFX}.tif',output=f'slope{SFX}.tif',units='degrees')

# Python derivatives
def disk_kernel(r_cells):
    r=int(round(r_cells));y,x=np.ogrid[-r:r+1,-r:r+1];return(x*x+y*y)<=r*r
def nanmean_filter(a,kernel):
    valid=np.isfinite(a).astype(np.float32);a0=np.where(valid.astype(bool),a,0).astype(np.float32)
    kf=kernel.astype(np.float32);s=ndi.convolve(a0,kf,mode='nearest');c=ndi.convolve(valid,kf,mode='nearest')
    out=np.full_like(a,np.nan,dtype=np.float32);np.divide(s,c,out=out,where=c>0);return out
def nanmax_disk(a,k):
    big=np.where(np.isfinite(a),a,-np.inf);r=ndi.maximum_filter(big,footprint=k,mode='nearest')
    return np.where(np.isfinite(r),r,np.nan).astype(np.float32)
def nanmin_disk(a,k):
    small=np.where(np.isfinite(a),a,np.inf);r=ndi.minimum_filter(small,footprint=k,mode='nearest')
    return np.where(np.isfinite(r),r,np.nan).astype(np.float32)

WIN=5;k=np.ones((WIN,WIN),dtype=np.float32)
v=np.isfinite(dem).astype(np.float32);z0=np.where(v.astype(bool),dem,0).astype(np.float32)
s=ndi.convolve(z0,k,mode='nearest');s2=ndi.convolve(z0*z0,k,mode='nearest')
n=ndi.convolve(v,k,mode='nearest')
var=np.where(n>1,(s2-s*s/np.maximum(n,1))/np.maximum(n-1,1),np.nan)
rough=np.sqrt(np.clip(var,0,None)).astype(np.float32);rough[n<(WIN*WIN)]=np.nan
write_tif(f'roughness_5{SFX}.tif',rough)
rk=disk_kernel(10/RES)
lr=(nanmax_disk(dem,rk)-nanmin_disk(dem,rk)).astype(np.float32)
write_tif(f'local_relief_10{SFX}.tif',lr)

for size in(3,5,11,25):
    valid=np.isfinite(dem).astype(np.float32);z0=np.where(valid.astype(bool),dem,0).astype(np.float32)
    sm=uniform_filter(z0,size=size,mode='nearest');sc=uniform_filter(valid,size=size,mode='nearest')
    smooth=np.where(sc>0,sm/sc,np.nan);lrm=(dem-smooth).astype(np.float32)
    write_tif(f'lrm_{size}{SFX}.tif',lrm)

def tpi(z,r_m):return(z-nanmean_filter(z,disk_kernel(r_m/RES))).astype(np.float32)
write_tif(f'tpi_05{SFX}.tif',tpi(dem,5.0))
t15=tpi(dem,15.0);write_tif(f'tpi_15{SFX}.tif',t15)
write_tif(f'tpi_25{SFX}.tif',tpi(dem,25.0))
gy,gx=np.gradient(t15,RES)
write_tif(f'tpi_grad_mag{SFX}.tif',np.hypot(gx,gy).astype(np.float32))
write_tif(f'tpi_grad_dir{SFX}.tif',(np.degrees(np.arctan2(gx,-gy))%360).astype(np.float32))

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
write_tif(f'openness_pos{SFX}.tif',op);write_tif(f'openness_neg{SFX}.tif',on)

# Land cover clip
print('clipping land cover...',flush=True)
lc_src='landcover_2013_pennsylvania_chb_drb/landcover_2013_pennsylvania_chb_drb.img'
with rasterio.open(lc_src) as ds:
    tr=pyproj.Transformer.from_crs(CRS,ds.crs,always_xy=True)
    corners=[(X0,Y0),(X0,Y1),(X1,Y0),(X1,Y1)]
    sxs=[tr.transform(x,y)[0] for x,y in corners]
    sys_=[tr.transform(x,y)[1] for x,y in corners]
    win=from_bounds(min(sxs)-500,min(sys_)-500,max(sxs)+500,max(sys_)+500,ds.transform)
    a=ds.read(1,window=win);wt=ds.window_transform(win);lc_crs=ds.crs
with rasterio.open(DERIV/'landcover_mckean5_1m.tif','w',driver='GTiff',
                   height=a.shape[0],width=a.shape[1],count=1,dtype='uint8',
                   crs=lc_crs,transform=wt,nodata=0,compress='deflate') as ds:
    ds.write(a,1)
print(f'wrote landcover_mckean5_1m.tif',flush=True)

# Overview
panels=[
    (f'hillshade{SFX}.tif','hillshade','gray',(None,None)),
    (f'dem{SFX}.tif','DEM','terrain',(None,None)),
    (f'slope{SFX}.tif','slope','magma',(0,30)),
    (f'lrm_5{SFX}.tif','LRM 5','RdBu_r',(-0.6,0.6)),
    (f'tpi_15{SFX}.tif','TPI 15','RdBu_r',(-0.5,0.5)),
    (f'openness_neg{SFX}.tif','openness neg','viridis',(None,None)),
]
fig,axes=plt.subplots(2,3,figsize=(18,12))
for ax,(fname,title,cmap,lim) in zip(axes.ravel(),panels):
    a=read_tif(fname)
    kw=dict(cmap=cmap,extent=[X0,X1,Y0,Y1])
    if lim[0] is not None:kw.update(vmin=lim[0],vmax=lim[1])
    im=ax.imshow(a,**kw);ax.set_title(title);ax.set_xticks([]);ax.set_yticks([])
    plt.colorbar(im,ax=ax,fraction=0.046,pad=0.04)
fig.suptitle(f'McKean 5x5 (23 tiles) - 1m',fontsize=14)
fig.tight_layout(rect=[0,0,1,0.97])
fig.savefig(DERIV/f'tile_overview{SFX}.png',dpi=120,bbox_inches='tight')
plt.close(fig)
print(f'wrote tile_overview{SFX}.png\n\nDONE.',flush=True)
