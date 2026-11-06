"""S4 and S5. Change at pads plugged between the flights against matched control pads, with the gate.

Purpose
    For every treated and matched control pad, apply the feature flag rule of _change_features_9t.py to the
    high-passed change field and record the median change. Seam distance is a covariate.
    Primary. Flag rate at treated pads minus flag rate at their matched controls. Interval by cluster bootstrap
    over pad complexes (a match set follows its treated pad's complex). Gate per protocol section 5 with one
    threshold delta_rate in rate units, and the preregistered minimum n. The 0.16 to 0.22 m height floor is a
    measurement spec, not this threshold.
    Secondary. Mean-change difference. Dose response (Spearman) of change against years from plug to late flight.
    Placebo. The same statistic on random splits of the control pool into pseudo-treated and pseudo-control pads,
    which estimates the false-alarm spread of the difference.
    No detectable change is not evidence of no restoration or no plugging. Evidence level (a).

Inputs
    change_controls_matched_9t.gpkg from the newest S2 run (or --ctrl-dir)
    data/9t/derived/lidar_2006_2008/dod_v2_highpass_9t_2m.tif and dem_2019_v2_9t_2m.tif (held)
    qgis/annotations/annotations_proj_v2.gpkg layers pad, pit_full, roads (held, clear zone for moved copies)
    plug_eligible_counts_9t.json from the S1 run named in S2's config (readiness)

Outputs (run folder expansions/4_modalities/4_5_multitemporal_lidar/results/<YYYYMMDD>_dod_compare_<hash7>/)
    plug_change_by_pad_9t.csv     one row per pad in a match set (role, flagged, median dz, seam distance)
    plug_change_compare_9t.json   rate difference with interval, gate verdict, secondary, placebo, n
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_5_multitemporal_lidar/src/_dod_plug_change_compare_9t.py [--ctrl-dir DIR] [--out-root DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _dod_shared_io as io  # noqa: E402
from _dod_shared_io import ek  # noqa: E402
from _dod_recovery_test_9t import seam_distance  # noqa: E402


def measure(pads, field, transform, slope, excl, params, seed: int, seam_d=None) -> pd.DataFrame:
    F = io.Field(field, transform, slope, excl, params, np.random.default_rng(seed))
    res, x0, y1 = float(transform.a), float(transform.c), float(transform.f)
    rows = []
    for _, p in pads.iterrows():
        f = F.flag(p.geometry)
        c = p.geometry.representative_point()
        r_, c_ = int((y1 - c.y) // res), int((c.x - x0) // res)
        sd = float(seam_d[r_, c_]) if seam_d is not None and 0 <= r_ < field.shape[0] and 0 <= c_ < field.shape[1] else np.nan
        rows.append({"pad_id": p.pad_id, "match_id": p.match_id, "role": p.role, "complex_id": p.complex_id,
                     "assessable": f is not None, "flagged": bool(f["changed"]) if f else np.nan,
                     "median_dz_m": f["med"] if f else np.nan, "frac_changed": f["frac_changed"] if f else np.nan,
                     "seam_dist_m": sd, "first_eligible_plug": p.get("first_eligible_plug")})
    return pd.DataFrame(rows)


def rate_diff(D: pd.DataFrame, value: str = "flagged") -> float:
    t, c = D[D.role == "treated"][value].astype(float), D[D.role == "control"][value].astype(float)
    return float(t.mean() - c.mean()) if len(t) and len(c) else float("nan")


def cluster_ci(D: pd.DataFrame, value: str, B: int, seed: int):
    """Clusters are treated-pad complexes. A match set is kept whole and follows its treated pad."""
    cx = D[D.role == "treated"].set_index("match_id").complex_id
    D = D.assign(cluster=D.match_id.map(cx))
    groups = {k: g for k, g in D.groupby("cluster")}
    if len(groups) < 2:
        v = rate_diff(D, value)
        return v, float("nan"), float("nan"), len(groups)
    pt, lo, hi, _ = ek.block_bootstrap(lambda bl: rate_diff(pd.concat([groups[b] for b in bl]), value),
                                       list(groups), B=B, seed=seed)
    return pt, lo, hi, len(groups)


def placebo(pool: pd.DataFrame, n_treated: int, k: int, reps: int, seed: int) -> dict:
    """Random pseudo-treated sets of the treated size, each against k pseudo-controls, from unplugged pads."""
    rng = np.random.default_rng(seed)
    A = pool[pool.assessable]
    need = n_treated * (1 + k)
    if n_treated == 0 or len(A) < need:
        return {"reps": 0, "note": f"pool of {len(A)} too small for {need} pads"}
    d = []
    for _ in range(reps):
        pick = A.iloc[rng.choice(len(A), need, replace=False)]
        d.append(pick.iloc[:n_treated].flagged.astype(float).mean() - pick.iloc[n_treated:].flagged.astype(float).mean())
    d = np.array(d)
    return {"reps": reps, "mean": float(d.mean()), "q025": float(np.quantile(d, 0.025)), "q975": float(np.quantile(d, 0.975))}


def gate(lo: float, hi: float, delta: float, n: int, n_min: int) -> str:
    if n < n_min or not np.isfinite(lo):
        return "inconclusive (n below the preregistered minimum)" if n < n_min else "inconclusive"
    return ek.decide(lo, hi, delta, "superiority")


def run(cfg: dict, out_root: Path | None = None, ctrl_dir: Path | None = None, rasters=None, layers=None,
        pool_pads=None) -> dict:
    import geopandas as gpd
    from scipy import ndimage as ndi
    from scipy.stats import spearmanr
    crs, cp = cfg["crs"], cfg["compare"]
    gp = io.stage_file(None if ctrl_dir is None else Path(ctrl_dir) / "change_controls_matched_9t.gpkg", "dod_ctrl",
                       "change_controls_matched_9t.gpkg", out_root, "S2 matched controls")
    M = gpd.read_file(gp, layer="pads")
    ek.assert_crs(M, crs)
    inputs = [gp]
    if rasters is None:
        pf, pl = io.resolve(cfg["dems"]["dod_highpass"]), io.resolve(cfg["dems"]["late"])
        field, T, _ = io.read_raster(pf, crs)
        late, _, _ = io.read_raster(pl, crs)
        inputs += [pf, pl]
    else:
        field, late, T = rasters
    if layers is None:
        ga = io.resolve(cfg["annotations_gpkg"])
        layers = [io.read_layer(ga, cfg[k], crs) for k in ("pad_layer", "pit_layer", "road_layer")]
        inputs.append(ga)
    res = float(T.a)
    params = io.flag_params(cfg)
    run_dir = ek.new_run(io.EXP, "dod_compare", {"compare": cp, "flag": params, "ctrl": str(gp)}, base=out_root,
                         why="S4 and S5 change at plugged pads against matched controls (fw_4_5 section 6).")
    excl = ndi.binary_dilation(io.feature_mask(layers, field.shape, T, 0), iterations=int(round(40 / res)))
    slope = io.slope_deg(late, res)
    seam_d = seam_distance(field, res)
    D = measure(M, field, T, slope, excl, params, int(cfg["flag_rule"]["seed"]), seam_d)
    ek.assert_rows(D, len(M), "measured pads = matched pads")
    csv = run_dir / "plug_change_by_pad_9t.csv"
    D.to_csv(csv, index=False)
    A = D[D.assessable]
    # a match set with no assessable treated or no assessable control drops out whole
    ok_sets = A.groupby("match_id").role.agg(lambda r: {"treated", "control"} <= set(r))
    A = A[A.match_id.isin(ok_sets[ok_sets].index)]
    B, seed = int(cp["bootstrap_B"]), int(cp["seed"])
    pt, lo, hi, n_cl = cluster_ci(A, "flagged", B, seed)
    mpt, mlo, mhi, _ = cluster_ci(A, "median_dz_m", B, seed + 1)
    n_t = int((A.role == "treated").sum())
    n_min = int(cfg["eligibility"]["min_eligible_pads"])
    T_ = A[A.role == "treated"].copy()
    dose = {"note": "needs dates"}
    if "first_eligible_plug" in T_ and T_.first_eligible_plug.notna().sum() >= 3:
        yrs = pd.Timestamp(f"{cfg['projects']['late']['year_lo']}-01-01") - pd.to_datetime(T_.first_eligible_plug)
        rho, p = spearmanr(yrs.dt.days / 365.25, T_.median_dz_m.abs())
        dose = {"spearman_rho": float(rho), "p": float(p), "n": int(len(T_)), "exploratory": True}
    plc = {"reps": 0, "note": "no pool given"}
    if pool_pads is not None:
        Pm = measure(pool_pads.assign(match_id=-1, role="pool", complex_id=-1), field, T, slope, excl, params,
                     int(cfg["flag_rule"]["seed"]) + 7, seam_d)
        plc = placebo(Pm, n_t, int(cfg["controls"]["max_controls"]), int(cp["n_placebo"]), seed + 2)
    out = {"primary": {"statistic": "flag rate treated minus matched controls", "estimate": pt, "lo": lo, "hi": hi,
                       "n_treated": n_t, "n_controls": int((A.role == "control").sum()), "n_clusters": n_cl,
                       "delta_rate": float(cp["delta_rate"]), "min_n": n_min,
                       "verdict": gate(lo, hi, float(cp["delta_rate"]), n_t, n_min),
                       "bootstrap_unreliable": n_cl < 15},
           "secondary_mean_change_m": {"estimate": mpt, "lo": mlo, "hi": mhi},
           "dose_response": dose, "placebo": plc,
           "seam_dist_median_m": {r: float(g.seam_dist_m.median()) for r, g in A.groupby("role")},
           "not_assessable": int((~D.assessable).sum()),
           "reading": "Evidence level (a), terrain change. No detectable change is not no restoration or no plugging. "
                      "Recovery from S3 bounds what the chain can see."}
    js = run_dir / "plug_change_compare_9t.json"
    js.write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    ek.write_provenance(run_dir, inputs=inputs, outputs=[csv, js], params={"compare": cp, "flag": params},
                        seeds={"bootstrap": seed, "flag": cfg["flag_rule"]["seed"]})
    return {"run_dir": run_dir, "csv": csv, "result": out}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--ctrl-dir", type=Path, default=None, help="S2 run folder (default newest)")
    ap.add_argument("--placebo", action="store_true", help="also measure the whole S2 control pool for the placebo")
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    cfg = io.load_config(a.config)
    pool = None
    if a.placebo:
        import pandas as pd_
        el = io.need(io.latest_run("dod_elig", a.out_root), "S1 run folder")
        P = pd_.read_csv(el / "plug_eligible_pads_9t.csv")
        W = pd_.read_csv(el / "plug_eligible_wells_9t.csv")
        from _dod_controls_matched_9t import control_pool
        ok = control_pool(P, W, bool(cfg["controls"]["require_spud_before_early"]), cfg["eligibility"]["spud_field"])
        pads = io.read_layer(io.resolve(cfg["annotations_gpkg"]), cfg["pad_layer"], cfg["crs"])
        pool = pads[pads.pad_id.isin(P.pad_id[ok.to_numpy()])]
    r = run(cfg, a.out_root, a.ctrl_dir, pool_pads=pool)
    print(json.dumps(r["result"], indent=2, default=float))


if __name__ == "__main__":
    main()
