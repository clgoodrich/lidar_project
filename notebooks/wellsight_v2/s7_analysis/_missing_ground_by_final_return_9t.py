"""Split the missing-ground mask by whether a pulse actually got down there.

WHY THE PLAIN MASK CROSS-HATCHES
--------------------------------
`missing_ground_9t_0p5m.tif` marks every 0.5 m cell with no vendor ground
return. At 45.2% of the tile it is mostly canopy, and it carries a woven
cross-hatch because ground returns are sparse: between scan lines there is
often no ground return even where the ground is perfectly visible. So the plain
mask mixes two completely different situations and draws the scan pattern on
top of both.

This separates them by asking what the laser actually did in each cell.

THREE LAYERS
------------
    missing_any_final    no vendor ground, and no final return of any pulse
                         landed in the cell at all. Nothing terminated here.

    missing_with_final   no vendor ground, but some pulse DID terminate here.
                         The final return may be up in the canopy, so this is
                         "a pulse ended in this column", not "the laser reached
                         the dirt".

    missing_at_ground    no vendor ground, and a final return terminated within
                         +/-15 cm of the bare-earth surface. **This is the one
                         that matters**: the laser reached the ground, the
                         return is the last of its pulse, and it still was not
                         labelled ground.

The +/-15 cm band is the same one the earlier class-1 audit used to find the
5.6 M withheld at-ground points, so the numbers are comparable.

A final return is `return_number == number_of_returns` -- the last echo of its
pulse, which is the one that reached the lowest surface that pulse could see.

TILE SELECTION
--------------
Nine tiles, not sixteen. A first version tested overlap with `>` and `<`, which
counts a tile touching the bounding box along one edge as overlapping; seven
tiles do exactly that and contribute no points. The test now requires strictly
positive overlap on both axes.

Run:
    python notebooks/wellsight_v2/s7_analysis/_missing_ground_by_final_return_9t.py
Writes, into data/9t/results/recovered_ground_9t/:
    final_return_count_9t_0p5m.tif
    missing_with_final_9t_0p5m.tif
    missing_at_ground_9t_0p5m.tif
    missing_no_final_9t_0p5m.tif
"""
from __future__ import annotations

from pathlib import Path

import laspy
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[3]
REC = ROOT / "data/9t/results/recovered_ground_9t"
CNT_V = REC / "count_vendorground_9t_0p5m.tif"
DEM = REC / "dem_vendorground_9t_0p5m.tif"
SRC_DIRS = ("data/_source/lidar/westernpa",
            "data/_source/lidar/westernpa/OTHER_DATA")

BB = (619500.0, 4593000.0, 624000.0, 4597500.0)
CELL = 0.5
NEAR_GROUND_M = 0.15
CRS = "EPSG:6346"


def tiles():
    out, seen = [], set()
    for d in SRC_DIRS:
        for f in sorted((ROOT / d).glob("*.laz")):
            if ".copc." in f.name or f.name in seen:
                continue
            with laspy.open(f) as rd:
                lo, hi = rd.header.mins, rd.header.maxs
            # strictly positive overlap on BOTH axes, or the tile only touches
            # the edge and contributes nothing
            if (min(hi[0], BB[2]) - max(lo[0], BB[0]) <= 0 or
                    min(hi[1], BB[3]) - max(lo[1], BB[1]) <= 0):
                continue
            seen.add(f.name)
            out.append(f)
    return out


def write(path, arr, transform, dtype, nodata):
    prof = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                count=1, dtype=dtype, crs=CRS, transform=transform,
                nodata=nodata, compress="deflate", zlevel=9, tiled=True,
                blockxsize=512, blockysize=512)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(arr.astype(dtype), 1)
    return path.stat().st_size / 1e6


def main() -> int:
    for p in (CNT_V, DEM):
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    with rasterio.open(CNT_V) as s:
        transform = s.transform
        H, W = s.height, s.width
        vendor = s.read(1, masked=True).filled(0)
    with rasterio.open(DEM) as s:
        dem = s.read(1).astype("float32")
        if s.nodata is not None:
            dem[dem == s.nodata] = np.nan

    n_final = np.zeros((H, W), dtype="int32")
    n_atgnd = np.zeros((H, W), dtype="int32")

    tl = tiles()
    print(f"  {len(tl)} tiles genuinely overlap 9t")
    total = 0
    for i, f in enumerate(tl, 1):
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x >= BB[0]) & (x < BB[2]) & (y >= BB[1]) & (y < BB[3])
        if not m.any():
            continue
        rn = np.asarray(las.return_number)[m]
        nr = np.asarray(las.number_of_returns)[m]
        fin = rn == nr
        if not fin.any():
            continue
        xs, ys = x[m][fin], y[m][fin]
        zs = np.asarray(las.z)[m][fin]

        col = np.clip(((xs - BB[0]) / CELL).astype(np.int64), 0, W - 1)
        row = np.clip(((BB[3] - ys) / CELL).astype(np.int64), 0, H - 1)
        flat = row * W + col
        n_final += np.bincount(flat, minlength=H * W).reshape(H, W).astype("int32")

        g = dem[row, col]
        near = np.isfinite(g) & (np.abs(zs - g) <= NEAR_GROUND_M)
        if near.any():
            n_atgnd += np.bincount(flat[near],
                                   minlength=H * W).reshape(H, W).astype("int32")
        total += int(fin.sum())
        print(f"   [{i}/{len(tl)}] {f.name[-18:]}  final returns "
              f"{int(fin.sum()):9,d}", flush=True)

    void = vendor <= 0
    with_final = void & (n_final > 0)
    at_ground = void & (n_atgnd > 0)
    no_final = void & (n_final <= 0)

    cell_km2 = CELL * CELL / 1e6
    print(f"\n  {total:,} final returns rasterised\n")
    rows = [("no vendor ground (the plain mask)", void),
            ("  ...no final return landed at all", no_final),
            ("  ...a pulse terminated here", with_final),
            ("  ...terminated within 15 cm of the ground", at_ground)]
    for lbl, m in rows:
        print(f"  {lbl:45s} {int(m.sum()):12,d} cells  "
              f"{m.sum()*cell_km2:7.3f} km2  {m.mean()*100:5.1f}% of tile")

    print()
    for name, arr, dt, nd in (
            ("final_return_count", np.clip(n_final, 0, 255), "uint8", 0),
            ("missing_with_final", with_final, "uint8", 0),
            ("missing_at_ground", at_ground, "uint8", 0),
            ("missing_no_final", no_final, "uint8", 0)):
        p = REC / f"{name}_9t_0p5m.tif"
        mb = write(p, arr, transform, dt, nd)
        print(f"  {p.name:38s} {mb:6.1f} MB")
    print(f"\n  {REC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
