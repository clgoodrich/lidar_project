"""S3 (3.4). Observability audit Q0. Share of 9t-like pit depths detectable in each Gulf window.

Purpose
    1. 9t reference. Depth of every annotated 9t pit floor (pit_inside) as median rim elevation in a
       5 m ring minus the floor minimum, on the 0.5 m 9t DEM. Held data, runnable now.
    2. Target. Minimum detectable depth (MDD) = 3 x robust SD of detrended 0.5 m ground DEM on stable
       ground (NLCD 81 pasture, 82 crops) per window, and per wetland and void stratum when strata exist.
    3. Share of 9t pit depths at or above each MDD, with a Clopper-Pearson interval.
    Readiness. A share under the prereg observability floor labels the window "target not observable".
    That is a statement about the data, not a model failure. Scoring is then not run.
Inputs
    data/9t/derived/05/dem_9t_05.tif, qgis/annotations/annotations_proj.gpkg layer pit_inside (held)
    data/<area>/derived/05/dem_<area>_05.tif (from the core 'derive' step), NLCD 2021 (assumed)
    data/<area>/results/transfer/xfer_blocks_roles_<area>.gpkg (optional, for strata)
Outputs
    expansions/3_geography/3_4_gulf_texas/results/tables/gulf_pit_depths_ref_9t.csv
    data/<area>/results/transfer/xfer_observable_depth_<area>.csv
Run
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_observable_depth_audit.py --ref-only
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_observable_depth_audit.py --area la_caddo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.4"
STABLE_NLCD = (81, 82)


def ref_depths(max_n: int = 0) -> pd.DataFrame:
    import geopandas as gpd
    dem = gt.require_input(ek.path_for("nine_t") / "dem_9t_05.tif", "9t 0.5 m DEM")
    pits = gpd.read_file(gt.require_input(ek.path_for("truth") / "annotations_proj.gpkg", "9t annotations"),
                         layer="pit_inside")
    ek.assert_crs(pits, "EPSG:6346")
    pits = pits[pits.geometry.notna() & ~pits.geometry.is_empty].reset_index(drop=True)
    if max_n:
        pits = pits.head(max_n)
    d = gt.feature_depths_from_raster(dem, list(pits.geometry))
    return pd.DataFrame({"pit_idx": np.arange(len(pits)), "depth_m": d, "area_m2": pits.geometry.area})


def stable_mask_from_nlcd(nlcd_path: Path, shape, transform, crs) -> np.ndarray:
    import rasterio
    from rasterio.warp import Resampling, reproject
    dst = np.zeros(shape, np.uint8)
    with rasterio.open(nlcd_path) as r:
        reproject(rasterio.band(r, 1), dst, dst_transform=transform, dst_crs=crs, resampling=Resampling.nearest)
    return np.isin(dst, STABLE_NLCD)


def audit_area(area: str, depths: np.ndarray, cfg: dict) -> pd.DataFrame:
    import rasterio
    dem_p = gt.require_input(ek.area_dir(area) / "derived" / "05" / f"dem_{area}_05.tif",
                             f"0.5 m ground DEM for {area}", "run core 'derive' first")
    nlcd = gt.config_input(cfg, "nlcd_2021", EXP)
    with rasterio.open(dem_p) as r:
        ek.assert_crs(r, cfg["areas"][area]["crs"])
        dem = r.read(1).astype(np.float32)
        if r.nodata is not None:
            dem[dem == r.nodata] = np.nan
        tf, crs = r.transform, r.crs
    stable = stable_mask_from_nlcd(nlcd, dem.shape, tf, crs)
    rows = [{"stratum": "all", **gt.observable_share(depths, gt.min_detectable_depth(dem, stable))}]
    bp = gt.area_transfer_dir(area) / f"xfer_blocks_roles_{area}.gpkg"
    if bp.exists():
        import geopandas as gpd
        from rasterio.features import rasterize
        b = gpd.read_file(bp)
        for col in [c for c in cfg["prereg"]["strata"] if c in b]:
            for s, g in b.groupby(col):
                m = rasterize([(x, 1) for x in g.geometry], out_shape=dem.shape, transform=tf).astype(bool)
                rows.append({"stratum": f"{col}={s}", **gt.observable_share(depths, gt.min_detectable_depth(
                    np.where(m, dem, np.nan), stable & m))})
    floor = cfg["prereg"].get("observability_floor")
    df = pd.DataFrame(rows)
    df["observable_floor"] = floor
    df["readiness"] = ["unset floor (user decision)" if floor is None else
                       ("observable" if s >= floor else "target not observable") for s in df["share"]]
    return df


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", default=None)
    ap.add_argument("--ref-only", action="store_true")
    ap.add_argument("--max-pits", type=int, default=0, help="pilot cap on 9t pits (0 = all)")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    ref_p = ek.sub(EXP, "results/tables") / "gulf_pit_depths_ref_9t.csv"
    try:
        if ref_p.exists() and not a.max_pits:
            ref = pd.read_csv(ref_p)
        else:
            ref = ref_depths(a.max_pits)
            ref.to_csv(ref_p, index=False)
            ek.write_provenance(ref_p.parent, outputs=[ref_p], params={"ring_m": 5.0, "layer": "pit_inside"})
        q = np.nanpercentile(ref["depth_m"], [10, 25, 50, 75, 90])
        print(f"9t pit depths n={ref['depth_m'].notna().sum()} p10..p90 = {np.round(q, 3)}  ({ref_p})")
        if a.ref_only or not a.area:
            return 0
        df = audit_area(a.area, ref["depth_m"].to_numpy(), cfg)
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    out = gt.area_transfer_dir(a.area) / f"xfer_observable_depth_{a.area}.csv"
    df.to_csv(out, index=False)
    print(df.to_string(index=False), f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
