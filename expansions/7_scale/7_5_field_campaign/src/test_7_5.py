"""Tests for 7.5 on tiny synthetic data. CPU only, no network, seconds.

The P2 audit CSV comes from the real P2 writer (into a temp dir). The 5.4 site table and accounting come from
the real 5.4 S1 producer. The 7.5 export goes unmodified into the real 5.4 S3 reader.

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

EXP = HERE.parents[2]
CRS = "EPSG:6346"
X0, Y0 = 620000.0, 4594000.0


def _p2_audit(tmp: Path, audit: list[int], buffer: list[int]) -> Path:
    """Audit CSV written by the real P2 writer, plus the sidecar its --freeze step writes. Temp dir only."""
    sys.path.insert(0, str(EXP / "0_prerequisites" / "p2_audit_set" / "src"))
    import _audit_draw_blocks_9t as dr
    ids = audit + buffer
    tab = pd.DataFrame({"block_id": ids, "dens_t": 1, "slope_t": 2})
    p = tmp / "audit_blocks_9t_v1.csv"
    dr.write_audit_csv(p, tab, {"audit": audit, "buffer": buffer, "share": 0.5}, "block", 100.0, 7)
    Path(str(p) + ".sha256").write_text(f"{fd.ek.sha256(p)}  {p.name}\n", encoding="utf-8")
    return p


def _world(tmp: Path) -> dict:
    import geopandas as gpd
    from shapely.geometry import Point, box
    rng = np.random.default_rng(5)
    blocks = gpd.GeoDataFrame({"block_id": [0, 1, 2, 3]},
                              geometry=[box(X0 + i * 375, Y0, X0 + (i + 1) * 375, Y0 + 375) for i in range(4)], crs=CRS)
    blocks.to_file(tmp / "blocks.gpkg", driver="GPKG")
    audit = _p2_audit(tmp, audit=[0, 1], buffer=[2])
    pits = [Point(X0 + rng.uniform(5, 745), Y0 + rng.uniform(5, 370)).buffer(3) for _ in range(80)]
    pits += [Point(X0 + rng.uniform(760, 1110), Y0 + rng.uniform(5, 370)).buffer(3) for _ in range(10)]   # buffer block
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
    cfg["inputs"].update(blocks=a("blocks.gpkg"), audit_blocks=a(audit.name), reserved_area=a("reserved.gpkg"),
                         candidates_frozen=a("cands.csv"), historic_marks=a("none.gpkg"))
    cfg["inputs"]["truth"] = {**a("ann.gpkg"), "layers": {"pit": "pit_inside", "pad": "pad"}}
    cfg["inputs"]["dep_wells"] = {**a("dep.gpkg"), "spud_col": "SPUD_DATE", "id_col": "PERMIT_NUM", "pad_col": "WELL_PAD_I"}
    cfg["arm_A"].update(n=30, floor_per_stratum=3)
    cfg["arm_B"].update(n=10)
    cfg["arm_C"].update(n_cells=4)
    return cfg


def _records(blind: pd.DataFrame, fg) -> pd.DataFrame:
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
    return rec


def _wells_for(log: pd.DataFrame, blind: pd.DataFrame, fg) -> pd.DataFrame:
    """One confirmed well row at the target for every visited confirmed record (point and cell searches)."""
    v = log[(log["access"] == "visited") & (log["identity"] == "confirmed_well")]
    b = blind.set_index("site_id")
    return pd.DataFrame({"site_id": v["site_id"], "visit_id": v["visit_id"], "well_seq": 1,
                         "gnss_x": v["site_id"].map(b["x"]), "gnss_y": v["site_id"].map(b["y"]),
                         "identity": "confirmed_well", "evidence_codes": "wellhead", "tied_record_id": "",
                         "notes": ""})[fg.WELL_COLUMNS]


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
    assert (tmp_path / "sheets" / "field_well_template_v1.csv").exists()
    rec = _records(blind, fg)
    r = fi.validate(rec, blind, fg.codebook(cfg), cfg["protocol"]["coord_check_m"])
    log, clean, rep = fi.reconcile(r, blind)
    assert len(clean) == len(blind) and (clean.loc[clean["outcome"] == "inaccessible", "identity"] == "ambiguous").all()
    wl = fi.reconcile_wells(_wells_for(log, blind, fg), log, clean, fg.codebook(cfg), 5.0)
    res = fa.analyse(cfg, clean, key, rep, tmp_path, wells=wl)
    tab = pd.read_csv(tmp_path / "field_bounds_v1.csv")
    assert (tab["lower_bound"] <= tab["upper_bound"] + 1e-12).all() and (tab["interval_lo"] <= tab["lower_bound"] + 1e-12).all()
    pooled = tab[tab["stratum"] == "all (weighted)"]
    assert set(pooled["gate"]) == {"inconclusive"}, "n = 30 + 10 + 4 cannot reach width 0.30"
    ok = tab[tab["gate"] == "success (precision)"]
    assert ok["interval_method"].str.startswith("census").all(), "only a stratum taken whole can pass at this n"
    assert "two_searcher" in res["search_sensitivity"]
    bad = rec.copy(); bad.loc[bad.index[1], ["outcome", "identity"]] = ["steel_anomaly_only", "confirmed_well"]
    with pytest.raises(AssertionError):
        fi.validate(bad, blind, fg.codebook(cfg), 30.0)


# ----------------------------------------------------------------------------- F05 and arm B frame
def test_audit_frame_read_with_p2_reader_and_roles(tmp_path):
    """The P2 file has # header lines. A plain read_csv raises. Buffer blocks are not Arm A ground."""
    cfg = _world(tmp_path)
    with pytest.raises(pd.errors.ParserError):
        pd.read_csv(tmp_path / "audit_blocks_9t_v1.csv")
    s = fd.draw(cfg, tmp_path / "t")
    assert any(f.startswith("P2 audit blocks [0, 1]") for f in s["frame_sources"])
    blind = pd.read_csv(tmp_path / "t" / "field_sample_blind_v1.csv")
    a = blind[blind["arm"] == "A"]
    assert len(a) and (a["x"] < X0 + 750).all(), "no Arm A site in the buffer block 2"


