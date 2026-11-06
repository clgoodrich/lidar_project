"""S2. Matched control pads for the plugged-between-flights pads.

Purpose
    Controls are eligible pads without the intervention (protocol section 11), not ordinary terrain.
    Pool. Pads with at least one DEP well, no well plugged between the flights or inside a flight window, every well
    spudded before the end of the early window (when require_spud_before_early) and none plugged before the late flight.
    So the pad was active at the early flight and still unplugged at the late one.
    Covariates. Mean slope (late DEM), pad area, baseline roughness (std of the early DEM minus its 5 x 5 mean inside
    the pad), distance to the nearest mapped road, and distance to the nearest straight survey seam in the high-passed
    change field (seam_dist_m, fix 4.5-02 of 2026-11-06). Treated pads sat a median 36 m from a seam and controls
    220 m, so seam bias could pass for change. Standardised on treated plus pool. Infinite seam distances (no seam in
    the field) are capped at the largest finite one. Controls are also exact-matched on seam band
    (controls.seam_band_edges_m, proposed default 50 m), because a covariate in the distance alone did not stop a
    far-from-seam control being picked.
    Match. Nearest neighbour without replacement, 1 to max_controls per treated pad, inside a caliper of caliper_sd
    on every standardised covariate. Treated pads are matched in random order (seeded). Balance is reported as
    standardised mean differences before and after.

Inputs
    plug_eligible_pads_9t.csv and plug_eligible_wells_9t.csv from the newest S1 run (or --elig-dir)
    data/9t/derived/lidar_2006_2008/dem_2006_v2_9t_2m.tif, dem_2019_v2_9t_2m.tif, dod_v2_highpass_9t_2m.tif (held)
    qgis/annotations/annotations_proj_v2.gpkg layers pad, roads (held)

Outputs (run folder expansions/4_modalities/4_5_multitemporal_lidar/results/<YYYYMMDD>_dod_ctrl_<hash7>/)
    change_controls_matched_9t.gpkg   layer pads. Treated and matched control pads with match_id, role, covariates
    change_controls_balance_9t.json   SMD before and after, unmatched treated pads, pool size
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_5_multitemporal_lidar/src/_dod_controls_matched_9t.py [--elig-dir DIR] [--out-root DIR]
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


def pad_covariates(pads, early, late, transform, roads, seam_field=None) -> pd.DataFrame:
    from rasterio.features import geometry_mask
    from scipy import ndimage as ndi
    res = float(transform.a)
    slope = io.slope_deg(late, res)
    e = np.where(np.isfinite(early), early, np.nanmean(early))
    rough = early - ndi.uniform_filter(e, size=5, mode="nearest")
    rows = []
    from rasterio.transform import from_origin
    x0, y1 = float(transform.c), float(transform.f)
    H, W = early.shape
    for geom in pads.geometry:
        bx0, by0, bx1, by1 = geom.bounds
        c0, r0 = max(int((bx0 - x0) // res) - 1, 0), max(int((y1 - by1) // res) - 1, 0)
        c1, r1 = min(int(np.ceil((bx1 - x0) / res)) + 1, W), min(int(np.ceil((y1 - by0) / res)) + 1, H)
        if c1 <= c0 or r1 <= r0:
            rows.append({"slope_deg": np.nan, "rough_2006_m": np.nan})
            continue
        tr = from_origin(x0 + c0 * res, y1 - r0 * res, res, res)
        m = ~geometry_mask([geom], out_shape=(r1 - r0, c1 - c0), transform=tr, all_touched=True)
        sl, ro = slope[r0:r1, c0:c1], rough[r0:r1, c0:c1]
        ok = m & np.isfinite(ro) & np.isfinite(sl)
        rows.append({"slope_deg": float(sl[ok].mean()) if ok.any() else np.nan,
                     "rough_2006_m": float(np.nanstd(ro[ok])) if ok.sum() > 2 else np.nan})
    C = pd.DataFrame(rows, index=pads.index)
    C["area_m2"] = pads.geometry.area.to_numpy()
    if roads is not None and len(roads):
        from shapely import STRtree
        tree = STRtree(list(roads.geometry))
        C["road_dist_m"] = [float(geom.distance(roads.geometry.iloc[tree.nearest(geom)])) for geom in pads.geometry]
    else:
        C["road_dist_m"] = np.nan
    if seam_field is not None:
        sd = io.value_at(io.seam_distance(seam_field, res), transform, pads.geometry)
        fin = np.isfinite(sd)
        cap = float(np.nanmax(np.where(fin, sd, np.nan))) if fin.any() else float(max(early.shape) * res)
        C["seam_dist_m"] = np.where(np.isnan(sd), np.nan, np.minimum(sd, cap))
    else:
        C["seam_dist_m"] = np.nan
    return C


def control_pool(pads_tab: pd.DataFrame, wells_tab: pd.DataFrame, require_spud: bool, spud_field: str) -> pd.Series:
    """Boolean per pad_id. See the module docstring for the rule."""
    w = wells_tab[wells_tab.pad_id.notna()].copy()
    w["plug_date"] = pd.to_datetime(w.plug_date, errors="coerce")
    w["late_start"] = pd.to_datetime(w.late_start, errors="coerce")
    w["early_end_t"] = pd.to_datetime(w.early_end, errors="coerce")
    bad = (w.elig_class.isin(["eligible", "ambiguous"])) | (w.plug_date.notna() & (w.plug_date < w.late_start))
    if require_spud and spud_field in w:
        sp = pd.to_datetime(w[spud_field], errors="coerce")
        bad |= sp.isna() | (sp.dt.year <= 1800) | (sp >= w.early_end_t)
    bad_pads = set(w.loc[bad, "pad_id"])
    has_well = set(w.pad_id)
    return pads_tab.pad_id.map(lambda p: p in has_well and p not in bad_pads)


def match(Zt: np.ndarray, Zp: np.ndarray, k: int, caliper: float, rng, st=None, sp=None) -> list[list[int]]:
    """Greedy nearest neighbour without replacement. Returns, per treated row, pool row indices.
    st, sp are optional exact-match strata (a control must share its treated pad's stratum)."""
    used = np.zeros(len(Zp), bool)
    out = [[] for _ in range(len(Zt))]
    order = rng.permutation(len(Zt))
    for _round in range(k):
        for i in order:
            if len(out[i]) > _round:
                continue
            ok = ~used & np.all(np.abs(Zp - Zt[i]) <= caliper, axis=1)
            if st is not None:
                ok &= sp == st[i]
            if not ok.any():
                continue
            d = np.where(ok, np.linalg.norm(Zp - Zt[i], axis=1), np.inf)
            j = int(np.argmin(d))
            used[j] = True
            out[i].append(j)
    return out


def smd(a: np.ndarray, b: np.ndarray) -> float:
    s = np.sqrt((np.nanvar(a, ddof=1) + np.nanvar(b, ddof=1)) / 2) if len(a) > 1 and len(b) > 1 else np.nan
    return float((np.nanmean(a) - np.nanmean(b)) / s) if s and np.isfinite(s) and s > 0 else float("nan")


def run(cfg: dict, out_root: Path | None = None, elig_dir: Path | None = None, rasters=None, layers=None) -> dict:
    import geopandas as gpd
    crs, cc = cfg["crs"], cfg["controls"]
    pp = io.stage_file(None if elig_dir is None else Path(elig_dir) / "plug_eligible_pads_9t.csv", "dod_elig",
                       "plug_eligible_pads_9t.csv", out_root, "S1 eligible pads")
    wp = pp.parent / "plug_eligible_wells_9t.csv"
    P, Wt = pd.read_csv(pp), pd.read_csv(io.need(wp, "S1 eligible wells"))
    inputs = [pp, wp]
    hp = None
    if rasters is None:
        pe, pl = io.resolve(cfg["dems"]["early"]), io.resolve(cfg["dems"]["late"])
        early, T, _ = io.read_raster(pe, crs)
        late, _, _ = io.read_raster(pl, crs)
        inputs += [pe, pl]
        if "seam_dist_m" in cc["covariates"]:
            ph = io.resolve(cfg["dems"]["dod_highpass"])
            hp, _, _ = io.read_raster(ph, crs)
            inputs.append(ph)
    else:
        early, late, T = rasters[:3]
        hp = rasters[3] if len(rasters) > 3 else None
    if "seam_dist_m" in cc["covariates"] and hp is None:
        raise FileNotFoundError("MISSING INPUT high-passed change field for the seam_dist_m covariate. "
                                "Pass rasters=(early, late, T, highpass) or drop seam_dist_m from controls.covariates.")
    if layers is None:
        ga = io.resolve(cfg["annotations_gpkg"])
        pads, roads = io.read_layer(ga, cfg["pad_layer"], crs), io.read_layer(ga, cfg["road_layer"], crs)
        inputs.append(ga)
    else:
        pads, roads = layers
    pads = pads.merge(P[["pad_id", "complex_id", "treated", "eligible", "ambiguous", "n_wells", "first_eligible_plug"]],
                      on="pad_id", how="left", validate="one_to_one")
    ek.assert_rows(pads, len(P), "pads after S1 join")
    pads["pool"] = control_pool(P, Wt, bool(cc["require_spud_before_early"]), cfg["eligibility"]["spud_field"]).to_numpy()
    pads["treated"] = pads.treated.fillna(False).astype(bool)
    run_dir = ek.new_run(io.EXP, "dod_ctrl", cc, base=out_root, why="S2 matched controls (fw_4_5 section 6).")

    sel = pads[pads.treated | pads.pool].copy()
    C = pad_covariates(sel, early, late, T, roads, hp)
    sel = sel.drop(columns=[c for c in C.columns if c in sel]).join(C)
    cov = [c for c in cc["covariates"] if sel[c].notna().any()]
    dropped_cov = [c for c in cc["covariates"] if c not in cov]
    sel = sel.dropna(subset=cov)
    Z = (sel[cov] - sel[cov].mean()) / sel[cov].std(ddof=1).replace(0, 1)
    t_idx, p_idx = np.flatnonzero(sel.treated.to_numpy()), np.flatnonzero(sel.pool.to_numpy() & ~sel.treated.to_numpy())
    rng = np.random.default_rng(int(cc["seed"]))
    strata, edges = None, cc.get("seam_band_edges_m")
    if edges and "seam_dist_m" in cov:
        strata = np.digitize(sel.seam_dist_m.to_numpy(float), np.asarray(edges, float))
    m = match(Z.to_numpy()[t_idx], Z.to_numpy()[p_idx], int(cc["max_controls"]), float(cc["caliper_sd"]), rng,
              None if strata is None else strata[t_idx], None if strata is None else strata[p_idx])
    rows = []
    for mi, (ti, js) in enumerate(zip(t_idx, m)):
        if not js:
            continue
        rows.append({**sel.iloc[ti].to_dict(), "match_id": mi, "role": "treated"})
        rows += [{**sel.iloc[p_idx[j]].to_dict(), "match_id": mi, "role": "control"} for j in js]
    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs) if rows else gpd.GeoDataFrame(
        columns=list(sel.columns) + ["match_id", "role"], geometry="geometry", crs=crs)
    gp = run_dir / "change_controls_matched_9t.gpkg"
    out.to_file(gp, layer="pads", driver="GPKG")
    tr, pl_ = sel.iloc[t_idx], sel.iloc[p_idx]
    bal = {"n_treated": int(len(t_idx)), "n_pool": int(len(p_idx)),
           "n_treated_matched": int(sum(bool(j) for j in m)), "n_controls": int(sum(len(j) for j in m)),
           "unmatched_treated_pad_ids": [int(sel.iloc[ti].pad_id) for ti, j in zip(t_idx, m) if not j],
           "smd_before": {c: smd(tr[c].to_numpy(), pl_[c].to_numpy()) for c in cov},
           "smd_after": {c: smd(out[out.role == "treated"][c].to_numpy(float), out[out.role == "control"][c].to_numpy(float))
                         for c in cov} if len(out) else {},
           "covariates_used": cov, "covariates_dropped_all_missing": dropped_cov, "caliper_sd": cc["caliper_sd"],
           "seam_band_edges_m": edges if strata is not None else None,
           "seam_dist_median_m": {"treated": float(np.nanmedian(out[out.role == "treated"].seam_dist_m)) if len(out) else None,
                                  "control": float(np.nanmedian(out[out.role == "control"].seam_dist_m)) if len(out) else None}
           if "seam_dist_m" in out else None, "note": "Old controls (terrain clear of mapped features) are not used."}
    js = run_dir / "change_controls_balance_9t.json"
    js.write_text(json.dumps(bal, indent=2), encoding="utf-8")
    ek.write_provenance(run_dir, inputs=inputs, outputs=[gp, js], params=cc, seeds={"match": cc["seed"]})
    return {"run_dir": run_dir, "gpkg": gp, "balance": bal}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--elig-dir", type=Path, default=None, help="S1 run folder (default newest)")
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    r = run(io.load_config(a.config), a.out_root, a.elig_dir)
    print(json.dumps(r["balance"], indent=2))


if __name__ == "__main__":
    main()
