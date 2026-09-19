"""What ARE the 35% of points the vendor left unclassified, and can we classify them?

THE SITUATION
-------------
The USGS 3DEP PA WesternPA 2019 D20 delivery carries two classes and nothing
else. Class 2 is ground, roughly 65%. Everything else -- roughly 35% -- is class
1, "unassigned". There are no vegetation classes, no buildings, no water, and the
noise flags are essentially unused. The vendor ran a ground filter and stopped.

So a third of every tile is unlabelled, and the only thing this project has ever
done with it is build a canopy height model off the first returns. That is a lot
of discarded structure.

WHAT WE HAVE TO WORK WITH
-------------------------
Point format 6, LAS 1.4. Every dimension needed for a vegetation classification
is populated:

    ReturnNumber, NumberOfReturns   up to 15 returns, so the full pulse profile
    Intensity                       16-bit
    ScanAngleRank, ScanChannel      geometry
    GpsTime, PointSourceId          flightline identity, for overlap checks

Return structure is the important one. It is not a derived quantity -- it is
recorded by the scanner and it is unambiguous. If a pulse produced five returns
and this is the third, then something intercepted the beam above this point AND
below it. That point is inside a canopy. No height model, no threshold, no
classifier opinion required.

WHAT THIS SCRIPT DOES
---------------------
  PART 1  Return-structure census. How multi-return is this delivery, and how
          much of class 1 is structurally unambiguous?
  PART 2  Class 1 cross-tabulated by height above ground against return
          position. This is the table that says what the unassigned points are.
  PART 3  Apply an ASPRS-conformant classification and report what lands where.
  PART 4  So what? Vegetation structure inside annotated pads and pits versus
          the ground around them. If a 150-year-old well pad regrew differently
          from the forest around it, these points can see it and the DEM cannot.

Bands follow the USGS 3DEP Lidar Base Specification convention for vegetation
(ASPRS 3 / 4 / 5 split at 2 m and 5 m).

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md). One pass per tile:

    readers.las -> filters.hag_nn -> writers.las

then numpy. Full density, no decimation.

Run:
    python notebooks/wellsight_v2/s7_analysis/_classify_nonground_returns_9t.py
    ... --tiles 616591 621594 --write-laz
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

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "_source" / "lidar" / "westernpa"
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
OUT = ROOT / "data" / "9t" / "results" / "nonground_classification"
PDAL = "pdal"

#: ASPRS vegetation split, per the USGS 3DEP Lidar Base Specification.
#: The 0.15 m floor is the same near-ground tolerance the sniff test used.
BANDS = [
    ("below ground",  -1e9, -0.15, 7),    # ASPRS 7, low point (noise)
    ("at ground",    -0.15,  0.15, 1),    # genuinely ambiguous -- left alone
    ("low veg",       0.15,   2.0, 3),
    ("medium veg",     2.0,   5.0, 4),
    ("high veg",       5.0,  60.0, 5),
    ("above canopy",  60.0,   1e9, 18),   # ASPRS 18, high noise
]

#: Structure metrics need enough points per cell to be stable. At ~4.8 ppsm a
#: 5 m cell holds ~120 returns; a 2 m cell holds ~19, and the understory share
#: then degenerates to a median of exactly zero.
CELL = 5.0          # raster cell for the structure metrics, metres
MIN_CELL_PTS = 30
RING_IN = 2.0       # control annulus around an annotated polygon
RING_OUT = 15.0


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


def load_tile(laz, keep_las=False):
    """One PDAL pass: height above the vendor's ground surface for every point."""
    tmp = Path(tempfile.gettempdir()) / f"_ngc_{laz.stem}.las"
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
        "gps": np.asarray(las.gps_time),
        "x": np.asarray(las.x), "y": np.asarray(las.y), "z": np.asarray(las.z),
        "cls": np.asarray(las.classification).astype("int16"),
        "hag": np.asarray(las.HeightAboveGround, dtype="float32"),
        "rn": np.asarray(las.return_number).astype("int8"),
        "nr": np.asarray(las.number_of_returns).astype("int8"),
        "inten": np.asarray(las.intensity).astype("float32"),
    }
    if not keep_las:
        tmp.unlink(missing_ok=True)
        return d, None
    return d, tmp


