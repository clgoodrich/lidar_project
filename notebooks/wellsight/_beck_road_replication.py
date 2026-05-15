"""Beck et al. 2015 forest-road extraction — faithful replication on the 9t tile.

Paper: Beck, Olsen, Sessions, Wing (2015) "Automated Extraction of Forest Road
Network Geometry from Aerial LiDAR", Eur. J. Forest Eng. 1(1):21-33.

Two attributes drive the paper:
  (1) per-cell mean intensity of ground returns — varies with surface material
  (2) per-cell ground-return density — higher under canopy gaps (i.e. roads)

Beck filters individual ground points by per-canopy-type intensity ranges
(Table 1), removes noise/isolated points, gridifies, density-thresholds at 20
returns/cell, and finally runs a recursive shortest-path "connection routine"
to bridge gaps with a max-road-grade constraint.

We collapse the point-domain operations to cell-domain operations on our 1 m
rasters (which were built from the same LAZ).

Calibration: the paper's Table 1 intensity values are sensor-specific to the
Watershed Sciences 2008 Oregon flight and won't transfer. We use Beck's
PROCESS but auto-calibrate the per-canopy ranges from the PA 2019 data by
sampling intensity inside high-density-anomaly pixels (where canopy gaps —
likely roads/clearings — concentrate).
"""
import argparse
import time
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.transform import xy
from scipy import ndimage as ndi
from shapely.geometry import LineString
from skimage.graph import route_through_array
from skimage.morphology import (
    binary_closing, binary_opening, remove_small_objects,
    skeletonize, disk
)

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
DERIV = ROOT / "data" / "derivatives"

# Beck's canopy classes (paper §2.1). We define them by CHM in meters.
CHM_CLEARCUT_MAX = 1.0
CHM_YOUNG_MIN, CHM_YOUNG_MAX = 5.0, 15.0
CHM_MATURE_MIN = 15.0

# Paper hyperparameters (Beck §2.1, Figure 2)
MIN_DENSITY = 1.5         # In per-pass-normalized units (median=1.0), 1.5
                          # selects cells where the best flight pass measured
                          # >=1.5x its median per-pass density — i.e. clear
                          # canopy openings invariant to which pass scanned
                          # nadir there. Beck's intent, sensor-geometry-clean.
MAX_GRADE_DEG = 12.0      # paper's max road grade (user-supplied; 10-12° typical)
ISOLATION_MIN_SIZE = 100  # cells; drop connected components smaller than this


# ===================== IO ====================================================
def read_raster(path):
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None:
            a = np.where(a == nd, np.nan, a)
        return a, ds.transform, ds.crs


def write_raster(arr, path, transform, crs, dtype="float32", nd=None):
    profile = dict(
        driver="GTiff", height=arr.shape[0], width=arr.shape[1],
        count=1, dtype=dtype, crs=crs, transform=transform,
        compress="deflate", predictor=2, tiled=True,
        blockxsize=512, blockysize=512,
    )
    if nd is not None:
        profile["nodata"] = nd
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(arr.astype(dtype), 1)


# ===================== Beck steps ============================================
def canopy_classes(chm):
    """1 = clearcut, 2 = young, 3 = mature, 0 = transitional (ambiguous)."""
    c = np.zeros(chm.shape, dtype=np.uint8)
    c[chm < CHM_CLEARCUT_MAX] = 1
    c[(chm >= CHM_YOUNG_MIN) & (chm <= CHM_YOUNG_MAX)] = 2
    c[chm > CHM_MATURE_MIN] = 3
    return c


def density_anomaly(density, sigma_local=2.0, sigma_surround=15.0):
    """Local-vs-surrounding density. Positive = elevated (canopy gap)."""
    d = np.nan_to_num(density, nan=0.0).astype(np.float32)
    loc = ndi.gaussian_filter(d, sigma=sigma_local)
    bg = ndi.gaussian_filter(d, sigma=sigma_surround)
    return np.clip(loc - bg, 0, None).astype(np.float32)


