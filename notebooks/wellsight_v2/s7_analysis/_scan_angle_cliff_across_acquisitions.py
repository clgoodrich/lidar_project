"""Is the 18-degree ground-classification cut this vendor, or everybody?

WHY THIS MATTERS
----------------
On five Venango tiles, every at-ground return beyond ~18 degrees off nadir was
left unassigned -- roughly a million per tile, 0.0% classified as ground, and
the discarded returns measure 6.5-6.7 cm RMSE against neighbouring flight lines,
inside the USGS QL2 spec of 10 cm.

Five tiles from one delivery is one data point, not a finding. If the same cliff
appears in a different acquisition, flown by a different contractor to a
different quality level, then it is a convention and we should expect it in
every dataset this project ever touches. If it does not, it is specific to
PA WesternPA 2019 D20 and only that area needs reprocessing.

WHAT IS COMPARED
----------------
    PA WesternPA 2019 D20      Venango. QL2, ~4.8 ppsm, flown March 2020.
    PA Northcentral 2019 B19   McKean. QL1, ~9 ppsm, a separate acquisition.

THE MEASUREMENT
---------------
For each tile, of the returns sitting within +/- 15 cm of the ground surface --
that is, returns that demonstrably reached the ground -- what share were
classified as ground, binned by off-nadir scan angle?

A cliff is a threshold in a processing script. A taper is accuracy. The two look
nothing alike and the difference is the whole point.

Decimated 1-in-3 for speed. The measurement is a RATIO within each angle bin, so
thinning the cloud does not bias it; it only widens the error bars, and with
millions of returns per tile those are negligible.

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md).

SAMPLE OR CENSUS
----------------
`--n-per-area 6` samples, which is what the first pass did. `--all` runs every
map square in both deliveries -- 258 of them -- in parallel. The census matters
because a sample of seven cannot tell "this delivery" from "this batch of
flights", and it turned out to be the latter: tiles are grouped by FLIGHT BLOCK
(delivery + month flown), not by county, because Venango was flown twice and the
two halves do not behave the same.

With 258 curves on one axis, individual lines are drawn faint and each block's
median curve is drawn over the top. The band is the block's 10th-90th percentile.

Run:
    python notebooks/wellsight_v2/s7_analysis/_scan_angle_cliff_across_acquisitions.py
    ... --n-per-area 6
    ... --all --workers 6
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.legend_handler import HandlerTuple
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRCROOT = ROOT / "data" / "_source" / "lidar"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "1_data_qa"
CSV = ROOT / "data" / "9t" / "results" / "nonground_classification"
PDAL = "pdal"

NEAR = 0.15
STEP = 3             # decimation; a ratio per angle bin is unaffected
EDGES = np.arange(0, 40.5, 1.0)   # Venango Nov 2019 sweeps to 31 deg

SURFACE, INK, INK2, MUTED, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a887e", "#d8d7cf"
#: Colourblind rule: a red/green pair is the one a deuteranope or
#: protanope cannot read, so no figure here contains both. Checked with
#: the dataviz validator over ALL pairs, not just adjacent ones.
#:   blue #1F5FA8  amber #D97706  deep red #A31515
#:   worst pair dE 21.1 deutan / 21.5 protan / 22.6 normal, all >= 3:1
BLUE, VERM, GREEN, GREY = "#1F5FA8", "#A31515", "#D97706", "#8E959B"
#: one colour per flight block, assigned in fixed order (dataviz skill)
BLOCK_COLOURS = [BLUE, VERM, GREEN, "#111827", "#6B7280"]

#: (label, directory, colour). Keep the two deliveries visually distinct --
#: the whole question is whether they behave the same.
AREAS = [
    ("PA WesternPA 2019 D20  (Venango, QL2)", "westernpa", BLUE),
    ("PA Northcentral 2019 B19  (McKean, QL1)", "mckean", VERM),
]


def tile_code(path):
    """The map-square code a source file covers."""
    m = re.search(r"(e\d+n\d+|17T..\d{6})", path.name)
    return m.group(1) if m else path.stem[-10:]


def unique_tiles(root):
    """One file per map square.

    Counting files instead of squares inflated every total in the first pass.
    Six squares under `westernpa` are on disk twice: four are byte-identical
    copies in `separate_sections/test_section/` (already flagged in
    `docs/_ledgers/duplicates_proposed_moves.csv`), and two are a `.copc.laz`
    cloud-optimised re-encoding sitting beside the plain `.laz` of the same
    tile. Either way the square is one square.

    Kept copy: the plain `.laz` over a `.copc.laz`, then the shallower path --
    the same order `tools/find_duplicates.py` uses.
    """
    best = {}
    for f in sorted(root.rglob("*.laz")):
        if f.name.startswith("_merged"):
            continue
        key = tile_code(f)
        rank = (f.name.endswith(".copc.laz"), len(f.relative_to(root).parts),
                str(f))
        if key not in best or rank < best[key][0]:
            best[key] = (rank, f)
    return [f for _, f in sorted(best.values(), key=lambda t: str(t[1]))]


def run_pipeline(stages, label, timeout=3600):
    """Write the pipeline to a temp file and shell out. See CLAUDE.md."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-900:]); print(r.stderr[-900:])
        raise RuntimeError(f"{label} failed, exit {r.returncode}")


