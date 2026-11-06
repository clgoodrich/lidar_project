"""Smoke tests for 6.1 on tiny synthetic data. Seconds, CPU only, no network.

Run
    python -m pytest -q expansions/6_adjacent/6_1_co2_geothermal/src/test_6_1.py -p no:cacheprovider
"""
from __future__ import annotations

import json
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


# ----------------------------------------------------------------------------- 2026-11-06 review fixes
def _legacy_pit_pad_files(tmp: Path) -> tuple[Path, Path]:
    """Pre-2026-11-06 5.6 files. They reuse det_id 0..n-1 in each file and carry no kind column. No producer
    writes this shape any more, so this one fixture is hand built. It checks that old files stay safe."""
    import geopandas as gpd
    from shapely.geometry import box
    pit = gpd.GeoDataFrame({"det_id": [0, 1], "score": [0.9, 0.8], "source": ["matched", "undecided"]},
                           geometry=[box(X0 + 18, Y0 + 48, X0 + 24, Y0 + 54), box(X0 + 120, Y0 + 20, X0 + 126, Y0 + 26)],
                           crs=CRS)
    pad = gpd.GeoDataFrame({"det_id": [0, 1], "score": [0.85, 0.7], "source": ["matched", "unmatched"]},
                           geometry=[box(X0 + 140, Y0 + 40, X0 + 170, Y0 + 70), box(X0 + 210, Y0 + 10, X0 + 240, Y0 + 40)],
                           crs=CRS)
    pp, dp = tmp / "pit_legacy.gpkg", tmp / "pad_legacy.gpkg"
    pit.to_file(pp)
    pad.to_file(dp)
    return pp, dp


def _real_56_files(tmp: Path, blocks: Path) -> tuple[Path, Path]:
    """Run the real 5.6 S0 writer (_records_full_detector_output_9t.main) on raw upstream layers in the shape the
    5.6 policy re-cut writes (matched and undecided pit layers, pad model_geometry, thr_used at the policy
    cutoffs). 6.1 then reads the writer's files unmodified (fix rule. no consumer-shaped fixtures)."""
    import json
    import geopandas as gpd
    from shapely.geometry import box
    src56 = Path(__file__).resolve().parents[3] / "5_tasks" / "5_6_record_association" / "src"
    if str(src56) not in sys.path:
        sys.path.insert(0, str(src56))
    import _records_full_detector_output_9t as s0
    d = tmp / "s56"
    d.mkdir(exist_ok=True)
    pits = gpd.GeoDataFrame({"score": [0.9, 0.8], "near_pit_m": [0.0, 30.0], "dup_on_pit": [1, 0],
                             "fold": [0, 1], "thr_used": [0.35, 0.35]},
                            geometry=[box(X0 + 18, Y0 + 48, X0 + 24, Y0 + 54), box(X0 + 120, Y0 + 20, X0 + 126, Y0 + 26)],
                            crs=CRS)
    cand = d / "pit_recut.gpkg"
    pits.iloc[:1].to_file(cand, layer="matched", driver="GPKG")
    pits.iloc[1:].to_file(cand, layer="undecided", driver="GPKG")
    pads = gpd.GeoDataFrame({"score": [0.85, 0.7], "thr_used": [0.525, 0.525]},
                            geometry=[box(X0 + 140, Y0 + 40, X0 + 170, Y0 + 70), box(X0 + 210, Y0 + 10, X0 + 240, Y0 + 40)],
                            crs=CRS)
    padp = d / "pad_recut.gpkg"
    pads.to_file(padp, layer="model_geometry", driver="GPKG")
    ann = d / "ann.gpkg"
    gpd.GeoDataFrame({"pad_id": [7]}, geometry=[pads.geometry.iloc[0]], crs=CRS).to_file(ann, layer="plat", driver="GPKG")
    cfg = json.loads((src56 / "config_5_6.json").read_text())
    cfg["pit"]["expected_predictions"] = 2
    pp, dp = d / "detector_output_pit_full_9t.gpkg", d / "detector_output_pad_full_9t.gpkg"
    cfg["inputs"].update(pit_candidates=str(cand), pad_products=dict(path=str(padp), layer="model_geometry"),
                         annotations=str(ann), pit_blocks=str(blocks), pad_blocks=str(blocks))
    cfg["outputs"].update(full_pit=str(pp), full_pad=str(dp), row_counts=str(d / "rows.csv"),
                          id_policy=str(d / "ids.json"))
    cp = d / "cfg.json"
    cp.write_text(json.dumps(cfg))
    assert s0.main(["--config", str(cp)]) == 0
    return pp, dp


