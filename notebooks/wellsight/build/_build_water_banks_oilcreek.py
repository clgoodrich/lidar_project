"""Fill the LiDAR water returns laterally to the actual bank edges using the
DEM as a constraint.

Logic:
  1. Start from the cleaned solid water mask (LiDAR class-9 returns + small
     morphological closing).
  2. For each connected component, compute the local water-surface elevation
     z_water as the median DEM value under the mask cells.
  3. Region-grow each component: a cell becomes water if
        DEM(cell) <= z_water(nearest_component) + tol      AND
        distance(cell, nearest_component) <= max_radius_m
     The DEM threshold is what closes the bank-to-bank gap -- everything
     lower than the water surface around a stream segment fills in.
  4. Light cleanup: small-component drop + tiny closing.

Outputs:
  water_banks_<key>_1m.tif       uint8 filled-to-bank mask
  water_polygons_banks_<key>.gpkg polygon vector
  dist_to_water_banks_<key>_1m.tif distance raster from the banked mask

CLI:
  python notebooks/wellsight/build/_build_water_banks_oilcreek.py
  python notebooks/wellsight/build/_build_water_banks_oilcreek.py --tol 0.4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio import features
from scipy.ndimage import (
    binary_closing, distance_transform_edt, label, median_filter)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, make_profile

KEY = "oilcreek_22tile"
RES = 1.0
OUT_DIR = DERIV / "extras" / KEY


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=0.5,
                    help="metres above water surface still counted as water "
                         "(default 0.5 m -- captures shallow shoals/edges)")
    ap.add_argument("--max-radius", type=float, default=40.0,
                    help="maximum lateral spread from a water seed (m); "
                         "prevents the fill from leaking into a different "
                         "valley with similar elevation")
    ap.add_argument("--min-area", type=float, default=500.0,
                    help="drop final components smaller than this (m^2)")
    args = ap.parse_args()

    solid_path = OUT_DIR / f"water_solid_{KEY}_1m.tif"
    dem_path = OUT_DIR / f"dem_{KEY}_1m.tif"
    for p in (solid_path, dem_path):
        if not p.exists():
            print(f"missing input: {p}", file=sys.stderr); return 1

    with rasterio.open(solid_path) as r:
        seed = (r.read(1) > 0)
        transform = r.transform; crs = r.crs
        H, W = r.height, r.width
    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        dem_nodata = r.nodata
    bad_dem = ~np.isfinite(dem) if dem_nodata is None else (dem == dem_nodata) | ~np.isfinite(dem)

    print(f"grid {W}x{H}  seed water cells: {int(seed.sum()):,}")

    # 1) Per-component water-surface elevation
    lab, n_lab = label(seed, structure=np.ones((3, 3), dtype=bool))
    z_water = np.zeros(n_lab + 1, dtype=np.float32)
    for k in range(1, n_lab + 1):
        m = (lab == k) & ~bad_dem
        if m.sum() < 5:
            z_water[k] = np.nan
            continue
        z_water[k] = float(np.median(dem[m]))
    valid_lab_count = int(np.isfinite(z_water[1:]).sum())
    print(f"components with z_water: {valid_lab_count}/{n_lab}")

    # 2) Nearest-seed map: for each cell, which seed-cell index is closest
    #    `distance_transform_edt(... return_indices=True)` gives the (row,col)
    #    of the nearest True pixel in the input mask.
    dist, (ny, nx) = distance_transform_edt(~seed, return_indices=True)
    nearest_lab = lab[ny, nx]
    nearest_z = z_water[nearest_lab]
    nearest_z[np.isnan(nearest_z)] = -1e9

    # 3) Fill: DEM <= z_water + tol AND within max_radius AND DEM is valid
    bank = (~bad_dem) & (dist <= args.max_radius) & (dem <= nearest_z + args.tol)
    bank |= seed  # always keep the original water hits
    bank_cells = int(bank.sum())
    print(f"after bank fill: {bank_cells:,}  "
          f"(+{(bank_cells - seed.sum())/max(seed.sum(),1)*100:.1f}%)")

    # 4) Smooth a touch -- median filter to drop salt-and-pepper artefacts
    bank = median_filter(bank.astype(np.uint8), size=3).astype(bool)
    # Drop tiny components
    lab2, n2 = label(bank, structure=np.ones((3, 3), dtype=bool))
    sizes = np.bincount(lab2.ravel())
    keep = sizes >= max(1, int(round(args.min_area / (RES * RES))))
    keep[0] = False
    bank = keep[lab2]
    print(f"final components: {int(keep.sum())}  cells: {int(bank.sum()):,}  "
          f"({bank.sum()/(H*W)*100:.2f}% of grid)")

    # Write raster
    out_tif = OUT_DIR / f"water_banks_{KEY}_1m.tif"
    sprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="uint8", nodata=255, bigtiff=True)
    with rasterio.open(out_tif, "w", **sprof) as ds:
        ds.write(bank.astype(np.uint8), 1)
    print(f"wrote {out_tif.name}")

    # Polygonize
    try:
        import geopandas as gpd
        from shapely.geometry import shape
        polys = []
        for geom, val in features.shapes(bank.astype(np.uint8),
                                         mask=bank, transform=transform):
            sg = shape(geom)
            polys.append({"geometry": sg, "area_m2": sg.area})
        if polys:
            gpkg = OUT_DIR / f"water_polygons_banks_{KEY}.gpkg"
            gdf = gpd.GeoDataFrame(polys, crs=crs)
            gdf.to_file(gpkg, driver="GPKG", layer="water_banks")
            print(f"wrote {gpkg.name}  ({len(polys)} polygon(s))")
            top = gdf.nlargest(5, "area_m2")["area_m2"].tolist()
            print("  top 5 areas (m^2):", ", ".join(f"{v:,.0f}" for v in top))
    except Exception as e:
        print(f"  polygonize failed: {e}")

    # Distance raster
    d = distance_transform_edt(~bank).astype(np.float32) * RES
    dpath = OUT_DIR / f"dist_to_water_banks_{KEY}_1m.tif"
    dprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="float32", nodata=-1.0, bigtiff=True)
    with rasterio.open(dpath, "w", **dprof) as ds:
        ds.write(d, 1)
    print(f"wrote {dpath.name}  max={d.max():.0f} m  median={np.median(d):.0f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
