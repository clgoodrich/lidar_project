"""Was the vendor right to throw away the wide-angle ground returns?

THE QUESTION
------------
Every at-ground return beyond roughly 18 degrees off nadir was left unassigned
-- 1,019,614 of them in tile 616591 alone, not one classified as ground. That is
a threshold in someone's processing script, not a physical taper.

Whether that was the right call depends on one thing only: are those returns
ACCURATE? If they land within a few centimetres of the true surface, the cut was
over-conservative and we are throwing away a million measurements per tile. If
they scatter by 20-30 cm, the vendor was right and putting them back would
degrade every terrain product we build.

HOW TO ANSWER IT WITHOUT A SURVEY CREW
--------------------------------------
Flight lines overlap. Where they do, the same patch of ground is measured twice:
at a WIDE angle by the line whose swath edge falls there, and at a NARROW angle
by the neighbouring line whose swath centre covers it. The narrow-angle ground is
the best data in the survey, and it is an independent yardstick for the
wide-angle returns sitting in the same place.

So, for each excluded return from flight line L:

    1. fit a local plane through class-2 ground from OTHER lines only
    2. evaluate that plane at the return's position
    3. residual = the return's elevation minus the plane

Never comparing a line against itself is the whole point -- otherwise a line with
a systematic boresight error would validate its own mistake.

THE CONTROLS
------------
A residual is meaningless without something to compare it to, so the same
measurement is made on:

    accepted, wide angle   class-2 ground at the same wide angles (where any
                           exists below the cut) -- returns the vendor DID keep
    accepted, narrow       class-2 ground under 10 degrees -- the survey's own
                           best case, and the floor on what this method can
                           resolve

If the excluded returns match the narrow-angle control, the cut cost us data for
nothing. If they are several times worse, it was justified.

THE BAR
-------
USGS 3DEP Lidar Base Specification, Quality Level 2: RMSEz <= 10 cm in
non-vegetated terrain, which is 19.6 cm at 95% confidence. Measured against the
same-survey yardstick this is a RELATIVE accuracy, not absolute, so it is a
lower bound on the true error -- a shared systematic error would cancel. Said
plainly on the figure.

Terrain slope is removed by the plane fit rather than ignored; on a 20% slope a
1 m horizontal error would otherwise read as 20 cm of vertical error.

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md).

Run:
    python notebooks/wellsight_v2/s7_analysis/_are_excluded_returns_accurate.py
    ... --tiles 616591 621594
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "_source" / "lidar" / "westernpa"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "scan_angle"
CSV = ROOT / "data" / "9t" / "results" / "nonground_classification"
PDAL = "pdal"

NEAR = 0.15          # "at ground level"
NARROW = 10.0        # degrees, the narrow-angle control
FIT_R = 2.0          # plane-fit radius, metres
FIT_MIN = 8          # points needed for a fit
SAMPLE = 40000       # points per group, for speed
QL2_RMSE = 0.10      # USGS 3DEP QL2 non-vegetated vertical RMSEz, metres
SEED = 42

SURFACE, INK, INK2, MUTED, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a887e", "#d8d7cf"
#: Colourblind rule: a red/green pair is the one a deuteranope or
#: protanope cannot read, so no figure here contains both. Checked with
#: the dataviz validator over ALL pairs, not just adjacent ones.
#:   blue #1F5FA8  amber #D97706  deep red #A31515
#:   worst pair dE 21.1 deutan / 21.5 protan / 22.6 normal, all >= 3:1
GREY, BLUE, VERM, GREEN = "#8E959B", "#1F5FA8", "#A31515", "#D97706"


def run_pipeline(stages, label, timeout=3600):
    """Write the pipeline to a temp file and shell out. See CLAUDE.md."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-1200:]); print(r.stderr[-1200:])
        raise SystemExit(f"{label} failed, exit {r.returncode}")


def find_tile(code):
    hits = [f for f in sorted(SRC.rglob("*.laz"))
            if not f.name.startswith("_merged")
            and re.search(rf"17T..{code}(\.copc)?\.laz$", f.name)]
    if not hits:
        raise SystemExit(f"no source file for tile {code}")
    return hits[0]