def measure(laz):
    """Ground-classification rate against scan angle, for one tile."""
    tmp = Path(tempfile.gettempdir()) / f"_cliff_{laz.stem}.las"
    run_pipeline([
        str(laz),
        {"type": "filters.decimation", "step": STEP},
        {"type": "filters.hag_nn", "count": 8, "allow_extrapolation": True},
        {"type": "writers.las", "filename": str(tmp),
         "extra_dims": "HeightAboveGround=float32", "compression": "false"},
    ], laz.stem)

    import laspy
    las = laspy.read(str(tmp))
    cls = np.asarray(las.classification).astype("int16")
    hag = np.asarray(las.HeightAboveGround, dtype="float32")
    psid = np.asarray(las.point_source_id)
    gps = np.asarray(las.gps_time)
    for a in ("scan_angle", "scan_angle_rank"):
        if hasattr(las, a):
            v = np.asarray(getattr(las, a), dtype="float32")
            ang = np.abs(v * 0.006 if a == "scan_angle" else v)
            break
    tmp.unlink(missing_ok=True)

    at = np.isfinite(hag) & (np.abs(hag) < NEAR)
    pool = at & ((cls == 2) | (cls == 1))
    n_pool, _ = np.histogram(ang[pool], bins=EDGES)
    n_g2, _ = np.histogram(ang[pool & (cls == 2)], bins=EDGES)
    rate = np.divide(n_g2, n_pool, out=np.full(EDGES.size - 1, np.nan),
                     where=n_pool > 50)

    cut = np.nan
    for i in range(1, rate.size):
        if np.isfinite(rate[i]) and rate[i] < 0.10 and \
                np.isfinite(rate[i - 1]) and rate[i - 1] > 0.50:
            cut = float(EDGES[i]); break
    lost = int((pool & (cls == 1) & (ang >= cut)).sum()) * STEP if \
        np.isfinite(cut) else 0
    d0 = datetime(1980, 1, 6) + timedelta(seconds=float(gps.min()) + 1e9 - 18)
    return dict(points=int(cls.size) * STEP, lines=int(np.unique(psid).size),
                ground_pct=100 * float((cls == 2).mean()),
                max_ang=float(np.percentile(ang, 99.9)),
                cut=cut, lost=lost, flown=d0.strftime("%Y-%m-%d"),
                rate=rate, n_pool=n_pool)


def _short(area):
    """'PA WesternPA 2019 D20  (Venango, QL2)' -> 'Venango'."""
    return area.split("(")[1].split(",")[0] if "(" in area else area


