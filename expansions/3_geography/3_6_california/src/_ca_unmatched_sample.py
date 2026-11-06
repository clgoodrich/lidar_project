"""S6 (3.6). Unmatched top-K candidate adjudication. Draw the sample, then summarise two blind labels.

Purpose
    --draw. A seeded random sample of n_unmatched_sample unmatched candidates from the top K per km2
    (K = 40) of the primary score run. Writes a blind sheet with an id, centroid and an empty label
    column for two annotators (vocabulary missed_pad, equipment_yard, building_or_road, natural, other).
    --summarise. Agreement between the two labels (Cohen kappa), share per class with Clopper-Pearson
    intervals on agreed labels, and the missed-pad share as an estimate of annotation incompleteness.
Inputs
    data/<run_id>/xfer_candidates_<arm>_<area>.csv (core 'score'), xfer_blocks_roles_<area>.gpkg
    config_3_6.json inputs.unmatched_labels (filled sheet, assumed)
Outputs
    data/<area>/results/transfer/ca_unmatched_sheet_<area>.csv
    data/<area>/results/transfer/ca_unmatched_summary_<area>.json
Run
    python expansions/3_geography/3_6_california/src/_ca_unmatched_sample.py --area ca1 --cands <csv> --draw
    python expansions/3_geography/3_6_california/src/_ca_unmatched_sample.py --area ca1 --summarise
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.6"
VOCAB = ["missed_pad", "equipment_yard", "building_or_road", "natural", "other"]


def draw_unmatched(cands: pd.DataFrame, eligible_km2: float, n: int, seed: int, k_per_km2=gt.K_PER_KM2):
    k = int(round(k_per_km2 * eligible_km2))
    top = cands.sort_values(["score", "area_m2", "blob_id"], ascending=[False, False, True]).head(k)
    un = top[top["truth_id"].isna()]
    rng = np.random.default_rng(seed)
    pick = un.iloc[sorted(rng.choice(len(un), min(n, len(un)), replace=False))] if len(un) else un
    sheet = pick[["blob_id", "row", "col", "block_id"]].rename(columns={"blob_id": "cand_id"}).copy()
    sheet["cand_id"] = sheet["cand_id"].astype(str)
    sheet["label_a"], sheet["label_b"] = "", ""
    return sheet, {"k": k, "top_k_unmatched": int(len(un)), "sampled": int(len(pick))}


def summarise(lab: pd.DataFrame) -> dict:
    for c in ("label_a", "label_b"):
        bad = set(lab[c].dropna()) - set(VOCAB)
        if bad:
            raise ValueError(f"{c} has labels outside the vocabulary {bad}")
    kappa = gt.cohen_kappa(lab["label_a"], lab["label_b"])
    agreed = lab[lab["label_a"] == lab["label_b"]]
    out = {"n": int(len(lab)), "n_agreed": int(len(agreed)), "kappa": kappa, "shares": {}}
    for v in VOCAB:
        p, lo, hi = ek.clopper_pearson(int((agreed["label_a"] == v).sum()), len(agreed)) if len(agreed) else (np.nan,) * 3
        out["shares"][v] = {"p": p, "ci95": [lo, hi]}
    out["annotation_incompleteness_est"] = out["shares"]["missed_pad"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    ap.add_argument("--cands", default="")
    ap.add_argument("--draw", action="store_true")
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    d = gt.area_transfer_dir(a.area)
    import geopandas as gpd
    try:
        if a.draw:
            c = pd.read_csv(gt.require_input(Path(a.cands), "candidate table from core 'score'"))
            b = gpd.read_file(gt.require_input(d / f"xfer_blocks_roles_{a.area}.gpkg", "block roles"))
            km2 = b[(b["role"] == "test") & b["eligible"]]["area_km2"].sum()
            sheet, info = draw_unmatched(c, km2, int(cfg["prereg"]["n_unmatched_sample"]), int(cfg["prereg"]["master_seed"]))
            sheet.to_csv(d / f"ca_unmatched_sheet_{a.area}.csv", index=False)
            print(info, f"\nwrote {d / f'ca_unmatched_sheet_{a.area}.csv'}")
        if a.summarise:
            s = summarise(pd.read_csv(gt.config_input(cfg, "unmatched_labels", EXP, area=a.area)))
            (d / f"ca_unmatched_summary_{a.area}.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
            print(json.dumps(s, indent=2))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
