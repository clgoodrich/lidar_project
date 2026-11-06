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


def test_taper_profile_has_mean_h():
    # oracle by hand. Raised cosine flat to R/2, zero at R. Mean over the disc = (5/4 - 1/pi^2) / 2 = 0.574339
    assert abs(S3.TAPER_MEAN - 0.5743394) < 1e-6
    R, h = 20.0, 0.3
    g = np.linspace(-R, R, 801)
    X, Y = np.meshgrid(g, g)
    inside = np.hypot(X, Y) <= R
    z = S3.inject(X.ravel(), Y.ravel(), np.zeros(X.size), [(0.0, 0.0)], np.pi * R ** 2, h)
    assert abs(-z[inside.ravel()].mean() - h) < 0.005
    assert np.allclose(z[~inside.ravel()], 0.0)
    # tapered, not a step. The edge ring carries much less than the centre
    r = np.hypot(X.ravel(), Y.ravel())
    assert -z[(r > 0.9 * R) & (r <= R)].mean() < 0.1 * -z[r < 0.4 * R].mean()


def _chain_grid(monkeypatch, n=300):
    import _change_rebuild_v2_9t as R
    bb = (X0, Y1 - n * RES, X0 + n * RES, Y1)
    monkeypatch.setattr(R, "BB", bb)
    monkeypatch.setattr(R, "N", n)
    monkeypatch.setattr(R, "RES", RES)
    return bb


def _points(bb, seed=3, density=0.6, pass_offset=0.08):
    """2006 ground points of the _surfaces terrain in two overlapping passes. Pass 200 sits pass_offset high."""
    rng = np.random.default_rng(seed)
    w, hgt = bb[2] - bb[0], bb[3] - bb[1]
    n = int(density * w * hgt)
    x, y = bb[0] + rng.random(n) * w, bb[1] + rng.random(n) * hgt
    xx, yy = x - bb[0], bb[3] - y
    z = 300 + 0.05 * xx + 0.03 * yy + 2 * np.sin(xx / 40) * np.cos(yy / 55) + rng.normal(0, 0.03, n)
    lab = np.where(xx < 0.6 * w, 100, 200)
    both = (xx > 0.35 * w) & (xx < 0.6 * w) & (rng.random(n) < 0.5)
    lab[both] = 200
    z = z + pass_offset * (lab == 200)
    return x, y, z, lab


def _grid_builder(n):
    from scipy.interpolate import LinearNDInterpolator

    def build(x, y, z):
        cs = X0 + (np.arange(n) + 0.5) * RES
        rs = Y1 - (np.arange(n) + 0.5) * RES
        gx, gy = np.meshgrid(cs, rs)
        return LinearNDInterpolator(np.c_[x, y], z)(gx, gy)
    return build


def _ref(n):
    yy, xx = np.mgrid[0:n, 0:n] * RES + RES / 2
    return 300 + 0.05 * xx + 0.03 * yy + 2 * np.sin(xx / 40) * np.cos(yy / 55)


def test_recovery_runs_the_point_chain(tmp_path, monkeypatch):
    """S3 runs the S4 chain on points. A 0.08 m pass offset must be removed by the overlap step (no false alarms),
    a 0.5 m tapered mound must be seen, and a held field that differs from the h = 0 chain must fail the check."""
    from rasterio.transform import from_origin
    n = 300
    bb = _chain_grid(monkeypatch, n)
    pts = _points(bb)
    ref = _ref(n)
    T = from_origin(X0, Y1, RES, RES)
    d19 = ref + np.random.default_rng(5).normal(0, 0.03, ref.shape)
    build = _grid_builder(n)
    hp0, info = S3.point_chain(*pts, ref, d19, build)
    assert abs(info["offset_std_m"] - 0.04) < 0.01           # two passes 0.08 apart, zero-mean gauge -> +-0.04
    pads = _pads().iloc[:0]
    sites = np.array([[X0 + 150 + 150 * i, Y1 - 150 - 150 * j] for i in range(3) for j in range(3)])
    cfg = _cfg()
    cfg["recovery"].update(heights_m=[0.5], areas_m2=[400.0])
    r = S3.run(cfg, out_root=tmp_path, points=pts, surfaces=(ref, d19, T), layers=[pads, None, None],
               sites_xy=sites, build_dem=build, held_field=hp0)
    cv = r["curve"][r["curve"].slope_class == "all"].set_index("height_m")
    assert cv.loc[0.5, "rate"] >= 0.7 and cv.loc[0.0, "rate"] <= 0.3
    assert r["summary"]["reproduce_check"]["status"] == "pass"
    assert set(r["summary"]["chain_info"]) == {"h0", "h0.5_a400"}
    bad = S3.reproduce_check(hp0, hp0 + 0.05, 0.01)
    assert bad["status"] == "fail" and abs(bad["rms_m"] - 0.05) < 1e-9


