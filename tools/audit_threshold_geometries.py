"""Recompute detection decisions from threshold-test pixels and geometry."""
import ast
from pathlib import Path
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from scipy import ndimage as ndi
from shapely.geometry import shape

def polygons(path,t,min_area):
    with rasterio.open(path) as ds:
        mask=ds.read(1)>=t
        geoms=[shape(g) for g,v in shapes(mask.astype('uint8'),mask=mask,transform=ds.transform)]
        return gpd.GeoDataFrame(geometry=[g for g in geoms if g.area>=min_area],crs=ds.crs)

p='data/9t/results/pit/thresholds/pit_heldout_found_vs_missed_thr0p20_9t.gpkg'
gt=gpd.read_file(p,layer='rim_found_vs_missed')
pred=polygons('data/9t/models/pit/unet_v2/pit_prob_floor.tif',.2,4)
centers=pred.geometry.centroid
hits=[bool(len(centers.sindex.query(g,predicate='contains'))) for g in gt.geometry]
print('PIT RECOMPUTED',len(pred),'polygons',sum(hits),'/',len(gt),'found',flush=True)

gt=gpd.read_file('data/9t/results/pad/thresholds/pad_heldout_found_vs_missed_thr0p50_9t.gpkg',layer='pad_found_vs_missed')
for t in [.45,.5]:
    pred=polygons('data/9t/models/pad/unet/pad_prob.tif',t,100)
    hits=[]
    for g in gt.geometry:
        best=0
        for j in pred.sindex.query(g,predicate='intersects'):
            p=pred.geometry.iloc[j];a=g.intersection(p).area
            best=max(best,a/(g.area+p.area-a))
        hits.append(best>=.3)
    print('PAD RECOMPUTED',t,len(pred),'polygons',sum(hits),'/',len(gt),'found',flush=True)

gt=gpd.read_file('data/9t/results/road/thresholds/road_heldout_found_vs_missed_thr0p20_9t.gpkg',layer='road_found_vs_missed')
with rasterio.open('data/9t/models/road/unet_1m/road_prob.tif') as ds:
    mask=ds.read(1)>=.2
    distance=ndi.distance_transform_edt(~mask,sampling=abs(ds.transform.a))
    tree=ast.parse(Path('notebooks/wellsight_v2/s5_eval/_road_threshold_products_9t.py').read_text(encoding='utf-8-sig'))
    scope=dict(globals(),TOL_M=5.,SAMPLE_M=1.)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='coverage')
    exec(compile(ast.Module(body=[node],type_ignores=[]),'coverage','exec'),scope)
    cov=scope['coverage'](gt.geometry,distance,ds.transform)
    clean=gt.clean.astype(bool).to_numpy()
    print('ROAD RECOMPUTED',int((cov>=.5).sum()),'/',len(gt),'clean',int((cov[clean]>=.5).sum()),'/',int(clean.sum()),'clean_km',gt[clean].geometry.length.sum()/1000,'all_km',gt.geometry.length.sum()/1000,'max_coverage_difference',np.max(np.abs(cov-gt.coverage)),flush=True)
