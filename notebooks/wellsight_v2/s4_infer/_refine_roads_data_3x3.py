"""Post-process the raw road U-Net rasters into clean, connected road centerlines.

The 1 m road model (`road_unet_1m`, see [[road_unet_1m]]) produces good per-block
`road_prob_<key>_1m.tif` rasters but two artifacts remain:

  1. DRAINAGE / WATERWAY FALSE POSITIVES. Incised stream channels are linear
     concave features and look like cut roads to the model. We discriminate with
     the validated cross-section concavity test (`_xdrop`, ported from
     `_filter_streams_xsec_9t.py`): sample the RAW DEM perpendicular to each line
     and compute  xdrop_m = median( mean(z_left, z_right) - z_center ).
     A drainage channel sits in a V/U (xdrop_m > 0); a graded road-cut is
     flat-to-convex (xdrop_m ~ 0). Chunks with xdrop_m >= --drop are reclassed
     'drainage' and dropped. (Same test as the stream filter, KEEP polarity
     flipped: there roadlike=drop, here drainage=drop.)

  2. FRAGMENTATION. Roads that should be continuous come out in pieces. We close
     hairline gaps with a small morphological closing, then bridge medium gaps at
     the vector level with bearing-aware endpoint snapping: two line endpoints
     within --gap metres whose OUTWARD tangents point at each other within
     --ang degrees get a straight connector.

Pipeline per block (operates on road_prob_<key>_1m.tif + raw dem_<key>_1m.tif):
    prob >= --thr  ->  remove_small_objects  ->  binary_closing
      ->  skeletonize  ->  skan trace to LineStrings (world coords)
      ->  endpoint gap-bridge  ->  linemerge
      ->  xdrop drainage filter (chunked)  ->  drop short stubs
      ->  re-rasterize kept roads (buffer --buf) + write gpkg + overlay PNG

Outputs into the block dir:
    roads_<key>_1m.gpkg            layer 'roads' (kept centerlines, + xdrop_m,
                                   bridge flag), layer 'drainage' (dropped)
    road_clean_<key>_1m.tif        uint8 0/1 cleaned road raster
    road_clean_overlay_<key>_1m.png  hillshade + kept(red)/drainage(cyan)/bridge(yellow)

CLI:
  python notebooks/wellsight/build/_refine_roads_data_3x3.py --only 609590      # pilot
  python notebooks/wellsight/build/_refine_roads_data_3x3.py --list
  python notebooks/wellsight/build/_refine_roads_data_3x3.py                     # all blocks
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio import features as rfeatures
from scipy import ndimage as ndi
from shapely.geometry import LineString
from shapely.ops import linemerge, unary_union
from skimage.morphology import (binary_closing, disk, remove_small_objects,
                                 skeletonize)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, path_for  # noqa: E402

REGION = "westernpa_d20"

# ---- tunable params (defaults chosen on the 604603 + 609590 pilots) ---------
PROB_THR = 0.50        # P(road) binarization threshold
MIN_AREA = 250         # drop connected components smaller than this (px ~ m^2)
CLOSE_PX = 3           # morphological closing radius (px) for hairline gaps
GAP_M = 25.0           # max endpoint-snap distance (m)
ANG_TOL = 35.0         # max bearing mismatch for a bridge (deg)
CHUNK_M = 25.0         # xdrop chunk length (m)
PERP_M = 6.0           # xdrop perpendicular sample offset (m)
DROP_STRONG = 0.60     # xdrop_m >= this -> drainage by DEPTH alone (headwater
                       #   hollows below the flow-accum threshold). Set high so
                       #   shallow road-cuts on flat ground are NOT dropped.
DROP_MILD = 0.35       # xdrop_m needed for a stream-coincident chunk to count
                       #   as drainage. Catchment lets us trust milder concavity,
                       #   but a FLAT road-ditch (D8 routes down it on flat
                       #   terrain) stays below this -> kept.
STREAM_TH = 4000       # D8 flow-accum threshold (cells = m^2) to map a channel
STREAM_BUF_PX = 3      # dilate mapped streams this many px before testing cover
COVER_FRAC = 0.50      # frac of a line on a mapped stream -> drainage (catchment)
MIN_LINE_M = 35.0      # drop kept stubs shorter than this (m)
BUF_M = 1.5            # re-rasterization buffer (matches label build)


# ---------------------------------------------------------------------------
# cross-section concavity (verbatim logic from _filter_streams_xsec_9t.py)
# ---------------------------------------------------------------------------
def _resample(line: LineString, step: float) -> np.ndarray:
    n = max(2, int(np.ceil(line.length / step)) + 1)
    ts = np.linspace(0, line.length, n)
    return np.array([[p.x, p.y] for p in (line.interpolate(t) for t in ts)])


def _sample_dem(xs, ys, dem, tf) -> np.ndarray:
    cols = ((xs - tf.c) / tf.a).astype(int)
    rows = ((ys - tf.f) / tf.e).astype(int)
    H, W = dem.shape
    out = np.full(len(xs), np.nan, dtype=np.float32)
    ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    out[ok] = dem[rows[ok], cols[ok]]
    return out


def _xdrop(line, dem, tf, *, step, perp_m):
    if line.length < step * 2:
        return None
    pts = _resample(line, step)
    xs, ys = pts[:, 0], pts[:, 1]
    dx = np.gradient(xs); dy = np.gradient(ys)
    tlen = np.hypot(dx, dy); tlen[tlen < 1e-6] = 1.0
    tx, ty = dx / tlen, dy / tlen
    px, py = -ty, tx
    zc = _sample_dem(xs,             ys,             dem, tf)
    zl = _sample_dem(xs - px*perp_m, ys - py*perp_m, dem, tf)
    zr = _sample_dem(xs + px*perp_m, ys + py*perp_m, dem, tf)
    drop = (zl + zr) * 0.5 - zc
    ok = np.isfinite(drop)
    if ok.sum() < 2:
        return None
    return float(np.median(drop[ok]))


def _chunk_line(line, chunk_m):
    if line.length <= chunk_m:
        return [line]
    out = []
    n = int(np.ceil(line.length / chunk_m))
    edges = np.linspace(0.0, line.length, n + 1)
    for t0, t1 in zip(edges[:-1], edges[1:]):
        inner_n = max(2, int(np.ceil((t1 - t0) / 5.0)) + 1)
        ts = np.linspace(t0, t1, inner_n)
        out.append(LineString([(p.x, p.y)
                               for p in (line.interpolate(t) for t in ts)]))
    return out


# ---------------------------------------------------------------------------
# per-block D8 hydrology: mapped flow-accumulation stream network
# ---------------------------------------------------------------------------
def build_block_streams(block, key, dem_p, threshold, *, overwrite=False):
    """Return path to a uint8 0/1 stream-seed raster for the block, built with
    WhiteboxTools (breach -> d8 pointer -> flow accum -> extract_streams) and
    cached. Heavy intermediates (breach, accum) are deleted after; only the
    small seed raster is kept."""
    seed = block / f"stream_seed_t{threshold}_{key}_1m.tif"
    if seed.exists() and not overwrite:
        return seed
    import whitebox
    wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(block.resolve()))
    breach = f"_dem_breached_{key}.tif"
    pntr = f"_d8pntr_{key}.tif"; accum = f"_d8accum_{key}.tif"
    raw = f"_streams_{key}.tif"
    wbt.breach_depressions_least_cost(dem=dem_p.name, output=breach,
                                      dist=50, flat_increment=1e-3)
    wbt.d8_pointer(dem=breach, output=pntr)
    wbt.d8_flow_accumulation(i=breach, output=accum, out_type="cells", log=False)
    wbt.extract_streams(flow_accum=accum, output=raw, threshold=threshold)
    with rasterio.open(block / raw) as r:
        arr = r.read(1); nd = r.nodata; prof = r.profile.copy()
    sm = np.isfinite(arr) & (arr != (nd if nd is not None else -9999))
    prof.update(dtype="uint8", nodata=255, compress="deflate")
    with rasterio.open(seed, "w", **prof) as ds:
        ds.write(sm.astype(np.uint8), 1)
    for nm in (breach, pntr, accum, raw):
        (block / nm).unlink(missing_ok=True)
    return seed


def _stream_cover(line, stream_mask, tf, step=2.5):
    """Fraction of a line's sampled points that fall on the (dilated) stream
    mask — the catchment-coincidence signal."""
    pts = _resample(line, step)
    cols = ((pts[:, 0] - tf.c) / tf.a).astype(int)
    rows = ((pts[:, 1] - tf.f) / tf.e).astype(int)
    H, W = stream_mask.shape
    ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    if ok.sum() == 0:
        return 0.0
    return float(stream_mask[rows[ok], cols[ok]].mean())


# ---------------------------------------------------------------------------
# vectorize skeleton -> world-coord LineStrings via skan
# ---------------------------------------------------------------------------
def skeleton_to_lines(mask, transform):
    from skan import Skeleton
    skel = skeletonize(mask)
    if skel.sum() < 2:
        return []
    try:
        sk = Skeleton(skel)
    except ValueError:
        return []
    lines = []
    a, e, c, f = transform.a, transform.e, transform.c, transform.f
    for i in range(sk.n_paths):
        rc = sk.path_coordinates(i)          # (N,2) rows,cols in pixel space
        if len(rc) < 2:
            continue
        xs = c + (rc[:, 1] + 0.5) * a
        ys = f + (rc[:, 0] + 0.5) * e
        ls = LineString(np.column_stack([xs, ys]))
        if ls.length > 0:
            lines.append(ls)
    return lines


# ---------------------------------------------------------------------------
# bearing-aware endpoint gap bridging
# ---------------------------------------------------------------------------
def _endpoint_bearing(line, which, sample_m=8.0):
    """Outward unit bearing at an endpoint ('start' or 'end')."""
    L = line.length
    if which == "start":
        p0 = np.array(line.coords[0])
        p1 = np.array(line.interpolate(min(sample_m, L)).coords[0])
        v = p0 - p1                      # points outward from the line
    else:
        p0 = np.array(line.coords[-1])
        p1 = np.array(line.interpolate(max(0.0, L - sample_m)).coords[0])
        v = p0 - p1
    n = np.hypot(*v)
    return v / n if n > 1e-6 else np.array([0.0, 0.0])


def bridge_gaps(lines, gap_m, ang_tol_deg):
    """Add straight connectors between compatible endpoints. Returns
    (all_lines_incl_bridges, n_bridges, bridge_geoms)."""
    cos_tol = np.cos(np.radians(ang_tol_deg))
    eps = []  # (line_idx, which, point(np2), bearing(np2))
    for li, ln in enumerate(lines):
        for which in ("start", "end"):
            pt = np.array(ln.coords[0] if which == "start" else ln.coords[-1])
            eps.append([li, which, pt, _endpoint_bearing(ln, which)])
    used = set()
    bridges = []
    for i in range(len(eps)):
        if i in used:
            continue
        li, wi, pi, bi = eps[i]
        best, best_d = None, gap_m
        for j in range(len(eps)):
            if j == i or j in used:
                continue
            lj, wj, pj, bj = eps[j]
            if lj == li:
                continue
            d = float(np.hypot(*(pj - pi)))
            if d < 1e-3 or d > best_d:
                continue
            conn = (pj - pi) / d                 # unit i->j
            # i's outward bearing should align with i->j, j's with j->i
            if np.dot(bi, conn) < cos_tol:
                continue
            if np.dot(bj, -conn) < cos_tol:
                continue
            best, best_d = j, d
        if best is not None:
            used.add(i); used.add(best)
            bridges.append(LineString([tuple(pi), tuple(eps[best][2])]))
    return lines + bridges, len(bridges), bridges


# ---------------------------------------------------------------------------
# per-block driver
# ---------------------------------------------------------------------------
def refine_block(block: Path, key: str, *, args) -> dict:
    prob_p = block / f"road_prob_{key}_1m.tif"
    dem_p = block / f"dem_{key}_1m.tif"
    hs_p = block / f"hillshade_{key}_1m.tif"
    if not prob_p.exists() or not dem_p.exists():
        print(f"  [{key}] missing prob/dem — skip"); return {}

    with rasterio.open(prob_p) as r:
        prob = r.read(1).astype(np.float32)
        pnd = r.nodata
        tf = r.transform
        crs = r.crs or DST_CRS
        H, W = prob.shape
    valid = np.isfinite(prob) & (prob != (pnd if pnd is not None else -1.0))

    with rasterio.open(dem_p) as r:
        dem = r.read(1).astype(np.float32)
        dnd = r.nodata
    if dnd is not None:
        dem[dem == dnd] = np.nan

    # hydrology: mapped D8 stream network (catchment evidence), dilated
    stream_dil = None
    if not args.no_hydro:
        try:
            seed_p = build_block_streams(block, key, dem_p, args.stream_th)
            with rasterio.open(seed_p) as r:
                sm = r.read(1)
                snd = r.nodata
            sm = (sm == 1)
            if args.stream_buf_px > 0:
                sm = ndi.binary_dilation(sm, disk(args.stream_buf_px))
            stream_dil = sm
        except Exception as ex:  # WBT missing / failure -> depth-only fallback
            print(f"  [{key}] hydrology unavailable ({ex}); xdrop-depth only")

    # 1) binarize + denoise + close hairline gaps
    mask = (prob >= args.thr) & valid
    raw_px = int(mask.sum())
    mask = remove_small_objects(mask, min_size=args.min_area)
    if args.close_px > 0:
        mask = binary_closing(mask, disk(args.close_px))
    mask &= valid

    # 2) vectorize
    lines = skeleton_to_lines(mask, tf)
    if not lines:
        print(f"  [{key}] no skeleton lines after denoise"); return {}

    # 3) bridge gaps, then merge collinear pieces
    alllines, n_bridge, bridge_geoms = bridge_gaps(lines, args.gap, args.ang)
    merged = linemerge(unary_union(alllines))
    if merged.geom_type == "LineString":
        merged_lines = [merged]
    else:
        merged_lines = [g for g in merged.geoms if g.geom_type == "LineString"]

    # 4) drainage filter (chunked): drop a chunk if it COINCIDES with a mapped
    #    stream (catchment) OR is deeply concave (xdrop >= drop_strong). A flat-
    #    ground road in a shallow cut has neither -> kept.
    keep_geoms, keep_drop, drain_geoms = [], [], []
    for ln in merged_lines:
        for seg in _chunk_line(ln, args.chunk):
            if seg.length < 10.0:
                keep_geoms.append(seg); keep_drop.append(np.nan); continue
            d = _xdrop(seg, dem, tf, step=2.5, perp_m=args.perp)
            cover = (_stream_cover(seg, stream_dil, tf)
                     if stream_dil is not None else 0.0)
            # hydrology catch: coincides with a mapped stream AND is at least
            # mildly concave. The concavity gate is what rejects flat-terrain
            # road ditches (D8 routes flow down them but they're flat-bottomed).
            hydro_drain = (cover >= args.cover_frac
                           and d is not None and d >= args.drop_mild)
            depth_drain = (d is not None and d >= args.drop_strong)
            if hydro_drain or depth_drain:
                drain_geoms.append(seg)
            else:
                keep_geoms.append(seg); keep_drop.append(d)

    # re-merge kept chunks, drop short stubs
    if keep_geoms:
        km = linemerge(unary_union(keep_geoms))
        kept = ([km] if km.geom_type == "LineString"
                else [g for g in km.geoms if g.geom_type == "LineString"])
    else:
        kept = []
    kept = [g for g in kept if g.length >= args.min_line]

    # 5) outputs ---------------------------------------------------------
    gkept = gpd.GeoDataFrame({"length_m": [g.length for g in kept]},
                             geometry=kept, crs=crs)
    out_gpkg = block / f"roads_{key}_1m.gpkg"
    if len(gkept):
        gkept.to_file(out_gpkg, layer="roads", driver="GPKG")
    if drain_geoms:
        gdr = gpd.GeoDataFrame({"length_m": [g.length for g in drain_geoms]},
                               geometry=drain_geoms, crs=crs)
        gdr.to_file(out_gpkg, layer="drainage", driver="GPKG")

    # re-rasterize kept roads
    clean = np.zeros((H, W), np.uint8)
    if len(gkept):
        shapes = [(geom.buffer(args.buf), 1) for geom in gkept.geometry]
        clean = rfeatures.rasterize(shapes, out_shape=(H, W), transform=tf,
                                    fill=0, dtype="uint8")
    clean[~valid] = 0
    prof = dict(driver="GTiff", height=H, width=W, count=1, dtype="uint8",
                nodata=0, crs=crs, transform=tf, compress="deflate", tiled=True,
                blockxsize=512, blockysize=512)
    with rasterio.open(block / f"road_clean_{key}_1m.tif", "w", **prof) as ds:
        ds.write(clean, 1)

    # overlay
    if hs_p.exists():
        with rasterio.open(hs_p) as r:
            hs = r.read(1)
        ext = [tf.c, tf.c + W * tf.a, tf.f + H * tf.e, tf.f]
        fig, ax = plt.subplots(figsize=(13, 13), dpi=130)
        ax.imshow(hs, cmap="gray", extent=ext, interpolation="nearest")
        for g in drain_geoms:
            x, y = g.xy; ax.plot(x, y, color="#00d0d0", lw=0.7, alpha=0.9)
        for g in kept:
            x, y = g.xy; ax.plot(x, y, color="#e41a1c", lw=1.0, alpha=0.95)
        for g in bridge_geoms:
            x, y = g.xy; ax.plot(x, y, color="#ffd700", lw=1.2, alpha=0.95)
        ax.set_title(f"{key}: roads (red) | drainage dropped (cyan) | "
                     f"bridges (yellow)\nkept {sum(g.length for g in kept)/1000:.1f} km, "
                     f"drainage {sum(g.length for g in drain_geoms)/1000:.1f} km, "
                     f"{n_bridge} bridges")
        ax.set_aspect("equal"); ax.set_xlabel("Easting"); ax.set_ylabel("Northing")
        fig.savefig(block / f"road_clean_overlay_{key}_1m.png",
                    bbox_inches="tight")
        plt.close(fig)

    clean_px = int(clean.sum())
    stats = dict(key=key, raw_px=raw_px, clean_px=clean_px,
                 kept_km=sum(g.length for g in kept) / 1000.0,
                 drain_km=sum(g.length for g in drain_geoms) / 1000.0,
                 n_kept=len(kept), n_drain=len(drain_geoms), n_bridge=n_bridge)
    print(f"  [{key}] raw {raw_px:,}px -> clean {clean_px:,}px | "
          f"roads {stats['kept_km']:.1f}km ({len(kept)}) | "
          f"drainage dropped {stats['drain_km']:.1f}km ({len(drain_geoms)}) | "
          f"{n_bridge} bridges")
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="single block key, e.g. 609590")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--thr", type=float, default=PROB_THR)
    ap.add_argument("--min-area", type=int, default=MIN_AREA, dest="min_area")
    ap.add_argument("--close-px", type=int, default=CLOSE_PX, dest="close_px")
    ap.add_argument("--gap", type=float, default=GAP_M)
    ap.add_argument("--ang", type=float, default=ANG_TOL)
    ap.add_argument("--chunk", type=float, default=CHUNK_M)
    ap.add_argument("--perp", type=float, default=PERP_M)
    ap.add_argument("--drop-strong", type=float, default=DROP_STRONG,
                    dest="drop_strong", help="xdrop_m depth that alone marks "
                    "drainage (headwater hollows)")
    ap.add_argument("--drop-mild", type=float, default=DROP_MILD,
                    dest="drop_mild", help="xdrop_m needed for a stream-"
                    "coincident chunk to count as drainage")
    ap.add_argument("--stream-th", type=int, default=STREAM_TH, dest="stream_th",
                    help="D8 flow-accum threshold (cells) to map a channel")
    ap.add_argument("--stream-buf-px", type=int, default=STREAM_BUF_PX,
                    dest="stream_buf_px")
    ap.add_argument("--cover-frac", type=float, default=COVER_FRAC,
                    dest="cover_frac", help="frac of a line on a mapped stream "
                    "to call it drainage")
    ap.add_argument("--no-hydro", action="store_true",
                    help="skip D8 hydrology; use xdrop depth only")
    ap.add_argument("--min-line", type=float, default=MIN_LINE_M, dest="min_line")
    ap.add_argument("--buf", type=float, default=BUF_M)
    args = ap.parse_args()

    root = path_for("data_3x3") / REGION
    blocks = sorted(p for p in root.iterdir()
                    if p.is_dir() and (p / f"road_prob_{p.name}_1m.tif").exists())
    if args.list:
        print(f"{len(blocks)} block(s):",
              ", ".join(p.name for p in blocks)); return 0
    if args.only:
        blocks = [p for p in blocks if p.name == args.only]
        if not blocks:
            print(f"no block {args.only}", file=sys.stderr); return 1

    print(f"refine: thr={args.thr} min_area={args.min_area} close={args.close_px}px "
          f"gap={args.gap}m ang={args.ang} | drainage: "
          f"{'NO-HYDRO ' if args.no_hydro else f'streams(t{args.stream_th},cover>={args.cover_frac}) '}"
          f"or xdrop>={args.drop_strong}m on {len(blocks)} block(s)")
    t0 = time.time()
    allstats = []
    for b in blocks:
        print(f"=== {b.name} ===")
        s = refine_block(b, b.name, args=args)
        if s:
            allstats.append(s)
    dt = (time.time() - t0) / 60
    print(f"\nDONE {len(allstats)}/{len(blocks)} in {dt:.1f} min")
    if allstats:
        tot_k = sum(s["kept_km"] for s in allstats)
        tot_d = sum(s["drain_km"] for s in allstats)
        tot_b = sum(s["n_bridge"] for s in allstats)
        print(f"  totals: roads {tot_k:.1f} km | drainage dropped {tot_d:.1f} km | "
              f"{tot_b} bridges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
