"""The 33% of unassigned points sitting at ground level -- are they ground?

THE QUESTION
------------
Reclassifying class 1 by height band leaves one bucket undecided: the points
within +/- 15 cm of the ground surface. Across four tiles that is 5,615,796
points, 32.9% of all class 1, and 4.2 M of them are single returns. A single
return at ground level, off a terminal pulse, is what ground looks like.

So why is the vendor not calling them ground, and would it matter if we did?

WHAT ACTUALLY DECIDES IT
------------------------
Not whether the points look like ground -- they do. What decides it is WHERE
they sit relative to the class-2 points we already have.

  If they land in cells that already hold class-2 returns, they are redundant.
  The DEM cell already has an observed elevation. Adding a second observation
  20 cm away changes nothing you can measure.

  If they land in cells with NO class-2 return, that cell's elevation is
  currently INTERPOLATED across from its neighbours. There, a withheld
  ground-level point is the difference between a measured surface and a
  guessed one.

So the whole question reduces to one number: how much of the DEM is currently
interpolated, and how much of that could be replaced by a real observation that
is sitting right there in class 1.

  PART A  What are they? Return structure, overlap flag, scan angle, intensity,
          flightline -- measured against class 2 in the same tiles, to see
          which property the classifier was actually keying on.
  PART B  Where are they? A 0.5 m grid -- the DEM's own resolution -- crossed
          against how many class-2 points each cell already holds.
  PART C  What would change? Void cells filled, and the elevation difference
          where a guessed cell becomes a measured one.

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md). One pass per tile, full density.

Run:
    python notebooks/wellsight_v2/s7_analysis/_audit_nearground_unassigned_9t.py
    ... --tiles 621594 616591 --profile
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "_source" / "lidar" / "westernpa"
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
OUT = ROOT / "data" / "9t" / "results" / "nonground_classification"
PDAL = "pdal"

NEAR = 0.15         # +/- this many metres of the ground surface
RES = 0.5           # the DEM's own cell size -- the only grid that matters here


def run_pipeline(stages, label, timeout=3600):
    """Write the pipeline to a temp file and shell out. See CLAUDE.md."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-1500:])
        print(r.stderr[-1500:])
        raise SystemExit(f"{label} failed, exit {r.returncode}")
    return r


def find_tile(code):
    hits = sorted(SRC.glob(f"*_17T??{code}.laz")) + \
        sorted(SRC.glob(f"*_17T??{code}.copc.laz"))
    if not hits:
        raise SystemExit(f"no source file for tile {code} in {SRC}")
    return hits[0]


