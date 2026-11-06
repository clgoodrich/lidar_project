"""Smoke tests for 6.2 on tiny synthetic data. Seconds, CPU only, no GPU training, no network.

Run
    python -m pytest -q expansions/6_adjacent/6_2_coal_features/src/test_6_2.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _coal_candidates_coal as S1  # noqa: E402
import _coal_common as K  # noqa: E402
import _coal_confusion_coal as S3  # noqa: E402
import _coal_inventory_audit_coal as S0b  # noqa: E402
import _coal_inventory_sample_coal as S0a  # noqa: E402
import _coal_label_sheets_coal as S2  # noqa: E402
import _coal_reverse_confusion_9t as S5  # noqa: E402
import _coal_unet_cv5_coal as S4  # noqa: E402

CRS = "EPSG:6346"
X0, Y0 = 580000.0, 4400000.0


def _tif(path, arr):
    import rasterio
    from rasterio.transform import from_origin
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1, dtype=arr.dtype,
                       crs=CRS, transform=from_origin(X0, Y0 + 100, 1.0, 1.0)) as r:
        r.write(arr, 1)
    return path


@pytest.fixture()
def world(tmp_path):
    import geopandas as gpd
    from shapely.geometry import Point, box
    cfg = K.load_config()
    pts = [Point(X0 + 10 + 20 * i, Y0 + 50) for i in range(10)]
    gpd.GeoDataFrame({"OBJECTID": range(4), "FEATURE_TY": ["Portal", "ADIT", "unknown x", "Shaft"]},
                     geometry=pts[:4], crs=CRS).to_file(tmp_path / "open.gpkg")
    gpd.GeoDataFrame({"OBJECTID": range(3), "PROBLEM_TY": ["Gob Pile", "VALLEY FILL", "Spoil"]},
                     geometry=[p.buffer(6) for p in pts[4:7]], crs=CRS).to_file(tmp_path / "aml.gpkg")
    gpd.GeoDataFrame({"OBJECTID": range(3), "FEATURE_TY": ["Subsidence"] * 3},
                     geometry=[p.buffer(3) for p in pts[7:]], crs=CRS).to_file(tmp_path / "sub.gpkg")
    over = {"mine_openings": tmp_path / "open.gpkg", "aml_problem": tmp_path / "aml.gpkg",
            "subsidence_prone": tmp_path / "sub.gpkg"}
    for spec in cfg["mine_layers"]:
        spec["path"] = str(over[spec["name"]])
    blocks = K.make_blocks((X0, Y0, X0 + 200, Y0 + 100), 50, CRS)
    blocks.to_file(tmp_path / "blocks.gpkg", layer="blocks")
    prob = np.zeros((100, 200), np.float32)
    prob[46:54, 6:14] = 0.9                     # over the first portal
    prob[20:26, 150:156] = 0.7                   # over nothing listed
    _tif(tmp_path / "pit.tif", prob)
    _tif(tmp_path / "pad.tif", prob * 0.8)
    for k, v in (("blocks", "blocks.gpkg"), ("pit_prob", "pit.tif"), ("pad_prob", "pad.tif"),
                 ("features", "pit.tif")):
        cfg["inputs"][k] = {**cfg["inputs"][k], "path": str(tmp_path / v)}
    cfg["inputs"]["audit_blocks"] = {"path": str(tmp_path / "audit.csv"), "state": "test"}
    cfg["inputs"]["split_file"] = {"path": str(tmp_path / "split.csv"), "state": "test"}
    return cfg, tmp_path, blocks


def test_type_map_and_tolerance(world):
    cfg, tmp, blocks = world
    rec, unmapped = K.read_mine_layers(cfg)
    assert rec.cls.value_counts().to_dict() == {"M": 3, "H": 3, "S": 3}
    assert unmapped == {"mine_openings": {"unknown x": 1}}
    assert rec.valley_fill.sum() == 1
    from shapely.geometry import Point
    tol = cfg["tolerance"]
    assert K.class_match("M", Point(0, 0).buffer(2), Point(25, 0), tol)
    assert not K.class_match("M", Point(0, 0).buffer(2), Point(35, 0), tol)
    assert K.class_match("S", Point(0, 0).buffer(5), Point(1, 0).buffer(5), tol)
    big = Point(0, 0).buffer(80)                                   # > 1 ha, centroid fallback
    assert K.class_match("H", Point(40, 0).buffer(3), big, tol)


def test_audit_draw_and_summary(world):
    cfg, tmp, blocks = world
    rec, _ = K.read_mine_layers(cfg)
    s, comp = S0a.draw(rec, blocks, 2, 3, 1)
    assert s.groupby("cls").size().to_dict() == {"H": 2, "M": 2, "S": 2} and len(comp) == 3
    s["identity"] = ["same", "same", "same", "nothing", "same", "same"]
    s["offset_m"] = [4, 8, 6, 0, 3, 5]
    comp[["n_visible_M", "n_matched_M", "n_visible_S", "n_matched_S", "n_visible_H", "n_matched_H"]] = [4, 3, 1, 1, 0, 0]
    res = S0b.summarise(cfg, s, comp)
    m = res["per_class"]["M"] if "M" in res["per_class"] else None
    assert m is not None and res["completeness"]["M"]["visible"] == 12
    assert all(v["exploratory"] for v in res["per_class"].values())


def test_candidates_sample_confusion(world):
    cfg, tmp, blocks = world
    res = S1.well_candidates(cfg, blocks)
    assert len(res["pit"]) == 2 and len(res["pad"]) == 2
    out = tmp / "cands.gpkg"
    for m, g in res.items():
        g.to_file(out, layer=m)
    cfg["inputs"]["candidates"] = {**cfg["inputs"]["candidates"], "path": str(out)}
    import _confuser_sample_9t as CS
    cands = CS.load_candidates(cfg)
    audit = S2.freeze_audit(cfg, blocks)
    assert audit == S2.freeze_audit(cfg, blocks)             # frozen, never redrawn
    rec, _ = K.read_mine_layers(cfg)
    cfg["sample"].update(n_total=10, n_random_candidates=3, per_class_audit=2)
    s = S2.draw(cfg, cands, rec, blocks, audit)
    assert set(s.source) <= {"candidate", "inventory record", "random point"} and s.incl_prob.notna().all()
    assert not s.block_id.dropna().isin(audit).any()
    cands["model"] = cands.src_layer
    cxy = np.column_stack([cands.geometry.centroid.x, cands.geometry.centroid.y])
    cands["block_id"], cands["cx"], cands["cy"] = K.C.block_of_points(cxy, blocks), cxy[:, 0], cxy[:, 1]
    top = S3.topk_per_model(cands, blocks, 1000)
    labels = pd.DataFrame({"uid": top.uid, "class": ["M" if x < X0 + 50 else "O" for x in top["cx"]]})
    mat, r, missing = S3.confusion(top, labels.iloc[:-1], cfg, blocks, B=50)
    assert len(missing) == 1 and mat.loc["M"].sum() >= 1
    assert r["per_model"]["pit"]["role"] == "primary"
    assert S3.render(mat, tmp / "conf.png").exists()


def test_burn_split_reverse(world):
    import geopandas as gpd
    from shapely.geometry import box
    cfg, tmp, blocks = world
    polys = gpd.GeoDataFrame({"class": ["M", "S", "W", "H"], "uid": list("abcd")},
                             geometry=[box(X0 + 5, Y0 + 5, X0 + 10, Y0 + 10), box(X0 + 60, Y0 + 5, X0 + 66, Y0 + 11),
                                       box(X0 + 110, Y0 + 60, X0 + 115, Y0 + 65), box(X0 + 160, Y0 + 60, X0 + 170, Y0 + 70)],
                             crs=CRS)
    v = S4.burn(tmp / "pit.tif", polys, tmp / "mine.tif", "mine")
    assert set(v) == {0, 1, 2, 3}
    w = S4.burn(tmp / "pit.tif", polys, tmp / "wn.tif", "wellneg")
    assert set(w) == {0, 3, 255}
    cxy = np.column_stack([polys.geometry.centroid.x, polys.geometry.centroid.y])
    man = pd.DataFrame({"cls": polys["class"], "block_id": K.C.block_of_points(cxy, blocks)})
    split = S4.make_split(cfg, man, blocks, [7], 3, 5)
    assert not split.block_id.isin([7]).any()
    for f in range(3):
        f_ = split[split.fold == f]
        assert not set(f_[f_.role == "train"].block_id) & set(f_[f_.role == "held_out"].block_id)
    mu, sd = S4.pooled_stats([(np.array([0.0]), np.array([1.0]), 10), (np.array([2.0]), np.array([1.0]), 10)])
    assert np.isclose(mu[0], 1.0) and np.isclose(sd[0], np.sqrt(2.0))
    pits = gpd.GeoDataFrame({"truth_id": [1, 2]}, geometry=[box(X0 + 6, Y0 + 46, X0 + 14, Y0 + 54),
                                                            box(X0 + 100, Y0 + 10, X0 + 104, Y0 + 14)], crs=CRS)
    pits["block_id"] = K.C.block_of_points(np.column_stack([pits.geometry.centroid.x, pits.geometry.centroid.y]), blocks)
    cands = S1.well_candidates(cfg, blocks)["pit"]
    p, k = S5.reverse_hits(cands, pits, blocks, 0.3, 1000)
    assert p.hit_iou.tolist() == [True, False]
    res = S5.summarise(p, blocks, 50, 1)
    assert res["share_pits_called_mine"] == 0.5
