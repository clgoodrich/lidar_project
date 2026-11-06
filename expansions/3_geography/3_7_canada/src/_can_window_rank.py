"""S2 and S7 (3.7). Lexicographic window and province ranking from measured values, never from belief.

Purpose
    Rule (fixed in the prereg, lexicographic, not a weighted score).
      1 licence allows derived products and internal labelling
      2 measured ground density at or above the eligibility cut (S1)
      3 record coordinates carry a documented method (S0)
      4 a regional reviewer is committed
      5 at least n_min_blocks blocks with expected drawn features (pilot count)
      6 terrain and canopy similarity to 9t, tie-break only
    A province that fails any of 1 to 5 is "not runnable" and is recorded, not scored.
    S7 writes the same table with the framework's ranking columns and a recommendation line.
    Windows are never chosen by well count alone.
Inputs
    config_3_7.json inputs.province_criteria (assumed, filled from S0, S1, licences, roster)
    expansions/3_geography/3_7_canada/results/tables/can_tile_probe.csv (S1, overrides ground_ppm2 when present)
Outputs
    expansions/3_geography/3_7_canada/results/tables/can_window_scores.csv
    expansions/3_geography/3_7_canada/results/tables/can_province_rank.csv   (--provinces-table)
Run
    python expansions/3_geography/3_7_canada/src/_can_window_rank.py
    python expansions/3_geography/3_7_canada/src/_can_window_rank.py --provinces-table
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.7"


def rank_provinces(df: pd.DataFrame, min_ppm2: float, n_min: int) -> pd.DataFrame:
    d = df.copy()
    d["g1_licence"] = d["licence_ok"].astype(bool)
    d["g2_density"] = d["ground_ppm2"] >= min_ppm2
    d["g3_coords"] = d["coord_method_documented"].astype(bool)
    d["g4_reviewer"] = d["reviewer_committed"].astype(bool)
    d["g5_blocks"] = d["blocks_expected"] >= n_min
    d["runnable"] = d[["g1_licence", "g2_density", "g3_coords", "g4_reviewer", "g5_blocks"]].all(axis=1)
    d["similarity"] = (d["slope_sim"] + d["canopy_sim"]) / 2
    keys = [("runnable", True), ("g1_licence", True), ("g2_density", True), ("g3_coords", True),
            ("g4_reviewer", True), ("g5_blocks", True), ("similarity", True)]
    out = gt.lexicographic_rank(d, keys)
    out["status"] = ["run" if r else "not runnable (" + ",".join(
        g for g in ("g1_licence", "g2_density", "g3_coords", "g4_reviewer", "g5_blocks") if not row[g]) + ")"
        for r, (_, row) in zip(out["runnable"], out.iterrows())]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provinces-table", action="store_true")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    try:
        crit = pd.read_csv(gt.config_input(cfg, "province_criteria", EXP))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    tables = ek.sub(EXP, "results/tables")
    probe = tables / "can_tile_probe.csv"
    if probe.exists():   # measured values win over typed ones
        pm = pd.read_csv(probe).dropna(subset=["ground_ppm2_median"]) if "ground_ppm2_median" in pd.read_csv(probe) else None
        if pm is not None and len(pm):
            crit = crit.merge(pm[["province", "ground_ppm2_median"]], on="province", how="left")
            crit["ground_ppm2"] = crit["ground_ppm2_median"].fillna(crit["ground_ppm2"])
    r = rank_provinces(crit, pr["min_ground_ppm2"], pr["n_min_blocks"])
    r.to_csv(tables / "can_window_scores.csv", index=False)
    print(r[["rank", "province", "status", "ground_ppm2", "similarity"]].to_string(index=False))
    for _, row in r[r["runnable"]].iterrows():
        area = cfg["provinces"][row.province]["area"]
        crs = gt.utm_epsg_csrs(row.window_lon)
        print(f"set areas.{area}.centre_lonlat = [{row.window_lon}, {row.window_lat}] and crs EPSG:{crs} in config_3_7.json")
    if a.provinces_table:
        t = r[["province", "ground_ppm2", "g1_licence", "coord_method_documented", "reviewer_committed",
               "blocks_expected", "rank", "status"]]
        t.to_csv(tables / "can_province_rank.csv", index=False)
        top = r[r["runnable"]].head(1)
        print("recommendation:", f"run {top.province.iloc[0]} first" if len(top) else "no province is runnable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
