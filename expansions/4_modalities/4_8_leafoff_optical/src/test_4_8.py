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
    assert g["by_source"]["local_mosaic"]["decision"] in {"success", "failure", "inconclusive"}
    assert g["interpretability"]["local_mosaic"]["n"] == len(use)
    assert (tmp_path / "leafoff_status_by_source_9t.png").exists()
