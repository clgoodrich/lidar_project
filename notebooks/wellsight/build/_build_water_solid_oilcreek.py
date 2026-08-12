"""Turn the sparse class-9 water hits into a contiguous, solid water-body
mask + polygons for the 22-tile Oil Creek mosaic.

LiDAR water returns are speckled along streams because most pulses don't
return from a water surface. We solidify in 3 steps:

  1. Morphological closing on the raw mask (small disk, ~5 m radius) to
     bridge gaps along narrow streams.
  2. Connected-component filtering: drop blobs smaller than ``--min-area``
     m^2 (default 25) -- those are isolated noise hits, not stream segments.
  3. Polygonize the result to a GeoPackage for QGIS / shapely work.

Outputs (next to the existing rasters):
  water_solid_<key>_1m.tif         uint8 0/1 cleaned mask
  water_polygons_<key>.gpkg        polygon vector
  dist_to_water_solid_<key>_1m.tif float32 dist to cleaned mask (overwrites
                                   the speckled-input distance if present)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio import features
from scipy.ndimage import binary_closing, distance_transform_edt, label

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, make_profile

KEY = "oilcreek_22tile"
RES = 1.0
OUT_DIR = DERIV / "tiles" / "extras" / KEY


def disk_struct(r_m: float, res: float = 1.0) -> np.ndarray:
    r = int(round(r_m / res))
    y, x = np.mgrid[-r:r+1, -r:r+1]
    return ((x*x + y*y) <= r*r).astype(bool)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--close-r", type=float, default=5.0,
                    help="morphological closing disk radius in metres "
                         "(default 5; bigger = fills bigger gaps but also "
                         "fattens streams)")
    ap.add_argument("--min-area", type=float, default=25.0,
                    help="drop connected components smaller than this many "
                         "square metres (default 25 m^2)")
    args = ap.parse_args()

    mask_path = OUT_DIR / f"water_mask_{KEY}_1m.tif"
    if not mask_path.exists():
        print(f"missing input mask: {mask_path}", file=sys.stderr); return 1
    with rasterio.open(mask_path) as r:
        mask = (r.read(1) > 0)
        transform = r.transform; crs = r.crs
        H, W = r.height, r.width

    raw_cells = int(mask.sum())
    print(f"raw water cells: {raw_cells:,}  ({raw_cells/(H*W)*100:.2f}% of grid)")

    # 1) closing
    se = disk_struct(args.close_r)
    closed = binary_closing(mask, structure=se, iterations=1, border_value=0)
    closed_cells = int(closed.sum())
    print(f"after closing r={args.close_r:.0f}m: {closed_cells:,}  "
          f"(+{(closed_cells-raw_cells)/max(raw_cells,1)*100:.1f}%)")

    # 2) connected-component filter (8-connectivity)
    lab, n_lab = label(closed, structure=np.ones((3, 3), dtype=bool))
    sizes = np.bincount(lab.ravel())
    keep = sizes >= max(1, int(round(args.min_area / (RES * RES))))
    keep[0] = False  # background
    solid = keep[lab]
    n_components_in = n_lab
    n_components_out = int(keep.sum())
    print(f"connected components: {n_components_in} -> {n_components_out} "
          f"(dropped {n_components_in - n_components_out} blobs "
          f"smaller than {args.min_area:.0f} m^2)")
    print(f"solid water cells: {int(solid.sum()):,}  "
          f"({solid.sum()/(H*W)*100:.2f}% of grid)")

    # Write cleaned mask
    solid_path = OUT_DIR / f"water_solid_{KEY}_1m.tif"
    sprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="uint8", nodata=255, bigtiff=True)
    with rasterio.open(solid_path, "w", **sprof) as ds:
        ds.write(solid.astype(np.uint8), 1)
    print(f"wrote {solid_path.name}")

    # 3) Polygonize
    gpkg_path = OUT_DIR / f"water_polygons_{KEY}.gpkg"
    try:
        import geopandas as gpd
        from shapely.geometry import shape
        polys = []
        for geom, val in features.shapes(solid.astype(np.uint8),
                                         mask=solid, transform=transform):
            polys.append({"geometry": shape(geom), "area_m2": shape(geom).area})
        if polys:
            gdf = gpd.GeoDataFrame(polys, crs=crs)
            gdf.to_file(gpkg_path, driver="GPKG", layer="water")
            print(f"wrote {gpkg_path.name}  ({len(polys)} polygon(s))")
            top = gdf.nlargest(5, "area_m2")[["area_m2"]]
            print("  top 5 polygons by area (m^2):")
            for v in top["area_m2"]:
                print(f"    {v:,.0f}")
    except Exception as e:
        print(f"  polygonize failed: {e}")

    # 4) Refresh dist-to-water using the cleaned mask
    dist = distance_transform_edt(~solid).astype(np.float32) * RES
    dpath = OUT_DIR / f"dist_to_water_solid_{KEY}_1m.tif"
    dprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="float32", nodata=-1.0, bigtiff=True)
    with rasterio.open(dpath, "w", **dprof) as ds:
        ds.write(dist, 1)
    print(f"wrote {dpath.name}  "
          f"(max d-to-water = {float(dist.max()):.0f} m, "
          f"median = {float(np.median(dist)):.0f} m)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
