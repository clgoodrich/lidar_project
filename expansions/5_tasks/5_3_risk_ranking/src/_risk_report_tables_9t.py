"""S7. Report tables for risk ranking on 9t (fw_5_3 section 6 S7).

Purpose
    Write the tables the iteration doc quotes. Every number in the doc comes from these files.
    - risk_topn_<scenario>_9t.csv  top N per scenario with P, H, E, p_source, p_band, rank and the conditional
                                   statement. Never a lone score. Joined to the S5 rank interval when present
    - risk_topn_split_9t.csv       documented wells and candidates ranked in separate lists as well as together
    - risk_report_summary_9t.json  N, counts, which stages ran, which inputs were missing, stability and
                                   sensitivity headlines, endpoint result if S6 ran
    Then a banned-phrase check over every CSV, JSON and MD in the 5.3 results/tables tree. 'validated',
    'probability of a well' and 'risk score' used alone fail the run.
Inputs
    @exp:5.3/results/tables/risk_scenario_ranks_9t.csv, risk_scenario_summary_9t.json (S3, required)
    risk_site_rank_interval_9t.csv (S5), risk_weight_sweep_9t.csv and risk_oneout_change_9t.csv (S4),
    risk_endpoint_enrichment_9t.csv (S6), risk_exposure_summary_9t.json (S1), all optional
Outputs
    @exp:5.3/results/tables/report/  risk_topn_A_9t.csv ... risk_topn_split_9t.csv, risk_report_summary_9t.json
Run
    python expansions/5_tasks/5_3_risk_ranking/src/_risk_report_tables_9t.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _risk_ranking_core as rc  # noqa: E402

ek = th.ek
COLS = ["site_id", "p_source", "p_band", "P", "H", "E", "status", "x", "y", "conditional"]


def opt(cfg, key):
    p = th.resolve(cfg["outputs"][key])
    return p if p.exists() else None


def scan_banned(root: Path, cfg) -> list:
    hits = []
    for p in root.rglob("*"):
        if p.suffix.lower() in (".csv", ".json", ".md") and p.is_file():
            h = rc.banned_phrase_hits(p.read_text(encoding="utf-8", errors="replace"),
                                      cfg["banned_phrases"], cfg["banned_alone"])
            if h:
                hits.append((str(p), h))
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    rp = opt(cfg, "ranks_csv")
    if rp is None:
        raise th.MissingInput("ranks_csv (S3 output)", th.resolve(cfg["outputs"]["ranks_csv"]),
                              "Run _risk_scenarios_9t.py first.")
    ranks = pd.read_csv(rp)
    s3 = json.loads(th.resolve(cfg["outputs"]["ranks_summary"]).read_text(encoding="utf-8"))
    n = s3["top_n"]
    rd = th.resolve(cfg["outputs"]["report_dir"])
    rd.mkdir(parents=True, exist_ok=True)
    si = pd.read_csv(opt(cfg, "site_interval_csv")) if opt(cfg, "site_interval_csv") else None
    outs = []
    for s in s3["scenarios"]:
        t = ranks[ranks[f"rank_{s}"] <= n].sort_values([f"rank_{s}", "site_id"])[
            COLS + [f"rank_{s}"] + ([f"tie_{s}"] if f"tie_{s}" in ranks else [])].copy()
        t.insert(0, "scenario", s)
        if si is not None:
            t = t.merge(si[si.scenario == s][["site_id", "rank_lo", "rank_hi", "topn_freq", "stable_in"]],
                        on="site_id", how="left")
        o = rd / f"risk_topn_{s}_9t.csv"
        t.to_csv(o, index=False)
        outs.append(o)
    split = []
    for s in s3["scenarios"]:
        for src in ("record", "feature_band"):
            sub = ranks[ranks.p_source == src].copy()
            sub["rank_in_list"] = rc._lex_rank([-sub[f"rank_{s}"].to_numpy(float)])
            sub["tie_in_list"] = rc.tie_size(sub["rank_in_list"].to_numpy())
            sub = sub[sub.rank_in_list <= n].sort_values(["rank_in_list", "site_id"])[
                COLS + ["rank_in_list", "tie_in_list"]]
            sub.insert(0, "list", f"{s}_{src}_only")
            split.append(sub)
    o = rd / "risk_topn_split_9t.csv"
    pd.concat(split, ignore_index=True).to_csv(o, index=False)
    outs.append(o)
    summ = dict(top_n=n, n_sites=int(len(ranks)), scenarios=s3["scenarios"], primary=s3["primary"],
                p_source_counts=ranks.p_source.value_counts().to_dict(),
                missing_components=s3.get("missing_components"), e_status=s3.get("e_status"),
                index_rules=s3.get("index_rules"), scenario_report=s3.get("scenario_report"),
                between_scenario_jaccard=s3.get("top_n_jaccard_between_scenarios"),
                stages_run={k: opt(cfg, k) is not None for k in
                            ("exposure_csv", "hazard_csv", "ranks_csv", "sweep_csv", "stability_csv", "endpoint_csv")},
                statement="Scenario rankings are rules. Candidate rows are " + th.CONDITIONAL +
                          ". Stability is not validity. Q1 needs endpoint data.")
    if si is not None:
        summ["stable_in_count"] = si.groupby("scenario").stable_in.sum().to_dict()
    if opt(cfg, "stability_csv"):
        st = pd.read_csv(opt(cfg, "stability_csv"))
        summ["bootstrap_jaccard"] = st.groupby("scenario").jaccard_vs_base.agg(
            median="median", p05=lambda v: v.quantile(0.05)).round(4).to_dict("index")
        fl = cfg.get("stability_floor_jaccard")
        if fl is not None:
            summ["q2_decision"] = {s: ("success" if v["p05"] >= fl else "failure" if v["median"] < fl else "neither")
                                   for s, v in summ["bootstrap_jaccard"].items()}
        else:
            summ["q2_decision"] = "no stability floor set (user decision)"
    summ["stages_run"] = {k: bool(v) for k, v in summ["stages_run"].items()}
    if opt(cfg, "endpoint_csv"):
        summ["endpoint"] = pd.read_csv(opt(cfg, "endpoint_csv")).to_dict("records")
    else:
        summ["endpoint"] = "Q1 not run. Endpoint data absent."
    js = th.write_json(rd / "risk_report_summary_9t.json", summ)
    outs.append(js)
    hits = scan_banned(th.resolve(cfg["outputs"]["audit"]).parent, cfg)
    if hits:
        raise SystemExit(f"BANNED PHRASES in outputs: {hits}")
    for p in outs:
        print(f"wrote {p}")
    print("banned-phrase check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
