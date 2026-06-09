"""Stack the per-pixel input features into a single multi-band float32 GeoTIFF.

Output: data/derivatives/tiles/9t/features_pit_9t_05.tif (7 bands, float32, tiled, deflate)
Channels (in order):
  1 lrm_25       2 lrm_5      3 slope        4 tpi_05
  5 openness_pos 6 openness_neg  7 roughness_11
Also writes feature_stats.json with per-channel mean/std computed over TRAIN blocks only.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T as D

CHANNELS = [
    ("lrm_25",       "lrm_25_9t_05.tif"),
    ("lrm_5",        "lrm_5_9t_05.tif"),
    ("slope",        "slope_9t_05.tif"),
    ("tpi_05",       "tpi_05_9t_05.tif"),
    ("openness_pos", "openness_pos_9t_05.tif"),
    ("openness_neg", "openness_neg_9t_05.tif"),
    ("roughness_11", "roughness_11_9t_05.tif"),
]


def main():
    paths = [(name, D / fname) for name, fname in CHANNELS]
    for _, p in paths:
        if not p.exists():
            raise FileNotFoundError(p)

    with rasterio.open(paths[0][1]) as r0:
        profile = r0.profile.copy()
        H, W = r0.height, r0.width
        transform = r0.transform
    print(f"Reference grid: {W} x {H} @ 0.5 m")

    out_path = D / "features_pit_9t_05.tif"
    profile.update(count=len(paths), dtype="float32", compress="deflate",
                   predictor=3, tiled=True, blockxsize=512, blockysize=512,
                   BIGTIFF="YES", nodata=np.nan)

    # Load TRAIN block mask for stats
    blocks = gpd.read_file(D / "pit_blocks_9t.gpkg", layer="blocks")
    train_blocks = blocks[blocks.split == "train"]
    train_mask = rasterize(
        [(g, 1) for g in train_blocks.geometry],
        out_shape=(H, W), transform=transform, fill=0, dtype="uint8",
    ).astype(bool)
    print(f"Train mask: {int(train_mask.sum())} px = {train_mask.mean()*100:.1f}% of tile")

    stats = {}
    with rasterio.open(out_path, "w", **profile) as dst:
        for i, (name, src) in enumerate(paths, start=1):
            with rasterio.open(src) as r:
                arr = r.read(1).astype(np.float32)
                if r.nodata is not None:
                    arr = np.where(arr == r.nodata, np.nan, arr)
            # Stats from train block, excluding NaN
            vals = arr[train_mask]
            vals = vals[np.isfinite(vals)]
            mu, sd = float(np.mean(vals)), float(np.std(vals))
            stats[name] = {"mean": mu, "std": sd, "p2": float(np.percentile(vals, 2)),
                           "p98": float(np.percentile(vals, 98))}
            print(f"  band {i} {name:14s}  mean={mu:8.3f}  std={sd:8.3f}  "
                  f"p2={stats[name]['p2']:8.2f}  p98={stats[name]['p98']:8.2f}")
            dst.write(arr, i)
            dst.set_band_description(i, name)

    with open(D / "feature_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\nWrote {out_path.name} and feature_stats.json")


if __name__ == "__main__":
    main()
