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
import _thermal_primary_holm_9t as th

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
    rows, ties = [], []
    for k in range(6):
        lst = 290 + k + rng.normal(0, 0.2, (m, m)) - 2.0
        lst[cl10] = 290 + k
        lst[pad10] = 293 + k
        qa = np.full((m, m), 64.0)                  # QA_PIXEL bit 6 clear sky
        if k == 1:
            qa[:] = 64 + 8                          # scene s1 fully cloud (bit 3)
        p = _tif(d / f"scene{k}.tif", np.stack([lst, qa]), 10)
        rows.append({"scene_id": f"s{k}", "sensor": "landsat_tirs", "datetime_utc": f"2024-0{k + 3}-15T15:20:00",
                     "path": p.name, "cloud_frac": 0.0, "qc_pass": True, "lst_err_K": 1.0})
        off = 80.0 if k == 5 else 3.0               # s5 misregistered beyond 0.5 x 100 m
        ties += [{"scene_id": f"s{k}", "dx_m": off, "dy_m": 0.0}, {"scene_id": f"s{k}", "dx_m": -off, "dy_m": 0.0}]
    pd.DataFrame(rows).to_csv(d / "scenes.csv", index=False)
    pd.DataFrame(ties).to_csv(d / "ties.csv", index=False)
    bl = [box(X0 + ix * 375, Y0 + iy * 375, X0 + (ix + 1) * 375, Y0 + (iy + 1) * 375) for iy in range(4) for ix in range(4)]
    gpd.GeoDataFrame({"block_id": [iy * 12 + ix for iy in range(4) for ix in range(4)],
                      "ix": [ix for iy in range(4) for ix in range(4)], "iy": [iy for iy in range(4) for ix in range(4)]},
                     geometry=bl, crs=6346).to_file(d / "blocks.gpkg", layer="blocks")
    pd.DataFrame({"date": pd.date_range("2024-01-01", "2024-12-31").strftime("%Y-%m-%d"), "ppt": 1.0,
                  "tmin": 0, "tmax": 10}).to_csv(d / "prism.csv", index=False)
    pd.DataFrame({"date": ["2024-03-01", "2024-07-01"], "leaf_state": ["leaf_off", "leaf_on"]}).to_csv(d / "leaf.csv", index=False)
    cfg = io.load_config()
    cfg["inputs"].update(pads={"abs": str(d / "pads.gpkg"), "layer": "pad", "id_col": "pad_id"},
                         clearings={"abs": str(d / "clear.gpkg"), "layer": None, "id_col": "clearing_id"},
                         chm={"abs": str(d / "chm.tif")}, dem={"abs": str(d / "dem.tif")},
                         nlcd={"abs": str(d / "none.tif")}, prism={"abs": str(d / "prism.csv")},
                         leaf_state={"abs": str(d / "leaf.csv")}, audit_blocks={"abs": str(d / "no_audit.csv")},
                         blocks={"abs": str(d / "blocks.gpkg")}, folds=None)
    cfg["sensors"] = [dict(cfg["sensors"][0], lst_scale=1.0, lst_offset=0.0, err_band=None,
                           scene_index={"abs": str(d / "scenes.csv")}, tiepoints={"abs": str(d / "ties.csv")})]
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


world_cache: dict = {}


def _chain(world):
    d, cfg = world
    if "chain" not in world_cache:
        g = t1.run(cfg, out_root=d / "res")
        m = tm.run(cfg, out_root=d / "res", allow_no_audit=True)
        sites = Path(m["run_dir"]) / "thermal_matched_sites_9t.gpkg"
        gp = Path(g["run_dir"]) / "thermal_gate_summary_9t.json"
        s = t2.run(cfg, "landsat_tirs", out_root=d / "res", sites_path=sites, gate_path=gp)
        sp = t2.run(cfg, "landsat_tirs", out_root=d / "res" / "pop", sites_path=sites, gate_path=gp, layer="population")
        world_cache["chain"] = (g, m, sites, gp, s, sp)
    return world_cache["chain"]


