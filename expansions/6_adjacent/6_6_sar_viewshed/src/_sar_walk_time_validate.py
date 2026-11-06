"""6.6 S5. GNSS walk test of the travel-time model (Q3). Not a well result.

Purpose
    Model each walked route's time along the walked track (Tobler speed from DEM slope per segment, times the
    land-cover multiplier) and compare it with the measured time. Split routes in half (seeded, by route). On the
    calibration half, fit one non-negative time multiplier per land-cover group by non-negative least squares
    (measured time = sum over groups of multiplier times the Tobler time spent in that group). Score the holdout
    with the fitted multipliers. Relative error per route is |model - measured| / measured. Primary is the median
    over holdout routes with a route bootstrap interval (B = 2000). The route is the unit of independence.
    GNSS noise (review 6.6-01). At 1 Hz a walker moves about 1.3 m per fix and the fix error is 2 to 3 m. The old
    rule dropped any segment shorter than the error, which dropped every segment, so modelled time was 0. Raw
    segments would instead inflate the length by noise. Now the track is smoothed with a centred moving average
    (walk_smooth_s, ends padded by point reflection so a straight walk keeps its ends), then thinned to points at
    least walk_min_disp_m apart (or 3 times the median fix error after smoothing, if larger). Segment length and
    slope come from the thinned track. Measured time still runs from the first to the last raw fix.
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


def smooth_track(t: np.ndarray, x: np.ndarray, y: np.ndarray, window_s: float) -> tuple[np.ndarray, np.ndarray, int]:
    """Centred moving average over about window_s seconds of fixes. Ends are padded by point reflection
    (2 * x0 - x_k), so a constant-velocity walk keeps its true end points. Returns x, y and the window in points."""
    n = len(x)
    dt = float(np.median(np.diff(t))) if n > 1 else 1.0
    w = int(max(1, round(window_s / dt if dt > 0 else 1)))
    w = w + 1 if w % 2 == 0 else w
    h = min(w // 2, n - 1)
    if h < 1:
        return x.astype(float), y.astype(float), 1
    w = 2 * h + 1
    out = []
    for a in (x.astype(float), y.astype(float)):
        pad = np.r_[2 * a[0] - a[1:h + 1][::-1], a, 2 * a[-1] - a[-h - 1:-1][::-1]]
        out.append(np.convolve(pad, np.ones(w) / w, mode="valid"))
    return out[0], out[1], w


def thin_by_displacement(x: np.ndarray, y: np.ndarray, min_disp: float) -> np.ndarray:
    """Indices of points at least min_disp from the previous kept point. The first and last points are kept."""
    keep = [0]
    for i in range(1, len(x)):
        if np.hypot(x[i] - x[keep[-1]], y[i] - y[keep[-1]]) >= min_disp:
            keep.append(i)
    if keep[-1] != len(x) - 1:
        keep.append(len(x) - 1)
    return np.array(keep, int)


def route_segments(g, tr: pd.DataFrame, lc: np.ndarray | None, cp: dict, wp: dict | None = None) -> dict:
    """Tobler time per land-cover group along one track, after noise-aware smoothing and thinning."""
    wp = wp or {}
    tr = tr.sort_values("t_s")
    t = tr.t_s.to_numpy(float)
    xr, yr = tr.x.to_numpy(float), tr.y.to_numpy(float)
    xs, ys, w = smooth_track(t, xr, yr, float(wp.get("walk_smooth_s", 15.0)))
    err = float(np.nanmedian(tr.err_m)) if "err_m" in tr and tr.err_m.notna().any() else 0.0
    min_disp = max(float(wp.get("walk_min_disp_m", 10.0)), 3.0 * err / np.sqrt(w))
    k = thin_by_displacement(xs, ys, min_disp)
    x, y = xs[k], ys[k]
    v, u = g.to_vu(x, y)
    z = V.bilinear(g.dem, v, u)
    dxy = np.hypot(np.diff(x), np.diff(y))
    keep = (dxy > 0) & np.isfinite(np.diff(z))
    S = np.diff(z)[keep] / dxy[keep]
    t_seg = dxy[keep] / V.tobler_speed_ms(S, cp)
    if lc is not None:
        code, _ = V.nearest(lc, v[1:][keep], u[1:][keep])
        grp = np.array([str(int(c)) for c in code])
    else:
        grp = np.array(["all"] * len(t_seg))
    by = pd.Series(t_seg, dtype=float).groupby(grp).sum().to_dict()
    return {"measured_s": float(t[-1] - t[0]), "tobler_by_group": by,
            "length_m": float(dxy[keep].sum()), "n_points_raw": int(len(t)), "n_points_used": int(len(k)),
            "n_segments_no_dem": int((~np.isfinite(np.diff(z))).sum()), "smooth_window_pts": int(w),
            "min_disp_m": float(min_disp)}


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
    segs = {rid: route_segments(g, tracks[tracks.route_id == rid], lc, cp, vc) for rid in ids}
    zero = [rid for rid in ids if segs[rid]["length_m"] <= 0]
    if zero:
        raise ValueError(f"routes with zero modelled length {zero}. Check the track and the DEM extent.")
    mult = fit_multipliers([segs[r] for r in cal])
    default = float(np.median(list(mult.values()))) if mult else 1.0
    rows = []
    for rid in ids:
        s = segs[rid]
        mt = model_time(s, mult, default)
        rows.append({"route_id": rid, "half": "calibration" if rid in cal else "holdout", "measured_s": s["measured_s"],
                     "model_s": mt, "rel_err": abs(mt - s["measured_s"]) / s["measured_s"] if s["measured_s"] else np.nan,
                     "length_m": s["length_m"], "n_points_raw": s["n_points_raw"], "n_points_used": s["n_points_used"],
                     "min_disp_m": s["min_disp_m"]})
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
