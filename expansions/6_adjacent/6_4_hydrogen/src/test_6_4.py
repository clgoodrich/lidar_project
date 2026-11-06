"""Smoke tests for 6.4 (hydrogen profile of the 6.1 pipeline). Seconds, CPU only, no network.

Run
    python -m pytest -q expansions/6_adjacent/6_4_hydrogen/src/test_6_4.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "6_1_co2_geothermal" / "src"))
import _h2_screen_run_9t as H2  # noqa: E402
import test_6_1 as T61  # noqa: E402


def _tops(tmp: Path, units="ft") -> Path:
    p = tmp / "tops.csv"
    pd.DataFrame({"permit": [None], "reservoir_top": [2000.0], "seal_top": [1500.0], "units": [units],
                  "datum": ["KB"]}).to_csv(p, index=False)
    return p


def test_profile_merge():
    cfg = H2.merged_config()
    prof = H2.L.load_profile(cfg, "hydrogen")
    assert len(prof["limits"]) == 10 and prof["screen_layer"] == "L7_field_boundary"
    assert "suitable" in prof["banned_phrases"] and "leak" in prof["banned_phrases"]
    assert cfg["profiles"]["co2"]["screen_layer"] == "L7_screen_area"     # 6.1 profile untouched


def test_penetration_flag_records_only():
    rec = pd.DataFrame({"record_id": ["a", "b", "c", "d"], "depth_ft": [3000, 1700, 900, None]})
    tops = pd.DataFrame({"reservoir_top": [2000.0], "seal_top": [1500.0], "units": ["ft"]})
    r, info = H2.penetration_flag(rec, tops, 50, 0.5)
    assert list(r.penetration_flag) == ["reaches reservoir (from records)", "reaches seal only (from records)",
                                        "above seal (from records)", "unknown"]
    r2, info2 = H2.penetration_flag(rec.assign(depth_ft=[None, None, None, 100]), tops, 50, 0.5)
    assert info2["dropped"] and r2.penetration_flag.str.startswith("dropped").all()


def test_units_mismatch_fails(tmp_path):
    cfg = H2.merged_config()
    with pytest.raises(AssertionError, match="units"):
        H2.read_tops(cfg, _tops(tmp_path, units="m"))


def test_missing_tops_named(tmp_path):
    cfg = H2.merged_config()
    with pytest.raises(H2.L.MissingInput, match="reservoir_tops"):
        H2.read_tops(cfg, tmp_path / "absent.csv")


def test_h2_chain(tmp_path):
    cfg = H2.merged_config()
    prof = H2.L.load_profile(cfg, "hydrogen")
    w = T61.make_world(tmp_path)
    w["reservoir_tops"] = _tops(tmp_path)
    out = tmp_path / "h2"
    out.mkdir()
    rh, el, er, state = H2.hooks(cfg, w)
    res = H2.RUN.run_all(cfg, prof, out, w, records_hook=rh, extra_layers=el, extra_rows=er, B=20)
    assert res["claim_hits"] == 0, pd.read_csv(out / "screen_claim_audit_h2_9t.csv")
    import pyogrio
    names = {r[0] for r in pyogrio.list_layers(out / "screening_package_h2_9t.gpkg")}
    assert "L7_field_boundary" in names and "L7_screen_area" not in names
    rec = pyogrio.read_dataframe(out / "screening_package_h2_9t.gpkg", layer="L1_records")
    assert set(rec.penetration_flag) == {"reaches reservoir (from records)", "unknown", "above seal (from records)"}
    cand = pyogrio.read_dataframe(out / "screening_package_h2_9t.gpkg", layer="L2_candidates")
    assert "penetration_flag" not in cand.columns
    c = pd.read_csv(out / "screening_counts_h2_9t.csv").set_index("metric")
    assert c.loc["h2_flag_reaches_reservoir", "value"] == 1
    text = (out / "screening_summary_h2_9t.md").read_text()
    assert "fast-leaking" in text and text.index("cannot tell you") < text.index("## Candidates")


def test_h2_reader_zero_tolerance():
    prof = H2.L.load_profile(H2.merged_config(), "hydrogen")
    qs = list(prof["reader_questions"])
    a = pd.DataFrame([{"reader_id": f"R{r}", "question_id": q, "correct": 1} for r in range(6) for q in qs])
    a.loc[(a.reader_id == "R2") & (a.question_id == "Q_h2_material"), "correct"] = 0
    assert H2.RC.gate(prof, a)["gate"] == "failure"


# ----------------------------------------------------------------------------- 2026-11-06 review fix 6.4-01
def _world_no_depth(tmp_path):
    import geopandas as gpd
    w = T61.make_world(tmp_path)
    g = gpd.read_file(w["dep_wells"])
    g["TOTAL_MAXI"] = ""                    # the held DEP export has an empty string in every row
    g.to_file(tmp_path / "wells_nodepth.gpkg")
    w["dep_wells"] = tmp_path / "wells_nodepth.gpkg"
    w["reservoir_tops"] = _tops(tmp_path)
    return w


def test_zero_depth_coverage_fails_loudly(tmp_path):
    cfg = H2.merged_config()
    prof = H2.L.load_profile(cfg, "hydrogen")
    w = _world_no_depth(tmp_path)
    out = tmp_path / "h2"
    out.mkdir()
    rh, el, er, _ = H2.hooks(cfg, w)
    with pytest.raises(H2.NoDepthInRecords, match="depth coverage is 0"):
        H2.RUN.run_all(cfg, prof, out, w, records_hook=rh, extra_layers=el, extra_rows=er, B=20, figure=False)


def test_zero_depth_coverage_reported_not_dropped(tmp_path):
    cfg = H2.merged_config()
    prof = H2.L.load_profile(cfg, "hydrogen")
    w = _world_no_depth(tmp_path)
    out = tmp_path / "h2"
    out.mkdir()
    rh, el, er, _ = H2.hooks(cfg, w, allow_no_depth=True)
    H2.RUN.run_all(cfg, prof, out, w, records_hook=rh, extra_layers=el, extra_rows=er, B=20, figure=False)
    import pyogrio
    rec = pyogrio.read_dataframe(out / "screening_package_h2_9t.gpkg", layer="L1_records")
    assert set(rec.penetration_flag) == {"not computable, no depth in records"}
    c = pd.read_csv(out / "screening_counts_h2_9t.csv").set_index("metric")
    assert c.loc["h2_depth_coverage_share", "value"] == 0
    assert c.loc["h2_penetration_flag_not_computable", "value"] == 1
    assert "h2_penetration_flag_dropped" not in c.index
    assert "not computable" in (out / "screening_summary_h2_9t.md").read_text()
