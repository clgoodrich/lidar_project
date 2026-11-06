"""Build the 1 m pit and pad label rasters for 9t.

WHY
---
The architecture comparison needs every target on ONE grid. Roads and drainage
already train at 1 m from ``labels_road_9t_1m.tif``; pits and pads only exist at
0.5 m. Without these two rasters the comparison confounds architecture with
resolution, because each target would be measured on a different grid.

The 1 m feature stack already exists (``features_pit_9t_1m.tif``, 7 bands,
z-scored via ``feature_stats_1m.json``) and is what the road and drainage models
already consume. So this is a rasterisation job, not a derivative rebuild.

WHAT IT COSTS, STATED UP FRONT
------------------------------
Median annotated pit floor is ~26 m2. At 0.5 m that is ~104 px and the shape is
resolvable. At 1 m it is ~26 px: enough to detect, marginal to delineate. The
``pit_wall`` rim is worse -- a few metres wide becomes 2-3 px, and IoU on a 3 px
ring swings on single-pixel disagreement.

The 1 m numbers are therefore EXPECTED to be lower than the 0.5 m leaderboard
numbers. That is geometry, not regression. The 0.5 m CV5 results stay the
production figures; these rasters exist for a controlled comparison only.

CLASS ORDER AND BURN ORDER
--------------------------
Copied verbatim from the 0.5 m builders so the only difference is the grid.

    labels_pit_9t_1m.tif    0 = background
                            1 = pit floor   (pit_inside)
                            2 = pit wall    (pit_wall)
       Wall is burned first and floor on top, matching
       ``_build_pit_dataset_v2.rasterize_labels``: a cell inside both is floor.

    labels_pad_9t_1m.tif    0 = background
                            1 = pad
       Pads are polygons, so they rasterise directly. No buffering, matching
       ``_build_pad_road_dataset``.

Grid comes from ``features_pit_9t_1m.tif`` so labels and features align by
construction rather than by assumption -- the same rule
``_rebuild_labels_road_9t_1m.py`` follows.

nodata=255 is load-bearing: ``_dl.py`` uses ``FocalLoss(ignore=255)``.

Outputs (data/9t/derived/05/):
    labels_pit_9t_1m.tif
    labels_pad_9t_1m.tif

Existing files are copied to ``*_pre<date>.tif`` before being replaced, never
overwritten silently.

Reproduce:
  python notebooks/wellsight_v2/s2_labels/_build_labels_pit_pad_9t_1m.py
  python notebooks/wellsight_v2/s2_labels/_build_labels_pit_pad_9t_1m.py --dry-run
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T as D, path_for, read_layer  # noqa: E402

ANN = path_for("truth") / "annotations_proj.gpkg"
GRID = D / "features_pit_9t_1m.tif"

OUT_PIT = D / "labels_pit_9t_1m.tif"
OUT_PAD = D / "labels_pad_9t_1m.tif"

REF_PIT_05 = D / "labels_pit_9t_05.tif"
REF_PAD_05 = D / "labels_pad_9t_05.tif"


def _profile(H, W, crs, transform):
    return dict(driver="GTiff", height=H, width=W, count=1, dtype="uint8",
                crs=crs, transform=transform, nodata=255,
                compress="deflate", predictor=2, tiled=True)


def _backup(path: Path) -> None:
    if not path.exists():
        return
    bak = path.with_name(f"{path.stem}_pre{date.today().isoformat()}{path.suffix}")
    if bak.exists():
        print(f"  backup already exists, left alone: {bak.name}")
        return
    shutil.copy2(path, bak)
    print(f"  backed up -> {bak.name}")


def _compare_against_05(name, arr, ref_path, cls, px_1m=1.0, px_05=0.25):
    """Area at 1 m against area at 0.5 m. Both measure the same annotations, so a
    large gap means the rasterisation lost thin geometry, not that the data
    changed."""
    if not ref_path.exists():
        print(f"    no 0.5 m reference at {ref_path.name}, skipping area check")
        return
    with rasterio.open(ref_path) as r:
        ref = r.read(1)
    a1 = int((arr == cls).sum()) * px_1m
    a0 = int((ref == cls).sum()) * px_05
    if a0 == 0:
        print(f"    {name}: 0.5 m reference has no class {cls} pixels")
        return
    print(f"    {name}: {a1:,.0f} m2 at 1 m vs {a0:,.0f} m2 at 0.5 m "
          f"({100 * a1 / a0:.1f}% retained)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be written; write nothing")
    args = ap.parse_args(argv)

    if not GRID.exists():
        raise SystemExit(f"missing 1 m feature stack: {GRID}")

    with rasterio.open(GRID) as r:
        H, W = r.height, r.width
        transform, crs = r.transform, r.crs
        res = r.res
    print(f"grid from {GRID.name}: {W} x {H} @ {res[0]:g} m  {crs}")
    if abs(res[0] - 1.0) > 1e-6 or abs(res[1] - 1.0) > 1e-6:
        raise SystemExit(f"expected a 1 m grid, got {res}")

    layers = gpd.list_layers(ANN)["name"].tolist()
    print(f"annotation layers: {layers}")

    # --- pit: 3-class, wall first then floor on top ---------------------------
    pit_inside = read_layer(ANN, "pit_inside").to_crs(crs)
    pit_wall = read_layer(ANN, "pit_wall").to_crs(crs)
    print(f"\npit: {len(pit_inside)} floors, {len(pit_wall)} walls")

    shapes = ([(g, 2) for g in pit_wall.geometry if g is not None and not g.is_empty]
              + [(g, 1) for g in pit_inside.geometry if g is not None and not g.is_empty])
    if not shapes:
        raise SystemExit("no pit geometry to burn; refusing to write a blank raster")
    pit_arr = rasterize(shapes, out_shape=(H, W), transform=transform,
                        fill=0, dtype="uint8")
    n_floor = int((pit_arr == 1).sum())
    n_wall = int((pit_arr == 2).sum())
    print(f"  floor {n_floor:,} px, wall {n_wall:,} px "
          f"({100 * (n_floor + n_wall) / (H * W):.3f}% of tile)")
    _compare_against_05("floor", pit_arr, REF_PIT_05, 1)
    _compare_against_05("wall", pit_arr, REF_PIT_05, 2)
    if n_floor == 0 or n_wall == 0:
        raise SystemExit("a pit class rasterised to zero pixels; refusing to write")

    # --- pad: binary, polygons burn directly ----------------------------------
    pad_layer = "pad" if "pad" in layers else "plat"
    pad = read_layer(ANN, pad_layer).to_crs(crs)
    print(f"\npad: {len(pad)} polygons (layer '{pad_layer}')")
    pad_shapes = [(g, 1) for g in pad.geometry if g is not None and not g.is_empty]
    if not pad_shapes:
        raise SystemExit("no pad geometry to burn; refusing to write a blank raster")
    pad_arr = rasterize(pad_shapes, out_shape=(H, W), transform=transform,
                        fill=0, dtype="uint8")
    n_pad = int((pad_arr == 1).sum())
    print(f"  pad {n_pad:,} px ({100 * n_pad / (H * W):.3f}% of tile)")
    _compare_against_05("pad", pad_arr, REF_PAD_05, 1)
    if n_pad == 0:
        raise SystemExit("pad rasterised to zero pixels; refusing to write")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    prof = _profile(H, W, crs, transform)
    for path, arr in ((OUT_PIT, pit_arr), (OUT_PAD, pad_arr)):
        _backup(path)
        with rasterio.open(path, "w", **prof) as dst:
            dst.write(arr, 1)
        print(f"wrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
