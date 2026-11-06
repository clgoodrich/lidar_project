"""Tests for 3.0 on tiny synthetic data. CPU only, no network, seconds. Review 2026-11-06 regressions at the end.

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
import _transfer_holm_gate as hg  # noqa: E402
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


def _fields(tmp_path, prob, bp, truth, **ck):
    f = pf.example_fields()
    f.update(area="synth", reference={"run": "synthetic", "label": "new baseline"}, split_file=str(bp),
             split_sha256="x" * 64, lidar="synthetic", ground_density="synthetic", label_source="test",
             model_policy="single_fold:0", adaptation_area="none", test_area="synthetic", audit_file="none",
             labellers="test", density_c=5.0)
    f["checkpoint"] = {"family": "pit/unet_iso_cv5", "lineage": "isolated", "sha256": {"0": "a" * 64}, **ck}
    f["multiplicity"] = {"method": "holm", "gate": "synth", "family": ["synth"], "max_undefined": 0.0}
    f["scoring"] = {"area": "synth", "task": "pit", "prob": str(prob), "blocks": str(bp), "truth": truth,
                    "truth_id": "pit_inside_id", "k": 40, "seed": 3, "B": 100, "void_cap": None,
                    "cutoff": 0.35, "iou": 0.3, "dedupe": "truth_matched", "order": "score", "mode": "primary"}
    return f


def _ckpt_record(tmp_path, prob, lineage="isolated", provisional=False):
    rec = {"checkpoint": {"task": "pit", "family": "pit/unet_iso_cv5", "lineage": lineage, "provisional": provisional,
                          "provisional_reasons": ["test"] if provisional else [], "sha256": {"0": "a" * 64}},
           "prob_sha256": tl.ek.sha256(prob)}
    p = tmp_path / f"ck_{lineage}_{provisional}.json"
    p.write_text(json.dumps(rec))
    return p


def test_harness_from_prereg_and_decision(tmp_path, monkeypatch):
    """F08 / G-06. Prereg declares policy and checkpoint. Exact verdicts for each lineage case."""
    real = pf.ek.new_run
    monkeypatch.setattr(pf.ek, "new_run", lambda *a, **k: real(*a, **{**k, "base": tmp_path / "rec"}))
    prob, bp, truth = make_area(tmp_path)
    f = _fields(tmp_path, prob, bp, truth)
    assert pf.check(f) == []
    assert pf.check(dict(f, margin_source="the fold spread of 9t"))
    bad = json.loads(json.dumps(f)); bad["scoring"]["cutoff"] = 0.10          # 0.10 is the sensitivity
    assert any("policy_for" in x for x in pf.check(bad))
    tpl = tmp_path / "tpl.md"
    tpl.write_text("# T\n\n## 1. Question\nx\n\n## 6. Primary analysis\ny\n\n## 11. Required\nz\n")
    fp = tmp_path / "fields.json"
    fp.write_text(json.dumps(f))
    out = tmp_path / "prereg.md"
    assert pf.main(["--fields", str(fp), "--template", str(tpl), "--out", str(out)]) == 0
    assert tl.read_prereg(out)["scoring"]["cutoff"] == 0.35
    with pytest.raises(SystemExit):
        pf.main(["--fields", str(fp), "--template", str(tpl), "--out", str(out)])      # never overwritten
    ns = sr.argparse.Namespace(prereg=out, **{k: None for k in sr.SCORE_KEYS})
    ns.k = 40.0                                                                      # 40.0 equals 40 (minor fix)
    s = sr.resolve(ns)
    s["checkpoint_record"] = str(_ckpt_record(tmp_path, prob))
    rd = sr.run(s, out_base=tmp_path / "runs", prereg=out, quiet=True)
    js = json.loads((rd / "transfer_score_synth.json").read_text())
    assert js["policy"] == tl.ek.policy_for("pit") and js["secondary_density_scaled"]["c"] == 5.0
    ns2 = sr.argparse.Namespace(prereg=out, **{k: None for k in sr.SCORE_KEYS})
    ns2.k = 30
    with pytest.raises(SystemExit):
        sr.resolve(ns2)                                                              # flag disagrees with prereg
    # identical target and reference, both isolated and final: diff 0, margin 0.1 -> exactly "success"
    args = ["--target", str(rd), "--reference", str(rd), "--prereg", str(out)]
    assert dr.main(args) == 0
    d = json.loads((rd / "transfer_decision_synth.json").read_text())
    assert d["primary"]["diff"] == 0 and d["primary"]["verdict"] == "success" and d["confirmatory"] is True
    # archival reference: descriptive, never supported
    monkeypatch.setattr(dr, "load_reference", lambda ref, task, k: (
        {"kind": "archival", "policy": None, "dedupe": None, "checkpoint": None,
         "footprint": "truth_bearing_blocks_only"}, pd.read_csv(rd / "transfer_blocks_synth.csv")))
    assert dr.main(["--target", str(rd), "--reference", "archival", "--prereg", str(out)]) == 0
    d = json.loads((rd / "transfer_decision_synth.json").read_text())
    assert d["primary"]["verdict"] == "descriptive" and d["primary"]["verdict_if_confirmatory"] == "success"
    assert "supported" not in (rd / "transfer_decision_synth.md").read_text()


def test_decision_refuses_policy_mismatch_and_provisional(tmp_path):
    """F08. A reference stamped with another cutoff is refused. A provisional checkpoint gives descriptive."""
    prob, bp, truth = make_area(tmp_path)
    f = _fields(tmp_path, prob, bp, truth)
    pr = json.loads(json.dumps(f))
    tsum = {"policy": tl.ek.policy_for("pit"), "scorer": {"dedupe": "truth_matched"},
            "checkpoint": {"family": "pit/unet_iso_cv5", "lineage": "isolated", "provisional": False,
                           "sha256": {"0": "a" * 64}}}
    ref_ok = {"kind": "run", "policy": tl.ek.policy_for("pit"), "dedupe": "truth_matched",
              "checkpoint": dict(tsum["checkpoint"]), "footprint": "all_blocks"}
    assert dr.compatibility(pr, tsum, ref_ok) == (True, [])
    with pytest.raises(AssertionError, match="policy mismatch"):
        dr.compatibility(pr, tsum, {**ref_ok, "policy": tl.ek.policy_for("pit", "sensitivity")})
    with pytest.raises(AssertionError, match="G-02"):
        dr.compatibility(pr, tsum, {**ref_ok, "footprint": "truth_bearing_blocks_only"})
    hist = {**ref_ok, "checkpoint": {"family": "pit/unet_iso_cv5", "lineage": "historical_cv5", "provisional": True}}
    ok, why = dr.compatibility(pr, tsum, hist)
    assert ok is False and any("historical_cv5" in w for w in why)
    bad = json.loads(json.dumps(pr)); bad["scoring"]["dedupe"] = "none"
    with pytest.raises(AssertionError, match="dedupe"):
        dr.compatibility(bad, tsum, ref_ok)
    del bad["scoring"]["dedupe"]
    with pytest.raises(ValueError, match="does not declare"):
        dr.compatibility(bad, tsum, ref_ok)


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


# ----------------------------------------------------------------------------- review 2026-11-06 regressions
def _gdf(boxes, **cols):
    import geopandas as gpd
    from shapely.geometry import box
    return gpd.GeoDataFrame(cols, geometry=[box(*b) for b in boxes], crs="EPSG:6346")


def test_policy_is_policy_for():
    """F02. The library's primary policy is ek.policy_for, and the config mirror agrees with it."""
    for task in ("pit", "pad"):
        assert tl.policy(task) == tl.ek.policy_for(task)
        assert tl.CFG_CUTOFF_BY_TASK[task] == tl.ek.policy_for(task)["cutoff"]
    assert tl.CUTOFF == tl.ek.policy_for("pit", "sensitivity")["cutoff"] == 0.10
    with pytest.raises(ValueError, match="explicit cutoff or a policy"):
        tl.candidates(np.zeros((4, 4), np.float32), None, "EPSG:6346")


