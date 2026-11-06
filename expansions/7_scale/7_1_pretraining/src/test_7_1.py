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


def test_subsets_finetune_and_curves(tmp_path):
    import _ssl_label_subsets_9t as ls
    import _ssl_finetune_pit_9t as ft
    import _ssl_corpus_chips_us as cc
    import _ssl_curve_score_9t as cs
    cfg = _cfg(tmp_path)
    sub = ls.build(cfg, historical=True)
    for f in sub["folds"]:
        a, b = set(sub["subsets"][f"{f['fold']}|0|0.5"]["blocks"]), set(sub["subsets"][f"{f['fold']}|0|1.0"]["blocks"])
        assert a <= b and not (b & set(f["heldout"]))
    cc.build_corpus(cfg, pd.read_csv(tmp_path / "windows.csv"), tmp_path / "proc")
    idx = pd.read_csv(tmp_path / "proc" / "ssl_chip_index_us.csv")
    st = np.load(tmp_path / "proc" / "ssl_norm_stats_us.npz")
    ck = pt.pretrain("A1", 0, idx, st["mu"], st["sd"], cfg, tmp_path / "A1", device="cpu", max_steps=1, batch=2, epochs=1)
    for arm, init in (("A0", None), ("A1", ck)):
        rd = ft.run(cfg, arm, 0, 1.0, 0, sub, init, device="cpu", epochs=1, samples=2, batch=1, base_dir=tmp_path / "runs",
                    models_dir=tmp_path / "models")
        assert list(rd.glob("oof_candidates_*.csv")) and (rd / "_PROVENANCE.json").exists()
    # curve analysis on fabricated out-of-fold tables (3 seeds, 3 fractions, 2 arms)
    rng = np.random.default_rng(1)
    fake = tmp_path / "fake"
    for arm, lift in (("A0", 0.0), ("A1", 0.2)):
        for f in (0.25, 0.5, 1.0):
            for s in (0, 1, 2):
                d = fake / f"{arm}_{f}_{s}"; d.mkdir(parents=True)
                bl = pd.DataFrame({"block_id": range(20), "n_truth": 2, "area_km2": 0.05, "arm": arm,
                                   "fraction": f, "seed": s, "fold": [b % 5 for b in range(20)]})
                rows = []
                for b in range(20):
                    for t in range(2):
                        hit = rng.random() < min(0.95, 0.3 + 0.4 * f + lift)
                        rows.append({"cand_id": f"c{b}_{t}", "block_id": b, "score": rng.random(), "area_m2": 10.0,
                                     "matched_truth": f"t{b}_{t}" if hit else None, "arm": arm, "fraction": f, "seed": s})
                pd.DataFrame(rows).to_csv(d / f"oof_candidates_{arm}.csv", index=False)
                bl.to_csv(d / f"oof_blocks_{arm}.csv", index=False)
    (tmp_path / "t").mkdir(); (tmp_path / "f").mkdir()
    res = cs.analyse(cfg, fake, "A1", 200, tmp_path / "t", tmp_path / "f")
    assert res["primary"]["decision"] in ("success", "failure", "inconclusive")
    assert (tmp_path / "t" / "ssl_G_frozen_9t.json").exists()
    g1 = json.loads((tmp_path / "t" / "ssl_G_frozen_9t.json").read_text())["G"]
    cs.analyse(cfg, fake, "A1", 50, tmp_path / "t", tmp_path / "f")
    assert json.loads((tmp_path / "t" / "ssl_G_frozen_9t.json").read_text())["G"] == g1, "G must stay frozen"


def test_runtime_bench_smoke(tmp_path):
    import _ssl_runtime_bench_9t as rb
    out = tmp_path / "bench.json"
    assert rb.main(["--device", "cpu", "--synthetic", "--steps", "1", "--batch-sizes", "1", "--patch-sizes", "32",
                    "--objectives", "A3", "supervised", "--out", str(out)]) == 0
    recs = json.loads(out.read_text())["records"]
    assert any("s3_loop_hours" in r for r in recs)
