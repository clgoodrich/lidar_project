"""Is 0.5 m simply finer than the delivery can support?

THE QUESTION
------------
The corn rows are cells with no return in them. An obvious possibility is that
they are not a scanner problem at all but a gridding one: if the cell is smaller
than the spacing between returns, empty cells are arithmetic, not a defect. This
measures the empty-cell rate against cell size so the choice can be made on
numbers instead of on the rule of thumb.

WHAT IT REPORTS, AND WHY THREE FLAVOURS
---------------------------------------
ALL RETURNS      what any raster gridded from the full cloud sees.
FIRST RETURNS    what the DSM sees, and so the CHM. This is the one the corn
                 rows live in.
GROUND CLASS     what the DEM sees. Sparser again, because most returns are not
                 ground, so the DEM is the layer most exposed to cell size.

OCCUPANCY IS NOT THE SAME AS A HOLE IN THE PRODUCT. The delivered DSM is a TIN
interpolated to the grid, so an empty cell gets a value from its neighbours and
never shows. The occupancy rate is the RAW exposure; the product's void rate is
what is left after interpolation gives up. Both are reported, because the gap
between them is the whole argument: at 0.5 m most cells are empty and almost
none of them are holes.

THE COST OF COARSENING IS REAL AND IS ALSO REPORTED
---------------------------------------------------
A median annotated pit floor is 29.1 m2, which is a circle about 6.1 m across.
At 0.5 m that is 12 cells wide; at 2 m it is 3. Halving the void rate is not
worth a target the model cannot resolve, so the table carries both columns and
the decision is a trade, not a fix.

Run:
    python notebooks/wellsight_v2/s7_analysis/_void_rate_vs_cell_size_9t.py
Writes:
    data/9t/results/nonground_classification/void_rate_vs_cell_size_9t.json
"""
from __future__ import annotations

import json
from pathlib import Path

import laspy
import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
OUT = (ROOT / "data/9t/results/nonground_classification"
       / "void_rate_vs_cell_size_9t.json")

#: Cell sizes to test, metres.
CELLS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
#: Median annotated pit floor area, from _annotation_inventory_stats.py.
PIT_FLOOR_M2 = 29.1


def laz_files():
    seen, out = set(), []
    for d in ("data/_source/lidar/westernpa",
              "data/_source/lidar/westernpa/OTHER_DATA"):
        for f in sorted((ROOT / d).glob("*.laz")):
            if ".copc." in f.name or f.name in seen:
                continue
            seen.add(f.name)
            out.append(f)
    return out


def main() -> int:
    with rasterio.open(D05 / "dem_9t_05.tif") as r:
        B = tuple(r.bounds)
    print(f"extent {B[0]:.0f} {B[1]:.0f} {B[2]:.0f} {B[3]:.0f}")

    # One boolean occupancy grid per cell size per flavour. Boolean and not a
    # count: 4.5 km at 0.5 m is 81 million cells, and a count array would be
    # 650 MB where the flag is 81.
    grids = {}
    for c in CELLS:
        nx = int(np.ceil((B[2] - B[0]) / c))
        ny = int(np.ceil((B[3] - B[1]) / c))
        grids[c] = dict(nx=nx, ny=ny,
                        all=np.zeros(ny * nx, bool),
                        first=np.zeros(ny * nx, bool),
                        ground=np.zeros(ny * nx, bool))
        print(f"  {c:.2f} m grid {nx} x {ny} = {nx*ny/1e6:.1f} M cells")

    n_pts = 0
    for f in laz_files():
        with laspy.open(f) as rd:
            lo, hi = rd.header.mins, rd.header.maxs
        if lo[0] > B[2] or hi[0] < B[0] or lo[1] > B[3] or hi[1] < B[1]:
            continue
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x >= B[0]) & (x < B[2]) & (y >= B[1]) & (y < B[3])
        if not m.any():
            continue
        x, y = x[m], y[m]
        rn = np.asarray(las.return_number)[m]
        cl = np.asarray(las.classification)[m]
        n_pts += int(m.sum())
        for c in CELLS:
            gd = grids[c]
            col = np.clip(((x - B[0]) / c).astype(np.int64), 0, gd["nx"] - 1)
            row = np.clip(((B[3] - y) / c).astype(np.int64), 0, gd["ny"] - 1)
            i = row * gd["nx"] + col
            gd["all"][i] = True
            gd["first"][i[rn == 1]] = True
            gd["ground"][i[cl == 2]] = True
        print(f"    {f.name}: {int(m.sum()):,}")
    print(f"  {n_pts:,} returns")

    # What the delivered products actually leave empty, for comparison
    prod = {}
    for name, fn in (("dsm", "dsm_9t_05.tif"), ("dem", "dem_9t_05.tif"),
                     ("chm", "chm_9t_05.tif")):
        with rasterio.open(D05 / fn) as r:
            a = r.read(1, window=from_bounds(*B, transform=r.transform),
                       boundless=True, fill_value=np.nan).astype("float32")
        a[a < -1000.0] = np.nan
        prod[name] = float(100 * np.mean(~np.isfinite(a)))
    print(f"\ndelivered products at 0.5 m, share of cells with no value:")
    for k, v in prod.items():
        print(f"  {k.upper()}  {v:.2f}%")

    dia = (4.0 * PIT_FLOOR_M2 / np.pi) ** 0.5
    rows = []
    print(f"\nEMPTY-CELL RATE BY CELL SIZE  "
          f"(a median pit floor is {dia:.1f} m across)")
    print("  cell     all returns   first returns   ground class   "
          "pit floor")
    for c in CELLS:
        gd = grids[c]
        r_ = dict(cell_m=c,
                  empty_all=float(100 * np.mean(~gd["all"])),
                  empty_first=float(100 * np.mean(~gd["first"])),
                  empty_ground=float(100 * np.mean(~gd["ground"])),
                  pit_floor_cells=float(dia / c))
        rows.append(r_)
        print(f"  {c:.2f} m   {r_['empty_all']:8.2f}%   "
              f"{r_['empty_first']:10.2f}%   {r_['empty_ground']:9.2f}%   "
              f"{r_['pit_floor_cells']:5.1f} cells")

    res = dict(extent=list(B), n_returns=n_pts,
               pit_floor_m2=PIT_FLOOR_M2, pit_floor_diameter_m=float(dia),
               delivered_void_pct_at_0p5m=prod, by_cell_size=rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")

    half = next(r for r in rows if r["cell_m"] == 0.5)
    print(f"\n  At 0.5 m, {half['empty_first']:.0f}% of cells hold no first "
          f"return, yet the delivered DSM is only {prod['dsm']:.2f}% empty.")
    print("  The interpolation closes almost all of it. The corn rows are the "
          "remainder --")
    print("  the runs too wide for a neighbour to reach across.")
    print(f"\n  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
