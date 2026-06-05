"""Run the class-9 water + bank-fill pipeline across every block we already
built a DEM for:

  - data_3x3/westernpa_d20/<key>/   14 WP 4500x4500 m blocks
  - data_3x3/northcentral_b19/<key>/  4 NC 4500x4500 m blocks
  - data/derivatives/{sw_marcellus_1m,nec_marcellus_1m,wc_coaloil_1m}/
      3 region 4500x4500 m mosaics

For each: rasterize class-9 returns from the source LAZ tiles onto the same
1m UTM 17N grid as the DEM, morphologically close + drop tiny components,
then bank-fill laterally to the local water-surface elevation derived from
the DEM. Outputs land alongside the existing rasters in each folder.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import laspy
import numpy as np
import rasterio
from rasterio import features
from scipy.ndimage import (
    binary_closing, distance_transform_edt, label, median_filter)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DERIV, DST_CRS, ROOT, make_profile, run_pdal
from _build_3x3_hillshades import (  # type: ignore
    discover_tiles as discover_wp_tiles,
    enumerate_blocks as enumerate_wp_blocks,
)

RES = 1.0
NC_RE = re.compile(r"^e(\d{4})n(\d{4})$")
NC_SRC_DIR = ROOT / "data" / "mckean"
NC_SRC_CRS = "EPSG:6350"

REGION_PROJ_DIR = {
    "sw_marcellus_1m":  ROOT / "data" / "external" / "usgs_3dep_pa_lidar" / "laz" / "PA_WesternPA_2019_D20",
    "wc_coaloil_1m":    ROOT / "data" / "external" / "usgs_3dep_pa_lidar" / "laz" / "PA_WesternPA_2019_D20",
    "nec_marcellus_1m": ROOT / "data" / "external" / "usgs_3dep_pa_lidar" / "laz" / "PA_Northcentral_2019_B19",
}
REGION_SRC_CRS = {
    "sw_marcellus_1m":  None,
    "wc_coaloil_1m":    None,
    "nec_marcellus_1m": "EPSG:6350",
}


def disk(r_m: float, res: float = 1.0) -> np.ndarray:
    r = int(round(r_m / res))
    y, x = np.mgrid[-r:r+1, -r:r+1]
    return ((x*x + y*y) <= r*r).astype(bool)


def laz_intersects(p: Path, bbox_dst: tuple[float, float, float, float],
                   src_crs: str | None) -> bool:
    """True if the LAZ tile (after projecting its header bbox to UTM 17N)
    intersects the target bbox."""
    try:
        h = laspy.open(p).header
    except Exception:
        return False
    src_min = (h.x_min, h.y_min); src_max = (h.x_max, h.y_max)
    if src_crs is None:
        x0, y0 = src_min; x1, y1 = src_max
    else:
        from pyproj import Transformer
        t = Transformer.from_crs(src_crs, DST_CRS, always_xy=True)
        corners = [t.transform(x, y) for x in (src_min[0], src_max[0])
                                      for y in (src_min[1], src_max[1])]
        xs = [c[0] for c in corners]; ys = [c[1] for c in corners]
        x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
    bx0, by0, bx1, by1 = bbox_dst
    return not (x1 < bx0 or x0 > bx1 or y1 < by0 or y0 > by1)


def collect_jobs(only_keys, only_kind):
    jobs = []  # (label, out_dir, dem_path, members:list[Path], src_crs)

    # data_3x3 / westernpa_d20
    if only_kind in (None, "wp"):
        wp_tiles = discover_wp_tiles()
        wp_blocks = enumerate_wp_blocks(wp_tiles)
        wp_lookup = {b["key"]: list(b["members"]) for b in wp_blocks}
        parent = DERIV / "data_3x3" / "westernpa_d20"
        if parent.exists():
            for sub in sorted(p for p in parent.iterdir() if p.is_dir()):
                key = sub.name
                if only_keys and key not in only_keys: continue
                dem = sub / f"dem_{key}_1m.tif"
                if not dem.exists(): continue
                members = wp_lookup.get(key)
                if not members: continue
                jobs.append((f"wp/{key}", sub, dem, members, None))

    # data_3x3 / northcentral_b19
    if only_kind in (None, "nc"):
        parent = DERIV / "data_3x3" / "northcentral_b19"
        if parent.exists():
            for sub in sorted(p for p in parent.iterdir() if p.is_dir()):
                key = sub.name
                if only_keys and key not in only_keys: continue
                m = NC_RE.match(key)
                if not m: continue
                dem = sub / f"dem_{key}_1m.tif"
                if not dem.exists(): continue
                e0, n0 = int(m.group(1)), int(m.group(2))
                members = [NC_SRC_DIR / f"USGS_LPC_PA_Northcentral_2019_B19_e{e0+de}n{n0+dn}.laz"
                           for de in range(3) for dn in range(3)]
                if any(not p.exists() for p in members): continue
                jobs.append((f"nc/{key}", sub, dem, members, NC_SRC_CRS))

    # regions
    if only_kind in (None, "region"):
        for region_dir, proj_dir in REGION_PROJ_DIR.items():
            if only_keys and region_dir not in only_keys: continue
            sub = DERIV / region_dir
            dem = sub / f"dem_{region_dir}.tif"
            if not dem.exists() or not proj_dir.exists(): continue
            with rasterio.open(dem) as r:
                bb = r.bounds
            target_bbox = (bb.left, bb.bottom, bb.right, bb.top)
            src_crs = REGION_SRC_CRS[region_dir]
            members = [p for p in sorted(proj_dir.glob("*.laz"))
                       if laz_intersects(p, target_bbox, src_crs)]
            if not members: continue
            jobs.append((f"region/{region_dir}", sub, dem, members, src_crs))
    return jobs


def extract_water(label_str: str, out_dir: Path, dem_path: Path,
                  members: list[Path], src_crs: str | None,
                  *, key_for_files: str,
                  close_r: float, min_area: float,
                  tol: float, max_radius: float,
                  skip_existing: bool) -> None:
    sprof_paths = [out_dir / f"water_{name}_{key_for_files}.tif"
                   for name in ("count", "mask", "solid", "banks")]
    gpkg_path = out_dir / f"water_polygons_banks_{key_for_files}.gpkg"
    if skip_existing and all(p.exists() for p in sprof_paths) and gpkg_path.exists():
        print(f"[{label_str}] all outputs exist, skip"); return

    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        dem_nodata = r.nodata
        H, W = r.height, r.width
        transform = r.transform; crs = r.crs
        left, top = transform.c, transform.f
        bottom = top - H * RES
    sprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="uint8", nodata=255, bigtiff=True)
    cprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="uint16", nodata=0, bigtiff=True)

    count_path, mask_path, solid_path, bank_path = sprof_paths

    if not (count_path.exists() and skip_existing):
        stages: list = [str(p) for p in members]
        stages.append({"type": "filters.merge"})
        if src_crs:
            stages.append({"type": "filters.reprojection",
                           "in_srs": src_crs, "out_srs": DST_CRS})
        stages.append({"type": "filters.range", "limits": "Classification[9:9]"})
        stages.append({"type": "writers.gdal",
                       "filename": str(count_path),
                       "resolution": RES, "output_type": "count",
                       "data_type": "uint16",
                       "origin_x": left, "origin_y": bottom,
                       "width": W, "height": H, "nodata": 0})
        t0 = time.time()
        run_pdal(stages, label=f"water_{key_for_files}", tmp_dir=out_dir, timeout=3600)
        print(f"[{label_str}] count raster in {time.time()-t0:.1f}s "
              f"({len(members)} LAZ)")

    # Sometimes there are no class-9 returns at all -> writers.gdal won't
    # create the file. Handle gracefully.
    if not count_path.exists():
        print(f"[{label_str}] no class-9 returns; skipping mask/bank/polygon")
        return

    with rasterio.open(count_path) as r:
        cnt = r.read(1)
    raw = (cnt > 0)
    print(f"[{label_str}] raw class-9 cells: {int(raw.sum()):,}  "
          f"({raw.sum()/(H*W)*100:.2f}%)")
    if raw.sum() == 0:
        print(f"[{label_str}] empty water - skipping downstream"); return

    with rasterio.open(mask_path, "w", **sprof) as ds:
        ds.write(raw.astype(np.uint8), 1)

    closed = binary_closing(raw, structure=disk(close_r), iterations=1,
                            border_value=0)
    lab1, _ = label(closed, structure=np.ones((3, 3), dtype=bool))
    sz1 = np.bincount(lab1.ravel())
    keep1 = sz1 >= max(1, int(round(min_area / (RES * RES))))
    keep1[0] = False
    solid = keep1[lab1]
    with rasterio.open(solid_path, "w", **sprof) as ds:
        ds.write(solid.astype(np.uint8), 1)

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
    bank = (~bad_dem) & (dist <= max_radius) & (dem <= nz + tol)
    bank |= solid
    bank = median_filter(bank.astype(np.uint8), size=3).astype(bool)
    lab3, _ = label(bank, structure=np.ones((3, 3), dtype=bool))
    sz3 = np.bincount(lab3.ravel())
    keep3 = sz3 >= max(1, int(round(min_area / (RES * RES))))
    keep3[0] = False
    bank = keep3[lab3]
    with rasterio.open(bank_path, "w", **sprof) as ds:
        ds.write(bank.astype(np.uint8), 1)
    print(f"[{label_str}] banked cells: {int(bank.sum()):,}  "
          f"({int(keep3.sum())} components)")

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
                        layer=f"water_banks_{key_for_files}")
            top = gdf.nlargest(3, "area_m2")["area_m2"].tolist()
            print(f"[{label_str}] {len(polys)} polygons   top: "
                  + ", ".join(f"{v:,.0f}" for v in top))
    except Exception as e:
        print(f"[{label_str}] polygonize failed: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated key/region filter")
    ap.add_argument("--kind", choices=("wp", "nc", "region"),
                    help="restrict to one job type")
    ap.add_argument("--close-r", type=float, default=12.0)
    ap.add_argument("--min-area", type=float, default=300.0)
    ap.add_argument("--tol", type=float, default=0.5)
    ap.add_argument("--max-radius", type=float, default=40.0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    jobs = collect_jobs(only, args.kind)
    if not jobs:
        print("no jobs", file=sys.stderr); return 1
    print(f"{len(jobs)} job(s):")
    for label_str, out_dir, dem_path, members, src_crs in jobs:
        print(f"  {label_str}  ({len(members)} LAZ, src_crs={src_crs})")

    t0_all = time.time()
    for label_str, out_dir, dem_path, members, src_crs in jobs:
        # key_for_files = "<key>_1m" for blocks ; for regions the dem filename
        # already encodes the suffix - extract it.
        stem = dem_path.stem  # e.g. dem_604590_1m  or  dem_sw_marcellus_1m
        assert stem.startswith("dem_"), stem
        key_for_files = stem[len("dem_"):]
        try:
            extract_water(label_str, out_dir, dem_path, members, src_crs,
                          key_for_files=key_for_files,
                          close_r=args.close_r, min_area=args.min_area,
                          tol=args.tol, max_radius=args.max_radius,
                          skip_existing=not args.overwrite)
        except Exception as e:
            print(f"[{label_str}] FAILED: {e}")
            continue
    print(f"\nALL DONE in {(time.time()-t0_all)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
