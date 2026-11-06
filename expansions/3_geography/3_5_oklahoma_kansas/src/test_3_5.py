"""Smoke tests for 3.5 Oklahoma and Kansas. Tiny synthetic data, no GPU, no network.

Run: python -m pytest -q expansions/3_geography/3_5_oklahoma_kansas/src/test_3_5.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402
import _okks_blocks_roles as br  # noqa: E402
import _okks_coreg_optical as co  # noqa: E402
import _okks_label_budget_9t as lb  # noqa: E402
import _okks_modality_compare as mc  # noqa: E402
import _okks_modality_train as mt  # noqa: E402
import _okks_optical_coverage as oc  # noqa: E402
import _okks_optical_stack as os_  # noqa: E402
import _okks_registry_wells as rw  # noqa: E402
import _okks_truth_adjudicate as ta  # noqa: E402

CRS = "EPSG:6344"


def test_registry_normalisation():
    df = pd.DataFrame({"API": ["1", "2", "3"], "WELLSTATUS": ["OR", "NE", "ZZ"], "SH_LAT": [36.5, 36.6, 99],
                       "SH_LON": [-95.5, -95.6, -95.0], "FOOTAGE_EW": [250, 0, 0], "FOOTAGE_NS": [10, 0, 0],
                       "QTR1": ["NE", "SE", None], "QTR2": [None, "NW", None]})
    df["coord_method"] = rw.ok_coord_method(df)
    assert df["coord_method"].tolist() == ["footage", "quarter_calls_2", "unknown"]
    g = gt.normalise_registry(df, {"well_id": "API", "status_raw": "WELLSTATUS", "lat": "SH_LAT", "lon": "SH_LON",
                                   "coord_method": "coord_method"}, "ok", rw.OK_STATUS, lonlat_crs="EPSG:4326")
    assert g.status_norm.tolist() == ["orphan", "no_evidence_at_location", "unmapped"]
    assert g.coord_ok.tolist() == [True, True, False]


def test_config_crs_matches_zone():
    cfg = gt.load_config("3.5")
    for area, ac in cfg["areas"].items():
        assert gt.utm_epsg_nad83_2011(ac["centre_lonlat"][0]) == int(ac["crs"].split(":")[1]), area
    assert cfg["areas"]["ok_creek"]["crs"] == "EPSG:6343"     # zone 14, not 15


def test_coverage_dates():
    import geopandas as gpd
    from shapely.geometry import box
    blocks = gt.make_blocks((0, 0, 750, 375), CRS)
    tiles = gpd.GeoDataFrame({"tile": ["a", "b"], "acq_date": ["2019-06-01", "2023-06-01"], "res_m": 0.6,
                              "bands": 4, "cloud_flag": [False, False]},
                             geometry=[box(0, 0, 400, 375), box(300, 0, 750, 375)], crs=CRS)
    c = oc.coverage_table(blocks, tiles, "2019-03-01", "2019-04-01", max_gap_years=1.0)
    assert len(c) == 2 and c.covered.all()
    assert c.set_index("block_id").loc["b000_000", "tile"] == "a"
    assert c.date_eligible.tolist() == [True, True]          # block 2 also intersects tile a


def test_phase_correlation_and_shift():
    rng = np.random.default_rng(0)
    ref = rng.normal(size=(128, 128))
    from scipy.ndimage import gaussian_filter
    ref = gaussian_filter(ref, 2)
    mov = np.roll(np.roll(ref, -3, axis=1), 2, axis=0)
    dy, dx, pk = co.phase_correlation(ref, mov)
    assert abs(dx - 3) < 0.3 and abs(dy + 2) < 0.3 and pk > 0.1
    back = os_.shift_block(mov[None], dx, -dy)[0]
    m = np.isfinite(back)
    assert np.allclose(back[m], ref[m], atol=1e-9)
    assert np.isclose(os_.ndvi(np.array([1.0]), np.array([3.0]))[0], 0.5, atol=1e-5)


def test_terciles_and_budget_plan():
    cuts = br.tercile_cuts(np.arange(1, 10, dtype=float))
    assert br.apply_terciles([1.0, 5.0, 9.0, np.nan], cuts) == ["low", "mid", "high", "unknown"]
    split = pd.DataFrame({"fold": [0] * 4 + [1] * 4, "role": "held_out", "block_id": list(range(8))})
    plan = lb.make_plan(split, [0.25, 0.5, 1.0], master=1)
    for f, v in plan.items():
        s = v["train"]
        assert set(s["0.25"]) <= set(s["0.50"]) <= set(s["1.00"])
        assert not set(s["1.00"]) & set(v["test"] + v["val"])
    assert mt.trial_list(12, 5) == mt.trial_list(12, 5) and len(mt.trial_list(12, 5)) == 12


def test_adjudicate_and_strata():
    import geopandas as gpd
    from shapely.geometry import box
    L = gpd.GeoDataFrame({"class": ["pit", "pad"]}, geometry=[box(0, 0, 10, 10), box(50, 50, 80, 80)], crs=CRS)
    O = gpd.GeoDataFrame({"class": ["pit", "pad"], "activity": ["inactive", "active"]},
                         geometry=[box(1, 1, 10, 10), box(200, 200, 230, 230)], crs=CRS)
    t = ta.adjudicate(L, O)
    assert sorted(t.seen_in) == ["both", "lidar", "optical"] and len(t) == 3
    assert t.loc[t.seen_in == "both", "activity"].iloc[0] == "inactive"
    tabs = {"b1": {"c": pd.DataFrame({"blob_id": [1, 2], "score": [0.9, 0.8], "area_m2": [5, 5],
                                      "truth_id": [1, 2]}), "n_truth": 2, "km2": 0.14, "truth_ids": [1, 2]}}
    st = mc.subset_truth(tabs, {1})
    assert st["b1"]["n_truth"] == 1 and np.isclose(gt.pooled_recall_at_k(st, ["b1"]), 1.0)
    assert st["b1"]["truth_ids"] == [1]
    merged = mc.stratified_tables({"ok_rogers": tabs, "ok_nowata": tabs})
    assert set(merged) == {"ok_rogers|b1", "ok_nowata|b1"}


def test_arms_and_class_policies():
    """Pits and pads are scored apart at their own policies. L0 (a pit model) is never scored on pads."""
    assert "L0" in mc.arms_for("pit") and "L0" not in mc.arms_for("pad")
    assert mc.CLASS_TASKS == ("pit", "pad")
    import geopandas as gpd
    from shapely.geometry import box
    t = gpd.GeoDataFrame({"truth_id": [0, 1, 2], "class": ["pit", "pad", "pit"]},
                         geometry=[box(0, 0, 1, 1)] * 3, crs=CRS)
    assert gt.class_truth(t, "pit")["truth_id"].tolist() == [0, 2]
    assert gt.class_truth(t, "pad")["truth_id"].tolist() == [1]
    assert gt.ek.policy_for("pit")["cutoff"] == 0.35 and gt.ek.policy_for("pad")["cutoff"] == 0.525


def test_gain_plot_keeps_negative_gains(tmp_path, monkeypatch):
    """The old plot fixed the y axis at 0 to 1, so a gain of -0.2 with interval [-0.3, -0.1] was invisible."""
    import matplotlib.figure
    seen = {}

    def keep(self, *a, **k):
        seen["ylim"] = self.axes[0].get_ylim()
    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", keep)
    res = {"oklahoma": {"pit": {"primary_F1_minus_L1": {"gain": -0.2, "gain_ci": [-0.3, -0.1]},
                                "policy": {"cutoff": 0.35}, "note": "x"}}}
    rows = mc.gain_rows(res)
    assert rows == [{"arm": "primary_F1", "stratum": "oklahoma pit", "recall": -0.2, "lo": -0.3, "hi": -0.1}]
    gt.plot_recall_strata(pd.DataFrame(rows), tmp_path / "g.png", ylim=None)
    assert seen["ylim"][0] < -0.3 and seen["ylim"][1] >= 0.0


def test_l2_needs_declared_transfer_checkpoint():
    cfg = gt.load_config("3.5")
    assert len(cfg["model"]["pit"]["transfer_checkpoint"]) == 5          # provisional five-fold ensemble
    assert cfg["model"]["pit"]["init_checkpoint"] is None
    import pytest
    with pytest.raises(gt.DecisionMissingError, match="init_checkpoint"):   # L2 init fold is not decided
        gt.transfer_checkpoint(cfg, "pit", "3.5")



def test_defaults_gain_family_per_class():
    """take defaults 2026-11-06. delta_gain 0.03. G gated per class on Oklahoma only (Holm over 2)."""
    cfg = gt.load_config("3.5")
    assert cfg["prereg"]["delta_gain"] == 0.03 and cfg["prereg"]["margin"] == 0.03
    assert cfg["multiplicity"]["family"] == ["F1-L1:pit:oklahoma", "F1-L1:pad:oklahoma"]
    h = gt.hg.holm({"F1-L1:pit:oklahoma": 0.02, "F1-L1:pad:oklahoma": 0.3})
    assert h == {"F1-L1:pit:oklahoma": 0.04, "F1-L1:pad:oklahoma": 0.3}
