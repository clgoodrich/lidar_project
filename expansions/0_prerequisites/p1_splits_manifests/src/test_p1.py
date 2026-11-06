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
import _split_future_csv_9t as fc  # noqa: E402

P2_SRC = Path(__file__).resolve().parents[2] / "p2_audit_set" / "src"
SHARED = Path(__file__).resolve().parents[3] / "_shared" / "src"


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
    with pytest.raises(AssertionError):                       # P2-03. audit block in held_out (scoring) fails
        trainer.guard_lists(audit, {"train": [1], "inner_val": [2], "held_out": [9]}, 25)


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


def synth_blocks_gpkg(tmp: Path) -> Path:
    p = tmp / "blocks.gpkg"
    synth_blocks().to_file(p, layer="blocks")
    return p


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


def _rehashed(doc, edit):
    d = json.loads(json.dumps(doc))
    edit(d["tasks"]["pit"])
    d["content_sha256"] = sc.lists_hash(d["tasks"])                # tamperer recomputes the content hash
    return d


@pytest.mark.parametrize("what", ["seed", "frac", "list_hash", "exclusions"])
def test_verify_fails_on_tamper_after_rehash(tmp_path, what):
    """P1-05. Each edit is followed by a fresh content hash, so only a recompute can catch it."""
    mp = synth_manifest(tmp_path)
    doc = fw.build({"pit": mp}, check_exporter=False)
    f = tmp_path / "s.json"

    def drop_block(t):                                             # declare block 3 excluded, remove it
        t["excluded_audit_blocks"] = [3]
        t["exclude_source"] = "hand-written"
        t["folds"] = {k: {r: [b for b in v if b != 3] for r, v in roles.items()} for k, roles in t["folds"].items()}
        t["n_blocks"] -= 1
    edits = {"seed": lambda t: t.update(seed=t["seed"] + 1),
             "frac": lambda t: t.update(inner_val_frac=0.5),
             "list_hash": lambda t: t["list_sha256"]["0"].update(train="0" * 64),
             "exclusions": drop_block}
    f.write_text(json.dumps(_rehashed(doc, edits[what])))
    fw.split_file_for("pit", f)                                    # self-hash is consistent, so verify is the guard
    assert fw.verify(f, manifests={"pit": mp}, check_exporter=False), f"verify passed a tampered {what}"


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
    # P1-02. run at a non-zero buffer. Zero leaks must hold against the dilated forbidden set.
    res = sl.leakage_for_task("pit", {0: splits[0], 1: splits[1]}, man, blocks, feat, n=300, buffer_m=5.0,
                              patch=16, jitter=5.0)
    assert all(v["buffer_m"] == 5.0 for v in res.values())
    assert all(v["isolated_leaking"] == 0 for v in res.values())
    assert sum(v["historical_leaking"] for v in res.values()) > 0


def test_buffer_default_is_derived_and_missing_fails(tmp_path):
    """P1-02. No --buffer-m means the derived buffer. A missing derivation stops, never 0 m."""
    import _pit_unet_iso_train_9t as tr
    with pytest.raises(SystemExit, match="derived buffer missing"):
        sl.resolve_buffers(["pit"], None, tmp_path / "missing.json")
    bj = tmp_path / "buffer.json"
    bj.write_text(json.dumps({"buffer_m_by_task": {"pit": 100.0, "pad": None}, "task": "pit"}))
    assert sl.resolve_buffers(["pit"], None, bj) == {"pit": 100.0}
    with pytest.raises(SystemExit):                                # pad has no derived buffer here
        sl.resolve_buffers(["pit", "pad"], None, bj)
    assert sl.resolve_buffers(["pit", "pad"], 7.0, None) == {"pit": 7.0, "pad": 7.0}
    with pytest.raises(SystemExit, match="derived buffer missing"):
        tr.main(["--splits", str(bj), "--buffer-json", str(tmp_path / "missing.json"), "--dry-run"])
    with pytest.raises(SystemExit, match="derived buffer missing"):
        sl.main(["--splits", str(bj), "--buffer-json", str(tmp_path / "missing.json")])


def test_norm_trace_fails_with_missing_fold(tmp_path):
    """P1 minor. A trace with fold 1 absent must not pass."""
    from rasterio.transform import from_origin
    blocks = synth_blocks()
    splits = {0: {"held_out": [15], "inner_val": [14], "train": [0]}, 1: {"held_out": [14], "inner_val": [15], "train": [0]}}
    d = tmp_path / "fold0"
    d.mkdir()
    np.savez(d / "norm_stats_fold0.npz", mu=np.zeros(2), r0=np.array([0]), c0=np.array([0]), patch=10)
    r = sl.check_norm(tmp_path, splits, blocks, from_origin(0, 100, 0.5, 0.5), 0.0)
    assert r["missing_folds"] == ["1"] and r["pass"] is False