def test_g03_score_order_ab_fixture():
    """G-03. One truth, A (score 0.9, IoU 0.6) and B (score 0.5, IoU 0.9), K = 1.
    Score order matches A, A is kept, recall 1. IoU order matches B, A is kept unmatched, recall 0.
    Dedupe is off here so only the order differs. The 3.1 test runs the same fixture through 3.1."""
    truth = _gdf([(0, 0, 10, 10)], truth_id=[5])
    cands = _gdf([(0, 0, 6, 10), (0, 0, 10, 9)], score=[0.9, 0.5])
    blocks = _gdf([(0, 0, 100, 100)], block_id=[0])                       # 0.01 km2, K = 100 per km2 -> 1
    for order, want in (("score", 1.0), ("iou", 0.0)):
        pol = tl.policy("pit", match_order=order, k_per_km2=100.0)
        out = tl.score_tables(cands, truth, blocks, pol, dedupe="none")      # isolate the order effect
        assert out["keep"].sum() == 1
        assert out["tab"].hits.sum() / out["tab"].n_truth.sum() == want


def test_dedupe_active_in_full_score(tmp_path):
    """Dedupe used to see NaN (not None) for unmatched candidates and never dropped a second piece.
    Truth 10 x 10 m. Blob 1 covers 8 x 10 m (IoU 0.8). Blob 2 is 1.5 x 6 m, 0.5 m apart, centroid inside."""
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    p = np.zeros((200, 200), np.float32)                                   # 100 m, 0.5 m cells, origin (0, 100)
    p[(100 - 20) * 2:(100 - 10) * 2, 10 * 2:18 * 2] = 0.9                  # x 10-18, y 10-20
    p[(100 - 18) * 2:(100 - 12) * 2, int(18.5 * 2):20 * 2] = 0.8           # x 18.5-20, y 12-18
    tf = from_origin(0, 100, 0.5, 0.5)
    pr = tmp_path / "p.tif"
    with rasterio.open(pr, "w", driver="GTiff", height=200, width=200, count=1, dtype="float32", crs="EPSG:6346",
                       transform=tf) as d:
        d.write(p, 1)
    gpd.GeoDataFrame({"block_id": [0]}, geometry=[box(0, 0, 100, 100)], crs="EPSG:6346").to_file(
        tmp_path / "b.gpkg", layer="blocks", driver="GPKG")
    gpd.GeoDataFrame({"pid": [1]}, geometry=[box(10, 10, 20, 20)], crs="EPSG:6346").to_file(
        tmp_path / "t.gpkg", layer="t", driver="GPKG")
    s = tl.score(pr, tmp_path / "b.gpkg", f"{tmp_path / 't.gpkg'}:t", 200.0, truth_id="pid", B=20)["summary"]
    assert s["n_candidates"] == 2 and s["n_duplicates_dropped"] == 1 and s["primary"]["recall"] == 1.0


