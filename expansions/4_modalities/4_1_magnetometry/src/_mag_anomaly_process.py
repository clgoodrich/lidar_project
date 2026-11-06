"""S3. Process ground magnetometer data into a residual grid, an analytic-signal grid and an anomaly pick table.

Purpose
    Steps, per site.
    1. Despike each line. A sample further than k x MAD from its running median is replaced by that median.
    2. Diurnal correction. The base-station field is interpolated to each rover time and its departure from the
       base median is subtracted.
    3. Regional removal. A low-order polynomial in easting and northing is fitted by least squares, with two
       trimming passes that drop the largest residuals so anomalies do not bend the fit.
    4. Noise. White-noise sigma from the along-line second difference of the residual (robust). A grid input
       uses the robust sigma of its residual, which the anomaly inflates, so grid picks are conservative.
    5. Grid at 0.25 m by linear interpolation. Cells further than 1.5 x line spacing from any sample are masked.
    6. FFT derivatives. Vertical derivative |k| F, horizontal derivatives i k F, analytic signal amplitude
       sqrt(dx^2 + dy^2 + dz^2). Optional reduction to pole with the main-field inclination and declination.
    7. Picks. Analytic-signal local maxima above median + k x robust sigma of the analytic signal, kept only
       where the residual peak in the window is at least k x line noise and the exceedance is seen on two
       or more lines (or the peak is at least strong_k_sigma). Each pick has amplitude, position,
       signal to noise and width (equivalent diameter of the half-maximum patch).
    8. QC. Repeat-line RMS (is_repeat rows against the nearest main-line sample). Test-object check (distance
       from the nearest pick to the placed object).
    An already gridded GeoTIFF can replace steps 1 to 5. Its noise comes from the grid residual.
    Anomaly means steel of any kind (evidence level c). It is not a well.

Inputs (assumed, schemas in config_4_1.json)
    expansions/4_modalities/4_1_magnetometry/data/raw/<site>/mag_lines.csv
    expansions/4_modalities/4_1_magnetometry/data/raw/<site>/mag_base.csv
    or expansions/4_modalities/4_1_magnetometry/data/raw/<site>/mag_grid.tif

Outputs
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_residual_<site>.tif
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_asig_<site>.tif
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_anomalies_<site>.csv
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_qc_<site>.json

Run
    python expansions/4_modalities/4_1_magnetometry/src/_mag_anomaly_process.py --site SITE_A [--site SITE_B ...]
        [--test-object E N] [--from-grid]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage as ndi
from scipy.interpolate import griddata
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mag_shared_io as io  # noqa: E402
from _mag_shared_io import ek  # noqa: E402


def robust_sigma(v) -> float:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    return float(1.4826 * np.median(np.abs(v - np.median(v)))) if len(v) else float("nan")


def despike(lines: pd.DataFrame, win: int, k: float) -> tuple[pd.DataFrame, int]:
    out = lines.copy()
    n = 0
    for _, idx in out.groupby("line_id").groups.items():
        v = out.loc[idx, "tf_nT"]
        med = v.rolling(win, center=True, min_periods=1).median()
        dev = (v - med).abs()
        mad = 1.4826 * dev.rolling(win, center=True, min_periods=1).median()
        floor = max(float(np.nanmedian(mad)), 1e-6)
        bad = dev > k * np.maximum(mad, floor)
        n += int(bad.sum())
        out.loc[idx[bad.values], "tf_nT"] = med[bad]
    return out, n


def diurnal_correct(lines: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    t = pd.to_datetime(lines["time_utc"], utc=True, format="ISO8601").astype("int64") / 1e9
    tb = pd.to_datetime(base["time_utc"], utc=True, format="ISO8601").astype("int64") / 1e9
    if t.min() < tb.min() - 1 or t.max() > tb.max() + 1:
        raise ValueError("base station does not cover the survey time span. QC fail (framework section 8)")
    b = np.interp(t, tb.values, base["tf_nT"].values)
    out = lines.copy()
    out["tf_corr_nT"] = out["tf_nT"].values - (b - np.median(base["tf_nT"].values))
    return out


def _design(x, y, order):
    cols = [np.ones_like(x)]
    for o in range(1, order + 1):
        for i in range(o + 1):
            cols.append(x ** (o - i) * y ** i)
    return np.column_stack(cols)


def remove_regional(x, y, v, order: int = 1, trim: float = 0.8, passes: int = 2):
    x0, y0 = x - x.mean(), y - y.mean()
    A = _design(x0, y0, order)
    keep = np.isfinite(v)
    for _ in range(passes + 1):
        coef, *_ = np.linalg.lstsq(A[keep], v[keep], rcond=None)
        r = v - A @ coef
        cut = np.quantile(np.abs(r[np.isfinite(r)]), trim)
        keep = np.isfinite(v) & (np.abs(r) <= cut)
    return r, coef


def to_grid(x, y, v, cell: float, max_dist: float):
    xmin, xmax, ymin, ymax = x.min(), x.max(), y.min(), y.max()
    xs = np.arange(xmin, xmax + cell / 2, cell)
    ys = np.arange(ymax, ymin - cell / 2, -cell)          # north up
    X, Y = np.meshgrid(xs, ys)
    G = griddata((x, y), v, (X, Y), method="linear")
    d, _ = cKDTree(np.c_[x, y]).query(np.c_[X.ravel(), Y.ravel()])
    G[(d.reshape(X.shape) > max_dist)] = np.nan
    from rasterio.transform import from_origin
    T = from_origin(xmin - cell / 2, ymax + cell / 2, cell, cell)
    return G, X, Y, T


def fft_derivatives(G, cell: float, rtp: bool = False, inc: float = 67.0, dec: float = -9.0):
    """Returns (field, dx, dy, dz, asig). NaNs are filled with 0 for the transform and re-masked after.
    Rows run north to south, so the array is flipped to make ky point north."""
    mask = np.isfinite(G)
    A = np.flipud(np.where(mask, G - np.nanmean(G), 0.0))
    ny, nx = A.shape
    py, px = ny // 2, nx // 2
    A = np.pad(A, ((py, py), (px, px)), mode="reflect")
    F = np.fft.fft2(A)
    kx = 2 * np.pi * np.fft.fftfreq(A.shape[1], cell)
    ky = 2 * np.pi * np.fft.fftfreq(A.shape[0], cell)
    KX, KY = np.meshgrid(kx, ky)
    K = np.hypot(KX, KY)
    if rtp:
        I, D = np.radians(inc), np.radians(dec)
        L, M, N = np.cos(I) * np.sin(D), np.cos(I) * np.cos(D), np.sin(I)
        with np.errstate(divide="ignore", invalid="ignore"):
            th = N + 1j * (L * KX + M * KY) / np.where(K == 0, 1, K)
        F = F / th ** 2
        F[0, 0] = 0
    inv = lambda S: np.flipud(np.real(np.fft.ifft2(S))[py:py + ny, px:px + nx])
    f, dx, dy, dz = inv(F), inv(1j * KX * F), inv(1j * KY * F), inv(K * F)
    asig = np.sqrt(dx ** 2 + dy ** 2 + dz ** 2)
    for a in (f, dx, dy, dz, asig):
        a[~mask] = np.nan
    return f, dx, dy, dz, asig


def line_noise(lines: pd.DataFrame, col: str) -> float:
    """White-noise sigma from the along-line second difference (var of d2 = 6 sigma^2). Smooth anomalies
    contribute little to d2, so the estimate is not inflated by the anomaly the way a residual MAD is."""
    d2 = [np.diff(g[col].values, 2) for _, g in lines.groupby("line_id") if len(g) > 3]
    return robust_sigma(np.concatenate(d2)) / np.sqrt(6.0) if d2 else float("nan")


def pick_anomalies(asig, resid, X, Y, cell: float, k: float, line_sigma: float, window_m: float,
                   line_spacing: float = 1.0, strong_k: float = 6.0) -> pd.DataFrame:
    """Support rule. A pick needs its |residual| >= k sigma patch to span at least one line spacing in both
    axes (seen on two or more lines), or a peak at or above strong_k sigma (a shallow casing seen on one line).
    The rule controls false picks from single noisy samples, which a bare 3 sigma cut admits on large grids."""
    w = max(3, int(round(window_m / cell)) | 1)
    a = np.nan_to_num(asig, nan=0.0)
    med, sig = float(np.nanmedian(asig)), robust_sigma(asig)
    thr = med + k * max(sig, 1e-9)
    peaks = (a == ndi.maximum_filter(a, size=w)) & (a > thr)
    rabs = ndi.maximum_filter(np.nan_to_num(np.abs(resid), nan=0.0), size=w)
    exceed = np.nan_to_num(np.abs(resid), nan=0.0) >= k * line_sigma
    plab, _ = ndi.label(exceed)
    sls = ndi.find_objects(plab)
    rows = []
    for r, c in zip(*np.nonzero(peaks)):
        if rabs[r, c] < k * line_sigma:
            continue
        r0, r1, c0, c1 = max(0, r - w // 2), r + w // 2 + 1, max(0, c - w // 2), c + w // 2 + 1
        win = np.where(exceed[r0:r1, c0:c1], np.abs(np.nan_to_num(resid[r0:r1, c0:c1])), -1)
        rr, cc = np.unravel_index(np.argmax(win), win.shape)
        lab_id = plab[r0 + rr, c0 + cc]
        sl = sls[lab_id - 1]
        ext = min(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) * cell
        if ext < line_spacing and rabs[r, c] < strong_k * line_sigma:
            continue
        half = a >= a[r, c] / 2
        lab, _ = ndi.label(half)
        n = int((lab == lab[r, c]).sum())
        rows.append({"easting": float(X[r, c]), "northing": float(Y[r, c]), "asig_peak": float(a[r, c]),
                     "resid_peak_abs_nT": float(rabs[r, c]), "snr": float(rabs[r, c] / line_sigma),
                     "width_m": float(2 * np.sqrt(n * cell * cell / np.pi))})
    df = pd.DataFrame(rows, columns=["easting", "northing", "asig_peak", "resid_peak_abs_nT", "snr", "width_m"])
    df = df.sort_values("asig_peak", ascending=False).reset_index(drop=True)
    df.insert(0, "pick_id", np.arange(len(df)))
    df.attrs["asig_threshold"] = thr
    return df


def repeat_rms(lines: pd.DataFrame, col: str, tol_m: float = 0.25) -> float | None:
    if "is_repeat" not in lines or not (lines["is_repeat"] == 1).any():
        return None
    rep, main = lines[lines.is_repeat == 1], lines[lines.is_repeat != 1]
    d, j = cKDTree(main[["easting", "northing"]].values).query(rep[["easting", "northing"]].values)
    ok = d <= tol_m
    if not ok.any():
        return None
    diff = rep[col].values[ok] - main[col].values[j[ok]]
    return float(np.sqrt(np.mean(diff ** 2)))


def process_lines(lines: pd.DataFrame, base: pd.DataFrame, pc: dict, line_spacing: float) -> dict:
    need = {"line_id", "time_utc", "easting", "northing", "tf_nT"}
    miss = need - set(lines.columns)
    if miss:
        raise ValueError(f"line data missing columns {sorted(miss)}")
    lines = lines.sort_values(["line_id", "time_utc"]).reset_index(drop=True)
    lines, n_spk = despike(lines, pc["despike_window"], pc["despike_k_mad"])
    lines = diurnal_correct(lines, base)
    x, y = lines.easting.values.astype(float), lines.northing.values.astype(float)
    r, coef = remove_regional(x, y, lines.tf_corr_nT.values.astype(float), pc["poly_order"])
    lines["resid_nT"] = r
    main = lines[lines.get("is_repeat", 0) != 1] if "is_repeat" in lines else lines
    sigma = line_noise(main, "resid_nT")
    G, X, Y, T = to_grid(main.easting.values, main.northing.values, main.resid_nT.values,
                         pc["grid_cell_m"], pc["mask_factor"] * line_spacing)
    return {"lines": lines, "grid": G, "X": X, "Y": Y, "T": T, "sigma": sigma, "n_spikes": n_spk,
            "regional_coef": coef.tolist(), "repeat_rms_nT": repeat_rms(lines, "resid_nT"), "line_spacing": line_spacing}


def process_grid(path: Path, pc: dict) -> dict:
    import rasterio
    with rasterio.open(path) as s:
        G = s.read(1, masked=True).astype(float).filled(np.nan)
        T = s.transform
        ek.assert_crs(s, "EPSG:6346")
    rr, cc = np.mgrid[0:G.shape[0], 0:G.shape[1]]
    X, Y = T.c + (cc + 0.5) * T.a, T.f + (rr + 0.5) * T.e
    ok = np.isfinite(G)
    r, coef = remove_regional(X[ok], Y[ok], G[ok], pc["poly_order"])
    R = np.full(G.shape, np.nan)
    R[ok] = r
    return {"grid": R, "X": X, "Y": Y, "T": T, "sigma": robust_sigma(r), "n_spikes": 0,
            "regional_coef": coef.tolist(), "repeat_rms_nT": None, "cell": abs(T.a),
            "line_spacing": abs(T.a)}


def analyse(P: dict, pc: dict, test_object=None, tol=1.0) -> tuple[pd.DataFrame, dict, np.ndarray]:
    cell = P.get("cell", pc["grid_cell_m"])
    f, dx, dy, dz, asig = fft_derivatives(P["grid"], cell, pc["rtp"], pc["inclination_deg"], pc["declination_deg"])
    picks = pick_anomalies(asig, f, P["X"], P["Y"], cell, pc["pick_k_sigma"], P["sigma"], pc["pick_window_m"],
                           P.get("line_spacing", 1.0), pc.get("strong_k_sigma", 6.0))
    qc = {"noise_sigma_nT": P["sigma"], "n_spikes_replaced": P["n_spikes"], "regional_coef": P["regional_coef"],
          "repeat_rms_nT": P["repeat_rms_nT"], "n_picks": int(len(picks)),
          "asig_threshold": picks.attrs.get("asig_threshold"), "grid_valid_frac": float(np.isfinite(P["grid"]).mean()),
          "rtp": pc["rtp"]}
    if test_object is not None:
        if len(picks):
            d = np.hypot(picks.easting - test_object[0], picks.northing - test_object[1])
            qc["test_object"] = {"position": list(test_object), "nearest_pick_m": float(d.min()),
                                 "found": bool(d.min() <= tol)}
        else:
            qc["test_object"] = {"position": list(test_object), "nearest_pick_m": None, "found": False}
    return picks, qc, asig


def run(cfg: dict, out_root: Path | None = None, sites=(), test_objects: dict | None = None,
        from_grid: bool = False, data: dict | None = None) -> dict:
    """data: optional {site: (lines_df, base_df)} for tests. Otherwise read the assumed files."""
    from _common import write_tif
    pc, ls = cfg["processing"], cfg["survey"]["line_spacing_m"]
    test_objects = test_objects or {}
    rd = ek.new_run(cfg["exp_id"], "magproc", {"processing": pc, "sites": list(sites)}, base=out_root,
                    why="S3 anomaly processing")
    inputs, outputs, res = [], [], {}
    for site in sites:
        if data and site in data:
            P = process_lines(*data[site], pc, ls)
        elif from_grid:
            p = io.need_input(cfg, "grid_tif", site=site)
            inputs.append(p)
            P = process_grid(p, pc)
        else:
            pl, pb = io.need_input(cfg, "line_data", site=site), io.need_input(cfg, "base_station", site=site)
            inputs += [pl, pb]
            P = process_lines(pd.read_csv(pl), pd.read_csv(pb), pc, ls)
        picks, qc, asig = analyse(P, pc, test_objects.get(site, pc.get("test_object")), pc["test_object_tol_m"])
        picks.insert(0, "site_id", site)
        o_r, o_a = rd / f"mag_residual_{site}.tif", rd / f"mag_asig_{site}.tif"
        o_p, o_q = rd / f"mag_anomalies_{site}.csv", rd / f"mag_qc_{site}.json"
        write_tif(o_r, P["grid"].astype("float32"), transform=P["T"], crs=cfg["crs"], dtype="float32", nodata=-9999.0)
        write_tif(o_a, asig.astype("float32"), transform=P["T"], crs=cfg["crs"], dtype="float32", nodata=-9999.0)
        picks.to_csv(o_p, index=False)
        o_q.write_text(json.dumps(qc, indent=2, default=str), encoding="utf-8")
        outputs += [o_r, o_a, o_p, o_q]
        res[site] = {"picks": picks, "qc": qc}
        print(site, json.dumps({k: v for k, v in qc.items() if k != "regional_coef"}, default=str))
    ek.write_provenance(rd, inputs, outputs, params=pc)
    return {"run_dir": rd, "sites": res}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--site", action="append", required=True)
    ap.add_argument("--test-object", nargs=2, type=float, default=None, help="E N of the placed steel object (all sites)")
    ap.add_argument("--from-grid", action="store_true")
    a = ap.parse_args()
    to = {s: tuple(a.test_object) for s in a.site} if a.test_object else None
    run(io.load_config(a.config), a.out_root, a.site, to, a.from_grid)


if __name__ == "__main__":
    main()
