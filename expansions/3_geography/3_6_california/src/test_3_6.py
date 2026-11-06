"""Smoke tests for 3.6 California. Tiny synthetic data, no GPU, no network.

Run: python -m pytest -q expansions/3_geography/3_6_california/src/test_3_6.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402
import _ca_equipment_rule as er  # noqa: E402
import _ca_field_area_scores as fa  # noqa: E402
import _ca_label_packs as lp  # noqa: E402
import _ca_status_by_pad as sp  # noqa: E402
import _ca_unmatched_sample as us  # noqa: E402

CRS = "EPSG:6340"


def test_config_paths_and_crs():
    cfg = gt.load_config("3.6")
    p = gt.resolve(cfg["inputs"]["ndsm"]["path"], "3.6", area="ca1")
    assert p.name == "ndsm_ca1_05.tif" and "ca1" in p.parts
    assert gt.utm_epsg_nad83_2011(cfg["areas"]["ca_la"]["centre_lonlat"][0]) == 6340
    assert cfg["primary_classes"] == ["E1", "E2"]


def test_field_scores():
    df = pd.DataFrame({"field": ["a", "b", "c"], "ground_ppm2": [5, 1, 4], "date_gap_months": [3, 2, 30],
                       "developed_share": [0.1, 0.1, 0.1], "veg_cover": [0.2, 0.1, 0.1],
                       "pad_density_per_km2": [10, 50, 30], "naip_year": [2022, 2022, 2020]})
    s = fa.score_fields(df, {"min_ground_ppm2": 2.0, "max_date_gap_months": 12, "developed_cap": 0.3})
    assert s.iloc[0]["field"] == "a" and s.set_index("field").loc["b", "passes"] == False  # noqa: E712


def test_label_pack_blindness():
    d = lp.double_label_draw([f"b{i}" for i in range(10)], 0.2, 1)
    assert len(d) == 2 and d == lp.double_label_draw([f"b{i}" for i in range(10)], 0.2, 1)
    lp.assert_blind(["block_id", "naip_png", "hillshade_png", "ndsm_png", "double_label"])
    with pytest.raises(AssertionError):
        lp.assert_blind(["block_id", "WellStatus"])


def test_unmatched_draw_and_summary():
    c = pd.DataFrame({"blob_id": range(10), "score": np.linspace(1, 0.1, 10), "area_m2": 5.0,
                      "truth_id": [1, None, 2, None, None, None, None, None, None, None],
                      "row": 0, "col": 0, "block_id": "b"})
    sheet, info = us.draw_unmatched(c, eligible_km2=0.15, n=3, seed=0)
    assert info["k"] == 6 and info["top_k_unmatched"] == 4 and len(sheet) == 3
    lab = pd.DataFrame({"label_a": ["missed_pad", "natural", "natural", "other"],
                        "label_b": ["missed_pad", "natural", "other", "other"]})
    s = us.summarise(lab)
    assert s["n_agreed"] == 3 and np.isclose(s["shares"]["missed_pad"]["p"], 1 / 3)
    with pytest.raises(ValueError):
        us.summarise(pd.DataFrame({"label_a": ["pumpjack"], "label_b": ["other"]}))


def test_status_join():
    import geopandas as gpd
    from shapely.geometry import Point, box
    pads = gpd.GeoDataFrame({"truth_id": [1, 2, 3], "class": ["E1", "E2", "E1"]},
                            geometry=[box(0, 0, 50, 50), box(70, 0, 120, 50), box(500, 500, 550, 550)], crs=CRS)
    wells = gpd.GeoDataFrame({"status_norm": ["idle", "plugged", "active", "orphan"]},
                             geometry=[Point(10, 10), Point(55, 10), Point(300, 300), Point(20, 20)], crs=CRS)
    j = sp.join_wells_to_pads(wells, pads, 25)
    assert j["truth_id"].tolist()[:2] == [1, 1] and pd.isna(j["truth_id"].iloc[2])
    st, per, counts = sp.status_tables(j, pads)
    assert counts == {"wells_total": 4, "wells_no_pad": 1, "pads_no_well": 2, "idle_or_orphan_on_equipped": 2}


def test_equipment_rule():
    nd = np.zeros((100, 100), np.float32)
    nd[10:14, 10:14] = 3.0           # 4 m2 object at 0.5 m
    nd[50:52, 50:52] = 30.0          # too tall
    lab = er.equipment_objects(nd, 0.5)
    assert set(np.unique(lab)) == {0, 1}
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.geometry import box
    tf = from_origin(0, 50, 0.5, 0.5)
    pads = gpd.GeoDataFrame({"truth_id": [1, 2]}, geometry=[box(0, 40, 4, 44), box(30, 0, 40, 10)], crs=CRS)
    assert er.rule_flags(lab, tf, pads, 10).tolist() == [True, False]
    cands = pd.DataFrame({"blob_id": [1, 2], "score": [0.9, 0.2], "area_m2": [5, 5], "truth_id": [2, None]})
    assert er.model_found(cands, 0.03) == {2}
    p = pd.DataFrame({"block_id": ["a", "a", "b", "b"], "model": [True, False, False, False],
                      "union": [True, True, True, False]})
    g = er.paired_union_gain(p, B=200, seed=0)
    assert np.isclose(g["union_minus_model"], 0.5) and g["ci95"][0] <= 0.5 <= g["ci95"][1]
