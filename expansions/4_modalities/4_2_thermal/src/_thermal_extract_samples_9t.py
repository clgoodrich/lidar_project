"""4.2 stage T2. Pixel-weighted LST per site and scene, with covariates (9t). Run only if T1 passes for that sensor.

Purpose
    For every matched site (pad, clearing, forest) and every usable scene, the area-weighted LST using the
    fractional overlap of the site polygon with each pixel, the LST error where the product carries one,
    and a partial-overlap flag. Covariates per site and scene. Mean CHM, NLCD majority class, slope,
    aspect, clear-sky solar loading at the scene time (NOAA solar position on the site centroid, cosine
    of incidence on the mean slope and aspect), PRISM antecedent rain over antecedent_days, nearest leaf
    state from the leaf-state curve.
    QC (review 4.2-02 and F-note). Only scenes whose tie points passed the T1 registration limit are
    extracted. Pixels flagged by the instrument per-pixel cloud QA band are masked. A sensor without a
    QA band refuses. LST outside a physical range after scaling refuses (catches a wrong scale).
    --layer population extracts every pad and eligible clearing (for T4), --layer sites the matched set.
Inputs
    sites        <run>_thermal_match_*/thermal_matched_sites_9t.gpkg (from _thermal_match_clearings_9t.py)
    T1 summary   <run>_thermal_gate_*/thermal_gate_summary_9t.json (sensor must not be 'failure')
    scene index  expansions/4_modalities/4_2_thermal/data/raw/scene_index_<sensor>_9t.csv (assumed)
    nlcd, prism, leaf state (held, paths in config_4_2.json)
Outputs (expansions/4_modalities/4_2_thermal/results/<YYYYMMDD>_thermal_samples_<hash7>/)
    thermal_samples_by_scene_9t.csv (one row per site and scene), provenance
Run
    python expansions/4_modalities/4_2_thermal/src/_thermal_extract_samples_9t.py --sensor landsat_tirs [--sites PATH] [--gate PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _thermal_shared_io as io
from _thermal_shared_io import ek

SHORT = "thermal_samples"


def nlcd_majority(path: Path, sites) -> pd.Series:
    def mode(v):
        v = v[np.isfinite(v) & (v > 0)]
        return float(pd.Series(v).mode().iloc[0]) if len(v) else np.nan
    return io.zonal(path, sites, "site_id", fn=mode)


def antecedent_rain(prism: pd.DataFrame, day, n: int) -> float:
    d = pd.Timestamp(day).normalize().tz_localize(None)
    w = prism[(prism["date"] < d) & (prism["date"] >= d - pd.Timedelta(days=n))]
    return float(w["ppt"].sum()) if len(w) else np.nan


def leaf_state_at(leaf: pd.DataFrame, day):
    if leaf is None or leaf.empty:
        return None
    d = pd.Timestamp(day).tz_localize(None)
    i = (leaf["date"] - d).abs().idxmin()
    return leaf.loc[i, "leaf_state"]


def qa_bad(qa: np.ndarray, rule: dict) -> np.ndarray:
    """True where the instrument per-pixel QA says the LST is not usable (cloud, shadow, fill).

    rule type 'bits_clear' : bad if any listed bit is set (Landsat Collection 2 QA_PIXEL style).
    rule type 'field_in'   : bits [lo, hi] form an integer field. Good if the field value is in `good`
                             (ECOSTRESS LSTE QC mandatory flag style).
    Non-finite QA is bad."""
    fin = np.isfinite(qa)
    q = np.where(fin, qa, 0).astype(np.int64)
    t = rule.get("type")
    if t == "bits_clear":
        bad = np.zeros(q.shape, bool)
        for b in rule["bits"]:
            bad |= ((q >> int(b)) & 1).astype(bool)
    elif t == "field_in":
        lo, hi = rule["bits"]
        field = (q >> int(lo)) & ((1 << (int(hi) - int(lo) + 1)) - 1)
        bad = ~np.isin(field, rule["good"])
    else:
        raise ValueError(f"unknown QA rule type {t!r}")
    return bad | ~fin


def scene_lst(r, s_cfg: dict) -> tuple[np.ndarray, float]:
    """Scaled LST with the per-pixel cloud QA applied (F-note). Refuses when the QA band is absent or the
    scaled values are not physical temperatures (catches a wrong scale or offset). Returns (lst, share masked)."""
    qb = s_cfg.get("qa_band")
    if not qb or r.count < int(qb):
        raise RuntimeError(f"{s_cfg['name']}: no per-pixel cloud QA band (qa_band={qb!r}, file has {r.count} bands). "
                           "Scene-level cloud_frac does not mask cloud over a pad. Refusing")
    lst = r.read(s_cfg["lst_band"], masked=True).astype(float).filled(np.nan) * s_cfg["lst_scale"] + s_cfg["lst_offset"]
    bad = qa_bad(r.read(int(qb)).astype(float), s_cfg["qa_rule"])
    fin = np.isfinite(lst)
    lo, hi = s_cfg.get("lst_plausible_K", [200.0, 350.0])
    v = lst[fin & ~bad]
    if v.size and np.mean((v < lo) | (v > hi)) > 0.01:
        raise RuntimeError(f"{s_cfg['name']}: {np.mean((v < lo) | (v > hi)):.1%} of QA-clear LST outside {lo}-{hi} K "
                           f"after scale {s_cfg['lst_scale']} and offset {s_cfg['lst_offset']}. Check the sensor scaling")
    share = float(np.mean(bad[fin])) if fin.any() else 1.0
    lst[bad] = np.nan
    return lst, share


def registered_scenes(gate: dict, sensor: str) -> tuple[set[str], set[str]]:
    """Review 4.2-02. Scenes with tie points inside the limit, and the scenes dropped for registration."""
    reg = gate["sensors"][sensor].get("registration") or {}
    if reg.get("status") != "ok":
        raise RuntimeError(f"T1 has no registration check for {sensor} (tie points {reg.get('status')!r}). "
                           "T2 does not extract unregistered scenes")
    checked = set(map(str, reg.get("scenes_checked", [])))
    over = set(map(str, reg.get("scenes_over_limit", [])))
    return checked - over, over


def run(cfg: dict, sensor: str, out_root: Path | None = None, sites_path: Path | None = None,
        gate_path: Path | None = None, scene_index: Path | None = None, layer: str = "sites") -> dict:
    import geopandas as gpd
    import rasterio
    from pyproj import Transformer
    s_cfg = {s["name"]: s for s in cfg["sensors"]}[sensor]
    gp = Path(gate_path) if gate_path else io.latest_run(io.EXP, "thermal_gate") / "thermal_gate_summary_9t.json"
    gate = json.loads(io.need(gp, "T1 gate summary").read_text())
    v = gate["sensors"][sensor]["verdict"]
    if v == "failure" or gate["t0"]["verdict"] == "failure":
        raise RuntimeError(f"T1 gate for {sensor} is {v} (T0 {gate['t0']['verdict']}). T2 is not run after a CLOSE")
    sp = Path(sites_path) if sites_path else io.latest_run(io.EXP, "thermal_match") / "thermal_matched_sites_9t.gpkg"
    sites = gpd.read_file(io.need(sp, "matched sites"), layer=layer)
    ek.assert_crs(sites, "EPSG:6346")
    si = Path(scene_index) if scene_index else io.resolve(s_cfg["scene_index"])
    scenes = pd.read_csv(io.need(si, f"{sensor} scene index", cfg["_scene_index_schema"]), parse_dates=["datetime_utc"])
    g = cfg["gate"]
    scenes = scenes[scenes["qc_pass"].astype(bool) & (scenes["cloud_frac"] <= g["max_cloud_frac"])]
    ok_reg, over_reg = registered_scenes(gate, sensor)
    sid = scenes["scene_id"].astype(str)
    n_no_tie = int((~sid.isin(ok_reg | over_reg)).sum())
    n_over = int(sid.isin(over_reg).sum())
    scenes = scenes[sid.isin(ok_reg)]
    ex = cfg["extract"]
    inp = cfg["inputs"]
    prism = pd.read_csv(io.need(io.resolve(inp["prism"]), "PRISM daily", "date, ppt, tmin, tmax"), parse_dates=["date"])
    lp = io.resolve(inp["leaf_state"])
    leaf = pd.read_csv(lp, parse_dates=["date"]) if lp and lp.exists() else None
    nl = io.resolve(inp["nlcd"])
    sites["nlcd_major"] = nlcd_majority(nl, sites).reindex(sites["site_id"]).to_numpy() if nl and nl.exists() else np.nan
    c = sites.geometry.centroid
    lon, lat = Transformer.from_crs(6346, 4326, always_xy=True).transform(c.x.to_numpy(), c.y.to_numpy())
    asp = (np.degrees(np.arctan2(sites["aspect_sin"], sites["aspect_cos"])) + 360) % 360
    run_dir = ek.new_run(io.EXP, SHORT, {"sensor": sensor, "sites": str(sp), "layer": layer, "scenes": str(si), "extract": ex},
                         base=out_root, why=f"T2 extraction for {sensor}.")
    rows, qa_share = [], {}
    for _, sc in scenes.iterrows():
        path = Path(sc["path"])
        if not path.is_absolute():
            path = si.parent / path
        with rasterio.open(io.need(path, f"scene {sc['scene_id']}", "GeoTIFF, LST band per config")) as r:
            lst, qa_share[str(sc["scene_id"])] = scene_lst(r, s_cfg)
            err = (r.read(s_cfg["err_band"], masked=True).astype(float).filled(np.nan)
                   if s_cfg.get("err_band") and r.count >= s_cfg["err_band"] else None)
            T, crs = r.transform, r.crs
        geoms = sites.to_crs(crs).geometry if sites.crs != crs else sites.geometry
        for k, geom in enumerate(geoms):
            wm = io.weighted_mean(lst, T, geom, ss=ex["supersample"])
            zen, az = io.solar_position(sc["datetime_utc"], lat[k], lon[k])
            row = {"site_id": sites["site_id"].iloc[k], "site_class": sites["site_class"].iloc[k],
                   "pair_id": sites["pair_id"].iloc[k], "block_id": sites["block_id"].iloc[k],
                   "scene_id": sc["scene_id"], "datetime_utc": sc["datetime_utc"], "sensor": sensor,
                   "lst_K": wm["mean"], "weight_px": wm["weight"],
                   "partial": bool(wm["geom_area_px"] > 0 and wm["weight"] < ex["partial_weight_frac"] * wm["geom_area_px"]),
                   "lst_err_K": io.weighted_mean(err, T, geom, ss=ex["supersample"])["mean"] if err is not None else np.nan,
                   "chm_mean_m": sites["chm_mean_m"].iloc[k], "nlcd_major": sites["nlcd_major"].iloc[k],
                   "slope_deg": sites["slope_deg"].iloc[k], "aspect_sin": sites["aspect_sin"].iloc[k],
                   "aspect_cos": sites["aspect_cos"].iloc[k], "solar_zenith_deg": zen,
                   "solar_wm2": float(io.clear_sky_loading(sites["slope_deg"].iloc[k], asp.iloc[k], zen, az)),
                   "rain_mm": antecedent_rain(prism, sc["datetime_utc"], ex["antecedent_days"]),
                   "leaf_state": leaf_state_at(leaf, sc["datetime_utc"])}
            rows.append(row)
    out = pd.DataFrame(rows)
    ek.assert_rows(out, len(sites) * len(scenes), "site x scene")
    out_csv = run_dir / "thermal_samples_by_scene_9t.csv"
    out.to_csv(out_csv, index=False)
    summary = {"stage": "T2", "sensor": sensor, "layer": layer, "n_sites": int(len(sites)), "n_scenes": int(len(scenes)),
               "n_rows": int(len(out)), "n_partial": int(out["partial"].sum()) if len(out) else 0,
               "n_scenes_dropped_registration": n_over, "n_scenes_without_tiepoints": n_no_tie,
               "qa_masked_share_by_scene": qa_share,
               "n_missing_lst": int(out["lst_K"].isna().sum()) if len(out) else 0}
    (run_dir / "thermal_samples_summary_9t.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return io.finish(run_dir, summary, inputs=[sp, si, gp], outputs=[out_csv], params=ex)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--sensor", required=True)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--sites", type=Path, default=None)
    ap.add_argument("--gate", type=Path, default=None)
    ap.add_argument("--scene-index", type=Path, default=None)
    ap.add_argument("--layer", choices=("sites", "population"), default="sites",
                    help="sites = matched set for T3, population = all pads and eligible clearings for T4")
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.sensor, a.out_root, a.sites, a.gate, a.scene_index, a.layer),
                     indent=1, default=str))


if __name__ == "__main__":
    main()
