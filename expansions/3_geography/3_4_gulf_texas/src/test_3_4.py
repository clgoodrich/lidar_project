"""Tests for 3.4 and the shared core _geo_transfer_core.py. Tiny synthetic data, no GPU, no network.

Expected values in the scorer tests are worked out by hand in the comments, never read back from the scorer.
The parity test feeds one fixture to the 3.0 reference scorer (imported read-only) and to gt.score_raster.

Run: python -m pytest -q -p no:cacheprovider expansions/3_geography/3_4_gulf_texas/src/test_3_4.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _geo_transfer_core as gt  # noqa: E402
import _gulf_relief_norm_channels as rn  # noqa: E402
import _gulf_rrc_orphans_tx as rrc  # noqa: E402
import _gulf_window_choice_tx as wc  # noqa: E402
import _gulf_wetland_strata as ws  # noqa: E402

CRS = "EPSG:6344"
ek = gt.ek


def _tables(n_blocks, hit_rate, seed=0, n_truth=4, n_cand=60):
    """Synthetic block tables. Each block has n_truth features. hit_rate of them get a high-scoring match."""
    rng = np.random.default_rng(seed)
    tabs = {}
    for b in range(n_blocks):
        rows = []
        for t in range(n_truth):
            s = rng.uniform(0.6, 0.9) if rng.random() < hit_rate else rng.uniform(0.0, 0.05)
            rows.append({"blob_id": b * 1000 + t, "score": s, "area_m2": 20.0, "truth_id": f"{b}_{t}"})
        for c in range(n_cand):
            rows.append({"blob_id": b * 1000 + 100 + c, "score": rng.uniform(0.1, 0.5), "area_m2": 10.0,
                         "truth_id": None})
        tabs[f"b{b}"] = {"c": pd.DataFrame(rows), "n_truth": n_truth, "km2": 0.140625,
                         "truth_ids": [f"{b}_{t}" for t in range(n_truth)]}
    return tabs


# ----------------------------------------------------------------------------- raster fixture helpers
X0, Y0 = 500000.0, 4500200.0       # EPSG:6346 origin of the 1 m parity fixture (200 x 200 cells)


def _px(r0, r1, c0, c1, x0=X0, y0=Y0, cell=1.0):
    """Box covering pixel rows r0..r1-1 and cols c0..c1-1."""
    from shapely.geometry import box
    return box(x0 + c0 * cell, y0 - r1 * cell, x0 + c1 * cell, y0 - r0 * cell)


def _write(path, arr, crs, transform, nodata=-1.0, dtype="float32"):
    import rasterio
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1, dtype=dtype,
                       crs=crs, transform=transform, nodata=nodata) as d:
        d.write(arr.astype(dtype), 1)
    return path


def _parity_fixture(tmp_path):
    """2 x 2 blocks of 100 m on a 1 m grid. Block 3 (bottom right) is all nodata.

    truth 0  ten pixels in block 0, two rectangles touching at one corner. 4-connected extraction gives
             cand1 (4 px, p 0.9, IoU 0.4) and cand2 (6 px, p 0.6, IoU 0.6). Score order matches cand1,
             IoU order matches cand2. The other one is a second piece and is deduplicated.
    D        3 x 3 px distractor in block 0, p 0.8, no truth.
    truth 1  block 1, no candidate (a miss).
    truth 3  block 2, exact 6 x 6 candidate, p 0.5.
    truth 2  inside the nodata block. Never in the denominator.
    Eligible area 3 x 0.01 km2. At K = 40 per km2, K = round(1.2) = 1.
    """
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.ops import unary_union
    prob = np.zeros((200, 200), np.float32)
    prob[10:12, 10:12] = 0.9
    prob[12:14, 12:15] = 0.6
    prob[50:53, 50:53] = 0.8
    prob[150:156, 30:36] = 0.5
    prob[100:200, 100:200] = -1.0
    tf = from_origin(X0, Y0, 1.0, 1.0)
    p = _write(tmp_path / "prob.tif", prob, "EPSG:6346", tf)
    blocks = gpd.GeoDataFrame({"block_id": [0, 1, 2, 3]},
                              geometry=[_px(0, 100, 0, 100), _px(0, 100, 100, 200), _px(100, 200, 0, 100),
                                        _px(100, 200, 100, 200)], crs="EPSG:6346")
    bp = tmp_path / "blocks.gpkg"
    blocks.to_file(bp, layer="blocks", driver="GPKG")
    truth = gpd.GeoDataFrame({"tid": [0, 1, 2, 3]},
                             geometry=[unary_union([_px(10, 12, 10, 12), _px(12, 14, 12, 15)]), _px(30, 35, 130, 135),
                                       _px(150, 155, 150, 155), _px(150, 156, 30, 36)], crs="EPSG:6346")
    tp = tmp_path / "truth.gpkg"
    truth.to_file(tp, layer="feat", driver="GPKG")
    return p, bp, tp, blocks, truth


def _gt_inputs(blocks, truth):
    b = blocks.copy()
    b["eligible"] = True
    b["area_km2"] = b.geometry.area / 1e6
    t = truth.rename(columns={"tid": "truth_id"})
    return b, t


# ----------------------------------------------------------------------------- policy, candidates, matching
def test_score_raster_requires_task_and_uses_policy(tmp_path):
    p, bp, tp, blocks, truth = _parity_fixture(tmp_path)
    b, t = _gt_inputs(blocks, truth)
    with pytest.raises(ValueError, match="needs a task"):
        gt.score_raster(p, t, b)
    tabs, c = gt.score_raster(p, t, b, task="pit")
    assert c.attrs["policy"] == ek.policy_for("pit")            # stamped, cutoff 0.35, score order
    assert c.attrs["policy"]["cutoff"] == 0.35
    assert all(v["policy_hash"] == ek.policy_for("pit")["policy_hash"] for v in tabs.values())
    # a 0.20 blob is a candidate under the 0.10 sensitivity cutoff only
    prob = np.zeros((40, 40), np.float32)
    prob[5:10, 5:10] = 0.2
    _, c1 = gt.extract_candidates(prob, cell_area_m2=0.25, cutoff=ek.policy_for("pit")["cutoff"], min_m2=4.0)
    _, c2 = gt.extract_candidates(prob, cell_area_m2=0.25, cutoff=ek.policy_for("pit", "sensitivity")["cutoff"],
                                  min_m2=4.0)
    assert len(c1) == 0 and len(c2) == 1


def test_candidates_and_match():
    p = np.zeros((40, 40))
    p[5:10, 5:10] = 0.8          # 25 px = 6.25 m2, kept
    p[30, 30] = 0.9              # 0.25 m2, dropped
    p[0, 0] = np.nan
    lab, c = gt.extract_candidates(p, cell_area_m2=0.25, cutoff=0.35, min_m2=4.0)
    assert len(c) == 1 and abs(c.score[0] - 0.8) < 1e-9 and np.isclose(c.area_m2[0], 6.25)
    t = np.zeros((40, 40), int)
    t[5:11, 5:11] = 7
    assert gt.greedy_match(lab, t, {1: 0.8}, iou=0.3, order="score") == {1: 7}
    t2 = np.zeros((40, 40), int)
    t2[0:40, 0:40] = 3           # IoU far below 0.3
    assert gt.greedy_match(lab, t2, {1: 0.8}, iou=0.3, order="score") == {}


def test_match_order_score_versus_iou():
    """Ten-pixel truth. Candidate 1 has 4 px at score 0.9 (IoU 0.4), candidate 2 has 6 px at 0.6 (IoU 0.6)."""
    cl = np.zeros((4, 5), int)
    cl[0:2, 0:2] = 1
    cl[2:4, 2:5] = 2
    tl = np.where(cl > 0, 5, 0)
    s = {1: 0.9, 2: 0.6}
    assert gt.greedy_match(cl, tl, s, iou=0.3, order="score") == {1: 5}
    assert gt.greedy_match(cl, tl, s, iou=0.3, order="iou") == {2: 5}


# ----------------------------------------------------------------------------- parity with the 3.0 reference
def _ref_score(p, bp, tp, mode, k, dedupe="none"):
    sys.path.insert(0, str(HERE.parents[1] / "3_0_transfer_protocol" / "src"))
    import _transfer_score_lib as tl
    kw = {"truth_id": "tid", "B": 20, "seed": 0, "calib_pixels": 1000, "k_curve": (), "dedupe": dedupe}
    sig = inspect.signature(tl.score).parameters
    pol = ek.policy_for("pit", mode)
    if "task" in sig:
        kw.update(task="pit", mode=mode)
    else:                                                          # older 3.0 scorer, explicit settings
        kw.update(cutoff=pol["cutoff"], min_area=pol["min_area_m2"], iou=pol["iou"], order=pol["match_order"])
    return tl.score(p, bp, f"{tp}:feat", k, **kw)


@pytest.mark.parametrize("mode,dedupe,expect_k40,expect_k100", [
    ("primary", "none", 1 / 3, 1 / 3), ("sensitivity", "none", 0.0, 1 / 3),
    ("primary", "truth_matched", 1 / 3, 2 / 3), ("sensitivity", "truth_matched", 0.0, 2 / 3)])
def test_parity_with_3_0_reference_scorer(tmp_path, mode, dedupe, expect_k40, expect_k100):
    """Same raster and truth through 3.0 `score` and gt.score_raster. Identical candidates, matches, recall.

    Hand values without dedupe. Ranking is cand1 0.9, D 0.8, cand2 0.6, c3 0.5.
    Primary (score order) matches cand1 to truth 0. K = 1 keeps cand1. Recall 1 / 3. K = 3 also 1 / 3.
    Sensitivity (IoU order) matches cand2. K = 1 keeps cand1, now unmatched. Recall 0. K = 3 keeps cand2. 1 / 3.
    With dedupe the other piece of truth 0 leaves the ranking, so K = 3 reaches c3 as well. Recall 2 / 3.
    """
    p, bp, tp, blocks, truth = _parity_fixture(tmp_path)
    b, t = _gt_inputs(blocks, truth)
    tabs, c = gt.score_raster(p, t, b, task="pit", mode=mode, dedupe=dedupe)
    for k, expect in ((40.0, expect_k40), (100.0, expect_k100)):
        ref = _ref_score(p, bp, tp, mode, k, dedupe)
        rc = ref["candidates"]
        mine = c[~c["duplicate"]]
        key = lambda df, col: sorted(zip(df["area_m2"].round(6), df["score"].round(6),  # noqa: E731
                                         [None if pd.isna(v) else int(v) for v in df[col]]))
        assert key(mine, "truth_id") == key(rc, "matched")          # same candidates, scores, areas, matches
        assert int(c["duplicate"].sum()) == ref["summary"]["n_duplicates_dropped"]
        assert sum(v["n_truth"] for v in tabs.values()) == ref["summary"]["n_truth"] == 3
        r_gt = gt.pooled_recall_at_k(tabs, list(tabs), k)
        assert np.isclose(r_gt, ref["summary"]["primary"]["recall"]) and np.isclose(r_gt, expect)
        assert np.isclose(sum(v["km2"] for v in tabs.values()), ref["summary"]["eligible_area_km2"])


@pytest.mark.parametrize("mode", ["primary", "sensitivity"])
def test_dedupe_second_piece(tmp_path, mode):
    """With the dedupe rule the unmatched piece of truth 0 is dropped before ranking.

    Primary drops cand2, ranking cand1, D, c3. Sensitivity drops cand1, ranking D, cand2, c3.
    K = 3 then hits truth 0 and truth 3 in both modes. Recall 2 / 3. At K = 1, 1 / 3 and 0.
    """
    p, bp, tp, blocks, truth = _parity_fixture(tmp_path)
    b, t = _gt_inputs(blocks, truth)
    tabs, c = gt.score_raster(p, t, b, task="pit", mode=mode)
    dropped = c.loc[c["duplicate"], "score"].round(6).tolist()
    assert dropped == ([0.6] if mode == "primary" else [0.9])
    assert np.isclose(gt.pooled_recall_at_k(tabs, list(tabs), 100.0), 2 / 3)
    assert np.isclose(gt.pooled_recall_at_k(tabs, list(tabs), 40.0), 1 / 3 if mode == "primary" else 0.0)


# ----------------------------------------------------------------------------- end to end, ids, support
def test_score_raster_end_to_end_zero_ids_and_nodata(tmp_path):
    """0.5 m grid, 4 blocks of 375 m (make_blocks counts rows from the bottom). Truth ids 0, -5 and 'a'.

    b001_000 (top left)      truth 0, exact 20 x 20 px candidate p 0.9. Internal nodata 100 x 100 px.
    b001_001 (top right)     truth -5, candidate p 0.5. Its right half is nodata (missing edge cells).
    b000_000 (bottom left)   a candidate centred at x 373 m overlaps truth 'a' at IoU 100 / 220 = 0.45.
    b000_001 (bottom right)  ineligible. Truth 'a' has its centroid here (x 376 m), so it is outside.
    Support cells. 562500 - 10000, 750 x 375 = 281250, 562500. Denominator {0, -5}.
    The old core matched the straddler and left it outside the denominator. Now it is not matchable.
    K = 14 keeps all three candidates. Recall 2 / 2. At K = 1 only the 0.9 candidate. Recall 1 / 2.
    """
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.geometry import box
    prob = np.zeros((1500, 1500), np.float32)
    prob[100:120, 100:120] = 0.9
    prob[400:500, 400:500] = -1.0                        # internal nodata in b001_000
    prob[100:110, 900:910] = 0.5
    prob[:750, 1125:] = -1.0                             # b001_001 loses its right half
    prob[1000:1010, 740:752] = 0.7                       # straddling candidate, centroid x 373 m
    p = _write(tmp_path / "prob.tif", prob, CRS, from_origin(0, 750, 0.5, 0.5))
    blocks = gt.make_blocks((0, 0, 750, 750), CRS)
    blocks["eligible"] = blocks["block_id"] != "b000_001"
    truth = gpd.GeoDataFrame({"truth_id": [0, -5, "a"]},
                             geometry=[box(50, 690, 60, 700), box(450, 695, 455, 700), box(371, 245, 381, 250)],
                             crs=CRS)
    tabs, cands = gt.score_raster(p, truth, blocks, task="pit")
    sup = pd.DataFrame(cands.attrs["support"]).set_index("block_id")
    assert sup.loc["b001_000", "support_cells"] == 562500 - 10000
    assert sup.loc["b001_001", "support_cells"] == 281250
    assert np.isclose(tabs["b001_000"]["km2"], (562500 - 10000) * 0.25 / 1e6)
    assert np.isclose(tabs["b001_001"]["km2"], 281250 * 0.25 / 1e6)
    assert np.isclose(tabs["b000_000"]["km2"], 562500 * 0.25 / 1e6)
    assert "b000_001" not in tabs
    assert sorted(map(str, sum((v["truth_ids"] for v in tabs.values()), []))) == ["-5", "0"]
    assert cands.attrs["n_truth_denominator"] == 2
    assert set(cands["truth_id"].dropna()) == {0, -5}           # id 0 matches, the straddler is not matched
    assert np.isclose(gt.pooled_recall_at_k(tabs, list(tabs)), 1.0)
    # K = 1 (k_per_km2 tiny but positive) keeps only the 0.9 candidate. Recall 1 / 2 with truth id 0 as the hit
    k1 = 1.0 / sum(v["km2"] for v in tabs.values())
    assert np.isclose(gt.pooled_recall_at_k(tabs, list(tabs), k1), 0.5)


def test_truth_ids_invariant_under_relabelling(tmp_path):
    p, bp, tp, blocks, truth = _parity_fixture(tmp_path)
    b, t = _gt_inputs(blocks, truth)
    r = []
    for ids in ([0, 1, 2, 3], [7, -1, 99, 1000], ["w", "x", "y", "z"]):
        tabs, _ = gt.score_raster(p, t.assign(truth_id=ids), b, task="pit")
        r.append(gt.pooled_recall_at_k(tabs, list(tabs), 100.0))
    assert np.allclose(r, 2 / 3)
    with pytest.raises(AssertionError, match="duplicate truth_id"):
        gt.score_raster(p, t.assign(truth_id=[1, 1, 2, 3]), b, task="pit")


def test_support_masks_zero_area_and_paired_arms(tmp_path):
    """Optional masks reduce the budget. Zero support drops a block. Arms with different masks cannot pair."""
    import geopandas as gpd
    from rasterio.transform import from_origin
    p, bp, tp, blocks, truth = _parity_fixture(tmp_path)
    b, t = _gt_inputs(blocks, truth)
    tabs0, c0 = gt.score_raster(p, t, b, task="pit")
    assert c0.attrs["dropped_blocks"] == [3] and 3 not in tabs0       # all-nodata block, zero support
    assert np.isclose(tabs0[0]["km2"], 0.01)
    # exclusion polygon over the left half of block 0 (50 x 100 cells = 0.005 km2) removes truth 0 and cand1
    water = gpd.GeoDataFrame(geometry=[_px(0, 100, 0, 50)], crs="EPSG:6346")
    tabs1, c1 = gt.score_raster(p, t, b, task="pit", exclude_polygons=water)
    assert np.isclose(tabs1[0]["km2"], 0.005) and tabs1[0]["n_truth"] == 0
    # same mask as a raster on the identical grid gives the same tables
    m = np.ones((200, 200), np.uint8)
    m[0:100, 0:50] = 0
    mp = _write(tmp_path / "mask.tif", m, "EPSG:6346", from_origin(X0, Y0, 1.0, 1.0), nodata=255, dtype="uint8")
    tabs2, _ = gt.score_raster(p, t, b, task="pit", mask_rasters=[mp])
    assert all(np.isclose(tabs1[k]["km2"], tabs2[k]["km2"]) for k in tabs1)
    with pytest.raises(AssertionError, match="differ in scored support"):
        gt.paired_arm_difference(tabs0, tabs1, 0.05, B=10)
    # a mask that removes everything
    with pytest.raises(AssertionError, match="no block has scored support"):
        gt.score_raster(p, t, b, task="pit", eligible_mask_fn=lambda s, tf: np.zeros(s, bool))


def test_grid_contract_units_and_alignment(tmp_path):
    """Feet and degrees are refused. A half-pixel shifted mask is refused. Non-square cells get |a*e| area."""
    from rasterio.transform import from_origin
    p, bp, tp, blocks, truth = _parity_fixture(tmp_path)
    b, t = _gt_inputs(blocks, truth)
    with pytest.raises(AssertionError, match="not metres"):
        gt.grid_contract("EPSG:2272", from_origin(0, 0, 1, 1))
    with pytest.raises(AssertionError, match="not projected"):
        gt.grid_contract("EPSG:4269", from_origin(0, 0, 1, 1))
    assert gt.grid_contract("EPSG:6346+5703", from_origin(0, 0, 1, 0.5))["cell_area_m2"] == 0.5
    m = np.ones((200, 200), np.uint8)
    sp = _write(tmp_path / "shift.tif", m, "EPSG:6346", from_origin(X0 + 0.5, Y0, 1.0, 1.0), nodata=255, dtype="uint8")
    with pytest.raises(AssertionError, match="transform"):
        gt.score_raster(p, t, b, task="pit", mask_rasters=[sp])
    pf = _write(tmp_path / "ft.tif", np.zeros((10, 10), np.float32), "EPSG:2272", from_origin(0, 10, 1, 1))
    bf = gt.make_blocks((0, 0, 10, 10), "EPSG:2272", size=5).assign(eligible=True)
    with pytest.raises(AssertionError, match="not metres"):
        gt.score_raster(pf, t.set_crs("EPSG:2272", allow_override=True), bf, task="pit")
    # non-square cells. 1 m wide, 0.5 m tall. An 8-cell blob is 4 m2 (cell*cell would say 8)
    prob = np.zeros((40, 20), np.float32)
    prob[4:8, 4:6] = 0.9
    pn = _write(tmp_path / "ns.tif", prob, "EPSG:6346", from_origin(X0, Y0, 1.0, 0.5))
    bn = gt.make_blocks((X0, Y0 - 20, X0 + 20, Y0), "EPSG:6346", size=20).assign(eligible=True)
    tn = t.iloc[:0]
    _, cn = gt.score_raster(pn, tn, bn, task="pit")
    assert len(cn) == 1 and np.isclose(cn["area_m2"].iloc[0], 4.0)
    assert np.isclose(pd.DataFrame(cn.attrs["support"])["support_km2"].iloc[0], 400 / 1e6)


# ----------------------------------------------------------------------------- pooled recall tie order (F09)
def _tie_tables():
    """Block 'b' has blobs 2 (hit on truth 't') and 10 (miss), equal score and area. km2 0.025 -> K = 1."""
    c = pd.DataFrame({"blob_id": [10, 2], "score": [0.5, 0.5], "area_m2": [5.0, 5.0], "truth_id": [None, "t"]})
    return {"b": {"c": c, "n_truth": 1, "km2": 0.025, "truth_ids": ["t"]}}


def test_pooled_tie_order_numeric_and_draws():
    tabs = _tie_tables()
    assert gt.pooled_recall_at_k(tabs, ["b"]) == 1.0                 # numeric 2 < 10. A string sort keeps 10
    shuf = {"b": {**tabs["b"], "c": tabs["b"]["c"].iloc[::-1].reset_index(drop=True)}}
    assert gt.pooled_recall_at_k(shuf, ["b"]) == 1.0
    # repeated draws. K = round(40 * 0.05) = 2 keeps blob 2 of draw 0 and blob 2 of draw 1. Both copies hit
    assert gt.pooled_recall_at_k(tabs, ["b", "b"]) == 1.0
    # budget boundary. K = round(40 * 0.075) = 3 keeps 2, 2, 2 (three draws). Recall 3 / 3
    assert gt.pooled_recall_at_k(tabs, ["b", "b", "b"]) == 1.0
    no_ids = {"b": {k: v for k, v in tabs["b"].items() if k != "truth_ids"}}
    assert gt.pooled_recall_at_k(no_ids, ["b", "b"]) == 1.0          # 3.0 JSON tables, keyed by draw
    with pytest.raises(ValueError, match="numeric"):
        gt.pooled_recall_at_k({"b": {**tabs["b"], "c": tabs["b"]["c"].assign(blob_id=["x", "y"])}}, ["b"])


def test_pooled_hits_only_on_denominator_truth():
    """A candidate matched to truth outside the drawn blocks' truth lists is not a hit. Recall never exceeds 1."""
    c = pd.DataFrame({"blob_id": [1, 2], "score": [0.9, 0.8], "area_m2": [5.0, 5.0], "truth_id": ["out", "in"]})
    tabs = {"b": {"c": c, "n_truth": 1, "km2": 1.0, "truth_ids": ["in"]}}
    assert gt.pooled_recall_at_k(tabs, ["b"]) == 1.0
    c2 = c.assign(truth_id=["out", None])
    assert gt.pooled_recall_at_k({"b": {**tabs["b"], "c": c2}}, ["b"]) == 0.0


