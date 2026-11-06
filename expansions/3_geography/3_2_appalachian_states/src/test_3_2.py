"""Smoke tests for 3.2 on tiny synthetic data (seconds, no GPU, no network).

Run
    python -m pytest -q expansions/3_geography/3_2_appalachian_states/src/test_3_2.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "3_1_warren_forest_mckean" / "src"))

import _appal_wells_loaders as wl  # noqa: E402
import _appal_wells_harmonise as wh  # noqa: E402
import _appal_window_cover_union as wc  # noqa: E402
import _appal_state_table as stt  # noqa: E402
import _appal_thin_density_arm as th  # noqa: E402
import _appal_adapt_finetune as ad  # noqa: E402
import _geo_xfer_lib as xl  # noqa: E402

ek = xl.ek
CFG = xl.load_config(HERE.parent / "config_3_2.json")


def test_status_rules_and_precision():
    W = CFG["wells"]
    s = pd.Series(["PA", "AC", "UL", "Plugged and Abandoned", "Orphan Well - Ready", "Active Well", "D&A",
                   "Temporary Inactive  Status 4th Year", "Not Drilled", None])
    got = wl.map_status(s, W["status_rules"]).tolist()
    assert got == ["plugged", "active", "orphan", "plugged", "orphan", "active", "abandoned", "abandoned", "other", "other"]
    assert wl.decimals(pd.Series(["42.19713", "-78.1", "x"])).tolist()[:2] == [5.0, 1.0]


def test_normalise_keeps_rows_dates_and_sentinels():
    W = CFG["wells"]
    raw = pd.DataFrame({"id": ["1", "2", "3"], "la": ["41.123456", "41.1", ""], "lo": ["-79.123456", "-79.2", ""],
                        "st": ["AC", "PA", "UN"], "sp": ["1800-01-01", "1925-06-01", "1990-01-01"],
                        "pl": [None, "1950-01-01", None], "x": ["1", "500000.0", "2"], "y": ["1", "4000000.0", "2"]})
    src = {"state": "Test", "id": "id", "lat": "la", "lon": "lo", "status": "st", "date_spud": "sp", "date_plug": "pl",
           "datum": "NAD83", "sentinel_xy": [500000.0, 4000000.0], "sentinel_cols": ["x", "y"]}
    out = wl.normalise("syn", src, raw, W)
    assert len(out) == 3 and list(out.columns) == wl.SCHEMA
    assert out.date_unknown_sentinel.tolist() == [True, False, False]
    assert out.early_dated.tolist() == [False, True, False]
    assert out.status_h.tolist() == ["active", "plugged", "orphan"]
    assert out.has_coords.tolist() == [True, False, False]          # row 2 is the WV sentinel location
    assert out.low_precision.tolist() == [False, True, True]


def test_geod_shift_and_window_tags():
    d = wl.geod_shift_m(np.array([37.0]), np.array([-85.0]), np.array([37.0001]), np.array([-85.0]))
    assert d[0] == pytest.approx(11.1, abs=0.2)
    wins = pd.DataFrame({"window": ["A", "B"], "minx": [-80, -79], "maxx": [-79.5, -78], "miny": [40, 40], "maxy": [41, 41]})
    df = pd.DataFrame({"lon": [-79.7, -78.5, -70.0], "lat": [40.5, 40.5, 40.5]})
    t = wh.tag_windows(df, wins, {"a": "A", "b": "B"})
    assert t.tolist()[:2] == ["a", "b"] and pd.isna(t.iloc[2])


def test_query_audit_and_union_cover():
    log = pd.DataFrame({"window": list("abcd"), "status": ["ok", "ok", "error", "ok"], "reported_total": [5, 0, 3, 10],
                        "retrieved": [5, 0, 0, 7]})
    assert wc.query_audit(log).outcome.tolist() == ["ok_complete", "successful_empty", "failed", "incomplete"]
    win = pd.Series({"minx": -80.0, "miny": 40.0, "maxx": -79.98, "maxy": 40.02})
    tiles = pd.DataFrame({"bb_minx": [-80.0], "bb_miny": [40.0], "bb_maxx": [-79.99], "bb_maxy": [40.02]})
    cov, km2, n = wc.window_cover(win, tiles, "EPSG:4269")
    assert cov == pytest.approx(0.5, abs=0.02) and n == 1 and km2 > 3


def test_state_table_row_and_paired_eval():
    area = {"state": "S", "window": "W", "role": "primary", "program": "P"}
    score = {"primary": {"recall": 0.8, "hits": 8, "n_truth": 10, "n_blocks": 20, "truth_density_per_km2": 3.0,
                         "diff": -0.1, "lo": -0.3, "hi": 0.1, "decision": "inconclusive"}, "stamp": None}
    cover = pd.DataFrame({"tag": ["t"], "configured": [True], "cover": [0.97]})
    r = stt.window_row("t", area, score, cover, pd.DataFrame())
    assert r["status"] == "scored" and r["union_cover"] == 0.97 and r["stamp"] == "preregistered"
    z = [(5, 10)] * 20
    a = [(7, 10)] * 20
    res = ad.paired_eval(z, a, B=100, seed=0)
    assert res["adapted_minus_zero_shot"] == pytest.approx(0.2) and res["lo"] == pytest.approx(0.2)


def test_thin_file_keeps_fraction(tmp_path):
    import laspy
    hdr = laspy.LasHeader(point_format=6, version="1.4")
    hdr.scales = [0.01] * 3
    las = laspy.LasData(hdr)
    n = 20000
    las.x = np.random.default_rng(0).uniform(0, 10, n)
    las.y = np.random.default_rng(1).uniform(0, 10, n)
    las.z = np.zeros(n)
    las.classification = np.full(n, 2, np.uint8)
    src, dst = tmp_path / "a.las", tmp_path / "b.las"
    las.write(str(src))
    n_in, n_out = th.thin_file(src, dst, 0.25, seed=3)
    assert n_in == n and abs(n_out / n - 0.25) < 0.02
    assert laspy.read(str(dst)).header.point_count == n_out


def test_labels_and_norm(tmp_path):
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    tf = from_origin(0, 20, 0.5, 0.5)
    f = tmp_path / "f.tif"
    with rasterio.open(f, "w", driver="GTiff", width=40, height=40, count=2, dtype="float32", crs=ek.DST_CRS,
                       transform=tf) as d:
        d.write(np.stack([np.ones((40, 40)), np.arange(1600).reshape(40, 40)]).astype("float32"))
    floors = gpd.GeoDataFrame(geometry=[box(5, 5, 7, 7)], crs=ek.DST_CRS)
    rims = gpd.GeoDataFrame(geometry=[box(4, 4, 8, 8)], crs=ek.DST_CRS)
    lab = ad.rasterize_pit_labels(floors, rims, f, tmp_path / "l.tif")
    a = rasterio.open(lab).read(1)
    assert (a == 1).sum() == 16 and (a == 2).sum() == 64 - 16
    mu, sd = ad.fit_norm(f, gpd.GeoDataFrame(geometry=[box(0, 0, 20, 20)], crs=ek.DST_CRS), max_px=10_000)
    assert mu[0] == pytest.approx(1.0) and sd[1] > 100


def test_config_shapes_match_31():
    for k in ("areas", "outputs", "assumed", "reference", "eligibility", "roles", "models", "builders", "projected_width"):
        assert k in CFG
    for t, a in CFG["areas"].items():
        assert {"window", "role", "pair", "tiles"} <= set(a), t
        assert CFG["areas"][a["pair"]]["pair"] == t
