"""Registration check between the early and late DEMs on stable ground (QC for S3 and S4).

Purpose
    A residual planimetric shift (dx, dy) between two DEMs makes a false change dz = -(gx dx + gy dy) on slopes.
    On stable ground (outside every mapped pad, pit and road plus a buffer, slope under max_slope_deg) fit
        dz = dz0 - gx * dx - gy * dy
    by least squares, where gx, gy are the late-DEM gradients. Report the shift, the vertical bias, the spread by
    slope bin, and the planimetric error implied by spread against tan(slope) (the same test as _icp_change_9t.py).
    Pass when |shift| <= shift_tol_m and |dz0| <= bias_tol_m. apply_shift() corrects an early DEM by the fitted shift
    and is the registration step of the S3 recovery chain.

Inputs
    data/9t/derived/lidar_2006_2008/dem_2006_v2_9t_2m.tif and dem_2019_v2_9t_2m.tif (held, git-ignored)
    qgis/annotations/annotations_proj_v2.gpkg layers pad, pit_full, roads (held)

Outputs (run folder expansions/4_modalities/4_5_multitemporal_lidar/results/<YYYYMMDD>_dod_reg_<hash7>/)
    dod_registration_9t.json   shift, bias, slope-binned sigma, implied planimetric error, pass or fail
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_5_multitemporal_lidar/src/_dod_registration_check_9t.py [--out-root DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _dod_shared_io as io  # noqa: E402
from _dod_shared_io import ek  # noqa: E402


def robust_sigma(v: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(v - np.median(v)))) if len(v) else float("nan")


def fit_shift(early: np.ndarray, late: np.ndarray, res: float, stable: np.ndarray, n_max: int, seed: int,
              max_slope: float = 30.0) -> dict:
    """Least-squares (dz0, dx, dy) on stable cells, with one robust reweighting pass."""
    z = np.where(np.isfinite(late), late, np.nanmean(late))
    gy, gx = np.gradient(z, res)
    gy = -gy                                   # rows run south, so flip to a north-positive gradient
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    dz = late - early
    ok = stable & np.isfinite(dz) & (slope < max_slope)
    idx = np.flatnonzero(ok.ravel())
    if len(idx) < 100:
        return {"error": f"only {len(idx)} stable cells"}
    rng = np.random.default_rng(seed)
    if len(idx) > n_max:
        idx = rng.choice(idx, n_max, replace=False)
    A = np.c_[np.ones(len(idx)), -gx.ravel()[idx], -gy.ravel()[idx]]
    b = dz.ravel()[idx]
    w = np.ones(len(b))
    for _ in range(2):
        sol, *_ = np.linalg.lstsq(A * w[:, None], b * w, rcond=None)
        r = b - A @ sol
        s = robust_sigma(r)
        w = (np.abs(r) < 3 * s).astype(float) if s > 0 else w
    out = {"dz0_m": float(sol[0]), "dx_m": float(sol[1]), "dy_m": float(sol[2]),
           "shift_m": float(np.hypot(sol[1], sol[2])), "n_cells": int(len(idx)),
           "sigma_before_m": robust_sigma(b - np.median(b)), "sigma_after_m": robust_sigma(b - A @ sol)}
    return out, slope, dz, ok


def slope_binned(dz, slope, ok, bins) -> tuple[list, dict]:
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = ok & (slope >= lo) & (slope < hi)
        if m.sum() >= 200:
            v = dz[m]
            rows.append({"slope_lo": lo, "slope_hi": hi, "n": int(m.sum()), "median_m": float(np.median(v)),
                         "sigma_m": robust_sigma(v), "tan_mid": float(np.tan(np.radians((lo + hi) / 2)))})
    implied = {}
    if len(rows) >= 3:
        t = np.array([r["tan_mid"] for r in rows])
        g = np.array([r["sigma_m"] for r in rows])
        k, s0 = np.linalg.lstsq(np.c_[t, np.ones_like(t)], g, rcond=None)[0]
        implied = {"implied_planimetric_error_m": float(k), "flat_ground_sigma_m": float(s0)}
    return rows, implied


def apply_shift(early: np.ndarray, res: float, dx: float, dy: float) -> np.ndarray:
    """Move the early surface by (+dx east, +dy north) with bilinear resampling. Edges become NaN."""
    from scipy import ndimage as ndi
    m = np.isfinite(early)
    z = np.where(m, early, np.nanmean(early))
    shifted = ndi.shift(z, (-dy / res, dx / res), order=1, mode="constant", cval=np.nan)
    mm = ndi.shift(m.astype(float), (-dy / res, dx / res), order=1, mode="constant", cval=0) > 0.99
    return np.where(mm, shifted, np.nan)


def check(early, late, transform, layers, rc: dict, seed: int = 0) -> dict:
    res = float(transform.a)
    excl = io.feature_mask(layers, early.shape, transform, int(round(rc["stable_buffer_m"] / res)))
    r = fit_shift(early, late, res, ~excl, int(rc["sample_cells"]), seed, float(rc["max_slope_deg"]))
    if isinstance(r, dict):
        return {**r, "verdict": "fail"}
    fit, slope, dz, ok = r
    bins, implied = slope_binned(dz - fit["dz0_m"], slope, ok, rc["slope_bins"])
    passed = fit["shift_m"] <= rc["shift_tol_m"] and abs(fit["dz0_m"]) <= rc["bias_tol_m"]
    return {**fit, "slope_bins": bins, **implied, "stable_share": float(ok.mean()),
            "tolerances": {"shift_tol_m": rc["shift_tol_m"], "bias_tol_m": rc["bias_tol_m"]},
            "verdict": "pass" if passed else "fail"}


def run(cfg: dict, out_root: Path | None = None) -> dict:
    crs = cfg["crs"]
    pe, pl = io.resolve(cfg["dems"]["early"]), io.resolve(cfg["dems"]["late"])
    early, T, _ = io.read_raster(io.need(pe, "early DEM", "regenerate with _change_rebuild_v2_9t.py"), crs)
    late, T2, _ = io.read_raster(io.need(pl, "late DEM", "regenerate with _change_rebuild_v2_9t.py"), crs)
    if early.shape != late.shape or T != T2:
        raise AssertionError("early and late DEM grids differ")
    ga = io.resolve(cfg["annotations_gpkg"])
    layers = [io.read_layer(ga, cfg[k], crs) for k in ("pad_layer", "pit_layer", "road_layer")]
    run_dir = ek.new_run(io.EXP, "dod_reg", cfg["registration"], base=out_root,
                         why="Registration check of the early and late DEMs on stable ground.")
    res = check(early, late, T, layers, cfg["registration"])
    js = run_dir / "dod_registration_9t.json"
    js.write_text(json.dumps(res, indent=2), encoding="utf-8")
    ek.write_provenance(run_dir, inputs=[pe, pl, ga], outputs=[js], params=cfg["registration"])
    return {"run_dir": run_dir, "json": js, "result": res}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    r = run(io.load_config(a.config), a.out_root)
    print(json.dumps({k: v for k, v in r["result"].items() if k != "slope_bins"}, indent=2))


if __name__ == "__main__":
    main()