def test_csv_roles_are_json_names_and_refuse_overwrite(tmp_path):
    """P1-01 and the overwrite minor."""
    mp = synth_manifest(tmp_path)
    doc = fw.build({"pit": mp}, check_exporter=False)
    j = fw.write_split(doc, tmp_path / "cv_splits_future_9t_v1.json")
    assert {r[2] for r in fc.flatten(doc)["pit"]} == {"train", "inner_val", "held_out"}
    fc.main(["--json", str(j), "--out-dir", str(tmp_path)])
    out = tmp_path / "cv_splits_future_pit_9t_v1.csv"
    assert set(pd.read_csv(out).role) == {"train", "inner_val", "held_out"}
    fc.main(["--json", str(j), "--out-dir", str(tmp_path)])        # identical content may be rewritten
    out.write_text(out.read_text().replace("train", "inner_val", 1))
    with pytest.raises(SystemExit, match="different content"):
        fc.main(["--json", str(j), "--out-dir", str(tmp_path)])
    fc.main(["--json", str(j), "--out-dir", str(tmp_path), "--force"])
    with pytest.raises(FileExistsError):                           # the JSON writer never overwrites
        fw.write_split(doc, j)


def test_semivariogram_and_range():
    rng = np.random.default_rng(0)
    z = rng.normal(size=(60, 60))
    lags, g, n = bd.semivariogram(z, np.ones_like(z, bool), 5.0, 25.0, 200.0)
    assert np.all(n > 0) and abs(np.nanmean(g) - 1.0) < 0.1      # white noise, gamma = variance
    r = bd.range_rule(lags, g)
    # P1-04. a flat variogram reaches the sill at once. The range lies below the first lag, so the rule
    # flags it and reports the first lag as an upper bound, not as a measured range.
    assert r["range_below_first_lag"] is True
    assert r["range_m_upper_bound"] == lags[0] == 12.5


def test_range_rule_wobble_cannot_swing_buffer():
    # P1-04. The 9t pit variogram. First lag at 94.88% of the sill, second at 96.64%, tail flat with
    # sd 0.38% of the sill. A 0.12% wobble of the first lag must not move the buffer.
    lags = np.arange(12.5, 1000, 25.0)
    tail = 1.0 + 0.0038 * np.where(np.arange(len(lags)) % 2, 1, -1)    # mean 1, sd 0.0038
    base = np.r_[[0.9488, 0.9664, 0.9708, 0.9764, 0.983], tail[5:]]
    up = []
    for g0 in (0.9488, 0.9500):
        g = base.copy()
        g[0] = g0
        up.append(bd.range_rule(lags, g)["range_m_upper_bound"])
    # oracle by hand. sill ~ 1.0, sigma 0.0038, robust threshold 0.95 + 2 * 0.0038 = 0.9576.
    # first lag >= 0.9576 is lag 2 (0.9664) at 37.5 m in both cases. 47 m + 37.5 m = 84.5 m -> 100 m.
    assert up == [37.5, 37.5]
    assert bd.range_rule(lags, base)["first_lag_within_noise"] is True
    assert bd.range_rule(lags, base)["range_below_first_lag"] is False


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


