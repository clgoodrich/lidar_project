"""3.0 S2 archival check. Rebuild the historical 9t recall at K from the sweep's own tables and compare.

Purpose
    The archival reference is the operating-point sweep, rebuilt from its own per-fold object tables
    (`cv5_sweep_objects_*`), fold-specific proposal cutoffs, Platt calibrators fitted on the other four folds,
    per-fold budgets floored on each fold's own area and its stable tie order. This script does not rewrite
    that logic. It imports `_operating_point_policy_sweep_pit_pad_9t.py` and calls its `fold_data`,
    `rule_budget`, `apply_rule` and `score` for each budget, then compares with the saved sweep table and the
    protocol's quoted targets. Acceptance. Matches to three decimals, every discrepancy explained.
    This is a readiness check. It is not a transfer result.

Inputs
    data/9t/results/operating_point/cv5_sweep_objects_{pit,pad}_thr0p05to0p95_9t.csv.gz,
    cv5_sweep_counts_per_block_{pit,pad}_thr0p05to0p95_9t.csv,
    policy_sweep_cost_budget_conformal_fbeta_heldout_cv5_iou0p30_pit_pad_9t.csv (saved results)

Outputs
    <out-dir>/transfer_archival_check_9t.json   per task and budget, rebuilt and saved numbers, differences, verdict
    Default out-dir expansions/3_geography/3_0_transfer_protocol/results/tables/
    Run record under expansions/3_geography/3_0_transfer_protocol/results/<run_id>/

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_archival_check_9t.py [--budgets 30 40] [--tasks pit pad]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _transfer_score_lib as tl  # noqa: E402
ek = tl.ek
CFG = json.loads((HERE.parent / "config_3_0.json").read_text(encoding="utf-8"))
SAVED = "policy_sweep_cost_budget_conformal_fbeta_heldout_cv5_iou0p30_pit_pad_9t.csv"
FIELDS = ("recall", "recall_lo", "recall_hi", "recall_fold_min", "recall_fold_max", "candidates", "n_gt")


def rebuild(task: str, budgets, ops) -> dict:
    folds = ops.fold_data(task)
    cache, out = {}, {}
    for b in budgets:
        rules = [ops.rule_budget(f, b) for f in folds]
        keeps = [ops.apply_rule(f, r) for f, r in zip(folds, rules)]
        m = ops.score(folds, keeps, cache)
        out[str(b)] = {k: float(m[k]) for k in FIELDS} | {"rule_per_fold": [int(r[1]) for r in rules],
                                                        "fold_km2": [float(f["held_km2"]) for f in folds]}
    return out


def compare(rebuilt: dict, saved_df, task: str, decimals: int, targets: dict) -> dict:
    import pandas as pd
    res = {}
    for b, r in rebuilt.items():
        row = saved_df[(saved_df.task == task) & (saved_df.family == "budget") & (pd.to_numeric(saved_df.setting, errors="coerce") == float(b))]
        entry = {"rebuilt": r}
        if len(row):
            s = row.iloc[0]
            diffs = {k: float(r[k] - float(s[k])) for k in FIELDS}
            entry["saved"] = {k: float(s[k]) for k in FIELDS}
            entry["max_abs_diff"] = max(abs(v) for v in diffs.values())
            entry["matches_saved"] = all(round(r[k], decimals) == round(float(s[k]), decimals) for k in FIELDS)
            entry["diffs"] = diffs
        else:
            entry["matches_saved"] = None
            entry["note"] = "budget not in the saved sweep table"
        t = targets.get(task, {}).get(b)
        if t is not None:
            entry["protocol_target"] = t
            entry["matches_protocol_target"] = round(r["recall"], decimals) == round(t, decimals)
        res[b] = entry
    return res


def explain(res: dict) -> list[str]:
    """Plain-language reasons for any mismatch that the code can identify."""
    notes = []
    for task, by_b in res.items():
        for b, e in by_b.items():
            if e.get("matches_saved") is False:
                worst = max(e["diffs"], key=lambda k: abs(e["diffs"][k]))
                notes.append(f"{task} K={b}: largest difference in {worst} ({e['diffs'][worst]:+.4f}). "
                             "Interval fields depend on the bootstrap seed and plan cache. Point fields do not.")
            if e.get("matches_protocol_target") is False:
                notes.append(f"{task} K={b}: rebuilt {e['rebuilt']['recall']:.4f} vs protocol {e['protocol_target']}")
    return notes


def main(argv=None) -> int:
    c = CFG["archival"]
    ap = argparse.ArgumentParser(description="3.0 S2 archival check")
    ap.add_argument("--budgets", type=float, nargs="+", default=c["budgets"])
    ap.add_argument("--tasks", nargs="+", default=["pit", "pad"])
    ap.add_argument("--out-dir", type=Path, default=None)
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2" / "s5_eval"))
    import pandas as pd
    import _operating_point_policy_sweep_pit_pad_9t as ops
    saved_p = ops.OUT / SAVED
    if not saved_p.exists():
        raise SystemExit(f"saved sweep table missing: {saved_p}")
    saved = pd.read_csv(saved_p)
    budgets = [int(b) if float(b).is_integer() else b for b in a.budgets]
    res = {t: compare(rebuild(t, budgets, ops), saved, t, c["decimals"], c["targets_from_protocol"]) for t in a.tasks}
    notes = explain(res)
    ok = all(e.get("matches_saved") is not False and e.get("matches_protocol_target") is not False
             for by_b in res.values() for e in by_b.values())
    doc = {"check": "archival", "verdict": "match" if ok else "mismatch, see notes", "notes": notes, "results": res,
           "sweep_module": str(Path(ops.__file__)), "sweep_module_sha256": ek.sha256(Path(ops.__file__)),
           "evidence_level": "(a) drawn feature", "label": "historical diagnostic, not an unbiased baseline"}
    out = a.out_dir or ek.sub("3.0", "results/tables")
    out.mkdir(parents=True, exist_ok=True)
    js = out / "transfer_archival_check_9t.json"
    js.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    run = ek.new_run("3.0", "archival_check", {"budgets": budgets, "tasks": a.tasks}, why="S2 archival check.")
    objs = [ops.OUT / f"cv5_sweep_objects_{t}_thr0p05to0p95_9t.csv.gz" for t in a.tasks]
    ek.write_provenance(run, inputs=[saved_p, Path(ops.__file__)] + objs, outputs=[js])
    for t, by_b in res.items():
        for b, e in by_b.items():
            r = e["rebuilt"]
            print(f"{t} K={b}/km2: rebuilt recall {r['recall']:.4f} [{r['recall_lo']:.4f}, {r['recall_hi']:.4f}] "
                  f"fold {r['recall_fold_min']:.3f}-{r['recall_fold_max']:.3f}  matches saved {e.get('matches_saved')}"
                  + (f"  protocol {e['protocol_target']} match {e['matches_protocol_target']}" if "protocol_target" in e else ""))
    print(f"verdict {doc['verdict']}\nwrote {js}\nrun record {run}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
