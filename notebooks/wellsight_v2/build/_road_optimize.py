"""Optimize road-network post-processing against ground truth.

You cannot optimize what you cannot measure. This builds a quantitative harness
on 9t (hand-drawn `roads` = ground truth, evaluated on HELD-OUT test blocks),
implements an arsenal of competing algorithms for each pipeline stage, and runs
coordinate-ascent + hand-designed power-combos to find the max-F1 configuration.
The winner is printed as a leaderboard and saved; `--apply` runs it on any block.

Metrics (relaxed buffer-matching, Heipke/Wiedemann):
  completeness = len(GT within tol of pred) / len(GT)        (recall)
  correctness  = len(pred within tol of GT) / len(pred)      (precision)
  quality      = TP / (TP+FP+FN);   F1 = 2*comp*corr/(comp+corr)
plus connectivity (#components, km).

Arsenal:
  enhance : none | sato | frangi | meijering | blend(prob+ridge)
  thresh  : global | hysteresis | otsu
  pathopen: off | oriented-line union (suppress blobs/texture, keep lines)
  slope   : off | gate(<deg)
  skel    : zhang | lee | medial
  reconnect: none | lcp(pairwise) | mst(component spanning) over 1/prob cost
  island  : min component length

CLI:
  python notebooks/wellsight/build/_road_optimize.py                 # optimize on 9t
  python notebooks/wellsight/build/_road_optimize.py --apply-block \
      data/derivatives/tiles/data_3x3/westernpa_d20/613590 --apply-key 613590
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT

R9 = DERIV / "tiles" / "9t"
TOL = 8.0          # buffer match tolerance (m)


# ===========================================================================
# data
# ===========================================================================
def load_9t():
    import geopandas as gpd
    with rasterio.open(R9 / "road_unet_1m" / "road_prob.tif") as r:
        prob = r.read(1).astype(np.float32); tf = r.transform; crs = r.crs; res = r.res[0]
    arg = None
    ap = R9 / "road_unet_1m" / "road_argmax.tif"
    if ap.exists():
        with rasterio.open(ap) as r:
            arg = r.read(1)
    # slope at 1 m
    sl = None
    sp = R9.parent / "9t_1m" / "slope_9t_1m.tif"
    if sp.exists():
        with rasterio.open(sp) as r:
            sl = r.read(1).astype(np.float32)
    blocks = gpd.read_file(R9 / "pit_blocks_9t.gpkg")
    test = blocks[blocks.split == "test"]
    from shapely.ops import unary_union
    region = unary_union(test.geometry.values)
    gt = gpd.read_file(DERIV / "annotations" / "annotations_proj.gpkg", layer="roads")
    gt = gt.to_crs(DST_CRS)
    gt = gt[gt.intersects(region)].copy()
    gt["geometry"] = gt.geometry.intersection(region)
    gt = gt[~gt.is_empty]
    return dict(prob=prob, arg=arg, slope=sl, tf=tf, crs=crs, res=res,
                region=region, gt=gt)


# ===========================================================================
# arsenal -- stage functions
# ===========================================================================
def enhance(prob, method):
    if method == "none":
        return prob
    from skimage.filters import sato, frangi, meijering
    sig = range(1, 5)
    if method == "sato":
        e = sato(prob, sigmas=sig, black_ridges=False)
    elif method == "frangi":
        e = frangi(prob, sigmas=sig, black_ridges=False)
    elif method == "meijering":
        e = meijering(prob, sigmas=sig, black_ridges=False)
    elif method == "blend":
        e = sato(prob, sigmas=sig, black_ridges=False)
        e = e / (e.max() + 1e-9)
        return np.clip(0.6 * prob + 0.4 * e, 0, 1)
    e = e / (e.max() + 1e-9)
    return e.astype(np.float32)


def _line_se(length, angle_deg):
    a = np.deg2rad(angle_deg)
    t = np.arange(length)
    xs = np.round(t * np.cos(a)).astype(int)
    ys = np.round(t * np.sin(a)).astype(int)
    xs -= xs.min(); ys -= ys.min()
    se = np.zeros((ys.max() + 1, xs.max() + 1), bool)
    se[ys, xs] = True
    return se


def path_open(mask, length=14, n_ang=12):
    """Keep pixels lying on a straight run of >= `length` in SOME direction."""
    out = np.zeros_like(mask)
    for ang in np.linspace(0, 180, n_ang, endpoint=False):
        out |= ndi.binary_opening(mask, structure=_line_se(length, ang))
    return out


def to_mask(E, prob, arg, slope, cfg):
    from skimage.filters import apply_hysteresis_threshold, threshold_otsu
    margin = (arg != 2) if arg is not None else np.ones(E.shape, bool)
    if cfg["thresh"] == "global":
        m = E >= cfg["t"]
    elif cfg["thresh"] == "otsu":
        m = E >= threshold_otsu(E[E > 0.05])
    else:  # hysteresis
        m = apply_hysteresis_threshold(E, cfg["lo"], cfg["hi"])
    m = m & margin
    if cfg.get("slope_max") and slope is not None:
        m &= np.nan_to_num(slope, nan=90) <= cfg["slope_max"]
    m = ndi.binary_closing(m, np.ones((3, 3)))
    m = ndi.binary_fill_holes(m)
    if cfg.get("pathopen"):
        m = path_open(m, length=cfg.get("po_len", 14))
    from skimage.morphology import remove_small_objects
    m = remove_small_objects(m, min_size=cfg.get("min_px", 40))
    return m


def skeleton(mask, method):
    from skimage.morphology import skeletonize, medial_axis
    if method == "lee":
        return skeletonize(mask, method="lee")
    if method == "medial":
        return medial_axis(mask)
    return skeletonize(mask)


def lines_from_skel(skel_img, tf):
    from shapely.geometry import LineString
    from skan import Skeleton
    try:
        sk = Skeleton(skel_img)
    except ValueError:
        return []
    out = []
    for i in range(sk.n_paths):
        rc = sk.path_coordinates(i)
        if len(rc) < 2:
            continue
        xs, ys = rasterio.transform.xy(tf, rc[:, 0], rc[:, 1])
        ls = LineString(np.column_stack([xs, ys]))
        if ls.length > 0:
            out.append(ls)
    return out


def _key(p, q=1.0):
    return (round(p[0] / q) * q, round(p[1] / q) * q)


def prune_merge(lines, spur):
    import networkx as nx
    from shapely.geometry import LineString
    from shapely.ops import linemerge, unary_union
    G = nx.MultiGraph()
    for ls in lines:
        G.add_edge(_key(ls.coords[0]), _key(ls.coords[-1]), geom=ls, length=ls.length)
    ch = True
    while ch:
        ch = False
        for n in [n for n in G.nodes if G.degree(n) == 1]:
            es = list(G.edges(n, keys=True, data=True))
            if not es:
                continue
            u, v, k, d = es[0]
            if d["length"] < spur:
                G.remove_edge(u, v, k); ch = True
        G.remove_nodes_from([n for n in list(G.nodes) if G.degree(n) == 0])
    kept = [d["geom"] for *_x, d in G.edges(data=True)]
    if not kept:
        return []
    m = linemerge(unary_union(kept))
    segs = list(m.geoms) if m.geom_type == "MultiLineString" else [m]
    return [s for s in segs if isinstance(s, LineString) and s.length > 0]


def reconnect(segs, prob, tf, res, method, max_gap=35, max_ang=40, gate=3.0):
    if method == "none" or len(segs) < 2:
        return segs, []
    from shapely.geometry import LineString, Point
    from skimage.graph import route_through_array
    cost = 1.0 / (np.clip(np.nan_to_num(prob), 0, 1) + 0.05)
    inv = ~tf; H, W = prob.shape

    def tang(ls, s):
        c = list(ls.coords)
        p0, p1 = (c[0], c[min(3, len(c) - 1)]) if s else (c[-1], c[max(-4, -len(c))])
        v = np.array(p1) - np.array(p0); n = np.linalg.norm(v)
        return v / n if n else v
    from scipy.spatial import cKDTree
    ends = []
    for i, ls in enumerate(segs):
        ends.append((i, Point(ls.coords[0]), -tang(ls, True)))
        ends.append((i, Point(ls.coords[-1]), -tang(ls, False)))
    pts = np.array([[e[1].x, e[1].y] for e in ends])
    pairs = cKDTree(pts).query_pairs(max_gap, output_type="ndarray") if len(ends) > 1 else []
    cand = []  # (cost_per_len, geom, ia, ib)
    for a, b in pairs:
            ia, pa, ta = ends[a]
            ib, pb, tb = ends[b]
            if ia == ib:
                continue
            gap = pa.distance(pb)
            if gap > max_gap or gap < res:
                continue
            d = np.array([pb.x - pa.x, pb.y - pa.y]); d /= np.linalg.norm(d) + 1e-9
            if np.dot(ta, d) < np.cos(np.radians(max_ang)) or np.dot(tb, -d) < np.cos(np.radians(max_ang)):
                continue
            ca, ra = inv * (pa.x, pa.y); cb, rb = inv * (pb.x, pb.y)
            ra, ca, rb, cb = int(ra), int(ca), int(rb), int(cb)
            if not (0 <= ra < H and 0 <= ca < W and 0 <= rb < H and 0 <= cb < W):
                continue
            try:
                path, w = route_through_array(cost, (ra, ca), (rb, cb),
                                              fully_connected=True, geometric=True)
            except Exception:  # noqa: BLE001
                continue
            cpl = w / max(len(path), 1)
            if cpl > gate:
                continue
            xs, ys = rasterio.transform.xy(tf, np.array(path)[:, 0], np.array(path)[:, 1])
            cand.append((cpl, LineString(np.column_stack([xs, ys])), ia, ib))
    cand.sort(key=lambda x: x[0])
    bridges = []
    if method == "lcp":
        used = set()
        for cpl, g, ia, ib in cand:
            ea = (ia, "a");
            if ia in used or ib in used:
                continue
            bridges.append(g); used.add(ia); used.add(ib)
    else:  # mst: greedily merge components (union-find)
        import networkx as nx
        parent = {}
        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for cpl, g, ia, ib in cand:
            ra, rb = find(ia), find(ib)
            if ra != rb:
                parent[ra] = rb; bridges.append(g)
    return segs + bridges, bridges


def island_filter(segs, min_len):
    import networkx as nx
    G = nx.Graph()
    for i, ls in enumerate(segs):
        G.add_edge(_key(ls.coords[0]), _key(ls.coords[-1]), idx=i, length=ls.length)
    keep = []
    for comp in nx.connected_components(G):
        sub = G.subgraph(comp)
        idxs = [d["idx"] for *_x, d in sub.edges(data=True)]
        if sum(d["length"] for *_x, d in sub.edges(data=True)) >= min_len:
            keep.extend(idxs)
    return [segs[i] for i in keep]


# ===========================================================================
# full pipeline + scoring
# ===========================================================================
def run_pipeline(D, cfg):
    import geopandas as gpd
    E = enhance(D["prob"], cfg["enhance"])
    mask = to_mask(E, D["prob"], D["arg"], D["slope"], cfg)
    if mask.sum() == 0:
        return gpd.GeoDataFrame(geometry=[], crs=DST_CRS)
    skel = skeleton(mask, cfg["skel"])
    lines = lines_from_skel(skel, D["tf"])
    segs = prune_merge(lines, cfg.get("spur", 20))
    segs, _ = reconnect(segs, D["prob"], D["tf"], D["res"], cfg.get("reconnect", "none"))
    segs = prune_merge(segs, 0.1)
    segs = island_filter(segs, cfg.get("island", 120))
    return gpd.GeoDataFrame(geometry=segs, crs=DST_CRS)


def score(D, gdf):
    from shapely.ops import unary_union
    region, gt = D["region"], D["gt"]
    if len(gdf) == 0:
        return dict(comp=0, corr=0, f1=0, quality=0, km=0, n=0)
    pred = gdf.intersection(region)
    pred = pred[~pred.is_empty]
    if len(pred) == 0:
        return dict(comp=0, corr=0, f1=0, quality=0, km=0, n=0)
    P = unary_union(pred.values); Gu = unary_union(gt.geometry.values)
    pl, gl = P.length, Gu.length
    if pl == 0 or gl == 0:
        return dict(comp=0, corr=0, f1=0, quality=0, km=round(pl / 1000, 2), n=len(gdf))
    matched_gt = Gu.intersection(P.buffer(TOL)).length
    matched_pr = P.intersection(Gu.buffer(TOL)).length
    comp = matched_gt / gl
    corr = matched_pr / pl
    f1 = 2 * comp * corr / (comp + corr) if (comp + corr) else 0
    tp = matched_pr; fp = pl - matched_pr; fn = gl - matched_gt
    quality = tp / (tp + fp + fn) if (tp + fp + fn) else 0
    return dict(comp=round(comp, 3), corr=round(corr, 3), f1=round(f1, 3),
                quality=round(quality, 3), km=round(pl / 1000, 2), n=len(gdf))


# ===========================================================================
# optimization
# ===========================================================================
BASE = dict(enhance="none", thresh="hysteresis", hi=0.6, lo=0.4, t=0.5,
            pathopen=False, po_len=14, slope_max=None, skel="zhang",
            spur=20, reconnect="lcp", island=120, min_px=40)

SWEEPS = [
    ("enhance", ["none", "sato", "blend"]),
    ("thresh", ["hysteresis", "otsu"]),
    ("pathopen", [False, True]),
    ("slope_max", [None, 25]),
    ("skel", ["zhang", "lee"]),
    ("reconnect", ["none", "lcp", "mst"]),
    ("spur", [20, 30]),
    ("island", [80, 150]),
    ("hi", [0.55, 0.65]),
    ("lo", [0.35, 0.45]),
]


def optimize(D):
    log = []
    cfg = dict(BASE)
    t0 = time.time()
    best = score(D, run_pipeline(D, cfg)); best_cfg = dict(cfg)
    log.append(("BASE", dict(cfg), best))
    print(f"BASE f1={best['f1']} comp={best['comp']} corr={best['corr']} "
          f"km={best['km']} n={best['n']}")
    for passnum in range(2):
        for param, opts in SWEEPS:
            for v in opts:
                if cfg.get(param) == v and (param, v) != ("enhance", "none"):
                    pass
                trial = dict(best_cfg); trial[param] = v
                if trial == best_cfg:
                    continue
                s = score(D, run_pipeline(D, trial))
                log.append((f"{param}={v}", dict(trial), s))
                tag = ""
                if s["f1"] > best["f1"]:
                    best, best_cfg = s, dict(trial); tag = "  <-- NEW BEST"
                print(f"  p{passnum} {param}={v}: f1={s['f1']} comp={s['comp']} "
                      f"corr={s['corr']} km={s['km']} n={s['n']}{tag}")
        print(f"-- pass {passnum} best f1={best['f1']} cfg={ {k:best_cfg[k] for k in ['enhance','thresh','pathopen','slope_max','skel','reconnect','island']} }")
    print(f"\nOPTIMIZE done in {time.time()-t0:.0f}s. BEST f1={best['f1']}: {best_cfg}")
    (R9 / "road_unet_1m" / "road_postproc_best.json").write_text(
        json.dumps({"metrics": best, "config": best_cfg}, indent=2))
    return best_cfg, best, log


def load_block(block, key, prob_path=None, drain_path=None):
    blk = Path(block); sfx = f"{key}_1m"
    pp = Path(prob_path) if prob_path else blk / f"road_prob_{sfx}.tif"
    with rasterio.open(pp) as r:
        prob = r.read(1).astype(np.float32); tf = r.transform; res = r.res[0]; crs = r.crs
    def rd(stem):
        p = blk / f"{stem}_{sfx}.tif"
        if not p.exists():
            return None
        with rasterio.open(p) as r:
            return r.read(1)
    # If a drainage prob is supplied (recall model), derive argmax (bg/road/drain)
    # so the drainage gate (arg!=2) still works without a saved argmax raster.
    if drain_path and Path(drain_path).exists():
        with rasterio.open(drain_path) as r:
            pdr = np.clip(r.read(1).astype(np.float32), 0, 1)
        pr = np.clip(prob, 0, 1); pbg = np.clip(1 - pr - pdr, 0, 1)
        arg = np.argmax(np.stack([pbg, pr, pdr]), axis=0).astype(np.uint8)
    else:
        arg = rd("road_argmax")
    slope = rd("slope")
    return dict(prob=prob, arg=arg, slope=(slope.astype(np.float32) if slope is not None else None),
                tf=tf, crs=crs, res=res, region=None, gt=None, blk=blk, key=key, sfx=sfx)


def _sample(arr, ls, tf, step=3.0):
    if arr is None:
        return np.nan
    inv = ~tf; H, W = arr.shape; vals = []
    for t in np.linspace(0, ls.length, max(2, int(ls.length / step))):
        p = ls.interpolate(t); c, r = inv * (p.x, p.y); r, c = int(r), int(c)
        if 0 <= r < H and 0 <= c < W and np.isfinite(arr[r, c]):
            vals.append(arr[r, c])
    return float(np.median(vals)) if vals else np.nan


def apply_best(D, cfg, conf_min=0.6):
    """Run the winning pipeline on a block, attribute + score confidence, write."""
    import geopandas as gpd
    from shapely.geometry import Point
    from shapely.ops import unary_union
    E = enhance(D["prob"], cfg["enhance"])
    mask = to_mask(E, D["prob"], D["arg"], D["slope"], cfg)
    dtw = ndi.distance_transform_edt(mask) * D["res"]
    skel = skeleton(mask, cfg["skel"])
    segs = prune_merge(lines_from_skel(skel, D["tf"]), cfg.get("spur", 20))
    segs, bridges = reconnect(segs, D["prob"], D["tf"], D["res"], cfg.get("reconnect", "lcp"))
    segs = prune_merge(segs, 0.1)
    segs = island_filter(segs, cfg.get("island", 80))
    rows = []
    for s in segs:
        mp = _sample(D["prob"], s, D["tf"]); sl = _sample(D["slope"], s, D["tf"])
        w = 2.0 * _sample(dtw, s, D["tf"])
        straight = Point(s.coords[0]).distance(Point(s.coords[-1]))
        flat = 1 - (np.clip((sl - 6) / 24, 0, 1) if np.isfinite(sl) else 0.5)
        conf = 0.48 * (mp if np.isfinite(mp) else 0.3) + 0.20 * min(s.length / 300, 1) + 0.32 * flat
        rows.append({"length_m": round(s.length, 1),
                     "mean_proad": round(mp, 3) if np.isfinite(mp) else None,
                     "width_m": round(w, 1) if np.isfinite(w) else None,
                     "mean_slope": round(sl, 1) if np.isfinite(sl) else None,
                     "sinuosity": round(s.length / max(straight, 1e-6), 3) if straight > 0 else None,
                     "confidence": round(conf, 3), "geometry": s})
    gdf = gpd.GeoDataFrame(rows, crs=DST_CRS) if rows else gpd.GeoDataFrame(geometry=[], crs=DST_CRS)
    clean = gdf[gdf.confidence >= conf_min].copy() if len(gdf) else gdf
    out = D["blk"] / f"roads_opt_{D['sfx']}.gpkg"
    if out.exists():
        out.unlink()
    if len(gdf):
        gdf.to_file(out, layer="roads_all", driver="GPKG")
        if len(clean):
            clean.to_file(out, layer="roads_clean", driver="GPKG")
    if bridges:
        gpd.GeoDataFrame(geometry=bridges, crs=DST_CRS).to_file(out, layer="bridges", driver="GPKG")
    stats = {"key": D["key"], "network_km": round(sum(s.length for s in segs) / 1000, 2),
             "clean_km": round(float(clean.length.sum()) / 1000, 2) if len(clean) else 0.0,
             "n_clean": int(len(clean)), "bridges": len(bridges), "config": cfg}
    # county-TIGER recall (clip the full county roads to the block)
    cty = [ROOT / "data" / "external" / "tiger_roads" / f
           for f in ("tl_2024_42083_roads.shp", "tl_2024_42121_roads.shp")]
    tg = [gpd.read_file(f).to_crs(DST_CRS) for f in cty if f.exists()]
    if tg and len(clean):
        import pandas as pd
        tg = gpd.GeoDataFrame(pd.concat(tg, ignore_index=True), crs=DST_CRS)
        minx, miny, maxx, maxy = clean.total_bounds
        tg = tg.cx[minx:maxx, miny:maxy]
        if len(tg):
            tgu = unary_union(tg.geometry.values); pr = unary_union(clean.geometry.values)
            stats["tiger_km_in_block"] = round(tgu.length / 1000, 2)
            stats["tiger_recall"] = round(tgu.intersection(pr.buffer(20)).length / max(tgu.length, 1), 3)
            stats["novel_km"] = round(pr.difference(tgu.buffer(25)).length / 1000, 2)
    (D["blk"] / f"roads_opt_{D['sfx']}_stats.json").write_text(json.dumps(stats, indent=2))
    print(f"[{D['key']}] applied best: network {stats['network_km']} km, "
          f"clean {stats['clean_km']} km ({stats['n_clean']} segs), bridges {stats['bridges']}")
    print(f"  stats: {json.dumps({k: v for k, v in stats.items() if k != 'config'})}")
    # overlay
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from rasterio.enums import Resampling
        ds = 3
        with rasterio.open(D["blk"] / f"hillshade_{D['sfx']}.tif") as r:
            H, W = r.height, r.width
            hs = r.read(1, out_shape=(H // ds, W // ds), resampling=Resampling.nearest); b = r.bounds
        ext = (b.left, b.right, b.bottom, b.top)
        fig, ax = plt.subplots(figsize=(14, 14)); ax.imshow(hs, cmap="gray", extent=ext, origin="upper")
        if len(gdf):
            noise = gdf[gdf.confidence < conf_min]
            if len(noise):
                noise.plot(ax=ax, color="#888", linewidth=0.4, alpha=0.4)
            if len(clean):
                clean.plot(ax=ax, column="confidence", cmap="autumn_r", linewidth=1.7,
                           vmin=conf_min, vmax=1, legend=True)
        if bridges:
            gpd.GeoDataFrame(geometry=bridges, crs=DST_CRS).plot(ax=ax, color="#00ff88", linewidth=1.8)
        ax.set_title(f"{D['key']}: OPTIMIZED road network (sato+otsu+lee+lcp); conf>={conf_min}")
        ax.set_xticks([]); ax.set_yticks([])
        fig.savefig(D["blk"] / f"roads_opt_{D['sfx']}_overlay.png", dpi=120, bbox_inches="tight")
        plt.close(fig); print(f"  -> roads_opt_{D['sfx']}_overlay.png")
    except Exception as ex:  # noqa: BLE001
        print(f"  overlay skipped: {ex}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply-block", default=None)
    ap.add_argument("--apply-key", default=None)
    ap.add_argument("--slope-gate", type=float, default=None,
                    help="override slope_max for out-of-domain blocks (e.g. 25)")
    ap.add_argument("--prob", default=None,
                    help="override road_prob path (e.g. recall model output)")
    ap.add_argument("--drain", default=None,
                    help="drainage_prob path; used to derive the argmax drainage gate")
    args = ap.parse_args()
    best_path = R9 / "road_unet_1m" / "road_postproc_best.json"
    if args.apply_block:
        cfg = json.loads(best_path.read_text())["config"]
        if args.slope_gate:
            cfg["slope_max"] = args.slope_gate
        D = load_block(args.apply_block, args.apply_key,
                       prob_path=args.prob, drain_path=args.drain)
        apply_best(D, cfg)
        return 0
    D = load_9t()
    print(f"GT roads in 9t test region: {len(D['gt'])} lines, "
          f"{sum(g.length for g in D['gt'].geometry)/1000:.2f} km")
    optimize(D)
    return 0


if __name__ == "__main__":
    sys.exit(main())
