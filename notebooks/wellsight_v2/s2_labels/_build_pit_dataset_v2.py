"""Build the pit label raster, the spatial-block split, and the per-pit manifest.

Rewrite of ``_build_pit_dataset.py``. Same outputs and same values; three
differences that matter.

**It refuses to reassign the split unless told to.** Regenerating the manifest
moves every block tally, and therefore every CV5 fold, away from whatever the
deployed checkpoints were trained against. That happened for real on
2026-08-12 and was recovered only from the E: mirror -- see
``docs/golden/NON_DETERMINISTIC.md:28-62``. ``--force`` is a decision to retrain
everything downstream, not a way past a prompt.

**Nothing is written until every input has been validated**, so a failed run
cannot leave a fresh raster beside a stale manifest. The original wrote the
raster at its line 77 and the manifest at 159, and currently dies in between.

**``--out-dir`` and ``--dry-run``** make it possible to see what a run would do
without touching the live training inputs. Their absence is how the 2026-08-12
incident happened.

It no longer writes ``mask_plat_9t_05.tif``: zero readers repo-wide, and
byte-identical to ``labels_plat_9t_05.tif`` from ``_build_pad_road_dataset.py``.
Dropping it also means the pad layer is never loaded -- ``pad_id`` already rides
on ``pit_inside``.

Inputs
    data/9t/derived/05/dem_9t_05.tif        reference grid; nothing is resampled
    qgis/annotations/annotations_proj.gpkg  layers pit_inside, pit_wall

Outputs (into <out-dir>)
    labels_pit_9t_05.tif      uint8: 0=bg, 1=pit_floor, 2=pit_wall, nodata=255
    pit_blocks_9t.gpkg        layer "blocks", all 144 cells, carrying `split`
    pit_dataset_manifest.csv  pit_inside_id, pad_id, block_id, split, centroid_x/y

Run
    python notebooks/wellsight_v2/s2_labels/_build_pit_dataset_v2.py --dry-run
    python notebooks/wellsight_v2/s2_labels/_build_pit_dataset_v2.py --out-dir /tmp/scratch
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping, NamedTuple, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import box

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))          # notebooks/wellsight_v2, for _common
sys.path.insert(0, str(_HERE))                 # s2_labels, for _manifest_guard

from _common import DERIV_9T, normalize_ids, path_for, read_layer
from _manifest_guard import check_or_refuse

# Spatial-block grid: 12 x 12 = 144 cells over the 4.5 km tile, each 375 m.
# Finer grid -> more blocks contain pits -> better-balanced splits.
GRID_NX, GRID_NY = 12, 12
#: Fractions of PITS, not of blocks. Pits cluster on pads, so splitting by block
#: count could hand test a fifth of the blocks and a twentieth of the pits.
SPLIT_FRACS: dict[str, float] = {"train": 0.70, "val": 0.15, "test": 0.15}
RNG_SEED = 42

REF_NAME = "dem_9t_05.tif"
LABELS_NAME = "labels_pit_9t_05.tif"
BLOCKS_NAME = "pit_blocks_9t.gpkg"
#: Carries no area or resolution token, unlike every other output. That breaks
#: the descriptive-filename rule, but 12 readers hardcode it. Follow-up.
MANIFEST_NAME = "pit_dataset_manifest.csv"


class Grid(NamedTuple):
    """The reference DEM's grid. Every output copies these numbers verbatim,
    which is what makes label pixel (r, c) the same ground as feature pixel
    (r, c)."""
    profile: dict
    transform: rasterio.Affine
    height: int
    width: int
    bounds: rasterio.coords.BoundingBox
    crs: rasterio.crs.CRS

    @property
    def px_m2(self) -> float:
        """Ground area of one pixel, m^2. 0.5 x 0.5 = 0.25 at the usual grid."""
        return self.transform.a * (-self.transform.e)


def load_grid(ref_path: Path) -> Grid:
    with rasterio.open(ref_path) as r:
        return Grid(r.profile.copy(), r.transform, r.height, r.width, r.bounds, r.crs)


def load_pits(ann_path: Path, grid: Grid) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Read the two pit layers and validate them against the reference grid.

    ``read_layer`` resolves canonical layer names against legacy ones and
    normalizes the ID columns, so a pre-rename GeoPackage loads unchanged.
    """
    pit_inside = read_layer(ann_path, "pit_inside")
    pit_wall = read_layer(ann_path, "pit_wall")

    # The block grid is built from the DEM's bounds but was historically stamped
    # with the ANNOTATION crs. If those ever diverge the sjoin below either
    # raises or, worse, mis-assigns every pit. Compare CRS objects, never their
    # str(): the DEM carries full WKT PROJCS while DST_CRS is "EPSG:6346", and
    # CRS.__eq__ compares by definition.
    for name, gdf in (("pit_inside", pit_inside), ("pit_wall", pit_wall)):
        if gdf.crs is None:
            raise SystemExit(f"{name} has no CRS; expected {grid.crs.to_string()}")
        if gdf.crs != grid.crs:
            raise SystemExit(
                f"CRS mismatch on {name}\n"
                f"  reference grid : {grid.crs.to_string()}\n"
                f"  annotation     : {gdf.crs.to_string()}\n"
                "Reproject the annotation upstream. Doing it here would silently "
                "shift every centroid and every burned pixel.")

    # A duplicated or null id would be collapsed silently by the sjoin lookup.
    ids = pit_inside["pit_inside_id"]
    if ids.isna().any():
        raise SystemExit(f"pit_inside has {int(ids.isna().sum())} rows with no pit_inside_id")
    if ids.duplicated().any():
        dupes = sorted(ids[ids.duplicated()].unique())[:10]
        raise SystemExit(f"pit_inside_id is not unique; repeated: {dupes}")

    return pit_inside, pit_wall


