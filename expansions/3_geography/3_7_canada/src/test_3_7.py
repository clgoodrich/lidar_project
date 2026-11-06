"""Smoke tests for 3.7 Canada. Tiny synthetic data, no GPU, no network.

Run: python -m pytest -q expansions/3_geography/3_7_canada/src/test_3_7.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402
import _can_inventory_rows as inv  # noqa: E402
import _can_record_assoc as ra  # noqa: E402
import _can_tile_probe as tp  # noqa: E402
import _can_window_rank as wr  # noqa: E402

CRS = "EPSG:2956"


def test_ladder_levels():
    cfg = gt.load_config("3.7")
    df = pd.DataFrame({"UWI": ["a", "b", "c"], "Status": ["x", "y", "z"], "SurfLat": [53.0, 53.1, 53.2],
                       "SurfLon": [-110.0, -110.1, -110.2], "CoordSource": ["GPS survey", "LSD converted", None]})
    g = gt.normalise_registry(df, cfg["provinces"]["ab"]["wells"]["colmap"], "ab_wells")
    lad = inv.ladder(g, cfg["coord_method_map"], cfg["prereg"]["lsd_uncertainty_m"])
    assert lad["coord_class"].tolist() == ["surveyed", "lsd_legal_subdivision", "unknown"]
    assert lad["v_level"].tolist() == ["V1", "V1", "V0"]
    assert lad["uncertainty_m"].tolist()[1] == 200
    assert gt.utm_epsg_csrs(-110.0) == 2956 and gt.utm_epsg_csrs(-82.2) == 2958


def test_province_rank():
    df = pd.DataFrame({"province": ["ab", "bc", "on"], "licence_ok": [True, True, False], "ground_ppm2": [3, 1, 9],
                       "coord_method_documented": [True, True, True], "reviewer_committed": [True, True, True],
                       "blocks_expected": [40, 40, 40], "slope_sim": [0.2, 0.9, 0.9], "canopy_sim": [0.1, 0.9, 0.9],
                       "window_lon": [-110, -121, -82], "window_lat": [53, 56, 42.9]})
    r = wr.rank_provinces(df, 2.0, 15)
    assert r.iloc[0]["province"] == "ab" and r.iloc[0]["status"] == "run"
    assert "g2_density" in r.set_index("province").loc["bc", "status"]
    assert "g1_licence" in r.set_index("province").loc["on", "status"]


def test_tile_probe(tmp_path):
    import laspy
    from pyproj import CRS as PCRS
    h = laspy.LasHeader(point_format=3, version="1.4")
    h.offsets, h.scales = [500000, 6000000, 0], [0.01, 0.01, 0.01]
    h.add_crs(PCRS.from_epsg(2956))
    n = 4000
    rng = np.random.default_rng(0)
    las = laspy.LasData(h)
    las.x = 500000 + rng.uniform(0, 750, n)
    las.y = 6000000 + rng.uniform(0, 375, n)
    las.z = rng.uniform(600, 610, n)
    las.classification = np.where(np.arange(n) % 2 == 0, 2, 1).astype(np.uint8)
    las.gps_time = rng.uniform(3.0e8, 3.0e8 + 86400, n)
    p = tmp_path / "t.laz" if laspy.LazBackend.detect_available() else tmp_path / "t.las"
    las.write(p)
    rec, crs = tp.probe(p)
    assert rec["points"] == n and rec["class_2"] == n // 2 and crs is not None
    assert rec["las_version"] == "1.4"
    blocks = gt.make_blocks((500000, 6000000, 500750, 6000375), crs.to_string())
    bd = gt.las_block_density([p], blocks)
    assert len(bd) == 2 and bd["ground_ppm2"].sum() > 0 and (bd["void_frac_05"] > 0.9).all()
    d0, d1 = tp.gps_dates(np.array([3.0e8]), adjusted=True)
    assert d0.startswith("2021")


def test_shifted_null_and_excess():
    from shapely.geometry import box
    fp = box(0, 0, 10000, 10000)
    rng = np.random.default_rng(1)
    fx, fy = rng.uniform(2000, 8000, 50), rng.uniform(2000, 8000, 50)
    px, py = fx[:20] + 5, fy[:20] + 5                     # records sit on features
    rad = np.full(20, 50.0)
    obs = float(np.mean(ra.nearest_dist(px, py, fx, fy) <= rad))
    null, rej = ra.shifted_null(px, py, rad, fx, fy, fp, 200, 300, 2000, seed=0)
    assert obs == 1.0 and len(null) == 200
    e = ra.excess(obs, null)
    assert e["normalised_excess"] > 0.8 and e["p_upper"] < 0.05


def test_shifted_null_at_100_spread_records():
    """G-09. 100 records spread over the whole 10 km footprint, 50 of them on features. The old rule
    rejected every shift (some record always left the box) and gave 0 of 999 kept, excess NaN.
    The torus shift keeps all 999. Records on features give obs 0.5 and a null near 50 * pi * 50^2 / 1e8."""
    from shapely.geometry import box
    cfg = gt.load_config("3.7")["prereg"]
    fp = box(0, 0, 10000, 10000)
    rng = np.random.default_rng(3)
    px, py = rng.uniform(0, 10000, 100), rng.uniform(0, 10000, 100)
    fx, fy = px[:50] + 5, py[:50] + 5
    rad = np.full(100, 50.0)
    obs = float(np.mean(ra.nearest_dist(px, py, fx, fy) <= rad))
    null, rej = ra.shifted_null(px, py, rad, fx, fy, fp, cfg["n_shifts"], cfg["shift_min_m"], cfg["shift_max_m"], 0)
    assert obs == 0.5 and len(null) == 999 and rej == 0
    e = ra.excess(obs, null, cfg["n_shifts"])
    assert e["status"] == "computed" and e["null_mean"] < 0.05 and e["normalised_excess"] > 0.45


def test_shifted_null_not_computable_is_explicit():
    """Two far-apart squares. A 300 to 2000 m shift always leaves them, so no shift is kept.
    The result says not computable and every number is NaN."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    fp = unary_union([box(0, 0, 1000, 1000), box(9000, 9000, 10000, 10000)])
    rng = np.random.default_rng(4)
    px = np.r_[rng.uniform(0, 1000, 50), rng.uniform(9000, 10000, 50)]
    py = np.r_[rng.uniform(0, 1000, 50), rng.uniform(9000, 10000, 50)]
    null, rej = ra.shifted_null(px, py, np.full(100, 50.0), px, py, fp, 50, 300, 2000, 0, max_tries=4)
    e = ra.excess(1.0, null, 50)
    assert len(null) < 50 and e["status"].startswith("not computable") and np.isnan(e["normalised_excess"])
