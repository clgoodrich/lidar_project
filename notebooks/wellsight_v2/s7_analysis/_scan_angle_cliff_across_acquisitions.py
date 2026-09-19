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

Run:
    python notebooks/wellsight_v2/s7_analysis/_scan_angle_cliff_across_acquisitions.py
    ... --n-per-area 6
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRCROOT = ROOT / "data" / "_source" / "lidar"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "scan_angle"
CSV = ROOT / "data" / "9t" / "results" / "nonground_classification"
PDAL = "pdal"

NEAR = 0.15
STEP = 3             # decimation; a ratio per angle bin is unaffected
EDGES = np.arange(0, 30.5, 1.0)

SURFACE, INK, INK2, MUTED, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a887e", "#d8d7cf"
BLUE, VERM, GREEN, GREY = "#1F5FA8", "#C43E1C", "#4FA352", "#B0B0B0"

#: (label, directory, colour). Keep the two deliveries visually distinct --
#: the whole question is whether they behave the same.
AREAS = [
    ("PA WesternPA 2019 D20  (Venango, QL2)", "westernpa", BLUE),
    ("PA Northcentral 2019 B19  (McKean, QL1)", "mckean", VERM),
]


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-area", type=int, default=6)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    CSV.mkdir(parents=True, exist_ok=True)

    rows = []
    for label, sub, col in AREAS:
        files = [f for f in sorted((SRCROOT / sub).rglob("*.laz"))
                 if not f.name.startswith("_merged")]
        if not files:
            print(f"!! no tiles under {SRCROOT / sub}")
            continue
        # spread the sample across the directory rather than taking a
        # contiguous block, which could sit inside one flight line
        pick = files[:: max(1, len(files) // args.n_per_area)][:args.n_per_area]
        print(f"\n=== {label}   {len(files)} tiles available, sampling "
              f"{len(pick)}")
        for f in pick:
            code = re.search(r"(e\d+n\d+|17T..\d{6})", f.name)
            code = code.group(1) if code else f.stem[-10:]
            try:
                r = measure(f)
            except Exception as e:
                print(f"    {code:14s} FAILED  {e}")
                continue
            r.update(area=label, colour=col, tile=code)
            rows.append(r)
            c = f"{r['cut']:.0f} deg" if np.isfinite(r["cut"]) else "none"
            print(f"    {code:14s} {r['points']:>11,} pts  {r['lines']:>2d} lines"
                  f"  flown {r['flown']}  ground {r['ground_pct']:4.1f}%"
                  f"  max|ang| {r['max_ang']:4.1f}  cliff {c:>7s}"
                  f"  lost {r['lost']:>9,}")

    if not rows:
        raise SystemExit("nothing measured")
    df = pd.DataFrame([{k: v for k, v in r.items()
                        if k not in ("rate", "n_pool")} for r in rows])
    df.to_csv(CSV / "scan_angle_cliff_by_acquisition.csv", index=False)
    _report(df)
    _figure(rows, df)
    print(f"\nwrote {CSV / 'scan_angle_cliff_by_acquisition.csv'}")
    return 0


def _report(df):
    line = "=" * 78
    print(f"\n{line}\nDOES THE CLIFF REPEAT?\n{line}")
    for area, g in df.groupby("area"):
        have = g.cut.notna()
        print(f"\n  {area}")
        print(f"    tiles measured        : {len(g)}")
        print(f"    tiles with a cliff    : {int(have.sum())} of {len(g)}")
        if have.any():
            v = g.cut[have]
            print(f"    cutoff                : {v.min():.0f}-{v.max():.0f} deg"
                  f"  (median {v.median():.0f})")
            print(f"    at-ground returns lost: {int(g.lost.sum()):,} across "
                  f"{len(g)} tiles, {int(g.lost.sum()/len(g)):,} per tile")
        print(f"    max |scan angle|      : {g.max_ang.min():.1f}-"
              f"{g.max_ang.max():.1f} deg")
        print(f"    ground share          : {g.ground_pct.min():.1f}-"
              f"{g.ground_pct.max():.1f}%")


def _figure(rows, df):
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE,
                         "font.family": "DejaVu Sans", "text.color": INK})
    mid = 0.5 * (EDGES[:-1] + EDGES[1:])
    fig, ax = plt.subplots(1, 2, figsize=(16.6, 7.2),
                           gridspec_kw={"width_ratios": [1.5, 1]})

    seen = set()
    for r in rows:
        ok = np.isfinite(r["rate"])
        lab = r["area"] if r["area"] not in seen else None
        seen.add(r["area"])
        ax[0].plot(mid[ok], 100 * r["rate"][ok], color=r["colour"],
                   linewidth=1.9, alpha=0.85, label=lab)
    ax[0].set_ylim(-3, 103)
    ax[0].set_xlim(0, float(df.max_ang.max()) + 1.5)
    ax[0].set_xlabel("off-nadir scan angle, degrees", fontsize=11.5, color=INK2)
    ax[0].set_ylabel("share classified as ground, %", fontsize=11.5, color=INK2)
    ax[0].set_title("Of the returns that reached the ground,\nhow many became "
                    "class 2", fontsize=15, fontweight="bold", loc="left",
                    pad=9)
    ax[0].legend(frameon=False, fontsize=10.5, loc="lower left")

    # right: where each tile's cliff sits, one dot per tile
    areas = list(dict.fromkeys(df.area))
    for i, a in enumerate(areas):
        g = df[df.area == a]
        col = g.colour.iloc[0]
        y = np.full(len(g), i) + np.linspace(-0.16, 0.16, len(g))
        cut = g.cut.fillna(-1).values
        has = cut > 0
        ax[1].scatter(cut[has], y[has], s=95, color=col, zorder=3,
                      edgecolor=SURFACE, linewidth=1.4)
        if (~has).any():
            ax[1].scatter(np.full((~has).sum(), 0.6), y[~has], s=95,
                          color=col, marker="x", linewidth=2.2, zorder=3)
        ax[1].scatter(g.max_ang.values, y, s=48, facecolor="none",
                      edgecolor=col, linewidth=1.4, zorder=2)
    ax[1].set_yticks(range(len(areas)))
    ax[1].set_yticklabels([a.split("  (")[0] + "\n(" + a.split("  (")[1]
                           for a in areas], fontsize=10)
    ax[1].set_xlabel("degrees off nadir", fontsize=11.5, color=INK2)
    ax[1].set_title("Filled = the cliff.  Hollow = widest angle flown.\n"
                    "× = no cliff found", fontsize=15, fontweight="bold",
                    loc="left", pad=9)
    ax[1].set_ylim(-0.6, len(areas) - 0.4)
    ax[1].set_xlim(0, float(df.max_ang.max()) + 2)

    for a in ax:
        a.grid(color=RULE, linewidth=0.6, alpha=0.7)
        a.set_axisbelow(True)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            a.spines[sp].set_color(RULE)
        a.tick_params(colors=INK2, labelsize=10.5)
    fig.subplots_adjust(left=0.055, right=0.985, top=0.855, bottom=0.095,
                        wspace=0.32)
    p = OUT / "ground_classification_cliff_by_acquisition.png"
    fig.savefig(p, dpi=190)
    plt.close(fig)
    print(f"wrote {p}")


if __name__ == "__main__":
    sys.exit(main())
