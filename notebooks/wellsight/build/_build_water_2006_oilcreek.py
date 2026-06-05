"""Build a class-9 water mask from the 2006-2008 PA Statewide LiDAR over the
22-tile Oil Creek mosaic footprint, on the same UTM-17N grid as the 2019
mosaic so we can do change-detection.

The 2006-2008 collection has a mislabeled CRS (header claims EPSG:32128, but
XY values are PA SP North in US-survey feet -- EPSG:2271 -- and Z is also in
US ft). We override the source CRS and apply ``Z = Z * 0.3048`` before
reprojection to EPSG:6346 (UTM 17N, m).

Outputs (next to the 2019 water rasters):
  water_count_2006_oilcreek_22tile_1m.tif    uint16 class-9 returns per cell
  water_mask_2006_oilcreek_22tile_1m.tif     uint8 0/1 raw mask
  water_solid_2006_oilcreek_22tile_1m.tif    uint8 morphological-close mask
  water_banks_2006_oilcreek_22tile_1m.tif    uint8 DEM-constrained bank fill
  water_polygons_banks_2006_oilcreek_22tile.gpkg  polygon vector
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio import features
from scipy.ndimage import (
    binary_closing, distance_transform_edt, label, median_filter)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT, make_profile, run_pdal

KEY = "oilcreek_22tile"
TAG = "2006"
RES = 1.0
OUT_DIR = DERIV / "extras" / KEY
SRC_DIR = ROOT / "data" / "files" / "older_files"
PLAN = ROOT / "data" / "external" / "oil_creek" / "statewide_2006_plan.txt"


def disk(r_m: float, res: float = 1.0) -> np.ndarray:
    r = int(round(r_m / res))
    y, x = np.mgrid[-r:r+1, -r:r+1]
    return ((x*x + y*y) <= r*r).astype(bool)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--close-r", type=float, default=12.0)
    ap.add_argument("--min-area", type=float, default=300.0)
    ap.add_argument("--tol", type=float, default=0.5)
    ap.add_argument("--max-radius", type=float, default=40.0)
    args = ap.parse_args()

    dem_path = OUT_DIR / f"dem_{KEY}_1m.tif"
    if not dem_path.exists():
        print(f"missing 2019 DEM template: {dem_path}", file=sys.stderr); return 1
    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        dem_nodata = r.nodata
        H, W = r.height, r.width
        transform = r.transform; crs = r.crs
        left, top = transform.c, transform.f
        bottom = top - H * RES
    print(f"target grid {W}x{H}  bbox {left:.0f},{bottom:.0f},{left+W*RES:.0f},{top:.0f}")

    names = [u.rsplit("/", 1)[-1] for u in PLAN.read_text().splitlines() if u.strip()]
    paths = [SRC_DIR / n for n in names]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"ERROR {len(missing)} missing LAZ:\n  " +
              "\n  ".join(p.name for p in missing[:5]), file=sys.stderr)
        return 1
    print(f"{len(paths)} 2006-2008 LAZ inputs")

    # 1) class-9 count raster on the 2019 grid
    count_path = OUT_DIR / f"water_count_{TAG}_{KEY}_1m.tif"
    if not count_path.exists():
        stages: list = [{"type": "readers.las", "filename": str(p),
                         "override_srs": "EPSG:2271"} for p in paths]
        stages.append({"type": "filters.merge"})
        stages.append({"type": "filters.assign", "value": "Z = Z * 0.3048"})
        stages.append({"type": "filters.reprojection",
                       "in_srs": "EPSG:2271", "out_srs": DST_CRS})
        stages.append({"type": "filters.range", "limits": "Classification[9:9]"})
        stages.append({"type": "writers.gdal",
                       "filename": str(count_path),
                       "resolution": RES, "output_type": "count",
                       "data_type": "uint16",
                       "origin_x": left, "origin_y": bottom,
                       "width": W, "height": H, "nodata": 0})
        t0 = time.time()
        run_pdal(stages, label=f"water_{TAG}_{KEY}", tmp_dir=OUT_DIR, timeout=3600)
        print(f"count raster in {time.time()-t0:.1f}s")

    with rasterio.open(count_path) as r:
        cnt = r.read(1)
    raw = (cnt > 0)
    print(f"raw class-9 cells: {int(raw.sum()):,}  ({raw.sum()/(H*W)*100:.2f}%)")

    # Save raw mask
    mask_path = OUT_DIR / f"water_mask_{TAG}_{KEY}_1m.tif"
    sprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="uint8", nodata=255, bigtiff=True)
    with rasterio.open(mask_path, "w", **sprof) as ds:
        ds.write(raw.astype(np.uint8), 1)
    print(f"wrote {mask_path.name}")

    # 2) morphological closing + min-area filter
    closed = binary_closing(raw, structure=disk(args.close_r), iterations=1,
                            border_value=0)
    lab, _ = label(closed, structure=np.ones((3, 3), dtype=bool))
    sizes = np.bincount(lab.ravel())
    keep = sizes >= max(1, int(round(args.min_area / (RES * RES))))
    keep[0] = False
    solid = keep[lab]
    print(f"solid (closed + filtered): {int(solid.sum()):,} cells  "
          f"({int(keep.sum())} components)")

    solid_path = OUT_DIR / f"water_solid_{TAG}_{KEY}_1m.tif"
    with rasterio.open(solid_path, "w", **sprof) as ds:
        ds.write(solid.astype(np.uint8), 1)
    print(f"wrote {solid_path.name}")

    # 3) bank fill using the 2019 DEM
    bad_dem = (~np.isfinite(dem) if dem_nodata is None
               else (dem == dem_nodata) | ~np.isfinite(dem))
    lab2, n2 = label(solid, structure=np.ones((3, 3), dtype=bool))
    z_water = np.zeros(n2 + 1, dtype=np.float32)
    for k in range(1, n2 + 1):
        m = (lab2 == k) & ~bad_dem
        z_water[k] = float(np.median(dem[m])) if m.sum() >= 5 else np.nan
    dist, (ny, nx) = distance_transform_edt(~solid, return_indices=True)
    nearest = lab2[ny, nx]
    nz = z_water[nearest]; nz[np.isnan(nz)] = -1e9
    bank = (~bad_dem) & (dist <= args.max_radius) & (dem <= nz + args.tol)
    bank |= solid
    bank = median_filter(bank.astype(np.uint8), size=3).astype(bool)
    lab3, _ = label(bank, structure=np.ones((3, 3), dtype=bool))
    sz3 = np.bincount(lab3.ravel())
    keep3 = sz3 >= max(1, int(round(args.min_area / (RES * RES))))
    keep3[0] = False
    bank = keep3[lab3]
    print(f"banked: {int(bank.sum()):,} cells  ({int(keep3.sum())} components)")

    bank_path = OUT_DIR / f"water_banks_{TAG}_{KEY}_1m.tif"
    with rasterio.open(bank_path, "w", **sprof) as ds:
        ds.write(bank.astype(np.uint8), 1)
    print(f"wrote {bank_path.name}")

    # 4) polygonize
    try:
        import geopandas as gpd
        from shapely.geometry import shape
        polys = []
        for geom, val in features.shapes(bank.astype(np.uint8),
                                         mask=bank, transform=transform):
            sg = shape(geom)
            polys.append({"geometry": sg, "area_m2": sg.area})
        if polys:
            gpkg = OUT_DIR / f"water_polygons_banks_{TAG}_{KEY}.gpkg"
            gdf = gpd.GeoDataFrame(polys, crs=crs)
            gdf.to_file(gpkg, driver="GPKG", layer=f"water_banks_{TAG}")
            print(f"wrote {gpkg.name}  ({len(polys)} polygons)")
            top = gdf.nlargest(5, "area_m2")["area_m2"].tolist()
            print("  top 5 areas (m^2):", ", ".join(f"{v:,.0f}" for v in top))
    except Exception as e:
        print(f"  polygonize failed: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