def calibrate_intensity_ranges(intensity, canopy, density, density_anom, chm, valid,
                               low_pct=25.0, high_pct=75.0):
    """For each canopy class, find the intensity range where strong
    road-candidate pixels concentrate. Seed criteria are class-specific to
    match Beck's logic:
      - clearcut: very high local density (canopy already absent)
      - young/mature: high density anomaly AND locally-low CHM (= canopy gap)

    Returns dict {class: (lo, hi)} of intensity range.

    We tighten percentile bounds (p25-p75 instead of p10-p90) so the
    accepted range tracks the road peak rather than the entire seed
    distribution."""
    chm_loc = ndi.uniform_filter(chm.astype(np.float32), size=51)  # 50 m window
    chm_gap = (chm + 0.1) / (chm_loc + 0.1)  # <1 = locally lower than neighborhood

    # Seed from per-pass-normalized density — values >= 1.8 mean the best
    # pass at this cell saw 80%-above-median ground returns, i.e. clearly
    # open canopy. Threshold is geometry-invariant unlike raw counts.
    seeds = {
        1: valid & (canopy == 1) & (density >= 1.6),
        2: valid & (canopy == 2) & (density >= 1.8),
        3: valid & (canopy == 3) & (density >= 1.8),
    }
    out = {}
    for c, name in [(1, "clearcut"), (2, "young"), (3, "mature")]:
        mask = seeds[c]
        n = int(mask.sum())
        if n < 200:
            print(f"  {name:9s}: only {n} seed pixels — SKIPPED", flush=True)
            out[c] = None
            continue
        sample = intensity[mask]
        lo = float(np.percentile(sample, low_pct))
        hi = float(np.percentile(sample, high_pct))
        med = float(np.median(sample))
        print(f"  {name:9s}: seed n={n:7d}  intensity p25/p50/p75 = "
              f"{lo:.0f} / {med:.0f} / {hi:.0f}", flush=True)
        out[c] = (lo, hi)
    return out


def build_initial_rl(intensity, canopy, ranges):
    """Beck Step 1: RL = pixels whose intensity falls in the per-canopy
    acceptable range."""
    rl = np.zeros(intensity.shape, dtype=bool)
    for c, rng in ranges.items():
        if rng is None:
            continue
        lo, hi = rng
        rl |= (canopy == c) & (intensity >= lo) & (intensity <= hi)
    return rl


def beck_noise_cleanup(rl):
    """Beck Steps 2-3: small-radius RL-neighbor support.
       Step 2: keep RL cells with >=2 RL neighbors in 3x3 (paper: 0.78 m radius)
       Step 3: keep RL cells with >=5 RL neighbors in 5x5 (paper intermediate)
    """
    n3 = ndi.convolve(rl.astype(np.uint8), np.ones((3, 3), np.uint8),
                      mode="constant") - rl.astype(np.uint8)
    rl = rl & (n3 >= 2)
    n5 = ndi.convolve(rl.astype(np.uint8), np.ones((5, 5), np.uint8),
                      mode="constant") - rl.astype(np.uint8)
    rl = rl & (n5 >= 5)
    return rl


def beck_isolation_cleanup(rl, radius_px=11, min_count=15):
    """Beck Step 4: require RL support at the larger radius (~10.67 m).
    Implemented via a circular convolution on the binary RL mask."""
    se = disk(radius_px)
    cnt = ndi.convolve(rl.astype(np.uint16), se.astype(np.uint16),
                       mode="constant")
    return rl & (cnt >= min_count)


def density_threshold(rl, density, min_density=MIN_DENSITY):
    """Beck Step 6 — adapted for PA 2019 D20.

    `density` arrives per-pass-normalized (median=1.0, see _build_density_
    persource_9t.py). Residual within-pass nadir gradients remain. Apply a
    LOCAL anomaly (small surround) so we keep only sharp road-scale density
    elevations and ignore the broad nadir/edge gradient of each flight pass.
    """
    d_smooth = ndi.uniform_filter(density.astype(np.float32), size=3)
    anom = density_anomaly(d_smooth, sigma_local=1.5, sigma_surround=20.0)
    # Combine: must be elevated in absolute (Beck's intent) AND show local anomaly
    return rl & (d_smooth >= min_density) & (anom > 0.15)


