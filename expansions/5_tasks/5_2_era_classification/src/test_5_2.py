"""Smoke tests for 5.2 era classification on tiny synthetic data. No GPU, no network, no real data.

Run
    python -m pytest -q expansions/5_tasks/5_2_era_classification/src/test_5_2.py -p no:cacheprovider
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
import _era_core_tools as ec  # noqa: E402
import _task5_helpers as th  # noqa: E402

CFG = json.loads((HERE / "config_5_2.json").read_text(encoding="utf-8"))
CLASSES = CFG["era_classes"]


def test_classify_dates_and_cross_flags():
    s = pd.Series(["1800-01-01", "1900-01-01", None, "1850-05-01", "2030-01-01", "1975-03-02"])
    c = ec.classify_dates(s, ["1800-01-01", "1900-01-01"], 1859, "2026-11-05")
    assert list(c) == ["sentinel_1800-01-01", "sentinel_1900-01-01", "null", "pre_1859", "future", "valid"]
    df = pd.DataFrame({"s": ["1980-01-01", "1980-01-01"], "p": ["1979-12-01", "1983-01-01"], "g": ["1979-01-01", None]})
    cls = {k: ec.classify_dates(df[v], ["1800-01-01"], 1859, "2026-11-05") for k, v in
           (("spud", "s"), ("permit", "p"), ("plug", "g"))}
    f = ec.cross_field_flags(df, "s", "p", "g", cls, 365)
    assert f.plug_before_spud.tolist() == [True, False]
    assert f.spud_before_permit_gap.tolist() == [False, True]


def test_era_class_intervals_and_tightest():
    assert ec.era_class(1870, 1870, CLASSES) == "E1"
    assert ec.era_class(1859, 1930, CLASSES) == "spans"
    assert ec.early_label(1859, 1930, CLASSES) == 1.0
    assert ec.early_label(1960, 1960, CLASSES) == 0.0
    assert np.isnan(ec.early_label(1940, 1960, CLASSES))
    best, conflict = ec.tightest([(1859, 1890, "map:a", "1890", "record_link", 10.0),
                                  (1880, 1880, "dep_spud", "1880", "record", 0.0)])
    assert best[2] == "dep_spud" and not conflict
    _, conflict = ec.tightest([(1859, 1870, "m", "1870", "r", 0), (1960, 1960, "d", "1960", "r", 0)])
    assert conflict


def test_sentinel_never_enters_model_input():
    ok = pd.DataFrame({"stratum": ["dated_map"], "lo": [1859], "hi": [1890], "source_date": ["1890"]})
    ec.assert_no_sentinel(ok)
    with pytest.raises(AssertionError):
        ec.assert_no_sentinel(ok.assign(stratum="sentinel"))
    with pytest.raises(AssertionError):
        ec.assert_no_sentinel(ok.assign(lo=1800, hi=1800))
    with pytest.raises(AssertionError):
        ec.assert_no_sentinel(ok.assign(source_date="1800-01-01"))


def test_aft_recovers_direction_and_concordance():
    rng = np.random.default_rng(0)
    x = rng.normal(size=400)
    year = ec.YEAR0 + np.exp(4.0 + 0.4 * x + rng.normal(0, 0.1, 400))
    lo, hi = np.floor(year), np.floor(year)
    cens = rng.random(400) < 0.4            # left-censored map marks
    lo[cens] = 1859
    m = ec.IntervalLogNormalAFT(ridge=0.01).fit(x[:, None], lo, hi)
    assert m.coef_[1] > 0.2
    c = ec.interval_concordance(m.predict_year(x[:, None]), lo, hi)
    assert c > 0.8


def test_stratified_sample_and_overlap():
    df = pd.DataFrame({"permit": range(200), "era_class": ["E1"] * 20 + ["E2"] * 30 + ["E3"] * 150})
    s = ec.stratified_sample(df, "era_class", 60, 1)
    assert len(s) == 60 and set(s.era_class) == {"E1", "E2", "E3"}
    assert np.isclose((s.weight).sum(), 200)
    assert ec.overlap_coefficient([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert ec.overlap_coefficient([0, 0.1], [10, 10.1]) == pytest.approx(0.0)


def test_pad_morphology_square():
    from shapely.geometry import box
    t = ec.pad_morphology([box(0, 0, 10, 10), box(0, 0, 40, 10)])
    assert t.area_m2[0] == pytest.approx(100)
    assert t.compactness[0] == pytest.approx(np.pi / 4)
    assert t.elongation[1] == pytest.approx(4)


def test_build_labels_records_and_marks():
    from shapely.geometry import Point
    import geopandas as gpd
    import _era_interval_labels_9t as s2
    strata = pd.DataFrame({"permit": ["121-1", "121-2", "121-3"], "stratum": ["dated_record", "sentinel", "sentinel"],
                           "x": [0.0, 100.0, 500.0], "y": [0.0, 0.0, 0.0], "spud_year": [1960.0, np.nan, np.nan],
                           "status": "x", "spud_class": "valid"})
    marks = gpd.GeoDataFrame({"mark_id": ["a", "b"], "map_id": ["m1", "m2"], "map_date": ["1880", "1910"],
                              "permit": ["121-2", None], "identity_basis": ["record_link", "position_only"],
                              "pos_error_m": [10.0, 20.0], "map_year": [1880.0, 1910.0]},
                             geometry=[Point(100, 0), Point(505, 0)], crs=th.CRS)
    lab = s2.build_labels(strata, marks, CFG)
    by = lab.set_index("permit")
    assert by.loc["121-1", "era_class"] == "E3"
    assert by.loc["121-2", "era_class"] == "E1" and bool(by.loc["121-2", "primary"])
    assert by.loc["121-3", "link_flag"] == "position_only" and not bool(by.loc["121-3", "primary"])
    assert (lab.evidence_level == "a").all() and (lab.era_basis == "interval").all()


def test_label_audit_score():
    import _era_label_audit_sample_9t as s3
    sheet = pd.DataFrame({"permit": list("abcd"), "era_class": ["E1", "E1", "E3", "E3"], "weight": 1.0,
                          "audit_source_ok": ["yes"] * 4, "audit_date_ok": ["yes", "no", "yes", "yes"],
                          "audit_link_ok": ["yes", "yes", "no", ""]})
    r = s3.score(sheet)
    assert r["n_completed"] == 3 and r["agreement"]["k"] == 1 and r["link_error"]["k"] == 1
    assert set(r["disputed_permits"]) == {"b", "c"}


def _synthetic_pairs(n_blocks=20, per_block=12, seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_blocks):
        for i in range(per_block):
            cls = rng.choice(["E1", "E2", "E3"], p=[0.3, 0.3, 0.4])
            yr = {"E1": rng.integers(1860, 1899), "E2": rng.integers(1900, 1955), "E3": rng.integers(1956, 2010)}[cls]
            area = np.exp(6 + (yr - 1930) / 40 + rng.normal(0, 0.3))
            lo, hi = (1859, 1899) if cls == "E1" and rng.random() < 0.5 else (yr, yr)
            rows.append(dict(permit=f"p{b}_{i}", pad_id=b * 100 + i, block_id=b, stratum="dated_map", lo=lo, hi=hi,
                             era_class=ec.era_class(lo, hi, CLASSES), early=ec.early_label(lo, hi, CLASSES),
                             primary=True, area_m2=area, perimeter_m=4 * np.sqrt(area),
                             compactness=rng.uniform(0.5, 0.9), elongation=rng.uniform(1, 3), wells_on_pad=1,
                             pits_on_pad=rng.integers(0, 3), slope_mean_deg=rng.uniform(2, 20), void_frac=rng.uniform(0, .5),
                             road_dist_m=rng.uniform(0, 200), landcover_class=np.nan, oilfield_dist_m=np.nan,
                             flight_year=np.nan, easting_km=620 + b * 0.3, northing_km=4594 + rng.uniform(0, 3)))
    for i in range(10):
        rows.append(dict(rows[i], permit=f"s{i}", stratum="sentinel", lo=np.nan, hi=np.nan, era_class=np.nan,
                         early=np.nan, primary=np.nan))
    return pd.DataFrame(rows)


def _tmp_cfg(tmp_path, pairs):
    cfg = json.loads(json.dumps(CFG))
    pp = tmp_path / "pairs.csv"
    pairs.to_csv(pp, index=False)
    cfg["inputs"]["pairs"] = {"path": str(pp)}
    cfg["inputs"]["labels"] = {"path": str(tmp_path / "labels.csv")}
    cfg["inputs"]["audit_blocks"] = {"path": str(tmp_path / "none.csv")}
    for k in cfg["outputs"]:
        cfg["outputs"][k] = str(tmp_path / Path(cfg["outputs"][k]).name) if k != "runs" else str(tmp_path / "runs")
    cfg["model"].update(bootstrap_B=80, label_noise_reps=2, label_noise_p=[0.1])
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg))
    return p


def test_model_end_to_end_and_support(tmp_path):
    import _era_model_arms_9t as s6
    import _era_sentinel_support_9t as s7
    pairs = _synthetic_pairs()
    cp = _tmp_cfg(tmp_path, pairs)
    assert s6.main(["--config", str(cp), "--provisional-folds"]) == 0
    summ = json.loads((tmp_path / "era_model_summary_9t.json").read_text())
    assert summ["status"] == "exploratory"
    # By construction area encodes year and the M1 covariates are noise. M3 beats M1 by far more than
    # delta_era 0.05, and every block holds both classes, so no draw is undefined.
    assert summ["primary"]["decision"] == "success" and summ["primary"]["undefined_share"] == 0.0
    assert summ["folds"]["audit"] == "no audit exclusion, exploratory"
    assert summ["secondary"]["M2"]["auc"] > 0.6      # morphology carries the synthetic signal
    pred = pd.read_csv(tmp_path / "era_predictions_9t.csv")
    assert not pred.permit.str.startswith("s").any()  # sentinel rows never predicted as training data
    assert (tmp_path / "era_auc_by_arm_9t.png").exists()
    assert s7.main(["--config", str(cp)]) == 0
    sup = pd.read_csv(tmp_path / "era_sentinel_support_9t.csv")
    assert len(sup) == 10 and set(sup.era_basis) <= {"predicted_unvalidated", "extrapolated"}


def test_model_refuses_sentinel_labels(tmp_path):
    import _era_model_arms_9t as s6
    pairs = _synthetic_pairs()
    pairs.loc[0, "stratum"] = "sentinel"          # a labelled row tagged sentinel must stop the run
    cp = _tmp_cfg(tmp_path, pairs)
    with pytest.raises(AssertionError):
        s6.main(["--config", str(cp), "--provisional-folds"])


def test_readiness_gate_blocks_small_sets(tmp_path):
    import _era_model_arms_9t as s6
    pairs = _synthetic_pairs(n_blocks=3, per_block=5)
    cp = _tmp_cfg(tmp_path, pairs)
    assert s6.main(["--config", str(cp), "--provisional-folds"]) == 0
    summ = json.loads((tmp_path / "era_model_summary_9t.json").read_text())
    assert summ["status"] == "descriptive_only"


def test_missing_assumed_input_named():
    import _era_interval_labels_9t as s2
    cfg = json.loads(json.dumps(CFG))
    cfg["inputs"]["historic_marks"]["path"] = "Z:/definitely/missing.gpkg"
    with pytest.raises(th.MissingInput) as e:
        th.inp(cfg, "historic_marks")
    assert "historic_marks" in str(e.value)
    assert s2.build_labels is not None


# ----------------------------------------------------------------------------- review fixes 2026-11-06
P1_SRC = HERE.parents[2] / "0_prerequisites" / "p1_splits_manifests" / "src"
P2_SRC = HERE.parents[2] / "0_prerequisites" / "p2_audit_set" / "src"


def _real_p1_csv(tmp_path, monkeypatch):
    """Split CSV written by the real P1 writer (roles train, val, heldout). 5 blocks, block b held out in fold b."""
    sys.path.insert(0, str(P1_SRC))
    import _split_future_csv_9t as fc
    folds = {str(f): {"train": [b for b in range(5) if b not in (f, (f + 1) % 5)], "inner_val": [(f + 1) % 5],
                      "held_out": [f]} for f in range(5)}
    js = tmp_path / "cv_splits_future_9t_v1.json"
    js.write_text(json.dumps({"tasks": {"pit": {"folds": folds}}}))
    monkeypatch.setattr(sys, "argv", ["x", "--json", str(js), "--out-dir", str(tmp_path)])
    fc.main()
    return tmp_path / "cv_splits_future_pit_9t_v1.csv"


def _real_p2_audit(tmp_path, audit=(3,), buffer=(4,)):
    sys.path.insert(0, str(P2_SRC))
    import _audit_draw_blocks_9t as dr
    ids = sorted(set(audit) | set(buffer))
    tab = pd.DataFrame({"block_id": ids, "dens_t": 1, "slope_t": 2})
    p = tmp_path / "audit_blocks_9t_v1.csv"
    dr.write_audit_csv(p, tab, {"audit": list(audit), "buffer": list(buffer), "share": 0.2}, "block", 100.0, 1)
    Path(str(p) + ".sha256").write_text(f"{th.ek.sha256(p)}  {p.name}\n", encoding="utf-8")
    return p


def test_load_folds_reads_real_p1_csv_and_p2_audit(tmp_path, monkeypatch):
    """P1-01 and P2-01. Pre-fix the 'held_out' filter found 0 rows of the P1 CSV and the plain read_csv of the
    audit file raised. Expected by hand. Blocks 3 (audit) and 4 (buffer) leave, block b keeps fold b."""
    import _era_model_arms_9t as s6
    cfg = json.loads(json.dumps(CFG))
    cfg["inputs"]["split_file"] = {"path": str(_real_p1_csv(tmp_path, monkeypatch))}
    cfg["inputs"]["audit_blocks"] = {"path": str(_real_p2_audit(tmp_path))}
    df = pd.DataFrame({"block_id": [0, 1, 2, 3, 4, 0], "x": range(6)})
    out, info = s6.load_folds(cfg, df, provisional=False)
    assert out.block_id.tolist() == [0, 1, 2, 0] and out.fold.astype(int).tolist() == [0, 1, 2, 0]
    assert info["n_audit_blocks_dropped"] == 2 and info["audit"].startswith("P2 audit")
    assert ":" not in info["split_file"]


def test_load_folds_missing_audit(tmp_path):
    import _era_model_arms_9t as s6
    cfg = json.loads(json.dumps(CFG))
    cfg["inputs"]["audit_blocks"] = {"path": str(tmp_path / "none.csv")}
    df = pd.DataFrame({"block_id": list(range(10))})
    with pytest.raises(FileNotFoundError):
        s6.load_folds(cfg, df, provisional=False)
    _, info = s6.load_folds(cfg, df, provisional=True)
    assert info["audit"] == "no audit exclusion, exploratory"


def test_primary_one_class_resamples_are_counted_and_inconclusive():
    """5.2 NaN. Three blocks, one all early and two all late. A resample is one-class with probability
    (2/3)^3 + (1/3)^3 = 1/3 (hand oracle). With no declared max_undefined the decision is inconclusive."""
    import _era_model_arms_9t as s6
    rng = np.random.default_rng(0)
    pred = pd.DataFrame({"block_id": np.repeat([0, 1, 2], 10), "early": np.repeat([1.0, 0.0, 0.0], 10),
                         "M3_score": rng.uniform(size=30), "M1_score": rng.uniform(size=30)})
    cfg = json.loads(json.dumps(CFG))
    cfg["model"]["bootstrap_B"] = 2000
    r = s6.primary(pred, cfg)
    assert abs(r["undefined_share"] - 1 / 3) < 0.04
    assert np.isnan(r["lo"]) and r["decision"] == "inconclusive" and r["max_undefined"] == 0.0