def one(job):
    """Worker. Measure one map square; never raise, so one bad tile is not fatal."""
    label, col, path = job
    code = tile_code(path)
    try:
        r = measure(path)
    except Exception as e:
        return dict(area=label, colour=col, tile=code, error=str(e)[:90])
    r.update(area=label, colour=col, tile=code,
             block=f"{_short(label)} {r['flown'][:7]}")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-area", type=int, default=6)
    ap.add_argument("--all", action="store_true",
                    help="every map square in both deliveries, not a sample")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--redraw", action="store_true",
                    help="redraw the figure from the CSVs, measure nothing")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    CSV.mkdir(parents=True, exist_ok=True)

    if args.redraw:
        suffix = "_all_tiles" if args.all else ""
        rows, df = _rows_from_csv(suffix)
        print(f"redrawing from {len(df)} measured map squares")
        _report(df)
        _figure(rows, df, suffix)
        return 0

    jobs = []
    for label, sub, col in AREAS:
        files = unique_tiles(SRCROOT / sub)
        if not files:
            print(f"!! no tiles under {SRCROOT / sub}")
            continue
        if args.all:
            pick = files
        else:
            # spread the sample across the directory rather than taking a
            # contiguous block, which could sit inside one flight line
            pick = files[:: max(1, len(files) // args.n_per_area)][:args.n_per_area]
        print(f"=== {label}   {len(files)} tiles available, measuring {len(pick)}")
        jobs += [(label, col, f) for f in pick]

    rows, bad, done = [], 0, 0
    workers = max(1, min(args.workers, len(jobs)))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, j) for j in jobs]
        for fu in as_completed(futs):
            r = fu.result()
            done += 1
            if r.get("error"):
                bad += 1
                print(f"  [{done}/{len(jobs)}] {r['tile']:14s} FAILED  {r['error']}")
                continue
            rows.append(r)
            c = f"{r['cut']:.0f} deg" if np.isfinite(r["cut"]) else "none"
            print(f"  [{done}/{len(jobs)}] {r['tile']:14s} {r['block']:16s}"
                  f" ground {r['ground_pct']:4.1f}%  max|ang| {r['max_ang']:4.1f}"
                  f"  cliff {c:>7s}  lost {r['lost']:>9,}")

    if not rows:
        raise SystemExit("nothing measured")
    if bad:
        print(f"\n{bad} of {len(jobs)} tiles failed to measure")

    df = pd.DataFrame([{k: v for k, v in r.items()
                        if k not in ("rate", "n_pool")} for r in rows])
    df = df.sort_values(["block", "tile"])
    suffix = "_all_tiles" if args.all else ""
    f_sum = CSV / f"scan_angle_cliff_by_acquisition{suffix}.csv"
    f_crv = CSV / f"scan_angle_rate_curves{suffix}.csv"
    df.to_csv(f_sum, index=False)
    # the per-bin curves too, so figures can be redrawn without re-measuring
    curves = pd.DataFrame([
        dict(area=r["area"], block=r["block"], tile=r["tile"],
             angle=0.5 * (EDGES[i] + EDGES[i + 1]),
             at_ground_returns=int(r["n_pool"][i]),
             pct_called_ground=(100 * r["rate"][i]
                                if np.isfinite(r["rate"][i]) else None))
        for r in rows for i in range(EDGES.size - 1)
        if r["n_pool"][i] > 50])
    curves.to_csv(f_crv, index=False)
    _report(df)
    _figure(rows, df, suffix)
    print(f"\nwrote {f_sum}\nwrote {f_crv}")
    return 0


def _report(df):
    line = "=" * 78
    print(f"\n{line}\nDOES THE CLIFF REPEAT?  one row per flight block\n{line}")
    print(f"  {'flight block':18s} {'squares':>7s} {'with a cliff':>13s} "
          f"{'cliff, deg':>16s} {'widest':>8s} {'at-ground lost':>15s}")
    for b, g in df.groupby("block"):
        have = g.cut.notna()
        rng = (f"{g.cut[have].min():.0f}-{g.cut[have].max():.0f} "
               f"(med {g.cut[have].median():.0f})") if have.any() else "-"
        print(f"  {b:18s} {len(g):>7d} {int(have.sum()):>7d} "
              f"{100*have.mean():>4.0f}% {rng:>16s} "
              f"{g.max_ang.median():>8.1f} {int(g.lost.sum()):>15,}")
    print("\n  A cliff is a threshold in a processing script.")
    print("  No cliff means the ground rate tapers to the edge of the sweep, "
          "which is accuracy.")


