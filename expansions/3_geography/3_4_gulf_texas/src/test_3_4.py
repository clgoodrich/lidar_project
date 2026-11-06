"""Smoke tests for 3.4 and the shared core _geo_transfer_core.py. Tiny synthetic data, no GPU, no network.

Run: python -m pytest -q expansions/3_geography/3_4_gulf_texas/src/test_3_4.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo_transfer_core as gt  # noqa: E402
import _gulf_relief_norm_channels as rn  # noqa: E402
import _gulf_rrc_orphans_tx as rrc  # noqa: E402
import _gulf_window_choice_tx as wc  # noqa: E402
import _gulf_wetland_strata as ws  # noqa: E402

CRS = "EPSG:6344"


def _tables(n_blocks, hit_rate, seed=0, n_truth=4, n_cand=60):
    """Synthetic block tables. Each block has n_truth features. hit_rate of them get a high-scoring match."""
    rng = np.random.default_rng(seed)
    tabs = {}
    for b in range(n_blocks):
        rows = []
        for t in range(n_truth):
            s = rng.uniform(0.6, 0.9) if rng.random() < hit_rate else rng.uniform(0.0, 0.05)
            rows.append({"blob_id": f"{b}_{t}", "score": s, "area_m2": 20.0, "truth_id": f"{b}_{t}"})
        for c in range(n_cand):
            rows.append({"blob_id": f"{b}_x{c}", "score": rng.uniform(0.1, 0.5), "area_m2": 10.0, "truth_id": None})
        tabs[f"b{b}"] = {"c": pd.DataFrame(rows), "n_truth": n_truth, "km2": 0.140625}
    return tabs


def test_candidates_and_match():
    p = np.zeros((40, 40))
    p[5:10, 5:10] = 0.8          # 25 px = 6.25 m2, kept
    p[30, 30] = 0.9              # 0.25 m2, dropped
    p[0, 0] = np.nan
    lab, c = gt.extract_candidates(p, 0.5)
    assert len(c) == 1 and abs(c.score[0] - 0.8) < 1e-9
    t = np.zeros((40, 40), int)
    t[5:11, 5:11] = 7
    assert gt.greedy_iou_match(lab, t) == {1: 7}
    t2 = np.zeros((40, 40), int)
    t2[0:40, 0:40] = 3           # IoU far below 0.3
    assert gt.greedy_iou_match(lab, t2) == {}


def test_recall_and_decisions():
    good, ref = _tables(20, 0.95, 1), _tables(20, 0.95, 2)
    r = gt.pooled_recall_at_k(good, list(good))
    assert 0.8 <= r <= 1.0
    dup = gt.pooled_recall_at_k(good, ["b0", "b0"])        # duplicates count twice, recall unchanged
    assert dup == gt.pooled_recall_at_k(good, ["b0"])
    res = gt.transfer_difference(good, ref, margin=0.2, B=200)
    assert res["decision"] == "success"
    bad = _tables(20, 0.1, 3)
    assert gt.transfer_difference(bad, ref, margin=0.1, B=200)["decision"] == "failure"
    few = gt.transfer_difference(_tables(5, 0.9, 4), ref, margin=0.1, B=100)
    assert "permutation" in few and "warning" in few
    pa = gt.paired_arm_difference(good, bad, delta_gain=0.05, B=200)
    assert pa["decision"] == "success"
    with pytest.raises(AssertionError):
        gt.paired_arm_difference(good, _tables(3, 0.5), 0.05, B=10)
    assert gt.ceiling_per_block(good)["ceiling"].between(0, 1).all()
    assert abs(gt.density_scaled_k(10, 20) - 20.0) < 1e-9


def test_blocks_roles_buffer_and_density_grid():
    g = gt.make_blocks((0, 0, 3000, 3000), CRS)
    assert len(g) == 64 and not g["edge"].any()
    r = gt.assign_roles(g, {"test": 0.3, "adapt_train": 0.7}, seed=1, buffer_m=100)
    assert set(r["role"]) <= {"test", "adapt_train", "buffer"}
    near = r[r.role == "adapt_train"].geometry.distance(r[r.role == "test"].geometry.union_all())
    assert (near > 100).all()
    r2 = gt.assign_roles(g, {"test": 0.3, "adapt_train": 0.7}, seed=1, buffer_m=100)
    assert (r.role == r2.role).all()                      # same seed, same draw
    from rasterio.transform import from_origin
    b = gt.make_blocks((0, 0, 750, 375), CRS)
    H, W = 750, 1500
    ground = np.zeros((H, W), np.uint32)
    ground[:, :750] = 2
    occ = ground > 0
    df = gt.block_stats_from_grids(b, from_origin(0, 375, 0.5, 0.5), 0.5, ground, occ,
                                   np.zeros_like(ground), ground.copy())
    assert np.isclose(df.loc[0, "ground_ppm2"], 8.0) and np.isclose(df.loc[0, "void_frac_05"], 0.0)
    assert np.isclose(df.loc[1, "void_frac_05"], 1.0)


def test_observability_and_relief():
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:200, 0:200]
    dem = 0.05 * xx + rng.normal(0, 0.02, (200, 200))
    mdd = gt.min_detectable_depth(dem, np.ones_like(dem, bool))
    assert 0.02 < mdd < 0.12
    s = gt.observable_share(np.array([0.05, 0.5, 1.0, np.nan]), 0.3)
    assert s["n"] == 3 and s["observable"] == 2
    from rasterio.transform import from_origin
    from shapely.geometry import box
    flat = np.zeros((100, 100))
    flat[40:60, 40:60] = -1.0
    d = gt.feature_depths(flat, from_origin(0, 50, 0.5, 0.5), [box(20, 20, 30, 30)])
    assert np.isclose(d[0], 1.0)
    res = rn.plane_residual(0.3 * xx[:50, :50] + 2.0)
    assert np.nanmax(np.abs(res)) < 1e-6
    arr, rel = rn.normalise_block(dem[:50, :50], np.ones((7, 50, 50)))
    assert arr.shape == (8, 50, 50) and rel >= rn.RELIEF_FLOOR_M


def test_registry_rrc_and_ledger():
    df = pd.DataFrame({"API": ["1", "2", "3"], "status": ["orphan_confirmed", "weird", None],
                       "lon": [-94.0, -95.0, 0.0], "lat": [32.0, 31.0, 0.0]})
    g = rrc.normalise_rrc(df, {"well_id": "API", "status_raw": "status", "lat": "lat", "lon": "lon"})
    assert list(g.status_norm) == ["orphan", "unmapped", "missing"]
    assert g.coord_ok.tolist() == [True, True, False]
    with pytest.raises(gt.MissingInputError):
        rrc.normalise_rrc(df.drop(columns=["lat"]), {"well_id": "API", "lat": "lat", "lon": "lon"})
    calls = []

    def fake(url, params):
        calls.append(params)
        if params.get("returnCountOnly"):
            return {"count": 5}
        off = params["resultOffset"]
        if off == 2:
            raise IOError("boom")
        n = min(2, 5 - off)
        return {"features": [{"attributes": {"OBJECTID": off + i}, "geometry": {"x": 1, "y": 2}} for i in range(n)]}
    out, led = gt.arcgis_paged_query("u", page=2, fetch=fake, max_tries=1)
    assert not led["complete"] and led["failed_offsets"] == [2] and led["retrieved"] == 3


def test_window_rule_and_agreement():
    counts = pd.DataFrame({"county": ["A", "B", "C"], "per_km2": [0.1, 0.3, 0.2], "orphans": [1, 3, 2]})
    listing = pd.DataFrame({"county": ["A", "B", "C"], "project": ["p", "q", "r"], "ql": ["QL2", "QL3", "QL1"],
                            "flight_year": [2019, 2020, 2016], "eligible_km2": [20, 20, 30]})
    r = wc.rank_counties(counts, listing)
    assert r.iloc[0]["county"] == "C" and not r.set_index("county").loc["B", "passes_gate"]
    assert not wc.rank_counties(counts, None)["passes_gate"].any()
    import geopandas as gpd
    from shapely.geometry import box
    a = gpd.GeoDataFrame({"class": ["E1", "E2"]}, geometry=[box(0, 0, 10, 10), box(20, 20, 30, 30)], crs=CRS)
    b = gpd.GeoDataFrame({"class": ["E1", "E1"]}, geometry=[box(1, 1, 10, 10), box(50, 50, 60, 60)], crs=CRS)
    f = gt.polygon_f1(a, b)
    assert f["matched"] == 1 and np.isclose(f["f1"], 0.5)
    assert np.isclose(gt.cohen_kappa(["a", "b", "a"], ["a", "b", "a"]), 1.0)
    assert gt.utm_epsg_nad83_2011(-93.96) == 6344 and gt.utm_epsg_nad83_2011(-102.84) == 6342


def test_sampler_excludes_forbidden():
    g = gt.make_blocks((0, 0, 1500, 375), CRS)
    tr, forb = g.iloc[[0]], g.iloc[[2, 3]].geometry.union_all()
    w = gt.sample_windows(tr, forb, 128.0, 30, seed=0)
    from shapely.geometry import box
    assert len(w) == 30 and not any(box(*bx).intersects(forb) for bx in w)
    with pytest.raises(RuntimeError):
        gt.sample_windows(g.iloc[[1]], g.geometry.union_all(), 128.0, 5, seed=0, max_tries=2)


def test_score_raster_end_to_end(tmp_path):
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    prob = np.zeros((1500, 1500), np.float32)
    prob[100:120, 100:120] = 0.9
    prob[900:910, 900:910] = 0.5
    p = tmp_path / "prob.tif"
    with rasterio.open(p, "w", driver="GTiff", width=1500, height=1500, count=1, dtype="float32",
                       crs=CRS, transform=from_origin(0, 750, 0.5, 0.5), nodata=-1) as d:
        d.write(prob, 1)
    blocks = gt.make_blocks((0, 0, 750, 750), CRS)
    blocks["eligible"] = True
    truth = gpd.GeoDataFrame({"truth_id": [1, 2]}, geometry=[box(50, 690, 60, 700), box(600, 100, 610, 110)], crs=CRS)
    tabs, cands = gt.score_raster(p, truth, blocks)
    assert len(tabs) == 4 and sum(t["n_truth"] for t in tabs.values()) == 2
    assert np.isclose(gt.pooled_recall_at_k(tabs, list(tabs)), 0.5)


def test_wetland_strata():
    g = gt.make_blocks((0, 0, 750, 750), CRS)
    dens = pd.DataFrame({"block_id": g.block_id, "void_frac_05": [0.1, 0.5, 0.8, 0.95], "ground_ppm2": 2.0})
    cfg = {"prereg": {"wet_cuts": [0.1, 0.5], "void_cuts": [0.45, 0.7], "void_cap": 0.9}}
    out = ws.build_strata(g, dens, np.array([0.0, 0.2, 0.7, 0.0]), np.array([0, 0, 0.6, 0]), cfg)
    assert out.wet_stratum.tolist() == ["dry", "mixed", "wet", "dry"]
    assert out.void_stratum.tolist() == ["low", "mid", "high", "high"]
    assert out.eligible.tolist() == [True, True, False, False]


def test_config_and_missing_input_message():
    cfg = gt.load_config("3.4")
    assert cfg["prereg"]["k_per_km2"] == 40
    for area, ac in cfg["areas"].items():
        if ac["centre_lonlat"]:
            assert gt.utm_epsg_nad83_2011(ac["centre_lonlat"][0]) == int(ac["crs"].split(":")[1]), area
    with pytest.raises(gt.MissingInputError, match="assumed schema"):
        gt.require_input(Path("nope_does_not_exist.csv"), "thing", {"a": "int"})
    with pytest.raises(gt.DecisionMissingError):
        gt.need_decision(cfg, "margin")
