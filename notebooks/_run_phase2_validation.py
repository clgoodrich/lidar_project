"""
Phase 2 — Validation framework.

For each feature-type layer, tests whether wells cluster near candidates at
rates above a covariate-matched null. Runs two independent test statistics:

  1. Nearest-candidate distance CDF — for each well, distance to the nearest
     candidate. Compared against the same quantity under a stratified null.
  2. Candidate count within search radii (50/100/150/200 m) per well —
     vs null mean, reported as enrichment ratio + empirical p-value.

Null model: draw background points with the same slope-class × HAND-class
joint distribution as the real wells. This is the simplest honest null — it
ensures the comparison isn't dominated by "wells tend to be on gentle slopes,
and candidates tend to be on gentle slopes, so they co-occur." Land cover
stratification is a TODO pending NLCD data.

Positive control: GPS-quality DEP wells — TODO, requires DEP dataset.
Negative control: well coordinates randomly offset by 500 m.
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from shapely.geometry import Point, box
from shapely.strtree import STRtree

ROOT = Path(r"C:/Users/colto/Documents/GitHub/lidar_project")
DATA = ROOT / "data"
SUB = DATA / "derivatives" / "subarea"
WELLS_PATH = DATA / "wells_with_features.shp"

SUB_BBOX = (619500.0, 4594000.0, 624500.0, 4599000.0)
TARGET_CRS = "EPSG:26917"

SEED = 42
rng = np.random.default_rng(SEED)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ───────────────────────────────────────────────────────────────────────────
# Load wells inside subarea
# ───────────────────────────────────────────────────────────────────────────
wells_all = gpd.read_file(WELLS_PATH).to_crs(TARGET_CRS)
sub_poly = box(*SUB_BBOX)
wells = wells_all[wells_all.geometry.within(sub_poly)].copy().reset_index(drop=True)
log(f"{len(wells)} wells in calibration subarea")

# ───────────────────────────────────────────────────────────────────────────
# Stratification rasters (slope + HAND)
# ───────────────────────────────────────────────────────────────────────────
def _read_raster(path):
    with rasterio.open(path) as s:
        d = s.read(1).astype("float32")
        nd = s.nodata
        t = s.transform
    if nd is not None:
        d[d == nd] = np.nan
    return d, t


SLOPE_ARR, RASTER_T = _read_raster(SUB / "slope.tif")
HAND_ARR, _ = _read_raster(SUB / "hand.tif")

def sample_at(arr, xs, ys, transform):
    """Nearest-pixel sample of a raster at each (x, y) coordinate."""
    inv = ~transform
    cols, rows = inv * (xs, ys)
    rows = np.round(rows).astype(int)
    cols = np.round(cols).astype(int)
    out = np.full(len(xs), np.nan, dtype="float32")
    valid = (rows >= 0) & (rows < arr.shape[0]) & (cols >= 0) & (cols < arr.shape[1])
    out[valid] = arr[rows[valid], cols[valid]]
    return out


wells["slope"] = sample_at(SLOPE_ARR, wells.geometry.x.values, wells.geometry.y.values, RASTER_T)
wells["hand"]  = sample_at(HAND_ARR,  wells.geometry.x.values, wells.geometry.y.values, RASTER_T)


# ───────────────────────────────────────────────────────────────────────────
# Covariate-matched null: draw n background points with same
# (slope_class, HAND_class) joint distribution as the wells.
# ───────────────────────────────────────────────────────────────────────────
SLOPE_BINS = np.array([0, 2, 5, 10, 15, 25, 45, 90])
HAND_BINS  = np.array([0, 1, 3, 5, 10, 20, 100, 1e6])

def _bin_label(values, bins):
    return np.clip(np.digitize(values, bins) - 1, 0, len(bins) - 2)

wells["slope_bin"] = _bin_label(wells["slope"].fillna(0).values, SLOPE_BINS)
wells["hand_bin"]  = _bin_label(wells["hand"].fillna(0).values,  HAND_BINS)

def draw_background(n_total: int, seed: int = SEED) -> gpd.GeoDataFrame:
    """Stratified rejection sampling: sample uniformly from the subarea, bin
    each candidate, then draw from each bin to match the well distribution."""
    local_rng = np.random.default_rng(seed)

    # Target counts per (slope_bin, hand_bin) cell
    target = (wells.groupby(["slope_bin", "hand_bin"]).size() /
              len(wells) * n_total).round().astype(int)
    target = target[target > 0]

    # Over-sample to make rejection sampling fast
    oversample = max(20 * n_total, 200_000)
    xs = local_rng.uniform(SUB_BBOX[0], SUB_BBOX[2], size=oversample)
    ys = local_rng.uniform(SUB_BBOX[1], SUB_BBOX[3], size=oversample)
    s_vals = sample_at(SLOPE_ARR, xs, ys, RASTER_T)
    h_vals = sample_at(HAND_ARR, xs, ys, RASTER_T)
    valid = ~(np.isnan(s_vals) | np.isnan(h_vals))
    xs, ys, s_vals, h_vals = xs[valid], ys[valid], s_vals[valid], h_vals[valid]
    sb = _bin_label(s_vals, SLOPE_BINS)
    hb = _bin_label(h_vals, HAND_BINS)

    picked_x, picked_y = [], []
    for (s_target_bin, h_target_bin), k in target.items():
        mask = (sb == s_target_bin) & (hb == h_target_bin)
        avail = np.where(mask)[0]
        if len(avail) == 0:
            continue
        if len(avail) >= k:
            picks = local_rng.choice(avail, size=k, replace=False)
        else:
            picks = local_rng.choice(avail, size=k, replace=True)
        picked_x.extend(xs[picks])
        picked_y.extend(ys[picks])

    bg = gpd.GeoDataFrame(
        geometry=[Point(x, y) for x, y in zip(picked_x, picked_y)],
        crs=TARGET_CRS,
    )
    return bg


# ───────────────────────────────────────────────────────────────────────────
# Association statistics
# ───────────────────────────────────────────────────────────────────────────
def nearest_candidate_distances(points: gpd.GeoDataFrame, candidates: gpd.GeoDataFrame):
    """For each point, return the distance to the nearest candidate polygon."""
    if len(candidates) == 0:
        return np.full(len(points), np.inf)
    tree = STRtree(candidates.geometry.values)
    dists = np.empty(len(points))
    for i, pt in enumerate(points.geometry.values):
        nearest_idx = tree.nearest(pt)
        dists[i] = pt.distance(candidates.geometry.values[nearest_idx])
    return dists


def candidate_counts_within(points: gpd.GeoDataFrame, candidates: gpd.GeoDataFrame,
                            radii: list[float]) -> np.ndarray:
    """For each point, count candidates within each radius. Returns (n_pts, n_radii)."""
    if len(candidates) == 0:
        return np.zeros((len(points), len(radii)), dtype=int)
    tree = STRtree(candidates.geometry.values)
    counts = np.zeros((len(points), len(radii)), dtype=int)
    for i, pt in enumerate(points.geometry.values):
        for j, r in enumerate(radii):
            buf = pt.buffer(r)
            cands = tree.query(buf)
            # STRtree.query returns candidate indices whose bbox intersects — filter precisely
            actual = sum(1 for idx in cands if candidates.geometry.values[idx].distance(pt) <= r)
            counts[i, j] = actual
    return counts


# ───────────────────────────────────────────────────────────────────────────
# Run validation for a given feature type
# ───────────────────────────────────────────────────────────────────────────
def validate(layer_path: Path, layer_name: str, label: str):
    log(f"=== Validating Feature Type {label} from {layer_path.name} ===")
    if not layer_path.exists():
        log("  (layer missing)")
        return None
    candidates = gpd.read_file(layer_path, layer=layer_name).to_crs(TARGET_CRS)
    # Clip to subarea
    candidates = candidates[candidates.geometry.within(box(*SUB_BBOX))].copy()
    log(f"  candidates: {len(candidates)}")
    if len(candidates) == 0:
        return None

    # Well → nearest candidate distances
    t0 = time.time()
    well_dists = nearest_candidate_distances(wells, candidates)
    log(f"  well nearest-dist: median={np.median(well_dists):.1f} m, p25={np.percentile(well_dists, 25):.1f}, p75={np.percentile(well_dists, 75):.1f}")

    # Background (null) → nearest candidate distances
    bg = draw_background(len(wells))
    bg_dists = nearest_candidate_distances(bg, candidates)
    log(f"  null nearest-dist: median={np.median(bg_dists):.1f} m, p25={np.percentile(bg_dists, 25):.1f}, p75={np.percentile(bg_dists, 75):.1f}")

    # KS test: are wells closer to candidates than null?
    from scipy.stats import ks_2samp
    ks = ks_2samp(well_dists, bg_dists, alternative="greater")
    log(f"  KS (wells distance < null distance): statistic={ks.statistic:.4f}, p={ks.pvalue:.4g}")

    # Counts within radii
    radii = [50, 100, 150, 200]
    well_counts = candidate_counts_within(wells, candidates, radii)
    bg_counts = candidate_counts_within(bg, candidates, radii)
    log(f"  enrichment (well mean / null mean):")
    for j, r in enumerate(radii):
        wmean = well_counts[:, j].mean()
        bmean = bg_counts[:, j].mean()
        enrich = wmean / max(bmean, 1e-6)
        log(f"    r={r:4d}m  wells={wmean:.3f}  null={bmean:.3f}  ratio={enrich:.2f}x")

    # Negative control: offset wells by 500 m in random directions
    log("  negative control (wells offset by 500 m)...")
    angles = rng.uniform(0, 2 * np.pi, size=len(wells))
    wx_shift = wells.geometry.x.values + 500 * np.cos(angles)
    wy_shift = wells.geometry.y.values + 500 * np.sin(angles)
    wells_shift = gpd.GeoDataFrame(
        geometry=[Point(x, y) for x, y in zip(wx_shift, wy_shift)],
        crs=TARGET_CRS,
    )
    # Drop wells that shifted outside the subarea
    wells_shift = wells_shift[wells_shift.geometry.within(box(*SUB_BBOX))].copy()
    log(f"    shifted wells remaining in subarea: {len(wells_shift)}")
    if len(wells_shift) > 0:
        shift_dists = nearest_candidate_distances(wells_shift, candidates)
        ks_neg = ks_2samp(shift_dists, bg_dists, alternative="greater")
        log(f"    KS (shifted wells vs null): statistic={ks_neg.statistic:.4f}, p={ks_neg.pvalue:.4g}")

    return {
        "layer": layer_name,
        "label": label,
        "n_candidates": len(candidates),
        "well_nd_median": float(np.median(well_dists)),
        "null_nd_median": float(np.median(bg_dists)),
        "ks_stat": float(ks.statistic),
        "ks_pval": float(ks.pvalue),
        "enrichment_100m": float(well_counts[:, 1].mean() / max(bg_counts[:, 1].mean(), 1e-6)),
    }


# ───────────────────────────────────────────────────────────────────────────
# Run
# ───────────────────────────────────────────────────────────────────────────
results = []
for layer_path, layer_name, label in [
    (SUB / "features_A_pads.gpkg", "pads", "A"),
    (SUB / "features_B_roads.gpkg", "roads", "B"),
]:
    res = validate(layer_path, layer_name, label)
    if res is not None:
        results.append(res)

if results:
    df = pd.DataFrame(results)
    log("Summary:")
    log(df.to_string(index=False))
    df.to_csv(SUB / "validation_results.csv", index=False)

log("DONE")
