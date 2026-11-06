"""S3. Signal recovery test. Inject a known terrain change into the early POINTS and run the chain that built S4's field.

Purpose
    The 3,368 m2 patch threshold belongs to one spatial-null procedure and is not a physical floor (protocol
    section 11). This stage measures what the chain recovers. For each height h (0.1 to 0.5 m mean) and footprint
    area (100 to 1,000 m2), a tapered mound of mean height h is cut into the 2006 to 2008 ground points at n_sites
    pad sites at once. The points then go through the same chain as notebooks/wellsight_v2/s7_analysis/
    _change_rebuild_v2_9t.py, which wrote dod_v2_highpass_9t_2m.tif, the field S4 analyses.
        1. per-pass horizontal shift   fitted on slopes against the 2019 reference and applied per pass
        2. per-pass vertical offsets   least squares over flight-line overlaps, zero-mean gauge
        3. TIN surface                 one 2 m TIN code (L.build_dem)
        4. differencing                2019 v2 surface minus the rebuilt 2006 surface, gentle-ground median removed
        5. destripe and high-pass      _icp_change_classify_9t.destripe and highpass
        6. thresholding                the feature flag rule of _change_features_9t.py (moved copies, slope matched)
    The share of mounds flagged is the recovery rate. h = 0 gives the false-alarm rate at the same sites.
    Reproduction check. At h = 0 the chain must reproduce the held S4 field. The run records the RMS and maximum
    difference and refuses (exit 3) when the RMS exceeds recovery.reproduce_tol_m.
    Profile. A raised-cosine mound, flat to half the radius and tapering to zero at the radius. Its amplitude is
    h / TAPER_MEAN so the mean over the footprint is h. TAPER_MEAN = (5/4 - 1/pi^2) / 2 in closed form. This replaced
    a step disc and a global DEM shift on 2026-11-06 (review 4.5-01). The 2019 side holds no injection, so its held
    v2 surface is reused unchanged.
    Every mound gets its slope and its distance to the nearest survey seam.

Inputs
    data/9t/derived/lidar_2006_2008/*.laz (2006 to 2008 ground points, held), dem_2019_v2_9t_2m.tif (held)
    data/9t/derived/05/dem_9t_05.tif (2019 reference for the shift fit, read by _change_lineadj_9t.dem2019, held)
    data/9t/derived/lidar_2006_2008/dod_v2_highpass_9t_2m.tif (held, reproduction check)
    qgis/annotations/annotations_proj_v2.gpkg layers pad, pit_full, roads (held)
    change_controls_matched_9t.gpkg from the newest S2 run (optional. Sites are those pads when present)

Outputs (run folder expansions/4_modalities/4_5_multitemporal_lidar/results/<YYYYMMDD>_dod_recov_<hash7>/)
    change_recovery_9t.csv          one row per site, height and area (flagged, frac_changed, slope, seam distance)
    change_recovery_curve_9t.csv    recovery rate and Clopper-Pearson interval per height, area and slope class
    change_recovery_curve_9t.png    recovery against height, one line per area
    change_recovery_summary_9t.json reproduction check, per-run shifts and offsets, profile
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_5_multitemporal_lidar/src/_dod_recovery_test_9t.py [--n-sites 40] [--heights 0.3]
        [--areas 400] [--out-root DIR]
    Each height and area is one full 2006 rebuild (minutes). h = 0 is built once.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _dod_shared_io as io  # noqa: E402
from _dod_shared_io import ek, seam_distance  # noqa: E402,F401  (seam_distance kept importable from here)

TAPER_MEAN = (5.0 / 4.0 - 1.0 / np.pi ** 2) / 2.0     # mean of the unit raised-cosine profile over its disc


def taper(r: np.ndarray, R: float) -> np.ndarray:
    """Unit profile. 1 inside R/2, cos^2 fall-off to 0 at R, 0 outside. Divide by TAPER_MEAN for a unit mean."""
    a = R / 2.0
    t = np.clip((r - a) / a, 0.0, 1.0)
    w = np.cos(np.pi * t / 2.0) ** 2
    return np.where(r <= R, w, 0.0)


def inject(x, y, z, sites_xy, area_m2: float, h: float) -> np.ndarray:
    """2006 heights with a mound of mean height h CUT into them at every site, so 2019 minus 2006 reads +h (fill)."""
    if h == 0:
        return z
    R = float(np.sqrt(area_m2 / np.pi))
    from scipy.spatial import cKDTree
    tree = cKDTree(np.c_[x, y])
    zz = z.copy()
    for sx, sy in sites_xy:
        idx = np.asarray(tree.query_ball_point([sx, sy], R), dtype=int)
        if len(idx):
            zz[idx] -= (h / TAPER_MEAN) * taper(np.hypot(x[idx] - sx, y[idx] - sy), R)
    return zz


def point_chain(x6, y6, z6, lab6, ref, d19, build_dem=None, min_pass_pts: int = 200000) -> tuple[np.ndarray, dict]:
    """Steps 1 to 5 of the module docstring, copied in order from _change_rebuild_v2_9t.main and calling its functions.
    Returns the high-passed change field and the fitted shifts and offsets."""
    import _change_lineadj_9t as L
    import _change_rebuild_v2_9t as R
    from _icp_change_classify_9t import destripe, highpass
    build_dem = build_dem or L.build_dem
    gy, gx = np.gradient(np.nan_to_num(ref, nan=np.nanmean(ref)), R.RES)
    ge, gn = gx, -gy
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    ae, an, _, _ = R.horiz_shift(x6, y6, z6, ref, ge, gn, slope)
    xs, ys, per = x6.copy(), y6.copy(), {}
    for p in np.unique(lab6):
        m = lab6 == p
        if m.sum() > min_pass_pts:
            a1, a2, _, _ = R.horiz_shift(x6[m], y6[m], z6[m], ref, ge, gn, slope, nmax=600000)
        else:
            a1, a2 = ae, an
        xs[m], ys[m] = x6[m] + a1, y6[m] + a2
        per[int(p)] = (round(a1, 4), round(a2, 4))
    off, _, _ = R.overlap_offsets(xs, ys, z6, lab6, slope, tag="S3")
    zc = z6 - np.array([off.get(p, 0.0) for p in lab6])
    d06 = build_dem(xs, ys, zc)
    dod = d19 - d06
    mk = (slope < 5.0) & np.isfinite(dod) & (np.abs(dod) < 0.5)
    dod = dod - np.median(dod[mk])
    hp = highpass(destripe(dod)).astype(float)
    return hp, {"shift_all_m": (round(ae, 4), round(an, 4)), "shift_per_pass_m": per,
                "offset_std_m": float(np.std(list(off.values()))) if off else float("nan")}


def reproduce_check(hp0: np.ndarray, held: np.ndarray | None, tol: float) -> dict:
    if held is None:
        return {"status": "not checked", "note": "no held S4 field given"}
    d = hp0 - held
    ok = np.isfinite(d)
    if ok.sum() == 0:
        return {"status": "fail", "note": "no overlapping finite cells"}
    rms, mx = float(np.sqrt(np.mean(d[ok] ** 2))), float(np.max(np.abs(d[ok])))
    nan_mismatch = int((np.isfinite(hp0) != np.isfinite(held)).sum())
    return {"status": "pass" if rms <= tol else "fail", "rms_m": rms, "max_abs_m": mx, "tol_m": tol,
            "nan_mismatch_cells": nan_mismatch}


def _load_points(cfg):
    import _change_lineadj_9t as L
    x, y, z, p, g = L.load_points()
    return x, y, z, L.passes(p, g)


def run(cfg: dict, out_root: Path | None = None, n_sites: int | None = None, points=None, surfaces=None, layers=None,
        sites_xy: np.ndarray | None = None, build_dem=None, held_field=None, heights=None, areas=None) -> dict:
    """points = (x, y, z, pass_label) of 2006 ground. surfaces = (ref_2019, d19_v2, transform). held_field = S4 field."""
    from shapely.geometry import Point
    import _change_rebuild_v2_9t as R
    crs, rc, fr = cfg["crs"], cfg["recovery"], cfg["flag_rule"]
    n_sites = int(n_sites or rc["n_sites"])
    heights = list(rc["heights_m"] if heights is None else heights)
    areas = list(rc["areas_m2"] if areas is None else areas)
    inputs = []
    if points is None:
        points = _load_points(cfg)
        inputs += sorted(io.resolve(cfg["projects"]["early"]["laz_dir"]).glob(cfg["projects"]["early"]["laz_glob"]))
    if surfaces is None:
        import _change_lineadj_9t as L
        pl = io.resolve(cfg["dems"]["late"])
        d19, T, _ = io.read_raster(pl, crs)
        ref = L.dem2019()
        inputs += [pl, ek.path_for("data") / "9t/derived/05/dem_9t_05.tif"]
    else:
        ref, d19, T = surfaces
    if held_field is None and surfaces is None:
        ph = io.resolve(cfg["dems"]["dod_highpass"])
        held_field, _, _ = io.read_raster(ph, crs)
        inputs.append(ph)
    res = float(T.a)
    if (abs(float(T.c) - R.BB[0]) > 1e-6 or abs(float(T.f) - R.BB[3]) > 1e-6 or abs(res - R.RES) > 1e-9
            or d19.shape != (R.N, R.N)):
        raise ValueError(f"grid mismatch. The chain grid is BB {R.BB} at {R.RES} m ({R.N} cells). Got origin "
                         f"({T.c}, {T.f}), res {res}, shape {d19.shape}. S3 must run on the grid that built S4's field.")
    if layers is None:
        ga = io.resolve(cfg["annotations_gpkg"])
        layers = [io.read_layer(ga, cfg[k], crs) for k in ("pad_layer", "pit_layer", "road_layer")]
        inputs.append(ga)
    rng = np.random.default_rng(int(rc["seed"]))
    if sites_xy is None:
        d = io.latest_run("dod_ctrl", out_root)
        if d is not None and (d / "change_controls_matched_9t.gpkg").exists():
            import geopandas as gpd
            g = gpd.read_file(d / "change_controls_matched_9t.gpkg", layer="pads")
            inputs.append(d / "change_controls_matched_9t.gpkg")
        else:
            g = layers[0]
        pts = g.geometry.representative_point()
        sites_xy = np.c_[pts.x, pts.y]
        if len(sites_xy) > n_sites:
            sites_xy = sites_xy[rng.choice(len(sites_xy), n_sites, replace=False)]
    params = {**io.flag_params(cfg)}
    tol = float(rc.get("reproduce_tol_m", 0.01))
    run_dir = ek.new_run(io.EXP, "dod_recov", {"recovery": rc, "n_sites": len(sites_xy), "flag": params,
                                               "heights": heights, "areas": areas, "chain": "points_v2"},
                         base=out_root, why="S3 signal recovery through the S4 point chain (fw_4_5 section 6, review 4.5-01).")
    x6, y6, z6, lab6 = points
    feat = io.feature_mask(layers, d19.shape, T, 0)
    slope = io.slope_deg(d19, res)
    x0, y1 = float(T.c), float(T.f)
    rr, cc_ = np.mgrid[0:d19.shape[0], 0:d19.shape[1]]
    X, Y = x0 + (cc_ + 0.5) * res, y1 - (rr + 0.5) * res
    from scipy import ndimage as ndi

    hp0, info0 = point_chain(x6, y6, z6, lab6, ref, d19, build_dem)
    repro = reproduce_check(hp0, held_field, tol)
    chain_info = {"h0": info0}
    rows = []
    for area in areas:
        rad = float(np.sqrt(area / np.pi))
        discs = [Point(x, y).buffer(rad, 32) for x, y in sites_xy]
        inj_mask = np.zeros(d19.shape, bool)
        for x, y in sites_xy:
            inj_mask |= (X - x) ** 2 + (Y - y) ** 2 <= rad ** 2
        excl = ndi.binary_dilation(feat | inj_mask, iterations=int(round(40 / res)))   # 40 m clear, as _change_features_9t
        for h in [0.0] + heights:
            if h == 0:
                hp = hp0
            else:
                hp, chain_info[f"h{h}_a{area:g}"] = point_chain(x6, y6, inject(x6, y6, z6, sites_xy, area, h), lab6,
                                                                ref, d19, build_dem)
            seam_d = seam_distance(hp, res)
            F = io.Field(hp, T, slope, excl, params, np.random.default_rng(int(fr["seed"])))
            for k, (geom, (x, y)) in enumerate(zip(discs, sites_xy)):
                f = F.flag(geom)
                r_, c_ = int((y1 - y) // res), int((x - x0) // res)
                inside = 0 <= r_ < slope.shape[0] and 0 <= c_ < slope.shape[1]
                rows.append({"site": k, "x": x, "y": y, "area_m2": area, "height_m": h,
                             "assessable": f is not None, "flagged": bool(f["changed"]) if f else None,
                             "frac_changed": f["frac_changed"] if f else np.nan,
                             "median_dz_m": f["med"] if f else np.nan,
                             "slope_deg": f["slope"] if f else float(slope[r_, c_]) if inside else np.nan,
                             "seam_dist_m": float(seam_d[r_, c_]) if inside else np.nan})
    tab = pd.DataFrame(rows)
    csv = run_dir / "change_recovery_9t.csv"
    tab.to_csv(csv, index=False)
    A = tab[tab.assessable].copy()
    A["slope_class"] = np.where(A.slope_deg < 15, "under_15", "15_plus")
    curve = []
    for keys, g in list(A.groupby(["height_m", "area_m2"])) + list(A.groupby(["height_m", "area_m2", "slope_class"])):
        k, n = int(g.flagged.sum()), int(len(g))
        p, lo, hi = ek.clopper_pearson(k, n)
        keys = keys if isinstance(keys, tuple) else (keys,)
        curve.append({"height_m": keys[0], "area_m2": keys[1], "slope_class": keys[2] if len(keys) > 2 else "all",
                      "n": n, "flagged": k, "rate": p, "lo": lo, "hi": hi})
    cv = pd.DataFrame(curve)
    ccsv = run_dir / "change_recovery_curve_9t.csv"
    cv.to_csv(ccsv, index=False)
    png = run_dir / "change_recovery_curve_9t.png"
    _figure(cv[cv.slope_class == "all"], png)
    summ = {"chain": "2006 points -> per-pass shift -> overlap offsets -> TIN -> DoD -> destripe -> highpass "
                     "(_change_rebuild_v2_9t). Same chain as S4's field.",
            "profile": {"shape": "raised cosine, flat to R/2, zero at R", "taper_mean": TAPER_MEAN,
                        "amplitude_over_h": 1.0 / TAPER_MEAN},
            "reproduce_check": repro, "chain_info": chain_info}
    sj = run_dir / "change_recovery_summary_9t.json"
    sj.write_text(json.dumps(summ, indent=2, default=str), encoding="utf-8")
    ek.write_provenance(run_dir, inputs=inputs, outputs=[csv, ccsv, png, sj], params={"recovery": rc, "flag": params},
                        seeds={"sites": rc["seed"], "flag": fr["seed"]}, hash_limit_mb=0)
    return {"run_dir": run_dir, "csv": csv, "curve": cv, "summary": summ}


def _figure(cv: pd.DataFrame, png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    P = ek.PALETTE  # lost/found palette, worst pair dE 21.1 deutan (dataviz validator --pairs all, CLAUDE.md)
    cols, marks = [P["blue"], P["orange"], P["dark_red"], P["charcoal"]], ["o", "s", "^", "D"]
    fig, ax = plt.subplots(figsize=(6, 4))
    for i, (a, g) in enumerate(cv.groupby("area_m2")):
        g = g.sort_values("height_m")
        ax.errorbar(g.height_m, g.rate, yerr=[g.rate - g.lo, g.hi - g.rate], color=cols[i % 4], marker=marks[i % 4],
                    capsize=3, label=f"{a:g} m2")
    ax.set_xlabel("injected mean change (m). 0 is the false-alarm rate")
    ax.set_ylabel("share of sites flagged")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Recovery through the point chain", fontsize=10)
    ax.legend(title="footprint", fontsize=8)
    fig.tight_layout()
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--n-sites", type=int, default=None)
    ap.add_argument("--heights", type=float, nargs="*", default=None)
    ap.add_argument("--areas", type=float, nargs="*", default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    r = run(io.load_config(a.config), a.out_root, a.n_sites, heights=a.heights, areas=a.areas)
    print(json.dumps(r["summary"]["reproduce_check"], indent=2))
    print(r["curve"][r["curve"].slope_class == "all"].to_string(index=False))
    if r["summary"]["reproduce_check"]["status"] == "fail":
        print("REFUSED. The h = 0 chain does not reproduce S4's field. Recovery numbers do not describe S4.")
        sys.exit(3)


if __name__ == "__main__":
    main()
