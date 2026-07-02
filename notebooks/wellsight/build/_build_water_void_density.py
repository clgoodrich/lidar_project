"""Detect open water as LiDAR-return VOIDS (density method, #1 from the
water-detection discussion).

Physics: a NIR LiDAR pulse is reflected away from the sensor by smooth water
(specular reflection), so open water returns ~no points. Forest canopy, by
contrast, still returns plenty. So an ALL-RETURN point-count raster cleanly
separates water (count ~0) from both bare ground and canopy -- unlike the
ground-only `ground_density_*.tif`, which is also low under dense canopy.

Pipeline (per --suffix, grid taken from the existing DEM):
  1. PDAL: rasterize ALL-return COUNT per cell over the DEM grid.
  2. void = (count <= --max-count).
  3. GATE: keep only voids within --stream-buf m of the mapped stream network
     (stream_seed_t<thr>_<key>_1m), so specular roofs / wet fields on uplands
     are rejected -- water voids should sit on the drainage network.
  4. Clean: remove specks < --min-area m^2, morphological close, fill holes.
  5. Polygonize -> water_void_<key>.gpkg (layer `water_void`); also write the
     count raster, the binary mask, and a hillshade overlay PNG for QC.

Outputs land in the suffix's tile dir (e.g. data/derivatives/tiles/9t/). That
dir is wholly gitignored, so nothing here leaks into git.

CLI:
  python notebooks/wellsight/build/_build_water_void_density.py --suffix 9t
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes as rio_shapes
from scipy.ndimage import binary_closing, binary_fill_holes, distance_transform_edt
from skimage.morphology import remove_small_objects

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT, read_tif, run_pdal, write_tif

# --- per-suffix registry: where the grid + source LAZ + stream net live -------
REG = {
    "9t": {
        "tile_dir": DERIV / "tiles" / "9t",
        "dem": DERIV / "tiles" / "9t" / "dem_9t_05.tif",
        "hillshade": DERIV / "tiles" / "9t" / "hillshade_9t_05.tif",
        "stream": DERIV / "tiles" / "9t" / "stream_seed_t5000_9t_1m.tif",
        "slope": DERIV / "tiles" / "9t" / "slope_9t_05.tif",
        "laz_glob": (ROOT / "data" / "source_laz" / "westernpa", "USGS_LPC_PA_WesternPA_2019_D20_*.laz"),
    },
}


def select_tiles(laz_dir: Path, pattern: str, bounds) -> list[Path]:
    """Return LAZ tiles whose header bbox intersects `bounds` (xmin,ymin,xmax,ymax)."""
    import laspy
    bx0, by0, bx1, by1 = bounds
    hits = []
    for p in sorted(laz_dir.glob(pattern)):
        try:
            with laspy.open(str(p)) as f:
                h = f.header
                tx0, ty0 = h.mins[0], h.mins[1]
                tx1, ty1 = h.maxs[0], h.maxs[1]
        except Exception as e:  # noqa: BLE001
            print(f"  ! header read failed {p.name}: {e}")
            continue
        if not (tx1 < bx0 or tx0 > bx1 or ty1 < by0 or ty0 > by1):
            hits.append(p)
    return hits


def build_count_raster(tiles: list[Path], grid, out_path: Path, tile_dir: Path) -> None:
    """PDAL: ALL-return count per cell on the DEM grid -> out_path (uint16)."""
    x0, y0, x1, y1, res, W, H = grid
    stages: list = [str(p) for p in tiles]
    if len(tiles) > 1:
        stages.append({"type": "filters.merge"})
    stages.append({
        "type": "writers.gdal",
        "filename": str(out_path),
        "resolution": res,
        "origin_x": x0, "origin_y": y0,
        "width": W, "height": H,
        "output_type": "count",
        "data_type": "uint16",
        "nodata": 0,
        "gdaldriver": "GTiff",
    })
    run_pdal(stages, label=f"watervoid_count", tmp_dir=tile_dir, timeout=3600)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", default="9t", choices=sorted(REG))
    ap.add_argument("--max-count", type=int, default=1,
                    help="cells with <= this many returns are candidate water (default 1)")
    ap.add_argument("--stream-buf", type=float, default=40.0,
                    help="keep voids within this many m of a mapped stream (default 40)")
    ap.add_argument("--max-slope", type=float, default=2.0,
                    help="keep only voids flatter than this (deg); water interpolates "
                         "to ~0 deg, sloped dropouts are rejected (default 2.0; 0=off)")
    ap.add_argument("--min-area", type=float, default=25.0,
                    help="drop void blobs smaller than this many m^2 (default 25)")
    ap.add_argument("--no-gate", action="store_true",
                    help="skip the stream-proximity gate (debug: see raw voids)")
    args = ap.parse_args()

    cfg = REG[args.suffix]
    tile_dir: Path = cfg["tile_dir"]
    dem_path: Path = cfg["dem"]
    key = args.suffix

    # --- grid from DEM --------------------------------------------------------
    with rasterio.open(dem_path) as d:
        res = d.res[0]
        W, H = d.width, d.height
        x0, y0min, x1, y1max = d.bounds.left, d.bounds.bottom, d.bounds.right, d.bounds.top
        transform = d.transform
        crs = d.crs
    grid = (x0, y0min, x1, y1max, res, W, H)  # origin = lower-left for writers.gdal
    bounds = (x0, y0min, x1, y1max)
    print(f"[{key}] grid {W}x{H} @ {res} m  bounds {x0:.0f},{y0min:.0f},{x1:.0f},{y1max:.0f}")

    # --- count raster ---------------------------------------------------------
    count_path = tile_dir / f"allret_count_{key}_05.tif"
    if not count_path.exists():
        tiles = select_tiles(cfg["laz_glob"][0], cfg["laz_glob"][1], bounds)
        print(f"[{key}] {len(tiles)} source tiles intersect the window")
        if not tiles:
            print("  ! no source tiles found", file=sys.stderr); return 1
        build_count_raster(tiles, grid, count_path, tile_dir)
    else:
        print(f"[{key}] reusing existing {count_path.name}")

    with rasterio.open(count_path) as c:
        count = c.read(1)  # uint16, 0 where no points
    void = count <= args.max_count
    print(f"[{key}] raw voids (<= {args.max_count} ret): {void.sum()} cells "
          f"= {void.sum()*res*res/1e4:.2f} ha")

    # --- stream-proximity gate ------------------------------------------------
    if not args.no_gate:
        with rasterio.open(cfg["stream"]) as s:
            from rasterio.warp import reproject, Resampling
            stream = np.zeros((H, W), dtype=np.uint8)
            reproject(
                source=rasterio.band(s, 1), destination=stream,
                src_transform=s.transform, src_crs=s.crs,
                dst_transform=transform, dst_crs=crs,
                resampling=Resampling.nearest,
            )
        stream_bool = stream > 0
        dist = distance_transform_edt(~stream_bool) * res
        near = dist <= args.stream_buf
        on = void & near
        print(f"[{key}] after stream gate (<= {args.stream_buf} m): "
              f"{on.sum()} cells = {on.sum()*res*res/1e4:.2f} ha "
              f"({100*on.sum()/max(void.sum(),1):.0f}% of raw kept)")
        void = on

    # --- flatness gate (water interpolates to a near-flat surface) ------------
    if args.max_slope > 0:
        with rasterio.open(cfg["slope"]) as sl:
            slope = sl.read(1); slnd = sl.nodata
        flat = (slope != slnd) & (slope < args.max_slope)
        before = void.sum()
        void = void & flat
        print(f"[{key}] after flatness gate (< {args.max_slope} deg): "
              f"{void.sum()} cells = {void.sum()*res*res/1e4:.2f} ha "
              f"({100*void.sum()/max(before,1):.0f}% of stream-gated kept)")

    # --- clean ----------------------------------------------------------------
    min_px = int(round(args.min_area / (res * res)))
    void = binary_closing(void, structure=np.ones((3, 3)), iterations=1)
    void = binary_fill_holes(void)
    void = remove_small_objects(void, min_size=min_px)
    print(f"[{key}] cleaned: {void.sum()} cells = {void.sum()*res*res/1e4:.2f} ha "
          f"(min blob {args.min_area} m^2 = {min_px} px)")

    # --- write binary tif -----------------------------------------------------
    mask_path = tile_dir / f"water_void_{key}_05.tif"
    write_tif(mask_path, void.astype("uint8"), transform=transform, crs=crs,
              dtype="uint8", nodata=0)
    print(f"[{key}] -> {mask_path.name}")

    # --- polygonize -----------------------------------------------------------
    import geopandas as gpd
    from shapely.geometry import shape
    polys, areas = [], []
    for geom, val in rio_shapes(void.astype("uint8"), mask=void, transform=transform):
        if val != 1:
            continue
        g = shape(geom)
        polys.append(g); areas.append(g.area)
    gpkg_path = tile_dir / f"water_void_{key}.gpkg"
    if polys:
        gdf = gpd.GeoDataFrame({"area_m2": areas}, geometry=polys, crs=DST_CRS)
        gdf.to_file(gpkg_path, layer="water_void", driver="GPKG")
        print(f"[{key}] -> {gpkg_path.name}  ({len(polys)} polygons, "
              f"{sum(areas)/1e4:.2f} ha, largest {max(areas)/1e4:.2f} ha)")
    else:
        print(f"[{key}] no water-void polygons after cleaning")

    # --- overlay PNG ----------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        hs = read_tif(cfg["hillshade"])
        fig, ax = plt.subplots(figsize=(12, 12), dpi=110)
        ax.imshow(hs, cmap="gray",
                  extent=(x0, x1, y0min, y1max), origin="upper")
        ov = np.ma.masked_where(~void, void)
        ax.imshow(ov, cmap="cool", alpha=0.55,
                  extent=(x0, x1, y0min, y1max), origin="upper")
        ax.set_title(f"{key}: water-return voids (<= {args.max_count} ret, "
                     f"stream-gated {args.stream_buf:.0f} m)")
        ax.set_xticks([]); ax.set_yticks([])
        png = tile_dir / f"water_void_overlay_{key}.png"
        fig.savefig(png, bbox_inches="tight"); plt.close(fig)
        print(f"[{key}] -> {png.name}")
    except Exception as e:  # noqa: BLE001
        print(f"[{key}] overlay skipped: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