def connection_routine(rl, slope_deg, max_grade_deg=MAX_GRADE_DEG,
                       max_bridge_dist_px=80, max_components_bridged=2000,
                       verbose=True):
    """Beck Step 7 — paper's recursive shortest-path connection routine.

    Reimagined for rasters: build a slope-penalized cost surface, find
    connected components of the RL mask, and for each component endpoint,
    try a cost-surface shortest-path to other endpoints (max_dist).

    Slope penalty enforces the max-grade constraint."""
    s = np.nan_to_num(slope_deg, nan=0.0).astype(np.float32)
    # Make staying in RL cheap (0.1) and outside expensive (1.0+) with extra
    # slope penalty above max_grade_deg.
    cost = np.where(rl, 0.1, 1.0).astype(np.float32)
    excess = np.maximum(s - max_grade_deg, 0.0) / max_grade_deg
    cost = cost * (1.0 + excess * excess * 5.0)

    # Find connected components and their pixel locations
    lab, n = ndi.label(rl, structure=np.ones((3, 3), dtype=np.uint8))
    if verbose:
        print(f"  {n} RL components before bridging", flush=True)

    # Get a representative coordinate per component (centroid-ish)
    if n == 0:
        return rl, 0
    locs = ndi.center_of_mass(rl, lab, index=np.arange(1, n + 1))
    locs = np.array([(int(r), int(c)) for r, c in locs])

    # Sort components by size, only attempt to bridge the largest M
    sizes = np.bincount(lab.ravel())[1:]
    order = np.argsort(-sizes)[:max_components_bridged]
    bridged = rl.copy()
    n_bridges = 0
    H, W = rl.shape

    for i, ci in enumerate(order):
        p = locs[ci]
        # Bridge to nearest larger component within max_bridge_dist_px
        d2 = ((locs[:, 0] - p[0]) ** 2 + (locs[:, 1] - p[1]) ** 2).astype(np.float64)
        cand_order = np.argsort(d2)
        for cj in cand_order:
            if cj == ci:
                continue
            d = np.sqrt(d2[cj])
            if d < 3:
                continue
            if d > max_bridge_dist_px:
                break
            q = locs[cj]
            # Local window
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
            # Acceptance: average cost-per-step low → real road material
            if c / max(d, 1.0) > 0.6:
                continue
            for (rr, cc) in path:
                bridged[rr + ymin, cc + xmin] = True
            n_bridges += 1
            break
    if verbose:
        print(f"  bridges added: {n_bridges}", flush=True)
    return bridged, n_bridges


def vectorize(rl_mask, transform):
    """Skeletonize and return polylines in world coords."""
    if rl_mask.sum() == 0:
        return gpd.GeoDataFrame(columns=["length_m", "geometry"])
    from skan import Skeleton, summarize
    skel = skeletonize(rl_mask)
    if skel.sum() == 0:
        return gpd.GeoDataFrame(columns=["length_m", "geometry"])
    sk = Skeleton(skel)
    try:
        _ = summarize(sk, separator="_")
    except TypeError:
        _ = summarize(sk)
    px = abs(transform.a)
    rows = []
    for i in range(sk.n_paths):
        coords = sk.path_coordinates(i)
        if len(coords) < 2:
            continue
        diffs = np.diff(coords, axis=0)
        plen = float(np.sum(np.hypot(diffs[:, 0], diffs[:, 1]))) * px
        if plen < 20.0:
            continue
        xs, ys = xy(transform, coords[:, 0].astype(int), coords[:, 1].astype(int),
                    offset="center")
        ls = LineString(list(zip(np.asarray(xs).tolist(), np.asarray(ys).tolist())))
        rows.append(dict(length_m=plen, geometry=ls))
    return gpd.GeoDataFrame(rows, geometry="geometry")


