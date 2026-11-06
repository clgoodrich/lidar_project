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
VP_UNK = dict(VP, void_obstacle="unknown")          # the pre-2026-11-06 rule, kept as a sensitivity


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
    assert r["vis"][C, C + 30] == 255                                 # no DEM value at the target, nodata
    assert r["vis"][C + 5, C + 5] == V.UNKNOWN and r["n_void_unknown"] == 1   # void target, unobserved ground
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
    cu = V.cumulative(g, [OBS, xy(C, C + 60)], 90, "O0", vp=VP)
    assert np.nanmax(cu["count"]) == 2 and cu["count"][C, C + 40] == 1 and cu["n_unknown"] == 0


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


# ----------------------------------------------------------------------------- 2026-11-06 review fixes
# Expected values below come from the geometry of each set-up, not from agreement between profile and sweep.
def _strip(kind: str):
    """Flat ground. Column C + 20 is unobserved over the full height: NaN DEM, or void (no ground return)."""
    dem = np.zeros((N, N))
    void = np.zeros((N, N), bool)
    if kind == "nan":
        dem[:, C + 20] = np.nan
    else:
        void[:, C + 20] = True
    return grid(dem, void=void if kind == "void" else None)


@pytest.mark.parametrize("kind", ["nan", "void"])
def test_unobserved_strip_gives_unknown(kind):
    """F13 / 6.6-02. On flat ground nothing known can block. The only thing between observer and target is
    unobserved terrain, so the honest answer is unknown. Pre-fix both implementations said visible."""
    g = _strip(kind)
    vp = VP_UNK                     # NaN is unknown under both void rules. The void case tests the old rule
    p = V.los_profile(g, OBS, xy(C, C + 40), "O0", vp=vp)
    assert p["state"] == "unknown" and p["visible"] is None and p["p_visible"] is None
    assert V.los_profile(g, OBS, xy(C, C + 10), "O0", vp=vp)["state"] == "visible"      # strip not on the ray
    r = V.viewshed(g, OBS, 90, "O0", vp=vp)
    assert r["vis"][C, C + 40] == V.UNKNOWN and r["vis"][C, C + 10] == V.VISIBLE
    assert r["vis"][C, C - 40] == V.VISIBLE                                              # other side
    assert r["n_unknown"] > 0


def test_known_blocker_wins_over_unknown():
    """A 10 m wall at C + 10 hides C + 40 whatever the unobserved strip at C + 20 holds."""
    dem = np.zeros((N, N))
    dem[:, C + 10] = 10.0
    dem[:, C + 20] = np.nan
    g = grid(dem)
    assert V.los_profile(g, OBS, xy(C, C + 40), "O0", vp=VP)["state"] == "hidden"
    assert V.viewshed(g, OBS, 90, "O0", vp=VP)["vis"][C, C + 40] == V.HIDDEN


def test_o2_missing_canopy_is_unknown():
    dem = np.zeros((N, N))
    chm = np.zeros((N, N))
    chm[:, C + 20] = np.nan                                       # no canopy value on the ray
    g = grid(dem, dem, chm)
    p = V.los_profile(g, OBS, xy(C, C + 40), "O2", k_ext=0.1, vp=VP)
    assert p["state"] == "unknown" and p["p_visible"] is None
    r = V.viewshed(g, OBS, 90, "O2", k_ext=0.1, vp=VP)
    assert r["vis"][C, C + 40] == V.UNKNOWN and np.isnan(r["frac"][C, C + 40])


def test_cumulative_keeps_unknown_apart():
    """6.6-02. One observer west of a void strip. The cell east of the strip is unknown, not 'seen by nobody'.
    A second observer east of the strip sees it, so then it is seen once. The strip cells stay unknown."""
    g = _strip("void")
    one = V.cumulative(g, [OBS], 90, "O0", vp=VP_UNK)
    assert one["state"][C, C + 40] == V.UNKNOWN and np.isnan(one["count"][C, C + 40])
    assert one["count"][C, C - 40] == 1
    two = V.cumulative(g, [OBS, xy(C, C + 60)], 90, "O0", vp=VP_UNK)
    assert two["count"][C, C + 40] == 1 and two["state"][C, C + 40] == V.VISIBLE
    assert two["state"][C, C + 20] == V.UNKNOWN


