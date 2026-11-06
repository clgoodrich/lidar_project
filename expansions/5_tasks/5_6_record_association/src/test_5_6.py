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


def test_dedupe_rules():
    df = pd.DataFrame(dict(source=["matched", "matched", "undecided", "undecided"], dup_on_pit=[1, 1, 1, 0]))
    assert len(core.dedupe(df, "deployment")) == 3
    assert len(core.dedupe(df, "keep_all")) == 4
    with pytest.raises(ValueError):
        core.dedupe(df, "nonsense")


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
    import geopandas as gpd
    from shapely.geometry import box, Point
    rng = np.random.default_rng(0)
    blocks = gpd.GeoDataFrame(
        dict(block_id=[0, 1, 2, 3], ix=[0, 1, 0, 1], iy=[0, 0, 1, 1], n_pits=[3, 3, 3, 3], n_pads=[2, 2, 2, 2]),
        geometry=[box(X0 + i * 375, Y0 + j * 375, X0 + (i + 1) * 375, Y0 + (j + 1) * 375)
                  for i, j in [(0, 0), (1, 0), (0, 1), (1, 1)]], crs=CRS)
    bp = tmp_path / "blocks.gpkg"
    blocks.to_file(bp, layer="blocks", driver="GPKG")
    pc = X0 + rng.uniform(20, 730, (24, 2))
    pc[:, 1] += Y0 - X0
    pits = gpd.GeoDataFrame(dict(cx=pc[:, 0], cy=pc[:, 1], score=rng.uniform(.5, 1, 24),
                                 source=["matched"] * 16 + ["undecided"] * 8, novel=[0] * 16 + [1] * 8,
                                 det_id=np.arange(24)),
                            geometry=[Point(x, y).buffer(2) for x, y in pc], crs=CRS)
    pp = tmp_path / "pit.gpkg"
    pits.to_file(pp, driver="GPKG")
    pads = gpd.GeoDataFrame(dict(score=np.full(8, .6), source=["matched"] * 6 + ["unmatched"] * 2,
                                 novel=[0] * 6 + [1] * 2, det_id=np.arange(8), cx=pc[:8, 0], cy=pc[:8, 1]),
                            geometry=[Point(x, y).buffer(15) for x, y in pc[:8]], crs=CRS)
    dp = tmp_path / "pad.gpkg"
    pads.to_file(dp, driver="GPKG")
    ann = tmp_path / "ann.gpkg"
    gpd.GeoDataFrame(dict(pit_inside_id=np.arange(16)), geometry=list(pits.geometry[:16]), crs=CRS).to_file(
        ann, layer="pit_inside", driver="GPKG")
    gpd.GeoDataFrame(dict(pad_id=np.arange(6)), geometry=list(pads.geometry[:6]), crs=CRS).to_file(
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
    cfg["inputs"].update(full_pit=str(pp), full_pad=str(dp), annotations=str(ann), pit_blocks=str(bp),
                         pad_blocks=str(bp), dep_wells=str(wp))
    cfg["outputs"]["runs"] = str(tmp_path / "runs")
    cfg["null"]["shift_min_m"], cfg["null"]["shift_max_m"] = 50.0, 120.0
    cfg["null"]["max_loss"] = 0.5
    cp = tmp_path / "cfg.json"
    cp.write_text(json.dumps(cfg))
    return cp, tmp_path


def test_end_to_end_association(tmp_path):
    import _records_assoc_v2_9t as v2
    cp, tmp = _synthetic(tmp_path)
    assert v2.main(["--config", str(cp), "--n-shift", "25"]) == 0
    run = next((tmp / "runs").glob("*_recassoc_*"))
    s = json.loads((run / "summary.json").read_text())
    assert s["positive_control"]["passed"] is True
    R = pd.read_csv(run / "rates.csv")
    assert set(R.detector_set) == {"full", "novel", "annotated"}
    assert (R.evidence_level == "a").all()
    P = pd.read_csv(run / "proposals.csv")
    pit = P[P.proposal_type == "global_one_to_one"]
    assert pit.det_id.is_unique and pit.permit.is_unique
    assert (run / "_PROVENANCE.json").exists()


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
    t = co.cohort_table(dep, keys)
    assert list(t.cohort) == ["listed_2022", "newly_documented"]