def test_g05_interior_nan_and_boundary():
    """G-05. One interior NaN pixel no longer makes a block an edge block. Nodata joined to the raster
    border does. Interior nodata above the void cap drops the block."""
    from rasterio.transform import from_origin
    blocks = _gdf([(0, 0, 50, 50), (50, 0, 100, 50)], block_id=[0, 1])
    tf = from_origin(0, 50, 0.5, 0.5)
    prob = np.full((100, 200), 0.01, np.float32)
    prob[50, 50] = np.nan                                                   # one interior pixel in block 0
    b = tl.eligible_blocks(blocks, prob, tf)
    assert b.edge.tolist() == [False, False] and b.eligible.tolist() == [True, True]
    assert b.void_frac.iloc[0] == pytest.approx(1 / 10000)
    prob2 = prob.copy()
    prob2[:, 199] = np.nan                                                  # border column in block 1
    assert tl.eligible_blocks(blocks, prob2, tf).edge.tolist() == [False, True]
    prob3 = prob.copy()
    prob3[20:80, 10:90] = np.nan                                            # 48% interior nodata in block 0
    assert tl.eligible_blocks(blocks, prob3, tf, void_cap=0.4).eligible.tolist() == [False, True]
    assert tl.eligible_blocks(blocks, prob3, tf, void_cap=0.5).eligible.tolist() == [True, True]


def test_f11_grid_contract():
    """F11. Feet and degrees raise, a compound CRS with an EPSG:6346 horizontal part passes, a half-pixel
    shift, a rotation and a shape change raise."""
    from affine import Affine
    from pyproj import CRS
    tl.assert_metric_crs("EPSG:6346")
    tl.assert_metric_crs(CRS.from_user_input("EPSG:6346+5703"))
    for bad in ("EPSG:2272", "EPSG:4326", "EPSG:26917"):
        with pytest.raises(AssertionError):
            tl.assert_metric_crs(bad)
    g = {"crs": "EPSG:6346", "transform": Affine(0.5, 0, 0, 0, -0.5, 100), "shape": (10, 10)}
    tl.assert_same_grid(g, dict(g, crs=CRS.from_user_input("EPSG:6346+5703")))
    with pytest.raises(ValueError, match="pixel transform"):
        tl.assert_same_grid(g, dict(g, transform=Affine(0.5, 0, 0.25, 0, -0.5, 100)))
    with pytest.raises(ValueError, match="rotated"):
        tl.assert_same_grid(g, dict(g, transform=Affine(0.5, 0.01, 0, 0, -0.5, 100)))
    with pytest.raises(ValueError, match="shape"):
        tl.assert_same_grid(g, dict(g, shape=(10, 11)))
    with pytest.raises(AssertionError):
        tl.assert_same_grid(g, dict(g, crs="EPSG:2272"))