def test_arm_b_restricted_to_frame(tmp_path):
    cfg = _world(tmp_path)
    fd.draw(cfg, tmp_path / "t")
    blind = pd.read_csv(tmp_path / "t" / "field_sample_blind_v1.csv")
    b = blind[blind["arm"] == "B"]
    inside = (b["x"] < X0 + 750) | ((b["x"] >= X0 + 2000) & (b["x"] <= X0 + 3000))
    assert len(b) == 10 and inside.all(), "Arm B draws only candidates inside the audit blocks or reserved area"
    cands = pd.read_csv(tmp_path / "cands.csv")
    key = pd.read_csv(tmp_path / "t" / "field_sample_key_v1.csv")
    n_in = int((cands["cx"] < X0 + 750).sum())                       # hand count of the frame
    assert key.loc[key["arm"] == "B"].groupby("stratum")["N_h"].first().sum() == n_in


# ----------------------------------------------------------------------------- F04 design-based inference
def _clustered(n_clusters: int, per: int, stratum="s", pi=0.5, ident="confirmed_well") -> pd.DataFrame:
    return pd.DataFrame({"pi": pi, "identity": ident, "outcome": ident, "stratum": stratum,
                         "cluster_id": np.repeat([f"{stratum}_L{i}" for i in range(n_clusters)], per)})


def test_single_cluster_cannot_pass_precision():
    import _field_analysis_bounds as fa
    df = pd.DataFrame({"pi": [1.0] * 100, "identity": ["confirmed_well"] * 100,
                       "outcome": ["confirmed_well"] * 100, "cluster_id": ["one lease"] * 100})
    result = fa.summarise(df, {}, 0.1)
    assert result["gate"] == "inconclusive"
    assert result["interval_lo"] == 0 and result["interval_hi"] == 1


def test_copies_inside_three_clusters_do_not_buy_precision():
    """300 confirmed sites in 3 leases. Kish n = 300 gave width 0.012 and success. Design n is 3 PSUs."""
    import _field_analysis_bounds as fa
    from scipy.stats import beta, t
    r = fa.summarise(_clustered(3, 100), {}, 0.30)
    ne = 3 * (t.ppf(0.975, 299) / t.ppf(0.975, 2)) ** 2           # hand oracle, Korn-Graubard with v = 0
    assert r["gate"] == "inconclusive"
    assert r["interval_lo"] == pytest.approx(beta.ppf(0.025, ne, 1), rel=1e-9)
    assert r["width"] > 0.9


