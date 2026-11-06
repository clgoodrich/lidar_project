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
import _ca_pad_recall_by_class as pr  # noqa: E402
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
    from rasterio.transform import from_origin
    tf = from_origin(0, 50, 0.5, 0.5)
    # object 1 covers rows 10-13, cols 10-13 (x 5-7, y 43-45). The candidate at (6, 40) sits in row 20, col 12.
    # Cell-centre distance to the object is 7 rows x 0.5 m = 3.5 m. Radius sqrt(pi / pi) = 1 plus buffer 3 = 4 m,
    # so it is flagged. With buffer 2 (3 m) it is not. The candidate at (30, 10) is far from any object.
    c = pd.DataFrame({"blob_id": [1, 2], "score": [0.9, 0.2], "area_m2": [np.pi, np.pi], "x": [6.0, 30.0],
                      "y": [40.0, 10.0], "truth_id": [None, 2]})
    assert er.candidate_flags(c, lab, tf, 3.0).tolist() == [True, False]
    assert er.candidate_flags(c, lab, tf, 2.0).tolist() == [False, False]
    assert er.model_found(c, 0.03) == set() and er.model_found(c, 0.05) == {2}    # K = 1, then K = 2


def test_equipment_union_can_lose_at_equal_k():
    """G-10. Hand case. Pads 1 and 2 are matched by A (0.9) and B (0.8). C (0.5) and D (0.4) are false
    candidates next to equipment. K = 2. Model keeps A, B (recall 1). Union puts flagged C, D first and keeps
    them (recall 0). Rule keeps C, D (recall 0). The old rule took model OR rule on truth pads and could not lose."""
    c = pd.DataFrame({"blob_id": [1, 2, 3, 4], "score": [0.9, 0.8, 0.5, 0.4], "area_m2": 5.0,
                      "truth_id": [1, 2, None, None]})
    f = er.found_at_equal_k(c, np.array([False, False, True, True]), k=2)
    assert f["model"] == {1, 2} and f["union"] == set() and f["rule"] == set()
    pads = pd.DataFrame({"block_id": ["a", "b"], "truth_id": [1, 2]})
    for col in ("model", "union"):
        pads[col] = pads["truth_id"].isin(f[col])
    g = er.paired_union_gain(pads, B=200, seed=0)
    assert g["union_minus_model"] == -1.0
    # a flagged true hit beyond K is pulled in: model keeps A, B. Union keeps flagged E (pad 3) then A
    c2 = pd.concat([c.iloc[:2], pd.DataFrame({"blob_id": [5], "score": [0.3], "area_m2": [5.0], "truth_id": [3]})])
    f2 = er.found_at_equal_k(c2, np.array([False, False, True]), k=2)
    assert f2["model"] == {1, 2} and f2["union"] == {3, 1}


def test_pad_scoring_uses_pad_policy():
    """3.6 pad scoring stamps the pad policy (cutoff 0.525). A 0.5 blob is not a pad candidate."""
    import geopandas as gpd
    import rasterio
    import tempfile
    from rasterio.transform import from_origin
    from shapely.geometry import box
    d = Path(tempfile.mkdtemp())
    prob = np.zeros((200, 200), np.float32)        # 1 m cells, one 200 m block, 0.04 km2, K = round(1.6) = 2
    prob[10:30, 10:30] = 0.5
    prob[100:130, 100:130] = 0.6
    with rasterio.open(d / "p.tif", "w", driver="GTiff", width=200, height=200, count=1, dtype="float32",
                       crs=CRS, transform=from_origin(0, 200, 1, 1), nodata=-1) as w:
        w.write(prob, 1)
    blocks = gt.make_blocks((0, 0, 200, 200), CRS, size=200).assign(eligible=True)
    truth = gpd.GeoDataFrame({"truth_id": [0, 1], "class": ["E1", "E2"]},
                             geometry=[box(10, 170, 30, 190), box(100, 70, 130, 100)], crs=CRS)
    rows, tabs_by = pr.class_rows(d / "p.tif", truth, blocks, {"primary": ["E1", "E2"]})
    assert tabs_by["_policy"] == gt.ek.policy_for("pad") and tabs_by["_policy"]["cutoff"] == 0.525
    assert rows[0]["n_truth"] == 2 and np.isclose(rows[0]["recall_k40"], 0.5)   # only the 0.6 blob is a candidate
