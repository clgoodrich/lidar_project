"""Prep the 1 m road-training inputs from the 9t_1m derivative stack.

Mirrors pits/_stack_features.py but at 1 m and with roughness_5 (the native 1 m
roughness kernel) in place of roughness_11. Produces, under data/derivatives/9t/:
    features_pit_9t_1m.tif   7-band float32 stack (same channel order as 0.5 m)
    feature_stats_1m.json    per-channel mean/std over TRAIN blocks only
    labels_road_9t_1m.tif    uint8 0=bg 1=road (roads buffered 1.5 m), 1 m grid

The 1 m grid is taken from data/derivatives/9t_1m/dem_9t_1m.tif, which was built
by _build_derivatives over the exact 9t bbox -> aligns with pit_blocks_9t.gpkg.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T as D

SRC_1M = DERIV / "9t_1m"
ANN = DERIV / "annotations" / "annotations_proj.gpkg"
ROAD_BUFFER_M = 1.5
DRAIN_BUFFER_M = 2.0  # channels are a touch wider than the 1.5 m road half-width

CHANNELS = [
    ("lrm_25",       "lrm_25_9t_1m.tif"),
    ("lrm_5",        "lrm_5_9t_1m.tif"),
    ("slope",        "slope_9t_1m.tif"),
    ("tpi_05",       "tpi_05_9t_1m.tif"),
    ("openness_pos", "openness_pos_9t_1m.tif"),
    ("openness_neg", "openness_neg_9t_1m.tif"),
    ("roughness_5",  "roughness_5_9t_1m.tif"),
]


def main():
    paths = [(name, SRC_1M / fname) for name, fname in CHANNELS]
    for _, p in paths:
        if not p.exists():
            raise FileNotFoundError(p)

    with rasterio.open(paths[0][1]) as r0:
        profile = r0.profile.copy()
        H, W = r0.height, r0.width
        transform = r0.transform
        crs = r0.crs
    print(f"Reference grid: {W} x {H} @ 1 m")

    # --- feature stack + train-only stats ---
    out_path = D / "features_pit_9t_1m.tif"
    profile.update(count=len(paths), dtype="float32", compress="deflate",
                   predictor=3, tiled=True, blockxsize=512, blockysize=512,
                   BIGTIFF="YES", nodata=np.nan)
    blocks = gpd.read_file(D / "pit_blocks_9t.gpkg", layer="blocks")
    train_blocks = blocks[blocks.split == "train"]
    train_mask = rasterize([(g, 1) for g in train_blocks.geometry],
                           out_shape=(H, W), transform=transform,
                           fill=0, dtype="uint8").astype(bool)
    print(f"Train mask: {int(train_mask.sum())} px = {train_mask.mean()*100:.1f}%")

    stats = {}
    with rasterio.open(out_path, "w", **profile) as dst:
        for i, (name, src) in enumerate(paths, start=1):
            with rasterio.open(src) as r:
                arr = r.read(1).astype(np.float32)
                if r.nodata is not None:
                    arr = np.where(arr == r.nodata, np.nan, arr)
            vals = arr[train_mask]
            vals = vals[np.isfinite(vals)]
            mu, sd = float(np.mean(vals)), float(np.std(vals))
            stats[name] = {"mean": mu, "std": sd,
                           "p2": float(np.percentile(vals, 2)),
                           "p98": float(np.percentile(vals, 98))}
            print(f"  band {i} {name:14s}  mean={mu:8.3f}  std={sd:8.3f}")
            dst.write(arr, i)
            dst.set_band_description(i, name)
    with open(D / "feature_stats_1m.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"wrote {out_path.name} + feature_stats_1m.json")

    # --- road labels at 1 m: 0=bg, 1=road, 2=drainage ---
    # Drainage is painted first, then road on top, so a road that crosses a
    # channel (culvert) stays labelled road rather than drainage.
    roads = gpd.read_file(ANN, layer="roads")
    layers = gpd.list_layers(ANN)["name"].tolist()
    drainage = (gpd.read_file(ANN, layer="drainage")
                if "drainage" in layers else gpd.GeoDataFrame(geometry=[]))

    label = np.zeros((H, W), dtype="uint8")
    if len(drainage):
        dbuf = [g.buffer(DRAIN_BUFFER_M) for g in drainage.geometry
                if g is not None and not g.is_empty]
        drain_arr = rasterize([(g, 1) for g in dbuf], out_shape=(H, W),
                              transform=transform, fill=0, dtype="uint8")
        label[drain_arr == 1] = 2
    rbuf = [g.buffer(ROAD_BUFFER_M) for g in roads.geometry
            if g is not None and not g.is_empty]
    road_arr = rasterize([(g, 1) for g in rbuf], out_shape=(H, W),
                         transform=transform, fill=0, dtype="uint8")
    label[road_arr == 1] = 1  # road wins over drainage on overlap

    p1 = profile.copy()
    p1.update(count=1, dtype="uint8", nodata=255, compress="deflate", predictor=2)
    p1.pop("blockxsize", None); p1.pop("blockysize", None)
    with rasterio.open(D / "labels_road_9t_1m.tif", "w", **p1) as dst:
        dst.write(label, 1)
    print(f"labels_road_9t_1m.tif  ({int((label==1).sum())} px road, "
          f"{int((label==2).sum())} px drainage)")


if __name__ == "__main__":
    main()
