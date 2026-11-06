"""S2. Hazard proxy H for risk ranking on 9t (fw_5_3 section 6 S2).

Purpose
    Build H components from records, mapped inputs and priors only. Never from the endpoint.
    - h_status        status class score (orphan or abandoned highest, plugged lowest), config mapping
    - h_age           age bracket from SPUD_DATE. The 1800-01-01 and 1900-01-01 sentinels are their own class
                      'unknown_sentinel'. A sentinel is never read as early era
    - h_no_plug_record  1 when a record has no plugging date
    - h_depth, h_formation, h_oldest_formation  only when the column's missing share is at most 0.5
    - h_tops_depth    formation top depth from the assumed subsurface tops table, when present
    - surface_evidence_flag  a detector feature at the site, evidence level (a), kept as its own flag
    - pathway_flag    a mapped stream within 100 m. A pathway, not a hazard. NaN when hydrography is absent
    Candidates with no record get the configured '_undocumented_candidate' status score and missing age.
    A lineage check fails the run if any H column is an endpoint column or comes from an endpoint input.
Inputs
    @exp:5.3/results/tables/risk_exposure_sites_9t.csv  (S1)
    dep_wells (held), subsurface_tops (assumed, optional)
Outputs
    @exp:5.3/results/tables/risk_hazard_proxy_9t.csv
    @exp:5.3/results/tables/risk_hazard_summary_9t.json  sources, missing shares, dropped columns, lineage
    run folder @exp:5.3/results/runs/<YYYYMMDD>_risk_hazard_<hash>/
Run
    python expansions/5_tasks/5_3_risk_ranking/src/_risk_hazard_proxy_9t.py
"""
from __future__ import annotations

import argparse
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


def build(cfg, sites: pd.DataFrame, rec: pd.DataFrame | None, tops: pd.DataFrame | None):
    H, lineage, dropped = rc.hazard(sites, cfg, extra_records=rec)
    if tops is not None:
        th.require_columns(tops, ["PERMIT_NUM", "top_depth_m"], "subsurface_tops")
        m = dict(zip("rec_" + tops["PERMIT_NUM"].astype(str), tops["top_depth_m"]))
        H["h_tops_depth"] = [m.get(s, np.nan) for s in sites["site_id"]]
        lineage["h_tops_depth"] = ["subsurface_tops:top_depth_m"]
    col = f"{cfg['pathway_receptor']}_d_nearest"
    if col in sites:
        H["pathway_flag"] = (sites[col].to_numpy(float) <= cfg["pathway_band_m"]).astype(float)
        lineage["pathway_flag"] = [f"{cfg['pathway_receptor']}:geometry"]
    else:
        H["pathway_flag"] = np.nan
        lineage["pathway_flag"] = ["absent"]
    rc.check_lineage(lineage, cfg["endpoint_columns"], cfg["endpoint_inputs"])
    H["H"] = rc.h_index(H)
    ek.assert_rows(H, len(sites), "hazard vs sites")
    summ = dict(n_sites=int(len(H)), dropped_optional=dropped, lineage=lineage,
                missing_share={c: round(float(H[c].isna().mean()), 4) for c in H.columns if c != "site_id"},
                age_bracket_counts=H["age_bracket"].value_counts().to_dict(),
                h_components=[c for c in H.columns if c.startswith("h_")],
                note="H is an index of harm potential given existence, built from records and priors only.")
    return H, summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    src = th.resolve(cfg["outputs"]["exposure_csv"])
    if not src.exists():
        raise th.MissingInput("exposure_csv (S1 output)", src, "Run _risk_exposure_layers_9t.py first.")
    sites = pd.read_csv(src, dtype={"SPUD_DATE": str, "DATE_PLUGG": str})
    run = rio.start_run(cfg, "risk_hazard", "S2 hazard proxy.", ["status_hazard_score", "age_bracket_score"])
    rec = pd.DataFrame(rio.records(cfg).drop(columns="geometry"))
    tops = pd.read_csv(th.inp(cfg, "subsurface_tops")) if th.has(cfg, "subsurface_tops") else None
    H, summ = build(cfg, sites, rec, tops)
    out = th.outp(cfg, "hazard_csv")
    H.to_csv(out, index=False)
    js = th.write_json(th.outp(cfg, "hazard_summary"), summ)
    ek.write_provenance(run, inputs=[src, th.inp(cfg, "dep_wells")], outputs=[out, js], params=summ)
    print(f"dropped optional {summ['dropped_optional']}\nage {summ['age_bracket_counts']}\nwrote {out}\nwrote {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
