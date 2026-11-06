"""S1 stratum table for 5.2 era classification (fw_5_2 section 7 S1).

Purpose
    One row per DEP well in the 9t bounding box with a stratum in
    {dated_record, dated_map, sentinel, undated_other}. Priority is dated_record (valid spud date),
    then dated_map (an identity-resolved 4.6 mark, position-only links do not count), then sentinel
    (spud is 1800-01-01), then undated_other. The sentinel is kept as its own value and never imputed.
    If the 4.6 marks file is absent, dated_map is empty and the summary says so.

Inputs (config_5_2.json)
    dep_wells        @dep_wells/venango_wells_all.gpkg (read-only)
    historic_marks   @results_9t/historic/historic_well_marks_9t.gpkg (ASSUMED, from 4.6 S4, optional here)
Outputs
    strata_csv   @exp:5.2/results/tables/era_strata_wells_9t.csv
    run folder   @exp:5.2/results/<YYYYMMDD>_era_strata_<hash>/
Evidence level
    (b) historical records. Strata are bookkeeping, not era claims.
Run
    python expansions/5_tasks/5_2_era_classification/src/_era_strata_wells_9t.py
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


def load_marks(cfg: dict):
    """Identity-resolved marks or None. Schema checked against config."""
    if not th.has(cfg, "historic_marks"):
        return None
    m = th.read_vector(th.inp(cfg, "historic_marks"))
    th.require_columns(m, ["mark_id", "map_id", "map_date", "permit", "identity_basis", "pos_error_m"], "historic_marks")
    m["map_year"] = pd.to_numeric(m["map_date"].astype(str).str[:4], errors="coerce")
    return m


def build_strata(w: pd.DataFrame, marks, cfg: dict) -> pd.DataFrame:
    dc = cfg["dates"]
    spud_cls = ec.classify_dates(w[dc["fields"]["spud"]], dc["sentinels"], dc["first_oil_year"], dc["audit_today"])
    out = pd.DataFrame({"permit": w["PERMIT_NUM"].values, "status": w["WELL_STATU"].values,
                        "x": w["x"].values, "y": w["y"].values, "spud_class": spud_cls.values,
                        "spud_year": ec.valid_year(w[dc["fields"]["spud"]], spud_cls).values})
    resolved = set()
    if marks is not None:
        ok = marks["identity_basis"] != "position_only"
        resolved = set(marks.loc[ok & marks["permit"].notna(), "permit"].astype(str))
    out["has_map_mark"] = out["permit"].astype(str).isin(resolved)
    sent = f"sentinel_{dc['sentinels'][0]}"
    out["stratum"] = np.select(
        [out["spud_class"] == "valid", out["has_map_mark"], out["spud_class"] == sent],
        ["dated_record", "dated_map", ec.SENTINEL_STRATUM], default="undated_other")
    out = th.tag(out, "b", "bookkeeping")
    out["era_basis"] = "stratum_only"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    dep_p = th.inp(cfg, "dep_wells")
    w = th.load_dep(dep_p, bbox=cfg["bbox_9t"])
    marks = load_marks(cfg)
    s = build_strata(w, marks, cfg)
    ek.assert_rows(s, len(w), "strata vs wells in bbox")
    ek.assert_unique(s, "permit")
    csv = th.outp(cfg, "strata_csv")
    s.to_csv(csv, index=False)
    run = ek.new_run("5.2", "era_strata", {"bbox": cfg["bbox_9t"], "marks": marks is not None},
                     base=th.resolve(cfg["outputs"]["runs"]), why="S1 stratum table.")
    ek.write_provenance(run, inputs=[dep_p], outputs=[csv],
                        params={"marks_present": marks is not None,
                                "note": "dated_map empty until 4.6 delivers marks" if marks is None else ""})
    print(s["stratum"].value_counts().to_string())
    if marks is None:
        print("historic_marks absent. dated_map stratum is empty. Build 4.6 S4 first.")
    print(csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
