"""S6 (3.7, exploratory). Record association and coordinate quality, after scoring is frozen.

Purpose
    Corrected 5.6 rules (protocol section 4). Full detector output at the frozen cutoff, matched and
    unmatched. Shifted-set null. The whole record set is translated as one by a random vector
    (shift_min_m to shift_max_m). Shifts that move any record outside the scored footprint are rejected,
    so the count and composition stay fixed. Statistic. The share of records with a feature within the
    radius (the radius is the stated uncertainty for legal-land-description records, else assoc_radius_m).
    Normalised excess = (observed - null mean) / (1 - null mean), with a 95% band from the null draws.
    It is not precision and not predictive value. Per record report the nearest drawn feature distance and
    the coordinate class. V2 is assigned only where an independent drawn feature lies inside the stated
    uncertainty AND a blind judge marked it (column blind_agree), never from proximity alone.
Inputs
    expansions/3_geography/3_7_canada/data/interim/can_inventory_rows.gpkg   (S0)
    data/<prov>/results/transfer/xfer_truth_features_<prov>.gpkg, xfer_blocks_roles_<prov>.gpkg
    data/<prov>/results/transfer/can_blind_judgements_<prov>.csv (optional, record_id, blind_agree)
Outputs
    data/<prov>/results/transfer/can_record_assoc_<prov>.csv   (per record)
    data/<prov>/results/transfer/can_record_assoc_<prov>.json  (excess and null band)
Run
    python expansions/3_geography/3_7_canada/src/_can_record_assoc.py --province ab
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
EXP = "3.7"


def nearest_dist(px: np.ndarray, py: np.ndarray, fx: np.ndarray, fy: np.ndarray) -> np.ndarray:
    from scipy.spatial import cKDTree
    if len(fx) == 0:
        return np.full(len(px), np.inf)
    d, _ = cKDTree(np.c_[fx, fy]).query(np.c_[px, py])
    return d


def shifted_null(px, py, radius, fx, fy, footprint, n: int, rmin: float, rmax: float, seed: int, max_tries=50):
    """Translate the whole record set. Reject shifts that lose a record from the footprint."""
    from shapely import contains_xy
    rng = np.random.default_rng(seed)
    vals, rejected = [], 0
    while len(vals) < n and rejected < n * max_tries:
        r, th = rng.uniform(rmin, rmax), rng.uniform(0, 2 * np.pi)
        sx, sy = px + r * np.cos(th), py + r * np.sin(th)
        if not contains_xy(footprint, sx, sy).all():
            rejected += 1
            continue
        vals.append(float(np.mean(nearest_dist(sx, sy, fx, fy) <= radius)))
    return np.array(vals), rejected


def excess(obs: float, null: np.ndarray) -> dict:
    m = float(np.mean(null)) if len(null) else float("nan")
    lo, hi = (np.percentile(null, [2.5, 97.5]) if len(null) else (np.nan, np.nan))
    norm = (obs - m) / (1 - m) if m < 1 else float("nan")
    return {"observed": obs, "null_mean": m, "null_band": [float(lo), float(hi)], "normalised_excess": norm,
            "p_upper": float((np.sum(null >= obs) + 1) / (len(null) + 1)) if len(null) else float("nan"),
            "label": "exploratory. Excess is not precision or predictive value"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--province", required=True)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    pc = cfg["provinces"][a.province]
    area = pc["area"]
    import geopandas as gpd
    d = gt.area_transfer_dir(area)
    try:
        rec = gpd.read_file(gt.require_input(ek.sub(EXP, "data/interim") / "can_inventory_rows.gpkg", "S0 inventory"))
        feats = gpd.read_file(gt.require_input(d / f"xfer_truth_features_{area}.gpkg", "drawn features"))
        blocks = gpd.read_file(gt.require_input(d / f"xfer_blocks_roles_{area}.gpkg", "scored blocks"))
        gt.require_input(next(iter(sorted(d.glob("*/xfer_score_k40_*.json"))), d / "missing_score.json"),
                         "frozen province score", verify="Association runs only after scoring is frozen")
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    crs = cfg["areas"][area]["crs"]
    rec = rec[(rec["province"] == a.province) & rec["coord_ok"]].to_crs(crs)
    fp = blocks[blocks["eligible"]].geometry.union_all()
    rec = rec[rec.within(fp)].reset_index(drop=True)
    fc = feats.to_crs(crs).geometry.centroid
    px, py, fx, fy = rec.geometry.x.to_numpy(), rec.geometry.y.to_numpy(), fc.x.to_numpy(), fc.y.to_numpy()
    radius = np.array([u if (c.startswith("lsd") or c == "lot_concession") and pd.notna(u) else pr["assoc_radius_m"]
                       for c, u in zip(rec["coord_class"], rec["uncertainty_m"])], float)
    dist = nearest_dist(px, py, fx, fy)
    obs = float(np.mean(dist <= radius)) if len(rec) else float("nan")
    null, rej = shifted_null(px, py, radius, fx, fy, fp, int(pr["n_shifts"]), pr["shift_min_m"], pr["shift_max_m"],
                             int(pr["master_seed"]))
    res = {**excess(obs, null), "n_records": int(len(rec)), "shifts_kept": int(len(null)), "shifts_rejected": int(rej)}
    rec["nearest_feature_m"] = dist
    rec["radius_m"] = radius
    jp = d / f"can_blind_judgements_{area}.csv"
    agree = pd.read_csv(jp).set_index("record_id")["blind_agree"] if jp.exists() else pd.Series(dtype=bool)
    rec["blind_agree"] = rec["well_id"].map(agree).fillna(False).astype(bool)
    rec.loc[(rec["nearest_feature_m"] <= rec["radius_m"]) & rec["blind_agree"], "v_level"] = "V2"
    rec["evidence_label"] = np.where(rec["v_level"] == "V2", "level-(d) candidate (V2), not confirmed", "record (V0/V1)")
    rec.drop(columns="geometry").to_csv(d / f"can_record_assoc_{area}.csv", index=False)
    (d / f"can_record_assoc_{area}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2), f"\nwrote {d / f'can_record_assoc_{area}.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
