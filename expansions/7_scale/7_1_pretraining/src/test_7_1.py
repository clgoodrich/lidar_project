"""Smoke tests for 7.1 on tiny synthetic data. One CPU batch per objective. No real training, no network.

Run
    python -m pytest -q expansions/7_scale/7_1_pretraining/src/test_7_1.py -p no:cacheprovider
"""
from __future__ import annotations

import os

os.environ["CUDA_VISIBLE_DEVICES"] = ""          # CPU only, set before torch is imported

import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _ssl_pretrain_objectives_us as pt  # noqa: E402

CRS = "EPSG:6346"


def test_norm_valid_zero_nodata_nan_and_empty(tmp_path):
    import pytest
    import _ssl_corpus_chips_us as cc
    p = tmp_path / "stats.tif"
    _raster(p, np.array([[0, 2], [-9999, np.nan]]), nodata=-9999)
    idx = pd.DataFrame([dict(stack_path=str(p), row=0, col=0, size=2)])
    mu, sd = cc.norm_stats(idx, 1, 0, 1)
    np.testing.assert_allclose(mu, [1])
    np.testing.assert_allclose(sd, [1])
    _raster(p, np.full((2, 2), -9999), nodata=-9999)
    with pytest.raises(ValueError, match="valid observations"):
        cc.norm_stats(idx, 1, 0, 1)


def test_all_channels_and_complete_windows(tmp_path):
    import _ssl_corpus_chips_us as cc
    cfg = {"corpus": {"chip_px": 2, "stride_px": 2, "max_nodata_frac": 0.2}, "channels": ["a", "b"]}
    p = tmp_path / "bands.tif"
    a = np.ones((2, 2, 2)); a[1, 0, 0] = -9999
    _raster(p, a, nodata=-9999)
    rows, drops = cc.chips_for_window(p, "w", 3, cfg, None)
    assert rows == [] and drops["nodata"] == 1
    cfg["corpus"]["chip_px"] = 3
    assert cc.chips_for_window(p, "w", 3, cfg, None)[0] == []


def test_build_corpus_reprojects_exclusions(tmp_path):
    import geopandas as gpd
    import rasterio
    import pytest
    from shapely.geometry import box
    import _ssl_corpus_chips_us as cc
    cfg = _cfg(tmp_path)
    p = tmp_path / "mercator.tif"
    _raster(p, np.ones((7, 64, 64)), x0=-8900000, y1=5000000)
    with rasterio.open(p, "r+") as r:
        r.crs = "EPSG:3857"
        footprint = box(*r.bounds)
    exclusion = tmp_path / "exclusion.gpkg"
    gpd.GeoDataFrame(geometry=[footprint.buffer(1)], crs="EPSG:3857").to_crs(CRS).to_file(exclusion)
    cfg["inputs"]["corpus_exclusions"] = [{"key": "expansions", "rel": str(exclusion)}]
    windows = pd.DataFrame([dict(window_id="w", stack_path=str(p), ground_ppsm=3)])
    with pytest.raises(FileNotFoundError, match="no admitted chips"):
        cc.build_corpus(cfg, windows, tmp_path / "out")


def test_future_manifest_producer_contract_and_hash(tmp_path):
    import pytest
    import _ssl_label_subsets_9t as ls
    sys.path.insert(0, str(pt.ek.sub("p1", "src")))
    import _split_future_write_9t as producer
    tasks = {"pit": {"folds": {"0": {"train": [2], "inner_val": [3], "held_out": [4]}}}}
    p = tmp_path / "future.json"
    doc = {"schema": "wellsight.cv_splits.v1", "tasks": tasks, "content_sha256": producer.sc.lists_hash(tasks)}
    p.write_text(json.dumps(doc))
    assert ls.folds_future(p) == [{"fold": 0, "train": [2], "val": [3], "heldout": [4]}]
    doc["tasks"]["pit"]["folds"]["0"]["train"] = [4]
    p.write_text(json.dumps(doc))
    with pytest.raises(AssertionError, match="hash mismatch"):
        ls.folds_future(p)


def _raster(path, arr, x0=0.0, y1=150.0, res=0.5, nodata=np.nan, dtype="float32"):
    import rasterio
    from rasterio.transform import from_origin
    arr = arr if arr.ndim == 3 else arr[None]
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[2], height=arr.shape[1], count=arr.shape[0],
                       dtype=dtype, crs=CRS, transform=from_origin(x0, y1, res, res), nodata=nodata) as o:
        o.write(arr.astype(dtype))


