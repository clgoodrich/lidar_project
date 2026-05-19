"""Pit-rim polygon extraction v2 — refined with best practices.

Improvements over v1 (_pit_rim_polygons.py):
  - Bilinear interpolation for sub-pixel spoke sampling
  - Adjacent-basin rejection (truncate spokes whose profile dips back to pit-floor level)
  - MAD-based outlier replacement on per-spoke radii (robust to bad spokes)
  - Confidence-weighted radius interpolation before smoothing
  - Fourier low-pass polygon smoothing (k <= 6) replaces box filter
  - Robust center snap: local-min on 3x3-smoothed depth window
  - Combined confidence: slope magnitude * floor-to-rim monotonicity fraction

Output: data/derivatives/pit_1m_polygons_v2.gpkg
"""
import numpy as np, rasterio, geopandas as gpd
from pathlib import Path
from shapely.geometry import Polygon, Point
from shapely import make_valid
from scipy.ndimage import gaussian_filter1d, uniform_filter

DERIV = Path('data/derivatives')
ANNO = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'
RES = 1.0
N_SPOKES = 36
MAX_R_CELLS = 12
SNAP_R = 2
STEP = 0.5
FOURIER_KMAX = 8              # keep harmonics 0..8
MAD_K = 3.0                   # outlier z-threshold (in MAD units)
ADJ_BASIN_FRAC = 0.25         # spoke truncates if elev dips below floor + frac*depth

TILES = {'9t': '_9t_1m.tif', 'mk5': '_mk5_1m.tif', 'mkf': '_mkf_1m.tif'}


def read_raster(path):
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            a = np.where(a == nd, np.nan, a)
        return a, ds.bounds, ds.shape


def bilinear(raster, r, c):
    """Sub-pixel bilinear sample. NaN if any neighbour is NaN or OOB."""
    H, W = raster.shape
    if r < 0 or c < 0 or r >= H - 1 or c >= W - 1:
        return np.nan
    r0, c0 = int(np.floor(r)), int(np.floor(c))
    fr, fc = r - r0, c - c0
    v00 = raster[r0, c0]; v01 = raster[r0, c0 + 1]
    v10 = raster[r0 + 1, c0]; v11 = raster[r0 + 1, c0 + 1]
    if not (np.isfinite(v00) and np.isfinite(v01) and np.isfinite(v10) and np.isfinite(v11)):
        return np.nan
    return (v00 * (1 - fr) * (1 - fc) + v01 * (1 - fr) * fc
            + v10 * fr * (1 - fc) + v11 * fr * fc)


def sample_profile(raster, cr, cc, angle, max_r, step):
    """Bilinear-sampled radial profile."""
    distances = np.arange(1.0, max_r, step)
    elevs, coords = [], []
    for d in distances:
        r_s = cr + d * np.sin(angle)
        c_s = cc + d * np.cos(angle)
        v = bilinear(raster, r_s, c_s)
        if not np.isfinite(v):
            break
        elevs.append(v)
        coords.append((r_s, c_s, d * RES))
    if len(elevs) < 5:
        return None, None, None
    return (np.array([c[2] for c in coords]),
            np.array(elevs), coords)


