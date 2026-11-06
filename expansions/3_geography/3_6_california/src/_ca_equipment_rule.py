"""S8 (3.6, exploratory). Above-ground equipment rule against the terrain model at equal K (review G-10).

Purpose
    Equipment object. A compact cluster of nDSM cells 1.5 to 12 m above ground, area 1 to 400 m2.
    Parameters are fixed in the config before scoring.
    The rule never looks at truth pads. It flags a model CANDIDATE when an equipment object lies within the
    candidate's equivalent radius plus equip_pad_buffer_m of its centroid. Three rankings share one budget
    K = round(40 * eligible km2) over ALL candidates of the test blocks.
      model   score desc, area desc, blob id asc
      rule    flagged candidates only, same order
      union   flagged candidates first, then the rest, same order (union_rule "flagged_first")
    A pad is found when a kept candidate matches it. Because the union spends the same K, promoting flagged
    false positives can push true hits out, so the union can lose to the model. Paired block bootstrap of
    union minus model recall. Labelled exploratory. Reported for E1 (equipped) and all primary pads.
    The old version flagged truth pads directly and took model OR rule, so it could never lose.
Inputs
    data/<area>/derived/05/ndsm_<area>_05.tif (config input ndsm)
    data/<area>/results/transfer/ca_pads_truth_<area>.gpkg, xfer_blocks_roles_<area>.gpkg
    data/<run_id>/xfer_candidates_<arm>_pad_<area>.csv (core 'score', columns blob_id score area_m2 truth_id x y)
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


def candidate_flags(cands: pd.DataFrame, obj_lab: np.ndarray, transform, buffer_m: float) -> np.ndarray:
    """True where an equipment object cell lies within sqrt(area / pi) + buffer_m of the candidate centroid.

    Truth-free. Distances come from a Euclidean distance transform in metres (non-square cells allowed).
    """
    from scipy.ndimage import distance_transform_edt
    if not len(cands):
        return np.zeros(0, bool)
    if not (obj_lab > 0).any():
        return np.zeros(len(cands), bool)
    dist = distance_transform_edt(obj_lab == 0, sampling=(abs(transform.e), abs(transform.a)))
    cc, rr = ~transform * (cands["x"].to_numpy(float), cands["y"].to_numpy(float))
    rr, cc = np.floor(rr).astype(int), np.floor(cc).astype(int)
    inside = (rr >= 0) & (rr < dist.shape[0]) & (cc >= 0) & (cc < dist.shape[1])
    d = np.full(len(cands), np.inf)
    d[inside] = dist[rr[inside], cc[inside]]
    return d <= np.sqrt(cands["area_m2"].to_numpy(float) / np.pi) + buffer_m


def _order(cands: pd.DataFrame) -> pd.DataFrame:
    return cands.sort_values(["score", "area_m2", "blob_id"], ascending=[False, False, True], kind="mergesort")


def found_at_equal_k(cands: pd.DataFrame, flagged: np.ndarray, k: int, union_rule: str = "flagged_first") -> dict:
    """{model, rule, union: set of truth ids found} with exactly the same budget k for each ranking."""
    if union_rule != "flagged_first":
        raise ValueError(f"unknown union_rule {union_rule}")
    c = cands.assign(_flag=np.asarray(flagged, bool))
    if "duplicate" in c:
        c = c[~c["duplicate"].astype(bool)]
    model = _order(c)
    rule = model[model["_flag"]]
    union = pd.concat([rule, model[~model["_flag"]]])
    hits = lambda df: set(df.head(k)["truth_id"].dropna().tolist())  # noqa: E731
    return {"model": hits(model), "rule": hits(rule), "union": hits(union), "k": int(k),
            "n_flagged": int(c["_flag"].sum()), "n_candidates": int(len(c))}


def model_found(cands: pd.DataFrame, eligible_km2: float, k_per_km2=gt.K_PER_KM2) -> set:
    k = int(round(k_per_km2 * eligible_km2))
    top = _order(cands).head(k)
    return set(top["truth_id"].dropna().astype(int))


def paired_union_gain(pads: pd.DataFrame, B: int, seed: int) -> dict:
    """pads has block_id, model (bool), union (bool). Paired block bootstrap of union recall minus model recall."""
    by = {b: g for b, g in pads.groupby("block_id")}
    keys = list(by)

    def rec(col):
        return lambda bl: float(np.mean(np.concatenate([by[b][col].to_numpy() for b in bl]))) if bl else np.nan
    d, lo, hi, draws = ek.bootstrap_diff(rec("union"), keys, rec("model"), keys, B=B, seed=seed, paired=True,
                                         return_draws=True)
    return {"union_minus_model": d, "ci95": [lo, hi], "undefined_share": ek.undefined_share(draws),
            "label": "exploratory"}


def support_km2(cands_csv: str, test_blocks) -> float:
    """Scored support of the test blocks from the core score JSON beside the candidate table (F07).
    Falls back to the block area_km2 with a printed warning when the JSON is absent."""
    import json
    p = Path(cands_csv)
    js = p.with_name(p.name.replace("xfer_candidates_", "xfer_score_k40_").replace(".csv", ".json"))
    if js.exists():
        sup = (json.loads(js.read_text(encoding="utf-8")).get("scoring") or {}).get("support_km2_by_block")
        if sup:
            return float(sum(sup.get(str(b), 0.0) for b in test_blocks["block_id"]))
    print(f"warning: {js.name} has no support table. Using declared block area", file=sys.stderr)
    return float(test_blocks["area_km2"].sum())


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
    cands = cands[cands["block_id"].isin(test["block_id"])].reset_index(drop=True)
    with rasterio.open(nd) as r:
        ek.assert_crs(r, pads.crs)
        arr = r.read(1).astype(np.float32)
        if r.nodata is not None:
            arr[arr == r.nodata] = np.nan
        obj = equipment_objects(arr, abs(r.res[0] * r.res[1]) ** 0.5, tuple(pr["equip_height_m"]),
                                tuple(pr["equip_area_m2"]))
        flags = candidate_flags(cands, obj, r.transform, float(pr["equip_pad_buffer_m"]))
    k = int(round(gt.K_PER_KM2 * support_km2(a.cands, test)))
    found = found_at_equal_k(cands, flags, k)
    for col in ("model", "rule", "union"):
        pads[col] = pads["truth_id"].isin(found[col])
    rows = []
    for name, sub in (("primary", pads), ("E1", pads[pads["class"] == "E1"])):
        if len(sub) == 0:
            continue
        g = paired_union_gain(sub, a.B, int(pr["master_seed"]))
        rows.append({"set": name, "n_pads": len(sub), "recall_model": sub["model"].mean(), "recall_rule": sub["rule"].mean(),
                     "recall_union": sub["union"].mean(), "union_minus_model": g["union_minus_model"],
                     "lo": g["ci95"][0], "hi": g["ci95"][1], "undefined_share": g["undefined_share"],
                     "k": found["k"], "n_flagged": found["n_flagged"], "union_rule": "flagged_first",
                     "label": "exploratory, equal K over all candidates"})
    out = d / f"ca_equipment_rule_vs_model_{a.area}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(pd.DataFrame(rows).to_string(index=False), f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
