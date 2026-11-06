"""6.6 S4. Field validation of visibility calls (Q1 and Q2). Not a well result.

Purpose
    Read paired sight checks (observer, target, seen yes or no, canopy state, GNSS error). Split by station, never
    by pair (half calibration, half holdout, seeded). Predict every check with the brute-force profile under O0,
    O1 and O2. Fit the O2 extinction k per canopy state on calibration stations only (grid search on agreement).
    Score the holdout. Agreement, sensitivity (visible truth called visible) and specificity (hidden truth called
    hidden) are reported separately, because a falsely visible call leaves a coverage gap. GNSS error is a
    tolerance band, applied both ways (review 6.6 minor). The call is made at the stated points and at the band
    offsets of either end. If every call agrees, the pair is scored as a hit or a miss. If calls inside the band
    differ, the pair is "ambiguous within GNSS error" and leaves the agreement denominator, whichever way truth
    went. The old rule rescued misses only, which inflated agreement. A call of unknown (unobserved terrain on the
    sightline) is not scored either and is counted.
    The station is the unit of independence (station bootstrap, B = 2000). Under 15 stations the bootstrap is
    marked unreliable and a pair-level Clopper-Pearson interval, which ignores clustering, is shown beside it.
    Gate per opacity model and canopy state against the acceptance level A (a user decision, required).
Inputs
    data/9t/source/sar_field/sight_checks_9t.csv (assumed, schema in config_6_6.json), DEM, DSM, CHM (held)
Outputs
    data/9t/results/sar/<run_id>/sar_sight_predictions_9t.csv, sar_sight_validation_9t.json, _PROVENANCE.json
Run
    python expansions/6_adjacent/6_6_sar_viewshed/src/_sar_viewshed_validate.py [--checks FILE] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _sar_viewshed_tool as V
from _sar_viewshed_tool import ek

REQUIRED = ["check_id", "station_id", "obs_x", "obs_y", "tgt_x", "tgt_y", "visible", "canopy_state", "gnss_err_m"]


def split_stations(stations, seed: int) -> tuple[list, list]:
    s = sorted(set(stations))
    rng = np.random.default_rng(seed)
    perm = list(rng.permutation(s))
    h = len(perm) // 2
    cal, hold = sorted(perm[:h]), sorted(perm[h:])
    ek.assert_disjoint(cal, hold, "calibration vs holdout stations")
    return cal, hold


def predict(g, row, opacity: str, k: float, vp: dict) -> dict:
    """Calls at the stated points and over the GNSS band. Returns call, agree (None when not scored) and status.

    status 'scored' (every call in the band is the same and known), 'ambiguous' (calls in the band differ),
    'unknown' (the stated call is unknown or nodata)."""
    eye = getattr(row, "eye_h", vp["eye_height_m"])
    th = getattr(row, "tgt_h", vp["person_height_m"])
    eye = vp["eye_height_m"] if pd.isna(eye) else eye
    th = vp["person_height_m"] if pd.isna(th) else th

    def call(ox, oy, tx, ty):
        r = V.los_profile(g, (ox, oy), (tx, ty), opacity, eye, th, k, vp)
        if r["visible"] is None:
            return None
        return bool(r["p_visible"] >= vp["o2_visible_threshold"]) if opacity == "O2" else r["visible"]
    c = call(row.obs_x, row.obs_y, row.tgt_x, row.tgt_y)
    if c is None:
        return {"call": None, "agree": None, "status": "unknown"}
    e = float(row.gnss_err_m or 0)
    band = {c}
    if e > 0:
        for dx, dy in ((e, 0), (-e, 0), (0, e), (0, -e)):
            for ends in ("obs", "tgt"):
                ox, oy = (row.obs_x + dx, row.obs_y + dy) if ends == "obs" else (row.obs_x, row.obs_y)
                tx, ty = (row.tgt_x + dx, row.tgt_y + dy) if ends == "tgt" else (row.tgt_x, row.tgt_y)
                band.add(call(ox, oy, tx, ty))
    if len(band) > 1:
        return {"call": c, "agree": None, "status": "ambiguous"}
    return {"call": c, "agree": c == bool(row.visible), "status": "scored"}


def metrics(df: pd.DataFrame) -> dict:
    d = df[df.agree.notna()].copy()
    d["agree"] = d.agree.astype(bool)
    v = d.visible.astype(bool)
    st = df["status"] if "status" in df else pd.Series("scored", index=df.index)
    return {"n_pairs": int(len(d)), "n_ambiguous_gnss": int((st == "ambiguous").sum()),
            "n_unknown_call": int((st == "unknown").sum()),
            "agreement": float(d.agree.mean()) if len(d) else np.nan,
            "sensitivity": float(d.loc[v, "agree"].mean()) if v.any() else np.nan,
            "specificity": float(d.loc[~v, "agree"].mean()) if (~v).any() else np.nan}


def station_ci(df: pd.DataFrame, col: str, B: int, seed: int):
    by = {s: g for s, g in df[df.agree.notna()].groupby("station_id")}

    def stat(st):
        g = pd.concat([by[s] for s in st])
        return float(g[col].astype(float).mean()) if len(g) else np.nan
    return ek.block_bootstrap(stat, sorted(by), B=B, seed=seed)[:3]


def run(cfg: dict, checks: pd.DataFrame, g, B: int | None = None) -> tuple[pd.DataFrame, dict]:
    vp, vc = cfg["viewshed"], cfg["validation"]
    miss = [c for c in REQUIRED if c not in checks]
    if miss:
        raise ValueError(f"sight checks lack columns {miss}")
    ek.assert_unique(checks, "check_id")
    ek.assert_no_nan(checks.station_id, "station_id")
    B = B or vc["B"]
    cal, hold = split_stations(checks.station_id, ek.child_seed(vc["master_seed"], 0, 0))
    checks = checks.assign(half=np.where(checks.station_id.isin(cal), "calibration", "holdout"))
    k_fit = {}
    for st, sub in checks[checks.half == "calibration"].groupby("canopy_state"):
        best = None
        for k in vc["k_grid"]:
            ags = [predict(g, r, "O2", k, vp)["agree"] for r in sub.itertuples()]
            ags = [a_ for a_ in ags if a_ is not None]
            ag = float(np.mean(ags)) if ags else -1.0
            if best is None or ag > best[1] + 1e-12:
                best = (k, ag)
        k_fit[st] = {"k": best[0], "calibration_agreement": float(best[1])}
    rows = []
    for r in checks.itertuples():
        for op in ("O0", "O1", "O2"):
            k = k_fit.get(r.canopy_state, {"k": vp["k_extinction"].get(r.canopy_state, 0.0)})["k"] if op == "O2" else 0.0
            rows.append({"check_id": r.check_id, "station_id": r.station_id, "half": r.half, "canopy_state": r.canopy_state,
                         "visible": int(r.visible), "opacity": op, "k": k,
                         "distance_m": float(np.hypot(r.tgt_x - r.obs_x, r.tgt_y - r.obs_y)), **predict(g, r, op, k, vp)})
    pr = pd.DataFrame(rows)
    A = vc["acceptance_A"]
    res = {"stations": {"calibration": cal, "holdout": hold}, "k_fit": k_fit, "acceptance_A": A, "results": {}}
    n_hold = len(hold)
    if n_hold < 15:
        res["bootstrap_note"] = f"{n_hold} holdout stations. Fewer than 15, the station bootstrap is unreliable."
    if len(set(checks.station_id)) < vc["min_stations"]:
        res["design_note"] = f"fewer than {vc['min_stations']} stations. Any gate result is inconclusive."
    ho = pr[pr.half == "holdout"]
    seed = ek.child_seed(vc["master_seed"], 1, 0)
    for (op, st), sub in ho.groupby(["opacity", "canopy_state"]):
        m = metrics(sub)
        if m["n_pairs"]:
            m["agreement_ci"] = station_ci(sub, "agree", B, seed)
            sc_ = sub[sub.agree.notna()]
            k_ok = int(sc_.agree.astype(bool).sum())
            m["pair_clopper_pearson_ignores_clustering"] = ek.clopper_pearson(k_ok, int(len(sc_)))
            if A is None:
                m["gate"] = "not scored. Set validation.acceptance_A in config_6_6.json first (user decision)"
            elif "design_note" in res:
                m["gate"] = "inconclusive (too few stations)"
            else:
                lo, hi = m["agreement_ci"][1], m["agreement_ci"][2]
                m["gate"] = "success" if lo > A else "failure" if hi < A else "inconclusive"
        bands = vc["distance_bands_m"]
        sub = sub.assign(band=pd.cut(sub.distance_m, bands))
        m["by_distance_exploratory"] = {str(b): metrics(x) for b, x in sub.groupby("band", observed=True)}
        res["results"][f"{op}:{st}"] = m
    return pr, res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__ + "\n" + V.NOT_WELL, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--checks", default=None)
    ap.add_argument("--dem", default=None)
    ap.add_argument("--dsm", default=None)
    ap.add_argument("--chm", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--B", type=int, default=None)
    a = ap.parse_args()
    cfg = V.load_config(a.config)
    cp = V.input_path(cfg, "sight_checks", a.checks)
    checks = pd.read_csv(cp)
    pad = 50.0
    xs = pd.concat([checks.obs_x, checks.tgt_x])
    ys = pd.concat([checks.obs_y, checks.tgt_y])
    g = V.load_grid(V.input_path(cfg, "dem", a.dem), V.input_path(cfg, "dsm", a.dsm), V.input_path(cfg, "chm", a.chm),
                    bbox=(xs.min() - pad, ys.min() - pad, xs.max() + pad, ys.max() + pad))
    pr, res = run(cfg, checks, g, a.B)
    out = Path(a.out) if a.out else ek.new_run("6.6", "sarvalidate", cfg["validation"],
                                               base=V.resolve(cfg["outputs"]["results"]), why=V.NOT_WELL)
    out.mkdir(parents=True, exist_ok=True)
    p1 = out / "sar_sight_predictions_9t.csv"
    pr.to_csv(p1, index=False)
    p2 = out / "sar_sight_validation_9t.json"
    p2.write_text(json.dumps(res | {"not_a_well_result": V.NOT_WELL}, indent=2, default=str), encoding="utf-8")
    ek.write_provenance(out, inputs=[cp], outputs=[p1, p2], params=cfg["validation"])
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "by_distance_exploratory"} for k, v in res["results"].items()},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