def rasterize_labels(pit_inside: gpd.GeoDataFrame,
                     pit_wall: gpd.GeoDataFrame,
                     grid: Grid) -> np.ndarray:
    """Burn the annotations onto the grid: 0 background, 1 floor, 2 wall.

    Walls are listed first so floors paint over them where they overlap.
    ``all_touched=False`` means a pixel is claimed only if its CENTRE falls
    inside the shape -- True would fatten every pit by a half-pixel of invented
    rim, 25 cm at 0.5 m.
    """
    shapes = ([(g, 2) for g in pit_wall.geometry if g and not g.is_empty]
              + [(g, 1) for g in pit_inside.geometry if g and not g.is_empty])
    if not shapes:
        # rasterize() raises on an empty iterable; an empty annotation set is a
        # legitimate (if useless) input, so return a blank grid instead.
        return np.zeros((grid.height, grid.width), dtype="uint8")

    label = rasterize(shapes, out_shape=(grid.height, grid.width),
                      transform=grid.transform, fill=0, dtype="uint8",
                      all_touched=False)

    # Protect the downstream contract where it is produced rather than where it
    # is consumed: _dl.py:99 FocalLoss(ignore=255) and _pit_unet_v2_infer.py
    # hardcode {0, 1, 2}.
    seen = set(np.unique(label).tolist())
    if not seen <= {0, 1, 2}:
        raise SystemExit(f"label raster holds unexpected classes: {sorted(seen)}")
    return label


def write_labels(path: Path, label: np.ndarray, grid: Grid) -> None:
    """Write the label raster on the DEM's exact profile.

    Deliberately not _common.write_tif: make_profile hardcodes tiled=True /
    blocksize=512, while the DEM (and therefore every existing label raster) is
    tiled=False with 9000x1 row strips. Matching those bytes is what lets a v1
    and v2 run be compared by sha256.
    """
    profile = grid.profile.copy()
    profile.update(dtype="uint8", count=1, nodata=255,
                   compress="deflate", predictor=2)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(label, 1)


def build_blocks(grid: Grid, nx: int = GRID_NX, ny: int = GRID_NY) -> gpd.GeoDataFrame:
    """The nx-by-ny chessboard, row-major from the bottom-left.

    Every cell is kept, including the pit-free ones: four s7_analysis scripts
    take unary_union over every row to define "the 9t region", and dropping the
    empties would silently shrink it.
    """
    minx, miny, maxx, maxy = (grid.bounds.left, grid.bounds.bottom,
                              grid.bounds.right, grid.bounds.top)
    bw, bh = (maxx - minx) / nx, (maxy - miny) / ny
    ij = [(i, j) for j in range(ny) for i in range(nx)]
    return gpd.GeoDataFrame(
        {"block_id": [j * nx + i for i, j in ij],
         "ix": [i for i, _ in ij],
         "iy": [j for _, j in ij],
         "geometry": [box(minx + i * bw, miny + j * bh,
                          minx + (i + 1) * bw, miny + (j + 1) * bh) for i, j in ij]},
        crs=grid.crs)