def test_stratum_with_one_psu_is_unidentified():
    import _field_analysis_bounds as fa
    df = pd.concat([_clustered(3, 100, "s1"), _clustered(1, 100, "s2")], ignore_index=True)
    r = fa.summarise(df, {}, 0.30)
    assert r["gate"] == "inconclusive" and (r["interval_lo"], r["interval_hi"]) == (0.0, 1.0)
    assert "stratum s2 has one PSU" in r["interval_method"]
    # a stratum taken whole (pi = 1) adds no variance and is not a refusal
    df.loc[df["stratum"] == "s2", "pi"] = 1.0
    assert "unidentified" not in fa.summarise(df, {}, 0.30)["interval_method"]


def test_linearisation_variance_by_hand():
    """Clusters a (2 confirmed), b (1 non-well), c (1 confirmed, 1 non-well). Equal weights, one stratum.
    R = 3/5. z_a = 2(0.4)/5 = 0.16, z_b = -0.6/5 = -0.12, z_c = (0.4 - 0.6)/5 = -0.04, mean 0.
    v = 3/2 (0.0256 + 0.0144 + 0.0016) = 0.0624. Korn-Graubard n before df scaling = 0.24 / 0.0624."""
    import _field_analysis_bounds as fa
    df = pd.DataFrame({"pi": 0.1, "stratum": "s", "cluster_id": ["a", "a", "b", "c", "c"],
                       "identity": ["confirmed_well", "confirmed_well", "definite_non_well", "confirmed_well", "definite_non_well"]})
    y = (df["identity"] == "confirmed_well").to_numpy(float)
    v = fa.design_variance(df, y)
    assert v["R"] == pytest.approx(0.6) and v["v"] == pytest.approx(0.0624) and v["df"] == 2
    from scipy.stats import t
    lo, hi, ne = fa.korn_graubard(0.6, 0.0624, 5, 3, 2)
    assert ne == pytest.approx(0.24 / 0.0624 * (t.ppf(0.975, 4) / t.ppf(0.975, 2)) ** 2)


# ----------------------------------------------------------------------------- 7.5-01 sizing claim
def test_n182_does_not_support_pm010_and_target_n():
    import _field_sample_size_design as fs
    from scipy.stats import beta
    cfg = fd.load_cfg()
    tab = fs.size_table(cfg).set_index("d")
    assert tab.loc[0.10, "n_with_deff_and_access"] == 182
    # hand oracle. n_eff = 182 x 0.8 / 1.5 = 97.07 -> 97, k = round(48.53) = 49, Clopper-Pearson width + gap 0.2
    lo, hi = beta.ppf(0.025, 49, 97 - 49 + 1), beta.ppf(0.975, 50, 97 - 49)
    assert tab.loc[0.10, "bound_width_at_that_n"] == pytest.approx(round(hi - lo + 0.2, 3)) == pytest.approx(0.407)
    assert str(tab.loc[0.10, "n_with_gap"]).startswith("unreachable")
    assert int(tab.loc[0.10, "n_for_target_width"]) == 746
    chk = fs.design_check(cfg, pd.DataFrame({"arm": ["A"], "stratum": ["s"], "n_h": [182]}))
    row = chk[(chk["arm"] == "A") & (chk["stratum"] == "arm total")].iloc[0]
    assert row["supports"] == "exploratory only" and not row["meets_target_width"]
    assert fs.design_check(cfg, pd.DataFrame({"arm": ["A"], "stratum": ["s"], "n_h": [746]})).iloc[0]["meets_target_width"]


