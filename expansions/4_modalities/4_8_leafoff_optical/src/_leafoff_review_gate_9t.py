"""S5 and the gate of framework 4.8. Reviewer agreement on usable chips and the usable-share decision per source.

Purpose. Per source, the usable share is usable chips over judged chips, with a Clopper-Pearson interval. Judged
chips exclude missing data (unavailable, blank, undated). Coverage, the judged share of sampled chips, must reach
min_coverage (0.80, user accepted default 2026-11-06) before the gate decides. Below it the decision is inconclusive.
The gate compares the share with usable_share_gate (0.60). Success (fetch D10) if the lower bound is above the gate, failure
(unusable here) if the upper bound is below it, else inconclusive. Interpretability uses the two blind reviewers
on usable chips only. It reports Cohen's kappa over yes, no and cannot_tell, and the share judged visible by both,
with an exact interval. A "no" is not rejection of the feature. Blank and unavailable chips are never negatives.
Inputs.
  data/9t/results/optical/leafoff_chip_status_9t.csv (from S2)
  expansions/4_modalities/4_8_leafoff_optical/data/raw/reviews/*.csv (assumed, one per reviewer; optional for the gate)
Outputs.
  data/9t/results/optical/leafoff_gate_9t.json
  data/9t/results/optical/leafoff_status_by_source_9t.png
Run.
  python expansions/4_modalities/4_8_leafoff_optical/src/_leafoff_review_gate_9t.py [--status CSV] [--reviews DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import _leafoff_kit_4_8 as lk

MISSING = {"unavailable", "blank", "undated"}


def gate(status: pd.DataFrame, level: float, min_coverage: float) -> dict:
    """4.8-01. Missing data (unavailable, blank, undated) is left out of the denominator, never counted as a
    not-usable chip. Coverage is the share of sampled chips that carry a quality judgement. With no judged chip
    the share is undefined and the decision is inconclusive. Below min_coverage (prereg.min_coverage, 0.80)
    neither success nor failure is called, so a source cannot pass on a small judged share."""
    out = {}
    for sid, g in status.groupby("source_id"):
        judged = g[~g.status.isin(MISSING)]
        k, n = int((judged.status == "usable").sum()), len(judged)
        p, lo, hi = lk.ek.clopper_pearson(k, n)
        cov = n / len(g) if len(g) else float("nan")
        enough = bool(n and cov >= min_coverage)
        dec = lk.ek.decide(lo - level, hi - level, 0.0, "superiority") if enough else "inconclusive"
        out[sid] = {"n": n, "n_sampled": len(g), "n_missing": int(len(g) - n),
                    "coverage": cov, "min_coverage": min_coverage, "coverage_ok": enough,
                    "missing_counts": g.status[g.status.isin(MISSING)].value_counts().to_dict(),
                    "usable": k, "share": p, "lo": lo, "hi": hi, "decision": dec,
                    "action": None, "status_counts": g.status.value_counts().to_dict()}
        out[sid]["action"] = ({"success": "fetch D10", "failure": "unusable here", "inconclusive": "report, sample more"}[dec]
                              if enough else "no judged chip. Verify the flight date or coverage before calling the gate" if not n
                              else f"coverage {cov:.2f} below {min_coverage:.2f}. Resolve missing chips before calling the gate")
    return out


def agreement(status: pd.DataFrame, rev: pd.DataFrame) -> dict:
    from sklearn.metrics import cohen_kappa_score
    use = status[status.status == "usable"][["feature_key", "source_id"]]
    out = {}
    for sid, g in rev.merge(use, on=["feature_key", "source_id"]).groupby("source_id"):
        w = g.pivot_table(index="feature_key", columns="reviewer", values="visible", aggfunc="first").dropna()
        if w.shape[1] < 2 or not len(w):
            out[sid] = {"n": len(w), "note": "fewer than two reviewers on usable chips"}
            continue
        a, b = w.columns[:2]
        both = int(((w[a] == "yes") & (w[b] == "yes")).sum())
        p, lo, hi = lk.ek.clopper_pearson(both, len(w))
        out[sid] = {"n": len(w), "kappa": float(cohen_kappa_score(w[a], w[b], labels=["yes", "no", "cannot_tell"])),
                    "visible_both": p, "visible_lo": lo, "visible_hi": hi,
                    "note": "a 'no' is not rejection of the feature"}
    return out


def figure(status: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    P = lk.ek.PALETTE   # lost/found palette, worst pair dE 21.1 deutan (dataviz validator --pairs all, CLAUDE.md)
    order = ["usable", "low visible ground", "cloud or shadow", "unregistered", "off-season", "undated", "blank", "unavailable"]
    srcs = sorted(status.source_id.unique())
    fig, axes = plt.subplots(1, len(srcs), figsize=(4.2 * len(srcs), 3.6), squeeze=False)
    for ax, sid in zip(axes[0], srcs):
        c = status[status.source_id == sid].status.value_counts().reindex(order, fill_value=0)
        col = [P["blue"] if s == "usable" else P["grey"] if s in MISSING else P["orange"] for s in order]
        ax.barh(order, c.values, color=col)
        for y, v in enumerate(c.values):
            ax.text(v, y, f" {v}", va="center", fontsize=8)
        ax.invert_yaxis()
        ax.set_title(sid, fontsize=9)
        ax.set_xlabel("chips")
    fig.suptitle("Chip status. Blue usable, orange quality-limited, grey missing data (never a negative)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv=None) -> int:
    cfg = lk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--status", default=None)
    ap.add_argument("--reviews", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    res_dir = lk.resolve(cfg["outputs"]["results"])
    sp = lk.need(Path(a.status) if a.status else res_dir / "leafoff_chip_status_9t.csv", "S2 chip status table")
    st = pd.read_csv(sp)
    res = {"gate_level": pr["usable_share_gate"], "min_coverage": pr["min_coverage"],
           "by_source": gate(st, pr["usable_share_gate"], float(pr["min_coverage"]))}
    rd = Path(a.reviews) if a.reviews else lk.resolve(cfg["inputs"]["reviews"])
    files = sorted(rd.glob("*.csv")) if rd.exists() else []
    if files:
        rev = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        bad = set(rev.visible) - {"yes", "no", "cannot_tell"}
        if bad:
            raise ValueError(f"visible must be yes, no or cannot_tell, got {bad}")
        res["interpretability"] = agreement(st, rev)
    else:
        res["interpretability"] = f"not run: no reviewer files in {rd} (assumed input)"
    out = Path(a.out) if a.out else res_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "leafoff_gate_9t.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    figure(st, out / "leafoff_status_by_source_9t.png")
    lk.prov(out, "leafoff_review_gate_9t", inputs=[sp, *files], outputs=[out / "leafoff_gate_9t.json"], params=pr)
    print(json.dumps({k: {kk: v[kk] for kk in ("usable", "n", "decision")} for k, v in res["by_source"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
