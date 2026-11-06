"""Smoke tests for P2 on tiny synthetic data. CPU only, no network, seconds.

Run
    python -m pytest -q expansions/0_prerequisites/p2_audit_set/src/test_p2.py -p no:cacheprovider
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
import _audit_guard_lib as ag  # noqa: E402
import _audit_draw_blocks_9t as dr  # noqa: E402
import _audit_exposure_ledger_9t as el  # noqa: E402
import _audit_discovery_draw as dd  # noqa: E402
import _audit_reserve_warren as rw  # noqa: E402


def grid(n=6, size=375.0):
    import geopandas as gpd
    from shapely.geometry import box
    g = [box(ix * size, iy * size, (ix + 1) * size, (iy + 1) * size) for iy in range(n) for ix in range(n)]
    return gpd.GeoDataFrame({"block_id": list(range(n * n))}, geometry=g, crs="EPSG:6346")


def write_frozen(tmp: Path, ids, buffer_m=100.0) -> Path:
    p = tmp / "audit.csv"
    p.write_text(f"# test\n# seed=1 share=0.15 buffer_m={buffer_m} buffer_mode=window\n"
                 + pd.DataFrame({"block_id": ids, "role": "audit", "stratum": "", "area": "t"}).to_csv(index=False))
    Path(str(p) + ".sha256").write_text(ag._sha(p.read_bytes()) + "  audit.csv\n")
    return p


def test_guard_refuses_audit_ids_windows_and_tampering(tmp_path):
    p = write_frozen(tmp_path, [3, 7])
    aud = ag.load_audit(p)
    assert aud.attrs["header"]["buffer_m"] == 100.0
    ag.assert_no_audit([1, 2, 4], aud)
    with pytest.raises(ag.AuditViolation):
        ag.assert_no_audit([1, 7], aud, "train")              # training on an audit block must fail
    from shapely.geometry import box
    blocks = grid()
    b3 = blocks.geometry[3].bounds
    with pytest.raises(ag.AuditViolation):
        ag.assert_no_audit([box(b3[0] + 10, b3[1] + 10, b3[0] + 50, b3[1] + 50)], aud, "windows", blocks)
    ag.assert_no_audit([box(0, 0, 50, 50)], aud, "windows", blocks)
    p.write_text(p.read_text() + "9,audit,,t\n")              # edited after freezing
    with pytest.raises(ag.AuditViolation):
        ag.load_audit(p)


def test_guard_refuses_unfrozen(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("block_id,role\n1,audit\n")
    with pytest.raises(ag.AuditViolation):
        ag.load_audit(p)
    assert len(ag.load_audit(p, allow_unfrozen=True)) == 1


def test_split_file_check(tmp_path):
    """P2-03. An audit block in held_out is a violation too. It would reach calibration and scoring."""
    aud = ag.load_audit(write_frozen(tmp_path, [5]))
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps({"tasks": {"pit": {"folds": {"0": {"held_out": [5], "inner_val": [1], "train": [2]},
                                                           "1": {"held_out": [1], "inner_val": [5], "train": [2]},
                                                           "2": {"held_out": [3], "inner_val": [1], "train": [2]}}}}}))
    v = ag.check_split_file(sp, aud)
    assert len(v) == 2
    assert any("fold 0 held_out" in x for x in v) and any("fold 1 inner_val" in x for x in v)


def test_window_guard_applies_audit_buffer(tmp_path):
    """P2-03. A window 1 m outside an audit block fails when the audit buffer is 100 m."""
    from shapely.geometry import box
    blocks = grid()
    aud = ag.load_audit(write_frozen(tmp_path, [3], buffer_m=100.0))
    x0, y0, x1, y1 = blocks.geometry[3].bounds                 # block 3 is x 1125..1500, y 0..375
    near = box(x1 + 1, y0 + 10, x1 + 41, y0 + 50)              # 1 m east of block 3
    far = box(x1 + 101, y0 + 10, x1 + 141, y0 + 50)            # 101 m east, clear of the buffer
    with pytest.raises(ag.AuditViolation, match="within 100.0 m"):
        ag.assert_no_audit([near], aud, "windows", blocks)
    ag.assert_no_audit([far], aud, "windows", blocks)
    with pytest.raises(ag.AuditViolation, match="below"):
        ag.assert_no_audit([far], aud, "windows", blocks, buffer_m=10.0)


def test_window_guard_refuses_audit_ids_missing_from_blocks(tmp_path):
    """P2-03. Audit block 99 has no polygon. The check must raise, not pass."""
    from shapely.geometry import box
    aud = ag.load_audit(write_frozen(tmp_path, [3, 99]))
    with pytest.raises(ag.AuditViolation, match="no polygon"):
        ag.assert_no_audit([box(0, 0, 10, 10)], aud, "windows", grid())


def test_committed_hash_without_git(monkeypatch):
    """P1/P2 minor. No git binary gives None, not an exception."""
    def no_git(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(ag.subprocess, "run", no_git)
    assert ag.committed_hash(ag.ek.REPO / "README.md") is None


def test_audit_scope_is_pit_only(tmp_path):
    """P2 minor. The draw frame is the pit-bearing blocks. A pad reader is refused, a pit reader is not."""
    tab = pd.DataFrame({"block_id": [1, 2, 3], "dens_t": [0, 1, 2], "slope_t": [0, 1, 2]})
    p = tmp_path / "audit_blocks_9t_dryrun.csv"
    dr.write_audit_csv(p, tab, {"audit": [1, 3], "buffer": [], "share": 0.15}, "window", 100.0, 20261104)
    a = ag.load_audit(p, allow_unfrozen=True, task="pit")
    assert a.attrs["header"]["frame"] == "pit_bearing_blocks" and a.attrs["header"]["tasks"] == "pit"
    assert sorted(a.block_id) == [1, 3]
    ag.load_audit(p, allow_unfrozen=True, task="pit_full")
    with pytest.raises(ag.AuditViolation, match="drawn for tasks"):
        ag.load_audit(p, allow_unfrozen=True, task="pad")


def test_draw_is_seeded_stratified_and_buffered():
    rng = np.random.default_rng(0)
    blocks = grid()
    tab = pd.DataFrame({"block_id": range(36), "n_feat": rng.integers(1, 20, 36), "slope": rng.uniform(2, 30, 36)})
    tab["dens_t"], tab["slope_t"] = dr.terciles(tab.n_feat).values, dr.terciles(tab.slope).values
    r1 = dr.build(tab, blocks, 100.0, "window", 0.25, 20261104, 2, 0.6)
    r2 = dr.build(tab, blocks, 100.0, "window", 0.25, 20261104, 2, 0.6)
    assert r1["audit"] == r2["audit"] and len(r1["audit"]) == 9
    sel = tab[tab.block_id.isin(r1["audit"])]
    assert (sel.dens_t.value_counts().reindex(range(3)).fillna(0) >= 2).all()
    assert (sel.slope_t.value_counts().reindex(range(3)).fillna(0) >= 2).all()
    assert r1["buffer"] and not set(r1["buffer"]) & set(r1["audit"])
    rb = dr.build(tab, blocks, 100.0, "block", 0.25, 20261104, 2, 0.6)
    assert rb["share"] == 0.10 or "warning" in rb                # block mode starves training, share drops
    ks = dr.ks_tests(tab, r1["audit"])
    assert 0 <= ks["slope"]["p"] <= 1


def test_allocate_sums():
    a = dr.allocate({(0, 0): 5, (0, 1): 3, (1, 1): 9}, 6)
    assert sum(a.values()) == 6 and a[(1, 1)] >= a[(0, 1)]


def test_exposure_ledger_counts():
    held = {"m1": {0: [0, 1], 1: [2, 3]}, "m2": {0: [0], 1: [1]}}
    uses = [{"name": "thr", "kind": "all_non_heldout_per_model"}, {"name": "ctx", "kind": "all_blocks"},
            {"name": "eyes", "kind": "unknown"}]
    df = el.ledger([0, 1, 2, 3], held, uses)
    assert len(df) == 4
    assert df.set_index("block_id").n_model_uses.to_dict() == {0: 2, 1: 2, 2: 3, 3: 3}
    assert (df.n_uses == df.n_model_uses + 3).all()


def test_discovery_draw_and_shortfall():
    blocks = grid()
    blocks["role"] = ""
    blocks.loc[:5, "role"] = "test"
    d = dd.draw_discovery(blocks, {6, 7}, 2.0, 1)
    assert d.area_km2.sum() >= 2.0 and not set(d.block_id) & set(range(8))
    assert d.equals(dd.draw_discovery(blocks, {6, 7}, 2.0, 1))
    with pytest.raises(SystemExit):
        dd.draw_discovery(blocks, set(), 100.0, 1)


def test_reserve_refuses_seen_area():
    from shapely.geometry import box
    blocks = grid()
    blocks["role"] = "test"
    blocks.loc[[0, 1], "role"] = "audit"
    rows, probs = rw.reserve(blocks, [])
    assert list(rows.block_id) == [0, 1] and probs == []
    _, probs = rw.reserve(blocks, [(Path("prob.tif"), box(0, 0, 10, 10), "EPSG:6346")])
    assert probs
    _, probs = rw.reserve(blocks, [(Path("prob.tif"), box(0, 0, 10, 10), None)])
    assert probs and "no CRS" in probs[0]


def test_reserve_reprojects_extents():
    """P1/P2 minor. An output in another CRS over a reserved block is caught after reprojection."""
    import geopandas as gpd
    from shapely.geometry import box
    g = [box(600000 + ix * 375, 4500000, 600000 + (ix + 1) * 375, 4500375) for ix in range(4)]
    blocks = gpd.GeoDataFrame({"block_id": range(4), "role": ["audit", "test", "test", "test"]}, geometry=g, crs="EPSG:6346")
    c = gpd.GeoSeries([blocks.geometry[0].centroid.buffer(20)], crs="EPSG:6346").to_crs("EPSG:4326").iloc[0]
    _, probs = rw.reserve(blocks, [(Path("p.tif"), box(*c.bounds), "EPSG:4326")])
    assert len(probs) == 1 and "[0]" in probs[0]            # raw degrees would never touch UTM metres
    c3 = gpd.GeoSeries([blocks.geometry[3].centroid.buffer(20)], crs="EPSG:6346").to_crs("EPSG:4326").iloc[0]
    _, probs = rw.reserve(blocks, [(Path("q.tif"), box(*c3.bounds), "EPSG:4326")])
    assert probs == []


def test_pad_draw_dry_run_on_held_9t(tmp_path, monkeypatch):
    """User default 2026-11-06. A separate pad draw from the pad-bearing blocks, dry run only.
    Runs the real main() on the held 9t pad manifest. Oracle by hand. The eligible blocks are the distinct
    pad manifest block ids, the audit size is round(0.15 n). The file is readable for pad and refused for pit.
    No frozen file is written."""
    import _split_core_lib_9t as sc
    try:
        man = sc.load_manifest("pad")
    except FileNotFoundError:
        pytest.skip("9t pad manifest not held")
    n_elig = man.dropna(subset=["block_id"]).block_id.astype(int).nunique()
    monkeypatch.setattr(dr.ek, "new_run", lambda *a, **k: tmp_path / "run")      # no run record from a test
    monkeypatch.setattr(dr.ek, "write_provenance", lambda *a, **k: None)
    assert dr.main(["--task", "pad", "--buffer-m", "150", "--out-dir", str(tmp_path)]) == 0
    p = tmp_path / "audit_blocks_pad_9t_dryrun.csv"
    a = ag.load_audit(p, allow_unfrozen=True, task="pad")
    h = a.attrs["header"]
    assert h["frame"] == "pad_bearing_blocks" and h["tasks"] == "pad" and h["buffer_m"] == 150.0
    assert len(a[a.role == "audit"]) == int(round(0.15 * n_elig))
    assert set(a.block_id) <= set(man.block_id.dropna().astype(int))
    with pytest.raises(ag.AuditViolation, match="drawn for tasks"):
        ag.load_audit(p, allow_unfrozen=True, task="pit")
    assert not Path(str(p) + ".sha256").exists()
    js = json.loads((tmp_path / "audit_draw_pad_9t_dryrun.json").read_text())
    assert js["tasks"] == "pad" and js["n_eligible"] == n_elig
