"""Does putting the deleted returns back actually change anything downstream?

THE QUESTION
------------
The data-QA section shows that 13.7 M ground returns were deleted, that they
measure as well as the ones kept, and that putting them back closes about a
quarter of the holes. It then shows that the DEM barely moves: where the vendor
already had ground the median change is 0.000 m.

That is the DEM. **The model does not read the DEM.** It reads slope, local
relief and openness -- layers built from the GRADIENT of the surface, where a
small height change over a short distance becomes a large change in value. So
"the DEM barely moves" does not settle the question, and this measures the
layers that matter instead.

WHAT IT COMPARES
----------------
Two surfaces that differ only in which returns went into them:

    dem_vendorground_9t_0p5m.tif                 vendor's ground only
    dem_vendorplusrecovered_slope0p35_9t_0p5m.tif  plus the recovered returns

From each, three derived layers computed identically, so any difference is the
input and not the recipe:

    slope        degrees, from the gradient
    local relief elevation minus a 5-cell mean, in centimetres
    openness     a cheap proxy -- elevation minus a 25-cell mean, in
                 centimetres. Not the real Yokoyama openness, which needs a
                 radial search; it stands in here as a second, longer-baseline
                 shape measure, and it is computed the same way on both
                 surfaces so the COMPARISON is still fair.

SPLIT BY WHAT ACTUALLY HAPPENED TO EACH CELL
--------------------------------------------
Reporting one number over the whole tile would bury the answer, because 94% of
cells never changed at all. Every statistic is split:

    already had ground   the vendor measured it; nothing should move here, and
                         if it does we are overwriting a professional survey
    void, now filled     no ground before, a measurement now. This is where
                         change is expected and wanted.
    void, still empty    no ground before, none now. Interpolated either way.

Run in blocks because the rasters are 9000x9000 and there are two of them.

Run:
    python notebooks/wellsight_v2/s7_analysis/_does_recovered_ground_change_the_layers_9t.py
Writes:
    data/9t/results/recovered_ground_9t/layer_change_from_recovered_9t.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[3]
REC = ROOT / "data/9t/results/recovered_ground_9t"
OLD = REC / "dem_vendorground_9t_0p5m.tif"
NEW = REC / "dem_vendorplusrecovered_slope0p35_9t_0p5m.tif"
CNT_V = REC / "count_vendorground_9t_0p5m.tif"
CNT_R = REC / "count_recoveredground_slope0p35_9t_0p5m.tif"
OUT = REC / "layer_change_from_recovered_9t.json"

CELL = 0.5
BLOCK = 1500
HALO = 32                     # wide enough for the 25-cell mean plus gradient


def derive(z):
    """slope (deg), local relief (cm), long-baseline relief (cm)."""
    gy, gx = np.gradient(z, CELL, CELL)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    lrm = (z - ndimage.uniform_filter(z, 5, mode="nearest")) * 100.0
    opn = (z - ndimage.uniform_filter(z, 25, mode="nearest")) * 100.0
    return slope, lrm, opn


def main() -> int:
    for p in (OLD, NEW, CNT_V, CNT_R):
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    acc = {k: {n: [] for n in ("dem_cm", "slope_deg", "lrm_cm", "opn_cm")}
           for k in ("had_ground", "filled", "still_void")}
    counts = {k: 0 for k in acc}

    with rasterio.open(OLD) as so, rasterio.open(NEW) as sn, \
            rasterio.open(CNT_V) as sv, rasterio.open(CNT_R) as sr:
        H, W = so.height, so.width
        for r0 in range(0, H, BLOCK):
            for c0 in range(0, W, BLOCK):
                r1, c1 = min(r0 + BLOCK, H), min(c0 + BLOCK, W)
                rr0, cc0 = max(0, r0 - HALO), max(0, c0 - HALO)
                rr1, cc1 = min(H, r1 + HALO), min(W, c1 + HALO)
                win = ((rr0, rr1), (cc0, cc1))

                zo = so.read(1, window=win).astype("float64")
                zn = sn.read(1, window=win).astype("float64")
                if so.nodata is not None:
                    zo[zo == so.nodata] = np.nan
                    zn[zn == sn.nodata] = np.nan
                if not np.isfinite(zo).any():
                    continue
                zo = np.nan_to_num(zo, nan=float(np.nanmean(zo)))
                zn = np.nan_to_num(zn, nan=float(np.nanmean(zn)))

                so_, lo_, oo_ = derive(zo)
                sn_, ln_, on_ = derive(zn)

                # back to the block interior, where the halo is valid
                a, b = r0 - rr0, (r0 - rr0) + (r1 - r0)
                c, d = c0 - cc0, (c0 - cc0) + (c1 - c0)
                cut = (slice(a, b), slice(c, d))

                v = sv.read(1, window=((r0, r1), (c0, c1)), masked=True).filled(0)
                g = sr.read(1, window=((r0, r1), (c0, c1)), masked=True).filled(0)
                masks = {"had_ground": v > 0,
                         "filled": (v <= 0) & (g > 0),
                         "still_void": (v <= 0) & (g <= 0)}

                d_dem = np.abs(zn - zo)[cut] * 100.0
                d_sl = np.abs(sn_ - so_)[cut]
                d_lrm = np.abs(ln_ - lo_)[cut]
                d_opn = np.abs(on_ - oo_)[cut]

                for k, m in masks.items():
                    if not m.any():
                        continue
                    counts[k] += int(m.sum())
                    # subsample: percentiles do not need every cell, and
                    # keeping them all would be tens of GB
                    idx = np.flatnonzero(m.ravel())
                    if idx.size > 20000:
                        idx = np.random.default_rng(0).choice(idx, 20000,
                                                              replace=False)
                    acc[k]["dem_cm"].append(d_dem.ravel()[idx])
                    acc[k]["slope_deg"].append(d_sl.ravel()[idx])
                    acc[k]["lrm_cm"].append(d_lrm.ravel()[idx])
                    acc[k]["opn_cm"].append(d_opn.ravel()[idx])
            print(f"  rows {r0}-{r1} done", flush=True)

    total = sum(counts.values())
    res = {"cells_total": total,
           "cells": {k: dict(n=counts[k], pct=round(counts[k] / total * 100, 2))
                     for k in counts},
           "abs_change": {}}
    print()
    for k in ("had_ground", "filled", "still_void"):
        res["abs_change"][k] = {}
        print(f"  {k}  ({counts[k]:,} cells, "
              f"{counts[k]/total*100:.1f}% of tile)")
        for n in ("dem_cm", "slope_deg", "lrm_cm", "opn_cm"):
            if not acc[k][n]:
                continue
            v = np.concatenate(acc[k][n])
            q = {"median": float(np.median(v)),
                 "p90": float(np.percentile(v, 90)),
                 "p99": float(np.percentile(v, 99))}
            res["abs_change"][k][n] = {kk: round(vv, 4) for kk, vv in q.items()}
            unit = "deg" if n == "slope_deg" else "cm"
            print(f"     {n:10s} median {q['median']:7.3f}  "
                  f"p90 {q['p90']:7.3f}  p99 {q['p99']:8.3f}  {unit}")
        print()

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
