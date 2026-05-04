"""Pit template-learning pipeline.

Inputs:
  wellhead_pits.gpkg  (90 Point annotations)
  0.5m derivative rasters in data/derivatives/

Process:
  1. reproject pit points to EPSG:6346
  2. extract HALF-cell windows around each point from a set of channels
  3. auto-snap each window's center to the local minimum in LRM_5 within
     a small search radius (so slight mis-clicks don't blur the template)
  4. per-window normalize (subtract window mean) so varying pit depths line up
  5. compute median template per channel
  6. on LRM_5 across the full tile run skimage.feature.match_template (NCC)
  7. save per-channel mean/median cutout figure + match-score raster +
     non-max-suppressed candidate GPKG

Outputs (data/derivatives/):
  pit_template_cutouts.png      (grid of snapped cutouts per channel)
  pit_template_mean.png         (mean/median template per channel)
  pit_match_score_05.tif        (NCC scores across the tile)
  pit_candidates_template.gpkg  (top candidates, ranked)
  pit_candidates_template.png   (hillshade overlay)
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Point
from rasterio.transform import from_origin
from skimage.feature import match_template, peak_local_max
import matplotlib.pyplot as plt

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
RES   = 0.5
X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0
W = int((X1 - X0) / RES); H = int((Y1 - Y0) / RES)
T = from_origin(X0, Y1, RES, RES)
CRS = 'EPSG:6346'

# Window: 15 m -> 30 cells across.  We use an *odd* size with a clear center.
HALF   = 15   # half window in cells -> full = 31 cells ~ 15.5 m
SNAP_R = 4    # local search radius in cells for auto-snap (~2 m)

CHANNELS = [
    'lrm_5_05.tif',
    'lrm_11_05.tif',
    'tpi_05_05.tif',
    'openness_neg_05.tif',
    'intensity_ground_05.tif',
    'hillshade_05.tif',
]


def read(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a


def world_to_rc(x, y):
    col = (x - X0) / RES
    row = (Y1 - y) / RES
    return row, col


def rc_to_world(row, col):
    x = X0 + (col + 0.5) * RES
    y = Y1 - (row + 0.5) * RES
    return x, y


# 1. load + reproject pit points
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pts_xy = np.array([[g.x, g.y] for g in pits.geometry])
print(f'loaded {len(pts_xy)} pit points')

# 2. read channels
rasters = {name: read(name) for name in CHANNELS}
lrm5 = rasters['lrm_5_05.tif']

# 3. snap each pit center to local minimum in LRM_5 within SNAP_R
snapped_rc = []
drops = []
for (x, y) in pts_xy:
    r0, c0 = world_to_rc(x, y)
    ri, ci = int(round(r0)), int(round(c0))
    r1, r2 = max(0, ri - SNAP_R), min(H, ri + SNAP_R + 1)
    c1, c2 = max(0, ci - SNAP_R), min(W, ci + SNAP_R + 1)
    win = lrm5[r1:r2, c1:c2]
    if np.isnan(win).all():
        drops.append((ri, ci)); continue
    fmin = np.nanargmin(win)
    dr, dc = divmod(fmin, win.shape[1])
    snapped_rc.append((r1 + dr, c1 + dc))

snapped_rc = np.array(snapped_rc)
print(f'snapped centers: {len(snapped_rc)}  (dropped {len(drops)})')
print(f'mean snap offset: {np.mean([abs(r1)+abs(c1) for (r1,c1),(r0,c0) in zip(snapped_rc, [world_to_rc(x,y) for x,y in pts_xy[:len(snapped_rc)]])]):.2f} cells')

# 4. extract normalized cutouts per channel
WIN = 2 * HALF + 1
def cutouts_for(raster):
    out = []
    for (r, c) in snapped_rc:
        r1, r2 = r - HALF, r + HALF + 1
        c1, c2 = c - HALF, c + HALF + 1
        if r1 < 0 or c1 < 0 or r2 > H or c2 > W:
            continue
        win = raster[r1:r2, c1:c2].astype(np.float32)
        if np.isnan(win).mean() > 0.2:
            continue
        m = np.nanmean(win)
        out.append(win - m)
    return np.stack(out, axis=0) if out else np.empty((0, WIN, WIN), dtype=np.float32)

cutouts = {name: cutouts_for(rasters[name]) for name in CHANNELS}
for name, arr in cutouts.items():
    print(f'  {name:30s}  {arr.shape[0]} cutouts')

# 5. median + mean templates per channel
medians = {name: np.nanmedian(cutouts[name], axis=0) for name in CHANNELS}
means   = {name: np.nanmean  (cutouts[name], axis=0) for name in CHANNELS}

# Figure: first 24 cutouts of LRM_5 + the mean/median templates per channel
fig, axes = plt.subplots(4, 6, figsize=(15, 11))
show = cutouts['lrm_5_05.tif'][:24]
for i, ax in enumerate(axes.ravel()):
    if i < len(show):
        ax.imshow(show[i], cmap='RdBu_r', vmin=-0.8, vmax=0.8)
        ax.set_title(f'pit {i}', fontsize=8)
    else:
        ax.axis('off')
    ax.set_xticks([]); ax.set_yticks([])
fig.suptitle('snapped LRM_5 cutouts around each annotated pit (first 24)', fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(DERIV / 'pit_template_cutouts.png', dpi=130, bbox_inches='tight')
plt.close(fig)

fig, axes = plt.subplots(2, len(CHANNELS), figsize=(3*len(CHANNELS), 6))
for j, name in enumerate(CHANNELS):
    a0 = axes[0, j]; a1 = axes[1, j]
    im0 = a0.imshow(means[name],   cmap='RdBu_r' if 'lrm' in name or 'tpi' in name else 'viridis')
    im1 = a1.imshow(medians[name], cmap='RdBu_r' if 'lrm' in name or 'tpi' in name else 'viridis')
    a0.set_title(f'mean {name}', fontsize=8)
    a1.set_title(f'median {name}', fontsize=8)
    for ax in (a0, a1):
        ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(im0, ax=a0, fraction=0.046, pad=0.04)
    plt.colorbar(im1, ax=a1, fraction=0.046, pad=0.04)
fig.suptitle(f'pit template (n={cutouts["lrm_5_05.tif"].shape[0]})', fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(DERIV / 'pit_template_mean.png', dpi=130, bbox_inches='tight')
plt.close(fig)
print('wrote pit_template_cutouts.png, pit_template_mean.png')

# 6. template match: run NCC on each of the 4 pit-informative channels,
# then combine by averaging.  Single-channel NCC is noisy; joint signal is
# much stronger because pits show up in *all* of these simultaneously.
MATCH_CHANNELS = ['lrm_5_05.tif', 'lrm_11_05.tif', 'tpi_05_05.tif', 'openness_neg_05.tif']

def per_channel_score(chan_name):
    template = medians[chan_name].astype(np.float32)
    template = np.where(np.isnan(template), 0, template)
    img = rasters[chan_name].astype(np.float32)
    valid = ~np.isnan(img)
    img_f = np.where(valid, img, 0)
    s = match_template(img_f, template, pad_input=True)
    s[~valid] = np.nan
    return s

print('running match_template per channel...')
per_scores = {}
for name in MATCH_CHANNELS:
    per_scores[name] = per_channel_score(name)
    print(f'  {name:25s}  p50={np.nanpercentile(per_scores[name],50):.3f}  p99={np.nanpercentile(per_scores[name],99):.3f}')

# combine: mean across channels (all contribute equally)
score = np.nanmean(np.stack(list(per_scores.values()), axis=0), axis=0)
valid = ~np.isnan(score)
print(f'combined score: p50={np.nanpercentile(score,50):.3f}  p99={np.nanpercentile(score,99):.3f}')

# save score raster
with rasterio.open(DERIV / 'pit_match_score_05.tif', 'w', driver='GTiff',
                   height=H, width=W, count=1, dtype='float32', crs=CRS,
                   transform=T, nodata=-9999, tiled=True, compress='deflate',
                   predictor=3) as ds:
    ds.write(np.where(np.isnan(score), -9999, score).astype(np.float32), 1)
print('wrote pit_match_score_05.tif')

# 7. peak finding: non-max suppression across a 5 m radius
min_distance_cells = int(round(5.0 / RES))
# Calibrate threshold against the distribution of scores AT the annotated pits.
ref_rows = [r for (r, c) in snapped_rc if 0 <= r < H and 0 <= c < W]
ref_cols = [c for (r, c) in snapped_rc if 0 <= r < H and 0 <= c < W]
ref_scores = np.array([score[r, c] for r, c in zip(ref_rows, ref_cols)])
ref_scores = ref_scores[~np.isnan(ref_scores)]
print(f'scores AT annotated pits: p10={np.percentile(ref_scores,10):.3f}  p50={np.percentile(ref_scores,50):.3f}  p90={np.percentile(ref_scores,90):.3f}')
THR = float(np.percentile(ref_scores, 25))  # keep peaks where score >= annotated-pit p25
print(f'chosen threshold (annotated-pit p25): {THR:.3f}')

peaks = peak_local_max(np.nan_to_num(score, nan=-1),
                       min_distance=min_distance_cells,
                       threshold_abs=THR)
print(f'found {len(peaks)} peaks at thr={THR:.3f}, min_dist={min_distance_cells*RES} m')

# convert to world coords, compute nearest-annotated-pit distance
rows = peaks[:, 0]; cols = peaks[:, 1]
xs, ys = rc_to_world(rows, cols)
scores = score[rows, cols]

# distance to nearest annotated pit
from scipy.spatial import cKDTree
tree = cKDTree(pts_xy)
dnear, inear = tree.query(np.c_[xs, ys], k=1)

cand = gpd.GeoDataFrame({
    'score':         scores,
    'nearest_pit_m': dnear,
    'is_hit_25m':    dnear <= 25,
    'is_hit_10m':    dnear <= 10,
    'geometry':      [Point(x, y) for x, y in zip(xs, ys)],
}, crs=CRS).sort_values('score', ascending=False).reset_index(drop=True)
cand.to_file(DERIV / 'pit_candidates_template.gpkg', driver='GPKG')
print(f'wrote pit_candidates_template.gpkg  ({len(cand)} rows)')

# recall at various thresholds
print('\n--- recall (hits <=10m of an annotated pit) per score threshold ---')
thr_grid = sorted({float(np.percentile(ref_scores, q)) for q in (5, 10, 25, 50, 75)})
for t in thr_grid:
    sub = cand[cand['score'] >= t]
    hits10 = sub['is_hit_10m'].sum()
    hits25 = sub['is_hit_25m'].sum()
    # count distinct pits covered
    nn = tree.query(np.c_[sub.geometry.x, sub.geometry.y], k=1)[1] if len(sub) else np.array([])
    pits_covered_10 = len(np.unique(nn[sub['is_hit_10m'].values])) if len(sub) else 0
    print(f'  thr={t:.2f}  n={len(sub):5d}  hits<=10m={hits10:4d}  pits_covered<=10m={pits_covered_10}/90  precision10={hits10/max(len(sub),1):.2%}')

# 8. overview PNG
hs = read('hillshade_05.tif')
fig, ax = plt.subplots(figsize=(14, 14))
ax.imshow(hs, cmap='gray', extent=[X0, X1, Y0, Y1])
# annotated pits in red
ax.scatter(pts_xy[:, 0], pts_xy[:, 1], s=40, facecolors='none', edgecolors='red', linewidths=1.5, label=f'annotated pits ({len(pts_xy)})')
# top 500 candidates by score
top = cand.head(500)
ax.scatter(top.geometry.x, top.geometry.y, s=15, c=top['score'], cmap='plasma',
           vmin=THR, vmax=top['score'].max(), label=f'top {len(top)} candidates')
ax.set_title('pit template match — hillshade + annotated pits (red) + top 500 candidates')
ax.legend(loc='lower left')
ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
fig.savefig(DERIV / 'pit_candidates_template.png', dpi=130, bbox_inches='tight')
plt.close(fig)
print('wrote pit_candidates_template.png')
