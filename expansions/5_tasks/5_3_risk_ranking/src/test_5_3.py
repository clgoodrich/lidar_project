"""Smoke tests for expansion 5.3 risk ranking on tiny synthetic data (seconds, no GPU, no network).

Run
    python -m pytest -q expansions/5_tasks/5_3_risk_ranking/src/test_5_3.py -p no:cacheprovider
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
import _task5_helpers as th  # noqa: E402
import _risk_ranking_core as rc  # noqa: E402

X0, Y0 = 619500.0, 4593000.0


# ----------------------------------------------------------------------------- unit
def test_p_bands_are_ordinal_terciles():
    b, cuts = rc.p_bands(np.linspace(1, 0, 12), k=9)
    assert list(b[:3]) == ["K1"] * 3 and b[-1] == "below_K"
    assert set(b) == {"K1", "K2", "K3", "below_K"}
    assert cuts[0] > cuts[1] > cuts[2]


def test_sentinel_is_its_own_age_class():
    br = rc.age_bracket(pd.Series(["1800-01-01", "1950-05-01", "1970-01-01", "1990-01-01", None]),
                        {"1800-01-01", "1900-01-01"})
    assert list(br) == ["unknown_sentinel", "pre1956", "1956_1984", "1985_on", "missing"]


def test_lineage_check_blocks_endpoint():
    rc.check_lineage({"h_status": ["dep_wells:WELL_STATU"]}, ["flux_kg_h"], ["field_flux"])
    with pytest.raises(AssertionError):
        rc.check_lineage({"h_gas": ["dep_inspections:gas_detected"]}, ["gas_detected"], ["dep_inspections"])
    with pytest.raises(AssertionError):
        rc.check_lineage({"flux_kg_h": ["x:y"]}, ["flux_kg_h"], [])


def test_banned_phrases():
    assert rc.banned_phrase_hits("a validated list", ["validated"], ["risk score"]) == ["validated"]
    assert rc.banned_phrase_hits("the risk score", [], ["risk score"]) == ["risk score"]
    assert rc.banned_phrase_hits("risk score scenario A", [], ["risk score"]) == []


def test_enrichment_and_scenarios():
    rank = np.arange(1, 11)
    ev = np.r_[np.ones(2, bool), np.zeros(8, bool)]
    assert rc.enrichment(rank, ev, 2) == pytest.approx(5.0)
    df = pd.DataFrame(dict(P=[1, 1, .5, .25], H=[.1, .9, .5, .2], E=[.9, .1, .5, .2],
                           p_source=["record", "record", "feature_band", "feature_band"]))
    R = rc.scenario_ranks(df)
    assert R.rank_A.tolist()[0] == 1 and R.rank_B.tolist()[1] == 1
    assert set(R.rank_C[:2]) == {1, 2}
    assert len(rc.weight_grid(0.5)) == 9


def test_receptor_error_buffer():
    import geopandas as gpd
    g = gpd.GeoDataFrame({"pos_error_m": [0.0, 30.0]},
                         geometry=gpd.points_from_xy([X0 + 40, X0 + 70], [Y0, Y0]), crs="EPSG:6346")
    r = rc.Receptor("water_wells", "points", g, "pos_error_m")
    ex = r.exposure(np.array([[X0, Y0]]), [50])
    assert ex["water_wells_n_50"][0] == 2 and ex["water_wells_n_50_strict"][0] == 1


# ----------------------------------------------------------------------------- pipeline
@pytest.fixture()
def synth(tmp_path):
    import geopandas as gpd
    from shapely.geometry import LineString, box
    rng = np.random.default_rng(1)
    blocks = gpd.GeoDataFrame({"block_id": [0, 1, 2, 3], "n_pits": [3, 2, 0, 4]},
                              geometry=[box(X0 + i * 375, Y0, X0 + (i + 1) * 375, Y0 + 375) for i in range(4)],
                              crs="EPSG:6346")
    blocks.to_file(tmp_path / "blocks.gpkg", layer="blocks", driver="GPKG")
    n = 30
    xs, ys = X0 + rng.uniform(0, 1500, n), Y0 + rng.uniform(0, 375, n)
    stat = rng.choice(["Active", "DEP Orphan List", "Plugged OG Well", "DEP Abandoned List"], n)
    spud = rng.choice(["1800-01-01", "1975-03-02", "1990-01-01", "1950-02-02"], n)
    plug = np.where(stat == "Plugged OG Well", "1999-01-01", None)
    gpd.GeoDataFrame(dict(PERMIT_NUM=[f"121-{i}" for i in range(n)], WELL_STATU=stat, SPUD_DATE=spud,
                          DATE_PLUGG=plug, TOTAL_MAXI=[None] * n),
                     geometry=gpd.points_from_xy(xs, ys), crs="EPSG:6346").to_file(tmp_path / "dep.gpkg")
    m = 20
    cx, cy = X0 + rng.uniform(0, 1500, m), Y0 + rng.uniform(0, 375, m)
    gpd.GeoDataFrame(dict(det_id=np.arange(m), cand_id=np.r_[np.arange(10), np.arange(10)] + 1,
                          score=rng.uniform(0.5, 0.9, m), cx=cx, cy=cy,
                          source=["matched"] * 10 + ["undecided"] * 10),
                     geometry=gpd.points_from_xy(cx, cy).buffer(2), crs="EPSG:6346").to_file(tmp_path / "cand.gpkg")
    gpd.GeoDataFrame({"MTFCC": ["S1400"]}, geometry=[LineString([(X0, Y0 + 100), (X0 + 1500, Y0 + 200)])],
                     crs="EPSG:6346").to_file(tmp_path / "roads.gpkg")
    gpd.GeoDataFrame({"pos_error_m": rng.uniform(0, 40, 15)},
                     geometry=gpd.points_from_xy(X0 + rng.uniform(0, 1500, 15), Y0 + rng.uniform(0, 375, 15)),
                     crs="EPSG:6346").to_file(tmp_path / "ww.gpkg")
    cfg = json.loads((HERE / "config_5_3.json").read_text(encoding="utf-8"))
    for k in list(cfg["inputs"]):
        cfg["inputs"][k]["path"] = str(tmp_path / f"absent_{k}")
    for k, f in dict(dep_wells="dep.gpkg", candidates_full="cand.gpkg", pit_blocks="blocks.gpkg",
                     roads="roads.gpkg", water_wells="ww.gpkg").items():
        cfg["inputs"][k]["path"] = str(tmp_path / f)
    cfg["inputs"]["water_wells"]["kind"] = "points"
    cfg["inputs"]["field_flux"]["path"] = str(tmp_path / "flux.csv")
    cfg["inputs"]["prereg"]["path"] = str(tmp_path / "prereg.json")
    cfg["outputs"] = {k: str(tmp_path / "out" / Path(v.split("/", 1)[1]).name) for k, v in cfg["outputs"].items()}
    cfg["n_dirichlet"], cfg["n_boot"] = 20, 5
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path, p, cfg


def test_pipeline_runs_and_orders(synth):
    tmp, cp, cfg = synth
    import _risk_data_audit_9t as s0
    import _risk_exposure_layers_9t as s1
    import _risk_hazard_proxy_9t as s2
    import _risk_scenarios_9t as s3
    import _risk_sensitivity_9t as s4
    import _risk_rank_bootstrap_9t as s5
    import _risk_endpoint_check_9t as s6
    import _risk_report_tables_9t as s7
    c = ["--config", str(cp)]
    with pytest.raises(th.MissingInput):
        s3.main(c)                                   # S1 has not run
    assert s0.main(c) == 0
    audit = pd.read_csv(th.resolve(cfg["outputs"]["audit"]))
    assert not audit.loc[audit.layer == "buildings", "present"].item()
    assert s1.main(c) == 0
    summ = json.loads(Path(cfg["outputs"]["exposure_summary"]).read_text())
    assert "water_wells" in summ["receptors_present"] and "buildings" in summ["missing_components"]
    assert summ["k"] == int(round(40 * 4 * 0.140625))        # every block of the grid, not the 3 with pits
    assert s2.main(c) == 0
    H = pd.read_csv(cfg["outputs"]["hazard_csv"])
    assert "h_depth" not in H                        # fully missing column dropped
    # prereg written before S3, so the ranks carry its hash
    prereg = dict(top_n=5, delta_enrich_gain=0.5, primary_scenario="A", seed=7,
                  endpoint_event_rule={"kind": "rate_cutoff", "flux_cutoff_kg_h": 0.1})
    Path(cfg["inputs"]["prereg"]["path"]).write_text(json.dumps(prereg))
    assert s3.main(c) == 0
    R = pd.read_csv(cfg["outputs"]["ranks_csv"])
    assert {"P", "H", "E", "p_source", "rank_A", "rank_D", "tie_A"} <= set(R.columns)
    # candidates have no plugging record, so under the default rule their H is unrankable (never skipped)
    assert R.loc[R.p_source == "feature_band", "rank_B"].isna().all()
    assert R.loc[R.p_source == "record", "rank_B"].notna().all()
    s3summ = json.loads(Path(cfg["outputs"]["ranks_summary"]).read_text())
    assert s3summ["e_status"] == "ok" and s3summ["index_rules"]["H"]["rule"] == "unrankable"
    assert (R.loc[R.p_source == "feature_band", "conditional"] == th.CONDITIONAL).all()
    assert s4.main(c + ["--no-figure"]) == 0
    assert s5.main(c + ["--no-figure"]) == 0
    si = pd.read_csv(cfg["outputs"]["site_interval_csv"])
    assert si.topn_freq.between(0, 1).all()
    # endpoint, then an order violation when the prereg changes afterwards
    rec = R[R.p_source == "record"]
    pd.DataFrame(dict(PERMIT_NUM=rec.site_id.str[4:], flux_kg_h=np.linspace(0, 1, len(rec)))).to_csv(
        cfg["inputs"]["field_flux"]["path"], index=False)
    assert s6.main(c + ["--n-boot", "20"]) == 0
    E = pd.read_csv(cfg["outputs"]["endpoint_csv"])
    assert "A" in set(E.order) and "records_only" in set(E.order)
    prereg["top_n"] = 6
    Path(cfg["inputs"]["prereg"]["path"]).write_text(json.dumps(prereg))
    with pytest.raises(SystemExit, match="ORDER VIOLATION"):
        s6.main(c)
    assert s7.main(c) == 0


# ----------------------------------------------------------------------------- review 2026-11-06 regressions
def test_index_missing_component_is_not_skipped():
    """5.3-01. Expected values by hand. h_a ties at 3 (mid-rank 0.5 each). Site 1 lacks h_b."""
    df = pd.DataFrame(dict(h_a=[3.0, 3.0], h_b=[0.0, np.nan]))
    cols = {"h_a": 1, "h_b": 1}
    v = rc.index_from(df, cols)
    assert v[0] == pytest.approx(0.5) and np.isnan(v[1])          # old code gave [0.5, 0.5]
    # declared imputation: h_b missing -> 1, so h_b ranks [0.25, 0.75] and the means are [0.375, 0.625]
    v = rc.index_from(df, cols, rc.IndexRule("impute", impute={"h_b": 1.0}))
    assert v.tolist() == pytest.approx([0.375, 0.625])
    # declared partial coverage: half the components is enough
    v = rc.index_from(df, cols, rc.IndexRule(min_coverage=0.5))
    assert v.tolist() == pytest.approx([0.5, 0.5])
    with pytest.raises(ValueError, match="no declared"):
        rc.index_from(df, cols, rc.IndexRule("impute"))


def test_e_with_one_component_is_unusable():
    """5.3-02. One 0/1 road column cannot order the top N."""
    with pytest.raises(rc.IndexUnusable, match="1 component"):
        rc.check_index(np.array([0, 1, 1, 0.0]), 1, 2, 3, "E")
    with pytest.raises(rc.IndexUnusable, match="2 distinct"):
        rc.check_index(np.array([0, 1, 1, 0.0]), 2, 2, 3, "E")
    import _risk_scenarios_9t as s3
    sites = pd.DataFrame(dict(site_id=["a", "b", "c"], x=0.0, y=0.0, p_source="record", p_band="record",
                              status="Active", block_id=0, conditional="", cand_score=np.nan, P=1.0,
                              roads_n_100=[0, 1, 1]))
    H = pd.DataFrame(dict(site_id=["a", "b", "c"], h_status=[3, 1, 2]))
    df = s3.assemble(sites, H, {"roads_n_100": 1}, cfg={"e_min_distinct": 2})
    assert df.E.isna().all() and df.attrs["e_status"].startswith("unusable")
    R = s3.rank_all(df)
    assert R.rank_A.isna().all() and R.rank_B.tolist() == [1, 3, 2]   # B ranks by H alone, E absent everywhere


def test_ties_are_ties_not_row_order():
    r = rc._lex_rank([np.array([1.0, 1.0, 0.0])])
    assert r.tolist() == [1, 1, 3]                                    # old code gave [1, 2, 3]
    assert rc.tie_size(r).tolist() == [2, 2, 1]
    df = pd.DataFrame(dict(P=[1.0] * 3, H=[0.5] * 3, E=[0.2, 0.2, 0.9], p_source="record"))
    R = rc.scenario_ranks(df)
    assert R.rank_A.tolist() == [2, 2, 1] and R.rank_B.tolist() == [2, 2, 1]
    assert rc.top_set(R.rank_A.to_numpy(), 2, ["a", "b", "c"]) == {"a", "b", "c"}   # the tie at N is kept
    assert np.isnan(rc.jaccard(set(), set()))                        # nothing rankable is not agreement


def test_rank01_never_hits_zero():
    assert rc.rank01(np.array([1.0, 2.0])).tolist() == pytest.approx([0.25, 0.75])
    assert rc.rank01(np.array([5.0])).tolist() == [0.5]
    p = rc.rank01(np.array([0.0, 1.0, 1.0, 1.0]))
    assert p[0] == pytest.approx(0.125) and p[0] > 0                 # old code gave exactly 0


def test_endpoint_fallback_key_is_read():
    f = np.arange(1, 11, dtype=float)
    ev, used = rc.endpoint_events_rule(f, {"kind": "rate_cutoff", "flux_cutoff_kg_h": None,
                                           "top_decile_fallback": True})
    assert ev.tolist() == [False] * 9 + [True] and used.startswith("top_decile")
    with pytest.raises(ValueError):
        rc.endpoint_events_rule(f, {"kind": "rate_cutoff", "flux_cutoff_kg_h": None})
    assert rc.endpoint_events(f, {"kind": "rate_cutoff", "flux_cutoff_kg_h": 5}).sum() == 6


def test_build_sites_merges_every_candidate_in_radius():
    rec = pd.DataFrame(dict(PERMIT_NUM=["121-1"], x=[0.0], y=[0.0], WELL_STATU=["Active"]))
    cand = pd.DataFrame(dict(cand_id=[7, 8, 9], score=[0.9, 0.8, 0.7], x=[10.0, 20.0, 500.0], y=0.0, block_id=0))
    s, _ = rc.build_sites(rec, cand, k=3, assoc_radius=50)
    assert sorted(s.site_id) == ["cand_9", "rec_121-1"]              # old code kept cand_8 as its own site
    r = s.set_index("site_id").loc["rec_121-1"]
    assert r.n_assoc_cand == 2 and r.assoc_cand_id == 7


def test_footprint_uses_every_block(tmp_path):
    import geopandas as gpd
    from shapely.geometry import box
    import _risk_io_9t as rio
    gpd.GeoDataFrame({"block_id": [0, 1], "n_pits": [3, 0]},
                     geometry=[box(X0, Y0, X0 + 375, Y0 + 375), box(X0 + 375, Y0, X0 + 750, Y0 + 375)],
                     crs="EPSG:6346").to_file(tmp_path / "b.gpkg", layer="blocks", driver="GPKG")
    cfg = {"inputs": {"pit_blocks": {"path": str(tmp_path / "b.gpkg")}}, "block_size_m": 375.0}
    assert rio.footprint_km2(cfg) == pytest.approx(2 * 0.140625)    # old code gave 0.140625


def test_audit_path_is_repo_relative():
    import _risk_data_audit_9t as s0
    cfg = {"inputs": {"x": {"path": "@exp:5.3/data/processed/never_there.gpkg"}}}
    row, _ = s0.audit_layer("x", cfg["inputs"]["x"], cfg)
    assert row["path"] == "expansions/5_tasks/5_3_risk_ranking/data/processed/never_there.gpkg"


def test_enrichment_undefined_share_is_reported():
    """All 20 events sit in one of 10 cells. A resample that misses that cell has no event, so enrichment is
    undefined there. Oracle: replay the bootstrap index draws and count resamples without the event cell."""
    import _risk_endpoint_check_9t as s6
    n_cell, per = 10, 20
    cells = [f"c{i}" for i in range(n_cell)]
    d = pd.DataFrame(dict(site_id=[f"rec_{i}" for i in range(n_cell * per)],
                          cell=np.repeat(cells, per), event=np.repeat(np.arange(n_cell) == 3, per),
                          weight=1.0, flux_kg_h=1.0, rank_A=np.arange(1, n_cell * per + 1, dtype=float),
                          H=0.5, E=0.5))
    H = pd.DataFrame(dict(site_id=d.site_id, h_status=1.0, h_age=1.0))
    cfg = {"top_n_share": 0.05, "min_endpoint_events": 15, "cluster_cell_m": 1000.0}
    prereg = {"top_n": 10, "primary_scenario": "A", "seed": 11, "delta_enrich_gain": 0.5}
    B = 200
    out = s6.analyse(d, H, cfg, prereg, None, B=B).set_index("order")
    rng = np.random.default_rng(11)
    ev_ix = sorted(cells).index("c3")
    expect = np.mean([ev_ix not in rng.integers(0, n_cell, n_cell) for _ in range(B)])
    assert out.loc["A", "undefined_share"] == pytest.approx(expect) and expect > 0
    assert np.isnan(out.loc["A", "enrich_lo"]) and out.loc["A", "decision"] == "inconclusive"


def test_decided_defaults_are_in_the_config():
    """Defaults accepted 2026-11-06. H unrankable, E min_coverage 1.0, max_undefined 0."""
    import json
    cfg = json.loads((HERE / "config_5_3.json").read_text())
    assert cfg["index_missing"]["H"] == {"rule": "unrankable", "min_coverage": 1.0, "impute": {}}
    assert cfg["index_missing"]["E"]["rule"] == "unrankable" and cfg["index_missing"]["E"]["min_coverage"] == 1.0
    assert cfg["max_undefined"] == 0.0


def test_prereg_cannot_loosen_max_undefined():
    """A prereg declaring 0.2 is refused. The old code would have used 0.2 and turned the undefined draws of the
    test above into a finite interval."""
    import _risk_endpoint_check_9t as s6
    cfg = {"max_undefined": 0.0}
    assert s6.max_undefined(cfg, {}) == 0.0
    assert s6.max_undefined(cfg, {"max_undefined": 0}) == 0.0
    with pytest.raises(SystemExit, match="differs from the decided value"):
        s6.max_undefined(cfg, {"max_undefined": 0.2})


def test_provenance_paths_are_repo_relative(tmp_path):
    """Every repo path in a 5.3 provenance file is repo-relative, params and argv included."""
    import json
    import _risk_io_9t as rio
    inside = rio.ek.REPO / "expansions" / "5_tasks" / "5_3_risk_ranking" / "src" / "config_5_3.json"
    p = rio.write_provenance(tmp_path, inputs=[inside], params={"src": str(inside), "nested": [str(inside)]})
    txt = p.read_text()
    assert str(rio.ek.REPO) not in txt and str(rio.ek.REPO).replace("\\", "/") not in txt
    d = json.loads(txt)
    want = "expansions/5_tasks/5_3_risk_ranking/src/config_5_3.json"
    assert d["inputs"][0]["path"] == want and d["params"]["src"] == want and d["params"]["nested"] == [want]
