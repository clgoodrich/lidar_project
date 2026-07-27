"""Export thresholded views of the pit U-Net floor probability raster.

`pit_prob_floor_9t_05.tif` (on disk as `pit_prob_floor.tif`) is the RAW model
output -- continuous float32, 0.000 to 0.972, with no threshold baked in. Every
operating point already exists inside that one file, so producing a thresholded
view costs nothing and requires no retraining or re-inference.

This writes, per threshold, two views of the same cut:

  ..._mask_thr0pXX_...   uint8 1 where prob >= threshold, nodata 0. Binary, for
                         "what area does this threshold claim?" at a glance.
  ..._prob_thr0pXX_...   float32 probability kept only where >= threshold, NaN
                         elsewhere. Same footprint, but retains confidence so
                         strong and marginal detections stay distinguishable.

Thresholds 0.20 and 0.30 are the two that matter, and they optimise different
things (measured on 127 held-out pits, see _heldout_rim_containment_9t.py):
  0.20  best LOCATION       126/127 pits found (99.2%), 1041 polygons tile-wide
  0.30  best DELINEATION    122/127 at floor IoU>=0.3 (95.3%), 827 polygons
The previously used 0.60 finds only 109/127 (85.8%) -- it was an F1 optimum, and
F1 is the wrong objective when the goal is finding wells.

Run:
  python notebooks/wellsight_v2/eval/_export_pit_floor_threshold_tifs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[3]
SRC = (ROOT / "data" / "derivatives" / "tiles" / "9t" / "pit_unet_v2"
       / "pit_prob_floor.tif")
OUT_DIR = SRC.parent
THRESHOLDS = [0.20, 0.30]


def tag(t: float) -> str:
    return f"thr{t:.2f}".replace(".", "p")


def main() -> int:
    with rasterio.open(SRC) as r:
        prob = r.read(1).astype(np.float32)
        if r.nodata is not None:
            prob = np.where(prob == r.nodata, 0.0, prob)
        prof = r.profile.copy()
        px = abs(r.transform.a) * abs(r.transform.e)

    print(f"source {SRC}")
    print(f"  raw probability, no threshold baked in: "
          f"{prob.min():.3f}..{prob.max():.3f}, {prob.shape}\n")

    for t in THRESHOLDS:
        m = prob >= t
        ha = m.sum() * px / 1e4

        mask_p = OUT_DIR / f"pit_unet_floor_mask_{tag(t)}_9t_05.tif"
        p = prof.copy()
        p.update(dtype="uint8", nodata=0, count=1, compress="deflate",
                 tiled=True)
        with rasterio.open(mask_p, "w", **p) as d:
            d.write(m.astype(np.uint8), 1)
            d.write_colormap(1, {0: (0, 0, 0, 0), 1: (215, 25, 28, 255)})
            d.update_tags(1, THRESHOLD=str(t), SOURCE=SRC.name,
                          MEANING="1 = pit floor probability >= threshold")
        print(f"  wrote {mask_p}")
        print(f"    {m.sum():,} px = {ha:.2f} ha ({100 * m.mean():.3f}% of tile)")

        prob_p = OUT_DIR / f"pit_unet_floor_prob_{tag(t)}_9t_05.tif"
        p = prof.copy()
        p.update(dtype="float32", nodata=np.nan, count=1, compress="deflate",
                 predictor=2, tiled=True)
        with rasterio.open(prob_p, "w", **p) as d:
            d.write(np.where(m, prob, np.nan).astype(np.float32), 1)
            d.update_tags(1, THRESHOLD=str(t), SOURCE=SRC.name,
                          MEANING="pit floor probability where >= threshold")
        print(f"  wrote {prob_p}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
