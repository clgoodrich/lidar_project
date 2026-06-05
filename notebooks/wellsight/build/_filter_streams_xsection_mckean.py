"""Cross-sectional road filter for the t=5000 stream linestrings on McKean.

For each line, walk along it at 5 m steps. At each step, find the local
tangent direction from neighbouring vertices, rotate 90 deg to get the
perpendicular, and sample the DEM at three points:

    z_left   = DEM(center - perp * PERP_M)
    z_center = DEM(center)
    z_right  = DEM(center + perp * PERP_M)

For a real stream cross-section, the channel center sits in the bottom of a
V or U:        \\___/      => mean(z_left, z_right) - z_center > 0  (concave)

For a road cut or graded surface, the running surface is flat-to-convex:
                 ___        => mean(z_left, z_right) - z_center <= 0
              __/   \\__       (flat -> ~0; crowned road -> negative)

We summarise each line by the **median** ``cross_drop_m`` over its samples
(median = robust to spurious DEM noise near junctions and bridges).

Classification:
    roadlike  if  cross_drop_m  <  DROP_MIN_M   (default 0.30 m)
    short     if  arc_length    <  MIN_LEN_M     (30 m -- too short to sample)
    stream    otherwise

Outputs per block (alongside the existing classified shapefiles):
    streams_t5000_<key>_xsec.shp        all lines + cross_drop_m + klass
    streams_t5000_<key>_kept_xsec.shp   klass != roadlike
    streams_t5000_<key>_roadlike_xsec.shp  klass == roadlike

CLI:
  python notebooks/wellsight/build/_filter_streams_xsection_mckean.py
  python notebooks/wellsight/build/_filter_streams_xsection_mckean.py --perp 7 --drop 0.4
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

REGION = DERIV / "data_3x3" / "northcentral_b19"
THRESHOLD = 5000
SAMPLE_STEP_M = 5.0
MIN_LEN_M = 30.0


def _resample(line: LineString, step: float) -> np.ndarray:
    n = max(2, int(np.ceil(line.length / step)) + 1)
    ts = np.linspace(0, line.length, n)
    return np.array([[p.x, p.y] for p in (line.interpolate(t) for t in ts)])


def _sample_dem(xs: np.ndarray, ys: np.ndarray, dem: np.ndarray, tf) -> np.ndarray:
    cols = ((xs - tf.c) / tf.a).astype(int)
    rows = ((ys - tf.f) / tf.e).astype(int)
    H, W = dem.shape
    out = np.full(len(xs), np.nan, dtype=np.float32)
    ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    out[ok] = dem[rows[ok], cols[ok]]
    return out


def _line_xsection(line: LineString, dem: np.ndarray, tf,
                   *, step: float, perp_m: float) -> float | None:
    if line.length < 2 * step:
        return None
    pts = _resample(line, step)
    xs, ys = pts[:, 0], pts[:, 1]
    # Tangent direction via central differences, then perpendicular.
    dx = np.gradient(xs); dy = np.gradient(ys)
    tlen = np.hypot(dx, dy)
    tlen[tlen < 1e-6] = 1.0
    tx, ty = dx / tlen, dy / tlen
    # Perpendicular = rotate tangent +90 deg.
    px, py = -ty, tx
    zc = _sample_dem(xs,           ys,           dem, tf)
    zl = _sample_dem(xs - px*perp_m, ys - py*perp_m, dem, tf)
    zr = _sample_dem(xs + px*perp_m, ys + py*perp_m, dem, tf)
    edge = (zl + zr) * 0.5
    drop = edge - zc  # positive = channel-shaped (center is lower)
    ok = np.isfinite(drop)
    if ok.sum() < 3:
        return None
    return float(np.median(drop[ok]))


def classify_block(key: str, work: Path, *, perp_m: float, drop_min: float) -> None:
    shp = work / f"streams_t{THRESHOLD}_{key}_1m.shp"
    dem_path = work / f"dem_{key}_1m.tif"
    if not (shp.exists() and dem_path.exists()):
        print(f"[{key}] missing inputs, skip"); return

    g = gpd.read_file(shp)
    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        nodata = r.nodata
        tf = r.transform
    if nodata is not None:
        dem[dem == nodata] = np.nan

    drop = np.full(len(g), np.nan, dtype=np.float32)
    klass = np.array(["stream"] * len(g), dtype=object)
    for i, geom in enumerate(g.geometry):
        if geom is None or geom.is_empty or geom.length < MIN_LEN_M:
            klass[i] = "short"; continue
        d = _line_xsection(geom, dem, tf, step=SAMPLE_STEP_M, perp_m=perp_m)
        if d is None:
            klass[i] = "short"; continue
        drop[i] = d
        if d < drop_min:
            klass[i] = "roadlike"

    g["xdrop_m"] = drop
    g["klass"] = klass
    g.crs = g.crs or "EPSG:6346"

    g.to_file(work / f"streams_t{THRESHOLD}_{key}_xsec.shp")
    g.loc[g.klass != "roadlike"].to_file(work / f"streams_t{THRESHOLD}_{key}_kept_xsec.shp")
    g.loc[g.klass == "roadlike"].to_file(work / f"streams_t{THRESHOLD}_{key}_roadlike_xsec.shp")

    long = g[g.klass != "short"]
    n_road = int((g.klass == "roadlike").sum())
    n_keep = int((g.klass == "stream").sum())
    n_short = int((g.klass == "short").sum())
    km_road = float(g.loc[g.klass == "roadlike"].length.sum()) / 1000
    km_keep = float(g.loc[g.klass == "stream"].length.sum()) / 1000
    print(f"[{key}] total={len(g)} ({float(g.length.sum())/1000:.1f} km)  "
          f"keep={n_keep} ({km_keep:.1f} km)  road={n_road} ({km_road:.1f} km)  "
          f"short={n_short}")
    if len(long):
        q = long.xdrop_m
        print(f"        xdrop_m p10={q.quantile(0.10):+.2f}  p50={q.median():+.2f}  "
              f"p90={q.quantile(0.90):+.2f}  (drop_min={drop_min:+.2f})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated key filter")
    ap.add_argument("--perp", type=float, default=5.0,
                    help="perpendicular sample distance (m), default 5")
    ap.add_argument("--drop", type=float, default=0.30,
                    help="lines with cross_drop_m below this are roadlike "
                         "(default 0.30 m -- a real channel has banks "
                         "noticeably above the thalweg)")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    blocks = sorted(p for p in REGION.iterdir() if p.is_dir())
    if only:
        blocks = [b for b in blocks if b.name in only]
    if not blocks:
        print("no McKean blocks found", file=sys.stderr); return 1

    print(f"cross_drop_m < {args.drop:.2f} m  (perp = {args.perp:.1f} m)  -> roadlike")
    for sub in blocks:
        classify_block(sub.name, sub, perp_m=args.perp, drop_min=args.drop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