def _cfg(tmp: Path) -> dict:
    import geopandas as gpd
    from shapely.geometry import box
    cfg = pt.load_cfg()
    a = lambda p: {"key": "expansions", "rel": str((tmp / p).resolve())}  # noqa: E731
    rng = np.random.default_rng(0)
    # corpus. Two windows away from the synthetic 9t footprint.
    for i, x0 in enumerate((1000.0, 2000.0)):
        _raster(tmp / f"win{i}.tif", rng.normal(i, 1, (7, 128, 128)), x0=x0)
    pd.DataFrame({"window_id": ["w0", "w1"], "stack_path": [str(tmp / "win0.tif"), str(tmp / "win1.tif")],
                  "ground_ppsm": [3.0, 9.0]}).to_csv(tmp / "windows.csv", index=False)
    # synthetic 9t. 3 x 3 blocks of 50 m, 300 x 300 px, pits as 4 m squares.
    blocks = gpd.GeoDataFrame({"block_id": list(range(9)), "n_feat": [2, 0, 3, 1, 2, 0, 4, 1, 2]},
                              geometry=[box(i * 50, j * 50, (i + 1) * 50, (j + 1) * 50) for j in range(3) for i in range(3)], crs=CRS)
    blocks.to_file(tmp / "blocks.gpkg", driver="GPKG")
    gpd.GeoDataFrame(geometry=[box(5000, 5000, 5001, 5001)], crs=CRS).to_file(tmp / "far.gpkg", driver="GPKG")
    pits = [box(b.centroid.x - 2, b.centroid.y - 2, b.centroid.x + 2, b.centroid.y + 2) for b in blocks.geometry]
    gpd.GeoDataFrame(geometry=pits, crs=CRS).to_file(tmp / "ann.gpkg", layer="pit_inside", driver="GPKG")
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    lbl = rasterize([(p, 1) for p in pits], out_shape=(300, 300), transform=from_origin(0, 150, 0.5, 0.5)).astype("uint8")
    _raster(tmp / "lbl.tif", lbl, nodata=255, dtype="uint8")
    feat = rng.normal(0, 1, (7, 300, 300)); feat[0] -= lbl * 2
    _raster(tmp / "feat.tif", feat)
    pd.DataFrame({"fold": [0, 0, 0, 1, 1, 1, 2, 2, 2], "role": "held_out", "block_id": list(range(9))}).to_csv(tmp / "hist.csv", index=False)
    cfg["inputs"].update(feature_stack_9t=a("feat.tif"), labels_pit_9t=a("lbl.tif"), blocks_9t=a("blocks.gpkg"),
                         split_historical=a("hist.csv"), corpus_windows=a("windows.csv"),
                         corpus_exclusions=[a("blocks.gpkg"), a("far.gpkg")], audit_blocks=a("none.csv"))
    cfg["inputs"]["truth"] = {**a("ann.gpkg"), "layer": "pit_inside"}
    cfg["corpus"].update(chip_px=64, stride_px=48, norm_sample_chips=20)
    cfg["pretrain"]["contrast"].update(embed_dim=8, pixels_per_chip=16)
    cfg["finetune"].update(seeds=[0], fractions=[0.5, 1.0], inner_val_share_historical=0.2)
    return cfg


def test_corpus_pretrain_probe(tmp_path):
    import _ssl_corpus_chips_us as cc
    import _ssl_identity_probe_us as ip
    cfg = _cfg(tmp_path)
    s = cc.build_corpus(cfg, pd.read_csv(tmp_path / "windows.csv"), tmp_path / "proc")
    assert s["n_chips"] > 0
    idx = pd.read_csv(tmp_path / "proc" / "ssl_chip_index_us.csv")
    st = np.load(tmp_path / "proc" / "ssl_norm_stats_us.npz")
    for arm in ("A1", "A2", "A3"):
        ck = pt.pretrain(arm, 0, idx, st["mu"], st["sd"], cfg, tmp_path / arm, device="cpu", max_steps=1, batch=2, epochs=1)
        assert ck.exists()
        log = pd.read_csv(tmp_path / arm / "pretrain_log.csv")
        assert np.isfinite(log["loss"]).all()
        if arm != "A2":
            assert "mean_fill_l1" in log.columns
    Z, sub, _ = ip.embed(tmp_path / "A2" / "ssl_A2_seed0.pt", idx, st["mu"], st["sd"], 20, 0)
    res = ip.probe(Z, sub, 0)
    assert res["n_windows"] == 2


