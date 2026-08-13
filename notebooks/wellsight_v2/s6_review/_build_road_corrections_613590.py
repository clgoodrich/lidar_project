"""Turn the human road review of 613590 into a corrected training block.

Consumes the QGIS review package (built 2026-06-15, edited by the user
2026-06-17) and emits a corridor-supervised label raster + sample centers:

    review_roads_613590_ORIGINAL.gpkg  minus  review_roads_613590.gpkg
        -> REJECTED segments (model false positives) = hard negatives
    review_roads_613590.gpkg           -> KEPT segments (confirmed road)
    added_roads_613590.gpkg            -> ADDED lines (roads the model missed)

Label raster (`labels_road_corr_613590_1m.tif`, uint8):
    1   road  — kept + added, buffered ROAD_BUFFER_M (matches 9t prep)
    0   bg    — rejected segments buffered REJECT_BUFFER_M, plus a margin ring
                around confirmed roads (sharpens edges)
    255 ignore — EVERYTHING else

The ignore default is the point: the human reviewed the *predicted network*,
not every square metre of the block, so any unlabelled pixel might be a real
road nobody drew. Painting it bg would teach false negatives. FocalCE skips
ignore, so the loss only sees pixels a human actually adjudicated.

Paint order is bg-then-road, so a margin ring crossing another road loses to
that road.

Splits: a 3x3 grid of cells over the block, seeded assignment to
train/val/test. Train sample centers are additionally eroded by
PATCH_HALF_M + JITTER_M from cell edges, so no training patch can ever
overlap a val/test cell (kills the block-boundary leakage the 2026-07-01
methodology audit flagged).

Outputs (under <block>/corrections/):
    labels_road_corr_613590_1m.tif
    correction_centers_613590.csv     x, y, kind (added|reject|kept), split
    correction_split_cells_613590.gpkg
    correction_lines_613590.gpkg      layers: added, reject, kept (with split)
    corrections_summary.json

Reproduce:
  python notebooks/wellsight_v2/s6_review/_build_road_corrections_613590.py
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import LineString, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, path_for

BLOCK = path_for("data_3x3") / "westernpa_d20" / "613590" / "derived" / "1m"
REVIEW = BLOCK / "review"
OUT = BLOCK / "corrections"
FEATURES = BLOCK / "features_613590_1m.tif"

ROAD_BUFFER_M = 1.5      # matches _prep_road_1m.py
REJECT_BUFFER_M = 2.0    # a touch wider: mark the false-positive corridor
MARGIN_BUFFER_M = 4.0    # outer edge of the bg ring around confirmed roads
CHUNK_M = 40.0           # matches the review-package / training chunk size

GRID_N = 4               # 4x4 split cells (1125 m each)
PATCH_HALF_M = 128.0     # 256 px patch at 1 m
JITTER_M = 30.0
ERODE_M = PATCH_HALF_M + JITTER_M
SPLIT_SEED = 0
CELL_SPLITS = ["train"] * 10 + ["val"] * 3 + ["test"] * 3
TARGET_SHARE = {"train": 0.60, "val": 0.20, "test": 0.20}
SEARCH_N = 4000          # seeded search for a balanced cell assignment


def chunk_line(line: LineString, chunk_m: float = CHUNK_M):
    """Split a line into <=chunk_m pieces (same policy as the review build)."""
    if line is None or line.is_empty:
        return []
    geoms = list(line.geoms) if line.geom_type == "MultiLineString" else [line]
    out = []
    for g in geoms:
        if g.length <= chunk_m:
            out.append(g)
            continue
        n = int(np.ceil(g.length / chunk_m))
        edges = np.linspace(0.0, g.length, n + 1)
        for t0, t1 in zip(edges[:-1], edges[1:]):
            ts = np.linspace(t0, t1, max(2, int(np.ceil((t1 - t0) / 5.0)) + 1))
            seg = LineString([(p.x, p.y) for p in
                              (g.interpolate(t) for t in ts)])
            if not seg.is_empty and seg.length > 0:
                out.append(seg)
    return out


def midpoints(gdf):
    pts = []
    for g in gdf.geometry:
        if g is None or g.is_empty:
            continue
        gg = (max(g.geoms, key=lambda s: s.length)
              if g.geom_type == "MultiLineString" else g)
        p = gg.interpolate(0.5, normalized=True)
        pts.append((p.x, p.y))
    return np.array(pts) if pts else np.zeros((0, 2))


def build_split_cells(bounds, added, rejected):
    """Grid the block, then search seeded assignments for a balanced split.

    The user's added roads are clustered in the block's NW, so a naive random
    assignment can leave zero additions held out (which would make the
    recall-improvement question unanswerable). Score each candidate by how
    close its per-split share of added km AND rejected km sits to
    TARGET_SHARE, and keep the best.
    """
    minx, miny, maxx, maxy = bounds
    xs = np.linspace(minx, maxx, GRID_N + 1)
    ys = np.linspace(miny, maxy, GRID_N + 1)
    cells = [box(xs[i], ys[j], xs[i + 1], ys[j + 1])
             for j in range(GRID_N) for i in range(GRID_N)]
    add_km = np.array([added.intersection(c).length.sum() / 1000
                       for c in cells])
    rej_km = np.array([rejected.intersection(c).length.sum() / 1000
                       for c in cells])
    base = np.array(CELL_SPLITS)[:len(cells)]

    best, best_cost = None, float("inf")
    for seed in range(SEARCH_N):
        rng = np.random.default_rng(seed)
        splits = base.copy()
        rng.shuffle(splits)
        cost = 0.0
        for arr, w in ((add_km, 2.0), (rej_km, 1.0)):  # additions matter most
            tot = arr.sum()
            if tot <= 0:
                continue
            for s, target in TARGET_SHARE.items():
                share = arr[splits == s].sum() / tot
                cost += w * (share - target) ** 2
        if cost < best_cost:
            best_cost, best = cost, splits.copy()
    print(f"split search: best cost {best_cost:.5f} over {SEARCH_N} seeds")
    return gpd.GeoDataFrame({"cell_id": range(len(cells)), "split": best},
                            geometry=cells, crs="EPSG:6346")


def assign_split(gdf, cells):
    """Label each feature by the cell containing its midpoint."""
    if not len(gdf):
        gdf = gdf.copy(); gdf["split"] = []; return gdf
    mids = midpoints(gdf)
    pts = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(mids[:, 0], mids[:, 1]), crs=gdf.crs)
    j = gpd.sjoin(pts, cells[["split", "cell_id", "geometry"]],
                  how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    out = gdf.copy()
    out["split"] = j["split"].to_numpy()
    out["cell_id"] = j["cell_id"].to_numpy()
    out["mid_x"] = mids[:, 0]
    out["mid_y"] = mids[:, 1]
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cur = gpd.read_file(REVIEW / "review_roads_613590.gpkg")
    orig = gpd.read_file(REVIEW / "review_roads_613590_ORIGINAL.gpkg")
    added = gpd.read_file(REVIEW / "added_roads_613590.gpkg")

    kept = cur.copy()
    rejected = orig[~orig.seg_id.isin(set(cur.seg_id))].copy()
    print(f"kept    {len(kept):6d} segs  {kept.length.sum()/1000:7.2f} km")
    print(f"reject  {len(rejected):6d} segs  {rejected.length.sum()/1000:7.2f} km")
    print(f"added   {len(added):6d} lines {added.length.sum()/1000:7.2f} km")

    # Rejected segments are bimodal in model confidence: the low-prob ones were
    # inserted by post-processing gap-bridging (the model already says bg
    # there, so they carry no gradient); the high-prob ones are the true model
    # false positives that make this loop worth running.
    if "mean_proad" in rejected:
        hard = int((rejected.mean_proad >= 0.5).sum())
        print(f"        of which model-confident (P>=0.5): {hard} "
              f"({rejected.loc[rejected.mean_proad >= 0.5].length.sum()/1000:.2f} km)")

    # Added lines are long; chunk them so sample centers follow the geometry.
    add_chunks = []
    for g in added.geometry:
        add_chunks.extend(chunk_line(g))
    added_ch = gpd.GeoDataFrame(geometry=add_chunks, crs=added.crs)
    print(f"added chunked -> {len(added_ch)} segments")

    with rasterio.open(FEATURES) as r:
        tf, H, W, crs = r.transform, r.height, r.width, r.crs
        bounds = r.bounds

    cells = build_split_cells(bounds, added, rejected)
    kept = assign_split(kept, cells)
    rejected = assign_split(rejected, cells)
    added_ch = assign_split(added_ch, cells)

    print("\nsplit distribution (km):")
    for name, g in [("kept", kept), ("reject", rejected), ("added", added_ch)]:
        km = g.groupby("split").apply(
            lambda d: round(d.length.sum() / 1000, 2), include_groups=False)
        print(f"  {name:7s} {km.to_dict()}")

    # ---- label raster: 255 ignore -> 0 bg -> 1 road ----
    label = np.full((H, W), 255, dtype=np.uint8)
    road_geom = list(kept.geometry) + list(added_ch.geometry)

    ring = [g.buffer(MARGIN_BUFFER_M).difference(g.buffer(ROAD_BUFFER_M))
            for g in road_geom]
    bg_shapes = ([(g.buffer(REJECT_BUFFER_M), 1) for g in rejected.geometry]
                 + [(g, 1) for g in ring if not g.is_empty])
    if bg_shapes:
        bg = rasterize(bg_shapes, out_shape=(H, W), transform=tf, fill=0,
                       dtype="uint8").astype(bool)
        label[bg] = 0

    road = rasterize([(g.buffer(ROAD_BUFFER_M), 1) for g in road_geom],
                     out_shape=(H, W), transform=tf, fill=0,
                     dtype="uint8").astype(bool)
    label[road] = 1

    prof = {"driver": "GTiff", "height": H, "width": W, "count": 1,
            "dtype": "uint8", "crs": crs, "transform": tf, "nodata": 255,
            "compress": "deflate", "tiled": True}
    lbl_path = OUT / "labels_road_corr_613590_1m.tif"
    with rasterio.open(lbl_path, "w", **prof) as dst:
        dst.write(label, 1)
    n_road = int((label == 1).sum()); n_bg = int((label == 0).sum())
    n_ign = int((label == 255).sum())
    print(f"\nlabels: road {n_road:,} px | bg {n_bg:,} px | ignore {n_ign:,} px "
          f"({100*n_ign/label.size:.1f}% of block)")

    # ---- sample centers, with train eroded away from val/test cells ----
    train_cells = cells[cells.split == "train"].geometry
    train_safe = train_cells.buffer(-ERODE_M).union_all()
    rows = []
    for kind, g in [("added", added_ch), ("reject", rejected), ("kept", kept)]:
        for _, r in g.iterrows():
            if pd.isna(r.get("split")):
                continue
            keep_pt = True
            if r["split"] == "train":
                from shapely.geometry import Point
                keep_pt = train_safe.contains(Point(r.mid_x, r.mid_y))
            if keep_pt:
                rows.append({"x": r.mid_x, "y": r.mid_y, "kind": kind,
                             "split": r["split"], "cell_id": r.cell_id})
    centers = pd.DataFrame(rows)
    centers.to_csv(OUT / "correction_centers_613590.csv", index=False)
    print("\ncenters after erosion:")
    print(centers.groupby(["split", "kind"]).size().to_string())

    cells.to_file(OUT / "correction_split_cells_613590.gpkg",
                  layer="cells", driver="GPKG")
    lines_path = OUT / "correction_lines_613590.gpkg"
    if lines_path.exists():
        lines_path.unlink()
    for name, g in [("added", added_ch), ("reject", rejected), ("kept", kept)]:
        cols = [c for c in ["split", "cell_id", "mean_proad", "length_m",
                            "geometry"] if c in g.columns]
        g[cols].to_file(lines_path, layer=name, driver="GPKG",
                        mode="a" if name != "added" else "w")

    # Stamp from file mtimes. The review is edited in QGIS between rounds, so a
    # hardcoded date silently goes stale the moment the user saves again.
    def _mtime(p):
        return _dt.date.fromtimestamp(p.stat().st_mtime).isoformat()

    summary = {
        "built": _dt.date.today().isoformat(),
        "source_review_edited": _mtime(REVIEW / "review_roads_613590.gpkg"),
        "source_added_edited": _mtime(REVIEW / "added_roads_613590.gpkg"),
        "n_kept": len(kept), "km_kept": round(kept.length.sum() / 1000, 2),
        "n_rejected": len(rejected),
        "km_rejected": round(rejected.length.sum() / 1000, 2),
        "n_rejected_model_confident": int((rejected.mean_proad >= 0.5).sum())
        if "mean_proad" in rejected else None,
        "n_added_lines": len(added),
        "km_added": round(added.length.sum() / 1000, 2),
        "n_added_chunks": len(added_ch),
        "label_px": {"road": n_road, "bg": n_bg, "ignore": n_ign},
        "buffers_m": {"road": ROAD_BUFFER_M, "reject": REJECT_BUFFER_M,
                      "margin": MARGIN_BUFFER_M},
        "split": {"grid": GRID_N, "seed": SPLIT_SEED,
                  "erode_m": ERODE_M,
                  "cells": cells.groupby("split").size().to_dict()},
        "centers": {f"{s}_{k}": int(v) for (s, k), v in
                    centers.groupby(["split", "kind"]).size().items()},
    }
    (OUT / "corrections_summary.json").write_text(
        json.dumps(summary, indent=2, default=str))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
