"""Rasterize instance-model detections into UNet-style raster layers.

For each instance iteration that has an instances.gpkg, write onto the 9t
reference grid:
  *_mask.tif     uint8  0/1   any-instance vs background (semantic-argmax analog)
  *_instid.tif   int32  0=bg  per-pixel detection ID (preserves separation)

No re-inference: reads the existing polygons. Higher-score detections are burned
last so they win on overlap (mask stays 0/1; instid takes the top-score object).
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DERIV_9T, make_profile  # noqa: E402
import _instance_common as ic  # noqa: E402

JOBS = [
    ("pit_07_maskrcnn", "pits", "pit"),
    ("pit_08_yolo", "pits", "pit"),
    ("pad_05_maskrcnn", "pads", "pad"),
    ("pad_06_yolo", "pads", "pad"),
]


def main() -> int:
    prof = ic.reference_profile()
    H, W, tf, crs = prof["height"], prof["width"], prof["transform"], prof["crs"]
    for iter_name, layer, tag in JOBS:
        gpkg = DERIV_9T / "iterations" / iter_name / "instances.gpkg"
        if not gpkg.exists():
            print(f"{iter_name}: no instances.gpkg, skip"); continue
        g = gpd.read_file(gpkg, layer=layer)
        if "score" in g.columns:
            g = g.sort_values("score")  # ascending -> high scores burned last
        outdir = gpkg.parent

        # Binary mask (semantic-argmax analog).
        mask = rasterize([(geom, 1) for geom in g.geometry],
                         out_shape=(H, W), transform=tf, fill=0, dtype="uint8")
        mp = make_profile(width=W, height=H, transform=tf, crs=crs,
                          dtype="uint8", nodata=255, bigtiff=True)
        with rasterio.open(outdir / f"{tag}_mask.tif", "w", **mp) as dst:
            dst.write(mask, 1)

        # Instance-ID label raster (1..N by ascending score; top score wins overlap).
        shapes = [(geom, i + 1) for i, geom in enumerate(g.geometry)]
        instid = rasterize(shapes, out_shape=(H, W), transform=tf, fill=0,
                           dtype="int32")
        ip = make_profile(width=W, height=H, transform=tf, crs=crs,
                          dtype="int32", nodata=0, bigtiff=True)
        with rasterio.open(outdir / f"{tag}_instid.tif", "w", **ip) as dst:
            dst.write(instid, 1)

        print(f"{iter_name}: wrote {tag}_mask.tif ({int((mask==1).sum()):,} px) "
              f"+ {tag}_instid.tif ({len(g)} instances)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
