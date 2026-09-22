"""The returns the vendor clipped: past 18 degrees, final echo, not called ground.

THE DEFINITION, EXACTLY
-----------------------
Four conditions, all read from the delivered LAZ itself -- nothing
reconstructed, nothing inferred:

    1  it is in the vendor's own delivery
    2  |scan angle| >= 18 degrees          past the threshold
    3  return_number == number_of_returns  the final echo of its pulse
    4  classification != 2                 not called ground

Condition 3 is what makes this meaningful rather than merely wide-angle. A
final echo is the last thing that pulse saw, so it reached the lowest surface
available to it. Condition 4 is the vendor's decision. Together they are the
population the 18 degree rule excluded from the ground surface.

Scan angle in LAS point format 6 is a signed short in units of 0.006 degrees,
so the threshold is 3000 raw. Reading it as though it were degrees -- which the
older ScanAngleRank field would have been -- understates the cut by a factor of
167 and selects essentially everything.

WHAT COMES OUT
--------------
    clipped_final_count_9t_0p5m.tif       how many such returns fall in each
                                          0.5 m cell. This is the overlay: the
                                          swath-edge stripes are the shape of
                                          the cut.
    clipped_final_nearground_count_...    the subset landing within 15 cm of
                                          the bare-earth surface, i.e. the ones
                                          that demonstrably reached the dirt
                                          and were still denied ground status.

Class 2 past 18 degrees is counted and reported too. It should be near zero --
that is the cut restated -- and if it is not, the threshold story is wrong and
worth finding out before anyone presents it.

TILE SELECTION
--------------
Nine tiles, not sixteen: a header test using > and < counts a tile that merely
touches the bounding-box edge, and seven do exactly that while contributing no
points. Strictly positive overlap on both axes is required.

Run:
    python notebooks/wellsight_v2/s7_analysis/_clipped_final_returns_9t.py
"""
from __future__ import annotations

from pathlib import Path

import laspy
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[3]
REC = ROOT / "data/9t/results/recovered_ground_9t"
DEM = REC / "dem_vendorground_9t_0p5m.tif"
SRC_DIRS = ("data/_source/lidar/westernpa",
            "data/_source/lidar/westernpa/OTHER_DATA")

BB = (619500.0, 4593000.0, 624000.0, 4597500.0)
CELL = 0.5
CRS = "EPSG:6346"
#: LAS point format 6 stores scan angle in 0.006 degree units
SCAN_UNIT_DEG = 0.006
CUT_DEG = 18.0
NEAR_GROUND_M = 0.15


def tiles():
    out, seen = [], set()
    for d in SRC_DIRS:
        for f in sorted((ROOT / d).glob("*.laz")):
            if ".copc." in f.name or f.name in seen:
                continue
            with laspy.open(f) as rd:
                lo, hi = rd.header.mins, rd.header.maxs
            if (min(hi[0], BB[2]) - max(lo[0], BB[0]) <= 0 or
                    min(hi[1], BB[3]) - max(lo[1], BB[1]) <= 0):
                continue
            seen.add(f.name)
            out.append(f)
    return out


def write(path, arr, transform):
    prof = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                count=1, dtype="uint8", crs=CRS, transform=transform,
                nodata=0, compress="deflate", zlevel=9, tiled=True,
                blockxsize=512, blockysize=512)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(np.clip(arr, 0, 255).astype("uint8"), 1)
    return path.stat().st_size / 1e6


def main() -> int:
    if not DEM.exists():
        raise SystemExit(f"missing: {DEM}")
    with rasterio.open(DEM) as s:
        transform, H, W = s.transform, s.height, s.width
        dem = s.read(1).astype("float32")
        if s.nodata is not None:
            dem[dem == s.nodata] = np.nan

    n_clip = np.zeros((H, W), dtype="int32")
    n_near = np.zeros((H, W), dtype="int32")
    tot = dict(inbox=0, past=0, past_final=0, clipped=0,
               class2_past=0, near=0)

    tl = tiles()
    print(f"  {len(tl)} tiles overlap 9t; cut at {CUT_DEG}° "
          f"(raw {CUT_DEG / SCAN_UNIT_DEG:.0f})")
    for i, f in enumerate(tl, 1):
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x >= BB[0]) & (x < BB[2]) & (y >= BB[1]) & (y < BB[3])
        if not m.any():
            continue
        sa = np.abs(np.asarray(las.scan_angle)[m]) * SCAN_UNIT_DEG
        rn = np.asarray(las.return_number)[m]
        nr = np.asarray(las.number_of_returns)[m]
        cls = np.asarray(las.classification)[m]
        z = np.asarray(las.z)[m]
        xs, ys = x[m], y[m]

        past = sa >= CUT_DEG
        final = rn == nr
        keep = past & final & (cls != 2)

        tot["inbox"] += int(m.sum())
        tot["past"] += int(past.sum())
        tot["past_final"] += int((past & final).sum())
        tot["class2_past"] += int((past & (cls == 2)).sum())
        tot["clipped"] += int(keep.sum())

        if keep.any():
            col = np.clip(((xs[keep] - BB[0]) / CELL).astype(np.int64), 0, W - 1)
            row = np.clip(((BB[3] - ys[keep]) / CELL).astype(np.int64), 0, H - 1)
            flat = row * W + col
            n_clip += np.bincount(flat,
                                  minlength=H * W).reshape(H, W).astype("int32")
            g = dem[row, col]
            near = np.isfinite(g) & (np.abs(z[keep] - g) <= NEAR_GROUND_M)
            tot["near"] += int(near.sum())
            if near.any():
                n_near += np.bincount(flat[near],
                                      minlength=H * W).reshape(H, W).astype("int32")
        print(f"   [{i}/{len(tl)}] {f.name[-18:]}  clipped {int(keep.sum()):9,d}",
              flush=True)

    print(f"\n  returns inside 9t                      {tot['inbox']:12,d}")
    print(f"  past {CUT_DEG:.0f}°                              "
          f"{tot['past']:12,d}  ({tot['past']/max(tot['inbox'],1)*100:.1f}%)")
    print(f"    ...and a final return               {tot['past_final']:12,d}")
    print(f"    ...and not class 2  = CLIPPED       {tot['clipped']:12,d}")
    print(f"    ...of those, within 15 cm of ground {tot['near']:12,d}  "
          f"({tot['near']/max(tot['clipped'],1)*100:.1f}%)")
    print(f"\n  class 2 past {CUT_DEG:.0f}° (should be ~0)       "
          f"{tot['class2_past']:12,d}")

    cell_km2 = CELL * CELL / 1e6
    print(f"\n  cells touched by a clipped return      "
          f"{int((n_clip > 0).sum()):12,d}  "
          f"{(n_clip > 0).sum()*cell_km2:.3f} km2  "
          f"{(n_clip > 0).mean()*100:.1f}% of tile")
    print(f"  cells with a near-ground one           "
          f"{int((n_near > 0).sum()):12,d}  "
          f"{(n_near > 0).sum()*cell_km2:.3f} km2  "
          f"{(n_near > 0).mean()*100:.1f}% of tile")

    print()
    for name, arr in (("clipped_final_count", n_clip),
                      ("clipped_final_nearground_count", n_near)):
        p = REC / f"{name}_9t_0p5m.tif"
        print(f"  {p.name:42s} {write(p, arr, transform):6.1f} MB")
    print(f"\n  {REC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
