"""Smoke tests for the 6.6 viewshed tool on synthetic terrain (S2). Seconds, CPU only, no network.
Not a well result.

Run
    python -m pytest -q expansions/6_adjacent/6_6_sar_viewshed/src/test_6_6.py -p no:cacheprovider
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from affine import Affine

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _sar_viewshed_tool as V  # noqa: E402
import _sar_viewshed_validate as SV  # noqa: E402
import _sar_walk_time_validate as WV  # noqa: E402

N = 201
C = N // 2
X0, Y0 = 600000.0, 4590000.0
TF = Affine(1.0, 0, X0, 0, -1.0, Y0 + N)
VP = V.load_config()["viewshed"]


def grid(dem, dsm=None, chm=None, void=None):
    return V.Grid(dem.astype(np.float32), None if dsm is None else dsm.astype(np.float32),
                  None if chm is None else chm.astype(np.float32), void, TF, "EPSG:6346", 1.0)


def xy(r, c):
    return X0 + c + 0.5, Y0 + N - r - 0.5


OBS = xy(C, C)


def test_plane_all_visible():
    g = grid(np.zeros((N, N)))
    r = V.viewshed(g, OBS, 90, "O0", vp=VP)
    inside = r["vis"] != 255
    assert inside.sum() > 0 and (r["vis"][inside] == 1).all()


def test_wall_hides_behind():
    dem = np.zeros((N, N))
    dem[:, C + 20] = 10.0
    r = V.viewshed(grid(dem), OBS, 90, "O0", vp=VP)
    assert r["vis"][C, C + 40] == 0 and r["vis"][C, C - 40] == 1 and r["vis"][C, C + 19] == 1
    assert V.los_profile(grid(dem), OBS, xy(C, C + 40), "O0", vp=VP)["visible"] is False


def test_hill_and_pit():
    rr, cc = np.mgrid[:N, :N]
    hill = 20 * np.exp(-((rr - C) ** 2 + (cc - C - 50) ** 2) / (2 * 6 ** 2))
    r = V.viewshed(grid(hill), OBS, 99, "O0", vp=VP)
    assert r["vis"][C, C + 70] == 0 and r["vis"][C, C + 45] == 1
    pit = np.zeros((N, N))
    pit[(rr - C) ** 2 + (cc - C - 50) ** 2 <= 25] = -5.0
    r = V.viewshed(grid(pit), OBS, 99, "O0", vp=VP)
    assert r["vis"][C, C + 46] == 0 and r["vis"][C, C + 54] == 0   # the floor is hidden by the near rim
    assert r["vis"][C, C + 57] == 1                                 # ground beyond the pit is seen again


def test_canopy_opacity_models():
    dem = np.zeros((N, N))
    chm = np.zeros((N, N))
    chm[C - 10:C + 10, C + 20:C + 26] = 15.0                       # 6 m thick block
    g = grid(dem, dem + chm, chm)
    tgt = (C, C + 40)
    assert V.viewshed(g, OBS, 90, "O0", vp=VP)["vis"][tgt] == 1
    assert V.viewshed(g, OBS, 90, "O1", vp=VP)["vis"][tgt] == 0
    r = V.viewshed(g, OBS, 90, "O2", k_ext=0.1, vp=VP)
    assert np.isclose(r["frac"][tgt], np.exp(-0.1 * 6), atol=0.05)
    p = V.los_profile(g, OBS, xy(*tgt), "O2", k_ext=0.1, vp=VP)
    assert np.isclose(p["transmission"], np.exp(-0.1 * 6), atol=0.05)


def test_sweep_matches_brute_force_on_1000_pairs():
    rng = np.random.default_rng(3)
    from scipy.ndimage import gaussian_filter
    dem = gaussian_filter(rng.normal(0, 1, (N, N)), 4) * 40
    g = grid(dem)
    r = V.viewshed(g, OBS, 95, "O0", vp=VP)
    cells = np.argwhere(r["vis"] != 255)
    pick = cells[rng.choice(len(cells), 1000, replace=False)]
    unresolved = 0
    for v, u in pick:
        sw = bool(r["vis"][v, u])
        bf = V.los_profile(g, OBS, xy(v, u), "O0", vp=VP)["visible"]
        if bf == sw:
            continue
        # half-cell tolerance: the sweep decided the cell from a sample within half a cell of its centre
        ok = any(V.los_profile(g, OBS, (xy(v, u)[0] + dx, xy(v, u)[1] + dy), "O0", vp=VP)["visible"] == sw
                 for dx in (-0.5, 0, 0.5) for dy in (-0.5, 0, 0.5))
        unresolved += not ok
    assert unresolved == 0


def test_nodata_edges_and_voids():
    dem = np.zeros((N, N))
    dem[C, C + 30] = np.nan
    void = np.zeros((N, N), bool)
    void[C + 5, C + 5] = True
    r = V.viewshed(grid(dem, void=void), OBS, 90, "O0", vp=VP)
    assert r["vis"][C, C + 30] == 255 and r["vis"][C + 5, C + 5] == 255 and r["n_void_masked"] == 1
    with pytest.raises(ValueError, match="outside"):
        V.viewshed(grid(dem), (X0 - 100, Y0), 50, "O0", vp=VP)
    r = V.viewshed(grid(np.zeros((N, N))), xy(5, 5), 50, "O0", vp=VP)       # radius past the raster edge
    assert r["vis"][0, 0] == 1 and r["n_cells"] > 0


def test_pockets_and_cumulative():
    dem = np.zeros((N, N))
    dem[:, C + 20] = 10.0
    g = grid(dem)
    r = V.viewshed(g, OBS, 90, "O0", vp=VP)
    lab, keep = V.hidden_pockets(r["vis"], 1.0, 400)
    assert len(keep) == 1 and keep[0][1] > 1000
    acc = V.cumulative(g, [OBS, xy(C, C + 60)], 90, "O0", vp=VP)
    assert acc.max() == 2 and acc[C, C + 40] == 1


def test_travel_time_tobler():
    cp = V.load_config()["cost"]
    dem = np.zeros((51, 51))
    tt, route = V.travel_time(dem, 1.0, (25, 0), np.ones((51, 51)), cp, target_vu=(25, 50))
    v0 = V.tobler_speed_ms(0.0, cp)
    assert np.isclose(tt[25, 50], 50 / v0, rtol=1e-6) and route[0] == (25, 0) and route[-1] == (25, 50)
    slope = np.tile(np.arange(51) * 0.2, (51, 1))                   # rises eastwards, 20%
    up, _ = V.travel_time(slope, 1.0, (25, 0), np.ones((51, 51)), cp)
    down, _ = V.travel_time(slope, 1.0, (25, 50), np.ones((51, 51)), cp)
    assert up[25, 50] > down[25, 0]
    m = V.landcover_multiplier(np.array([[11, 41]]), (1, 2), cp)
    assert np.isinf(m[0, 0]) and m[0, 1] == 1.4


def test_sight_validation_station_split():
    dem = np.zeros((N, N))
    dem[:, C + 20] = 10.0
    g = grid(dem, dem, np.zeros((N, N)))
    rows = []
    for s in range(8):
        for j, (dc, vis) in enumerate(((-40, 1), (40, 0), (10, 1))):
            o = xy(C + s * 3 - 12, C)
            t = xy(C + s * 3 - 12, C + dc)
            rows.append({"check_id": f"{s}-{j}", "station_id": f"st{s}", "obs_x": o[0], "obs_y": o[1], "tgt_x": t[0],
                         "tgt_y": t[1], "visible": vis, "canopy_state": "leaf_off", "gnss_err_m": 0.0})
    cfg = V.load_config()
    pr, res = SV.run(cfg, pd.DataFrame(rows), g, B=50)
    assert not set(res["stations"]["calibration"]) & set(res["stations"]["holdout"])
    m = res["results"]["O0:leaf_off"]
    assert m["agreement"] == 1.0 and m["sensitivity"] == 1.0 and m["specificity"] == 1.0
    assert "not scored" in m["gate"] and "bootstrap_note" in res


def test_walk_time_fit():
    cfg = V.load_config()
    g = grid(np.zeros((N, N)))
    v0 = V.tobler_speed_ms(0.0, cfg["cost"])
    rows = []
    for rid in range(10):
        xs = np.linspace(X0 + 10, X0 + 190, 37)
        y = Y0 + 20 + rid * 15
        t = (xs - xs[0]) / v0 * 1.5                                   # walkers are 1.5 times slower than Tobler
        rows += [{"route_id": f"r{rid}", "t_s": ti, "x": xi, "y": y, "err_m": 1.0} for xi, ti in zip(xs, t)]
    df, res = WV.run(cfg, pd.DataFrame(rows), g, B=50)
    assert np.isclose(res["multipliers_fit_on_calibration"]["all"], 1.5, rtol=1e-3)
    assert res["median_rel_err"]["point"] < 1e-3
