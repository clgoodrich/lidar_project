"""Clip TIGER 2024 'All Roads' for Venango (42121) and McKean (42083) counties
to the union of every hillshade footprint built so far.

Inputs:
  data/external/tiger_roads/tl_2024_{42121,42083}_roads.shp  (EPSG:4269 by default)
  data/derivatives/mosaic_3x3/<key>/hillshade_1m.tif         (14 Venango blocks)
  data/derivatives/mosaic_3x3_mckean/<key>/hillshade_1m.tif  (4 McKean blocks)
  data/derivatives/hillshade_9t_1m.tif                       (legacy 9t block)
  data/derivatives/hillshade_mkf_1m.tif, hillshade_mk5_1m.tif (legacy McKean)

Hillshade footprint = the polygon of *valid (non-nodata)* pixels. We compute
this per raster and dissolve the union.

Output:
  data/external/tiger_roads/roads_clipped.gpkg     (EPSG:6346, all matching roads)
  data/external/tiger_roads/hillshade_footprint.gpkg  (EPSG:6346, the clip polygon)
"""
from __future__ import annotations
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio import features
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
TIGER_DIR = ROOT / "data" / "external" / "tiger_roads"
DERIV = ROOT / "data" / "derivatives"
DST_CRS = "EPSG:6346"

HILLSHADES = []
# New 3x3 Venango blocks
HILLSHADES += list((DERIV / "mosaic_3x3").glob("*/hillshade_1m.tif"))
# New 3x3 McKean blocks
HILLSHADES += list((DERIV / "mosaic_3x3_mckean").glob("*/hillshade_1m.tif"))
# Legacy single-tile hillshades that are still live
for name in ("hillshade_9t_1m.tif", "hillshade_mkf_1m.tif", "hillshade_mk5_1m.tif"):
    p = DERIV / name
    if p.exists():
        HILLSHADES.append(p)


def raster_footprint(tif: Path):
    """Return a shapely polygon of valid (non-nodata, non-NaN) pixels, in raster CRS."""
    with rasterio.open(tif) as ds:
        arr = ds.read(1)
        nd = ds.nodata
        if nd is None:
            mask = np.isfinite(arr).astype(np.uint8)
        else:
            mask = ((arr != nd) & np.isfinite(arr)).astype(np.uint8)
        if mask.sum() == 0:
            return None, ds.crs
        polys = [shape(g) for g, v in features.shapes(mask, transform=ds.transform) if v == 1]
        return unary_union(polys), ds.crs


def main():
    print(f"hillshades to dissolve: {len(HILLSHADES)}")
    geoms = []
    for tif in HILLSHADES:
        g, crs = raster_footprint(tif)
        if g is None:
            continue
        gs = gpd.GeoSeries([g], crs=crs).to_crs(DST_CRS)
        geoms.append(gs.iloc[0])
        print(f"  {tif.relative_to(ROOT)}  CRS={crs.to_epsg()}")
    fp = unary_union(geoms)
    fp_gdf = gpd.GeoDataFrame(geometry=[fp], crs=DST_CRS)
    fp_path = TIGER_DIR / "hillshade_footprint.gpkg"
    fp_gdf.to_file(fp_path, driver="GPKG")
    print(f"footprint area: {fp.area / 1e6:.2f} km²  ->  {fp_path}")

    # Load + reproject TIGER roads
    shp_paths = sorted(TIGER_DIR.glob("tl_2024_*_roads.shp"))
    print(f"\nloading {len(shp_paths)} TIGER shapefiles ...")
    parts = []
    for p in shp_paths:
        g = gpd.read_file(p)
        fips = p.stem.split("_")[2]
        g["county_fips"] = fips
        parts.append(g)
        print(f"  {p.name}: {len(g):,} roads, crs={g.crs.to_epsg()}")
    roads = pd.concat(parts, ignore_index=True)
    roads = gpd.GeoDataFrame(roads, geometry="geometry", crs=parts[0].crs).to_crs(DST_CRS)
    print(f"combined: {len(roads):,} roads in {DST_CRS}")

    # Clip to footprint (intersection)
    clipped = gpd.clip(roads, fp_gdf)
    # Drop any rows that became empty / invalid
    clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()]
    out = TIGER_DIR / "roads_clipped.gpkg"
    clipped.to_file(out, driver="GPKG")
    total_len_km = clipped.length.sum() / 1000.0
    print(f"\nclipped roads: {len(clipped):,} features, total length {total_len_km:.1f} km")
    print(f"wrote {out}")

    # Quick breakdown by MTFCC (TIGER road class)
    if "MTFCC" in clipped.columns:
        print("\nby MTFCC:")
        for mtfcc, sub in clipped.groupby("MTFCC"):
            print(f"  {mtfcc}: {len(sub):,}  ({sub.length.sum()/1000:.1f} km)")


if __name__ == "__main__":
    main()