def _rows_from_csv(suffix=""):
    """Rebuild the figure inputs from the measurement CSVs.

    The measurement costs 95 s a tile. Redrawing must not.
    """
    f_sum = CSV / f"scan_angle_cliff_by_acquisition{suffix}.csv"
    f_crv = CSV / f"scan_angle_rate_curves{suffix}.csv"
    df = pd.read_csv(f_sum)
    crv = pd.read_csv(f_crv)
    if "block" not in df:
        df["block"] = [f"{_short(a)} {str(d)[:7]}"
                       for a, d in zip(df.area, df.flown)]
    mid = 0.5 * (EDGES[:-1] + EDGES[1:])
    rows = []
    for _, r in df.iterrows():
        g = crv[crv.tile == r.tile]
        rate = np.full(mid.size, np.nan)
        npool = np.zeros(mid.size, dtype=int)
        idx = np.searchsorted(mid, g.angle.values)
        ok = (idx < mid.size) & np.isclose(mid[np.clip(idx, 0, mid.size - 1)],
                                           g.angle.values)
        rate[idx[ok]] = g.pct_called_ground.values[ok] / 100.0
        npool[idx[ok]] = g.at_ground_returns.values[ok]
        rows.append(dict(r, rate=rate, n_pool=npool))
    return rows, df


