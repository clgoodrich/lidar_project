"""4.2 matched control set. Pads, matched non-well clearings and forest controls, fixed before any LST is read (9t).

Purpose
    Compute lidar covariates per polygon (area, mean CHM, mean slope, aspect sin and cos) from held
    rasters, drop clearings within pad_buffer_m of a pad or inside an audit block, then match one
    clearing per pad by greedy nearest neighbour with a caliper, exact on area band (framework section 3,
    matched clearing). Forest controls are the pad outline moved 150 to 400 m to ground with mean CHM at
    least forest_chm_min_m and clear of every pad. No LST or other response is opened by this script.
Inputs
    pads        truth/annotations_proj_v2.gpkg layer pad (held)
    clearings   expansions/4_modalities/4_2_thermal/data/raw/nonpad_clearings_9t.gpkg (assumed, see config)
    chm, dem    nine_t_1m/chm_9t_1m.tif, dem_9t_1m.tif (held, full 9t)
    audit       frozen P2 audit set (results_9t/splits/audit_blocks_9t_v1.csv) through ek.require_audit, mapped
                to bx_by with the 9t block layer. Missing file refuses unless --allow-no-audit (exploratory)
Outputs (expansions/4_modalities/4_2_thermal/results/<YYYYMMDD>_thermal_match_<hash7>/)
    thermal_matched_sites_9t.gpkg (layer sites, columns site_id, site_class pad|clearing|forest, pair_id,
    block_id, covariates, population=matched. Layer population, every pad and eligible clearing unmatched,
    population=unmatched, for T4), thermal_match_pairs_9t.csv, thermal_match_summary_9t.json, provenance
Run
    python expansions/4_modalities/4_2_thermal/src/_thermal_match_clearings_9t.py [--clearings PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _thermal_shared_io as io
from _thermal_shared_io import ek

SHORT = "thermal_match"


def covariates(gdf, id_col: str, chm: Path, dem: Path, bands) -> pd.DataFrame:
    """Lidar covariates per polygon. Aspect from the mean surface gradient inside the polygon."""
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds, Window
    out = pd.DataFrame({id_col: gdf[id_col].to_numpy(), "area_m2": gdf.geometry.area.to_numpy()})
    out["chm_mean_m"] = io.zonal(chm, gdf, id_col).reindex(out[id_col]).to_numpy()
    sl, asp_s, asp_c = [], [], []
    with rasterio.open(dem) as s:
        res = s.res[0]
        for geom in gdf.geometry:
            try:
                w = from_bounds(*geom.buffer(2 * res).bounds, transform=s.transform).round_offsets().round_lengths()
                w = w.intersection(Window(0, 0, s.width, s.height))
                a = s.read(1, window=w, masked=True).astype(float).filled(np.nan)
            except Exception:  # noqa: BLE001
                sl.append(np.nan); asp_s.append(np.nan); asp_c.append(np.nan)
                continue
            m = ~geometry_mask([geom], a.shape, s.window_transform(w)) & np.isfinite(a)
            if m.sum() < 4:
                sl.append(np.nan); asp_s.append(np.nan); asp_c.append(np.nan)
                continue
            slope, aspect = io.slope_aspect(np.where(np.isfinite(a), a, np.nanmean(a)), res)
            sl.append(float(np.nanmean(slope[m])))
            ar = np.radians(aspect[m])
            asp_s.append(float(np.mean(np.sin(ar))))
            asp_c.append(float(np.mean(np.cos(ar))))
    out["slope_deg"], out["aspect_sin"], out["aspect_cos"] = sl, asp_s, asp_c
    out["area_band"] = np.digitize(out["area_m2"], bands[1:-1])
    return out


def forest_controls(pads, cov_pads, chm: Path, mcfg: dict, rng, id_col: str):
    """Pad outline translated to forest ground, one per pad, clear of every pad buffer."""
    import geopandas as gpd
    from shapely import affinity
    union = pads.geometry.buffer(mcfg["pad_buffer_m"]).union_all()
    rows = []
    for pid, geom in zip(pads[id_col], pads.geometry):
        for _ in range(mcfg["forest_tries"]):
            a, d = rng.uniform(0, 2 * np.pi), rng.uniform(*mcfg["forest_shift_m"])
            gm = affinity.translate(geom, d * np.cos(a), d * np.sin(a))
            if gm.intersects(union):
                continue
            tmp = gpd.GeoDataFrame({"_id": [0]}, geometry=[gm], crs=pads.crs)
            v = io.zonal(chm, tmp, "_id").iloc[0]
            if np.isfinite(v) and v >= mcfg["forest_chm_min_m"]:
                rows.append({"site_id": f"forest_{pid}", "pair_id": f"pair_{pid}", "geometry": gm})
                break
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=pads.crs) if rows else None


def population_layer(pads, clear, cp_, cc_, pairs, pin: str, cin: str):
    """Review 4.2-01. Every pad and every eligible clearing, unmatched. Matching on the lidar covariates
    makes lidar uninformative by construction, so T4 measures added value on this population instead."""
    import geopandas as gpd
    pair_of_pad = {t: f"pair_{t}" for t in pairs["treated_id"]}
    pair_of_clear = {c: f"pair_{t}" for t, c in zip(pairs["treated_id"], pairs["control_id"])}
    a = pads[[pin, "geometry", "block_id"]].rename(columns={pin: "src_id"}).merge(
        cp_.rename(columns={"id": "src_id"}), on="src_id", how="left")
    a["site_id"], a["site_class"] = [f"pad_{i}" for i in a["src_id"]], "pad"
    a["pair_id"] = a["src_id"].map(pair_of_pad)
    b = clear[[cin, "geometry", "block_id"]].rename(columns={cin: "src_id"}).merge(
        cc_.rename(columns={"id": "src_id"}), on="src_id", how="left")
    b["site_id"], b["site_class"] = [f"clearing_{i}" for i in b["src_id"]], "clearing"
    b["pair_id"] = b["src_id"].map(pair_of_clear)
    g = gpd.GeoDataFrame(pd.concat([a, b], ignore_index=True), geometry="geometry", crs=pads.crs)
    g["src_id"] = g["src_id"].astype(str)
    g["population"] = "unmatched"
    g["lst_read"] = False
    ek.assert_unique(g, "site_id")
    return g


def run(cfg: dict, out_root: Path | None = None, clearings_path: Path | None = None, pads_path: Path | None = None,
        max_pads: int | None = None, allow_no_audit: bool = False) -> dict:
    import geopandas as gpd
    inp, m = cfg["inputs"], cfg["matching"]
    pin, cin = inp["pads"], inp["clearings"]
    pp = Path(pads_path) if pads_path else io.resolve(pin)
    cp = Path(clearings_path) if clearings_path else io.resolve(cin)
    pads = io.read_polys(pp, pin.get("layer"), pin["id_col"], "pad polygons")
    clear = io.read_polys(cp, cin.get("layer"), cin["id_col"], "non-pad clearings (matched clearing source)")
    chm = io.need(io.resolve(inp["chm"]), "CHM raster", "single band, metres, EPSG:6346")
    pads, clear = io.within_raster(pads, chm), io.within_raster(clear, chm)
    if max_pads:
        pads = pads.head(max_pads)
    dem = io.need(io.resolve(inp["dem"]), "DEM raster", "single band, metres, EPSG:6346")
    audit_ids, audit_info = io.audit_exclusion(inp.get("audit_blocks"), allow_no_audit, inp.get("blocks"))
    run_dir = ek.new_run(io.EXP, SHORT, {"matching": m, "pads": str(pp), "clearings": str(cp), "n_pads": len(pads)},
                         base=out_root, why="Matched clearings and forest controls, drawn before LST is read.")
    n_clear0 = len(clear)
    buf = pads.geometry.buffer(m["pad_buffer_m"]).union_all()
    clear = clear[~clear.geometry.intersects(buf)].copy()
    for g in (pads, clear):
        c = g.geometry.centroid
        g["block_id"] = io.block_of(c.x, c.y)
    pads = pads[~pads["block_id"].isin(audit_ids)]
    clear = clear[~clear["block_id"].isin(audit_ids)]
    cp_ = covariates(pads, pin["id_col"], chm, dem, m["area_bands_m2"]).rename(columns={pin["id_col"]: "id"})
    cc_ = covariates(clear, cin["id_col"], chm, dem, m["area_bands_m2"]).rename(columns={cin["id_col"]: "id"})
    pairs = io.match_caliper(cp_, cc_, "id", m["continuous"], m["exact"], m["caliper_sd"], m["n_per"],
                             seed=ek.child_seed(cfg["master_seed"], arm=10))
    ek.assert_unique(pairs, "control_id")
    rng = np.random.default_rng(ek.child_seed(cfg["master_seed"], arm=11))
    matched_pads = pads[pads[pin["id_col"]].isin(pairs["treated_id"])]
    forest = forest_controls(matched_pads, cp_, chm, m, rng, pin["id_col"])
    pair_of_clear = dict(zip(pairs["control_id"], pairs["treated_id"]))
    sp = matched_pads[[pin["id_col"], "geometry"]].rename(columns={pin["id_col"]: "src_id"})
    sp["site_id"] = [f"pad_{i}" for i in sp["src_id"]]
    sp["site_class"], sp["pair_id"] = "pad", [f"pair_{i}" for i in sp["src_id"]]
    sc = clear[clear[cin["id_col"]].isin(pairs["control_id"])][[cin["id_col"], "geometry"]].rename(columns={cin["id_col"]: "src_id"})
    sc["site_id"] = [f"clearing_{i}" for i in sc["src_id"]]
    sc["site_class"], sc["pair_id"] = "clearing", [f"pair_{pair_of_clear[i]}" for i in sc["src_id"]]
    parts = [sp, sc]
    if forest is not None:
        forest["src_id"], forest["site_class"] = forest["site_id"], "forest"
        parts.append(forest)
    sites = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=pads.crs)
    sites["src_id"] = sites["src_id"].astype(str)
    cov = covariates(sites, "site_id", chm, dem, m["area_bands_m2"])
    sites = sites.merge(cov.drop(columns=["area_m2"]), on="site_id", how="left")
    sites["area_m2"] = sites.geometry.area
    c = sites.geometry.centroid
    sites["block_id"] = io.block_of(c.x, c.y)
    ek.assert_unique(sites, "site_id")
    ek.assert_no_nan(sites["block_id"], "block_id")
    sites["lst_read"] = False
    sites["population"] = "matched"
    popl = population_layer(pads, clear, cp_, cc_, pairs, pin["id_col"], cin["id_col"])
    out_g = run_dir / "thermal_matched_sites_9t.gpkg"
    out_p = run_dir / "thermal_match_pairs_9t.csv"
    out_j = run_dir / "thermal_match_summary_9t.json"
    sites.to_file(out_g, layer="sites", driver="GPKG")
    popl.to_file(out_g, layer="population", driver="GPKG")
    pairs.to_csv(out_p, index=False)
    smd = {}
    for col in m["continuous"]:
        a = cp_.set_index("id").loc[pairs["treated_id"], col]
        b = cc_.set_index("id").loc[pairs["control_id"], col]
        s = np.sqrt((a.var() + b.var()) / 2) or 1.0
        smd[col] = float((a.mean() - b.mean()) / s)
    summary = {"stage": "matching (before T2)", "n_pads_in": int(len(pads)), "n_clearings_in": int(n_clear0),
               "n_clearings_clear_of_pads": int(len(clear)), "n_pairs": int(len(pairs)),
               "n_forest": int(0 if forest is None else len(forest)), "n_audit_blocks_excluded": len(audit_ids),
               "audit": audit_info, "exploratory": bool(audit_info["exploratory"]),
               "n_population": int(len(popl)),
               "std_mean_diff_matched": smd, "lst_read": False}
    out_j.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return io.finish(run_dir, summary, inputs=[pp, cp, chm, dem], outputs=[out_g, out_p, out_j], params=m,
                     seeds={"master": cfg["master_seed"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--clearings", type=Path, default=None)
    ap.add_argument("--pads", type=Path, default=None)
    ap.add_argument("--max-pads", type=int, default=None)
    ap.add_argument("--allow-no-audit", action="store_true",
                    help="run without the frozen P2 audit set. The output is labelled exploratory")
    a = ap.parse_args()
    s = run(io.load_config(a.config), a.out_root, a.clearings, a.pads, a.max_pads, a.allow_no_audit)
    print(json.dumps(s, indent=1, default=str))


if __name__ == "__main__":
    main()
