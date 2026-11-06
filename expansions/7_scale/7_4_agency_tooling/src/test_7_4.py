"""Smoke tests for 7.4 on tiny synthetic data. CPU only, no network, seconds.

Run
    python -m pytest -q expansions/7_scale/7_4_agency_tooling/src/test_7_4.py -p no:cacheprovider
"""
from __future__ import annotations

import os

os.environ["CUDA_VISIBLE_DEVICES"] = ""

import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _agency_las_validity as va  # noqa: E402

CRS = "EPSG:6346"


def test_t1_fixtures_zero_silent_passes(tmp_path):
    import _agency_fixture_las_build as fx
    cfg = va.load_cfg()
    cfg["validity"]["min_tile_extent_m"] = 40.0
    res = fx.check(fx.build(tmp_path, 50.0), cfg)
    assert res["_summary"]["silent_passes"] == 0
    assert res["_summary"]["passed"] == res["_summary"]["n"], {k: v for k, v in res.items() if k[0] != "_" and not v["pass"]}


def _blobs():
    import geopandas as gpd
    from shapely.geometry import box
    return gpd.GeoDataFrame({"score": [0.9, 0.4, 0.7], "area_m2": [20.0, 30.0, 25.0], "tile_id": ["t1", "t1", "t2"]},
                            geometry=[box(620000, 4594000, 620005, 4594004), box(620100, 4594100, 620106, 4594105),
                                      box(620200, 4594000, 620205, 4594005)], crs=CRS)


def test_export_formats_and_guard(tmp_path):
    import _agency_export_formats as ex
    wells = pd.DataFrame({"x": [620010.0, 620500.0], "y": [4594000.0, 4594500.0]})
    wells.to_csv(tmp_path / "wells.csv", index=False)
    before = (tmp_path / "wells.csv").read_bytes()
    w = ex.read_known_wells(tmp_path / "wells.csv", CRS)
    meta = {"run_id": "20261105_agency_abc", "model_id": "m", "model_sha256": "s", "method": "unet_cv5 frozen policy"}
    t = ex.build_table(_blobs(), "pit", meta, area_km2=0.05, k_per_km2=40, wells=w, validity={"t2": "warn:canopy"})
    assert list(t["rank_in_run"]) == [1, 2, 3] and (t["label"] == "candidate").all() and (t["evidence_level"] == "a").all()
    assert abs(t.iloc[0]["dist_nearest_known_m"] - np.hypot(7.5, 2.0)) < 0.01
    assert t.loc[t["tile_id"] == "t2", "validity_flag"].iloc[0].startswith("warn")
    cfg = va.load_cfg()
    s = ex.write_all({"pit": t}, tmp_path / "run", cfg["forbidden_words"])
    assert s["n"] == 3
    csv = pd.read_csv(tmp_path / "run" / "candidates.csv")
    assert set(ex.COLUMNS) <= set(csv.columns)
    kml = (tmp_path / "run" / "candidates.kml").read_text()
    assert "candidate" in kml and "confirmed" not in kml.lower()
    assert (tmp_path / "wells.csv").read_bytes() == before, "known wells must stay read-only"
    t2 = t.copy(); t2["method"] = "confirmed well detector"
    with pytest.raises(ValueError):
        ex.write_all({"pit": t2}, tmp_path / "run2", cfg["forbidden_words"])


def test_trust_wording_and_calibration(tmp_path):
    import _agency_trust_calibrate as tc
    cfg = va.load_cfg()
    a = lambda p: {"key": "expansions", "rel": str((tmp_path / p).resolve())}  # noqa: E731
    cfg["transfer_evidence"] = [{"area": "9t", "path": a("e9t.json")}, {"area": "warren", "path": a("ew.json")}]
    st = tc.trust_statement(cfg, "abc")
    assert "evaluated on 9t only" in st and "not a well" in st.lower()
    assert "27 of 424" in st, "context line must be parsed from LEADERBOARD.md"
    (tmp_path / "ew.json").write_text(json.dumps({"recall": 0.8, "lo": 0.7, "hi": 0.9, "decision": "inconclusive", "model_sha256": "abc"}))
    assert "not shown to transfer or to fail" in tc.trust_statement(cfg, "abc")
    assert "different model hash" in tc.trust_statement(cfg, "zzz")
    rng = np.random.default_rng(0)
    s = rng.random(80); y = (rng.random(80) < s).astype(int)
    cal = tc.calibrate(s, y, "abc", B=50)
    f = tc.apply_calibration(cal, "abc")
    out = f(np.sort(s))
    assert np.all(np.diff(out) >= -1e-12), "calibration must be monotone"
    with pytest.raises(PermissionError):
        tc.apply_calibration(cal, "other")


def test_cli_run_reproducible(tmp_path):
    import rasterio
    import torch
    from rasterio.transform import from_origin
    sys.path.insert(0, str(va.ek.REPO / "notebooks" / "wellsight_v2"))
    import _dl
    import _agency_cli_candidates as cli
    rng = np.random.default_rng(0)
    stack = tmp_path / "stack.tif"
    with rasterio.open(stack, "w", driver="GTiff", width=64, height=64, count=7, dtype="float32", crs=CRS,
                       transform=from_origin(620000, 4594032, 0.5, 0.5), nodata=np.nan) as o:
        o.write(rng.normal(size=(7, 64, 64)).astype("float32"))
    torch.manual_seed(0)
    for k in (0, 1):
        d = tmp_path / f"m{k}"; d.mkdir()
        torch.save({"state_dict": _dl.UNet(in_ch=7, n_classes=3).state_dict(), "mu": np.zeros(7, np.float32),
                    "sd": np.ones(7, np.float32), "channels": va.load_cfg()["channels"], "patch": 64}, d / "best.pt")
    cfg = va.load_cfg()
    cfg["models"]["pit"].update(checkpoints=[{"key": "expansions", "rel": str(tmp_path / "m{k}" / "best.pt")}], folds=[0, 1])
    cfg["manifest"] = {"key": "expansions", "rel": str(tmp_path / "manifest.json")}
    cfg["frozen_cutoff"]["pit"] = 0.34
    (tmp_path / "manifest.json").write_text(json.dumps(cli.build_manifest(cfg, ["pit"])))
    cp = tmp_path / "cfg.json"; cp.write_text(json.dumps(cfg))
    pd.DataFrame({"x": [620010.0], "y": [4594010.0]}).to_csv(tmp_path / "wells.csv", index=False)
    outs = []
    for i in (1, 2):
        rc = cli.main(["--config", str(cp), "run", "--features", str(stack), "--out", str(tmp_path / f"o{i}"),
                       "--model", "pit", "--device", "cpu", "--known-wells", str(tmp_path / "wells.csv")])
        assert rc == 0
        rd = next((tmp_path / f"o{i}").iterdir())
        outs.append((rd / "candidates.csv").read_bytes())
        assert (rd / "trust_statement.md").exists() and (rd / "_PROVENANCE.json").exists()
    assert outs[0] == outs[1], "T4: same input must give identical candidates"
    # a tampered checkpoint is refused (exit 3)
    torch.save({"state_dict": {}}, tmp_path / "m1" / "best.pt")
    assert cli.main(["--config", str(cp), "run", "--features", str(stack), "--out", str(tmp_path / "o3"),
                     "--model", "pit", "--device", "cpu"]) == 3
    assert cli.main(["--config", str(cp), "run", "--features", str(stack), "--out", str(tmp_path / "o4"), "--res", "1.0"]) == 2
