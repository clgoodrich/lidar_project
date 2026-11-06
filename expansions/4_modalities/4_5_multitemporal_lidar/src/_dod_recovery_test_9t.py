"""S3. Signal recovery test. Inject a known terrain change into the early DEM and run the whole chain.

Purpose
    The 3,368 m2 patch threshold belongs to one spatial-null procedure and is not a physical floor (protocol
    section 11). This stage measures what the chain recovers. For each height h (0.1 to 0.5 m mean) and footprint
    area (100 to 1,000 m2), a disc of fill h is cut into the early DEM at n_sites pad sites at once, then
        1. registration   fit and remove the residual shift on stable ground (_dod_registration_check_9t.py)
        2. differencing   late minus registered early
        3. high-pass      destripe and highpass from notebooks/wellsight_v2/s7_analysis/_icp_change_classify_9t.py
        4. thresholding   the feature flag rule of _change_features_9t.py (moved copies, slope matched)
    and the share of discs flagged is the recovery rate. h = 0 gives the false-alarm rate at the same sites.
    Every disc gets its slope and its distance to the nearest survey seam (_change_seams_9t.seams).
    Limitation. The published chain registers point clouds by ICP. This chain registers DEMs. The recovery is
    therefore for the DEM chain. State that next to every number.

Inputs
    data/9t/derived/lidar_2006_2008/dem_2006_v2_9t_2m.tif, dem_2019_v2_9t_2m.tif (held)
    qgis/annotations/annotations_proj_v2.gpkg layers pad, pit_full, roads (held)
    change_controls_matched_9t.gpkg from the newest S2 run (optional. Sites are those pads when present)

Outputs (run folder expansions/4_modalities/4_5_multitemporal_lidar/results/<YYYYMMDD>_dod_recov_<hash7>/)
    change_recovery_9t.csv          one row per site, height and area (flagged, frac_changed, slope, seam distance)
    change_recovery_curve_9t.csv    recovery rate and Clopper-Pearson interval per height, area and slope class
    change_recovery_curve_9t.png    recovery against height, one line per area
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_5_multitemporal_lidar/src/_dod_recovery_test_9t.py [--n-sites 40] [--out-root DIR]
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
from _dod_shared_io import ek  # noqa: E402
import _dod_registration_check_9t as REG  # noqa: E402


def chain(early, late, transform, stable, rc, register: bool):
    """Registration, differencing, destripe and high-pass. Returns the high-passed field and the fitted shift."""
    import _icp_change_classify_9t as CC
    res = float(transform.a)
    shift = {"dx_m": 0.0, "dy_m": 0.0, "dz0_m": 0.0}
    e = early
    if register:
        r = REG.fit_shift(early, late, res, stable, int(rc["sample_cells"]), 0, float(rc["max_slope_deg"]))
        if not isinstance(r, dict):
            shift = {k: r[0][k] for k in shift}
            e = REG.apply_shift(early, res, shift["dx_m"], shift["dy_m"])
    dod = (late - e).astype(np.float32)
    return CC.highpass(CC.destripe(dod)).astype(float), shift


def seam_distance(field, res: float) -> np.ndarray:
    from scipy import ndimage as ndi
    import _change_seams_9t as SE
    sm, _ = SE.seams(field)
    if not (sm > 0).any():
        return np.full(field.shape, np.inf)
    return ndi.distance_transform_edt(sm == 0) * res


def run(cfg: dict, out_root: Path | None = None, n_sites: int | None = None, rasters=None, layers=None,
        sites_xy: np.ndarray | None = None) -> dict:
    from shapely.geometry import Point
    crs, rc, fr = cfg["crs"], cfg["recovery"], cfg["flag_rule"]
    n_sites = int(n_sites or rc["n_sites"])
    inputs = []
    if rasters is None:
        pe, pl = io.resolve(cfg["dems"]["early"]), io.resolve(cfg["dems"]["late"])
        early, T, _ = io.read_raster(pe, crs)
        late, _, _ = io.read_raster(pl, crs)
        inputs += [pe, pl]
    else:
        early, late, T = rasters
    if layers is None:
        ga = io.resolve(cfg["annotations_gpkg"])
        layers = [io.read_layer(ga, cfg[k], crs) for k in ("pad_layer", "pit_layer", "road_layer")]
        inputs.append(ga)
    res = float(T.a)
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
    run_dir = ek.new_run(io.EXP, "dod_recov", {"recovery": rc, "n_sites": len(sites_xy), "flag": params}, base=out_root,
                         why="S3 signal recovery through the whole chain (fw_4_5 section 6).")
    feat = io.feature_mask(layers, early.shape, T, 0)
    stable = ~io.feature_mask(layers, early.shape, T, int(round(cfg["registration"]["stable_buffer_m"] / res)))
    slope = io.slope_deg(late, res)
    x0, y1 = float(T.c), float(T.f)
    rr, cc_ = np.mgrid[0:early.shape[0], 0:early.shape[1]]
    X, Y = x0 + (cc_ + 0.5) * res, y1 - (rr + 0.5) * res

    rows = []
    for area in rc["areas_m2"]:
        rad = float(np.sqrt(area / np.pi))
        discs = [Point(x, y).buffer(rad, 32) for x, y in sites_xy]
        inj_mask = np.zeros(early.shape, bool)
        for x, y in sites_xy:
            inj_mask |= (X - x) ** 2 + (Y - y) ** 2 <= rad ** 2
        excl = feat | inj_mask
        from scipy import ndimage as ndi
        excl = ndi.binary_dilation(excl, iterations=int(round(40 / res)))     # 40 m clear, as _change_features_9t
        for h in [0.0] + list(rc["heights_m"]):
            hp, shift = chain(np.where(inj_mask, early - h, early), late, T, stable & ~inj_mask,
                              cfg["registration"], bool(rc["register"]))
            seam_d = seam_distance(hp, res)
            F = io.Field(hp, T, slope, excl, params, np.random.default_rng(int(fr["seed"])))
            for k, (geom, (x, y)) in enumerate(zip(discs, sites_xy)):
                f = F.flag(geom)
                r_, c_ = int((y1 - y) // res), int((x - x0) // res)
                rows.append({"site": k, "x": x, "y": y, "area_m2": area, "height_m": h,
                             "assessable": f is not None, "flagged": bool(f["changed"]) if f else None,
                             "frac_changed": f["frac_changed"] if f else np.nan,
                             "median_dz_m": f["med"] if f else np.nan,
                             "slope_deg": f["slope"] if f else float(slope[r_, c_]) if 0 <= r_ < slope.shape[0] and 0 <= c_ < slope.shape[1] else np.nan,
                             "seam_dist_m": float(seam_d[r_, c_]) if 0 <= r_ < seam_d.shape[0] and 0 <= c_ < seam_d.shape[1] else np.nan,
                             "shift_dx_m": shift["dx_m"], "shift_dy_m": shift["dy_m"]})
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
    ek.write_provenance(run_dir, inputs=inputs, outputs=[csv, ccsv, png], params={"recovery": rc, "flag": params},
                        seeds={"sites": rc["seed"], "flag": fr["seed"]})
    return {"run_dir": run_dir, "csv": csv, "curve": cv}


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
    ax.set_title("Recovery through the DEM chain", fontsize=10)
    ax.legend(title="footprint", fontsize=8)
    fig.tight_layout()
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--n-sites", type=int, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    r = run(io.load_config(a.config), a.out_root, a.n_sites)
    print(r["curve"][r["curve"].slope_class == "all"].to_string(index=False))


if __name__ == "__main__":
    main()
