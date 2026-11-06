"""S3 (3.8). Reference stability test and the noise floor.

Purpose
    Candidate references are coherent pixel sets (median coherence at least coherence_min and the lowest
    LOS variance). A reference passes when, for every pair of independent references, the rate of their
    difference series stays inside the noise floor over the whole window. The noise floor is the SD of
    reference-corrected long-term rates at control sites. Several references are kept, never one.
Inputs
    data/ak1/derived/ak_stack_ak1/ak_los_series_ak1.csv (S2, rows with kind = 'reference' added by the
    analyst from the candidate reference pixels, plus control rows)
Outputs
    data/ak1/results/ak_reference_stability_ak1.csv
Run
    python expansions/3_geography/3_8_alaska/src/_ak_reference_stability_ak1.py
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402
from _ak_rate_difference_ak1 import end_of_season_rate  # noqa: E402

ek = gt.ek
EXP = "3.8"


def reference_pairs(ser: pd.DataFrame, eos: int, thaw: list[int]) -> pd.DataFrame:
    refs = ser[ser["kind"] == "reference"]
    wide = refs.pivot_table(index="date", columns="point_id", values="los_mm")
    rows = []
    for a, b in itertools.combinations(wide.columns, 2):
        diff = pd.DataFrame({"date": wide.index, "los_mm": (wide[a] - wide[b]).to_numpy()})
        rows.append({"ref_a": a, "ref_b": b, "diff_rate_mm_yr": end_of_season_rate(diff, eos, thaw)})
    return pd.DataFrame(rows)


def noise_floor(ser: pd.DataFrame, ref_id: str, eos: int, thaw: list[int]) -> float:
    w = ser.pivot_table(index="date", columns="point_id", values="los_mm")
    ctrl = ser.loc[ser["kind"] == "control", "point_id"].unique()
    rates = [end_of_season_rate(pd.DataFrame({"date": w.index, "los_mm": (w[c] - w[ref_id]).to_numpy()}), eos, thaw)
             for c in ctrl]
    return float(np.nanstd(rates))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    try:
        ser = pd.read_csv(gt.require_input(ek.area_dir("ak1") / "derived" / "ak_stack_ak1" / "ak_los_series_ak1.csv",
                                           "S2 series with reference rows"))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    if (ser["kind"] == "reference").sum() == 0:
        print("no reference rows in the series. Add candidate reference pixels in S2.", file=sys.stderr)
        return 2
    pairs = reference_pairs(ser, pr["end_of_season_month"], pr["thaw_months"])
    first = ser.loc[ser["kind"] == "reference", "point_id"].iloc[0]
    nf = noise_floor(ser, first, pr["end_of_season_month"], pr["thaw_months"])
    pairs["noise_floor_mm_yr"] = nf
    pairs["passes"] = pairs["diff_rate_mm_yr"].abs() <= nf
    out = ek.area_dir("ak1") / "results" / "ak_reference_stability_ak1.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(out, index=False)
    print(pairs.to_string(index=False), f"\nall pass: {bool(pairs['passes'].all())}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
