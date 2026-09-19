"""Test 1: is the 18-degree ground cut just standard swath-overlap handling?

THE SKEPTICAL CASE THIS EXISTS TO ANSWER
----------------------------------------
3DEP vendors routinely flag points in the overlap between adjacent flight lines
as overage and build the DTM from the core of each swath only. The symptom of
that is exactly what we reported: ground classification stopping at a fixed
scan angle, with gaps in stripes along the swath edges.

If the discarded returns are overage, then the ground in those stripes IS
measured -- by the neighbouring flight line, at a lower scan angle -- and our
headline claim ("13.8% of the area has no ground measurement under it") is
measuring the wrong thing. Our void test asked whether a cell holds any return
and no ground return. It never asked WHICH FLIGHT LINE the returns came from.

WHAT IS CHECKED, IN ORDER OF HOW BADLY IT WOULD HURT
----------------------------------------------------
1. Are the discarded points flagged? Withheld and Overlap bits (LAS 1.4 point
   formats 6+), and ASPRS class 12 "overlap points" for older formats.
2. Do the void cells have a SECOND flight line over them at all? This is the
   one that settles it. A cell covered by one line only cannot be rescued by a
   neighbour, no matter how the points are flagged.
3. Where a void cell does have a second line, did that line deliver ground?
   If yes, the void is our bookkeeping error. If no, the void is real.

Void cells are counted the way `_recovered_ground_maps_9t.py` counts them: a
1 m cell holding at least one return and no vendor ground return. 1 m, not
0.5 m, because at 0.5 m a cell holds about one ground point and half of them
come up empty by chance.

Run:
    python notebooks/wellsight_v2/s7_analysis/_test_overage_hypothesis.py
    python notebooks/wellsight_v2/s7_analysis/_test_overage_hypothesis.py \
        --tiles 621594 616591 --res 1.0
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import laspy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
OUT = ROOT / "data/9t/results/nonground_classification"
CUT = 18.0


def find(code):
    hits = sorted(SRC.rglob(f"*{code}*.laz")) + sorted(SRC.rglob(f"*{code}*.las"))
    hits = [h for h in hits if not h.name.startswith("_merged")]
    if not hits:
        raise SystemExit(f"no source tile for {code}")
    return hits[0]


def flags(las, n):
    """Withheld / overlap / synthetic, whichever the point format carries."""
    out = {}
    for name in ("withheld", "overlap", "synthetic", "key_point"):
        try:
            v = np.asarray(getattr(las, name))
            if v.shape == (n,):
                out[name] = v.astype(bool)
        except (AttributeError, ValueError):
            pass
    return out


def run(code, res):
    p = find(code)
    las = laspy.read(p)
    n = len(las.points)
    fmt = las.header.point_format.id
    x = np.asarray(las.x)
    y = np.asarray(las.y)
    cls = np.asarray(las.classification).astype(np.int16)
    psid = np.asarray(las.point_source_id).astype(np.int32)
    ang = np.asarray(las.scan_angle if hasattr(las, "scan_angle")
                     else las.scan_angle_rank).astype(np.float32)
    # LAS 1.4 formats 6+ store scan angle in 0.006 degree increments
    if fmt >= 6:
        ang = ang * 0.006
    fl = flags(las, n)

    print(f"\n=== {code}   {p.name}")
    print(f"  LAS point format {fmt}, {n:,} points, "
          f"{len(np.unique(psid))} flight lines")
    print(f"  scan angle range {ang.min():.1f} to {ang.max():.1f} deg")
    print(f"  classes present: "
          f"{ {int(k): int(v) for k, v in zip(*np.unique(cls, return_counts=True))} }")

    wide = np.abs(ang) > CUT
    ground = cls == 2
    # what we called "recoverable": not ground, beyond the cut, not noise
    disc = wide & ~ground & (cls != 7)
    print(f"\n  -- 1. are the discarded points FLAGGED? "
          f"({disc.sum():,} points beyond {CUT:.0f} deg, not ground, not noise)")
    if not fl:
        print("     point format carries no classification flag bits")
    for name, v in fl.items():
        print(f"     {name:10s} set on {v[disc].sum():,} of {disc.sum():,} "
              f"({100 * v[disc].mean():.2f}%)   "
              f"whole tile {100 * v.mean():.2f}%")
    n12 = int((cls == 12).sum())
    print(f"     ASPRS class 12 (overlap points): {n12:,} in the tile")

    # ---- 2 and 3: per-cell flight-line coverage --------------------------
    x0, y0 = np.floor(x.min()), np.floor(y.min())
    ix = ((x - x0) // res).astype(np.int64)
    iy = ((y - y0) // res).astype(np.int64)
    w = int(ix.max()) + 1
    cell = iy * w + ix
    ncell = int(cell.max()) + 1

    any_ret = np.zeros(ncell, bool)
    has_gnd = np.zeros(ncell, bool)
    np.logical_or.at(any_ret, cell, True)
    np.logical_or.at(has_gnd, cell[ground], True)
    void = any_ret & ~has_gnd
    print(f"\n  -- void cells at {res:g} m: {void.sum():,} of "
          f"{any_ret.sum():,} occupied ({100 * void.mean() * ncell / max(any_ret.sum(), 1):.2f}%)")

    # how many DISTINCT flight lines touch each cell
    order = np.lexsort((psid, cell))
    c_s, p_s = cell[order], psid[order]
    newcell = np.r_[True, c_s[1:] != c_s[:-1]]
    newpair = newcell | (p_s[1:] != p_s[:-1]).astype(bool).tolist() \
        if False else np.r_[True, (c_s[1:] != c_s[:-1]) | (p_s[1:] != p_s[:-1])]
    nlines = np.zeros(ncell, np.int32)
    np.add.at(nlines, c_s[newpair], 1)

    # and how many lines delivered GROUND into each cell
    g_ord = order[ground[order]]
    cg, pg = cell[g_ord], psid[g_ord]
    ng_lines = np.zeros(ncell, np.int32)
    if cg.size:
        newg = np.r_[True, (cg[1:] != cg[:-1]) | (pg[1:] != pg[:-1])]
        np.add.at(ng_lines, cg[newg], 1)

    vl = nlines[void]
    print(f"\n  -- 2. do VOID cells have a second flight line over them?")
    for k in (1, 2, 3):
        m = (vl == k) if k < 3 else (vl >= 3)
        lbl = f"{k} line" if k < 3 else "3+ lines"
        print(f"     {lbl:10s} {m.sum():>9,}  ({100 * m.mean():5.1f}% of void cells)")
    multi = vl >= 2
    print(f"     -> {100 * multi.mean():.1f}% of void cells are covered by "
          f"more than one line")

    print(f"\n  -- 3. of the void cells WITH a second line, did any line "
          f"deliver ground?")
    print(f"     by construction none did: a void cell has no ground return "
          f"from any line.")
    # the real question: is the neighbouring line's coverage there but shallow?
    vm = np.where(void)[0]
    if vm.size:
        share_wide = np.zeros(ncell, np.float32)
        cnt = np.zeros(ncell, np.int64)
        np.add.at(cnt, cell, 1)
        wcnt = np.zeros(ncell, np.int64)
        np.add.at(wcnt, cell[wide], 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            share_wide = np.where(cnt > 0, wcnt / np.maximum(cnt, 1), np.nan)
        print(f"     void cells whose returns are ALL beyond {CUT:.0f} deg: "
              f"{np.nansum(share_wide[vm] > 0.999):,.0f} "
              f"({100 * np.nanmean(share_wide[vm] > 0.999):.1f}%)")
        print(f"     void cells with SOME near-nadir returns and still no "
              f"ground: {np.nansum(share_wide[vm] < 0.5):,.0f} "
              f"({100 * np.nanmean(share_wide[vm] < 0.5):.1f}%)")

    return dict(tile=code, fmt=fmt, points=int(n), lines=int(len(np.unique(psid))),
                discarded=int(disc.sum()),
                withheld_on_discarded=float(fl["withheld"][disc].mean()) if "withheld" in fl else None,
                overlap_on_discarded=float(fl["overlap"][disc].mean()) if "overlap" in fl else None,
                class12=n12, void_cells=int(void.sum()),
                void_multiline_pct=float(100 * multi.mean()) if vl.size else None,
                res=res)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", nargs="+", default=["621594", "616591"])
    ap.add_argument("--res", type=float, default=1.0)
    a = ap.parse_args()
    rows = [run(t, a.res) for t in a.tiles]
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "overage_hypothesis_test.json"
    p.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
