"""Extract pit rim polygons using radial curvature-break approach.

For each annotated pit:
  1. Cast 36 radial spokes outward from the snapped pit center
  2. Sample DEM and LRM_5 elevation profiles along each spoke
  3. Find the rim via second-derivative peak (curvature maximum = wall-to-terrain inflection)
  4. Score each spoke's quality based on profile shape
  5. Fit a smooth polygon through the rim points, weighting by spoke quality

Output: data/derivatives/pit_1m_polygons.gpkg
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Polygon, Point
from shapely import make_valid
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import interp1d

DERIV = Path('data/derivatives')
ANNO = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'
RES = 1.0
N_SPOKES = 36
MAX_R_CELLS = 12
SNAP_R = 2
STEP = 0.5  # sub-pixel sampling step in cells
SIGMA_PROFILE = 1.2  # smoothing for elevation profile
SIGMA_CURV = 1.0  # smoothing for curvature

TILES = {'9t': '_9t_1m.tif', 'mk5': '_mk5_1m.tif', 'mkf': '_mkf_1m.tif'}


def read_raster(path):
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            a = np.where(a == nd, np.nan, a)
        return a, ds.bounds, ds.shape


def sample_profile(raster, cr, cc, angle, max_r, step):
    """Sample raster values along a radial spoke using nearest-neighbor."""
    H, W = raster.shape
    distances = np.arange(1.0, max_r, step)
    elevs = []
    coords = []

    for d in distances:
        r_s = cr + d * np.sin(angle)
        c_s = cc + d * np.cos(angle)
        ri, ci = int(round(r_s)), int(round(c_s))
        if ri < 0 or ci < 0 or ri >= H or ci >= W:
            break
        v = raster[ri, ci]
        if not np.isfinite(v):
            break
        elevs.append(v)
        coords.append((r_s, c_s, d * RES))

    if len(elevs) < 5:
        return None, None, None

    return np.array([c[2] for c in coords]), np.array(elevs), coords


def find_rim_slope_decay(dem_profile, lrm_profile, distances):
    """Find rim where the wall slope decays to background level.

    Uses a climb-then-fall state machine: slope must first rise above the
    threshold (confirming we're on the pit wall), then we detect when it
    drops below. LRM zero-crossing refines the result when available.

    Returns (rim_distance_m, rim_index, flag, confidence).
    """
    n = len(dem_profile)
    if n < 6:
        return None

    profile = gaussian_filter1d(dem_profile, sigma=1.0)
    slope = np.diff(profile)
    if len(slope) < 4:
        return None
    slope_sm = gaussian_filter1d(slope, sigma=0.8)

    peak_slope = np.max(slope_sm)
    if peak_slope < 0.005:
        d0 = distances[0]
        return d0, 0, d0, d0, 'no_wall', 0.1

    threshold = peak_slope * 0.15

    # State machine: wait for slope to climb above threshold, then find decay
    climbing = False
    rim_idx = None
    for i in range(len(slope_sm)):
        if slope_sm[i] > threshold:
            climbing = True
        elif climbing:
            rim_idx = i + 1
            break

    if rim_idx is None:
        # Wall never flattened — use the elevation peak as fallback
        rim_idx = np.argmax(profile)
        flag = 'max_range'
        confidence = 0.3
    else:
        confidence = min(1.0, peak_slope / 0.03)
        flag = 'normal'

    # LRM refinement: only nudge outward (never inward) if LRM zero-crossing
    # confirms the rim is slightly further out than slope-decay alone found
    if lrm_profile is not None and flag == 'normal':
        lrm_n = min(len(lrm_profile), n)
        lrm_smooth = gaussian_filter1d(lrm_profile[:lrm_n], sigma=1.0)
        peak_slope_idx = np.argmax(slope_sm)
        if peak_slope_idx < len(lrm_smooth) - 1:
            after_peak = lrm_smooth[peak_slope_idx:]
            zero_crossings = np.where(np.diff(np.sign(after_peak)))[0]
            if len(zero_crossings) > 0:
                lrm_rim = peak_slope_idx + zero_crossings[0] + 1
                # Only use if LRM agrees and is at or beyond the slope-decay rim
                if 0 <= (lrm_rim - rim_idx) <= 3:
                    rim_idx = int(round(0.6 * rim_idx + 0.4 * lrm_rim))
                    confidence = min(1.0, confidence + 0.15)

    rim_idx = np.clip(rim_idx, 1, min(n, len(distances)) - 1)
    rim_dist = distances[rim_idx]

    if rim_dist <= 1.5:
        flag = 'flat_early'
        confidence *= 0.5

    # Floor boundary: where the slope first exceeds 25% of peak (wall begins)
    floor_threshold = peak_slope * 0.25
    floor_idx = 0
    for i in range(len(slope_sm)):
        if slope_sm[i] > floor_threshold:
            floor_idx = i
            break
    floor_idx = max(floor_idx, 1)
    floor_dist = distances[min(floor_idx, len(distances) - 1)]

    # Outer rim boundary: continue past rim crest until the downslope flattens
    # Find the elevation peak (rim crest) at or beyond the slope-decay rim
    crest_search_start = max(rim_idx - 1, 0)
    crest_idx = crest_search_start + np.argmax(profile[crest_search_start:])

    # From the crest, walk outward until the (now negative) slope flattens
    outer_idx = min(crest_idx + 1, n - 1)
    if crest_idx < n - 2:
        for i in range(crest_idx + 1, len(slope_sm)):
            if slope_sm[i] > -peak_slope * 0.10:
                outer_idx = i + 1
                break
        else:
            outer_idx = n - 1
    outer_idx = np.clip(outer_idx, rim_idx, len(distances) - 1)
    outer_dist = distances[outer_idx]

    return rim_dist, rim_idx, floor_dist, outer_dist, flag, confidence


def extract_pit_polygon(x, y, dem, lrm, bounds, shape):
    H, W = shape
    X0, Y1 = bounds.left, bounds.top
    r = int(round((Y1 - y) / RES))
    c = int(round((x - X0) / RES))
    HALF = MAX_R_CELLS + 3

    r1, r2 = r - HALF, r + HALF + 1
    c1, c2 = c - HALF, c + HALF + 1
    if r1 < 0 or c1 < 0 or r2 > H or c2 > W:
        return None

    dem_win = dem[r1:r2, c1:c2]
    lrm_win = lrm[r1:r2, c1:c2] if lrm is not None else None

    if np.isnan(dem_win).mean() > 0.5:
        return None

    cr, cc = HALF, HALF

    # Snap to local minimum in DEM within SNAP_R cells
    s1r, s2r = max(0, cr - SNAP_R), min(dem_win.shape[0], cr + SNAP_R + 1)
    s1c, s2c = max(0, cc - SNAP_R), min(dem_win.shape[1], cc + SNAP_R + 1)
    snap_win = dem_win[s1r:s2r, s1c:s2c]
    if not np.isfinite(snap_win).any():
        return None
    fmin = np.nanargmin(snap_win)
    dr, dc_off = divmod(fmin, snap_win.shape[1])
    cr_s, cc_s = s1r + dr, s1c + dc_off
    pit_bottom = dem_win[cr_s, cc_s]

    angles = np.linspace(0, 2 * np.pi, N_SPOKES, endpoint=False)
    floor_dists_raw = []
    rim_dists_raw = []
    outer_dists_raw = []
    rim_elevs = []
    spoke_flags = []
    spoke_confs = []
    valid_angles = []

    for angle in angles:
        dem_dists, dem_vals, dem_coords = sample_profile(
            dem_win, cr_s, cc_s, angle, MAX_R_CELLS, STEP)
        if dem_dists is None:
            spoke_flags.append('failed')
            spoke_confs.append(0.0)
            continue

        lrm_vals = None
        if lrm_win is not None:
            lrm_dists, lrm_v, _ = sample_profile(
                lrm_win, cr_s, cc_s, angle, MAX_R_CELLS, STEP)
            if lrm_v is not None:
                min_len = min(len(lrm_v), len(dem_vals))
                lrm_vals = lrm_v[:min_len]

        result = find_rim_slope_decay(dem_vals, lrm_vals, dem_dists)
        if result is None:
            spoke_flags.append('failed')
            spoke_confs.append(0.0)
            continue

        rim_dist, rim_idx, floor_dist, outer_dist, flag, conf = result
        spoke_flags.append(flag)
        spoke_confs.append(conf)
        valid_angles.append(angle)
        floor_dists_raw.append(floor_dist)
        rim_dists_raw.append(rim_dist)
        outer_dists_raw.append(outer_dist)

        rim_idx_clamped = min(rim_idx, len(dem_coords) - 1)
        rp, cp, _ = dem_coords[rim_idx_clamped]
        ri, ci = int(round(rp)), int(round(cp))
        if 0 <= ri < dem_win.shape[0] and 0 <= ci < dem_win.shape[1]:
            v = dem_win[ri, ci]
            if np.isfinite(v):
                rim_elevs.append(v)

    if len(valid_angles) < 10:
        return None

    orig_wx = X0 + (c1 + cc_s) * RES
    orig_wy = Y1 - (r1 + cr_s) * RES

    def smooth_and_build_poly(raw_dists, angles_list):
        arr = np.array(raw_dists)
        w = 5
        padded = np.concatenate([arr[-w//2:], arr, arr[:w//2]])
        kernel = np.ones(w) / w
        sm = np.convolve(padded, kernel, mode='valid')[:len(arr)]
        coords = []
        for d, a in zip(sm, angles_list):
            wx = orig_wx + d * np.cos(a)
            wy = orig_wy - d * np.sin(a)
            coords.append((wx, wy))
        coords.append(coords[0])
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = make_valid(poly)
        if poly.is_empty or poly.area < 1.0:
            return None, sm
        if poly.geom_type == 'MultiPolygon':
            poly = max(poly.geoms, key=lambda g: g.area)
        if poly.geom_type != 'Polygon':
            return None, sm
        return poly, sm

    floor_poly, floor_sm = smooth_and_build_poly(floor_dists_raw, valid_angles)
    rim_poly, rim_sm = smooth_and_build_poly(rim_dists_raw, valid_angles)
    outer_poly, outer_sm = smooth_and_build_poly(outer_dists_raw, valid_angles)

    if rim_poly is None:
        return None

    try:
        rim_mean_elev = np.mean(rim_elevs) if rim_elevs else pit_bottom
        depth = rim_mean_elev - pit_bottom

        n_total = len(spoke_flags)
        n_normal = spoke_flags.count('normal')
        n_flat_early = spoke_flags.count('flat_early')
        n_no_wall = spoke_flags.count('no_wall')
        n_max_range = spoke_flags.count('max_range')
        n_failed = spoke_flags.count('failed')
        valid_confs = [c for c, f in zip(spoke_confs, spoke_flags) if f != 'failed']
        mean_conf = float(np.mean(valid_confs)) if valid_confs else 0.0

        return {
            'geometry': rim_poly,
            'geometry_floor': floor_poly,
            'geometry_outer': outer_poly,
            'depth_m': float(depth),
            'rim_elev_m': float(rim_mean_elev),
            'pit_bottom_m': float(pit_bottom),
            'area_m2': float(rim_poly.area),
            'area_floor_m2': float(floor_poly.area) if floor_poly else np.nan,
            'area_outer_m2': float(outer_poly.area) if outer_poly else np.nan,
            'perimeter_m': float(rim_poly.length),
            'circularity': float(4 * np.pi * rim_poly.area / (rim_poly.length ** 2)),
            'mean_radius_m': float(np.mean(rim_sm)),
            'mean_floor_radius_m': float(np.mean(floor_sm)),
            'mean_outer_radius_m': float(np.mean(outer_sm)),
            'min_radius_m': float(np.min(rim_sm)),
            'max_radius_m': float(np.max(rim_sm)),
            'radius_std_m': float(np.std(rim_sm)),
            'spokes_total': n_total,
            'spokes_normal': n_normal,
            'spokes_flat_early': n_flat_early,
            'spokes_no_wall': n_no_wall,
            'spokes_max_range': n_max_range,
            'spokes_failed': n_failed,
            'pct_normal': float(n_normal / n_total) if n_total > 0 else 0.0,
            'pct_truncated': float((n_flat_early + n_no_wall + n_failed) / n_total) if n_total > 0 else 0.0,
            'mean_confidence': mean_conf,
        }
    except Exception:
        return None


# ---- Process all tiles ----
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
print(f'Pits: {len(pits)}')

results = []
seen_fids = set()
for tag, suffix in TILES.items():
    dem, bounds, shape = read_raster(str(DERIV / f'dem{suffix}'))
    lrm_path = DERIV / f'lrm_5{suffix}'
    lrm, _, _ = read_raster(str(lrm_path)) if lrm_path.exists() else (None, None, None)

    bx0, by0, bx1, by1 = bounds
    in_tile = pits.cx[bx0:bx1, by0:by1]
    if len(in_tile) == 0:
        continue
    print(f'  {tag}: {len(in_tile)} pits')
    count = 0
    contained = 0
    for idx, row in in_tile.iterrows():
        if idx in seen_fids:
            continue
        result = extract_pit_polygon(row.geometry.x, row.geometry.y, dem, lrm, bounds, shape)
        if result is not None:
            pt = Point(row.geometry.x, row.geometry.y)
            if result['geometry'].contains(pt):
                contained += 1
            seen_fids.add(idx)
            result['pit_fid'] = int(idx)
            result['tile'] = tag
            results.append(result)
            count += 1
    print(f'    -> {count} polygons, {contained} contain annotation point ({contained / max(count, 1):.0%})')

# Build three GeoDataFrames: floor, rim (wall top), outer (full envelope)
shared_cols = ['pit_fid', 'tile', 'depth_m', 'rim_elev_m', 'pit_bottom_m',
               'area_m2', 'area_floor_m2', 'area_outer_m2',
               'perimeter_m', 'circularity',
               'mean_radius_m', 'mean_floor_radius_m', 'mean_outer_radius_m',
               'min_radius_m', 'max_radius_m', 'radius_std_m',
               'spokes_total', 'spokes_normal', 'spokes_flat_early', 'spokes_no_wall',
               'spokes_max_range', 'spokes_failed', 'pct_normal', 'pct_truncated',
               'mean_confidence']

# Rim layer (primary — wall-to-terrain transition)
gdf_rim = gpd.GeoDataFrame(
    [{k: v for k, v in r.items() if k not in ('geometry_floor', 'geometry_outer')} for r in results],
    crs=CRS
)
gdf_rim.to_file(DERIV / 'pit_1m_polygons.gpkg', driver='GPKG', layer='rim')

# Floor layer (pit bottom only)
floor_records = []
for r in results:
    if r.get('geometry_floor') is not None:
        rec = {k: v for k, v in r.items() if k not in ('geometry', 'geometry_floor', 'geometry_outer')}
        rec['geometry'] = r['geometry_floor']
        floor_records.append(rec)
gdf_floor = gpd.GeoDataFrame(floor_records, crs=CRS)
gdf_floor.to_file(DERIV / 'pit_1m_polygons.gpkg', driver='GPKG', layer='floor')

# Outer layer (full rim envelope — includes outer slope)
outer_records = []
for r in results:
    if r.get('geometry_outer') is not None:
        rec = {k: v for k, v in r.items() if k not in ('geometry', 'geometry_floor', 'geometry_outer')}
        rec['geometry'] = r['geometry_outer']
        outer_records.append(rec)
gdf_outer = gpd.GeoDataFrame(outer_records, crs=CRS)
gdf_outer.to_file(DERIV / 'pit_1m_polygons.gpkg', driver='GPKG', layer='outer')

print(f'\nSaved: pit_1m_polygons.gpkg')
print(f'  rim layer:   {len(gdf_rim)} polygons (wall-to-terrain transition)')
print(f'  floor layer: {len(gdf_floor)} polygons (pit bottom)')
print(f'  outer layer: {len(gdf_outer)} polygons (full rim envelope)')
print()
stats_cols = ['depth_m', 'area_m2', 'area_floor_m2', 'area_outer_m2',
              'circularity', 'mean_radius_m', 'mean_floor_radius_m',
              'mean_outer_radius_m', 'mean_confidence']
print(gdf_rim[stats_cols].describe().round(2).to_string())
print()
print('--- Spoke quality summary ---')
print(f'  Mean % normal spokes:        {gdf_rim["pct_normal"].mean():.0%}')
print(f'  Mean % truncated:            {gdf_rim["pct_truncated"].mean():.0%}')
print(f'  Mean confidence:             {gdf_rim["mean_confidence"].mean():.2f}')
print(f'  Mean depth:                  {gdf_rim["depth_m"].mean():.2f} m')
print(f'  Mean rim radius:             {gdf_rim["mean_radius_m"].mean():.2f} m')
print(f'  Mean floor radius:           {gdf_rim["mean_floor_radius_m"].mean():.2f} m')
print(f'  Mean outer radius:           {gdf_rim["mean_outer_radius_m"].mean():.2f} m')
