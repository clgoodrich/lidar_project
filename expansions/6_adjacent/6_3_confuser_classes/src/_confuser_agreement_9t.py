"""6.3 S0 and S3. Reviewer agreement, pilot throughput, adjudication queue and the adjudicated label table.

Purpose
    From the two-reviewer label file, report raw percent agreement and Cohen's kappa (kappa is not an acceptance
    criterion), the share U, minutes per candidate, and class counts weighted by 1 / inclusion probability.
    Write the disagreements to an adjudication queue. When an adjudication file exists, merge it. Any sheet still
    unresolved stays U. Classes are checked against the codebook (P C Q K R H B X U). Unmatched is not negative.
Inputs
    data/9t/results/confusers/confuser_labels_9t.csv        reviewer rows (sheet_id, reviewer, class, confidence, minutes)
    data/9t/results/confusers/confuser_sheet_key_9t.csv     sheet_id -> uid
    data/9t/results/confusers/confuser_sample_9t.csv        inclusion probabilities
    data/9t/results/confusers/confuser_adjudication_9t.csv  optional (sheet_id, class) from the third look
Outputs
    confuser_agreement_9t.json, confuser_adjudication_queue_9t.csv, confuser_labels_adjudicated_9t.csv
    (pilot: the same names with _pilot_ before the area tag)
Run
    python expansions/6_adjacent/6_3_confuser_classes/src/_confuser_agreement_9t.py [--pilot] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _confuser_common_9t as C
from _confuser_common_9t import ek


def cohen_kappa(a: list, b: list) -> float:
    a, b = np.asarray(a), np.asarray(b)
    cats = sorted(set(a) | set(b))
    po = float(np.mean(a == b))
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def agreement(cfg: dict, labels: pd.DataFrame, key: pd.DataFrame, sample: pd.DataFrame,
              adjud: pd.DataFrame | None = None) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    codes = set(cfg["classes"]["all"])
    lab = labels[labels["class"].astype(str).str.len() > 0].copy()
    lab["class"] = lab["class"].astype(str).str.strip().str.upper()
    bad = set(lab["class"]) - codes
    if bad:
        raise AssertionError(f"classes not in the codebook: {sorted(bad)}")
    if lab.duplicated(["sheet_id", "reviewer"]).any():
        raise AssertionError("a reviewer labelled one sheet twice")
    revs = sorted(lab.reviewer.unique())
    if len(revs) < 2:
        raise AssertionError(f"need two reviewers, got {revs}")
    r1, r2 = revs[:2]
    w = lab.pivot(index="sheet_id", columns="reviewer", values="class")[[r1, r2]].dropna()
    agree = (w[r1] == w[r2])
    res = {"reviewers": [r1, r2], "n_sheets_both": int(len(w)), "percent_agreement": float(agree.mean()),
           "kappa": cohen_kappa(w[r1].tolist(), w[r2].tolist()),
           "kappa_note": "kappa is reported, not an acceptance criterion",
           "share_U_any": float(((w[r1] == "U") | (w[r2] == "U")).mean())}
    if "minutes" in lab and pd.to_numeric(lab.minutes, errors="coerce").notna().any():
        m = pd.to_numeric(lab.minutes, errors="coerce")
        res["minutes_per_candidate_median"] = float(m.median())
        res["reviewer_hours_per_20"] = float(m.median() * 20 / 60)
    queue = w[~agree].reset_index().rename(columns={r1: f"class_{r1}", r2: f"class_{r2}"})
    final = w[agree][r1].rename("class").reset_index()
    final["basis"] = "two reviewers agree"
    if adjud is not None and len(adjud):
        ad = adjud[["sheet_id", "class"]].copy()
        ad["class"] = ad["class"].astype(str).str.upper()
        if set(ad["class"]) - codes:
            raise AssertionError("adjudication uses a class not in the codebook")
        ad = ad[ad.sheet_id.isin(queue.sheet_id)]
        final = pd.concat([final, ad.assign(basis="adjudicated")], ignore_index=True)
    unresolved = queue[~queue.sheet_id.isin(final.sheet_id)]
    final = pd.concat([final, pd.DataFrame({"sheet_id": unresolved.sheet_id, "class": "U",
                                            "basis": "unresolved, kept U"})], ignore_index=True)
    n0 = len(final)
    final = final.merge(key[["sheet_id", "uid"]], on="sheet_id", how="left")
    final = final.merge(sample[["uid", "incl_prob", "band", "score"]], on="uid", how="left")
    ek.assert_rows(final, n0, "labels to sample join")
    ek.assert_unique(final, "sheet_id")
    ek.assert_no_nan(final.incl_prob, "incl_prob")
    final["weight"] = 1.0 / final.incl_prob
    res["n_adjudicated"] = int((final.basis == "adjudicated").sum())
    res["n_unresolved_U"] = int((final.basis == "unresolved, kept U").sum())
    res["class_counts"] = final["class"].value_counts().to_dict()
    res["class_weighted_share"] = (final.groupby("class").weight.sum() / final.weight.sum()).round(4).to_dict()
    res["class_by_band"] = final.groupby(["band", "class"]).size().unstack(fill_value=0).to_dict(orient="index")
    res["class_by_band"] = {str(k): v for k, v in res["class_by_band"].items()}
    return res, queue, final


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--labels", default=None)
    ap.add_argument("--adjudication", default=None)
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    out = C.results_dir(cfg, a.out)
    ar = cfg["area"]
    tag = "_pilot" if a.pilot else ""
    labels = Path(a.labels) if a.labels else out / f"confuser_labels_{ar}.csv"
    key = out / f"confuser_sheet_key_{ar}.csv"
    sample = out / (f"confuser_pilot_sample_{ar}.csv" if a.pilot else f"confuser_sample_{ar}.csv")
    for p in (labels, key, sample):
        if not p.exists():
            raise C.MissingInput(f"{p} missing (labels are a user-only step).")
    adj = Path(a.adjudication) if a.adjudication else out / f"confuser_adjudication{tag}_{ar}.csv"
    res, queue, final = agreement(cfg, pd.read_csv(labels), pd.read_csv(key), pd.read_csv(sample),
                                  pd.read_csv(adj) if adj.exists() else None)
    js = out / f"confuser_agreement{tag}_{ar}.json"
    js.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    q = out / f"confuser_adjudication_queue{tag}_{ar}.csv"
    queue.to_csv(q, index=False)
    f = out / f"confuser_labels_adjudicated{tag}_{ar}.csv"
    final.to_csv(f, index=False)
    C.provenance(cfg, out, "confagree", inputs=[labels, key, sample], outputs=[js, q, f])
    print(json.dumps({k: res[k] for k in ("n_sheets_both", "percent_agreement", "kappa", "share_U_any")}, indent=2))
    print(f"wrote {js}\nwrote {q}\nwrote {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
