"""Build labeled raster + spatial-block train/val/test split for the pit segmentation task.

Inputs:
    data/derivatives/tiles/9t/dem_9t_05.tif                  (reference grid)
    data/derivatives/annotations/annotations_proj.gpkg (pit_inside, pit_wall, plat)

Outputs (under data/derivatives/tiles/9t/):
    labels_pit_9t_05.tif       uint8 raster: 0=bg, 1=pit_floor, 2=pit_wall
    mask_plat_9t_05.tif        uint8 raster: 0/1 plat mask
    pit_blocks_9t.gpkg         spatial-block grid with split assignments
    pit_dataset_manifest.csv   per-pit table: pit_inside_id, pad_id, block_id, split, centroid_x/y
"""
import sys                                  # used to edit Python's import search path below
from pathlib import Path                    # file paths as objects, works on any OS

import geopandas as gpd                     # pandas, except every row also carries a shape
import numpy as np                          # arrays and the random number generator
import pandas as pd                         # plain tables (the manifest CSV)
import rasterio                             # read and write GeoTIFFs
from rasterio.features import rasterize     # turn vector shapes into a grid of numbers
from shapely.geometry import box            # build a rectangle from its four edges

# Put notebooks/wellsight_v2/ on the import path so `from _common import ...` works
# no matter what directory you launch the script from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T, path_for  # shared project paths, read_layer

REF = DERIV_9T / "dem_9t_05.tif"            # the DEM whose grid every output below copies
ANN = path_for("truth") / "annotations_proj.gpkg"  # your drawings, reprojected to metres
OUT = DERIV_9T                              # everything below is written into this folder

# Spatial-block grid: 12 x 12 = 144 cells over the 4.5 km tile (each 375 m).
# Finer grid -> more blocks contain pits -> better-balanced splits.
GRID_NX, GRID_NY = 12, 12
# Per-class split fractions on blocks that contain pits
SPLIT_FRACS = {"train": 0.70, "val": 0.15, "test": 0.15}  # 70% practice, 15% check, 15% exam
RNG_SEED = 42                               # fixed seed, so the same split comes out every run