def test_coarse_cell_mapping_matches_transform():
    """6.6 minor. 100 random points. The oracle is the coarse grid's own affine transform (floor of inverse)."""
    f = 10
    g = grid(np.zeros((N, N)))
    ctf = g.transform * g.transform.scale(f)
    rng = np.random.default_rng(5)
    pts = np.c_[X0 + rng.uniform(0, 200, 100), Y0 + N - rng.uniform(0, 200, 100)]
    got, want = [], []
    for x, y in pts:
        cv, cu = V.fine_to_coarse_vu(*g.to_vu(x, y), f)
        got.append((int(round(cv)), int(round(cu))))
        col, row = ~ctf * (x, y)
        want.append((int(np.floor(row)), int(np.floor(col))))
    assert got == want


def _noisy_track(rid, sigma, speed=1.3, dur=140, seed=0, y0=None):
    rng = np.random.default_rng(seed)
    t = np.arange(0, dur + 1, 1.0)                                   # 1 Hz
    x = X0 + 20 + speed * t
    y = np.full_like(t, (Y0 + 100) if y0 is None else y0)
    return pd.DataFrame({"route_id": rid, "t_s": t, "x": x + rng.normal(0, sigma, len(t)),
                         "y": y + rng.normal(0, sigma, len(t)), "err_m": 2.5})


@pytest.mark.parametrize("sigma", [0.3, 2.5])
def test_walk_time_noisy_1hz_track(sigma):
    """6.6-01. A walker at 1.3 m/s for 140 s on flat ground covers 182 m. Fixes at 1 Hz carry err_m 2.5.
    The modelled length and Tobler time must be within 5% of the truth. Pre-fix, sigma 0.3 gave length 0
    (every 1.3 m step is under the 2.5 m error) and sigma 2.5 inflated the length by noise."""
    cfg = V.load_config()
    g = grid(np.zeros((N, N)))
    s = WV.route_segments(g, _noisy_track("r", sigma), None, cfg["cost"], cfg["validation"])
    true_len = 1.3 * 140
    assert abs(s["length_m"] - true_len) / true_len < 0.05
    v0 = V.tobler_speed_ms(0.0, cfg["cost"])
    assert abs(s["tobler_by_group"]["all"] - true_len / v0) / (true_len / v0) < 0.05


def test_walk_time_fit_on_noisy_tracks():
    """Ten noisy routes, walkers 1.5 times slower than Tobler. The fitted multiplier is 1.5 within 5%."""
    cfg = V.load_config()
    g = grid(np.zeros((N, N)))
    v0 = V.tobler_speed_ms(0.0, cfg["cost"])
    tr = pd.concat([_noisy_track(f"r{i}", 2.5, speed=v0 / 1.5, seed=i, y0=Y0 + 20 + 15 * i) for i in range(10)])
    df, res = WV.run(cfg, tr, g, B=50)
    assert abs(res["multipliers_fit_on_calibration"]["all"] - 1.5) / 1.5 < 0.05


def test_gnss_tolerance_is_two_sided():
    """6.6 minor. A target 2 m behind a 10 m wall is hidden at the stated point and visible 3 m nearer. With a
    3 m GNSS error the call is ambiguous whichever way truth went. Pre-fix the miss was rescued as a hit and
    the hit stayed a hit, so both rows counted as agreement."""
    dem = np.zeros((N, N))
    dem[:, C + 20] = 10.0
    g = grid(dem, dem, np.zeros((N, N)))
    o, t_amb, t_clear = xy(C, C), xy(C, C + 22), xy(C, C - 40)
    rows = pd.DataFrame([
        {"obs_x": o[0], "obs_y": o[1], "tgt_x": t_amb[0], "tgt_y": t_amb[1], "visible": 0, "gnss_err_m": 3.0},
        {"obs_x": o[0], "obs_y": o[1], "tgt_x": t_amb[0], "tgt_y": t_amb[1], "visible": 1, "gnss_err_m": 3.0},
        {"obs_x": o[0], "obs_y": o[1], "tgt_x": t_clear[0], "tgt_y": t_clear[1], "visible": 1, "gnss_err_m": 3.0},
        {"obs_x": o[0], "obs_y": o[1], "tgt_x": t_clear[0], "tgt_y": t_clear[1], "visible": 0, "gnss_err_m": 3.0}])
    out = [SV.predict(g, r, "O0", 0.0, VP) for r in rows.itertuples()]
    assert [x["status"] for x in out] == ["ambiguous", "ambiguous", "scored", "scored"]
    assert [x["agree"] for x in out] == [None, None, True, False]


