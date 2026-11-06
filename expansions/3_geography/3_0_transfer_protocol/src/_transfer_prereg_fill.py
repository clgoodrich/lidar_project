"""3.0 S5. Preregistration filler. Turn a fields file into a filled, hash-stamped transfer preregistration.

Purpose
    Read a fields JSON (one entry per field, see `example_fields()` and `config_3_0.json` `prereg_required`),
    check it, hash every input that exists, and write `transfer_<area>_prereg.md`. The file keeps the
    template's eleven sections in order. Under each it prints the filled values. At the end it embeds one
    ```json prereg``` block that `_transfer_score_run.py --prereg` reads, so the scorer runs from the file alone.
    Checks (fail closed)
        every required field present and non-empty
        primary K is 40 per km2 (user decision 2026-11-04). Any other K needs `"k_override_reason"`
        margin is a positive number with a stated source. It may not come from fold spread or variance
        evidence level is one of (a) (b) (c) (d) and never a merge
        if a projected-width table is given, the width at the planned block count is at most 2 x margin
    A filled file that exists is never overwritten. Fix mistakes in an Amendments section by hand.

Inputs
    --fields   JSON of field values (example with --example)
    template   C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/transfer_prereg_template.md (read only)
    optional   --ci-width CSV from `_transfer_ci_width_9t.py`

Outputs
    --out, default C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/transfer_<area>_prereg.md
    Run record under expansions/3_geography/3_0_transfer_protocol/results/<run_id>/

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_prereg_fill.py --example > fields_warren.json
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_prereg_fill.py --fields fields_warren.json [--ci-width ...] [--out ...]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _transfer_score_lib as tl  # noqa: E402
ek = tl.ek
CFG = json.loads((HERE.parent / "config_3_0.json").read_text(encoding="utf-8"))
LEVELS = ("(a) drawn feature", "(b) historical", "(c) steel", "(d) confirmed well")
SECTION_FIELDS = {
    1: ["question"], 2: ["task", "candidate_unit", "scoring.footprint", "eligibility", "edge_rule"],
    3: ["lidar", "ground_density", "evidence_level", "label_source"], 4: ["frozen", "model_policy"],
    5: ["adaptation_area", "test_area", "audit_file", "buffer_m", "buffer_source"],
    6: ["primary_metric", "scoring.k", "scoring.seed", "scoring.B"], 7: ["margin", "margin_source", "actions"],
    8: ["labellers", "categories"], 9: ["report"], 10: [], 11: ["reference.run", "density_c", "split_file", "split_sha256",
                                                                  "planned_blocks"],
}


def example_fields() -> dict:
    return {
        "question": "Does the 9t pit model keep its recall at K = 40 per km2 in <area>.",
        "area": "<area>", "task": "pit", "candidate_unit": "one detection per pit, second pieces dropped",
        "eligibility": "complete blocks, void fraction at most the cap, identical for observed and null",
        "edge_rule": "blocks with any part outside valid data are dropped",
        "lidar": "<program, dates, tile list path>", "ground_density": "<measured per block, file path>",
        "evidence_level": "(a) drawn feature", "label_source": "<who drew, blind to scores>",
        "frozen": "weights, 0.5 m preprocessing, proposal cutoff 0.10, min area 4 m2, matching IoU 0.3, K",
        "model_policy": "single_fold:<k> or fold_mean, named before scoring",
        "adaptation_area": "<path or none>", "test_area": "<path>", "audit_file": "<P2 audit file or none>",
        "buffer_m": 100, "buffer_source": "P1 S4 buffer_derivation_9t.json",
        "primary_metric": "recall at K per km2 of scored eligible area",
        "margin": 0.10, "margin_source": "tolerable missed-feature burden at K, stated here",
        "actions": {"success": "proceed to 3.2 or adaptation", "failure": "error review, no transfer claim",
                    "inconclusive": "report, change design or add blocks"},
        "labellers": "<names kept off documents>", "categories": ["pit", "possible pit", "uncertain"],
        "report": "detection and record association reported separately",
        "reference": {"run": "<9t reference run folder>", "label": "new baseline or archival"},
        "density_c": None, "split_file": "<P1 split file>", "split_sha256": "<sha256>", "planned_blocks": 30,
        "scoring": {"area": "<area>", "task": "pit", "prob": "<target probability raster>", "blocks": "<blocks gpkg>",
                    "truth": "<truth gpkg:layer>", "truth_id": "pit_inside_id", "footprint": None,
                    "void": None, "void_cap": 0.5, "k": 40, "seed": 20261105, "B": 2000},
    }


def get(d: dict, dotted: str):
    for p in dotted.split("."):
        if not isinstance(d, dict) or p not in d:
            return None
        d = d[p]
    return d


def check(f: dict, ci_width: Path | None = None) -> list[str]:
    probs = []
    for k in CFG["prereg_required"]:
        v = get(f, k)
        if v is None and k != "density_c" or (isinstance(v, str) and (not v.strip() or v.startswith("<"))):
            probs.append(f"field {k} missing or still a placeholder")
    k = get(f, "scoring.k")
    if k is not None and float(k) != float(CFG["scoring_defaults"]["k_per_km2"]) and not f.get("k_override_reason"):
        probs.append(f"primary K {k} is not the decided 40 per km2 and no k_override_reason is given")
    m = f.get("margin")
    if not isinstance(m, (int, float)) or m <= 0:
        probs.append("margin must be a positive number in recall units")
    src = str(f.get("margin_source", "")).lower()
    if re.search(r"fold spread|variance|standard error|interval width", src):
        probs.append("margin_source names variance or fold spread. Margins come from the burden tradeoff")
    if f.get("evidence_level") not in LEVELS:
        probs.append(f"evidence_level must be one of {LEVELS}")
    if ci_width and isinstance(m, (int, float)):
        import pandas as pd
        t = pd.read_csv(ci_width)
        n = f.get("planned_blocks")
        row = t.iloc[(t.n_blocks - (n or 0)).abs().argsort()[:1]]
        w = float(row.median_width.iloc[0])
        if w > 2 * m:
            probs.append(f"projected width {w:.3f} at about {int(row.n_blocks.iloc[0])} blocks exceeds 2 x margin {2*m:.3f}")
    return probs


def hashes(f: dict) -> dict:
    out = {}
    s = f.get("scoring", {})
    for k in ("prob", "blocks", "footprint", "void"):
        if s.get(k):
            p = Path(s[k])
            out[k] = ek.sha256(p) if p.exists() else "not yet produced"
    if s.get("truth"):
        p = Path(str(s["truth"]).rsplit(":", 1)[0])
        out["truth"] = ek.sha256(p) if p.exists() else "not yet produced"
    for k in ("split_file", "audit_file"):
        v = f.get(k)
        if v and Path(v).exists():
            out[k] = ek.sha256(Path(v))
    return out


def render(f: dict, template: str, h: dict) -> str:
    heads = re.findall(r"^## (\d+)\. (.+)$", template, re.M)
    out = [f"# Transfer pre-registration, {f['area']} ({f['task']})", "",
           f"**Status.** Filled {dt.date.today().isoformat()} by `_transfer_prereg_fill.py` from "
           "`docs/iterations/transfer_prereg_template.md`. Commit before viewing any target output. "
           "Do not edit after scoring. Add an amendment instead.", ""]
    for num, title in heads:
        out += [f"## {num}. {title}"]
        keys = SECTION_FIELDS.get(int(num), [])
        if not keys:
            out += ["None yet.", ""]
            continue
        for k in keys:
            v = get(f, k)
            out.append(f"- {k}. {json.dumps(v) if isinstance(v, (dict, list)) else v}")
        out.append("")
    out += ["## Input hashes", ""] + [f"- {k}. `{v}`" for k, v in h.items()] + [""]
    block = {**f, "input_sha256": h, "scorer_module_sha256": tl.module_sha256(),
             "filled": dt.datetime.now().isoformat(timespec="seconds")}
    out += ["## Machine-readable block", "", "```json prereg", json.dumps(block, indent=1), "```", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="3.0 S5 fill a transfer preregistration")
    ap.add_argument("--fields", type=Path)
    ap.add_argument("--example", action="store_true", help="print an example fields JSON")
    ap.add_argument("--ci-width", type=Path, default=None)
    ap.add_argument("--template", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.example:
        print(json.dumps(example_fields(), indent=1))
        return 0
    if not a.fields:
        raise SystemExit("give --fields (start from --example)")
    f = json.loads(a.fields.read_text(encoding="utf-8"))
    probs = check(f, a.ci_width)
    if probs:
        print("REFUSING. Fix these fields:\n  " + "\n  ".join(probs))
        return 1
    tpl = a.template or (ek.path_for("docs") / "iterations" / "transfer_prereg_template.md")
    if not tpl.exists():
        raise SystemExit(f"template missing: {tpl}")
    out = a.out or (ek.path_for("docs") / "iterations" / f"transfer_{f['area']}_prereg.md")
    if out.exists():
        raise SystemExit(f"{out} exists. A filled preregistration is never overwritten. Add an amendment by hand.")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(f, tpl.read_text(encoding="utf-8"), hashes(f)), encoding="utf-8")
    tl.read_prereg(out)                                  # round-trip check
    run = ek.new_run("3.0", f"prereg_{f['area']}", f, why="S5 fill a preregistration.")
    ek.write_provenance(run, inputs=[a.fields, tpl], outputs=[out])
    print(f"wrote {out}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
