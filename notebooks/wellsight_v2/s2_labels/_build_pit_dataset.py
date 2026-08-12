"""Build labeled raster + spatial-block train/val/test split for the pit segmentation task.

Inputs:
    data/derivatives/tiles/9t/dem_9t_05.tif                  (reference grid)
    data/derivatives/annotations/annotations_proj.gpkg (pit_inside, pit_wall, plat)

Outputs (under data/derivatives/tiles/9t/):
    labels_pit_9t_05.tif       uint8 raster: 0=bg, 1=pit_floor, 2=pit_wall
    mask_plat_9t_05.tif        uint8 raster: 0/1 plat mask
    pit_blocks_9t.gpkg         spatial-block grid with split assignments
    pit_dataset_manifest.csv   per-pit table: pit_id, plat_id, block_id, split, centroid_x/y
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T

REF = DERIV_9T / "dem_9t_05.tif"
ANN = DERIV / "annotations" / "annotations_proj.gpkg"
OUT = DERIV_9T

# Spatial-block grid: 12 x 12 = 144 cells over the 4.5 km tile (each 375 m).
# Finer grid -> more blocks contain pits -> better-balanced splits.
GRID_NX, GRID_NY = 12, 12
# Per-class split fractions on blocks that contain pits
SPLIT_FRACS = {"train": 0.70, "val": 0.15, "test": 0.15}
RNG_SEED = 42


def main():
    with rasterio.open(REF) as r:
        profile = r.profile.copy()
        transform = r.transform
        H, W = r.height, r.width
        bounds = r.bounds
        crs = r.crs
    print(f"Reference grid: {W} x {H} @ 0.5 m, bounds={tuple(bounds)}")

    pit_in = gpd.read_file(ANN, layer="pit_inside")
    pit_wall = gpd.read_file(ANN, layer="pit_wall")
    plat = gpd.read_file(ANN, layer="plat")

    # --- rasterize labels ---
    # Burn order matters: wall first, floor on top so floor wins on overlap.
    shapes_wall = [(g, 2) for g in pit_wall.geometry if g and not g.is_empty]
    shapes_floor = [(g, 1) for g in pit_in.geometry if g and not g.is_empty]
    label = rasterize(
        shapes_wall + shapes_floor,
        out_shape=(H, W),
        transform=transform,
        fill=0,
        dtype="uint8",
        all_touched=False,
    )
    n_floor = int((label == 1).sum())
    n_wall = int((label == 2).sum())
    px_m2 = transform.a * (-transform.e)
    print(f"Label pixels: floor={n_floor} ({n_floor*px_m2:.0f} m^2)  wall={n_wall} ({n_wall*px_m2:.0f} m^2)")

    lbl_profile = profile.copy()
    lbl_profile.update(dtype="uint8", count=1, nodata=255, compress="deflate", predictor=2)
    label_path = OUT / "labels_pit_9t_05.tif"
    with rasterio.open(label_path, "w", **lbl_profile) as dst:
        dst.write(label, 1)
    print(f"Wrote {label_path.name}")

    # --- plat mask ---
    plat_mask = rasterize(
        [(g, 1) for g in plat.geometry if g and not g.is_empty],
        out_shape=(H, W),
        transform=transform,
        fill=0,
        dtype="uint8",
    )
    plat_path = OUT / "mask_plat_9t_05.tif"
    with rasterio.open(plat_path, "w", **lbl_profile) as dst:
        dst.write(plat_mask, 1)
    print(f"Wrote {plat_path.name}  ({int(plat_mask.sum())} px = {int(plat_mask.sum()*px_m2)} m^2)")

    # --- spatial-block grid ---
    minx, miny, maxx, maxy = bounds.left, bounds.bottom, bounds.right, bounds.top
    bw = (maxx - minx) / GRID_NX
    bh = (maxy - miny) / GRID_NY
    blocks = []
    for j in range(GRID_NY):
        for i in range(GRID_NX):
            x0 = minx + i * bw
            y0 = miny + j * bh
            blocks.append({"block_id": j * GRID_NX + i,
                           "ix": i, "iy": j,
                           "geometry": box(x0, y0, x0 + bw, y0 + bh)})
    blocks = gpd.GeoDataFrame(blocks, crs=pit_in.crs)

    # Count pits per block by centroid
    pit_in = pit_in.copy()
    pit_in["cx"] = pit_in.geometry.centroid.x
    pit_in["cy"] = pit_in.geometry.centroid.y
    cents = gpd.GeoDataFrame(pit_in[["pit_id"]].copy(), geometry=pit_in.geometry.centroid, crs=pit_in.crs)
    j = gpd.sjoin(cents, blocks[["block_id", "geometry"]], how="left", predicate="within")
    pit_block = j.set_index("pit_id")["block_id"].to_dict()
    pit_in["block_id"] = pit_in["pit_id"].map(pit_block)

    n_per_block = pit_in.groupby("block_id").size().rename("n_pits")
    blocks = blocks.merge(n_per_block, on="block_id", how="left")
    blocks["n_pits"] = blocks["n_pits"].fillna(0).astype(int)

    # Assign splits to balance PIT COUNTS (not block counts), since pits cluster.
    # Greedy fill: shuffle pit-bearing blocks, then assign each to whichever split is
    # furthest below its target pit-count.
    rng = np.random.default_rng(RNG_SEED)
    pit_blocks = blocks[blocks.n_pits > 0][["block_id", "n_pits"]].sample(frac=1, random_state=RNG_SEED).values
    total_pits = int(sum(n for _, n in pit_blocks))
    targets = {s: total_pits * f for s, f in SPLIT_FRACS.items()}
    running = {"train": 0, "val": 0, "test": 0}
    split_of = {}
    for bid, n_pits in pit_blocks:
        # Pick split with the largest remaining deficit.
        deficits = {s: targets[s] - running[s] for s in running}
        chosen = max(deficits, key=deficits.get)
        split_of[int(bid)] = chosen
        running[chosen] += int(n_pits)
    blocks["split"] = blocks["block_id"].map(split_of).fillna("unused")

    print("\nBlock split summary:")
    for s in ("train", "val", "test", "unused"):
        sub = blocks[blocks.split == s]
        print(f"  {s:7s}  blocks={len(sub):2d}  pits={int(sub.n_pits.sum()):4d}")

    blocks.to_file(OUT / "pit_blocks_9t.gpkg", layer="blocks", driver="GPKG")
    print(f"Wrote pit_blocks_9t.gpkg")

    # --- manifest ---
    pit_in["split"] = pit_in["block_id"].map(split_of).fillna("unused")
    manifest = pit_in[["pit_id", "plat_id", "block_id", "split", "cx", "cy"]].copy()
    manifest.columns = ["pit_id", "plat_id", "block_id", "split", "centroid_x", "centroid_y"]
    manifest.to_csv(OUT / "pit_dataset_manifest.csv", index=False)
    print(f"Wrote pit_dataset_manifest.csv  ({len(manifest)} pits)")

    print("\nManifest split counts:")
    print(manifest["split"].value_counts().to_string())


if __name__ == "__main__":
    main()
