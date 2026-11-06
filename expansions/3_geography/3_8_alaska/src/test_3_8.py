"""Smoke tests for 3.8 Alaska. Tiny synthetic data, no GPU, no network.

Run: python -m pytest -q expansions/3_geography/3_8_alaska/src/test_3_8.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "3_4_gulf_texas" / "src"))
import _ak_active_layer_check_ak1 as al  # noqa: E402
import _ak_injection_recovery_ak1 as ir  # noqa: E402
import _ak_insar_series_ak1 as ins  # noqa: E402
import _ak_observability_ak1 as ob  # noqa: E402
import _ak_placebo_ak1 as pl  # noqa: E402
import _ak_rate_difference_ak1 as rd  # noqa: E402
import _ak_reference_stability_ak1 as rs  # noqa: E402
import _ak_site_matching_ak1 as sm  # noqa: E402
import _ak_wells_sites_ak1 as ws  # noqa: E402

WL = 0.05546576


def test_site_clusters():
    x = np.array([0, 100, 250, 1000, 1290, 5000.0])
    lab = ws.cluster_sites(x, np.zeros(6), 300)
    assert len(set(lab)) == 3 and lab[0] == lab[2] and lab[3] == lab[4] != lab[5]


def test_sbas_inversion_recovers_ramp():
    dates = list(pd.date_range("2020-06-01", periods=8, freq="12D"))
    pairs = [(dates[i], dates[j]) for i in range(8) for j in (i + 1, i + 2) if j < 8]
    A = ins.sbas_design(pairs, dates)
    truth = np.linspace(0, 7, 8)
    phi = np.array([[truth[dates.index(b)] - truth[dates.index(a)]] for a, b in pairs])
    ts = ins.invert_series(phi, A)
    assert np.allclose(ts[:, 0], truth)
    assert np.isclose(ins.phase_to_los_mm(np.array([-4 * np.pi]), WL)[0], WL * 1000)
    wr = {(dates[0], dates[1]): np.array([0.1]), (dates[1], dates[2]): np.array([0.2]),
          (dates[0], dates[2]): np.array([0.3])}
    cl = ins.closure_phase(wr, dates[:3])
    assert len(cl) == 1 and cl["closure_abs_mean"].iloc[0] < 1e-9


def test_rates_amplitude_and_decision():
    dates = [d for y in (2019, 2020, 2021) for d in pd.date_range(f"{y}-05-01", f"{y}-09-30", freq="12D")]
    los = ir.injected_los(dates, rate_mm_yr=-10, seasonal_mm=0, thaw=[5, 6, 7, 8, 9])
    s = pd.DataFrame({"date": dates, "los_mm": los})
    assert abs(rd.end_of_season_rate(s, 9, [5, 6, 7, 8, 9]) + 10) < 0.5
    s2 = pd.DataFrame({"date": dates, "los_mm": ir.injected_los(dates, 0, 8, [5, 6, 7, 8, 9])})
    assert 6 < rd.seasonal_amplitude(s2, [5, 6, 7, 8, 9]) <= 8.01
    assert rd.decide_two_sided(3, 5, 2) == "decisive, difference"
    assert rd.decide_two_sided(-1, 1, 2) == "decisive, equivalence"
    assert rd.decide_two_sided(-1, 3, 2) == "inconclusive"


def test_injection_recovers_on_synthetic_stack():
    phi, coh, pairs, dates = ir.synthetic_stack(0, n_pix=10, noise_rad=0.05)
    r = ir.run_injection(phi, coh, pairs, dates, WL, 10.0, 5.0, [5, 6, 7, 8, 9], 9, 0.0)
    assert abs(r["rate_rec"] - 10.0) < 1.5


def test_matching_and_diffs():
    sites = pd.DataFrame({"site_id": ["s1", "s2"], "landcover": [1, 1], "ice_class": ["h", "h"], "slope_class": ["f", "f"],
                          "wetness": [0.5, 0.9], "road_dist_m": [100, 200], "frame": ["F", "F"]})
    cands = pd.DataFrame({"cand_id": [f"c{i}" for i in range(5)], "landcover": [1, 1, 1, 1, 2],
                          "ice_class": "h", "slope_class": "f", "wetness": [0.5, 0.55, 0.9, 0.95, 0.5],
                          "road_dist_m": [100, 110, 200, 190, 100], "frame": "F"})
    m, un = sm.match(sites, cands, ["landcover", "ice_class", "slope_class"], ["wetness", "road_dist_m"], 2)
    assert set(m[m.site_id == "s1"].cand_id) == {"c0", "c1"} and set(m[m.site_id == "s2"].cand_id) == {"c2", "c3"}
    assert not un and "c4" not in set(m.cand_id)
    pts = pd.DataFrame({"point_id": ["s1", "s2", "c0", "c1", "c2", "c3"], "kind": ["site"] * 2 + ["control"] * 4,
                        "rate": [5.0, 1.0, 1.0, 3.0, 0.0, 2.0]})
    d = rd.matched_diffs(pts, m, "rate")
    assert np.allclose(d.set_index("site_id")["diff"].to_numpy(), [3.0, 0.0])
    pm = pl.placebo_medians(pd.DataFrame({"site_id": ["a", "a", "b", "b"], "value": [1.0, 1.0, 2.0, 2.0]}), 20, 0)
    assert np.allclose(pm, 0.0)


def test_observability_and_reference():
    assert ob.fill_fraction(10000, 40) == 1.0 and np.isclose(ob.fill_fraction(10000, 200), 0.25)
    acq = pd.DataFrame({"frame": "F", "mission": "sentinel1", "date": ["2020-06-01", "2020-07-01", "2020-01-01"]})
    flags = pd.DataFrame({"frame": ["F"], "date": ["2020-07-01"], "snow": [False], "wet_melt": [True], "flood": [False]})
    u = ob.usable_per_season(acq, flags, [5, 6, 7, 8, 9])
    assert u["usable"].tolist() == [1]
    assert ob.decide(0.5, 10, 6, None, 1.0).startswith("defer") and ob.decide(0.01, 10, 6, 5, 1) == "no-go"
    dates = [d for y in (2019, 2020) for d in pd.date_range(f"{y}-06-01", f"{y}-09-20", freq="30D")]
    rows = []
    for pid, kind, rate in (("r1", "reference", 0.0), ("r2", "reference", 0.1), ("c1", "control", 1.0), ("c2", "control", -1.0)):
        los = ir.injected_los(dates, rate, 0, [5, 6, 7, 8, 9])
        rows += [{"point_id": pid, "kind": kind, "date": d.date().isoformat(), "los_mm": v} for d, v in zip(dates, los)]
    ser = pd.DataFrame(rows)
    pairs = rs.reference_pairs(ser, 9, [5, 6, 7, 8, 9])
    assert len(pairs) == 1 and abs(pairs["diff_rate_mm_yr"].iloc[0] + 0.1) < 0.05
    assert rs.noise_floor(ser, "r1", 9, [5, 6, 7, 8, 9]) > 0.5
    amp = al.amplitude_by_year(ser.assign(kind="active_layer"), [5, 6, 7, 8, 9])
    assert set(amp.columns) == {"site", "year", "amp_mm"}
