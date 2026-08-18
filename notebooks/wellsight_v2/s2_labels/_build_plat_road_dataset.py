"""Build labels and manifests for plat segmentation, road segmentation, and road classification.

Outputs (under data/derivatives/tiles/9t/):
    labels_plat_9t_05.tif        uint8  0=bg, 1=plat
    labels_road_9t_05.tif        uint8  0=bg, 1=road  (roads buffered 1.5 m)
    plat_dataset_manifest.csv    one row per plat: pad_id, block_id, split, centroid_x/y
    road_dataset_manifest.csv    one row per road LINE: road_id, kind, block_id, split, mid_x/y
    road_classifier_samples.csv  one row per sample POINT along lines (for the classifier)
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T as D, path_for, read_layer

ANN = path_for("truth") / "annotations_proj.gpkg"
REF = D / "dem_9t_05.tif"
BLOCKS = D / "pit_blocks_9t.gpkg"

ROAD_BUFFER_M = 1.5  # half-width for road rasterization
SAMPLE_STRIDE_M = 4.0  # sample points along lines for the classifier
CHUNK_M = 40.0  # split long road/not_road polylines into ~40 m segments so the
                # U-Net samples patch centers ALONG every road (not just the
                # midpoint) and the eval scores comparable-length units. Drainage
                # already arrives pre-chunked from the cross-section filter.


def chunk_line(line: LineString, chunk_m: float):
    """Split a polyline into ~chunk_m segments (densified to ~5 m vertices)."""
    if line is None or line.is_empty:
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


def assign_split(geom_or_pt, blocks):
    """Look up which block (and thereby split) a point or geometry falls in."""
    if geom_or_pt is None or getattr(geom_or_pt, "is_empty", True):
        return None, "unused"
    if hasattr(geom_or_pt, "centroid"):
        pt = geom_or_pt.centroid if geom_or_pt.geom_type != "Point" else geom_or_pt
    else:
        pt = geom_or_pt
    hit = blocks[blocks.geometry.contains(pt)]
    if len(hit):
        return int(hit.iloc[0].block_id), str(hit.iloc[0].split)
    return None, "unused"


def sample_along_line(line: LineString, stride_m: float):
    pts = []
    L = line.length
    if L < 1.0:
        pts.append(line.interpolate(0.5, normalized=True))
        return pts
    n = max(1, int(L // stride_m))
    for i in range(n + 1):
        d = min(i * stride_m, L)
        pts.append(line.interpolate(d))
    return pts


def main():
    with rasterio.open(REF) as r:
        profile = r.profile.copy()
        H, W = r.height, r.width
        tf = r.transform
        crs = r.crs

    blocks = gpd.read_file(BLOCKS, layer="blocks")
    plat = read_layer(ANN, "plat")
    roads = read_layer(ANN, "roads")
    not_roads = read_layer(ANN, "not_roads")
    drainage = (read_layer(ANN, "drainage")
                if "drainage" in gpd.list_layers(ANN)["name"].tolist()
                else gpd.GeoDataFrame(geometry=[], crs=roads.crs))
    print(f"plat={len(plat)}  roads={len(roads)}  not_roads={len(not_roads)}  "
          f"drainage={len(drainage)}")

    # --- plat label raster (binary) ---
    plat_arr = rasterize(
        [(g, 1) for g in plat.geometry if g and not g.is_empty],
        out_shape=(H, W), transform=tf, fill=0, dtype="uint8",
    )
    p1 = profile.copy()
    p1.update(dtype="uint8", count=1, nodata=255, compress="deflate", predictor=2)
    with rasterio.open(D / "labels_plat_9t_05.tif", "w", **p1) as dst:
        dst.write(plat_arr, 1)
    print(f"labels_plat_9t_05.tif  ({int(plat_arr.sum())} px = {int(plat_arr.sum()*0.25)} m^2)")

    # --- road label raster (binary, buffered) ---
    buffered = [g.buffer(ROAD_BUFFER_M) for g in roads.geometry if g and not g.is_empty]
    road_arr = rasterize(
        [(g, 1) for g in buffered],
        out_shape=(H, W), transform=tf, fill=0, dtype="uint8",
    )
    with rasterio.open(D / "labels_road_9t_05.tif", "w", **p1) as dst:
        dst.write(road_arr, 1)
    print(f"labels_road_9t_05.tif  ({int(road_arr.sum())} px = {int(road_arr.sum()*0.25)} m^2)")

    # --- plat manifest ---
    plat_rows = []
    for _, row in plat.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        bid, split = assign_split(row.geometry, blocks)
        c = row.geometry.centroid
        plat_rows.append({"pad_id": int(row.pad_id), "block_id": bid, "split": split,
                          "centroid_x": c.x, "centroid_y": c.y,
                          "area_m2": float(row.geometry.area)})
    plat_man = pd.DataFrame(plat_rows)
    plat_man.to_csv(D / "plat_dataset_manifest.csv", index=False)
    print(f"plat_dataset_manifest.csv  splits={plat_man['split'].value_counts().to_dict()}")

    # --- road CHUNK manifest + chunk geometries (used by the road U-Net) ---
    # Roads/not_roads are long polylines -> chunk them so every ~40 m becomes its
    # own patch center (training) and eval unit. Drainage is already short chunks.
    chunk_rows = []   # -> road_dataset_manifest.csv (centers + split for sampler)
    chunk_geoms = []  # -> road_chunks_9t.gpkg (geometry for eval)
    for src, kind, do_chunk in [(roads, "road", True),
                                (not_roads, "not_road", True),
                                (drainage, "drainage", False)]:
        for i, row in src.reset_index(drop=True).iterrows():
            g = row.geometry
            if g is None or g.is_empty:
                continue
            segs = chunk_line(g, CHUNK_M) if do_chunk else [g]
            for j, seg in enumerate(segs):
                mid = seg.interpolate(0.5, normalized=True)
                bid, split = assign_split(mid, blocks)
                lid = f"{kind}_{i}_{j}"
                chunk_rows.append({"line_id": lid, "kind": kind,
                                   "parent_id": i, "seg_idx": j,
                                   "block_id": bid, "split": split,
                                   "mid_x": mid.x, "mid_y": mid.y,
                                   "length_m": float(seg.length)})
                chunk_geoms.append({"line_id": lid, "kind": kind, "split": split,
                                    "geometry": seg})
    road_man = pd.DataFrame(chunk_rows)
    road_man.to_csv(D / "road_dataset_manifest.csv", index=False)
    gchunks = gpd.GeoDataFrame(chunk_geoms, crs=roads.crs)
    gchunks.to_file(D / "road_chunks_9t.gpkg", layer="chunks", driver="GPKG")
    for k in ("road", "not_road", "drainage"):
        sub = road_man[road_man.kind == k]
        if len(sub):
            used = sub[sub.split.isin(["train", "val", "test"])]
            print(f"road_dataset_manifest.csv  {k:9s} chunks={len(sub):5d}  "
                  f"in-tile median_len={used.length_m.median():.0f}m  "
                  f"splits={used['split'].value_counts().to_dict()}")
    print(f"wrote road_chunks_9t.gpkg ({len(gchunks)} chunks)")

    # --- road classifier sample points (per POINT along lines) ---
    pt_rows = []
    for src, kind, label in [(roads, "road", 1), (not_roads, "not_road", 0)]:
        for i, row in src.reset_index(drop=True).iterrows():
            line_id = f"{kind}_{i}"
            if row.geometry is None or row.geometry.is_empty:
                continue  # keep i aligned with the gpkg row order used by eval
            for pt in sample_along_line(row.geometry, SAMPLE_STRIDE_M):
                bid, split = assign_split(pt, blocks)
                pt_rows.append({"line_id": line_id, "kind": kind, "label": label,
                                "block_id": bid, "split": split,
                                "x": pt.x, "y": pt.y})
    pts_df = pd.DataFrame(pt_rows)
    pts_df.to_csv(D / "road_classifier_samples.csv", index=False)
    by_split = pts_df.groupby(["label", "split"]).size().unstack(fill_value=0)
    print(f"road_classifier_samples.csv  total={len(pts_df)}")
    print(by_split)


if __name__ == "__main__":
    main()
