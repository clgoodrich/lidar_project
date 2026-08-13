"""Precision / recall / F1 as a function of how strict the IoU match has to be.

The point of this figure is to stop any single IoU threshold having to be
defended as "the" number. A reader picks their own strictness and reads off the
score. Nothing is selected here.

CRITICAL: the probability/score threshold of each model is chosen ONCE on val at
IoU 0.3 and then held FIXED across every tau on the x-axis. Re-selecting the
operating point per tau would manufacture a flattering curve, which is exactly
what this figure exists to rule out.

Reads `metrics_9t.csv` written by `_reeval_instance_precision_9t.py`.

Run:
  python notebooks/wellsight_v2/s5_eval/_plot_iou_strictness_scale_9t.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = path_for("derivatives") / "eval_9t_instance_precision"
SRC = OUT / "metrics_9t.csv"

MODELS = ["pit_unet_v2", "plat_unet"]
COLORS = {"recall": "#1a9641", "precision": "#d7191c", "f1": "#2c7bb6"}


def main() -> int:
    df = pd.read_csv(SRC)

    fig, axs = plt.subplots(1, len(MODELS), figsize=(6.0 * len(MODELS), 4.6),
                            sharey=True)
    lines = []
    for ax, m in zip(axs, MODELS):
        g = df[df.model == m].sort_values("iou")
        thr = g.threshold.iloc[0]
        for k in ("recall", "precision", "f1"):
            ax.plot(g.iou, g[k], marker="o", ms=4, lw=1.8, color=COLORS[k],
                    label=k)
        ax.axvline(0.3, ls="--", lw=1.0, color="0.4")
        ax.text(0.305, 0.03, "IoU 0.30\n(reported)", fontsize=8, color="0.3")
        ax.set_title(f"{m}\nprob threshold {thr:.2f}, fixed across all IoU  "
                     f"(n_gt {g.n_gt_test.iloc[0]}, n_det {g.n_det_scored.iloc[0]})",
                     fontsize=10)
        ax.set_xlabel("IoU required to call a detection correct")
        ax.grid(alpha=0.3)
        ax.set_ylim(0, 1.0)
        ax.set_xlim(0, 0.95)
    axs[0].set_ylabel("score")
    axs[0].legend(loc="lower left", fontsize=9)
    fig.suptitle("How strict is 'correct'? Precision, recall and F1 vs the IoU "
                 "matching threshold\n"
                 "9t held-out test instances, hand-drawn ground truth, "
                 "operating point frozen on val",
                 fontsize=11)
    fig.tight_layout()
    p = OUT / "iou_strictness_scale_pit_pad_9t.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {p}")

    # markdown table, for pasting into docs
    md = ["| IoU required | pit R | pit P | pit F1 | pad R | pad P | pad F1 |",
          "|---|---|---|---|---|---|---|"]
    pit = df[df.model == "pit_unet_v2"].set_index("iou")
    pad = df[df.model == "plat_unet"].set_index("iou")
    for t in sorted(pit.index):
        md.append(f"| {t:.2f} | {pit.loc[t, 'recall']:.3f} | "
                  f"{pit.loc[t, 'precision']:.3f} | {pit.loc[t, 'f1']:.3f} | "
                  f"{pad.loc[t, 'recall']:.3f} | {pad.loc[t, 'precision']:.3f} | "
                  f"{pad.loc[t, 'f1']:.3f} |")
    tbl = OUT / "iou_strictness_scale_pit_pad_9t.md"
    tbl.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"  wrote {tbl}")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
