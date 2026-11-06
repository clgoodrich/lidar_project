"""Tests for 7.3 on tiny synthetic data. CPU only, no network, seconds.

The P1 split and P2 audit inputs are written by the real producers (P1 _split_future_write_9t.build,
P2 _audit_draw_blocks_9t.write_audit_csv) into pytest temp folders, never into the real splits folder.

Run
    python -m pytest -q expansions/7_scale/7_3_benchmark/src/test_7_3.py -p no:cacheprovider
"""
from __future__ import annotations

import hashlib
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

PREREQ = HERE.parents[2] / "0_prerequisites"
CRS = "EPSG:6346"
BS = 50.0  # synthetic block size in metres
AUDIT_BLOCK, BUFFER_BLOCK = 7, 3


def _policy(task="pit_floor", **over):
    return {**ek.policy_for(task), **over}


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
        for k in (0, 1):
            with rasterio.open(tmp / f"{name}_fold{k}.tif", "w", count=1, **{**prof, "nodata": -1}) as o:
                o.write(prob, 1)
    pd.DataFrame({"fold": [0] * 4 + [1] * 4, "role": "held_out", "block_id": list(range(8))}).to_csv(tmp / "hist.csv", index=False)
    return blocks, gpd.GeoDataFrame(geometry=pits, crs=CRS)


