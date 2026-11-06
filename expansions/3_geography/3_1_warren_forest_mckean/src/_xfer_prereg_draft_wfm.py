"""3.1 S5. Preregistration draft for one transfer arm, filled from saved files with hashes.

Purpose
    Writes a preregistration draft that names every frozen choice before scoring. K, the
    margin, the model policy and checkpoint hashes, the proposal cutoff, the roles file and
    its seed and hash, the buffer, the reference table and its hash, the annotation protocol,
    and the single primary estimand. Anything not yet decided is written as BLOCKER and listed
    at the top, so the draft cannot be mistaken for a committed preregistration. The user
    commits the final file. The scorer refuses to run without it (assumed.prereg).
    If a template exists at --template, its text is appended for the sections it adds.

Inputs
    config_3_1.json, S1 roles gpkg and json, S2 projected width json, reference tables,
    checkpoints (P1 isolated assumed, CV5 held), derived buffer (assumed)

Outputs
    expansions/3_geography/3_1_warren_forest_mckean/results/tables/<area>/xfer_prereg_draft_<area>.md

Run
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_prereg_draft_wfm.py --area warren
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_1.json"


def h(p):
    p = Path(p)
    return ek.sha256(p)[:16] if p.exists() and p.is_file() else "BLOCKER (missing)"


def ckpt_lines(cfg, task):
    out, blockers = [], []
    try:
        xl.assumed_path(cfg, "isolated_ckpt", task=task, k=0)
        src, prov = "P1 isolated", False
    except xl.MissingInput:
        src, prov = "CV5 original sampler (PROVISIONAL)", True
        blockers.append(f"{task}: P1 isolated checkpoints missing")
    for k in range(cfg["models"]["n_folds"]):
        if prov:
            p = xl.resolve_path({**cfg["models"][task]["cv5"], "rel": cfg["models"][task]["cv5"]["rel"].format(k=k)})
        else:
            p = Path(str(xl.resolve_path(cfg["assumed"]["isolated_ckpt"]["spec"])).format(task=task, k=k))
        out.append(f"| {task} | {k} | {src} | `{p}` | {h(p)} |")
    return out, blockers


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--template", default=None)
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    T = ctx["tables"]
    blockers = []
    margin = (cfg.get("margin_delta") or {}).get(a.area)
    if margin is None:
        blockers.append("margin Delta not set (user decision, burden units then recall points)")
    roles_g, roles_j = T / f"xfer_blocks_roles_{a.area}.gpkg", T / f"xfer_blocks_roles_{a.area}.json"
    rj = json.loads(roles_j.read_text()) if roles_j.exists() else {}
    if not rj:
        blockers.append("S1 roles not built")
    elif rj.get("buffer_provisional"):
        blockers.append("buffer is provisional (P1 derived buffer missing)")
    pw = T / f"xfer_projected_width_{a.area}.json"
    if not pw.exists():
        blockers.append("S2 projected width not run")
    elif pw.with_suffix(".csv").exists():
        import pandas as pd
        ok = pd.read_csv(pw.with_suffix(".csv")).gate_width_le_2margin.map(lambda v: v is True or v == "True")
        if not ok.any():
            blockers.append(f"projected width exceeds 2 x Delta ({margin}) in every S2 design cell. Add blocks or revisit Delta")
    ref = xl.resolve_path(cfg["reference"]["blocks_csv"])
    ref_s = xl.resolve_path(cfg["reference"]["summary_json"])
    pol = xl.policy("pit")                     # review F02. The one scoring policy
    if "slope_recall" in str(ref) or "xfer_ref_block_tables" in str(xl.resolve_path(cfg["reference"]["tables"]["pit"])):
        blockers.append("reference tables are provisional (historical CV5 pit). Scores stay descriptive until the P1 isolated baseline")
    lines_pit, b1 = ckpt_lines(cfg, "pit")
    lines_pad, b2 = ckpt_lines(cfg, "pad")
    blockers += b1 + b2
    try:
        xl.assumed_path(cfg, "flight_dates")
    except xl.MissingInput:
        blockers.append("flight dates not recorded (USGS metadata, manifest D1)")
    blockers.append("reviewers and adjudicator not named")
    A = cfg["areas"][a.area]
    md = [f"# Preregistration draft. Transfer {a.area} (arm {A['arm']})", "",
          f"**Generated** {dt.date.today().isoformat()} by `_xfer_prereg_draft_wfm.py`. DRAFT. Not committed. Not valid for scoring.",
          "", "## Blockers", *[f"- {b}" for b in blockers], "",
          "## Primary estimand",
          "Recall of annotated pit floors at K = 40 candidates per km2 of eligible test area, target minus the 9t reference. "
          "Complete blind blocks, including empty ones. Block bootstrap, B = 2000, independent per area. Non-inferiority "
          f"against minus Delta. Delta = {margin if margin is not None else 'BLOCKER'}.", "",
          "## Fixed choices",
          f"- K primary 40 per km2. K = 30 sensitivity only.",
          f"- Scoring policy ek.policy_for({pol['task']}) {pol['policy_hash']}. IoU {pol['iou']}, greedy one-to-one in score order. "
          f"Blobs under {pol['min_area_m2']} m2 dropped. Score = mean probability. Dedupe truth_matched.",
          f"- Proposal cutoff {pol['cutoff']} (ek.policy_for, the sweep's cutoff). Declare it, the IoU, the dedupe, K and the checkpoint in the json prereg block.",
          f"- Model policy {cfg['models']['policy']}.",
          f"- Program {A['program']}. Native density primary. Thinning is a separate sensitivity arm.",
          f"- Roles seed {rj.get('seed', 'BLOCKER')}. Buffer {rj.get('buffer_m', 'BLOCKER')} m. "
          f"Adaptation dropped {rj.get('adaptation_dropped', 'BLOCKER')}.",
          f"- Eligibility. cover >= {cfg['eligibility']['min_cover']}, void <= {cfg['eligibility']['max_void_frac']}, "
          f"density rule {cfg['eligibility']['density_rule']} ({rj.get('density_min_per_m2', 'BLOCKER')} per m2). "
          "Low-density blocks are a reported stratum.", "",
          "## Hashes", "| file | sha256 (16) |", "|---|---|",
          f"| roles `{roles_g}` | {h(roles_g)} |", f"| reference `{ref}` | {h(ref)} |",
          f"| config `{a.config}` | {h(a.config)} |", "",
          "| task | fold | source | checkpoint | sha256 (16) |", "|---|---|---|---|---|", *lines_pit, *lines_pad, "",
          "## Annotation protocol",
          "Two reviewers per test block, layers pit_inside, pit_full and pad, no model output, no well points, no scores. "
          "Third look adjudicates. A seeded 20% of test blocks is re-annotated independently. Exposure logged per block.", "",
          "## Gates",
          "Readiness. Projected width at most 2Delta. Success. Holm-adjusted one-sided bootstrap share under 0.025. "
          "Failure. Upper bound below minus Delta. Otherwise inconclusive. One scoring run.",
          f"- Multiplicity. Holm over the declared primaries {(cfg.get('multiplicity') or {}).get('family')}. "
          "Secondaries are reported, never gated. No undefined bootstrap draw is tolerated (max_undefined 0).", ""]
    if a.template and Path(a.template).exists():
        md += ["## Template text", Path(a.template).read_text(encoding="utf-8")]
    out = T / f"xfer_prereg_draft_{a.area}.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:8 + len(blockers)]))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