# columns of the real fine-tune outputs that the curve analysis reads (checked against ft.run output below)
OOF_CAND_COLS = ["cand_id", "block_id", "score", "area_m2", "matched_truth", "arm", "fraction", "seed"]
OOF_BLOCK_COLS = ["block_id", "n_truth", "area_km2", "arm", "fraction", "seed", "fold"]


def _p2_audit(tmp: Path, audit, buffer=(), freeze=True) -> Path:
    """Audit CSV written by the real P2 writer (write_audit_csv), into tmp. freeze=True adds the .sha256
    sidecar the way P2 --freeze does, for this temp file only (the real audit set is never frozen here)."""
    sys.path.insert(0, str(pt.ek.EXP_ROOT / "0_prerequisites" / "p2_audit_set" / "src"))
    import _audit_draw_blocks_9t as dr
    ids = list(audit) + list(buffer)
    tab = pd.DataFrame({"block_id": ids, "dens_t": 0, "slope_t": 0})
    p = tmp / "audit_blocks_9t_v1.csv"
    dr.write_audit_csv(p, tab, {"audit": list(audit), "buffer": list(buffer), "share": 0.1}, "block", 100.0, 1)
    if freeze:
        Path(str(p) + ".sha256").write_text(f"{pt.ek.sha256(p)}  {p.name}\n", encoding="utf-8")
    return p


def test_missing_audit_refuses_unless_allowed(tmp_path):
    """7.1-01. A missing audit file never becomes an empty set. Pre-fix code trained on silently."""
    import pytest
    import _ssl_label_subsets_9t as ls
    import _ssl_finetune_pit_9t as ft
    cfg = _cfg(tmp_path)
    with pytest.raises(FileNotFoundError, match="audit set not frozen"):
        ls.audit_sets(cfg)
    with pytest.raises(ValueError, match="audit"):
        ls.build(cfg, historical=True)
    sub = ls.build(cfg, historical=True, audit=ls.audit_sets(cfg, allow_no_audit=True))
    assert sub["audit_guard"] == "no audit exclusion, exploratory" and sub["audit_sha256"] is None
    with pytest.raises(FileNotFoundError, match="audit set not frozen"):
        ft.run(cfg, "A0", 0, 1.0, 0, sub, None, device="cpu", epochs=1, samples=2, batch=1,
               base_dir=tmp_path / "runs", models_dir=tmp_path / "models")
    rd = ft.run(cfg, "A0", 0, 1.0, 0, sub, None, device="cpu", epochs=1, samples=2, batch=1, allow_no_audit=True,
                base_dir=tmp_path / "runs", models_dir=tmp_path / "models")
    assert json.loads((rd / "_CONFIG.json").read_text())["audit_guard"] == "no audit exclusion, exploratory"
    assert set(pd.read_csv(next(rd.glob("oof_blocks_*.csv")))["audit_guard"]) == {"no audit exclusion, exploratory"}