def find_rim_v2(dem_profile, lrm_profile, distances, pit_bottom):
    """Detect rim with adjacent-basin rejection + monotonicity-based confidence."""
    n = len(dem_profile)
    if n < 6:
        return None

    profile = gaussian_filter1d(dem_profile, sigma=1.0)

    # Adjacent-basin truncation: trigger only when (a) we've climbed a meaningful
    # height, and (b) the profile then dips for >=2 consecutive samples back to
    # floor+frac*rise. Avoids over-clipping shallow pits.
    running_max = np.maximum.accumulate(profile)
    rise = running_max - profile[0]
    MIN_CLIMB = 0.20  # metres — ignore dips before this much rise
    dip_run = 0
    cut = None
    for i in range(2, n):
        meaningful_rise = max(MIN_CLIMB, 0.3 * float(rise[i]))
        if rise[i] < meaningful_rise:
            dip_run = 0
            continue
        if profile[i] < profile[0] + ADJ_BASIN_FRAC * rise[i]:
            dip_run += 1
            if dip_run >= 2:
                cut = i - 1
                break
        else:
            dip_run = 0
    if cut is not None and cut >= 5:
        profile = profile[:cut]
        distances = distances[:cut]
        n = len(profile)
    if n < 6:
        return None

    slope = np.diff(profile)
    if len(slope) < 4:
        return None
    slope_sm = gaussian_filter1d(slope, sigma=0.8)
    peak_slope = float(np.max(slope_sm))
    if peak_slope < 0.005:
        return distances[0], 0, distances[0], distances[0], 'no_wall', 0.1

    threshold = peak_slope * 0.15

    climbing = False
    rim_idx = None
    for i in range(len(slope_sm)):
        if slope_sm[i] > threshold:
            climbing = True
        elif climbing:
            rim_idx = i + 1
            break

    if rim_idx is None:
        rim_idx = int(np.argmax(profile))
        flag = 'max_range'
    else:
        flag = 'normal'

    # Monotonicity confidence: fraction of climbing samples from floor to rim
    floor_to_rim = slope_sm[:max(rim_idx, 1)]
    if len(floor_to_rim) > 0:
        monotonicity = float(np.mean(floor_to_rim > 0))
    else:
        monotonicity = 0.0
    slope_conf = min(1.0, peak_slope / 0.03)
    confidence = slope_conf * (0.5 + 0.5 * monotonicity)
    if flag == 'max_range':
        confidence *= 0.5

    # LRM refinement (outward nudge only)
    if lrm_profile is not None and flag == 'normal':
        lrm_n = min(len(lrm_profile), n)
        lrm_smooth = gaussian_filter1d(lrm_profile[:lrm_n], sigma=1.0)
        peak_slope_idx = int(np.argmax(slope_sm))
        if peak_slope_idx < len(lrm_smooth) - 1:
            after_peak = lrm_smooth[peak_slope_idx:]
            zero_crossings = np.where(np.diff(np.sign(after_peak)))[0]
            if len(zero_crossings) > 0:
                lrm_rim = peak_slope_idx + int(zero_crossings[0]) + 1
                if 0 <= (lrm_rim - rim_idx) <= 3:
                    rim_idx = int(round(0.6 * rim_idx + 0.4 * lrm_rim))
                    confidence = min(1.0, confidence + 0.15)

    rim_idx = int(np.clip(rim_idx, 1, min(n, len(distances)) - 1))
    rim_dist = float(distances[rim_idx])

    if rim_dist <= 1.5:
        flag = 'flat_early'
        confidence *= 0.5

    floor_threshold = peak_slope * 0.25
    floor_idx = 1
    for i in range(len(slope_sm)):
        if slope_sm[i] > floor_threshold:
            floor_idx = max(i, 1)
            break
    floor_dist = float(distances[min(floor_idx, len(distances) - 1)])

    crest_search_start = max(rim_idx - 1, 0)
    crest_idx = crest_search_start + int(np.argmax(profile[crest_search_start:]))
    outer_idx = min(crest_idx + 1, n - 1)
    if crest_idx < n - 2:
        for i in range(crest_idx + 1, len(slope_sm)):
            if slope_sm[i] > -peak_slope * 0.10:
                outer_idx = i + 1
                break
        else:
            outer_idx = n - 1
    outer_idx = int(np.clip(outer_idx, rim_idx, len(distances) - 1))
    outer_dist = float(distances[outer_idx])

    return rim_dist, rim_idx, floor_dist, outer_dist, flag, confidence


def mad_replace(radii, confidences, k=MAD_K):
    """Replace MAD-outlier radii with confidence-weighted neighbour mean."""
    r = np.array(radii, dtype=float)
    w = np.array(confidences, dtype=float)
    if len(r) < 5:
        return r
    med = np.median(r)
    mad = np.median(np.abs(r - med))
    if mad < 1e-6:
        return r
    z = np.abs(r - med) / (1.4826 * mad)
    bad = z > k
    if not bad.any():
        return r
    n = len(r)
    r_out = r.copy()
    for i in np.where(bad)[0]:
        # Weighted mean of the two flanking *good* spokes
        wsum, vsum = 0.0, 0.0
        for off in (1, 2, 3):
            for j in ((i - off) % n, (i + off) % n):
                if not bad[j]:
                    weight = w[j] / (off ** 2)
                    wsum += weight
                    vsum += weight * r[j]
            if wsum > 0:
                break
        r_out[i] = vsum / wsum if wsum > 0 else med
    return r_out


