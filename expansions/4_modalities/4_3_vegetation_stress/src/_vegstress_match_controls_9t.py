"""4.3 matched controls. Non-well disturbance matched to pads, fixed before any vegetation index is read (9t).

Purpose
    Lidar covariates per polygon (area, mean CHM, aspect sin and cos) with the 4.2 covariate code. Drop
    controls within pad_buffer_m of any pad or inside an audit block. Greedy nearest-neighbour caliper
    matching, exact on area band and, where both layers carry them, on age_band and soil_unit
    (framework section 3, matched control). No index raster is opened here.
Inputs
    pads      truth/annotations_proj_v2.gpkg layer pad (held)
    controls  expansions/4_modalities/4_3_vegetation_stress/data/raw/nonpad_disturbance_9t.gpkg (assumed)
    chm, dem  nine_t_1m/chm_9t_1m.tif, dem_9t_1m.tif (held)
    audit     frozen P2 audit set through ek.require_audit (review P2-01). Missing refuses unless --allow-no-audit
Outputs (expansions/4_modalities/4_3_vegetation_stress/results/<YYYYMMDD>_vegstress_match_<hash7>/)
    vegstress_matched_sites_9t.gpkg (layer sites, site_id, site_class pad|control, pair_id, block_id,
    covariates, population=matched. Layer population, every pad and eligible control, for V3),
    vegstress_match_pairs_9t.csv, vegstress_match_summary_9t.json, provenance
Run
    python expansions/4_modalities/4_3_vegetation_stress/src/_vegstress_match_controls_9t.py [--controls PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import _vegstress_shared_io as io
from _vegstress_shared_io import ek
from _thermal_match_clearings_9t import covariates   # 4.2 code, on sys.path via the shared module

SHORT = "vegstress_match"


def run(cfg: dict, out_root: Path | None = None, controls_path: Path | None = None, allow_no_audit: bool = False) -> dict:
    import geopandas as gpd
    inp, m = cfg["inputs"], cfg["matching"]
    pin, cin = inp["pads"], inp["controls"]
    pp = io.resolve(pin)
    cp = Path(controls_path) if controls_path else io.resolve(cin)
    pads = io.read_polys(pp, pin.get("layer"), pin["id_col"], "pad polygons")
    ctrl = io.read_polys(cp, cin.get("layer"), cin["id_col"], "non-well disturbance controls")
    chm = io.need(io.resolve(inp["chm"]), "CHM raster")
    dem = io.need(io.resolve(inp["dem"]), "DEM raster")
    pads, ctrl = io.within_raster(pads, chm), io.within_raster(ctrl, chm)
    audit_ids, audit_info = io.audit_exclusion(inp.get("audit_blocks"), allow_no_audit, inp.get("blocks"))
    run_dir = ek.new_run(io.EXP, SHORT, {"matching": m, "controls": str(cp)}, base=out_root,
                         why="Matched non-well disturbance controls, drawn before any index is read.")
    n0 = len(ctrl)
    ctrl = ctrl[~ctrl.geometry.intersects(pads.geometry.buffer(m["pad_buffer_m"]).union_all())].copy()
    for g in (pads, ctrl):
        c = g.geometry.centroid
        g["block_id"] = io.block_of(c.x, c.y)
    pads, ctrl = pads[~pads.block_id.isin(audit_ids)], ctrl[~ctrl.block_id.isin(audit_ids)]
    a = covariates(pads, pin["id_col"], chm, dem, m["area_bands_m2"]).rename(columns={pin["id_col"]: "id"})
    b = covariates(ctrl, cin["id_col"], chm, dem, m["area_bands_m2"]).rename(columns={cin["id_col"]: "id"})
    exact = list(m["exact"])
    for col in ("age_band", "soil_unit"):
        if col in pads.columns and col in ctrl.columns:
            a[col], b[col] = pads[col].to_numpy(), ctrl[col].to_numpy()
            exact.append(col)
    pairs = io.match_caliper(a, b, "id", m["continuous"], exact, m["caliper_sd"], m["n_per"],
                             seed=ek.child_seed(cfg["master_seed"], arm=10))
    ek.assert_unique(pairs, "control_id")
    pair_of = dict(zip(pairs.control_id, pairs.treated_id))
    sp = pads[pads[pin["id_col"]].isin(pairs.treated_id)][[pin["id_col"], "geometry"]].rename(columns={pin["id_col"]: "src_id"})
    sp["site_id"], sp["site_class"], sp["pair_id"] = [f"pad_{i}" for i in sp.src_id], "pad", [f"pair_{i}" for i in sp.src_id]
    sc = ctrl[ctrl[cin["id_col"]].isin(pairs.control_id)][[cin["id_col"], "geometry"]].rename(columns={cin["id_col"]: "src_id"})
    sc["site_id"], sc["site_class"] = [f"control_{i}" for i in sc.src_id], "control"
    sc["pair_id"] = [f"pair_{pair_of[i]}" for i in sc.src_id]
    sites = gpd.GeoDataFrame(pd.concat([sp, sc], ignore_index=True), geometry="geometry", crs=pads.crs)
    sites["src_id"] = sites["src_id"].astype(str)
    cov = covariates(sites, "site_id", chm, dem, m["area_bands_m2"])
    sites = sites.merge(cov, on="site_id", how="left")
    c = sites.geometry.centroid
    sites["block_id"] = io.block_of(c.x, c.y)
    sites["index_read"] = False
    sites["population"] = "matched"
    ek.assert_unique(sites, "site_id")
    # review 4.3-02: every pad and eligible control, unmatched, for V3
    pa = pads[[pin["id_col"], "geometry", "block_id"]].rename(columns={pin["id_col"]: "src_id"})
    pa["site_id"], pa["site_class"] = [f"pad_{i}" for i in pa.src_id], "pad"
    pa["pair_id"] = pa.src_id.map({t: f"pair_{t}" for t in pairs.treated_id})
    pb = ctrl[[cin["id_col"], "geometry", "block_id"]].rename(columns={cin["id_col"]: "src_id"})
    pb["site_id"], pb["site_class"] = [f"control_{i}" for i in pb.src_id], "control"
    pb["pair_id"] = pb.src_id.map({c: f"pair_{pair_of[c]}" for c in pairs.control_id})
    popl = gpd.GeoDataFrame(pd.concat([pa, pb], ignore_index=True), geometry="geometry", crs=pads.crs)
    popl["src_id"] = popl["src_id"].astype(str)
    popl = popl.merge(covariates(popl, "site_id", chm, dem, m["area_bands_m2"]), on="site_id", how="left")
    popl["population"], popl["index_read"] = "unmatched", False
    ek.assert_unique(popl, "site_id")
    out_g, out_p, out_j = (run_dir / "vegstress_matched_sites_9t.gpkg", run_dir / "vegstress_match_pairs_9t.csv",
                           run_dir / "vegstress_match_summary_9t.json")
    sites.to_file(out_g, layer="sites", driver="GPKG")
    popl.to_file(out_g, layer="population", driver="GPKG")
    pairs.to_csv(out_p, index=False)
    summary = {"stage": "matching (before V2)", "n_pads": int(len(pads)), "n_controls_in": int(n0),
               "n_controls_clear": int(len(ctrl)), "n_pairs": int(len(pairs)), "exact_on": exact, "index_read": False,
               "n_population": int(len(popl)), "n_audit_blocks_excluded": len(audit_ids), "audit": audit_info,
               "exploratory": bool(audit_info["exploratory"])}
    out_j.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return io.finish(run_dir, summary, inputs=[pp, cp, chm, dem], outputs=[out_g, out_p, out_j], params=m,
                     seeds={"master": cfg["master_seed"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--controls", type=Path, default=None)
    ap.add_argument("--allow-no-audit", action="store_true",
                    help="run without the frozen P2 audit set. The output is labelled exploratory")
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.out_root, a.controls, a.allow_no_audit), indent=1, default=str))


if __name__ == "__main__":
    main()
