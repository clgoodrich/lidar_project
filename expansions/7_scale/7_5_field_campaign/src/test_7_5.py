"""Smoke tests for 7.5 on tiny synthetic data. CPU only, no network, seconds.

Run
    python -m pytest -q expansions/7_scale/7_5_field_campaign/src/test_7_5.py -p no:cacheprovider
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
import _field_sample_draw_frames as fd  # noqa: E402

CRS = "EPSG:6346"
X0, Y0 = 620000.0, 4594000.0


def _world(tmp: Path) -> dict:
    import geopandas as gpd
    from shapely.geometry import Point, box
    rng = np.random.default_rng(5)
    blocks = gpd.GeoDataFrame({"block_id": [0, 1, 2, 3]},
                              geometry=[box(X0 + i * 375, Y0, X0 + (i + 1) * 375, Y0 + 375) for i in range(4)], crs=CRS)
    blocks.to_file(tmp / "blocks.gpkg", driver="GPKG")
    pd.DataFrame({"block_id": [0, 1], "role": "comparative_audit"}).to_csv(tmp / "audit.csv", index=False)
    pits = [Point(X0 + rng.uniform(5, 745), Y0 + rng.uniform(5, 370)).buffer(3) for _ in range(80)]
    pads = [Point(X0 + rng.uniform(20, 730), Y0 + rng.uniform(20, 355)).buffer(15) for _ in range(15)]
    gpd.GeoDataFrame(geometry=pits, crs=CRS).to_file(tmp / "ann.gpkg", layer="pit_inside", driver="GPKG")
    gpd.GeoDataFrame(geometry=pads, crs=CRS).to_file(tmp / "ann.gpkg", layer="plat", driver="GPKG")
    gpd.GeoDataFrame(geometry=[box(X0 + 2000, Y0, X0 + 3000, Y0 + 1000)], crs=CRS).to_file(tmp / "reserved.gpkg", driver="GPKG")
    wp = [p.centroid for p in pits[:40]] + [Point(X0 + 2100, Y0 + 100), Point(X0 + 2600, Y0 + 600)]
    dates = (["1800-01-01"] * 10 + ["1885-05-01"] * 10 + ["1950-02-02"] * 10 + [None] * 10 + ["1960-01-01", "1890-01-01"])
    gpd.GeoDataFrame({"PERMIT_NUM": [f"P{i}" for i in range(len(wp))], "SPUD_DATE": dates,
                      "WELL_PAD_I": [f"pad{i // 4}" for i in range(len(wp))]}, geometry=wp, crs=CRS).to_file(tmp / "dep.gpkg", driver="GPKG")
    pd.DataFrame({"cand_id": [f"c{i}" for i in range(60)], "class": "pit", "score": rng.random(60),
                  "cx": X0 + rng.uniform(400, 1400, 60), "cy": Y0 + rng.uniform(5, 370, 60), "block_id": 2}).to_csv(tmp / "cands.csv", index=False)
    cfg = fd.load_cfg()
    a = lambda p: {"key": "expansions", "rel": str((tmp / p).resolve())}  # noqa: E731
    cfg["inputs"].update(blocks=a("blocks.gpkg"), audit_blocks=a("audit.csv"), reserved_area=a("reserved.gpkg"),
                         candidates_frozen=a("cands.csv"), historic_marks=a("none.gpkg"))
    cfg["inputs"]["truth"] = {**a("ann.gpkg"), "layers": {"pit": "pit_inside", "pad": "pad"}}
    cfg["inputs"]["dep_wells"] = {**a("dep.gpkg"), "spud_col": "SPUD_DATE", "id_col": "PERMIT_NUM", "pad_col": "WELL_PAD_I"}
    cfg["arm_A"].update(n=30, floor_per_stratum=3)
    cfg["arm_B"].update(n=10)
    cfg["arm_C"].update(n_cells=4)
    return cfg


def test_allocation_and_era():
    al = fd.allocate({"a": 100, "b": 5, "c": 40}, 30, 10)
    assert al["b"] == 5 and sum(al.values()) == 30 and al["a"] > al["c"]
    r = {"sentinel": "1800-01-01", "steel_from_year": 1930, "early_before_year": 1900}
    assert fd.era_class("1800-01-01", r) == "unknown_sentinel" and fd.era_class("1871", r) == "early_dated"
    assert fd.era_class("1955-01-01", r) == "steel_dated" and fd.era_class(None, r) == "no_date"


def test_draw_sheets_ingest_analyse(tmp_path):
    import _field_analysis_bounds as fa
    import _field_results_ingest as fi
    import _field_sample_size_design as fs
    import _field_sheet_generate as fg
    cfg = _world(tmp_path)
    out = tmp_path / "t"
    s = fd.draw(cfg, out)
    assert set(s["by_arm"]) == {"A", "B", "C"}
    with pytest.raises(PermissionError):
        fd.draw(cfg, out)
    key = pd.read_csv(out / "field_sample_key_v1.csv")
    strata = set(key.loc[key["arm"] == "A", "stratum"].str.split("|").str[-1])
    assert "unknown_sentinel" in strata, "the 1800 sentinel is its own stratum"
    a = key[key["arm"] == "A"]
    assert np.isclose((1 / a["pi"]).sum(), a.groupby("stratum")["N_h"].first().sum()), "weights must sum to the frame size"
    blind = pd.read_csv(out / "field_sample_blind_v1.csv")
    assert not {"score", "stratum", "dep_id", "era"} & set(blind.columns)
    chk = fs.design_check(cfg, pd.read_csv(out / "field_frame_counts_v1.csv"))
    assert "exploratory only" in set(chk["supports"])
    paths = fg.write_sheets(blind.drop(columns=["arm", "pi", "weight"]), cfg, tmp_path / "sheets")
    txt = paths[0].read_text()
    assert "methane" in txt.lower() and "score" not in txt.lower()
    # synthetic field records
    rng = np.random.default_rng(1)
    rows = []
    for i, r in blind.iterrows():
        if i % 9 == 0:
            rows.append({"site_id": r.site_id, "visit_id": f"v{i}", "search_round": 1, "access": "permission_refused", "date": "2027-05-01"})
            continue
        ident = rng.choice(["confirmed_well", "definite_non_well", "ambiguous"], p=[0.3, 0.4, 0.3])
        out_c = {"confirmed_well": "confirmed_well", "definite_non_well": "nothing_found", "ambiguous": "unresolved"}[ident]
        rows.append({"site_id": r.site_id, "visit_id": f"v{i}", "search_round": 1, "searcher_id": "s1", "date": "2027-05-02",
                     "access": "visited", "gnss_x": r.x + 2, "gnss_y": r.y - 1, "outcome": out_c, "identity": ident,
                     "identity_basis": "charcoal hearth" if ident == "definite_non_well" else "", "blind_confirmed": True,
                     "evidence_codes": "wellhead" if ident == "confirmed_well" else ""})
        if i % 4 == 1:
            rows.append({**rows[-1], "visit_id": f"v{i}b", "search_round": 2, "searcher_id": "s2"})
    rec = pd.DataFrame(rows)
    for c in fg.ENTRY_COLUMNS:
        if c not in rec:
            rec[c] = np.nan
    r = fi.validate(rec, blind, fg.codebook(cfg), cfg["protocol"]["coord_check_m"])
    log, clean, rep = fi.reconcile(r, blind)
    assert len(clean) == len(blind) and (clean.loc[clean["outcome"] == "inaccessible", "identity"] == "ambiguous").all()
    res = fa.analyse(cfg, clean, key, rep, 100, tmp_path)
    tab = pd.read_csv(tmp_path / "field_bounds_v1.csv")
    assert (tab["lower_bound"] <= tab["upper_bound"] + 1e-12).all() and (tab["interval_lo"] <= tab["lower_bound"] + 1e-12).all()
    assert set(tab["gate"]) <= {"success (precision)", "inconclusive"}
    assert "two_searcher" in res["search_sensitivity"]
    bad = rec.copy(); bad.loc[bad.index[1], ["outcome", "identity"]] = ["steel_anomaly_only", "confirmed_well"]
    with pytest.raises(AssertionError):
        fi.validate(bad, blind, fg.codebook(cfg), 30.0)