def _producers(tmp: Path, roles=("audit", "buffer")):
    """P1 future split and P2 audit CSV written by the real producer code, plus a sha256 sidecar.
    Returns the P1 document (the independent oracle for the expected roles)."""
    sys.path.insert(0, str(PREREQ / "p1_splits_manifests" / "src"))
    sys.path.insert(0, str(PREREQ / "p2_audit_set" / "src"))
    import _split_future_write_9t as fw
    import _audit_draw_blocks_9t as dr
    rng = np.random.default_rng(3)
    rows = []
    for b in range(8):
        for _ in range(int(rng.integers(1, 5))):
            rows.append(dict(pit_inside_id=len(rows), block_id=float(b), split="train",
                             centroid_x=(b % 4) * BS + 25.0, centroid_y=(b // 4) * BS + 25.0))
    mp = tmp / "pit_manifest.csv"
    pd.DataFrame(rows).to_csv(mp, index=False)
    doc = fw.build({"pit": mp}, check_exporter=False)
    (tmp / "future.json").write_text(json.dumps(doc), encoding="utf-8")
    tab = pd.DataFrame({"block_id": [AUDIT_BLOCK], "dens_t": [1], "slope_t": [2]})
    res = {"audit": [AUDIT_BLOCK], "buffer": [BUFFER_BLOCK], "share": 0.15}
    p = tmp / "audit.csv"
    dr.write_audit_csv(p, tab, res, "block", 25.0, 20261104)
    if tuple(roles) != ("audit", "buffer"):            # a producer file with a role 7.3 does not know
        p.write_text(p.read_text(encoding="utf-8").replace(",audit,", f",{roles[0]},"), encoding="utf-8")
    Path(str(p) + ".sha256").write_text(hashlib.sha256(p.read_bytes()).hexdigest() + "  audit.csv\n")
    return doc


def _cfg(tmp: Path) -> Path:
    cfg = json.loads((HERE / "config_7_3.json").read_text())
    a = lambda p: {"key": "expansions", "rel": str((tmp / p).resolve())}  # noqa: E731
    cfg["release_root"] = a("rel")
    cfg["inputs"].update(feature_stack=a("stack.tif"), dem=a("dem.tif"), blocks=a("blocks.gpkg"),
                         split_future={**a("future.json"), "split_task": "pit"}, audit_blocks=a("audit.csv"),
                         split_historical=a("hist.csv"), second_reviewer=a("none.gpkg"))
    cfg["inputs"]["annotations"] = {**a("ann.gpkg"), "layers": {"pit_floor": "pit_inside", "pit_full": "pit_full", "pad": "pad"}}
    cfg["baselines"] = {"good": {"task": "pit_floor", "fold_raster": a("good_fold{k}.tif"), "split_file": a("hist.csv")},
                        "bad": {"task": "pit_floor", "fold_raster": a("bad_fold{k}.tif"), "split_file": a("hist.csv")},
                        "absent": {"task": "pit_floor", "fold_raster": a("nope_fold{k}.tif"), "split_file": a("hist.csv")}}
    p = tmp / "cfg.json"
    p.write_text(json.dumps(cfg))
    return p


def _devtest_fold(doc) -> int:
    folds = doc["tasks"]["pit"]["folds"]
    return next(int(f) for f in sorted(folds, key=int)
                if set(folds[f]["held_out"]) - {AUDIT_BLOCK, BUFFER_BLOCK})


def test_scorer_matches_expkit(tmp_path):
    blocks, pits = _world(tmp_path)
    import rasterio
    with rasterio.open(tmp_path / "good_fold1.tif") as r:
        prob, tf = r.read(1), r.transform
    pol = _policy(k_per_km2=2000)
    s, c = sc.evaluate([((prob, tf), None)], pits, blocks, policy=pol, B=20)
    ref = ek.recall_at_k(c["score"], c["matched_truth"], c["block_id"], {0: s["n_truth"]}, s["area_km2"],
                         k_per_km2=2000, areas=c["area_m2"], cand_ids=c["cand_id"])
    assert ref["hits"] == s["hits"] and ref["k"] == s["k"] and s["n_truth"] == 16 and s["recall"] > 0.9
    s2, _ = sc.evaluate([((prob, tf), None)], pits, blocks, policy=pol, B=20)
    assert json.dumps(sc._round({k: v for k, v in s.items() if k[0] != "_"}), sort_keys=True) == \
        json.dumps(sc._round({k: v for k, v in s2.items() if k[0] != "_"}), sort_keys=True)
    # the local fresh-checkout copies equal expkit's on the same payload
    payload = sc.payload_from_files(c, s["_blocks"], strict=True)
    fn = lambda bl: sc.pooled_recall(bl, 2000)  # noqa: E731
    _, lo, hi, d1 = ek.block_bootstrap(fn, payload, B=30, seed=5)
    _, lo2, hi2, d2 = sc._bootstrap_local(fn, payload, 30, 5, 0.05)
    assert np.array_equal(d1, d2) and (lo, hi) == (lo2, hi2)


def test_policy_primary_cutoff_not_010(tmp_path):
    """7.3-01. A 0.20 blob over a truth pit is not a primary candidate (pit cutoff 0.35). It is one in
    the 0.10 sensitivity mode. The pre-fix scorer used 0.10 as its default and found it."""
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.geometry import box
    blocks = gpd.GeoDataFrame({"block_id": [0]}, geometry=[box(0, 0, 375, 375)], crs=CRS)   # K = 40 x 0.14 = 6
    truth = gpd.GeoDataFrame(geometry=[box(20, 20, 25, 25)], crs=CRS)
    prob = np.zeros((750, 750), np.float32)
    prob[700:710, 40:50] = 0.20                     # rows 700..709 are y 25..20, cols 40..49 are x 20..25
    tf = from_origin(0, 375, 0.5, 0.5)
    for task, cut in (("pit_floor", 0.35), ("pit_full", 0.35), ("pad", 0.525)):
        assert sc.load_policy(task) == ek.policy_for(task) and sc.load_policy(task)["cutoff"] == cut
    s, _ = sc.evaluate([((prob, tf), None)], truth, blocks, policy=sc.load_policy("pit_floor"), B=0)
    assert (s["n_candidates"], s["hits"], s["policy"]["cutoff"], s["policy"]["match_order"]) == (0, 0, 0.35, "score")
    s, _ = sc.evaluate([((prob, tf), None)], truth, blocks, policy=sc.load_policy("pit_floor", "sensitivity"), B=0)
    assert (s["n_candidates"], s["hits"], s["policy"]["cutoff"]) == (1, 1, 0.10)
    cfg = json.loads((HERE / "config_7_3.json").read_text())
    assert "thr" not in cfg["scorer"] and "thr_by_task" not in cfg["scorer"]
    with pytest.raises(SystemExit):                 # --task is required, no hidden 0.10 default
        sc.main(["--pred", "x.tif", "--labels", "l.gpkg", "--blocks", "b.gpkg", "--out", "o.json"])


def test_match_order_score_not_iou():
    """fw_00 section 4. Score order gives the truth to the higher-score candidate (IoU 0.4) over the
    lower-score one (IoU 0.6). IoU order (sensitivity) does the reverse."""
    import geopandas as gpd
    from shapely.geometry import box
    truth = gpd.GeoDataFrame({"truth_id": ["t"], "block_id": [0]}, geometry=[box(0, 0, 10, 1)], crs=CRS)
    cands = gpd.GeoDataFrame({"cand_id": ["a", "b"], "score": [0.9, 0.5], "block_id": [0, 0]},
                             geometry=[box(0, 0, 4, 1), box(4, 0, 10, 1)], crs=CRS)
    m, _ = sc.match_greedy_iou(cands, truth, 0.3, order="score", block_col="block_id")
    assert m == ["t", None]
    m, _ = sc.match_greedy_iou(cands, truth, 0.3, order="iou", block_col="block_id")
    assert m == [None, "t"]


def test_match_within_block_only():
    """7.3-02. Truth centroid in block 1, candidate centroid in block 0, IoU 0.6. Within-block matching
    gives 0 hits. The pre-fix scorer matched across blocks and gave 1."""
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.geometry import box
    blocks = gpd.GeoDataFrame({"block_id": [0, 1]}, geometry=[box(0, 0, 50, 50), box(50, 0, 100, 50)], crs=CRS)
    truth = gpd.GeoDataFrame(geometry=[box(47, 20, 55, 28)], crs=CRS)          # centroid x 51, block 1
    prob = np.zeros((100, 200), np.float32)
    prob[44:60, 90:106] = 0.9                                                 # x 45..53, centroid x 49, block 0
    s, c = sc.evaluate([((prob, from_origin(0, 50, 0.5, 0.5)), None)], truth, blocks,
                       policy=_policy(k_per_km2=2000), B=0)
    assert list(c["block_id"]) == [0] and (s["hits"], s["n_truth"], s["recall"]) == (0, 1, 0.0)


def test_bootstrap_recall_never_above_one():
    """7.3-02 with eligible_truth. A legacy cross-block match (candidate in block 0 holding truth of block 1)
    is not a hit. Draw [b0, b0, b1] by hand: truth 1, eligible hits 0, recall 0. Pre-fix it was 2.0."""
    cands = pd.DataFrame({"cand_id": ["c0", "c1"], "block_id": [0, 1], "score": [0.9, 0.8],
                          "area_m2": [10.0, 10.0], "matched_truth": ["t1", None], "truth_block_id": [1, None]})
    blocks_tab = pd.DataFrame({"block_id": [0, 1], "n_truth": [0, 1], "area_km2": [0.0025, 0.0025]})
    p = sc.payload_from_files(cands, blocks_tab, strict=True)
    assert sc.pooled_recall([p[0], p[0], p[1]], 1e6) == 0.0
    with pytest.raises(ValueError):
        sc.payload_from_files(cands.drop(columns="truth_block_id"), blocks_tab, strict=True)


def test_future_roles_from_real_p1_p2(tmp_path):
    """F05. P1 and P2 files written by the real producers feed the export unmodified. P2 'audit' is the
    hidden test and 'buffer' is excluded. Expected roles come from the P1 document by hand."""
    _world(tmp_path)
    doc = _producers(tmp_path)
    import _bench_export_release_9t as ex
    k_dev = _devtest_fold(doc)
    roles, folds = ex.roles_from_future(tmp_path / "future.json", tmp_path / "audit.csv", k_dev, "pit")
    want = {AUDIT_BLOCK: "test", BUFFER_BLOCK: "buffer"}
    for f, r in doc["tasks"]["pit"]["folds"].items():
        for b in r["held_out"]:
            want.setdefault(int(b), "devtest" if int(f) == k_dev else "train")
    assert roles == want
    assert [f["fold"] for f in folds] == [0, 1, 2, 3, 4]
    with pytest.raises(FileNotFoundError):
        ex.roles_from_future(tmp_path / "future.json", tmp_path / "nope.csv", k_dev, "pit")


def test_unknown_p2_role_refused(tmp_path):
    _world(tmp_path)
    doc = _producers(tmp_path, roles=("comparative_audit", "buffer"))
    import _bench_export_release_9t as ex
    with pytest.raises(ValueError, match="unknown P2 roles"):
        ex.roles_from_future(tmp_path / "future.json", tmp_path / "audit.csv", _devtest_fold(doc), "pit")


def test_export_check_fails_on_unreadable_layer(tmp_path, monkeypatch):
    """F05 minor. The hidden-label check must fail, not skip, when a shipped layer cannot be read."""
    _world(tmp_path)
    doc = _producers(tmp_path)
    import geopandas as gpd
    import _bench_export_release_9t as ex
    real = gpd.read_file

    def broken(path, *a, **k):
        if "labels" in Path(str(path)).parts and k.get("layer") == "pit_floor":
            raise RuntimeError("unreadable layer")
        return real(path, *a, **k)
    monkeypatch.setattr(gpd, "read_file", broken)
    with pytest.raises(RuntimeError, match="unreadable"):
        ex.export(ex.load_cfg(_cfg(tmp_path)), tmp_path / "rel", provisional=False, max_tiles=0,
                  devtest_fold=_devtest_fold(doc))


def test_export_baselines_fresh_checkout(tmp_path):
    _world(tmp_path)
    doc = _producers(tmp_path)
    import _bench_export_release_9t as ex
    import _bench_baselines_score_9t as bl
    import _bench_fresh_checkout_test as fc
    import _bench_card_datasheet_9t as ds
    cfg = ex.load_cfg(_cfg(tmp_path))
    k_dev = _devtest_fold(doc)
    summ = ex.export(cfg, tmp_path / "rel", provisional=False, max_tiles=None, devtest_fold=k_dev)
    root = tmp_path / "rel" / "terrain_v1"
    assert summ["n_tiles"] == 8 and summ["roles"]["test"] == 1 and summ["roles"]["buffer"] == 1
    assert "P2 audit set" in summ["audit_exclusion"]
    pol = json.loads((root / "scoring_policy.json").read_text())
    for t in ("pit_floor", "pit_full", "pad"):
        assert pol["primary"][t] == ek.policy_for(t) and pol["sensitivity"][t] == ek.policy_for(t, "sensitivity")
    import geopandas as gpd
    for p in (root / "labels").glob("*.gpkg"):
        g = gpd.read_file(p, layer="pit_floor")
        assert not set(g["block_id"].astype(int)) & {BUFFER_BLOCK, AUDIT_BLOCK}, "hidden or buffer label leaked"
    assert ex.verify_manifest(root) == []
    df = bl.run(cfg, root, B=20)
    assert set(df.loc[df.status == "scored", "model"]) == {"good", "bad"}
    assert set(df.loc[df.status == "scored", "cutoff"]) == {0.35}
    assert "missing" in df.loc[df.model == "absent", "status"].iloc[0]
    cmds = json.loads((root / "baselines" / "baseline_commands.json").read_text())
    for argv in cmds.values():
        assert "--thr" not in argv and argv[argv.index("--task") + 1] == "pit_floor"
    s = json.loads((root / "baselines" / "good_score.json").read_text())
    assert s["policy"] == ek.policy_for("pit_floor")
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
            s, c = sc.evaluate([((r.read(1), r.transform), None)], pits, blocks, policy=_policy(k_per_km2=2000), B=0)
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
