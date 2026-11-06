"""Smoke tests for 4.5 multitemporal lidar on tiny synthetic data. Seconds, no network, no GPU.

Run  python -m pytest -q expansions/4_modalities/4_5_multitemporal_lidar/src/test_4_5.py -p no:cacheprovider
"""
from __future__ import annotations

import copy
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _dod_shared_io as io  # noqa: E402
import _dod_flight_windows_9t as S0  # noqa: E402
import _dod_plug_eligibility_9t as S1  # noqa: E402
import _dod_controls_matched_9t as S2  # noqa: E402
import _dod_registration_check_9t as REG  # noqa: E402
import _dod_recovery_test_9t as S3  # noqa: E402
import _dod_plug_change_compare_9t as S4  # noqa: E402

CRS = "EPSG:6346"
RES = 2.0
N = 400                       # 800 m square
X0, Y1 = 620000.0, 4596000.0


def _cfg():
    cfg = copy.deepcopy(io.load_config())
    cfg["bbox_9t"] = [X0, Y1 - N * RES, X0 + N * RES, Y1]
    cfg["flag_rule"]["ctrl_dist_m"] = [60.0, 300.0]
    cfg["flag_rule"]["min_ctrl"] = 8
    cfg["registration"]["sample_cells"] = 20000
    cfg["recovery"].update(heights_m=[0.5], areas_m2=[400.0])
    cfg["compare"].update(bootstrap_B=50, n_placebo=20)
    cfg["eligibility"]["min_eligible_pads"] = 2
    return cfg


def _surfaces(seed=0):
    from rasterio.transform import from_origin
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:N, 0:N] * RES
    early = 300 + 0.05 * xx + 0.03 * yy + 2 * np.sin(xx / 40) * np.cos(yy / 55)
    late = early + rng.normal(0, 0.06, early.shape)
    return early, late, from_origin(X0, Y1, RES, RES)


def _pads():
    import geopandas as gpd
    from shapely.geometry import box
    cells = [(X0 + 100 + 150 * i, Y1 - 100 - 150 * j) for i in range(4) for j in range(4)]
    g = gpd.GeoDataFrame({"pad_id": range(len(cells)), "area_m2": 900.0},
                         geometry=[box(x, y - 30, x + 30, y) for x, y in cells], crs=CRS)
    return g


def test_gps_dates_and_windows():
    assert S0.gps_adjusted_to_date(268931930.4) == dt.date(2020, 3, 22)
    proj = {"name": "P", "year_lo": 2006, "year_hi": 2008}
    meta = pd.DataFrame({"project": ["P"], "tile": [None], "start_date": ["2007-03-01"], "end_date": ["2007-04-15"],
                         "source": ["report p3"]})
    w = S0.tile_window({"tile": "t.laz"}, proj, meta)
    assert w["method"] == "metadata" and w["window_end"] == "2007-04-15"
    w = S0.tile_window({"tile": "t.laz", "header_creation_date": "2008-06-01"}, proj, None)
    assert w["method"] == "year_bounds+header_upper" and w["window_end"] == "2008-06-01"
    assert S0.anomalies({"tile": "t", "gps_first": "2009-01-02"}, proj)


def test_scan_laz_adjusted_gps(tmp_path):
    import laspy
    h = laspy.LasHeader(point_format=1, version="1.2")
    h.global_encoding.gps_time_type = laspy.header.GpsTimeType.STANDARD
    h.offsets, h.scales = [620000, 4595000, 0], [0.01, 0.01, 0.01]
    las = laspy.LasData(h)
    las.x, las.y, las.z = np.array([620001.0, 620002.0]), np.array([4595001.0, 4595002.0]), np.array([300.0, 301.0])
    las.gps_time = np.array([268931930.0, 268935000.0])
    p = tmp_path / "t.las"
    las.write(p)
    r = S0.scan_laz(p, None)
    assert r["gps_first"] == "2020-03-22" and r["scan"] == "full"