def test_chain(world):
    d, cfg = world
    g, m, sites, gp, s, sp = _chain(world)
    assert g["t0"]["verdict"] == "success"
    assert g["sensors"]["landsat_tirs"]["scenes"]["usable"] == 6
    assert m["n_pairs"] >= 20 and m["lst_read"] is False
    assert m["exploratory"] is True and m["audit"]["audit"] == "no audit exclusion, exploratory"
    assert s["n_scenes"] == 5 and s["n_rows"] == s["n_sites"] * 5
    samples = Path(s["run_dir"]) / "thermal_samples_by_scene_9t.csv"
    c = t3.run(cfg, out_root=d / "res", samples_path=samples)
    assert c["signed_contrast_K"] > 1.0          # injected +3 K at the pixel, diluted by partial pixels
    assert c["undefined_share"] == 0.0
    pop_samples = Path(sp["run_dir"]) / "thermal_samples_by_scene_9t.csv"
    a = t4.run(cfg, out_root=d / "res", sites_path=sites, samples_path=pop_samples, fallback_folds=3)
    assert a["identifiable"] is True and a["layer"] == "population"
    assert a["n_sites"] == 48                     # 24 pads + 24 clearings, none matched away
    assert a["auc"]["lidar_plus"] >= a["auc"]["lidar_only"] - 1e-9
    assert "undefined_share" in a["recall_at_k"] and "undefined_share" in a["auc"]
    assert json.loads((Path(a["run_dir"]) / "thermal_added_value_9t.json").read_text())["stage"] == "T4"
    # Holm gate over the two primaries, read from the stage outputs the real scripts wrote
    assert a["delta_gain"] == 0.03 and a["recall_at_k"]["margin"] == 0.03
    h = th.run(cfg, out_root=d / "res", t3=Path(c["run_dir"]) / "thermal_contrast_summary_9t.json",
               t4=Path(a["run_dir"]) / "thermal_added_value_9t.json")
    ps = {"T3": c["p_success"], "T4": a["recall_at_k"]["p_success"]}
    lo, hi = sorted(ps, key=ps.get)
    want_lo = min(1.0, 2 * ps[lo])                       # Holm by hand, m = 2
    want_hi = max(want_lo, ps[hi])
    assert h["m"] == 2
    assert h["gates"][lo]["holm_p_success"] == pytest.approx(want_lo)
    assert h["gates"][hi]["holm_p_success"] == pytest.approx(want_hi)
    for k in ("T3", "T4"):
        hp = h["gates"][k]
        want = "success" if hp["holm_p_success"] < 0.025 else "failure" if hp["holm_p_failure"] < 0.025 else "inconclusive"
        assert hp["verdict"] == want and hp["status"] == "ok"


def test_t4_matched_layer_not_identifiable(world):
    """4.2-01. On the caliper-matched layer the verdict is not_identifiable whatever the numbers."""
    d, cfg = world
    g, m, sites, gp, s, sp = _chain(world)
    samples = Path(s["run_dir"]) / "thermal_samples_by_scene_9t.csv"
    a = t4.run(cfg, out_root=d / "res", sites_path=sites, samples_path=samples, fallback_folds=3, layer="sites")
    assert a["verdict_unadjusted"] == "not_identifiable" and a["identifiable"] is False


def test_registration_gate(world):
    """4.2-02. s5 has 80 m tie-point error (limit 0.5 x 100 m = 50 m). T1 lists it and T2 drops it.
    A sensor without tie points cannot pass T1 even with a huge contrast, and T2 refuses it."""
    d, cfg = world
    g, m, sites, gp, s, sp = _chain(world)
    reg = g["sensors"]["landsat_tirs"]["registration"]
    assert reg["scenes_over_limit"] == ["s5"] and reg["qc_pass"] is True and reg["rmse_m_median"] == pytest.approx(3.0)
    assert s["n_scenes_dropped_registration"] == 1 and s["n_scenes"] == 5
    c2 = json.loads(json.dumps(cfg))
    c2["sensors"][0]["tiepoints"] = {"abs": str(d / "none.csv")}
    c2["gate"]["min_usable_scenes"] = 1
    g2 = t1.run(c2, out_root=d / "res_reg", proxy_dT=1000.0)
    v = g2["sensors"]["landsat_tirs"]
    assert v["lo"] > c2["gate"]["delta_T_K"] and v["contrast_to_spread"] >= 1
    assert v["verdict"] == "inconclusive" and v["registration_qc"]["pass"] is False
    with pytest.raises(RuntimeError, match="no registration check"):
        t2.run(c2, "landsat_tirs", out_root=d / "res_reg", sites_path=sites,
               gate_path=Path(g2["run_dir"]) / "thermal_gate_summary_9t.json")


