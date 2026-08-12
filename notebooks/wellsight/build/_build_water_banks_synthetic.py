"""DEM-only fallback water layer for blocks where the source LAZ has no
class-9 classification.

Pipeline per block:
  1. WBT BreachDepressionsLeastCost + D8FlowAccumulation on the existing DEM.
  2. Threshold log-flow-accumulation to a binary stream raster (this is the
     synthetic seed mask, analogous to class-9 hits in the LAZ version).
  3. Apply the same DEM-constrained bank fill: per connected component,
     compute median DEM elevation, then grow laterally where DEM <= z_water
     + tol and within max_radius m of a seed cell.
  4. Polygonize to a GeoPackage.

Outputs (next to the DEM):
  water_seed_synth_<key>.tif    uint8 binary stream raster
  water_banks_synth_<key>.tif   uint8 banked mask
  water_polygons_banks_synth_<key>.gpkg

CLI:
  python notebooks/wellsight/build/_build_water_banks_synthetic.py
  python notebooks/wellsight/build/_build_water_banks_synthetic.py --threshold 5000
  python notebooks/wellsight/build/_build_water_banks_synthetic.py --only wc_coaloil_1m,e1423n2238
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
from _common import DERIV, make_profile

RES = 1.0


def disk(r_m: float, res: float = 1.0) -> np.ndarray:
    r = int(round(r_m / res))
    y, x = np.mgrid[-r:r+1, -r:r+1]
    return ((x*x + y*y) <= r*r).astype(bool)


def find_dry_blocks() -> list[tuple[str, Path, Path]]:
    """Find DEM-bearing folders that don't already have a class-9 bank file."""
    out = []
    # data_3x3
    for region in ("westernpa_d20", "northcentral_b19"):
        parent = DERIV / "tiles" / "data_3x3" / region
        if not parent.exists(): continue
        for sub in sorted(p for p in parent.iterdir() if p.is_dir()):
            key = sub.name
            dem = sub / f"dem_{key}_1m.tif"
            if not dem.exists(): continue
            class9_banks = sub / f"water_banks_{key}_1m.tif"
            if class9_banks.exists():
                # Has class-9 water; only flag as "dry" if banks is empty.
                with rasterio.open(class9_banks) as r:
                    if (r.read(1) > 0).any(): continue
            out.append((f"data_3x3/{region}/{key}", sub, dem))
    # regions
    for region in ("sw_marcellus_1m", "wc_coaloil_1m", "nec_marcellus_1m"):
        sub = DERIV / "tiles" / region
        dem = sub / f"dem_{region}.tif"
        if not dem.exists(): continue
        class9_banks = sub / f"water_banks_{region}.tif"
        if class9_banks.exists():
            with rasterio.open(class9_banks) as r:
                if (r.read(1) > 0).any(): continue
        out.append((f"region/{region}", sub, dem))
    return out


