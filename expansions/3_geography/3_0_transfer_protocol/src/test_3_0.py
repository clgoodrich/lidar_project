"""Smoke tests for 3.0 on tiny synthetic data. CPU only, no network, seconds.

Run
    python -m pytest -q expansions/3_geography/3_0_transfer_protocol/src/test_3_0.py -p no:cacheprovider
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
import _transfer_score_lib as tl  # noqa: E402
import _transfer_score_run as sr  # noqa: E402
import _transfer_prereg_fill as pf  # noqa: E402
import _transfer_decision_report as dr  # noqa: E402
import _transfer_ci_width_9t as cw  # noqa: E402
import _transfer_baseline_repeat_9t as br  # noqa: E402

RES, SIZE = 0.5, 400                          # 200 m square, 2 x 2 blocks of 100 m, 0.04 km2


def world_to_px(x, y):
    return int((200 - y) / RES), int(x / RES)


def make_area(tmp: Path, uint8: bool = False):
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    p = np.zeros((SIZE, SIZE), np.float32)
    feats = [(20, 20, 0.9), (150, 30, 0.8), (60, 160, 0.7)]          # three annotated pits
    decoys = [(150, 150, 0.95), (120, 60, 0.95)]                       # two unannotated blobs ranked first
    for x, y, s in feats + decoys:
        r, c = world_to_px(x, y + 4)                                   # top-left corner of the 4 m box
        p[r:r + 8, c:c + 8] = s                                        # 4 m x 4 m blob
    tf = from_origin(0, 200, RES, RES)
    prob = tmp / "prob.tif"
    with rasterio.open(prob, "w", driver="GTiff", height=SIZE, width=SIZE, count=1,
                       dtype="uint8" if uint8 else "float32", crs="EPSG:6346", transform=tf,
                       nodata=255 if uint8 else None) as d:
        d.write(np.round(p * 254).astype(np.uint8) if uint8 else p, 1)
    blocks = gpd.GeoDataFrame({"block_id": [0, 1, 2, 3]},
                              geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100), box(0, 100, 100, 200),
                                        box(100, 100, 200, 200)], crs="EPSG:6346")
    bp = tmp / "blocks.gpkg"
    blocks.to_file(bp, layer="blocks", driver="GPKG")
    truth = gpd.GeoDataFrame({"pit_inside_id": [1, 2, 3]}, geometry=[box(x, y, x + 4, y + 4) for x, y, _ in feats],
                             crs="EPSG:6346")
    tp = tmp / "truth.gpkg"
    truth.to_file(tp, layer="pit_inside", driver="GPKG")
    return prob, bp, f"{tp}:pit_inside"


def test_recall_one_and_two_thirds(tmp_path):
    prob, bp, truth = make_area(tmp_path)
    full = tl.score(prob, bp, truth, 125.0, truth_id="pit_inside_id", B=200, seed=1, drop_edge=False)
    s = full["summary"]
    assert s["k_total"] == 5 and s["n_truth"] == 3 and s["primary"]["recall"] == 1.0
    part = tl.score(prob, bp, truth, 100.0, truth_id="pit_inside_id", B=200, seed=1, drop_edge=False)
    assert part["summary"]["k_total"] == 4
    assert abs(part["summary"]["primary"]["recall"] - 2 / 3) < 1e-9
    assert "warning" in part["summary"]["primary"]                    # 4 blocks < 15
    assert part["summary"]["recall_at_k_expkit"]["hits"] == 2
    again = tl.score(prob, bp, truth, 100.0, truth_id="pit_inside_id", B=200, seed=1, drop_edge=False)
    assert json.dumps(again["summary"], sort_keys=True, default=str) == json.dumps(part["summary"], sort_keys=True, default=str)


def test_void_half_pixel_shift_rejected(tmp_path):
    import rasterio
    from affine import Affine
    prob, bp, truth = make_area(tmp_path)
    void = tmp_path / "void.tif"
    with rasterio.open(prob) as r:
        profile = r.profile.copy()
    profile["transform"] = profile["transform"] * Affine.translation(0.5, 0)
    with rasterio.open(void, "w", **profile) as r:
        r.write(np.zeros((SIZE, SIZE), dtype=np.float32), 1)
    with pytest.raises(ValueError, match="pixel transform"):
        tl.score(prob, bp, truth, void_path=void, B=10)


def test_uint8_dn254_and_duplicates(tmp_path):
    prob, bp, truth = make_area(tmp_path, uint8=True)
    s = tl.score(prob, bp, truth, 125.0, truth_id="pit_inside_id", B=100, seed=1, drop_edge=False)["summary"]
    assert s["primary"]["recall"] == 1.0


def test_dedupe_second_piece():
    import geopandas as gpd
    from shapely.geometry import box
    truth = gpd.GeoDataFrame({"truth_id": [7]}, geometry=[box(0, 0, 10, 10)], crs="EPSG:6346")
    c = gpd.GeoDataFrame({"score": [0.9, 0.5]}, geometry=[box(0, 0, 9, 9), box(9.2, 9.2, 9.8, 9.8)], crs="EPSG:6346")
    m, hit = tl.match_greedy(truth, c)
    assert m == [7, None] and hit == {7}
    assert tl.dedupe_mask(c, truth, m).tolist() == [False, True]


def test_per_group_budget_floor():
    df = pd.DataFrame({"score": [0.9, 0.8, 0.7, 0.6], "area_m2": 1.0, "cand_id": range(4), "group": [0, 0, 1, 1]})
    keep = tl.rank_keep(df, 10.0, 0.0, "per_group", {0: 0.15, 1: 0.25})
    assert keep.tolist() == [True, False, True, True]


def test_harness_from_prereg_and_decision(tmp_path, monkeypatch):
    real = pf.ek.new_run
    monkeypatch.setattr(pf.ek, "new_run", lambda *a, **k: real(*a, **{**k, "base": tmp_path / "rec"}))
    prob, bp, truth = make_area(tmp_path)
    f = pf.example_fields()
    f.update(area="synth", reference={"run": "synthetic", "label": "new baseline"}, split_file=str(bp),
             split_sha256="x" * 64, lidar="synthetic", ground_density="synthetic", label_source="test",
             model_policy="single_fold:0", adaptation_area="none", test_area="synthetic", audit_file="none",
             labellers="test", density_c=5.0)
    f["scoring"] = {"area": "synth", "task": "pit", "prob": str(prob), "blocks": str(bp), "truth": truth,
                    "truth_id": "pit_inside_id", "k": 40, "seed": 3, "B": 100, "void_cap": None}
    assert pf.check(f) == []
    bad = dict(f, margin_source="the fold spread of 9t")
    assert pf.check(bad)
    tpl = tmp_path / "tpl.md"
    tpl.write_text("# T\n\n## 1. Question\nx\n\n## 6. Primary analysis\ny\n\n## 11. Required\nz\n")
    fp = tmp_path / "fields.json"
    fp.write_text(json.dumps(f))
    out = tmp_path / "prereg.md"
    assert pf.main(["--fields", str(fp), "--template", str(tpl), "--out", str(out)]) == 0
    assert tl.read_prereg(out)["scoring"]["k"] == 40
    with pytest.raises(SystemExit):
        pf.main(["--fields", str(fp), "--template", str(tpl), "--out", str(out)])      # never overwritten
    ns = sr.argparse.Namespace(prereg=out, **{k: None for k in sr.SCORE_KEYS})
    s = sr.resolve(ns)
    rd = sr.run(s, out_base=tmp_path / "runs", prereg=out, quiet=True)
    js = json.loads((rd / "transfer_score_synth.json").read_text())
    assert js["prereg_sha256"] and js["secondary_density_scaled"]["c"] == 5.0
    ns2 = sr.argparse.Namespace(prereg=out, **{k: None for k in sr.SCORE_KEYS})
    ns2.k = 30
    with pytest.raises(SystemExit):
        sr.resolve(ns2)                                                              # flag disagrees with prereg
    t = pd.read_csv(rd / "transfer_blocks_synth.csv")
    d = dr.decision(t, t, 0.1, 200, 1)
    assert d["diff"] == 0 and d["verdict"] in ("success", "inconclusive")


def test_decide_paths():
    good = pd.DataFrame({"hits": [9] * 30, "n_truth": [10] * 30, "area_km2": 0.14})
    bad = pd.DataFrame({"hits": [3] * 30, "n_truth": [10] * 30, "area_km2": 0.14})
    assert dr.decision(good, good, 0.1, 200, 1)["verdict"] == "success"
    assert dr.decision(bad, good, 0.1, 200, 1)["verdict"] == "failure"


def test_projected_width_shrinks():
    rng = np.random.default_rng(0)
    pool = pd.DataFrame({"hits": rng.integers(0, 6, 60), "n_truth": 6, "area_km2": 0.14})
    t = cw.projected(pool, [10, 40], [0.1], reps=20, B=100, seed=1)
    assert t.median_width.iloc[0] > t.median_width.iloc[1]


def test_stable_json_ignores_settings(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"x": 1, "settings": {"p": "a"}}))
    b.write_text(json.dumps({"x": 1, "settings": {"p": "b"}}))
    assert br.stable(a) == br.stable(b)


def test_oof_mosaic(tmp_path):
    import rasterio
    prob, bp, _ = make_area(tmp_path)
    for k in range(2):
        with rasterio.open(prob) as r:
            prof = r.profile
            a = np.full((SIZE, SIZE), 0.1 * (k + 1), np.float32)
        with rasterio.open(tmp_path / f"f{k}.tif", "w", **prof) as d:
            d.write(a, 1)
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps({"tasks": {"pit": {"folds": {"0": {"held_out": [0, 1]}, "1": {"held_out": [2, 3]}}}}}))
    m = br.build_mosaic(str(tmp_path / "f{k}.tif"), sp, bp, "pit", tmp_path / "m.tif")
    with rasterio.open(m) as r:
        z = r.read(1)
    assert np.isclose(z[-1, 0], 0.1) and np.isclose(z[0, 0], 0.2)     # bottom rows blocks 0-1, top rows blocks 2-3