def load_tile(laz):
    tmp = Path(tempfile.gettempdir()) / f"_nga_{laz.stem}.las"
    t0 = time.time()
    run_pipeline([
        str(laz),
        {"type": "filters.hag_nn", "count": 8, "allow_extrapolation": True},
        {"type": "writers.las", "filename": str(tmp),
         "extra_dims": "HeightAboveGround=float32", "compression": "false"},
    ], "hag")
    print(f"    hag_nn {time.time() - t0:.0f}s")
    import laspy
    las = laspy.read(str(tmp))
    d = {
        "x": np.asarray(las.x), "y": np.asarray(las.y), "z": np.asarray(las.z),
        "cls": np.asarray(las.classification).astype("int16"),
        "hag": np.asarray(las.HeightAboveGround, dtype="float32"),
        "rn": np.asarray(las.return_number).astype("int8"),
        "nr": np.asarray(las.number_of_returns).astype("int8"),
        "inten": np.asarray(las.intensity).astype("float32"),
        "psid": np.asarray(las.point_source_id).astype("int32"),
        "eofl": np.asarray(las.edge_of_flight_line).astype(bool),
    }
    for a in ("scan_angle", "scan_angle_rank"):
        if hasattr(las, a):
            v = np.asarray(getattr(las, a), dtype="float32")
            d["ang"] = v * 0.006 if a == "scan_angle" else v
            break
    for f in ("withheld", "overlap", "synthetic", "key_point"):
        try:
            d[f] = np.asarray(getattr(las, f)).astype(bool)
        except Exception:
            d[f] = np.zeros(d["z"].size, dtype=bool)
    tmp.unlink(missing_ok=True)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", nargs="+",
                    default=["621594", "616591", "615591", "613591"])
    ap.add_argument("--profile", action="store_true",
                    help="draw a cross-section of the classification")
    ap.add_argument("--profile-target", default="pit", choices=("pit", "pad"),
                    help="centre the cross-section on a pit floor or a pad")
    ap.add_argument("--profile-length", type=float, default=0.0,
                    help="transect length in metres; 0 = pick from the feature")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    props, cells, voids = [], [], []
    for code in args.tiles:
        laz = find_tile(code)
        print(f"=== tile {code}")
        d = load_tile(laz)
        g2 = d["cls"] == 2
        ng = (d["cls"] == 1) & np.isfinite(d["hag"]) & (np.abs(d["hag"]) < NEAR)
        print(f"    {d['z'].size:,} pts, {int(g2.sum()):,} ground, "
              f"{int(ng.sum()):,} near-ground unassigned")

        # ---- PART A: which property separates them from class 2? ----------
        for lbl, m in (("class 2", g2), ("near-ground class 1", ng)):
            props.append({
                "tile": code, "group": lbl, "points": int(m.sum()),
                "single_return": float((d["nr"][m] == 1).mean()),
                "terminal_return": float((d["rn"][m] == d["nr"][m]).mean()),
                "overlap_flag": float(d["overlap"][m].mean()),
                "edge_of_flightline": float(d["eofl"][m].mean()),
                "med_abs_scan_angle": float(np.median(np.abs(d["ang"][m]))),
                "p95_abs_scan_angle": float(np.percentile(np.abs(d["ang"][m]), 95)),
                "med_intensity": float(np.median(d["inten"][m])),
                "n_flightlines": int(np.unique(d["psid"][m]).size),
            })

        # ---- PART B: the DEM grid, cell by cell ---------------------------
        x0, y1 = d["x"].min(), d["y"].max()
        nx = int(np.ceil((d["x"].max() - x0) / RES)) + 1
        ny = int(np.ceil((y1 - d["y"].min()) / RES)) + 1
        flat = (np.clip(((y1 - d["y"]) / RES).astype(np.int64), 0, ny - 1) * nx +
                np.clip(((d["x"] - x0) / RES).astype(np.int64), 0, nx - 1))
        n = nx * ny
        c_g2 = np.bincount(flat[g2], minlength=n)
        c_ng = np.bincount(flat[ng], minlength=n)
        c_any = np.bincount(flat, minlength=n)

        covered = c_any > 0                      # the tile's real footprint
        has_g2 = c_g2 > 0
        void = covered & ~has_g2                 # interpolated in the DEM today
        fixable = void & (c_ng > 0)              # ...and a ground-level point sits there

        cells.append({
            "tile": code, "cells_covered": int(covered.sum()),
            "cells_with_ground": int(has_g2.sum()),
            "cells_void": int(void.sum()),
            "cells_void_fixable": int(fixable.sum()),
            "pct_void": 100 * void.sum() / covered.sum(),
            "pct_void_fixable": 100 * fixable.sum() / covered.sum(),
            "pct_of_void_fixable": 100 * fixable.sum() / max(void.sum(), 1),
            "area_void_m2": float(void.sum() * RES ** 2),
            "area_fixable_m2": float(fixable.sum() * RES ** 2),
        })

        # how the near-ground points distribute over cells that already have
        # ground -- the redundancy question
        bins = [0, 1, 2, 3, 5, 9, 10 ** 9]
        lbls = ["0", "1", "2", "3-4", "5-8", "9+"]
        idx = np.digitize(c_g2, bins[1:-1], right=False)
        for i, lb in enumerate(lbls):
            m = (idx == i) & covered
            voids.append({"tile": code, "class2_in_cell": lb,
                          "cells": int(m.sum()),
                          "nearground_pts": int(c_ng[m].sum())})

        if args.profile and code == args.tiles[0]:
            _profile(code, d, target=args.profile_target,
                     length=args.profile_length)
        del d

    pr, ce, vo = pd.DataFrame(props), pd.DataFrame(cells), pd.DataFrame(voids)
    pr.to_csv(OUT / "nearground_vs_ground_properties.csv", index=False)
    ce.to_csv(OUT / "dem_void_cells_by_tile.csv", index=False)
    vo.to_csv(OUT / "nearground_points_by_cell_ground_count.csv", index=False)
    _report(pr, ce, vo)
    print(f"\nwrote CSVs to {OUT}")
    return 0


