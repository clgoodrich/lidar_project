"""Geometric road filter for the t=5000 stream linestrings on McKean.

For each block under data/derivatives/tiles/data_3x3/northcentral_b19/<key>/,
loads streams_t5000_<key>_1m.shp and computes two per-line metrics from the
DEM alone:

  sinuosity = arc_length / straight_line_distance
              streams meander (>= ~1.15), roads/ditches are near-straight (<= 1.05)

  mean_slope_deg = mean |dz/ds| sampled at vertices along the line
                   streams descend (typically >= 2 deg in McKean terrain);
                   roads cross-grade at <1 deg for long distances

Classification (per line):
  - SHORT  (length < MIN_LEN)            -> not classified, kept as "stream"
                                            (too short to compute reliable stats)
  - ROADLIKE  (sinuosity < SIN_MAX  AND  mean_slope < SLOPE_MAX)
  - STREAM  otherwise

Outputs per block:
  streams_t5000_<key>_classified.shp   all lines + columns {sinuosity, slope_deg, klass}
  streams_t5000_<key>_kept.shp         klass != roadlike (the cleaned stream net)
  streams_t5000_<key>_roadlike.shp     klass == roadlike (rejected candidates)

CLI:
  python notebooks/wellsight/build/_filter_streams_roads_mckean.py
  python notebooks/wellsight/build/_filter_streams_roads_mckean.py --sin 1.05 --slope 2.0
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
SAMPLE_STEP_M = 5.0  # resample centerline this densely before computing slope
MIN_LEN_M = 30.0     # below this, line is too short to classify reliably


def _resample(line: LineString, step: float) -> np.ndarray:
    """Sample (x, y) along the line at ``step`` m intervals (inclusive ends)."""
    n = max(2, int(np.ceil(line.length / step)) + 1)
    ts = np.linspace(0, line.length, n)
    return np.array([[p.x, p.y] for p in (line.interpolate(t) for t in ts)])


def _line_stats(line: LineString, dem: np.ndarray, tf, *, step: float):
    if line.length < 1e-3:
        return None
    pts = _resample(line, step)
    xs, ys = pts[:, 0], pts[:, 1]
    # straight-line distance between endpoints
    d = float(np.hypot(xs[-1] - xs[0], ys[-1] - ys[0]))
    sinu = float(line.length / d) if d > 1e-3 else np.nan
    # sample DEM at each vertex
    cols = ((xs - tf.c) / tf.a).astype(int)
    rows = ((ys - tf.f) / tf.e).astype(int)
    H, W = dem.shape
    ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    if ok.sum() < 2:
        return None
    z = np.full(len(pts), np.nan, dtype=np.float32)
    z[ok] = dem[rows[ok], cols[ok]]
    z = z[np.isfinite(z)]
    if len(z) < 2:
        return None
    # mean absolute slope along the line, in degrees
    dz = np.abs(np.diff(z))
    seg = float(line.length / (len(pts) - 1))  # ~step
    slope_rad = np.arctan(dz / max(seg, 1e-6))
    slope_deg = float(np.degrees(np.mean(slope_rad)))
    return sinu, slope_deg


def classify_block(key: str, work: Path, *, sin_max: float, slope_max: float) -> dict:
    shp = work / f"streams_t{THRESHOLD}_{key}_1m.shp"
    dem_path = work / f"dem_{key}_1m.tif"
    if not (shp.exists() and dem_path.exists()):
        return {"key": key, "skipped": True}

    g = gpd.read_file(shp)
    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        nodata = r.nodata
        tf = r.transform
    if nodata is not None:
        dem[dem == nodata] = np.nan

    sinu = np.full(len(g), np.nan, dtype=np.float32)
    slp = np.full(len(g), np.nan, dtype=np.float32)
    klass = np.array(["stream"] * len(g), dtype=object)

    for i, geom in enumerate(g.geometry):
        if geom is None or geom.is_empty:
            klass[i] = "short"; continue
        if geom.length < MIN_LEN_M:
            klass[i] = "short"; continue
        out = _line_stats(geom, dem, tf, step=SAMPLE_STEP_M)
        if out is None:
            klass[i] = "short"; continue
        sinu[i], slp[i] = out
        if sinu[i] < sin_max and slp[i] < slope_max:
            klass[i] = "roadlike"

    g["sinuosity"] = sinu
    g["slope_deg"] = slp
    g["klass"] = klass
    g.crs = g.crs or "EPSG:6346"

    out_all = work / f"streams_t{THRESHOLD}_{key}_classified.shp"
    out_keep = work / f"streams_t{THRESHOLD}_{key}_kept.shp"
    out_road = work / f"streams_t{THRESHOLD}_{key}_roadlike.shp"
    g.to_file(out_all)
    g.loc[g.klass != "roadlike"].to_file(out_keep)
    g.loc[g.klass == "roadlike"].to_file(out_road)

    n_road = int((g.klass == "roadlike").sum())
    n_short = int((g.klass == "short").sum())
    n_keep = int((g.klass == "stream").sum())
    km = lambda mask: float(g.loc[mask].length.sum()) / 1000.0
    print(f"[{key}] total={len(g)} lines ({km(g.klass==g.klass):.1f} km)  "
          f"keep={n_keep} ({km(g.klass=='stream'):.1f} km)  "
          f"road={n_road} ({km(g.klass=='roadlike'):.1f} km)  "
          f"short={n_short} ({km(g.klass=='short'):.1f} km)")
    return {"key": key, "total": len(g), "stream": n_keep,
            "roadlike": n_road, "short": n_short}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated key filter")
    ap.add_argument("--sin", type=float, default=1.05,
                    help="sinuosity below this counts as road-like (default 1.05)")
    ap.add_argument("--slope", type=float, default=2.0,
                    help="mean slope (deg) below this counts as road-like "
                         "(default 2.0)")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    blocks = sorted(p for p in REGION.iterdir() if p.is_dir())
    if only:
        blocks = [b for b in blocks if b.name in only]
    if not blocks:
        print("no McKean blocks found", file=sys.stderr); return 1

    print(f"sinuosity < {args.sin}  AND  mean_slope < {args.slope} deg  -> roadlike")
    for sub in blocks:
        classify_block(sub.name, sub, sin_max=args.sin, slope_max=args.slope)
    return 0


if __name__ == "__main__":
    sys.exit(main())
