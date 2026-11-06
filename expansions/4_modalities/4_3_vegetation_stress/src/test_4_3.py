"""Smoke tests for 4.3 vegetation stress on tiny synthetic data. Seconds, no GPU, no network.

Run
    python -m pytest -q expansions/4_modalities/4_3_vegetation_stress/src/test_4_3.py -p no:cacheprovider
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box, Point

import _vegstress_shared_io as io
import _vegstress_label_audit_9t as v0
import _vegstress_observability_9t as v1
import _vegstress_match_controls_9t as vm
import _vegstress_extract_sites_9t as v2
import _vegstress_added_value_9t as v3
import _vegstress_leak_test_9t as v4

X0, Y0, EXT = 619500.0, 4593000.0, 1300.0


def _tif(path, bands: dict, res, crs="EPSG:6346"):
    import rasterio
    from rasterio.transform import from_origin
    names = list(bands)
    a = np.stack([bands[n] for n in names]).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[1], width=a.shape[2], count=a.shape[0],
                       dtype="float32", crs=crs, transform=from_origin(X0, Y0 + EXT, res, res), nodata=np.nan) as d:
        d.write(a)
        d.descriptions = tuple(names)
    return path


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    import geopandas as gpd
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    d = tmp_path_factory.mktemp("w43")
    pads, ctrls = [], []
    for i in range(100):
        cx, cy = X0 + 40 + (i % 10) * 125, Y0 + 40 + (i // 10) * 125
        pads.append(box(cx, cy, cx + 30, cy + 30))
        ctrls.append(box(cx + 65, cy + 65, cx + 95, cy + 95))
    leak = np.arange(100) < 50
    gpd.GeoDataFrame({"pad_id": range(100)}, geometry=pads, crs=6346).to_file(d / "pads.gpkg", layer="pad")
    gpd.GeoDataFrame({"control_id": range(100)}, geometry=ctrls, crs=6346).to_file(d / "ctrl.gpkg")
    gpd.GeoDataFrame({"PERMIT_NUM": [f"p{i}" for i in range(100)],
                      "SPUD_DATE": pd.to_datetime(["1900-01-01" if i % 3 else "1800-01-01" for i in range(100)])},
                     geometry=[Point(p.centroid.x, p.centroid.y) for p in pads], crs=6346).to_file(d / "wells.gpkg", layer="w")
    n1 = int(EXT)
    T1 = from_origin(X0, Y0 + EXT, 1, 1)
    chm = np.full((n1, n1), 20.0, "float32")
    chm[rasterize([(g, 1) for g in pads + ctrls], (n1, n1), transform=T1).astype(bool)] = 0.5
    _tif(d / "chm.tif", {"chm": chm}, 1)
    _tif(d / "dem.tif", {"dem": 400 + np.fromfunction(lambda r, c: 0.03 * c, (n1, n1))}, 1)
    n5 = n1 // 5
    T5 = from_origin(X0, Y0 + EXT, 5, 5)
    padm = rasterize([(g, 1) for g in pads], (n5, n5), transform=T5).astype(bool)
    leakm = rasterize([(g, 1) for g, l in zip(pads, leak) if l], (n5, n5), transform=T5).astype(bool)
    ctlm = rasterize([(g, 1) for g in ctrls], (n5, n5), transform=T5).astype(bool)
    rng = np.random.default_rng(0)
    scenes = []
    for k, (date, season) in enumerate((("2025-06-15", "leaf_on"), ("2025-09-15", "shoulder"), ("2025-03-15", "leaf_off"))):
        red, nir = np.full((n5, n5), 0.05), np.full((n5, n5), 0.40) - 0.1 * (season == "leaf_off")
        red[padm | ctlm], nir[padm | ctlm] = 0.10, 0.30
        nir[leakm] = 0.20
        nir += rng.normal(0, 0.005, nir.shape)
        p = _tif(d / f"s{k}.tif", {"green": red, "red": red, "nir": nir, "swir": np.full_like(red, 0.2),
                                   "scl": np.full_like(red, 4.0)}, 5)
        scenes.append({"scene_id": f"s{k}", "date": date, "season": season, "path": {"abs": str(p)}})
    recs = []
    for i in range(100):
        c = pads[i].centroid
        recs.append({"record_id": f"r{i}", "source": "measurement" if i % 2 else "complaint" if leak[i] else "inspection",
                     "date": "2015-05-01", "x": c.x + 20, "y": c.y, "coord_precision_m": 10,
                     "code": "GAS_MIGRATION" if leak[i] else "NO_VIOLATION", "lease_id": f"L{i // 2}",
                     "operator": "op", "permit_num": f"p{i}"})
    pd.DataFrame(recs).to_csv(d / "records.csv", index=False)
    cfg = io.load_config()
    cfg["inputs"].update(pads={"abs": str(d / "pads.gpkg"), "layer": "pad", "id_col": "pad_id"},
                         controls={"abs": str(d / "ctrl.gpkg"), "layer": None, "id_col": "control_id"},
                         chm={"abs": str(d / "chm.tif")}, dem={"abs": str(d / "dem.tif")},
                         dep_wells={"abs": str(d / "wells.gpkg"), "layer": "w"},
                         records={"abs": str(d / "records.csv")}, audit_blocks=None, folds=None)
    cfg["scenes"], cfg["scene_index"] = scenes, None
    cfg["observability"]["min_scenes_per_season"] = 1
    cfg["matching"].update(caliper_sd=3.0, exact=[])
    cfg["added_value"]["bootstrap_B"] = 100
    cfg["leak_test"].update(bootstrap_B=100, outer_folds=3)
    return d, cfg


def test_hanley_mcneil_40_vs_40():
    se = io.hanley_mcneil_se(0.70, 40, 40)
    assert se == pytest.approx(0.0585, abs=5e-4)
    assert 0.70 - 1.96 * se > 0.5 and io.min_n_per_class(0.70) <= 40


def test_indices_missing_bands_are_nan():
    ix = io.indices({"red": np.array([0.1]), "nir": np.array([0.3])})
    assert ix["ndvi"][0] == pytest.approx(0.5) and np.isnan(ix["ndre"][0]) and np.isnan(ix["evi"][0])


def test_chain(world):
    d, cfg = world
    res = d / "res"
    o = v1.run(cfg, out_root=res)
    assert o["per_pixel_size"]["10m"]["verdict"] in ("success", "inconclusive")
    assert o["per_pixel_size"]["30m"]["verdict"] == "failure"
    lab = v0.run(cfg, out_root=res)
    assert lab["verdict"] == "success" and lab["counts"]["leak"]["n"] == 50
    m = vm.run(cfg, out_root=res)
    assert m["n_pairs"] >= 90 and m["index_read"] is False
    sites = Path(m["run_dir"]) / "vegstress_matched_sites_9t.gpkg"
    e = v2.run(cfg, out_root=res, sites_path=sites)
    assert e["n_rows"] == e["n_sites"] * 3 and "ndre" in e["indices_all_nan"]
    by_site = Path(e["run_dir"]) / "vegstress_by_site_9t.csv"
    a = v3.run(cfg, out_root=res, sites_path=sites, by_site_path=by_site, fallback_folds=3)
    assert a["stage"] == "V3" and a["verdict"] in ("success", "failure", "inconclusive")
    # V4 uses pads-only V2 (all labelled pads), leak pads have lower NIR
    e2 = v2.run(cfg, out_root=res / "pads", pads_only=True)
    t = v4.run(cfg, out_root=res, labels_dir=Path(lab["run_dir"]), by_site_path=Path(e2["run_dir"]) / "vegstress_by_site_9t.csv")
    assert t["results"]["all"]["status"] == "ok"
    assert t["results"]["all"]["auc_cov_stress"] > 0.9


def test_leak_test_refuses_without_gate(world, tmp_path):
    d, cfg = world
    (tmp_path / "vegstress_label_counts_9t.json").write_text(json.dumps({"verdict": "failure"}))
    with pytest.raises(RuntimeError, match="not success"):
        v4.run(cfg, out_root=tmp_path, labels_dir=tmp_path)
