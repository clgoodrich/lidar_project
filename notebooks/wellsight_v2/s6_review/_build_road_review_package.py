"""Build a QGIS review package for human-in-the-loop road correction on a block.

Chops the predicted road network into ~40 m segments (matching the training
chunk size) with a `status` field so the reviewer flags bad segments instead of
deleting them — preserving false-positive geometry as hard negatives. Also emits
an empty line layer for drawing missed roads (new positives) and a how-to note.

Outputs (under <block>/review/):
    review_roads_<key>.gpkg   layer 'review'  — predicted ~40 m segs, status=keep
    added_roads_<key>.gpkg    layer 'added'   — empty; draw missed roads here
    README_EDIT.md            QGIS instructions

CLI:
  python notebooks/wellsight/build/_build_road_review_package.py --key 613590
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyogrio
import rasterio
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS

REGION = DERIV / "tiles" / "data_3x3" / "westernpa_d20"
CHUNK_M = 40.0


def sample_mean(arr, tf, line, step=3.0):
    """Mean raster value along a line (skips nodata/-1)."""
    if arr is None or line is None or line.is_empty:
        return np.nan
    inv = ~tf; H, W = arr.shape; vals = []
    for t in np.linspace(0, line.length, max(2, int(line.length / step))):
        p = line.interpolate(t); c, r = inv * (p.x, p.y); r, c = int(r), int(c)
        if 0 <= r < H and 0 <= c < W and arr[r, c] >= 0 and np.isfinite(arr[r, c]):
            vals.append(float(arr[r, c]))
    return round(float(np.mean(vals)), 3) if vals else np.nan


def chunk_line(line: LineString, chunk_m: float):
    if line is None or line.is_empty or line.geom_type != "LineString":
        return []
    if line.length <= chunk_m:
        return [line]
    n = int(np.ceil(line.length / chunk_m))
    edges = np.linspace(0.0, line.length, n + 1)
    out = []
    for t0, t1 in zip(edges[:-1], edges[1:]):
        inner = max(2, int(np.ceil((t1 - t0) / 5.0)) + 1)
        ts = np.linspace(t0, t1, inner)
        seg = LineString([(p.x, p.y) for p in (line.interpolate(t) for t in ts)])
        if not seg.is_empty and seg.length > 0:
            out.append(seg)
    return out


README = """# Road review — {key}

Goal: correct the model's predicted roads so we can retrain on YOUR fixes.

## Layers to load (drag into QGIS, in this order)
1. `hillshade_{key}_1m.tif`            (basemap)
2. `road_prob_{key}_1m.tif`           (optional: model confidence heat-map)
3. `review/review_roads_{key}.gpkg`    (the predicted roads — you edit this)
4. `review/added_roads_{key}.gpkg`     (empty — you DRAW missed roads here)

## How to correct (flag, don't delete)
- Toggle editing (pencil icon) on `review_roads`.
- Select the bad segments (false roads, bogus links). Open the attribute table
  or Field Calculator and set **status = 'reject'** for them. DO NOT delete —
  the rejected geometry is used as a hard negative ("not a road") in training.
- Leave good segments as **status = 'keep'** (the default).
- If unsure, set **status = 'unsure'** and we'll exclude it from training.
- For roads the model MISSED: toggle editing on `added_roads`, draw the
  centerline(s). status auto = 'added'. Trace the road, not the exact width.
- Save edits (Ctrl+S) and toggle editing off when done.

## Tips
- Style `review_roads` by `status` (keep=green, reject=red) to track progress.
- Sort the attribute table by `mean_proad` ascending to review the model's
  least-confident segments first — those are the likeliest false positives.

Segments are ~{chunk:.0f} m so you can flag a bad stretch without splitting lines.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="613590")
    ap.add_argument("--src", default=None, help="source gpkg (default roads_opt_<key>_1m.gpkg)")
    ap.add_argument("--layer", default="roads_clean")
    ap.add_argument("--prob", default=None, help="road_prob raster to sample mean_proad per seg")
    ap.add_argument("--chunk", type=float, default=CHUNK_M, help="segment length (m)")
    args = ap.parse_args()

    blk = REGION / args.key
    src = Path(args.src) if args.src else blk / f"roads_opt_{args.key}_1m.gpkg"
    out_dir = blk / "review"
    out_dir.mkdir(parents=True, exist_ok=True)

    prob = tf = None
    prob_path = Path(args.prob) if args.prob else blk / f"road_prob_{args.key}_1m.tif"
    if prob_path.exists():
        with rasterio.open(prob_path) as r:
            prob = r.read(1).astype(np.float32); tf = r.transform

    g = gpd.read_file(src, layer=args.layer).to_crs(DST_CRS)
    keep_cols = [c for c in ("confidence", "mean_proad", "width_m", "mean_slope") if c in g.columns]
    rows = []
    sid = 0
    for pid, row in g.reset_index(drop=True).iterrows():
        geom = row.geometry
        parts = list(geom.geoms) if geom and geom.geom_type == "MultiLineString" else [geom]
        for part in parts:
            for seg in chunk_line(part, args.chunk):
                rec = {"seg_id": sid, "parent_id": int(pid), "status": "keep",
                       "length_m": round(float(seg.length), 1), "geometry": seg}
                for c in keep_cols:
                    rec[c] = row[c]
                if prob is not None and "mean_proad" not in rec:
                    rec["mean_proad"] = sample_mean(prob, tf, seg)
                rows.append(rec); sid += 1
    review = gpd.GeoDataFrame(rows, crs=DST_CRS)
    review_path = out_dir / f"review_roads_{args.key}.gpkg"
    review.to_file(review_path, layer="review", driver="GPKG")
    print(f"review: {len(review)} segments (~{args.chunk:.0f} m), {review.length.sum()/1000:.1f} km "
          f"-> {review_path.name}")

    # empty 'added' layer with a fixed schema (LineString)
    added = gpd.GeoDataFrame({"status": gpd.pd.Series([], dtype="object"),
                              "note": gpd.pd.Series([], dtype="object")},
                             geometry=gpd.GeoSeries([], crs=DST_CRS))
    added_path = out_dir / f"added_roads_{args.key}.gpkg"
    pyogrio.write_dataframe(added, added_path, layer="added", geometry_type="LineString")
    print(f"added : empty draw-here layer -> {added_path.name}")

    (out_dir / "README_EDIT.md").write_text(
        README.format(key=args.key, chunk=CHUNK_M), encoding="utf-8")
    print(f"note  : README_EDIT.md")
    print(f"\nReview package ready: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