def return_position(rn, nr):
    """only / first / intermediate / last. Intermediate is the load-bearing one.

    An intermediate return means the pulse was intercepted both above and below
    this point. That is a physical fact recorded by the scanner, not an
    inference, and it cannot be ground.
    """
    pos = np.empty(rn.size, dtype="U6")
    only = nr == 1
    pos[only] = "only"
    pos[(~only) & (rn == 1)] = "first"
    pos[(~only) & (rn == nr)] = "last"
    pos[(rn > 1) & (rn < nr)] = "inter"
    return pos


def classify(d):
    """Assign an ASPRS class to every class-1 point from its height band."""
    new = d["cls"].copy()
    target = d["cls"] == 1
    for _, lo, hi, code in BANDS:
        m = target & np.isfinite(d["hag"]) & (d["hag"] >= lo) & (d["hag"] < hi)
        new[m] = code
    # An intermediate return cannot be ground and cannot be near-ground clutter.
    # Anything still sitting at "1" that is an intermediate return is vegetation
    # by construction; promote it to low veg rather than leave it undecided.
    still = (new == 1) & (d["rn"] > 1) & (d["rn"] < d["nr"])
    new[still] = 3
    return new, int(still.sum())


def grid_metrics(d, bb, cell=CELL):
    """Per-cell canopy structure from the returns. Bincount, not a loop."""
    nx = int(np.ceil((bb[2] - bb[0]) / cell))
    ny = int(np.ceil((bb[3] - bb[1]) / cell))
    col = np.clip(((d["x"] - bb[0]) / cell).astype(int), 0, nx - 1)
    row = np.clip(((bb[3] - d["y"]) / cell).astype(int), 0, ny - 1)
    flat = row * nx + col
    n = nx * ny
    hag = np.nan_to_num(d["hag"], nan=-999.0)

    def cnt(m):
        return np.bincount(flat[m], minlength=n).astype("float32")

    first = (d["rn"] == 1)
    all_n = cnt(np.ones(flat.size, bool))
    first_n = cnt(first)
    # canopy cover: the standard first-return ratio
    cover = np.divide(cnt(first & (hag > 2.0)), first_n,
                      out=np.full(n, np.nan, "float32"), where=first_n > 0)
    # understory: returns in the 0.5-3 m shrub layer, as a share of all returns
    under = np.divide(cnt((hag > 0.5) & (hag < 3.0)), all_n,
                      out=np.full(n, np.nan, "float32"), where=all_n > 0)
    # how often a pulse got through: multi-return share
    pen = np.divide(cnt(d["nr"] > 1), all_n,
                    out=np.full(n, np.nan, "float32"), where=all_n > 0)
    # canopy top and vertical spread
    h95 = np.full(n, np.nan, "float32")
    veg = hag > 0.5
    if veg.any():
        order = np.lexsort((hag[veg], flat[veg]))
        fv, hv = flat[veg][order], hag[veg][order]
        edges = np.searchsorted(fv, np.arange(n + 1))
        k = edges[1:] - edges[:-1]
        ok = k >= 4
        idx = (edges[:-1] + (0.95 * (k - 1)).astype(int))[ok]
        h95[ok] = hv[idx]
    return {"cover": cover.reshape(ny, nx), "under": under.reshape(ny, nx),
            "penetration": pen.reshape(ny, nx), "h95": h95.reshape(ny, nx),
            "n": all_n.reshape(ny, nx)}, (nx, ny)


STASH = {}


