"""Tests for 7.4 on tiny synthetic data. CPU only, no network, seconds.

Fixtures are written here directly with laspy, rasterio and numpy. They do not use _agency_fixture_las_build.py,
which is part of the code under test. Assertions use exit codes, status fields and values computed by hand
in this file, not the checker's own message strings.

Run
    python -m pytest -q expansions/7_scale/7_4_agency_tooling/src/test_7_4.py -p no:cacheprovider
"""
from __future__ import annotations

import os

os.environ["CUDA_VISIBLE_DEVICES"] = ""

import hashlib  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _agency_las_validity as va  # noqa: E402

CRS = "EPSG:6346"
X0, Y0 = 620000.0, 4594000.0


# ----------------------------------------------------------------------------- independent fixtures
def _las(path: Path, *, crs: str | None = "EPSG:6346+5703", ground_step: float = 0.25, veg_step: float = 0.25,
         size: float = 50.0, single: bool = False, scale_xy: float = 1.0, lonlat: bool = False,
         wkt: str | None = None) -> dict:
    """Ground points on a regular grid, vegetation on a grid shifted by 0.1 m. Returns the hand-computed oracle."""
    import laspy
    from pyproj import CRS as PCRS
    g = np.arange(0, size, ground_step) if ground_step else np.empty(0)
    v = np.arange(0, size, veg_step)
    gx, gy = [a.ravel() for a in np.meshgrid(g, g)]
    vx, vy = [a.ravel() + 0.1 for a in np.meshgrid(v, v)]
    x, y = np.r_[gx, vx], np.r_[gy, vy]
    n_g, n = len(gx), len(gx) + len(vx)
    h = laspy.LasHeader(point_format=6, version="1.4")
    if lonlat:
        h.scales = np.array([1e-7, 1e-7, 0.001])
        X, Y = -79.5 + x / 85000.0, 41.4 + y / 111000.0
    else:
        h.scales = np.array([0.001, 0.001, 0.001])
        X, Y = X0 * scale_xy + x * scale_xy, Y0 * scale_xy + y * scale_xy
    if crs is not None:
        h.add_crs(PCRS.from_user_input(crs))
    if wkt is not None:
        h.vlrs.append(laspy.vlrs.known.WktCoordinateSystemVlr(wkt))
        h.global_encoding.wkt = True
    h.offsets = np.array([X.min(), Y.min(), 0.0])
    las = laspy.LasData(h)
    las.x, las.y = X, Y
    las.z = np.r_[np.full(n_g, 300.0), np.full(n - n_g, 315.0)]
    las.classification = np.r_[np.full(n_g, 2, np.uint8), np.full(n - n_g, 1, np.uint8)]
    las.return_number = np.ones(n, np.uint8)
    las.number_of_returns = np.full(n, 1 if single else 2, np.uint8)
    las.gps_time = np.linspace(3e8, 3e8 + 10, n)
    las.write(path)
    # oracle in metres: occupied 1 m cells, ground density, 0.5 m void share
    xm, ym = x, y
    cells = {(int(np.floor(a - xm.min())), int(np.floor(b - ym.min()))) for a, b in zip(xm, ym)}
    gsub = {(int(np.floor((a - xm.min()) / 0.5)), int(np.floor((b - ym.min()) / 0.5))) for a, b in zip(gx, gy)}
    return {"ground_density": n_g / len(cells), "void": 1 - len(gsub) / (4 * len(cells)), "share": n_g / n}


def _cfg():
    cfg = va.load_cfg()
    cfg["validity"]["min_tile_extent_m"] = 40.0     # the 50 m fixtures are not small tiles
    return cfg


def _n(field: str) -> int:
    return len([r for r in str(field).split(";") if r])


def test_validity_baseline_ok_and_measured(tmp_path):
    oracle = _las(tmp_path / "ok.las")
    assert oracle["ground_density"] == 16.0 and oracle["void"] == 0.0 and oracle["share"] == 0.5
    r = va.check_tile(tmp_path / "ok.las", _cfg())
    assert r["status"] == "ok" and r["reasons"] == [] and r["warnings"] == []
    assert r["ground_density_ppsm"] == pytest.approx(oracle["ground_density"])
    assert r["void_frac"] == pytest.approx(oracle["void"])
    assert r["ground_share"] == pytest.approx(oracle["share"])


