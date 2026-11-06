"""S2 of framework 4.7. Ingest one native drone cloud and measure ground density, canopy and void fraction.

Purpose. Through the PDAL CLI (run_pdal), grid all returns and ground returns (class 2) at density_res_m, plus a
first-return DSM and an IDW ground DEM. Footprint is every cell with any return. Native ground density is ground
returns over footprint area. Void fraction is the share of footprint cells with no ground return. Canopy is the
share of footprint cells where DSM minus DEM exceeds 2 m. Per-site ground density is written when the site layer
exists. No reprojection happens here. A cloud not in EPSG:6346 stops with an alert.
Inputs.
  one LAS/LAZ from data/_source/drone_netl/ (assumed)
  data/_source/drone_netl/netl_sites_oc.gpkg (optional, assumed)
Outputs (default data/oilcreek/derived/drone_native/, ignored by data/**/derived/**).
  <stem>_ground_count_oc.tif, <stem>_all_count_oc.tif, <stem>_dem_oc.tif, <stem>_dsm_oc.tif
  <stem>_density_oc.json      header, class counts, native density, void and canopy fractions
  <stem>_site_density_oc.csv  ground returns per m2 per site (when sites exist)
Run.
  python expansions/4_modalities/4_7_drone_lidar/src/_drone_ingest_density_oc.py --las PATH [--sites GPKG] [--res 1.0] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _drone_kit_4_7 as dk


def surface(las: Path, out_tif: Path, res: float, grid, kind: str, tmp: Path, label: str) -> np.ndarray:
    """kind 'dem' = IDW of ground, 'dsm' = max of first returns."""
    x0, y0, W, H = grid
    st = [{"type": "readers.las", "filename": str(las)},
          {"type": "filters.range", "limits": "Classification[2:2]" if kind == "dem" else "ReturnNumber[1:1]"},
          {"type": "writers.gdal", "filename": str(out_tif), "output_type": "idw" if kind == "dem" else "max",
           "resolution": res, "origin_x": x0, "origin_y": y0, "width": W, "height": H, "window_size": 3,
           **({} if kind == "dem" else {"binmode": True}),
           "data_type": "float32", "nodata": -9999}]
    dk.run_pdal(st, label=label, tmp_dir=tmp, verbose=False)
    return dk.read_tif(out_tif)


def site_density(las: Path, sites, ground_class: int) -> pd.DataFrame:
    """Ground returns per m2 inside each site polygon (points get a 10 m buffer)."""
    import laspy
    from shapely import contains_xy
    geoms = [g if g.geom_type != "Point" else g.buffer(10.0) for g in sites.geometry]
    n = np.zeros(len(geoms), np.int64)
    with laspy.open(str(las)) as f:
        for pts in f.chunk_iterator(2_000_000):
            m = np.asarray(pts.classification) == ground_class
            x, y = np.asarray(pts.x)[m], np.asarray(pts.y)[m]
            for k, g in enumerate(geoms):
                n[k] += int(contains_xy(g, x, y).sum())
    area = np.array([g.area for g in geoms])
    return pd.DataFrame({"site_id": sites.site_id.to_numpy(), "hillside": sites.hillside.to_numpy(),
                         "area_m2": area, "n_ground": n, "ground_ppsm": n / area})


def ingest(las: Path, out: Path, res: float, ground_class: int, crs: str, sites=None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    info = dk.las_info(las, ground_class)
    want = int(crs.split(":")[1])
    if info["epsg"] != want:
        raise ValueError(f"ALERT: {las.name} is EPSG:{info['epsg']}, not {crs}. Reproject explicitly and log it before S2")
    grid = dk.grid_of(info["mins"], info["maxs"], res)
    stem = las.stem
    g = dk.count_raster(las, out / f"{stem}_ground_count_oc.tif", res, grid, f"Classification[{ground_class}:{ground_class}]", out, f"gc_{stem}")
    al = dk.count_raster(las, out / f"{stem}_all_count_oc.tif", res, grid, None, out, f"ac_{stem}")
    dem = surface(las, out / f"{stem}_dem_oc.tif", res, grid, "dem", out, f"dem_{stem}")
    dsm = surface(las, out / f"{stem}_dsm_oc.tif", res, grid, "dsm", out, f"dsm_{stem}")
    fp = al > 0
    fp_area = float(fp.sum() * res * res)
    hag = dsm - dem
    res_d = {**info, "res_m": res, "footprint_m2": fp_area,
             "native_ground_ppsm": info["n_ground"] / fp_area if fp_area else float("nan"),
             "native_all_ppsm": info["n_points"] / fp_area if fp_area else float("nan"),
             "void_fraction": float(((g == 0) & fp).sum() / fp.sum()) if fp.any() else float("nan"),
             "canopy_fraction_2m": float(np.nanmean(hag[fp] > 2.0)) if fp.any() else float("nan")}
    if sites is not None:
        sd = site_density(las, sites, ground_class)
        sd.to_csv(out / f"{stem}_site_density_oc.csv", index=False)
        res_d["n_sites_in_cloud"] = int((sd.n_ground > 0).sum())
    (out / f"{stem}_density_oc.json").write_text(json.dumps(res_d, indent=2), encoding="utf-8")
    return res_d


def main(argv=None) -> int:
    cfg = dk.load_cfg()
    L = cfg["ladder"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--las", required=True)
    ap.add_argument("--sites", default=None)
    ap.add_argument("--res", type=float, default=L["density_res_m"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    las = dk.need(Path(a.las), "native drone cloud", cfg["inputs"]["raw_las"])
    sp = Path(a.sites) if a.sites else dk.resolve(cfg["inputs"]["sites"])
    sites = None
    if sp.exists():
        import geopandas as gpd
        sites = gpd.read_file(sp)
        dk.ek.assert_crs(sites, cfg["crs"])
        dk.ek.assert_unique(sites, "site_id")
    out = Path(a.out) if a.out else dk.resolve(cfg["outputs"]["native"])
    r = ingest(las, out, a.res, L["ground_class"], cfg["crs"], sites)
    dk.prov(out, f"drone_ingest_{las.stem}", inputs=[las], outputs=sorted(out.glob(f"{las.stem}_*_oc.*")), params=r)
    print(json.dumps({k: r[k] for k in ("n_points", "n_ground", "native_ground_ppsm", "void_fraction", "canopy_fraction_2m")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
