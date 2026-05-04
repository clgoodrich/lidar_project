"""Extract pit rim polygons using radial spoke / break-in-slope approach.

For each annotated pit:
  1. Cast 36 radial spokes outward from the pit center
  2. Along each spoke, sample the elevation profile
  3. Find where the slope flattens out (wall -> terrain transition)
  4. Connect those rim break-points into a polygon

This gives the actual pit shape where the walls even out to surrounding terrain.

Output: data/derivatives/pit_1m_polygons.gpkg
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pathlib import Path
from shapely.geometry import Polygon, Point
from shapely import make_valid
from scipy.ndimage import gaussian_filter1d

DERIV = Path('data/derivatives')
ANNO = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'
RES = 1.0
N_SPOKES = 36
MAX_R = 12  # max search radius in metres

TILES = {'9t': '_9t_1m.tif', 'mk5': '_mk5_1m.tif', 'mkf': '_mkf_1m.tif'}
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
print(f'Pits: {len(pits)}')


def read_raster(path):
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            a = np.where(a == nd, np.nan, a)
        return a, ds.bounds, ds.shape


def find_rim_along_spoke(dem_win, cr, cc, angle, max_r=MAX_R):
    """Walk outward from (cr,cc) along a spoke at given angle.
    Find where the pit wall slope flattens to surrounding terrain.
    Returns (row, col, distance, flag) where flag indicates spoke quality:
      'normal'    - clean wall-to-terrain transition found
      'flat_early'- hit flat surface very quickly (likely pad/road)
      'no_wall'   - no significant slope found (flat terrain or mis-click)
      'max_range' - wall never flattened within search radius
    """
    step = 0.5
    distances = np.arange(1.0, max_r / RES, step)
    elevs = []
    coords = []

    for d in distances:
        r_s = cr + d * np.sin(angle)
        c_s = cc + d * np.cos(angle)
        ri, ci = int(round(r_s)), int(round(c_s))
        if ri < 0 or ci < 0 or ri >= dem_win.shape[0] or ci >= dem_win.shape[1]:
            break
        v = dem_win[ri, ci]
        if np.isfinite(v):
            elevs.append(v)
            coords.append((r_s, c_s, d * RES))
        else:
            break

    if len(elevs) < 5:
        return None

    elevs = np.array(elevs)
    elevs_sm = gaussian_filter1d(elevs, sigma=1.0)
    slope = np.diff(elevs_sm)

    if len(slope) < 3:
        return None

    slope_sm = gaussian_filter1d(slope, sigma=0.8)

    peak_slope = np.max(slope_sm)

    # Flag: no real wall (flat terrain, slope never gets significant)
    if peak_slope < 0.005:
        # Return first coord with 'no_wall' flag
        return coords[0][0], coords[0][1], coords[0][2], 'no_wall'

    threshold = peak_slope * 0.15

    climbing = False
    rim_idx = None
    for i in range(len(slope_sm)):
        if slope_sm[i] > threshold:
            climbing = True
        elif climbing:
            rim_idx = i + 1
            break

    # Determine flag
    if rim_idx is not None:
        dist_m = coords[min(rim_idx, len(coords)-1)][2]
        if dist_m <= 1.5:
            flag = 'flat_early'
        else:
            flag = 'normal'
    else:
        rim_idx = np.argmax(elevs_sm)
        flag = 'max_range'

    rim_idx = min(rim_idx, len(coords) - 1)
    rim_idx = max(rim_idx, 1)

    return coords[rim_idx][0], coords[rim_idx][1], coords[rim_idx][2], flag


def extract_pit_polygon(x, y, dem, bounds, shape):
    H, W = shape
    X0, Y1 = bounds.left, bounds.top
    r = int(round((Y1 - y) / RES))
    c = int(round((x - X0) / RES))
    HALF = int(MAX_R / RES) + 2

    r1, r2 = r - HALF, r + HALF + 1
    c1, c2 = c - HALF, c + HALF + 1
    if r1 < 0 or c1 < 0 or r2 > H or c2 > W:
        return None

    dem_win = dem[r1:r2, c1:c2]
    if np.isnan(dem_win).mean() > 0.5:
        return None

    # Center = the annotation point in window coords
    cr, cc = HALF, HALF

    # Snap to local min within 2 cells
    snap = 2
    snap_win = dem_win[cr-snap:cr+snap+1, cc-snap:cc+snap+1]
    if not np.isfinite(snap_win).any():
        return None
    fmin = np.nanargmin(snap_win)
    dr, dc = divmod(fmin, snap_win.shape[1])
    cr_s, cc_s = cr - snap + dr, cc - snap + dc
    pit_bottom = dem_win[cr_s, cc_s]

    # Cast spokes from the snapped center
    angles = np.linspace(0, 2*np.pi, N_SPOKES, endpoint=False)
    rim_points = []
    rim_elevs = []
    rim_dists = []
    spoke_flags = []

    for angle in angles:
        result = find_rim_along_spoke(dem_win, cr_s, cc_s, angle)
        if result is not None:
            rp, cp, dist, flag = result
            rim_points.append((rp, cp))
            ri, ci = int(round(rp)), int(round(cp))
            if 0 <= ri < dem_win.shape[0] and 0 <= ci < dem_win.shape[1]:
                v = dem_win[ri, ci]
                if np.isfinite(v):
                    rim_elevs.append(v)
            rim_dists.append(dist)
            spoke_flags.append(flag)

    if len(rim_points) < 10:
        return None

    # Spoke quality summary
    n_total = len(spoke_flags)
    n_normal = spoke_flags.count('normal')
    n_flat_early = spoke_flags.count('flat_early')
    n_no_wall = spoke_flags.count('no_wall')
    n_max_range = spoke_flags.count('max_range')

    # Convert to world coordinates
    world_coords = []
    for (rp, cp) in rim_points:
        wx = X0 + (c1 + cp) * RES
        wy = Y1 - (r1 + rp) * RES
        world_coords.append((wx, wy))
    world_coords.append(world_coords[0])

    try:
        poly = Polygon(world_coords)
        if not poly.is_valid:
            poly = make_valid(poly)
        if poly.is_empty or poly.area < 1.0:
            return None
        if poly.geom_type == 'MultiPolygon':
            poly = max(poly.geoms, key=lambda g: g.area)
        if poly.geom_type != 'Polygon':
            return None

        rim_mean_elev = np.mean(rim_elevs) if rim_elevs else pit_bottom
        depth = rim_mean_elev - pit_bottom

        # Compute radii for only "normal" spokes (true wall transitions)
        normal_dists = [d for d, f in zip(rim_dists, spoke_flags) if f == 'normal']
        flat_dists = [d for d, f in zip(rim_dists, spoke_flags) if f == 'flat_early']

        return {
            'geometry': poly,
            'depth_m': float(depth),
            'rim_elev_m': float(rim_mean_elev),
            'pit_bottom_m': float(pit_bottom),
            'area_m2': float(poly.area),
            'perimeter_m': float(poly.length),
            'circularity': float(4*np.pi*poly.area/(poly.length**2)),
            'mean_radius_m': float(np.mean(rim_dists)),
            'min_radius_m': float(np.min(rim_dists)),
            'max_radius_m': float(np.max(rim_dists)),
            'radius_std_m': float(np.std(rim_dists)),
            # Spoke quality flags
            'spokes_total': n_total,
            'spokes_normal': n_normal,
            'spokes_flat_early': n_flat_early,
            'spokes_no_wall': n_no_wall,
            'spokes_max_range': n_max_range,
            'pct_normal': float(n_normal / n_total) if n_total > 0 else 0.0,
            'pct_truncated': float((n_flat_early + n_no_wall) / n_total) if n_total > 0 else 0.0,
            # Radius of just the clean wall spokes vs truncated ones
            'normal_mean_radius_m': float(np.mean(normal_dists)) if normal_dists else np.nan,
            'flat_mean_radius_m': float(np.mean(flat_dists)) if flat_dists else np.nan,
        }
    except:
        return None


# ---- Process all tiles ----
results = []
seen_fids = set()
for tag, suffix in TILES.items():
    dem, bounds, shape = read_raster(str(DERIV / f'dem{suffix}'))
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
        result = extract_pit_polygon(row.geometry.x, row.geometry.y, dem, bounds, shape)
        if result is not None:
            pt = Point(row.geometry.x, row.geometry.y)
            if result['geometry'].contains(pt):
                contained += 1
            seen_fids.add(idx)
            result['pit_fid'] = int(idx)
            result['tile'] = tag
            results.append(result)
            count += 1
    print(f'    -> {count} polygons, {contained} contain point ({contained/max(count,1):.0%})')

gdf = gpd.GeoDataFrame(results, crs=CRS)
col_order = ['pit_fid', 'tile', 'depth_m', 'rim_elev_m', 'pit_bottom_m',
             'area_m2', 'perimeter_m', 'circularity',
             'mean_radius_m', 'min_radius_m', 'max_radius_m', 'radius_std_m',
             'spokes_total', 'spokes_normal', 'spokes_flat_early', 'spokes_no_wall',
             'spokes_max_range', 'pct_normal', 'pct_truncated',
             'normal_mean_radius_m', 'flat_mean_radius_m', 'geometry']
gdf = gdf[col_order]
gdf.to_file(DERIV / 'pit_1m_polygons.gpkg', driver='GPKG')
print(f'\nSaved: pit_1m_polygons.gpkg ({len(gdf)} polygons)')
print()
stats_cols = ['depth_m', 'area_m2', 'circularity', 'mean_radius_m',
              'min_radius_m', 'max_radius_m', 'radius_std_m']
print(gdf[stats_cols].describe().round(2).to_string())
print()
print('--- Spoke quality summary ---')
print(f'  Mean % normal spokes:        {gdf["pct_normal"].mean():.0%}')
print(f'  Mean % truncated (flat/none): {gdf["pct_truncated"].mean():.0%}')
print(f'  Mean % max-range (open wall): {gdf["spokes_max_range"].mean()/N_SPOKES:.0%}')
print()
# Pits with significant truncation (likely near pad/road)
trunc = gdf[gdf['pct_truncated'] >= 0.25]
print(f'Pits with >=25% truncated spokes: {len(trunc)} ({len(trunc)/len(gdf):.0%})')
print(f'  (these are likely adjacent to pads or roads)')
trunc_show = ['pit_fid', 'tile', 'pct_normal', 'pct_truncated',
              'spokes_flat_early', 'spokes_no_wall', 'normal_mean_radius_m', 'flat_mean_radius_m']
if len(trunc) > 0:
    pd.set_option('display.width', 140)
    print(trunc[trunc_show].head(20).round(2).to_string(index=False))
