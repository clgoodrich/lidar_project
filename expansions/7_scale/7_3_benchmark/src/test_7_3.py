"""Smoke tests for 7.3 on tiny synthetic data. CPU only, no network, seconds.

Run
    python -m pytest -q expansions/7_scale/7_3_benchmark/src/test_7_3.py -p no:cacheprovider
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
sys.path.insert(0, str(HERE.parents[2] / "_shared" / "src"))
import expkit as ek  # noqa: E402
import _bench_evaluate_recall_k as sc  # noqa: E402

CRS = "EPSG:6346"
BS = 50.0  # synthetic block size in metres


def _world(tmp: Path):
    """4x2 blocks of 50 m, a 2-band stack, a DEM, pits as 5 m squares, fold rasters for two models."""
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    nx, ny, res = 4, 2, 0.5
    W, H = int(nx * BS / res), int(ny * BS / res)
    tf = from_origin(0, ny * BS, res, res)
    blocks = gpd.GeoDataFrame({"block_id": list(range(nx * ny))},
                              geometry=[box(i * BS, j * BS, (i + 1) * BS, (j + 1) * BS) for j in range(ny) for i in range(nx)],
                              crs=CRS)
    blocks.to_file(tmp / "blocks.gpkg", driver="GPKG")
    rng = np.random.default_rng(0)
    pits = []
    for b in blocks.geometry:
        x0, y0 = b.bounds[:2]
        for _ in range(2):
            cx, cy = x0 + rng.uniform(10, 40), y0 + rng.uniform(10, 40)
            pits.append(box(cx - 2.5, cy - 2.5, cx + 2.5, cy + 2.5))
    gpd.GeoDataFrame(geometry=pits, crs=CRS).to_file(tmp / "ann.gpkg", layer="pit_inside", driver="GPKG")
    gpd.GeoDataFrame(geometry=[p.buffer(1) for p in pits], crs=CRS).to_file(tmp / "ann.gpkg", layer="pit_outside", driver="GPKG")
    gpd.GeoDataFrame(geometry=[blocks.geometry[0].centroid.buffer(8)], crs=CRS).to_file(tmp / "ann.gpkg", layer="plat", driver="GPKG")
    prof = dict(driver="GTiff", width=W, height=H, dtype="float32", crs=CRS, transform=tf, nodata=np.nan)
    with rasterio.open(tmp / "stack.tif", "w", count=2, **prof) as o:
        o.write(rng.normal(size=(2, H, W)).astype("float32"))
    with rasterio.open(tmp / "dem.tif", "w", count=1, **prof) as o:
        o.write(rng.normal(300, 1, size=(1, H, W)).astype("float32"))
    from rasterio.features import rasterize
    truth = rasterize([(p, 1) for p in pits], out_shape=(H, W), transform=tf).astype("float32")
    for name, noise in (("good", 0.05), ("bad", 0.45)):
        prob = np.clip(truth * 0.8 + rng.uniform(0, noise, (H, W)), 0, 1).astype("float32")
        with rasterio.open(tmp / f"{name}_fold1.tif", "w", count=1, **{**prof, "nodata": -1}) as o:
            o.write(prob, 1)
    pd.DataFrame({"fold": [0] * 4 + [1] * 4, "role": "held_out", "block_id": list(range(8))}).to_csv(tmp / "hist.csv", index=False)
    json.dump({"folds": [{"fold": 0, "heldout": [0, 1, 2]}, {"fold": 1, "heldout": [4, 5, 6]}], "buffer_blocks": [3]},
              open(tmp / "future.json", "w"))
    pd.DataFrame({"block_id": [7], "role": ["comparative_audit"]}).to_csv(tmp / "audit.csv", index=False)
    return blocks, gpd.GeoDataFrame(geometry=pits, crs=CRS)


def _cfg(tmp: Path) -> Path:
    cfg = json.loads((HERE / "config_7_3.json").read_text())
    a = lambda p: {"key": "expansions", "rel": str((tmp / p).resolve())}  # noqa: E731
    cfg["release_root"] = a("rel")
    cfg["inputs"].update(feature_stack=a("stack.tif"), dem=a("dem.tif"), blocks=a("blocks.gpkg"),
                         split_future=a("future.json"), audit_blocks=a("audit.csv"), split_historical=a("hist.csv"),
                         second_reviewer=a("none.gpkg"))
    cfg["inputs"]["annotations"] = {**a("ann.gpkg"), "layers": {"pit_floor": "pit_inside", "pit_full": "pit_full", "pad": "pad"}}
    cfg["baselines"] = {"good": {"task": "pit_floor", "fold_raster": a("good_fold{k}.tif"), "split_file": a("hist.csv")},
                        "bad": {"task": "pit_floor", "fold_raster": a("bad_fold{k}.tif"), "split_file": a("hist.csv")},
                        "absent": {"task": "pit_floor", "fold_raster": a("nope_fold{k}.tif"), "split_file": a("hist.csv")}}
    p = tmp / "cfg.json"
    p.write_text(json.dumps(cfg))
    return p


def test_scorer_matches_expkit(tmp_path):
    blocks, pits = _world(tmp_path)
    import rasterio
    with rasterio.open(tmp_path / "good_fold1.tif") as r:
        prob, tf = r.read(1), r.transform
    s, c = sc.evaluate([((prob, tf), None)], pits, blocks, B=20, k_per_km2=2000)
    ref = ek.recall_at_k(c["score"], c["matched_truth"], c["block_id"], {0: s["n_truth"]}, s["area_km2"],
                         k_per_km2=2000, areas=c["area_m2"], cand_ids=c["cand_id"])
    assert ref["hits"] == s["hits"] and ref["k"] == s["k"]
    assert s["recall"] > 0.9
    s2, _ = sc.evaluate([((prob, tf), None)], pits, blocks, B=20, k_per_km2=2000)
    assert json.dumps(sc._round({k: v for k, v in s.items() if k[0] != "_"}), sort_keys=True) == \
        json.dumps(sc._round({k: v for k, v in s2.items() if k[0] != "_"}), sort_keys=True)


def test_export_baselines_fresh_checkout(tmp_path):
    _world(tmp_path)
    import _bench_export_release_9t as ex
    import _bench_baselines_score_9t as bl
    import _bench_fresh_checkout_test as fc
    import _bench_card_datasheet_9t as ds
    cfg = ex.load_cfg(_cfg(tmp_path))
    summ = ex.export(cfg, tmp_path / "rel", provisional=False, max_tiles=None, devtest_fold=1)
    root = tmp_path / "rel" / "terrain_v1"
    assert summ["n_tiles"] == 8 and summ["roles"]["test"] == 1
    import geopandas as gpd
    for p in (root / "labels").glob("*.gpkg"):
        g = gpd.read_file(p, layer="pit_floor")
        assert not set(g["block_id"].astype(int)) & {3, 7}, "hidden or buffer label leaked"
    assert ex.verify_manifest(root) == []
    df = bl.run(cfg, root, B=20)
    assert set(df.loc[df.status == "scored", "model"]) == {"good", "bad"}
    assert "missing" in df.loc[df.model == "absent", "status"].iloc[0]
    md, _ = ds.build(cfg, root)
    assert "not measured" in md and "not wells" in md
    res = fc.fresh_check(root)
    assert res["pass"], res


def test_validity_and_leaderboard(tmp_path, monkeypatch):
    blocks, pits = _world(tmp_path)
    import rasterio
    import _bench_validity_checks_9t as va
    import _bench_leaderboard_submit_9t as lb
    arms = {}
    for name in ("good", "bad"):
        with rasterio.open(tmp_path / f"{name}_fold1.tif") as r:
            s, c = sc.evaluate([((r.read(1), r.transform), None)], pits, blocks, B=0, k_per_km2=2000)
        arms[name] = (c, s["_blocks"])
    same = va.paired_diff(arms["good"], arms["good"], 2000, 50, 0)
    assert same["point"] == 0 and same["lo"] == 0 and "permutation" in same
    w = va.h3_width(arms["good"], n_test=4, k_per_km2=2000, B=100, seed=0, reps=3)
    assert w >= 0
    monkeypatch.setattr(lb, "table_path", lambda: tmp_path / "subs.csv")
    tab = pd.DataFrame({"team": ["t"] * 3, "date": ["2026-10-01", "2026-10-20", "2026-11-01"]})
    with pytest.raises(PermissionError):
        lb.check_cap(tab, "t", pd.Timestamp("2026-11-05").date(), 3, 90)
    lb.check_cap(tab, "u", pd.Timestamp("2026-11-05").date(), 3, 90)
    md = lb.render(pd.DataFrame([dict(team="a", track="A", date="2026-11-01", recall=0.8, lo=0.7, hi=0.9,
                                      diff_vs_baseline=0.05, diff_lo=0.01, diff_hi=0.09, maintainer=True,
                                      transductive=False),
                                 dict(team="b", track="A", date="2026-11-02", recall=0.78, lo=0.7, hi=0.86,
                                      diff_vs_baseline=0.03, diff_lo=-0.01, diff_hi=0.07, maintainer=False,
                                      transductive=False)]), "terrain_v1")
    assert md.count("| 1 |") == 2, "overlapping intervals should tie"