def test_signflip_not_identifiable_under_two_blocks():
    """Consolidated review. One block with truth gives residual 0, so the sign-flip interval collapses."""
    one = pd.DataFrame({"hits": [3, 0], "n_truth": [4, 0]})
    assert tl.signflip_interval(one, 200, 1) == tl.NOT_IDENTIFIABLE
    two = pd.DataFrame({"hits": [3, 1], "n_truth": [4, 4]})
    lo, hi = tl.signflip_interval(two, 200, 1)
    assert lo < 0.5 < hi


def test_g02_fill_and_ref_tables_schema(tmp_path):
    """G-02. Blocks with no feature get one fold model each (round robin), only NaN cells are filled,
    the uint8-derived values stay quantised, and the tables keep old keys and add policy and meta."""
    import geopandas as gpd
    import rasterio
    import _transfer_ref_tables_9t as rt
    from shapely.geometry import box
    assert rt.fill_assignment([9, 3, 7], "round_robin") == {3: 0, 7: 1, 9: 2}
    tf = rasterio.transform.from_origin(0, 10, 1, 1)
    blocks = gpd.GeoDataFrame({"block_id": [0, 1]}, geometry=[box(0, 0, 5, 10), box(5, 0, 10, 10)], crs="EPSG:6346")
    base = np.full((10, 10), np.nan, np.float32)
    base[:, :5] = 0.5                                                       # block 0 has its OOF prediction
    prof = dict(driver="GTiff", height=10, width=10, count=1, dtype="float32", crs="EPSG:6346", transform=tf, nodata=-1.0)
    for k in range(5):
        with rasterio.open(tmp_path / f"f{k}.tif", "w", **prof) as d:
            d.write(np.full((10, 10), 0.1 * (k + 1), np.float32), 1)
    out = rt.fill_mosaic(base, tf, blocks, {1: 3}, str(tmp_path / "f{k}.tif"), quantise=True)
    assert np.all(out[:, :5] == 0.5) and np.allclose(out[:, 5:], round(0.4 * 254) / 254)
    mean = rt.fill_mosaic(base, tf, blocks, {1: "mean"}, str(tmp_path / "f{k}.tif"), quantise=False)
    assert np.allclose(mean[:, 5:], 0.3)
    doc = {"0": {"cands": [{"blob_id": 0, "score": 0.9, "area_m2": 9.0, "truth_id": 4}], "n_truth": 1, "km2": 0.01, "fold": 0},
           "1": {"cands": [{"blob_id": 1, "score": 0.95, "area_m2": 9.0, "truth_id": None}], "n_truth": 0, "km2": 0.01, "fold": 1},
           "policy": tl.policy("pit"), "meta": {"footprint": "all_blocks"}}
    p = tmp_path / "t.json"
    p.write_text(json.dumps(doc))
    blk, pol, meta = tl.read_ref_tables(p)
    assert set(blk) == {"0", "1"} and pol["cutoff"] == 0.35 and meta["footprint"] == "all_blocks"
    assert tl.ref_block_counts(blk, 50.0, "global").hits.sum() == 0         # K = 1, the 0.95 decoy wins
    assert tl.ref_block_counts(blk, 100.0, "per_group").hits.sum() == 1     # one per fold, block 0 keeps its hit


# ----------------------------------------------------------------------------- user defaults 2026-11-06
def test_defaults_in_config():
    """take defaults. void cap 0.5, round robin primary, margin 0.03, Holm with max_undefined 0."""
    sd = tl._CFG["scoring_defaults"]
    assert tl.VOID_CAP_DEFAULT == 0.5 and sd["zero_feature_fill"] == "round_robin"
    assert sd["margin_default"] == 0.03
    assert sd["multiplicity"]["method"] == "holm" and sd["multiplicity"]["max_undefined"] == 0.0
    assert hg.MAX_UNDEFINED == 0.0 and pf.example_fields()["margin"] == 0.03


def test_default_void_cap_honoured():
    """Cap None falls back to 0.5. A block 4/16 void is kept, one 12/16 void is dropped."""
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.geometry import box
    prob = np.zeros((6, 10), np.float32)
    tf = from_origin(0, 6, 1, 1)
    prob[1:5, 1:5][:, :1] = np.nan             # left block 4 of 16 void (0.25)
    prob[1:5, 5:9][:, :3] = np.nan             # right block 12 of 16 void (0.75)
    blocks = gpd.GeoDataFrame({"block_id": [1, 2]}, geometry=[box(1, 1, 5, 5), box(5, 1, 9, 5)], crs="EPSG:6346")
    eb = tl.eligible_blocks(blocks, prob, tf, void_cap=None)
    assert eb.void_cap.tolist() == [0.5, 0.5]
    assert eb.eligible.tolist() == [True, False]


