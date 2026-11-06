"""6.6 S5. GNSS walk test of the travel-time model (Q3). Not a well result.

Purpose
    Model each walked route's time along the walked track (Tobler speed from DEM slope per segment, times the
    land-cover multiplier) and compare it with the measured time. Split routes in half (seeded, by route). On the
    calibration half, fit one non-negative time multiplier per land-cover group by non-negative least squares
    (measured time = sum over groups of multiplier times the Tobler time spent in that group). Score the holdout
    with the fitted multipliers. Relative error per route is |model - measured| / measured. Primary is the median
    over holdout routes with a route bootstrap interval (B = 2000). Track points with an error larger than the
    segment length are dropped, so GNSS noise does not inflate distance. The route is the unit of independence.
    Gate. Success when the upper bound is under the time tolerance. Failure when the lower bound is above it.
Inputs
    data/9t/source/sar_field/walk_tracks_9t.csv (assumed: route_id, t_s, x, y, err_m), DEM (held), landcover (held)
Outputs
    data/9t/results/sar/<run_id>/sar_walk_routes_9t.csv, sar_walk_validation_9t.json
Run
    python expansions/6_adjacent/6_6_sar_viewshed/src/_sar_walk_time_validate.py [--tracks FILE] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _sar_viewshed_tool as V
from _sar_viewshed_tool import ek


def route_segments(g, tr: pd.DataFrame, lc: np.ndarray | None, cp: dict) -> dict:
    """Tobler time per land-cover group along one track."""
    tr = tr.sort_values("t_s")
    x, y = tr.x.to_numpy(), tr.y.to_numpy()
    v, u = g.to_vu(x, y)
    z = V.bilinear(g.dem, v, u)
    dxy = np.hypot(np.diff(x), np.diff(y))
    err = tr.err_m.to_numpy()[1:] if "err_m" in tr else np.zeros(len(dxy))
    keep = (dxy > err) & np.isfinite(np.diff(z))
    S = np.diff(z)[keep] / dxy[keep]
    t_seg = dxy[keep] / V.tobler_speed_ms(S, cp)
    if lc is not None:
        code, _ = V.nearest(lc, v[1:][keep], u[1:][keep])
        grp = np.array([str(int(c)) for c in code])
    else:
        grp = np.array(["all"] * len(t_seg))
    by = pd.Series(t_seg).groupby(grp).sum().to_dict()
    return {"measured_s": float(tr.t_s.iloc[-1] - tr.t_s.iloc[0]), "tobler_by_group": by,
            "length_m": float(dxy[keep].sum()), "n_dropped_points": int((~keep).sum())}


def fit_multipliers(routes: list[dict]) -> dict:
    from scipy.optimize import nnls
    groups = sorted({k for r in routes for k in r["tobler_by_group"]})
    A = np.array([[r["tobler_by_group"].get(gk, 0.0) for gk in groups] for r in routes])
    b = np.array([r["measured_s"] for r in routes])
    m, _ = nnls(A, b)
    return dict(zip(groups, m.tolist()))


def model_time(r: dict, mult: dict, default: float) -> float:
    return float(sum(t * mult.get(k, default) for k, t in r["tobler_by_group"].items()))


def run(cfg: dict, tracks: pd.DataFrame, g, lc=None, B: int | None = None) -> tuple[pd.DataFrame, dict]:
    vc, cp = cfg["validation"], cfg["cost"]
    for c in ("route_id", "t_s", "x", "y"):
        if c not in tracks:
            raise ValueError(f"walk tracks lack column {c}")
    ids = sorted(tracks.route_id.unique())
    rng = np.random.default_rng(ek.child_seed(vc["master_seed"], 2, 0))
    perm = list(rng.permutation(ids))
    cal, hold = sorted(perm[: len(perm) // 2]), sorted(perm[len(perm) // 2:])
    ek.assert_disjoint(cal, hold, "calibration vs holdout routes")
    segs = {rid: route_segments(g, tracks[tracks.route_id == rid], lc, cp) for rid in ids}
    mult = fit_multipliers([segs[r] for r in cal])
    default = float(np.median(list(mult.values()))) if mult else 1.0
    rows = []
    for rid in ids:
        s = segs[rid]
        mt = model_time(s, mult, default)
        rows.append({"route_id": rid, "half": "calibration" if rid in cal else "holdout", "measured_s": s["measured_s"],
                     "model_s": mt, "rel_err": abs(mt - s["measured_s"]) / s["measured_s"] if s["measured_s"] else np.nan,
                     "length_m": s["length_m"], "n_dropped_points": s["n_dropped_points"]})
    df = pd.DataFrame(rows)
    ho = df[df.half == "holdout"].set_index("route_id")
    res = {"multipliers_fit_on_calibration": mult, "n_routes": len(ids), "holdout_routes": hold,
           "time_tolerance_rel": vc["time_tolerance_rel"]}
    if len(ho):
        pt, lo, hi, _ = ek.block_bootstrap(lambda L: float(np.median(ho.loc[L, "rel_err"])), list(ho.index),
                                           B=B or vc["B"], seed=ek.child_seed(vc["master_seed"], 2, 1))
        res["median_rel_err"] = {"point": pt, "lo95": lo, "hi95": hi}
        tol = vc["time_tolerance_rel"]
        if tol is None:
            res["gate"] = "not scored. Set validation.time_tolerance_rel first (user decision)"
        elif len(ids) < vc["min_routes"]:
            res["gate"] = f"inconclusive (fewer than {vc['min_routes']} routes)"
        else:
            res["gate"] = "success" if hi < tol else "failure" if lo > tol else "inconclusive"
    return df, res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__ + "\n" + V.NOT_WELL, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--tracks", default=None)
    ap.add_argument("--dem", default=None)
    ap.add_argument("--landcover", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--B", type=int, default=None)
    a = ap.parse_args()
    cfg = V.load_config(a.config)
    tp = V.input_path(cfg, "walk_tracks", a.tracks)
    tr = pd.read_csv(tp)
    pad = 50.0
    g = V.load_grid(V.input_path(cfg, "dem", a.dem),
                    bbox=(tr.x.min() - pad, tr.y.min() - pad, tr.x.max() + pad, tr.y.max() + pad))
    lc = None
    lcp = V.input_path(cfg, "landcover", a.landcover, required=False)
    if lcp is not None:
        import rasterio
        from rasterio.warp import Resampling, reproject
        lc = np.zeros(g.dem.shape, np.int32)
        with rasterio.open(lcp) as src:
            reproject(rasterio.band(src, 1), lc, dst_transform=g.transform, dst_crs=g.crs, resampling=Resampling.nearest)
    df, res = run(cfg, tr, g, lc, a.B)
    out = Path(a.out) if a.out else ek.new_run("6.6", "sarwalk", cfg["validation"],
                                               base=V.resolve(cfg["outputs"]["results"]), why=V.NOT_WELL)
    out.mkdir(parents=True, exist_ok=True)
    p1, p2 = out / "sar_walk_routes_9t.csv", out / "sar_walk_validation_9t.json"
    df.to_csv(p1, index=False)
    p2.write_text(json.dumps(res | {"not_a_well_result": V.NOT_WELL}, indent=2, default=str), encoding="utf-8")
    ek.write_provenance(out, inputs=[tp], outputs=[p1, p2], params=cfg["validation"])
    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
