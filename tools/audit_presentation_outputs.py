"""Read-only audit of presentation source GIS outputs."""
from pathlib import Path
import json
import numpy as np
import geopandas as gpd
import rasterio
import ast
import sys
import pandas as pd
from scipy import ndimage as ndi
from rasterio.features import shapes, rasterize
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
def emit(**data):
    print(json.dumps(data, default=str), flush=True)

def helpers(filename, names, extra=None):
    tree=ast.parse((ROOT/filename).read_text(encoding='utf-8-sig'))
    scope=dict(globals(), REPORT_TAUS=[.3], MIN_AREA_M2=4., TOL_M=5., SAMPLE_M=1.)
    if extra:scope.update(extra)
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in names:
            exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'),scope)
    return scope

def raster(path, thresholds):
    with rasterio.open(ROOT / path) as ds:
        counts = {t: 0 for t in thresholds}
        valid = 0
        for _, window in ds.block_windows(1):
            a = ds.read(1, window=window, masked=True)
            valid += int(a.count())
            for t in thresholds:
                counts[t] += int(np.ma.filled(a >= t, False).sum())
        px = abs(ds.transform.a * ds.transform.e - ds.transform.b * ds.transform.d)
        emit(kind='raster', path=path, crs=ds.crs, shape=ds.shape,
             tags=ds.tags(1), valid_pixels=valid, tile_ha=ds.width*ds.height*px/10000,
             thresholds={str(t):dict(pixels=n,ha=n*px/10000,pct=100*n/(ds.width*ds.height)) for t,n in counts.items()})

for path, ts in ([] if '--pad-only' in sys.argv else [
    ('data/9t/models/pit/unet_v2/pit_prob_floor.tif',[.2]),
    ('data/9t/models/pit/unet_v2/pit_unet_floor_prob_thr0p20_9t_05.tif',[.2]),
    ('data/9t/models/pad/unet/pad_prob.tif',[.45,.5]),
    ('data/9t/models/road/unet_1m/road_prob.tif',[.2]),
]):
    raster(path,ts)

for task, tag in ([] if '--pad-only' in sys.argv else [('pit','20'),('pad','50'),('road','20')]):
    path=ROOT/f'data/9t/results/{task}/thresholds/{task}_heldout_found_vs_missed_thr0p{tag}_9t.gpkg'
    for layer in gpd.list_layers(path).name:
        if layer == 'layer_styles': continue
        df=gpd.read_file(path,layer=layer)
        info=dict(kind='gpkg',path=str(path.relative_to(ROOT)),layer=layer,n=len(df),columns=list(df.columns))
        if 'verdict' in df: info['verdict']=df.verdict.value_counts().to_dict()
        if 'clean' in df:
            clean=df[df.clean.astype(bool)]
            info['clean_n']=len(clean)
            info['clean_length_km']=float(clean.geometry.length.sum()/1000)
            if 'verdict' in df:info['clean_verdict']=clean.verdict.value_counts().to_dict()
        if layer=='model_geometry':info['polygon_area_ha']=float(df.geometry.area.sum()/10000)
        emit(**info)

transfer=ROOT/'data/_comparisons/pit_heldout_and_transfer_2026-09-20/613590_transfer_from_9t_cv5_05'
for path in ([] if '--pad-only' in sys.argv else sorted(transfer.glob('*.gpkg'))):
    gt=gpd.read_file(path,layer='pit_floors_scored')
    pred=gpd.read_file(path,layer='predictions_unmatched_not_FPs')
    candidates=[]
    for i,geom in enumerate(gt.geometry):
        for j in pred.sindex.query(geom,predicate='intersects'):
            p=pred.geometry.iloc[j]
            inter=geom.intersection(p).area
            score=inter/(geom.area+p.area-inter)
            if score>=.3:candidates.append((float(pred.score.iloc[j]),i,int(j)))
    used_gt=set();used_pred=set()
    for score,i,j in sorted(candidates,reverse=True):
        if i not in used_gt and j not in used_pred:used_gt.add(i);used_pred.add(j)
    emit(kind='transfer_geometry',path=path.name,n_gt=len(gt),n_pred=len(pred),saved_found=int(gt.found_iou30.sum()),recomputed_found=len(used_gt),recall=len(used_gt)/len(gt))

for task, layer, key in ([('pad','plat','pad_id')] if '--pad-only' in sys.argv else [('pit','pit_inside','pit_inside_id'),('pad','plat','pad_id')]):
    model=ROOT/f'data/9t/models/{task}/unet_cv5'
    assignment=pd.read_csv(model/f'{task}_cv5_fold_assignment_9t.csv')
    truth=gpd.read_file(ROOT/'qgis/annotations/annotations_proj.gpkg',layer=layer)
    truth=truth[[key,'geometry']].dissolve(by=key).reset_index().merge(assignment,on=key)
    blocks=gpd.read_file(ROOT/f'data/9t/derived/05/{task}_blocks_9t.gpkg',layer='blocks')
    table=pd.read_csv(model/f'{task}_cv5_per_fold_9t.csv')
    funcs=helpers(f'notebooks/wellsight_v2/s3_train/_{task}_unet_cv5.py',['polygonize','match_scores'],{'MIN_AREA_M2':4. if task=='pit' else 100.})
    for fold in range(5):
        if '--fold3' in sys.argv and fold != 3: continue
        ids=assignment.loc[assignment.fold==fold,'block_id']
        footprint=blocks[blocks.block_id.isin(ids)].geometry.union_all()
        rest=sorted(set(assignment.block_id.unique())-set(sorted(ids.unique())))
        shuffled=list(np.random.default_rng(20260727+1000*fold).permutation(rest))
        val_ids=shuffled[:max(1,int(round(.2*len(shuffled))))]
        val_footprint=blocks[blocks.block_id.isin(val_ids)].geometry.union_all()
        name=f'pit_prob_floor_cvfold{fold}_9t_05.tif' if task=='pit' else f'pad_prob_cvfold{fold}_9t_05.tif'
        with rasterio.open(model/f'fold{fold}'/name) as ds:
            prob=ds.read(1)
            keep=rasterize([(g.buffer(40 if task=='pit' else 80),1) for g in [footprint,val_footprint]],out_shape=prob.shape,transform=ds.transform)
            prob[keep==0]=0
            for row in table[table.fold==fold].itertuples():
                pred=funcs['polygonize'](prob,ds.transform,ds.crs,row.prob_threshold)
                pred=pred[pred.geometry.centroid.within(footprint)].reset_index(drop=True)
                gt=truth[truth.fold==fold]
                scores=funcs['match_scores'](gt,pred)[.3]
                emit(kind='cv_raster_recomputed',task=task,fold=fold,rule=row.objective,**scores,expected_recall=row.recall_iou30,expected_precision=row.precision_iou30)
        del prob,keep
