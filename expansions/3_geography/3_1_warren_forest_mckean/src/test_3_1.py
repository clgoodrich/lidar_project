"""Smoke tests for 3.1 (and the shared transfer library) on tiny synthetic data.

Seconds, no GPU, no network. Run
    python -m pytest -q expansions/3_geography/3_1_warren_forest_mckean/src/test_3_1.py -p no:cacheprovider
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
import _geo_xfer_lib as xl  # noqa: E402

ek = xl.ek
X0, Y0 = 600000.0, 4600000.0


def _blocks(n=4, size=100.0):
    b = xl.make_blocks((X0, Y0, X0 + n * size, Y0 + n * size), size=size)
    b["eligible"] = True
    return b


def _squares(centres, half=2.0, crs=ek.DST_CRS):
    import geopandas as gpd
    from shapely.geometry import box
    return gpd.GeoDataFrame({"truth_id": np.arange(len(centres))},
                            geometry=[box(x - half, y - half, x + half, y + half) for x, y in centres], crs=crs)


def test_blocks_cover_and_roles():
    from shapely.geometry import box
    b = _blocks(8)
    cov = xl.cover_fraction(b, box(X0, Y0, X0 + 750, Y0 + 800))
    assert cov.min() == pytest.approx(0.5) and cov.max() == 1.0
    b["strat"] = b.ix % 3
    r, meta = xl.assign_roles(b, seed=1, buffer_m=150, min_adapt_km2=0.05, strat_col="strat")
    assert not meta["adaptation_dropped"]
    ad = r[r.role == "adaptation"].geometry.union_all()
    assert r[r.role.isin(["test", "audit"])].geometry.distance(ad).min() >= 150
    r2, m2 = xl.assign_roles(b, seed=1, buffer_m=150, min_adapt_km2=100.0)
    assert m2["adaptation_dropped"] and "adaptation" not in set(r2.role)
    r3, _ = xl.assign_roles(b, seed=1, buffer_m=150, min_adapt_km2=0.05, strat_col="strat")
    assert r3.role.tolist() == r.role.tolist()          # same seed, same roles


def test_match_iou_one_to_one_and_duplicates():
    t = _squares([(X0 + 10, Y0 + 10), (X0 + 50, Y0 + 50)])
    c = _squares([(X0 + 10, Y0 + 10), (X0 + 10.5, Y0 + 10), (X0 + 80, Y0 + 80)])
    c["score"] = [0.5, 0.9, 0.7]
    c["cand_id"] = [0, 1, 2]
    m = xl.match_iou(t, c)
    assert m.notna().sum() == 1                          # the second blob on pit 0 is a duplicate
    # G-03. Pairs are taken in score order (ek.policy_for match_order). Blob 1 (score 0.9, IoU 0.78) wins
    # over the exact overlap (score 0.5). The pre-fix IoU-order matcher picked blob 0.
    assert m.isna().iloc[0] and m.iloc[1] == 0


def test_score_area_matches_toolkit_and_counts_empty_blocks():
    b = _blocks(2)
    t = _squares([(X0 + 20, Y0 + 20), (X0 + 120, Y0 + 20), (X0 + 20, Y0 + 120)])
    c = _squares([(X0 + 20, Y0 + 20), (X0 + 120, Y0 + 20), (X0 + 150, Y0 + 150)])
    c["score"] = [0.9, 0.2, 0.8]
    s, per, sc, st = xl.score_area(c, t, b, k_per_km2=50.0)      # 0.04 km2 -> K = 2
    assert s["k"] == 2 and s["hits"] == 1 and s["n_truth"] == 3    # kept 0.9 (hit) and 0.8 (decoy)
    assert len(per) == 4 and per.n_truth.sum() == 3 and (per.n_truth == 0).sum() == 1
    assert st.found.sum() == 1


def test_diff_and_permutation_note():
    tgt = [(8, 10)] * 10
    ref = [(9, 10)] * 50
    d = xl.diff_vs_reference(tgt, ref, margin=0.05, B=200, seed=0, gate="warren")
    assert d["diff"] == pytest.approx(-0.1) and "permutation_p" in d
    assert d["decision"] == "failure"
    with pytest.raises(ValueError, match="margin is required"):
        xl.diff_vs_reference(tgt, ref, margin=None, B=50)
    assert xl.diff_vs_reference(tgt, ref, margin=0.05, B=50)["decision"] == "not gated (secondary or sensitivity)"
    assert xl.density_scaled_k(40, 30, 15) == pytest.approx(20)


def test_candidates_from_prob_and_score_transfer(tmp_path):
    from rasterio.transform import from_origin
    import _xfer_score_k40_wfm as sk
    prob = np.zeros((400, 400), np.float32)
    centres = [(50, 50), (150, 60), (300, 300), (250, 120)]
    for r, c in centres:
        prob[r - 4:r + 4, c - 4:c + 4] = 0.8
    tf = from_origin(X0, Y0 + 200, 0.5, 0.5)
    cands = xl.candidates_from_prob(prob, tf, policy=xl.policy("pit"))
    assert len(cands) == 4 and np.allclose(cands.score, 0.8)
    xy = [(X0 + (c + 0.0) * 0.5, Y0 + 200 - (r + 0.0) * 0.5) for r, c in centres[:3]]
    truth = _squares(xy, half=2.0)
    b = _blocks(2)
    b["ix"], b["iy"] = b.ix, b.iy
    cands["cand_id"] = np.arange(len(cands))
    ref = pd.DataFrame({"block_id": range(30), "hits": 9, "hits_k30": 8, "n_truth": 10, "area_km2": 0.14})
    res, per, sc, st = sk.score_transfer(cands, truth, b, ref, margin=0.1, B=100, seed=0, superblock_side=2)
    assert res["primary"]["n_truth"] == 3 and res["primary"]["k"] == 2 and res["primary"]["hits"] == 2
    assert {"k30", "density_scaled", "superblock", "calibration", "reference"} <= set(res)
    for key in ("k30", "density_scaled", "superblock"):           # secondaries are reported, never gated
        assert res[key]["decision"] == "not gated (secondary or sensitivity)"


def test_defaults_margin_and_family():
    """take defaults 2026-11-06. Margin 0.03 per arm, Holm over warren, mckean, forest, max_undefined 0."""
    cfg = xl.load_config(HERE.parent / "config_3_1.json")
    assert cfg["margin_delta"] == {"warren": 0.03, "mckean": 0.03, "forest": 0.03}
    assert cfg["multiplicity"]["method"] == "holm" and cfg["multiplicity"]["max_undefined"] == 0.0
    assert cfg["multiplicity"]["family"] == ["warren", "mckean", "forest"]
    c2 = xl.load_config(HERE.parents[2] / "3_2_appalachian_states" / "src" / "config_3_2.json")
    assert set(c2["margin_delta"].values()) == {0.03}
    assert c2["multiplicity"]["family"] == ["ny_alg", "oh_wash", "ky_lee", "wv_ple"]


def test_primary_holm_family_of_three():
    """A clear pass alone (share 0) stays a success in a family of three. A share between alpha/(2m) and
    alpha/2 is success alone and inconclusive in the family of three until the family step."""
    tgt = [(9, 10)] * 40
    ref = [(9, 10)] * 40
    d = xl.diff_vs_reference(tgt, ref, margin=0.03, B=200, seed=0, gate="warren",
                             family=["warren", "mckean", "forest"])
    assert d["holm_input"]["p_one_sided"] == 0.0 and d["decision"] == "success"
    h = xl.hg.holm_partial(0.012, -0.02, 0.05, 0.03, "noninferiority", 3)
    assert h[0] == "inconclusive"
    assert xl.hg.holm_partial(0.012, -0.02, 0.05, 0.03, "noninferiority", 1)[0] == "success"


def test_las_header_and_ground_grid(tmp_path):
    import laspy
    hdr = laspy.LasHeader(point_format=6, version="1.4")
    hdr.offsets = [X0, Y0, 0]
    hdr.scales = [0.01, 0.01, 0.01]
    from pyproj import CRS
    hdr.add_crs(CRS.from_epsg(6346))
    las = laspy.LasData(hdr)
    rng = np.random.default_rng(0)
    n = 4000
    las.x = X0 + rng.uniform(0, 9.9, n)
    las.y = Y0 + rng.uniform(0, 9.9, n)
    las.z = rng.uniform(300, 301, n)
    las.classification = np.where(np.arange(n) % 2 == 0, 2, 1).astype(np.uint8)
    p = tmp_path / "t.las"
    las.write(str(p))
    h = xl.las_header(p)
    assert h["n_points"] == n and h["crs_epsg"] == 6346 and h["las_version"] == "1.4"
    g, tf, info = xl.ground_grid([p], (X0, Y0, X0 + 10, Y0 + 10), 0.5)
    assert g.sum() == n // 2 and info[0]["n_class"] == n // 2
    b = xl.make_blocks((X0, Y0, X0 + 10, Y0 + 10), size=5)
    dens, void = xl.grid_stats_per_block(b, g, tf, 0.5)
    assert dens.sum() * 25 == pytest.approx(n // 2)
    assert (void < 0.5).all()


def test_annotation_package_and_agreement(tmp_path):
    import _xfer_annot_tools_wfm as at
    b = _blocks(2)
    b["role"] = ["test", "test", "audit", "test"]
    b["recheck"] = [True, False, False, True]
    gp, log, n = at.build_package(b, tmp_path / "pkg", "syn")
    assert n == 3 and gp.exists() and log.exists()
    (tmp_path / "pkg2").mkdir()
    (tmp_path / "pkg2" / "pit_prob_x.tif").write_text("x")
    with pytest.raises(AssertionError):
        at.build_package(b, tmp_path / "pkg2", "syn")
    a1 = _squares([(X0 + 20, Y0 + 20), (X0 + 30, Y0 + 30), (X0 + 120, Y0 + 120)])
    a2 = _squares([(X0 + 20, Y0 + 20), (X0 + 120.5, Y0 + 120)])
    res = at.agreement(a1, a2, b)
    assert res["matched"] == 2 and res["recall_b_vs_a"] == pytest.approx(2 / 3)


def test_projected_width_small():
    import _xfer_projected_width_wfm as pw
    ref = pd.DataFrame({"hits": [9, 8, 10, 7] * 10, "n_truth": [10] * 40, "area_km2": 0.14})
    r0, phi, rho = pw.dispersion(ref)
    assert 0.8 < r0 < 0.9 and phi > 0
    g = {"n_blocks": [10, 40], "densities_per_km2": [30], "cluster_sizes": [1, 3]}
    tab = pw.projected_grid(list(zip(ref.hits, ref.n_truth)), r0, phi, g, reps=5, B=50, seed=1, block_km2=0.14,
                            margin=0.1)
    assert len(tab) == 4
    w10 = tab[(tab.n_test_blocks == 10) & (tab.cluster_size == 1)].median_width.iloc[0]
    w40 = tab[(tab.n_test_blocks == 40) & (tab.cluster_size == 1)].median_width.iloc[0]
    assert w40 < w10


def test_post_build_stack_and_channel_check(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    import _xfer_build_derivs_wfm as bd
    from _common import write_tif
    ch = ["lrm_25", "lrm_5", "slope", "tpi_05", "openness_pos", "openness_neg", "roughness_11"]
    tf = from_origin(X0, Y0 + 20, 0.5, 0.5)
    dem = (300 + np.add.outer(np.arange(40), np.arange(40)) * 0.01).astype(np.float32)
    write_tif(tmp_path / "dem_s.tif", dem, transform=tf, crs=ek.DST_CRS)
    write_tif(tmp_path / "ground_density_s.tif", (np.arange(1600).reshape(40, 40) % 3).astype(np.uint16),
              transform=tf, crs=ek.DST_CRS, dtype="uint16", nodata=0)
    for c in ch[:-1]:
        write_tif(tmp_path / f"{c}_s.tif", dem * 0 + 1, transform=tf, crs=ek.DST_CRS)
    ref = tmp_path / "ref.tif"
    with rasterio.open(ref, "w", driver="GTiff", width=40, height=40, count=7, dtype="float32", crs=ek.DST_CRS,
                       transform=tf) as d:
        for i, c in enumerate(ch, 1):
            d.set_band_description(i, c)
    rec = bd.post_build(tmp_path, "s", ch, ref)
    assert rec["void_frac"] == pytest.approx(534 / 1600, abs=1e-3)
    xl.check_channels(Path(rec["features"]), ch)
    with pytest.raises(AssertionError):
        xl.check_channels(Path(rec["features"]), ch[::-1])


def test_predict_array_cpu():
    import torch
    from _dl import UNet
    torch.manual_seed(0)
    m = UNet(in_ch=7, n_classes=3, base=8)
    p = xl.predict_array(m, np.random.default_rng(0).normal(size=(7, 48, 48)).astype(np.float32),
                         np.zeros(7, np.float32), np.ones(7, np.float32), patch=32, overlap=8, n_classes=3)
    assert p.shape == (3, 48, 48) and np.allclose(p.sum(0), 1, atol=1e-4)


def test_config_paths_resolve_without_literals():
    cfg = xl.load_config(HERE.parent / "config_3_1.json")
    ctx = xl.area_ctx(cfg, "warren", mkdirs=False)
    assert "warren_sheffield" in ctx["tiles_pattern"]
    with pytest.raises(xl.MissingInput):
        xl.assumed_path(cfg, "truth", "warren")
    assert json.loads(json.dumps(cfg))["k_per_km2"] == 40.0


# ----------------------------------------------------------------------------- review 2026-11-06 regressions
def _write_prob(path, arr, tf, crs=ek.DST_CRS, dtype="float32"):
    import rasterio
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype=dtype,
                       crs=crs, transform=tf, nodata=-1.0 if dtype == "float32" else 255) as d:
        d.write(arr.astype(dtype), 1)
    return path


def test_g03_same_fixture_as_3_0():
    """G-03. The 3.0 A/B fixture (A score 0.9 IoU 0.6, B score 0.5 IoU 0.9, K = 1) gives recall 1.0 in 3.1.
    The pre-fix 3.1 IoU-order matcher gave 0.0."""
    import geopandas as gpd
    from shapely.geometry import box
    truth = gpd.GeoDataFrame({"truth_id": [5]}, geometry=[box(X0, Y0, X0 + 10, Y0 + 10)], crs=ek.DST_CRS)
    cands = gpd.GeoDataFrame({"score": [0.9, 0.5]}, geometry=[box(X0, Y0, X0 + 6, Y0 + 10), box(X0, Y0, X0 + 10, Y0 + 9)],
                             crs=ek.DST_CRS)
    blocks = gpd.GeoDataFrame({"block_id": [0]}, geometry=[box(X0, Y0, X0 + 100, Y0 + 100)], crs=ek.DST_CRS)
    s, per, sc, st = xl.score_area(cands, truth, blocks, k_per_km2=100.0)
    assert s["k"] == 1 and s["recall"] == 1.0
    assert s["policy_hash"] == ek.policy_for("pit")["policy_hash"]


@pytest.mark.parametrize("x_start,width", [(50, 100), (20, 160), (5, 250), (60, 330)])
def test_f03_seam_blob_matches_whole_raster_oracle(tmp_path, x_start, width):
    """F03. A 20 m tall blob crossing block seams must come out as ONE candidate, identical to extraction on
    the whole raster (oracle), with area width x 20 m. The pre-fix blockwise reader gave one clipped
    copy per block (for 100 x 20 m: two 1,800 m2 candidates)."""
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.geometry import box
    res, W, H = 0.5, 800, 200                                   # 400 m x 100 m raster
    tf = from_origin(X0, Y0 + 100, res, res)
    p = np.zeros((H, W), np.float32)
    p[int(40 / res):int(60 / res), int(x_start / res):int((x_start + width) / res)] = 0.8
    path = _write_prob(tmp_path / "p.tif", p, tf)
    blocks = gpd.GeoDataFrame({"block_id": [0, 1, 2, 3]},
                              geometry=[box(X0 + i * 100, Y0, X0 + (i + 1) * 100, Y0 + 100) for i in range(4)],
                              crs=ek.DST_CRS)
    pol = xl.policy("pit")
    import _xfer_score_k40_wfm as sk
    got = sk.candidates_in_blocks(path, blocks, policy=pol)
    oracle = xl.tl.extract(p, tf, ek.DST_CRS, pol)
    oracle["block_id"] = xl.tl.assign_blocks(oracle, blocks)
    assert len(got) == len(oracle) == 1
    assert got.geometry.area.iloc[0] == pytest.approx(width * 20.0)
    assert got.geometry.iloc[0].equals(oracle.geometry.iloc[0])
    assert got.score.iloc[0] == pytest.approx(oracle.score.iloc[0])
    assert int(got.block_id.iloc[0]) == int(oracle.block_id.iloc[0])
    sub = blocks[blocks.block_id.isin([int(got.block_id.iloc[0])])]          # one block alone still sees the whole blob
    one = sk.candidates_in_blocks(path, sub, policy=pol)
    assert len(one) == 1 and one.geometry.area.iloc[0] == pytest.approx(width * 20.0)


def test_f11_feet_raster_refused(tmp_path):
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.geometry import box
    path = _write_prob(tmp_path / "ft.tif", np.zeros((10, 10), np.float32), from_origin(1000, 1000, 1.64, 1.64),
                       crs="EPSG:2272")
    b = gpd.GeoDataFrame({"block_id": [0]}, geometry=[box(1000, 980, 1010, 1000)], crs=ek.DST_CRS)
    with pytest.raises(AssertionError):
        xl.candidates_for_blocks(path, b, xl.policy("pit"))


def test_g07_low_density_stratum_scored_or_reported(tmp_path):
    """G-07. Low-density complete blocks enter the role draw (stratified apart) and the scorer reports them.
    With no low-density block the record says so instead of dropping the key."""
    import _xfer_blocks_roles_wfm as br
    import _xfer_score_k40_wfm as sk
    cfg = xl.load_config(HERE.parent / "config_3_1.json")
    b = _blocks(8)
    b["cover"] = 1.0
    b["void_frac"] = 0.3
    b["ground_per_m2"] = np.where(b.ix < 2, 1.0, 3.0)                       # 16 low-density blocks
    out, meta = br.eligibility_and_roles(b, cfg, 1.9, 150.0, seed=1, strat=None)
    low = out[out.low_density]
    assert len(low) == 16 and not low.eligible.any()
    assert (low.role == "test").sum() > 0                                     # pre-fix: all 'ineligible'
    assert set(out[out.role == "test"].stratum) == {"main", "low_density"}
    truth = _squares([(X0 + 20, Y0 + 20)])
    rec = sk.low_density_stratum(out, lambda bb: _squares([(X0 + 20, Y0 + 20)]).assign(score=0.9), truth, xl.policy())
    assert rec["status"] == "scored" and rec["n_blocks"] == int(((out.role == "test") & out.low_density).sum())
    none = out.assign(low_density=False)
    rec2 = sk.low_density_stratum(none, lambda bb: None, truth, xl.policy())
    assert rec2 == {"status": "empty", "reason": "no block falls under the density rule", "n_low_density_blocks": 0,
                    "roles": {}}


def test_p1_03_buffer_from_real_p1_writer_and_zero_refused(tmp_path):
    """P1-03. The P1 writer's JSON (assemble + write_buffer_json) is read through ek.read_buffer.
    The pre-fix reader indexed pit_buffer_m and raised KeyError. A zero buffer is refused."""
    import importlib
    import _xfer_blocks_roles_wfm as br
    sys.path.insert(0, str(ek.EXP_ROOT / "0_prerequisites" / "p1_splits_manifests" / "src"))
    bd = importlib.import_module("_split_buffer_derive_9t")
    p = bd.write_buffer_json(bd.assemble({"pit": {"buffer_m": 100.0}, "pad": "not derived"}), tmp_path / "buf.json")
    cfg = xl.load_config(HERE.parent / "config_3_1.json")
    cfg["assumed"]["derived_buffer"]["spec"] = {"abs": str(p)}
    assert br.derived_buffer(cfg, "pit", False) == (100.0, False)
    with pytest.raises(xl.MissingInput):
        br.derived_buffer(cfg, "pad", False)                                  # pad has no derived buffer
    assert br.derived_buffer(cfg, "pad", True) == (cfg["fallback_buffer_m"], True)
    with pytest.raises(ValueError, match="positive"):
        xl.assign_roles(_blocks(4), seed=1, buffer_m=0.0)


def test_las_without_crs_raises():
    import _xfer_tile_inventory_wfm as ti
    row = {"file": "x.laz", "minx": 0, "miny": 0, "maxx": 10, "maxy": 10}
    with pytest.raises(ValueError, match="no CRS"):
        ti.footprint_6346(row, None)
    with pytest.raises(ValueError, match="metres"):
        ti.footprint_6346(row, 2272)
    assert ti.footprint_6346(row, 6346).area == 100


def test_f08_lineage_and_reference_guards(tmp_path):
    """F08. Old-schema or truth-only reference tables are refused. A provisional inference record makes every
    decision descriptive while keeping the would-be decision."""
    import _xfer_score_k40_wfm as sk
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"0": {"cands": [], "n_truth": 0, "km2": 0.14}}))
    with pytest.raises(AssertionError, match="no policy stamp"):
        sk.reference_counts(old, xl.policy(), 40, 30)
    tr = tmp_path / "tr.json"
    tr.write_text(json.dumps({"0": {"cands": [], "n_truth": 1, "km2": 0.14}, "policy": xl.policy(),
                              "meta": {"footprint": "truth_bearing_blocks_only"}}))
    with pytest.raises(AssertionError, match="G-02"):
        sk.reference_counts(tr, xl.policy(), 40, 30)
    sens = tmp_path / "sens.json"
    sens.write_text(json.dumps({"0": {"cands": [], "n_truth": 1, "km2": 0.14}, "policy": ek.policy_for("pit", "sensitivity"),
                                "meta": {"footprint": "all_blocks"}}))
    with pytest.raises(AssertionError, match="policy mismatch"):
        sk.reference_counts(sens, xl.policy(), 40, 30)
    ok, why = xl.tl.confirmatory_ok({"family": "pit/unet_cv5", "lineage": "historical_cv5", "provisional": True},
                                    {"family": "pit/unet_cv5", "lineage": "historical_cv5", "provisional": True})
    res = {"primary": {"decision": "success"}, "k30": {"decision": "not gated (secondary or sensitivity)"}}
    sk.apply_lineage(res, ok, why)
    assert res["primary"] == {"decision": "descriptive", "decision_if_confirmatory": "success"}
    assert res["provisional"] is True and res["k30"]["decision"] == "not gated (secondary or sensitivity)"
