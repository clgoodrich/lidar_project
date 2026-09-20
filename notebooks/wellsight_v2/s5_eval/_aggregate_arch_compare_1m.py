"""Aggregate the 1 m architecture comparison that was trained but never scored.

WHY THIS EXISTS
---------------
`s3_train/_arch_compare_9t_1m.py` trains one architecture against one target and
writes `pooled_metrics.json` -- but ONLY when a single invocation finishes every
fold it was asked for. Two of the nine runs died partway (pad/unetpp_r34_imagenet
to a host-RAM MemoryError on fold 2, roaddrain/unet after fold 0), so they have
finished folds on disk and no pooled file at all. Reading the pooled files would
therefore silently drop completed work.

This reads the FOLDS, not the pooled summaries. A fold counts as finished when it
has both `best.pt` and a `train_log.csv` with the full epoch count; anything less
is reported as partial and excluded from the means, by name, rather than quietly
averaged in.

WHAT THE NUMBER IS -- AND IS NOT
--------------------------------
The score here is **inner-validation IoU of the target class**, taken at each
fold's best epoch. That is what the comparison was designed around: the four
architectures form a ladder where each rung isolates one variable

    unet                 -> r34_scratch          encoder DEPTH
    r34_scratch          -> r34_imagenet         ImageNet PRETRAINING
    r34_imagenet         -> unetpp_r34_imagenet  DENSE SKIP CONNECTIONS

and IoU on a held-back fold is a fair way to rank them against each other.

It is **not** comparable to the numbers in LEADERBOARD.md. Those are held-out
DETECTION metrics -- recall and precision at IoU 0.3 after polygonising a
probability raster -- computed at 0.5 m. These runs are segmentation IoU at 1 m.
Different grid, different quantity. `_score_arch_compare_heldout_1m.py` is what
closes that gap; this script deliberately does not pretend to.

COLOUR
------
Four architectures sit side by side as bars the reader compares, so this is a
CATEGORICAL palette and takes the categorical checks -- not the monotonic-
lightness check a sequential ramp would get.

A single-hue blue ramp was tried first, on the reasoning that the four
architectures form an ordered ladder. The validator rejected it:

    "#9dbde0,#4a87c8,#1f5fa8,#0d3057"  --mode light --pairs all
    FAIL lightness band, FAIL chroma floor,
    FAIL normal-vision floor: #1f5fa8 <-> #4a87c8 dE 12.8, below the 15 hard
    floor -- readers with full colour vision cannot separate that pair either.

So the ladder is carried by position and label, and the colour is four hues from
the dataviz reference categorical theme, slots 1/2/3/7:

    node scripts/validate_palette.js \
      "#2a78d6,#eb6834,#1baf7a,#4a3aa7" --mode light --pairs all
    -> ALL CHECKS PASS
       CVD separation      worst all-pairs #1baf7a <-> #eb6834 dE 9.2 deutan,
                           9.6 tritan   (target >= 8)
       Normal-vision floor worst all-pairs #4a3aa7 <-> #2a78d6 dE 16.3
       WARN contrast       #1baf7a 2.74 against the paper

No red is present. The orange/aqua pair is the colourblind-safe substitute FOR a
red/green pair, and the validator's 9.2 dE under deuteranopia is the evidence --
a real red/green pair collapses to about 2 there.

The contrast WARN on aqua obligates relief, which this figure has: every bar
carries its value above it and its fold count inside it, every line is directly
labelled at its right end, and each architecture keeps one marker shape
throughout. Nothing here rests on hue alone.

Run:
    python notebooks/wellsight_v2/s5_eval/_aggregate_arch_compare_1m.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "data/9t/models/_arch_compare/1m"
OUTDIR = ROOT / "data/9t/results/arch_compare_1m"
FIGDIR = ROOT / "docs/presentation/figures_30to45min/4_models"

EPOCHS = 40

#: The ladder, in the order the rungs are meant to be read.
ARCHS = ["unet", "r34_scratch", "r34_imagenet", "unetpp_r34_imagenet"]
NICE = {"unet": "U-Net (plain)",
        "r34_scratch": "ResNet-34, from scratch",
        "r34_imagenet": "ResNet-34, ImageNet",
        "unetpp_r34_imagenet": "U-Net++, ResNet-34 ImageNet"}
#: Two short lines for the x axis. The full names in NICE collide at this
#: figure width -- "ResNet-34, ImageNet" ran straight into its neighbour.
TICK = {"unet": "U-Net\nplain",
        "r34_scratch": "ResNet-34\nscratch",
        "r34_imagenet": "ResNet-34\nImageNet",
        "unetpp_r34_imagenet": "U-Net++\nR34 ImageNet"}
TARGETS = ["pit", "pad", "roaddrain"]
#: Which IoU column each target is scored on, matching score_cls in the trainer.
SCORED = {"pit": "iou_floor", "pad": "iou_pad", "roaddrain": "iou_road"}

#: dataviz reference categorical slots 1/2/3/7. ALL CHECKS PASS --pairs all:
#: CVD worst #1baf7a<->#eb6834 dE 9.2 deutan / 9.6 tritan; normal-vision worst
#: #4a3aa7<->#2a78d6 dE 16.3; WARN contrast #1baf7a 2.74, relieved by the
#: value labels, fold counts, marker shapes and direct line labels below.
RAMP = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"]
MARKS = ["o", "s", "^", "D"]
PAPER, INK, INK2, MUTED, RULE = "#f7f8f6", "#141a1f", "#545c63", "#8a887e", "#c9ccc6"


def read_folds(target: str, arch: str) -> tuple[list[dict], list[str]]:
    """Every fold on disk for one run, split into finished and partial."""
    d = BASE / target / arch
    rows, partial = [], []
    if not d.exists():
        return rows, partial
    for fd in sorted(d.glob("fold*")):
        log, ckpt = fd / "train_log.csv", fd / "best.pt"
        if not log.exists() or not ckpt.exists():
            partial.append(f"{fd.name} ({'no train_log' if ckpt.exists() else 'no checkpoint'})")
            continue
        t = pd.read_csv(log)
        if len(t) < EPOCHS:
            partial.append(f"{fd.name} ({len(t)}/{EPOCHS} epochs)")
            continue
        best = t.loc[t["score"].idxmax()]
        rows.append(dict(
            target=target, arch=arch, fold=int(fd.name.replace("fold", "")),
            best_epoch=int(best["epoch"]), score=float(best["score"]),
            va_loss=float(best["va_loss"]), minutes=float(t["sec"].sum() / 60),
            n_epochs=len(t)))
    return rows, partial


def curve(target: str, arch: str) -> np.ndarray | None:
    """Mean validation score per epoch across finished folds, for the figure."""
    d = BASE / target / arch
    cur = []
    for fd in sorted(d.glob("fold*")):
        log = fd / "train_log.csv"
        if not log.exists():
            continue
        t = pd.read_csv(log)
        if len(t) >= EPOCHS:
            cur.append(t["score"].to_numpy()[:EPOCHS])
    return np.mean(cur, axis=0) if cur else None


def figure(df: pd.DataFrame, path: Path) -> None:
    """Left: where each architecture lands. Right: how it got there."""
    tg = [t for t in TARGETS if (df.target == t).any()]
    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, axes = plt.subplots(2, len(tg), figsize=(6.4 * len(tg), 10.4),
                             squeeze=False)

    for j, t in enumerate(tg):
        sub = df[df.target == t]
        ax = axes[0][j]
        present = [a for a in ARCHS if (sub.arch == a).any()]
        xs = np.arange(len(present))
        means = [sub[sub.arch == a]["score"].mean() for a in present]
        sds = [sub[sub.arch == a]["score"].std(ddof=0) for a in present]
        cols = [RAMP[ARCHS.index(a)] for a in present]
        ax.bar(xs, means, yerr=sds, color=cols, width=0.62, zorder=3,
               error_kw=dict(ecolor=INK2, capsize=5, lw=1.4))
        # every fold as a dot, so five folds are never hidden behind one bar
        for i, a in enumerate(present):
            v = sub[sub.arch == a]["score"].to_numpy()
            ax.scatter(np.full(len(v), xs[i]) + np.linspace(-.13, .13, len(v)),
                       v, s=26, facecolor="white", edgecolor=INK, zorder=5,
                       linewidth=1.1, marker=MARKS[ARCHS.index(a)])
            ax.text(xs[i], means[i] + sds[i] + 0.016, f"{means[i]:.3f}",
                    ha="center", va="bottom", fontsize=12.5, fontweight="bold",
                    color=INK, zorder=6)
            ax.text(xs[i], 0.012, f"n={len(v)}", ha="center", va="bottom",
                    fontsize=10.5, color="white", zorder=6)
        ax.set_xticks(xs)
        ax.set_xticklabels([TICK[a] for a in present], fontsize=11)
        ax.set_ylim(0, max(np.array(means) + np.array(sds)) * 1.22)
        ax.set_ylabel(f"{SCORED[t].replace('iou_', '')} IoU, held-back fold",
                      fontsize=12)
        ax.set_title(t, fontsize=16, fontweight="bold", loc="left", color=INK)
        ax.grid(axis="y", color=RULE, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

        ax2 = axes[1][j]
        ends = []
        for a in present:
            c = curve(t, a)
            if c is None:
                continue
            i = ARCHS.index(a)
            ax2.plot(np.arange(1, len(c) + 1), c, color=RAMP[i], linewidth=2.0,
                     marker=MARKS[i], markersize=4.5, markevery=6, zorder=3)
            ends.append([float(c[-1]), a, i, len(c)])
        # The four curves converge, so labels placed at their own end values
        # overprint (U-Net and U-Net++ sat on top of each other). Push them
        # apart top-down by a minimum gap, then draw a leader to the true end.
        if ends:
            lo = min(e[0] for e in ends)
            hi = max(e[0] for e in ends)
            gap = max((hi - lo), 1e-6) * 0.55 + (hi - lo) * 0.0
            gap = max(gap, (hi - lo) if (hi - lo) > 0 else 0.01)
            step = max(gap / max(len(ends) - 1, 1), (hi - lo) * 0.42, 0.006)
            ends.sort(key=lambda e: -e[0])
            placed, prev = [], None
            for y, a, i, n in ends:
                yy = y if prev is None else min(y, prev - step)
                placed.append((yy, y, a, i, n))
                prev = yy
            for yy, y, a, i, n in placed:
                ax2.plot([n, n + 1.6], [y, yy], color=RAMP[i], linewidth=1.0,
                         zorder=2)
                ax2.text(n + 2.2, yy, NICE[a], color=RAMP[i], fontsize=10.5,
                         va="center", fontweight="bold")
        ax2.set_xlim(1, EPOCHS * 1.62)
        ax2.set_xlabel("epoch", fontsize=12)
        ax2.set_ylabel("validation IoU (mean of folds)", fontsize=12)
        ax2.grid(color=RULE, linewidth=0.8, zorder=0)
        ax2.set_axisbelow(True)
        for s in ("top", "right"):
            ax2.spines[s].set_visible(False)

    fig.suptitle("Four architectures on the same folds, same channels, "
                 "same 40 epochs", fontsize=21, fontweight="bold", x=0.012,
                 ha="left", y=0.985)
    fig.text(0.012, 0.947,
             "Validation IoU of the scored class at each fold's best epoch. "
             "Bars are the mean over folds,\nwhiskers one standard deviation, "
             "dots the individual folds. This is segmentation overlap at 1 m, "
             "not the\nheld-out detection recall in LEADERBOARD.md, which is "
             "computed at 0.5 m.",
             fontsize=12.5, color=INK2, va="top", linespacing=1.5)
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    a = ap.parse_args()
    globals()["EPOCHS"] = a.epochs

    rows, partials = [], {}
    for t in TARGETS:
        for arch in ARCHS:
            r, p = read_folds(t, arch)
            rows += r
            if p:
                partials[f"{t}/{arch}"] = p
    if not rows:
        raise SystemExit(f"no finished folds under {BASE}")
    df = pd.DataFrame(rows)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    per_fold = OUTDIR / "arch_compare_per_fold_9t_1m.csv"
    df.sort_values(["target", "arch", "fold"]).to_csv(per_fold, index=False)

    g = (df.groupby(["target", "arch"])
           .agg(n_folds=("fold", "count"), iou_mean=("score", "mean"),
                iou_sd=("score", lambda v: float(np.std(v))),
                iou_min=("score", "min"), iou_max=("score", "max"),
                minutes=("minutes", "sum"))
           .reset_index())
    g["arch_order"] = g["arch"].map({a: i for i, a in enumerate(ARCHS)})
    g = g.sort_values(["target", "arch_order"]).drop(columns="arch_order")
    summ = OUTDIR / "arch_compare_summary_9t_1m.csv"
    g.to_csv(summ, index=False)

    print(f"{'target':10s} {'architecture':28s} {'folds':>5s} {'IoU':>7s} "
          f"{'sd':>6s} {'min':>6s} {'max':>6s} {'GPU min':>8s}")
    print("-" * 80)
    for _, r in g.iterrows():
        print(f"{r.target:10s} {NICE[r.arch]:28s} {r.n_folds:5.0f} "
              f"{r.iou_mean:7.3f} {r.iou_sd:6.3f} {r.iou_min:6.3f} "
              f"{r.iou_max:6.3f} {r.minutes:8.0f}")

    # The ladder: each rung is one isolated change. Reported with the spread,
    # because a gain smaller than a fold-to-fold sd is not a gain.
    print("\nladder (each step changes exactly one thing)")
    steps = [("unet", "r34_scratch", "deeper encoder"),
             ("r34_scratch", "r34_imagenet", "ImageNet pretraining"),
             ("r34_imagenet", "unetpp_r34_imagenet", "dense skip connections")]
    ladder = []
    for t in TARGETS:
        s = g[g.target == t]
        for lo, hi, what in steps:
            a, b = s[s.arch == lo], s[s.arch == hi]
            if a.empty or b.empty:
                continue
            d = float(b.iou_mean.iloc[0] - a.iou_mean.iloc[0])
            pooled_sd = float(np.hypot(a.iou_sd.iloc[0], b.iou_sd.iloc[0]))
            verdict = "within noise" if abs(d) < pooled_sd else \
                      ("HELPS" if d > 0 else "HURTS")
            ladder.append(dict(target=t, step=what, delta_iou=d,
                               pooled_sd=pooled_sd, verdict=verdict))
            print(f"  {t:10s} {what:24s} {d:+.3f}  (pooled sd {pooled_sd:.3f})"
                  f"  {verdict}")

    pd.DataFrame(ladder).to_csv(OUTDIR / "arch_compare_ladder_9t_1m.csv",
                                index=False)

    if partials:
        print("\nEXCLUDED as unfinished (not averaged in):")
        for k, v in partials.items():
            print(f"  {k}: {', '.join(v)}")
    (OUTDIR / "arch_compare_unfinished_9t_1m.json").write_text(
        json.dumps(partials, indent=2), encoding="utf-8")

    fig_path = FIGDIR / "arch_compare_four_architectures_9t_1m.png"
    figure(df, fig_path)

    print(f"\n  {per_fold}")
    print(f"  {summ}")
    print(f"  {OUTDIR / 'arch_compare_ladder_9t_1m.csv'}")
    print(f"  {OUTDIR / 'arch_compare_unfinished_9t_1m.json'}")
    print(f"  {fig_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
