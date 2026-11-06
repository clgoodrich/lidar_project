"""Smoke tests for 5.4 undocumented density on tiny synthetic data. No GPU, no network, no real data.

Run: python -m pytest -q expansions/5_tasks/5_4_undocumented_density/src/test_5_4.py -p no:cacheprovider
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
sys.path.insert(0, str(HERE.parents[1] / "5_6_record_association" / "src"))
import _density_distinct_wells_9t as dw  # noqa: E402
import _density_sensitivity_grid_9t as sg  # noqa: E402
import _density_field_bounds_9t as fb  # noqa: E402
import _density_capture_recapture_9t as cr  # noqa: E402
import _density_identifiability_terms_9t as it  # noqa: E402

CRS = "EPSG:6346"
X0, Y0 = 619500.0, 4593000.0


def test_merge_points_single_linkage():
    xy = np.array([[0, 0], [10, 0], [20, 0], [100, 0]], float)
    lab = dw.merge_points(xy, 15)
    assert lab[0] == lab[1] == lab[2] and lab[3] != lab[0]


def test_top_k_ties_by_area_then_id():
    c = pd.DataFrame(dict(score=[.9, .9, .8], area_m2=[5, 10, 1], det_id=[0, 1, 2]))
    top, k = dw.top_k(c, area_km2=0.05, k_per_km2=40)
    assert k == 2 and list(top.det_id) == [1, 0]


def test_grid_formula_and_inconsistent_flag():
    G = sg.grid(100, 50, dict(p_min=0.5, p_max=0.5, r_min=0.5, r_max=0.5, step=0.05, m_values=[1.0]))
    row = G.iloc[0]
    assert row.total == pytest.approx(100) and row.missed == pytest.approx(50) and row.undocumented == pytest.approx(50)
    G = sg.grid(10, 50, dict(p_min=0.5, p_max=0.5, r_min=0.5, r_max=0.5, step=0.05, m_values=[1.0]))
    assert G.inconsistent.iloc[0] == 1


def test_field_bounds_infinite_when_recall_can_be_zero():
    B = pd.DataFrame(dict(site_id=range(10), identity=["confirmed_well"] * 3 + ["definite_non_well"] * 5 +
                          ["ambiguous"] * 2, weight=1.0))
    pb = fb.p_bounds(B)
    assert pb["ppv_lower"] == pytest.approx(0.3) and pb["ppv_upper"] == pytest.approx(0.5)
    C = pd.DataFrame(dict(area_id="a", well_id=["w1", "w2"], detected=[0, 0]))
    rb = fb.r_bounds(C)
    assert rb["r_lo"] == 0 and rb["label"].startswith("conditional")
    tb = fb.total_bounds(100, pb, rb, [1.0])
    assert tb["finite_upper"] is False and np.isinf(tb["total_upper"])
    C = pd.DataFrame(dict(area_id="a", well_id=[f"w{i}" for i in range(20)], detected=[1] * 15 + [0] * 5))
    tb = fb.total_bounds(100, pb, fb.r_bounds(C), [1.0, 2.0])
    assert tb["finite_upper"] and tb["total_lower"] < tb["total_upper"]


def test_chapman_known_value():
    N, v = cr.chapman(100, 100, 50)
    assert N == pytest.approx(101 * 101 / 51 - 1) and v > 0


def _setup(tmp_path):
    import geopandas as gpd
    from shapely.geometry import box, Point
    rng = np.random.default_rng(3)
    blocks = gpd.GeoDataFrame(dict(block_id=[0, 1], n_pits=[5, 0]),
                              geometry=[box(X0, Y0, X0 + 375, Y0 + 375), box(X0 + 375, Y0, X0 + 750, Y0 + 375)], crs=CRS)
    bp = tmp_path / "b.gpkg"
    blocks.to_file(bp, layer="blocks", driver="GPKG")
    xy = np.c_[X0 + rng.uniform(10, 365, 12), Y0 + rng.uniform(10, 365, 12)]
    xy[1] = xy[0] + 3                           # two blobs of one site
    pit = gpd.GeoDataFrame(dict(cx=xy[:, 0], cy=xy[:, 1], score=rng.uniform(.5, 1, 12), det_id=range(12),
                                novel=[0] * 6 + [1] * 6, block_id=0, area_m2=10.0),
                           geometry=[Point(*p) for p in xy], crs=CRS)
    pp = tmp_path / "pit.gpkg"
    pit.to_file(pp, driver="GPKG")
    rec = np.r_[xy[:4] + 2, np.c_[X0 + rng.uniform(10, 365, 4), Y0 + rng.uniform(10, 365, 4)]]
    dep = gpd.GeoDataFrame(dict(PERMIT_NUM=[f"121-{i}" for i in range(8)], WELL_STATU=["Active"] * 7 + ["Proposed But Never Materialized"]),
                           geometry=gpd.points_from_xy(rec[:, 0], rec[:, 1]), crs=CRS)
    wp = tmp_path / "dep.gpkg"
    dep.to_file(wp, driver="GPKG")
    cfg = json.loads((HERE / "config_5_4.json").read_text())
    cfg["expected_pit_rows"] = 12
    cfg["bootstrap_B"] = 50
    cfg["inputs"].update(full_pit=str(pp), pit_blocks=str(bp), dep_wells=str(wp),
                         sites=str(tmp_path / "sites.csv"), accounting=str(tmp_path / "acc.json"),
                         cohort_excess=str(tmp_path / "nope.csv"))
    for k in cfg["outputs"]:
        cfg["outputs"][k] = str(tmp_path / Path(cfg["outputs"][k]).name)
    cfg["outputs"]["sites"], cfg["outputs"]["accounting"] = str(tmp_path / "sites.csv"), str(tmp_path / "acc.json")
    cp = tmp_path / "cfg.json"
    cp.write_text(json.dumps(cfg))
    return cp, tmp_path


def test_end_to_end_density(tmp_path):
    cp, tmp = _setup(tmp_path)
    assert dw.main(["--config", str(cp)]) == 0
    acc = json.loads((tmp / "acc.json").read_text())
    # 5.4-02: footprint is both complete blocks, truth-free (0.28125 km2) -> K = round(40 * 0.28125) = 11.
    # The old truth-bearing footprint kept only block 0 and gave K = 6.
    assert acc["footprint_blocks"] == 2 and acc["K"] == 11 and acc["D_blobs"] == 11
    bs = acc["D_sites_block_bootstrap"]
    assert bs["draw_max"] <= acc["K"] and bs["hi"] <= acc["K"]
    assert acc["N_doc_records"] == 7 and acc["N_doc_wells"] == 6      # records 0 and 1 sit 3 m apart and merge
    assert sg.main(["--config", str(cp)]) == 0
    assert (tmp / "density_sensitivity_9t.png").exists()
    assert cr.main(["--config", str(cp)]) == 0
    assert it.main(["--config", str(cp)]) == 0
    T = pd.read_csv(tmp / "density_identifiability_terms_9t.csv")
    assert T.set_index("term").loc["r", "status"] == "unidentified"
    with pytest.raises(SystemExit):
        fb.main(["--config", str(cp)])          # arm_b is not held


def test_d_bootstrap_respects_the_k_cap():
    """5.4-01. Block 0 holds 10 separate high-score candidates, blocks 1 to 3 one low-score candidate each, K = 5.
    The point is 5 sites. The old bootstrap summed per-block site counts after the cut, so a draw of block 0
    four times gave 20 > K. The rerun cut can never exceed K."""
    rows = [dict(det_id=i + 1, block_id=0, cx=100.0 * i, cy=0.0, score=0.9 - 0.01 * i, area_m2=10.0, novel=1)
            for i in range(10)]
    rows += [dict(det_id=20 + b, block_id=b, cx=5000.0 * b, cy=5000.0, score=0.1, area_m2=10.0, novel=1)
             for b in (1, 2, 3)]
    c = pd.DataFrame(rows)
    pt, lo, hi, draws = dw.d_bootstrap(c, [0, 1, 2, 3], 5, 15.0, 400, 0)
    assert pt == 5 and draws.max() <= 5 and hi <= 5
    old_pb = {0: 5, 1: 0, 2: 0, 3: 0}
    rng = np.random.default_rng(0)
    old = [sum(old_pb[[0, 1, 2, 3][j]] for j in rng.integers(0, 4, 4)) for _ in range(400)]
    assert max(old) > 5                          # the old method leaves the support
    # hand value: a draw holding no copy of block 0 has at most 4 low candidates, all separate, so D = 4
    assert draws.min() >= 4 - 0


def test_frame_hash_guard_cannot_be_skipped():
    B = pd.DataFrame(dict(site_id=[1, 2], identity="ambiguous", weight=1.0))
    with pytest.raises(SystemExit):
        fb.check_frame(B, "abc")                                   # column missing
    with pytest.raises(SystemExit):
        fb.check_frame(B.assign(frame_sha256=["abc", "xyz"]), "abc")   # mixed frames
    with pytest.raises(SystemExit):
        fb.check_frame(B.assign(frame_sha256=["", ""]), "abc")         # blank
    fb.check_frame(B.assign(frame_sha256="abc"), "abc")


def test_degenerate_capture_recapture_has_no_se():
    # m reaches the smaller source: Chapman variance is 0 by construction, which is not precision
    N, v = cr.chapman(10, 5, 5)
    assert v == 0 and cr.degenerate(10, 5, 5) and not cr.degenerate(10, 5, 4)


def test_footprint_is_truth_free():
    import geopandas as gpd
    from shapely.geometry import box
    b = gpd.GeoDataFrame(dict(block_id=[0, 1, 2], n_pits=[3, 0, 0]), geometry=[box(0, 0, 1, 1)] * 3, crs=CRS)
    assert len(dw.footprint(b)) == 3
    assert len(dw.footprint(b.assign(n_pits=[0, 0, 9]))) == 3      # changing truth leaves the footprint alone