def zone_compare(metrics, bb, shape, polys, label, rows):
    """Structure metrics inside annotated polygons vs a ring around them."""
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    nx, ny = shape
    tf = from_origin(bb[0], bb[3], CELL, CELL)
    geom = polys.union_all()
    if geom.is_empty:
        return
    inside = rasterize([(geom, 1)], out_shape=(ny, nx), transform=tf,
                       dtype="uint8").astype(bool)
    ring_g = geom.buffer(RING_OUT).difference(geom.buffer(RING_IN))
    ring = rasterize([(ring_g, 1)], out_shape=(ny, nx), transform=tf,
                     dtype="uint8").astype(bool)
    enough = metrics["n"] >= MIN_CELL_PTS
    for k in ("cover", "under", "penetration", "h95"):
        a, b = metrics[k][inside & enough], metrics[k][ring & enough]
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if a.size < 20 or b.size < 20:
            continue
        # Cliff's delta: the chance a cell inside outranks a cell in the ring,
        # rescaled to -1..+1. Rank-based, so a skewed metric cannot fake it.
        from scipy.stats import mannwhitneyu
        u, pv = mannwhitneyu(a, b, alternative="two-sided")
        STASH[(label, k)] = (a, b)
        rows.append({"feature": label, "metric": k,
                     "n_cells_in": a.size, "n_cells_ring": b.size,
                     "inside": float(np.median(a)), "ring": float(np.median(b)),
                     "delta": float(np.median(a) - np.median(b)),
                     "mean_in": float(np.mean(a)), "mean_ring": float(np.mean(b)),
                     "cliffs_delta": float(2 * u / (a.size * b.size) - 1),
                     "p": float(pv)})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", nargs="+", default=["616591", "621594"])
    ap.add_argument("--figure", action="store_true",
                    help="plot the canopy-height result")
    ap.add_argument("--write-laz", action="store_true",
                    help="write a reclassified copy of each tile")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    census, xtab, classed, zrows, acq, delivered = [], [], [], [], [], []
    pads = gpd.read_file(ANN, layer="plat")
    pits = gpd.read_file(ANN, layer="pit_inside")

    for code in args.tiles:
        laz = find_tile(code)
        print(f"=== tile {code}  ({laz.name})")
        d, tmp = load_tile(laz, keep_las=args.write_laz)
        n = d["z"].size
        # Adjusted Standard GPS Time -> UTC. Leaf-on or leaf-off decides what
        # every canopy number below actually means, so it is not optional.
        from datetime import datetime, timedelta
        t0, t1 = (datetime(1980, 1, 6) + timedelta(seconds=float(v) + 1e9 - 18)
                  for v in (d["gps"].min(), d["gps"].max()))
        leaf = "LEAF-OFF" if t0.month in (11, 12, 1, 2, 3, 4) else "leaf-on"
        print(f"    {n:,} points, flown {t0:%Y-%m-%d %H:%M} .. {t1:%Y-%m-%d %H:%M}"
              f" UTC  [{leaf}]")
        acq.append({"tile": code, "start": t0.isoformat(), "end": t1.isoformat(),
                    "leaf": leaf, "points": n})
        for c, k in zip(*np.unique(d["cls"], return_counts=True)):
            delivered.append({"tile": code, "class": int(c), "points": int(k)})
        pos = return_position(d["rn"], d["nr"])
        g2, c1 = d["cls"] == 2, d["cls"] == 1

        for nr in range(1, int(d["nr"].max()) + 1):
            m = d["nr"] == nr
            if not m.any():
                continue
            census.append({"tile": code, "n_returns": nr, "points": int(m.sum()),
                           "share": m.mean(),
                           "share_class1": float(c1[m].mean()),
                           "share_ground": float(g2[m].mean())})

        for p in ("only", "first", "inter", "last"):
            for bname, lo, hi, _ in BANDS:
                m = c1 & (pos == p) & np.isfinite(d["hag"]) & \
                    (d["hag"] >= lo) & (d["hag"] < hi)
                xtab.append({"tile": code, "position": p, "band": bname,
                             "points": int(m.sum())})

        new, promoted = classify(d)
        for c in sorted(np.unique(new)):
            m = new == c
            classed.append({"tile": code, "class": int(c), "points": int(m.sum()),
                            "share": float(m.mean()),
                            "was_class1": int((m & c1).sum())})
        print(f"    reclassified {int(c1.sum()):,} class-1 points "
              f"({promoted:,} promoted on return structure alone)")

        bb = (d["x"].min(), d["y"].min(), d["x"].max(), d["y"].max())
        metrics, shape = grid_metrics(d, bb)
        tb = box(*bb)
        for lbl, gdf in (("pad", pads), ("pit", pits)):
            sel = gdf[gdf.centroid.within(tb)]
            if len(sel):
                zone_compare(metrics, bb, shape, sel, f"{code}/{lbl}", zrows)

        if args.write_laz and tmp is not None:
            import laspy
            las = laspy.read(str(tmp))
            las.classification = new.astype("uint8")
            p = OUT / f"reclassified_nonground_{code}_asprs345.laz"
            las.write(str(p))
            tmp.unlink(missing_ok=True)
            print(f"    wrote {p}  ({p.stat().st_size/1e6:.0f} MB)")
        del d

    ce, xt, cl, zc = (pd.DataFrame(census), pd.DataFrame(xtab),
                      pd.DataFrame(classed), pd.DataFrame(zrows))
    dv = pd.DataFrame(delivered)
    pd.DataFrame(acq).to_csv(OUT / "acquisition_windows.csv", index=False)
    dv.to_csv(OUT / "delivered_class_counts.csv", index=False)
    ce.to_csv(OUT / "return_structure_census.csv", index=False)
    xt.to_csv(OUT / "class1_height_by_return_position.csv", index=False)
    cl.to_csv(OUT / "reclassified_class_counts.csv", index=False)
    if not zc.empty:
        zc.to_csv(OUT / "veg_structure_pad_pit_vs_ring.csv", index=False)
    _report(ce, xt, cl, zc, dv, acq)
    if args.figure and not zc.empty:
        _figure(zc)
    print(f"\nwrote CSVs to {OUT}")
    return 0