def _report(pr, ce, vo):
    line = "=" * 78
    print(f"\n{line}\nPART A  HOW DO THEY DIFFER FROM CLASS 2?\n{line}")
    g = pr.groupby("group").agg(
        points=("points", "sum"), single=("single_return", "mean"),
        term=("terminal_return", "mean"), ovl=("overlap_flag", "mean"),
        eofl=("edge_of_flightline", "mean"),
        ang=("med_abs_scan_angle", "mean"), ang95=("p95_abs_scan_angle", "mean"),
        inten=("med_intensity", "mean"))
    cols = [("points", "points", "13,.0f"), ("single", "single return", "13.1%"),
            ("term", "terminal return", "15.1%"), ("ovl", "overlap flag", "13.2%"),
            ("eofl", "edge of swath", "14.2%"),
            ("ang", "med |scan angle|", "17.1f"),
            ("ang95", "p95 |scan angle|", "17.1f"),
            ("inten", "med intensity", "14.0f")]
    for key, label, fmt in cols:
        vals = "".join(format(g.loc[grp, key], fmt.split(".", 1)[0] + "s"
                              if False else fmt).rjust(22)
                       for grp in g.index)
        print(f"  {label:20s}{vals}")
    print("  " + " " * 20 + "".join(str(i).rjust(22) for i in g.index))

    print(f"\n{line}\nPART B  WHERE DO THEY LAND ON THE DEM GRID?\n{line}")
    t = vo.groupby("class2_in_cell").agg(cells=("cells", "sum"),
                                         pts=("nearground_pts", "sum"))
    t = t.reindex(["0", "1", "2", "3-4", "5-8", "9+"]).dropna()
    tot_c, tot_p = t.cells.sum(), t.pts.sum()
    print(f"  {'class 2 in the cell':>20s} {'cells':>12s} {'share':>8s} "
          f"{'near-gnd pts':>14s} {'share':>8s}")
    for k, r in t.iterrows():
        print(f"  {k:>20s} {r.cells:12,.0f} {100*r.cells/tot_c:7.1f}% "
              f"{r.pts:14,.0f} {100*r.pts/tot_p:7.1f}%")

    print(f"\n{line}\nPART C  WHAT WOULD ACTUALLY CHANGE\n{line}")
    s = ce.sum(numeric_only=True)
    print(f"  {RES} m cells inside the tiles' footprint : {s.cells_covered:,.0f}")
    print(f"  cells holding at least one class-2 return: "
          f"{s.cells_with_ground:,.0f} "
          f"({100*s.cells_with_ground/s.cells_covered:.2f}%)")
    print(f"  cells with NO ground return -- the DEM interpolates across these:")
    print(f"      {s.cells_void:,.0f} cells "
          f"({100*s.cells_void/s.cells_covered:.2f}%), "
          f"{s.area_void_m2/1e4:,.1f} ha")
    print(f"  of those, cells where a near-ground class-1 point IS sitting:")
    print(f"      {s.cells_void_fixable:,.0f} cells "
          f"({100*s.cells_void_fixable/s.cells_covered:.3f}% of the tile, "
          f"{100*s.cells_void_fixable/max(s.cells_void,1):.1f}% of the voids), "
          f"{s.area_fixable_m2/1e4:,.2f} ha")
    print("\n  That last number is the whole answer. It is the only place where "
          "calling\n  these points ground would replace a guessed elevation "
          "with a measured one.")
    print("\n  per tile")
    print(f"  {'tile':>8s} {'void cells':>12s} {'% of tile':>10s} "
          f"{'fixable':>10s} {'% of voids':>11s}")
    for _, r in ce.iterrows():
        print(f"  {r.tile:>8s} {r.cells_void:12,.0f} {r.pct_void:9.2f}% "
              f"{r.cells_void_fixable:10,.0f} {r.pct_of_void_fixable:10.1f}%")


