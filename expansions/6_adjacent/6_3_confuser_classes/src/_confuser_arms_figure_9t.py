"""6.3 S6. Arm comparison figure. Confuser detections per km2 and drawn-feature recall at K, by arm.

Purpose
    Two panels. Seed values are dots, the arm pooled over seeds is a bar outline, and the paired bootstrap
    intervals from the gate file are printed under the panels. Blue baseline, orange confuser arm, grey random
    (ek.PALETTE, lost/found palette, worst pair dE 21.1 deutan per CLAUDE.md, dataviz validator --pairs all).
    Each arm also has its own marker shape (circle, triangle, square) and a direct label, so colour is never
    the only cue.
Inputs (data/9t/results/confusers/)
    confuser_arm_scores_9t.csv, confuser_gate_9t.json (S5 score)
Outputs
    data/9t/results/confusers/confuser_arms_by_metric_9t.png
Run
    python expansions/6_adjacent/6_3_confuser_classes/src/_confuser_arms_figure_9t.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import _confuser_common_9t as C
from _confuser_common_9t import ek

STYLE = {"baseline": (ek.PALETTE["blue"], "o"), "confuser": (ek.PALETTE["orange"], "^"),
         "random": (ek.PALETTE["grey"], "s")}


def render(tab: pd.DataFrame, gate: dict, out_png: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    seed = tab.groupby(["arm", "seed"]).agg(conf=("n_confuser", "sum"), km2=("km2", "sum"),
                                            hits=("hits", "sum"), n=("n_truth", "sum")).reset_index()
    seed["conf_km2"] = seed.conf / seed.km2
    seed["recall"] = seed.hits / seed.n
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6))
    for ax, col, title in ((axes[0], "conf_km2", "labelled confuser detections per km2 at K"),
                           (axes[1], "recall", "drawn-feature recall at K")):
        for i, arm in enumerate(["baseline", "confuser", "random"]):
            s = seed[seed.arm == arm]
            if not len(s):
                continue
            c, mk = STYLE[arm]
            ax.scatter([i] * len(s), s[col], color=c, marker=mk, s=40, zorder=3)
            ax.hlines(s[col].mean(), i - 0.25, i + 0.25, color=c, lw=2)
            ax.text(i, s[col].max(), f"  {arm}", fontsize=8, va="bottom")
        ax.set_xticks([0, 1, 2], ["baseline", "confuser", "random"])
        ax.set_title(title, fontsize=9)
    p1, p2 = gate["primary_1_reduction"], gate["primary_2_recall_diff"]
    fig.text(0.01, -0.04, f"reduction (random minus confuser) {p1['point']:.2f} per km2, 95% block interval "
                          f"{p1['lo95']:.2f} to {p1['hi95']:.2f}. recall difference (confuser minus baseline) "
                          f"{p2['point']:.3f}, {p2['lo95']:.3f} to {p2['hi95']:.3f}. gate {gate['gate']}. "
                          "Evidence level a. Dots are seeds, not landscapes.", fontsize=7, wrap=True)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_png


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    out = C.results_dir(cfg, a.out)
    ar = cfg["area"]
    tab = out / f"confuser_arm_scores_{ar}.csv"
    gate = out / f"confuser_gate_{ar}.json"
    for p in (tab, gate):
        if not p.exists():
            raise C.MissingInput(f"{p} missing. Run _confuser_pooled_score_9t.py score first.")
    png = render(pd.read_csv(tab), json.loads(gate.read_text()), out / f"confuser_arms_by_metric_{ar}.png")
    print(f"wrote {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
