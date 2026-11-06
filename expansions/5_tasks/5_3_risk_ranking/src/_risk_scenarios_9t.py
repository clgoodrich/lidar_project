"""S3. Scenario rankings for risk ranking on 9t (fw_5_3 section 6 S3).

Purpose
    Order sites under named rules. Each scenario is a rule, not a finding.
      A  exposure first, ties by H
      B  hazard first, ties by E
      C  documented wells first, then E
      D  product of rank-scaled P, H and E. Conditional on the feature model. Never the primary
      E  agency default order, only when the agency list exists (assumed input)
    Every row carries P, H, E, p_source and p_band next to the ranks. There is never a lone score.
    Candidate rows carry the statement "conditional on the feature model".
    E is the mean percentile rank of the configured exposure components that exist. H is the mean percentile
    rank of the H components (S2). P is 1 for records and the K-rank band value for candidates.
    When the preregistration file exists its SHA-256 is stamped into the summary, so S6 can check that the
    ranks were frozen before any endpoint file was opened.
Inputs
    @exp:5.3/results/tables/risk_exposure_sites_9t.csv, risk_exposure_summary_9t.json (S1)
    @exp:5.3/results/tables/risk_hazard_proxy_9t.csv (S2)
    agency_list (assumed, optional), prereg (assumed, optional here, required by S6)
Outputs
    @exp:5.3/results/tables/risk_scenario_ranks_9t.csv
    @exp:5.3/results/tables/risk_scenario_summary_9t.json  N, top-N overlap across scenarios, prereg hash
    run folder @exp:5.3/results/runs/<YYYYMMDD>_risk_scenarios_<hash>/
Run
    python expansions/5_tasks/5_3_risk_ranking/src/_risk_scenarios_9t.py
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _risk_io_9t as rio  # noqa: E402
import _risk_ranking_core as rc  # noqa: E402

ek = th.ek


def load_stage_inputs(cfg):
    """S1 and S2 outputs. Fails naming the stage to run when one is absent."""
    need = {"exposure_csv": "_risk_exposure_layers_9t.py", "exposure_summary": "_risk_exposure_layers_9t.py",
            "hazard_csv": "_risk_hazard_proxy_9t.py"}
    for k, script in need.items():
        p = th.resolve(cfg["outputs"][k])
        if not p.exists():
            raise th.MissingInput(k, p, f"Run {script} first.")
    sites = pd.read_csv(th.resolve(cfg["outputs"]["exposure_csv"]), dtype={"SPUD_DATE": str, "DATE_PLUGG": str})
    summ = json.loads(th.resolve(cfg["outputs"]["exposure_summary"]).read_text(encoding="utf-8"))
    H = pd.read_csv(th.resolve(cfg["outputs"]["hazard_csv"]))
    return sites, summ, H


def assemble(sites: pd.DataFrame, H: pd.DataFrame, comps: dict, drop_e=(), drop_h=()) -> pd.DataFrame:
    """P, H, E per site. drop_e / drop_h remove components (S4 one-out)."""
    ek.assert_rows(H, len(sites), "hazard vs sites")
    assert (H["site_id"].to_numpy() == sites["site_id"].to_numpy()).all(), "site order differs between S1 and S2"
    df = sites[["site_id", "x", "y", "p_source", "p_band", "status", "block_id", "conditional",
                "cand_score"]].copy()
    df["P"] = sites["P"].to_numpy(float)
    hc = {c: 1 for c in H.columns if c.startswith("h_") and c not in drop_h
          and pd.api.types.is_numeric_dtype(H[c])}
    df["H"] = rc.index_from(H, hc)
    ec = {c: s for c, s in comps.items() if c not in drop_e}
    df["E"] = rc.index_from(sites, ec)
    return df


def rank_all(df: pd.DataFrame, agency=None) -> pd.DataFrame:
    R = rc.scenario_ranks(df, agency)
    return pd.concat([df.reset_index(drop=True), R.reset_index(drop=True)], axis=1)


def agency_ranks(cfg, sites):
    if not th.has(cfg, "agency_list"):
        return None
    a = pd.read_csv(th.inp(cfg, "agency_list"))
    th.require_columns(a, ["PERMIT_NUM", "agency_rank"], "agency_list")
    m = dict(zip("rec_" + a["PERMIT_NUM"].astype(str), a["agency_rank"]))
    return np.array([m.get(s, np.nan) for s in sites["site_id"]], float)


def prereg_hash(cfg):
    if th.has(cfg, "prereg"):
        return ek.sha256(th.inp(cfg, "prereg"))
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    sites, s1, H = load_stage_inputs(cfg)
    run = rio.start_run(cfg, "risk_scenarios", "S3 scenario rankings.", ["e_components", "primary_scenario"])
    df = assemble(sites, H, s1["e_components_used"])
    ranked = rank_all(df, agency_ranks(cfg, sites))
    n = rc.top_n_size(len(ranked), cfg["top_n_max"], cfg["top_n_share"])
    scen = [c[5:] for c in ranked.columns if c.startswith("rank_")]
    tops = {s: rc.top_set(ranked[f"rank_{s}"], n, ranked.site_id) for s in scen}
    jac = {f"{s}_{t}": round(rc.jaccard(tops[s], tops[t]), 4) for s in scen for t in scen if s < t}
    out = th.outp(cfg, "ranks_csv")
    ranked.to_csv(out, index=False)
    summ = dict(top_n=n, n_sites=int(len(ranked)), scenarios=scen, primary=cfg["primary_scenario"],
                top_n_jaccard_between_scenarios=jac,
                top_n_candidate_share={s: round(float(np.mean([t.startswith("cand_") for t in tops[s]])), 4)
                                       for s in scen},
                e_components=s1["e_components_used"], missing_components=s1["missing_components"],
                prereg_sha256=prereg_hash(cfg), endpoint_inputs_read=[],
                statement=("Scenario rankings are rules, not findings. Candidate rows are " + th.CONDITIONAL + "."))
    js = th.write_json(th.outp(cfg, "ranks_summary"), summ)
    ek.write_provenance(run, inputs=[th.resolve(cfg["outputs"][k]) for k in ("exposure_csv", "hazard_csv")],
                        outputs=[out, js], params=summ)
    print(json.dumps({k: summ[k] for k in ("top_n", "n_sites", "top_n_jaccard_between_scenarios",
                                           "top_n_candidate_share")}, indent=1))
    print(f"wrote {out}\nwrote {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
