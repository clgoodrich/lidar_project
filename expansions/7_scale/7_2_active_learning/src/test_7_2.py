"""Smoke tests for 7.2 on tiny synthetic data. CPU only, no network, seconds.

Run
    python -m pytest -q expansions/7_scale/7_2_active_learning/src/test_7_2.py -p no:cacheprovider
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
import _al_policies_select_9t as ps  # noqa: E402

CRS = "EPSG:6346"


def _world(tmp: Path):
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from shapely.geometry import box
    nx, ny, bs, res = 6, 5, 50.0, 0.5
    W, H = int(nx * bs / res), int(ny * bs / res)
    tf = from_origin(0, ny * bs, res, res)
    blocks = gpd.GeoDataFrame({"block_id": list(range(nx * ny)), "n_feat": 3},
                              geometry=[box(i * bs, j * bs, (i + 1) * bs, (j + 1) * bs) for j in range(ny) for i in range(nx)], crs=CRS)
    blocks.to_file(tmp / "blocks.gpkg", driver="GPKG")
    rng = np.random.default_rng(3)
    pits, fakes = [], []
    for b in blocks.geometry:
        x0, y0 = b.bounds[:2]
        for _ in range(3):
            cx, cy = x0 + rng.uniform(8, 42), y0 + rng.uniform(8, 42)
            pits.append(box(cx - 2, cy - 2, cx + 2, cy + 2))
        cx, cy = x0 + rng.uniform(8, 42), y0 + rng.uniform(8, 42)
        fakes.append(box(cx - 2, cy - 2, cx + 2, cy + 2))
    gpd.GeoDataFrame(geometry=pits, crs=CRS).to_file(tmp / "ann.gpkg", layer="pit_inside", driver="GPKG")
    t = rasterize([(p, 1) for p in pits], out_shape=(H, W), transform=tf).astype("float32")
    f = rasterize([(p, 1) for p in fakes], out_shape=(H, W), transform=tf).astype("float32")
    for k in (0, 1):
        sc = rng.uniform(0.2, 0.9, size=len(pits))
        prob = rasterize([(p, s) for p, s in zip(pits, sc)], out_shape=(H, W), transform=tf, dtype="float32") * (rng.random(len(pits))[0] > -1)
        prob = np.maximum(prob, f * rng.uniform(0.2, 0.7))
        with rasterio.open(tmp / f"prob_fold{k}.tif", "w", driver="GTiff", width=W, height=H, count=1, dtype="float32",
                           crs=CRS, transform=tf, nodata=-1) as o:
            o.write(prob.astype("float32"), 1)
    with rasterio.open(tmp / "lbl.tif", "w", driver="GTiff", width=W, height=H, count=1, dtype="uint8", crs=CRS,
                       transform=tf, nodata=255) as o:
        o.write(t.astype("uint8"), 1)
    pd.DataFrame({"fold": [b % 2 for b in range(nx * ny)], "role": "held_out", "block_id": range(nx * ny)}).to_csv(tmp / "folds.csv", index=False)
    pd.DataFrame({"block_id": [29], "role": ["comparative_audit"]}).to_csv(tmp / "audit.csv", index=False)


def _cfg(tmp: Path) -> dict:
    cfg = ps.load_cfg()
    a = lambda p: {"key": "expansions", "rel": str((tmp / p).resolve())}  # noqa: E731
    cfg["inputs"].update(blocks=a("blocks.gpkg"), fold_blocks=a("folds.csv"), audit_blocks=a("audit.csv"),
                         discovery_extra_blocks=a("none.gpkg"), base_labels=a("lbl.tif"))
    cfg["inputs"]["truth"] = {**a("ann.gpkg"), "layer": "pit_inside"}
    cfg["inputs"]["oof_prob"] = {"key": "expansions", "rel": str((tmp / "prob_fold{k}.tif").resolve())}
    cfg["split"]["stopping_blocks"] = 6
    cfg.update(budget_minutes=240, batch_minutes=60)
    cfg["cost_minutes"].update(C=6.0, W=30.0)
    cfg["scoring"]["k_per_km2"] = 1600.0
    cfg["replay"].update(round0_items=10)
    return cfg


def test_poisson_pi_exact():
    w = np.array([0.5, 0.2, 0.2, 0.1])
    pi = ps.poisson_pi(w, np.array([6, 6, 6, 6.0]), 12.0)
    assert abs((pi * 6).sum() - 12.0) < 1e-6 and (pi > 0).all() and (pi <= 1).all()
    items = pd.DataFrame({"item_id": list("abcd"), "score": [0.5, 0.1, 0.9, 0.45], "tile_id": [1, 1, 1, 2]})
    wu = ps.weights(items, {"weight": "entropy_softmax", "temperature": 0.25})
    assert wu.argmax() in (0, 3) and wu.min() > 0


def test_split_items_replay_curves(tmp_path):
    import geopandas as gpd
    import _al_split_pool_stop_9t as sp
    import _al_replay_sim_9t as rp
    import _al_curve_score_9t as cs
    _world(tmp_path)
    cfg = _cfg(tmp_path)
    blocks = gpd.read_file(tmp_path / "blocks.gpkg")
    split = sp.make_split(blocks, {29}, cfg, None, eligible=set(range(30)))
    assert 29 not in split["pool"] + split["discovery"] + split["stopping"]
    sys.path.insert(0, str(ps.ek.REPO / "notebooks" / "wellsight_v2"))
    from _common import read_layer
    truth = read_layer(tmp_path / "ann.gpkg", "pit_inside")
    r = sp.build_items(cfg, blocks, split, pd.read_csv(tmp_path / "folds.csv"), truth, lambda k: tmp_path / f"prob_fold{k}.tif")
    assert set(r["items"]["type"]) == {"C", "W"} and len(r["stop_blocks"]) == 6
    cur, scores, incl = rp.replay(cfg, r["items"], r["oracle"], r["stop_cands"], r["stop_blocks"], split,
                                  ["R", "U", "D", "H", "B"], n_seeds=3)
    assert cur["cum_minutes"].max() >= cfg["budget_minutes"] - cfg["batch_minutes"]
    assert (incl["pi"] > 0).all()
    (tmp_path / "t").mkdir(); (tmp_path / "f").mkdir()
    # G_raw by hand. Control R, mean over seeds of recall at the last round within the budget minus within 75%.
    R = cur[cur["policy"] == "R"]
    at = lambda m: np.mean([g[g["cum_minutes"] <= m].sort_values("round")["recall_stop"].iloc[-1]  # noqa: E731
                            for _, g in R.groupby("seed")])
    g_raw = at(cfg["budget_minutes"]) - at(0.75 * cfg["budget_minutes"])
    # stop round by hand. First round whose R mean recall moved under delta for the second round in a row.
    m = R.groupby("round")["recall_stop"].mean()
    small = (m.diff().abs() < cfg["stop"]["delta"]).to_numpy()
    stop_hand = next((int(m.index[i]) for i in range(1, len(m)) if small[i] and small[i - 1]), None)
    assert cfg["G"] is None
    res = cs.analyse(cfg, cur, scores, incl, r["stop_cands"], r["stop_blocks"], r["oracle"], 100, tmp_path / "t", tmp_path / "f")
    assert res["G"]["G"] is None and abs(res["G"]["G_raw"] - g_raw) < 1e-12, "G_raw is reported unfloored"
    assert res["primary"]["decision"] == cs.G_UNSET, "7.2-01. An unset G is inconclusive, never derived"
    assert res["stop_rule"]["enforced"] is True
    if stop_hand is not None:
        assert res["stop_rule"]["round"] == stop_hand and res["stop_rule"]["rounds_kept"] == stop_hand
    else:
        assert res["stop_rule"]["rounds_kept"] == res["stop_rule"]["rounds_run"]
    cfg["G"] = 1.0                                   # a recall difference can never reach 1, so hi < G
    assert cs.analyse(cfg, cur, scores, incl, r["stop_cands"], r["stop_blocks"], r["oracle"], 100, tmp_path / "t",
                      tmp_path / "f")["primary"]["decision"] == "failure"
    cfg["G"] = None
    res = cs.analyse(cfg, cur, scores, incl, r["stop_cands"], r["stop_blocks"], r["oracle"], 100, tmp_path / "t",
                     tmp_path / "f", prereg={"G": 1.0, "_path": "prereg.json"})
    assert res["G"]["source"].startswith("preregistration") and res["primary"]["decision"] == "failure"
    assert "pool_recall" in res["discovery"]
    assert (tmp_path / "f" / "al_replay_curves_minutes_9t.png").exists()


def test_replay_default_is_preregistered_ten_seeds():
    import inspect
    import _al_replay_sim_9t as rp
    assert ps.load_cfg()["replay"]["seeds"] == 10
    assert inspect.signature(rp.replay).parameters["n_seeds"].default is None, "None reads the config (10)"


def test_timer_minutes():
    import _al_review_timer_minutes as tm
    ev = pd.DataFrame({"timestamp": ["2026-11-05T10:00:00", "2026-11-05T10:03:00", "2026-11-05T10:10:00",
                                     "2026-11-05T10:30:00", "2026-11-05T11:00:00", "2026-11-05T11:00:05"],
                       "reviewer": "r1", "item_id": ["a", "a", "b", "b", "c", "c"],
                       "event": ["start", "stop", "start", "stop", "start", "stop"]})
    m = tm.minutes(ev).set_index("item_id")
    assert m.loc["a", "minutes"] == 3 and m.loc["b", "minutes"] == 5, "idle gaps are cut at 5 minutes"
    assert "under_10s" in m.loc["c", "flag"]


def test_review_package_ingest(tmp_path, monkeypatch):
    import geopandas as gpd
    import _al_split_pool_stop_9t as sp
    import _al_review_round_9t as rr
    _world(tmp_path)
    cfg = _cfg(tmp_path)
    blocks = gpd.read_file(tmp_path / "blocks.gpkg")
    split = sp.make_split(blocks, {29}, cfg, None, eligible=set(range(30)))
    sys.path.insert(0, str(ps.ek.REPO / "notebooks" / "wellsight_v2"))
    from _common import read_layer
    r = sp.build_items(cfg, blocks, split, pd.read_csv(tmp_path / "folds.csv"), read_layer(tmp_path / "ann.gpkg", "pit_inside"),
                       lambda k: tmp_path / f"prob_fold{k}.tif")
    rd = tmp_path / "round_01"; rd.mkdir()
    sel = ps.select_round(r["items"], split, set(), ["U", "H"], cfg, 1, cfg["master_seed"], "m0")
    for p, d in sel.items():
        d[d["selected"]].to_csv(rd / f"batch_{p}.csv", index=False)
    monkeypatch.setattr(rr, "interim_dir", lambda: tmp_path)
    rev = rr.package(rd, r["items_geo"], cfg, 1)
    # the reviewer draws two missed pits. One inside a window H selected, one in no window.
    hw = sel["H"][sel["H"]["selected"] & (sel["H"]["type"] == "W")]["item_id"]
    assert len(hw), "fixture needs H to draw at least one discovery window"
    wgeo = r["items_geo"].set_index("item_id").loc[hw.iloc[0], "geometry"]
    from shapely.geometry import box
    cx, cy = wgeo.centroid.x, wgeo.centroid.y
    import pyogrio
    add = gpd.GeoDataFrame({"status": ["added", "added"], "note": ["", ""]},
                           geometry=[box(cx - 1, cy - 1, cx + 1, cy + 1), box(-50, -50, -48, -48)], crs=r["items_geo"].crs)
    pyogrio.write_dataframe(add, rev / "added_pits_al_r01.gpkg", layer="added", geometry_type="Polygon")
    g = gpd.read_file(rev / "review_pits_al_r01.gpkg", layer="review")
    assert set(g.columns) == {"pit_inside_id", "status", "geometry"}, "the sheet must hide score and policy"
    g.loc[g.index[0], "status"] = "reject"
    g.to_file(rev / "review_pits_al_r01.gpkg", layer="review", driver="GPKG")
    lab = rr.ingest(rd, cfg, 1, None)
    assert (lab["status"] == "reject").sum() == 1 and lab.loc[lab["status"] == "reject", "y"].iloc[0] == 0
    # retrain inputs for policy U from the ingested round (trainer_cmd is null, so no training)
    import _al_retrain_round_9t as rt
    inc = pd.concat([d.assign(round=1) for d in sel.values()])
    inc[["item_id", "type", "policy", "round", "pi", "selected"]].to_csv(rd / "inclusion_log.csv", index=False)
    r["items_geo"].to_file(tmp_path / "items.gpkg", driver="GPKG")
    (tmp_path / "split.json").write_text(json.dumps(split))
    args = lambda pol: ["--config", str(tmp_path / "cfg.json"), "--round", "1", "--policy", pol, "--live",  # noqa: E731
                        str(tmp_path), "--split", str(tmp_path / "split.json"), "--items-geo", str(tmp_path / "items.gpkg")]
    (tmp_path / "cfg.json").write_text(json.dumps(cfg))
    assert rt.main(args("U")) == 2, "7.2-02. An undeclared seed set refuses the retrain"
    cfg["seed_label_blocks"] = []
    (tmp_path / "cfg.json").write_text(json.dumps(cfg))
    assert rt.main(args("U")) == 0
    man = json.loads((rd / "train_U" / "train_manifest.json").read_text())
    assert man["pixels"]["forbidden_px"] > 0 and (rd / "train_U" / "labels_U_r01.tif").exists()
    # 7.2-02. Only U's acquired labels train U. Pre-fix the base raster put every truth pit of the pool in.
    import rasterio
    from rasterio.features import rasterize
    with rasterio.open(rd / "train_U" / "labels_U_r01.tif") as src:
        out, tf = src.read(1), src.transform
    gi = r["items_geo"].set_index("item_id")
    labu = lab[lab["policies"].str.split(";").apply(lambda q: "U" in q)]
    acq = rasterize([(gi.loc[i, "geometry"], 1) for i in labu["item_id"]], out_shape=out.shape, transform=tf).astype(bool)
    assert (out[~acq] == 255).all(), "pixels outside U's acquired items must be ignore"
    with rasterio.open(tmp_path / "lbl.tif") as src:
        base = src.read(1)
    assert (base == 1).sum() > (out == 1).sum() + 1000
    assert man["n_added_kept"] == 0 and man["n_added_unattributed"] == 2, "U drew no window, so no addition is U's"
    assert rt.main(args("H")) == 0
    mh = json.loads((rd / "train_H" / "train_manifest.json").read_text())
    assert mh["n_added_kept"] == 1 and mh["n_added_unattributed"] == 1, "only the addition inside H's window is H's"
    # a declared seed block keeps its base labels exactly
    seed_b = split["pool"][0]
    cfg["seed_label_blocks"] = [seed_b]
    (tmp_path / "cfg.json").write_text(json.dumps(cfg))
    assert rt.main(args("U")) == 0
    with rasterio.open(rd / "train_U" / "labels_U_r01.tif") as src:
        out2 = src.read(1)
    bm = rasterize([(blocks.set_index("block_id").loc[seed_b, "geometry"], 1)], out_shape=out.shape, transform=tf).astype(bool)
    bm &= ~acq
    assert (out2[bm] == base[bm]).all() and (base[bm] == 1).any()
