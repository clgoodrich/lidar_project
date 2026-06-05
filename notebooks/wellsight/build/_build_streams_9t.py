"""Build a stream network (raster seed + vector linestrings) for the 9t mosaic
at an arbitrary flow-accumulation threshold.

Models the McKean per-block builder (_build_streams_t10k_mckean.py) but targets
the single 9t tile and reuses the already-conditioned breached DEM
(dem_breached_9t_1m.tif) so the slow BreachDepressionsLeastCost step is skipped.

Outputs in data/derivatives/9t/:
  stream_seed_t<th>_9t_1m.tif    uint8 0/1 stream raster
  streams_t<th>_9t_1m.shp        linestrings (+ .prj/.shx/.dbf/.cpg)
  streams_t<th>_9t_1m.gpkg       same, GeoPackage (matches t10000 convention)

CLI:
  python notebooks/wellsight/build/_build_streams_9t.py --threshold 5000
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV  # noqa: E402

OUT_DIR = DERIV / "9t"
SFX = "9t_1m"
CRS_EPSG = 6346
BREACHED = OUT_DIR / f"dem_breached_{SFX}.tif"   # reuse existing conditioned DEM
DEM_FLAT = DERIV / "dem_9t_1m.tif"               # fallback raw DEM if no breach

PRJ_WKT = (
    'PROJCS["NAD83(2011) / UTM zone 17N",'
    'GEOGCS["NAD83(2011)",DATUM["NAD83_National_Spatial_Reference_System_2011",'
    'SPHEROID["GRS 1980",6378137,298.257222101]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],'
    'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",-81],'
    'PARAMETER["scale_factor",0.9996],'
    'PARAMETER["false_easting",500000],PARAMETER["false_northing",0],'
    'UNIT["metre",1],AXIS["Easting",EAST],AXIS["Northing",NORTH],'
    'AUTHORITY["EPSG","6346"]]'
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=5000,
                    help="flow-accumulation threshold in cells (default 5000)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    th = args.threshold

    seed_path = OUT_DIR / f"stream_seed_t{th}_{SFX}.tif"
    shp_path = OUT_DIR / f"streams_t{th}_{SFX}.shp"
    gpkg_path = OUT_DIR / f"streams_t{th}_{SFX}.gpkg"
    if seed_path.exists() and shp_path.exists() and not args.overwrite:
        print(f"skip: {seed_path.name} + {shp_path.name} exist (use --overwrite)")
        return 0

    import whitebox
    wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(OUT_DIR.resolve()))

    # Condition the DEM only if the breached one is missing.
    if BREACHED.exists():
        breach = BREACHED.name
        print(f"reusing breached DEM: {breach}")
    else:
        if not DEM_FLAT.exists():
            print(f"missing DEM: {DEM_FLAT}", file=sys.stderr); return 1
        import shutil
        local = OUT_DIR / f"_dem_{SFX}.tif"
        if not local.exists():
            shutil.copy2(DEM_FLAT, local)
        breach = f"dem_breached_{SFX}.tif"
        print("breaching DEM (no cached breach found)...")
        rc = wbt.breach_depressions_least_cost(
            dem=local.name, output=breach, dist=50, flat_increment=1e-3)
        print(f"  breach rc={rc}")

    pntr = f"_d8pntr_{SFX}.tif"
    accum = f"_d8accum_{SFX}.tif"
    streams_raw = f"_streams_t{th}_{SFX}.tif"
    streams_vec = shp_path.name

    t0 = time.time()
    rc = wbt.d8_pointer(dem=breach, output=pntr); print(f"d8_pointer rc={rc}")
    rc = wbt.d8_flow_accumulation(i=breach, output=accum,
                                  out_type="cells", log=False)
    print(f"d8_flow_accumulation rc={rc}")
    rc = wbt.extract_streams(flow_accum=accum, output=streams_raw, threshold=th)
    print(f"extract_streams rc={rc} threshold={th}")

    # WBT NoData-background raster -> clean 0/1 uint8.
    with rasterio.open(OUT_DIR / streams_raw) as r:
        arr = r.read(1); nd = r.nodata; prof = r.profile.copy()
    seed = np.isfinite(arr) & (arr != (nd if nd is not None else -9999))
    prof.update(dtype="uint8", nodata=255, compress="lzw")
    with rasterio.open(seed_path, "w", **prof) as ds:
        ds.write(seed.astype(np.uint8), 1)
    print(f"wrote {seed_path.name} cells={int(seed.sum()):,}")

    # Vectorize to linestrings.
    rc = wbt.raster_streams_to_vector(streams=streams_raw, d8_pntr=pntr,
                                      output=streams_vec)
    print(f"raster_streams_to_vector rc={rc}")
    (OUT_DIR / (Path(streams_vec).stem + ".prj")).write_text(PRJ_WKT)

    # Fix CRS + also write a GeoPackage (matches the existing t10000 product).
    import geopandas as gpd
    g = gpd.read_file(OUT_DIR / streams_vec)
    g = g.set_crs(epsg=CRS_EPSG, allow_override=True)
    g.to_file(OUT_DIR / streams_vec)
    g.to_file(gpkg_path, driver="GPKG")
    print(f"wrote {streams_vec} + {gpkg_path.name}: {len(g)} lines, "
          f"{g.length.sum()/1000:.1f} km")

    for nm in (pntr, accum, streams_raw):
        (OUT_DIR / nm).unlink(missing_ok=True)
    print(f"DONE in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
