"""Smoke tests for 3.3 on tiny synthetic data (seconds, no GPU, no network).

Run
    python -m pytest -q expansions/3_geography/3_3_low_relief_slope/src/test_3_3.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

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
    g2 = s5.gate(summ, None, False, n_flat=0)
    assert g2["s1_decision"] == "no_margin_set" and not g2["release_area_test"]