# ----------------------------------------------------------------------------- 7.5-02 control unit
def test_control_sensitivity_counts_wells_not_cells():
    """Two searched cells with two listed controls each, all four found. Sensitivity is 4 / 4 = 1."""
    import _field_analysis_bounds as fa
    import _field_results_ingest as fi
    import _field_sheet_generate as fg
    cfg = fd.load_cfg()
    blind = pd.DataFrame({"site_id": ["S0", "S1"], "arm": "C", "x": [0.0, 1000.0], "y": 0.0})
    key = pd.DataFrame({"site_id": ["S0", "S1"], "arm": "C", "controls": ["P1;P2", "P3;P4"], "pi": 0.5})
    rec = pd.DataFrame({"site_id": ["S0", "S1"], "visit_id": ["v0", "v1"], "search_round": 1, "searcher_id": "s1",
                        "date": "2027-05-02", "access": "visited", "gnss_x": [0.0, 1000.0], "gnss_y": 0.0,
                        "outcome": "confirmed_well", "identity": "confirmed_well", "identity_basis": "",
                        "blind_confirmed": True, "evidence_codes": "agency_record_tied_on_site"})
    for c in fg.ENTRY_COLUMNS:
        rec[c] = rec.get(c, np.nan)
    log, clean, rep = fi.reconcile(fi.validate(rec, blind, fg.codebook(cfg), 30.0), blind)
    wells = pd.DataFrame({"site_id": ["S0", "S0", "S1", "S1"], "visit_id": ["v0", "v0", "v1", "v1"], "well_seq": [1, 2, 1, 2],
                          "gnss_x": [10.0, -10.0, 1010.0, 990.0], "gnss_y": 0.0, "identity": "confirmed_well",
                          "evidence_codes": "agency_record_tied_on_site", "tied_record_id": ["P1", "P2", "P3", "P4"], "notes": ""})
    wl = fi.reconcile_wells(wells, log, clean, fg.codebook(cfg), 5.0)
    sc = fa.sensitivity(rep, key, clean, wl)["seeded_controls"]
    assert (sc["n_controls"], sc["found"], sc["sensitivity"]) == (4, 4, 1.0)