def main():
    # Copy the DEM's grid. Every output below reuses these exact numbers, which is
    # what makes label pixel (r, c) the same patch of ground as feature pixel (r, c).
    with rasterio.open(REF) as r:
        profile = r.profile.copy()          # size, dtype, CRS, compression, all in one dict
        transform = r.transform             # where the grid sits on Earth, and how big a pixel is
        H, W = r.height, r.width            # 9000 x 9000
        bounds = r.bounds                   # the tile's outer edges, in metres
        crs = r.crs                         # EPSG:6346
    print(f"Reference grid: {W} x {H} @ 0.5 m, bounds={tuple(bounds)}")

    pit_in = read_layer(ANN, "pit_inside")   # pit floors, the inner polygons you drew
    pit_wall = read_layer(ANN, "pit_wall")   # the rim donuts, built by _prep_annotations
    plat = read_layer(ANN, "plat")           # well pad outlines

    # --- rasterize labels ---
    # Burn order matters: wall first, floor on top so floor wins on overlap.
    shapes_wall = [(g, 2) for g in pit_wall.geometry if g and not g.is_empty]   # pair each rim with the number 2
    shapes_floor = [(g, 1) for g in pit_in.geometry if g and not g.is_empty]    # pair each floor with the number 1
    # Paint those shapes onto a blank 9000 x 9000 grid. Later shapes paint over
    # earlier ones, which is exactly why the floors are listed second.
    label = rasterize(
        shapes_wall + shapes_floor,
        out_shape=(H, W),                   # same size as the DEM
        transform=transform,                # same position on Earth as the DEM
        fill=0,                             # every pixel starts as background
        dtype="uint8",                      # whole numbers 0-255, one byte per pixel
        all_touched=False,                  # paint a pixel only if its CENTRE is inside the shape
    )
    n_floor = int((label == 1).sum())       # how many floor pixels got painted
    n_wall = int((label == 2).sum())        # how many wall pixels got painted
    px_m2 = transform.a * (-transform.e)    # ground area of one pixel, m^2 (0.5 x 0.5 = 0.25)
    print(f"Label pixels: floor={n_floor} ({n_floor*px_m2:.0f} m^2)  wall={n_wall} ({n_wall*px_m2:.0f} m^2)")

    lbl_profile = profile.copy()            # start from the DEM's settings
    lbl_profile.update(dtype="uint8", count=1, nodata=255, compress="deflate", predictor=2)  # labels are 1 band of small ints
    label_path = OUT / "labels_pit_9t_05.tif"
    with rasterio.open(label_path, "w", **lbl_profile) as dst:
        dst.write(label, 1)                 # write the grid into band 1
    print(f"Wrote {label_path.name}")

    # --- plat mask ---
    # Same idea, simpler: 1 anywhere a pad polygon covers, 0 everywhere else.
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
    # Chop the tile into a 12 x 12 chessboard. Each square goes entirely into
    # train, val, or test -- never split down the middle.
    minx, miny, maxx, maxy = bounds.left, bounds.bottom, bounds.right, bounds.top
    bw = (maxx - minx) / GRID_NX            # block width in metres (375)
    bh = (maxy - miny) / GRID_NY            # block height in metres (375)
    blocks = []                             # collect the 144 squares here
    for j in range(GRID_NY):                # walk the rows
        for i in range(GRID_NX):            # walk the columns within a row
            x0 = minx + i * bw              # left edge of this square
            y0 = miny + j * bh              # bottom edge of this square
            blocks.append({"block_id": j * GRID_NX + i,     # 0..143, one number per square
                           "ix": i, "iy": j,               # column and row, handy when debugging
                           "geometry": box(x0, y0, x0 + bw, y0 + bh)})  # the square itself
    blocks = gpd.GeoDataFrame(blocks, crs=pit_in.crs)      # turn the plain list into a map layer

    # Count pits per block by centroid
    pit_in = pit_in.copy()                  # work on a copy, leave the loaded layer alone
    pit_in["cx"] = pit_in.geometry.centroid.x  # each pit's centre point, x
    pit_in["cy"] = pit_in.geometry.centroid.y  # each pit's centre point, y
    # A pit belongs to whichever square its CENTRE lands in. Using the centre means a
    # pit straddling a block edge is counted once, not twice.
    cents = gpd.GeoDataFrame(pit_in[["pit_inside_id"]].copy(), geometry=pit_in.geometry.centroid, crs=pit_in.crs)
    j = gpd.sjoin(cents, blocks[["block_id", "geometry"]], how="left", predicate="within")  # which square holds each centre
    pit_block = j.set_index("pit_inside_id")["block_id"].to_dict()  # lookup: pit -> its square
    pit_in["block_id"] = pit_in["pit_inside_id"].map(pit_block)     # stamp the square number onto each pit

    n_per_block = pit_in.groupby("block_id").size().rename("n_pits")  # tally pits per square
    blocks = blocks.merge(n_per_block, on="block_id", how="left")     # attach the tally as a column
    blocks["n_pits"] = blocks["n_pits"].fillna(0).astype(int)         # squares with no pits get 0, not blank

    # Assign splits to balance PIT COUNTS (not block counts), since pits cluster.
    # Greedy fill: shuffle pit-bearing blocks, then assign each to whichever split is
    # furthest below its target pit-count.
    rng = np.random.default_rng(RNG_SEED)
    # Only squares that actually contain pits get split. sample(frac=1) shuffles them,
    # with a fixed seed so the shuffle is identical on every run.
    pit_blocks = blocks[blocks.n_pits > 0][["block_id", "n_pits"]].sample(frac=1, random_state=RNG_SEED).values
    total_pits = int(sum(n for _, n in pit_blocks))         # how many pits are in play
    targets = {s: total_pits * f for s, f in SPLIT_FRACS.items()}  # how many each split SHOULD end up with
    running = {"train": 0, "val": 0, "test": 0}             # how many each split has so far
    split_of = {}                                           # lookup: square -> train/val/test
    for bid, n_pits in pit_blocks:                          # hand out the squares one at a time
        # Pick split with the largest remaining deficit.
        deficits = {s: targets[s] - running[s] for s in running}  # how far each split still is from its target
        chosen = max(deficits, key=deficits.get)            # the hungriest split wins this square
        split_of[int(bid)] = chosen                         # record the decision
        running[chosen] += int(n_pits)                      # that split now owns this square's pits
    blocks["split"] = blocks["block_id"].map(split_of).fillna("unused")  # squares with no pits are "unused"

    print("\nBlock split summary:")
    for s in ("train", "val", "test", "unused"):
        sub = blocks[blocks.split == s]                     # the squares that landed in this split
        print(f"  {s:7s}  blocks={len(sub):2d}  pits={int(sub.n_pits.sum()):4d}")  # squares and pits per split

    blocks.to_file(OUT / "pit_blocks_9t.gpkg", layer="blocks", driver="GPKG")  # save the chessboard for the trainer
    print(f"Wrote pit_blocks_9t.gpkg")

    # --- manifest ---
    # One row per pit, saying which square it sits in and which split that square
    # went to. The trainer reads this to know which pits it is allowed to learn from.
    pit_in["split"] = pit_in["block_id"].map(split_of).fillna("unused")  # copy the square's split onto the pit
    manifest = pit_in[["pit_inside_id", "pad_id", "block_id", "split", "cx", "cy"]].copy()  # keep only these columns
    manifest.columns = ["pit_inside_id", "pad_id", "block_id", "split", "centroid_x", "centroid_y"]  # clearer names in the CSV
    manifest.to_csv(OUT / "pit_dataset_manifest.csv", index=False)  # index=False: no extra unnamed column
    print(f"Wrote pit_dataset_manifest.csv  ({len(manifest)} pits)")

    print("\nManifest split counts:")
    print(manifest["split"].value_counts().to_string())     # final tally, pits per split


if __name__ == "__main__":
    main()
