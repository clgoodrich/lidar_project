"""Smoke tests for 6.3 on tiny synthetic rasters. Seconds, CPU only, no GPU training, no network.

Run
    python -m pytest -q expansions/6_adjacent/6_3_confuser_classes/src/test_6_3.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _confuser_agreement_9t as AG  # noqa: E402
import _confuser_common_9t as C  # noqa: E402
import _confuser_pooled_score_9t as PS  # noqa: E402
import _confuser_sample_9t as S1  # noqa: E402
import _confuser_sheets_9t as S2  # noqa: E402
import _confuser_unet_cv5_9t as TR  # noqa: E402

CRS = "EPSG:6346"
X0, Y0 = 600000.0, 4590000.0
NB = 6          # six 50 m blocks in a row, 1 m cells


def _tif(path, arr, nodata=None):
    import rasterio
    from rasterio.transform import from_origin
    arr = arr if arr.ndim == 3 else arr[None]
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[2], height=arr.shape[1], count=arr.shape[0],
                       dtype=arr.dtype, crs=CRS, transform=from_origin(X0, Y0 + 50, 1.0, 1.0), nodata=nodata) as r:
        r.write(arr)
    return path


@pytest.fixture()
def world(tmp_path):
    import geopandas as gpd
    from shapely.geometry import box
    blocks = gpd.GeoDataFrame({"block_id": list(range(NB))},
                              geometry=[box(X0 + 50 * i, Y0, X0 + 50 * (i + 1), Y0 + 50) for i in range(NB)], crs=CRS)
    blocks.to_file(tmp_path / "blocks.gpkg", layer="blocks")
    rng = np.random.default_rng(0)
    boxes = [box(X0 + 5 + 9 * i, Y0 + 20, X0 + 9 + 9 * i, Y0 + 24) for i in range(30)]
    cand = gpd.GeoDataFrame({"cand_id": range(30), "score": rng.uniform(0.5, 0.95, 30), "fold": 0},
                            geometry=boxes, crs=CRS)
    cand.iloc[:20].to_file(tmp_path / "cand.gpkg", layer="undecided")
    cand.iloc[20:].to_file(tmp_path / "cand.gpkg", layer="matched")
    pd.DataFrame({"block_id": [5], "role": "audit"}).to_csv(tmp_path / "audit.csv", index=False)
    _tif(tmp_path / "hs.tif", rng.uniform(0, 255, (50, 300)).astype(np.float32))
    _tif(tmp_path / "slope.tif", rng.uniform(0, 30, (50, 300)).astype(np.float32))
    _tif(tmp_path / "relief.tif", rng.normal(0, 0.3, (50, 300)).astype(np.float32))
    _tif(tmp_path / "feat.tif", rng.normal(5, 2, (7, 50, 300)).astype(np.float32))
    lbl = np.zeros((50, 300), np.uint8)
    lbl[26:30, 10:14] = 1
    _tif(tmp_path / "lbl.tif", lbl)
    cfg = C.load_config()
    for k, f in (("candidates", "cand.gpkg"), ("blocks", "blocks.gpkg"), ("audit_blocks", "audit.csv"),
                 ("hillshade", "hs.tif"), ("slope", "slope.tif"), ("relief", "relief.tif"),
                 ("features", "feat.tif"), ("labels_pit", "lbl.tif")):
        cfg["inputs"][k] = {**cfg["inputs"][k], "path": str(tmp_path / f)}
    cfg["inputs"]["aerial"] = {"path": str(tmp_path / "none.tif"), "optional": True}
    cfg["sample"].update(n_total=10, n_pilot=5)
    return cfg, tmp_path, blocks, cand


def test_sample_excludes_audit_and_weights(world):
    cfg, tmp, *_ = world
    csv, s = S1.build(cfg, tmp)
    assert len(s) == 10 and not s.block_id.isin([5]).any()
    assert np.allclose(s.groupby("band").incl_prob.first() * s.groupby("band").N_band.first(), 2)
    assert s.relabel.sum() == 1
    csv2, s2 = S1.build(cfg, tmp)
    assert s.uid.tolist() == s2.uid.tolist()          # QC 5d, same config same output


def test_sheets_blind(world):
    cfg, tmp, *_ = world
    csv, s = S1.build(cfg, tmp)
    r = S2.build(cfg, tmp, csv, ["a", "b"], limit=2)
    assert len(r["sheets"]) == 2 and r["sheets"][0].exists()
    lab = pd.read_csv(r["labels"])
    assert "score" not in lab.columns and "uid" not in lab.columns and len(lab) == 20


def test_agreement_and_adjudication(world):
    cfg, tmp, *_ = world
    csv, s = S1.build(cfg, tmp)
    S2.build(cfg, tmp, csv, ["a", "b"], limit=1)
    key = pd.read_csv(tmp / "confuser_sheet_key_9t.csv")
    ids = key.sheet_id.tolist()
    la = ["C"] * 5 + ["P"] * 5
    lb = ["C"] * 4 + ["Q"] + ["P"] * 4 + ["U"]
    labels = pd.DataFrame({"sheet_id": ids * 2, "reviewer": ["a"] * 10 + ["b"] * 10, "class": la + lb,
                           "minutes": 6})
    adj = pd.DataFrame({"sheet_id": [ids[4]], "class": ["Q"]})
    res, q, final = AG.agreement(cfg, labels, key, s, adj)
    assert res["percent_agreement"] == 0.8 and len(q) == 2
    assert final.set_index("sheet_id").loc[ids[9], "class"] == "U"       # unresolved stays U
    assert final.set_index("sheet_id").loc[ids[4], "class"] == "Q"
    with pytest.raises(AssertionError, match="codebook"):
        AG.agreement(cfg, labels.assign(**{"class": "Z"}), key, s)


def test_trainer_leakage_and_arms(world, tmp_path):
    cfg, tmp, blocks, cand = world
    split = pd.DataFrame({"fold": 0, "role": ["train", "train", "train", "inner_val", "held_out"],
                          "block_id": [0, 1, 2, 3, 4]})
    fb = TR.fold_blocks(split, 0, [5])
    with pytest.raises(AssertionError, match="audit"):
        TR.fold_blocks(split, 0, [1])
    polys = cand.iloc[:6][["geometry"]].assign(**{"class": "C"})
    tr = list(blocks.loc[blocks.block_id.isin(fb["train"])].geometry)
    nc = TR.negative_centres("confuser", polys, tr, 1)
    nr = TR.negative_centres("random", polys, tr, 1)
    assert len(nc) == len(nr) == 6 and len(TR.negative_centres("baseline", polys, tr, 1)) == 0
    info = TR.burn_confuser_labels(tmp / "lbl.tif", polys, tmp / "lbl_conf.tif")
    assert info["confuser_pixels"] > 0
    import rasterio
    with rasterio.open(tmp / "lbl_conf.tif") as r:
        a = r.read(1)
    assert set(np.unique(a)) == {0, 1, 3} and (a[26:30, 10:14] == 1).all()   # pit pixels never overwritten
    _, Iso = TR.import_trainers()
    with rasterio.open(tmp / "feat.tif") as r:
        tf = r.transform
    smp = Iso(feat_path=tmp / "feat.tif", lbl_path=tmp / "lbl.tif", policies=[("pit", nc, 2.0)],
              block_bounds=np.array([g.bounds for g in tr]), transform=tf, mu=np.zeros(7, np.float32),
              sd=np.ones(7, np.float32), patch=16, augment=False, seed=3,
              forbid=list(blocks.loc[blocks.block_id.isin([3, 4, 5])].geometry))
    mu, sd, n = TR.fold_stats(smp, 20, 7)
    assert n > 0 and np.allclose(mu, 5, atol=0.5) and np.allclose(sd, 2, atol=0.5)


def test_pooled_scoring(world, tmp_path):
    cfg, tmp, blocks, _ = world
    import geopandas as gpd
    root = tmp / "models"
    rng = np.random.default_rng(1)
    for arm in ("baseline", "confuser", "random"):
        for s in (0, 1, 2):
            for k in (0, 1):
                prob = rng.uniform(0, 0.05, (50, 300)).astype(np.float32)
                prob[26:30, 10:14] = 0.9                                   # the drawn pit, found by all arms
                if arm != "confuser":
                    prob[10:14, 60:64] = 0.8                              # a confuser the confuser arm drops
                d = root / arm / f"seed{s}" / f"fold{k}"
                d.mkdir(parents=True)
                _tif(d / f"pit_prob_floor_cvfold{k}_9t_05.tif", prob)
    ab = blocks[blocks.block_id.isin([0, 1])].reset_index(drop=True)
    parts = []
    for arm in ("baseline", "confuser", "random"):
        for s in (0, 1, 2):
            g = PS.arm_candidates(PS.prob_paths(root, arm, s), ab, CRS, cfg["score"])
            top, k = C.top_k(g, float(ab.area.sum() / 1e6), 400)
            parts.append(top.assign(arm=arm, seed=s))
    mem, blind = PS.pool(gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS), 5.0)
    assert len(blind) == 2 and "arm" not in blind.columns
    pit_id = mem.loc[mem.geometry.centroid.x < X0 + 20, "pooled_id"].iloc[0]
    labels = pd.DataFrame({"uid": blind.uid, "class": ["P" if u == pit_id else "C" for u in blind.uid]})
    truth = gpd.GeoDataFrame({"truth_id": [1]}, geometry=[__import__("shapely").geometry.box(
        X0 + 10, Y0 + 20, X0 + 14, Y0 + 24)], crs=CRS)
    tab = PS.per_block_table(mem, labels, truth, ab, cfg)
    with pytest.raises(C.MissingInput, match="prespecify"):
        PS.score(cfg, tab, mem, labels, B=50)
    cfg["score"]["recall_margin_delta"] = 0.05
    res = PS.score(cfg, tab, mem, labels, B=50)
    assert res["primary_1_reduction"]["point"] > 0 and res["primary_2_recall_diff"]["point"] == 0
    assert res["suppressed_vs_baseline"]["P"] == 0 and "permutation_p_reduction" in res