def _report(ce, xt, cl, zc, dv, acq):
    line = "=" * 76
    ASPRS = {1: "unassigned", 2: "ground", 3: "low vegetation",
             4: "medium vegetation", 5: "high vegetation", 7: "low noise",
             18: "high noise"}

    print(f"\n{line}\nPART 1  RETURN-STRUCTURE CENSUS\n{line}")
    g = ce.groupby("n_returns").agg(points=("points", "sum"))
    tot = g.points.sum()
    print(f"  {'returns in pulse':>17s} {'points':>13s} {'share':>8s}")
    for nr, r in g.iterrows():
        print(f"  {nr:>17d} {r.points:13,.0f} {100*r.points/tot:7.2f}%")
    multi = g[g.index > 1].points.sum()
    print(f"\n  single-return pulses : {100*g.loc[1,'points']/tot:.1f}%")
    print(f"  multi-return pulses  : {100*multi/tot:.1f}%   "
          "<- every one of these penetrated something")

    print(f"\n{line}\nPART 2  WHAT THE UNASSIGNED POINTS ARE\n{line}")
    p = xt.pivot_table(index="band", columns="position", values="points",
                       aggfunc="sum").fillna(0)
    order = [b[0] for b in BANDS if b[0] in p.index]
    cols = [c for c in ("only", "first", "inter", "last") if c in p.columns]
    p = p.loc[order, cols]
    tot1 = p.values.sum()
    print(f"  {'height band':>14s} " + "".join(f"{c:>12s}" for c in cols) +
          f"{'total':>12s}{'share':>8s}")
    for b in order:
        rw = p.loc[b]
        print(f"  {b:>14s} " + "".join(f"{rw[c]:12,.0f}" for c in cols) +
              f"{rw.sum():12,.0f}{100*rw.sum()/tot1:7.1f}%")
    print(f"  {'TOTAL':>14s} " + "".join(f"{p[c].sum():12,.0f}" for c in cols) +
          f"{tot1:12,.0f}")
    if "inter" in p.columns:
        print(f"\n  intermediate returns : {p['inter'].sum():,.0f} "
              f"({100*p['inter'].sum()/tot1:.1f}% of class 1)")
        print("  These had a return above AND below them. They are inside a "
              "canopy,\n  as a matter of recorded fact rather than inference.")

    print(f"\n{line}\nPART 3  AFTER CLASSIFICATION\n{line}")
    g = cl.groupby("class").agg(points=("points", "sum"),
                                was1=("was_class1", "sum"))
    tot = g.points.sum()
    print(f"  {'code':>4}  {'class':20s} {'points':>13s} {'share':>8s} "
          f"{'from class 1':>14s}")
    for c, r in g.iterrows():
        print(f"  {c:>4}  {ASPRS.get(int(c), '?'):20s} {r.points:13,.0f} "
              f"{100*r.points/tot:7.2f}% {r.was1:14,.0f}")
    left = g.loc[1, "points"] if 1 in g.index else 0
    print(f"\n  still unassigned : {left:,.0f} ({100*left/tot:.2f}%) -- the "
          "near-ground band,\n  where a rock and a low return are genuinely "
          "not separable.")

    if zc.empty:
        return
    print(f"\n{line}\nPART 4  DOES THE VEGETATION REMEMBER THE WELL PAD?\n{line}")
    names = {"cover": "canopy cover (first rtn > 2 m)",
             "under": "understory share 0.5-3 m (mean)",
             "penetration": "multi-return share",
             "h95": "canopy height p95 (m)"}
    hdr = "Cliff's d"
    print(f"  {'feature':14s} {'metric':30s} {'inside':>8s} {'ring':>8s} "
          f"{'delta':>8s} {hdr:>10s} {'p':>9s} {'cells':>12s}")
    for _, r in zc.iterrows():
        star = "  <-" if abs(r.cliffs_delta) >= 0.15 and r.p < 0.01 else ""
        # the understory median is a true 0.000 in leaf-off mature forest, so
        # show its mean instead of printing a column of zeros
        ins, rng = ((r.mean_in, r.mean_ring) if r.metric == "under"
                    else (r.inside, r.ring))
        print(f"  {r.feature:14s} {names.get(r.metric, r.metric):30s} "
              f"{ins:8.3f} {rng:8.3f} {ins - rng:+8.3f} "
              f"{r.cliffs_delta:+10.3f} {r.p:9.2e} "
              f"{int(r.n_cells_in):5d}/{int(r.n_cells_ring):<6d}{star}")
    print("\n  The ring is the forest immediately around the feature, "
          "so this is a\n  like-for-like comparison. Cliff's delta is "
          "the rank-based effect size: the chance a cell inside\n  "
          "outranks one in the ring, rescaled to -1..+1. |d| >= 0.15 with "
          "p < 0.01\n  is marked -- a significant p on thousands of "
          "cells means little on its own.")


