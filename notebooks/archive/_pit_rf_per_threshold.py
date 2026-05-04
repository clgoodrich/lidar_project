"""Per-threshold overlays for the pit RF: one PNG per threshold level
showing annotated pits + predicted candidates, colored by correctness.

Color scheme on each plot:
  red  hollow circle : annotated pit (ground truth)
  green dot          : predicted candidate <=10 m from an annotated pit (TP)
  orange dot         : predicted candidate >10 m from any annotated pit (FP)
  red  X             : annotated pit with NO prediction within 10 m (missed)
"""
import numpy as np, rasterio, geopandas as gpd
from pathlib import Path
from scipy.spatial import cKDTree
import matplotlib.pyplot as plt

DERIV = Path('data/derivatives')
ANNO  = Path('data/derivatives/annotations')
X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0
CRS = 'EPSG:6346'
POS_DIST_M = 10.0

THRS = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]

def read(name):
    with rasterio.open(DERIV / name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a == nd, np.nan, a)
    return a

cand = gpd.read_file(DERIV / 'pit_candidates_rf.gpkg').to_crs(CRS)
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x, g.y] for g in pits.geometry])
tree_pits = cKDTree(pit_xy)

hs = read('hillshade_05.tif')

for thr in THRS:
    sub = cand[cand['proba'] >= thr].copy()
    if len(sub) == 0:
        print(f'thr={thr} -> no candidates, skipping')
        continue
    cxy = np.c_[sub.geometry.x, sub.geometry.y]
    d_to_pit, _ = tree_pits.query(cxy, k=1)
    is_tp = d_to_pit <= POS_DIST_M
    tp_xy = cxy[is_tp]; fp_xy = cxy[~is_tp]

    # identify annotated pits that were found vs missed at this threshold
    if len(sub):
        tree_cand = cKDTree(cxy)
        d_pit_to_cand, _ = tree_cand.query(pit_xy, k=1)
        pit_found = d_pit_to_cand <= POS_DIST_M
    else:
        pit_found = np.zeros(len(pit_xy), dtype=bool)
    missed_xy = pit_xy[~pit_found]
    found_xy  = pit_xy[ pit_found]

    fig, ax = plt.subplots(figsize=(14, 14))
    ax.imshow(hs, cmap='gray', extent=[X0, X1, Y0, Y1])
    # annotated pits: solid red circle
    ax.scatter(pit_xy[:, 0], pit_xy[:, 1], s=40, c='red',
               marker='o', linewidths=0,
               label=f'annotated pits ({len(pit_xy)})')
    # predictions that hit an annotated pit: solid lime X
    if len(tp_xy):
        ax.scatter(tp_xy[:, 0], tp_xy[:, 1], s=70, c='lime',
                   marker='X', linewidths=0,
                   label=f'found pits ({len(tp_xy)})')

    precision = is_tp.mean() if len(is_tp) else 0
    recall    = pit_found.mean()
    ax.set_title(f'pit RF @ proba>={thr:.2f}   '
                 f'n={len(sub)}  TP={is_tp.sum()}  FP={(~is_tp).sum()}  '
                 f'pits_covered={pit_found.sum()}/{len(pit_xy)}   '
                 f'precision={precision:.0%}  recall={recall:.0%}')
    ax.legend(loc='lower left', fontsize=9)
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    fig.savefig(DERIV / f'pit_rf_thr{int(thr*100):02d}.png',
                dpi=130, bbox_inches='tight')
    plt.close(fig)
    print(f'wrote pit_rf_thr{int(thr*100):02d}.png  '
          f'(n={len(sub)} TP={is_tp.sum()} FP={(~is_tp).sum()} '
          f'missed={len(missed_xy)})')
