"""S8 (3.6, exploratory). Above-ground equipment rule against the terrain model on the same blocks.

Purpose
    Equipment object. A compact cluster of nDSM cells 1.5 to 12 m above ground, area 1 to 400 m2,
    inside a pad polygon or its 10 m buffer. Parameters are fixed in the config before scoring.
    The rule flags a pad when at least one object touches it. Pad-level recall is compared for
    model (pad matched by a top-K candidate), rule, and union, on the same blocks, with a paired block
    bootstrap of union minus model. Labelled exploratory. Reported for E1 (equipped) and all primary pads.
Inputs
    data/<area>/derived/05/ndsm_<area>_05.tif (config input ndsm)
    data/<area>/results/transfer/ca_pads_truth_<area>.gpkg, xfer_blocks_roles_<area>.gpkg
    data/<run_id>/xfer_candidates_<arm>_<area>.csv (core 'score', truth_id column)
Outputs
    data/<area>/results/transfer/ca_equipment_rule_vs_model_<area>.csv
Run
    python expansions/3_geography/3_6_california/src/_ca_equipment_rule.py --area ca1 --cands <csv>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.6"


def equipment_objects(ndsm: np.ndarray, cell: float, h_rng=(1.5, 12.0), a_rng=(1.0, 400.0)) -> np.ndarray:
    """Label raster of compact above-ground clusters within the height and area ranges."""
    from scipy import ndimage
    m = np.isfinite(ndsm) & (ndsm >= h_rng[0]) & (ndsm <= h_rng[1])
    lab, n = ndimage.label(m, structure=np.ones((3, 3), int))
    if n == 0:
        return lab
    area = ndimage.sum(np.ones_like(ndsm), lab, np.arange(1, n + 1)) * cell * cell
    keep = np.r_[False, (area >= a_rng[0]) & (area <= a_rng[1])]
    return np.where(keep[lab], lab, 0)


def rule_flags(obj_lab: np.ndarray, transform, pads, buffer_m: float) -> pd.Series:
    from rasterio.features import rasterize
    pid = rasterize([(g.buffer(buffer_m), int(t)) for g, t in zip(pads.geometry, pads["truth_id"])],
                    out_shape=obj_lab.shape, transform=transform, fill=0, dtype="int32")
    hit = set(np.unique(pid[(obj_lab > 0) & (pid > 0)]).tolist())
    return pads["truth_id"].isin(hit)


def model_found(cands: pd.DataFrame, eligible_km2: float, k_per_km2=gt.K_PER_KM2) -> set:
    k = int(round(k_per_km2 * eligible_km2))
    top = cands.sort_values(["score", "area_m2", "blob_id"], ascending=[False, False, True]).head(k)
    return set(top["truth_id"].dropna().astype(int))


def paired_union_gain(pads: pd.DataFrame, B: int, seed: int) -> dict:
    """pads has block_id, model (bool), union (bool). Paired block bootstrap of union recall minus model recall."""
    by = {b: g for b, g in pads.groupby("block_id")}
    keys = list(by)

    def rec(col):
        return lambda bl: float(np.mean(np.concatenate([by[b][col].to_numpy() for b in bl]))) if bl else np.nan
    d, lo, hi = ek.bootstrap_diff(rec("union"), keys, rec("model"), keys, B=B, seed=seed, paired=True)
    return {"union_minus_model": d, "ci95": [lo, hi], "label": "exploratory"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    ap.add_argument("--cands", required=True)
    ap.add_argument("--B", type=int, default=2000)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    import geopandas as gpd
    import rasterio
    d = gt.area_transfer_dir(a.area)
    try:
        nd = gt.config_input(cfg, "ndsm", EXP, area=a.area)
        pads = gpd.read_file(gt.config_input(cfg, "pads_truth", EXP, area=a.area))
        blocks = gpd.read_file(gt.require_input(d / f"xfer_blocks_roles_{a.area}.gpkg", "block roles"))
        cands = pd.read_csv(gt.require_input(Path(a.cands), "candidate table (core 'score')"))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    test = blocks[(blocks["role"] == "test") & blocks["eligible"]]
    pads = pads[pads["block_id"].isin(test["block_id"]) & pads["class"].isin(cfg["primary_classes"])].copy()
    with rasterio.open(nd) as r:
        ek.assert_crs(r, pads.crs)
        arr = r.read(1).astype(np.float32)
        if r.nodata is not None:
            arr[arr == r.nodata] = np.nan
        obj = equipment_objects(arr, r.res[0], tuple(pr["equip_height_m"]), tuple(pr["equip_area_m2"]))
        pads["rule"] = rule_flags(obj, r.transform, pads, float(pr["equip_pad_buffer_m"])).to_numpy()
    pads["model"] = pads["truth_id"].astype(int).isin(model_found(cands, test["area_km2"].sum()))
    pads["union"] = pads["model"] | pads["rule"]
    rows = []
    for name, sub in (("primary", pads), ("E1", pads[pads["class"] == "E1"])):
        if len(sub) == 0:
            continue
        g = paired_union_gain(sub, a.B, int(pr["master_seed"]))
        rows.append({"set": name, "n_pads": len(sub), "recall_model": sub["model"].mean(), "recall_rule": sub["rule"].mean(),
                     "recall_union": sub["union"].mean(), "union_minus_model": g["union_minus_model"],
                     "lo": g["ci95"][0], "hi": g["ci95"][1], "label": "exploratory"})
    out = d / f"ca_equipment_rule_vs_model_{a.area}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(pd.DataFrame(rows).to_string(index=False), f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
