"""Aggregate the road sweep into a leaderboard (variants + baselines).

Reads test_metrics.json from each sweep variant dir plus the two baselines
(road_unet_1m_recall, road_unet_1m_corrected), normalizes the three differing
JSON shapes into one row schema, and writes:
  road_sweep_202607/leaderboard.csv
  road_sweep_202607/leaderboard.md   (paste-ready markdown table)
  road_sweep_202607/fig_sweep.png    (val IoU + 613590 added/reject bars)

Re-runnable at any time (skips variants without test_metrics.json yet).
Reproduce: python notebooks/wellsight_v2/s5_eval/_road_sweep_aggregate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T

SWEEP = DERIV_9T / "road_sweep_202607"
VARIANTS = ["cldice", "alpha078", "boundary", "orient", "res05"]
BASELINES = {
    "recall (baseline)": DERIV_9T / "road_unet_1m_recall" / "test_metrics.json",
    "corrected (baseline)": DERIV_9T / "road_unet_1m_corrected" / "test_metrics.json",
}


def _get(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default


def normalize_row(name, m):
    """Flatten one metrics dict (any of the 3 shapes) into a common row."""
    # 9t test block: either top-level (recall) or under '9t_test'
    t = m.get("9t_test", m)
    row = {
        "model": name,
        "res": m.get("res", "1m"),
        "val_road_iou": _get(m, "val_road_iou", "9t_val_road_iou"),
        "pix_iou": _get(t, "pixel_iou_road_test"),
        "ap_vs_drainage": _get(t, "ap_road_vs_drainage"),
        "P_road": _get(t, "mean_Proad_on_road_test"),
        "P_drain": _get(t, "mean_Proad_on_drainage_test"),
    }
    # 613590 held-out corrections (test cells) — added/reject after + AP
    corr = m.get("corrections_613590")
    if corr and "test" in corr:
        tc = corr["test"]
        row["added_P_after"] = _get(tc.get("added", {}), "mean_Proad_after")
        row["added_frac05_after"] = _get(tc.get("added", {}),
                                         "frac_over_0.5_after")
        row["reject_P_after"] = _get(tc.get("reject", {}), "mean_Proad_after")
        row["added_vs_reject_AP"] = tc.get("ap_added_vs_reject_after")
    return row


def main():
    rows = []
    for name, p in BASELINES.items():
        if p.exists():
            rows.append(normalize_row(name, json.loads(p.read_text())))
        else:
            print(f"  (missing baseline {p})")
    for v in VARIANTS:
        p = SWEEP / v / "test_metrics.json"
        if p.exists():
            rows.append(normalize_row(v, json.loads(p.read_text())))
        else:
            print(f"  (pending: {v})")

    df = pd.DataFrame(rows)
    df.to_csv(SWEEP / "leaderboard.csv", index=False)

    # markdown
    disp = df.copy()
    for c in ["val_road_iou", "pix_iou", "ap_vs_drainage", "P_road", "P_drain",
              "added_P_after", "added_frac05_after", "reject_P_after",
              "added_vs_reject_AP"]:
        if c in disp:
            disp[c] = disp[c].map(lambda x: f"{x:.3f}" if pd.notna(x) else "-")
    cols = ["model", "res", "val_road_iou", "pix_iou", "ap_vs_drainage",
            "P_road", "P_drain", "added_P_after", "added_frac05_after",
            "reject_P_after", "added_vs_reject_AP"]
    cols = [c for c in cols if c in disp]
    hdr = {"val_road_iou": "9t val IoU", "pix_iou": "9t test pixIoU",
           "ap_vs_drainage": "AP vs drain", "P_road": "P(road)",
           "P_drain": "P(drain)", "added_P_after": "613590 added P",
           "added_frac05_after": "added>=0.5", "reject_P_after": "reject P",
           "added_vs_reject_AP": "add-v-rej AP"}
    md = ["| " + " | ".join(hdr.get(c, c) for c in cols) + " |",
          "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in disp.iterrows():
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    md_txt = "\n".join(md)
    (SWEEP / "leaderboard.md").write_text(md_txt + "\n", encoding="utf-8")
    print(md_txt)

    # figure: val IoU (all) + 613590 added/reject P after (1m variants)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
    d = df.dropna(subset=["val_road_iou"])
    ax1.barh(d["model"], d["val_road_iou"], color="#4575b4")
    ax1.set_xlabel("9t val road IoU (selection metric)")
    ax1.set_xlim(0.55, max(0.66, d["val_road_iou"].max() + 0.01))
    ax1.set_title("Model selection score")
    ax1.invert_yaxis()
    d2 = df.dropna(subset=["added_P_after"])
    y = np.arange(len(d2)); h = 0.38
    ax2.barh(y - h / 2, d2["added_P_after"], h, color="#1a9850",
             label="added road P(road) — higher better")
    ax2.barh(y + h / 2, d2["reject_P_after"], h, color="#d73027",
             label="reject P(road) — lower better")
    ax2.set_yticks(y); ax2.set_yticklabels(d2["model"])
    ax2.set_xlabel("613590 held-out P(road)")
    ax2.set_title("Correction recall (added) vs precision (reject)")
    ax2.legend(fontsize=8); ax2.invert_yaxis()
    fig.tight_layout()
    fig.savefig(SWEEP / "fig_sweep.png", dpi=140)
    print(f"\nwrote {SWEEP/'leaderboard.md'}, .csv, fig_sweep.png")


if __name__ == "__main__":
    main()
