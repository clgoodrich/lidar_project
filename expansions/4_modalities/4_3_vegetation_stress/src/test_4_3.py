"""Tests for 4.3 vegetation stress on tiny synthetic data. Seconds, no GPU, no network.

Scenes are written the way the held stacks were made. Native 10 m (green, red, nir) and 20 m (swir, scl)
pixels copied onto a 5 m grid, stored as L2A DN with the baseline 04.00+ offset (DN = 10000 r + 1000).

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
import _vegstress_primary_holm_9t as vh

X0, Y0, EXT = 619500.0, 4593000.0, 1300.0
L2A_TAGS = {"BOA_ADD_OFFSET": "-1000", "BOA_QUANTIFICATION_VALUE": "10000", "PROCESSING_BASELINE": "05.11"}


def _tif(path, bands: dict, res, crs="EPSG:6346", tags=None):
    import rasterio
    from rasterio.transform import from_origin
    names = list(bands)
    a = np.stack([bands[n] for n in names]).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[1], width=a.shape[2], count=a.shape[0],
                       dtype="float32", crs=crs, transform=from_origin(X0, Y0 + EXT, res, res), nodata=np.nan) as d:
        d.write(a)
        d.descriptions = tuple(names)
        if tags:
            d.update_tags(**tags)
    return path


def _dn(refl):
    return np.asarray(refl, float) * 10000.0 + 1000.0


def _up(a, f):
    return np.repeat(np.repeat(a, f, axis=0), f, axis=1)


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
    n10 = n1 // 10
    T10 = from_origin(X0, Y0 + EXT, 10, 10)
    padm = rasterize([(g, 1) for g in pads], (n10, n10), transform=T10).astype(bool)
    leakm = rasterize([(g, 1) for g, l in zip(pads, leak) if l], (n10, n10), transform=T10).astype(bool)
    ctlm = rasterize([(g, 1) for g in ctrls], (n10, n10), transform=T10).astype(bool)
    rng = np.random.default_rng(0)
    scenes = []
    for k, (date, season) in enumerate((("2025-06-15", "leaf_on"), ("2025-09-15", "shoulder"), ("2025-03-15", "leaf_off"))):
        red, nir = np.full((n10, n10), 0.05), np.full((n10, n10), 0.40) - 0.1 * (season == "leaf_off")
        red[padm | ctlm], nir[padm | ctlm] = 0.10, 0.30
        nir[padm] = 0.25                                # every pad below every control
        nir[leakm] = 0.20                               # leak pads lower again
        nir += rng.normal(0, 0.005, nir.shape)
        swir20, scl20 = np.full((n10 // 2, n10 // 2), 0.2), np.full((n10 // 2, n10 // 2), 4.0)
        p = _tif(d / f"s{k}.tif", {"green": _up(_dn(red), 2), "red": _up(_dn(red), 2), "nir": _up(_dn(nir), 2),
                                   "swir": _up(_dn(swir20), 4), "scl": _up(scl20, 4)}, 5, tags=L2A_TAGS)
        scenes.append({"scene_id": f"s{k}", "date": date, "season": season, "path": {"abs": str(p)}, "radiometry": None})
    recs = []
    for i in range(100):
        c = pads[i].centroid
        recs.append({"record_id": f"r{i}", "source": "measurement" if i % 2 else "complaint" if leak[i] else "inspection",
                     "date": "2025-05-01", "x": c.x + 20, "y": c.y, "coord_precision_m": 10,
                     "code": "GAS_MIGRATION" if leak[i] else "NO_VIOLATION", "lease_id": f"L{i // 2}",
                     "operator": "op", "permit_num": f"p{i}"})
    for i in range(50, 60):       # old leak reports the 2025 imagery cannot see
        c = pads[i].centroid
        recs.append({"record_id": f"old{i}", "source": "complaint", "date": "2010-05-01", "x": c.x, "y": c.y,
                     "coord_precision_m": 10, "code": "GAS_MIGRATION", "lease_id": f"L{i // 2}", "operator": "op",
                     "permit_num": f"p{i}"})
    pd.DataFrame(recs).to_csv(d / "records.csv", index=False)
    cfg = io.load_config()
    cfg["inputs"].update(pads={"abs": str(d / "pads.gpkg"), "layer": "pad", "id_col": "pad_id"},
                         controls={"abs": str(d / "ctrl.gpkg"), "layer": None, "id_col": "control_id"},
                         chm={"abs": str(d / "chm.tif")}, dem={"abs": str(d / "dem.tif")},
                         dep_wells={"abs": str(d / "wells.gpkg"), "layer": "w"},
                         records={"abs": str(d / "records.csv")}, audit_blocks={"abs": str(d / "no_audit.csv")},
                         folds=None)
    cfg["scenes"], cfg["scene_index"] = scenes, None
    cfg["observability"]["min_scenes_per_season"] = 1
    cfg["matching"].update(caliper_sd=3.0, exact=[])
    cfg["added_value"]["bootstrap_B"] = 200
    cfg["leak_test"].update(bootstrap_B=100, outer_folds=3)
    cfg["labels"].update(codes_status="dep_verified", visible_lookback_days=60)
    return d, cfg


def test_hanley_mcneil_40_vs_40():
    se = io.hanley_mcneil_se(0.70, 40, 40)
    assert se == pytest.approx(0.0585, abs=5e-4)
    assert 0.70 - 1.96 * se > 0.5 and io.min_n_per_class(0.70) <= 40


def test_indices_missing_bands_are_nan():
    ix = io.indices({"red": np.array([0.1]), "nir": np.array([0.3])})
    assert ix["ndvi"][0] == pytest.approx(0.5) and np.isnan(ix["ndre"][0]) and np.isnan(ix["evi"][0])


def test_l2a_radiometry_and_native_grid(world):
    """4.3-01. DN 1500 with offset -1000 and quantification 10000 is reflectance 0.05 (by hand). The 5 m
    stack goes back to a 130 x 130 grid at 10 m and 65 x 65 at 20 m. Raw DN NDVI of forest is
    (5000 - 1500) / 6500 = 0.538, true NDVI is 0.35 / 0.45 = 0.778."""
    d, cfg = world
    grids, crs, info = v2.read_scene(str(d / "s0.tif"), cfg)
    b10, valid10, T10 = grids[10.0]
    assert b10["red"].shape == (130, 130) and T10.a == 10.0 and grids[20.0][0]["swir"].shape == (65, 65)
    assert b10["red"][0, 0] == pytest.approx(0.05) and grids[20.0][0]["swir"][0, 0] == pytest.approx(0.2)
    ndvi = io.indices(b10)["ndvi"][0, 0]
    assert ndvi == pytest.approx(0.35 / 0.45, abs=0.02)
    assert info["radiometry"]["add_offset"] == -1000.0 and info["scl_masked"] is True


def test_radiometry_refusals(world):
    d, cfg = world
    with pytest.raises(RuntimeError, match="no L2A radiometry"):
        io.radiometry({}, None)
    with pytest.raises(RuntimeError, match="carries BOA_ADD_OFFSET"):
        io.radiometry({"BOA_ADD_OFFSET": "0", "BOA_QUANTIFICATION_VALUE": "10000", "PROCESSING_BASELINE": "05.10"}, None)
    r = io.radiometry({}, {"add_offset": -1000, "quantification": 10000, "processing_baseline": "05.10",
                           "offset_removed_upstream": True, "source": "test"})
    assert io.to_reflectance(np.array([500.0]), r)[0] == pytest.approx(0.05)
    # offset applied to DN that already had it removed gives negative reflectance over land, and refuses
    p = _tif(d / "twice.tif", {"red": _up(np.full((10, 10), 300.0), 2), "nir": _up(np.full((10, 10), 3000.0), 2),
                               "scl": np.full((20, 20), 4.0)}, 5, tags=L2A_TAGS)
    with pytest.raises(RuntimeError, match="applied twice"):
        v2.read_scene(str(p), cfg)


def test_sub_native_stack_refuses(world):
    """A 5 m stack whose pixels vary inside a native 10 m pixel is not a copy of native pixels."""
    d, cfg = world
    rng = np.random.default_rng(1)
    p = _tif(d / "fake5m.tif", {"red": _dn(rng.uniform(0.02, 0.1, (40, 40))), "nir": _dn(rng.uniform(0.2, 0.4, (40, 40))),
                                "scl": np.full((40, 40), 4.0)}, 5, tags=L2A_TAGS)
    with pytest.raises(RuntimeError, match="block copy of native pixels"):
        v2.read_scene(str(p), cfg)


def test_scl_masks_water_snow_and_missing_refuses(world):
    d, cfg = world
    c2 = json.loads(json.dumps(cfg))
    c2["scl_valid"] = [4, 5, 6, 11]
    with pytest.raises(ValueError, match="forbidden SCL classes"):
        v2.read_scene(str(d / "s0.tif"), c2)
    scl = np.full((20, 20), 4.0)
    scl[:4, :4] = 6.0                                   # one 20 m water pixel
    p = _tif(d / "water.tif", {"red": _up(_dn(np.full((10, 10), 0.05)), 2), "nir": _up(_dn(np.full((10, 10), 0.4)), 2),
                               "swir": _up(_dn(np.full((5, 5), 0.2)), 4), "scl": scl}, 5, tags=L2A_TAGS)
    grids, _, _ = v2.read_scene(str(p), cfg)
    assert grids[20.0][1].sum() == 24 and not grids[20.0][1][0, 0]
    assert grids[10.0][1].sum() == 96 and not grids[10.0][1][:2, :2].any()
    p = _tif(d / "noscl.tif", {"red": _up(_dn(np.full((10, 10), 0.05)), 2), "nir": _up(_dn(np.full((10, 10), 0.4)), 2)},
             5, tags=L2A_TAGS)
    with pytest.raises(RuntimeError, match="no SCL band"):
        v2.read_scene(str(p), cfg)
    c3 = json.loads(json.dumps(cfg))
    c3["extract"]["allow_unmasked"] = True
    assert v2.read_scene(str(p), c3)[2]["scl_masked"] is False


def test_label_gate_date_filter_and_placeholder_codes(world, tmp_path):
    """4.3-03. Ten 2010 leak reports on pads 50 to 59 fall outside the visible window (2025-01-14 to
    2025-09-15), so leak stays 50, not 60. Placeholder codes refuse instead of closing Question B."""
    d, cfg = world
    lab = v0.run(cfg, out_root=tmp_path)
    assert lab["counts"]["leak"]["n"] == 50 and lab["counts"]["nonleak"]["n"] == 50
    assert lab["visible_window"] == {"from": "2025-01-14", "to": "2025-09-15", "lookback_days": 60}
    assert lab["n_records_in_years"] == 110 and lab["n_records_in_window"] == 100
    c2 = json.loads(json.dumps(cfg))
    c2["labels"]["codes_status"] = "placeholder"
    with pytest.raises(RuntimeError, match="placeholders"):
        v0.run(c2, out_root=tmp_path)
    c3 = json.loads(json.dumps(cfg))
    c3["labels"]["visible_lookback_days"] = None
    with pytest.raises(RuntimeError, match="visible_lookback_days"):
        v0.run(c3, out_root=tmp_path)


def test_chain(world):
    d, cfg = world
    res = d / "res"
    o = v1.run(cfg, out_root=res)
    # 30 m pads on a 10 m grid. Columns and rows alternate 3 and 2 whole pixels, so 9, 6, 6, 4. Median 6
    assert o["per_pixel_size"]["10m"]["median_open_interior_px"] == 6.0
    assert o["per_pixel_size"]["10m"]["verdict"] == "success"
    assert o["per_pixel_size"]["30m"]["verdict"] == "failure"
    lab = v0.run(cfg, out_root=res)
    assert lab["verdict"] == "success" and lab["counts"]["leak"]["n"] == 50
    m = vm.run(cfg, out_root=res, allow_no_audit=True)
    assert m["n_pairs"] >= 90 and m["index_read"] is False and m["exploratory"] is True
    assert m["n_population"] == 200
    sites = Path(m["run_dir"]) / "vegstress_matched_sites_9t.gpkg"
    e = v2.run(cfg, out_root=res, sites_path=sites, layer="population")
    assert e["n_rows"] == e["n_sites"] * 3 and e["n_sites"] == 200 and "ndre" in e["indices_all_nan"]
    assert e["scenes_unmasked"] == []
    by_site = Path(e["run_dir"]) / "vegstress_by_site_9t.csv"
    a = v3.run(cfg, out_root=res, sites_path=sites, by_site_path=by_site, fallback_folds=3)
    # Lidar features are equal for pads and controls, so lidar alone is chance (AUC 0.5). Every pad has lower
    # NDVI than every control, so lidar plus index puts all 100 pads first. K = 40 x 16 blocks x 0.140625 km2
    # = 90, so recall at K is 90 / 100 = 0.90 (by hand)
    assert a["stage"] == "V3" and a["identifiable"] is True and a["k_total"] == pytest.approx(90.0)
    assert a["recall_at_k"]["undefined_share"] == 0.0
    assert a["recall_at_k"]["lidar_plus"] == pytest.approx(0.90) and a["auc"]["lidar_only"] == pytest.approx(0.5)
    assert a["verdict_unadjusted"] == "success" and a["delta_gain"] == 0.03
    e2 = v2.run(cfg, out_root=res / "pads", pads_only=True)
    t = v4.run(cfg, out_root=res, labels_dir=Path(lab["run_dir"]), by_site_path=Path(e2["run_dir"]) / "vegstress_by_site_9t.csv")
    assert t["results"]["all"]["status"] == "ok"
    assert t["results"]["all"]["auc_cov_stress"] > 0.9
    assert "undefined_share" in t["results"]["all"]
    assert t["results"]["all"]["primary"] is True
    # Holm over primary A (V3) and primary B (V4 all labels), read from the real stage outputs
    h = vh.run(cfg, out_root=res, v3=Path(a["run_dir"]) / "vegstress_added_value_9t.json",
               v4=Path(t["run_dir"]) / "vegstress_leak_test_9t.json")
    ps = {"V3": a["recall_at_k"]["p_success"], "V4:all": t["results"]["all"]["p_success"]}
    lo, hi = sorted(ps, key=ps.get)
    want_lo = min(1.0, 2 * ps[lo])                       # Holm by hand, m = 2
    assert h["m"] == 2 and h["gates"][lo]["holm_p_success"] == pytest.approx(want_lo)
    assert h["gates"][hi]["holm_p_success"] == pytest.approx(max(want_lo, ps[hi]))
    # Every pad ranks above every control with the index, so every recall draw is 0.90 or more and
    # p_success for V3 is 0 (by construction). Holm keeps it 0, so V3 passes after adjustment
    assert ps["V3"] == 0.0 and h["gates"]["V3"]["verdict"] == "success"


def test_v3_matched_layer_not_identifiable(world):
    """4.3-02. On the matched layer lidar is uninformative by construction, so no verdict is given."""
    d, cfg = world
    res = d / "res_m"
    m = vm.run(cfg, out_root=res, allow_no_audit=True)
    sites = Path(m["run_dir"]) / "vegstress_matched_sites_9t.gpkg"
    e = v2.run(cfg, out_root=res, sites_path=sites)
    a = v3.run(cfg, out_root=res, sites_path=sites, by_site_path=Path(e["run_dir"]) / "vegstress_by_site_9t.csv",
               fallback_folds=3, layer="sites")
    assert a["verdict_unadjusted"] == "not_identifiable" and a["identifiable"] is False
    h = vh.run(cfg, out_root=res, v3=Path(a["run_dir"]) / "vegstress_added_value_9t.json", v4=res / "none.json")
    assert h["gates"]["V3"]["status"] == "not identifiable" and h["gates"]["V3"]["verdict"] == "inconclusive"
    assert h["gates"]["V4:all"]["status"] == "not run" and h["m"] == 2


def test_match_refuses_missing_audit(world, tmp_path):
    """P2-01. A missing audit file is never read as an empty set."""
    d, cfg = world
    with pytest.raises(FileNotFoundError, match="audit set not frozen"):
        vm.run(cfg, out_root=tmp_path)


def test_leak_test_refuses_without_gate(world, tmp_path):
    d, cfg = world
    (tmp_path / "vegstress_label_counts_9t.json").write_text(json.dumps({"verdict": "failure"}))
    with pytest.raises(RuntimeError, match="not success"):
        v4.run(cfg, out_root=tmp_path, labels_dir=tmp_path)


def test_config_defaults_2026_11_06(world, tmp_path):
    """Defaults accepted 2026-11-06. Lookback 365 days, gain 0.03 recall, no undefined draws, September
    stays shoulder, Holm over V3 and V4 all labels. With 365 days the window opens 2024-03-15 (first scene
    2025-03-15 minus 365 days, no 29 February between, by hand). The ten 2010 reports stay outside, so leak stays 50."""
    c = io.load_config()
    assert c["labels"]["visible_lookback_days"] == 365
    assert c["added_value"]["delta_gain"] == 0.03
    assert c["added_value"]["max_undefined"] == 0.0 and c["leak_test"]["max_undefined"] == 0.0
    assert [s["season"] for s in c["scenes"] if s["scene_id"] == "s2_sep_9t"] == ["shoulder"]
    assert c["primary_gate"]["primaries"] == ["V3", "V4:all"]
    d, cfg = world
    c2 = json.loads(json.dumps(cfg))
    c2["labels"]["visible_lookback_days"] = c["labels"]["visible_lookback_days"]
    lab = v0.run(c2, out_root=tmp_path)
    assert lab["visible_window"] == {"from": "2024-03-15", "to": "2025-09-15", "lookback_days": 365}
    assert lab["counts"]["leak"]["n"] == 50
