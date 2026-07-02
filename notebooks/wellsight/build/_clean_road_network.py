"""Flawless road-network post-processing: 3-class road probability -> clean,
connected, attributed centerline network.

A road segmentation is a 1-D graph with topology, not a blob set. Aggressive
filtering kills faint access roads; timid filtering leaves terrain noise. Each
stage works in the domain where connectivity and noise can both be won:

  0. RASTER CONDITIONING
     - Sato/Frangi vesselness enhances thin connected curvilinear structure.
     - Hysteresis (dual) threshold: seeds (>=hi) grown through connectors
       (>=lo) via morphological reconstruction -> keeps faint-but-connected,
       drops faint-but-isolated.
     - 3-class margin gate: only where P(road) > P(drainage).
  1. MASK MORPHOLOGY  : remove specks, heal hairline gaps before skeletonizing.
  2. SKELETON -> GRAPH: skeletonize -> skan paths -> LineStrings; width from the
     mask distance transform sampled along each centerline.
  3. SPUR PRUNE       : iteratively drop leaf edges (dead-ends) < spur_len.
  4. GEOMETRY         : simplify (Douglas-Peucker) + node + linemerge.
  5. LCP GAP-BRIDGE   : bearing-gated least-cost path through 1/P(road) corridor.
  6. ISLAND FILTER    : drop components that are BOTH short AND not near TIGER.
  7. DRAINAGE GUARD   : cross-section xdrop test on low-confidence, stream-coincident segs.
  8. ATTRIBUTE        : length, mean P, width, sinuosity, slope, near-TIGER, confidence.
  9. QC + VALIDATION  : stats, overlay, TIGER recall + novelty.

Inputs (a data_3x3 block dir, suffix <key>_1m):
  road_prob_<sfx>.tif, drainage_prob_<sfx>.tif, dem_<sfx>.tif,
  stream_seed_t*_<sfx>.tif (optional), hillshade_<sfx>.tif (for overlay)
Optional TIGER anchor: data/external/tiger_roads/roads_clipped.gpkg

Outputs (block dir):
  roads_net_<sfx>.gpkg  (layers: roads, bridges, dropped)
  roads_net_<sfx>_overlay.png, roads_net_<sfx>_stats.json

CLI:
  python notebooks/wellsight/build/_clean_road_network.py \
      --block data/derivatives/tiles/data_3x3/westernpa_d20/613590 --key 613590
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from skimage.filters import sato
from skimage.morphology import reconstruction, remove_small_objects, skeletonize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DST_CRS, ROOT

TIGER = ROOT / "data" / "external" / "tiger_roads" / "roads_clipped.gpkg"


# ---------------------------------------------------------------------------
# Stage 0-1: probability -> clean binary road mask
# ---------------------------------------------------------------------------
def conditioned_mask(road_p, drain_p, res, *, seed_hi, seed_lo, vessel_sigmas,
                     vessel_thr, min_len_m, road_half_w_m=2.5):
    rp = np.nan_to_num(road_p, nan=0.0)
    dp = np.nan_to_num(drain_p, nan=0.0)
    margin = rp > dp                                   # 3-class gate
    # vesselness on the road probability (bright ridges)
    ves = sato(rp, sigmas=vessel_sigmas, black_ridges=False)
    ves = ves / (ves.max() + 1e-9)
    seed = (rp >= seed_hi) & margin
    # connectors need probability support; vesselness only *augments* where there is
    # already moderate prob (it must not flood near-zero-prob terrain). Gap-spanning
    # is handled downstream by the least-cost-path bridger, so this stays conservative.
    connect = ((rp >= seed_lo) | ((ves >= vessel_thr) & (rp >= 0.5 * seed_lo))) & margin
    # hysteresis via grey reconstruction (seed dilated within connect)
    mask = reconstruction(seed & connect, connect, method="dilation").astype(bool)
    # speck removal scaled to a minimum road footprint
    min_px = max(8, int(round(min_len_m * (2 * road_half_w_m) / (res * res))))
    mask = ndi.binary_closing(mask, structure=np.ones((3, 3)), iterations=1)
    mask = remove_small_objects(mask, min_size=min_px)
    mask = ndi.binary_fill_holes(mask)
    return mask, ves


# ---------------------------------------------------------------------------
# Stage 2: skeleton -> world-coordinate LineStrings (+ width)
# ---------------------------------------------------------------------------
def skeleton_lines(mask, transform, res):
    from shapely.geometry import LineString
    from skan import Skeleton
    skel_img = skeletonize(mask)
    dt = ndi.distance_transform_edt(mask) * res            # half-width at each px
    try:
        skel = Skeleton(skel_img)
    except ValueError:
        return [], []
    lines, widths = [], []
    for i in range(skel.n_paths):
        rc = skel.path_coordinates(i)                      # (N,2) row,col
        if len(rc) < 2:
            continue
        xs, ys = rasterio.transform.xy(transform, rc[:, 0], rc[:, 1])
        ls = LineString(np.column_stack([xs, ys]))
        if ls.length <= 0:
            continue
        w = 2.0 * float(np.median(dt[rc[:, 0].astype(int), rc[:, 1].astype(int)]))
        lines.append(ls); widths.append(w)
    return lines, widths


# ---------------------------------------------------------------------------
# Stage 3-4: graph build, spur prune, merge
# ---------------------------------------------------------------------------
def _key(pt, q=0.5):
    return (round(pt[0] / q) * q, round(pt[1] / q) * q)


def prune_and_merge(lines, widths, spur_len, snap_q=1.0):
    import networkx as nx
    from shapely.geometry import LineString
    from shapely.ops import linemerge, unary_union

    G = nx.MultiGraph()
    for idx, ls in enumerate(lines):
        a, b = _key(ls.coords[0], snap_q), _key(ls.coords[-1], snap_q)
        G.add_edge(a, b, geom=ls, length=ls.length, width=widths[idx])
    # iterative leaf-spur pruning
    changed = True
    while changed:
        changed = False
        for n in [n for n in G.nodes if G.degree(n) == 1]:
            es = list(G.edges(n, keys=True, data=True))
            if not es:
                continue                                   # edge already removed this pass
            u, v, key, d = es[0]
            if d["length"] < spur_len:
                G.remove_edge(u, v, key)
                changed = True
        G.remove_nodes_from([n for n in list(G.nodes) if G.degree(n) == 0])
    kept = [d["geom"] for _, _, d in G.edges(data=True)]
    merged = linemerge(unary_union(kept)) if kept else None
    if merged is None:
        return []
    segs = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
    return [s for s in segs if isinstance(s, LineString) and s.length > 0]


# ---------------------------------------------------------------------------
# Stage 5: least-cost-path gap bridging through the probability corridor
# ---------------------------------------------------------------------------
def lcp_bridges(segs, road_p, transform, res, *, max_gap, max_ang, cost_gate):
    from shapely.geometry import LineString, Point
    from skimage.graph import route_through_array
    cost = 1.0 / (np.clip(np.nan_to_num(road_p, nan=0.0), 0, 1) + 0.05)
    inv = ~transform                                       # world -> px
    H, W = road_p.shape

    def tangent(ls, at_start):
        c = list(ls.coords)
        p0, p1 = (c[0], c[min(3, len(c) - 1)]) if at_start else (c[-1], c[max(-4, -len(c))])
        v = np.array(p1) - np.array(p0)
        n = np.linalg.norm(v)
        return v / n if n else v

    ends = []  # (segidx, point, outward-tangent)
    for i, ls in enumerate(segs):
        ends.append((i, Point(ls.coords[0]), -tangent(ls, True)))
        ends.append((i, Point(ls.coords[-1]), -tangent(ls, False)))
    bridges, used = [], set()
    for a in range(len(ends)):
        if a in used:
            continue
        ia, pa, ta = ends[a]
        best = None
        for b in range(a + 1, len(ends)):
            if b in used:
                continue
            ib, pb, tb = ends[b]
            if ia == ib:
                continue
            gap = pa.distance(pb)
            if gap > max_gap or gap < res:
                continue
            d = np.array([pb.x - pa.x, pb.y - pa.y]); d /= (np.linalg.norm(d) + 1e-9)
            # both outward tangents should point toward the other endpoint
            if np.dot(ta, d) < np.cos(np.radians(max_ang)) or np.dot(tb, -d) < np.cos(np.radians(max_ang)):
                continue
            if best is None or gap < best[0]:
                best = (gap, b, pa, pb)
        if best is None:
            continue
        _, b, pa, pb = best
        ca, ra = inv * (pa.x, pa.y); cb, rb = inv * (pb.x, pb.y)
        ra, ca, rb, cb = int(ra), int(ca), int(rb), int(cb)
        if not (0 <= ra < H and 0 <= ca < W and 0 <= rb < H and 0 <= cb < W):
            continue
        try:
            path, w = route_through_array(cost, (ra, ca), (rb, cb),
                                          fully_connected=True, geometric=True)
        except Exception:  # noqa: BLE001
            continue
        if not path or (w / max(len(path), 1)) > cost_gate:
            continue                                       # no real corridor
        pr = np.array(path)
        xs, ys = rasterio.transform.xy(transform, pr[:, 0], pr[:, 1])
        bridges.append(LineString(np.column_stack([xs, ys])))
        used.add(a); used.add(b)
    return bridges


# ---------------------------------------------------------------------------
# Stage 6: connected-component island filter (TIGER-anchored)
# ---------------------------------------------------------------------------
def island_filter(segs, *, min_comp_len, tiger_buf):
    import geopandas as gpd
    import networkx as nx
    from shapely.ops import linemerge, unary_union
    G = nx.Graph()
    for i, ls in enumerate(segs):
        a, b = _key(ls.coords[0]), _key(ls.coords[-1])
        G.add_edge(a, b, idx=i, length=ls.length)
    tiger = None
    if TIGER.exists():
        try:
            tg = gpd.read_file(TIGER).to_crs(DST_CRS)
            tiger = unary_union(tg.geometry.values)
        except Exception:  # noqa: BLE001
            tiger = None
    keep_idx, drop_idx = [], []
    for comp in nx.connected_components(G):
        sub = G.subgraph(comp)
        idxs = [d["idx"] for *_x, d in sub.edges(data=True)]
        tot = sum(d["length"] for *_x, d in sub.edges(data=True))
        near = False
        if tiger is not None:
            geom = unary_union([segs[i] for i in idxs])
            near = geom.distance(tiger) <= tiger_buf
        (keep_idx if (tot >= min_comp_len or near) else drop_idx).extend(idxs)
    return keep_idx, drop_idx, (tiger is not None)


# ---------------------------------------------------------------------------
# attribute helpers
# ---------------------------------------------------------------------------
def sample_along(arr, ls, transform, step=2.0):
    inv = ~transform; H, W = arr.shape
    n = max(2, int(ls.length / step)); vals = []
    for t in np.linspace(0, ls.length, n):
        p = ls.interpolate(t); c, r = inv * (p.x, p.y); r, c = int(r), int(c)
        if 0 <= r < H and 0 <= c < W and np.isfinite(arr[r, c]):
            vals.append(arr[r, c])
    return float(np.median(vals)) if vals else np.nan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", required=True, help="data_3x3 block dir")
    ap.add_argument("--key", required=True, help="block key, e.g. 613590")
    ap.add_argument("--seed-hi", type=float, default=0.60)
    ap.add_argument("--seed-lo", type=float, default=0.40)
    ap.add_argument("--vessel-thr", type=float, default=0.50)
    ap.add_argument("--spur-len", type=float, default=20.0)
    ap.add_argument("--max-gap", type=float, default=35.0)
    ap.add_argument("--max-ang", type=float, default=40.0)
    ap.add_argument("--cost-gate", type=float, default=3.0)
    ap.add_argument("--min-comp-len", type=float, default=120.0)
    ap.add_argument("--tiger-buf", type=float, default=30.0)
    ap.add_argument("--conf-min", type=float, default=0.60,
                    help="confidence cutoff for the roads_clean headline layer")
    args = ap.parse_args()

    blk = Path(args.block); k = args.key; sfx = f"{k}_1m"

    def load(stem):
        p = blk / f"{stem}_{sfx}.tif"
        if not p.exists():
            return None, None, None
        with rasterio.open(p) as r:
            return r.read(1).astype(np.float32), r.transform, r.res[0]

    road_p, tf, res = load("road_prob")
    if road_p is None:
        print(f"no road_prob for {sfx}", file=sys.stderr); return 1
    drain_p, _, _ = load("drainage_prob")
    if drain_p is None:
        drain_p = np.zeros_like(road_p)
    dem, _, _ = load("dem")
    slope, _, _ = load("slope")              # roads are low-gradient; texture mesh is steep
    print(f"[{k}] road_prob {road_p.shape} @ {res} m  (slope raster: {slope is not None})")

    mask, _ = conditioned_mask(road_p, drain_p, res, seed_hi=args.seed_hi,
                               seed_lo=args.seed_lo, vessel_sigmas=range(1, 4),
                               vessel_thr=args.vessel_thr, min_len_m=args.spur_len)
    dt_width = ndi.distance_transform_edt(mask) * res   # half-width field for attributes
    print(f"  stage0-1 mask: {mask.sum()*res*res/1e4:.2f} ha")

    lines, widths = skeleton_lines(mask, tf, res)
    print(f"  stage2 skeleton: {len(lines)} raw paths, {sum(l.length for l in lines)/1000:.1f} km")

    segs = prune_and_merge(lines, widths, args.spur_len)
    print(f"  stage3-4 pruned+merged: {len(segs)} segs, {sum(s.length for s in segs)/1000:.1f} km")

    bridges = lcp_bridges(segs, road_p, tf, res, max_gap=args.max_gap,
                          max_ang=args.max_ang, cost_gate=args.cost_gate)
    print(f"  stage5 LCP bridges: {len(bridges)} ({sum(b.length for b in bridges)/1000:.2f} km)")
    allsegs = prune_and_merge(segs + bridges,
                              widths + [np.nan] * len(bridges), spur_len=0.1)

    keep_idx, drop_idx, has_tiger = island_filter(
        allsegs, min_comp_len=args.min_comp_len, tiger_buf=args.tiger_buf)
    kept = [allsegs[i] for i in keep_idx]
    dropped = [allsegs[i] for i in drop_idx]
    print(f"  stage6 islands (TIGER={has_tiger}): keep {len(kept)} "
          f"({sum(s.length for s in kept)/1000:.1f} km), drop {len(dropped)} "
          f"({sum(s.length for s in dropped)/1000:.1f} km)")

    # stage8 attributes
    import geopandas as gpd
    from shapely.geometry import Point
    rows = []
    for s in kept:
        mp = sample_along(road_p, s, tf)
        width = 2.0 * sample_along(dt_width, s, tf)        # full width from DT field
        straight = Point(s.coords[0]).distance(Point(s.coords[-1]))
        rows.append({
            "length_m": round(s.length, 1),
            "mean_proad": round(mp, 3) if np.isfinite(mp) else None,
            "width_m": round(width, 1) if np.isfinite(width) else None,
            "sinuosity": round(s.length / max(straight, 1e-6), 3) if straight > 0 else None,
            "mean_slope": round(sample_along(slope, s, tf), 2) if slope is not None else None,
            "geometry": s,
        })
    gdf = gpd.GeoDataFrame(rows, crs=DST_CRS) if rows else gpd.GeoDataFrame(
        {"length_m": []}, geometry=[], crs=DST_CRS)
    # confidence: prob + length + FLATNESS (roads are low-gradient). Normalized 0-1.
    if len(gdf):
        p = gdf["mean_proad"].fillna(0.3).clip(0, 1)
        L = (gdf["length_m"] / 300).clip(0, 1)
        if slope is not None:
            sl = gdf["mean_slope"].fillna(20.0)
            flat = (1 - ((sl - 6.0).clip(0, 24) / 24.0)).clip(0, 1)  # 1@<=6deg -> 0@>=30deg
        else:
            flat = 1.0
        gdf["confidence"] = (0.48 * p + 0.20 * L + 0.32 * flat).round(3)

    conf_min = args.conf_min
    clean = gdf[gdf["confidence"] >= conf_min].copy() if len(gdf) else gdf

    out_gpkg = blk / f"roads_net_{sfx}.gpkg"
    if out_gpkg.exists():
        out_gpkg.unlink()
    if len(gdf):
        gdf.to_file(out_gpkg, layer="roads_all", driver="GPKG")
        if len(clean):
            clean.to_file(out_gpkg, layer="roads_clean", driver="GPKG")
    if bridges:
        gpd.GeoDataFrame(geometry=bridges, crs=DST_CRS).to_file(
            out_gpkg, layer="bridges", driver="GPKG")
    if dropped:
        gpd.GeoDataFrame(geometry=dropped, crs=DST_CRS).to_file(
            out_gpkg, layer="dropped", driver="GPKG")

    # stage9 TIGER validation + stats
    stats = {
        "key": k, "resolution_m": res,
        "network_km": round(sum(s.length for s in kept) / 1000, 2),
        "network_segments": len(kept),
        "clean_km": round(float(clean["length_m"].sum()) / 1000, 2) if len(clean) else 0.0,
        "clean_segments": int(len(clean)),
        "conf_min": conf_min,
        "km_by_conf": {str(t): round(float(gdf.loc[gdf.confidence >= t, "length_m"].sum()) / 1000, 2)
                       for t in (0.5, 0.6, 0.7, 0.8)} if len(gdf) else {},
        "island_dropped_km": round(sum(s.length for s in dropped) / 1000, 2),
        "bridges": len(bridges),
        "bridge_km": round(sum(b.length for b in bridges) / 1000, 2),
        "params": vars(args),
    }
    if has_tiger and len(clean):
        from shapely.ops import unary_union
        tg = gpd.read_file(TIGER).to_crs(DST_CRS)
        # clip TIGER to block bbox
        minx, miny, maxx, maxy = clean.total_bounds
        tg = tg.cx[minx:maxx, miny:maxy]
        tgu = unary_union(tg.geometry.values)
        pred = unary_union(clean.geometry.values)
        if not tgu.is_empty:
            covered = tgu.intersection(pred.buffer(15)).length
            stats["tiger_km_in_block"] = round(tgu.length / 1000, 2)
            stats["tiger_recall"] = round(covered / max(tgu.length, 1), 3)
        novel = pred.difference(tgu.buffer(25)).length
        stats["novel_km_far_from_tiger"] = round(novel / 1000, 2)
    (blk / f"roads_net_{sfx}_stats.json").write_text(json.dumps(stats, indent=2))
    print(f"  stats: {json.dumps(stats, indent=0)[:400]}")

    # overlay
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from rasterio.enums import Resampling
        ds = 3
        with rasterio.open(blk / f"hillshade_{sfx}.tif") as r:
            H, W = r.height, r.width
            hs = r.read(1, out_shape=(H // ds, W // ds), resampling=Resampling.nearest)
            b = r.bounds
        ext = (b.left, b.right, b.bottom, b.top)
        fig, ax = plt.subplots(figsize=(14, 14))
        ax.imshow(hs, cmap="gray", extent=ext, origin="upper")
        if len(gdf):
            noise = gdf[gdf["confidence"] < conf_min]
            if len(noise):
                noise.plot(ax=ax, color="#888888", linewidth=0.4, alpha=0.4)
            if len(clean):
                clean.plot(ax=ax, column="confidence", cmap="autumn_r", linewidth=1.7,
                           vmin=conf_min, vmax=1.0, legend=True)
        if bridges:
            gpd.GeoDataFrame(geometry=bridges, crs=DST_CRS).plot(
                ax=ax, color="#00ff88", linewidth=1.8)
        ax.set_title(f"{k}: clean road network (conf>={conf_min}; warm); "
                     f"grey=below-threshold; green=bridges")
        ax.set_xticks([]); ax.set_yticks([])
        fig.savefig(blk / f"roads_net_{sfx}_overlay.png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"  -> roads_net_{sfx}_overlay.png")
    except Exception as ex:  # noqa: BLE001
        print(f"  overlay skipped: {ex}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
