"""3.3 S5. Gate for the flat-county area test (Illinois Cumberland), read from the S1 result.

Purpose
    fw_3_3 S5 releases the Illinois area test only if S1 shows lowest-tercile recall below the
    top tercile by more than the margin, or the user asks. This stage reads the S1 summary and
    the margin, applies ek.decide, and writes the verdict plus the commands that would run the
    transfer pipeline (3.1 scripts) on the gated window. It never fetches anything.
    It also states the coverage problem. The 9t lowest slope tercile ends near 7.7 degrees
    (2026-11-05 run), far steeper than Midwest farmland, so S1 cannot speak to flat ground.

Inputs
    3.3 S1 run folder slope_recall_summary_9t.json, config_3_3.json (margin_delta, area_gate)

Outputs
    <S1 run folder>/slope_area_gate_9t.json   verdict (release, hold, no_margin_set), reasons, commands

Run
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_area_gate_9t.py
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_area_gate_9t.py --margin 0.05
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_area_gate_9t.py --user-request
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

CFG = HERE.parent / "config_3_3.json"
FLAT_DEG = 2.0   # rough upper slope of row-crop farmland, used only to word the coverage note


def gate(summary: dict, margin, user_request: bool, n_flat: int | None = None) -> dict:
    p = summary["primary"]
    cut_lo = summary["cut_points"]["feature_slope_deg"][0]
    flat = f"{n_flat} of {summary['n_features']} scored pits have 25 m slope under {FLAT_DEG} deg" if n_flat is not None else ""
    out = {"primary": p, "margin": margin, "lowest_tercile_upper_deg": cut_lo, "n_pits_under_flat_deg": n_flat,
           "coverage_note": (f"lowest tercile reaches {cut_lo:.1f} deg. {flat}. S1 says little about flat farmland"
                             if cut_lo > FLAT_DEG else "lowest tercile is flat")}
    if margin is None:
        out["s1_decision"] = "no_margin_set"
    else:
        out["s1_decision"] = ek.decide(p["lo"], p["hi"], margin, "noninferiority")
    penalty = out["s1_decision"] == "failure"
    out["release_area_test"] = bool(penalty or user_request)
    out["reason"] = ("user request" if user_request else
                     "slope penalty found (upper bound below minus margin)" if penalty else
                     "no slope penalty shown; area test stays gated" if out["s1_decision"] == "success" else
                     "inconclusive or no margin; area test stays gated until the user decides")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--run", default=None, help="S1 run folder (default newest)")
    ap.add_argument("--margin", type=float, default=None, help="override margin_delta (recall points)")
    ap.add_argument("--user-request", action="store_true")
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    runs = sorted(ek.sub("3.3", "results").glob("*_slope_recall_*"))
    run = Path(a.run) if a.run else (runs[-1] if runs else None)
    if run is None or not (run / "slope_recall_summary_9t.json").exists():
        raise FileNotFoundError("MISSING INPUT: 3.3 S1 summary. Run _slope_recall_tercile_9t.py first.")
    s = json.loads((run / "slope_recall_summary_9t.json").read_text())
    margin = a.margin if a.margin is not None else cfg.get("margin_delta")
    import pandas as pd
    fcsv = run / "slope_recall_features_9t.csv"
    n_flat = int((pd.read_csv(fcsv).slope_25m < FLAT_DEG).sum()) if fcsv.exists() else None
    out = gate(s, margin, a.user_request, n_flat)
    g = cfg["area_gate"]
    src31 = "expansions/3_geography/3_1_warren_forest_mckean/src"
    out["area_window"] = g
    out["commands_if_released"] = [
        f"python {src31}/_xfer_tile_inventory_wfm.py --area il_cumberland --tiles <fetched LAZ glob>",
        f"python {src31}/_xfer_blocks_roles_wfm.py --area il_cumberland",
        f"python {src31}/_xfer_projected_width_wfm.py --area il_cumberland",
        "then 3.1 S3 to S8 with --area il_cumberland (fetch is a user step, 3.61 GB, measure one tile first)"]
    o = run / "slope_area_gate_9t.json"
    o.write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    print(json.dumps(out, indent=2, default=float))
    print(f"wrote {o}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