def assign_blocks(pit_inside: gpd.GeoDataFrame, blocks: gpd.GeoDataFrame,
                  grid: Grid) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """Place each pit in a block by its centroid, and tally pits per block.

    Centroid, not overlap, so a pit straddling a block edge counts once.
    ``block_id`` stays float64 -- the off-grid pits force NaN into it, and
    Int64 would rewrite 77.0 as 77 in the CSV that 12 readers parse.
    """
    pits = pit_inside[["pit_inside_id", "pad_id"]].copy()
    centroids = pit_inside.geometry.centroid
    pits["cx"], pits["cy"] = centroids.x, centroids.y

    probes = gpd.GeoDataFrame(pits[["pit_inside_id"]], geometry=centroids, crs=grid.crs)
    hit = gpd.sjoin(probes, blocks[["block_id", "geometry"]],
                    how="left", predicate="intersects")
    # predicate="intersects" over a partition can match two blocks on a shared
    # edge. The original silently kept the first; make it loud instead, because
    # a duplicated probe would also corrupt the positional assignment below.
    if len(hit) != len(pits):
        extra = hit.index[hit.index.duplicated()].unique().tolist()[:10]
        raise SystemExit(
            f"{len(hit) - len(pits)} centroid(s) matched more than one block "
            f"(probe rows {extra}); the block grid is not a clean partition.")
    pits["block_id"] = hit["block_id"].values

    blocks = blocks.copy()
    blocks["n_pits"] = (blocks.block_id.map(pits.block_id.value_counts())
                        .fillna(0).astype(int))
    return pits, blocks


def assign_splits(blocks: gpd.GeoDataFrame,
                  fracs: Mapping[str, float] = SPLIT_FRACS,
                  seed: int = RNG_SEED) -> tuple[gpd.GeoDataFrame, dict[int, str]]:
    """Deal pit-bearing blocks into train/val/test, balanced on PIT COUNT.

    Shuffle once with a fixed seed, then give each block to whichever split is
    furthest below its target. Ties go to the first key in ``fracs`` -- build
    ``running`` in that order so reordering the dict cannot silently flip it.
    """
    blocks = blocks.copy()
    bearing = (blocks[blocks.n_pits > 0][["block_id", "n_pits"]]
               .sample(frac=1, random_state=seed).values)
    total = int(sum(n for _, n in bearing))
    targets = {s: total * f for s, f in fracs.items()}
    running = {s: 0 for s in fracs}
    split_of: dict[int, str] = {}
    for bid, n_pits in bearing:
        chosen = max(running, key=lambda s: targets[s] - running[s])
        split_of[int(bid)] = chosen
        running[chosen] += int(n_pits)

    # Pit-free blocks are "unused", spelled exactly: _build_pad_road_dataset.py
    # reads it back with str() and propagates it into the pad and road manifests.
    blocks["split"] = blocks["block_id"].map(split_of).fillna("unused")
    return blocks, split_of


def build_manifest(pits: pd.DataFrame, split_of: Mapping[int, str]) -> pd.DataFrame:
    """One row per pit: which block it sits in and which split that block took.

    ``block_id`` is float64 here; the map still hits because hash(77.0) ==
    hash(77). Casting it to int would break the NaN rows.
    """
    pits = pits.copy()
    pits["split"] = pits["block_id"].map(split_of).fillna("unused")
    manifest = pits[["pit_inside_id", "pad_id", "block_id", "split", "cx", "cy"]].copy()
    manifest.columns = ["pit_inside_id", "pad_id", "block_id", "split",
                        "centroid_x", "centroid_y"]
    return manifest


