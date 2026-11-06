"""Read-only production-code probes; all generated inputs stay beside this file."""
from pathlib import Path
import sys, json, importlib, platform, traceback
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
def module(folder, name):
    sys.path.insert(0, str(ROOT / 'expansions' / folder / 'src'))
    return importlib.import_module(name)
ek = module('_shared', 'expkit')
tc = module('3_geography/3_4_gulf_texas', '_geo_transfer_core')
tl = module('3_geography/3_0_transfer_protocol', '_transfer_score_lib')
results = {}
def probe(name, fn):
    try: results[name] = fn()
    except Exception as e: results[name] = {'exception':type(e).__name__, 'message':str(e)}
    print(name, results[name], flush=True)
def raster(name, a, tf=None, crs='EPSG:6346', nodata=None):
    p = OUT / name
    with rasterio.open(p, 'w', driver='GTiff', height=a.shape[-2], width=a.shape[-1], count=1,
                       dtype=a.dtype, crs=crs, transform=tf or from_origin(0,100,1,1), nodata=nodata) as d:
        d.write(a,1)
    return p
blocks = gpd.GeoDataFrame({'block_id':[1], 'area_km2':[.01], 'eligible':[True]}, geometry=[box(0,0,100,100)],crs='EPSG:6346')
def truth(tid): return gpd.GeoDataFrame({'truth_id':[tid]}, geometry=[box(10,80,20,90)],crs=blocks.crs)
a=np.zeros((100,100),np.float32); a[10:20,10:20]=.9
p=raster('prob.tif',a)
def id_zero():
    return {str(i):tc.pooled_recall_at_k(tc.score_raster(p,truth(i),blocks)[0],[1],100) for i in (0,1)}
probe('truth_zero',id_zero)
def cutoff():
    b=np.zeros_like(a); b[10:20,10:20]=.2
    path=raster('prob_low.tif',b)
    return {'regional_default_candidates':len(tc.score_raster(path,truth(1),blocks)[1]),
            'declared_pit_candidates':len(tc.score_raster(path,truth(1),blocks,thr=.35)[1])}
probe('cutoff',cutoff)
def mismatch_match():
    # One ten-pixel truth, two candidates: high score overlaps 4, low score 6.
    c=np.array([[1]*4+[2]*6],np.int32); t=np.ones_like(c)
    return {'regional_iou_match':tc.greedy_iou_match(c,t),'expected_score_order_match':{1:1}}
probe('matching_order',mismatch_match)
def footprint():
    b=np.full_like(a,np.nan); b[10:20,10:20]=.9
    tables,_=tc.score_raster(raster('mostly_nodata.tif',b,nodata=np.nan),truth(1),blocks)
    return {'budget_area_km2':tables[1]['km2'],'valid_area_km2':float(np.isfinite(b).sum()/1e6)}
probe('nodata_footprint',footprint)
probe('invalid_gate',lambda:{'nan_hi':ek.decide(.1,float('nan'),.05),'reversed':ek.decide(.2,-.2,.05)})
def guard():
    tr=module('0_prerequisites/p1_splits_manifests','_pit_unet_iso_train_9t')
    return {'configured_path':str(tr.P2_SRC),'exists':tr.P2_SRC.exists(),
            'call':tr.guard_lists(OUT/'unused.csv',{'train':[],'inner_val':[]})}
probe('trainer_audit_import',guard)
def benchmark():
    m=module('7_scale/7_3_benchmark','_bench_export_release_9t')
    source=ROOT/'expansions/0_prerequisites/p1_splits_manifests/data/interim/dryrun/cv_splits_future_9t_v1.json'
    audit=OUT/'audit.csv'; audit.write_text('block_id,role\n1,audit\n')
    return m.roles_from_future(source,audit,4)
probe('actual_p1_to_benchmark',benchmark)
def frozen_audit_format():
    m=module('7_scale/7_3_benchmark','_bench_export_release_9t')
    audit=OUT/'audit_comments.csv'; audit.write_text('# frozen audit\n# buffer_m=100\nblock_id,role\n1,audit\n')
    source=ROOT/'expansions/0_prerequisites/p1_splits_manifests/data/interim/dryrun/cv_splits_future_9t_v1.json'
    return m.roles_from_future(source,audit,4)
probe('p2_format_to_benchmark',frozen_audit_format)
def los():
    m=module('6_adjacent/6_6_sar_viewshed','_sar_viewshed_tool')
    dem=np.zeros((21,21),np.float32); dem[:,9:12]=np.nan
    g=m.Grid(dem,None,None,None,from_origin(0,21,1,1),'EPSG:6346',1.)
    return m.los_profile(g,(3.5,10.5),(17.5,10.5))