def _figure(rows, df, suffix=""):
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE,
                         "font.family": "DejaVu Sans", "text.color": INK})
    mid = 0.5 * (EDGES[:-1] + EDGES[1:])

    # A block that records no scan angle has nothing to say about a scan-angle
    # threshold. Venango 2011-09 is such a block; drop it and say so.
    no_angle = sorted({r["block"] for r in rows if not np.isfinite(r["max_ang"])
                       or r["max_ang"] < 1.0})
    rows = [r for r in rows if r["block"] not in no_angle]
    df = df[~df.block.isin(no_angle)]
    if not rows:
        raise SystemExit("every block was dropped for having no scan angle")

    blocks = sorted({r["block"] for r in rows},
                    key=lambda b: -sum(x["block"] == b for x in rows))
    cmap = {b: BLOCK_COLOURS[i % len(BLOCK_COLOURS)] for i, b in enumerate(blocks)}

    fig, ax = plt.subplots(1, 2, figsize=(16.6, 7.2),
                           gridspec_kw={"width_ratios": [1.6, 1]})

    # enough opacity that a single square still reads as ITS BATCH'S
    # colour rather than a neutral tint; 183 of them still stack legibly
    handles, labels = [], []
    faint = 0.85 if len(rows) <= 20 else float(np.clip(11.0 / len(rows),
                                                       0.07, 0.85))
    for b in blocks:
        col = cmap[b]
        sub = [r for r in rows if r["block"] == b]
        for r in sub:
            ok = np.isfinite(r["rate"])
            ax[0].plot(mid[ok], 100 * r["rate"][ok], color=col,
                       linewidth=0.9, alpha=faint, zorder=2)
        stack = np.vstack([r["rate"] for r in sub]) * 100

        # Past the edge of the sweep only a handful of squares still have
        # returns, and a median over those few says nothing about the block --
        # it was drawing the 16 wide-sweep squares as if the whole block
        # recovered after the cliff. Require half the block to be present.
        cover = np.isfinite(stack).sum(axis=0) / len(sub)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            med = np.nanmedian(stack, axis=0)
            lo = np.nanpercentile(stack, 10, axis=0)
            hi = np.nanpercentile(stack, 90, axis=0)
        ok = np.isfinite(med) & (cover >= 0.5)
        plural = "s" if len(sub) > 1 else ""
        if len(sub) > 1:
            ax[0].fill_between(mid[ok], lo[ok], hi[ok], color=col, alpha=0.16,
                               linewidth=0, zorder=3)
        ax[0].plot(mid[ok], med[ok], color=col, linewidth=3.0, zorder=4,
                   solid_capstyle="round")
        handles.append((Line2D([], [], color=col, linewidth=1.0, alpha=0.75),
                        Line2D([], [], color=col, linewidth=3.4)))
        labels.append(f"{b}   ({len(sub)} map square{plural})")
    ax[0].set_ylim(-4, 108)
    ax[0].set_xlim(0, float(df.max_ang.max()) + 1.5)
    ax[0].set_xlabel("off-nadir scan angle, degrees", fontsize=11.5, color=INK2)
    ax[0].set_ylabel("share classified as ground, %", fontsize=11.5, color=INK2)
    ax[0].set_title("Of the returns that reached the ground,\nhow many became "
                    "class 2", fontsize=15, fontweight="bold", loc="left", pad=9)
    leg = ax[0].legend(handles, labels, frameon=True, fontsize=10.5,
                       loc="lower left", facecolor=SURFACE, edgecolor=RULE,
                       framealpha=0.95, handlelength=4.6, handletextpad=1.0,
                       handler_map={tuple: HandlerTuple(ndivide=None, pad=0.5)},
                       title="  one square │ all of them",
                       title_fontsize=9.5, alignment="left")
    leg.get_title().set_color(MUTED)
    leg.get_frame().set_linewidth(0.7)
    if len(rows) > 20:
        ax[0].text(0.015, 0.045,
                   "Every faint line is one map square, in its own batch's "
                   "colour. The thick line of that colour is the middle of\n"
                   "them, drawn only where at least half the batch still has "
                   "returns; the band holds the middle 80%.",
                   transform=ax[0].transAxes, ha="left", va="bottom",
                   fontsize=9.5, color=MUTED, linespacing=1.6)
        leg.set_bbox_to_anchor((0.0, 0.115), transform=ax[0].transAxes)

    # right: where each square's cliff sits, one dot per square
    for i, b in enumerate(blocks):
        g = df[df.block == b]
        col = cmap[b]
        rng = np.random.default_rng(7)
        y = i + rng.uniform(-0.24, 0.24, len(g))
        cut = g.cut.values.astype(float)
        has = np.isfinite(cut)
        ax[1].scatter(g.max_ang.values, y, s=44, facecolor="none",
                      edgecolor=col, linewidth=1.2, alpha=0.5, zorder=2)
        if has.any():
            ax[1].scatter(cut[has], y[has], s=62, color=col, zorder=4,
                          edgecolor=SURFACE, linewidth=0.9, alpha=0.9)
            # the barred band, block median
            lo_, hi_ = float(np.nanmedian(cut[has])), float(g.max_ang.median())
            ax[1].annotate("", xy=(hi_, i - 0.36), xytext=(lo_, i - 0.36),
                           arrowprops=dict(arrowstyle="<->", color=col,
                                           linewidth=1.4, shrinkA=0, shrinkB=0))
            ax[1].text(0.5 * (lo_ + hi_), i - 0.44,
                       f"{hi_ - lo_:.1f}° barred", ha="center", va="top",
                       fontsize=9.5, color=col, fontweight="bold")
        if (~has).any():
            ax[1].scatter(np.full((~has).sum(), 0.7), y[~has], s=52,
                          color=col, marker="x", linewidth=1.8, zorder=3,
                          alpha=0.75)
    ax[1].set_yticks(range(len(blocks)))
    ax[1].set_yticklabels([f"{b}\n{int((df.block == b).sum())} squares"
                           for b in blocks], fontsize=10)
    ax[1].set_xlabel("degrees off nadir", fontsize=11.5, color=INK2)
    ax[1].set_title("Filled = where ground stops\nHollow = widest angle flown",
                    fontsize=15, fontweight="bold", loc="left", pad=9)
    ax[1].text(0.97, 0.97, "× at zero = no cliff;\nground runs to the edge "
               "of the sweep", transform=ax[1].transAxes, fontsize=9.5,
               color=MUTED, ha="right", va="top", linespacing=1.5)
    ax[1].set_ylim(-0.75, len(blocks) - 0.35)
    ax[1].set_xlim(0, float(df.max_ang.max()) + 2)

    for a in ax:
        a.grid(color=RULE, linewidth=0.6, alpha=0.7)
        a.set_axisbelow(True)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            a.spines[sp].set_color(RULE)
        a.tick_params(colors=INK2, labelsize=10.5)
    if no_angle:
        fig.text(0.055, 0.018, "Excluded: " + ", ".join(no_angle) +
                 " — these squares record no scan angle at all, so the "
                 "question cannot be asked of them.",
                 fontsize=9.5, color=MUTED, ha="left")
    fig.subplots_adjust(left=0.055, right=0.985, top=0.855,
                        bottom=0.135 if no_angle else 0.115, wspace=0.30)
    p = OUT / f"scan_angle_cliff_by_survey{suffix}.png"
    fig.savefig(p, dpi=190)
    plt.close(fig)
    print(f"wrote {p}")


if __name__ == "__main__":
    sys.exit(main())
