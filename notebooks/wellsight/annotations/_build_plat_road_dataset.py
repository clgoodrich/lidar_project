"""Build labels and manifests for plat segmentation, road segmentation, and road classification.

Outputs (under data/derivatives/9t/):
    labels_plat_9t_05.tif        uint8  0=bg, 1=plat
    labels_road_9t_05.tif        uint8  0=bg, 1=road  (roads buffered 1.5 m)
    plat_dataset_manifest.csv    one row per plat: plat_id, block_id, split, centroid_x/y
    road_dataset_manifest.csv    one row per road LINE: road_id, kind, block_id, split, mid_x/y
    road_classifier_samples.csv  one row per sample POINT along lines (for the classifier)
"""
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
import geopandas as gpd
from shapely.geometry import LineString, Point

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
ANN = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
REF = D / "dem_9t_05.tif"
BLOCKS = D / "pit_blocks_9t.gpkg"

ROAD_BUFFER_M = 1.5  # half-width for road rasterization
SAMPLE_STRIDE_M = 4.0  # sample points along lines for the classifier


def assign_split(geom_or_pt, blocks):
    """Look up which block (and thereby split) a point or geometry falls in."""
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
    plat = gpd.read_file(ANN, layer="plat")
    roads = gpd.read_file(ANN, layer="roads")
    not_roads = gpd.read_file(ANN, layer="not_roads")
    print(f"plat={len(plat)}  roads={len(roads)}  not_roads={len(not_roads)}")

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
        bid, split = assign_split(row.geometry, blocks)
        c = row.geometry.centroid
        plat_rows.append({"plat_id": int(row.plat_id), "block_id": bid, "split": split,
                          "centroid_x": c.x, "centroid_y": c.y,
                          "area_m2": float(row.geometry.area)})
    plat_man = pd.DataFrame(plat_rows)
    plat_man.to_csv(D / "plat_dataset_manifest.csv", index=False)
    print(f"plat_dataset_manifest.csv  splits={plat_man['split'].value_counts().to_dict()}")

    # --- road line manifest (per LINE, used by the road U-Net) ---
    line_rows = []
    for src, kind in [(roads, "road"), (not_roads, "not_road")]:
        for i, row in src.reset_index(drop=True).iterrows():
            g = row.geometry
            mid = g.interpolate(0.5, normalized=True)
            bid, split = assign_split(mid, blocks)
            line_rows.append({"line_id": f"{kind}_{i}", "kind": kind,
                              "block_id": bid, "split": split,
                              "mid_x": mid.x, "mid_y": mid.y,
                              "length_m": float(g.length)})
    road_man = pd.DataFrame(line_rows)
    road_man.to_csv(D / "road_dataset_manifest.csv", index=False)
    print(f"road_dataset_manifest.csv  "
          f"roads splits={road_man[road_man.kind=='road']['split'].value_counts().to_dict()}  "
          f"not_roads splits={road_man[road_man.kind=='not_road']['split'].value_counts().to_dict()}")

    # --- road classifier sample points (per POINT along lines) ---
    pt_rows = []
    for src, kind, label in [(roads, "road", 1), (not_roads, "not_road", 0)]:
        for i, row in src.reset_index(drop=True).iterrows():
            line_id = f"{kind}_{i}"
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
