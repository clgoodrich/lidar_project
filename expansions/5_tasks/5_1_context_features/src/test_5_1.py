"""Smoke tests for 5.1 context features. Tiny synthetic data, no GPU, no network, no real data. Seconds.

Run: python -m pytest -q expansions/5_tasks/5_1_context_features/src/test_5_1.py -p no:cacheprovider
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
sys.path.insert(0, str(HERE.parents[1] / "5_6_record_association" / "src"))

import _context_upstream_inventory_9t as s0  # noqa: E402
import _context_shared_folds_9t as s1  # noqa: E402
import _context_reliance_edits_9t as s2  # noqa: E402
import _context_retrain_manifest_9t as s3  # noqa: E402
import _context_stage2_features_9t as s4  # noqa: E402
import _context_stage2_learner_9t as s5  # noqa: E402
import _context_leakage_audit_9t as s6  # noqa: E402
import _task5_helpers as th  # noqa: E402

CRS = "EPSG:6346"


def test_config_parses_and_specs_resolve():
    cfg = th.load_cfg(str(HERE / "_context_shared_folds_9t.py"))
    assert cfg["k_per_km2"] == 40.0
    for name in cfg["inputs"]:
        th.inp(cfg, name, must_exist=False)
    for name in cfg["outputs"]:
        assert "5_1_context_features" in str(th.resolve(cfg["outputs"][name]))


def test_scheme_agreement_relabel_and_mismatch(tmp_path):
    a = {1: 0, 2: 0, 3: 1, 4: 1}
    assert s0.scheme_agreement(a, {1: 1, 2: 1, 3: 0, 4: 0})["same_partition"]
    assert not s0.scheme_agreement(a, {1: 0, 2: 1, 3: 0, 4: 1})["same_partition"]
    p = tmp_path / "assign.csv"
    pd.DataFrame({"pit_inside_id": [0, 1, 2], "block_id": [5.0, 5.0, np.nan], "fold": [2.0, 2.0, np.nan]}).to_csv(p, index=False)
    assert s0.block_fold_map(p) == {5: 2}


def test_shared_folds_deterministic_balanced_audit_excluded():
    rng = np.random.default_rng(1)
    b = pd.DataFrame({"block_id": np.arange(40), "n_pits": rng.integers(0, 9, 40), "n_pads": rng.integers(0, 6, 40)})
    m1 = s1.assign_shared(b, 5, 20261104, audit=[3, 7])
    m2 = s1.assign_shared(b.sample(frac=1, random_state=4), 5, 20261104, audit=[7, 3])
    assert m1 == m2
    assert 3 not in m1 and 7 not in m1 and len(m1) == 38
    summ = pd.DataFrame(s1.fold_summary(b, m1, 5))
    assert summ.n_pits.max() - summ.n_pits.min() <= 8


def test_retrain_jobs_disjoint_and_cover():
    m = {b: b % 5 for b in range(20)}
    jobs = s3.jobs_from_folds(m, 5, audit=[99])
    assert len(jobs) == 15
    for j in jobs:
        assert not set(j["held_out"]) & set(j["train"]) and not set(j["val"]) & set(j["train"])
        assert sorted(j["held_out"] + j["val"] + j["train"]) == list(range(20))


def _synthetic_prob():
    from rasterio.transform import from_origin
    p = np.zeros((40, 40), np.float32)
    p[5:10, 5:10] = 0.8
    p[20:24, 20:24] = 0.3
    p[30, 30] = 0.9          # 1 px = 0.25 m2 at 0.5 m, under the 4 m2 floor
    return p, from_origin(0, 20, 0.5, 0.5)


def test_extract_and_match():
    import geopandas as gpd
    from shapely.geometry import box
    p, tf = _synthetic_prob()
    c = s4.extract_candidates(p, tf, cutoff=0.10, min_area_m2=4.0, crs=CRS)
    assert len(c) == 2 and c.score.iloc[0] == pytest.approx(0.8)
    truth = gpd.GeoDataFrame({"truth_id": [7, 8]}, geometry=[box(2.5, 15, 5, 17.5), box(15, 0, 16, 1)], crs=CRS)
    mt, dup = s4.greedy_iou_match(c, truth, 0.3)
    assert mt[0] == 7 and mt[1] is None and not dup.any()
    assert s4.to_prob(np.array([254, 127, 255], np.uint8))[2] != s4.to_prob(np.array([254], np.uint8))[0]


def test_disc_stats_and_padded_read(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    a = np.zeros((100, 100), np.float32)
    a[50, 60] = 0.9
    tif = tmp_path / "road.tif"
    with rasterio.open(tif, "w", driver="GTiff", height=100, width=100, count=1, dtype="float32", crs=CRS,
                       transform=from_origin(0, 100, 1, 1), nodata=-1) as ds:
        ds.write(a, 1)
    with rasterio.open(tif) as ds:
        d = s4.disc_stats(ds, np.array([[50.5, 49.5], [1.0, 1.0]]), 30, "mindist", thr=0.5, cap=30)
        assert d[0] == pytest.approx(10, abs=0.01) and d[1] == 30
        m = s4.disc_stats(ds, np.array([[0.5, 99.5]]), 3, "mean")   # corner, mostly off-raster
        assert m[0] == pytest.approx(0.0)


def test_edits_change_only_masked_area_and_sham_keeps_area():
    from rasterio.transform import from_origin
    from shapely.geometry import LineString, box
    yy, xx = np.mgrid[0:120, 0:120].astype(np.float32)
    dem = (0.1 * xx + 0.05 * yy).astype(np.float32)
    dem[40:80, 40:80] = 7.0                     # a flat pad cut into the slope
    tf = from_origin(0, 60, 0.5, 0.5)
    cfg = {"reliance": {"pit_keep_radius_m": 3.0, "road_corridor_m": 2.0, "sham_min_offset_m": 5.0, "sham_max_offset_m": 20.0}}
    rng = np.random.default_rng(0)
    v = s2.unit_variants(dem, tf, (30.0, 30.0), [box(20, 20, 40, 40)], [LineString([(0, 5), (60, 5)])], [], cfg, rng)
    for k in ("orig", "pad", "road", "both", "sham_pad", "sham_road"):
        assert k in v
    e_pad = v["pad"][0]
    changed = np.abs(e_pad - dem) > 1e-4
    assert changed.any() and not changed[:20, :].any()   # rows far from the pad untouched
    assert v["pad"][1] > 0 and v["sham_pad"][2] and v["sham_pad"][1] == pytest.approx(v["pad"][1])
    stack = s2.fallback_derivatives(e_pad, 0.5)
    assert stack.shape == (7, 120, 120) and np.isfinite(stack).all()


def _toy_features(n_blocks=10, per_block=12, seed=0):
    rng = np.random.default_rng(seed)
    rows, nt, b2f = [], {}, {}
    cid = 0
    for b in range(n_blocks):
        b2f[b] = b % 5
        nt[b] = 3
        for i in range(per_block):
            y = int(i < 3)
            rows.append(dict(cand_id=cid, block_id=b, block_fold=b % 5, y=y, matched_truth=f"{b}_{i}" if y else "",
                             is_dup=False, area_m2=10 + i, stage1=rng.uniform(0.1, 0.9),
                             road_dist_m=(5 if y else 200) + rng.normal(0, 3), pad_mean_25m=rng.uniform(),
                             pad_mean_50m=rng.uniform(), pad_mean_100m=rng.uniform(),
                             n_pit_50m=rng.integers(0, 3), n_pit_100m=rng.integers(0, 5), slope=rng.uniform(0, 20)))
            cid += 1
    base = pd.DataFrame(rows)
    feat = pd.concat([base.assign(outer_fold=k) for k in range(5)], ignore_index=True)
    return feat, nt, b2f


def test_learner_cv_and_paired_bootstrap():
    feat, nt, b2f = _toy_features()
    cfg = {"stage2": {"gbm": {"max_depth": 3, "n_estimators": 20, "learning_rate": 0.1}, "gbm_lr_grid": [0.1],
                      "logit_C_grid": [1.0], "inner_folds": 2, "ablation_drop": ["road_dist_m", "n_pit_50m", "n_pit_100m"]},
           "block_m": 375.0, "k_per_km2": 40.0}
    scored, models, chosen = s5.run_cv(feat, cfg, nt, b2f, seed=1)
    assert len(scored) == feat.cand_id.nunique()
    sc = s5.Scorer(scored.assign(stage1=scored.stage1_arm), nt, 375.0 ** 2 / 1e6, 40.0)
    blocks = sorted(nt)
    r_gbm, r_s1 = sc.recall("gbm", blocks), sc.recall("stage1", blocks)
    for arm in ("gbm", "stage1", "logit"):
        for bl in (blocks, [0, 0, 3, 9, 9, 9]):
            assert sc.recall_fast(arm, bl) == pytest.approx(sc.recall(arm, bl))
    assert r_gbm > r_s1        # road distance separates the toy positives
    d, lo, hi = s5.ek.bootstrap_diff(lambda b: sc.recall("gbm", b), blocks, lambda b: sc.recall("stage1", b), blocks,
                                     B=50, seed=0, paired=True)
    assert lo <= d <= hi
    assert s5.ek.decide(lo, hi, 0.0, "superiority") in ("success", "inconclusive", "failure")


def test_scorer_duplicates_take_budget_but_count_once():
    df = pd.DataFrame({"block_id": [0, 0, 0], "cand_id": [0, 1, 2], "area_m2": [1, 1, 1], "a": [0.9, 0.8, 0.1],
                       "matched_truth": ["t1", "", "t2"]})
    sc = s5.Scorer(df, {0: 2}, 0.025, 80.0)     # K = 2 candidates
    assert sc.recall("a", [0]) == pytest.approx(0.5)
    assert sc.recall("a", [0, 0]) == pytest.approx(0.5)   # repeated block is a separate copy
    assert sc.recall_fast("a", [0]) == pytest.approx(0.5) and sc.recall_fast("a", [0, 0]) == pytest.approx(0.5)


def test_leakage_audit_flags_overlap(tmp_path):
    for k, train in ((0, [2, 3]), (1, [0, 1, 2, 3])):
        d = tmp_path / f"fold{k}"
        d.mkdir()
        (d / "training_blocks.json").write_text(json.dumps({"train": train, "val": []}))
    usage = {"mode": "outer", "block_to_fold": {"0": 0, "1": 0, "2": 1, "3": 1},
             "usage": [dict(outer_fold=0, block_fold=0, role="pad", kind="outer0", raster=str(tmp_path / "fold0" / "p.tif"), blocks=[0, 1]),
                       dict(outer_fold=1, block_fold=1, role="pad", kind="outer1", raster=str(tmp_path / "fold1" / "p.tif"), blocks=[2, 3])]}
    res = s6.audit(usage, s6.Seen({}), nested=False)
    assert not res["passed"] and res["n_failed"] == 1
    assert res["entries"][0]["passed"] and not res["entries"][1]["passed"]


def test_missing_input_names_itself(tmp_path):
    cfg = {"inputs": {"audit_blocks": {"path": str(tmp_path / "nope.csv"), "hint": "run P2"}}}
    with pytest.raises(th.MissingInput) as e:
        th.inp(cfg, "audit_blocks")
    assert "audit_blocks" in e.value.args[0]