def _elig(tmp_path):
    import geopandas as gpd
    pads = _pads()
    c = pads.geometry.centroid
    plug = [None, "2012-05-01", "2007-06-01", "2015-01-01", "1800-01-01", "2021-01-01"] + [None] * 10
    wells = gpd.GeoDataFrame({"PERMIT_NUM": [f"w{i}" for i in range(16)], "DATE_PLUGG": pd.to_datetime(plug),
                              "SPUD_DATE": pd.to_datetime(["1950-01-01"] * 16)}, geometry=list(c), crs=CRS)
    win = pd.DataFrame({"which": ["early", "late"], "tile": ["", ""], "window_start": ["2006-01-01", "2019-01-01"],
                        "window_end": ["2008-12-31", "2019-12-31"], "method": ["year_bounds"] * 2})
    wp = tmp_path / "w.csv"
    win.to_csv(wp, index=False)
    r = S1.run(_cfg(), out_root=tmp_path, windows_csv=wp, wells=wells, pads=pads)
    W = pd.read_csv(r["wells"])
    assert list(W.elig_class[:6]) == ["excluded", "eligible", "ambiguous", "eligible", "excluded", "excluded"]
    assert r["counts"]["treated_pads"] == 2 and r["counts"]["readiness"] == "ready"
    return r


def test_eligibility_classes(tmp_path):
    _elig(tmp_path)


def test_registration_recovers_shift():
    early, _, T = _surfaces()
    yy, xx = np.mgrid[0:N, 0:N] * RES
    f = lambda X, Y: 300 + 0.05 * X + 0.03 * Y + 2 * np.sin(X / 40) * np.cos(Y / 55)  # noqa: E731
    Yn = (N * RES - yy)
    E, L = f(xx, Yn), f(xx - 1.0, Yn - 0.5) + 0.05
    fit, *_ = REG.fit_shift(E, L, RES, np.ones(E.shape, bool), 20000, 0)
    assert abs(fit["dx_m"] - 1.0) < 0.05 and abs(fit["dy_m"] - 0.5) < 0.05 and abs(fit["dz0_m"] - 0.05) < 0.01
    E2 = REG.apply_shift(E, RES, fit["dx_m"], fit["dy_m"])
    assert np.nanstd((L - E2)[20:-20, 20:-20]) < 0.02


def test_recovery_chain_sees_half_metre(tmp_path):
    early, late, T = _surfaces()
    pads = _pads()
    sites = np.array([[X0 + 200 + 120 * i, Y1 - 200 - 120 * j] for i in range(3) for j in range(3)])
    r = S3.run(_cfg(), out_root=tmp_path, rasters=(early, late, T), layers=[pads, None, None], sites_xy=sites)
    cv = r["curve"][r["curve"].slope_class == "all"].set_index("height_m")
    assert cv.loc[0.5, "rate"] >= 0.7 and cv.loc[0.0, "rate"] <= 0.3


def test_controls_and_compare(tmp_path):
    r1 = _elig(tmp_path)
    early, late, T = _surfaces(1)
    pads = _pads()
    # real fill on the two treated pads (w1 on pad 1, w3 on pad 3)
    from rasterio.features import geometry_mask
    m = ~geometry_mask(list(pads.geometry.iloc[[1, 3]]), out_shape=late.shape, transform=T, all_touched=True)
    late = late + 0.6 * m
    cfg = _cfg()
    cfg["controls"]["caliper_sd"] = 5.0
    r2 = S2.run(cfg, out_root=tmp_path, elig_dir=r1["run_dir"], rasters=(early, late, T), layers=(pads, None))
    assert r2["balance"]["n_treated_matched"] == 2 and r2["balance"]["n_controls"] >= 2
    import _icp_change_classify_9t as CC
    hp = CC.highpass(CC.destripe((late - early).astype(np.float32))).astype(float)
    r4 = S4.run(cfg, out_root=tmp_path, ctrl_dir=r2["run_dir"], rasters=(hp, late, T), layers=[pads, None, None],
                pool_pads=pads.iloc[[0, 2, 4, 5, 6, 7, 8, 9, 10, 11]])
    pr = r4["result"]["primary"]
    assert pr["n_treated"] == 2 and pr["estimate"] > 0.5
    assert pr["verdict"].startswith("inconclusive") or pr["verdict"] in ("success", "failure")
    assert r4["result"]["placebo"]["reps"] == 20


def test_missing_input_named(tmp_path):
    with pytest.raises(FileNotFoundError, match="MISSING INPUT S0 flight windows"):
        S1.run(_cfg(), out_root=tmp_path / "empty")