# ===================== main ==================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", default="9t",
                    help="suffix used for raster filenames, e.g. 9t / mkf")
    args = ap.parse_args()
    TILE = args.tile

    OUT_DIR = DERIV / f"beck_{TILE}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=== Beck 2015 replication on {TILE} ===", flush=True)

    print("[1] Loading rasters...", flush=True)
    # Prefer the per-tile z-scored intensity (removes flight-line / tile-edge
    # calibration discontinuities). Fall back to raw if not present.
    iz = DERIV / f"intensity_zscore_{TILE}_1m.tif"
    ir = DERIV / f"intensity_ground_{TILE}_1m.tif"
    intensity_path = iz if iz.exists() else ir
    print(f"  intensity from: {intensity_path.name}")
    intensity, transform, crs = read_raster(intensity_path)
    # Density preference order:
    #  1. per-PointSourceId-normalized MAX (kills flight-pass nadir-edge artifacts)
    #  2. no-overlap raw density
    #  3. original (with overlap)
    dp = DERIV / f"ground_density_persource_{TILE}_1m.tif"
    dn = DERIV / f"ground_density_noverlap_{TILE}_1m.tif"
    dr = DERIV / f"ground_density_{TILE}_1m.tif"
    density_path = next(p for p in (dp, dn, dr) if p.exists())
    print(f"  density from:   {density_path.name}")
    density, _, _ = read_raster(density_path)
    chm,     _, _ = read_raster(DERIV / f"chm_{TILE}_1m.tif")
    slope,   _, _ = read_raster(DERIV / f"slope_{TILE}_1m.tif")
    dem,     _, _ = read_raster(DERIV / f"dem_{TILE}_1m.tif")

    chm = np.clip(np.nan_to_num(chm, nan=0.0), 0, 50.0)
    density = np.nan_to_num(density, nan=0.0)
    valid = ~np.isnan(dem) & ~np.isnan(intensity)
    print(f"  shape={intensity.shape}  valid={valid.mean()*100:.1f}%", flush=True)

    print("[2] Canopy classes from CHM...", flush=True)
    canopy = canopy_classes(chm)
    for c, name in [(1, "clearcut"), (2, "young"), (3, "mature"), (0, "transitional")]:
        n = int(((canopy == c) & valid).sum())
        print(f"  {name:13s}: {n:9,d} cells ({n/max(valid.sum(),1)*100:.1f}%)", flush=True)

    print("[3] Calibrating per-canopy intensity ranges via density anomaly...", flush=True)
    dens_anom = density_anomaly(density, sigma_local=2.0, sigma_surround=15.0)
    ranges = calibrate_intensity_ranges(intensity, canopy, density, dens_anom,
                                        chm, valid)

    print("[4] Step 1 - initial Roaded List from intensity ranges...", flush=True)
    rl0 = build_initial_rl(intensity, canopy, ranges) & valid
    print(f"  initial RL pixels: {rl0.sum():,} ({rl0.mean()*100:.2f}%)", flush=True)

    print("[5] Steps 2-3 - Beck noise/support cleanup...", flush=True)
    rl1 = beck_noise_cleanup(rl0)
    print(f"  after 3x3 + 5x5 support: {rl1.sum():,}", flush=True)

    print("[6] Step 4 - Beck isolation cleanup (10.67 m disk)...", flush=True)
    rl2 = beck_isolation_cleanup(rl1, radius_px=11, min_count=15)
    print(f"  after 11 px disk: {rl2.sum():,}", flush=True)

    print(f"[7] Step 6 - density >= {MIN_DENSITY} returns/cell...", flush=True)
    rl3 = density_threshold(rl2, density, min_density=MIN_DENSITY)
    print(f"  after density gate: {rl3.sum():,}", flush=True)

    print(f"[8] Step 4 (component) - drop components < {ISOLATION_MIN_SIZE} cells...", flush=True)
    rl4 = remove_small_objects(rl3, min_size=ISOLATION_MIN_SIZE)
    print(f"  after small-component removal: {rl4.sum():,}", flush=True)

    print("[9] Step 7 - slope-constrained connection routine...", flush=True)
    t0 = time.time()
    rl5, n_bridges = connection_routine(rl4, slope,
                                        max_grade_deg=MAX_GRADE_DEG,
                                        max_bridge_dist_px=60)
    rl5 = binary_closing(rl5, footprint=disk(1))
    print(f"  after bridging + closing: {rl5.sum():,}  ({time.time()-t0:.1f}s)",
          flush=True)

    print("[10] Vectorizing roaded list to centerlines...", flush=True)
    g = vectorize(rl5, transform)
    if len(g):
        g.crs = crs
        print(f"  centerlines: {len(g)}  total {g['length_m'].sum()/1000:.2f} km", flush=True)

    # ---- outputs ----
    write_raster(rl5.astype(np.uint8), OUT_DIR / f"beck_rl_{TILE}.tif",
                 transform, crs, dtype="uint8")
    write_raster(canopy, OUT_DIR / f"canopy_class_{TILE}.tif",
                 transform, crs, dtype="uint8")
    if len(g):
        g.to_file(OUT_DIR / f"beck_centerlines_{TILE}.gpkg",
                  layer="centerlines", driver="GPKG")

    # ---- QA overlay PNG ----
    try:
        hs_p = DERIV / f"hillshade_{TILE}_1m.tif"
        hs, _, _ = read_raster(hs_p)
        ext = [transform.c, transform.c + rl5.shape[1] * abs(transform.a),
               transform.f + rl5.shape[0] * transform.e, transform.f]
        fig, ax = plt.subplots(1, 1, figsize=(12, 12), dpi=130)
        ax.imshow(hs, cmap="gray", extent=ext, interpolation="nearest")
        # Faint RL mask overlay
        rl_show = np.ma.masked_where(~rl5, np.ones_like(rl5, dtype=np.uint8))
        ax.imshow(rl_show, cmap="autumn", alpha=0.35, extent=ext, interpolation="nearest")
        if len(g):
            for ls in g.geometry:
                x, y = ls.xy
                ax.plot(x, y, color="red", linewidth=0.9, alpha=0.95)
        ax.set_title(f"Beck 2015 replication — {TILE}  "
                     f"(n={len(g)}, {g['length_m'].sum()/1000 if len(g) else 0:.2f} km)")
        ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
        ax.set_aspect("equal")
        fig.savefig(OUT_DIR / f"beck_overlay_{TILE}.png", bbox_inches="tight")
        plt.close(fig)
    except Exception as e:
        print(f"  overlay skipped: {e}", flush=True)

    print(f"\nWrote outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
