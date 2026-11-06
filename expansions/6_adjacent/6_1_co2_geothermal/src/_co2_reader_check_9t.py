"""6.1 S5b. Reader check scoring and the Q1 gate.

Purpose
    Score the partner reader check. A reader is the unit. Primary is the share of readers who answer the
    completeness question correctly, with a Clopper-Pearson exact interval. Zero-tolerance questions (the
    completeness question, plus the hydrogen suitability question in 6.4) fail the gate on any wrong answer.
    Other limits must reach the profile floor (0.80 by default). Fewer than min_readers is inconclusive.
    --template writes a blank answer sheet with the preregistered questions.
Inputs
    screen_reader_answers_9t.csv  columns reader_id, question_id, correct (0 or 1), seconds_to_limits (optional)
    Assumed. Readers are a user-only step. Proposed path data/9t/results/screening/screen_reader_answers_9t.csv
Outputs (run folder)
    screen_reader_gate_9t.json (hydrogen: screen_reader_gate_h2_9t.json), or the blank template CSV
Run
    python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_reader_check_9t.py --out RUN_DIR --answers FILE
    python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_reader_check_9t.py --out RUN_DIR --template
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import _co2_screen_lib as L
from _co2_screen_lib import ek


def template(prof: dict, out_dir: Path, area: str, n_readers: int = 5) -> Path:
    rows = [{"reader_id": f"R{r + 1}", "question_id": q, "question": v["text"], "correct": ""}
            for r in range(n_readers) for q, v in prof["reader_questions"].items()]
    out = out_dir / L.fname("screen_reader_answers_template", prof, area, "csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    return out


def gate(prof: dict, answers: pd.DataFrame) -> dict:
    qs = prof["reader_questions"]
    unknown = set(answers.question_id) - set(qs)
    if unknown:
        raise AssertionError(f"answers name questions not in the preregistered profile: {sorted(unknown)}")
    ek.assert_no_nan(answers["correct"], "correct")
    a = answers.assign(correct=answers["correct"].astype(int))
    if a.duplicated(["reader_id", "question_id"]).any():
        raise AssertionError("duplicate reader_id x question_id rows")
    readers = sorted(a.reader_id.unique())
    n = len(readers)
    zt = [q for q, v in qs.items() if v.get("zero_tolerance")]
    res = {"n_readers": n, "per_question": {}, "zero_tolerance": zt}
    for q in qs:
        s = a[a.question_id == q]
        k = int(s.correct.sum())
        p, lo, hi = ek.clopper_pearson(k, len(s)) if len(s) else (float("nan"),) * 3
        res["per_question"][q] = {"k": k, "n": int(len(s)), "share": p, "lo95": lo, "hi95": hi}
    prim = res["per_question"].get("Q_complete", {})
    res["primary"] = {"question": "Q_complete", **prim}
    other = a[~a.question_id.isin(zt)]
    res["other_limits_share"] = float(other.correct.mean()) if len(other) else float("nan")
    zt_wrong = int((a[a.question_id.isin(zt)].correct == 0).sum())
    if zt_wrong:
        res["gate"] = "failure"
        res["action"] = "Rewrite the limits sheet. Retest with new readers."
    elif n < prof["min_readers"]:
        res["gate"] = "inconclusive"
        res["action"] = f"Fewer than {prof['min_readers']} readers. Report counts. Not a pass."
    elif res["other_limits_share"] >= prof["other_limits_floor"] and all(
            res["per_question"][q]["n"] == n for q in zt):
        res["gate"] = "success"
        res["action"] = "The limits are readable."
    else:
        res["gate"] = "failure"
        res["action"] = "Other limits under the floor or a zero-tolerance answer is missing. Rewrite and retest."
    if "seconds_to_limits" in a:
        res["median_seconds_to_limits"] = float(a.groupby("reader_id").seconds_to_limits.first().median())
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--profile", default="co2")
    ap.add_argument("--profile-file", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--answers", default=None)
    ap.add_argument("--template", action="store_true")
    a = ap.parse_args()
    cfg = L.load_config(a.config)
    prof = L.load_profile(cfg, a.profile, a.profile_file)
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if a.template:
        print(f"wrote {template(prof, out_dir, cfg['area'])}")
        return 0
    ans = Path(a.answers) if a.answers else out_dir / L.fname("screen_reader_answers", prof, cfg["area"], "csv")
    if not ans.exists():
        raise L.MissingInput(f"reader answers {ans} missing. The reader check is a user-only step. "
                             "Write the template with --template and collect answers.")
    res = gate(prof, pd.read_csv(ans))
    out = out_dir / L.fname("screen_reader_gate", prof, cfg["area"], "json")
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
