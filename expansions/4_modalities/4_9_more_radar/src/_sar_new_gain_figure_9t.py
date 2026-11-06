"""S6 of framework 4.9. Figure of the paired gain with its interval per arm and stratum.

Purpose. One row per arm and stratum. Blue points and bars are the observed gain of the arm. Grey points are the
placebo arm. A grey line marks zero gain. An orange dashed line marks the margin delta_gain and is labelled
directly. The primary arm is labelled "primary", the others "exploratory" with their Holm p. Colour is never the only
encoding. Placebo uses a hollow marker.
Inputs.
  data/9t/results/sar_new/sar_new_gain_by_arm_9t.csv (from S5)
Outputs.
  data/9t/results/sar_new/figures/sar_new_gain_by_arm_9t.png
Run.
  python expansions/4_modalities/4_9_more_radar/src/_sar_new_gain_figure_9t.py [--gain CSV] [--out PNG]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import _sar_kit_4_9 as sk


def figure(tab: pd.DataFrame, delta: float, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    P = sk.ek.PALETTE   # lost/found palette, worst pair dE 21.1 deutan (dataviz validator --pairs all, CLAUDE.md)
    keys = tab[tab.kind == "arm"][["arm", "stratum"]].drop_duplicates().values.tolist()
    fig, ax = plt.subplots(figsize=(6.8, 0.5 * len(keys) + 1.6))
    for i, (arm, st) in enumerate(keys):
        for kind, col, mfc, dy in (("arm", P["blue"], P["blue"], 0.12), ("placebo", P["grey"], "white", -0.12)):
            r = tab[(tab.arm == arm) & (tab.stratum == st) & (tab.kind == kind)]
            if not len(r):
                continue
            r = r.iloc[0]
            ax.errorbar(r.gain, i + dy, xerr=[[r.gain - r.lo], [r.hi - r.gain]], fmt="o", color=col, mfc=mfc, capsize=3)
        r = tab[(tab.arm == arm) & (tab.stratum == st) & (tab.kind == "arm")].iloc[0]
        tag = "primary" if r.primary else f"exploratory, Holm p {r.holm_p:.2f}" if np.isfinite(r.holm_p) else "exploratory"
        ax.text(1.01, i, f"{tag}. {r.decision}", transform=ax.get_yaxis_transform(), va="center", fontsize=7)
    ax.axvline(0, color=P["grey"], lw=1)
    ax.axvline(delta, color=P["orange"], ls="--")
    ax.text(delta, len(keys) - 0.4, f" margin {delta:+.2f}", color=P["orange"], fontsize=8)
    ax.set_yticks(range(len(keys)), [f"{a} {s}" for a, s in keys])
    ax.set_xlabel("AUC gain over the rich lidar baseline (paired, 95% block bootstrap)")
    ax.set_title("SAR arms against drawn features. Filled is the arm, hollow is its placebo", fontsize=9)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main(argv=None) -> int:
    cfg = sk.load_cfg()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gain", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    gp = sk.need(Path(a.gain) if a.gain else sk.resolve(cfg["outputs"]["results"]) / "sar_new_gain_by_arm_9t.csv", "S5 gain table")
    tab = pd.read_csv(gp)
    out = Path(a.out) if a.out else sk.resolve(cfg["outputs"]["figures"]) / "sar_new_gain_by_arm_9t.png"
    figure(tab, cfg["prereg"]["delta_gain"], out)
    sk.prov(out.parent, "sar_new_gain_figure_9t", inputs=[gp], outputs=[out])
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
