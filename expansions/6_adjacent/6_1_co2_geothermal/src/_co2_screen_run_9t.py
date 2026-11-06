"""6.1 chain runner. S1 eligibility, S2 layers, S4 counts, S3 summary, S5a claim audit, map, provenance.

Purpose
    Run every automatic stage of the screening package in order into one run folder. The reader check (S5b) is
    a user-only step and is scored separately with _co2_reader_check_9t.py. 6.4 calls run_all() with the
    hydrogen profile and its hooks, so the two packages share one pipeline.
Inputs
    As listed in each stage script. candidates_pit (5.6 output) is the first missing input today.
Outputs
    data/9t/results/screening/<run_id>/ (or --out) holding screen_eligible_mask_9t.gpkg,
    screen_eligible_summary_9t.json, screening_package_9t.gpkg, screening_layers_9t.json,
    screening_counts_9t.csv, screening_summary_9t.md, screen_claim_audit_9t.csv, screening_map_9t.png,
    _CONFIG.json, _RUN.md, _PROVENANCE.json
Run
    python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_screen_run_9t.py [--out DIR] [--candidates-pit FILE]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import _co2_claim_audit_9t as S5
import _co2_eligible_mask_9t as S1
import _co2_screen_counts_9t as S4
import _co2_screen_layers_9t as S2
import _co2_screen_lib as L
import _co2_screen_map_9t as FIG
import _co2_screen_summary_9t as S3
from _co2_screen_lib import ek


def run_all(cfg: dict, prof: dict, out: Path, overrides: dict | None = None, records_hook=None,
            extra_layers=None, extra_rows=None, B: int | None = None, figure: bool = True) -> dict:
    o = overrides or {}
    r1 = S1.build(cfg, prof, out, o)
    r2 = S2.build(cfg, prof, out, o, records_hook=records_hook, extra_layers=extra_layers)
    c = S4.counts(cfg, prof, out, extra_rows=extra_rows, B=B)
    s = S3.write_summary(cfg, prof, out)
    a, n_hits = S5.audit(cfg, prof, out)
    fig = FIG.render(cfg, prof, out) if figure else None
    outs = [r1["gpkg"], r1["json"], r2["gpkg"], r2["json"], c, s, a] + ([fig] if fig else [])
    ins = [p for p in (L.input_path(cfg, k, o.get(k), required=False) for k in cfg["inputs"]) if p is not None]
    ek.write_provenance(out, inputs=ins, outputs=outs, params={"params": cfg["params"], "profile": prof,
                                                              "decisions": cfg["decisions"]},
                        seeds={"master": cfg["params"]["master_seed"]})
    gate = "package success" if n_hits == 0 and r2["info"]["rows"].get("L0_limits") else "package failure"
    return {"out": out, "claim_hits": n_hits, "package_gate": gate, "outputs": [str(x) for x in outs]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    S2.add_cli(ap)
    ap.add_argument("--blocks", default=None)
    ap.add_argument("--ground-density", default=None)
    ap.add_argument("--chm", default=None)
    ap.add_argument("--B", type=int, default=None)
    a = ap.parse_args()
    cfg = L.load_config(a.config)
    prof = L.load_profile(cfg, a.profile, a.profile_file)
    out = L.run_dir(cfg, prof, a.out)
    o = S2.overrides_from(a) | {"blocks": a.blocks, "ground_density": a.ground_density, "chm": a.chm}
    res = run_all(cfg, prof, out, o, B=a.B)
    print(json.dumps(res, indent=2, default=str))
    return 0 if res["claim_hits"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
