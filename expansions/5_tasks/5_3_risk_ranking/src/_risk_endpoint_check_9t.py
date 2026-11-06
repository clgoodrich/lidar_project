"""S6. Endpoint check on documented wells, risk ranking on 9t (fw_5_3 section 6 S6, Q1).

Purpose
    Test whether a scenario puts more endpoint events in the top N than random order, on documented wells only.
    Order is enforced before any endpoint file is opened.
      1. The preregistration JSON must exist (N, delta_enrich_gain, primary scenario, seed, event rule).
      2. The S3 ranks must carry the SHA-256 of that same preregistration (ranks frozen under it).
      3. A ledger records the ranks hash the first time the endpoint is opened. A later run with different
         ranks fails, because the ranks changed after the endpoint was seen.
    Then the field flux table (primary) and the complaints table (secondary, if present) are read.
    Event. Measured rate at or above the preregistered cutoff (or the top decile). Enrichment is events in the
    top N over events expected in a random N, inverse inclusion weights when the table gives inclusion_prob.
    Interval. Block bootstrap over 1 km cells (wells on one lease are one cluster), B = 2000. A resample with no
    event or no top-N site has undefined enrichment. Its share is reported (undefined_share). Any undefined draw
    makes the interval NaN and the decision inconclusive. max_undefined is decided as 0 (config).
    Ranks with ties keep their shared rank, so a tie at the cutoff can put more than N wells in the top set.
    Fewer than 15 events. Clopper-Pearson for the top-N event share and the base share. Decision inconclusive.
    Comparators. Random order (enrichment 1 by construction), records-only order (status then age) and the
    agency list. Agreement with the agency list is reported as agreement, never as validation.
    Spearman of H and of E with log flux are secondary.
Inputs
    prereg, field_flux, complaints (optional), agency_list (optional), all assumed (fw_5_3 section 4A)
    @exp:5.3/results/tables/risk_scenario_ranks_9t.csv, risk_scenario_summary_9t.json (S3)
    @exp:5.3/results/tables/risk_hazard_proxy_9t.csv (S2, records-only order)
Outputs
    @exp:5.3/results/tables/risk_endpoint_enrichment_9t.csv
    @exp:5.3/results/tables/risk_endpoint_open_ledger_9t.json
    run folder @exp:5.3/results/runs/<YYYYMMDD>_risk_endpoint_<hash>/
Run
    python expansions/5_tasks/5_3_risk_ranking/src/_risk_endpoint_check_9t.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _risk_io_9t as rio  # noqa: E402
import _risk_ranking_core as rc  # noqa: E402

ek = th.ek
PREREG_KEYS = ("top_n", "delta_enrich_gain", "primary_scenario", "seed", "endpoint_event_rule")


def check_order(cfg) -> tuple[dict, str, Path]:
    """Steps 1 to 3. Returns (prereg, ranks_sha, ranks_path). Raises before any endpoint read."""
    pp = th.inp(cfg, "prereg")
    prereg = json.loads(pp.read_text(encoding="utf-8"))
    miss = [k for k in PREREG_KEYS if k not in prereg]
    if miss:
        raise SystemExit(f"PREREGISTRATION INCOMPLETE: missing {miss} in {pp}")
    ph = ek.sha256(pp)
    rp, sp = th.resolve(cfg["outputs"]["ranks_csv"]), th.resolve(cfg["outputs"]["ranks_summary"])
    if not rp.exists() or not sp.exists():
        raise th.MissingInput("ranks (S3 output)", rp, "Run _risk_scenarios_9t.py after committing the prereg.")
    s3 = json.loads(sp.read_text(encoding="utf-8"))
    if s3.get("prereg_sha256") != ph:
        raise SystemExit("ORDER VIOLATION: S3 ranks were not built under this preregistration "
                         f"(ranks carry {s3.get('prereg_sha256')}, prereg is {ph}). Rerun S3, then S6.")
    if s3.get("endpoint_inputs_read"):
        raise SystemExit(f"ORDER VIOLATION: S3 read endpoint inputs {s3['endpoint_inputs_read']}")
    rh = ek.sha256(rp)
    lp = th.resolve(cfg["outputs"]["endpoint_ledger"])
    if lp.exists():
        led = json.loads(lp.read_text(encoding="utf-8"))
        if led["ranks_sha256"] != rh or led["prereg_sha256"] != ph:
            raise SystemExit("ORDER VIOLATION: ranks or prereg changed after the endpoint was first opened "
                             f"({lp}). Do not retune after seeing the endpoint.")
    else:
        th.write_json(lp, dict(first_opened=dt.datetime.now().isoformat(timespec="seconds"),
                               ranks_sha256=rh, prereg_sha256=ph))
    return prereg, rh, rp


def endpoint_table(cfg, ranks: pd.DataFrame, rule: dict) -> pd.DataFrame:
    f = pd.read_csv(th.inp(cfg, "field_flux"))
    th.require_columns(f, ["PERMIT_NUM", "flux_kg_h"], "field_flux")
    if "inclusion_prob" not in f:
        f["inclusion_prob"] = 1.0        # simple random or unknown rule. Unknown is stated in the report
    f = f.groupby("PERMIT_NUM", as_index=False).agg(flux_kg_h=("flux_kg_h", "max"),
                                                    inclusion_prob=("inclusion_prob", "first"))
    f["site_id"] = "rec_" + f["PERMIT_NUM"].astype(str)
    d = ranks[ranks.p_source == "record"].merge(f[["site_id", "flux_kg_h", "inclusion_prob"]], on="site_id")
    d["event"], used = rc.endpoint_events_rule(d["flux_kg_h"].to_numpy(), rule)
    d.attrs["event_rule_used"] = used
    d["weight"] = 1.0 / d["inclusion_prob"].clip(lower=1e-6)
    d["cell"] = (np.floor(d.x / cfg["cluster_cell_m"]).astype(int).astype(str) + "_" +
                 np.floor(d.y / cfg["cluster_cell_m"]).astype(int).astype(str))
    return d


def enrich_stat(d: pd.DataFrame, col: str, n: int):
    def f(cells):
        sub = pd.concat([d[d.cell == c] for c in cells], ignore_index=True)
        if not len(sub):
            return np.nan
        r = sub[col].rank(method="min").to_numpy()      # ties keep one rank, never row order
        return rc.enrichment(r, sub["event"].to_numpy(), min(n, len(sub)), sub["weight"].to_numpy())
    return f


def max_undefined(cfg, prereg) -> float:
    """Tolerated share of undefined bootstrap draws. Config max_undefined is 0 (user accepted 2026-11-06, take
    defaults), so any undefined draw gives a NaN interval and an inconclusive decision. A prereg may restate it
    but may not loosen it."""
    want = float(cfg.get("max_undefined", 0.0))
    got = prereg.get("max_undefined")
    if got is not None and float(got) != want:
        raise SystemExit(f"max_undefined {got} in the preregistration differs from the decided value {want}")
    return want


def analyse(d: pd.DataFrame, H: pd.DataFrame, cfg, prereg, agency_col=None, B: int = 2000) -> pd.DataFrame:
    n = rc.top_n_size(len(d), prereg["top_n"], cfg["top_n_share"])
    hm = H.set_index("site_id")
    d = d.copy()
    d["rank_records_only"] = rc._lex_rank([hm.loc[d.site_id, "h_status"].to_numpy(float),
                                           hm.loc[d.site_id, "h_age"].to_numpy(float)])
    cells = sorted(d.cell.unique())
    n_ev = int(d.event.sum())
    rows = []
    cols = [c for c in d.columns if c.startswith("rank_")]
    max_undef = max_undefined(cfg, prereg)
    for c in cols:
        r = d[c].rank(method="min").to_numpy()
        point = rc.enrichment(r, d.event.to_numpy(), n, d.weight.to_numpy())
        top = r <= n
        k_top, k_all = int(d.event[top].sum()), n_ev
        row = dict(order=c[5:], top_n=n, n_wells=len(d), n_events=n_ev, events_in_top=k_top,
                   enrichment=point, primary=(c[5:] == prereg["primary_scenario"]))
        if n_ev < cfg["min_endpoint_events"]:
            p, lo, hi = ek.clopper_pearson(k_top, n)
            pb, lb, hb = ek.clopper_pearson(k_all, len(d))
            row.update(method="clopper_pearson (fewer than 15 events)", top_share=p, top_lo=lo, top_hi=hi,
                       base_share=pb, base_lo=lb, base_hi=hb, decision="inconclusive (fewer than 15 events)")
        else:
            _, lo, hi, dr = ek.block_bootstrap(enrich_stat(d, c, n), cells, B=B, seed=prereg["seed"],
                                               max_undefined=max_undef)
            row.update(method=f"block bootstrap over {cfg['cluster_cell_m']:.0f} m cells, B={B}",
                       enrich_lo=lo, enrich_hi=hi, undefined_share=ek.undefined_share(dr),
                       max_undefined_declared=max_undef)
            g = prereg.get("delta_enrich_gain")
            row["decision"] = (ek.decide(lo - 1, hi - 1, g, "superiority") if g is not None
                               else "no margin preregistered")
        if agency_col is not None and c != agency_col:
            ag = d[agency_col].rank(method="first").to_numpy()
            row["agency_top_n_agreement_jaccard"] = rc.jaccard(set(d.site_id[top]), set(d.site_id[ag <= n]))
        rows.append(row)
    lf = np.log(d.flux_kg_h.clip(lower=1e-6))
    for q in ("H", "E"):
        rho = spearmanr(d[q], lf, nan_policy="omit").statistic
        rows.append(dict(order=f"spearman_{q}_vs_log_flux", n_wells=len(d), enrichment=np.nan, spearman=float(rho),
                         primary=False, method="secondary, exploratory"))
    out = pd.DataFrame(rows)
    out["event_rule_used"] = d.attrs.get("event_rule_used")
    out["statement"] = "Documented wells only. Agreement with an agency list is agreement, not validation."
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    ap.add_argument("--n-boot", type=int, default=2000)
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    prereg, rh, rp = check_order(cfg)           # nothing about the endpoint is read before this returns
    run = rio.start_run(cfg, "risk_endpoint", "S6 endpoint check.", ["min_endpoint_events", "cluster_cell_m"])
    ranks = pd.read_csv(rp)
    H = pd.read_csv(th.resolve(cfg["outputs"]["hazard_csv"]))
    d = endpoint_table(cfg, ranks, prereg["endpoint_event_rule"])
    if not len(d):
        raise SystemExit("ENDPOINT EMPTY: no documented site joins the flux table on PERMIT_NUM. Q1 cannot run.")
    ag = "rank_E" if "rank_E" in d else None
    out = analyse(d, H, cfg, prereg, ag, B=a.n_boot)
    o = th.outp(cfg, "endpoint_csv")
    out.to_csv(o, index=False)
    ins = [th.inp(cfg, "prereg"), rp, th.inp(cfg, "field_flux")]
    rio.write_provenance(run, inputs=ins, outputs=[o], params=dict(prereg=prereg, ranks_sha256=rh),
                        seeds={"bootstrap": prereg["seed"]})
    print(out.to_string(index=False))
    print(f"wrote {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
