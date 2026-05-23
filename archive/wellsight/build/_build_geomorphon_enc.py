"""Compute geomorphon enclosure count rasters at multiple scales.

For each DEM cell, casts 8 rays outward to a lookup distance.
Along each ray, tracks the maximum zenith angle (upward look).
If zenith > flatness_threshold, that direction is "higher."
The enclosure count = number of "higher" directions (0-8).

Outputs per tile:
  geomorphon_enc_5_<tile>_1m.tif   (lookup=5 cells)
  geomorphon_enc_8_<tile>_1m.tif   (lookup=8 cells)
  geomorphon_enc_12_<tile>_1m.tif  (lookup=12 cells)

These are integer rasters (0-8) that can be sampled per candidate
as ML features, or visualized directly.
"""
import numpy as np, rasterio
from pathlib import Path
import time

DERIV = Path('data/derivatives')
RES = 1.0

# 8 directions: N, NE, E, SE, S, SW, W, NW (row_delta, col_delta)
DIRECTIONS = [
    (-1,  0),  # N
    (-1,  1),  # NE
    ( 0,  1),  # E
    ( 1,  1),  # SE
    ( 1,  0),  # S
    ( 1, -1),  # SW
    ( 0, -1),  # W
    (-1, -1),  # NW
]

LOOKUP_DISTANCES = [5, 8, 12]
FLATNESS_DEG = 1.0  # degrees (Jasiewicz & Stepinski 2013 default)
FLATNESS_RAD = np.radians(FLATNESS_DEG)

TILES = {
    '9t': '_9t_1m.tif',
    'mk5': '_mk5_1m.tif',
    'mkf': '_mkf_1m.tif',
}


def compute_enclosure(dem, lookup, flatness_rad):
    """Compute geomorphon enclosure count for entire DEM array.

    For each cell, for each of 8 directions:
      Walk outward 1..lookup cells.
      At each step, compute the zenith angle = atan2(elev_diff, horiz_dist).
      Track the MAXIMUM zenith angle seen along that ray.
      If max_zenith > flatness_threshold, that direction is "higher."

    Returns: uint8 array (0-8) same shape as dem.
    """
    H, W = dem.shape
    enclosure = np.zeros((H, W), dtype=np.uint8)

    # Pre-compute horizontal distances for diagonal vs cardinal
    # Diagonal steps are sqrt(2) * RES apart
    diag = np.sqrt(2.0) * RES

    for d_idx, (dr, dc) in enumerate(DIRECTIONS):
        is_diag = (dr != 0 and dc != 0)
        step_dist = diag if is_diag else RES

        # For this direction, compute "is_higher" for all cells at once
        # using a rolling maximum zenith angle approach
        max_zenith = np.full((H, W), -np.inf, dtype=np.float32)

        for step in range(1, lookup + 1):
            # Source and target indices
            # We want: for each cell (r,c), look at cell (r + step*dr, c + step*dc)
            # The neighbor's elevation relative to center
            horiz_dist = step * step_dist

            # Compute valid slice ranges
            # Source rows/cols that have a valid neighbor at this step
            if dr > 0:
                src_r = slice(0, H - step * dr)
                nbr_r = slice(step * dr, H)
            elif dr < 0:
                src_r = slice(-step * dr, H)
                nbr_r = slice(0, H + step * dr)
            else:
                src_r = slice(0, H)
                nbr_r = slice(0, H)

            if dc > 0:
                src_c = slice(0, W - step * dc)
                nbr_c = slice(step * dc, W)
            elif dc < 0:
                src_c = slice(-step * dc, W)
                nbr_c = slice(0, W + step * dc)
            else:
                src_c = slice(0, W)
                nbr_c = slice(0, W)

            # Elevation difference: neighbor - center
            elev_diff = dem[nbr_r, nbr_c] - dem[src_r, src_c]

            # Zenith angle: positive means neighbor is higher
            zenith = np.arctan2(elev_diff, horiz_dist)

            # Update maximum zenith for this direction
            np.maximum(max_zenith[src_r, src_c], zenith, out=max_zenith[src_r, src_c])

        # After all steps: if max_zenith > flatness threshold, direction is "higher"
        higher = max_zenith > flatness_rad
        enclosure += higher.astype(np.uint8)

    return enclosure


def process_tile(tag, suffix):
    dem_path = DERIV / f'dem{suffix}'
    print(f'\n  Tile: {tag} ({dem_path.name})')

    with rasterio.open(dem_path) as ds:
        dem = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            dem = np.where(dem == nd, np.nan, dem)
        profile = ds.profile.copy()

    # Fill NaN with nearest valid elevation so rays crossing data gaps
    # see "flat" terrain rather than a jump to the global median.
    from scipy.ndimage import distance_transform_edt
    nan_mask = np.isnan(dem)
    if nan_mask.any():
        _, nearest_idx = distance_transform_edt(nan_mask, return_distances=True, return_indices=True)
        dem_filled = dem.copy()
        dem_filled[nan_mask] = dem[tuple(nearest_idx[:, nan_mask])]
    else:
        dem_filled = dem

    H, W = dem.shape
    print(f'    Shape: {H}x{W}, NaN: {np.isnan(dem).sum()} cells')

    profile.update(dtype='uint8', count=1, nodata=255)

    for lookup in LOOKUP_DISTANCES:
        t0 = time.time()
        enc = compute_enclosure(dem_filled, lookup, FLATNESS_RAD)

        # Mask out original NaN cells
        enc[np.isnan(dem)] = 255

        out_path = DERIV / f'geomorphon_enc_{lookup}{suffix}'
        with rasterio.open(out_path, 'w', **profile) as dst:
            dst.write(enc, 1)

        elapsed = time.time() - t0
        # Stats on valid cells
        valid = enc[enc != 255]
        print(f'    lookup={lookup:2d}: {elapsed:.1f}s  '
              f'mean_enc={valid.mean():.2f}  '
              f'pct_6plus={100*(valid>=6).mean():.1f}%  '
              f'pct_8={100*(valid==8).mean():.1f}%  '
              f'-> {out_path.name}')


if __name__ == '__main__':
    print('Computing geomorphon enclosure counts...')
    print(f'  Flatness threshold: {FLATNESS_DEG} deg')
    print(f'  Lookup distances: {LOOKUP_DISTANCES} cells')
    print(f'  Directions: 8 (cardinal + diagonal)')

    for tag, suffix in TILES.items():
        process_tile(tag, suffix)

    print('\nDone.')
