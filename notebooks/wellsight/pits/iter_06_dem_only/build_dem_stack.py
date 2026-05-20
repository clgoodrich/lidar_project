"""Build a 1-channel feature TIF containing only the raw DEM.

This is the simplest possible input to test against the engineered 7/11-channel
stacks. Same grid, same CRS, same train-block stats computation.
"""
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import rasterize
import geopandas as gpd

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
OUTDIR = D / "iterations" / "06_dem_only"; OUTDIR.mkdir(parents=True, exist_ok=True)

DEM_PATH = D / "dem_9t_05.tif"
BLOCKS = D / "pit_blocks_9t.gpkg"


def main():
    with rasterio.open(DEM_PATH) as r:
        dem = r.read(1).astype(np.float32)
        nd = r.nodata
        profile = r.profile.copy()
        tf = r.transform
        H, W = r.height, r.width
    if nd is not None:
        dem = np.where(dem == nd, np.nan, dem)
    print(f"DEM: {dem.shape} finite={np.isfinite(dem).mean()*100:.1f}% "
          f"z={np.nanmin(dem):.1f}..{np.nanmax(dem):.1f}")

    # Train-block stats
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    train_mask = rasterize(
        [(g, 1) for g in blocks[blocks.split == "train"].geometry],
        out_shape=(H, W), transform=tf, fill=0, dtype="uint8",
    ).astype(bool)
    vals = dem[train_mask]; vals = vals[np.isfinite(vals)]
    mu = float(vals.mean()); sd = float(vals.std())
    if sd < 1e-6: sd = 1.0
    stats = {"dem": {"mean": mu, "std": sd,
                     "p2": float(np.percentile(vals, 2)),
                     "p98": float(np.percentile(vals, 98))}}
    print(f"  train-block stats: mean={mu:.2f} std={sd:.2f} "
          f"p2={stats['dem']['p2']:.1f} p98={stats['dem']['p98']:.1f}")

    out_path = OUTDIR / "features_dem_9t_05.tif"
    profile.update(count=1, dtype="float32", compress="deflate", predictor=3,
                   tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES",
                   nodata=np.nan)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(dem, 1)
        dst.set_band_description(1, "dem")
    (OUTDIR / "feature_stats_dem.json").write_text(json.dumps(stats, indent=2))
    print(f"  wrote {out_path.name} and feature_stats_dem.json")


if __name__ == "__main__":
    main()
