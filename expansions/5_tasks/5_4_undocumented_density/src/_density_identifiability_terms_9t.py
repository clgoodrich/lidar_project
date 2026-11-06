"""5.4 S0. Identifiability table, one row per term of T = D p m / r and of undocumented = T - N_doc.

Purpose
    Says, from the files on disk, which terms are identified, bounded or unidentified today, with the value or range,
    evidence level, source file and what would identify each one. The lead writes
    docs/iterations/density_identifiability.md from this table (this script does not write outside 5.4).

Inputs (config_5_4.json, all optional, status follows from presence)
    accounting (S1), field_bounds output (S3), cohort_excess (5.6 S4), arm_b, arm_c
Outputs
    expansions/5_tasks/5_4_undocumented_density/results/tables/density_identifiability_terms_9t.csv
Run
    python expansions/5_tasks/5_4_undocumented_density/src/_density_identifiability_terms_9t.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402


def terms(cfg) -> pd.DataFrame:
    acc = json.loads(th.inp(cfg, "accounting").read_text()) if th.has(cfg, "accounting") else None
    fb_p = th.resolve(cfg["outputs"]["field_bounds"])
    fb = json.loads(fb_p.read_text()) if fb_p.exists() else None
    rows = []
    if acc:
        bs = acc["D_sites_block_bootstrap"]
        rows.append(dict(term="D", status="identified", value=acc["D_sites"],
                         range=f"block bootstrap {bs['lo']:.0f} to {bs['hi']:.0f}", evidence_level="a",
                         source=th.rel(th.resolve(cfg["outputs"]["accounting"])),
                         identifies_it="Distinct sites at K = 40 per km² (done)"))
        rows.append(dict(term="N_doc", status="identified_conditional", value=acc["N_doc_wells"], range="",
                         evidence_level="b", source=th.rel(th.resolve(cfg["outputs"]["accounting"])),
                         identifies_it="DEP coordinate provenance (R1) to confirm the 5 m merge and footprint scope"))
    else:
        rows.append(dict(term="D", status="unidentified", value="", range="", evidence_level="a", source="",
                         identifies_it="Run _density_distinct_wells_9t.py"))
    if fb:
        p, r = fb["p"], fb["r"]
        rows.append(dict(term="p", status="bounded", value="", range=f"{p['ppv_lower_ci_lo']:.3f} to {p['ppv_upper_ci_hi']:.3f}",
                         evidence_level="d", source=th.rel(fb_p), identifies_it="7.5 Arm B (done)"))
        rows.append(dict(term="r", status="bounded" if r["r_lo"] > 0 else "bounded_below_by_zero",
                         value="", range=f"{r['r_lo']:.3f} to {r['r_hi']:.3f} ({r['label']})", evidence_level="d",
                         source=th.rel(fb_p), identifies_it="7.5 Arm C, repeated searches for sensitivity"))
    else:
        rows.append(dict(term="p", status="unidentified", value="", range="0 to 1", evidence_level="",
                         source="", identifies_it="7.5 Arm B score-stratified field sample with identity status"))
        rows.append(dict(term="r", status="unidentified", value="", range="0 to 1, so no finite upper bound on T",
                         evidence_level="", source="", identifies_it="7.5 Arm C independent searches of sampled areas"))
    rows.append(dict(term="m", status="unidentified", value="", range=str(cfg["grid"]["m_values"]),
                     evidence_level="", source="", identifies_it="Field counts of wells per confirmed site"))
    coh = th.has(cfg, "cohort_excess")
    rows.append(dict(term="cohort_excess", status="descriptive_only" if coh else "not_run", value="", range="",
                     evidence_level="a", source=th.rel(th.resolve(cfg["inputs"]["cohort_excess"]["path"])) if coh else "",
                     identifies_it="Not a density input. No recall-equivalence gate (protocol section 5)"))
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    T = terms(cfg)
    out = th.outp(cfg, "terms")
    T.to_csv(out, index=False)
    print(T[["term", "status", "value", "range"]].to_string(index=False), "\nwrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
