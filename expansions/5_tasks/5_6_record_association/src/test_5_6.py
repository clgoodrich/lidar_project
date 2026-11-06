"""Smoke tests for 5.6 record association on tiny synthetic data. No GPU, no network, no real data.

Run: python -m pytest -q expansions/5_tasks/5_6_record_association/src/test_5_6.py -p no:cacheprovider
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _records_assoc_core as core  # noqa: E402

CRS = "EPSG:6346"
X0, Y0 = 619500.0, 4593000.0


def _blobs(truth_variant: str):
    """Four predicted blobs. A (score .9) and B (.6) sit 1 m apart (one split pit). C and D are far apart.
    truth_variant changes only truth-derived columns, never geometry or score."""
    import geopandas as gpd
    from shapely.geometry import box
    geoms = [box(X0 + 10, Y0 + 10, X0 + 14, Y0 + 14), box(X0 + 15, Y0 + 10, X0 + 18, Y0 + 14),
             box(X0 + 100, Y0 + 100, X0 + 104, Y0 + 104), box(X0 + 200, Y0 + 50, X0 + 204, Y0 + 54)]
    g = gpd.GeoDataFrame(dict(score=[0.9, 0.6, 0.7, 0.8]), geometry=geoms, crs=CRS)
    if truth_variant == "drawn":
        g["source"] = ["matched", "undecided", "undecided", "matched"]
        g["dup_on_pit"] = [1, 1, 0, 1]
        g["near_pit_m"] = [0.0, 0.0, 50.0, 0.0]
    elif truth_variant == "changed":           # different truth: B flagged off, C now matched
        g["source"] = ["undecided", "undecided", "matched", "undecided"]
        g["dup_on_pit"] = [0, 0, 1, 0]
        g["near_pit_m"] = [9.0, 9.0, 0.0, 30.0]
    # "removed": no truth columns at all
    return g


def test_dedupe_prediction_only_and_refuses_truth_rule():
    # hand oracle: gap A-B is 1 m <= 2 m, so they merge and A (higher score) stays. C and D stay. Kept scores .9 .7 .8
    for v in ("drawn", "changed", "removed"):
        k = core.dedupe(_blobs(v), "geometric", gap_m=2.0)
        assert sorted(k.score) == [0.7, 0.8, 0.9]
        assert int(k.loc[k.score == 0.9, "n_merged"].iloc[0]) == 2
    assert len(core.dedupe(_blobs("drawn"), "keep_all")) == 4
    with pytest.raises(ValueError):
        core.dedupe(_blobs("drawn"), "deployment")       # the old truth-flag rule (F15)
    with pytest.raises(ValueError):
        core.dedupe(_blobs("drawn"), "nonsense")


def test_build_pit_membership_and_ids_invariant_to_truth(tmp_path):
    """F15. The real S0 builder, fed the same predictions under drawn, changed and removed truth."""
    import geopandas as gpd
    from shapely.geometry import box
    import _records_full_detector_output_9t as s0
    bp = tmp_path / "blocks.gpkg"
    gpd.GeoDataFrame(dict(block_id=[0], n_pits=[0]), geometry=[box(X0, Y0, X0 + 375, Y0 + 375)], crs=CRS).to_file(
        bp, layer="blocks", driver="GPKG")
    cfg = json.loads((Path(__file__).resolve().parent / "config_5_6.json").read_text())
    cfg["inputs"]["pit_blocks"] = str(bp)
    cfg["pit"]["expected_predictions"] = 4
    out = {}
    for v in ("drawn", "changed", "removed"):
        g = _blobs(v)
        layers = [g[g.source == "matched"], g[g.source != "matched"]] if "source" in g else [g]
        full, _ = s0.build_pit(cfg, "geometric", layers=layers)
        out[v] = dict(zip(full.score.round(3), full.det_id))
    assert out["drawn"] == out["changed"] == out["removed"]
    assert sorted(out["drawn"].values()) == [1, 2, 3]


def test_det_id_contract_random_and_disjoint():
    """5.6-01. det_id must not encode score or match status. Pit ids from 1, pad ids from 1000001."""
    from scipy.stats import spearmanr
    rng = np.random.default_rng(5)
    n = 400
    df = pd.DataFrame(dict(cx=rng.uniform(0, 4500, n), cy=rng.uniform(0, 4500, n), score=rng.uniform(.5, 1, n),
                           area_m2=rng.uniform(4, 40, n)))
    pit = core.assign_det_ids(df, "pit", 11)
    pad = core.assign_det_ids(df, "pad", 12)
    assert sorted(pit) == list(range(1, n + 1))
    assert sorted(pad) == list(range(1_000_001, 1_000_001 + n))
    assert abs(spearmanr(pit, df.score)[0]) < 0.15           # the old ids had rho = -1.0 within source
    assert np.array_equal(pit, core.assign_det_ids(df.sample(frac=1, random_state=3).sort_index(), "pit", 11))
    # row order of the input does not change ids (keyed on prediction values, not position)
    sh = df.iloc[::-1].reset_index(drop=True)
    assert dict(zip(sh.score, core.assign_det_ids(sh, "pit", 11))) == dict(zip(df.score, pit))


def test_hungarian_gated_matches_dense_oracle():
    """5.6 memory. The gated per-component solve must equal the dense gated Hungarian (oracle)."""
    from scipy.optimize import linear_sum_assignment
    rng = np.random.default_rng(2)
    for _ in range(5):
        rec, det = rng.uniform(0, 600, (80, 2)), rng.uniform(0, 600, (70, 2))
        D = np.hypot(rec[:, None, 0] - det[None, :, 0], rec[:, None, 1] - det[None, :, 1])
        C = np.where(D <= 40, D, 1e9)
        a, b = linear_sum_assignment(C)
        ok = C[a, b] < 1e9
        i, j, d = core.hungarian(rec, det, 40)
        assert len(i) == ok.sum()
        assert d.sum() == pytest.approx(D[a[ok], b[ok]].sum())
        assert len(set(j)) == len(j) and len(set(i)) == len(i) and (d <= 40).all()


def test_hungarian_memory_is_bounded():
    import tracemalloc
    rng = np.random.default_rng(0)
    n = 6000                                   # dense float64 cost and distance matrices would need 576 MB
    rec, det = rng.uniform(0, 50000, (n, 2)), rng.uniform(0, 50000, (n, 2))
    tracemalloc.start()
    i, _, _ = core.hungarian(rec, det, 100.0)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak < 150e6 and len(i) > 0


def test_torus_null_accepts_every_direction():
    """5.6-02. Records hug the west edge of a square footprint. Old rule rejects shifts by direction; torus keeps all."""
    box_ = (0.0, 0.0, 1000.0, 1000.0)
    rec = np.c_[np.full(50, 20.0), np.linspace(100, 900, 50)]
    elig = lambda xy: (xy[:, 0] >= 0) & (xy[:, 0] <= 1000) & (xy[:, 1] >= 0) & (xy[:, 1] <= 1000)
    rate = lambda xy: {1: 0.0}
    old = core.shift_null(rec, elig, rate, n_shift=200, max_loss=0.1, rng=np.random.default_rng(1))
    new = core.shift_null(rec, elig, rate, n_shift=200, max_loss=0.1, rng=np.random.default_rng(1), wrap_bbox=box_)
    # hand oracle: any westward component of 200 to 500 m pushes all 50 records out, so westward shifts are rejected
    assert old["direction"]["spread"] > 0.5 and old["rejected"] > 0
    assert len(new["draws"]) == 200 and new["rejected"] == 0 and new["retained"] == [50] * 200
    assert new["direction"]["spread"] == 0.0


def test_rates_and_excess():
    det = np.array([[0.0, 0.0], [100.0, 0.0]])
    rec = np.array([[5.0, 0.0], [60.0, 0.0], [500.0, 0.0]])
    r = core.nn_rates(rec, det, [10, 50])
    assert r[10] == pytest.approx(1 / 3) and r[50] == pytest.approx(2 / 3)
    e = core.excess(0.5, [0.5] * 50)
    assert e["norm_excess"] == pytest.approx(0.0)
    e = core.excess(0.6, np.linspace(0.1, 0.3, 100))
    assert e["norm_lo"] > 0 and e["excess"] == pytest.approx(0.4)


def test_pad_rates_inside_and_within():
    from shapely.geometry import box
    pads = [box(0, 0, 10, 10)]
    rec = np.array([[5.0, 5.0], [15.0, 5.0], [100.0, 100.0]])
    r = core.pad_rates(rec, pads, [0, 10])
    assert r[0] == pytest.approx(1 / 3) and r[10] == pytest.approx(2 / 3)
    f = core.pad_rate_fn(pads, [0])
    assert f(rec)[0] == pytest.approx(1 / 3)


def test_shift_null_rejects_lossy_shifts():
    rec = np.array([[0.0, 0.0], [1.0, 1.0]])
    never = lambda xy: np.zeros(len(xy), bool)
    out = core.shift_null(rec, never, lambda xy: {1: 0.0}, n_shift=5, rng=np.random.default_rng(1), max_tries=3)
    assert out["draws"] == [] and out["rejected"] == 15
    always = lambda xy: np.ones(len(xy), bool)
    out = core.shift_null(rec, always, lambda xy: {1: 0.0}, n_shift=5, rng=np.random.default_rng(1))
    assert len(out["draws"]) == 5 and out["retained"] == [2] * 5


def test_assign_global_vs_per_status():
    rec = np.array([[0.0, 0.0], [1.0, 0.0]])
    grp = np.array(["active", "orphan_abandoned"], dtype=object)
    det = np.array([[0.5, 0.0]])
    g = core.assign(rec, grp, det, gate=10, mode="global")
    p = core.assign(rec, grp, det, gate=10, mode="per_status")
    assert len(g) == 1 and len(p) == 2
    assert {r["proposal_type"] for r in p} == {"competing_per_status"}


def test_link_ppv_bounds():
    b = core.link_ppv_bounds(["correct"] * 8 + ["wrong"] * 1 + ["ambiguous"] * 1)
    assert b["ppv_lower"] == pytest.approx(0.8) and b["ppv_upper"] == pytest.approx(0.9)
    assert b["ppv_lower_ci_lo"] < 0.8 < b["ppv_upper_ci_hi"]
    with pytest.raises(ValueError):
        core.link_ppv_bounds(["maybe"])


def test_missing_input_names_the_input(tmp_path):
    cfg = {"inputs": {"thing": {"path": str(tmp_path / "nope.gpkg"), "hint": "build it"}}}
    with pytest.raises(th.MissingInput) as e:
        th.inp(cfg, "thing")
    assert "thing" in str(e.value) and "build it" in str(e.value)


def test_resolve_specs():
    assert th.resolve("@exp:5.6/src").name == "src"
    assert th.resolve("plain/path").as_posix() == "plain/path"


# ----------------------------------------------------------------------------- synthetic end-to-end
def _synthetic(tmp_path):
    """Raw upstream layers are written in the producers' shapes, then the real S0 builder makes the full output
    that S1 consumes unmodified. Matched pits get the highest scores, as on 9t, so an id that followed the old
    concat-and-number rule would put every matched row first."""
    import geopandas as gpd
    from shapely.geometry import box, Point
    import _records_full_detector_output_9t as s0
    rng = np.random.default_rng(0)
    blocks = gpd.GeoDataFrame(
        dict(block_id=[0, 1, 2, 3], ix=[0, 1, 0, 1], iy=[0, 0, 1, 1], n_pits=[3, 3, 3, 3], n_pads=[2, 2, 2, 2]),
        geometry=[box(X0 + i * 375, Y0 + j * 375, X0 + (i + 1) * 375, Y0 + (j + 1) * 375)
                  for i, j in [(0, 0), (1, 0), (0, 1), (1, 1)]], crs=CRS)
    bp = tmp_path / "blocks.gpkg"
    blocks.to_file(bp, layer="blocks", driver="GPKG")
    pc = X0 + rng.uniform(20, 730, (24, 2))
    pc[:, 1] += Y0 - X0
    score = np.r_[np.linspace(0.99, 0.80, 16), np.linspace(0.79, 0.50, 8)]
    raw = gpd.GeoDataFrame(dict(score=score, dup_on_pit=[1] * 16 + [0] * 8, near_pit_m=[0.0] * 16 + [60.0] * 8,
                                fold=0, thr_used=0.5),
                           geometry=[Point(x, y).buffer(2) for x, y in pc], crs=CRS)
    cand = tmp_path / "cand.gpkg"
    raw.iloc[:16].to_file(cand, layer="matched", driver="GPKG")
    raw.iloc[16:].to_file(cand, layer="undecided", driver="GPKG")
    padp = tmp_path / "pad_products.gpkg"
    pad_geoms = [Point(x, y).buffer(15) for x, y in pc[:8]]
    gpd.GeoDataFrame(dict(score=np.linspace(0.9, 0.6, 8)), geometry=pad_geoms, crs=CRS).to_file(
        padp, layer="model_geometry", driver="GPKG")
    ann = tmp_path / "ann.gpkg"
    gpd.GeoDataFrame(dict(pit_inside_id=np.arange(16)), geometry=list(raw.geometry[:16]), crs=CRS).to_file(
        ann, layer="pit_inside", driver="GPKG")
    gpd.GeoDataFrame(dict(pad_id=np.arange(6)), geometry=pad_geoms[:6], crs=CRS).to_file(
        ann, layer="plat", driver="GPKG")
    # active records sit on detections (a positive control), orphan records are random
    act = pc[:12] + rng.normal(0, 2, (12, 2))
    orp = np.c_[X0 + rng.uniform(20, 730, 12), Y0 + rng.uniform(20, 730, 12)]
    xy = np.r_[act, orp]
    st = ["Active"] * 12 + ["DEP Orphan List"] * 12
    dep = gpd.GeoDataFrame(dict(PERMIT_NUM=[f"121-{10000 + i}" for i in range(24)], WELL_STATU=st),
                           geometry=gpd.points_from_xy(xy[:, 0], xy[:, 1]), crs=CRS)
    wp = tmp_path / "dep.gpkg"
    dep.to_file(wp, driver="GPKG")
    here = Path(__file__).resolve().parent
    cfg = json.loads((here / "config_5_6.json").read_text())
    cfg["tile_bbox"] = [X0, Y0, X0 + 750, Y0 + 750]
    cfg["pit"]["expected_predictions"] = 24
    pp, dp = tmp_path / "pit.gpkg", tmp_path / "pad.gpkg"
    cfg["inputs"].update(pit_candidates=str(cand), pad_products=dict(path=str(padp), layer="model_geometry"),
                         full_pit=str(pp), full_pad=str(dp), annotations=str(ann), pit_blocks=str(bp),
                         pad_blocks=str(bp), dep_wells=str(wp))
    cfg["outputs"].update(full_pit=str(pp), full_pad=str(dp), row_counts=str(tmp_path / "rows.csv"),
                          id_policy=str(tmp_path / "ids.json"), runs=str(tmp_path / "runs"),
                          adjudication_sheet=str(tmp_path / "sheet.csv"))
    cfg["null"]["shift_min_m"], cfg["null"]["shift_max_m"] = 50.0, 120.0
    cp = tmp_path / "cfg.json"
    cp.write_text(json.dumps(cfg))
    assert s0.main(["--config", str(cp)]) == 0
    return cp, tmp_path


def test_end_to_end_association(tmp_path):
    import geopandas as gpd
    import _records_assoc_v2_9t as v2
    import _records_link_ppv_sample_9t as ppv
    cp, tmp = _synthetic(tmp_path)
    pit, pad = gpd.read_file(tmp / "pit.gpkg"), gpd.read_file(tmp / "pad.gpkg")
    assert sorted(pit.det_id) == list(range(1, 25)) and sorted(pad.det_id) == list(range(1_000_001, 1_000_009))
    assert set(pit.kind) == {"pit"} and set(pad.kind) == {"pad"} and "cand_id" not in pit
    matched_ids = set(pit.loc[pit.source == "matched", "det_id"])
    assert matched_ids != set(range(1, 17))                # 5.6-01: matched rows are no longer ids 1..16
    ids = json.loads((tmp / "ids.json").read_text())
    assert ids["seed_pit"] == 20261106 and ids["seed_pad"] == 20261107 and "permutation" in ids["det_id_policy"]
    assert v2.main(["--config", str(cp), "--n-shift", "25"]) == 0
    run = next((tmp / "runs").glob("*_recassoc_*"))
    s = json.loads((run / "summary.json").read_text())
    assert s["positive_control"]["passed"] is True
    R = pd.read_csv(run / "rates.csv")
    assert set(R.detector_set) == {"full", "novel", "annotated"}
    assert (R.evidence_level == "a").all()
    has = R.n_records > 0                                   # 5.6-02: torus null computable for every group with records
    assert (R[has].null_status == "ok").all() and (R[has].shifts_accepted == 25).all()
    assert (R[~has].null_status == "not_computable").all()
    P = pd.read_csv(run / "proposals.csv")
    pit_p = P[P.proposal_type == "global_one_to_one"]
    assert pit_p.det_id.is_unique and pit_p.permit.is_unique
    assert (run / "_PROVENANCE.json").exists()
    S = ppv.draw(P, [0, 10, 25, 50], 10, 1)
    assert "det_score" not in S and "det_source" not in S
    assert not S.link_id.is_monotonic_increasing and not S.det_id.is_monotonic_increasing


def test_ppv_draw_blinds_score():
    import _records_link_ppv_sample_9t as ppv
    P = pd.DataFrame(dict(level="pit", link_id=range(40), dist_m=np.linspace(0, 99, 40), group="active",
                          det_score=0.9, det_source="matched", proposal_type="global_one_to_one"))
    S = ppv.draw(P, [0, 10, 25, 50], 20, 1)
    assert len(S) == 20 and "det_score" not in S and "det_source" not in S
    S["outcome"] = ["correct"] * 15 + ["ambiguous"] * 5
    res = ppv.score(S, 0.5)
    assert res["overall"]["ppv_lower"] < res["overall"]["ppv_upper"]


def test_gnss_paired_errors():
    import _records_gnss_validation_9t as gv
    P = pd.DataFrame(dict(level="pit", permit=["a", "b"], rec_x=[X0 + 10, X0 + 20], rec_y=[Y0, Y0],
                          det_x=[X0 + 1, X0 + 30], det_y=[Y0, Y0]))
    G = pd.DataFrame(dict(PERMIT_NUM=["a", "b", "c"], gx=[X0, X0 + 20, X0], gy=[Y0, Y0, Y0]))
    m = gv.paired_errors(P, G, (X0, Y0), 375.0)
    assert list(m.change_m.round(1)) == [9.0, -10.0]
    res = gv.summarise(m, G, margin=5.0, B=50, seed=0)
    assert res["abstentions"] == 1 and res["pit"]["wrong_matches"] == 1


def test_cohort_keys(tmp_path):
    import _records_cohort_strata_9t as co
    csv = tmp_path / "o.csv"
    pd.DataFrame(dict(Well_ident=["API:3712112345", "API:3712199999"], County=["Venango", "Butler"])).to_csv(csv)
    keys = co.old_keys_2022(csv)
    assert keys == {12345}
    dep = pd.DataFrame(dict(PERMIT_NUM=["121-12345", "121-55555"], WELL_STATU=["DEP Orphan List"] * 2,
                            x=[0, 0], y=[0, 0]))
    t = co.cohort_table(dep, keys, ["DEP Orphan List", "DEP Abandoned List"])
    assert list(t.cohort) == ["listed_2022", "newly_documented"]


def test_cohort_uses_the_s1_status_group():
    """Cohort definitions must equal the S1 orphan_abandoned group (review minor: they disagreed)."""
    import _records_cohort_strata_9t as co
    cfg = json.loads((Path(__file__).resolve().parent / "config_5_6.json").read_text())
    dep = pd.DataFrame(dict(PERMIT_NUM=["121-1", "121-2", "121-3"], WELL_STATU=["DEP Orphan List", "Abandoned", "Active"],
                            x=[0, 0, 0], y=[0, 0, 0]))
    t = co.cohort_table(dep, set(), cfg["status_groups"][co.COHORT_GROUP])
    assert list(t.PERMIT_NUM) == ["121-1"]


def test_other_states_refuses_non_metric_crs():
    from pyproj import CRS as P
    import _records_other_states_assoc as os_
    assert os_.check_metric_crs(P.from_epsg(6346), "x") is not None
    for code in (4326, 2272):                    # geographic degrees, US survey feet
        with pytest.raises(SystemExit):
            os_.check_metric_crs(P.from_epsg(code), "x")


def test_rel_paths_have_no_drive():
    p = th.rel(th.resolve("@exp:5.6/results/tables/x.csv"))
    assert p == "expansions/5_tasks/5_6_record_association/results/tables/x.csv"
