"""Smoke tests for 4.8 on tiny synthetic data. Offline (local mosaic only), no GPU. Seconds.

Run. python -m pytest -q expansions/4_modalities/4_8_leafoff_optical/src/test_4_8.py -p no:cacheprovider
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _leafoff_kit_4_8 as lk  # noqa: E402

CFG = lk.load_cfg()
X0, Y0, X1, Y1 = CFG["areas"]["9t"]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import LineString, box
    t = tmp_path_factory.mktemp("lo48")
    rng = np.random.default_rng(0)
    cx = rng.uniform(X0 + 200, X1 - 200, 30)
    cy = rng.uniform(Y0 + 200, Y1 - 200, 30)
    ann = t / "ann.gpkg"
    gpd.GeoDataFrame({"pit_inside_id": range(20)}, geometry=[box(x - 4, y - 4, x + 4, y + 4) for x, y in zip(cx[:20], cy[:20])],
                     crs=CFG["crs"]).to_file(ann, layer="pit_inside")
    gpd.GeoDataFrame({"pad_id": range(10)}, geometry=[box(x - 20, y - 20, x + 20, y + 20) for x, y in zip(cx[20:], cy[20:])],
                     crs=CFG["crs"]).to_file(ann, layer="pad")
    lines = [LineString([(X0 + 100 + 300 * i, Y0 + 50), (X0 + 100 + 300 * i, Y1 - 50)]) for i in range(12)]
    lines += [LineString([(X0 + 50, Y0 + 400 + 300 * j), (X1 - 50, Y0 + 400 + 300 * j)]) for j in range(3)]
    gpd.GeoDataFrame({"id": range(len(lines))}, geometry=lines, crs=CFG["crs"]).to_file(ann, layer="roads")
    # mosaic covers the west half only. Brown ground with green speckle.
    W = int((X1 - X0) / 2 / 2.0)
    H = int((Y1 - Y0) / 2.0)
    img = np.zeros((3, H, W), "uint8")
    img[0], img[1], img[2] = 120, 100, 80
    g = rng.random((H, W)) < 0.3
    img[1][g] = 150
    img[0][g] = 40
    img[2][g] = 40
    mos = t / "mosaic.tif"
    with rasterio.open(mos, "w", driver="GTiff", width=W, height=H, count=3, dtype="uint8", crs=CFG["crs"],
                       transform=from_origin(X0, Y1, 2.0, 2.0)) as d:
        d.write(img)
    return t, ann, mos


def test_measures_and_status():
    pr = CFG["prereg"]
    rng = np.random.default_rng(1)
    brown = (np.full((50, 50, 3), (120, 100, 80)) + rng.integers(-8, 9, (50, 50, 1))).astype(np.uint8)
    green = np.full((50, 50, 3), (60, 160, 60), np.uint8)
    assert lk.image_measures(brown, pr)["visible_ground_fraction"] == 1.0
    assert lk.image_measures(green, pr)["visible_ground_fraction"] == 0.0
    m = lk.image_measures(brown, pr)
    assert lk.chip_status(None, {"error": "x"}, None, pr, None)[0] == "unavailable"
    assert lk.chip_status(np.full((5, 5, 3), 255, np.uint8), {}, lk.image_measures(np.full((5, 5, 3), 255, np.uint8), pr), pr, None)[0] == "blank"
    assert lk.chip_status(brown, {"date": None}, m, pr, None)[0] == "undated"
    assert lk.chip_status(brown, {"date": "2020-07-01"}, m, pr, None)[0] == "off-season"
    assert lk.chip_status(brown, {"date": "2020-03-01"}, m, pr, 9.0)[0] == "unregistered"
    assert lk.chip_status(brown, {"date": "2020-03-01"}, m, pr, 1.0)[0] == "usable"


def test_pipeline(world, tmp_path):
    import _leafoff_chip_status_9t as s2
    import _leafoff_coverage_table_9t as s0
    import _leafoff_feature_sample_9t as s1
    import _leafoff_georeg_offset_9t as s3
    import _leafoff_review_gate_9t as s5
    t, ann, mos = world
    assert s0.main(["--programs", str(tmp_path / "none.csv"), "--out", str(tmp_path)]) == 0
    cov = pd.read_csv(tmp_path / "leafoff_coverage_9t.csv").set_index("source_id")
    assert cov.loc["naip_2022", "season"] == "leaf-on" and cov.loc["pema_venango_2020", "season"] == "undated"
    assert s1.main(["--n", "12", "--annotations", str(ann), "--out", str(tmp_path)]) == 0
    smp = pd.read_csv(tmp_path / "leafoff_feature_sample_9t.csv")
    assert len(smp) == 12 and set(smp.layer) == {"pit_inside", "pad"}
    s1.main(["--n", "12", "--annotations", str(ann), "--out", str(tmp_path / "again")])
    assert pd.read_csv(tmp_path / "again" / "leafoff_feature_sample_9t.csv").feature_key.tolist() == smp.feature_key.tolist()
    assert s3.main(["--template", "--sources", "local_mosaic", "--annotations", str(ann), "--out", str(tmp_path)]) == 0
    m = pd.read_csv(tmp_path / "leafoff_offsets_measured_9t.csv")
    assert len(m) == 10
    m["image_x"], m["image_y"] = m.lidar_x + 1.5, m.lidar_y - 1.0
    m.to_csv(tmp_path / "leafoff_offsets_measured_9t.csv", index=False)
    assert s3.main(["--measured", str(tmp_path / "leafoff_offsets_measured_9t.csv"), "--out", str(tmp_path)]) == 0
    sm = pd.read_csv(tmp_path / "leafoff_offsets_summary_9t.csv")
    assert sm.registered.all() and abs(sm.median_m.iloc[0] - np.hypot(1.5, 1.0)) < 1e-6
    out_csv = tmp_path / "status.csv"
    assert s2.main(["--sources", "local_mosaic", "--sample", str(tmp_path / "leafoff_feature_sample_9t.csv"), "--annotations", str(ann),
                    "--offsets", str(tmp_path / "leafoff_offsets_summary_9t.csv"), "--chips", str(tmp_path / "chips"),
                    "--out-csv", str(out_csv), "--local-mosaic", str(mos), "--local-date", "2020-03-20"]) == 0
    st = pd.read_csv(out_csv)
    west = smp.x < (X0 + X1) / 2
    stat = st.set_index("feature_key").status
    assert (stat[smp.feature_key[~west & (smp.x > (X0 + X1) / 2 + 60)]] == "blank").all()
    assert (stat[smp.feature_key[west & (smp.x < (X0 + X1) / 2 - 60)]] == "usable").all()
    rv = tmp_path / "reviews"
    rv.mkdir()
    use = st[st.status == "usable"].feature_key
    for name, vals in (("r1", ["yes"] * len(use)), ("r2", ["yes"] * (len(use) - 1) + ["no"])):
        pd.DataFrame({"feature_key": use, "source_id": "local_mosaic", "reviewer": name, "visible": vals}).to_csv(rv / f"{name}.csv", index=False)
    assert s5.main(["--status", str(out_csv), "--reviews", str(rv), "--out", str(tmp_path)]) == 0
    g = json.loads((tmp_path / "leafoff_gate_9t.json").read_text())
    # Oracle. Judged chips exclude blank, unavailable and undated. Clopper-Pearson from scipy's beta directly.
    from scipy.stats import beta
    judged = st[~st.status.isin(["blank", "unavailable", "undated"])]
    k, n = int((judged.status == "usable").sum()), len(judged)
    lo = beta.ppf(0.025, k, n - k + 1) if k else 0.0
    hi = beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    want = "success" if lo > 0.60 else "failure" if hi < 0.60 else "inconclusive"
    if n / len(st) < 0.80:                      # coverage rule, user default 2026-11-06
        want = "inconclusive"
    b = g["by_source"]["local_mosaic"]
    assert b["n"] == n and b["n_sampled"] == len(st) and b["coverage"] == pytest.approx(n / len(st))
    assert b["decision"] == want
    assert g["interpretability"]["local_mosaic"]["n"] == len(use)
    assert (tmp_path / "leafoff_status_by_source_9t.png").exists()


def test_undated_chips_are_missing_not_negative():
    """4.8-01. Pre-fix, 30 undated chips joined the denominator and the gate said 'unusable here'.
    Source a has 10 of 10 judged chips usable. Clopper-Pearson lower bound 0.025 ** (1 / 10) = 0.69 > 0.60.
    Its coverage is 10 / 40 = 0.25, under the 0.80 minimum (default 2026-11-06), so it is inconclusive, not
    success. Source b has 36 of 40 judged (coverage 0.90) and all usable. Lower bound 0.025 ** (1 / 36) = 0.90,
    so it succeeds."""
    import _leafoff_review_gate_9t as s5
    st = pd.DataFrame({"source_id": ["a"] * 40 + ["pema"] * 40 + ["b"] * 40,
                       "status": ["usable"] * 10 + ["undated"] * 30 + ["undated"] * 40 + ["usable"] * 36 + ["blank"] * 4})
    cov = lk.load_cfg()["prereg"]["min_coverage"]
    assert cov == 0.80
    g = s5.gate(st, 0.60, cov)
    assert g["a"]["n"] == 10 and g["a"]["coverage"] == pytest.approx(0.25)
    assert g["a"]["lo"] == pytest.approx(0.025 ** 0.1) and g["a"]["decision"] == "inconclusive"
    assert g["a"]["coverage_ok"] is False and "below 0.80" in g["a"]["action"]
    assert s5.gate(st, 0.60, 0.20)["a"]["decision"] == "success"         # the old behaviour, now only with a low floor
    assert g["b"]["coverage"] == pytest.approx(0.90) and g["b"]["lo"] == pytest.approx(0.025 ** (1 / 36))
    assert g["b"]["decision"] == "success"
    assert g["pema"]["n"] == 0 and g["pema"]["coverage"] == 0.0
    assert g["pema"]["decision"] == "inconclusive" and g["pema"]["action"] != "unusable here"


def test_intersections_are_true_junctions():
    """Minor 4.8 finding. An end-to-end joint is degree two and is not an intersection."""
    import _leafoff_georeg_offset_9t as s3
    from shapely.geometry import LineString
    bb = (-1e6, -1e6, 1e6, 1e6)
    joint = [LineString([(0, 0), (10, 0)]), LineString([(10, 0), (20, 0)])]
    assert len(s3.intersections(joint, bb)) == 0
    tee = [LineString([(0, 0), (20, 0)]), LineString([(10, 0), (10, 10)])]
    assert np.allclose(s3.intersections(tee, bb), [[10, 0]])
    cross = [LineString([(0, 0), (20, 0)]), LineString([(10, -10), (10, 10)])]
    assert np.allclose(s3.intersections(cross, bb), [[10, 0]])
    star = [LineString([(0, 0), (10, 0)]), LineString([(10, 0), (20, 0)]), LineString([(10, 0), (10, 10)])]
    assert np.allclose(s3.intersections(star, bb), [[10, 0]])