def test_cloud_qa_masks_and_refuses(world):
    """F-note. Scene s1 is flagged cloud in every pixel, so no site has LST there. A sensor without a QA
    band refuses. A wrong scale (100 x) is caught by the plausibility check."""
    d, cfg = world
    g, m, sites, gp, s, sp = _chain(world)
    smp = pd.read_csv(Path(s["run_dir"]) / "thermal_samples_by_scene_9t.csv")
    assert smp.loc[smp.scene_id == "s1", "lst_K"].isna().all()
    assert smp.loc[smp.scene_id == "s0", "lst_K"].notna().any()
    assert s["qa_masked_share_by_scene"]["s1"] == 1.0 and s["qa_masked_share_by_scene"]["s0"] == 0.0
    c2 = json.loads(json.dumps(cfg))
    c2["sensors"][0]["qa_band"] = None
    with pytest.raises(RuntimeError, match="no per-pixel cloud QA band"):
        t2.run(c2, "landsat_tirs", out_root=d / "res_qa", sites_path=sites, gate_path=gp)
    c3 = json.loads(json.dumps(cfg))
    c3["sensors"][0]["lst_scale"] = 100.0
    with pytest.raises(RuntimeError, match="Check the sensor scaling"):
        t2.run(c3, "landsat_tirs", out_root=d / "res_qa", sites_path=sites, gate_path=gp)


def test_audit_read_through_p2_writer(world):
    """P2-01. The audit CSV from the real P2 writer (# header, sha256 sidecar) is read, and pads in the
    audit block are dropped. P2 block 0 is 0_0 and holds pads 0 and 1 (counted by hand)."""
    import sys as _s
    _s.path.insert(0, str(Path(io.__file__).resolve().parents[3] / "0_prerequisites" / "p2_audit_set" / "src"))
    import _audit_draw_blocks_9t as dr
    import _audit_guard_lib as ag
    d, cfg = world
    ap = d / "audit_blocks_9t_v1.csv"
    dr.write_audit_csv(ap, pd.DataFrame({"block_id": [0], "dens_t": [1], "slope_t": [1]}),
                       {"audit": [0], "buffer": [], "share": 0.1}, "window", 100.0, 1)
    Path(str(ap) + ".sha256").write_text(ag._sha(ap.read_bytes()) + "  audit_blocks_9t_v1.csv\n")
    c2 = json.loads(json.dumps(cfg))
    c2["inputs"]["audit_blocks"] = {"abs": str(ap)}
    r = tm.run(c2, out_root=d / "res_audit")
    assert r["n_audit_blocks_excluded"] == 1 and r["n_pads_in"] == 22 and r["exploratory"] is False
    import geopandas as gpd
    pop = gpd.read_file(Path(r["run_dir"]) / "thermal_matched_sites_9t.gpkg", layer="population")
    assert "0_0" not in set(pop.loc[pop.site_class == "pad", "block_id"])
    with pytest.raises(FileNotFoundError, match="audit set not frozen"):
        tm.run(cfg, out_root=d / "res_audit")           # a missing file never becomes an empty set


def test_latest_run_by_recorded_time(tmp_path):
    """4.2-03. The later run has the hash that sorts first. latest_run must return it."""
    for name, when in (("20261105_x_fff0000", "2026-11-05T09:00:00"), ("20261105_x_aaa0000", "2026-11-05T10:00:00")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "_PROVENANCE.json").write_text(json.dumps({"written": when}))
    (tmp_path / "20261105_x_zzz0000").mkdir()             # unfinished, no provenance
    assert io.latest_run("4.2", "x", base=tmp_path).name == "20261105_x_aaa0000"


