"""4.3 stage V2. Vegetation indices per site and scene, pad interior under open sky, ring, and stress anomaly (9t).

Purpose
    For each site (pad or matched control) and each scene. NDVI and NDMI from the bands present (NDRE and
    EVI are NaN when red edge or blue is absent, as in the held Sentinel-2 stacks). Area-weighted mean
    over interior pixels that carry a valid SCL class and whose open share (1 m CHM below 2 m, averaged
    onto the scene grid) is at least open_frac_min. Same index over a ring ring_inner_m to ring_outer_m
    outside the site, clear of every site. Difference site minus ring. Stress anomaly is that difference
    minus the site's own mean difference in the same season of other years. With one year only, the
    reference is the site's mean over all scenes and anomaly_ref says so.
    --pads-only runs on pads without matched controls. It is exploratory and labelled so.
Inputs
    sites   <run>_vegstress_match_*/vegstress_matched_sites_9t.gpkg, or pads with --pads-only
    scenes  config scenes (held Sentinel-2 5 m stacks, EPSG:32617) plus the optional scene index
    chm     nine_t_1m/chm_9t_1m.tif (held)
Outputs (expansions/4_modalities/4_3_vegetation_stress/results/<YYYYMMDD>_vegstress_sites_<hash7>/)
    vegstress_by_site_9t.csv (one row per site and scene), vegstress_sites_summary_9t.json, provenance
Run
    python expansions/4_modalities/4_3_vegetation_stress/src/_vegstress_extract_sites_9t.py [--sites PATH | --pads-only] [--max-sites N]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _vegstress_shared_io as io
from _vegstress_shared_io import ek
from _vegstress_observability_9t import scene_list

SHORT = "vegstress_sites"
INDICES = ("ndvi", "ndmi", "ndre", "evi")


def read_scene(path: str, names: list[str], scale: float):
    import rasterio
    with rasterio.open(path) as r:
        desc = [d.lower() if d else "" for d in r.descriptions]
        bands = {n: r.read(desc.index(n) + 1).astype(float) for n in names if n in desc}
        T, crs, shape = r.transform, r.crs, (r.height, r.width)
    scl = bands.pop("scl", None)
    bands = {k: v * scale for k, v in bands.items()}
    return bands, scl, T, crs, shape


def open_share(chm_path: Path, T, crs, shape, open_max: float) -> np.ndarray:
    """Share of 1 m CHM cells below open_max inside each scene pixel."""
    import rasterio
    from rasterio.warp import reproject, Resampling
    with rasterio.open(chm_path) as s:
        chm = s.read(1, masked=True).astype(float).filled(np.nan)
        op = np.where(np.isfinite(chm), (chm < open_max).astype(float), np.nan)
        dst = np.full(shape, np.nan)
        reproject(op, dst, src_transform=s.transform, src_crs=s.crs, dst_transform=T, dst_crs=crs,
                  resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
    return dst


def anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["year"] = pd.to_datetime(df["date"]).dt.year
    multi_year = df.groupby(["site_id", "season"])["year"].nunique().max() > 1
    for ix in INDICES:
        d = f"{ix}_diff"
        if multi_year:
            tot = df.groupby(["site_id", "season"])[d].transform("sum")
            cnt = df.groupby(["site_id", "season"])[d].transform("count")
            yr_tot = df.groupby(["site_id", "season", "year"])[d].transform("sum")
            yr_cnt = df.groupby(["site_id", "season", "year"])[d].transform("count")
            ref = (tot - yr_tot) / (cnt - yr_cnt).replace(0, np.nan)
        else:
            ref = df.groupby("site_id")[d].transform("mean")
        df[f"{ix}_anomaly"] = df[d] - ref
    df["anomaly_ref"] = "same season other years" if multi_year else "site mean over all scenes (one year only)"
    return df


def run(cfg: dict, out_root: Path | None = None, sites_path: Path | None = None, pads_only: bool = False,
        max_sites: int | None = None) -> dict:
    import geopandas as gpd
    ex, o = cfg["extract"], cfg["observability"]
    if pads_only:
        pin = cfg["inputs"]["pads"]
        sp = io.resolve(pin)
        s = io.read_polys(sp, pin.get("layer"), pin["id_col"], "pad polygons")
        s = io.within_raster(s, io.need(io.resolve(cfg["inputs"]["chm"]), "CHM raster"))
        sites = gpd.GeoDataFrame({"site_id": [f"pad_{i}" for i in s[pin["id_col"]]], "site_class": "pad",
                                  "pair_id": [f"pair_{i}" for i in s[pin["id_col"]]]}, geometry=s.geometry.values, crs=s.crs)
        c = sites.geometry.centroid
        sites["block_id"] = io.block_of(c.x, c.y)
    else:
        sp = Path(sites_path) if sites_path else io.latest_run("vegstress_match") / "vegstress_matched_sites_9t.gpkg"
        sites = gpd.read_file(io.need(sp, "matched sites (run _vegstress_match_controls_9t.py or pass --pads-only)"),
                              layer="sites")
    ek.assert_crs(sites, "EPSG:6346")
    if max_sites:
        sites = sites.head(max_sites)
    chm = io.need(io.resolve(cfg["inputs"]["chm"]), "CHM raster")
    scenes = scene_list(cfg)
    run_dir = ek.new_run(io.EXP, SHORT, {"extract": ex, "sites": str(sp), "pads_only": pads_only, "n_sites": len(sites),
                                          "scenes": scenes.scene_id.tolist()}, base=out_root, why="V2 index extraction.")
    rows = []
    for _, sc in scenes.iterrows():
        bands, scl, T, crs, shape = read_scene(io.need(sc["path"], f"scene {sc['scene_id']}"), cfg["band_names"],
                                               ex["reflectance_scale"])
        idx = io.indices(bands)
        valid = np.isin(scl, cfg["scl_valid"]) if scl is not None else np.ones(shape, bool)
        opn = open_share(chm, T, crs, shape, o["chm_open_max_m"])
        interior_ok = valid & (opn >= ex["open_frac_min"])
        g = sites.to_crs(crs)
        blocker = g.geometry.buffer(ex["ring_inner_m"]).union_all()
        for k, geom in enumerate(g.geometry):
            ring = geom.buffer(ex["ring_outer_m"]).difference(blocker)
            r = {"site_id": sites["site_id"].iloc[k], "site_class": sites["site_class"].iloc[k],
                 "pair_id": sites["pair_id"].iloc[k], "block_id": sites["block_id"].iloc[k],
                 "scene_id": sc["scene_id"], "date": sc["date"], "season": sc["season"]}
            for ix in INDICES:
                a = io.weighted_mean(idx[ix], T, geom, mask=interior_ok, ss=ex["supersample"])
                b = (io.weighted_mean(idx[ix], T, ring, mask=valid, ss=ex["supersample"]) if not ring.is_empty
                     else {"mean": np.nan, "n_px": 0})
                r[f"{ix}_site"], r[f"{ix}_ring"], r[f"{ix}_diff"] = a["mean"], b["mean"], a["mean"] - b["mean"]
                if ix == "ndvi":
                    r["n_px_site"], r["n_px_ring"] = a["n_px"], b["n_px"]
            rows.append(r)
    df = anomalies(pd.DataFrame(rows))
    ek.assert_rows(df, len(sites) * len(scenes), "site x scene")
    out_c, out_j = run_dir / "vegstress_by_site_9t.csv", run_dir / "vegstress_sites_summary_9t.json"
    df.to_csv(out_c, index=False)
    summary = {"stage": "V2", "exploratory": bool(pads_only), "n_sites": int(len(sites)), "n_scenes": int(len(scenes)),
               "n_rows": int(len(df)), "share_site_rows_no_open_pixels": float((df["n_px_site"] == 0).mean()),
               "median_ndvi_diff_by_class": df.groupby("site_class")["ndvi_diff"].median().to_dict(),
               "indices_all_nan": [ix for ix in INDICES if df[f"{ix}_site"].isna().all()],
               "anomaly_ref": df["anomaly_ref"].iloc[0] if len(df) else None,
               "note": "A difference in disturbed ground, not leakage. Evidence level (a)"}
    out_j.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return io.finish(run_dir, summary, inputs=[sp, chm] + [Path(p) for p in scenes.path], outputs=[out_c, out_j], params=ex)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--sites", type=Path, default=None)
    ap.add_argument("--pads-only", action="store_true")
    ap.add_argument("--max-sites", type=int, default=None)
    a = ap.parse_args()
    s = run(io.load_config(a.config), a.out_root, a.sites, a.pads_only, a.max_sites)
    print(json.dumps({k: v for k, v in s.items()}, indent=1, default=str))


if __name__ == "__main__":
    main()
