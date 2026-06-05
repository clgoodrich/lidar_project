"""Cross-section road filter for the t=5000 stream linestrings on the 9t tile.

Port of the McKean filters (_filter_streams_xsection_mckean.py +
_filter_streams_chunked_mckean.py) to the single 9t mosaic. Runs BOTH passes:

  * per-line   -> streams_t5000_9t_{xsec,kept_xsec,roadlike_xsec}.shp
  * per-chunk  -> streams_t5000_9t_chunked_{xsec,kept_xsec,roadlike_xsec}.shp

Concavity test: at samples along each (sub)line, take the tangent, rotate 90 deg,
sample the DEM PERP_M off each side, and compute
    xdrop_m = median( mean(z_left, z_right) - z_center ).
A real channel sits in a V/U (xdrop_m > 0); a road cut / graded surface is
flat-to-convex (xdrop_m <= ~0). Lines/chunks with xdrop_m < DROP_MIN are
classed 'roadlike' and dropped from the *_kept_* outputs.

Uses the RAW 1 m DEM (dem_9t_1m.tif), NOT the breached DEM — breaching fills
channels and would destroy the very concavity this test measures.

CLI:
  python notebooks/wellsight/build/_filter_streams_xsec_9t.py
  python notebooks/wellsight/build/_filter_streams_xsec_9t.py --chunk 25 --perp 5 --drop 0.30
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
from _common import DERIV  # noqa: E402

OUT_DIR = DERIV / "9t"
THRESHOLD = 5000
DEM_PATH = DERIV / "dem_9t_1m.tif"                       # raw DEM (not breached)
STREAMS = OUT_DIR / f"streams_t{THRESHOLD}_9t_1m.shp"

# Per-line pass params (match _filter_streams_xsection_mckean.py).
LINE_STEP_M = 5.0
LINE_MIN_LEN_M = 30.0
# Per-chunk pass params (match _filter_streams_chunked_mckean.py).
CHUNK_STEP_M = 2.5
CHUNK_MIN_LEN_M = 15.0


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
    zc = _sample_dem(xs,             ys,             dem, tf)
    zl = _sample_dem(xs - px*perp_m, ys - py*perp_m, dem, tf)
    zr = _sample_dem(xs + px*perp_m, ys + py*perp_m, dem, tf)
    drop = (zl + zr) * 0.5 - zc
    ok = np.isfinite(drop)
    if ok.sum() < 2:
        return None
    return float(np.median(drop[ok]))


def _chunk_line(line: LineString, chunk_m: float) -> list[LineString]:
    if line.length <= chunk_m:
        return [line]
    out: list[LineString] = []
    n = int(np.ceil(line.length / chunk_m))
    edges = np.linspace(0.0, line.length, n + 1)
    for t0, t1 in zip(edges[:-1], edges[1:]):
        inner_n = max(2, int(np.ceil((t1 - t0) / 5.0)) + 1)
        ts = np.linspace(t0, t1, inner_n)
        out.append(LineString([(p.x, p.y) for p in (line.interpolate(t) for t in ts)]))
    return out


def run_per_line(g_in, dem, tf, crs, *, perp_m: float, drop_min: float) -> None:
    drop = np.full(len(g_in), np.nan, dtype=np.float32)
    klass = np.array(["stream"] * len(g_in), dtype=object)
    for i, geom in enumerate(g_in.geometry):
        if geom is None or geom.is_empty or geom.length < LINE_MIN_LEN_M:
            klass[i] = "short"; continue
        d = _xdrop(geom, dem, tf, step=LINE_STEP_M, perp_m=perp_m)
        if d is None:
            klass[i] = "short"; continue
        drop[i] = d
        if d < drop_min:
            klass[i] = "roadlike"
    g = g_in.copy()
    g["xdrop_m"] = drop
    g["klass"] = klass
    g.crs = crs or "EPSG:6346"
    base = f"streams_t{THRESHOLD}_9t"
    g.to_file(OUT_DIR / f"{base}_xsec.shp")
    g.loc[g.klass != "roadlike"].to_file(OUT_DIR / f"{base}_kept_xsec.shp")
    g.loc[g.klass == "roadlike"].to_file(OUT_DIR / f"{base}_roadlike_xsec.shp")
    km = lambda m: float(g.loc[m].length.sum()) / 1000.0
    print(f"[per-line] total={len(g)} ({km(g.klass==g.klass):.1f} km)  "
          f"keep={int((g.klass=='stream').sum())} ({km(g.klass=='stream'):.1f} km)  "
          f"road={int((g.klass=='roadlike').sum())} ({km(g.klass=='roadlike'):.1f} km)  "
          f"short={int((g.klass=='short').sum())}")


def run_chunked(g_in, dem, tf, crs, *, chunk_m: float, perp_m: float,
                drop_min: float) -> None:
    rows: list[dict] = []
    for parent_id, geom in enumerate(g_in.geometry):
        if geom is None or geom.is_empty:
            continue
        for seg_idx, seg in enumerate(_chunk_line(geom, chunk_m)):
            rec = {"parent_id": parent_id, "seg_idx": seg_idx,
                   "seg_len_m": float(seg.length), "xdrop_m": np.nan,
                   "klass": "stream", "geometry": seg}
            if seg.length < CHUNK_MIN_LEN_M:
                rec["klass"] = "short"
            else:
                d = _xdrop(seg, dem, tf, step=CHUNK_STEP_M, perp_m=perp_m)
                if d is None:
                    rec["klass"] = "short"
                else:
                    rec["xdrop_m"] = d
                    if d < drop_min:
                        rec["klass"] = "roadlike"
            rows.append(rec)
    g = gpd.GeoDataFrame(rows, crs=crs or "EPSG:6346")
    base = f"streams_t{THRESHOLD}_9t_chunked"
    g.to_file(OUT_DIR / f"{base}_xsec.shp")
    g.loc[g.klass != "roadlike"].to_file(OUT_DIR / f"{base}_kept_xsec.shp")
    g.loc[g.klass == "roadlike"].to_file(OUT_DIR / f"{base}_roadlike_xsec.shp")
    km = lambda m: float(g.loc[m].length.sum()) / 1000.0
    print(f"[chunked] chunks={len(g)} from {len(g_in)} lines  "
          f"keep={int((g.klass=='stream').sum())} ({km(g.klass=='stream'):.1f} km)  "
          f"road={int((g.klass=='roadlike').sum())} ({km(g.klass=='roadlike'):.1f} km)  "
          f"short={int((g.klass=='short').sum())}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", type=float, default=25.0)
    ap.add_argument("--perp", type=float, default=5.0)
    ap.add_argument("--drop", type=float, default=0.30)
    args = ap.parse_args()

    if not STREAMS.exists():
        print(f"missing {STREAMS} — run _build_streams_9t.py --threshold 5000 first",
              file=sys.stderr)
        return 1
    if not DEM_PATH.exists():
        print(f"missing DEM {DEM_PATH}", file=sys.stderr); return 1

    g_in = gpd.read_file(STREAMS)
    with rasterio.open(DEM_PATH) as r:
        dem = r.read(1).astype(np.float32)
        nodata = r.nodata; tf = r.transform; crs = r.crs
    if nodata is not None:
        dem[dem == nodata] = np.nan

    print(f"xdrop_m < {args.drop:.2f} m -> roadlike  "
          f"(perp={args.perp:.0f} m, chunk={args.chunk:.0f} m)  on {len(g_in)} lines")
    run_per_line(g_in, dem, tf, crs, perp_m=args.perp, drop_min=args.drop)
    run_chunked(g_in, dem, tf, crs, chunk_m=args.chunk, perp_m=args.perp,
                drop_min=args.drop)
    print(f"\nDONE. outputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
