"""S5 (3.6). Primary pad scoring at K = 40 per km2 against E1 and E2, with class, ceiling and density tables.

Purpose
    Primary (confirmatory). Pad recall at K on E1 + E2 polygons, California minus the 9t isolated pad
    reference, independent block bootstraps, non-inferiority against -margin (D-CA1).
    Secondary. Recall by class (E1, E2, E3) and E0, each scored apart and never pooled into the primary.
    Ceiling per block min(1, K / density). If more than 25% of blocks have a ceiling below 0.9 the primary
    is flagged not interpretable and the density-scaled K becomes the descriptive result.
    Q2 status is never read here (QC check 10).
Inputs
    data/<area>/results/transfer/<run_id>/pad_prob_<area>_05.tif   (core 'infer --task pad')
    data/<area>/results/transfer/xfer_blocks_roles_<area>.gpkg, ca_pads_truth_<area>.gpkg
    config_3_6.json reference.tables (3.0 isolated pad out-of-fold block tables)
Outputs
    data/<area>/results/transfer/ca_pad_recall_by_class_<area>.csv
    data/<area>/results/transfer/ca_pad_primary_<area>.json
Run
    python expansions/3_geography/3_6_california/src/_ca_pad_recall_by_class.py --area ca1 --prob <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.6"


def class_rows(prob: Path, truth, blocks, classes_sets: dict) -> tuple[list, dict]:
    rows, tabs_by = [], {}
    for name, cls in classes_sets.items():
        t = truth[truth["class"].isin(cls)]
        tabs, _ = gt.score_raster(prob, t, blocks)
        tabs_by[name] = tabs
        ceil = gt.ceiling_per_block(tabs)
        rows.append({"set": name, "classes": "+".join(cls), "n_truth": sum(v["n_truth"] for v in tabs.values()),
                     "recall_k40": gt.pooled_recall_at_k(tabs, list(tabs)), "density_per_km2": gt.density_per_km2(tabs),
                     "share_ceiling_below_0p9": float((ceil["ceiling"] < 0.9).mean()),
                     "evidence_level": "(a) drawn feature"})
    return rows, tabs_by


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    ap.add_argument("--prob", required=True)
    ap.add_argument("--B", type=int, default=2000)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    import geopandas as gpd
    try:
        margin = float(gt.need_decision(cfg, "margin", "D-CA1 tolerable missed pads at K"))
        prob = gt.require_input(Path(a.prob), "pad probability raster")
        blocks = gpd.read_file(gt.require_input(gt.area_transfer_dir(a.area) / f"xfer_blocks_roles_{a.area}.gpkg",
                                                "block roles"))
        truth = gpd.read_file(gt.config_input(cfg, "pads_truth", EXP, area=a.area))
        ref = json.loads(gt.require_input(gt.resolve(cfg["reference"]["tables"]), "9t pad reference tables").read_text())
    except (gt.MissingInputError, gt.DecisionMissingError) as e:
        print(str(e), file=sys.stderr)
        return 2
    assert not any("status" in c.lower() for c in truth.columns), "status must not enter scoring tables"
    blocks = blocks[blocks["role"] == "test"]
    sets = {"primary": cfg["primary_classes"], "E1": ["E1"], "E2": ["E2"], "E3": ["E3"], "E0": ["E0"]}
    rows, tabs_by = class_rows(prob, truth, blocks, sets)
    tab_ref = {b: {"c": pd.DataFrame(v["cands"]), "n_truth": v["n_truth"], "km2": v["km2"]} for b, v in ref.items()}
    prim = gt.transfer_difference(tabs_by["primary"], tab_ref, margin, B=a.B, seed=int(cfg["prereg"]["master_seed"]))
    prim["interpretable"] = rows[0]["share_ceiling_below_0p9"] <= 0.25
    prim["density_scaled_k"] = gt.density_scaled_k(prim["density_target"], prim["density_ref"])
    if not prim["interpretable"]:
        prim["descriptive_density_scaled_recall"] = gt.pooled_recall_at_k(tabs_by["primary"], list(tabs_by["primary"]),
                                                                          prim["density_scaled_k"])
    d = gt.area_transfer_dir(a.area)
    pd.DataFrame(rows).to_csv(d / f"ca_pad_recall_by_class_{a.area}.csv", index=False)
    (d / f"ca_pad_primary_{a.area}.json").write_text(json.dumps(prim, indent=2, default=str), encoding="utf-8")
    print(pd.DataFrame(rows).to_string(index=False))
    print(json.dumps({k: prim[k] for k in ("diff", "diff_ci", "decision", "interpretable")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