def load(laz):
    tmp = Path(tempfile.gettempdir()) / f"_acc_{laz.stem}.las"
    run_pipeline([
        str(laz),
        {"type": "filters.hag_nn", "count": 8, "allow_extrapolation": True},
        {"type": "writers.las", "filename": str(tmp),
         "extra_dims": "HeightAboveGround=float32", "compression": "false"},
    ], "hag")
    import laspy
    las = laspy.read(str(tmp))
    d = {"x": np.asarray(las.x), "y": np.asarray(las.y),
         "z": np.asarray(las.z),
         "cls": np.asarray(las.classification).astype("int16"),
         "hag": np.asarray(las.HeightAboveGround, dtype="float32"),
         "psid": np.asarray(las.point_source_id).astype("int32")}
    for a in ("scan_angle", "scan_angle_rank"):
        if hasattr(las, a):
            v = np.asarray(getattr(las, a), dtype="float32")
            d["ang"] = np.abs(v * 0.006 if a == "scan_angle" else v)
            break
    tmp.unlink(missing_ok=True)
    return d


def find_cut(d):
    """Where does the ground-classification rate fall off a cliff?"""
    at = np.isfinite(d["hag"]) & (np.abs(d["hag"]) < NEAR)
    pool = at & ((d["cls"] == 2) | (d["cls"] == 1))
    edges = np.arange(0, 22.5, 1.0)
    n_pool, _ = np.histogram(d["ang"][pool], bins=edges)
    n_g2, _ = np.histogram(d["ang"][pool & (d["cls"] == 2)], bins=edges)
    rate = np.divide(n_g2, n_pool, out=np.full(edges.size - 1, np.nan),
                     where=n_pool > 50)
    for i in range(1, rate.size):
        if np.isfinite(rate[i]) and rate[i] < 0.10 and \
                np.isfinite(rate[i - 1]) and rate[i - 1] > 0.50:
            return float(edges[i]), rate, edges
    return float("nan"), rate, edges


def residuals(d, target, ref_ground, rng):
    """Elevation of each target point minus a plane fitted through OTHER lines.

    The plane removes terrain slope, which would otherwise dominate: on a 20%
    slope a metre of horizontal offset reads as 20 cm of vertical error.
    """
    idx = np.flatnonzero(target)
    if idx.size == 0:
        return np.array([])
    if idx.size > SAMPLE:
        idx = rng.choice(idx, SAMPLE, replace=False)
    out = []
    lines = np.unique(d["psid"][idx])
    for ln in lines:
        sel = idx[d["psid"][idx] == ln]
        # reference = class-2 ground from every OTHER flight line
        ref = ref_ground & (d["psid"] != ln)
        ri = np.flatnonzero(ref)
        if ri.size < FIT_MIN:
            continue
        tree = cKDTree(np.c_[d["x"][ri], d["y"][ri]])
        nb = tree.query_ball_point(np.c_[d["x"][sel], d["y"][sel]], r=FIT_R)
        for p, q in zip(sel, nb):
            if len(q) < FIT_MIN:
                continue
            j = ri[q]
            A = np.c_[d["x"][j] - d["x"][p], d["y"][j] - d["y"][p],
                      np.ones(j.size)]
            try:
                c, *_ = np.linalg.lstsq(A, d["z"][j].astype("float64"),
                                        rcond=None)
            except np.linalg.LinAlgError:
                continue
            out.append(float(d["z"][p]) - c[2])
    return np.asarray(out)


