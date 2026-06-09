"""Chunked cross-section road filter for the t=5000 streams on McKean.

Same cross-section concavity test as _filter_streams_xsection_mckean.py, but
**each input linestring is first chopped into fixed-length sub-segments**
before classification. That gives one ``klass`` label per chunk instead of
one per (sometimes very long) line, so editing in QGIS lets you delete a
single ~25 m piece of a misidentified road without losing the rest of the
adjacent real stream.

Per sub-segment we compute:
    xdrop_m  = median (mean(z_left, z_right) - z_center)
               sampled perpendicular to the segment, PERP_M off either side

Classification:
    short     length < MIN_LEN_M (too short to compute reliable xdrop)
    roadlike  xdrop_m  <  DROP_MIN_M
    stream    otherwise

Output columns: parent_id (original feature index), seg_idx (chunk number
within the parent), seg_len_m, xdrop_m, klass.

Outputs per block:
    streams_t5000_<key>_chunked_xsec.shp           all chunks
    streams_t5000_<key>_chunked_kept_xsec.shp      klass != roadlike
    streams_t5000_<key>_chunked_roadlike_xsec.shp  klass == roadlike

CLI:
  python notebooks/wellsight/build/_filter_streams_chunked_mckean.py
  python notebooks/wellsight/build/_filter_streams_chunked_mckean.py --chunk 50
  python notebooks/wellsight/build/_filter_streams_chunked_mckean.py --chunk 25 --drop 0.25
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV

REGION = DERIV / "tiles" / "data_3x3" / "northcentral_b19"
THRESHOLD = 5000
SAMPLE_STEP_M = 2.5  # perpendicular samples this densely within a chunk
MIN_LEN_M = 15.0     # below this a chunk is "short" (not classified)


def _chunk_line(line: LineString, chunk_m: float) -> list[LineString]:
    """Walk the line and emit equal-length sub-linestrings. The final chunk
    is whatever's left (may be shorter than ``chunk_m``)."""
    if line.length <= chunk_m:
        return [line]
    out: list[LineString] = []
    n = int(np.ceil(line.length / chunk_m))
    edges = np.linspace(0.0, line.length, n + 1)
    for t0, t1 in zip(edges[:-1], edges[1:]):
        # Sample along the parent line at a few intermediate points so the
        # sub-segment follows the original geometry (instead of a straight
        # chord from t0 to t1).
        inner_n = max(2, int(np.ceil((t1 - t0) / 5.0)) + 1)
        ts = np.linspace(t0, t1, inner_n)
        pts = [line.interpolate(t) for t in ts]
        out.append(LineString([(p.x, p.y) for p in pts]))
    return out


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


def _xdrop(line: LineString, dem, tf, *, step: float, perp_m: float) -> float | None:
    if line.length < step * 2:
        return None
    pts = _resample(line, step)
    xs, ys = pts[:, 0], pts[:, 1]
    dx = np.gradient(xs); dy = np.gradient(ys)
    tlen = np.hypot(dx, dy); tlen[tlen < 1e-6] = 1.0
    tx, ty = dx / tlen, dy / tlen
    px, py = -ty, tx
    zc = _sample_dem(xs,              ys,              dem, tf)
    zl = _sample_dem(xs - px*perp_m,  ys - py*perp_m,  dem, tf)
    zr = _sample_dem(xs + px*perp_m,  ys + py*perp_m,  dem, tf)
    drop = (zl + zr) * 0.5 - zc
    ok = np.isfinite(drop)
    if ok.sum() < 2:
        return None
    return float(np.median(drop[ok]))


def classify_block(key: str, work: Path, *, chunk_m: float, perp_m: float,
                   drop_min: float) -> None:
    shp = work / f"streams_t{THRESHOLD}_{key}_1m.shp"
    dem_path = work / f"dem_{key}_1m.tif"
    if not (shp.exists() and dem_path.exists()):
        print(f"[{key}] missing inputs, skip"); return

    g_in = gpd.read_file(shp)
    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        nodata = r.nodata
        tf = r.transform
        crs = r.crs
    if nodata is not None:
        dem[dem == nodata] = np.nan

    rows: list[dict] = []
    for parent_id, geom in enumerate(g_in.geometry):
        if geom is None or geom.is_empty:
            continue
        for seg_idx, seg in enumerate(_chunk_line(geom, chunk_m)):
            rec = {"parent_id": parent_id, "seg_idx": seg_idx,
                   "seg_len_m": float(seg.length),
                   "xdrop_m": np.nan, "klass": "stream",
                   "geometry": seg}
            if seg.length < MIN_LEN_M:
                rec["klass"] = "short"
            else:
                d = _xdrop(seg, dem, tf, step=SAMPLE_STEP_M, perp_m=perp_m)
                if d is None:
                    rec["klass"] = "short"
                else:
                    rec["xdrop_m"] = d
                    if d < drop_min:
                        rec["klass"] = "roadlike"
            rows.append(rec)

    g = gpd.GeoDataFrame(rows, crs=crs or "EPSG:6346")
    out_all = work / f"streams_t{THRESHOLD}_{key}_chunked_xsec.shp"
    out_keep = work / f"streams_t{THRESHOLD}_{key}_chunked_kept_xsec.shp"
    out_road = work / f"streams_t{THRESHOLD}_{key}_chunked_roadlike_xsec.shp"
    g.to_file(out_all)
    g.loc[g.klass != "roadlike"].to_file(out_keep)
    g.loc[g.klass == "roadlike"].to_file(out_road)

    n_total = len(g)
    n_road = int((g.klass == "roadlike").sum())
    n_keep = int((g.klass == "stream").sum())
    n_short = int((g.klass == "short").sum())
    km = lambda mask: float(g.loc[mask].length.sum()) / 1000.0
    print(f"[{key}] chunks={n_total} ({km(g.klass==g.klass):.1f} km from "
          f"{len(g_in)} parent lines)  "
          f"keep={n_keep} ({km(g.klass=='stream'):.1f} km)  "
          f"road={n_road} ({km(g.klass=='roadlike'):.1f} km)  "
          f"short={n_short} ({km(g.klass=='short'):.1f} km)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated key filter")
    ap.add_argument("--chunk", type=float, default=25.0,
                    help="chunk length (m), default 25")
    ap.add_argument("--perp", type=float, default=5.0,
                    help="perpendicular sample distance (m), default 5")
    ap.add_argument("--drop", type=float, default=0.30,
                    help="xdrop_m below this is roadlike (default 0.30)")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    blocks = sorted(p for p in REGION.iterdir() if p.is_dir())
    if only:
        blocks = [b for b in blocks if b.name in only]
    if not blocks:
        print("no McKean blocks found", file=sys.stderr); return 1

    print(f"chunk={args.chunk:.0f} m  perp={args.perp:.0f} m  "
          f"xdrop_m < {args.drop:.2f} -> roadlike")
    for sub in blocks:
        classify_block(sub.name, sub, chunk_m=args.chunk,
                        perp_m=args.perp, drop_min=args.drop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