def build_one(label_str: str, out_dir: Path, dem_path: Path, *,
              threshold: float, close_r: float, min_area: float,
              tol: float, max_radius: float, skip_existing: bool) -> None:
    key = dem_path.stem[len("dem_"):]  # strips the "dem_" prefix
    seed_path = out_dir / f"water_seed_synth_{key}.tif"
    bank_path = out_dir / f"water_banks_synth_{key}.tif"
    gpkg_path = out_dir / f"water_polygons_banks_synth_{key}.gpkg"
    if skip_existing and bank_path.exists() and gpkg_path.exists():
        print(f"[{label_str}] skip (exists)"); return

    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        dem_nodata = r.nodata
        H, W = r.height, r.width
        transform = r.transform; crs = r.crs

    print(f"[{label_str}] DEM {W}x{H}  threshold={threshold:.0f} px (flow accum)")

    # Run WBT hydrology — work in the block's folder so outputs stay grouped.
    import whitebox
    wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(out_dir.resolve()))
    breach_name = f"_wbt_breach_{key}.tif"
    pntr_name   = f"_wbt_d8pntr_{key}.tif"
    accum_name  = f"_wbt_d8accum_{key}.tif"
    streams_name= f"_wbt_streams_{key}.tif"

    t0 = time.time()
    rc = wbt.breach_depressions_least_cost(dem=dem_path.name, output=breach_name,
                                            dist=50, flat_increment=1e-3)
    if rc != 0:
        print(f"[{label_str}] breach FAILED rc={rc}"); return
    rc = wbt.d8_pointer(dem=breach_name, output=pntr_name)
    if rc != 0:
        print(f"[{label_str}] d8_pointer FAILED rc={rc}"); return
    rc = wbt.d8_flow_accumulation(i=breach_name, output=accum_name,
                                   out_type="cells", log=False)
    if rc != 0:
        print(f"[{label_str}] d8_flow_accumulation FAILED rc={rc}"); return
    rc = wbt.extract_streams(flow_accum=accum_name, output=streams_name,
                             threshold=threshold)
    if rc != 0:
        print(f"[{label_str}] extract_streams FAILED rc={rc}"); return
    print(f"[{label_str}] WBT hydrology in {time.time()-t0:.1f}s")

    with rasterio.open(out_dir / streams_name) as r:
        seed_raw = r.read(1)
    # ExtractStreams uses background = NoData; finite cells are the streams.
    if r.nodata is not None:
        seed = (seed_raw != r.nodata) & np.isfinite(seed_raw)
    else:
        seed = np.isfinite(seed_raw) & (seed_raw > 0)
    print(f"[{label_str}] synthetic seed cells: {int(seed.sum()):,}")
    # Save the seed for posterity (small file).
    seed_prof = make_profile(width=W, height=H, transform=transform, crs=crs,
                             dtype="uint8", nodata=255, bigtiff=False)
    with rasterio.open(seed_path, "w", **seed_prof) as ds:
        ds.write(seed.astype(np.uint8), 1)

    # Clean intermediates.
    for nm in (breach_name, pntr_name, accum_name, streams_name):
        try: (out_dir / nm).unlink()
        except OSError: pass

    if seed.sum() < 50:
        print(f"[{label_str}] no streams found at threshold; skip bank fill")
        return

    # 2) close + filter small components on the seed (matches class-9 path)
    closed = binary_closing(seed, structure=disk(close_r), iterations=1,
                            border_value=0)
    lab1, _ = label(closed, structure=np.ones((3, 3), dtype=bool))
    sz1 = np.bincount(lab1.ravel())
    keep1 = sz1 >= max(1, int(round(min_area / (RES * RES))))
    keep1[0] = False
    solid = keep1[lab1]

    # 3) bank fill against the DEM. Synthetic streams span huge longitudinal
    # elevation drops, so per-component median z_water is wrong. Use the DEM
    # at the *nearest seed cell* as the local water-surface elevation -- the
    # stream itself sits at that height by construction.
    bad_dem = (~np.isfinite(dem) if dem_nodata is None
               else (dem == dem_nodata) | ~np.isfinite(dem))
    dist, (ny, nx) = distance_transform_edt(~solid, return_indices=True)
    nz = dem[ny, nx]                       # DEM at the nearest seed cell
    nz_bad = bad_dem[ny, nx]
    bank = (~bad_dem) & (~nz_bad) & (dist <= max_radius) & (dem <= nz + tol)
    bank |= solid
    bank = median_filter(bank.astype(np.uint8), size=3).astype(bool)
    lab3, _ = label(bank, structure=np.ones((3, 3), dtype=bool))
    sz3 = np.bincount(lab3.ravel())
    keep3 = sz3 >= max(1, int(round(min_area / (RES * RES))))
    keep3[0] = False
    bank = keep3[lab3]

    bprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="uint8", nodata=255, bigtiff=True)
    with rasterio.open(bank_path, "w", **bprof) as ds:
        ds.write(bank.astype(np.uint8), 1)
    print(f"[{label_str}] banked: {int(bank.sum()):,} cells "
          f"({int(keep3.sum())} components)")

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
            gdf = gpd.GeoDataFrame(polys, crs=crs)
            gdf.to_file(gpkg_path, driver="GPKG",
                        layer=f"water_banks_synth_{key}")
            top = gdf.nlargest(3, "area_m2")["area_m2"].tolist()
            print(f"[{label_str}] {len(polys)} polygons  top: "
                  + ", ".join(f"{v:,.0f}" for v in top))
    except Exception as e:
        print(f"[{label_str}] polygonize failed: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated key/region filter")
    ap.add_argument("--threshold", type=float, default=50000.0,
                    help="flow accumulation threshold in cells (default 50000 "
                         "= 5 ha contributing area at 1m resolution; lower "
                         "captures finer tributaries but also over-fills)")
    ap.add_argument("--close-r", type=float, default=5.0)
    ap.add_argument("--min-area", type=float, default=500.0)
    ap.add_argument("--tol", type=float, default=0.3,
                    help="metres above seed elevation still counted as water")
    ap.add_argument("--max-radius", type=float, default=8.0,
                    help="max lateral spread from a seed cell (m)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    jobs = find_dry_blocks()
    if only:
        jobs = [j for j in jobs if any(o in j[0] for o in only)]
    if not jobs:
        print("no dry blocks found", file=sys.stderr); return 1
    print(f"{len(jobs)} dry block(s) to fill:")
    for label_str, _, _ in jobs: print(f"  {label_str}")
    t0_all = time.time()
    for label_str, out_dir, dem in jobs:
        try:
            build_one(label_str, out_dir, dem,
                      threshold=args.threshold, close_r=args.close_r,
                      min_area=args.min_area, tol=args.tol,
                      max_radius=args.max_radius,
                      skip_existing=not args.overwrite)
        except Exception as e:
            print(f"[{label_str}] FAILED: {e}")
    print(f"\nALL DONE in {(time.time()-t0_all)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
