"""S6 of framework 4.7. Describe native drone recall at the 9t density rung beside 9t airborne recall. No attribution.

Purpose. Pick the rung whose measured ground density is closest to the 9t airborne anchor (2.70 per m2), and set its
recall and interval next to the 9t airborne recall at K from the 3.0 scorer. Platform, season, scan geometry and
ground classification all differ, so the table says what differs and draws no cause from the gap.
Inputs.
  data/oilcreek/results/drone/drone_density_curve_oc.csv (from S5)
  data/9t/results/transfer/transfer_score_9t.json (assumed 3.0 scorer output; keys recall, lo, hi)
  expansions/4_modalities/4_7_drone_lidar/results/tables/drone_lidar_provenance_oc.json (from S1, optional)
Outputs.
  data/oilcreek/results/drone/drone_vs_airborne_oc.md
  data/oilcreek/results/drone/drone_vs_airborne_oc.json
Run.
  python expansions/4_modalities/4_7_drone_lidar/src/_drone_vs_airborne_oc.py [--curve CSV] [--airborne JSON] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import _drone_kit_4_7 as dk

DIFFERS = ["platform and flight height", "scan geometry and occlusion", "season and canopy state",
           "ground classification software", "site selection (NETL sites were found with lidar)"]


def main(argv=None) -> int:
    cfg = dk.load_cfg()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--curve", default=None)
    ap.add_argument("--airborne", default=None)
    ap.add_argument("--provenance", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    res_dir = dk.resolve(cfg["outputs"]["results"])
    cv = pd.read_csv(dk.need(Path(a.curve) if a.curve else res_dir / "drone_density_curve_oc.csv", "S5 density curve"))
    air = json.loads(dk.need(Path(a.airborne) if a.airborne else dk.resolve(cfg["inputs"]["airborne_9t_score"]),
                             "9t airborne recall at K (3.0 scorer)", cfg["inputs"]["airborne_9t_score"]).read_text())
    anchor = cfg["ladder"]["anchor_ground_ppsm"]
    row = cv.iloc[(cv.ground_ppsm - anchor).abs().argmin()]
    pp = Path(a.provenance) if a.provenance else dk.resolve(cfg["outputs"]["tables"]) / "drone_lidar_provenance_oc.json"
    cond = json.loads(pp.read_text())["check"]["conditional_on_visibility"] if pp.exists() else True
    res = {"drone_rung_rate": float(row.rate), "drone_ground_ppsm": float(row.ground_ppsm), "drone_recall": float(row.recall),
           "drone_lo": float(row.lo), "drone_hi": float(row.hi), "airborne_ground_ppsm": anchor,
           "airborne_recall": air["recall"], "airborne_lo": air.get("lo"), "airborne_hi": air.get("hi"),
           "what_differs": DIFFERS, "conditional_on_lidar_visible_sites": cond,
           "statement": "Descriptive only. The gap is not attributed to density or to any single factor"}
    out = Path(a.out) if a.out else res_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "drone_vs_airborne_oc.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    md = ["# Drone at the 9t density rung beside 9t airborne", "",
          "| Arm | Ground pts per m2 | Recall at K | 95% interval |", "|---|---|---|---|",
          f"| Drone rung {row.rate:g} | {row.ground_ppsm:.2f} | {row.recall:.3f} | {row.lo:.3f} to {row.hi:.3f} |",
          f"| 9t airborne | {anchor:.2f} | {air['recall']:.3f} | {air.get('lo')} to {air.get('hi')} |", "",
          "Different sites, platforms and seasons. " + "Also differs. " + ", ".join(DIFFERS) + ".",
          "Descriptive only. No cause is drawn from the gap."]
    if cond:
        md.append("The drone row is conditional on lidar-visible sites.")
    (out / "drone_vs_airborne_oc.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    dk.prov(out, "drone_vs_airborne", outputs=[out / "drone_vs_airborne_oc.json"], params=res)
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