def write_audit_with_p2(tmp: Path, audit_ids, buffer_m=25.0) -> Path:
    """Audit CSV from the real P2 writer, plus the sidecar its --freeze step writes."""
    sys.path.insert(0, str(P2_SRC))
    import _audit_draw_blocks_9t as dr
    tab = pd.DataFrame({"block_id": range(16), "dens_t": [i % 3 for i in range(16)], "slope_t": [i // 6 for i in range(16)]})
    p = tmp / "audit.csv"
    dr.write_audit_csv(p, tab, {"audit": list(audit_ids), "buffer": [], "share": 0.15}, "window", buffer_m, 1)
    Path(str(p) + ".sha256").write_text(f"{sc.ek.sha256(p)}  {p.name}\n")
    return p


def test_split_excluding_audit_blocks(tmp_path):
    mp = synth_manifest(tmp_path)
    ap = write_audit_with_p2(tmp_path, [0, 5])
    excl, src = fw.audit_exclusion(ap)
    doc = fw.build({"pit": mp}, check_exporter=False, exclude=excl, exclude_source=src)
    t = doc["tasks"]["pit"]
    assert t["excluded_audit_blocks"] == [0, 5] and t["n_blocks"] == 14
    assert not {0, 5} & {b for r in t["folds"].values() for v in r.values() for b in v}
    f = tmp_path / "v2.json"
    f.write_text(json.dumps(doc))
    assert fw.verify(f, manifests={"pit": mp}, check_exporter=False) == []
    with pytest.raises(ValueError):                                # untraceable exclusions are refused
        fw.build({"pit": mp}, check_exporter=False, exclude={0}, exclude_source="test")
    Path(str(ap) + ".sha256").unlink()
    ap.write_text(ap.read_text() + "7,audit,,9t\n")                # audit file changed after the split
    assert any("changed" in x for x in fw.verify(f, manifests={"pit": mp}, check_exporter=False))


# ----------------------------------------------------------------------------- buffer JSON and block buffer
@pytest.fixture(scope="module")
def buffer_json(tmp_path_factory):
    """Buffer JSON from the real P1 S4 functions on synthetic rasters. White-noise residual, 0.25 m pixels.

    Returns (path, oracle buffer in m). Oracle. range below the first lag, so the bound is the first lag
    centre (1 m). Buffer = ceil((rf radius px * 0.25 + 1) / 25) * 25."""
    import math
    import rasterio
    from rasterio.transform import from_origin
    tmp = tmp_path_factory.mktemp("buf")
    rng = np.random.default_rng(3)
    prof = dict(driver="GTiff", height=400, width=400, count=1, crs="EPSG:6346", transform=from_origin(0, 100, 0.25, 0.25))
    prob, lab = tmp / "prob.tif", tmp / "lab.tif"
    with rasterio.open(prob, "w", dtype="float32", nodata=-1.0, **prof) as d:
        d.write(rng.uniform(0, 1, (1, 400, 400)).astype(np.float32))
    with rasterio.open(lab, "w", dtype="uint8", **prof) as d:
        d.write(np.zeros((1, 400, 400), np.uint8))
    res = bd.derive(prob, lab, step_m=1.0, floor_class=1, n_classes=3, patch_px=64, lag_m=2.0, max_m=40.0)
    assert res["semivariogram"]["range_below_first_lag"] is True
    doc = bd.assemble({"pit": res, "pad": "pad inputs not held (test)"})
    p = bd.write_buffer_json(doc, tmp / "buffer_derivation_9t.json")
    oracle = math.ceil((res["receptive_field"]["radius_px"] * 0.25 + 1.0) / 25) * 25
    return p, float(oracle)


def test_buffer_json_schema(buffer_json):
    """P1-03. buffer_m_by_task and task are written. A task that is not derived is null with a reason."""
    p, oracle = buffer_json
    doc = json.loads(p.read_text())
    assert doc["task"] == "pit" and doc["buffer_m_by_task"] == {"pit": oracle, "pad": None}
    assert doc["by_task"]["pad"]["reason"].startswith("pad inputs not held")
    assert sc.ek.read_buffer("pit", p) == oracle
    with pytest.raises(KeyError):
        sc.ek.read_buffer("pad", p)


def chebyshev_neighbours(held, n=4):
    """Oracle. blocks of the 4 x 4 grid (id = iy * 4 + ix) that touch a held block, corners included."""
    out = set()
    for h in held:
        hx, hy = h % n, h // n
        for b in range(n * n):
            if b not in held and max(abs(b % n - hx), abs(b // n - hy)) == 1:
                out.add(b)
    return out


def test_block_buffer_moves_near_train_blocks(tmp_path, buffer_json):
    """P1-02. With 25 m blocks and the 25 m derived buffer, every train block that touches a held-out
    block (edges or corners) moves to role 'buffer'. Verify recomputes it."""
    bj, oracle = buffer_json
    assert oracle == 25.0
    mp = synth_manifest(tmp_path)
    gp = synth_blocks_gpkg(tmp_path)
    plain = fw.build({"pit": mp}, check_exporter=False)
    doc = fw.build({"pit": mp}, check_exporter=False, buffers={"pit": fw.buffer_spec("pit", bj)}, blocks={"pit": gp},
                   buffer_mode="block")
    t = doc["tasks"]["pit"]
    assert t["buffer_m"] == 25.0 and t["buffer_mode"] == "block"
    for f in range(5):
        p0 = plain["tasks"]["pit"]["folds"][str(f)]
        near = sorted(chebyshev_neighbours(set(p0["held_out"])) & set(p0["train"]))
        r = t["folds"][str(f)]
        assert r["buffer"] == near
        assert r["train"] == sorted(set(p0["train"]) - set(near))
        assert r["held_out"] == p0["held_out"] and r["inner_val"] == p0["inner_val"]
        assert t["buffer_removed_by_fold"][str(f)] == len(near)
    f = fw.write_split(doc, tmp_path / "v1.json")
    assert fw.verify(f, manifests={"pit": mp}, check_exporter=False) == []


# ----------------------------------------------------------------------------- F05 producer -> reader round trip
READER = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import expkit as ek
split, csvp, buf, aud = sys.argv[2:6]
out = {"split": {str(f): v for f, v in ek.read_split("pit", split).items()}}
df = ek.read_split_csv(csvp)
out["csv"] = sorted([int(b), int(f), r] for b, f, r in zip(df.block_id, df.fold, df.role))
out["buffer_pit"] = ek.read_buffer("pit", buf)
try:
    ek.read_buffer("pad", buf)
    out["buffer_pad"] = "no error"
except KeyError:
    out["buffer_pad"] = "KeyError"
a = ek.read_audit(aud, allow_unfrozen=True)
out["audit"] = sorted([int(b), r] for b, r in zip(a.block_id, a.role))
out["audit_ids"] = sorted(ek.audit_ids(a, roles=("audit",)))
print(json.dumps(out))
"""


def test_f05_round_trip_real_writers_fresh_process(tmp_path, buffer_json):
    """F05. Every P1/P2 file is made by its real writer and read through expkit in a fresh process."""
    import subprocess
    sys.path.insert(0, str(P2_SRC))
    import _audit_draw_blocks_9t as dr
    bj, oracle = buffer_json
    mp, gp = synth_manifest(tmp_path), synth_blocks_gpkg(tmp_path)
    doc = fw.build({"pit": mp}, check_exporter=False, buffers={"pit": fw.buffer_spec("pit", bj)}, blocks={"pit": gp},
                   buffer_mode="block")      # block mode so the 'buffer' role is exercised end to end
    sj = fw.write_split(doc, tmp_path / "cv_splits_future_9t_v1.json")
    fc.main(["--json", str(sj), "--out-dir", str(tmp_path)])
    cj = tmp_path / "cv_splits_future_pit_9t_v1.csv"
    tab = pd.DataFrame({"block_id": range(16), "dens_t": [i % 3 for i in range(16)], "slope_t": [i // 6 for i in range(16)]})
    aj = tmp_path / "audit_blocks_9t_dryrun.csv"
    dr.write_audit_csv(aj, tab, {"audit": [2, 11], "buffer": [3], "share": 0.15}, "block", oracle, 20261104)
    r = subprocess.run([sys.executable, "-c", READER, str(SHARED), str(sj), str(cj), str(bj), str(aj)],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout.strip().splitlines()[-1])
    folds = doc["tasks"]["pit"]["folds"]
    # expected straight from the written JSON. The 'buffer' role is not a training or scoring role.
    want_split = {f: {k: v[k] for k in ("held_out", "inner_val", "train")} for f, v in folds.items()}
    assert got["split"] == want_split
    want_csv = sorted([b, int(f), role] for f, v in folds.items() for role in ("train", "inner_val", "held_out") for b in v[role])
    assert got["csv"] == want_csv
    assert sum(len(v["buffer"]) for v in folds.values()) > 0       # the buffer did move blocks
    assert not [b for b, f, _ in got["csv"] if b in folds[str(f)]["buffer"]]
    assert got["buffer_pit"] == oracle and got["buffer_pad"] == "KeyError"
    assert got["audit"] == [[2, "audit"], [3, "buffer"], [11, "audit"]]
    assert got["audit_ids"] == [2, 11]


def test_default_buffer_mode_is_window(tmp_path, buffer_json):
    """User default 2026-11-06. With no buffer_mode given, build() and the CLI use `window`. Lists stay equal to the
    unbuffered split. The near blocks are counted per fold (hand oracle, Chebyshev neighbours of held-out)."""
    import inspect
    bj, _ = buffer_json
    mp = synth_manifest(tmp_path)
    gp = synth_blocks_gpkg(tmp_path)
    plain = fw.build({"pit": mp}, check_exporter=False)
    doc = fw.build({"pit": mp}, check_exporter=False, buffers={"pit": fw.buffer_spec("pit", bj)}, blocks={"pit": gp})
    t = doc["tasks"]["pit"]
    assert t["buffer_mode"] == "window" and t["buffer_removed_by_fold"] is None
    for f in range(5):
        p0 = plain["tasks"]["pit"]["folds"][str(f)]
        r = t["folds"][str(f)]
        assert r["train"] == p0["train"] and r["held_out"] == p0["held_out"]
        near = chebyshev_neighbours(set(p0["held_out"])) & set(p0["train"])
        assert t["near_held_out_by_fold"][str(f)] == len(near)
    src = inspect.getsource(fw.main)
    assert "default=DEFAULT_BUFFER_MODE" in src and fw.DEFAULT_BUFFER_MODE == "window"
    f = fw.write_split(doc, tmp_path / "v1.json")
    assert fw.verify(f, manifests={"pit": mp}, check_exporter=False) == []


def test_noise_band_is_two_sigma():
    """User default 2026-11-06. The range rule noise band is 2 sigma."""
    assert bd.NOISE_K == 2.0
