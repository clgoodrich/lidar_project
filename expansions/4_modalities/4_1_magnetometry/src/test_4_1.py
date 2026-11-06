"""Smoke tests for expansion 4.1 on tiny synthetic data. Seconds, no GPU, no network.

Run  python -m pytest -q expansions/4_modalities/4_1_magnetometry/src/test_4_1.py -p no:cacheprovider
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mag_shared_io as io  # noqa: E402
import _mag_anomaly_process as proc  # noqa: E402
import _mag_pick_well_match as match  # noqa: E402
import _mag_site_frame_9t as frame  # noqa: E402
import _mag_survey_design as design  # noqa: E402

CX, CY = 621000.0, 4595000.0
SRC = (CX + 2.0, CY - 3.0)


def synth(seed=0, src=SRC, p=2000.0, depth=1.0, h=0.3, extra=()):
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp("2026-11-05T14:00:00Z")
    rows, t = [], 0.0
    xs = CX - 10 + np.arange(0, 20.01, 1.0)
    for i, x in enumerate(xs):
        ys = np.arange(CY - 10, CY + 10.001, 0.1)
        ys = ys if i % 2 == 0 else ys[::-1]
        for y in ys:
            rows.append((i, t, x, y, 0))
            t += 0.125
        t += 10
    for y in np.arange(CY - 10, CY + 10.001, 0.1):     # repeat of line 5
        rows.append((5, t, xs[5], y, 1))
        t += 0.125
    df = pd.DataFrame(rows, columns=["line_id", "t", "easting", "northing", "is_repeat"])
    drift = 0.01 * df.t                                   # about 20 nT over the survey
    regional = 52000 + 0.5 * (df.easting - CX) - 0.3 * (df.northing - CY)
    anom = design.monopole_field(df.easting - src[0], df.northing - src[1], p, depth + h)
    for (ex, ey), ep in extra:                            # further steel objects, e.g. a test object
        anom = anom + design.monopole_field(df.easting - ex, df.northing - ey, ep, depth + h)
    df["tf_nT"] = regional + drift + anom + rng.normal(0, 0.3, len(df))
    df.loc[100, "tf_nT"] += 500                           # one spike
    df["time_utc"] = (t0 + pd.to_timedelta(df.t, unit="s")).astype(str)
    bt = np.arange(-60, t + 60, 1.0)
    base = pd.DataFrame({"time_utc": (t0 + pd.to_timedelta(bt, unit="s")).astype(str),
                         "tf_nT": 52000 + 0.01 * bt + rng.normal(0, 0.1, len(bt))})
    return df.drop(columns="t"), base


@pytest.fixture()
def cfg():
    return io.load_config()


def test_process_recovers_pick(cfg, tmp_path):
    lines, base = synth()
    r = proc.run(cfg, tmp_path, sites=["s1"], data={"s1": (lines, base)}, test_objects={"s1": SRC})
    picks, qc = r["sites"]["s1"]["picks"], r["sites"]["s1"]["qc"]
    assert len(picks) >= 1
    d = np.hypot(picks.easting[0] - SRC[0], picks.northing[0] - SRC[1])
    assert d < 1.0
    assert qc["noise_sigma_nT"] < 2.0
    assert qc["repeat_rms_nT"] < 3.0
    assert qc["test_object"]["found"]
    assert qc["n_spikes_replaced"] >= 1
    assert (r["run_dir"] / "mag_residual_s1.tif").exists()
    assert (r["run_dir"] / "_PROVENANCE.json").exists()


def test_blank_has_no_pick(cfg, tmp_path):
    lines, base = synth(seed=1, p=0.0)
    r = proc.run(cfg, tmp_path, sites=["b"], data={"b": (lines, base)})
    assert len(r["sites"]["b"]["picks"]) == 0


def test_match_and_gate(cfg, tmp_path):
    obj = (CX - 7.0, CY + 7.0)                            # test object placed at the blank, away from its centre
    data = {"w1": synth(2), "c1": synth(3), "b1": synth(4, src=obj)}
    tos = {"w1": SRC, "c1": SRC, "b1": obj}
    pr = proc.run(cfg, tmp_path, sites=list(data), data=data, test_objects=tos)
    sites = pd.DataFrame({"site_id": ["w1", "c1", "b1"], "stratum": ["steel_era", "confuser", "blank"],
                          "easting": [CX, SRC[0], CX], "northing": [CY, SRC[1], CY],
                          "lidar_cx": [CX + 1.5, np.nan, np.nan], "lidar_cy": [CY - 2.5, np.nan, np.nan],
                          "why_chosen": ["visible wellhead", "culvert", "open forest"]})
    wh = pd.DataFrame({"site_id": ["w1"], "easting": [SRC[0] + 0.3], "northing": [SRC[1]], "h_acc_m": [0.02]})
    idn = pd.DataFrame({"site_id": ["w1", "c1", "b1"],
                        "identity_status": ["confirmed_well", "definite_non_well", "definite_non_well"]})
    m = match.run(cfg, tmp_path, proc_run=pr["run_dir"], sites=sites, wellheads=wh, identity=idn)
    t = m["table"].set_index("site_id")
    assert t.loc["w1", "anomaly_present"] and t.loc["w1", "err_to_wellhead_m"] < 1.5
    assert t.loc["c1", "outcome"] == "steel_anomaly_c"
    assert t.loc["b1", "outcome"] == "nothing_found"
    assert m["gate"]["verdict"] == "pass"
    assert set(m["summary"].stratum) == {"steel_era", "confuser", "blank"}
    assert frame.validate_pilot(sites, cfg["site_frame"])["ok"]


def _gate_case(cfg, tmp_path, w_src_p, b_src_p, w_stratum="steel_era"):
    """Same layout as test_match_and_gate. w_src_p is the pole strength at the confirmed well, b_src_p at the
    blank centre (0 means no source). Every site keeps a findable test object, so only the tested
    defect can fail the gate."""
    far = (CX + 7.0, CY - 7.0)                           # test objects sit outside the 5 m match radius
    obj = (CX - 7.0, CY + 7.0)
    w1 = synth(2, p=w_src_p, extra=[] if w_src_p > 0 else [(far, 2000.0)])
    data = {"w1": w1, "c1": synth(3), "b1": synth(4, src=(CX, CY), p=b_src_p, extra=[(obj, 2000.0)])}
    tos = {"w1": SRC if w_src_p > 0 else far, "c1": SRC, "b1": obj}
    pr = proc.run(cfg, tmp_path, sites=list(data), data=data, test_objects=tos)
    sites = pd.DataFrame({"site_id": ["w1", "c1", "b1"], "stratum": [w_stratum, "confuser", "blank"],
                          "easting": [CX, SRC[0], CX], "northing": [CY, SRC[1], CY],
                          "why_chosen": ["visible wellhead", "culvert", "open forest"]})
    idn = pd.DataFrame({"site_id": ["w1", "c1", "b1"],
                        "identity_status": ["confirmed_well", "definite_non_well", "definite_non_well"]})
    return match.run(cfg, tmp_path, proc_run=pr["run_dir"], sites=sites, identity=idn)


def test_confirmed_well_without_anomaly_is_a_miss(cfg, tmp_path):
    """4.1-01. Pre-fix the outcome was confirmed_well_d from identity alone and the gate passed."""
    m = _gate_case(cfg, tmp_path, w_src_p=0.0, b_src_p=0.0)
    t = m["table"].set_index("site_id")
    assert not t.loc["w1", "anomaly_present"]
    assert t.loc["w1", "outcome"] == "confirmed_well_missed"
    assert [k for k, v in m["gate"]["checks"].items() if not v] == ["confirmed_steel_wells_detected"]
    assert m["gate"]["verdict"] == "fail"


def test_early_era_miss_is_reported_not_failed(cfg, tmp_path):
    m = _gate_case(cfg, tmp_path, w_src_p=0.0, b_src_p=0.0, w_stratum="early_era")
    assert m["table"].set_index("site_id").loc["w1", "outcome"] == "confirmed_well_missed"
    assert m["gate"]["early_or_undated_wells_missed"] == ["w1"]
    assert m["gate"]["verdict"] == "pass"


def test_blank_with_50nT_pick_fails_gate(cfg, tmp_path):
    """4.1-01. A 50 nT source under the blank. B = p / r2 with r = 1.0 + 0.3 m, so p = 50 * 1.3**2."""
    m = _gate_case(cfg, tmp_path, w_src_p=2000.0, b_src_p=50 * 1.3 ** 2)
    t = m["table"].set_index("site_id")
    assert t.loc["b1", "anomaly_present"] and t.loc["b1", "amplitude_nT"] > 10   # residual after regional removal
    assert t.loc["b1", "outcome"] == "blank_with_pick"
    assert [k for k, v in m["gate"]["checks"].items() if not v] == ["blanks_have_no_pick"]
    assert m["gate"]["verdict"] == "fail"


def test_outcome_table_crosses_identity_and_anomaly():
    got = {(i, a): match.outcome_for(True, True, i, a, "steel_era")
           for i in ("confirmed_well", "definite_non_well", "ambiguous") for a in (True, False)}
    assert got == {("confirmed_well", True): "confirmed_well_d", ("confirmed_well", False): "confirmed_well_missed",
                   ("definite_non_well", True): "steel_anomaly_c", ("definite_non_well", False): "nothing_found",
                   ("ambiguous", True): "steel_anomaly_c", ("ambiguous", False): "nothing_found"}
    assert match.outcome_for(False, True, "confirmed_well", True, "steel_era") == "inaccessible"
    assert match.outcome_for(True, False, "confirmed_well", True, "steel_era") == "unresolved"


def test_historic_date_after_steel_is_not_early_era():
    """Era gap. A historic record dated 1960 must not make a well early era. Pre-fix it did."""
    w = pd.DataFrame({"PERMIT_NUM": ["a", "b"], "SPUD_DATE": ["1955-01-01", None], "PERMIT_DAT": [None, None]})
    hist = pd.DataFrame({"PERMIT_NUM": ["a", "b"], "year_built_max": [1960, 1890]})
    assert frame.assign_strata(w, hist, 1930, 1800).tolist() == ["steel_era", "early_era"]
    with pytest.raises(ValueError, match="year_built_max"):
        frame.assign_strata(w, pd.DataFrame({"PERMIT_NUM": ["a"]}), 1930, 1800)


def test_dated_pre_steel_is_a_valid_pilot_stratum(cfg):
    """Era gap. assign_strata emits dated_pre_steel, so validate_pilot must accept it."""
    sites = pd.DataFrame({"site_id": ["a", "b", "c"], "stratum": ["dated_pre_steel", "confuser", "blank"],
                          "why_chosen": ["x", "y", "z"]})
    assert frame.validate_pilot(sites, cfg["site_frame"])["ok"]


def test_frame_counts_wells_from_raw_box(cfg, tmp_path):
    """Circular assert. The well count is checked against the raw box minus counted duplicates and blanks."""
    import geopandas as gpd
    from shapely.geometry import Point
    x0, y0 = cfg["bbox_9t"][0] + 100, cfg["bbox_9t"][1] + 100
    wells = gpd.GeoDataFrame({"PERMIT_NUM": ["p1", "p1", "p2", None], "SPUD_DATE": ["1950-01-01"] * 4,
                              "PERMIT_DAT": [None] * 4, "WELL_STATU": ["Active"] * 4},
                             geometry=[Point(x0, y0), Point(x0 + 50, y0), Point(x0 + 100, y0), Point(x0 + 150, y0)],
                             crs=cfg["crs"])
    pits = gpd.GeoDataFrame({"pit_full_id": [1]}, geometry=[Point(x0 + 50, y0).buffer(2)], crs=cfg["crs"])
    c = dict(cfg)
    c["inputs"] = {k: (dict(v, rel="absent/x.csv") if k in ("historic_dates", "confusers_blanks", "pilot_sites")
                       else v) for k, v in cfg["inputs"].items()}
    r = frame.run(c, tmp_path, wells=wells, pits=pits)
    sm = r["summary"]
    assert sm["n_wells_in_box"] == 4 and sm["n_duplicate_permit_records_dropped"] == 1
    assert sm["n_records_no_permit"] == 1
    assert sorted(r["frame"].site_id[r["frame"].site_id.str.startswith("well_")]) == ["well_p1", "well_p2"]
    assert "pit_1" not in set(r["frame"].site_id)      # the duplicate p1 record at x0+50 still screens the pit


def test_strata_logic():
    w = pd.DataFrame({"PERMIT_NUM": ["a", "b", "c", "d", "e"],
                      "SPUD_DATE": ["1955-01-01", "1800-01-01", None, "1890-05-01", "1900-01-01"],
                      "PERMIT_DAT": [None, None, None, None, None]})
    hist = pd.DataFrame({"PERMIT_NUM": ["e"], "year_built_max": [1895]})
    s = frame.assign_strata(w, hist, 1930, 1800).tolist()
    assert s == ["steel_era", "unknown_date", "unknown_date", "dated_pre_steel", "early_era"]


def test_pits_no_record():
    import geopandas as gpd
    from shapely.geometry import Point
    wells = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs="EPSG:6346")
    pits = gpd.GeoDataFrame({"pit_full_id": [1, 2]}, geometry=[Point(5, 0).buffer(2), Point(100, 0).buffer(2)],
                            crs="EPSG:6346")
    out = frame.pits_no_record(pits, wells, 25.0)
    assert out.site_id.tolist() == ["pit_2"]


def test_survey_design(cfg, tmp_path):
    r = design.run(cfg, tmp_path, "demo", CX, CY)
    d = r["design"]
    assert d["n_lines"] == 21 and abs(d["along_line_spacing_m"] - 0.08) < 1e-9
    assert design.detect_depth(3000.0, 1.0, 3.0, 0.3) == pytest.approx(np.sqrt(1000) - 0.3)
    assert json.loads((r["run_dir"] / "mag_survey_design_demo.json").read_text())["survey_time_min"] > 0
