"""5.4 S3. Conditional bounds on the total from 7.5 field data (Arm B precision, Arm C recall). Blocked until 7.5 runs.

Purpose
    p from Arm B by identity status (protocol section 6 bounds).
        p_lower = confirmed-well weight / total weight, p_upper = 1 - definite-non-well weight / total weight.
        Ambiguous and inaccessible sites sit between. Each bound gets a Clopper-Pearson interval on the Kish n.
    r from Arm C. Detected wells over wells found by independent search, exact interval. If no area was searched
        twice, search sensitivity is unbounded and r is labelled conditional on what searchers find.
    T bounds = [D p_lo m_lo / r_hi, D p_hi m_hi / r_lo]. r_lo = 0 gives an infinite upper bound, stated in words.
    Refuses to run when Arm B's frame hash differs from the S1 site table hash.

Inputs (config_5_4.json)
    accounting   results/tables/density_accounting_9t.json (S1, gives D, N_doc and frame_sha256)
    arm_b        assumed, expansions/7_scale/7_5_field_campaign/data/processed/arm_b_candidate_outcomes.csv
    arm_c        assumed, expansions/7_scale/7_5_field_campaign/data/processed/arm_c_search_outcomes.csv
Outputs
    expansions/5_tasks/5_4_undocumented_density/results/tables/density_field_bounds_9t.json
Run
    python expansions/5_tasks/5_4_undocumented_density/src/_density_field_bounds_9t.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402
import _records_assoc_core as core  # noqa: E402

ek = th.ek
MAP = {"confirmed_well": "correct", "definite_non_well": "wrong", "ambiguous": "ambiguous"}


def check_frame(B: pd.DataFrame, expected: str) -> None:
    """Every Arm B row must quote the S1 site-table hash (review minor: the guard was skippable when the column was
    missing, blank or mixed)."""
    if "frame_sha256" not in B:
        raise SystemExit("FRAME MISSING: arm_b has no frame_sha256 column (schema in config_5_4.json)")
    got = set(B.frame_sha256.astype(str).str.strip())
    if got != {expected}:
        raise SystemExit(f"FRAME MISMATCH: arm_b quotes {sorted(got)[:3]}, density_accounting_9t.json has {expected}")


def p_bounds(B: pd.DataFrame) -> dict:
    th.require_columns(B, ["site_id", "identity", "weight"], "arm_b")
    bad = set(B.identity) - set(MAP)
    if bad:
        raise SystemExit(f"SCHEMA MISMATCH [arm_b]: unknown identity values {bad}")
    return core.link_ppv_bounds(B.identity.map(MAP).to_numpy(), B.weight.to_numpy())


def r_bounds(C: pd.DataFrame, areas: pd.DataFrame | None = None) -> dict:
    """Detector recall from wells found by independent search. Cells with no well add no recall trials,
    but they are sampled cells, so the area counts come from arm_c_search_areas.csv when it is held."""
    th.require_columns(C, ["area_id", "well_id", "detected"], "arm_c")
    wells = C.drop_duplicates("well_id")
    k, n = int(wells.detected.sum()), int(len(wells))
    pt, lo, hi = ek.clopper_pearson(k, n) if n else (float("nan"),) * 3
    repeated = "search_round" in C and C.search_round.nunique() > 1
    if areas is not None:
        th.require_columns(areas, ["area_id", "searched"], "arm_c_areas")
        n_areas, n_inacc = int(areas.searched.astype(int).sum()), int((areas.searched.astype(int) == 0).sum())
    else:
        n_areas, n_inacc = int(C.area_id.nunique()), None   # undercount: cells with no well are invisible
    return dict(k=k, n=n, r=pt, r_lo=lo, r_hi=hi, n_areas=n_areas, n_areas_inaccessible=n_inacc,
                n_areas_source="arm_c_search_areas" if areas is not None else "well rows only (undercount)",
                search_sensitivity_bounded=bool(repeated),
                label="conditional on independent search" if not repeated else "search repeated")


def total_bounds(D: int, pb: dict, rb: dict, m_values) -> dict:
    lo_m, hi_m = min(m_values), max(m_values)
    p_lo, p_hi = pb["ppv_lower_ci_lo"], pb["ppv_upper_ci_hi"]
    r_lo, r_hi = rb["r_lo"], rb["r_hi"]
    lower = D * p_lo * lo_m / r_hi if r_hi > 0 else float("inf")
    upper = D * p_hi * hi_m / r_lo if r_lo > 0 else float("inf")
    return dict(total_lower=lower, total_upper=upper, finite_upper=bool(np.isfinite(upper)),
                statement=("Upper bound is infinite because the lower bound on recall is 0." if not np.isfinite(upper)
                           else "Bounds are conditional on every assumption in fw_5_4 section 5."))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    acc = json.loads(th.inp(cfg, "accounting").read_text())
    B = pd.read_csv(th.inp(cfg, "arm_b"))
    check_frame(B, acc["frame_sha256"])
    C = pd.read_csv(th.inp(cfg, "arm_c"))
    ap_ = th.inp(cfg, "arm_c_areas", must_exist=False) if "arm_c_areas" in cfg["inputs"] else None
    A = pd.read_csv(ap_) if ap_ is not None and Path(ap_).exists() else None
    pb, rb = p_bounds(B), r_bounds(C, A)
    tb = total_bounds(int(acc["D_sites"]), pb, rb, cfg["grid"]["m_values"])
    tb["undocumented_lower"] = tb["total_lower"] - acc["N_doc_wells"]
    tb["undocumented_upper"] = tb["total_upper"] - acc["N_doc_wells"]
    res = dict(D_sites=acc["D_sites"], N_doc_wells=acc["N_doc_wells"], p=pb, r=rb, total=tb,
               evidence_level="d for p and r, a for D", label="conditional bounds, not a count")
    out = th.write_json(th.outp(cfg, "field_bounds"), res)
    print(json.dumps(res, indent=2, default=str), "\nwrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