probe('nodata_line_of_sight',los)
def one_cluster():
    m=module('7_scale/7_5_field_campaign','_field_analysis_bounds')
    df=pd.DataFrame({'pi':[1.]*100,'identity':['confirmed_well']*100,'outcome':['confirmed']*100,'cluster_id':['one_lease']*100})
    return m.summarise(df,{},100,0,.1)
probe('one_cluster_precision',one_cluster)
def norm_nodata():
    m=module('7_scale/7_1_pretraining','_ssl_corpus_chips_us')
    path=raster('norm_nodata.tif',np.array([[1.,1.],[1.,-9999.]],np.float32),nodata=-9999.)
    idx=pd.DataFrame({'stack_path':[str(path)],'row':[0],'col':[0],'size':[2]})
    mu,sd=m.norm_stats(idx,1,0,1)
    return {'actual_mean':mu.tolist(),'expected_mean':[1.]}
probe('ssl_nodata_norm',norm_nodata)
def ssl_crs():
    from pyproj import Transformer
    from shapely.ops import transform
    m=module('7_scale/7_1_pretraining','_ssl_corpus_chips_us')
    tf=from_origin(-8900000,5000000,1,1)
    path=raster('ssl_other_crs.tif',np.ones((10,10),np.float32),tf,'EPSG:3857')
    fp=box(-8900000,4999990,-8899990,5000000)
    exc=transform(Transformer.from_crs(3857,6346,always_xy=True).transform,fp)
    cfg={'corpus':{'chip_px':10,'stride_px':10,'max_nodata_frac':.2},'channels':['x']}
    rows,drops=m.chips_for_window(path,'reserved_ground',3,cfg,exc)
    return {'same_physical_footprint_admitted':len(rows),'drops':drops}
probe('ssl_exclusion_crs',ssl_crs)
def future_ssl():
    m=module('7_scale/7_1_pretraining','_ssl_label_subsets_9t')
    return m.folds_future(ROOT/'expansions/0_prerequisites/p1_splits_manifests/data/interim/dryrun/cv_splits_future_9t_v1.json')
probe('actual_p1_to_ssl',future_ssl)
def ties():
    c=pd.DataFrame({'blob_id':[2,10],'score':[.5,.5],'area_m2':[4.,4.],'truth_id':[1,None]})
    tab={1:{'c':c,'n_truth':1,'km2':.025}}
    return {'numeric_reference':ek.recall_at_k(c.score,c.truth_id,[1,1],{1:1},.025,40,areas=c.area_m2,cand_ids=c.blob_id)['recall'],
            'regional_replay':tc.pooled_recall_at_k(tab,[1],40)}
probe('reference_tie_id_conversion',ties)
def seam():
    m=module('3_geography/3_1_warren_forest_mckean','_xfer_score_k40_wfm')
    aa=np.zeros((100,200),np.float32); aa[40:60,50:150]=.9
    path=raster('seam.tif',aa)
    bs=gpd.GeoDataFrame({'block_id':[1,2]},geometry=[box(0,0,100,100),box(100,0,200,100)],crs=blocks.crs)
    cs=m.candidates_in_blocks(path,bs,.35,4)
    return {'whole_raster_candidates':len(tl.candidates(aa,from_origin(0,100,1,1),blocks.crs,.35,4)),
            'per_block_candidates':len(cs),'areas':cs.area.tolist(),'bounds':[g.bounds for g in cs.geometry]}
probe('block_seam_duplicate',seam)
def geographic():
    path=raster('geographic.tif',a,crs='EPSG:4326')
    bs=blocks.set_crs('EPSG:4326',allow_override=True)
    ts=truth(1).set_crs('EPSG:4326',allow_override=True)
    tabs,cs=tc.score_raster(path,ts,bs)
    return {'accepted_geographic':True,'reported_blob_m2':cs.area_m2.tolist()}
probe('geographic_area_units',geographic)
def timing():
    import time
    source=ROOT/'expansions/3_geography/3_0_transfer_protocol/results/tables/xfer_ref_block_tables_9t.json'
    j=json.loads(source.read_text()); tabs={b:{'c':pd.DataFrame(v['cands']),'n_truth':v['n_truth'],'km2':v['km2']} for b,v in j.items()}
    t=time.perf_counter(); result=ek.block_bootstrap(lambda bl:tc.pooled_recall_at_k(tabs,bl),list(tabs),B=30,seed=0)
    secs=time.perf_counter()-t
    return {'blocks':len(tabs),'candidates':sum(len(v['c']) for v in tabs.values()),'B':30,'seconds':secs,
            'point':result[0],'estimated_seconds_B2000_linear':secs*2000/30}
probe('actual_reference_bootstrap_timing',timing)
results['environment']={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
 'numpy':np.__version__,'pandas':pd.__version__,'geopandas':gpd.__version__,'rasterio':rasterio.__version__}
(OUT/'reproductions.json').write_text(json.dumps(results,indent=2,default=str),encoding='utf8')
