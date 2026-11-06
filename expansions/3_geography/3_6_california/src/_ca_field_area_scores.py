"""S1 (3.6). Choose the pilot oil field by stated criteria, not by well count.

Purpose
    Gates first (all must pass). Measured ground density at least min_ground_ppm2, imagery-lidar date gap
    at most max_date_gap_months, developed-land share at most developed_cap.
    Then rank lexicographically. Pad density (pilot count) descending, vegetation cover ascending, newer
    NAIP first. One pilot area is picked. A second only after S3 passes. The Los Angeles catalogue window
    (held) is listed with its tile-box cover so its urban share can be measured before any use.
Inputs
    config_3_6.json inputs.field_candidates (assumed), lidar catalogue (held)
Outputs
    expansions/3_geography/3_6_california/results/tables/ca_area_scores_fields.csv
Run
    python expansions/3_geography/3_6_california/src/_ca_field_area_scores.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.6"


def score_fields(df: pd.DataFrame, pr: dict) -> pd.DataFrame:
    d = df.copy()
    gap, dev = pr.get("max_date_gap_months"), pr.get("developed_cap")
    d["gate_density"] = d["ground_ppm2"] >= pr.get("min_ground_ppm2", 2.0)
    d["gate_date"] = True if gap is None else d["date_gap_months"] <= gap
    d["gate_developed"] = True if dev is None else d["developed_share"] <= dev
    d["passes"] = d["gate_density"] & d["gate_date"] & d["gate_developed"]
    d["gates_unset"] = ",".join(k for k, v in (("max_date_gap_months", gap), ("developed_cap", dev)) if v is None)
    d["neg_veg"] = -d["veg_cover"]
    out = gt.lexicographic_rank(d, [("passes", True), ("pad_density_per_km2", True), ("neg_veg", True),
                                    ("naip_year", True)])
    return out.drop(columns=["neg_veg"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    out = ek.sub(EXP, "results/tables") / "ca_area_scores_fields.csv"
    cov = gt.window_cover_table(["California_LosAngeles"])
    print("Catalogue window (urban, measure developed share first):")
    print(cov.to_string(index=False))
    cov.to_csv(out.with_name("ca_la_window_cover.csv"), index=False)
    try:
        cand = pd.read_csv(gt.config_input(cfg, "field_candidates", EXP))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        print(f"wrote {out.with_name('ca_la_window_cover.csv')}. Field scoring waits on the candidate table.")
        return 2
    s = score_fields(cand, cfg["prereg"])
    s.to_csv(out, index=False)
    print(s[["rank", "field", "passes", "pad_density_per_km2", "veg_cover"]].to_string(index=False), f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
