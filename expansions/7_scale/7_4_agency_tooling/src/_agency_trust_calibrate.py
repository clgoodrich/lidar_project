"""Trust statement and optional local calibration for agency runs (7.4 sections 8 and 12, test T7).

Purpose
    trust      Write the trust statement shipped with every run. It says only what saved evidence supports.
               The context line (27 of 424 drawn pits near a catalogued well) is parsed from
               docs/iterations/LEADERBOARD.md at run time, never typed. The transfer table is read from
               the 3.0 and 3.1 result files. An area with no file has no evidence. The wording follows
               the 3.1 decision. success gives "tested on", failure "not shown to transfer", inconclusive
               "not shown to transfer or to fail", absent "evaluated on 9t only". A result file whose
               model hash differs from the run's model is listed as not applicable.
    calibrate  Fit a monotonic (isotonic) map from raw score to agency-labelled precision on 50 to 100 labels.
               Report Brier, log loss and ECE before and after with a bootstrap interval over labels.
               The file carries the model hash and is refused for a different model. A monotonic map
               cannot change ranking, so recall at fixed K is unchanged (asserted).

Inputs
    config_7_4.json transfer_evidence and context_line entries, a run's model hash
    calibrate: CSV with score and label (1 drawn or field-checked feature, 0 not), the model hash
Outputs
    trust_statement.md in the run folder (trust)
    calibration_<model_sha7>.json (calibrate)

Run
    python expansions/7_scale/7_4_agency_tooling/src/_agency_trust_calibrate.py trust --model-sha256 <sha> --out <run folder>
    python expansions/7_scale/7_4_agency_tooling/src/_agency_trust_calibrate.py calibrate --labels agency_labels.csv \
        --model-sha256 <sha> --out <folder>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _agency_las_validity import CFG, cfg_path, ek, load_cfg  # noqa: E402

WORDING = {"success": "tested on", "failure": "not shown to transfer",
           "inconclusive": "not shown to transfer or to fail", None: "evaluated on 9t only"}


def context_line(cfg: dict) -> str:
    c = cfg["context_line"]
    p = cfg_path(c)
    if p.exists():
        m = re.search(c["pattern"], p.read_text(encoding="utf-8"))
        if m:
            return (f"On 9t, {m.group(1)} of {m.group(2)} annotated pits ({m.group(3)}%) have a catalogued well "
                    f"within 25 m (source {c['rel']}). Expect most candidates not to be wells.")
    return "The context figure was not found in its source file. VERIFY before release."


def transfer_rows(cfg: dict, model_sha: str) -> list[dict]:
    rows = []
    for e in cfg["transfer_evidence"]:
        p = cfg_path(e["path"])
        if not p.exists():
            rows.append({"area": e["area"], "status": "no evidence (result file absent)"})
            continue
        r = json.loads(p.read_text())
        if r.get("model_sha256") and r["model_sha256"] != model_sha:
            rows.append({"area": e["area"], "status": "not applicable (different model hash)"})
            continue
        rows.append({"area": e["area"], "status": "evaluated", "recall": r.get("recall"), "lo": r.get("lo"),
                     "hi": r.get("hi"), "density": r.get("truth_density_per_km2"), "input_class": r.get("input_class"),
                     "decision": r.get("decision")})
    return rows


def trust_statement(cfg: dict, model_sha: str, run_summary: dict | None = None) -> str:
    rows = transfer_rows(cfg, model_sha)
    dec = next((r.get("decision") for r in rows if r["area"] != "9t" and r["status"] == "evaluated"), None)
    lines = ["# Trust statement", "",
             "The candidates are drawn-feature predictions at evidence level (a). A candidate is not a well.",
             context_line(cfg),
             "Reference performance is measured on 9t only. It is a historical diagnostic, not a new baseline.", "",
             "## Transfer evidence", "", "| Area | Status | Recall at 40 per km2 (95% CI) | Feature density per km2 | Input class |",
             "|---|---|---|---|---|"]
    for r in rows:
        rc = f"{r['recall']:.3f} ({r['lo']:.3f} to {r['hi']:.3f})" if r.get("recall") is not None else ""
        lines.append(f"| {r['area']} | {r['status']} | {rc} | {r.get('density') or ''} | {r.get('input_class') or ''} |")
    lines += ["", f"Transfer wording. Results are {WORDING.get(dec, WORDING[None])}.",
              "Results on other terrain, density or vintage are untested.", "",
              "## Score meaning",
              "Raw scores rank candidates. They are not probabilities of a well and are not calibrated across areas.",
              "A calibrated score, when present, estimates precision against the agency's own labels on the stated sample.", "",
              "## Missed features",
              "Recall is below 100% at any review budget. Absence of a candidate is not absence of a well.",
              "Wells with no surface expression stay invisible.", ""]
    if run_summary:
        lines += ["## This run", f"Tiles scored {run_summary.get('scored', 0)}. Warned {run_summary.get('warned', 0)}. "
                  f"Refused {run_summary.get('refused', 0)}. Warned and refused tiles are listed in the validity report. "
                  "Refused tiles are not covered.", ""]
    return "\n".join(lines)


def calibrate(scores, labels, model_sha: str, B: int = 1000, seed: int = 0) -> dict:
    from sklearn.isotonic import IsotonicRegression
    s, y = np.asarray(scores, float), np.asarray(labels, int)
    if len(s) < 50:
        note = f"{len(s)} labels. Below the 50 to 100 trial size"
    else:
        note = f"{len(s)} labels. A trial size, not a reliability guarantee"
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(s, y)
    cal = iso.predict(s)
    # monotone non-decreasing map, so cal is never reversed relative to raw score
    assert np.all(np.diff(cal[np.argsort(s, kind="stable")]) >= -1e-12)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(B):
        ix = rng.integers(0, len(s), len(s))
        draws.append(ek.calibration(y[ix], cal[ix])["brier"])
    return {"model_sha256": model_sha, "method": "isotonic regression, score to agency-labelled precision",
            "x": iso.X_thresholds_.tolist(), "y": iso.y_thresholds_.tolist(), "n_labels": int(len(s)),
            "before": ek.calibration(y, s), "after_in_sample": ek.calibration(y, cal),
            "brier_after_ci95": [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))],
            "ranking_ties_introduced": int(len(s) - len(np.unique(cal))), "note": note,
            "top_k_unchanged_note": "monotone map. Ranking at fixed K is unchanged except within new ties"}


def apply_calibration(cal: dict, model_sha: str):
    if cal["model_sha256"] != model_sha:
        raise PermissionError("calibration file belongs to a different model. Refused")
    x, y = np.asarray(cal["x"]), np.asarray(cal["y"])
    return lambda s: np.interp(np.asarray(s, float), x, y)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.4 trust statement and local calibration.")
    ap.add_argument("--config", default=str(CFG))
    sp = ap.add_subparsers(dest="cmd", required=True)
    t = sp.add_parser("trust")
    t.add_argument("--model-sha256", required=True)
    t.add_argument("--out", required=True)
    c = sp.add_parser("calibrate")
    c.add_argument("--labels", required=True)
    c.add_argument("--model-sha256", required=True)
    c.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "trust":
        (out / "trust_statement.md").write_text(trust_statement(cfg, a.model_sha256), encoding="utf-8")
        print(f"wrote {out / 'trust_statement.md'}")
        return 0
    if not Path(a.labels).exists():
        print(f"missing labels {a.labels}", file=sys.stderr)
        return 2
    df = pd.read_csv(a.labels)
    res = calibrate(df["score"], df["label"], a.model_sha256)
    p = out / f"calibration_{a.model_sha256[:7]}.json"
    p.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