def test_recovery_refuses_foreign_grid(tmp_path, monkeypatch):
    from rasterio.transform import from_origin
    _chain_grid(monkeypatch, 300)
    ref = _ref(300)
    with pytest.raises(ValueError, match="grid mismatch"):
        S3.run(_cfg(), out_root=tmp_path, points=(np.zeros(1),) * 4,
               surfaces=(ref, ref, from_origin(X0 + 2, Y1, RES, RES)), layers=[_pads(), None, None],
               sites_xy=np.zeros((1, 2)))


def _seam_field(shape, rows=(140, 290), step=0.3):
    """A high-passed field with a +step block between two straight row seams."""
    f = np.zeros(shape)
    f[rows[0]:rows[1]] += step
    return f


def test_seam_distance_is_matched(tmp_path):
    """Treated pads 1 and 3 sit near a seam. Pool pads in rows j = 1, 3 do too, rows j = 0, 2 sit over 100 m away.
    With seam_dist_m matched, every control must come from the near-seam rows (review 4.5-02)."""
    r1 = _elig(tmp_path)
    early, late, T = _surfaces(1)
    pads = _pads()
    hp = _seam_field(early.shape)
    sd = io.value_at(io.seam_distance(hp, RES), T, pads.geometry)
    near = {i for i in range(16) if i % 4 in (1, 3)}
    assert all(sd[i] < 40 for i in near) and all(sd[i] > 100 for i in range(16) if i not in near), sd
    cfg = _cfg()
    cfg["controls"].update(caliper_sd=5.0, max_controls=2)   # 4 controls from 6 near-seam pool pads (pool 0, 5 to 15)
    r2 = S2.run(cfg, out_root=tmp_path, elig_dir=r1["run_dir"], rasters=(early, late, T, hp), layers=(pads, None))
    import geopandas as gpd
    M = gpd.read_file(r2["gpkg"], layer="pads")
    ctrl = set(M[M.role == "control"].pad_id)
    assert ctrl and ctrl <= near, ctrl
    assert "seam_dist_m" in r2["balance"]["covariates_used"]
    with pytest.raises(FileNotFoundError, match="seam_dist_m"):
        S2.run(cfg, out_root=tmp_path, elig_dir=r1["run_dir"], rasters=(early, late, T), layers=(pads, None))


def test_late_window_widened_by_sampled_gps():
    """D20 over 9t is labelled 2019 but flew 2020-03-18. A sampled GPS date outside the year bounds must widen them."""
    proj = {"name": "D20", "year_lo": 2019, "year_hi": 2019}
    w = S0.tile_window({"tile": "t.laz", "scan": "sampled", "gps_first": "2020-03-18", "gps_last": "2020-03-18",
                        "header_creation_date": "2020-11-23"}, proj, None)
    assert (w["window_start"], w["window_end"]) == ("2019-01-01", "2020-03-18")
    assert w["method"] == "year_bounds+gps_widened"
    w = S0.tile_window({"tile": "t.laz", "scan": "full", "gps_first": "2020-03-18", "gps_last": "2020-03-18"},
                       proj, None)
    assert (w["window_start"], w["window_end"], w["method"]) == ("2020-03-18", "2020-03-18", "gps_full_scan")


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
    import _icp_change_classify_9t as CC
    hp = CC.highpass(CC.destripe((late - early).astype(np.float32))).astype(float)
    r2 = S2.run(cfg, out_root=tmp_path, elig_dir=r1["run_dir"], rasters=(early, late, T, hp), layers=(pads, None))
    assert r2["balance"]["n_treated_matched"] == 2 and r2["balance"]["n_controls"] >= 2
    r4 = S4.run(cfg, out_root=tmp_path, ctrl_dir=r2["run_dir"], rasters=(hp, late, T), layers=[pads, None, None],
                pool_pads=pads.iloc[[0, 2, 4, 5, 6, 7, 8, 9, 10, 11]])
    pr = r4["result"]["primary"]
    # both treated pads flagged, no control flagged, 2 clusters. Every bootstrap draw is 1.0, so lo = 1 > 0.10
    assert pr["n_treated"] == 2 and pr["estimate"] == 1.0
    assert (pr["lo"], pr["hi"]) == (1.0, 1.0)
    assert pr["verdict"] == "success"
    assert r4["result"]["placebo"]["reps"] == 20
    assert r4["result"]["seam_matched"] is True


def test_missing_input_named(tmp_path):
    with pytest.raises(FileNotFoundError, match="MISSING INPUT S0 flight windows"):
        S1.run(_cfg(), out_root=tmp_path / "empty")


def test_config_defaults_2026_11_06():
    """Defaults accepted 2026-11-06. Seam band edge 50 m, S3 reproduction tolerance 0.01 m RMS.
    A field off by 0.011 m everywhere fails at 0.01 and one off by 0.009 passes (RMS by hand)."""
    cfg = io.load_config()
    assert cfg["controls"]["seam_band_edges_m"] == [50.0]
    tol = cfg["recovery"]["reproduce_tol_m"]
    assert tol == 0.01
    z = np.zeros((20, 20))
    assert S3.reproduce_check(z, z + 0.011, tol)["status"] == "fail"
    assert S3.reproduce_check(z, z + 0.009, tol)["status"] == "pass"
