from pathlib import Path
import sys, json, importlib
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'expansions/3_geography/3_0_transfer_protocol/src'))
import _transfer_score_lib as tl
res={}
def tif(name,a,tf,nd):
    p=OUT/name
    with rasterio.open(p,'w',driver='GTiff',height=a.shape[0],width=a.shape[1],count=1,dtype=a.dtype,
                       crs='EPSG:6346',transform=tf,nodata=nd) as d: d.write(a,1)
    return p
tf=from_origin(0,100,1,1)
p=tif('dn254.tif',np.array([[0,127,254,255]],np.uint8),tf,255)
a,_,_=tl.read_prob(p)
res['dn254']={'values':a.tolist(),'zero_preserved':bool(a[0,0]==0),'nodata_nan':bool(np.isnan(a[0,3]))}
p=tif('float_nodata.tif',np.array([[0,np.nan,-1,1]],np.float32),tf,-1)
a,_,_=tl.read_prob(p)
res['float_zero_nan_nodata']={'values':a.tolist(),'zero_preserved':bool(a[0,0]==0)}
blocks=gpd.GeoDataFrame({'block_id':[1]},geometry=[box(0,0,100,100)],crs='EPSG:6346')
blocks.to_file(OUT/'alignment_blocks.gpkg',layer='blocks')
truth=gpd.GeoDataFrame({'truth_id':[1]},geometry=[box(10,80,20,90)],crs=blocks.crs)
truth.to_file(OUT/'alignment_truth.gpkg',layer='truth')
void=tif('shifted_void.tif',np.zeros((100,100),np.float32),from_origin(.5,100.5,1,1),-1)
r=tl.score(OUT/'prob.tif',OUT/'alignment_blocks.gpkg',str(OUT/'alignment_truth.gpkg'),
           void_path=void,void_cap=.1,cutoff=.35,B=10,calib_pixels=100)
res['half_pixel_void_grid']={'accepted':True,'n_eligible':r['summary']['n_blocks_eligible']}
bp=ROOT/'expansions/0_prerequisites/p1_splits_manifests/data/interim/dryrun/buffer_derivation_9t.json'
b=json.loads(bp.read_text())
res['actual_buffer_to_31']={'producer_buffer_m':b['buffer_m'],'consumer_key_present':'pit_buffer_m' in b}
sys.path.insert(0,str(ROOT/'expansions/0_prerequisites/p2_audit_set/src'))
import _audit_draw_blocks_9t as ad
tab=pd.DataFrame({'block_id':[7],'dens_t':[0],'slope_t':[0]})
aud=OUT/'actual_producer_audit.csv'
ad.write_audit_csv(aud,tab,{'audit':[7],'buffer':[],'share':.2},'block',100.,0)
sys.path.insert(0,str(ROOT/'expansions/7_scale/7_3_benchmark/src'))
import _bench_export_release_9t as ex
try:
    ex.roles_from_future(ROOT/'expansions/0_prerequisites/p1_splits_manifests/data/interim/dryrun/cv_splits_future_9t_v1.json',aud,4)
except Exception as e: res['actual_p2_to_73']={'exception':type(e).__name__,'message':str(e)}
# Demonstrate the role mismatch independently after removing CSV comment/schema blockers.
adapt=OUT/'consumer_shaped_split.json'; adapt.write_text(json.dumps({'folds':[]}))
au=OUT/'audit_no_comments.csv'; au.write_text('block_id,role\n7,audit\n')
res['audit_role_mapping']=ex.roles_from_future(adapt,au,4)[0]
sys.path.insert(0,str(ROOT/'expansions/5_tasks/5_6_record_association/src'))
import _records_assoc_core as ac
df=pd.DataFrame({'source':['matched','undecided'],'dup_on_pit':[1,1],'det_id':[0,1]})
res['truth_dependent_dedupe']={'with_annotation':ac.dedupe(df).det_id.tolist(),
 'without_annotation':ac.dedupe(df.assign(dup_on_pit=0)).det_id.tolist()}
(OUT/'contracts.json').write_text(json.dumps(res,indent=2,default=str),encoding='utf8')
print(json.dumps(res,indent=2,default=str))
