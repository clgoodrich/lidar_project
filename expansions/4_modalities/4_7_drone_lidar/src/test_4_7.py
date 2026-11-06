"""Smoke tests for 4.7 on a tiny synthetic LAS. PDAL CLI, no GPU, no network. About 30 seconds.

Run. python -m pytest -q expansions/4_modalities/4_7_drone_lidar/src/test_4_7.py -p no:cacheprovider
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
import _drone_kit_4_7 as dk  # noqa: E402

CFG = dk.load_cfg()
OX, OY = 620000.0, 4594000.0


def _las(path: Path, n=12000, seed=0, mislabel=0.0):
    """Ground on a gentle plane, canopy 2 to 10 m above it. mislabel = share of canopy points labelled ground (2),
    a vendor error that a rung keeping the native class would inherit."""
    import laspy
    import pyproj
    h = laspy.LasHeader(point_format=6, version="1.4")
    h.scales, h.offsets = [0.01] * 3, [OX, OY, 0]
    h.add_crs(pyproj.CRS.from_epsg(6346))
    rng = np.random.default_rng(seed)
    las = laspy.LasData(h)
    las.x, las.y = OX + rng.uniform(0, 60, n), OY + rng.uniform(0, 60, n)
    ground = rng.random(n) < 0.4
    las.z = 300 + 0.05 * (las.x - OX) + rng.normal(0, 0.03, n) + np.where(ground, 0.0, rng.uniform(2, 10, n))
    cls = np.where(ground, 2, 1)
    cls[~ground & (rng.random(n) < mislabel)] = 2
    las.classification = cls.astype(np.uint8)
    las.return_number = np.ones(n, np.uint8)
    las.number_of_returns = np.ones(n, np.uint8)
    las.write(str(path))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    import geopandas as gpd
    t = tmp_path_factory.mktemp("d47")
    raw = t / "raw"
    raw.mkdir()
    _las(raw / "syn.las")
    sites = gpd.GeoDataFrame({"site_id": [f"s{i}" for i in range(6)], "hillside": ["A"] * 3 + ["B"] * 3, "confirmed": False},
                             geometry=gpd.points_from_xy(OX + 10 + 8 * np.arange(6), OY + 30 + np.zeros(6)), crs=CFG["crs"])
    sites.to_file(raw / "sites.gpkg")
    meta = {k: "x" for k in CFG["inputs"]["provenance"]["schema"]}
    meta.update(n_sites=6, site_selection="located from lidar hillshade", sites_confirmed=None)
    (raw / "meta.json").write_text(json.dumps(meta))
    return t, raw


def test_provenance(built):
    import _drone_provenance_oc as s1
    t, raw = built
    assert s1.main(["--meta", str(raw / "meta.json"), "--las-dir", str(raw), "--sites", str(raw / "sites.gpkg"), "--out", str(t)]) == 0
    r = json.loads((t / "drone_lidar_provenance_oc.json").read_text())["check"]
    assert r["crs_ok"] and r["sites_match"] and r["conditional_on_visibility"]
    assert r["missing_fields"] == ["sites_confirmed"]


def test_ingest_thin_stack_curve(built):
    import _drone_density_curve_oc as s5
    import _drone_ingest_density_oc as s2
    import _drone_rung_stack_oc as s4
    import _drone_thin_ladder_oc as s3
    import _drone_vs_airborne_oc as s6
    import rasterio
    from rasterio.transform import from_origin
    t, raw = built
    las = raw / "syn.las"
    assert s2.main(["--las", str(las), "--sites", str(raw / "sites.gpkg"), "--out", str(t / "native")]) == 0
    dj = t / "native" / "syn_density_oc.json"
    d = json.loads(dj.read_text())
    assert 1.0 < d["native_ground_ppsm"] < 1.8 and 0.0 < d["void_fraction"] < 0.5
    assert s3.main(["--las", str(las), "--density-json", str(dj), "--rates", "1.0", "0.5", "0.1", "--seeds", "2",
                    "--out", str(t / "thin")]) == 0
    lad = pd.read_csv(t / "thin" / "syn_ladder_oc.csv")
    assert len(lad) == 5 and lad.positions_ok.all() and lad.nested_ok.all()
    assert (lad.n_ground_native_class == lad.target_ground).all() and (lad.reclassified == "smrf").all()
    half = lad[lad.rate == 0.5]
    # SMRF ground on a clean cloud is close to the native ground, so the retained share stays near the rate
    assert np.allclose(half.retained_ground_share, 0.5, atol=0.05)
    # same seed reproduces, different seed differs
    import laspy
    a = laspy.read(half.path.iloc[0]); b = laspy.read(half.path.iloc[1])
    assert not np.array_equal(np.sort(a.X), np.sort(b.X))
    again = t / "again.las"
    dk.run_pdal(s3.thin_pipeline(las, again, int(half.n_ground.iloc[0]), int(half.n_nonground.iloc[0]), int(half.seed.iloc[0]), 2),
                label="again", tmp_dir=t, verbose=False)
    assert np.array_equal(np.sort(a.X), np.sort(laspy.read(str(again)).X))
    assert s4.main(["--ladder", str(t / "thin" / "syn_ladder_oc.csv"), "--dem-only", "--out", str(t / "stacks")]) == 0
    rg = pd.read_csv(t / "thin" / "syn_rungs_oc.csv")
    assert rg.groupby("rate").void_fraction.mean().is_monotonic_decreasing
    # synthetic probability rasters: hits fade with thinning
    sites = pd.DataFrame({"x": OX + 10 + 8 * np.arange(6), "y": OY + 30.0})
    probs = []
    for r in rg.itertuples():
        p = np.zeros((120, 120), "float32")
        n_hit = {1.0: 6, 0.5: 4, 0.1: 1}[r.rate]
        for x, y in sites.values[:n_hit]:
            i, j = int((OY + 60 - y) / 0.5), int((x - OX) / 0.5)
            p[i - 3:i + 3, j - 3:j + 3] = 0.8
        f = t / f"prob_{r.sfx}.tif"
        with rasterio.open(f, "w", driver="GTiff", width=120, height=120, count=1, dtype="float32", crs=CFG["crs"],
                           transform=from_origin(OX, OY + 60, 0.5, 0.5)) as ds:
            ds.write(p, 1)
        probs.append(str(f))
    rg["prob"] = probs
    rg.to_csv(t / "rungs_prob.csv", index=False)
    assert s5.main(["--rungs", str(t / "rungs_prob.csv"), "--density-json", str(dj), "--sites", str(raw / "sites.gpkg"),
                    "--B", "200", "--k-per-km2", "3000", "--out", str(t / "res")]) == 0
    cv = pd.read_csv(t / "res" / "drone_density_curve_oc.csv")
    assert cv.recall.iloc[0] == 1.0 and cv.recall.iloc[-1] < cv.recall.iloc[0]
    meta = json.loads((t / "res" / "drone_density_curve_oc.json").read_text())
    pt = meta["thresholds"]["ppsm_at_0.90_of_native"]["point"]
    assert cv.ground_ppsm.min() < pt < cv.ground_ppsm.max()
    assert (t / "res" / "drone_density_curve_oc.png").exists()
    (t / "air.json").write_text(json.dumps({"recall": 0.7, "lo": 0.6, "hi": 0.8}))
    assert s6.main(["--curve", str(t / "res" / "drone_density_curve_oc.csv"), "--airborne", str(t / "air.json"),
                    "--provenance", str(t / "drone_lidar_provenance_oc.json"), "--out", str(t / "res")]) == 0


def _xyz(path):
    import laspy
    t = laspy.read(str(path))
    return set(zip(np.asarray(t.X).tolist(), np.asarray(t.Y).tolist(), np.asarray(t.Z).tolist()))


def test_ladder_nested_and_reclassified(tmp_path):
    """Review 4.7-01. A vendor cloud with 50 % of canopy labelled ground. Each rung must reclassify, so its ground
    count follows the true ground (about 0.4 n x rate), not the native label (about 0.7 n x rate). Rungs must nest."""
    import _drone_thin_ladder_oc as s3
    n = 12000
    las = tmp_path / "bad.las"
    _las(las, n=n, seed=4, mislabel=0.5)
    info = dk.las_info(las)
    rng = np.random.default_rng(4)
    true_ground = int((rng.random(n) < 0.4).sum())          # the same draw _las made first
    assert info["n_ground"] > 1.5 * true_ground                # the native label is badly inflated
    df = s3.ladder(las, tmp_path / "thin", [0.5, 0.25], 2, 7, 2, 3600.0, dk.load_cfg()["ladder"]["reclass"])
    for r in df.itertuples():
        assert abs(r.n_ground - r.rate * true_ground) < 0.15 * r.rate * true_ground, (r.rate, r.n_ground, true_ground)
    # nesting checked independently on the files. Same seed index, lower rung inside higher rung
    for k in (0, 1):
        q, h = (df[(df.rate == v) & (df.seed_idx == k)].path.iloc[0] for v in (0.25, 0.5))
        assert _xyz(q) <= _xyz(h)
    assert _xyz(df[df.rate == 0.5].path.iloc[0]) <= _xyz(df[df.rate == 1.0].path.iloc[0])
    assert df.seed[df.rate < 1].nunique() == 2                  # one seed per seed index, shared across rungs


def test_missing_input_names_r2(tmp_path):
    import _drone_provenance_oc as s1
    with pytest.raises(FileNotFoundError, match="NETL"):
        s1.main(["--meta", str(tmp_path / "none.json"), "--out", str(tmp_path)])


def test_crossing():
    import _drone_density_curve_oc as s5
    v = s5.crossing(np.array([10.0, 5.0, 1.0]), np.array([1.0, 0.95, 0.5]), 0.90)
    assert 1.0 < v < 5.0


def test_smrf_defaults_2026_11_06():
    """Default accepted 2026-11-06. SMRF parameters are the PDAL filters.smrf defaults (cell 1, slope 0.15,
    window 18, threshold 0.5, scalar 1.25, from the PDAL documentation) and reach the pipeline unchanged."""
    import _drone_thin_ladder_oc as s3
    rc = dk.load_cfg()["ladder"]["reclass"]
    want = {"cell": 1.0, "slope": 0.15, "window": 18.0, "threshold": 0.5, "scalar": 1.25}
    assert {k: rc[k] for k in want} == want and rc["method"] == "smrf"
    st = [s for s in s3.reclass_stages(rc, 2) if s["type"] == "filters.smrf"]
    assert len(st) == 1 and {k: st[0][k] for k in want} == want
