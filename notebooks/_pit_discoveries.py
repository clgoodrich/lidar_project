"""Discovery map: high-confidence pit candidates that are NOT near any of
your 90 annotated wellhead_pits.  These are the model's *new* finds.

Outputs:
  pit_discoveries.gpkg     (only candidates >25 m from any annotated pit,
                            ranked by proba)
  pit_discoveries.png      (hillshade overlay: annotated pits = red,
                            discoveries = cyan triangles colored by proba)
  pit_discoveries.txt      (counts per threshold)

Also prints how many discoveries fall inside known pad polygons (very
strong corroboration) vs. truly off-pad (more interesting / more uncertain).
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Point
from shapely import make_valid
from scipy.spatial import cKDTree
import matplotlib.pyplot as plt

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0
CRS = 'EPSG:6346'
NEW_DIST_M = 25.0   # candidate is "new" if >25 m from any annotated pit

cand = gpd.read_file(DERIV / 'pit_candidates_ensemble.gpkg').to_crs(CRS)
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pads = gpd.read_file(ANNO / 'pads_truth.gpkg').to_crs(CRS)
roads = gpd.read_file(ANNO / 'roads_truth.gpkg').to_crs(CRS)

pit_xy = np.array([[g.x, g.y] for g in pits.geometry])
tree = cKDTree(pit_xy)
cxy = np.array([[g.x, g.y] for g in cand.geometry])
dn, _ = tree.query(cxy, k=1)
cand['dist_to_annotated_m'] = dn

# discoveries = far from any annotated pit
disc = cand[cand['dist_to_annotated_m'] > NEW_DIST_M].copy()
print(f'Discoveries (>{NEW_DIST_M} m from any annotated pit):')

# also flag whether discovery sits inside a pad polygon (strong corroboration)
pads_clean = gpd.GeoSeries([make_valid(g) for g in pads.geometry], crs=CRS)
roads_clean = gpd.GeoSeries([make_valid(g) for g in roads.geometry], crs=CRS)
pad_union = pads_clean.union_all()
road_union = roads_clean.union_all()

disc_pts = gpd.GeoSeries(disc.geometry.values, crs=CRS)
disc['in_pad']        = disc_pts.within(pad_union).astype(np.int8).values
disc['dist_to_road_m'] = disc_pts.distance(road_union).values.astype(np.float32)

with open(DERIV / 'pit_discoveries.txt', 'w') as f:
    f.write(f'Discovery candidates (>{NEW_DIST_M} m from any annotated wellhead_pit)\n')
    f.write(f'Source: pit_candidates_ensemble.gpkg (calibrated proba)\n\n')
    f.write(f'{"thr":>5} {"total":>6} {"in_pad":>7} {"off_pad":>8} {"near_road_<25m":>14}\n')
    print(f'{"thr":>5} {"total":>6} {"in_pad":>7} {"off_pad":>8} {"near_road":>10}')
    for thr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
        sub = disc[disc['proba'] >= thr]
        if len(sub) == 0:
            row = f'{thr:5.2f} {0:6d} {0:7d} {0:8d} {0:14d}'
            f.write(row + '\n'); print(row); continue
        in_pad = int(sub['in_pad'].sum())
        off_pad = len(sub) - in_pad
        near_rd = int((sub['dist_to_road_m'] <= 25).sum())
        row = f'{thr:5.2f} {len(sub):6d} {in_pad:7d} {off_pad:8d} {near_rd:14d}'
        f.write(row + '\n'); print(row)

# Save the >=0.30 set as the deliverable; ranked
disc = disc.sort_values('proba', ascending=False).reset_index(drop=True)
out = disc[['proba', 'proba_raw', 'dist_to_annotated_m', 'in_pad', 'dist_to_road_m', 'geometry']]
out.to_file(DERIV / 'pit_discoveries.gpkg', driver='GPKG')

# ---- discovery map at thr >= 0.50
THR_VIZ = 0.50
viz = disc[disc['proba'] >= THR_VIZ]
print(f'\nMaking discovery map at proba >= {THR_VIZ}: {len(viz)} candidates')

with rasterio.open(DERIV / 'hillshade_05.tif') as ds:
    hs = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: hs = np.where(hs == nd, np.nan, hs)

fig, ax = plt.subplots(figsize=(15, 15))
ax.imshow(hs, cmap='gray', extent=[X0, X1, Y0, Y1])
# annotated pits (existing knowledge)
ax.scatter(pit_xy[:, 0], pit_xy[:, 1], s=40, c='red', marker='o',
           linewidths=0, label=f'annotated pits ({len(pit_xy)})')
# discoveries inside pads (strongly corroborated)
in_pad = viz[viz['in_pad'] == 1]
off_pad = viz[viz['in_pad'] == 0]
if len(in_pad):
    ax.scatter(in_pad.geometry.x, in_pad.geometry.y, s=110, c=in_pad['proba'],
               cmap='cool', vmin=THR_VIZ, vmax=1.0, marker='^',
               edgecolors='white', linewidths=0.6,
               label=f'discoveries inside pads ({len(in_pad)})')
if len(off_pad):
    ax.scatter(off_pad.geometry.x, off_pad.geometry.y, s=80, c=off_pad['proba'],
               cmap='YlOrRd', vmin=THR_VIZ, vmax=1.0, marker='v',
               edgecolors='black', linewidths=0.5,
               label=f'discoveries off pad ({len(off_pad)})')
# pad polygons in faint outline
pads_clean.boundary.plot(ax=ax, color='cyan', linewidth=0.7, alpha=0.6)
ax.set_title(f'Pit discoveries (proba >= {THR_VIZ}, >{NEW_DIST_M} m from any annotated pit)\n'
             f'inside pads: {len(in_pad)} (high confidence) | off pad: {len(off_pad)} (more uncertain)',
             fontsize=12)
ax.legend(loc='lower left', fontsize=9)
ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
fig.savefig(DERIV / 'pit_discoveries.png', dpi=140, bbox_inches='tight')
plt.close(fig)
print('wrote pit_discoveries.{gpkg,png,txt}')
