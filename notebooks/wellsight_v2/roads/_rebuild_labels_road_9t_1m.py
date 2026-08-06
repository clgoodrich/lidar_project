"""Rebuild ONLY the 1 m road label raster for 9t from current annotations.

`_prep_road_1m.py` builds three things: the 7-band feature stack, the train-only
channel statistics, and the label raster. It reads its channels from
`data/derivatives/tiles/9t_1m/`, which no longer exists -- that directory was one
of the junctions into `E:\\lidar_project_data_DO_NOT_DELETE` and the junctions are
gone. The two expensive products it made survive as
`features_pit_9t_1m.tif` (339 MB) and `feature_stats_1m.json`, so the stack does
not need rebuilding. The labels do.

Why: `labels_road_9t_1m.tif` dates from 2026-06-10 and holds 556,773 road pixels,
about 185.6 km at the 1.5 m half-width. `roads.shp` was extended on 2026-07-30 and
now carries 206.09 km inside the 9t footprint, so the label raster was training
the model to call ~20 km of real annotated road "background".

Grid comes from `features_pit_9t_1m.tif` so labels and features align by
construction rather than by assumption. Class order and buffers are copied
verbatim from `_prep_road_1m.py`:

    0 = background
    1 = road      (roads.shp buffered 1.5 m)
    2 = drainage  (drainage buffered 2.0 m)

Drainage is painted first and road on top, so a road crossing a channel stays
labelled road rather than drainage.

The previous label raster is copied to `labels_road_9t_1m_pre2026-08-06.tif`
before being replaced, so the old model stays reproducible.

Outputs (data/derivatives/tiles/9t/):
    labels_road_9t_1m.tif                  rebuilt, 0/1/2
    labels_road_9t_1m_pre2026-08-06.tif    the 2026-06-10 raster it replaced

Reproduce:
  python notebooks/wellsight_v2/roads/_rebuild_labels_road_9t_1m.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T as D                          # noqa: E402

ANN = DERIV / "annotations" / "annotations_proj.gpkg"
GRID = D / "features_pit_9t_1m.tif"
OUT = D / "labels_road_9t_1m.tif"
BACKUP = D / "labels_road_9t_1m_pre2026-08-06.tif"

ROAD_BUFFER_M = 1.5
DRAIN_BUFFER_M = 2.0


def main() -> int:
    with rasterio.open(GRID) as r:
        H, W = r.height, r.width
        transform, crs = r.transform, r.crs
    print(f"grid from {GRID.name}: {W} x {H} @ 1 m  {crs}")

    if OUT.exists():
        with rasterio.open(OUT) as r:
            old = r.read(1)
        print(f"old labels: {int((old == 1).sum()):,} road px, "
              f"{int((old == 2).sum()):,} drainage px")
        if old.shape != (H, W):
            raise SystemExit(f"old label grid {old.shape} != feature grid {(H, W)}")
        if not BACKUP.exists():
            shutil.copy2(OUT, BACKUP)
            print(f"backed up -> {BACKUP.name}")
        else:
            print(f"backup already exists, left alone: {BACKUP.name}")

    roads = gpd.read_file(ANN, layer="roads").to_crs(crs)
    layers = gpd.list_layers(ANN)["name"].tolist()
    drainage = (gpd.read_file(ANN, layer="drainage").to_crs(crs)
                if "drainage" in layers else gpd.GeoDataFrame(geometry=[]))
    print(f"annotations: {len(roads)} road lines, {len(drainage)} drainage lines")

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
    label[road_arr == 1] = 1        # road wins over drainage on overlap

    prof = dict(driver="GTiff", height=H, width=W, count=1, dtype="uint8",
                crs=crs, transform=transform, nodata=255,
                compress="deflate", predictor=2, tiled=True)
    with rasterio.open(OUT, "w", **prof) as dst:
        dst.write(label, 1)

    nr, nd = int((label == 1).sum()), int((label == 2).sum())
    print(f"new labels: {nr:,} road px (~{nr / (2 * ROAD_BUFFER_M * 1000):.1f} km), "
          f"{nd:,} drainage px")
    if OUT.exists() and 'old' in dir():
        print(f"change: road {nr - int((old == 1).sum()):+,} px, "
              f"drainage {nd - int((old == 2).sum()):+,} px")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
