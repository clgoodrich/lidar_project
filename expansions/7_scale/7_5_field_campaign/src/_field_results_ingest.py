"""Validate and reconcile field records into one site table and a visit log (7.5 S5, QC section 8).

Purpose
    Read the filled entry template(s). Check every code against the codebook. Check that the GNSS position
    lies within 30 m of the sampled target (flag, never silently move). Keep every attempted visit in the
    visit log, including refusals, access failures and weather. Reconcile to one primary record per site.
      - search_round 1 is the primary search. The latest complete round-1 record wins and the rest are
        kept in the log as superseded, with the reason.
      - search_round 2 records are independent repeats. They are kept apart for search sensitivity (S4).
      - A sampled site with no record, or with only failed access, is inaccessible and its identity is
        ambiguous. It stays in the denominator.
    Consistency rules. steel_anomaly_only never gives confirmed_well identity. nothing_found never gives
    definite_non_well unless an identifying basis is written. Breaches are errors, not warnings.

    Child well records (review F16). One row per well found in a visit, linked by visit_id. Every well keeps its
    own position, identity and tied agency record. Wells inherit the status of their visit. A round-2 well within
    well_merge_m of a round-1 well of the same site is the same well and shares its well_id. An area cell whose
    primary outcome is confirmed_well must list at least one confirmed well, and a nothing_found cell none.

Inputs
    one or more filled CSVs with the columns of field_entry_template_v1.csv
    optional well CSVs with the columns of field_well_template_v1.csv (--wells)
    results/tables/field_sample_blind_v1.csv, results/field_sheets_v1/field_codebook_v1.json
Outputs (expansions/7_scale/7_5_field_campaign/results/tables/)
    field_visit_log_v1.csv       every row received, with qc flags and status (primary, superseded, repeat)
    field_results_clean_v1.csv   one row per sampled site (outcome, identity, access, flags)
    field_repeat_searches_v1.csv round-2 records joined to their round-1 result
    field_wells_clean_v1.csv     one row per found well per visit (well_id, status, identity, tied_record_id)

Run
    python expansions/7_scale/7_5_field_campaign/src/_field_results_ingest.py --records team1.csv team2.csv --wells wells1.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _field_sample_draw_frames import CFG, ek, load_cfg, need  # noqa: E402
from _field_sheet_generate import ENTRY_COLUMNS, WELL_COLUMNS, codebook  # noqa: E402


def validate(rec: pd.DataFrame, blind: pd.DataFrame, cb: dict, coord_m: float) -> pd.DataFrame:
    missing = [c for c in ENTRY_COLUMNS if c not in rec.columns]
    if missing:
        raise AssertionError(f"field records lack columns {missing}")
    r = rec.copy()
    r["qc"] = ""
    def flag(mask, msg):
        r.loc[mask, "qc"] = r.loc[mask, "qc"].where(r.loc[mask, "qc"] == "", r.loc[mask, "qc"] + ";") + msg
    unknown_site = ~r["site_id"].isin(blind["site_id"])
    if unknown_site.any():
        raise AssertionError(f"records for sites not in the sample {r.loc[unknown_site, 'site_id'].tolist()[:5]}")
    for col, allowed in (("access", cb["access"]), ("outcome", cb["outcome"]), ("identity", cb["identity"])):
        bad = r[col].notna() & ~r[col].isin(allowed)
        if bad.any():
            raise AssertionError(f"invalid {col} codes {sorted(set(r.loc[bad, col]))}")
    ev = r["evidence_codes"].fillna("").astype(str)
    bad_ev = ev.apply(lambda s: [e for e in s.split(";") if e and e not in cb["evidence"]])
    if bad_ev.apply(len).any():
        raise AssertionError(f"invalid evidence codes {sorted({e for v in bad_ev for e in v})}")
    steel_conf = (r["outcome"] == "steel_anomaly_only") & (r["identity"] == "confirmed_well")
    if steel_conf.any():
        raise AssertionError("steel_anomaly_only cannot give identity confirmed_well (protocol section 6)")
    nf_nonwell = (r["outcome"] == "nothing_found") & (r["identity"] == "definite_non_well") & r["identity_basis"].fillna("").eq("")
    if nf_nonwell.any():
        raise AssertionError("nothing_found gives definite_non_well only with a written identifying basis")
    visited = r["access"] == "visited"
    no_outcome = visited & r["outcome"].isna()
    flag(no_outcome, "visited_without_outcome")
    b = blind.set_index("site_id")
    dx = r["gnss_x"].astype(float) - r["site_id"].map(b["x"])
    dy = r["gnss_y"].astype(float) - r["site_id"].map(b["y"])
    dist = np.hypot(dx, dy)
    r["gnss_offset_m"] = dist.round(2)
    flag(visited & (dist > coord_m), f"gnss_over_{coord_m:.0f}m")
    flag(visited & r["searcher_id"].isna(), "no_searcher_id")
    flag((r["blind_confirmed"].astype(str).str.lower() != "true") & visited, "blinding_not_confirmed")
    return r


def reconcile(r: pd.DataFrame, blind: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    r = r.copy()
    r["date"] = pd.to_datetime(r["date"], errors="coerce")
    r["status"] = "superseded"
    r["search_round"] = r["search_round"].fillna(1).astype(int)
    r.loc[r["search_round"] >= 2, "status"] = "repeat"
    prim = r[(r["search_round"] == 1) & (r["access"] == "visited") & r["outcome"].notna()]
    prim = prim.sort_values(["site_id", "date", "visit_id"]).groupby("site_id").tail(1)
    r.loc[prim.index, "status"] = "primary"
    clean = blind[["site_id", "arm"]].merge(prim[["site_id", "visit_id", "outcome", "identity", "access", "qc",
                                                  "magnetic_anomaly", "evidence_codes"]], on="site_id", how="left")
    attempts = r.groupby("site_id")["access"].apply(lambda s: ";".join(sorted(set(s.dropna()))))
    no_rec = clean["outcome"].isna()
    clean.loc[no_rec, "outcome"] = "inaccessible"
    clean.loc[no_rec, "identity"] = "ambiguous"
    clean.loc[no_rec, "access"] = clean.loc[no_rec, "site_id"].map(attempts).fillna("not_attempted")
    clean.loc[clean["outcome"].isin(["unresolved", "inaccessible", "steel_anomaly_only"]) & clean["identity"].isna(), "identity"] = "ambiguous"
    ek.assert_rows(clean, len(blind), "one row per sampled site")
    ek.assert_unique(clean, "site_id")
    rep = r[r["status"] == "repeat"][["site_id", "visit_id", "searcher_id", "outcome", "identity"]].merge(
        prim[["site_id", "searcher_id", "outcome", "identity"]], on="site_id", how="left", suffixes=("_r2", "_r1"))
    same_searcher = rep["searcher_id_r2"] == rep["searcher_id_r1"]
    if same_searcher.any():
        raise AssertionError("a repeat search was done by the round-1 searcher. It is not independent")
    return r, clean, rep


def reconcile_wells(wells: pd.DataFrame, log: pd.DataFrame, clean: pd.DataFrame, cb: dict,
                    merge_m: float) -> pd.DataFrame:
    """Validate child well rows against the visit log and give each distinct well one well_id per site."""
    from scipy.spatial import cKDTree
    cols = WELL_COLUMNS + ["search_round", "status", "well_id"]
    w = wells.copy() if wells is not None else pd.DataFrame(columns=WELL_COLUMNS)
    missing = [c for c in WELL_COLUMNS if c not in w.columns]
    if missing:
        raise AssertionError(f"well records lack columns {missing}")
    v = log.drop_duplicates("visit_id").set_index("visit_id")
    if log["visit_id"].duplicated().any():
        raise AssertionError("visit_id must be unique in the visit log to link well records")
    unknown = ~w["visit_id"].isin(v.index)
    if unknown.any():
        raise AssertionError(f"well rows for unknown visits {w.loc[unknown, 'visit_id'].tolist()[:5]}")
    wrong_site = w["site_id"].astype(str).ne(w["visit_id"].map(v["site_id"]).astype(str))
    if wrong_site.any():
        raise AssertionError(f"well rows whose site_id differs from their visit {w.loc[wrong_site, 'visit_id'].tolist()[:5]}")
    not_visited = w["visit_id"].map(v["access"]).ne("visited")
    if not_visited.any():
        raise AssertionError("well rows linked to a visit without access")
    bad = w["identity"].notna() & ~w["identity"].isin(cb["identity"])
    if bad.any() or w["identity"].isna().any():
        raise AssertionError("every well row needs a valid identity code")
    ev = w["evidence_codes"].fillna("").astype(str)
    bad_ev = {e for s in ev for e in s.split(";") if e and e not in cb["evidence"]}
    if bad_ev:
        raise AssertionError(f"invalid evidence codes on well rows {sorted(bad_ev)}")
    if w[["gnss_x", "gnss_y"]].isna().any().any():
        raise AssertionError("every well row needs its own GNSS position")
    w["search_round"] = w["visit_id"].map(v["search_round"]).astype(int)
    w["status"] = w["visit_id"].map(v["status"])
    w["tied_record_id"] = w["tied_record_id"].fillna("").astype(str).str.strip()
    w["well_id"] = None
    for site, g in w[w["status"] != "superseded"].groupby("site_id"):
        r1 = g[g["search_round"] == 1].sort_values("well_seq")
        ids = [f"{site}_w{i + 1}" for i in range(len(r1))]
        w.loc[r1.index, "well_id"] = ids
        later = g[g["search_round"] >= 2].sort_values(["search_round", "well_seq"])
        if not len(later):
            continue
        tree = cKDTree(r1[["gnss_x", "gnss_y"]].to_numpy(float)) if len(r1) else None
        extra = 0
        for i, row in later.iterrows():
            if tree is not None:
                d, j = tree.query([float(row["gnss_x"]), float(row["gnss_y"])])
                if d <= merge_m:
                    w.loc[i, "well_id"] = ids[j]
                    continue
            extra += 1
            w.loc[i, "well_id"] = f"{site}_x{extra}"
    # cell-level consistency on the primary search (arm C area searches)
    prim = w[w["status"] == "primary"]
    n_conf = prim[prim["identity"] == "confirmed_well"].groupby("site_id").size()
    c = clean[clean["arm"] == "C"].set_index("site_id")
    k = c.index.map(n_conf).fillna(0).astype(int)
    lack = c.index[(c["outcome"] == "confirmed_well").to_numpy() & (k == 0)]
    if len(lack):
        raise AssertionError(f"area cells with outcome confirmed_well but no confirmed well row {list(lack)[:5]}")
    contra = c.index[(c["outcome"] == "nothing_found").to_numpy() & (k > 0)]
    if len(contra):
        raise AssertionError(f"area cells with outcome nothing_found but confirmed well rows {list(contra)[:5]}")
    return w[cols].reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.5 S5 field record ingestion.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--records", nargs="+", required=True)
    ap.add_argument("--wells", nargs="*", default=[], help="filled well CSVs (field_well_template_v1.csv columns)")
    ap.add_argument("--blind", default=str(ek.sub("7.5", "results/tables") / "field_sample_blind_v1.csv"))
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    try:
        blind = pd.read_csv(need(Path(a.blind), "blind sample"))
        rec = pd.concat([pd.read_csv(need(Path(p), "field records")) for p in a.records], ignore_index=True)
        wells = (pd.concat([pd.read_csv(need(Path(p), "well records")) for p in a.wells], ignore_index=True)
                 if a.wells else pd.DataFrame(columns=WELL_COLUMNS))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    r = validate(rec, blind, codebook(cfg), cfg["protocol"]["coord_check_m"])
    log, clean, rep = reconcile(r, blind)
    t = ek.sub("7.5", "results/tables")
    log.to_csv(t / "field_visit_log_v1.csv", index=False)
    clean.to_csv(t / "field_results_clean_v1.csv", index=False)
    rep.to_csv(t / "field_repeat_searches_v1.csv", index=False)
    wl = reconcile_wells(wells, log, clean, codebook(cfg), cfg["density_export"]["well_merge_m"])
    wl.to_csv(t / "field_wells_clean_v1.csv", index=False)
    print(json.dumps({"rows": len(log), "sites": len(clean), "identity": clean["identity"].value_counts().to_dict(),
                      "qc_flags": int((log["qc"] != "").sum()),
                      "well_rows": len(wl), "distinct_wells": int(wl["well_id"].nunique())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