def test_audit_block_absent_from_oof_and_audit_once(tmp_path):
    """7.1-01 and 7.1-02. Audit CSV from the real P2 writer. Block 8 is sealed audit, block 7 is buffer.
    Fold 2 holds blocks 6, 7, 8 out (historical split in _cfg), so the expected scored set is {6, 7}."""
    import pytest
    import _ssl_label_subsets_9t as ls
    import _ssl_finetune_pit_9t as ft
    import _ssl_corpus_chips_us as cc
    import _ssl_curve_score_9t as cs
    cfg = _cfg(tmp_path)
    ap = _p2_audit(tmp_path, [8], [7])
    au = ls.audit_sets(cfg, ap)
    assert au["audit"] == {8} and au["buffer"] == {7} and au["sha256"] == pt.ek.sha256(ap)
    sub = ls.build(cfg, historical=True, audit=au)
    assert sub["audit_excluded"] == [8] and sub["buffer_excluded"] == [7]
    for f in sub["folds"]:
        assert not {7, 8} & set(f["train"] + f["val"]) and 8 not in f["heldout"]
        for k in (f"{f['fold']}|0|0.5", f"{f['fold']}|0|1.0"):
            assert not {7, 8} & set(sub["subsets"][k]["blocks"])
        a, b = set(sub["subsets"][f"{f['fold']}|0|0.5"]["blocks"]), set(sub["subsets"][f"{f['fold']}|0|1.0"]["blocks"])
        assert a <= b and not (b & set(f["heldout"]))
    assert next(f for f in sub["folds"] if f["fold"] == 2)["heldout"] == [6, 7]
    with pytest.raises(AssertionError, match="label subsets were built with audit"):
        ft.run(cfg, "A0", 2, 1.0, 0, {**sub, "audit_sha256": None}, None, device="cpu", epochs=1, samples=2, batch=1,
               audit_csv=ap, base_dir=tmp_path / "runs", models_dir=tmp_path / "models")
    cc.build_corpus(cfg, pd.read_csv(tmp_path / "windows.csv"), tmp_path / "proc")
    idx = pd.read_csv(tmp_path / "proc" / "ssl_chip_index_us.csv")
    st = np.load(tmp_path / "proc" / "ssl_norm_stats_us.npz")
    ck = pt.pretrain("A1", 0, idx, st["mu"], st["sd"], cfg, tmp_path / "A1", device="cpu", max_steps=1, batch=2, epochs=1)
    for arm, init in (("A0", None), ("A1", ck)):
        rd = ft.run(cfg, arm, 2, 1.0, 0, sub, init, device="cpu", epochs=1, samples=2, batch=1, audit_csv=ap,
                    base_dir=tmp_path / "runs", models_dir=tmp_path / "models")
        ob = pd.read_csv(next(rd.glob("oof_blocks_*.csv")))
        assert sorted(ob["block_id"]) == [6, 7], "the sealed audit block 8 must not be scored out of fold"
        assert set(ob["audit_guard"]) == {"P2 audit list applied"}
        assert set(OOF_BLOCK_COLS) <= set(ob.columns)
        assert set(OOF_CAND_COLS) <= set(pd.read_csv(next(rd.glob("oof_candidates_*.csv"))).columns)
        assert json.loads((rd / "_CONFIG.json").read_text())["audit_sha256"] == pt.ek.sha256(ap)
    # 7.1-02. --audit-once scores only the sealed audit blocks, from --predict-audit outputs.
    unfrozen = _p2_audit(tmp_path / "proc", [8], [7], freeze=False)
    with pytest.raises(FileNotFoundError):
        ft.predict_audit(cfg, tmp_path / "models" / "ft_A0_f1p0_s0_k2" / "best.pt", tmp_path / "none.csv", device="cpu")
    for arm in ("A0", "A1"):
        ft.predict_audit(cfg, tmp_path / "models" / f"ft_{arm}_f1p0_s0_k2" / "best.pt", ap, device="cpu",
                         base_dir=tmp_path / "audit_runs")
    ab = pd.concat([pd.read_csv(p) for p in (tmp_path / "audit_runs").rglob("audit_blocks_*.csv")])
    assert sorted(ab["block_id"]) == [8, 8] and set(ab["audit_sha256"]) == {pt.ek.sha256(ap)}
    cfg["finetune"]["primary_fraction"] = 1.0
    t = tmp_path / "t"; t.mkdir()
    with pytest.raises(cs.AuditRefused, match="no frozen hash"):
        cs.audit_once(cfg, tmp_path / "audit_runs", "A1", 50, t, unfrozen)
    with pytest.raises(cs.AuditRefused, match="G, finetune.audit_model_fold"):
        cs.audit_once(cfg, tmp_path / "audit_runs", "A1", 50, t, ap)
    assert not (t / "ssl_audit_lock.json").exists()
    cfg["G"], cfg["finetune"]["audit_model_fold"] = 0.05, 2
    res = cs.audit_once(cfg, tmp_path / "audit_runs", "A1", 50, t, ap)
    assert res["n_blocks"] == 1 and res["audit_opened"] is True
    assert res["decision"] == "void (fewer than 3 matched seeds)"
    lock = json.loads((t / "ssl_audit_lock.json").read_text())
    assert lock["audit_opened"] is True and lock["audit_sha256"] == pt.ek.sha256(ap)
    with pytest.raises(cs.AuditRefused, match="already opened"):
        cs.audit_once(cfg, tmp_path / "audit_runs", "A1", 50, t, ap)


def test_training_windows_resample_each_epoch():
    """7.1 minor. Pre-fix, index i drew the same window every epoch (rng seeded by index only)."""
    import _ssl_finetune_pit_9t as ft
    rng = np.random.default_rng(0)
    br = np.zeros((96, 96), "int32"); br[:, 48:] = 1
    feat, lbl = rng.normal(0, 1, (7, 96, 96)).astype("float32"), np.zeros((96, 96), "uint8")
    mu, sd = np.zeros(7, "float32"), np.ones(7, "float32")
    tr = ft.IsolatedPitDataset(feat, lbl, br, {0, 1}, set(), 32, 4, mu, sd, 5, augment=False)
    e1, e2 = tr[1][0].numpy(), tr[1][0].numpy()
    assert not np.array_equal(e1, e2), "a training window must be redrawn every epoch"
    tr2 = ft.IsolatedPitDataset(feat, lbl, br, {0, 1}, set(), 32, 4, mu, sd, 5, augment=False)
    assert np.array_equal(tr2[1][0].numpy(), e1), "epoch draws are reproducible from the child seed"
    va = ft.IsolatedPitDataset(feat, lbl, br, {0, 1}, set(), 32, 4, mu, sd, 5, augment=False, resample=False)
    assert np.array_equal(va[1][0].numpy(), va[1][0].numpy()), "validation windows stay fixed"


