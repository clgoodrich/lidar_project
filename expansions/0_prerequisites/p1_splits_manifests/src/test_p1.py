"""Smoke tests for P1 on tiny synthetic data. CPU only, no network, seconds.

Run
    python -m pytest -q expansions/0_prerequisites/p1_splits_manifests/src/test_p1.py -p no:cacheprovider
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split_core_lib_9t as sc  # noqa: E402
import _split_future_write_9t as fw  # noqa: E402
import _split_sampler_leakage_9t as sl  # noqa: E402
import _split_buffer_derive_9t as bd  # noqa: E402
import _split_determinism_check_9t as dc  # noqa: E402


def test_isolated_trainer_actual_frozen_audit_guard(tmp_path):
    import hashlib
    import _pit_unet_iso_train_9t as trainer
    audit = tmp_path / "audit.csv"
    raw = b"# buffer_m=25\nblock_id,role\n9,audit\n10,buffer\n"
    audit.write_bytes(raw)
    Path(str(audit) + ".sha256").write_text(hashlib.sha256(raw).hexdigest())
    assert trainer.guard_lists(audit, {"train": [1], "inner_val": [2]}, 25) == [9, 10]
    with pytest.raises(AssertionError):
        trainer.guard_lists(audit, {"train": [9], "inner_val": [2]}, 25)
    with pytest.raises(AssertionError, match="below"):
        trainer.guard_lists(audit, {"train": [1], "inner_val": [2]}, 24)


def synth_manifest(tmp: Path, n_blocks=16, n_nan=7, seed=0) -> Path:
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_blocks):
        for _ in range(int(rng.integers(1, 6))):
            ix, iy = b % 4, b // 4
            rows.append(dict(pit_inside_id=len(rows), block_id=float(b), split="train",
                             centroid_x=ix * 25 + rng.uniform(3, 22), centroid_y=100 - iy * 25 - rng.uniform(3, 22)))
    for _ in range(n_nan):
        rows.append(dict(pit_inside_id=len(rows), block_id=np.nan, split="none", centroid_x=500.0, centroid_y=500.0))
    p = tmp / "manifest.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def synth_blocks():
    import geopandas as gpd
    from shapely.geometry import box
    g = [box(ix * 25, 100 - (iy + 1) * 25, (ix + 1) * 25, 100 - iy * 25) for iy in range(4) for ix in range(4)]
    return gpd.GeoDataFrame({"block_id": list(range(16))}, geometry=g, crs="EPSG:6346")


def synth_raster(tmp: Path, n_ch=7, size=200, res=0.5) -> Path:
    import rasterio
    from rasterio.transform import from_origin
    p = tmp / "feat.tif"
    rng = np.random.default_rng(1)
    with rasterio.open(p, "w", driver="GTiff", height=size, width=size, count=n_ch, dtype="float32",
                       crs="EPSG:6346", transform=from_origin(0, 100, res, res)) as d:
        d.write(rng.normal(2.0, 3.0, (n_ch, size, size)).astype(np.float32))
    return p


def test_fixed_split_drops_nan_and_is_valid(tmp_path):
    p = sc.task_params("pit")
    man = sc.load_manifest("pit", synth_manifest(tmp_path))
    s = sc.make_splits(man, 5, p["seed"], p["inner_val_frac"], p["assign_folds"], "fixed")
    assert sc.check_roles(s, set(range(16))) == []
    s2 = sc.make_splits(man, 5, p["seed"], p["inner_val_frac"], p["assign_folds"], "fixed")
    assert sc.fold_hashes(s) == sc.fold_hashes(s2)
    h = sc.make_splits(man, 5, p["seed"], p["inner_val_frac"], p["assign_folds"], "historical")
    assert any(None in r["inner_val"] + r["train"] for r in h.values())      # the NaN block is in the lists
    assert any("NaN" in x for x in sc.check_roles(h))


def test_determinism_across_processes(tmp_path):
    mp = synth_manifest(tmp_path)
    res = dc.run_check(2, {"pit": str(mp)}, k=5)
    assert res["gate"] == "pass" and res["by_task"]["pit"]["fixed"]["differing_folds"] == []


def test_split_file_write_verify_and_tamper(tmp_path):
    mp = synth_manifest(tmp_path)
    doc = fw.build({"pit": mp}, check_exporter=False)
    f = tmp_path / "splits.json"
    f.write_text(json.dumps(doc))
    assert fw.verify(f, manifests={"pit": mp}, check_exporter=False) == []
    assert fw.split_file_for("pit", f)[0]["held_out"] == doc["tasks"]["pit"]["folds"]["0"]["held_out"]
    bad = json.loads(f.read_text())
    bad["tasks"]["pit"]["folds"]["0"]["train"].append(999)
    f.write_text(json.dumps(bad))
    assert fw.verify(f, manifests={"pit": mp}, check_exporter=False)
    with pytest.raises(AssertionError):
        fw.split_file_for("pit", f)


def test_window_leak_geometry():
    from rasterio.transform import from_origin
    from shapely.geometry import box
    tf = from_origin(0, 100, 0.5, 0.5)
    boxes = sc.window_boxes([0, 0], [0, 50], 50, tf)        # x 0..25 and 25..50, y 75..100
    n, hit = sc.count_window_leaks(boxes, [box(25, 75, 50, 100)])
    assert n == 1 and hit.tolist() == [False, True]          # shared edge does not count


def test_sampler_leakage_isolated_is_zero(tmp_path):
    mp = synth_manifest(tmp_path)
    man = sc.load_manifest("pit", mp)
    blocks = synth_blocks()
    feat = synth_raster(tmp_path)
    doc = fw.build({"pit": mp}, check_exporter=False)
    splits = {int(f): v for f, v in doc["tasks"]["pit"]["folds"].items()}
    res = sl.leakage_for_task("pit", {0: splits[0], 1: splits[1]}, man, blocks, feat, n=300, buffer_m=0.0,
                              patch=32, jitter=5.0)
    assert all(v["isolated_leaking"] == 0 for v in res.values())
    assert sum(v["historical_leaking"] for v in res.values()) > 0


def test_semivariogram_and_range():
    rng = np.random.default_rng(0)
    z = rng.normal(size=(60, 60))
    lags, g, n = bd.semivariogram(z, np.ones_like(z, bool), 5.0, 25.0, 200.0)
    assert np.all(n > 0) and abs(np.nanmean(g) - 1.0) < 0.1      # white noise, gamma = variance
    sill, rng_m = bd.sill_and_range(lags, g)
    assert rng_m == lags[0]


def test_receptive_field_small_unet():
    sys.path.insert(0, str(sc.ek.REPO / "notebooks" / "wellsight_v2"))
    from _dl import UNet
    rf = sc.receptive_field_px(UNet(in_ch=2, n_classes=2, base=4), 2, size=256)
    assert 100 < rf["width_px"] < 256 and rf["radius_px"] > 50


def test_fold_norm_stats(tmp_path):
    import _pit_unet_iso_train_9t as tr
    feat = synth_raster(tmp_path, n_ch=3)
    mu, sd, n = tr.fold_norm_stats(feat, np.array([[0, 0], [50, 50]]), 64, 16, 3)
    assert np.allclose(mu, 2.0, atol=0.5) and np.allclose(sd, 3.0, atol=0.5) and (n == 512).all()


def test_split_excluding_audit_blocks(tmp_path):
    mp = synth_manifest(tmp_path)
    doc = fw.build({"pit": mp}, check_exporter=False, exclude={0, 5}, exclude_source="test")
    t = doc["tasks"]["pit"]
    assert t["excluded_audit_blocks"] == [0, 5] and t["n_blocks"] == 14
    assert not {0, 5} & {b for r in t["folds"].values() for v in r.values() for b in v}
    f = tmp_path / "v2.json"
    f.write_text(json.dumps(doc))
    assert fw.verify(f, manifests={"pit": mp}, check_exporter=False) == []
