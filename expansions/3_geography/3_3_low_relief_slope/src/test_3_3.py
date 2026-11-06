"""Smoke tests for 3.3 on tiny synthetic data (seconds, no GPU, no network).

Run
    python -m pytest -q expansions/3_geography/3_3_low_relief_slope/src/test_3_3.py -p no:cacheprovider
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "3_1_warren_forest_mckean" / "src"))

import _slope_recall_tercile_9t as s1  # noqa: E402
import _slope_confound_logit_9t as s2  # noqa: E402
import _slope_terrain_edit_9t as s3  # noqa: E402
import _slope_edit_seam_check_9t as s4  # noqa: E402
import _slope_area_gate_9t as s5  # noqa: E402
import _geo_xfer_lib as xl  # noqa: E402


def _synthetic_features(n_blocks=30, per=6, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_blocks):
        for j in range(per):
            s = rng.uniform(0, 20)
            rows.append({"truth_id": b * 100 + j, "block_id": b, "slope_25m": s, "relief_50m": s * 0.8 + rng.normal(),
                         "area_m2": rng.uniform(5, 60), "depth_m": rng.uniform(0.2, 1.5), "void_frac": rng.uniform(0, 0.6),
                         "found": bool(rng.random() < (0.95 if s < 10 else 0.7))})
    f = pd.DataFrame(rows)
    f["slope_tercile"], _ = xl.terciles(f.slope_25m)
    f["relief_tercile"], _ = xl.terciles(f.relief_50m)
    blk = f.groupby("block_id").agg(hits=("found", "sum"), n_truth=("found", "size"),
                                    slope_mean=("slope_25m", "mean"), relief_mean=("relief_50m", "mean")).reset_index()
    blk["slope_tercile"], _ = xl.terciles(blk.slope_mean)
    blk["relief_tercile"], _ = xl.terciles(blk.relief_mean)
    return f, blk


def test_tercile_table_shapes_and_direction():
    f, blk = _synthetic_features()
    tab, diffs = s1.tercile_table(f, blk, B=200, seed=3)
    assert len(tab) == 12
    d = diffs["feature_slope_tercile_low_minus_high"]
    assert d["lo"] <= d["diff"] <= d["hi"]
    assert d["diff"] > 0          # synthetic truth: low slope is found more often
    assert tab.n_features[tab.level == "feature"].sum() == 2 * len(f)


def test_terrain_helpers():
    dem = np.add.outer(np.arange(50) * 0.1, np.arange(50) * 0.05)
    r = s1.local_relief(dem, 5)
    assert np.isclose(np.nanmax(r), 0.4 + 0.2, atol=1e-6)
    m = s1.nan_uniform(np.where(np.eye(50, dtype=bool), np.nan, 1.0), 3)
    assert np.allclose(m[np.isfinite(m)], 1.0)


def test_confound_logit_runs():
    f, _ = _synthetic_features()
    by, coef, meta = s2.confound_tables(f, B=30, seed=1)
    assert list(coef.term) == ["intercept"] + s2.COVS
    assert coef.loc[coef.term == "slope_25m", "coef_per_sd"].iloc[0] < 0
    assert meta["n_used"] == len(f)


def _plane_with_pit(n=200, res=0.5, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n]
    z = 300 + 0.02 * xx + 0.01 * yy + rng.normal(0, 0.01, (n, n))
    rr = np.hypot(yy - n / 2, xx - n / 2)
    z = z - 0.6 * np.clip(1 - (rr / 12) ** 2, 0, 1)
    return z.astype(np.float32), rr <= 14


def test_donor_and_variants_and_channel_locality():
    donor, rim = _plane_with_pit(60)
    res, w, amp = s3.donor_residual(donor, rim, feather_px=3)
    assert 0.5 < amp < 0.75
    target = (200 + 0.01 * np.add.outer(np.arange(240), np.arange(240))).astype(np.float32)
    var, foot, touched = s3.make_variants(target, res, w, amp, np.random.default_rng(0))
    assert set(var) == set(s3.VARIANTS)
    assert np.array_equal(var["background"], target)
    assert (var["pit"][foot] < target[foot]).mean() > 0.5
    for k in ("bump", "ramp", "flat_cut", "pit"):
        assert np.array_equal(var[k][~touched], target[~touched])
    ch_b = s3.channels_from_dem(var["background"])
    ch_p = s3.channels_from_dem(var["pit"])
    assert ch_b.shape == (7, 240, 240)
    assert s3.outside_diff(ch_p, ch_b, touched) <= 1e-3
    st = s3.seam_stats(var["pit"], var["background"], foot, touched)
    assert np.isfinite(st["ratio_inside_outside"])


def test_pick_locations_respects_slope_and_spacing():
    from rasterio.transform import from_origin
    from shapely.geometry import box
    slope = np.full((100, 100), 2.0)
    slope[:, 50:] = 20.0
    tf = from_origin(0, 100, 1, 1)
    pts, _ = s3.pick_locations(10, np.random.default_rng(0), slope, tf, 5.0, box(0, 0, 10, 10), None,
                               (0, 0, 100, 100), 5, 8)
    assert len(pts) == 10
    assert all(x < 50 for x, _ in pts)
    assert all(not (x < 10 and y < 10) for x, y in pts)


def test_seam_flags_and_gate():
    locs = pd.DataFrame([{"loc_id": 0, "outside_diff_ok": True, **{f"{v}_ratio_inside_outside": r for v, r in
                                                                     zip(s4.EDITS, (1.1, 3.0, 0.9, 1.0))}}])
    fl = s4.seam_flags(locs, "inside_outside", 0.2)
    assert fl["pass"].tolist() == [True, False, True, True]
    summ = {"primary": {"diff": -0.2, "lo": -0.3, "hi": -0.1}, "cut_points": {"feature_slope_deg": [7.0, 10.0]},
            "n_features": 10}
    g = s5.gate(summ, 0.05, False, n_flat=0)
    assert g["s1_decision"] == "failure" and g["release_area_test"]
    with pytest.raises(ValueError, match="margin is required"):
        s5.gate(summ, None, False, n_flat=0)
    # take defaults 2026-11-06. Margin 0.03. S1's Holm decision is used when the margins agree
    summ2 = {"primary": {"diff": -0.012, "lo": -0.063, "hi": 0.038, "margin": 0.03, "decision": "inconclusive",
                         "decision_basis": "interval spans the bound"},
             "cut_points": {"feature_slope_deg": [7.0, 10.0]}, "n_features": 10}
    g3 = s5.gate(summ2, 0.03, False, n_flat=0)
    assert g3["s1_decision"] == "inconclusive" and not g3["release_area_test"]
    assert g3["s1_decision_basis"] == "interval spans the bound"


def test_defaults_margin_family_footprint():
    cfg = json.loads((HERE.parent / "config_3_3.json").read_text(encoding="utf-8"))
    assert cfg["margin_delta"] == 0.03 and cfg["footprint_rule"] == "all_blocks"
    m = cfg["multiplicity"]
    assert m["method"] == "holm" and m["family"] == ["q1_slope_feature"] and m["max_undefined"] == 0.0


def test_s1_primary_holm_gate_exact():
    """Hand oracle. 10 draws, 1 at or below -0.03, share 0.1 -> not under 0.025, CI spans -> inconclusive.
    0 draws below -> share 0 -> success."""
    import _geo_xfer_lib as xl
    d = np.array([-0.05, -0.02, -0.01, 0, 0, 0.01, 0.01, 0.02, 0.02, 0.03])
    h = xl.hg.holm_input("q1_slope_feature", d, -0.045, 0.03, 0.03, "noninferiority", ["q1_slope_feature"])
    assert h["p_one_sided"] == pytest.approx(0.1) and h["decision_partial"] == "inconclusive"
    h = xl.hg.holm_input("q1_slope_feature", d[1:], -0.02, 0.03, 0.03, "noninferiority", ["q1_slope_feature"])
    assert h["p_one_sided"] == 0.0 and h["decision_partial"] == "success"


# ----------------------------------------------------------------------------- review 2026-11-06 regressions
def test_g12_donors_held_out_from_scoring_fold():
    """G-12. A location scored by fold k takes donors only from fold-k held-out pits."""
    import geopandas as gpd
    from shapely.geometry import box
    rims = gpd.GeoDataFrame({"pit_inside_id": [1, 2, 3, 4, 5]}, geometry=[box(i, 0, i + 1, 1) for i in range(5)],
                            crs="EPSG:6346")
    pit_fold = {1: 0, 2: 1, 3: 0, 4: 2}                                       # pit 5 has no fold
    pools = s3.donor_pools(rims, pit_fold, seed=7)
    assert sorted(pools) == [0, 1, 2]
    assert sorted(pools[0].pit_inside_id) == [1, 3] and list(pools[1].pit_inside_id) == [2]
    assert all(pit_fold[int(i)] == f for f, g in pools.items() for i in g.pit_inside_id)


def test_p2_01_audit_read_through_real_writer(tmp_path):
    """P2-01. The P2 writer's CSV (with # header lines) is read through ek.require_audit. A plain read_csv
    raised ParserError. A missing file raises unless the flag is set, and then the output is labelled."""
    import geopandas as gpd
    from shapely.geometry import box
    sys.path.insert(0, str(xl.ek.EXP_ROOT / "0_prerequisites" / "p2_audit_set" / "src"))
    import _audit_draw_blocks_9t as dr
    tab = pd.DataFrame({"block_id": [1, 2, 3], "dens_t": [0, 1, 2], "slope_t": [0, 1, 2]})
    p = tmp_path / "audit_blocks_9t_v1.csv"
    dr.write_audit_csv(p, tab, {"audit": [1, 3], "buffer": [2], "share": 0.15}, "block", 100.0, 20261104)
    with pytest.raises(Exception):
        pd.read_csv(p).block_id                                                # the pre-fix reader
    blocks = gpd.GeoDataFrame({"block_id": [1, 2, 3, 4]}, geometry=[box(i, 0, i + 1, 1) for i in range(4)],
                              crs="EPSG:6346")
    g, prov, label = s3.read_audit_geom({"spec": {"abs": str(p)}}, False, blocks, allow_unfrozen=True)
    assert prov is False and g.area == pytest.approx(3.0) and "(3)" in label    # audit 1, 3 and buffer 2
    with pytest.raises(FileNotFoundError):
        s3.read_audit_geom({"spec": {"abs": str(tmp_path / "missing.csv")}}, False, blocks)
    g2, prov2, label2 = s3.read_audit_geom({"spec": {"abs": str(tmp_path / "missing.csv")}}, True, blocks)
    assert g2 is None and prov2 is True and "exploratory" in label2


def test_p1_03_terrain_edit_buffer_reader(tmp_path):
    """P1-03. The P1 writer's buffer JSON is read with ek.read_buffer. The pre-fix code indexed pit_buffer_m."""
    import importlib
    sys.path.insert(0, str(xl.ek.EXP_ROOT / "0_prerequisites" / "p1_splits_manifests" / "src"))
    bd = importlib.import_module("_split_buffer_derive_9t")
    p = bd.write_buffer_json(bd.assemble({"pit": {"buffer_m": 75.0}}), tmp_path / "b.json")
    assert s3.read_buffer_or_fallback({"spec": {"abs": str(p)}}, False, 128.0) == (75.0, False)
    assert s3.read_buffer_or_fallback({"spec": {"abs": str(tmp_path / "no.json")}}, True, 128.0) == (128.0, True)


