"""S0 date audit for 5.2 era classification (fw_5_2 section 7 S0).

Purpose
    Count date quality in the DEP export per field (spud, permit, plug). Sentinel 1800-01-01, placeholder
    1900-01-01, null, before 1859, future, valid. Cross-field checks among valid dates. Plug before spud,
    spud before permit by more than the config gap, and the permit-minus-spud year distribution.
    Two scopes. Venango (the whole export) and the 9t bounding box. A third breakdown splits orphan and
    abandoned wells by membership of the 2022-05-09 orphan list (keyed on county and permit). The 2022 CSV has
    no spud field, so the sentinel share is compared inside the 2026 export by cohort, not across snapshots.
    Every number in era_label_audit.md must come from the CSV written here.

Inputs (config_5_2.json)
    dep_wells     @dep_wells/venango_wells_all.gpkg  -> data/_source/reference/dep_wells/venango_wells_all.gpkg (read-only)
    orphan_2022   @reference/legacy_data/US_Documented_Orphan_Wells.csv
Outputs
    date_audit_csv   @exp:5.2/results/tables/era_date_audit_9t.csv          (scope, field, class, n, share)
    date_audit_json  @exp:5.2/results/tables/era_date_audit_summary_9t.json  (cross-field flags, cohort sentinel shares)
    run folder       @exp:5.2/results/<YYYYMMDD>_era_date_audit_<hash>/ with _PROVENANCE.json
Evidence level
    (b) historical records, audit only. No era claim.
Run
    python expansions/5_tasks/5_2_era_classification/src/_era_date_audit_9t.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _era_core_tools as ec  # noqa: E402

ek = th.ek
ORPHAN_STATUSES = ["DEP Orphan List", "DEP Abandoned List", "Abandoned"]


def permit_key_2022(df22: pd.DataFrame, county: str = "Venango") -> set:
    """(county, permit number) keys of the 2022 list. API 37121NNNNN0000 maps to DEP permit 121-NNNNN."""
    d = df22[df22["County"] == county]
    n = d["Well_ident"].astype(str).str.extract(r"API:37(\d{3})(\d{5})")
    return {(county, int(b)) for a, b in n.dropna().itertuples(index=False)}


def audit(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict, dict]:
    dc = cfg["dates"]
    f = dc["fields"]
    cls = {k: ec.classify_dates(df[c], dc["sentinels"], dc["first_oil_year"], dc["audit_today"]) for k, c in f.items()}
    rows = []
    for k, c in cls.items():
        vc = c.value_counts()
        for name, n in vc.items():
            rows.append(dict(field=f[k], date_class=name, n=int(n), share=float(n / len(df)) if len(df) else np.nan))
    cross = ec.cross_field_flags(df, f["spud"], f["permit"], f["plug"], cls, dc["spud_before_permit_gap_days"])
    diff = cross["permit_minus_spud_years"].dropna()
    x = dict(n_rows=int(len(df)),
             plug_before_spud=int(cross["plug_before_spud"].sum()),
             spud_before_permit_gap=int(cross["spud_before_permit_gap"].sum()),
             permit_minus_spud_years=dict(n=int(len(diff)), median=float(diff.median()) if len(diff) else None,
                                          p05=float(diff.quantile(0.05)) if len(diff) else None,
                                          p95=float(diff.quantile(0.95)) if len(diff) else None),
             earliest_valid_spud=float(ec.valid_year(df[f["spud"]], cls["spud"]).min()) if len(df) else None)
    return pd.DataFrame(rows), x, cls


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    dep_p = th.inp(cfg, "dep_wells")
    w = th.load_dep(dep_p)
    x0, y0, x1, y1 = cfg["bbox_9t"]
    in9t = (w.x >= x0) & (w.x <= x1) & (w.y >= y0) & (w.y <= y1)
    scopes = {"venango": w, "9t_bbox": w[in9t]}
    tabs, summ = [], {"evidence_level": "b", "era_basis": "audit_only"}
    for name, d in scopes.items():
        t, x, cls = audit(d, cfg)
        t.insert(0, "scope", name)
        tabs.append(t)
        summ[name] = x
        # Sentinel share among orphan and abandoned wells by 2022 cohort
        if th.has(cfg, "orphan_2022"):
            df22 = pd.read_csv(th.inp(cfg, "orphan_2022"), low_memory=False)
            keys = permit_key_2022(df22)
            m = d["WELL_STATU"].isin(ORPHAN_STATUSES)
            num = d["PERMIT_NUM"].astype(str).str.extract(r"^\d{3}-(\d+)")[0].astype(float)
            on22 = np.array([("Venango", int(k)) in keys if np.isfinite(k) else False for k in num])
            sent = (cls["spud"] == f"sentinel_{cfg['dates']['sentinels'][0]}").to_numpy()
            coh = {}
            for cname, cm in (("on_2022_list", m.to_numpy() & on22), ("not_on_2022_list", m.to_numpy() & ~on22)):
                k, n = int((sent & cm).sum()), int(cm.sum())
                coh[cname] = dict(n=n, n_sentinel=k, share=k / n if n else None,
                                  cp95=list(ek.clopper_pearson(k, n)[1:]) if n else None)
            coh["note"] = "2022 CSV has no spud field. Shares are inside the 2026 export, split by 2022-list membership."
            summ[name]["orphan_sentinel_by_cohort"] = coh
    out = pd.concat(tabs, ignore_index=True)
    out = th.tag(out, "b", "audit")
    out["era_basis"] = "audit_only"
    csv = th.outp(cfg, "date_audit_csv")
    out.to_csv(csv, index=False)
    js = th.write_json(th.outp(cfg, "date_audit_json"), summ)
    run = ek.new_run("5.2", "era_date_audit", {k: cfg[k] for k in ("dates", "bbox_9t")},
                     base=th.resolve(cfg["outputs"]["runs"]), why="S0 date audit of the DEP export.")
    ek.write_provenance(run, inputs=[dep_p], outputs=[csv, js], params=cfg["dates"])
    print(out.to_string(index=False))
    print(csv, js, sep="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