def fourier_lowpass(radii, k_max=FOURIER_KMAX):
    """Keep DC + lowest k_max harmonics. radii must be uniformly sampled around 2pi."""
    r = np.asarray(radii, dtype=float)
    F = np.fft.rfft(r)
    if k_max + 1 < len(F):
        F[k_max + 1:] = 0
    return np.fft.irfft(F, n=len(r))


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

    # Snap to raw local minimum (matches v1 — empirically best containment)
    s1r, s2r = max(0, cr - SNAP_R), min(dem_win.shape[0], cr + SNAP_R + 1)
    s1c, s2c = max(0, cc - SNAP_R), min(dem_win.shape[1], cc + SNAP_R + 1)
    snap_win = dem_win[s1r:s2r, s1c:s2c]
    if not np.isfinite(snap_win).any():
        return None
    fmin = int(np.nanargmin(snap_win))
    dr, dc_off = divmod(fmin, snap_win.shape[1])
    cr_s, cc_s = s1r + dr, s1c + dc_off
    pit_bottom = float(dem_win[cr_s, cc_s])

    angles = np.linspace(0, 2 * np.pi, N_SPOKES, endpoint=False)
    floor_raw = np.full(N_SPOKES, np.nan)
    rim_raw = np.full(N_SPOKES, np.nan)
    outer_raw = np.full(N_SPOKES, np.nan)
    confs = np.zeros(N_SPOKES)
    flags = ['failed'] * N_SPOKES
    rim_elevs = []

    for i, angle in enumerate(angles):
        dem_d, dem_v, dem_coords = sample_profile(dem_win, cr_s, cc_s, angle, MAX_R_CELLS, STEP)
        if dem_d is None:
            continue
        lrm_v = None
        if lrm_win is not None:
            _, lv, _ = sample_profile(lrm_win, cr_s, cc_s, angle, MAX_R_CELLS, STEP)
            if lv is not None:
                lrm_v = lv[:min(len(lv), len(dem_v))]

        result = find_rim_v2(dem_v, lrm_v, dem_d, pit_bottom)
        if result is None:
            continue
        rim_dist, rim_idx, floor_dist, outer_dist, flag, conf = result

        flags[i] = flag
        confs[i] = conf
        floor_raw[i] = floor_dist
        rim_raw[i] = rim_dist
        outer_raw[i] = outer_dist

        rim_idx_clamped = min(rim_idx, len(dem_coords) - 1)
        rp, cp, _ = dem_coords[rim_idx_clamped]
        v = bilinear(dem_win, rp, cp)
        if np.isfinite(v):
            rim_elevs.append(float(v))

    valid_mask = np.isfinite(rim_raw)
    n_valid = int(valid_mask.sum())
    if n_valid < 10:
        return None

    # Fill failed spokes with confidence-weighted neighbour interpolation,
    # then MAD-replace outliers, then Fourier low-pass smooth.
    def fill_outliers_and_smooth(raw, confs):
        arr = raw.copy()
        n = len(arr)
        # circular fill of NaNs
        for i in np.where(~np.isfinite(arr))[0]:
            wsum, vsum = 0.0, 0.0
            for off in range(1, n // 2):
                for j in ((i - off) % n, (i + off) % n):
                    if np.isfinite(arr[j]):
                        weight = max(confs[j], 0.05) / (off ** 2)
                        wsum += weight
                        vsum += weight * arr[j]
                if wsum > 0:
                    break
            arr[i] = vsum / wsum if wsum > 0 else float(np.nanmedian(raw))
        arr = mad_replace(arr, np.maximum(confs, 0.05))
        arr = fourier_lowpass(arr, FOURIER_KMAX)
        # enforce minimum 1m radius (no spoke retracts inside the cell)
        return np.maximum(arr, 1.0)

    rim_sm = fill_outliers_and_smooth(rim_raw, confs)
    floor_sm = fill_outliers_and_smooth(floor_raw, confs)
    outer_sm = fill_outliers_and_smooth(outer_raw, confs)

    orig_wx = X0 + (c1 + cc_s) * RES
    orig_wy = Y1 - (r1 + cr_s) * RES

    def build_poly(radii):
        coords = []
        for d, a in zip(radii, angles):
            wx = orig_wx + d * np.cos(a)
            wy = orig_wy - d * np.sin(a)
            coords.append((wx, wy))
        coords.append(coords[0])
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = make_valid(poly)
        if poly.is_empty or poly.area < 1.0:
            return None
        if poly.geom_type == 'MultiPolygon':
            poly = max(poly.geoms, key=lambda g: g.area)
        if poly.geom_type != 'Polygon':
            return None
        return poly

    rim_poly = build_poly(rim_sm)
    floor_poly = build_poly(floor_sm)
    outer_poly = build_poly(outer_sm)
    if rim_poly is None:
        return None

    rim_mean_elev = float(np.mean(rim_elevs)) if rim_elevs else pit_bottom
    depth = float(rim_mean_elev - pit_bottom)

    n_total = N_SPOKES
    n_normal = flags.count('normal')
    n_flat_early = flags.count('flat_early')
    n_no_wall = flags.count('no_wall')
    n_max_range = flags.count('max_range')
    n_failed = flags.count('failed')
    valid_confs = confs[valid_mask]
    mean_conf = float(np.mean(valid_confs)) if len(valid_confs) else 0.0

    return {
        'geometry': rim_poly,
        'geometry_floor': floor_poly,
        'geometry_outer': outer_poly,
        'depth_m': depth,
        'rim_elev_m': rim_mean_elev,
        'pit_bottom_m': pit_bottom,
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
        'pct_normal': n_normal / n_total,
        'pct_truncated': (n_flat_early + n_no_wall + n_failed) / n_total,
        'mean_confidence': mean_conf,
    }


# ---- Process all tiles ----
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
print(f'Pits: {len(pits)}')

results = []
seen_fids = set()
for tag, suffix in TILES.items():
    dem_path = DERIV / f'dem{suffix}'
    if not dem_path.exists():
        print(f'  {tag}: dem missing, skipping')
        continue
    dem, bounds, shape = read_raster(str(dem_path))
    lrm_path = DERIV / f'lrm_5{suffix}'
    lrm, _, _ = read_raster(str(lrm_path)) if lrm_path.exists() else (None, None, None)

    bx0, by0, bx1, by1 = bounds
    in_tile = pits.cx[bx0:bx1, by0:by1]
    if len(in_tile) == 0:
        continue
    print(f'  {tag}: {len(in_tile)} pits')
    count, contained = 0, 0
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

# ---- Write layers ----
gdf_rim = gpd.GeoDataFrame(
    [{k: v for k, v in r.items() if k not in ('geometry_floor', 'geometry_outer')} for r in results],
    crs=CRS,
)
gdf_rim.to_file(DERIV / 'pit_1m_polygons_v2.gpkg', driver='GPKG', layer='rim')

def _layer(records, geom_key):
    out = []
    for r in records:
        if r.get(geom_key) is None:
            continue
        rec = {k: v for k, v in r.items() if k not in ('geometry', 'geometry_floor', 'geometry_outer')}
        rec['geometry'] = r[geom_key]
        out.append(rec)
    return gpd.GeoDataFrame(out, crs=CRS)

_layer(results, 'geometry_floor').to_file(DERIV / 'pit_1m_polygons_v2.gpkg', driver='GPKG', layer='floor')
_layer(results, 'geometry_outer').to_file(DERIV / 'pit_1m_polygons_v2.gpkg', driver='GPKG', layer='outer')

print(f'\nSaved: pit_1m_polygons_v2.gpkg ({len(gdf_rim)} rim polygons)')
stats_cols = ['depth_m', 'area_m2', 'area_floor_m2', 'area_outer_m2',
              'circularity', 'mean_radius_m', 'mean_confidence']
print(gdf_rim[stats_cols].describe().round(2).to_string())
print('\n--- Spoke quality summary ---')
print(f'  Mean % normal spokes: {gdf_rim["pct_normal"].mean():.0%}')
print(f'  Mean % truncated:     {gdf_rim["pct_truncated"].mean():.0%}')
print(f'  Mean confidence:      {gdf_rim["mean_confidence"].mean():.2f}')
print(f'  Mean depth:           {gdf_rim["depth_m"].mean():.2f} m')
print(f'  Mean rim radius:      {gdf_rim["mean_radius_m"].mean():.2f} m')