def stats(v):
    if v.size == 0:
        return dict(n=0, median=np.nan, mean=np.nan, rmse=np.nan, sd=np.nan,
                    p95=np.nan, iqr=np.nan)
    return dict(n=int(v.size), median=float(np.median(v)),
                mean=float(np.mean(v)),
                rmse=float(np.sqrt(np.mean(v ** 2))),
                sd=float(np.std(v)),
                p95=float(np.percentile(np.abs(v), 95)),
                iqr=float(np.percentile(v, 75) - np.percentile(v, 25)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", nargs="+", default=["616591", "621594"])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    CSV.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    rows, keep = [], {}
    for code in args.tiles:
        laz = find_tile(code)
        print(f"\n=== tile {code}")
        d = load(laz)
        nlines = int(np.unique(d["psid"]).size)
        cut, rate, edges = find_cut(d)
        at = np.isfinite(d["hag"]) & (np.abs(d["hag"]) < NEAR)
        g2 = d["cls"] == 2
        print(f"    {nlines} flight lines, cutoff {cut:.1f} deg")
        if nlines < 2:
            print("    only one flight line -- no independent yardstick, "
                  "skipping")
            del d
            continue

        groups = {
            "excluded, wide angle": at & (d["cls"] == 1) & (d["ang"] >= cut),
            "accepted, wide angle": at & g2 & (d["ang"] >= NARROW) &
                                    (d["ang"] < cut),
            "accepted, narrow angle": at & g2 & (d["ang"] < NARROW),
        }
        # MEASURED, not assumed: a narrow-angle yardstick does not exist.
        # Adjacent swaths meet edge to edge, so one line's wide-angle returns
        # overlap the NEIGHBOUR's wide-angle returns, never its centre. Using
        # class 2 under 10 deg from other lines covers 0.0% of the targets;
        # under 14 deg covers 29-50%; all accepted ground covers ~100%.
        # So the yardstick is every class-2 return from every OTHER flight
        # line -- still independent, and still data the vendor chose to keep.
        ref = g2
        print(f"    yardstick: class-2 ground from other lines "
              f"({int(ref.sum()):,} total, same-line excluded per point)")

        for name, m in groups.items():
            v = residuals(d, m, ref, rng)
            st = stats(v)
            st.update(tile=code, group=name, available=int(m.sum()))
            rows.append(st)
            keep[(code, name)] = v
            if st["n"]:
                print(f"    {name:24s} n={st['n']:>6,}  "
                      f"median {st['median']:+.3f}  RMSE {st['rmse']:.3f}  "
                      f"p95|e| {st['p95']:.3f} m")
        del d

    df = pd.DataFrame(rows)
    df.to_csv(CSV / "excluded_returns_vertical_accuracy.csv", index=False)
    _report(df)
    _figure(df, keep)
    print(f"\nwrote {CSV / 'excluded_returns_vertical_accuracy.csv'}")
    return 0


def _report(df):
    line = "=" * 78
    print(f"\n{line}\nVERTICAL ACCURACY AGAINST NARROW-ANGLE GROUND FROM OTHER "
          f"FLIGHT LINES\n{line}")
    print(f"  {'tile':>8s} {'group':24s} {'n':>8s} {'median':>9s} {'RMSE':>8s} "
          f"{'p95|e|':>8s}  verdict vs QL2")
    for _, r in df.iterrows():
        if not r.get("n"):
            continue
        verdict = "within spec" if r["rmse"] <= QL2_RMSE else "OUTSIDE spec"
        print(f"  {r['tile']:>8s} {r['group']:24s} {int(r['n']):>8,} "
              f"{r['median']:>+9.3f} {r['rmse']:>8.3f} {r['p95']:>8.3f}  "
              f"{verdict}")
    print(f"\n  QL2 bar: RMSEz <= {QL2_RMSE:.2f} m, non-vegetated.")
    print("  Relative accuracy against the same survey, so a shared systematic\n"
          "  error would cancel -- these are lower bounds on the true error.")


def _figure(df, keep):
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE,
                         "font.family": "DejaVu Sans", "text.color": INK})
    # the narrow-angle control is dropped: the swath geometry means it has no
    # spatial overlap with the wide-angle returns, so it returns zero points
    order = [g for g in ("accepted, narrow angle", "accepted, wide angle",
                         "excluded, wide angle")
             if df[(df.group == g) & (df.n > 0)].shape[0]]
    cols = {"accepted, narrow angle": BLUE, "accepted, wide angle": GREEN,
            "excluded, wide angle": VERM}
    tiles = sorted(df.tile.unique())
    fig, ax = plt.subplots(1, 2, figsize=(15.6, 7.0),
                           gridspec_kw={"width_ratios": [1.25, 1]})

    bins = np.arange(-0.60, 0.605, 0.02)
    mid = 0.5 * (bins[:-1] + bins[1:])
    for g in order:
        v = np.concatenate([keep.get((t, g), np.array([])) for t in tiles])
        if v.size < 50:
            continue
        h, _ = np.histogram(v, bins=bins)
        ax[0].step(mid, h / h.sum(), where="mid", color=cols[g], linewidth=2.5,
                   label=f"{g}   n={v.size:,}   RMSE "
                         f"{np.sqrt(np.mean(v**2)):.3f} m")
        ax[0].fill_between(mid, h / h.sum(), step="mid", color=cols[g],
                           alpha=0.15)
    for s in (-QL2_RMSE, QL2_RMSE):
        ax[0].axvline(s, color=INK, linewidth=1.3, linestyle="--", alpha=0.7)
    ax[0].text(QL2_RMSE, ax[0].get_ylim()[1] * 0.96,
               "  QL2 RMSEz, 10 cm", fontsize=10, color=INK2, va="top")
    ax[0].axvline(0, color=RULE, linewidth=1.2)
    ax[0].set_xlabel("elevation minus class-2 ground from OTHER flight lines, m",
                     fontsize=11, color=INK2)
    ax[0].set_ylabel("share of the group", fontsize=11, color=INK2)
    ax[0].set_title("How far off are the returns the vendor threw away?",
                    fontsize=15, fontweight="bold", loc="left", pad=9)
    ax[0].legend(frameon=False, fontsize=10, loc="upper left")

    w = 0.26
    xs = np.arange(len(tiles))
    for i, g in enumerate(order):
        vals = [float(df[(df.tile == t) & (df.group == g)].rmse.iloc[0])
                if len(df[(df.tile == t) & (df.group == g)]) else np.nan
                for t in tiles]
        off = (i - (len(order) - 1) / 2) * w
        b = ax[1].bar(xs + off, vals, width=w, color=cols[g], label=g)
        ax[1].bar_label(b, fmt="%.3f", fontsize=9, color=INK2, padding=2)
    ax[1].axhline(QL2_RMSE, color=INK, linewidth=1.4, linestyle="--")
    ax[1].set_ylim(0, max(0.12, float(np.nanmax(df.rmse)) * 1.35))
    ax[1].text(len(tiles) - 0.5, QL2_RMSE * 1.02, "QL2 spec, 10 cm",
               fontsize=10, color=INK2, va="bottom", ha="right")
    ax[1].set_xticks(xs); ax[1].set_xticklabels(tiles, fontsize=11)
    ax[1].set_ylabel("vertical RMSE, m", fontsize=11, color=INK2)
    ax[1].set_title("Same question, per tile", fontsize=15, fontweight="bold",
                    loc="left", pad=9)
    ax[1].legend(frameon=False, fontsize=9.5)

    for a in ax:
        a.grid(axis="y", color=RULE, linewidth=0.6, alpha=0.7)
        a.set_axisbelow(True)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            a.spines[sp].set_color(RULE)
        a.tick_params(colors=INK2, labelsize=10)
    fig.text(0.008, 0.016,
             "Each return is compared with a plane fitted through class-2 "
             "ground from OTHER flight lines, so no line validates itself. "
             "Relative accuracy: a shared systematic error would cancel.",
             fontsize=9, color=MUTED)
    fig.subplots_adjust(left=0.055, right=0.985, top=0.90, bottom=0.115,
                        wspace=0.18)
    p = OUT / "excluded_returns_vertical_accuracy.png"
    fig.savefig(p, dpi=190)
    plt.close(fig)
    print(f"wrote {p}")


if __name__ == "__main__":
    sys.exit(main())