# ----------------------------------------------------------------------------- void obstacle model (2026-11-06)
def test_fill_void_lower_by_hand():
    z = np.array([[0.0, 100.0, 100.0, 7.0, 5.0], [100.0, 0.0, 3.0, 100.0, np.nan]])
    void = np.array([[0, 1, 1, 0, 0], [1, 0, 0, 1, 0]], bool)
    out, unres = V.fill_void_lower(z, void)
    assert out[0].tolist() == [0.0, 0.0, 0.0, 7.0, 5.0]              # min(0, 7), not the mean 3.5
    assert unres[0].tolist() == [False] * 5
    assert unres[1].tolist() == [True, False, False, True, False]   # one-sided voids (nothing observed before, NaN after)


def _void_ridge():
    """Row C. Void columns C+20..C+24 hold a 100 m DEM artefact. C+19 is observed at 0 and C+25 at 7. The target
    C+35 is the first cell of a 10 m bench. Eye 1.7 m. Target slope (10 - 1.7) / 35 = 0.237. C+25 itself gives
    (7 - 1.7) / 25 = 0.212, so it does not block. A void obstacle at 0 (the lower neighbour) does not block. At 7
    (the higher neighbour) it would block, since (7 - 1.7) / 20 = 0.265."""
    dem = np.zeros((N, N))
    void = np.zeros((N, N), bool)
    dem[:, C + 20:C + 25] = 100.0
    void[:, C + 20:C + 25] = True
    dem[:, C + 25] = 7.0
    dem[:, C + 35:C + 46] = 10.0
    return dem, void


def test_void_obstacle_takes_the_lower_neighbour():
    dem, void = _void_ridge()
    vp = dict(VP, curvature=False)
    g = grid(dem, void=void)
    tgt = xy(C, C + 35)
    p = V.los_profile(g, OBS, tgt, "O0", vp=vp)
    assert p["state"] == "visible" and p["n_unknown_obstacles"] == 0
    assert V.viewshed(g, OBS, 90, "O0", vp=vp)["vis"][C, C + 35] == V.VISIBLE
    assert V.los_profile(g, OBS, tgt, "O0", vp=dict(vp, void_obstacle="unknown"))["state"] == "unknown"
    hi = dem.copy()
    hi[:, C + 20:C + 25] = 7.0                                     # the higher neighbour, observed: it hides
    assert V.los_profile(grid(hi), OBS, tgt, "O0", vp=vp)["state"] == "hidden"
    assert V.viewshed(grid(dem, void=void), OBS, 90, "O0", vp=vp)["void_obstacle"] == "lower_neighbour"


def test_void_at_the_observer_stays_unknown():
    """The observer stands in a void patch (as on 9t). No observed sample lies before the void, so it stays unknown."""
    dem = np.zeros((N, N))
    void = np.zeros((N, N), bool)
    void[:, C - 3:C + 6] = True
    g = grid(dem, void=void)
    assert V.los_profile(g, OBS, xy(C, C + 30), "O0", vp=VP)["state"] == "unknown"
    assert V.viewshed(g, OBS, 90, "O0", vp=VP)["vis"][C, C + 30] == V.UNKNOWN


def test_void_model_is_decided_and_checked():
    assert V.load_config()["viewshed"]["void_obstacle"] == "lower_neighbour"
    with pytest.raises(SystemExit):
        V.void_model(dict(VP, void_obstacle="mean"))


def test_sweep_matches_brute_force_with_voids():
    """Random terrain with random void blobs. Sweep and profile agree on the three-state call within half a cell."""
    rng = np.random.default_rng(5)
    from scipy.ndimage import gaussian_filter
    dem = gaussian_filter(rng.normal(0, 1, (N, N)), 4) * 40
    void = gaussian_filter(rng.normal(0, 1, (N, N)), 3) > 0.06          # about a quarter of the cells
    void[C - 2:C + 3, C - 2:C + 3] = False
    g = grid(dem, void=void)
    r = V.viewshed(g, OBS, 95, "O0", vp=VP)
    cells = np.argwhere((r["vis"] != 255) & ~void)
    pick = cells[rng.choice(len(cells), 300, replace=False)]
    name = {V.VISIBLE: "visible", V.HIDDEN: "hidden", V.UNKNOWN: "unknown"}
    unresolved = 0
    for v, u in pick:
        sw = name[int(r["vis"][v, u])]
        x, y = xy(v, u)
        ok = any(V.los_profile(g, OBS, (x + dx, y + dy), "O0", vp=VP)["state"] == sw
                 for dx in (0, -0.5, 0.5) for dy in (0, -0.5, 0.5))
        unresolved += not ok
    assert unresolved == 0, unresolved
