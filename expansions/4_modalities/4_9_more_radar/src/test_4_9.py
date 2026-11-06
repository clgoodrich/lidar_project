"""Smoke tests for 4.9 on tiny synthetic data. No GPU, no network. Under a minute.

Run. python -m pytest -q expansions/4_modalities/4_9_more_radar/src/test_4_9.py -p no:cacheprovider
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _sar_kit_4_9 as sk  # noqa: E402

CFG = sk.load_cfg()
X0, Y0, X1, Y1 = CFG["bbox_9t"]


def test_auc_and_holm():
    y = np.array([0, 0, 1, 1])
    assert sk.auc(y, np.array([0.1, 0.2, 0.3, 0.4])) == 1.0
    assert sk.auc(y, np.array([1, 1, 1, 1])) == 0.5
    h = sk.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert np.isclose(h["a"], 0.03) and np.isclose(h["c"], 0.06) and np.isclose(h["b"], 0.06)


def test_observability(tmp_path):
    import _sar_observability_9t as s0
    assert s0.main(["--catalogue", str(tmp_path / "none.csv"), "--out", str(tmp_path)]) == 0
    df = pd.read_csv(tmp_path / "sar_observability_by_arm_9t.csv")
    assert len(df) == 10
    coarse = dict(CFG["arms"]["A3"], res_az_m=30.0, res_rg_m=30.0)
    r = s0.observe("A3", coarse, "pit", CFG["targets"]["pit"], 1.5, 0.25)
    assert r["verdict"] == "cannot see pit at this resolution"
    assert abs(s0.speckle_sd_db(1) - 5.57) < 0.01


def _rows(n_blocks=30, per=20, seed=0, signal=1.5):
    rng = np.random.default_rng(seed)
    n = n_blocks * per
    y = (rng.random(n) < 0.2).astype(int)
    block = np.repeat(np.arange(n_blocks), per)
    x = X0 + 100 + 700 * (block % 6) + rng.uniform(0, 100, n)
    ym = Y0 + 100 + 700 * (block // 6) + rng.uniform(0, 100, n)
    df = pd.DataFrame({"row": np.arange(n), "y": y, "block": block, "x": x, "ym": ym})
    df["base:control:slope"] = rng.normal(0, 1, n) + 1.0 * y
    df["base:lidartex:rough"] = rng.normal(0, 1, n) + 0.5 * y
    df["arm:A1:VV_mean_db"] = rng.normal(0, 1, n) + signal * y
    return df


def test_power(tmp_path):
    import _sar_power_baseline_9t as s1
    df = _rows()
    df["score"] = df["base:control:slope"]
    f = tmp_path / "rows.csv"
    df.to_csv(f, index=False)
    assert s1.main(["--rows", f"{f}:score:syn", "--n-sims", "4", "--B", "20", "--out", str(tmp_path)]) == 0
    tab = pd.read_csv(tmp_path / "sar_power_by_stratum_9t.csv")
    assert set(tab.stratum) == {"all", "lidar_weak"}
    el = json.loads((tmp_path / "sar_power_eligibility_9t.json").read_text())
    assert "syn:all" in el["strata"] and el["record"] in {"proceed to purchase request", "no room, untestable at current baseline"}
    zero = tab[(tab.g == 0.0)]
    assert (zero.power <= 0.5).all()


def test_fetch_and_registration(tmp_path):
    import _sar_fetch_new_9t as s2
    import _sar_registration_9t as s3
    d = tmp_path / "src" / "X"
    d.mkdir(parents=True)
    (d / "a.bin").write_bytes(b"abc")
    man = pd.DataFrame([{"sensor": "X", "product_id": "p1", "url": "http://invalid", "filename": "a.bin",
                         "sha256": sk.ek.sha256(d / "a.bin"), "bytes": 3},
                        {"sensor": "X", "product_id": "p2", "url": "http://invalid", "filename": "b.bin", "sha256": "", "bytes": None}])
    mf = tmp_path / "man.csv"
    man.to_csv(mf, index=False)
    assert s2.main(["--manifest", str(mf), "--dest", str(tmp_path / "src"), "--dry-run"]) == 0
    rng = np.random.default_rng(0)
    rx, ry = rng.uniform(X0, X1, 12), rng.uniform(Y0, Y1, 12)
    sc = pd.DataFrame({"arm": "A1", "track": 7, "scatterer_id": range(12), "sar_x": rx + 3.0, "sar_y": ry - 2.0,
                       "ref_x": rx, "ref_y": ry, "ref_source": "survey"})
    sf = tmp_path / "sc.csv"
    sc.to_csv(sf, index=False)
    assert s3.main(["--scatterers", str(sf), "--out", str(tmp_path)]) == 0
    t = pd.read_csv(tmp_path / "sar_registration_by_track_9t.csv").iloc[0]
    assert t.shift_applied and abs(t.shift_x_m - 3.0) < 1e-9 and t.residual_max_m < 1e-6 and t.status == "ok"


def test_features_score_figure(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    import _sar_new_features_9t as s4
    import _sar_new_gain_figure_9t as s6
    import _sar_new_score_9t as s5
    df = _rows().drop(columns=["arm:A1:VV_mean_db"])
    W = H = 900
    rng = np.random.default_rng(1)
    st = rng.gamma(3, 0.01 / 3, (2, H, W))
    for r in df[df.y == 1].itertuples():
        i, j = int((Y0 + 4500 - r.ym) / 5), int((r.x - X0) / 5)
        st[:, max(0, i - 1):i + 2, max(0, j - 1):j + 2] *= 3.0
    sd = tmp_path / "A1"
    sd.mkdir()
    with rasterio.open(sd / "sar_A1_VV_stack_9t.tif", "w", driver="GTiff", width=W, height=H, count=2, dtype="float32",
                       crs=CFG["crs"], transform=from_origin(X0, Y0 + 4500, 5.0, 5.0)) as d:
        d.write(st.astype("float32"))
    rows = tmp_path / "rows.csv"
    df.to_csv(rows, index=False)
    assert s4.main(["--target", "pit", "--arm", "A1", "--rows", str(rows), "--stack-dir", str(sd),
                    "--features-out", str(sd / "feat.tif")]) == 0
    r2 = pd.read_csv(rows)
    assert "arm:A1:VV_mean_db" in r2 and "arm:A1:VV_ring_contrast_db" in r2
    assert r2.loc[r2.y == 1, "arm:A1:VV_mean_db"].median() > r2.loc[r2.y == 0, "arm:A1:VV_mean_db"].median()
    t3 = np.zeros((9, 4, 4))
    t3[0:3] = 1.0
    ha = s4.h_alpha(t3)
    assert np.allclose(ha["entropy"], 1.0)
    assert s5.main(["--target", "pit", "--arms", "A1", "--rows", str(rows), "--repeats", "1", "--B", "60",
                    "--eligibility", str(tmp_path / "none.json"), "--out", str(tmp_path)]) == 0
    g = pd.read_csv(tmp_path / "sar_new_gain_by_arm_9t.csv")
    arm = g[(g.kind == "arm") & (g.stratum == "all")].iloc[0]
    plc = g[(g.kind == "placebo") & (g.stratum == "all")].iloc[0]
    assert arm.gain > plc.gain and arm.primary
    assert s6.main(["--gain", str(tmp_path / "sar_new_gain_by_arm_9t.csv"), "--out", str(tmp_path / "fig.png")]) == 0
    assert (tmp_path / "fig.png").exists()
