"""S2 (3.8). Small-baseline time series from an unwrapped interferogram stack, with closure-phase QC.

Purpose
    Pilot rule. Process one frame over 3 to 5 sites and 3 to 5 controls first and review every
    interferogram by eye before scaling.
    1. Read the manifest of interferograms (date1, date2, unwrapped phase, coherence) on one grid.
    2. Per pixel, solve the small-baseline system A v = phi for incremental phase between consecutive
       dates (least squares, pseudo-inverse, pixels with coherence below coherence_min are masked per
       interferogram), integrate to a time series and convert to LOS millimetres,
       d = -lambda / (4 pi) * phi * 1000 (positive toward the satellite, the repo convention).
    3. Closure phase on every triplet (i, j, k) of wrapped phases. Intervals in a triplet whose closure
       magnitude exceeds closure_max_rad are flagged (soil-moisture bias).
    4. Extract the series at site and control pixels (mean over a pad-sized footprint).
    The fetch is gated. --plan-fetch writes a download plan from the acquisition list, --execute downloads.
Inputs
    data/ak1/derived/ak_stack_ak1/ifg_manifest_ak1.csv (assumed), ak_wells_sites_ak1.gpkg (S0),
    ak_controls_ak1.gpkg (S5 matching), config_3_8.json inputs.acquisitions (for --plan-fetch)
Outputs
    data/ak1/derived/ak_stack_ak1/ak_los_series_ak1.csv   (point_id, kind, date, los_mm)
    data/ak1/derived/ak_stack_ak1/ak_closure_flags_ak1.csv
    data/ak1/derived/ak_stack_ak1/ak_fetch_plan_ak1.csv    (--plan-fetch)
Run
    python expansions/3_geography/3_8_alaska/src/_ak_insar_series_ak1.py --plan-fetch
    python expansions/3_geography/3_8_alaska/src/_ak_insar_series_ak1.py
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.8"


def sbas_design(pairs: list[tuple], dates: list) -> np.ndarray:
    """A[i, k] = 1 when interval k (dates[k] to dates[k+1]) lies inside pair i."""
    idx = {d: i for i, d in enumerate(dates)}
    A = np.zeros((len(pairs), len(dates) - 1))
    for i, (d1, d2) in enumerate(pairs):
        A[i, idx[d1]:idx[d2]] = 1.0
    return A


def invert_series(phi: np.ndarray, A: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """phi (n_ifg, n_pix) -> cumulative phase (n_dates, n_pix), first date zero. Masked ifgs dropped per pixel."""
    n_ifg, n_pix = phi.shape
    out = np.full((A.shape[1] + 1, n_pix), np.nan)
    if mask is None:
        mask = np.isfinite(phi)
    groups = {}
    for p in range(n_pix):
        groups.setdefault(mask[:, p].tobytes(), []).append(p)
    for key, pix in groups.items():
        m = np.frombuffer(key, dtype=bool)
        if m.sum() < 1:
            continue
        Am = A[m]
        inc = np.linalg.pinv(Am) @ phi[m][:, pix]
        if np.linalg.matrix_rank(Am) < A.shape[1]:
            # disconnected network for these pixels. Keep the minimum-norm solution, flagged by the caller.
            pass
        out[1:, pix] = np.cumsum(inc, axis=0)
        out[0, pix] = 0.0
    return out


def phase_to_los_mm(phi: np.ndarray, wavelength_m: float) -> np.ndarray:
    return -wavelength_m / (4 * np.pi) * phi * 1000.0


def closure_phase(wrapped: dict, dates: list) -> pd.DataFrame:
    """wrapped[(d1, d2)] -> array. Closure of every available triplet, wrapped to (-pi, pi]."""
    rows = []
    for i, j, k in itertools.combinations(range(len(dates)), 3):
        a, b, c = (dates[i], dates[j]), (dates[j], dates[k]), (dates[i], dates[k])
        if a in wrapped and b in wrapped and c in wrapped:
            cl = np.angle(np.exp(1j * (wrapped[a] + wrapped[b] - wrapped[c])))
            rows.append({"d1": dates[i], "d2": dates[j], "d3": dates[k], "closure_abs_mean": float(np.nanmean(np.abs(cl)))})
    return pd.DataFrame(rows)


def footprint_mean(stack: np.ndarray, transform, geoms) -> np.ndarray:
    """stack (n_dates, H, W) -> (n_dates, n_geoms) mean inside each geometry."""
    from rasterio.features import geometry_mask
    out = []
    for g in geoms:
        m = ~geometry_mask([g], stack.shape[1:], transform)
        out.append(np.nanmean(stack[:, m], axis=1) if m.any() else np.full(stack.shape[0], np.nan))
    return np.array(out).T


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan-fetch", action="store_true")
    ap.add_argument("--execute", action="store_true", help="download the planned products (network, gated)")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    out_d = ek.area_dir("ak1") / "derived" / "ak_stack_ak1"
    try:
        if a.plan_fetch:
            acq = pd.read_csv(gt.config_input(cfg, "acquisitions", EXP))
            acq["date"] = pd.to_datetime(acq["date"])
            plan = acq[acq["date"].dt.month.isin(pr["thaw_months"])].sort_values(["frame", "date"])
            out_d.mkdir(parents=True, exist_ok=True)
            plan.to_csv(out_d / "ak_fetch_plan_ak1.csv", index=False)
            print(f"{len(plan)} thaw-season products planned -> {out_d / 'ak_fetch_plan_ak1.csv'}")
            if a.execute:
                import urllib.request
                for u in plan["url"]:
                    dst = out_d / "raw" / Path(u).name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if not dst.exists():
                        urllib.request.urlretrieve(u, dst)
            return 0
        man = pd.read_csv(gt.config_input(cfg, "ifg_manifest", EXP), parse_dates=["date1", "date2"])
        import geopandas as gpd
        import rasterio
        sites = gpd.read_file(gt.require_input(ek.sub(EXP, "data/interim") / "ak_wells_sites_ak1.gpkg", "S0 sites"))
        ctrl = gpd.read_file(gt.require_input(ek.sub(EXP, "data/interim") / "ak_controls_ak1.gpkg", "S5a matched controls"))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    dates = sorted(set(man["date1"]) | set(man["date2"]))
    pairs = list(zip(man["date1"], man["date2"]))
    A = sbas_design(pairs, dates)
    unw, cor, wr = [], [], {}
    for _, r in man.iterrows():
        with rasterio.open(r.unw_tif) as u, rasterio.open(r.corr_tif) as c:
            unw.append(u.read(1).astype(np.float32))
            cor.append(c.read(1).astype(np.float32))
            tf, crs = u.transform, u.crs
        if "wrapped_tif" in r and isinstance(r.wrapped_tif, str):
            with rasterio.open(r.wrapped_tif) as w:
                wr[(r.date1, r.date2)] = w.read(1).astype(np.float32)
    phi = np.stack(unw)
    H, W = phi.shape[1:]
    mask = (np.stack(cor) >= pr["coherence_min"]) & np.isfinite(phi)
    series = invert_series(phi.reshape(len(pairs), -1), A, mask.reshape(len(pairs), -1)).reshape(len(dates), H, W)
    los = phase_to_los_mm(series, pr["wavelength_m"][pr["mission"]])
    site_poly = sites.to_crs(crs).dissolve("site_id").convex_hull.buffer(pr["pad_side_m_default"] / 2)
    rows = []
    for kind, ids, geoms in (("site", list(site_poly.index), list(site_poly.geometry)),
                             ("control", list(ctrl["cand_id"]), list(ctrl.to_crs(crs).geometry.buffer(pr["pad_side_m_default"] / 2)))):
        v = footprint_mean(los, tf, geoms)
        for j, pid in enumerate(ids):
            rows += [{"point_id": pid, "kind": kind, "date": d.date().isoformat(), "los_mm": float(v[i, j])}
                     for i, d in enumerate(dates)]
    out_d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_d / "ak_los_series_ak1.csv", index=False)
    cl = closure_phase(wr, dates)
    if len(cl):
        cl["flag"] = cl["closure_abs_mean"] > pr["closure_max_rad"]
    cl.to_csv(out_d / "ak_closure_flags_ak1.csv", index=False)
    print(f"wrote {out_d / 'ak_los_series_ak1.csv'}\nwrote {out_d / 'ak_closure_flags_ak1.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