# ----------------------------------------------------------------------------- decisions and gates
def test_recall_and_decisions():
    good, ref = _tables(20, 0.95, 1), _tables(20, 0.95, 2)
    r = gt.pooled_recall_at_k(good, list(good))
    assert 0.8 <= r <= 1.0
    dup = gt.pooled_recall_at_k(good, ["b0", "b0"])        # duplicates count twice, recall unchanged
    assert dup == gt.pooled_recall_at_k(good, ["b0"])
    res = gt.transfer_difference(good, ref, margin=0.2, B=200)
    assert res["decision"] == "success" and res["undefined_share"] == 0.0
    bad = _tables(20, 0.1, 3)
    assert gt.transfer_difference(bad, ref, margin=0.1, B=200)["decision"] == "failure"
    few = gt.transfer_difference(_tables(5, 0.9, 4), ref, margin=0.1, B=100)
    assert few["decision"] == "inconclusive" and "permutation" in few          # band never stands in for a CI
    assert "Never used in a gate" in few["permutation"]["label"]
    pa = gt.paired_arm_difference(good, bad, delta_gain=0.05, B=200)
    assert pa["decision"] == "success"
    with pytest.raises(AssertionError):
        gt.paired_arm_difference(good, _tables(3, 0.5), 0.05, B=10)
    assert gt.ceiling_per_block(good)["ceiling"].between(0, 1).all()
    assert abs(gt.density_scaled_k(10, 20) - 20.0) < 1e-9


