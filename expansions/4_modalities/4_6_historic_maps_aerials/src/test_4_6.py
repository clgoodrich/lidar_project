"""Smoke tests for 4.6 on tiny synthetic data. Seconds, no GPU, no network.

Run. python -m pytest -q expansions/4_modalities/4_6_historic_maps_aerials/src/test_4_6.py -p no:cacheprovider
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
import _hist_kit_4_6 as hk  # noqa: E402

CFG = hk.load_cfg()
X0, Y0, X1, Y1 = CFG["bbox_9t"]


def test_source_search(tmp_path):
    import _hist_source_search_9t as s0
    w, s, e, n = hk.bbox_lonlat(CFG["bbox_9t"])
    df = pd.DataFrame([
        dict(source_id="a", title="t", kind="topo", date="1908", scale="62500", archive="USGS", url="u",
             west=w - 0.1, south=s - 0.1, east=e + 0.1, north=n + 0.1, scan_dpi=600, rights="PD", searched_on="2026-11-05"),
        dict(source_id="b", title="t", kind="atlas", date="1865", scale="", archive="LoC", url="u",
             west=w + 5, south=s, east=e + 5, north=n, scan_dpi=300, rights="PD", searched_on="2026-11-05"),
        dict(source_id="c", title="t", kind="aerial", date="1939", scale="20000", archive="PSU", url="u",
             west=None, south=None, east=None, north=None, scan_dpi=None, rights=None, searched_on="2026-11-05")])
    f = tmp_path / "src.csv"
    df.to_csv(f, index=False)
    assert s0.main(["--sources", str(f), "--out", str(tmp_path)]) == 0
    v = pd.read_csv(tmp_path / "hist_source_search_9t.csv").set_index("source_id").verdict
    assert v["a"] == "candidate" and v["b"] == "no coverage" and v["c"] == "unknown"


def test_missing_input_message(tmp_path):
    import _hist_source_search_9t as s0
    with pytest.raises(FileNotFoundError, match="source search log"):
        s0.main(["--sources", str(tmp_path / "nope.csv"), "--out", str(tmp_path)])


def _sheet(path: Path):
    """A NAD27 UTM 17N sheet covering the west half of 9t."""
    import rasterio
    from pyproj import Transformer
    from rasterio.transform import from_origin
    t = Transformer.from_crs("EPSG:6346", "EPSG:26717", always_xy=True)
    ux0, uy1 = t.transform(X0 - 300, Y1 + 300)
    a = (np.random.default_rng(0).integers(0, 255, (3, 200, 80))).astype("uint8")
    with rasterio.open(path, "w", driver="GTiff", width=80, height=200, count=3, dtype="uint8", crs="EPSG:26717",
                       transform=from_origin(ux0, uy1, 30, 30)) as d:
        d.write(a)


def test_topo_crop(tmp_path):
    import _hist_topo_crop_9t as s1
    sheet = tmp_path / "sheet.tif"
    _sheet(sheet)
    assert s1.main(["--sheet", str(sheet), "--source", "syn", "--res", "30", "--out", str(tmp_path),
                    "--marks-out", str(tmp_path / "marks")]) == 0
    meta = json.loads((tmp_path / "syn_crop_9t.json").read_text())
    assert 0.3 < meta["cover_share_9t"] < 0.6 and meta["partial_cover"]
    assert len(list(tmp_path.glob("syn_zoom4_*.png"))) == 16
    assert (tmp_path / "marks" / "syn__d1.csv").exists()


def _gcp(noise, seed=1):
    rng = np.random.default_rng(seed)
    px, py = rng.uniform(0, 3000, 22), rng.uniform(0, 3000, 22)
    x, y = X0 + 1.5 * px + 0.01 * py, Y1 - 1.5 * py
    return pd.DataFrame({"point_id": range(22), "role": ["gcp"] * 12 + ["check"] * 10, "px": px, "py": py,
                         "x": x + rng.normal(0, noise, 22), "y": y + rng.normal(0, noise, 22), "feature": "road"})


@pytest.mark.parametrize("noise,ok", [(2.0, True), (60.0, False)])
def test_georef(tmp_path, noise, ok):
    import _hist_georef_check_9t as s3
    f = tmp_path / "g.csv"
    _gcp(noise).to_csv(f, index=False)
    assert s3.main(["--source", "syn", "--gcp", str(f), "--out", str(tmp_path)]) == 0
    r = json.loads((tmp_path / "hist_georef_syn_9t.json").read_text())
    assert (r["verdict"] == "within limit") is ok
    assert r["rmse_lo"] <= r["rmse_m"] <= r["rmse_hi"]
    tps, _ = s3.accuracy(_gcp(2.0), "tps", 200, 0)
    assert tps["n_check"] == 10


def _marks(tmp_path):
    rng = np.random.default_rng(3)
    base = np.column_stack([rng.uniform(X0 + 500, X1 - 500, 8), rng.uniform(Y0 + 500, Y1 - 500, 8)])
    d = tmp_path / "marks"
    d.mkdir(exist_ok=True)
    for name, xy in (("d1", base), ("d2", np.vstack([base[:6] + 5.0, [[X0 + 50, Y0 + 50]]]))):
        pd.DataFrame({"mark_id": [f"{name}_{i}" for i in range(len(xy))], "source": "syn", "date": "1939",
                      "digitiser": name, "symbol": "derrick", "x": xy[:, 0], "y": xy[:, 1]}).to_csv(d / f"syn__{name}.csv", index=False)
    (tmp_path / "hist_georef_syn_9t.json").write_text(json.dumps({"rmse_m": 12.0}))
    return d, base


def test_marks_merge_and_compare(tmp_path):
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    import _hist_marks_merge_9t as s4
    import _hist_marks_vs_records_9t as s5
    import _hist_source_verdicts_9t as s6
    d, base = _marks(tmp_path)
    gpk = tmp_path / "marks.gpkg"
    assert s4.main(["--source", "syn", "--marks-dir", str(d), "--out-gpkg", str(gpk), "--out", str(tmp_path)]) == 0
    agr = json.loads((tmp_path / "hist_marks_agreement_syn_9t.json").read_text())
    assert agr["n_pairs"] == 6 and agr["n_marks"] == 15
    m = gpd.read_file(gpk, layer="marks")
    assert len(m) == 9 and (m.adjudicated == "agreed").sum() == 6
    ann = tmp_path / "ann.gpkg"
    gpd.GeoDataFrame({"pit_inside_id": [1]}, geometry=[box(*(base[0] - 3), *(base[0] + 3))], crs=CFG["crs"]).to_file(ann, layer="pit_inside")
    gpd.GeoDataFrame({"pad_id": [1]}, geometry=[box(*(base[1] - 30), *(base[1] + 30))], crs=CFG["crs"]).to_file(ann, layer="pad")
    dep = tmp_path / "dep.gpkg"
    gpd.GeoDataFrame({"PERMIT_NUM": range(6)}, geometry=gpd.points_from_xy(base[:6, 0] + 3, base[:6, 1]), crs=CFG["crs"]).to_file(dep)
    fp = tmp_path / "fp.gpkg"
    gpd.GeoDataFrame(geometry=[box(X0 - 1000, Y0 - 1000, X1 + 1000, Y1 + 1000)], crs=CFG["crs"]).to_file(fp)
    prob = np.zeros((450, 450), "float32")
    r, c = int((Y1 - base[0, 1]) / 10), int((base[0, 0] - X0) / 10)
    prob[r - 1:r + 2, c - 1:c + 2] = 0.9
    pt = tmp_path / "prob.tif"
    with rasterio.open(pt, "w", driver="GTiff", width=450, height=450, count=1, dtype="float32", crs=CFG["crs"],
                       transform=from_origin(X0, Y1, 10, 10)) as ds:
        ds.write(prob, 1)
    assert s5.main(["--source", "syn", "--marks", str(gpk), "--annotations", str(ann), "--dep", str(dep),
                    "--footprint", str(fp), "--prob", str(pt), "--n-shifts", "40", "--out", str(tmp_path)]) == 0
    res = json.loads((tmp_path / "hist_marks_compare_syn_9t.json").read_text())
    assert res["dep_association"]["observed"] == 6 and res["dep_association"]["excess"] > 0
    assert res["topk"]["in_topk"][0] > 0
    (tmp_path / "syn_crop_9t.json").write_text(json.dumps({"cover_share_9t": 0.9}))
    (tmp_path / "hist_georef_syn_9t.json").write_text(json.dumps({"rmse_m": 12.0, "rmse_hi": 15.0, "verdict": "within limit"}))
    assert s6.main(["--sources", "syn", "--tables", str(tmp_path), "--crops", str(tmp_path)]) == 0
    v = pd.read_csv(tmp_path / "hist_source_verdicts_9t.csv")
    assert v.verdict.iloc[0] in {"inconclusive", "usable here"}


def test_neatline_and_aerial_probe(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    import _hist_aerial_probe_9t as s2
    import _hist_topo_crop_9t as s1
    w, s, e, n = hk.bbox_lonlat(CFG["bbox_9t"])
    m = s1.neatline_mask(from_origin(X0, Y1, 30, 30), (150, 150), CFG["crs"], (w - 1, s - 1, e + 1, (s + n) / 2))
    assert 0.4 < m.mean() < 0.6
    scan = tmp_path / "f1.tif"
    with rasterio.open(scan, "w", driver="GTiff", width=100, height=100, count=1, dtype="uint8", crs=CFG["crs"],
                       transform=from_origin(X0, Y1, 1.0, 1.0)) as d:
        d.write(np.random.default_rng(0).integers(0, 255, (1, 100, 100)).astype("uint8"))
    idx = pd.DataFrame([dict(frame_id="f1", date="1939-04-01", archive="PSU", path=str(scan), west=w, south=s, east=e, north=n, scale=20000),
                        dict(frame_id="f2", date="1942-05-01", archive="USGS", path="", west=w, south=s, east=e, north=n, scale=24000),
                        dict(frame_id="f3", date="1950-05-01", archive="USGS", path="", west=w + 3, south=s, east=e + 3, north=n, scale=24000)])
    f = tmp_path / "idx.csv"
    idx.to_csv(f, index=False)
    assert s2.main(["--index", str(f), "--out", str(tmp_path)]) == 0
    dv = pd.read_csv(tmp_path / "hist_aerial_dates_9t.csv").set_index("date").verdict
    assert dv["1939-04-01"] == "legible candidate" and dv["1942-05-01"].startswith("inconclusive") and "1950-05-01" not in dv