@pytest.mark.parametrize("contract", [False, True])
def test_pit_pad_ids_keyed_by_kind(tmp_path, contract):
    """6.1-01. Colliding det_id 0 in the pit and the pad file must give two sites, keyed kind + det_id."""
    cfg = L.load_config()
    prof = L.load_profile(cfg, "co2")
    w = make_world(tmp_path)
    w["candidates_pit"], w["candidates_pad"] = (_real_56_files(tmp_path, w["blocks"]) if contract
                                                else _legacy_pit_pad_files(tmp_path))
    out = tmp_path / "run"
    out.mkdir()
    RUN.run_all(cfg, prof, out, w, B=20, figure=False)
    import pyogrio
    cand = pyogrio.read_dataframe(out / "screening_package_9t.gpkg", layer="L2_candidates")
    want = {"pit:1", "pit:2", "pad:1000001", "pad:1000002"} if contract else {"pit:0", "pit:1", "pad:0", "pad:1"}
    assert set(cand.site_uid) == want
    assert "proposals" not in cfg["inputs"]          # no reader of the producer-less proposals_56_9t.csv


def test_kind_column_must_match_file(tmp_path):
    cfg = L.load_config()
    pp, dp = _real_56_files(tmp_path, make_world(tmp_path)["blocks"])
    with pytest.raises(AssertionError, match="kind"):
        L.read_candidates(cfg, pit_override=dp, pad_override=pp)     # swapped files


def test_blind_zone_candidates_do_not_use_k(tmp_path):
    """6.1 minor. Three eligible 100 m blocks give 0.03 km2, so K = round(40 * 0.03) = 1. The top score sits in the
    blind block 3. Before the fix it took the only K slot. After the fix the top eligible candidate s1 gets it."""
    import geopandas as gpd
    from shapely.geometry import box
    cfg = L.load_config()
    prof = L.load_profile(cfg, "co2")
    w = make_world(tmp_path)
    cand = gpd.GeoDataFrame({"site_id": ["blind", "s1", "s2"], "score": [0.99, 0.9, 0.7]},
                            geometry=[box(X0 + 330, Y0 + 50, X0 + 336, Y0 + 56), box(X0 + 18, Y0 + 48, X0 + 24, Y0 + 54),
                                      box(X0 + 120, Y0 + 20, X0 + 126, Y0 + 26)], crs=CRS)
    cand.to_file(tmp_path / "cand_blind.gpkg")
    w["candidates_pit"] = tmp_path / "cand_blind.gpkg"
    out = tmp_path / "run"
    out.mkdir()
    RUN.run_all(cfg, prof, out, w, B=20, figure=False)
    import pyogrio
    c = pyogrio.read_dataframe(out / "screening_package_9t.gpkg", layer="L2_candidates").set_index("site_id")
    within = c["within_k"].astype(str).isin(["True", "1"])
    assert within.to_dict() == {"blind": False, "s1": True, "s2": False}
    assert pd.isna(c.loc["blind", "k_rank"]) and c.loc["s1", "k_rank"] == 1


def test_records_with_depth_zero_is_labelled(tmp_path):
    """6.4-01 seen from 6.1. An all-empty depth field gives 0 and a note that says so."""
    import geopandas as gpd
    cfg = L.load_config()
    prof = L.load_profile(cfg, "co2")
    w = make_world(tmp_path)
    g = gpd.read_file(w["dep_wells"])
    g["TOTAL_MAXI"] = ""                         # as in venango_wells_all.gpkg, empty string in every row
    g.to_file(tmp_path / "wells_nodepth.gpkg")
    w["dep_wells"] = tmp_path / "wells_nodepth.gpkg"
    out = tmp_path / "run"
    out.mkdir()
    RUN.run_all(cfg, prof, out, w, B=20, figure=False)
    c = pd.read_csv(out / "screening_counts_9t.csv").set_index("metric")
    assert c.loc["records_with_depth", "value"] == 0
    assert "no depth in records" in c.loc["records_with_depth", "note"]


def test_cutoff_is_per_kind_policy(tmp_path):
    """2026-11-06. A pit blob of mean 0.40 is kept (pit cutoff 0.35). A pad of mean 0.50 is dropped (pad cutoff
    0.525). The old single 0.50 cutoff dropped the pit. Hand oracle: 1 pit and 1 pad kept."""
    import geopandas as gpd
    from shapely.geometry import box
    cfg = L.load_config()
    assert L.frozen_cutoffs(cfg) == {"pit": 0.35, "pad": 0.525}
    pit = gpd.GeoDataFrame({"det_id": [1, 2], "kind": "pit", "score": [0.40, 0.30]},
                           geometry=[box(X0, Y0, X0 + 4, Y0 + 4), box(X0 + 50, Y0, X0 + 54, Y0 + 4)], crs=CRS)
    pad = gpd.GeoDataFrame({"det_id": [1000001, 1000002], "kind": "pad", "score": [0.50, 0.60]},
                           geometry=[box(X0, Y0 + 50, X0 + 30, Y0 + 80), box(X0 + 100, Y0, X0 + 130, Y0 + 30)], crs=CRS)
    pp, dp = tmp_path / "p.gpkg", tmp_path / "d.gpkg"
    pit.to_file(pp)
    pad.to_file(dp)
    c = L.read_candidates(cfg, pit_override=pp, pad_override=dp)
    assert set(c.site_uid) == {"pit:1", "pad:1000002"}
    bad = json.loads(json.dumps(cfg))
    bad["params"]["frozen_cutoff"] = 0.5
    with pytest.raises(SystemExit):
        L.frozen_cutoffs(bad)
