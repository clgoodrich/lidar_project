"""S4 and S5. Match anomaly picks to wellheads and lidar centroids, report per site, apply the pilot gate.

Purpose
    For each pilot site, the nearest pick within match_radius_m of the site position is the site's anomaly.
    The table gives stratum, anomaly present or absent, amplitude, signal to noise, localisation error to the
    surveyed wellhead and to the lidar centroid. Outcome (confirmed well d, steel anomaly c, nothing found,
    unresolved, inaccessible) is recorded apart from identity status (confirmed_well, definite_non_well,
    ambiguous) and crossed with it (OUTCOME_TABLE). A confirmed well with no anomaly is a miss. A blank with a
    pick is a false pick. Steel alone is never identity. Summaries are per stratum and are never pooled.
    Pilot gate (framework section 9). Pass needs every site's noise below target, every repeat-line RMS within
    tolerance, every confuser site not labelled a well, no pick at any blank, and an anomaly at every confirmed
    well in a steel-casing stratum. Any missing check makes the gate incomplete.
    3 to 5 sites test practicality. Nothing here is a sensitivity estimate.
    Feed forward (S5). Realised noise, survey area per hour from the S1 design, strata that need
    non-magnetic evidence.

Inputs
    expansions/4_modalities/4_1_magnetometry/data/raw/pilot_sites.csv      (assumed)
    expansions/4_modalities/4_1_magnetometry/data/raw/wellheads_gnss.csv   (assumed, optional per site)
    expansions/4_modalities/4_1_magnetometry/data/raw/site_identity.csv    (assumed)
    expansions/4_modalities/4_1_magnetometry/results/<magproc run>/mag_anomalies_<site>.csv, mag_qc_<site>.json
    expansions/4_modalities/4_1_magnetometry/results/<magdesign run>/mag_survey_design_<site>.json (optional)

Outputs
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_site_outcomes_pilot.csv
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_stratum_summary_pilot.csv
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_pilot_gate.json

Run
    python expansions/4_modalities/4_1_magnetometry/src/_mag_pick_well_match.py [--proc-run DIR] [--design-run DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mag_shared_io as io  # noqa: E402
from _mag_shared_io import ek  # noqa: E402

EVIDENCE_EARLY = ["unknown_date", "early_era", "dated_pre_steel"]


# 4.1-01. Outcome = identity crossed with the magnetometer result. Identity alone never sets it.
OUTCOME_TABLE = {
    ("confirmed_well", True): "confirmed_well_d",        # independent identity and a steel anomaly agree
    ("confirmed_well", False): "confirmed_well_missed",  # a known well with no anomaly. A miss
    ("definite_non_well", True): "steel_anomaly_c",      # steel that is not a well (confuser)
    ("definite_non_well", False): "nothing_found",
    ("ambiguous", True): "steel_anomaly_c",
    ("ambiguous", False): "nothing_found",
}


def outcome_for(accessible: bool, processed: bool, identity: str, anomaly: bool, stratum: str) -> str:
    if not accessible:
        return "inaccessible"
    if not processed:
        return "unresolved"
    if identity not in {k for k, _ in OUTCOME_TABLE}:
        raise ValueError(f"unknown identity_status {identity!r}")
    if stratum == "blank" and anomaly:
        return "blank_with_pick"                         # a pick where nothing was buried. A false pick
    return OUTCOME_TABLE[(identity, anomaly)]


def site_outcomes(sites: pd.DataFrame, picks: dict, qcs: dict, wellheads: pd.DataFrame | None,
                  identity: pd.DataFrame | None, radius: float) -> pd.DataFrame:
    wh = wellheads.set_index("site_id") if wellheads is not None and len(wellheads) else None
    idn = identity.set_index("site_id") if identity is not None and len(identity) else None
    rows = []
    for _, s in sites.iterrows():
        sid = s.site_id
        r = {"site_id": sid, "stratum": s.stratum, "processed": sid in picks}
        access = bool(s.get("accessible", 1)) if pd.notna(s.get("accessible", 1)) else True
        p = picks.get(sid)
        ref = (float(s.easting), float(s.northing))
        if wh is not None and sid in wh.index:
            ref = (float(wh.loc[sid, "easting"]), float(wh.loc[sid, "northing"]))
            r["wellhead_h_acc_m"] = float(wh.loc[sid, "h_acc_m"]) if "h_acc_m" in wh else np.nan
        if p is not None and len(p):
            d = np.hypot(p.easting - ref[0], p.northing - ref[1])
            j = int(np.argmin(d))
            hit = d.iloc[j] <= radius
        else:
            hit, j = False, None
        r["anomaly_present"] = bool(hit) if r["processed"] else None
        if hit:
            pk = p.iloc[j]
            r.update(pick_id=int(pk.pick_id), amplitude_nT=float(pk.resid_peak_abs_nT), snr=float(pk.snr),
                     width_m=float(pk.width_m), pick_e=float(pk.easting), pick_n=float(pk.northing))
            if wh is not None and sid in wh.index:
                r["err_to_wellhead_m"] = float(np.hypot(pk.easting - ref[0], pk.northing - ref[1]))
            if pd.notna(s.get("lidar_cx", np.nan)):
                r["err_to_lidar_m"] = float(np.hypot(pk.easting - s.lidar_cx, pk.northing - s.lidar_cy))
        ids = idn.loc[sid, "identity_status"] if idn is not None and sid in idn.index else "ambiguous"
        r["identity_status"] = ids
        r["outcome"] = outcome_for(access, r["processed"], ids, bool(hit), s.stratum)
        q = qcs.get(sid, {})
        r["noise_sigma_nT"] = q.get("noise_sigma_nT")
        r["repeat_rms_nT"] = q.get("repeat_rms_nT")
        r["test_object_found"] = (q.get("test_object") or {}).get("found")
        rows.append(r)
    return pd.DataFrame(rows)


def stratum_summary(t: pd.DataFrame) -> pd.DataFrame:
    """One row per stratum. Never pooled across strata. n is too small for intervals, so range only."""
    g = []
    for st, d in t.groupby("stratum"):
        pr = d[d.processed]
        e = pr["err_to_wellhead_m"] if "err_to_wellhead_m" in pr else pd.Series(dtype=float)
        g.append({"stratum": st, "n_sites": len(d), "n_processed": len(pr),
                  "n_anomaly": int(pr["anomaly_present"].fillna(False).astype(bool).sum()),
                  "err_wellhead_min_m": e.min(), "err_wellhead_max_m": e.max(),
                  "outcomes": json.dumps(d.outcome.value_counts().to_dict()),
                  "note": "single cases, practicality only"})
    return pd.DataFrame(g)


def pilot_gate(t: pd.DataFrame, gc: dict) -> dict:
    checks, missing = {}, []
    pr = t[t.processed]
    if len(pr) == 0:
        return {"verdict": "incomplete", "reason": "no processed sites"}
    checks["noise_below_target"] = bool((pr.noise_sigma_nT < gc["noise_target_nT"]).all())
    rr = pr.repeat_rms_nT
    if rr.isna().any():
        missing.append("repeat line missing at " + ",".join(pr.site_id[rr.isna()]))
    checks["repeat_lines_agree"] = bool((rr.dropna() <= gc["repeat_rms_tol_nT"]).all())
    conf = t[t.stratum == "confuser"]
    if len(conf) == 0:
        missing.append("no confuser site")
    checks["confuser_not_called_well"] = bool((conf.identity_status != "confirmed_well").all()
                                             and (conf.outcome != "confirmed_well_d").all())
    if (conf.identity_status == "ambiguous").any():
        missing.append("confuser identity not recorded")
    # 4.1-01. The magnetometer has to agree with identity. A pick at a blank is a false pick. A confirmed well in
    # a steel-casing stratum with no anomaly is a miss. Early or undated strata can lack steel (wood casing,
    # pulled casing), so a miss there is reported, not failed.
    blanks = pr[pr.stratum == "blank"]
    if len(t[t.stratum == "blank"]) == 0:
        missing.append("no blank site")
    checks["blanks_have_no_pick"] = bool(~(blanks.anomaly_present.fillna(False).astype(bool)).any())
    steel = pr[(pr.identity_status == "confirmed_well") & ~pr.stratum.isin(EVIDENCE_EARLY)]
    checks["confirmed_steel_wells_detected"] = bool(steel.anomaly_present.fillna(False).astype(bool).all())
    early_missed = pr[(pr.outcome == "confirmed_well_missed") & pr.stratum.isin(EVIDENCE_EARLY)]
    to = pr.test_object_found
    if to.isna().any():
        missing.append("test object not placed at " + ",".join(pr.site_id[to.isna()]))
    checks["test_object_found"] = bool(to.dropna().astype(bool).all())
    if not all(checks.values()):
        v = "fail"
    elif missing:
        v = "incomplete"
    else:
        v = "pass"
    return {"verdict": v, "checks": checks, "missing": missing, "thresholds": gc,
            "early_or_undated_wells_missed": early_missed.site_id.tolist(),
            "action": {"pass": "Proceed to 7.5 with magnetics as one evidence type",
                       "fail": "Record. Drop magnetics from 7.5 or change instrument",
                       "incomplete": "Fill the missing checks before calling the gate"}[v],
            "not_a_gate": "population sensitivity (needs 7.5)"}


def feed_forward(t: pd.DataFrame, designs: dict) -> dict:
    pr = t[t.processed]
    aph = [d.get("area_per_hour_m2") for d in designs.values() if d.get("area_per_hour_m2")]
    weak = sorted(set(t.stratum[(t.stratum.isin(EVIDENCE_EARLY))
                                & t.outcome.isin(["nothing_found", "confirmed_well_missed"])]))
    return {"realised_noise_nT": {"min": pr.noise_sigma_nT.min(), "max": pr.noise_sigma_nT.max()},
            "area_per_hour_m2": {"min": min(aph), "max": max(aph)} if aph else None,
            "strata_needing_non_magnetic_evidence": sorted(set(weak) | {"early_era", "unknown_date"}),
            "note": "wood or removed casing has no magnetic signature"}


def run(cfg: dict, out_root: Path | None = None, proc_run: Path | None = None, design_run: Path | None = None,
        sites: pd.DataFrame | None = None, wellheads=None, identity=None) -> dict:
    inputs = []
    if sites is None:
        p = io.need_input(cfg, "pilot_sites")
        inputs.append(p)
        sites = pd.read_csv(p)
        for name in ("wellheads", "site_identity"):
            q = io.resolve(cfg["inputs"][name])
            if q.exists():
                inputs.append(q)
                if name == "wellheads":
                    wellheads = pd.read_csv(q)
                else:
                    identity = pd.read_csv(q)
            else:
                print(f"optional input absent: {name} ({q})")
    ek.assert_unique(sites, "site_id")
    proc_run = Path(proc_run) if proc_run else io.latest_run(cfg["exp_id"], "magproc", out_root)
    picks, qcs = {}, {}
    for sid in sites.site_id:
        a, q = proc_run / f"mag_anomalies_{sid}.csv", proc_run / f"mag_qc_{sid}.json"
        if a.exists() and q.exists():
            picks[sid] = pd.read_csv(a)
            qcs[sid] = json.loads(q.read_text(encoding="utf-8"))
            inputs += [a, q]
    designs = {}
    if design_run:
        for f in Path(design_run).glob("mag_survey_design_*.json"):
            designs[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            inputs.append(f)
    t = site_outcomes(sites, picks, qcs, wellheads, identity, cfg["gate"]["match_radius_m"])
    ek.assert_rows(t, len(sites), "site outcomes")
    summ = stratum_summary(t)
    gate = pilot_gate(t, cfg["gate"])
    gate["feed_forward"] = feed_forward(t, designs)
    gate["evidence_level"] = "(c) steel anomaly for anomalies, (d) only where identity is confirmed independently"
    rd = ek.new_run(cfg["exp_id"], "magmatch", {"gate": cfg["gate"], "proc": str(proc_run)}, base=out_root,
                    why="S4 per-site report and pilot gate")
    o1, o2, o3 = rd / "mag_site_outcomes_pilot.csv", rd / "mag_stratum_summary_pilot.csv", rd / "mag_pilot_gate.json"
    t.to_csv(o1, index=False)
    summ.to_csv(o2, index=False)
    o3.write_text(json.dumps(gate, indent=2, default=str), encoding="utf-8")
    ek.write_provenance(rd, inputs, [o1, o2, o3], params=cfg["gate"])
    print(json.dumps(gate, indent=2, default=str))
    return {"run_dir": rd, "table": t, "summary": summ, "gate": gate}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--proc-run", type=Path, default=None)
    ap.add_argument("--design-run", type=Path, default=None)
    a = ap.parse_args()
    run(io.load_config(a.config), a.out_root, a.proc_run, a.design_run)


if __name__ == "__main__":
    main()