def test_holm_oracle():
    """Hand Holm. p (a .01, b .04, c .03), m 3. a 3x.01 = .03. c max(.03, 2x.03) = .06. b max(.06, .04) = .06."""
    adj = hg.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})
    adj = hg.holm({"a": 0.01, "b": float("nan")})          # NaN counts as 1 and stays NaN
    assert adj["a"] == pytest.approx(0.02) and np.isnan(adj["b"])


def test_one_sided_share_and_undefined():
    d = [-0.05, -0.04, 0.0, 0.01]
    assert hg.one_sided_p(d, 0.03) == 0.5                   # two of four at or below -0.03
    assert hg.one_sided_p(d, 0.03, "superiority") == 1.0    # all four at or below +0.03
    assert hg.one_sided_p(d, -0.045, "superiority") == 0.25 # one of four at or below -0.045
    assert np.isnan(hg.one_sided_p(d + [float("nan")], 0.03))   # max_undefined 0


def test_family_gate_exact_verdicts():
    """One primary at p .02 passes alone and fails to pass in a family of three (Holm .06)."""
    g = {"lo": -0.02, "hi": 0.05, "margin": 0.03, "bound_kind": "noninferiority"}
    alone = hg.family_gate({"x": {**g, "p_one_sided": 0.02}})
    assert alone["x"]["decision"] == "success" and alone["x"]["p_holm"] == pytest.approx(0.02)
    fam = hg.family_gate({"x": {**g, "p_one_sided": 0.02}, "y": {**g, "p_one_sided": 0.5},
                          "z": {**g, "p_one_sided": 0.5, "lo": -0.2, "hi": -0.05}})
    assert fam["x"]["p_holm"] == pytest.approx(0.06) and fam["x"]["decision"] == "inconclusive"
    assert fam["z"]["decision"] == "failure" and fam["y"]["decision"] == "inconclusive"
    assert hg.holm_partial(0.02, -0.02, 0.05, 0.03, "noninferiority", 1)[0] == "success"
    assert hg.holm_partial(0.02, -0.02, 0.05, 0.03, "noninferiority", 2)[0] == "inconclusive"
    assert hg.holm_partial(0.01, -0.02, 0.05, 0.03, "noninferiority", 2)[0] == "success"   # .01 < .05/4


def test_decision_family_of_one_matches_decide_and_family_cli(tmp_path):
    """A family of one equals ek.decide. The CLI refuses an incomplete family and applies Holm to a full one."""
    good = pd.DataFrame({"hits": [9] * 30, "n_truth": [10] * 30, "area_km2": 0.14})
    r = dr.decision(good, good, 0.03, 400, 1)
    assert r["verdict"] == r["verdict_unadjusted"] == "success" and r["p_one_sided"] == 0.0
    r2 = dr.decision(good, good, 0.03, 400, 1, gate="a", family=["a", "b"])
    assert r2["holm_input"]["family_size"] == 2
    pa, pb = tmp_path / "a.json", tmp_path / "b.json"
    pa.write_text(json.dumps({"holm_input": r2["holm_input"]}))
    with pytest.raises(SystemExit, match="not scored yet"):
        hg.main(["--inputs", str(pa), "--out", str(tmp_path / "f.json")])
    hb = dict(r2["holm_input"], gate="b", p_one_sided=0.4)
    pb.write_text(json.dumps({"holm_input": hb}))
    assert hg.main(["--inputs", str(pa), str(pb), "--out", str(tmp_path / "f.json")]) == 0
    f = json.loads((tmp_path / "f.json").read_text())
    assert f["a"]["p_holm"] == 0.0 and f["a"]["decision"] == "success"
    assert f["b"]["p_holm"] == pytest.approx(0.4) and f["b"]["decision"] == "inconclusive"


def test_prereg_multiplicity_checked(tmp_path):
    prob, bp, truth = make_area(tmp_path)
    f = _fields(tmp_path, prob, bp, truth)
    bad = dict(f, multiplicity={"method": "bonferroni", "gate": "synth", "family": ["synth"]})
    assert any("holm" in x for x in pf.check(bad))
    bad = dict(f, multiplicity={"method": "holm", "gate": "synth", "family": ["other"]})
    assert any("gate must be" in x for x in pf.check(bad))
