"""Build t=10000 stream seeds (raster + shapefile linestrings) for the four
McKean 3x3 blocks.

For each block under data/derivatives/tiles/data_3x3/northcentral_b19/<key>/:
  1. WBT BreachDepressionsLeastCost on dem_<key>_1m.tif
  2. WBT D8Pointer + D8FlowAccumulation (cells, no log)
  3. WBT ExtractStreams threshold=10000
  4. WBT RasterStreamsToVector -> .shp linestrings (CRS forced to EPSG:6346
     since WBT vector writers don't propagate it through the d8 pointer)

Outputs per block (next to the DEM):
  stream_seed_t10000_<key>_1m.tif   uint8 binary stream raster
  streams_t10000_<key>_1m.shp       linestrings (with .prj/.shx/.dbf/.cpg)

CLI:
  python notebooks/wellsight/build/_build_streams_t10k_mckean.py
  python notebooks/wellsight/build/_build_streams_t10k_mckean.py --only e1423n2238
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV

REGION = DERIV / "tiles" / "data_3x3" / "northcentral_b19"
DEFAULT_THRESHOLD = 10_000
CRS_EPSG = 6346  # UTM 17N (m) — matches DST_CRS used throughout

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


def find_blocks(only: set[str] | None) -> list[tuple[str, Path, Path]]:
    out: list[tuple[str, Path, Path]] = []
    if not REGION.exists():
        return out
    for sub in sorted(p for p in REGION.iterdir() if p.is_dir()):
        key = sub.name
        if only and key not in only:
            continue
        dem = sub / f"dem_{key}_1m.tif"
        if dem.exists():
            out.append((key, sub, dem))
    return out


def build_one(key: str, work: Path, dem: Path, *,
              threshold: int, overwrite: bool) -> None:
    seed_path = work / f"stream_seed_t{threshold}_{key}_1m.tif"
    shp_path = work / f"streams_t{threshold}_{key}_1m.shp"
    if seed_path.exists() and shp_path.exists() and not overwrite:
        print(f"[{key}] skip (raster + shp exist)")
        return

    import whitebox
    wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(work.resolve()))

    breach = f"_breach_{key}.tif"
    pntr = f"_d8pntr_{key}.tif"
    accum = f"_d8accum_{key}.tif"
    streams_raw = f"_streams_t{threshold}_{key}.tif"
    streams_vec = f"streams_t{threshold}_{key}_1m.shp"

    t0 = time.time()
    print(f"[{key}] DEM={dem.name}")
    if not (work / breach).exists():
        rc = wbt.breach_depressions_least_cost(
            dem=dem.name, output=breach, dist=50, flat_increment=1e-3)
        print(f"  breach rc={rc}")
    rc = wbt.d8_pointer(dem=breach, output=pntr); print(f"  d8_pointer rc={rc}")
    rc = wbt.d8_flow_accumulation(i=breach, output=accum,
                                   out_type="cells", log=False)
    print(f"  d8_flow_accumulation rc={rc}")
    rc = wbt.extract_streams(flow_accum=accum, output=streams_raw,
                              threshold=threshold)
    print(f"  extract_streams rc={rc} threshold={threshold}")

    # Convert WBT's NoData-background raster -> clean 0/1 uint8.
    with rasterio.open(work / streams_raw) as r:
        arr = r.read(1)
        nd = r.nodata
        prof = r.profile.copy()
    seed = np.isfinite(arr) & (arr != (nd if nd is not None else -9999))
    prof.update(dtype="uint8", nodata=255, compress="lzw")
    with rasterio.open(seed_path, "w", **prof) as ds:
        ds.write(seed.astype(np.uint8), 1)
    print(f"  wrote {seed_path.name} cells={int(seed.sum()):,}")

    # Vectorize to linestrings.
    rc = wbt.raster_streams_to_vector(streams=streams_raw, d8_pntr=pntr,
                                       output=streams_vec)
    print(f"  raster_streams_to_vector rc={rc}")
    # WBT drops the CRS; rewrite the sidecar .prj.
    prj = work / (Path(streams_vec).stem + ".prj")
    prj.write_text(PRJ_WKT)

    # Set CRS on the geopandas side too so downstream consumers don't
    # re-prompt the user for a CRS dialog.
    try:
        import geopandas as gpd
        g = gpd.read_file(work / streams_vec)
        g = g.set_crs(epsg=CRS_EPSG, allow_override=True)
        g.to_file(work / streams_vec)
        n = len(g)
        try:
            tot = float(g.length.sum())
            print(f"  {n} linestrings, total length = {tot/1000:.2f} km")
        except Exception:
            print(f"  {n} linestrings")
    except Exception as e:
        print(f"  geopandas post-fix skipped: {e}")

    # Clean intermediates.
    for nm in (pntr, accum, streams_raw):
        try: (work / nm).unlink()
        except OSError: pass
    # Keep breach raster around -- it's reusable for TWI/SPI later.
    print(f"[{key}] done in {time.time()-t0:.1f}s\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated key filter "
                                    "(e.g. e1423n2238,e1426n2236)")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                    help="flow-accumulation threshold in cells (default 10000)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    jobs = find_blocks(only)
    if not jobs:
        print("no McKean blocks found", file=sys.stderr); return 1
    print(f"{len(jobs)} block(s):")
    for k, _, _ in jobs:
        print(f"  {k}")

    t0 = time.time()
    for key, work, dem in jobs:
        try:
            build_one(key, work, dem, threshold=args.threshold,
                      overwrite=args.overwrite)
        except Exception as e:
            print(f"[{key}] FAILED: {e}")
    print(f"ALL DONE in {(time.time()-t0)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