def report(grid: Grid, label: np.ndarray, blocks: gpd.GeoDataFrame,
           manifest: pd.DataFrame) -> None:
    n_floor = int((label == 1).sum())
    n_wall = int((label == 2).sum())
    print(f"Label pixels: floor={n_floor} ({n_floor * grid.px_m2:.0f} m^2)  "
          f"wall={n_wall} ({n_wall * grid.px_m2:.0f} m^2)")

    # The original never surfaced either of these. Ten percent of the training
    # set vanishing with no message is how you find out six months later.
    off = int(manifest.block_id.isna().sum())
    print(f"Off-grid: {off} of {len(manifest)} pit centroids fall outside the "
          f"reference grid -> 'unused'")
    no_pad = int(manifest.pad_id.isna().sum())
    print(f"No pad:   {no_pad} of {len(manifest)} pits sit on no drawn pad")

    print("\nBlock split summary:")
    for s in ("train", "val", "test", "unused"):
        sub = blocks[blocks.split == s]
        print(f"  {s:7s}  blocks={len(sub):3d}  pits={int(sub.n_pits.sum()):4d}")

    print("\nManifest split counts:")
    print(manifest["split"].value_counts().to_string())


def build(*, ann_path: Path, out_dir: Path, ref_path: Path | None = None,
          grid_nx: int = GRID_NX, grid_ny: int = GRID_NY,
          fracs: Mapping[str, float] = SPLIT_FRACS, seed: int = RNG_SEED,
          force: bool = False, dry_run: bool = False) -> int:
    # The DEM is an INPUT and lives with the derivative stack, not with the
    # outputs. Defaulting it to out_dir made --out-dir unusable on a scratch
    # directory, which is the flag's whole purpose.
    ref_path = ref_path or (DERIV_9T / REF_NAME)
    labels_path = out_dir / LABELS_NAME
    blocks_path = out_dir / BLOCKS_NAME
    manifest_path = out_dir / MANIFEST_NAME

    grid = load_grid(ref_path)
    print(f"Reference grid: {grid.width} x {grid.height} @ {grid.transform.a} m, "
          f"bounds={tuple(grid.bounds)}")
    print(f"Annotations:    {ann_path}")
    print(f"Output dir:     {out_dir}\n")

    pit_inside, pit_wall = load_pits(ann_path, grid)
    print(f"Loaded {len(pit_inside)} pit floors, {len(pit_wall)} rims")

    # Everything above this line is read-only. The guard sits here, once, so a
    # refusal leaves every output exactly as it was -- including the raster,
    # which the original replaced before it could fail.
    check_or_refuse(manifest_path, id_col="pit_inside_id",
                    new_count=len(pit_inside), force=force)

    label = rasterize_labels(pit_inside, pit_wall, grid)
    blocks = build_blocks(grid, grid_nx, grid_ny)
    pits, blocks = assign_blocks(pit_inside, blocks, grid)
    blocks, split_of = assign_splits(blocks, fracs, seed)
    manifest = build_manifest(pits, split_of)

    report(grid, label, blocks, manifest)

    if dry_run:
        print("\n--dry-run: nothing written. Would have written:")
        for p in (labels_path, blocks_path, manifest_path):
            print(f"  {p}")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    # Manifest last on purpose: if the process dies mid-write the old row count
    # survives, so the next run is refused rather than sailing through on a
    # half-updated state.
    write_labels(labels_path, label, grid)
    print(f"\nWrote {labels_path.name}")
    blocks.to_file(blocks_path, layer="blocks", driver="GPKG")
    print(f"Wrote {blocks_path.name}")
    manifest.to_csv(manifest_path, index=False)
    print(f"Wrote {manifest_path.name}  ({len(manifest)} pits)")

    # The layer four s7_analysis scripts union over. Cheap to confirm.
    from pyogrio import list_layers
    written = [n for n, _ in list_layers(str(blocks_path))]
    assert written == ["blocks"], f"{blocks_path.name} holds {written}"
    assert len(blocks) == grid_nx * grid_ny, f"{len(blocks)} blocks, expected {grid_nx * grid_ny}"
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ann", type=Path,
                    default=path_for("truth") / "annotations_proj.gpkg",
                    help="annotation GeoPackage (legacy column names are accepted)")
    ap.add_argument("--out-dir", type=Path, default=DERIV_9T,
                    help="where the three outputs go")
    ap.add_argument("--ref", type=Path, default=None,
                    help=f"reference DEM (default: {DERIV_9T / REF_NAME})")
    ap.add_argument("--force", action="store_true",
                    help="reassign the split even though the annotation count changed. "
                         "This invalidates the held-out claim behind every deployed "
                         "checkpoint until they are retrained.")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and report, write nothing")
    args = ap.parse_args(argv)

    return build(ann_path=args.ann, out_dir=args.out_dir, ref_path=args.ref,
                 force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