def test_area_gate_commands_name_a_real_area():
    """Minor. The gate's commands use an area that config_3_1.json defines."""
    cmds = s5.gate_commands("il_cumberland")
    cfg31 = xl.load_config(HERE.parents[2] / "3_1_warren_forest_mckean" / "src" / "config_3_1.json")
    xl.area_ctx(cfg31, "il_cumberland", mkdirs=False)
    assert all("--area il_cumberland" in c for c in cmds)
    with pytest.raises(KeyError):
        s5.gate_commands("nowhere")


def test_f03_s1_fold_reader_has_no_seam_duplicates(tmp_path):
    """F03 in 3.3 S1. A 100 x 20 m blob across two held-out blocks gives one 2,000 m2 candidate.
    The old blockwise reader (kept for this test) gives two clipped 1,800 m2 copies."""
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    X0, Y0 = 600000.0, 4600000.0
    p = np.zeros((200, 400), np.float32)
    p[80:120, 100:300] = 0.8                                                   # x 50-150, y 40-60
    tf = from_origin(X0, Y0 + 100, 0.5, 0.5)
    path = tmp_path / "f.tif"
    with rasterio.open(path, "w", driver="GTiff", height=200, width=400, count=1, dtype="float32", crs="EPSG:6346",
                       transform=tf, nodata=-1.0) as d:
        d.write(p, 1)
    hb = gpd.GeoDataFrame({"block_id": [0, 1]}, geometry=[box(X0, Y0, X0 + 100, Y0 + 100), box(X0 + 100, Y0, X0 + 200, Y0 + 100)],
                          crs="EPSG:6346")
    new = s1.fold_candidates(path, hb, 40.0, xl.policy("pit"))
    assert len(new) == 1 and new.geometry.area.iloc[0] == pytest.approx(2000.0)
    old = s1.fold_candidates_blockwise_old(path, hb, 40.0, 0.35, 4.0)
    assert len(old) == 2 and sorted(old.geometry.area.round(1)) == [1800.0, 1800.0]