@pytest.mark.parametrize("name,kw,status", [
    ("no_crs", dict(crs=None), "refuse"),
    ("geographic", dict(crs="EPSG:4326", lonlat=True), "refuse"),
    ("zero_ground", dict(ground_step=None), "refuse"),
    ("single_return", dict(single=True), "warn"),
    # 7.4 minor. Feet tiles are refused because the derivative builder never converts them (was "warn")
    ("feet", dict(crs="EPSG:2272", scale_xy=1 / 0.3048006096), "refuse"),
])
def test_validity_one_defect_each(tmp_path, name, kw, status):
    _las(tmp_path / f"{name}.las", **kw)
    r = va.check_tile(tmp_path / f"{name}.las", _cfg())
    assert r["status"] == status
    if status == "refuse":
        assert len(r["reasons"]) == 1, r                # the one defect, nothing else, against the ok baseline
    else:
        assert r["reasons"] == [] and len(r["warnings"]) == 1


def test_validity_low_density_value(tmp_path):
    # dense vegetation on 0.25 m, ground every 2 m. 625 ground points over 2500 occupied 1 m cells
    oracle = _las(tmp_path / "sparse.las", ground_step=2.0)
    assert oracle["ground_density"] == 0.25 and oracle["void"] == 1 - 625 / 10000
    r = va.check_tile(tmp_path / "sparse.las", _cfg())
    assert r["status"] == "refuse"
    assert r["ground_density_ppsm"] == pytest.approx(0.25) and r["void_frac"] == pytest.approx(0.9375)


