"""S4 (3.4). Water mask, wetland and void strata per block, then the seeded role draw.

Purpose
    Hydro-flattened water erases depressions, so water polygons are masked and listed, never scored.
    Per 375 m block compute wetland share (NLCD 2021 classes 90 and 95, union with NWI polygons),
    water share, and the void fraction from S2. Assign wet_stratum (dry, mixed, wet) and void_stratum
    (low, mid, high) with the prereg cut points. Masked water area leaves the eligible area.
    Then draw roles with the core seeded draw stratified by wet_stratum, with the derived P1 buffer.
Inputs
    data/<area>/results/transfer/xfer_density_void_<area>.csv     (core 'density')
    NLCD 2021, NWI polygons, hydro-flattened water polygons         (config inputs, assumed)
Outputs
    data/<area>/results/transfer/xfer_blocks_roles_<area>.gpkg     (block_id, role, edge, eligible,
        wet_share, water_share, void_frac_05, wet_stratum, void_stratum, eligible_km2)
    data/<area>/results/transfer/xfer_water_mask_<area>.gpkg       (masked polygons, listed)
Run
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_wetland_strata.py --area la_caddo
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
WET_NLCD = (90, 95)


def cut(values, cuts, names):
    v = np.asarray(values, float)
    out = np.array([names[int(np.searchsorted(cuts, x, side="right"))] if np.isfinite(x) else "unknown"
                    for x in v], dtype=object)
    return out


def nlcd_share(blocks, nlcd_path: Path, classes) -> np.ndarray:
    """Share of each block in the given NLCD classes (reprojected nearest to 10 m inside each block)."""
    import rasterio
    from rasterio.warp import Resampling, reproject
    from rasterio.transform import from_origin
    out = []
    with rasterio.open(nlcd_path) as r:
        for geom in blocks.geometry:
            x0, y0, x1, y1 = geom.bounds
            n = int(round((x1 - x0) / 10.0))
            dst = np.zeros((n, n), np.uint8)
            reproject(rasterio.band(r, 1), dst, dst_transform=from_origin(x0, y1, 10.0, 10.0),
                      dst_crs=blocks.crs, resampling=Resampling.nearest)
            out.append(float(np.isin(dst, classes).mean()))
    return np.array(out)


def polygon_share(blocks, polys) -> np.ndarray:
    if polys is None or polys.empty:
        return np.zeros(len(blocks))
    polys = polys.to_crs(blocks.crs)
    u = polys.geometry.union_all()
    return np.array([g.intersection(u).area / g.area for g in blocks.geometry])


def build_strata(blocks, density: pd.DataFrame | None, wet_share, water_share, cfg: dict):
    pr = cfg["prereg"]
    g = blocks.copy()
    g["wet_share"] = wet_share
    g["water_share"] = water_share
    if density is not None:
        g = g.merge(density[["block_id", "void_frac_05", "ground_ppm2"]], on="block_id", how="left")
    else:
        g["void_frac_05"] = np.nan
    g["wet_stratum"] = cut(g["wet_share"], pr["wet_cuts"], ["dry", "mixed", "wet"])
    g["void_stratum"] = cut(g["void_frac_05"], pr["void_cuts"], ["low", "mid", "high"])
    g["eligible_km2"] = g["area_km2"] * (1 - g["water_share"])
    over = g["void_frac_05"].fillna(0) > pr.get("void_cap", 1.0)
    g["eligible"] = ~g["edge"] & ~over & (g["water_share"] < 0.5)
    return g


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    import geopandas as gpd
    try:
        blocks = gt._blocks_for_area(cfg, a.area, EXP)
        dens_p = gt.area_transfer_dir(a.area) / f"xfer_density_void_{a.area}.csv"
        density = pd.read_csv(gt.require_input(dens_p, "S2 density and void table", "core 'density'"))
        nlcd = gt.config_input(cfg, "nlcd_2021", EXP)
        nwi = gpd.read_file(gt.config_input(cfg, "nwi_polygons", EXP))
        water = gpd.read_file(gt.config_input(cfg, "water_polygons", EXP))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    wet = np.maximum(nlcd_share(blocks, nlcd, WET_NLCD), polygon_share(blocks, nwi))
    wat = polygon_share(blocks, water)
    g = build_strata(blocks, density, wet, wat, cfg)
    pr = cfg["prereg"]
    ac = cfg["areas"][a.area]
    roles = gt.assign_roles(g, ac.get("role_fractions", {"test": 1.0}), int(pr["master_seed"]),
                            float(pr["buffer_m"]), strata_col="wet_stratum")
    roles["eligible"] = g["eligible"].to_numpy() & (roles["role"] != "buffer").to_numpy()
    out = gt.area_transfer_dir(a.area) / f"xfer_blocks_roles_{a.area}.gpkg"
    roles.to_file(out, driver="GPKG")
    wm = gt.area_transfer_dir(a.area) / f"xfer_water_mask_{a.area}.gpkg"
    water.to_crs(blocks.crs).clip(blocks.total_bounds).to_file(wm, driver="GPKG")
    ek.write_provenance(out.parent, outputs=[out, wm], params={"cuts": [pr["wet_cuts"], pr["void_cuts"]]})
    print(pd.crosstab(roles["wet_stratum"], roles["role"]).to_string())
    print(f"masked water km2 = {(roles['area_km2'] * roles['water_share']).sum():.2f}")
    print(f"wrote {out}\nwrote {wm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
