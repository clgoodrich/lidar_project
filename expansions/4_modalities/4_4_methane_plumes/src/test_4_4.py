"""Smoke tests for 4.4 methane on tiny synthetic data. Seconds, no network, no GPU.

Run  python -m pytest -q expansions/4_modalities/4_4_methane_plumes/src/test_4_4.py -p no:cacheprovider
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _methane_shared_io as io  # noqa: E402
import _methane_gate_limit_pa as M0  # noqa: E402
import _methane_plume_overlay_pa as M2  # noqa: E402
import _methane_source_model_pa as M3  # noqa: E402


def _cfg(tmp: Path) -> dict:
    cfg = copy.deepcopy(io.load_config())
    cfg["m0"]["wells_per_footprint"]["from_dep_points"] = str(tmp / "absent.gpkg")
    cfg["m0"]["population"]["documented_orphan_csv"] = str(tmp / "absent.csv")
    cfg["m0"]["well_emission"]["per_well_rates_csv"] = str(tmp / "absent_rates.csv")
    cfg["m0"]["tail_bootstrap_B"] = 50
    cfg["m3"]["bootstrap_B"] = 50
    return cfg


def test_m0_arithmetic_and_close(tmp_path):
    r = M0.run(_cfg(tmp_path), out_root=tmp_path, dep_count=False)
    inst = r["result"]["instruments"][0]
    assert inst["R_mean_stated_low"] == pytest.approx(90 / (0.27 / 24))   # 8000
    assert inst["R_mean_best_case"] == pytest.approx(800.0)
    assert inst["gates"]["mean"] == "failure"
    assert inst["gates"]["tail"]["verdict"] == "inconclusive"             # no per-well rates
    assert r["result"]["overall_verdict"] == "CLOSE"                      # fallback 4 wells: 800 >= 400
    assert r["png"].exists() and (r["run_dir"] / "_PROVENANCE.json").exists()


def test_m0_tail_fit_runs(tmp_path):
    rng = np.random.default_rng(0)
    rates = pd.DataFrame({"well_id": range(19), "rate_kg_per_day": np.exp(rng.normal(-4, 3, 19))})
    p = tmp_path / "rates.csv"
    rates.to_csv(p, index=False)
    r = M0.run(_cfg(tmp_path), out_root=tmp_path, dep_count=False, rates_csv=p)
    tail = r["result"]["instruments"][0]["tail_fit"]
    assert 0 <= tail["lognormal"]["p_exceed"] <= 1 and tail["n_wells_used"] == 19
    assert r["result"]["instruments"][0]["gates"]["tail"]["verdict"] in ("success", "failure", "inconclusive")


def test_wells_per_footprint_drops_stacked_records():
    xy = np.array([[0.0, 0.0]] * 41 + [[5.0, 5.0], [10.0, 10.0], [100.0, 100.0]])
    w = M0.wells_per_footprint(xy, 30.0)
    assert w["max_raw"] >= 43 and w["max"] == 3 and w["max_stacked"] == 41


def _synthetic_catalogue(tmp: Path):
    import geopandas as gpd
    from pyproj import Transformer
    tf = Transformer.from_crs("EPSG:6346", "EPSG:4326", always_xy=True)
    x0, y0 = 620000.0, 4594000.0
    wells = [(x0 + 1000 * i, y0 + 1000 * j) for i in range(4) for j in range(4)]
    lon, lat = tf.transform(*np.array(wells).T)
    pd.DataFrame({"Longitude": lon, "Latitude": lat}).to_csv(tmp / "wells.csv", index=False)
    # source A at well 0 seen on 3 dates, source B at a facility, one bad-QA plume
    rows = []
    for k, (px, py, d, qa) in enumerate([(wells[0][0] + 20, wells[0][1], "2025-05-01", "good"),
                                         (wells[0][0] - 15, wells[0][1] + 10, "2025-06-01", "good"),
                                         (wells[0][0], wells[0][1] - 25, "2025-07-01", "good"),
                                         (x0 + 2500, y0 + 2500, "2025-05-01", "good"),
                                         (x0 + 3500, y0 + 500, "2025-05-01", "bad")]):
        lo, la = tf.transform(px, py)
        rows.append(dict(plume_id=f"p{k}", lat=la, lon=lo, emission_kg_h=200.0, emission_unc_kg_h=50.0,
                         source_unc_m=100.0, instrument="tanager", datetime_utc=d + "T16:00:00Z", sector="og",
                         qa_flag=qa, wind_source="hrrr", known_before_detection="false"))
    pd.DataFrame(rows).to_csv(tmp / "plumes.csv", index=False)
    fx, fy = x0 + 2500, y0 + 2530
    gpd.GeoDataFrame({"facility_id": [1], "facility_type": ["compressor"]},
                     geometry=gpd.points_from_xy([fx], [fy]), crs="EPSG:6346").to_file(tmp / "fac.gpkg")
    fp = gpd.GeoSeries.from_xy([x0 + 1500], [y0 + 1500], crs="EPSG:6346").buffer(6000).to_crs("EPSG:4326")
    pd.DataFrame({"obs_id": [f"o{i}" for i in range(6)], "instrument": "tanager",
                  "datetime_utc": pd.date_range("2025-05-01", periods=6, freq="MS").astype(str),
                  "footprint_wkt": [fp.iloc[0].wkt] * 6, "plume_search_done": "true",
                  "qa_flag": "good"}).to_csv(tmp / "obs.csv", index=False)
    (tmp / "log.json").write_text(json.dumps({"reported_total": 5, "pages": [{"page": 1, "status": "ok", "n": 5}]}))


def test_m2_m3_overlay_and_sources(tmp_path):
    _synthetic_catalogue(tmp_path)
    cfg = _cfg(tmp_path)
    cfg["m2"].update(plume_catalogue_csv=str(tmp_path / "plumes.csv"), catalogue_fetch_log=str(tmp_path / "log.json"),
                     observations_csv=str(tmp_path / "obs.csv"), wells_gpkg=str(tmp_path / "wells.csv"),
                     orphan_csv=None, candidate_wells_gpkg=None, facilities_gpkg=str(tmp_path / "fac.gpkg"),
                     pads_gpkg=None, cell_m=2000.0)
    r2 = M2.run(cfg, out_root=tmp_path)
    ov = pd.read_csv(r2["overlay"])
    assert len(ov) == 5 and r2["summary"]["qc"]["query"]["complete"]
    assert ov.loc[ov.plume_id == "p0", "n_dep_well"].iloc[0] == 1
    assert ov.loc[ov.plume_id == "p3", "near_facility"].iloc[0]
    r3 = M3.run(cfg, out_root=tmp_path, overlay_dir=r2["run_dir"])
    S = pd.read_csv(r3["sources"])
    assert len(S) == 2                                   # 4 usable plumes -> 2 sources
    a = S.loc[S.n_obs == 3].iloc[0]
    assert a.reading.startswith("well is the plausible source") and a.n_dates == 3
    rr = r3["result"]["rate_ratio"]["all_cells"]
    assert rr["n_wells"] > 0 and rr["verdict"] in ("success", "failure", "inconclusive")


def test_missing_input_message(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["m2"]["plume_catalogue_csv"] = str(tmp_path / "nope.csv")
    with pytest.raises(FileNotFoundError, match="MISSING INPUT plume catalogue"):
        M2.run(cfg, out_root=tmp_path)
