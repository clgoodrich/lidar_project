"""Smoke tests for 6.1 on tiny synthetic data. Seconds, CPU only, no network.

Run
    python -m pytest -q expansions/6_adjacent/6_1_co2_geothermal/src/test_6_1.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _co2_reader_check_9t as RC  # noqa: E402
import _co2_screen_lib as L  # noqa: E402
import _co2_screen_run_9t as RUN  # noqa: E402

CRS = "EPSG:6346"
X0, Y0 = 600000.0, 4590000.0


def make_world(tmp: Path) -> dict:
    """Four 100 m blocks. Block 3 has no ground returns (blind zone)."""
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    blocks = gpd.GeoDataFrame({"block_id": [0, 1, 2, 3]},
                              geometry=[box(X0 + i * 100, Y0, X0 + (i + 1) * 100, Y0 + 100) for i in range(4)], crs=CRS)
    bp = tmp / "blocks.gpkg"
    blocks.to_file(bp, layer="blocks")
    tf = from_origin(X0, Y0 + 100, 1.0, 1.0)
    dens = np.full((100, 400), 4, np.uint16)
    dens[:, 300:] = 0
    dens[::3, 200:300] = 0                      # 33% void, still eligible
    chm = np.zeros((100, 400), np.float32)
    chm[:, 100:200] = 15.0
    prof = dict(driver="GTiff", width=400, height=100, count=1, crs=CRS, transform=tf)
    with rasterio.open(tmp / "dens.tif", "w", dtype="uint16", nodata=0, **prof) as r:
        r.write(dens, 1)
    with rasterio.open(tmp / "chm.tif", "w", dtype="float32", nodata=-9999, **prof) as r:
        r.write(chm, 1)
    wells = gpd.GeoDataFrame({
        "PERMIT_NUM": ["121-1", "121-2", "121-3"], "WELL_STATU": ["Plugged OG Well", "Active", "Orphan"],
        "WELL_TYPE": ["OIL", "GAS", "OIL"], "TOTAL_MAXI": [1200.0, None, 3000.0],
        "DATE_PLUGG": pd.to_datetime(["1980-01-04", None, None]),
        "SPUD_DATE": pd.to_datetime(["1800-01-01", "1979-01-01", None]), "STORAGE_FI": [None, "Field A", None]},
        geometry=gpd.points_from_xy([X0 + 20, X0 + 150, X0 + 250], [Y0 + 50] * 3), crs=CRS)
    wells.to_file(tmp / "wells.gpkg")
    cand = gpd.GeoDataFrame({"site_id": ["s1", "s2", "s3", "s4"], "score": [0.9, 0.7, 0.55, 0.3], "fold": [0, 1, 2, 3]},
                            geometry=[box(X0 + 18, Y0 + 48, X0 + 24, Y0 + 54), box(X0 + 120, Y0 + 20, X0 + 126, Y0 + 26),
                                      box(X0 + 330, Y0 + 50, X0 + 336, Y0 + 56), box(X0 + 60, Y0 + 60, X0 + 63, Y0 + 63)],
                            crs=CRS)
    cand.to_file(tmp / "cand.gpkg")
    return {"blocks": bp, "ground_density": tmp / "dens.tif", "chm": tmp / "chm.tif",
            "dep_wells": tmp / "wells.gpkg", "candidates_pit": tmp / "cand.gpkg"}


def test_full_chain(tmp_path):
    cfg = L.load_config()
    prof = L.load_profile(cfg, "co2")
    w = make_world(tmp_path)
    out = tmp_path / "run"
    out.mkdir()
    res = RUN.run_all(cfg, prof, out, w, B=50)
    assert res["claim_hits"] == 0, pd.read_csv(out / "screen_claim_audit_9t.csv")
    import json
    s1 = json.loads((out / "screen_eligible_summary_9t.json").read_text())
    assert s1["n_blocks"] == 4 and s1["n_blind"] == 1
    import pyogrio
    names = {r[0] for r in pyogrio.list_layers(out / "screening_package_9t.gpkg")}
    assert {"L0_limits", "L1_records", "L2_candidates", "L4_eligible", "L7_screen_area"} <= names
    cand = pyogrio.read_dataframe(out / "screening_package_9t.gpkg", layer="L2_candidates")
    assert len(cand) == 3                               # s4 under the frozen cutoff
    assert set(cand.evidence_level) == {"a"} and set(cand.label) == {"candidate"}
    assert cand.set_index("site_id").loc["s3", "in_blind_zone"] in (True, 1, "True")
    c = pd.read_csv(out / "screening_counts_9t.csv").set_index("metric")
    assert c.loc["records_in_area", "value"] == 3
    assert c.loc["records_spud_sentinel_1800", "value"] == 1
    assert not c.index.str.contains("recall").any()
    text = (out / "screening_summary_9t.md").read_text()
    assert text.index("cannot tell you") < text.index("## Candidates")
    assert "hypothetical" in text
    assert (out / "screening_map_9t.png").exists() and (out / "_PROVENANCE.json").exists()


def test_claim_audit_catches_banned(tmp_path):
    cfg = L.load_config()
    prof = L.load_profile(cfg, "co2")
    out = tmp_path / "run"
    out.mkdir()
    RUN.run_all(cfg, prof, out, make_world(tmp_path), B=20, figure=False)
    s = out / "screening_summary_9t.md"
    s.write_text(s.read_text() + "\nThe inventory is complete and safe.\n")
    import _co2_claim_audit_9t as S5
    _, n = S5.audit(cfg, prof, out)
    assert n == 2


def test_missing_input_message(tmp_path):
    cfg = L.load_config()
    cfg["inputs"]["candidates_pit"] = {"path": str(tmp_path / "nope.gpkg"), "state": "assumed (5.6 output)",
                                      "schema": {"site_id": "str"}}
    with pytest.raises(L.MissingInput, match="candidates_pit"):
        L.input_path(cfg, "candidates_pit")


def test_reader_gate():
    prof = L.load_profile(L.load_config(), "co2")
    qs = list(prof["reader_questions"])
    ok = pd.DataFrame([{"reader_id": f"R{r}", "question_id": q, "correct": 1} for r in range(5) for q in qs])
    assert RC.gate(prof, ok)["gate"] == "success"
    bad = ok.copy()
    bad.loc[(bad.reader_id == "R0") & (bad.question_id == "Q_complete"), "correct"] = 0
    assert RC.gate(prof, bad)["gate"] == "failure"
    few = ok[ok.reader_id.isin(["R0", "R1", "R2"])]
    assert RC.gate(prof, few)["gate"] == "inconclusive"
