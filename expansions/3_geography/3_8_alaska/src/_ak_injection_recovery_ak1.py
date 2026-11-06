"""S4 (3.8). Injection-recovery acceptance test through the whole inversion chain.

Purpose
    Add known LOS displacement to the unwrapped interferogram phase at control pixels (a 10-pixel
    footprint): linear ramps at inject_amplitudes_mm_yr and seasonal cycles at inject_seasonal_mm.
    Convert to phase with the mission wavelength, add it to the noisy stack, run the same small-baseline
    inversion (S2) once (no noise-cancelling difference against an uninjected inversion, review G-08) and the
    same rate and amplitude estimators (S5b), then report recovered fraction and bias per amplitude and
    per coherence band. Readiness. The chain must recover 2 x delta (bias within 25 % of the injection).
    Results are saved before any well result is unmasked.
Inputs
    data/ak1/derived/ak_stack_ak1/ifg_manifest_ak1.csv (S2 inputs), or --synthetic for a self-test stack
Outputs
    data/ak1/results/ak_injection_recovery_ak1.csv
Run
    python expansions/3_geography/3_8_alaska/src/_ak_injection_recovery_ak1.py --synthetic
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
from _ak_insar_series_ak1 import invert_series, phase_to_los_mm, sbas_design  # noqa: E402
from _ak_rate_difference_ak1 import end_of_season_rate, seasonal_amplitude  # noqa: E402

ek = gt.ek
EXP = "3.8"


def injected_los(dates: list, rate_mm_yr: float, seasonal_mm: float, thaw: list[int]) -> np.ndarray:
    t = np.array([(d - dates[0]).days / 365.25 for d in dates])
    doy = np.array([d.dayofyear for d in dates])
    season = np.where(np.isin([d.month for d in dates], thaw), seasonal_mm * np.sin(np.pi * (doy - 120) / 150), 0.0)
    return rate_mm_yr * t + np.clip(season, 0, None)


def los_to_phase(los_mm: np.ndarray, wavelength_m: float) -> np.ndarray:
    return -(los_mm / 1000.0) * 4 * np.pi / wavelength_m


def run_injection(phi: np.ndarray, coh: np.ndarray, pairs, dates, wl, rate, amp, thaw, eos, coh_min) -> dict:
    """phi, coh (n_ifg, n_pix) at the chosen control pixels. Returns recovered rate and amplitude.

    The known signal is added to the noisy phase stack BEFORE inversion, and the rate and amplitude are read
    from that one inversion (review G-08). The old version subtracted a no-injection inversion of the same
    stack. The inversion is linear, so that difference equalled invert(dphi) and noise cancelled exactly.
    Now the stack's noise and its own background motion enter the recovered values, as they will at wells.
    """
    A = sbas_design(pairs, dates)
    inj = injected_los(dates, rate, amp, thaw)
    idx = {d: i for i, d in enumerate(dates)}
    dphi = np.array([los_to_phase(inj[idx[b]] - inj[idx[a]], wl) for a, b in pairs])
    test = phase_to_los_mm(invert_series(phi + dphi[:, None], A, coh >= coh_min), wl).mean(axis=1)
    s = pd.DataFrame({"date": dates, "los_mm": test})
    return {"rate_rec": end_of_season_rate(s, eos, thaw), "amp_rec": seasonal_amplitude(s, thaw)}


def synthetic_stack(seed: int = 0, n_pix: int = 10, noise_rad: float = 0.3):
    rng = np.random.default_rng(seed)
    dates = [d for y in (2019, 2020, 2021, 2022) for d in pd.date_range(f"{y}-05-01", f"{y}-09-30", freq="12D")]
    pairs = [(dates[i], dates[j]) for i in range(len(dates)) for j in (i + 1, i + 2) if j < len(dates)]
    phi = rng.normal(0, noise_rad, (len(pairs), n_pix))
    coh = rng.uniform(0.3, 0.9, (len(pairs), n_pix))
    return phi, coh, pairs, dates


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--synthetic", action="store_true", help="self-test on a synthetic stack (no data needed)")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    wl = pr["wavelength_m"][pr["mission"]]
    if a.synthetic:
        phi, coh, pairs, dates = synthetic_stack(int(pr["master_seed"]))
        bands = {"all": np.arange(phi.shape[1])}
    else:
        try:
            man = pd.read_csv(gt.config_input(cfg, "ifg_manifest", EXP), parse_dates=["date1", "date2"])
        except gt.MissingInputError as e:
            print(str(e), file=sys.stderr)
            return 2
        import rasterio
        dates = sorted(set(man["date1"]) | set(man["date2"]))
        pairs = list(zip(man["date1"], man["date2"]))
        rng = np.random.default_rng(int(pr["master_seed"]))
        stack, cstack = [], []
        for _, r in man.iterrows():
            with rasterio.open(r.unw_tif) as u, rasterio.open(r.corr_tif) as c:
                stack.append(u.read(1).ravel())
                cstack.append(c.read(1).ravel())
        phi_all, coh_all = np.stack(stack), np.stack(cstack)
        mc = np.nanmedian(coh_all, axis=0)
        pick = rng.choice(np.nonzero(np.isfinite(mc))[0], 300, replace=False)
        phi, coh = phi_all[:, pick], coh_all[:, pick]
        bands = {f"coh_{lo:.1f}_{hi:.1f}": np.nonzero((mc[pick] >= lo) & (mc[pick] < hi))[0]
                 for lo, hi in ((0.2, 0.4), (0.4, 0.6), (0.6, 1.01))}
    rows = []
    for band, idx in bands.items():
        for k in range(0, len(idx) - 9, 10):            # 10-pixel footprints
            fp = idx[k:k + 10]
            for rate in pr["inject_amplitudes_mm_yr"]:
                for amp in pr["inject_seasonal_mm"]:
                    r = run_injection(phi[:, fp], coh[:, fp], pairs, dates, wl, rate, amp, pr["thaw_months"],
                                      pr["end_of_season_month"], pr["coherence_min"])
                    rows.append({"band": band, "footprint": k // 10, "rate_inj": rate, "amp_inj": amp, **r,
                                 "rate_bias": r["rate_rec"] - rate,
                                 "recovered": abs(r["rate_rec"] - rate) <= 0.25 * rate})
    df = pd.DataFrame(rows)
    summ = df.groupby(["band", "rate_inj"]).agg(recovered=("recovered", "mean"), bias=("rate_bias", "median")).reset_index()
    out = ek.sub(EXP, "results/tables") / "ak_injection_selftest.csv" if a.synthetic else \
        ek.area_dir("ak1") / "results" / "ak_injection_recovery_ak1.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    summ.to_csv(out, index=False)
    d = pr["delta_mm_yr"]
    print(summ.to_string(index=False))
    if d is not None:
        ok = summ[summ["rate_inj"] >= 2 * d]["recovered"].min() >= 0.9 if (summ["rate_inj"] >= 2 * d).any() else False
        print(f"readiness (recovers 2 x delta = {2 * d}): {bool(ok)}")
    else:
        print("readiness undecided. delta_mm_yr (D-AK1) is not set")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
