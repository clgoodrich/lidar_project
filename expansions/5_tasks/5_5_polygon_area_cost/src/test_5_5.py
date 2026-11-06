"""Smoke tests for 5.5 polygon area and cost on tiny synthetic data. No GPU, no network, no real data.

Run: python -m pytest -q expansions/5_tasks/5_5_polygon_area_cost/src/test_5_5.py -p no:cacheprovider
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _padarea_geometry_tools as gt  # noqa: E402
import _padarea_by_pad_9t as bp  # noqa: E402
import _padarea_agreement_9t as ag  # noqa: E402
import _padarea_cost_mc_9t as mc  # noqa: E402
import _padarea_survey_ingest_9t as si  # noqa: E402
import _padarea_redraw_sample_9t as rd  # noqa: E402

CRS = "EPSG:6346"
X0, Y0 = 619500.0, 4593000.0


def _pads(n=12, scale=1.2, seed=0):
    import geopandas as gpd
    from shapely.geometry import box
    from shapely import affinity
    rng = np.random.default_rng(seed)
    cx = X0 + 40 + 60 * (np.arange(n) % 6)
    cy = Y0 + 40 + 200 * (np.arange(n) // 6)
    side = rng.uniform(20, 50, n)
    ref = gpd.GeoDataFrame(dict(pad_id=np.arange(n)), geometry=[box(x - s / 2, y - s / 2, x + s / 2, y + s / 2)
                                                                 for x, y, s in zip(cx, cy, side)], crs=CRS)
    pred = gpd.GeoDataFrame(dict(score=rng.uniform(.5, .9, n)),
                            geometry=[affinity.scale(g, np.sqrt(scale), np.sqrt(scale)) for g in ref.geometry], crs=CRS)
    return ref, pred


def _nested(scales, spacing=500.0, side=20.0):
    """One square pad per scale, far apart. The model polygon is the pad scaled in area by s about its centre,
    so the true log ratio is ln(s) and nested IoU is min(s, 1/s). Expected values are known by construction."""
    import geopandas as gpd
    from shapely.geometry import box
    from shapely import affinity
    cx = X0 + 100 + spacing * np.arange(len(scales))
    ref = gpd.GeoDataFrame(dict(pad_id=np.arange(len(scales))),
                           geometry=[box(x - side / 2, Y0 + 90, x + side / 2, Y0 + 110) for x in cx], crs=CRS)
    pred = gpd.GeoDataFrame(dict(score=np.linspace(0.9, 0.6, len(scales))),
                            geometry=[affinity.scale(g, np.sqrt(s), np.sqrt(s)) for g, s in zip(ref.geometry, scales)],
                            crs=CRS)
    return ref, pred


def test_overlap_rule_does_not_truncate_area_error():
    # 5.5-01. Scales 0.2 and 4 have IoU 0.2 and 0.25, below the 0.3 gate. Pre-fix they were dropped,
    # so |r| could never exceed ln(1/0.3) = 1.204. The primary rule must keep them with r = ln(s).
    scales = [0.2, 0.5, 1.3, 4.0]
    ref, pred = _nested(scales)
    T = gt.per_pad(pred, ref)
    assert T.matched.tolist() == [1, 1, 1, 1]
    assert np.allclose(T.log_ratio, np.log(scales), atol=1e-6)
    assert T.log_ratio.abs().max() == pytest.approx(np.log(5.0), abs=1e-6)
    Ts = gt.per_pad(pred, ref, rule="iou_gate", iou_min=0.3)
    assert Ts.matched.tolist() == [0, 1, 1, 0]           # the gate keeps only IoU 0.5 and 1/1.3
    assert np.allclose(Ts.iou[Ts.matched == 1], [0.5, 1 / 1.3], atol=1e-6)


def test_match_is_one_to_one_by_score():
    import geopandas as gpd
    from shapely.geometry import box
    ref = gpd.GeoDataFrame(dict(pad_id=[0]), geometry=[box(0, 0, 10, 10)], crs=CRS)
    pred = gpd.GeoDataFrame(dict(score=[0.6, 0.9]), geometry=[box(0, 0, 10, 10), box(5, 0, 15, 10)], crs=CRS)
    tid, iou = gt.match_one_to_one(pred, ref)
    assert tid.tolist() == [-1, 0] and iou[1] == pytest.approx(50 / 150)   # higher score claims the pad first


def test_road_length_in_window():
    # 5.5-02. Pad 10 x 10. A road runs from the east edge out to x = 100 along y = 5. Within 30 m of the edge
    # the road length is 30 m. A second road 50 m away adds nothing.
    import geopandas as gpd
    from shapely.geometry import box, LineString
    ref = gpd.GeoDataFrame(dict(pad_id=[0]), geometry=[box(0, 0, 10, 10)], crs=CRS)
    roads = gpd.GeoDataFrame(geometry=[LineString([(10, 5), (100, 5)]), LineString([(-100, 60), (100, 60)])], crs=CRS)
    assert gt.road_length(ref, roads, 30.0)[0] == pytest.approx(30.0, abs=1e-6)
    assert np.isnan(gt.road_length(ref, None, 30.0)[0])


def test_cost_units_converted_or_refused():
    # 5.5-02. Area cost per acre is converted to per m2. sqrt(lo hi) is the lognormal median.
    C = pd.DataFrame(dict(item=["fixed_per_well", "area_restoration", "road_restoration"],
                          unit=["USD per well", "USD/acre", "USD per ft"], low=[100.0, 4046.8564224, 0.3048],
                          high=[400.0, 4 * 4046.8564224, 4 * 0.3048], condition_class="unknown"))
    c = mc.parse_costs(C, "unknown")
    assert np.exp(c["area_restoration"][0]) == pytest.approx(2.0)      # 1 to 4 USD per m2, median 2
    assert np.exp(c["road_restoration"][0]) == pytest.approx(2.0)      # 1 to 4 USD per m
    assert np.exp(c["fixed_per_well"][0]) == pytest.approx(200.0)
    with pytest.raises(SystemExit):
        mc.parse_costs(C.assign(unit=["USD per well", "USD per pad", "USD per m"]), "unknown")
    with pytest.raises(SystemExit):
        mc.parse_costs(C.drop(columns="unit"), "unknown")


def test_road_term_refuses_without_length():
    T = pd.DataFrame(dict(log_ratio=[0.1, 0.2], block_id=[0, 1], A_ref=[100.0, 200.0], pad_id=[1, 2]))
    costs = {"fixed_per_well": (np.log(100), 0.1), "area_restoration": (0.0, 0.1), "road_restoration": (0.0, 0.1)}
    with pytest.raises(SystemExit):
        mc.simulate(T, costs, 20, [2], 0)
    P, _ = mc.simulate(T.assign(road_length_m=[0.0, 50.0]), costs, 20, [2], 0)
    # pad 2: F = 100, c_a A = 200, c_r L = 50 at the medians, so the area share is 200 / 350
    assert P.f_area_share.iloc[1] == pytest.approx(200 / 350)


def test_boundary_dist_zero_for_identical():
    ref, _ = _pads(2)
    m, h = gt.boundary_dist(ref.geometry.iloc[0], ref.geometry.iloc[0])
    assert m == pytest.approx(0, abs=1e-6) and h == pytest.approx(0, abs=1e-6)


def test_decision_rules():
    s = dict(median_lo=-0.05, median_hi=0.05, p90_abs_r=0.1)
    assert gt.area_decision(s, 0.2231, 0.25) == "success"
    assert gt.area_decision(dict(median_lo=0.3, median_hi=0.4, p90_abs_r=0.5), 0.2231, 0.25) == "failure"
    assert gt.area_decision(dict(median_lo=0.1, median_hi=0.3, p90_abs_r=0.5), 0.2231, 0.25) == "inconclusive"
    assert gt.delta_area(0.25, 0.5, 0.2) == pytest.approx(np.log(1.5))
    assert gt.delta_area(0.25, None, 0.2) == 0.2


def test_break_even_and_lognormal():
    be = mc.break_even(np.full(10, np.log(2)), [0.3])
    assert be["0.30"] == pytest.approx(0.3)
    mu, sd = mc.lognormal(100, 400)
    assert np.exp(mu) == pytest.approx(200) and sd > 0


def test_calibration_arm_flags_constant_bias():
    T = pd.DataFrame(dict(log_ratio=np.r_[np.full(20, 0.4) + np.linspace(-.01, .01, 20)], block_id=np.arange(20) % 6))
    c = ag.calibration_arm(T, 1)
    assert c["useful"] is True


def _cfg(tmp, **inputs):
    cfg = json.loads((HERE / "config_5_5.json").read_text())
    cfg["bootstrap_B"] = 50
    cfg["monte_carlo"]["draws"] = 200
    cfg["inputs"].update({k: str(v) for k, v in inputs.items()})
    for k in cfg["outputs"]:
        cfg["outputs"][k] = str(tmp / Path(cfg["outputs"][k]).name)
    p = tmp / "cfg.json"
    p.write_text(json.dumps(cfg))
    return p


def test_end_to_end_drawn_and_cost(tmp_path):
    import geopandas as gpd
    from shapely.geometry import box
    ref, pred = _pads(12, 1.3)
    ann = tmp_path / "ann.gpkg"
    ref.to_file(ann, layer="plat", driver="GPKG")
    pits = gpd.GeoDataFrame(dict(pit_inside_id=[0]), geometry=[box(X0 + 38, Y0 + 38, X0 + 42, Y0 + 42)], crs=CRS)
    pits.to_file(ann, layer="pit_inside", driver="GPKG")
    from shapely.geometry import LineString
    gpd.GeoDataFrame(dict(id=[0]), geometry=[LineString([(X0, Y0 + 40), (X0 + 400, Y0 + 40)])], crs=CRS).to_file(
        ann, layer="roads", driver="GPKG")
    pr = tmp_path / "pred.gpkg"
    pred.to_file(pr, layer="model_geometry", driver="GPKG")
    blocks = gpd.GeoDataFrame(dict(block_id=[0, 1]), geometry=[box(X0, Y0, X0 + 375, Y0 + 150),
                                                               box(X0, Y0 + 150, X0 + 375, Y0 + 375)], crs=CRS)
    bpath = tmp_path / "blocks.gpkg"
    blocks.to_file(bpath, layer="blocks", driver="GPKG")
    cost = tmp_path / "cost.csv"
    pd.DataFrame(dict(item=["fixed_per_well", "area_restoration", "road_restoration"], condition_class=["unknown", "", ""],
                      unit=["USD per well", "USD per m2", "USD per m"], low=[20000, 2, 5], high=[60000, 8, 20], year=2025, basis="synthetic")).to_csv(cost, index=False)
    cp = _cfg(tmp_path, pad_products=pr, annotations=ann, pad_blocks=bpath, pad_cover=tmp_path / "none.gpkg",
              cost_table=cost, by_pad=tmp_path / "pad_area_by_pad_9t.csv")
    assert bp.main(["--config", str(cp)]) == 0
    D = json.loads((tmp_path / "pad_area_tile_decomposition_9t.json").read_text())
    assert D["n_matched"] == 12 and D["tile_ratio"] > 1.2
    assert rd.main(["--config", str(cp), "--draw"]) == 0
    assert ag.main(["--config", str(cp), "--reference", "drawn"]) == 0
    S = json.loads((tmp_path / "pad_area_agreement_summary_drawn_9t.json").read_text())
    assert S["primary"]["median_r"] == pytest.approx(np.log(1.3), abs=0.02)
    assert mc.main(["--config", str(cp), "--reference", "drawn"]) == 0
    C = json.loads((tmp_path / "pad_cost_error_summary_drawn_9t.json").read_text())
    assert len(C["tolerance"]) == 3 and "portfolio" in C
    assert not Path(C["cost_table"]).is_absolute()
    assert C["median_road_length_m"] > 0                 # the road crosses every pad, so L_road is not 0
    assert (tmp_path / "pad_cost_error_drawn_9t.png").exists()


def test_survey_ingest_reprojects(tmp_path):
    import geopandas as gpd
    from shapely.geometry import box
    ref, _ = _pads(3)
    sv = ref.assign(definition="disturbed", method="RTK", h_acc_m=[0.03, 0.05, 0.2], digitiser="a").to_crs("EPSG:4326")
    sp = tmp_path / "survey.gpkg"
    sv.to_file(sp, driver="GPKG")
    ann = tmp_path / "ann.gpkg"
    gpd.GeoDataFrame(dict(pit_inside_id=[0]), geometry=[box(X0, Y0, X0 + 1, Y0 + 1)], crs=CRS).to_file(ann, layer="pit_inside", driver="GPKG")
    gpd.GeoDataFrame(dict(id=[0]), geometry=[box(X0, Y0, X0 + 2, Y0 + 2).boundary], crs=CRS).to_file(ann, layer="roads", driver="GPKG")
    cp = _cfg(tmp_path, survey=sp, annotations=ann)
    assert si.main(["--config", str(cp)]) == 0
    R = pd.read_csv(tmp_path / "pad_reference_area_9t.csv")
    assert len(R) == 3 and R.acc_flag.sum() == 1
    assert np.allclose(R.A_ref_disturbed, ref.geometry.area, rtol=1e-3)


def test_missing_cost_table_still_writes_break_even(tmp_path):
    T = pd.DataFrame(dict(log_ratio=[0.1, 0.2, -0.1], block_id=[0, 0, 1], A_ref=[100, 200, 300], pad_id=[1, 2, 3]))
    T.to_csv(tmp_path / "pad_area_agreement_drawn_9t.csv", index=False)
    cp = _cfg(tmp_path, cost_table=tmp_path / "absent.csv")
    with pytest.raises(SystemExit):
        mc.main(["--config", str(cp), "--reference", "drawn"])
    assert (tmp_path / "pad_cost_error_summary_drawn_9t.json").exists()
