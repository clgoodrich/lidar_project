"""3.2 S4 to S10. Run one 3.1 transfer stage over the 3.2 windows with config_3_2.json.

Purpose
    The per-window stages are the same code as 3.1, so they are not copied. This runner calls
    each 3.1 stage's main() with --config config_3_2.json --area <tag>, one window at a time,
    and keeps going past a window whose input is missing (it is reported, not hidden).
        blocks   S4   _xfer_blocks_roles_wfm.py      blocks, eligibility, roles inside the window box
        width    S5   _xfer_projected_width_wfm.py   projected width over density and clustering
        derivs   S6   _xfer_build_derivs_wfm.py      0.5 m rebuild (dry run unless --execute is passed through)
        package  S7   _xfer_annot_tools_wfm.py package   blind annotation package
        prereg   S7   _xfer_prereg_draft_wfm.py      preregistration draft with blockers
        infer    S8   _xfer_frozen_infer_wfm.py      frozen ensemble inference
        score    S8/S9 _xfer_score_k40_wfm.py        one scoring run with K=30, density-scaled, super-block
        errors   S10  _xfer_error_review_wfm.py      misses and the confuser queue
    Extra arguments after -- go to the stage unchanged (for example -- --execute).

Inputs / outputs
    As for each 3.1 stage, with 3.2 paths
    (expansions/3_geography/3_2_appalachian_states/results/tables/<tag>/, data/processed/<tag>/05/).
    A run summary is written to results/tables/stage_runs_appal.csv.

Run
    python expansions/3_geography/3_2_appalachian_states/src/_appal_window_stage_runner.py --stage blocks --tags ny_alg ky_lee -- --provisional-buffer
    python expansions/3_geography/3_2_appalachian_states/src/_appal_window_stage_runner.py --stage width
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
SRC31 = HERE.parents[2] / "3_1_warren_forest_mckean" / "src"
sys.path.insert(0, str(SRC31))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_2.json"
STAGES = {"blocks": ("_xfer_blocks_roles_wfm", []), "width": ("_xfer_projected_width_wfm", []),
          "derivs": ("_xfer_build_derivs_wfm", []), "package": ("_xfer_annot_tools_wfm", ["package"]),
          "prereg": ("_xfer_prereg_draft_wfm", []), "infer": ("_xfer_frozen_infer_wfm", []),
          "score": ("_xfer_score_k40_wfm", []), "errors": ("_xfer_error_review_wfm", [])}


def run_stage(stage: str, tags, extra, config: Path):
    mod = importlib.import_module(STAGES[stage][0])
    rows = []
    for t in tags:
        argv = STAGES[stage][1] + ["--config", str(config), "--area", t] + list(extra)
        try:
            rc = mod.main(argv)
            rows.append({"tag": t, "stage": stage, "status": "ok" if rc == 0 else f"rc {rc}", "detail": ""})
        except (xl.MissingInput, FileNotFoundError) as e:
            rows.append({"tag": t, "stage": stage, "status": "missing input", "detail": str(e).splitlines()[0]})
            print(f"  {t}: {str(e).splitlines()[0]}")
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    argv = argv[: argv.index("--")] if "--" in argv else argv
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stage", required=True, choices=sorted(STAGES))
    ap.add_argument("--tags", nargs="*", default=None)
    ap.add_argument("--config", default=str(CFG))
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    tags = a.tags or list(cfg["areas"])
    log = run_stage(a.stage, tags, extra, Path(a.config))
    log["date"] = dt.date.today().isoformat()
    p = ek.sub("3.2", "results/tables") / "stage_runs_appal.csv"
    (pd.concat([pd.read_csv(p), log]) if p.exists() else log).to_csv(p, index=False)
    print(log.to_string(index=False))
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