def test_added_value_counts_undefined_draws():
    """SH-01. 6 blocks, positives in 2. A paired resample misses both with probability (4/6)^6 = 0.088.
    Those draws are undefined, so the interval is NaN, the share is reported and the verdict is inconclusive."""
    rng = np.random.default_rng(3)
    rows = []
    for b in range(6):
        for i in range(20):
            y = int(b < 2 and i < 10)
            rows.append({"block": f"{b}_0", "fold": b, "y": y, "x1": rng.normal(y, 1), "x2": rng.normal(y, 1)})
    df = pd.DataFrame(rows)
    area = {f"{b}_0": 0.140625 for b in range(6)}
    r = io.added_value(df, ["x1"], ["x2"], "y", "fold", "block", area, 40.0, B=2000, seed=1)
    for k in ("recall_at_k", "auc"):
        assert r[k]["undefined_share"] == pytest.approx((4 / 6) ** 6, abs=0.02)
        assert np.isnan(r[k]["lo"]) and np.isnan(r[k]["hi"])
    assert io.ek.decide(r["recall_at_k"]["lo"], r["recall_at_k"]["hi"], 0.05, "superiority") == "inconclusive"


def test_missing_input_message(world):
    d, cfg = world
    with pytest.raises(FileNotFoundError, match="MISSING INPUT"):
        tm.run(cfg, out_root=d / "res", clearings_path=d / "nope.gpkg", allow_no_audit=True)


def test_config_defaults_2026_11_06():
    """Defaults accepted 2026-11-06. Useful gain 0.03 recall, no undefined draws, Holm over T3 and T4."""
    cfg = io.load_config()
    assert cfg["added_value"]["delta_gain"] == 0.03
    assert cfg["added_value"]["max_undefined"] == 0.0 and cfg["gate"]["max_undefined"] == 0.0
    assert cfg["primary_gate"]["primaries"] == ["T3", "T4"] and cfg["primary_gate"]["method"] == "holm"


def test_one_sided_shares_match_decide():
    """lo > margin on the 95% interval is p_success < 0.025. 1000 draws 0.001 to 1.000, margin 0.0205.
    20 draws are at or below it, so p_success 0.020 (by hand) and the stage verdict is success."""
    d = np.arange(1, 1001) / 1000.0
    s = io.one_sided_shares(d, 0.0205)
    assert s["p_success"] == pytest.approx(0.020) and s["p_failure"] == pytest.approx(0.980)
    lo, hi = np.percentile(d, [2.5, 97.5])
    assert io.ek.decide(lo, hi, 0.0205, "superiority") == "success"
    d2 = d.copy()
    d2[0] = np.nan                                       # one undefined draw, max_undefined 0
    assert np.isnan(io.one_sided_shares(d2, 0.0205)["p_success"])


def test_holm_gate_by_hand():
    """Both primaries pass unadjusted (0.020 and 0.015 under 0.025). Holm m = 2 gives 0.030 and 0.030,
    so both are inconclusive after adjustment. A missing primary counts as p 1 and keeps m = 2."""
    g = io.holm_gate({"T3": {"p_success": 0.020, "p_failure": 0.98}, "T4": {"p_success": 0.015, "p_failure": 0.985}})
    assert g["gates"]["T4"]["holm_p_success"] == pytest.approx(0.030)
    assert g["gates"]["T3"]["holm_p_success"] == pytest.approx(0.030)
    assert g["gates"]["T3"]["verdict"] == "inconclusive" and g["gates"]["T4"]["verdict"] == "inconclusive"
    g2 = io.holm_gate({"T3": {"p_success": 0.010, "p_failure": 0.99}, "T4": None})
    assert g2["m"] == 2 and g2["gates"]["T3"]["holm_p_success"] == pytest.approx(0.020)
    assert g2["gates"]["T3"]["verdict"] == "success" and g2["gates"]["T4"]["verdict"] == "inconclusive"
    g3 = io.holm_gate({"T3": {"p_success": 0.99, "p_failure": 0.004}, "T4": {"p_success": 0.5, "p_failure": 0.5}})
    assert g3["gates"]["T3"]["verdict"] == "failure" and g3["gates"]["T3"]["holm_p_failure"] == pytest.approx(0.008)
