"""Smoke tests for 6.5 on the synthetic worked example. Seconds, CPU only, no network.

Run
    python -m pytest -q expansions/6_adjacent/6_5_field_methane/src/test_6_5.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _methane_claim_audit as CA  # noqa: E402
import _methane_field_table as FT  # noqa: E402
import _methane_sheet_check as SC  # noqa: E402


def test_sheet_check_flags_failed_span():
    cfg = SC.load_config()
    s = FT.example_sheet(cfg)
    probs, val = SC.check(cfg, s)
    v = val.set_index("visit_id")
    assert v.loc["SYN-B-2", "valid"] == False and "calibration" in v.loc["SYN-B-2", "reasons"]  # noqa: E712
    assert v.loc[["SYN-A-1", "SYN-A-2", "SYN-B-1"], "valid"].all()


def test_sheet_check_units_and_background():
    cfg = SC.load_config()
    s = FT.example_sheet(cfg)
    s.loc[s.visit_id == "SYN-A-1", "units"] = "ppm_m"
    s = s[~((s.visit_id == "SYN-A-2") & (s.reading_type == "background"))]
    probs, val = SC.check(cfg, s)
    assert (probs.rule == "units").any()
    assert "no background" in val.set_index("visit_id").loc["SYN-A-2", "reasons"]


def test_table_categories_and_repeat(tmp_path):
    cfg = SC.load_config()
    r = FT.build(cfg, FT.example_sheet(cfg), tmp_path)
    st = r["by_site"].set_index("site_id")
    assert st.loc["SYN-A", "repeat_agreement"] == True and st.loc["SYN-A", "n_valid_visits_detected"] == 2  # noqa: E712
    assert st.loc["SYN-B", "site_category"].startswith(FT.BELOW) and pd.isna(st.loc["SYN-B", "repeat_agreement"])
    bv = r["by_visit"]
    assert (bv.loc[bv.visit_id == "SYN-B-2", "category"] == "invalid visit").all()
    s = r["summary"]["share_sites_detected_any_visit"]
    assert s["k"] == 1 and s["n"] == 2 and s["lo95"] < 0.5 < s["hi95"]
    # same sheet twice gives identical tables (QC 7)
    r2 = FT.build(cfg, FT.example_sheet(cfg), tmp_path / "again")
    assert r2["by_site"].equals(r["by_site"])


def test_claim_audit(tmp_path):
    cfg = SC.load_config()
    FT.build(cfg, FT.example_sheet(cfg), tmp_path)
    texts = {f.name: f.read_text() for f in (tmp_path / "field_methane_by_site.csv", tmp_path / "field_methane_summary.json")}
    assert CA.audit_texts(cfg, texts) == []
    texts["report_summary.md"] = "Site SYN-B shows no leak. Emission rate 0.2 kg/h."
    hits = CA.audit_texts(cfg, texts)
    assert {h["phrase"] for h in hits} >= {"no leak", "emission rate", "kg/h", "missing required word 'screening'"}