def test_validity_truncated_and_mixed_crs(tmp_path):
    _las(tmp_path / "t.las")
    b = (tmp_path / "t.las").read_bytes()
    (tmp_path / "t.las").write_bytes(b[: len(b) // 2])
    assert va.check_tile(tmp_path / "t.las", _cfg())["status"] == "refuse"
    d = tmp_path / "mixed"; d.mkdir()
    _las(d / "a.las"); _las(d / "b.las", crs="EPSG:26917+5703")
    df = va.check_folder(d, _cfg())
    assert list(df["status"]) == ["refuse", "refuse"] and df["reasons"].map(_n).tolist() == [1, 1]


def test_validity_override_only_when_absent(tmp_path):
    _las(tmp_path / "none.las", crs=None)
    r = va.check_tile(tmp_path / "none.las", _cfg(), crs_override="EPSG:6346")
    assert r["status"] == "warn" and r["crs"] == "EPSG:6346"   # override applied, vertical datum still missing
    # 7.4 minor. A CRS record that cannot be parsed is refused and the override is not applied (was "warn")
    _las(tmp_path / "bad.las", crs=None, wkt="GARBAGE[not a crs]")
    r = va.check_tile(tmp_path / "bad.las", _cfg(), crs_override="EPSG:6346")
    assert r["status"] == "refuse" and r["crs"] is None and len(r["reasons"]) == 1


# ----------------------------------------------------------------------------- export, trust
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
    assert t["within_review_budget"].tolist() == [True, True, False]          # floor(40 x 0.05) = 2
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


def test_known_wells_reader_refuses_bad_input(tmp_path):
    import _agency_export_formats as ex
    pd.DataFrame({"x": [620010.0, np.nan], "y": [4594000.0, 4594001.0]}).to_csv(tmp_path / "nan.csv", index=False)
    pd.DataFrame({"lon": [-79.5], "lat": [41.4]}).to_csv(tmp_path / "ll.csv", index=False)
    pd.DataFrame({"x": [-79.5], "y": [41.4]}).to_csv(tmp_path / "deg.csv", index=False)
    for f in ("nan.csv", "ll.csv", "deg.csv"):
        with pytest.raises(ex.InputError):
            ex.read_known_wells(tmp_path / f, CRS)
    g = ex.read_known_wells(tmp_path / "ll.csv", CRS, "EPSG:4326")           # declared, so accepted
    from pyproj import Transformer
    ox, oy = Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform(-79.5, 41.4)
    assert abs(g.geometry.x.iloc[0] - ox) < 1e-6 and abs(g.geometry.y.iloc[0] - oy) < 1e-6


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


# ----------------------------------------------------------------------------- CLI
def _stack(path: Path, crs: str, n: int = 64, seed: int = 0) -> Path:
    import rasterio
    from rasterio.transform import from_origin
    rng = np.random.default_rng(seed)
    with rasterio.open(path, "w", driver="GTiff", width=n, height=n, count=7, dtype="float32", crs=crs,
                       transform=from_origin(X0, Y0 + n * 0.5, 0.5, 0.5), nodata=np.nan) as o:
        o.write(rng.normal(size=(7, n, n)).astype("float32"))
    return path


def _models(tmp_path: Path) -> tuple[Path, dict]:
    """Tiny random pit (3-class) and pad (2-class) checkpoints, a manifest and a config file."""
    import torch
    sys.path.insert(0, str(va.ek.REPO / "notebooks" / "wellsight_v2"))
    import _dl
    import _agency_cli_candidates as cli
    cfg = va.load_cfg()
    torch.manual_seed(0)
    shas = {}
    for cls, nc in (("pit", 3), ("pad", 2)):
        for k in (0, 1):
            d = tmp_path / f"{cls}{k}"; d.mkdir()
            torch.save({"state_dict": _dl.UNet(in_ch=7, n_classes=nc).state_dict(), "mu": np.zeros(7, np.float32),
                        "sd": np.ones(7, np.float32), "channels": cfg["channels"], "patch": 64}, d / "best.pt")
        cfg["models"][cls].update(checkpoints=[{"key": "expansions", "rel": str(tmp_path / f"{cls}{{k}}" / "best.pt")}],
                                  folds=[0, 1])
        shas[cls] = hashlib.sha256((tmp_path / f"{cls}0" / "best.pt").read_bytes()).hexdigest()
    cfg["manifest"] = {"key": "expansions", "rel": str(tmp_path / "manifest.json")}
    cfg["frozen_cutoff"]["pit"] = 0.34
    (tmp_path / "manifest.json").write_text(json.dumps(cli.build_manifest(cfg, ["pit", "pad"])))
    cp = tmp_path / "cfg.json"; cp.write_text(json.dumps(cfg))
    return cp, shas


AREA_KM2 = 64 * 64 * 0.25 / 1e6            # every cell of the 64 x 64 stack is valid


def _run(cp, *args):
    import _agency_cli_candidates as cli
    return cli.main(["--config", str(cp), "run", "--device", "cpu", *map(str, args)])


def _only_run(out: Path) -> Path:
    runs = [p for p in out.iterdir() if p.is_dir()]
    assert len(runs) == 1
    return runs[0]


def test_cli_run_reproducible(tmp_path):
    cp, _ = _models(tmp_path)
    stack = _stack(tmp_path / "stack.tif", CRS)
    pd.DataFrame({"x": [620010.0], "y": [4594010.0]}).to_csv(tmp_path / "wells.csv", index=False)
    outs = []
    for i in (1, 2):
        assert _run(cp, "--features", stack, "--out", tmp_path / f"o{i}", "--model", "pit", "--cutoff", 0.0,
                    "--k-per-km2", 2000, "--known-wells", tmp_path / "wells.csv") == 0
        rd = _only_run(tmp_path / f"o{i}")
        outs.append((rd / "candidates.csv").read_bytes())
        assert (rd / "trust_statement.md").exists() and (rd / "_PROVENANCE.json").exists()
    assert outs[0] == outs[1], "T4: same input must give identical candidates"
    assert len(pd.read_csv(tmp_path / "o1" / _only_run(tmp_path / "o1").name / "candidates.csv")) >= 1
    import torch
    torch.save({"state_dict": {}}, tmp_path / "pit1" / "best.pt")            # tampered checkpoint, exit 3
    assert _run(cp, "--features", stack, "--out", tmp_path / "o3", "--model", "pit") == 3
    assert _run(cp, "--features", stack, "--out", tmp_path / "o4", "--model", "pit", "--res", 1.0) == 2


def test_features_crs_checked_against_declared(tmp_path):
    """7.4-02. The stack CRS is checked against the declared CRS and metre units, not against itself."""
    cp, _ = _models(tmp_path)
    feet = _stack(tmp_path / "feet.tif", "EPSG:2272")                        # 0.5 ft cells pass the res check
    assert _run(cp, "--features", feet, "--out", tmp_path / "a", "--model", "pit") == 2
    assert _run(cp, "--features", feet, "--out", tmp_path / "b", "--model", "pit", "--crs", "EPSG:2272") == 2
    utm = _stack(tmp_path / "utm.tif", "EPSG:26917")
    assert _run(cp, "--features", utm, "--out", tmp_path / "c", "--model", "pit") == 2     # undeclared, refused
    assert _run(cp, "--features", utm, "--out", tmp_path / "d", "--model", "pit", "--crs", "EPSG:26917") == 0
    assert _run(cp, "--features", _stack(tmp_path / "ok.tif", CRS), "--out", tmp_path / "e", "--model", "pit") == 0
    assert _run(cp, "--features", utm, "--out", tmp_path / "f", "--model", "pit", "--crs", "not-a-crs") == 2


def test_known_wells_fail_early_and_lonlat(tmp_path):
    """7.4 minors. A NaN well is an input refusal before any prediction. lon/lat needs a declared CRS."""
    from pyproj import Transformer
    cp, _ = _models(tmp_path)
    stack = _stack(tmp_path / "stack.tif", CRS)
    pd.DataFrame({"x": [620010.0, np.nan], "y": [4594010.0, 4594011.0]}).to_csv(tmp_path / "nan.csv", index=False)
    assert _run(cp, "--features", stack, "--out", tmp_path / "a", "--model", "pit", "--known-wells", tmp_path / "nan.csv") == 2
    assert not (tmp_path / "a").exists() or not any((tmp_path / "a").rglob("*_prob.tif")), "refused before prediction"
    wx, wy = 620010.0, 4594010.0
    lon, lat = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform(wx, wy)
    pd.DataFrame({"lon": [round(lon, 10)], "lat": [round(lat, 10)]}).to_csv(tmp_path / "ll.csv", index=False)
    common = ["--features", stack, "--model", "pit", "--cutoff", 0.0, "--k-per-km2", 2000, "--known-wells", tmp_path / "ll.csv"]
    assert _run(cp, *common, "--out", tmp_path / "b") == 2
    assert _run(cp, *common, "--out", tmp_path / "c", "--known-wells-crs", "EPSG:4326") == 0
    c = pd.read_csv(_only_run(tmp_path / "c") / "candidates.csv")
    assert len(c) >= 1
    want = np.hypot(c["centroid_x"] - wx, c["centroid_y"] - wy)
    assert np.allclose(c["dist_nearest_known_m"], want, atol=0.02)


def test_budget_per_class_for_both(tmp_path):
    """User default 2026-11-06. One budget per class, 40 per km2 each. Hand oracle with AREA_KM2.
    Default both gives each class floor(40 x area) and a total of 80 per km2. A shared --k-per-km2 applies per class.
    A per-class flag that disagrees with --k-per-km2 refuses."""
    cp, _ = _models(tmp_path)
    stack = _stack(tmp_path / "stack.tif", CRS)
    assert _run(cp, "--features", stack, "--out", tmp_path / "a", "--cutoff", 0.0) == 0          # default both, K 40 each
    prov = json.loads((_only_run(tmp_path / "a") / "_PROVENANCE.json").read_text())["params"]
    assert prov["review_budget_per_km2"] == {"pit": 40.0, "pad": 40.0}
    assert prov["review_budget_total_per_km2"] == 80.0
    assert prov["classes"]["pit"]["k"] == int(np.floor(40 * AREA_KM2))
    assert _run(cp, "--features", stack, "--out", tmp_path / "b", "--cutoff", 0.0, "--k-per-km2", 2000) == 0
    prov = json.loads((_only_run(tmp_path / "b") / "_PROVENANCE.json").read_text())["params"]
    assert prov["review_budget_per_km2"] == {"pit": 2000.0, "pad": 2000.0}
    assert _run(cp, "--features", stack, "--out", tmp_path / "d", "--k-per-km2", 40, "--k-per-km2-pit", 30) == 2
    assert _run(cp, "--features", stack, "--out", tmp_path / "c", "--cutoff", 0.0,
                "--k-per-km2-pit", 3000, "--k-per-km2-pad", 1000) == 0
    rd = _only_run(tmp_path / "c")
    prov = json.loads((rd / "_PROVENANCE.json").read_text())["params"]
    assert prov["review_budget_total_per_km2"] == 4000.0
    assert prov["classes"]["pit"]["k"] == int(np.floor(3000 * AREA_KM2)) == 3
    assert prov["classes"]["pad"]["k"] == int(np.floor(1000 * AREA_KM2)) == 1
    c = pd.read_csv(rd / "candidates.csv")
    assert (c["class"] == "pit").sum() <= 3 and (c["class"] == "pad").sum() <= 1


def test_calibration_with_both_models(tmp_path):
    """7.4 minor. One calibration file per model hash. It applies to its own class only (was exit 4)."""
    cp, shas = _models(tmp_path)
    stack = _stack(tmp_path / "stack.tif", CRS)
    (tmp_path / "cal_pit.json").write_text(json.dumps({"model_sha256": shas["pit"], "x": [0.0, 1.0], "y": [0.2, 0.8]}))
    base = ["--features", stack, "--cutoff", 0.0, "--k-per-km2-pit", 2000, "--k-per-km2-pad", 2000]
    assert _run(cp, *base, "--out", tmp_path / "a", "--calibration", tmp_path / "cal_pit.json") == 0
    c = pd.read_csv(_only_run(tmp_path / "a") / "candidates.csv")
    pit, pad = c[c["class"] == "pit"], c[c["class"] == "pad"]
    assert len(pit) >= 1 and len(pad) >= 1
    assert np.allclose(pit["score_cal"], 0.2 + 0.6 * pit["score"], atol=1e-5)
    assert pad["score_cal"].isna().all()
    (tmp_path / "cal_x.json").write_text(json.dumps({"model_sha256": "f" * 64, "x": [0.0, 1.0], "y": [0.0, 1.0]}))
    assert _run(cp, *base, "--out", tmp_path / "b", "--calibration", tmp_path / "cal_x.json") == 2


def test_refused_tile_not_passed_to_builder(tmp_path, monkeypatch):
    """7.4-01. The builder receives the admitted tiles only, resolved with the builder's own resolver."""
    import _agency_cli_candidates as cli
    sys.path[:0] = [str(va.ek.REPO / "notebooks" / "wellsight_v2" / "s1_build"), str(va.ek.REPO / "notebooks" / "wellsight_v2")]
    import _build_derivatives as bd
    cp, _ = _models(tmp_path)
    lid = tmp_path / "lidar"; lid.mkdir()
    _las(lid / "good.las")
    _las(lid / "noground.las", ground_step=None)             # zero class-2 points, refused
    seen = {}
    real = subprocess.run

    def fake(cmd, *a, **k):
        if any(str(c).endswith("_build_derivatives.py") for c in cmd):
            seen["tiles"] = cmd[cmd.index("--tiles") + 1]
            return subprocess.CompletedProcess(cmd, 1, "", "stub builder")
        return real(cmd, *a, **k)

    monkeypatch.setattr(cli.subprocess, "run", fake)
    assert _run(cp, "--lidar", lid, "--out", tmp_path / "o", "--model", "pit") == 4      # stub builder fails
    rep = pd.read_csv(_only_run(tmp_path / "o") / "validity_report.csv").set_index("tile_id")
    assert rep.loc["noground", "status"] == "refuse" and rep.loc["good", "status"] != "refuse"
    got = {Path(p).resolve() for p in bd.resolve_tiles(seen["tiles"])}
    assert got == {(lid / "good.las").resolve()}