def test_sparse_target_undefined_draws_give_inconclusive():
    """20 blocks, only one with truth. Many resamples have no truth, so draws are undefined (SH-01)."""
    t = _tables(20, 1.0, 5, n_truth=0, n_cand=3)
    t["b0"] = _tables(1, 1.0, 6)["b0"]
    ref = _tables(20, 0.95, 2)
    r = gt.transfer_difference(t, ref, margin=0.5, B=200)
    assert 0 < r["undefined_share"] < 1
    assert r["decision"] == "inconclusive" and "undefined" in r["decision_basis"]


def test_reference_policy_mismatch_refused():
    good, ref = _tables(20, 0.95, 1), _tables(20, 0.95, 2)
    with pytest.raises(AssertionError, match="policy mismatch"):
        gt.transfer_difference(good, ref, 0.1, B=10, ref_policy=ek.policy_for("pit", "sensitivity"),
                               target_policy=ek.policy_for("pit"))


# ----------------------------------------------------------------------------- checkpoint loads (G-11)
def test_partial_checkpoint_load_needs_allow_list():
    class T:                                   # tensor stand-in with a shape
        def __init__(self, *s):
            self.shape = s
    own = {"d1.0.weight": T(32, 8, 3, 3), "d1.1.weight": T(32), "out.weight": T(3, 32, 1, 1)}
    ck = {"state_dict": {"d1.0.weight": T(32, 7, 3, 3), "d1.1.weight": T(32), "out.weight": T(3, 32, 1, 1)},
          "channels": ["a", "b", "c", "d", "e", "f", "g"]}
    with pytest.raises(AssertionError, match="not in the allow-list"):
        gt.init_from_checkpoint(own, ck, reinit=(), channels=list("abcdefgh"))
    loaded, rec = gt.init_from_checkpoint(own, ck, reinit=("d1.0.",), channels=list("abcdefgh"))
    assert set(loaded) == {"d1.1.weight", "out.weight"} and rec["reinitialised"] == ["d1.0.weight"]
    own7 = {**own, "d1.0.weight": T(32, 7, 3, 3)}
    with pytest.raises(AssertionError, match="channel order"):
        gt.init_from_checkpoint(own7, ck, reinit=(), channels=list("bacdefg"))
    _, rec7 = gt.init_from_checkpoint(own7, ck, reinit=(), channels=list("abcdefg"))
    assert rec7["reinitialised"] == [] and rec7["channels_checked"] is True
    with pytest.raises(AssertionError, match="allow-list entry"):
        gt.init_from_checkpoint(own7, ck, reinit=("out.",), channels=list("abcdefg"))


def test_transfer_checkpoint_refuses_when_unset(tmp_path):
    cfg = gt.load_config("3.4")
    with pytest.raises(gt.DecisionMissingError, match="transfer_checkpoint"):
        gt.transfer_checkpoint(cfg, "pit", "3.4")
    cfg2 = {"model": {"pit": {"transfer_checkpoint": {"exp": "3.4", "rel": "models/nope/best.pt"}}}}
    with pytest.raises(gt.MissingInputError, match="transfer checkpoint"):
        gt.transfer_checkpoint(cfg2, "pit", "3.4")


# ----------------------------------------------------------------------------- unchanged helpers
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


def test_blocks_missing_void_is_ineligible():
    """G-13. A block with no density row (void unknown) is not eligible when a void cap is set."""
    g = gt.make_blocks((0, 0, 750, 375), CRS)
    dens = pd.DataFrame({"block_id": [g.block_id[0]], "void_frac_05": [0.1], "ground_ppm2": [2.0]})
    out = gt.eligibility_from_void(g.merge(dens, on="block_id", how="left"), 0.9)
    assert out["eligible"].tolist() == [True, False]


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