def _profile(code, d, target="pit", length=0.0, halfwidth=0.0):
    """Cross-section of the classification, with the ground surface zoomed."""
    """A cross-section: what the classification looks like, before and after."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import geopandas as gpd

    SURFACE, INK, INK2, MUTED, RULE = ("#fcfcfb", "#0b0b0b", "#52514e",
                                       "#8a887e", "#d8d7cf")
    # semantic, not decorative: earth for ground, a light-to-dark green ramp
    # climbing the canopy, grey for undecided, red for noise
    COL = {1: ("#9a988f", "unassigned"), 2: ("#8c6239", "ground"),
           3: ("#a8d08d", "low veg 0.15-2 m"), 4: ("#4f9d4f", "medium veg 2-5 m"),
           5: ("#1f6b34", "high veg > 5 m"),
           6: ("#c98b2e", "below ground, coherent"),
           7: ("#c0392b", "below ground, isolated"),
           9: ("#2a78d6", "water"), 18: ("#c0392b", "high noise")}

    # centre the transect on a real annotated feature, widest one available
    from shapely.geometry import box as _box, LineString
    bb = (d["x"].min(), d["y"].min(), d["x"].max(), d["y"].max())
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    subject, span = "tile centre", None
    layer = "pit_inside" if target == "pit" else "plat"
    try:
        gdf = gpd.read_file(ANN, layer=layer)
        sel = gdf[gdf.centroid.within(_box(*bb))]
        if len(sel):
            sel = sel.reset_index(drop=True)
            w = (sel.geometry.bounds.maxx - sel.geometry.bounds.minx).values
            pick = int(np.argmax(w))
            # a wide pit is easy to cut through but a shallow one is invisible
            # against 25 m of canopy. The depth experiment already measured
            # every floor, so use it: deepest pit that is still wide enough.
            depths = OUT.parent / "ground_reclassification" /                 "pit_depth_reclaim_strict_per_pit.csv"
            if target == "pit" and depths.exists():
                dep = pd.read_csv(depths)
                dep = dep[dep.tile.astype(str) == str(code)]
                dep = dep[dep.pit < len(sel)]
                if len(dep):
                    dep = dep.assign(width=w[dep.pit.values])
                    dep = dep[dep.width >= max(6.0, np.percentile(w, 60))]
                    if len(dep):
                        pick = int(dep.loc[dep.depth_A_m.idxmax(), "pit"])
                        print(f"    profile: pit {pick}, "
                              f"{dep.depth_A_m.max():.2f} m deep")
            big = sel.iloc[pick]
            cx, cy = big.geometry.centroid.x, big.geometry.centroid.y
            wide = float(w.max())
            subject = (f"across an annotated {target} "
                       f"({big.geometry.area:.0f} m², {wide:.1f} m wide)")
            # where the polygon actually starts and stops along the cut
            cut = big.geometry.intersection(
                LineString([(cx - 500, cy), (cx + 500, cy)]))
            if not cut.is_empty:
                xs = np.array(cut.bounds)[[0, 2]] - cx
                span = (float(xs[0]), float(xs[1]))
            if length <= 0:
                length = max(30.0, min(90.0, wide * 5))
            if halfwidth <= 0:
                halfwidth = 2.0 if target == "pit" else 1.5
    except Exception as e:
        print(f"    profile: could not read {layer} ({e})")
    length = length or 120.0
    halfwidth = halfwidth or 1.5

    m = ((np.abs(d["y"] - cy) < halfwidth) &
         (np.abs(d["x"] - cx) < length / 2))
    if m.sum() < 120:
        print("    profile: too few points, skipped")
        return
    dist = d["x"][m] - cx
    z = d["z"][m]
    old = d["cls"][m]
    hag = d["hag"][m]
    new = old.copy()
    t = old == 1
    for lo, hi, c in ((-1e9, -0.15, 7), (-0.15, 0.15, 1), (0.15, 2.0, 3),
                      (2.0, 5.0, 4), (5.0, 60.0, 5)):
        new[t & np.isfinite(hag) & (hag >= lo) & (hag < hi)] = c

    # A flat height band calls everything under the surface "noise", and the
    # profile shows that is wrong: inside a pit these points trace a continuous
    # floor. Split them the way the depth experiment did -- a point with
    # neighbours at the same level is a surface, an isolated one is an outlier.
    from scipy.spatial import cKDTree
    box_m = length / 2 + 12
    near_cut = ((np.abs(d["y"] - cy) < halfwidth + 12) &
                (np.abs(d["x"] - cx) < box_m) & (d["cls"] == 1) &
                np.isfinite(d["hag"]) & (d["hag"] < -0.15))
    if near_cut.sum() >= 4:
        bx, by, bz = d["x"][near_cut], d["y"][near_cut], d["z"][near_cut]
        nb = cKDTree(np.c_[bx, by]).query_ball_point(np.c_[bx, by], r=2.0)
        # Raw vertical range is the wrong measure of coherence on a hillside:
        # at 20% slope a 2 m radius spans 0.4 m of real relief, so a perfectly
        # flat-lying surface fails a 0.5 m range test purely for being tilted.
        # Detrend against a fitted plane and judge the residual instead.
        coh = np.zeros(len(nb), bool)
        for i, q in enumerate(nb):
            if len(q) - 1 < 3:
                continue
            A = np.c_[bx[q] - bx[i], by[q] - by[i], np.ones(len(q))]
            try:
                c, *_ = np.linalg.lstsq(A, bz[q], rcond=None)
            except np.linalg.LinAlgError:
                continue
            resid = bz[q] - A @ c
            coh[i] = (resid.max() - resid.min()) < 0.35
        key = {(round(a, 3), round(b, 3)) for a, b in
               zip(bx[coh], by[coh])}
        if key:
            cut_xy = list(zip(np.round(d["x"][m], 3), np.round(d["y"][m], 3)))
            promote = np.fromiter((k in key for k in cut_xy), bool, len(cut_xy))
            new[(new == 7) & promote] = 6

    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(3, 1, figsize=(15.0, 13.0), sharex=True,
                           gridspec_kw={"height_ratios": [1, 1, 0.85]})
    ax[0].sharey(ax[1])
    for a, cls, title in (
            (ax[0], old, "As delivered  —  two classes, and a third of the "
                         "points are simply “unassigned”"),
            (ax[1], new, "Reclassified by height above ground  —  the same "
                         "points, told apart"),
            (ax[2], new, "The ground surface, close up  —  this is the pit. "
                         "The coherent below-surface returns trace its floor")):
        for c in sorted(np.unique(cls)):
            k = cls == c
            col, lab = COL.get(int(c), ("#000000", f"class {c}"))
            a.scatter(dist[k], z[k], s=4.5, c=col, linewidths=0,
                      label=f"{lab}  ({int(k.sum()):,})")
        if span is not None:
            a.axvspan(span[0], span[1], color="#eb6834", alpha=0.10, zorder=0)
            for xv in span:
                a.axvline(xv, color="#eb6834", linewidth=1.3, alpha=0.65,
                          zorder=1)
        a.set_title(title, fontsize=13.5, fontweight="bold", loc="left", pad=8)
        a.legend(frameon=False, fontsize=9.5, markerscale=3.2, ncol=3,
                 loc="upper left")
        a.set_ylabel("elevation, m NAVD88", fontsize=11, color=INK2)
        a.grid(color=RULE, linewidth=0.6, alpha=0.7)
        a.set_axisbelow(True)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            a.spines[sp].set_color(RULE)
        a.tick_params(colors=INK2, labelsize=10)
    # the pit is a metre deep against 25 m of canopy, so it needs its own scale
    gz = z[np.isfinite(hag) & (np.abs(hag) < 0.6)]
    if gz.size > 10:
        lo, hi = np.percentile(gz, [1, 99])
        pad = max(0.55, 0.30 * (hi - lo))
        ax[2].set_ylim(lo - pad, hi + pad)
    ax[2].set_xlabel("distance along the transect, m", fontsize=11, color=INK2)
    note = ("  ·  orange band = the annotated polygon"
            if span is not None else "")
    fig.subplots_adjust(left=0.055, right=0.99, top=0.955, bottom=0.030,
                        hspace=0.13)
    p = OUT / f"classification_cross_section_{target}_{code}_{length:.0f}m.png"
    fig.savefig(p, dpi=185)
    plt.close(fig)
    print(f"    profile {p}")


if __name__ == "__main__":
    sys.exit(main())