# ----------------------------------------------------------------------------- F16 end to end into 5.4
def _density_frame_5_4(tmp: Path) -> tuple[Path, dict]:
    """5.4 S1 run on synthetic detections. Returns the 5.4 config path and the frame layout."""
    import geopandas as gpd
    from shapely.geometry import Point, box
    sys.path.insert(0, str(EXP / "5_tasks" / "5_4_undocumented_density" / "src"))
    sys.path.insert(0, str(EXP / "5_tasks" / "5_6_record_association" / "src"))
    import _density_distinct_wells_9t as dw
    d = tmp / "d54"
    d.mkdir()
    bl = [(i, box(X0 + i * 375, Y0, X0 + (i + 1) * 375, Y0 + 375), int(i != 3)) for i in range(4)]
    bl += [(4 + i + 2 * j, box(X0 + 1500 + 375 * i, Y0 + 375 * j, X0 + 1875 + 375 * i, Y0 + 375 * (j + 1)), 1)
           for j in range(2) for i in range(2)]
    gpd.GeoDataFrame({"block_id": [b[0] for b in bl], "n_pits": [b[2] for b in bl]},
                     geometry=[b[1] for b in bl], crs=CRS).to_file(d / "b.gpkg", layer="blocks", driver="GPKG")
    pts = []                                                     # (x, y, score, block_id)
    aud = [(X0 + 60 + 120 * i, Y0 + 60 + 120 * j) for j in range(3) for i in range(6)][:17]
    pts += [(x, y, 0.95 - 0.01 * k, 0 if x < X0 + 375 else 1) for k, (x, y) in enumerate(aud)]
    out_frame = [(X0 + 800 + 60 * i, Y0 + 60 + 100 * j) for j in range(3) for i in range(5)][:13]
    pts += [(x, y, 0.50 - 0.01 * k, 2) for k, (x, y) in enumerate(out_frame)]
    centres = [(X0 + 1625 + 250 * i, Y0 + 125 + 250 * j) for j in range(3) for i in range(3)]
    blk = lambda x, y: 4 + int((x - X0 - 1500) // 375) + 2 * int((y - Y0) // 375)  # noqa: E731
    pts += [(x, y, 0.20 - 0.01 * k, blk(x, y)) for k, (x, y) in enumerate(centres)]
    P = pd.DataFrame(pts, columns=["cx", "cy", "score", "block_id"])
    gpd.GeoDataFrame(P.assign(det_id=range(len(P)), novel=1, area_m2=10.0),
                     geometry=[Point(x, y) for x, y in zip(P.cx, P.cy)], crs=CRS).to_file(d / "pit.gpkg", driver="GPKG")
    gpd.GeoDataFrame({"PERMIT_NUM": ["121-1", "121-2"], "WELL_STATU": "Active"},
                     geometry=gpd.points_from_xy([X0 + 30, X0 + 200], [Y0 + 30, Y0 + 330]), crs=CRS).to_file(d / "dep.gpkg", driver="GPKG")
    cfg = json.loads((EXP / "5_tasks" / "5_4_undocumented_density" / "src" / "config_5_4.json").read_text())
    cfg["expected_pit_rows"] = len(P)
    cfg["bootstrap_B"] = 20
    cfg["inputs"].update(full_pit=str(d / "pit.gpkg"), pit_blocks=str(d / "b.gpkg"), dep_wells=str(d / "dep.gpkg"),
                         sites=str(d / "sites.csv"), accounting=str(d / "acc.json"))
    for k in cfg["outputs"]:
        cfg["outputs"][k] = str(d / Path(cfg["outputs"][k]).name)
    cfg["outputs"]["sites"], cfg["outputs"]["accounting"] = str(d / "sites.csv"), str(d / "acc.json")
    cp = d / "cfg.json"
    cp.write_text(json.dumps(cfg))
    assert dw.main(["--config", str(cp)]) == 0
    return cp, {"centres": centres}


def test_field_export_feeds_5_4_end_to_end(tmp_path):
    """Four Arm C cells. Zero wells, two new wells, a known control plus a new well, inaccessible.
    The real 7.5 export goes into the real 5.4 S3 reader, and the weighted accounting is checked by hand."""
    import geopandas as gpd
    from shapely.geometry import Point, box
    import _field_analysis_bounds as fa
    import _field_density_export as fx
    import _field_results_ingest as fi
    import _field_sheet_generate as fg
    cp54, lay = _density_frame_5_4(tmp_path)
    import _density_field_bounds_9t as fb
    cfg54 = json.loads(cp54.read_text())
    acc = json.loads(Path(cfg54["inputs"]["accounting"]).read_text())
    assert acc["D_sites"] == 39

    # 7.5 world. Arm A pits in the audit blocks, reserved area of nine 250 m cells over the 5.4 cell centres.
    rng = np.random.default_rng(2)
    blocks = gpd.GeoDataFrame({"block_id": [0, 1, 2, 3]},
                              geometry=[box(X0 + i * 375, Y0, X0 + (i + 1) * 375, Y0 + 375) for i in range(4)], crs=CRS)
    blocks.to_file(tmp_path / "blocks.gpkg", driver="GPKG")
    audit = _p2_audit(tmp_path, audit=[0, 1], buffer=[2])
    pits = [Point(X0 + rng.uniform(5, 745), Y0 + rng.uniform(5, 370)).buffer(3) for _ in range(40)]
    gpd.GeoDataFrame(geometry=pits, crs=CRS).to_file(tmp_path / "ann.gpkg", layer="pit_inside", driver="GPKG")
    gpd.GeoDataFrame(geometry=[box(X0 + 1500, Y0, X0 + 2250, Y0 + 750)], crs=CRS).to_file(tmp_path / "reserved.gpkg", driver="GPKG")

    def dep(extra):
        pts = [p.centroid for p in pits[:10]] + [e[1] for e in extra]
        gpd.GeoDataFrame({"PERMIT_NUM": [f"P{i}" for i in range(10)] + [e[0] for e in extra],
                          "SPUD_DATE": ["1885-05-01"] * 10 + ["1890-01-01"] * len(extra), "WELL_PAD_I": None},
                         geometry=pts, crs=CRS).to_file(tmp_path / "dep.gpkg", driver="GPKG")
    dep([])
    cfg = fd.load_cfg()
    a = lambda p: {"key": "expansions", "rel": str((tmp_path / p).resolve())}  # noqa: E731
    cfg["inputs"].update(blocks=a("blocks.gpkg"), audit_blocks=a(audit.name), reserved_area=a("reserved.gpkg"),
                         candidates_frozen={"key": "expansions", "rel": cfg54["inputs"]["sites"]}, historic_marks=a("none.gpkg"))
    cfg["inputs"]["truth"] = {**a("ann.gpkg"), "layers": {"pit": "pit_inside"}}
    cfg["inputs"]["dep_wells"] = {**a("dep.gpkg"), "spud_col": "SPUD_DATE", "id_col": "PERMIT_NUM", "pad_col": "WELL_PAD_I"}
    cfg["arm_A"].update(n=12, floor_per_stratum=2)
    cfg["arm_B"].update(n=10, n_bands=5)
    cfg["arm_C"].update(n_cells=4)

    # pass 1 learns which cells the seeded draw takes. Pass 2 adds one DEP control inside the third cell.
    fd.draw(cfg, tmp_path / "p1")
    k1 = pd.read_csv(tmp_path / "p1" / "field_sample_key_v1.csv")
    cells = k1.loc[k1["arm"] == "C", "source_id"].tolist()
    assert len(cells) == 4
    ll = [tuple(int(v) for v in c.split("_")[1:]) for c in cells]
    ctl_xy = (ll[2][0] + 60.0, ll[2][1] + 190.0)
    dep([("CTL1", Point(*ctl_xy))])
    out = tmp_path / "t"
    fd.draw(cfg, out)
    key = pd.read_csv(out / "field_sample_key_v1.csv", dtype={"frame_sha256": str})
    blind = pd.read_csv(out / "field_sample_blind_v1.csv")
    kc = key[key["arm"] == "C"].set_index("source_id")
    assert kc.index.tolist() == cells and kc.loc[cells[2], "controls"] == "CTL1"
    assert kc["controls"].fillna("").eq("").sum() == 3

    # Arm B frame by hand. 26 frame sites inside the audit blocks or reserved area (17 + 9), not the 13 in block 2.
    kb = key[key["arm"] == "B"].copy()
    assert sorted(kb.groupby("stratum")["N_h"].first().tolist()) == [5, 5, 5, 5, 6]
    assert (kb["frame_sha256"] == fd.ek.sha256(Path(cfg54["inputs"]["sites"]))).all()

    # field records. Arm A all non-wells. Arm B identities fixed per band. Arm C as in the docstring.
    plan_b = {"band1": ["confirmed_well", "confirmed_well"], "band2": ["confirmed_well", "definite_non_well"],
              "band3": ["definite_non_well", "definite_non_well"], "band4": ["ambiguous", "inaccessible"],
              "band5": ["definite_non_well", "definite_non_well"]}
    kb["ident"] = None
    for h, g in kb.groupby("stratum"):
        kb.loc[g.index, "ident"] = plan_b[h][:len(g)]
    b = blind.set_index("site_id")
    rows, wells = [], []

    def visit(sid, vid, ident, rnd=1, searcher="s1"):
        outc = {"confirmed_well": "confirmed_well", "definite_non_well": "nothing_found", "ambiguous": "unresolved",
                "nothing": "nothing_found"}[ident]
        rows.append({"site_id": sid, "visit_id": vid, "search_round": rnd, "searcher_id": searcher, "date": "2027-05-02",
                     "access": "visited", "gnss_x": b.loc[sid, "x"], "gnss_y": b.loc[sid, "y"], "outcome": outc,
                     "identity": "ambiguous" if ident == "nothing" else ident,
                     "identity_basis": "charcoal hearth" if ident == "definite_non_well" else "", "blind_confirmed": True,
                     "evidence_codes": "wellhead" if ident == "confirmed_well" else ""})
    for sid in key.loc[key["arm"] == "A", "site_id"]:
        visit(sid, f"v{sid}", "definite_non_well")
    for sid, ident in zip(kb["site_id"], kb["ident"]):
        if ident == "inaccessible":
            rows.append({"site_id": sid, "visit_id": f"v{sid}", "search_round": 1, "access": "permission_refused", "date": "2027-05-01"})
        else:
            visit(sid, f"v{sid}", ident)
            if ident == "confirmed_well":
                wells.append({"site_id": sid, "visit_id": f"v{sid}", "well_seq": 1, "gnss_x": b.loc[sid, "x"],
                              "gnss_y": b.loc[sid, "y"], "identity": "confirmed_well", "tied_record_id": ""})
    c1, c2, c3, c4 = (kc.loc[c, "site_id"] for c in cells)
    cen = {s: (b.loc[s, "x"], b.loc[s, "y"]) for s in (c1, c2, c3, c4)}
    visit(c1, "vc1", "nothing")                                                 # zero wells
    visit(c2, "vc2", "confirmed_well")                                          # two new wells
    visit(c2, "vc2b", "confirmed_well", rnd=2, searcher="s2")                    # repeat finds the first again
    visit(c3, "vc3", "confirmed_well")                                          # control plus a new well
    rows.append({"site_id": c4, "visit_id": "vc4", "search_round": 1, "access": "permission_refused", "date": "2027-05-01"})
    W = lambda s, v, q, dx, dy, ident="confirmed_well", tied="": {  # noqa: E731
        "site_id": s, "visit_id": v, "well_seq": q, "gnss_x": cen[s][0] + dx, "gnss_y": cen[s][1] + dy,
        "identity": ident, "tied_record_id": tied}
    wells += [W(c2, "vc2", 1, 0, 0), W(c2, "vc2", 2, 80, 80), W(c2, "vc2b", 1, 1, 1),
              {**W(c3, "vc3", 1, 0, 0, tied="CTL1"), "gnss_x": ctl_xy[0], "gnss_y": ctl_xy[1]},
              W(c3, "vc3", 2, 5, 0), W(c3, "vc3", 3, -90, -90, ident="ambiguous")]
    rec = pd.DataFrame(rows)
    for c in fg.ENTRY_COLUMNS:
        rec[c] = rec.get(c, np.nan)
    wr = pd.DataFrame(wells).assign(evidence_codes="wellhead", notes="")[fg.WELL_COLUMNS]
    cb = fg.codebook(cfg)
    log, clean, rep = fi.reconcile(fi.validate(rec, blind, cb, 30.0), blind)
    wl = fi.reconcile_wells(wr, log, clean, cb, cfg["density_export"]["well_merge_m"])
    assert wl.loc[(wl["site_id"] == c2) & (wl["search_round"] == 2), "well_id"].tolist() == [f"{c2}_w1"]

    # 7.5 export, then the real 5.4 S3 reader and function on the unmodified files
    res = fx.export(clean, wl, key, Path(cfg54["inputs"]["sites"]), cfg, tmp_path / "processed")
    assert res["arm_b_transfer_assumption"].startswith("ASSUMPTION"), "user default 2026-11-06, labelled as an assumption"
    B = pd.read_csv(tmp_path / "processed" / "arm_b_candidate_outcomes.csv")
    C = pd.read_csv(tmp_path / "processed" / "arm_c_search_outcomes.csv")
    assert list(B.columns) == list(cfg54["inputs"]["arm_b"]["schema"])
    assert list(C.columns) == list(cfg54["inputs"]["arm_c"]["schema"])
    areas = pd.read_csv(tmp_path / "processed" / "arm_c_search_areas.csv").set_index("site_id")
    assert len(areas) == 4 and areas.loc[c1, "n_wells_confirmed_r1"] == 0 and areas.loc[c4, "searched"] == 0
    assert (areas.loc[c3, "n_controls_listed"], areas.loc[c3, "n_controls_found"]) == (1, 1)
    cfg54["inputs"]["arm_b"]["path"] = str(tmp_path / "processed" / "arm_b_candidate_outcomes.csv")
    cfg54["inputs"]["arm_c"]["path"] = str(tmp_path / "processed" / "arm_c_search_outcomes.csv")
    cfg54["inputs"]["arm_c_areas"]["path"] = str(tmp_path / "processed" / "arm_c_search_areas.csv")
    cfg54["outputs"]["field_bounds"] = str(tmp_path / "fb.json")
    cp2 = tmp_path / "cfg54_field.json"
    cp2.write_text(json.dumps(cfg54))
    assert fb.main(["--config", str(cp2)]) == 0
    got = json.loads((tmp_path / "fb.json").read_text())
    # by hand. Band1 N 6 n 2 gives weight 3. Other bands N 5 n 2 give 2.5. Total 2 x 3 + 8 x 2.5 = 26.
    # confirmed weight 3 + 3 + 2.5 = 8.5. Non-well weight 2.5 + 5 + 5 = 12.5. Kish n = 26^2 / (2 x 9 + 8 x 6.25).
    assert got["p"]["ppv_lower"] == pytest.approx(8.5 / 26)
    assert got["p"]["ppv_upper"] == pytest.approx(1 - 12.5 / 26)
    assert got["p"]["n_eff"] == pytest.approx(676 / 68)
    # wells found: c2 w1 (on a frame site), c2 w2 (113 m off), control (92 m off), c3 new (5 m off). 2 of 4 detected.
    assert (got["r"]["k"], got["r"]["n"], got["r"]["r"]) == (2, 4, 0.5)
    assert got["r"]["search_sensitivity_bounded"] is True
    # 4 sampled cells. c4 is inaccessible, c1 was searched and held no well. 5.4 now counts both from the areas file.
    assert (got["r"]["n_areas"], got["r"]["n_areas_inaccessible"]) == (3, 1)
    assert got["r"]["n_areas_source"] == "arm_c_search_areas"
    assert got["D_sites"] == 39

    # 7.5's own Arm C density and control sensitivity from the same child table
    out_a = fa.analyse(cfg, clean, key, rep, tmp_path, wells=wl)
    ac = out_a["arm_C"]
    assert (ac["cells_searched"], ac["cells_inaccessible"], ac["undocumented_confirmed"]) == (3, 1, 3)
    assert ac["per_km2_observed"] == pytest.approx(3 / (3 * 0.0625))
    sc = out_a["search_sensitivity"]["seeded_controls"]
    assert (sc["n_controls"], sc["found"]) == (1, 1)

    # the export refuses a frame that changed after the draw
    sites = Path(cfg54["inputs"]["sites"])
    sites.write_text(sites.read_text() + "\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="frame changed"):
        fx.export(clean, wl, key, sites, cfg, tmp_path / "processed2")


# ----------------------------------------------------------------------------- user defaults 2026-11-06
def test_single_cluster_strata_collapse_with_adjacent_same_arm():
    """User default. A frame stratum with one cluster merges with its adjacent stratum before the draw.
    Hand oracle. Arm A order inside morph m1 is early_dated, steel_dated. m1|steel_dated has one cluster, so it
    merges with its previous neighbour in the same morph (the next one, m2|early_dated, is another morph).
    m2 keeps two strata with two clusters each. Arm B band3 (one cluster) merges with band4, the next band."""
    df = pd.DataFrame({"stratum": ["m1|early_dated"] * 4 + ["m1|steel_dated"] * 3 + ["m2|early_dated"] * 2 + ["m2|no_record"] * 2,
                       "cluster_id": ["a", "a", "b", "b", "L", "L", "L", "c", "d", "e", "f"]})
    order = ["m1|early_dated", "m1|steel_dated", "m2|early_dated", "m2|no_record"]
    out, log = fd.collapse_single_cluster(df, order, group=lambda h: h.split("|")[0])
    assert log == [{"merged": ["m1|early_dated", "m1|steel_dated"], "into": "m1|early_dated+steel_dated",
                    "reason": "m1|steel_dated has 1 cluster(s)"}]
    assert out["stratum"].value_counts().to_dict() == {"m1|early_dated+steel_dated": 7, "m2|early_dated": 2, "m2|no_record": 2}
    b = pd.DataFrame({"stratum": ["band1"] * 2 + ["band2"] * 2 + ["band3"] * 2 + ["band4"] * 2,
                      "cluster_id": ["p", "q", "r", "s", "t", "t", "u", "v"]})
    out, log = fd.collapse_single_cluster(b, ["band1", "band2", "band3", "band4"])
    assert [m["into"] for m in log] == ["band3+band4"]
    last = pd.DataFrame({"stratum": ["band1"] * 2 + ["band2"], "cluster_id": ["p", "q", "r"]})
    assert fd.collapse_single_cluster(last, ["band1", "band2"])[1][0]["into"] == "band1+band2", "last band takes the previous"


def test_draw_records_collapse_and_density_assumption(tmp_path):
    """The real draw applies the collapse (config strata) and every Arm A stratum in the key has two or more
    frame clusters or was merged. The density export labels the Arm B transfer as an assumption."""
    cfg = _world(tmp_path)
    assert cfg["strata"]["collapse_single_cluster"] is True
    assert cfg["density_export"]["detector_link_m"] == 15.0 and cfg["density_export"]["well_merge_m"] == 5.0
    assert cfg["density_export"]["arm_b_transfer_assumption"].startswith("ASSUMPTION")
    s = fd.draw(cfg, tmp_path / "t")
    # hand check of _world. Its pad early_dated stratum holds one cluster, so it merges with pad steel_dated
    assert [m["into"] for m in s["collapsed_strata"]["A"]] == ["pad_unclassified|early_dated+steel_dated"]
    assert s["collapsed_strata"]["B"] == []
    key = pd.read_csv(tmp_path / "t" / "field_sample_key_v1.csv")
    assert (key[key["arm"] != "C"].groupby(["arm", "stratum"])["cluster_id"].nunique() >= 2).all()
