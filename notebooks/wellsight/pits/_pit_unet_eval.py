"""Evaluate U-Net predictions against annotated pits — apples-to-apples with XGBoost.

For each tile:
  1. Load the probability raster
  2. Extract peak locations via peak_local_max (5m NMS, same as XGBoost pipeline)
  3. Match peaks to annotated pits within 10m
  4. Report precision, recall, and false positive count at multiple thresholds
"""
import numpy as np, rasterio, geopandas as gpd
from pathlib import Path
from scipy.spatial import cKDTree
from skimage.feature import peak_local_max

DERIV = Path('data/derivatives')
ANNO = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'
RES = 1.0
MIN_DIST = 5  # NMS radius in cells (same as XGBoost pipeline)
MATCH_DIST = 10.0  # metres — same as XGBoost labeling

pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
pit_xy = np.array([[g.x, g.y] for g in pits.geometry])
pit_tree = cKDTree(pit_xy)
print(f'Annotated pits: {len(pits)}')

TILES = {'9t': '_9t_1m.tif', 'mk5': '_mk5_1m.tif', 'mkf': '_mkf_1m.tif'}
THRESHOLDS = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]

# Collect all peaks across all tiles per threshold
all_peaks = {t: [] for t in THRESHOLDS}

for tag, suffix in TILES.items():
    pred_path = DERIV / f'pit_unet_pred_{tag}.tif'
    if not pred_path.exists():
        print(f'  {tag}: prediction not found, skipping')
        continue

    with rasterio.open(pred_path) as ds:
        prob = ds.read(1).astype(np.float32)
        bounds = ds.bounds
        shape = ds.shape
        nd = ds.nodata

    X0, Y1 = bounds.left, bounds.top
    H, W = shape

    # Mask nodata
    valid_mask = (prob >= 0) if nd is not None else np.ones_like(prob, dtype=bool)
    prob_clean = np.where(valid_mask, prob, 0.0)

    print(f'\n  {tag} ({H}x{W}):')

    for thr in THRESHOLDS:
        # Extract peaks above threshold with NMS
        coords = peak_local_max(prob_clean, min_distance=MIN_DIST,
                                threshold_abs=thr, exclude_border=MIN_DIST)

        for (r, c) in coords:
            x = X0 + (c + 0.5) * RES
            y = Y1 - (r + 0.5) * RES
            p = prob[r, c]
            all_peaks[thr].append((x, y, p, tag))

# Evaluate each threshold
print(f'\n{"thr":>5} {"n_peaks":>8} {"hits10":>7} {"pits_cov":>9} {"fp":>7} {"prec":>7} {"recall":>7}')
print('-' * 60)

results = []
for thr in THRESHOLDS:
    peaks = all_peaks[thr]
    n = len(peaks)
    if n == 0:
        print(f'{thr:5.2f} {0:8d} {0:7d} {0:9d} {0:7d} {"N/A":>7} {"N/A":>7}')
        continue

    peak_xy = np.array([(p[0], p[1]) for p in peaks])

    # How many peaks are within 10m of any annotated pit?
    d_to_pit, idx_pit = pit_tree.query(peak_xy, k=1)
    hits = int((d_to_pit <= MATCH_DIST).sum())
    fp = n - hits

    # How many distinct annotated pits are covered?
    matched_pit_indices = idx_pit[d_to_pit <= MATCH_DIST]
    pits_covered = len(np.unique(matched_pit_indices))

    prec = hits / n if n > 0 else 0
    recall = pits_covered / len(pits)

    print(f'{thr:5.2f} {n:8d} {hits:7d} {pits_covered:9d} {fp:7d} {prec:7.2%} {recall:7.2%}')
    results.append((thr, n, hits, pits_covered, fp, prec, recall))

# Compare with XGBoost
print('\n--- XGBoost ensemble (from pit_1m_ensemble_metrics.txt) ---')
xgb_path = DERIV / 'pit_1m_ensemble_metrics.txt'
if xgb_path.exists():
    print(xgb_path.read_text())

# Save
with open(DERIV / 'pit_unet_eval.txt', 'w') as f:
    f.write('U-Net pit detection evaluation\n')
    f.write(f'NMS radius: {MIN_DIST}m, match distance: {MATCH_DIST}m\n')
    f.write(f'Total annotated pits: {len(pits)}\n\n')
    f.write(f'{"thr":>5} {"n_peaks":>8} {"hits10":>7} {"pits_cov":>9} {"fp":>7} {"prec":>7} {"recall":>7}\n')
    for thr, n, hits, cov, fp, prec, recall in results:
        f.write(f'{thr:5.2f} {n:8d} {hits:7d} {cov:9d} {fp:7d} {prec:7.2%} {recall:7.2%}\n')

print('\nSaved: pit_unet_eval.txt')