def _fake_oof(root: Path, hits: dict, seeds=(0, 1, 2)):
    """Out-of-fold tables in the ft.run schema (OOF_*_COLS) with deterministic hits. 20 blocks x 2 truth,
    0.05 km2 each, so K = 40 per km2 x 1 km2 = 40 >= every candidate and recall = hits / 40 exactly.
    hits[(arm, f)] = n: blocks 0 .. n-1 have both truth found, the rest none."""
    for (arm, f), n in hits.items():
        for s in seeds:
            d = root / f"{arm}_{f}_{s}"; d.mkdir(parents=True)
            pd.DataFrame({"block_id": range(20), "n_truth": 2, "area_km2": 0.05, "arm": arm, "fraction": f,
                          "seed": s, "fold": [b % 5 for b in range(20)]}).to_csv(d / f"oof_blocks_{arm}.csv", index=False)
            rows = [{"cand_id": f"c{b}_{t}", "block_id": b, "score": 0.5, "area_m2": 10.0,
                     "matched_truth": f"t{b}_{t}" if b < n else None, "truth_block_id": b if b < n else None,
                     "arm": arm, "fraction": f, "seed": s}
                    for b in range(20) for t in range(2)]
            pd.DataFrame(rows).to_csv(d / f"oof_candidates_{arm}.csv", index=False)


def test_curves_G_from_config_never_floored(tmp_path):
    """7.2-01 pattern in 7.1, with exact verdicts. A0 recall 0.50 at f = 0.25 and 0.45 at f = 0.50, so
    G_raw = 0.45 - 0.50 = -0.05 by hand. A1 recall 0.90 at f = 0.25, diff +0.40. Per-block diff is 1 on
    8 of 20 blocks, so the 95% bootstrap interval is about 0.40 +- 0.21, far above G = 0.05 and far below 0.8."""
    import _ssl_curve_score_9t as cs
    cfg = _cfg(tmp_path)
    cfg["finetune"]["primary_fraction"] = 0.25
    _fake_oof(tmp_path / "fake", {("A0", 0.25): 10, ("A0", 0.5): 9, ("A0", 1.0): 12,
                                  ("A1", 0.25): 18, ("A1", 0.5): 18, ("A1", 1.0): 19})
    t, f = tmp_path / "t", tmp_path / "f"; t.mkdir(); f.mkdir()
    res = cs.analyse(cfg, tmp_path / "fake", "A1", 100, t, f)
    assert res["G"]["G"] is None and abs(res["G"]["G_raw"] - (-0.05)) < 1e-12, "G_raw reported, never floored"
    assert abs(res["primary"]["diff"] - 0.40) < 1e-12
    assert res["primary"]["decision"] == cs.G_UNSET, "an unset G is inconclusive, never a derived margin"
    cfg["G"] = 0.05
    res = cs.analyse(cfg, tmp_path / "fake", "A1", 100, t, f)
    assert res["G"]["source"].startswith("config") and res["primary"]["decision"] == "success"
    cfg["G"] = 0.8
    assert cs.analyse(cfg, tmp_path / "fake", "A1", 100, t, f)["primary"]["decision"] == "failure"
    cfg["G"] = None
    res = cs.analyse(cfg, tmp_path / "fake", "A1", 100, t, f, prereg={"G": 0.05, "_path": "prereg.json"})
    assert res["G"]["source"].startswith("preregistration") and res["primary"]["decision"] == "success"
    assert json.loads((t / "ssl_G_frozen_9t.json").read_text())["G_raw"] == res["G"]["G_raw"]


def test_runtime_bench_smoke(tmp_path):
    import _ssl_runtime_bench_9t as rb
    out = tmp_path / "bench.json"
    assert rb.main(["--device", "cpu", "--synthetic", "--steps", "1", "--batch-sizes", "1", "--patch-sizes", "32",
                    "--objectives", "A3", "supervised", "--out", str(out)]) == 0
    recs = json.loads(out.read_text())["records"]
    assert any("s3_loop_hours" in r for r in recs)
