"""4.2 stage T2. Pixel-weighted LST per site and scene, with covariates (9t). Run only if T1 passes for that sensor.

Purpose
    For every matched site (pad, clearing, forest) and every usable scene, the area-weighted LST using the
    fractional overlap of the site polygon with each pixel, the LST error where the product carries one,
    and a partial-overlap flag. Covariates per site and scene. Mean CHM, NLCD majority class, slope,
    aspect, clear-sky solar loading at the scene time (NOAA solar position on the site centroid, cosine
    of incidence on the mean slope and aspect), PRISM antecedent rain over antecedent_days, nearest leaf
    state from the leaf-state curve.
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


def run(cfg: dict, sensor: str, out_root: Path | None = None, sites_path: Path | None = None,
        gate_path: Path | None = None, scene_index: Path | None = None) -> dict:
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
    sites = gpd.read_file(io.need(sp, "matched sites"), layer="sites")
    ek.assert_crs(sites, "EPSG:6346")
    si = Path(scene_index) if scene_index else io.resolve(s_cfg["scene_index"])
    scenes = pd.read_csv(io.need(si, f"{sensor} scene index", cfg["_scene_index_schema"]), parse_dates=["datetime_utc"])
    g = cfg["gate"]
    scenes = scenes[scenes["qc_pass"].astype(bool) & (scenes["cloud_frac"] <= g["max_cloud_frac"])]
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
    run_dir = ek.new_run(io.EXP, SHORT, {"sensor": sensor, "sites": str(sp), "scenes": str(si), "extract": ex},
                         base=out_root, why=f"T2 extraction for {sensor}.")
    rows = []
    for _, sc in scenes.iterrows():
        path = Path(sc["path"])
        if not path.is_absolute():
            path = si.parent / path
        with rasterio.open(io.need(path, f"scene {sc['scene_id']}", "GeoTIFF, LST band per config")) as r:
            lst = r.read(s_cfg["lst_band"], masked=True).astype(float).filled(np.nan) * s_cfg["lst_scale"] + s_cfg["lst_offset"]
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
    summary = {"stage": "T2", "sensor": sensor, "n_sites": int(len(sites)), "n_scenes": int(len(scenes)),
               "n_rows": int(len(out)), "n_partial": int(out["partial"].sum()) if len(out) else 0,
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
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.sensor, a.out_root, a.sites, a.gate, a.scene_index), indent=1, default=str))


if __name__ == "__main__":
    main()
