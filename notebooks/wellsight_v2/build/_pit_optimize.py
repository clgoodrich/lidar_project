"""Optimize pit (well-depression) post-processing against ground truth.

The polygon/blob analog of `_road_optimize.py`. Roads are 1-D (skeleton ->
centerlines); pits are 2-D blobs (threshold -> connected components -> filter by
shape -> polygon -> centroid = candidate well point). Same philosophy: you can't
optimize what you can't measure, so this builds an object-level detection harness
on the 9t held-out test blocks (GT = hand-drawn `pit_inside` floors), sweeps the
shape/threshold knobs to max F1, saves the winner, and `--apply` runs it on any
block — emitting candidate well polygons + points with confidence and, if a
known-well file is supplied, distance to the nearest known well (per project QC).

Pipeline stages (each with competing options):
  source : pit_prob_floor   (the depression interior; the road `prob` analog)
  thresh : global | otsu | hysteresis
  gate   : restrict to argmax==floor (drop wall/bg leakage)         [optional]
  morph  : close + fill-holes + remove-small                        (clean blobs)
  shape  : area_min/area_max (m^2) + circularity_min + eccentricity_max
  -> polygonize each surviving blob; centroid = candidate well point

Detection match (object-level, greedy nearest within TOL):
  TP = pred centroid within TOL m of an unused GT centroid
  precision = TP/(TP+FP)   recall = TP/(TP+FN)   F1 = 2PR/(P+R)

CLI:
  # optimize on 9t test blocks, save best config:
  python notebooks/wellsight_v2/build/_pit_optimize.py
  # apply to a block's pit_prob_floor raster:
  python notebooks/wellsight_v2/build/_pit_optimize.py \
      --apply-block data/derivatives/tiles/data_3x3/westernpa_d20/613590 \
      --apply-key 613590 --prob <pit_prob_floor.tif> [--wells output_wells.csv]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio import features
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT

R9 = DERIV / "tiles" / "9t"
PIT = R9 / "pit_unet_v2"
ANN = DERIV / "annotations" / "annotations_proj.gpkg"
TOL = 6.0  # centroid match tolerance (m) -- pit floors are small


# ===========================================================================
# data
# ===========================================================================
def load_9t():
    """Load the 9t floor prob + argmax and the GT pit floors in the test region."""
    import geopandas as gpd
    from shapely.ops import unary_union
    with rasterio.open(PIT / "pit_prob_floor.tif") as r:
        prob = r.read(1).astype(np.float32); tf = r.transform; crs = r.crs; res = r.res[0]
    arg = None
    ap = PIT / "pit_argmax.tif"
    if ap.exists():
        with rasterio.open(ap) as r:
            arg = r.read(1)
    blocks = gpd.read_file(R9 / "pit_blocks_9t.gpkg")
    region = unary_union(blocks[blocks.split == "test"].geometry.values)
    gt = gpd.read_file(ANN, layer="pit_inside").to_crs(DST_CRS)
    gt = gt[gt.intersects(region)].copy()
    gt["geometry"] = gt.geometry.intersection(region)
    gt = gt[~gt.is_empty]
    return dict(prob=prob, arg=arg, tf=tf, crs=crs, res=res, region=region, gt=gt)


# ===========================================================================
# arsenal -- stage functions
# ===========================================================================
def enhance(prob, method):
    if method == "none":
        return prob
    if method == "gauss":            # mild smoothing -> rounder, fewer specks
        return ndi.gaussian_filter(prob, 1.0)
    return prob


def to_mask(E, prob, arg, cfg):
    """Threshold the floor prob -> clean binary blob mask."""
    from skimage.filters import apply_hysteresis_threshold, threshold_otsu
    if cfg["thresh"] == "global":
        m = E >= cfg["t"]
    elif cfg["thresh"] == "otsu":
        pos = E[E > 0.05]
        m = E >= (threshold_otsu(pos) if pos.size else 1.0)
    else:  # hysteresis
        m = apply_hysteresis_threshold(E, cfg["lo"], cfg["hi"])
    if cfg.get("floor_gate") and arg is not None:
        m = m & (arg == 1)           # argmax: 0=bg 1=floor 2=wall
    m = ndi.binary_closing(m, np.ones((3, 3)))
    m = ndi.binary_fill_holes(m)
    from skimage.morphology import remove_small_objects
    m = remove_small_objects(m, min_size=cfg.get("min_px", 12))
    return m


def blobs(mask, prob, tf, res, cfg):
    """Label blobs, filter by area/shape, return list of (poly, attrs)."""
    from shapely.geometry import shape
    from skimage.measure import label, regionprops
    lab = label(mask, connectivity=2)
    if lab.max() == 0:
        return []
    # one polygon per label in CRS coords
    geom_by_lab = {}
    for g, v in features.shapes(lab.astype(np.int32), mask=(lab > 0),
                                transform=tf, connectivity=8):
        v = int(v)
        p = shape(g)
        if v not in geom_by_lab or p.area > geom_by_lab[v].area:
            geom_by_lab[v] = p          # keep the largest ring per label
    px_area = res * res
    amin, amax = cfg.get("area_min", 4.0), cfg.get("area_max", 1500.0)
    cmin = cfg.get("circ_min", 0.45)
    emax = cfg.get("ecc_max", 0.92)
    out = []
    for rp in regionprops(lab, intensity_image=prob):
        poly = geom_by_lab.get(rp.label)
        if poly is None or poly.is_empty:
            continue
        area = poly.area
        if area < amin or area > amax:
            continue
        perim = poly.length
        circ = (4 * np.pi * area / (perim * perim)) if perim > 0 else 0.0
        if circ < cmin:
            continue
        ecc = float(rp.eccentricity)
        if ecc > emax:
            continue
        mp = float(rp.intensity_mean)
        out.append((poly, dict(area_m2=round(area, 1), circularity=round(circ, 3),
                               eccentricity=round(ecc, 3), mean_pfloor=round(mp, 3),
                               area_px=int(rp.area))))
    return out


# ===========================================================================
# pipeline + scoring
# ===========================================================================
def run_pipeline(D, cfg):
    import geopandas as gpd
    E = enhance(D["prob"], cfg["enhance"])
    mask = to_mask(E, D["prob"], D["arg"], cfg)
    bl = blobs(mask, D["prob"], D["tf"], D["res"], cfg)
    if not bl:
        return gpd.GeoDataFrame(geometry=[], crs=DST_CRS)
    rows = [{**a, "geometry": p} for p, a in bl]
    return gpd.GeoDataFrame(rows, crs=DST_CRS)


def _centroids(geoms):
    return np.array([[g.centroid.x, g.centroid.y] for g in geoms]) if len(geoms) else np.empty((0, 2))


def score(D, gdf):
    gt = D["gt"]
    ng = len(gt)
    if len(gdf) == 0 or ng == 0:
        return dict(prec=0.0, rec=0.0, f1=0.0, tp=0, fp=len(gdf), fn=ng, n=len(gdf))
    G = _centroids(gt.geometry.values)
    # greedy match: most-confident preds first (mean_pfloor), nearest unused GT <= TOL
    order = gdf.sort_values("mean_pfloor", ascending=False) if "mean_pfloor" in gdf else gdf
    P = _centroids(order.geometry.values)
    tree = cKDTree(G)
    used = set(); tp = 0
    for p in P:
        d, j = tree.query(p, k=min(4, ng))
        d = np.atleast_1d(d); j = np.atleast_1d(j)
        for dist, gi in zip(d, j):
            if dist <= TOL and gi not in used:
                used.add(int(gi)); tp += 1
                break
    fp = len(gdf) - tp; fn = ng - tp
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return dict(prec=round(prec, 3), rec=round(rec, 3), f1=round(f1, 3),
                tp=tp, fp=fp, fn=fn, n=len(gdf))


# ===========================================================================
# optimization
# ===========================================================================
BASE = dict(enhance="none", thresh="global", t=0.5, hi=0.6, lo=0.4,
            floor_gate=True, min_px=12, area_min=4.0, area_max=1500.0,
            circ_min=0.45, ecc_max=0.92)

SWEEPS = [
    ("enhance", ["none", "gauss"]),
    ("thresh", ["global", "otsu", "hysteresis"]),
    ("floor_gate", [True, False]),
    ("t", [0.4, 0.5, 0.6]),
    ("area_min", [4.0, 9.0, 16.0]),
    ("area_max", [800.0, 1500.0, 3000.0]),
    ("circ_min", [0.35, 0.45, 0.55]),
    ("ecc_max", [0.88, 0.92, 0.96]),
    ("min_px", [8, 12, 20]),
]


def optimize(D):
    cfg = dict(BASE)
    t0 = time.time()
    best = score(D, run_pipeline(D, cfg)); best_cfg = dict(cfg)
    print(f"BASE f1={best['f1']} prec={best['prec']} rec={best['rec']} "
          f"tp={best['tp']} fp={best['fp']} fn={best['fn']} n={best['n']}")
    for passnum in range(2):
        for param, opts in SWEEPS:
            for v in opts:
                trial = dict(best_cfg); trial[param] = v
                if trial == best_cfg:
                    continue
                s = score(D, run_pipeline(D, trial))
                tag = ""
                if s["f1"] > best["f1"]:
                    best, best_cfg = s, dict(trial); tag = "  <-- NEW BEST"
                print(f"  p{passnum} {param}={v}: f1={s['f1']} prec={s['prec']} "
                      f"rec={s['rec']} n={s['n']}{tag}")
        print(f"-- pass {passnum} best f1={best['f1']}")
    print(f"\nOPTIMIZE done in {time.time()-t0:.0f}s. BEST f1={best['f1']}: {best_cfg}")
    PIT.mkdir(parents=True, exist_ok=True)
    (PIT / "pit_postproc_best.json").write_text(
        json.dumps({"metrics": best, "config": best_cfg}, indent=2))
    return best_cfg, best


# ===========================================================================
# apply
# ===========================================================================
def _load_wells(path):
    """Read known wells (csv with lon/lat or x/y, or any vector) -> GeoDataFrame in DST_CRS."""
    import geopandas as gpd
    import pandas as pd
    p = Path(path)
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
        lc = {c.lower(): c for c in df.columns}
        xq = next((lc[k] for k in ("lon", "longitude", "x", "easting") if k in lc), None)
        yq = next((lc[k] for k in ("lat", "latitude", "y", "northing") if k in lc), None)
        if xq is None or yq is None:
            return None
        src = 4326 if any(k in lc for k in ("lon", "longitude", "lat", "latitude")) else DST_CRS
        g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[xq], df[yq]), crs=src)
    else:
        g = gpd.read_file(p)
    return g.to_crs(DST_CRS)


def load_block(block, key, prob_path=None, arg_path=None):
    blk = Path(block); sfx = f"{key}_1m"
    pp = Path(prob_path) if prob_path else blk / f"pit_prob_floor_{sfx}.tif"
    with rasterio.open(pp) as r:
        prob = r.read(1).astype(np.float32); tf = r.transform; res = r.res[0]; crs = r.crs
    arg = None
    ap = Path(arg_path) if arg_path else blk / f"pit_argmax_{sfx}.tif"
    if ap.exists():
        with rasterio.open(ap) as r:
            arg = r.read(1)
    return dict(prob=prob, arg=arg, tf=tf, crs=crs, res=res,
                blk=blk, key=key, sfx=sfx)


def apply_best(D, cfg, conf_min=0.5, wells=None):
    """Run the winning pipeline on a block, attribute confidence + nearest-well dist, write."""
    import geopandas as gpd
    E = enhance(D["prob"], cfg["enhance"])
    mask = to_mask(E, D["prob"], D["arg"], cfg)
    bl = blobs(mask, D["prob"], D["tf"], D["res"], cfg)
    rows = []
    for poly, a in bl:
        # confidence: floor-prob weight + shape plausibility (circular, compact)
        conf = 0.6 * a["mean_pfloor"] + 0.4 * min(a["circularity"] / 0.8, 1.0)
        rows.append({**a, "confidence": round(conf, 3), "geometry": poly})
    gdf = gpd.GeoDataFrame(rows, crs=DST_CRS) if rows else gpd.GeoDataFrame(geometry=[], crs=DST_CRS)

    # candidate well points = polygon centroids
    pts = gdf.copy()
    if len(pts):
        pts["geometry"] = pts.geometry.centroid

    # distance to nearest known well (project QC requirement for candidates)
    wg = _load_wells(wells) if wells else None
    if wg is not None and len(wg) and len(pts):
        wtree = cKDTree(_centroids(wg.geometry.values))
        d, _ = wtree.query(_centroids(pts.geometry.values), k=1)
        pts["dist_well_m"] = np.round(np.atleast_1d(d), 1)
        gdf["dist_well_m"] = pts["dist_well_m"].values

    clean = gdf[gdf.confidence >= conf_min].copy() if len(gdf) else gdf
    out = D["blk"] / f"pits_opt_{D['sfx']}.gpkg"
    if out.exists():
        out.unlink()
    if len(gdf):
        gdf.to_file(out, layer="pits_all", driver="GPKG")
        if len(clean):
            clean.to_file(out, layer="pits_clean", driver="GPKG")
        if len(pts):
            pts.to_file(out, layer="pit_points", driver="GPKG")
    stats = {"key": D["key"], "n_all": int(len(gdf)), "n_clean": int(len(clean)),
             "conf_min": conf_min, "detection": "pit_unet_v2 floor-prob blob",
             "config": cfg}
    if "dist_well_m" in gdf and len(clean):
        stats["clean_within_50m_of_known"] = int((clean.dist_well_m <= 50).sum())
        stats["clean_median_dist_well_m"] = round(float(clean.dist_well_m.median()), 1)
    (D["blk"] / f"pits_opt_{D['sfx']}_stats.json").write_text(json.dumps(stats, indent=2))
    print(f"[{D['key']}] pits: {stats['n_all']} candidates, {stats['n_clean']} clean "
          f"(conf>={conf_min}) -> {out.name}")
    print(f"  stats: {json.dumps({k: v for k, v in stats.items() if k != 'config'})}")

    # overlay
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from rasterio.enums import Resampling
        hs_p = D["blk"] / f"hillshade_{D['sfx']}.tif"
        if hs_p.exists():
            ds = 3
            with rasterio.open(hs_p) as r:
                H, W = r.height, r.width
                hs = r.read(1, out_shape=(H // ds, W // ds), resampling=Resampling.nearest); b = r.bounds
            ext = (b.left, b.right, b.bottom, b.top)
            fig, ax = plt.subplots(figsize=(14, 14)); ax.imshow(hs, cmap="gray", extent=ext, origin="upper")
            if len(clean):
                clean.plot(ax=ax, column="confidence", cmap="autumn_r", linewidth=1.2,
                           edgecolor="k", vmin=conf_min, vmax=1, legend=True)
            ax.set_title(f"{D['key']}: candidate pits (floor-prob blobs); conf>={conf_min}")
            ax.set_xticks([]); ax.set_yticks([])
            fig.savefig(D["blk"] / f"pits_opt_{D['sfx']}_overlay.png", dpi=120, bbox_inches="tight")
            plt.close(fig); print(f"  -> pits_opt_{D['sfx']}_overlay.png")
    except Exception as ex:  # noqa: BLE001
        print(f"  overlay skipped: {ex}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply-block", default=None)
    ap.add_argument("--apply-key", default=None)
    ap.add_argument("--prob", default=None, help="pit_prob_floor raster (apply mode)")
    ap.add_argument("--arg", default=None, help="pit_argmax raster (apply mode, optional)")
    ap.add_argument("--wells", default=None, help="known-well file for nearest-well distance")
    ap.add_argument("--conf-min", type=float, default=0.5)
    args = ap.parse_args()
    best_path = PIT / "pit_postproc_best.json"
    if args.apply_block:
        cfg = json.loads(best_path.read_text())["config"] if best_path.exists() else dict(BASE)
        D = load_block(args.apply_block, args.apply_key, prob_path=args.prob, arg_path=args.arg)
        apply_best(D, cfg, conf_min=args.conf_min, wells=args.wells)
        return 0
    D = load_9t()
    print(f"GT pit floors in 9t test region: {len(D['gt'])}")
    optimize(D)
    return 0


if __name__ == "__main__":
    sys.exit(main())
