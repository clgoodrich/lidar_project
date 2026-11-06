"""S6 (3.8). Location-only baseline and placebo sets. Required because a coordinate-only classifier beat
radar features in the 9t NISAR audit.

Purpose
    Baseline. Spatially blocked cross-validated AUC of well versus control from coordinates and matching
    covariates alone (logistic regression), against the same model with the displacement features
    (rate, seasonal amplitude) added. If the displacement model does not beat location-only, there is
    no site-specific signal beyond location.
    Placebo. Choose one control per matched set as a pseudo-well, recompute the E2 median difference with
    the remaining controls, repeat. If the placebo interval excludes zero the design is biased. Stop.
    Placebo and injection results are saved before well results are unmasked.
Inputs
    data/ak1/results/ak_rate_difference_ak1.csv (per-point rates, S5b), ak_matches_ak1.csv, ak_controls_ak1.gpkg
    config_3_8.json inputs.site_covariates, control_candidates
Outputs
    data/ak1/results/ak_placebo_ak1.csv
Run
    python expansions/3_geography/3_8_alaska/src/_ak_placebo_ak1.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.8"


def blocked_auc(X: np.ndarray, y: np.ndarray, groups: np.ndarray, seed: int) -> float:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    n_splits = min(5, len(np.unique(groups)))
    if n_splits < 2 or len(np.unique(y)) < 2:
        return float("nan")
    p = np.full(len(y), np.nan)
    for tr, te in GroupKFold(n_splits=n_splits).split(X, y, groups):
        if len(np.unique(y[tr])) < 2:
            continue
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=seed)).fit(X[tr], y[tr])
        p[te] = m.predict_proba(X[te])[:, 1]
    ok = np.isfinite(p)
    return float(roc_auc_score(y[ok], p[ok])) if len(np.unique(y[ok])) == 2 else float("nan")


def placebo_medians(ctrl_vals: pd.DataFrame, B: int, seed: int) -> np.ndarray:
    """ctrl_vals has site_id, value for each matched control. Pseudo-well = one control per set."""
    rng = np.random.default_rng(seed)
    sets = [g["value"].to_numpy() for _, g in ctrl_vals.groupby("site_id") if len(g) >= 2]
    out = []
    for _ in range(B):
        d = []
        for v in sets:
            k = rng.integers(len(v))
            d.append(v[k] - np.delete(v, k).mean())
        out.append(np.median(d) if d else np.nan)
    return np.array(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=2000)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    import geopandas as gpd
    try:
        rd = pd.read_csv(gt.require_input(ek.area_dir("ak1") / "results" / "ak_rate_difference_ak1.csv", "S5b"))
        series = pd.read_csv(gt.require_input(ek.area_dir("ak1") / "derived" / "ak_stack_ak1" / "ak_los_series_ak1.csv", "S2"))
        matches = pd.read_csv(gt.require_input(ek.sub(EXP, "data/interim") / "ak_matches_ak1.csv", "S5a"))
        scov = pd.read_csv(gt.config_input(cfg, "site_covariates", EXP))
        cand = pd.read_csv(gt.config_input(cfg, "control_candidates", EXP))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    from _ak_rate_difference_ak1 import end_of_season_rate, seasonal_amplitude
    pts = series.groupby(["point_id", "kind"]).apply(lambda g: pd.Series({
        "rate": end_of_season_rate(g, pr["end_of_season_month"], pr["thaw_months"]),
        "amp": seasonal_amplitude(g, pr["thaw_months"])}), include_groups=False).reset_index()
    cov_cols = pr["match_continuous"]
    sites_g = gpd.read_file(ek.sub(EXP, "data/interim") / "ak_wells_sites_ak1.gpkg").dissolve("site_id").centroid.to_crs(4326)
    s = scov.assign(lon=scov["site_id"].map(sites_g.x), lat=scov["site_id"].map(sites_g.y), y=1, point_id=scov["site_id"])
    c = cand[cand["cand_id"].isin(matches["cand_id"])].assign(y=0, point_id=lambda d: d["cand_id"])
    c = c.merge(matches[["cand_id", "site_id"]], on="cand_id")
    allp = pd.concat([s, c], ignore_index=True).merge(pts[["point_id", "rate", "amp"]], on="point_id", how="left")
    allp = allp.dropna(subset=["rate"])
    groups = allp["site_id"].astype(str).to_numpy()
    base_X = allp[["lon", "lat"] + cov_cols].to_numpy(float)
    auc_loc = blocked_auc(base_X, allp["y"].to_numpy(), groups, int(pr["master_seed"]))
    auc_disp = blocked_auc(np.c_[base_X, allp[["rate", "amp"]].to_numpy(float)], allp["y"].to_numpy(), groups,
                           int(pr["master_seed"]))
    cv = c.merge(pts[["point_id", "rate"]], on="point_id").rename(columns={"rate": "value"})
    pm = placebo_medians(cv[["site_id", "value"]].dropna(), a.B, int(pr["master_seed"]) + 5)
    lo, hi = np.nanpercentile(pm, [2.5, 97.5])
    res = pd.DataFrame([{"auc_location_only": auc_loc, "auc_with_displacement": auc_disp,
                         "displacement_beats_location": bool(auc_disp > auc_loc) if np.isfinite(auc_disp) else None,
                         "placebo_median": float(np.nanmedian(pm)), "placebo_lo": float(lo), "placebo_hi": float(hi),
                         "design_biased": bool(lo > 0 or hi < 0)}])
    out = ek.area_dir("ak1") / "results" / "ak_placebo_ak1.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)
    print(res.T.to_string(), f"\nwrote {out}")
    if res["design_biased"].iloc[0]:
        print("STOP. Placebo interval excludes zero. The design is biased. Fix before reading well results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
