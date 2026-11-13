"""Measure possible training-window overlap using the saved fold assignment."""
import json
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely

root=Path(__file__).resolve().parents[1]
base=root/'data/9t'
asg=pd.read_csv(base/'models/pad/unet_cv5/pad_cv5_fold_assignment_9t.csv').dropna()
blocks=gpd.read_file(base/'derived/05/pad_blocks_9t.gpkg',layer='blocks').to_crs(6346)
bf=dict(zip(asg.block_id,asg.fold))
blocks['fold']=blocks.block_id.map(bf)
with rasterio.open(base/'derived/05/features_pit_9t_05.tif') as ds:
    tf,H,W=ds.transform,ds.height,ds.width
results=[]
for k in range(5):
    held=sorted(asg.loc[asg.fold==k,'block_id'].unique())
    rest=sorted(set(asg.block_id.unique())-set(held))
    rng=np.random.default_rng(20260727+1000*k)
    shuffled=list(rng.permutation(rest))
    train=shuffled[max(1,int(round(.2*len(shuffled)))):]
    train_geom=blocks[blocks.block_id.isin(train)].geometry
    held_geom=blocks[blocks.block_id.isin(held)].geometry.union_all()
    bounds=np.array([g.bounds for g in train_geom])
    rng=np.random.default_rng(100+k)
    # Background draws exactly follow the sampler's block/centre distribution.
    hit=0
    example=None
    for _ in range(1000):
        b=bounds[rng.integers(0,len(bounds))]
        x,y=rng.uniform(b[0],b[2]),rng.uniform(b[1],b[3])
        row,col=int(round((y-tf.f)/tf.e)),int(round((x-tf.c)/tf.a))
        r0,c0=int(np.clip(row-192,0,H-384)),int(np.clip(col-192,0,W-384))
        x0,y0=tf*(c0,r0); x1,y1=tf*(c0+384,r0+384)
        box=shapely.box(x0,y1,x1,y0)
        overlap=box.intersection(held_geom).area
        if overlap>0:
            hit+=1
            if example is None:
                example=dict(centre=[x,y],heldout_overlap_m2=overlap)
    results.append(dict(fold=k,background_draws=1000,windows_overlapping_heldout_blocks=hit,example=example))
out=root/'nisar/reviews/nisar_boundary_audit.json'
out.write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
