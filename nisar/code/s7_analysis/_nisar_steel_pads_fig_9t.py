"""Figure: steel screen at lidar pads vs same-shaped controls, 9t, lidar-placed stack. Set 2026-11-26.

Reads nisar/results/9t/nisar_steel_pads_summary_9t_slc.json (from s5_eval/_nisar_steel_pads_9t.py --slc).
Panel a: hit rate (any track) by class, all post-June dates. Panel b: separate rule pass rates per track.
Colours: pads #1F5FA8, controls #8E959B hatched (identity also by hatch and legend, never colour alone).
No red/green pair. Pair taken from the validated lost/found palette and the steel-test greys.
Writes nisar/results/9t/figures/nisar_steel_pads_hit_rate_9t_slc.png
Run: python nisar/code/s7_analysis/_nisar_steel_pads_fig_9t.py
"""
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nisar" / "code"))
import _nisar_fig_style as S  # noqa: E402

RES = ROOT / "nisar" / "results" / "9t"
J = json.load(open(RES / "nisar_steel_pads_summary_9t_slc.json"))
BLUE, GREY = "#1F5FA8", "#8E959B"


def main():
    S.apply()
    t = [r for r in J["tests"] if r["dates"] == "all_post_june"]
    order = ["all", "cover_cls=open", "cover_cls=canopy", "size_cls=small", "size_cls=mid", "size_cls=large",
             "status_cls=active", "status_cls=plugged_or_abandoned", "status_cls=no_dep_well"]
    lab = {"all": "All pads", "cover_cls=open": "Open", "cover_cls=canopy": "Canopy", "size_cls=small": "Small",
           "size_cls=mid": "Mid", "size_cls=large": "Large", "status_cls=active": "Active well",
           "status_cls=plugged_or_abandoned": "Plugged/aband.", "status_cls=no_dep_well": "No DEP well"}
    rows = [next(r for r in t if r["cls"] == c) for c in order if any(r["cls"] == c for r in t)]
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw=dict(width_ratios=[2.2, 1]))
    x = np.arange(len(rows))
    a.bar(x - 0.2, [100 * r["pads_hit_any"] for r in rows], 0.4, color=BLUE, label="Lidar pads (+5 m)")
    a.bar(x + 0.2, [100 * r["ctrl_hit_any"] for r in rows], 0.4, color=GREY, hatch="///", ec="white",
          label="Same-shape controls")
    for i, r in enumerate(rows):
        a.text(i, 100 * max(r["pads_hit_any"], r["ctrl_hit_any"]) + 0.8, f"p={r['p_any']:.2g}\nn={r['n_pads']}",
               ha="center", fontsize=7)
    a.set_xticks(x); a.set_xticklabels([lab[r["cls"]] for r in rows], rotation=30, ha="right")
    a.set_ylabel("Sites with a steady bright pixel, any track (%)")
    a.set_title("a  Pads vs controls, post-June 2026", loc="left")
    a.set_ylim(0, 30); a.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
    pr = J["pass_rates"]["all_post_june"]
    tr = sorted(pr, key=int)
    xx = np.arange(len(tr))
    for k, (key, c, h, nm) in enumerate([("bright_pass", BLUE, None, "Brightness"),
                                          ("steady_pass", GREY, "///", "Steadiness"),
                                          ("both_pass", "#2B2F36", None, "Both")]):
        b.bar(xx + (k - 1) * 0.27, [100 * pr[t][key] for t in tr], 0.27, color=c, hatch=h, ec="white", label=nm)
    b.set_yscale("log"); b.set_xticks(xx); b.set_xticklabels([f"Track {t}" for t in tr])
    b.set_ylabel("Share of valid pixels (%)"); b.set_title("b  Rule pass rates", loc="left")
    b.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    S.save(fig, RES / "figures" / "nisar_steel_pads_hit_rate_9t_slc.png")
    print("wrote", RES / "figures" / "nisar_steel_pads_hit_rate_9t_slc.png")


if __name__ == "__main__":
    main()
