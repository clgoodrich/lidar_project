"""Road / linear-feature extraction v2 — comprehensive multi-channel pipeline.

A meticulous rewrite. v1 only saw narrow LRM signatures (incised tracks,
berms). v2 adds the channels and the network-level steps needed to recover
the whole road graph:

Channels (per pixel):
   A. sato(-LRM_5)            multi-sigma — narrow sunken tracks / drainage ditches
   B. sato(+LRM_5)            multi-sigma — narrow berms / push piles
   C. sato(-LRM_15)           multi-sigma — wide depressed roads
   D. sato(+LRM_15)           multi-sigma — wide crowned/improved roads
   E. sato(-roughness)        multi-sigma — flat strips on flat ground (THE missing
                                       channel — fires where a managed road
                                       surface is locally smoother than the
                                       surrounding rough ground but has no
                                       elevation signature)
   F. structure-tensor anisotropy of slope — linear "coherence" of grade
   G. asymmetric cut/fill bench score (from local theta) — cut benches on slopes

Fusion → threshold → morph cleanup → skeletonize → graph → cost-surface
GAP-BRIDGING (each endpoint searches along its tangent for a continuation,
shortest-path route through the score raster reconnects fragments) → re-
skeletonize → spur pruning → vectorize → write rasters + GeoPackage + PNG.

Run:
    python -u notebooks/wellsight/_road_extract.py --tile mkf
    python -u notebooks/wellsight/_road_extract.py --tile mkf --bbox X1 Y1 X2 Y2
    python -u notebooks/wellsight/_road_extract.py --tile mkf --debug-channels
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.transform import xy
from scipy import ndimage as ndi
from skimage.filters import sato
from skimage.graph import route_through_array
from skimage.morphology import (
    binary_closing, remove_small_objects, skeletonize, disk
)

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
DERIV = ROOT / "data" / "derivatives"
OUT_DIR = DERIV / "roads"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNEL_NAMES = ["lrm5_dark", "lrm5_bright", "lrm15_dark", "lrm15_bright",
                 "rough_strip", "canopy_gap", "density_strip"]


# ===================== IO ====================================================
def read_raster(path, window=None):
    with rasterio.open(path) as ds:
        a = ds.read(1, window=window).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            a = np.where(a == nd, np.nan, a)
        transform = ds.window_transform(window) if window is not None else ds.transform
        return a, transform, ds.crs


def fill_nan_nearest(a):
    if not np.isnan(a).any():
        return a
    mask = np.isnan(a)
    idx = ndi.distance_transform_edt(mask, return_distances=False, return_indices=True)
    return a[tuple(idx)]


def write_raster(arr, path, transform, crs, dtype="float32"):
    profile = dict(
        driver="GTiff", height=arr.shape[0], width=arr.shape[1],
        count=1, dtype=dtype, crs=crs, transform=transform,
        compress="deflate", predictor=2, tiled=True,
        blockxsize=512, blockysize=512,
    )
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(arr.astype(dtype), 1)


# ===================== feature builders ======================================
def lrm_at(dem, sigma_px):
    """Local Relief Model: DEM minus its low-pass at `sigma_px`."""
    fill = fill_nan_nearest(dem)
    sm = ndi.gaussian_filter(fill, sigma=sigma_px)
    out = (fill - sm).astype(np.float32)
    out[np.isnan(dem)] = np.nan
    return out


def roughness_map(dem, win=3):
    """Local std of DEM in a (win x win) box. High = rough/forested/eroded
    ground; low = smooth maintained surface (road, pad, field)."""
    fill = fill_nan_nearest(dem)
    mean = ndi.uniform_filter(fill, size=win)
    sq = ndi.uniform_filter(fill * fill, size=win)
    var = np.clip(sq - mean * mean, 0, None)
    out = np.sqrt(var).astype(np.float32)
    out[np.isnan(dem)] = np.nan
    return out


def multiscale_sato(img, sigmas, black_ridges):
    """Per-pixel max of sato responses across `sigmas`. NaN-safe."""
    img = fill_nan_nearest(img).astype(np.float32, copy=False)
    best = np.zeros_like(img, dtype=np.float32)
    for s in sigmas:
        r = sato(img, sigmas=[s], black_ridges=black_ridges,
                 mode="reflect").astype(np.float32)
        best = np.maximum(best, r)
    return best


def structure_tensor_anisotropy(field, sigma=8.0):
    """Coherence/anisotropy of a scalar field. Returns A in [0,1] and the
    major-eigenvector orientation theta in radians.

    A ~ 1 → locally linear (one dominant gradient direction).
    A ~ 0 → isotropic (e.g. plain noise or uniform slope).
    """
    f = fill_nan_nearest(field)
    gy, gx = np.gradient(f)
    Jxx = ndi.gaussian_filter(gx * gx, sigma=sigma)
    Jyy = ndi.gaussian_filter(gy * gy, sigma=sigma)
    Jxy = ndi.gaussian_filter(gx * gy, sigma=sigma)
    trace = Jxx + Jyy
    disc = np.sqrt(np.maximum(0, (Jxx - Jyy) ** 2 / 4.0 + Jxy ** 2))
    lam1 = trace / 2.0 + disc
    lam2 = trace / 2.0 - disc
    A = (lam1 - lam2) / (lam1 + lam2 + 1e-9)
    theta = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)
    return A.astype(np.float32), theta.astype(np.float32)


def density_anomaly(density, sigma_local=2.0, sigma_surround=15.0):
    """Beck-style local-vs-surrounding ground-return density anomaly.

    Smooth the density at a small scale (`sigma_local`) to denoise it, then
    subtract a much larger-scale background. Positive residual = locally
    elevated density = canopy-gap = road candidate."""
    d = density.astype(np.float32, copy=False)
    d = np.where(np.isfinite(d), d, 0)
    loc = ndi.gaussian_filter(d, sigma=sigma_local)
    bg = ndi.gaussian_filter(d, sigma=sigma_surround)
    out = (loc - bg).astype(np.float32)
    return np.clip(out, 0, None)  # only positive (above-surround) anomalies


def asymmetric_bench(lrm, theta, win_perp=5):
    """At each pixel, sample LRM `win_perp` px to each side perpendicular to
    local theta. Strong asymmetric difference (cut above / fill below) → bench.

    Sign-agnostic — returns |d|."""
    f = fill_nan_nearest(lrm)
    nx = -np.sin(theta)
    ny = np.cos(theta)
    H, W = f.shape
    yy, xx = np.indices(f.shape).astype(np.int32)

    def sample(d):
        ys = np.clip(yy + (d * ny).astype(np.int32), 0, H - 1)
        xs = np.clip(xx + (d * nx).astype(np.int32), 0, W - 1)
        return f[ys, xs]

    up = sample(+win_perp)
    dn = sample(-win_perp)
    return np.abs(up - dn).astype(np.float32)


# ===================== normalization =========================================
def robust_norm(r, valid=None, p_lo=75.0, p_hi=99.5):
    """Stretch r to [0,1] using percentiles of its NONZERO interior values."""
    if valid is None:
        sample = r[r > 0]
    else:
        sample = r[valid & (r > 0)]
    if sample.size < 1000:
        return np.zeros_like(r, dtype=np.float32)
    lo = np.percentile(sample, p_lo)
    hi = np.percentile(sample, p_hi)
    if hi <= lo:
        return np.zeros_like(r, dtype=np.float32)
    return np.clip((r - lo) / (hi - lo), 0, 1).astype(np.float32)


# ===================== gap bridging ==========================================
def endpoint_tangent(coords, n=8):
    """Unit tangent at `coords[0]` looking n pixels ahead."""
    if len(coords) < 2:
        return None
    k = min(n, len(coords) - 1)
    v = coords[k].astype(np.float64) - coords[0].astype(np.float64)
    norm = np.hypot(v[0], v[1])
    if norm == 0:
        return None
    return v / norm


def gather_endpoints(skel):
    """Return arrays (Nx2 endpoints, Nx2 tangents). Endpoints are skeleton
    pixels with exactly one 8-connected neighbor."""
    nbr = ndi.convolve(skel.astype(np.uint8),
                       np.ones((3, 3), dtype=np.uint8),
                       mode="constant") - skel.astype(np.uint8)
    ep_mask = skel & (nbr == 1)
    ys, xs = np.where(ep_mask)
    if len(ys) == 0:
        return np.empty((0, 2), int), np.empty((0, 2), float)

    # Estimate tangent per endpoint by walking up to 8 steps along the skeleton.
    H, W = skel.shape
    tangents = np.zeros((len(ys), 2), dtype=np.float64)
    for k in range(len(ys)):
        y0, x0 = ys[k], xs[k]
        path = [(y0, x0)]
        visited = {(y0, x0)}
        cur = (y0, x0)
        for _ in range(8):
            yy, xx = cur
            best = None
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = yy + dy, xx + dx
                    if 0 <= ny < H and 0 <= nx < W and skel[ny, nx] and (ny, nx) not in visited:
                        best = (ny, nx)
                        break
                if best is not None:
                    break
            if best is None:
                break
            visited.add(best)
            path.append(best)
            cur = best
        if len(path) < 2:
            continue
        v = np.array(path[-1]) - np.array(path[0])
        n = np.hypot(v[0], v[1])
        if n > 0:
            tangents[k] = v / n
    return np.stack([ys, xs], axis=1), tangents


def bridge_gaps(mask, score, slope_deg=None, max_grade_deg=12.0,
                max_dist_px=80, max_angle_deg=30,
                cost_ratio_thresh=2.2, valid=None, edge_reject_px=16,
                verbose=True):
    """Cost-surface gap bridging.

    For each endpoint, look along its tangent (+/-max_angle_deg) up to max_dist_px,
    find the best other endpoint, compute the Dijkstra least-cost path through
    cost = (1 - score + ε) in a local window, and accept the bridge if
    (path_cost / euclidean_distance) < cost_ratio_thresh.

    The acceptance condition is critical: it ensures we only bridge through
    high-score (probably-road) material, not across blank terrain.
    """
    skel = skeletonize(mask)
    if skel.sum() == 0:
        return mask, 0

    eps, tans = gather_endpoints(skel)
    if verbose:
        print(f"  endpoints: {len(eps)}", flush=True)
    if len(eps) == 0:
        return mask, 0

    H, W = mask.shape
    cost = (1.05 - score).astype(np.float32)  # >0 everywhere; cheap on roads
    # Beck's max-grade constraint: penalize traversing slopes steeper than
    # the configured maximum road grade. Quadratic above-threshold penalty.
    if slope_deg is not None and max_grade_deg > 0:
        s = np.nan_to_num(slope_deg, nan=0.0).astype(np.float32)
        excess = np.maximum(s - max_grade_deg, 0.0) / max_grade_deg
        cost = cost * (1.0 + excess * excess * 5.0)
    # Forbid bridging through invalid pixels (no-data padding). Otherwise long
    # radial bridges form across the no-data void between tile-edge endpoints.
    if valid is not None:
        cost = np.where(valid, cost, 1e6).astype(np.float32)
    # Identify endpoints that sit near the data boundary — those are tile cutoffs,
    # not real road endpoints, so don't seed bridges from them.
    near_edge = np.zeros_like(mask, dtype=bool)
    if valid is not None and edge_reject_px > 0:
        near_edge = ~ndi.binary_erosion(valid, iterations=edge_reject_px)

    augmented = mask.copy()
    added = 0
    cos_thr = np.cos(np.deg2rad(max_angle_deg))
    used = np.zeros(len(eps), dtype=bool)

    # Sort by index — process all; each endpoint at most one outgoing bridge.
    for i in range(len(eps)):
        if used[i]:
            continue
        p = eps[i]
        t = tans[i]
        if t[0] == 0 and t[1] == 0:
            continue
        # Skip endpoints near data boundary (tile cutoffs)
        if near_edge[p[0], p[1]]:
            continue
        d2 = (eps[:, 0] - p[0]) ** 2 + (eps[:, 1] - p[1]) ** 2
        # Candidates ordered by distance
        order = np.argsort(d2)
        for j in order:
            if j == i or used[j]:
                continue
            d2j = d2[j]
            if d2j < 9:  # already touching
                continue
            d = np.sqrt(d2j)
            if d > max_dist_px:
                break
            q = eps[j]
            v = q - p
            vn = v / (np.hypot(v[0], v[1]) + 1e-9)
            # Tangent at p must point toward q
            if np.dot(t, vn) < cos_thr:
                continue
            # The far endpoint's tangent should point toward p (compatible orientation)
            tq = tans[j]
            if (tq[0] != 0 or tq[1] != 0) and np.dot(-tq, vn) < cos_thr - 0.15:
                continue
            # Local window around the pair
            pad = 8
            ymin = max(0, int(min(p[0], q[0])) - pad)
            ymax = min(H, int(max(p[0], q[0])) + pad + 1)
            xmin = max(0, int(min(p[1], q[1])) - pad)
            xmax = min(W, int(max(p[1], q[1])) + pad + 1)
            local = cost[ymin:ymax, xmin:xmax]
            try:
                path, c = route_through_array(
                    local,
                    (int(p[0] - ymin), int(p[1] - xmin)),
                    (int(q[0] - ymin), int(q[1] - xmin)),
                    fully_connected=True,
                )
            except Exception:
                continue
            # Acceptance: average cost per step
            if c / max(d, 1.0) > cost_ratio_thresh:
                continue
            for (r, cc) in path:
                augmented[r + ymin, cc + xmin] = True
            used[i] = True
            used[j] = True
            added += 1
            break
    return augmented, added


# ===================== vectorize =============================================
def vectorize_mask(mask, transform, crs, score, chan_argmax,
                   min_length_m=20.0, spur_length_m=15.0):
    """Skeletonize → skan graph → polylines with rich attributes.

    Prunes spur branches shorter than `spur_length_m` (degree-1 endpoints
    on short paths) and merges through degree-2 nodes (skan handles this).
    """
    import geopandas as gpd
    from shapely.geometry import LineString
    from skan import Skeleton, summarize

    if mask.sum() == 0:
        return gpd.GeoDataFrame(columns=["length_m", "mean_width_m",
                                         "straightness", "geometry"], crs=crs)

    dist = ndi.distance_transform_edt(mask).astype(np.float32)
    skel = skeletonize(mask)
    if skel.sum() == 0:
        return gpd.GeoDataFrame(columns=["length_m", "mean_width_m",
                                         "straightness", "geometry"], crs=crs)

    sk = Skeleton(skel)
    try:
        summ = summarize(sk, separator="_")
    except TypeError:
        summ = summarize(sk)

    # Detect "spur" paths: those with at least one endpoint of degree 1 in the
    # graph AND shorter than spur_length_m. Drop them from the output.
    # skan summary columns: branch_type (1 = endpoint-to-junction, 2 = j2j, 0 = isolated)
    px = abs(transform.a)
    rows = []
    for i in range(sk.n_paths):
        coords = sk.path_coordinates(i)  # (N, 2) = (rows, cols)
        if len(coords) < 2:
            continue
        rows_idx = coords[:, 0].astype(np.int32)
        cols_idx = coords[:, 1].astype(np.int32)
        # Euclidean length in pixels
        diffs = np.diff(coords, axis=0)
        plen_px = float(np.sum(np.hypot(diffs[:, 0], diffs[:, 1])))
        length_m = plen_px * px

        if length_m < min_length_m:
            continue

        # Spur filter (junction-endpoint with very short length)
        btype = int(summ["branch_type"].iat[i]) if "branch_type" in summ.columns else 2
        if btype == 1 and length_m < spur_length_m:
            continue

        xs, ys = xy(transform, rows_idx, cols_idx, offset="center")
        xs = np.asarray(xs); ys = np.asarray(ys)
        ls = LineString(list(zip(xs.tolist(), ys.tolist())))
        chord = float(np.hypot(xs[-1] - xs[0], ys[-1] - ys[0]))
        straight = chord / max(length_m, 1e-6)
        widths = dist[rows_idx, cols_idx] * 2.0 * px
        mean_w = float(np.mean(widths))
        # Dominant channel by mode along the path
        ch_along = chan_argmax[rows_idx, cols_idx]
        if ch_along.size:
            vals, counts = np.unique(ch_along, return_counts=True)
            dom = int(vals[int(np.argmax(counts))])
        else:
            dom = 0
        score_mean = float(np.mean(score[rows_idx, cols_idx]))

        rows.append(dict(
            length_m=length_m,
            mean_width_m=mean_w,
            straightness=straight,
            score_mean=score_mean,
            dom_channel=CHANNEL_NAMES[dom] if 0 <= dom < len(CHANNEL_NAMES) else "?",
            geometry=ls,
        ))

    if not rows:
        return gpd.GeoDataFrame(columns=["length_m", "mean_width_m",
                                         "straightness", "geometry"], crs=crs)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)


# ===================== main ==================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True, help="suffix, e.g. mkf, mk5, 9t")
    ap.add_argument("--bbox", nargs=4, type=float, default=None,
                    metavar=("MINX", "MINY", "MAXX", "MAXY"))
    ap.add_argument("--score-thresh", type=float, default=0.40)
    ap.add_argument("--min-length-m", type=float, default=25.0)
    ap.add_argument("--spur-length-m", type=float, default=15.0)
    ap.add_argument("--max-width-m", type=float, default=15.0)
    ap.add_argument("--min-straightness", type=float, default=0.30)
    ap.add_argument("--bridge-dist-m", type=float, default=80.0)
    ap.add_argument("--max-grade-deg", type=float, default=12.0,
                    help="max road grade (deg) for gap-bridge cost (Beck)")
    ap.add_argument("--no-bridge", action="store_true")
    ap.add_argument("--debug-channels", action="store_true")
    args = ap.parse_args()

    suf = args.tile
    dem_p   = DERIV / f"dem_{suf}_1m.tif"
    slope_p = DERIV / f"slope_{suf}_1m.tif"
    lrm5_p  = DERIV / f"lrm_5_{suf}_1m.tif"
    chm_p   = DERIV / f"chm_{suf}_1m.tif"
    gden_p  = DERIV / f"ground_density_{suf}_1m.tif"
    for p in (dem_p, slope_p, lrm5_p):
        if not p.exists():
            raise FileNotFoundError(p)
    have_chm = chm_p.exists()
    have_gden = gden_p.exists()

    window = None
    if args.bbox:
        with rasterio.open(dem_p) as ds:
            window = from_bounds(*args.bbox,
                                 transform=ds.transform).round_offsets().round_lengths()

    print(f"[1/6] Loading rasters (tile={suf}, window={window})...", flush=True)
    dem, transform, crs = read_raster(dem_p, window=window)
    slope, _, _ = read_raster(slope_p, window=window)
    lrm5, _, _ = read_raster(lrm5_p, window=window)
    chm = None
    gden = None
    if have_chm:
        chm, _, _ = read_raster(chm_p, window=window)
        # CHM has sensor outliers up to ~kilometers; clamp to a sane range
        chm = np.clip(np.nan_to_num(chm, nan=0.0), 0.0, 50.0).astype(np.float32)
    if have_gden:
        gden_raw, _, _ = read_raster(gden_p, window=window)
        gden = np.nan_to_num(gden_raw, nan=0.0).astype(np.float32)
    print(f"  shape={dem.shape}  crs={crs}  px={abs(transform.a):.2f} m  "
          f"chm={'yes' if have_chm else 'no'}  density={'yes' if have_gden else 'no'}",
          flush=True)

    valid_full = ~np.isnan(dem)
    valid = ndi.binary_erosion(valid_full, iterations=8)

    print("[2/6] Building feature channels...", flush=True)
    t0 = time.time()
    print("  * LRM_15 (wide)", flush=True)
    lrm15 = lrm_at(dem, sigma_px=15.0)
    print("  * roughness (3x3 sigma)", flush=True)
    rough = roughness_map(dem, win=3)
    print("  * sato on LRM_5  (narrow, both polarities)", flush=True)
    s_ld = multiscale_sato(lrm5,  [1.0, 1.5, 2.5, 4.0], black_ridges=True)
    s_lb = multiscale_sato(lrm5,  [1.0, 1.5, 2.5, 4.0], black_ridges=False)
    print("  * sato on LRM_15 (wide, both polarities)", flush=True)
    s_wd = multiscale_sato(lrm15, [3.0, 5.0, 8.0],      black_ridges=True)
    s_wb = multiscale_sato(lrm15, [3.0, 5.0, 8.0],      black_ridges=False)
    print("  * sato on roughness (smooth strips)", flush=True)
    s_rs = multiscale_sato(rough, [1.5, 2.5, 4.0],      black_ridges=True)
    if chm is not None:
        print("  * sato on CHM (canopy-gap linearity)", flush=True)
        s_cg = multiscale_sato(chm, [1.5, 2.5, 4.0, 6.0], black_ridges=True)
    else:
        s_cg = np.zeros_like(s_rs)
    if gden is not None:
        print("  * density anomaly + sato (Beck-style)", flush=True)
        dens_anom = density_anomaly(gden, sigma_local=2.0, sigma_surround=15.0)
        s_ds = multiscale_sato(dens_anom, [1.5, 2.5, 4.0], black_ridges=False)
    else:
        s_ds = np.zeros_like(s_rs)
    print("  * structure-tensor anisotropy of slope", flush=True)
    aniso, theta = structure_tensor_anisotropy(np.nan_to_num(slope, nan=0.0), sigma=8.0)
    print("  * asymmetric cut-fill bench", flush=True)
    bench = asymmetric_bench(lrm5, theta, win_perp=5)
    print(f"  features in {time.time()-t0:.1f}s", flush=True)

    # zero everything outside the eroded interior
    for arr in (s_ld, s_lb, s_wd, s_wb, s_rs, s_cg, s_ds, aniso, bench):
        arr[~valid] = 0

    print("[3/6] Normalizing + fusing channels...", flush=True)
    n_ld = robust_norm(s_ld, valid=valid)
    n_lb = robust_norm(s_lb, valid=valid)
    n_wd = robust_norm(s_wd, valid=valid)
    n_wb = robust_norm(s_wb, valid=valid)
    n_rs = robust_norm(s_rs, valid=valid)
    n_cg = robust_norm(s_cg, valid=valid) if chm is not None else np.zeros_like(s_rs)
    n_ds = robust_norm(s_ds, valid=valid) if gden is not None else np.zeros_like(s_rs)
    n_an = robust_norm(aniso, valid=valid)
    n_be = robust_norm(bench, valid=valid)

    chan_stack = np.stack([n_ld, n_lb, n_wd, n_wb, n_rs, n_cg, n_ds], axis=0)
    ridge_max = chan_stack.max(axis=0)
    chan_argmax = chan_stack.argmax(axis=0).astype(np.uint8)
    chan_argmax[~valid] = 0

    # Beck-style consensus boost: if BOTH the canopy-gap and density channels
    # agree at a pixel, it's almost certainly a road through forest. Multiply
    # the ridge response by a small consensus bonus.
    consensus = np.minimum(n_cg, n_ds) if (chm is not None and gden is not None) else 0
    score = ridge_max * (1.0 + 0.30 * n_be + 0.20 * n_an + 0.30 * consensus)
    score = np.clip(score, 0, 1).astype(np.float32)
    score[~valid] = 0

    if args.debug_channels:
        sfx = suf if args.bbox is None else f"{suf}_sub"
        dbg = OUT_DIR / "channels"
        dbg.mkdir(exist_ok=True)
        for name, arr in zip(
            ["lrm5_dark", "lrm5_bright", "lrm15_dark", "lrm15_bright",
             "rough_strip", "canopy_gap", "density_strip",
             "aniso", "bench", "ridge_max", "score_final"],
            [n_ld, n_lb, n_wd, n_wb, n_rs, n_cg, n_ds,
             n_an, n_be, ridge_max, score]
        ):
            write_raster(arr, dbg / f"ch_{name}_{sfx}.tif", transform, crs)
        print(f"  wrote per-channel rasters to {dbg}/", flush=True)

    print(f"[4/6] Thresholding (>= {args.score_thresh}) + cleanup...", flush=True)
    mask = score >= args.score_thresh
    mask = binary_closing(mask, footprint=disk(1))
    mask = remove_small_objects(mask, min_size=30)
    print(f"  mask coverage: {mask.mean()*100:.2f}%", flush=True)

    if not args.no_bridge:
        print(f"[5/6] Cost-surface gap bridging "
              f"(R={args.bridge_dist_m} m, +/-30°)...", flush=True)
        t0 = time.time()
        mask, n_b = bridge_gaps(mask, score, slope_deg=slope,
                                max_grade_deg=args.max_grade_deg,
                                max_dist_px=int(args.bridge_dist_m),
                                max_angle_deg=30,
                                cost_ratio_thresh=2.2,
                                valid=valid, edge_reject_px=16)
        mask = binary_closing(mask, footprint=disk(1))
        print(f"  bridges added: {n_b}  ({time.time()-t0:.1f}s)", flush=True)
    else:
        print("[5/6] (bridging skipped)", flush=True)

    print("[6/6] Skeletonizing + vectorizing...", flush=True)
    gdf = vectorize_mask(mask, transform, crs, score, chan_argmax,
                         min_length_m=args.min_length_m,
                         spur_length_m=args.spur_length_m)
    print(f"  raw polylines: {len(gdf)}", flush=True)
    if len(gdf):
        keep = (
            (gdf["mean_width_m"] <= args.max_width_m) &
            (gdf["straightness"] >= args.min_straightness)
        )
        gdf = gdf[keep].reset_index(drop=True)
        print(f"  after width/straightness filter: {len(gdf)}", flush=True)

    # ---- outputs ----
    sfx = suf if args.bbox is None else f"{suf}_sub"
    out_score = OUT_DIR / f"road_score_{sfx}.tif"
    out_mask  = OUT_DIR / f"road_mask_{sfx}.tif"
    out_gpkg  = OUT_DIR / f"roads_{sfx}.gpkg"

    write_raster(score, out_score, transform, crs, "float32")
    write_raster(mask.astype(np.uint8), out_mask, transform, crs, "uint8")
    if len(gdf):
        gdf.to_file(out_gpkg, layer="centerlines", driver="GPKG")
        print(f"\n=== Summary ===")
        print(f"  centerlines: {len(gdf)}")
        print(f"  total length: {gdf['length_m'].sum()/1000:.2f} km")
        print(f"  length (m)  min/med/max: "
              f"{gdf['length_m'].min():.1f} / {gdf['length_m'].median():.1f} / "
              f"{gdf['length_m'].max():.1f}")
        print(f"  width  (m)  min/med/max: "
              f"{gdf['mean_width_m'].min():.1f} / {gdf['mean_width_m'].median():.1f} / "
              f"{gdf['mean_width_m'].max():.1f}")
        print(f"  dominant-channel counts: "
              f"{gdf['dom_channel'].value_counts().to_dict()}")

    # ---- QA overlay PNG ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        hs_p = DERIV / f"hillshade_{suf}_1m.tif"
        if hs_p.exists():
            hs, _, _ = read_raster(hs_p, window=window)
            ext = [transform.c,
                   transform.c + score.shape[1] * abs(transform.a),
                   transform.f + score.shape[0] * transform.e,
                   transform.f]
            fig, ax = plt.subplots(1, 1, figsize=(14, 14), dpi=120)
            ax.imshow(hs, cmap="gray", extent=ext, interpolation="nearest")
            if len(gdf):
                # color by dominant channel
                colors = {
                    "lrm5_dark":     "#e41a1c",  # red
                    "lrm5_bright":   "#ff7f00",  # orange
                    "lrm15_dark":    "#984ea3",  # purple
                    "lrm15_bright":  "#a65628",  # brown
                    "rough_strip":   "#4daf4a",  # green
                    "canopy_gap":    "#00ced1",  # cyan
                    "density_strip": "#ffd700",  # gold
                }
                for ch, sub in gdf.groupby("dom_channel"):
                    c = colors.get(ch, "yellow")
                    for ls in sub.geometry:
                        x, y = ls.xy
                        ax.plot(x, y, color=c, linewidth=0.9, alpha=0.95)
                # legend
                from matplotlib.lines import Line2D
                handles = [Line2D([0], [0], color=col, lw=2, label=k)
                           for k, col in colors.items() if k in gdf["dom_channel"].values]
                ax.legend(handles=handles, loc="lower right",
                          framealpha=0.85, fontsize=9)
            ax.set_title(f"Linear features (v2) — {sfx}  "
                         f"n={len(gdf)}  {gdf['length_m'].sum()/1000 if len(gdf) else 0:.1f} km")
            ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
            ax.set_aspect("equal")
            png_p = OUT_DIR / f"roads_overlay_{sfx}.png"
            fig.savefig(png_p, bbox_inches="tight")
            plt.close(fig)
            print(f"  overlay: {png_p}", flush=True)
    except Exception as e:
        print(f"  overlay skipped: {e}", flush=True)

    print(f"\nWrote:\n  {out_score}\n  {out_mask}\n  "
          f"{out_gpkg if len(gdf) else '(no gpkg — empty)'}")


if __name__ == "__main__":
    main()
