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
    aud = ag.load_audit(write_frozen(tmp_path, [5]))
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps({"tasks": {"pit": {"folds": {"0": {"held_out": [5], "inner_val": [1], "train": [2]},
                                                           "1": {"held_out": [1], "inner_val": [5], "train": [2]}}}}}))
    v = ag.check_split_file(sp, aud)
    assert len(v) == 1 and "fold 1 inner_val" in v[0]


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
    _, probs = rw.reserve(blocks, [(Path("prob.tif"), box(0, 0, 10, 10))])
    assert probs
