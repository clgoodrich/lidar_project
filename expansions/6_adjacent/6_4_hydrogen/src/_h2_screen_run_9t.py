"""6.4 S1 to S4. Hydrogen screening package as a profile of the 6.1 pipeline (no second pipeline).

Purpose
    Merge config_6_4.json onto the 6.1 config, select the hydrogen profile and run the 6.1 chain (eligibility,
    layers, counts, summary, claim audit, map) into data/9t/results/screening/h2/<run_id>/. The only hydrogen
    code is here. It adds three things through hooks.
      1. A record-derived penetration flag on L1_records (record depth against reservoir top minus the depth
         uncertainty). It never reads a lidar-derived column. Candidates never get one.
      2. Optional layer L8_monitor_sites when the partner supplies sites. Else listed absent.
      3. Extra count rows (h2_*) for depth coverage, flag counts and wells just outside the field boundary.
    If fewer than min_depth_coverage of records carry a depth, the flag is dropped and the sheet says so.
Inputs
    Everything 6.1 reads, with partner_area replaced by the field boundary, plus
    reservoir_tops  data/_source/partners/h2_partner/reservoir_seal_tops.csv   assumed (required)
    monitor_sites   data/_source/partners/h2_partner/monitor_sites.gpkg        assumed, optional
    completion_history  data/_source/partners/h2_partner/completion_history.csv  assumed, optional
Outputs
    data/9t/results/screening/h2/<run_id>/ holding screening_package_h2_9t.gpkg, screening_summary_h2_9t.md,
    screening_counts_h2_9t.csv, screen_claim_audit_h2_9t.csv, screening_map_h2_9t.png,
    screen_profile_hydrogen.json (the resolved profile, hashed in _PROVENANCE.json), _PROVENANCE.json, _RUN.md
Run
    python expansions/6_adjacent/6_4_hydrogen/src/_h2_screen_run_9t.py [--out DIR] [--reservoir-tops FILE]
    Reader check: python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_reader_check_9t.py --config <merged> ...
    is easier through this script: --reader-answers FILE (or --reader-template).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SRC_61 = HERE.parents[1] / "6_1_co2_geothermal" / "src"
sys.path.insert(0, str(SRC_61))
import _co2_reader_check_9t as RC  # noqa: E402
import _co2_screen_layers_9t as S2  # noqa: E402
import _co2_screen_lib as L  # noqa: E402
import _co2_screen_run_9t as RUN  # noqa: E402
from _co2_screen_lib import ek  # noqa: E402

CONFIG_64 = HERE / "config_6_4.json"
LIDAR_COLUMNS = {"score", "k_rank", "within_k", "nearest_record_m", "in_blind_zone", "ground_density_pts_m2", "void_frac"}


def merged_config(path_64: str | Path | None = None, path_61: str | Path | None = None) -> dict:
    base = L.load_config(path_61)
    d = json.loads(Path(path_64 or CONFIG_64).read_text(encoding="utf-8"))
    cfg = copy.deepcopy(base)
    cfg["exp_id"] = d["exp_id"]
    cfg["decisions"].update(d["decisions"])
    cfg["inputs"].update(d["inputs"])
    cfg["profiles"].update(d["profiles"])
    cfg["h2_params"] = d["h2_params"]
    return cfg


def read_tops(cfg: dict, override=None) -> pd.DataFrame:
    p = L.input_path(cfg, "reservoir_tops", override)
    t = pd.read_csv(p)
    for col in ("reservoir_top", "seal_top", "units"):
        if col not in t:
            raise L.MissingInput(f"{p} lacks column {col}. Schema {cfg['inputs']['reservoir_tops']['schema']}")
    want = cfg["h2_params"]["record_depth_units"]
    bad = set(t.units.astype(str)) - {want}
    if bad:
        raise AssertionError(f"tops units {bad} differ from record depth units '{want}'. Convert upstream. Run fails.")
    return t


def penetration_flag(rec: pd.DataFrame, tops: pd.DataFrame, unc_ft: float, min_cov: float) -> tuple[pd.DataFrame, dict]:
    """Record-only flag. depth_ft > reservoir_top - unc -> 'reaches reservoir (from records)'."""
    used = {"depth_ft", "record_id"}
    assert not (used & LIDAR_COLUMNS)
    r = rec.copy()
    if "permit" in tops and tops["permit"].notna().any():
        tp = tops.dropna(subset=["permit"]).set_index(tops.dropna(subset=["permit"])["permit"].astype(str))
        top = r["record_id"].map(tp["reservoir_top"])
        seal = r["record_id"].map(tp["seal_top"])
        fw = tops[tops["permit"].isna()] if tops["permit"].isna().any() else None
        if fw is not None and len(fw):
            top = top.fillna(float(fw.reservoir_top.iloc[0]))
            seal = seal.fillna(float(fw.seal_top.iloc[0]))
    else:
        top = pd.Series(float(tops.reservoir_top.iloc[0]), index=r.index)
        seal = pd.Series(float(tops.seal_top.iloc[0]), index=r.index)
    depth = pd.to_numeric(r["depth_ft"], errors="coerce")
    cov = float(depth.notna().mean()) if len(r) else 0.0
    info = {"depth_coverage": cov, "min_depth_coverage": min_cov, "dropped": cov < min_cov,
            "rule": f"depth_ft > reservoir_top - {unc_ft} ft", "source": "records only (depth_ft vs reservoir_seal_tops.csv)"}
    if info["dropped"]:
        r["penetration_flag"] = f"dropped. Depth coverage {cov:.2f} under {min_cov:.2f}"
    else:
        flag = np.where(depth.isna() | top.isna(), "unknown",
                        np.where(depth > top - unc_ft, "reaches reservoir (from records)",
                                 np.where(depth > seal - unc_ft, "reaches seal only (from records)",
                                          "above seal (from records)")))
        r["penetration_flag"] = flag
    r["penetration_source"] = info["source"]
    return r, info


def hooks(cfg: dict, overrides: dict):
    state = {}
    tops = read_tops(cfg, overrides.get("reservoir_tops"))
    hp = cfg["h2_params"]

    def records_hook(rec, cfg_, prof):
        r, info = penetration_flag(rec, tops, hp["depth_uncertainty_ft"], hp["min_depth_coverage"])
        comp = L.input_path(cfg_, "completion_history", overrides.get("completion_history"), required=False)
        if comp is not None:
            c = pd.read_csv(comp)
            c["permit"] = c.permit.astype(str)
            n0 = len(r)
            r = r.merge(c.rename(columns={"permit": "record_id"}), on="record_id", how="left")
            ek.assert_rows(r, n0, "completion history join")
        state["flag"] = info
        return r

    def extra_layers(cfg_, prof, area_poly):
        p = L.input_path(cfg_, "monitor_sites", overrides.get("monitor_sites"), required=False)
        if p is None:
            return {}, {"L8_monitor_sites": "partner monitoring sites not supplied"}
        g = L.read_vector(p, cfg_["crs"])
        g["evidence_level"] = "context"
        return {"L8_monitor_sites": g}, {}

    def extra_rows(r_in, cand, cfg_, prof):
        rows = []
        f = r_in.get("penetration_flag", pd.Series(dtype=str)).astype(str)
        info = state.get("flag", {})
        rows.append({"metric": "h2_depth_coverage_share", "value": info.get("depth_coverage", np.nan), "label": "count",
                     "level": "b", "note": "share of records with a depth"})
        if info.get("dropped"):
            rows.append({"metric": "h2_penetration_flag_dropped", "value": 1, "label": "count", "level": "b",
                         "note": "depth coverage under the floor. Flag dropped."})
        else:
            for k, lab in (("reaches reservoir (from records)", "reaches_reservoir"), ("unknown", "unknown")):
                rows.append({"metric": f"h2_flag_{lab}", "value": int((f == k).sum()), "label": "count", "level": "b",
                             "note": "from records only"})
        if "penetration_flag" in cand.columns:
            raise AssertionError("a candidate may not carry a penetration flag")
        return rows

    return records_hook, extra_layers, extra_rows, state


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    S2.add_cli(ap)
    ap.set_defaults(profile="hydrogen")
    ap.add_argument("--config-64", default=None)
    ap.add_argument("--reservoir-tops", default=None)
    ap.add_argument("--monitor-sites", default=None)
    ap.add_argument("--completion-history", default=None)
    ap.add_argument("--blocks", default=None)
    ap.add_argument("--ground-density", default=None)
    ap.add_argument("--chm", default=None)
    ap.add_argument("--B", type=int, default=None)
    ap.add_argument("--reader-answers", default=None)
    ap.add_argument("--reader-template", action="store_true")
    a = ap.parse_args()
    cfg = merged_config(a.config_64, a.config)
    prof = L.load_profile(cfg, "hydrogen")
    out = L.run_dir(cfg, prof, a.out, short="h2screen")
    if a.reader_template:
        print(f"wrote {RC.template(prof, out, cfg['area'])}")
        return 0
    if a.reader_answers:
        res = RC.gate(prof, pd.read_csv(a.reader_answers))
        p = out / L.fname("screen_reader_gate", prof, cfg["area"], "json")
        p.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(json.dumps(res, indent=2))
        return 0
    o = S2.overrides_from(a) | {"blocks": a.blocks, "ground_density": a.ground_density, "chm": a.chm,
                                "reservoir_tops": a.reservoir_tops, "monitor_sites": a.monitor_sites,
                                "completion_history": a.completion_history}
    (out / "screen_profile_hydrogen.json").write_text(json.dumps(prof, indent=2), encoding="utf-8")
    rh, el, er, _ = hooks(cfg, o)
    res = RUN.run_all(cfg, prof, out, o, records_hook=rh, extra_layers=el, extra_rows=er, B=a.B)
    print(json.dumps(res, indent=2, default=str))
    return 0 if res["claim_hits"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
