"""S5b (3.8). Per-site long-term rate and seasonal amplitude, matched-pair difference E2 and E3.

Purpose
    Long-term rate. Slope (mm/yr) of end-of-season LOS (last usable date in end_of_season_month or the
    nearest earlier thaw month, per year) across years. This removes the seasonal cycle by design.
    Seasonal amplitude. Peak-to-trough LOS change within each thaw season, median over years.
    E2 (primary). Per site, well-site rate minus the mean of its matched controls. Median over sites with
    a site-level bootstrap (B = 2000) and a permutation band (swap well and control labels within
    matching strata). Sites closer than the variogram range of control rates are merged into one cluster
    before resampling. Two-sided decision around delta (D-AK1). E3 is the same for seasonal amplitude.
    Projected width first. Draw n well-site-sized sets from control sites only. Width above 2 delta means
    the design has no power at this n and the study is reported underpowered.
    The result is about sites, never about well integrity.
Inputs
    data/ak1/derived/ak_stack_ak1/ak_los_series_ak1.csv          (S2)
    expansions/3_geography/3_8_alaska/data/interim/ak_matches_ak1.csv, ak_controls_ak1.gpkg (S5a)
Outputs
    data/ak1/results/ak_rate_difference_ak1.csv   (per site)
    data/ak1/results/ak_rate_difference_ak1.json  (E2, E3, width, decision)
Run
    python expansions/3_geography/3_8_alaska/src/_ak_rate_difference_ak1.py
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
EXP = "3.8"


def end_of_season_rate(series: pd.DataFrame, eos_month: int, thaw_months: list[int]) -> float:
    s = series.dropna(subset=["los_mm"]).copy()
    s["date"] = pd.to_datetime(s["date"])
    s = s[s["date"].dt.month.isin(thaw_months) & (s["date"].dt.month <= eos_month)]
    eos = s.sort_values("date").groupby(s["date"].dt.year).tail(1)
    if len(eos) < 2:
        return float("nan")
    t = (eos["date"] - eos["date"].min()).dt.days / 365.25
    return float(np.polyfit(t, eos["los_mm"], 1)[0])


def seasonal_amplitude(series: pd.DataFrame, thaw_months: list[int]) -> float:
    s = series.dropna(subset=["los_mm"]).copy()
    s["date"] = pd.to_datetime(s["date"])
    s = s[s["date"].dt.month.isin(thaw_months)]
    if s.empty:
        return float("nan")
    amp = s.groupby(s["date"].dt.year)["los_mm"].agg(lambda v: v.max() - v.min())
    return float(amp.median())


def decide_two_sided(lo: float, hi: float, delta: float) -> str:
    """fw 3.8 section 10. Difference if |median| lower bound clears delta, equivalence if inside +-delta."""
    if lo > delta or hi < -delta:
        return "decisive, difference"
    if lo > -delta and hi < delta:
        return "decisive, equivalence"
    return "inconclusive"


def variogram_range(x, y, v, bins: int = 12) -> float:
    """Distance where the empirical semivariance first reaches 95% of its sill (coarse, exploratory)."""
    from scipy.spatial.distance import pdist
    d = pdist(np.c_[x, y])
    g = 0.5 * pdist(np.asarray(v)[:, None], "sqeuclidean")
    if len(d) < 3:
        return 0.0
    edges = np.quantile(d, np.linspace(0, 1, bins + 1))
    mids, gam = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (d >= a) & (d <= b)
        if m.any():
            mids.append((a + b) / 2)
            gam.append(g[m].mean())
    gam = np.array(gam)
    sill = np.median(gam[len(gam) // 2:])
    hit = np.nonzero(gam >= 0.95 * sill)[0]
    return float(mids[hit[0]]) if len(hit) else float(mids[-1])


def matched_diffs(per_point: pd.DataFrame, matches: pd.DataFrame, col: str) -> pd.DataFrame:
    """per_point has point_id, kind, <col>. matches has site_id, cand_id, stratum."""
    site = per_point[per_point["kind"] == "site"].set_index("point_id")[col]
    ctrl = per_point[per_point["kind"] == "control"].set_index("point_id")[col]
    m = matches.assign(cv=matches["cand_id"].map(ctrl))
    agg = m.groupby("site_id").agg(ctrl_mean=("cv", "mean"), stratum=("stratum", "first")).reset_index()
    agg["site_v"] = agg["site_id"].map(site)
    agg["diff"] = agg["site_v"] - agg["ctrl_mean"]
    return agg.dropna(subset=["diff"])


def site_bootstrap_median(d: pd.DataFrame, cluster_col: str, B: int, seed: int):
    groups = [g["diff"].to_numpy() for _, g in d.groupby(cluster_col)]
    return ek.block_bootstrap(lambda bl: float(np.median(np.concatenate(bl))) if bl else np.nan, groups, B=B, seed=seed)


def permutation_band(d: pd.DataFrame, per_point: pd.DataFrame, matches: pd.DataFrame, col: str, B: int, seed: int):
    """Swap the site value with one of its own controls at random (within the matching stratum)."""
    rng = np.random.default_rng(seed)
    site = per_point[per_point["kind"] == "site"].set_index("point_id")[col]
    ctrl = per_point[per_point["kind"] == "control"].set_index("point_id")[col]
    grp = {s: g["cand_id"].tolist() for s, g in matches.groupby("site_id")}
    meds = []
    for _ in range(B):
        diffs = []
        for s in d["site_id"]:
            vals = [site[s]] + [ctrl[c] for c in grp[s] if c in ctrl.index]
            k = rng.integers(len(vals))
            pseudo = vals[k]
            rest = [v for i, v in enumerate(vals) if i != k]
            diffs.append(pseudo - np.nanmean(rest))
        meds.append(np.nanmedian(diffs))
    lo, hi = np.nanpercentile(meds, [2.5, 97.5])
    return float(lo), float(hi)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=None)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    B = a.B or int(pr["B"])
    import geopandas as gpd
    try:
        delta = float(gt.need_decision({"prereg": {"delta": pr["delta_mm_yr"]}}, "delta", "D-AK1 actionable rate"))
        ser = pd.read_csv(gt.require_input(ek.area_dir("ak1") / "derived" / "ak_stack_ak1" / "ak_los_series_ak1.csv", "S2 series"))
        matches = pd.read_csv(gt.require_input(ek.sub(EXP, "data/interim") / "ak_matches_ak1.csv", "S5a matches"))
        ctrl = gpd.read_file(gt.require_input(ek.sub(EXP, "data/interim") / "ak_controls_ak1.gpkg", "S5a controls"))
        sites = gpd.read_file(ek.sub(EXP, "data/interim") / "ak_wells_sites_ak1.gpkg")
    except (gt.MissingInputError, gt.DecisionMissingError) as e:
        print(str(e), file=sys.stderr)
        return 2
    pts = ser.groupby(["point_id", "kind"]).apply(lambda g: pd.Series({
        "rate": end_of_season_rate(g, pr["end_of_season_month"], pr["thaw_months"]),
        "amp": seasonal_amplitude(g, pr["thaw_months"])}), include_groups=False).reset_index()
    cpts = ctrl.merge(pts[pts["kind"] == "control"], left_on="cand_id", right_on="point_id")
    rng_m = variogram_range(cpts.geometry.x, cpts.geometry.y, cpts["rate"].fillna(0))
    sc = sites.dissolve("site_id").centroid
    from _ak_wells_sites_ak1 import cluster_sites
    clus = dict(zip(sc.index, cluster_sites(sc.x.to_numpy(), sc.y.to_numpy(), rng_m)))
    res, tables = {"variogram_range_m": rng_m, "delta_mm_yr": delta}, []
    for col, name in (("rate", "E2_rate_mm_yr"), ("amp", "E3_seasonal_amp_mm")):
        d = matched_diffs(pts, matches, col)
        d["cluster"] = d["site_id"].map(clus)
        pt, lo, hi, _ = site_bootstrap_median(d, "cluster", B, int(pr["master_seed"]))
        plo, phi = permutation_band(d, pts, matches, col, min(B, 1000), int(pr["master_seed"]) + 1)
        res[name] = {"median_diff": pt, "ci95": [lo, hi], "perm_band": [plo, phi], "n_sites": int(len(d)),
                     "n_clusters": int(d["cluster"].nunique()),
                     "decision": decide_two_sided(lo, hi, delta) if name.startswith("E2") else "exploratory"}
        tables.append(d.assign(estimand=name))
    cr = pts[pts["kind"] == "control"]["rate"].dropna().to_numpy()
    n = res["E2_rate_mm_yr"]["n_sites"]
    if len(cr) and n:
        w = ek.projected_width(lambda bl: float(np.median(bl)) if len(bl) else np.nan, list(cr), n, B=B, reps=50,
                               seed=int(pr["master_seed"]) + 2)
        res["projected_width"] = {"width": w, "ok": bool(w <= 2 * delta)}
        if w > 2 * delta:
            res["E2_rate_mm_yr"]["decision"] = "underpowered (projected width above 2 delta)"
    out = ek.area_dir("ak1") / "results"
    out.mkdir(parents=True, exist_ok=True)
    pd.concat(tables).to_csv(out / "ak_rate_difference_ak1.csv", index=False)
    (out / "ak_rate_difference_ak1.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
