"""Smoke tests for 4.2 thermal on tiny synthetic data. Seconds, no GPU, no network.

Run
    python -m pytest -q expansions/4_modalities/4_2_thermal/src/test_4_2.py -p no:cacheprovider
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

import _thermal_shared_io as io
import _thermal_gate_contrast_9t as t1
import _thermal_match_clearings_9t as tm
import _thermal_extract_samples_9t as t2
import _thermal_contrast_model_9t as t3
import _thermal_added_value_9t as t4

X0, Y0 = 619500.0, 4593000.0


def _tif(path, arr, res, x0=X0, y0=Y0 + 1500, crs="EPSG:6346", count=1):
    import rasterio
    from rasterio.transform import from_origin
    a = arr if arr.ndim == 3 else arr[None]
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[1], width=a.shape[2], count=a.shape[0],
                       dtype="float32", crs=crs, transform=from_origin(x0, y0, res, res), nodata=np.nan) as d:
        d.write(a.astype("float32"))
    return path


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    import geopandas as gpd
    d = tmp_path_factory.mktemp("w42")
    rng = np.random.default_rng(1)
    pads, clears = [], []
    for i in range(24):
        cx, cy = X0 + 100 + (i % 6) * 220, Y0 + 100 + (i // 6) * 330
        s = rng.uniform(25, 45)
        pads.append(box(cx, cy, cx + s, cy + s))
        clears.append(box(cx + 110, cy + 120, cx + 110 + s * rng.uniform(0.9, 1.1), cy + 120 + s))
    gpd.GeoDataFrame({"pad_id": range(24)}, geometry=pads, crs=6346).to_file(d / "pads.gpkg", layer="pad")
    gpd.GeoDataFrame({"clearing_id": range(24)}, geometry=clears, crs=6346).to_file(d / "clear.gpkg")
    n = 750                                     # 2 m grid over 1500 m
    yy, xx = np.mgrid[0:n, 0:n]
    dem = 400 + 0.05 * xx + 0.02 * yy
    chm = np.full((n, n), 20.0)
    padm = np.zeros((n, n), bool)
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    T2 = from_origin(X0, Y0 + 1500, 2, 2)
    padm = rasterize([(g, 1) for g in pads], (n, n), transform=T2).astype(bool)
    clm = rasterize([(g, 1) for g in clears], (n, n), transform=T2).astype(bool)
    chm[padm | clm] = 0.5
    _tif(d / "chm.tif", chm, 2)
    _tif(d / "dem.tif", dem, 2)
    # 10 m LST scenes: pads 3 K warmer than clearings, forest 2 K cooler
    m = 150
    T10 = from_origin(X0, Y0 + 1500, 10, 10)
    pad10 = rasterize([(g, 1) for g in pads], (m, m), transform=T10, all_touched=True).astype(bool)
    cl10 = rasterize([(g, 1) for g in clears], (m, m), transform=T10, all_touched=True).astype(bool)
    rows = []
    for k in range(6):
        lst = 290 + k + rng.normal(0, 0.2, (m, m)) - 2.0
        lst[cl10] = 290 + k
        lst[pad10] = 293 + k
        p = _tif(d / f"scene{k}.tif", lst, 10)
        rows.append({"scene_id": f"s{k}", "sensor": "landsat_tirs", "datetime_utc": f"2024-0{k + 3}-15T15:20:00",
                     "path": p.name, "cloud_frac": 0.0, "qc_pass": True, "lst_err_K": 1.0})
    pd.DataFrame(rows).to_csv(d / "scenes.csv", index=False)
    pd.DataFrame({"date": pd.date_range("2024-01-01", "2024-12-31").strftime("%Y-%m-%d"), "ppt": 1.0,
                  "tmin": 0, "tmax": 10}).to_csv(d / "prism.csv", index=False)
    pd.DataFrame({"date": ["2024-03-01", "2024-07-01"], "leaf_state": ["leaf_off", "leaf_on"]}).to_csv(d / "leaf.csv", index=False)
    cfg = io.load_config()
    cfg["inputs"].update(pads={"abs": str(d / "pads.gpkg"), "layer": "pad", "id_col": "pad_id"},
                         clearings={"abs": str(d / "clear.gpkg"), "layer": None, "id_col": "clearing_id"},
                         chm={"abs": str(d / "chm.tif")}, dem={"abs": str(d / "dem.tif")},
                         nlcd={"abs": str(d / "none.tif")}, prism={"abs": str(d / "prism.csv")},
                         leaf_state={"abs": str(d / "leaf.csv")}, audit_blocks=None, folds=None)
    cfg["sensors"] = [dict(cfg["sensors"][0], lst_scale=1.0, lst_offset=0.0, err_band=None,
                           scene_index={"abs": str(d / "scenes.csv")}, tiepoints=None)]
    cfg["gate"]["bootstrap_B"] = 200
    cfg["matching"].update(forest_chm_min_m=10.0, caliper_sd=3.0, exact=[])
    return d, cfg


def test_fill_fraction_exact():
    assert io.fill_fraction(box(0, 0, 50, 50), 100.0) == pytest.approx(0.25)
    assert io.fill_fraction(box(50, 50, 150, 150), 100.0) == pytest.approx(0.25)
    assert io.fill_fraction_offsets(box(0, 0, 100, 100), 100.0, 32, np.random.default_rng(0)) < 1.0


def test_solar_noon_summer():
    zen, az = io.solar_position("2024-06-21T17:20:00Z", 41.4, -79.7)   # near local solar noon
    assert 17 < zen < 20 and 150 < az < 210


def test_match_caliper_no_reuse():
    a = pd.DataFrame({"id": [1, 2], "x": [0.0, 1.0]})
    b = pd.DataFrame({"id": [10, 11, 12], "x": [0.05, 0.9, 5.0]})
    p = io.match_caliper(a, b, "id", ["x"], caliper_sd=0.5)
    assert set(p.control_id) == {10, 11} and p.control_id.is_unique


def test_chain(world):
    d, cfg = world
    g = t1.run(cfg, out_root=d / "res")
    assert g["t0"]["verdict"] == "success"
    assert g["sensors"]["landsat_tirs"]["scenes"]["usable"] == 6
    m = tm.run(cfg, out_root=d / "res")
    assert m["n_pairs"] >= 20 and m["lst_read"] is False
    sites = Path(m["run_dir"]) / "thermal_matched_sites_9t.gpkg"
    s = t2.run(cfg, "landsat_tirs", out_root=d / "res", sites_path=sites,
               gate_path=Path(g["run_dir"]) / "thermal_gate_summary_9t.json")
    assert s["n_rows"] == s["n_sites"] * 6
    samples = Path(s["run_dir"]) / "thermal_samples_by_scene_9t.csv"
    c = t3.run(cfg, out_root=d / "res", samples_path=samples)
    assert c["signed_contrast_K"] > 1.0          # injected +3 K at the pixel, diluted by partial pixels
    a = t4.run(cfg, out_root=d / "res", sites_path=sites, samples_path=samples, fallback_folds=3)
    assert a["auc"]["lidar_plus"] >= a["auc"]["lidar_only"] - 1e-9
    assert json.loads((Path(a["run_dir"]) / "thermal_added_value_9t.json").read_text())["stage"] == "T4"


def test_missing_input_message(world):
    d, cfg = world
    with pytest.raises(FileNotFoundError, match="MISSING INPUT"):
        tm.run(cfg, out_root=d / "res", clearings_path=d / "nope.gpkg")