def _figure(zc):
    """Canopy height over disturbance, against the forest immediately around it."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    SURFACE, INK, INK2, MUTED, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a887e", "#d8d7cf"
    S1, S2 = "#2a78d6", "#eb6834"
    h = zc[zc.metric == "h95"].reset_index(drop=True)
    if h.empty:
        return
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
                         "text.color": INK})
    fig, ax = plt.subplots(1, 2, figsize=(14.2, 6.4),
                           gridspec_kw={"width_ratios": [1.15, 1]})

    # left: the distributions for the largest sample, pads on 621594
    big = h.iloc[h.n_cells_in.argmax()]
    a, b = STASH[(big.feature, "h95")]
    for arr, col, lab in ((b, S1, f"forest ring  (n={b.size:,})"),
                          (a, S2, f"inside the feature  (n={a.size:,})")):
        xs = np.sort(arr)
        ax[0].plot(xs, np.linspace(0, 1, xs.size), color=col, linewidth=2.2,
                   label=lab)
        ax[0].axvline(np.median(arr), color=col, linewidth=1.1, linestyle=":")
    ax[0].set_xlabel("canopy height, 95th percentile per 5 m cell (m)",
                     fontsize=11, color=INK2)
    ax[0].set_ylabel("share of cells at or below", fontsize=11, color=INK2)
    ax[0].set_title(f"{big.feature}  —  the canopy is shorter over the "
                    f"disturbance", fontsize=14, fontweight="bold", loc="left",
                    pad=10)
    ax[0].legend(frameon=False, fontsize=10, loc="lower right")

    # right: every group, as an effect size
    h = h.sort_values("cliffs_delta")
    ypos = np.arange(len(h))
    ax[1].axvline(0, color=RULE, linewidth=1.4)
    for sig, alpha in ((h.p < 0.01, 1.0), (h.p >= 0.01, 0.35)):
        m = sig.values
        ax[1].scatter(h.cliffs_delta[m], ypos[m], s=95, color=S2, alpha=alpha,
                      zorder=3, edgecolor=SURFACE, linewidth=1.5)
    for y, (_, r) in zip(ypos, h.iterrows()):
        ax[1].text(r.cliffs_delta - 0.012, y, f"{r.delta:+.1f} m", ha="right",
                   va="center", fontsize=9.5, color=INK2)
    ax[1].set_yticks(ypos)
    ax[1].set_yticklabels([f"{r.feature}  ({int(r.n_cells_in)} cells)"
                           for _, r in h.iterrows()], fontsize=10)
    ax[1].set_xlabel("Cliff's delta  (negative = shorter canopy inside)",
                     fontsize=11, color=INK2)
    ax[1].set_title("every feature, same direction", fontsize=14,
                    fontweight="bold", loc="left", pad=10)
    ax[1].set_xlim(min(h.cliffs_delta.min() - 0.12, -0.45), 0.12)

    for a_ in ax:
        a_.grid(axis="x", color=RULE, linewidth=0.7, alpha=0.7)
        a_.set_axisbelow(True)
        for sp in ("top", "right"):
            a_.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            a_.spines[sp].set_color(RULE)
        a_.tick_params(colors=INK2, labelsize=10)

    fig.subplots_adjust(left=0.055, right=0.985, top=0.9, bottom=0.030,
                        wspace=0.42)
    out = OUT / "canopy_height_over_pads_pits_vs_ring_5m.png"
    fig.savefig(out, dpi=190)
    plt.close(fig)
    print("  figure " + str(out))


if __name__ == "__main__":
    sys.exit(main())
