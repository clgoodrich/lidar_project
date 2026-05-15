"""Build a per-LAZ-tile z-scored intensity raster for 9t.

Why: PA 2019 LiDAR has per-tile intensity-calibration offsets that produce
sharp linear discontinuities at LAZ tile boundaries when all tiles are
rasterized together. These artifacts mimic linear road features and dominate
Beck's intensity-based detector. Z-scoring each tile independently before
mosaicking equalizes the per-tile distributions and removes the artifacts.

Steps:
  1. For each LAZ tile, run a PDAL pipeline producing a temp 1 m mean-Intensity
     raster of ground returns over THAT tile's extent only.
  2. Compute (mean, std) of valid pixels in that raster.
  3. Z-score the tile raster: (x - mean) / std.
  4. Mosaic the 17 z-scored tile rasters into the full 4500x4500 9t grid by
     taking the MEAN of overlapping pixels (overlapping pixels are in the
     LAZ tile-overlap zones — averaging is fine post-zscore).
  5. Write `intensity_zscore_9t_1m.tif`.
"""
import argparse
import json
import math
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
DERIV = ROOT / "data" / "derivatives"
TILE_BASE = ROOT / "data" / "external" / "usgs_3dep_pa_lidar" / "laz"

# Per-tile config: bbox (UTM 17N) + source LAZ project subdir
TILES = {
    "9t":  dict(bbox=(619500.0, 4593000.0, 624000.0, 4597500.0),
                proj="PA_WesternPA_2019_D20",
                src_crs="EPSG:6346"),       # native UTM 17N
    "mkf": dict(bbox=(696000.0, 4645000.0, 706000.0, 4655000.0),
                proj="PA_Northcentral_2019_B19",
                src_crs="EPSG:6350"),       # native Conus Albers
}

RES = 1.0
CRS = "EPSG:6346"
PDAL = shutil.which("pdal") or "pdal"


def laz_bbox_in(p, src_crs, dst_crs):
    """Get LAZ bbox reprojected from src_crs into dst_crs (the target grid CRS)."""
    r = subprocess.run([PDAL, "info", str(p), "--metadata"],
                       capture_output=True, text=True, check=True)
    m = json.loads(r.stdout)["metadata"]
    sx0, sy0, sx1, sy1 = float(m["minx"]), float(m["miny"]), float(m["maxx"]), float(m["maxy"])
    if src_crs == dst_crs:
        return sx0, sy0, sx1, sy1
    # Reproject corners (and a few midpoints for safety)
    import pyproj
    t = pyproj.Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    xs, ys = [], []
    for x in (sx0, (sx0 + sx1) / 2, sx1):
        for y in (sy0, (sy0 + sy1) / 2, sy1):
            tx, ty = t.transform(x, y)
            xs.append(tx); ys.append(ty)
    return min(xs), min(ys), max(xs), max(ys)


def rasterize_tile(laz, out_path, bb, X0, Y0, X1, Y1, TMP_DIR,
                   src_crs="EPSG:6346", dst_crs="EPSG:6346"):
    """Rasterize a single LAZ to 1m mean intensity of ground returns,
    clipped to the intersection of its bbox and the tile grid."""
    minx = max(bb[0], X0)
    miny = max(bb[1], Y0)
    maxx = min(bb[2], X1)
    maxy = min(bb[3], Y1)
    if maxx <= minx or maxy <= miny:
        return None
    # snap to 1m grid aligned with 9t origin
    minx = math.floor(minx)
    miny = math.floor(miny)
    maxx = math.ceil(maxx)
    maxy = math.ceil(maxy)
    tw = int((maxx - minx) / RES)
    th = int((maxy - miny) / RES)
    if tw < 1 or th < 1:
        return None
    stages = [{"type": "readers.las", "filename": str(laz)}]
    if src_crs != dst_crs:
        stages.append({"type": "filters.reprojection",
                       "in_srs": src_crs, "out_srs": dst_crs})
    stages.append({"type": "filters.range", "limits": "Classification[2:2]"})
    stages.append({"type": "filters.crop",
                   "bounds": f"([{minx},{maxx}],[{miny},{maxy}])"})
    pipeline = {
        "pipeline": stages + [
            {
                "type": "writers.gdal",
                "filename": str(out_path),
                "output_type": "mean",
                "dimension": "Intensity",
                "resolution": RES,
                "origin_x": minx,
                "origin_y": miny,
                "width": tw,
                "height": th,
                "data_type": "float32",
                "nodata": -9999.0,
                "gdaldriver": "GTiff",
                "gdalopts": "COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES",
                "override_srs": CRS,
            },
        ]
    }
    tmp_pipe = TMP_DIR / "_pipe.json"
    with open(tmp_pipe, "w") as f:
        json.dump(pipeline, f)
    r = subprocess.run([PDAL, "pipeline", str(tmp_pipe)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"  PDAL failed for {laz.name}:")
        print(r.stderr[-500:])
        return None
    return (minx, miny, maxx, maxy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True, choices=list(TILES.keys()))
    args = ap.parse_args()
    cfg = TILES[args.tile]
    X0, Y0, X1, Y1 = cfg["bbox"]
    src_crs = cfg.get("src_crs", "EPSG:6346")
    dst_crs = CRS
    W = int((X1 - X0) / RES)
    H = int((Y1 - Y0) / RES)
    T_full = from_origin(X0, Y1, RES, RES)
    LAZ_DIR = TILE_BASE / cfg["proj"]
    TMP_DIR = DERIV / f"_tmp_intensity_tiles_{args.tile}"
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    tiles = sorted(LAZ_DIR.glob("*.laz"))
    print(f"tile={args.tile}  proj={cfg['proj']}  src_crs={src_crs}->{dst_crs}  "
          f"input LAZ tiles: {len(tiles)}")
    print(f"grid: {W}x{H} @ {RES} m  bbox=({X0},{Y0},{X1},{Y1})")

    # 1) Per-tile rasterize
    print("\n=== rasterize per tile (1 m mean intensity, ground returns) ===")
    raster_paths = []
    t0 = time.time()
    for i, laz in enumerate(tiles, 1):
        bb = laz_bbox_in(laz, src_crs, dst_crs)
        out = TMP_DIR / f"{laz.stem}_intensity.tif"
        info = rasterize_tile(laz, out, bb, X0, Y0, X1, Y1, TMP_DIR,
                              src_crs=src_crs, dst_crs=dst_crs)
        if info is None:
            continue
        raster_paths.append((out, info))
        if i % 10 == 0 or i == len(tiles):
            print(f"  [{i:3d}/{len(tiles)}]  elapsed={time.time()-t0:.0f}s",
                  flush=True)
    print(f"rasterized {len(raster_paths)} tiles in {time.time()-t0:.0f}s")

    # 2-3) Per-tile z-score
    print("\n=== z-score per tile + mosaic ===")
    z_sum = np.zeros((H, W), dtype=np.float64)
    z_cnt = np.zeros((H, W), dtype=np.uint16)

    for i, (rp, (minx, miny, maxx, maxy)) in enumerate(raster_paths, 1):
        with rasterio.open(rp) as ds:
            a = ds.read(1).astype(np.float32)
            nd = ds.nodata
        valid = (a != nd) if nd is not None else np.ones_like(a, dtype=bool)
        sample = a[valid]
        if sample.size < 1000:
            continue
        mu = float(np.mean(sample))
        sd = float(np.std(sample))
        if sd < 1.0:
            continue
        z = np.where(valid, (a - mu) / sd, 0.0).astype(np.float32)

        # Place into full grid: top-left in full grid
        col0 = int(round((minx - X0) / RES))
        row0 = int(round((Y1 - maxy) / RES))
        ah, aw = z.shape
        # Clip to grid bounds
        col1 = min(W, col0 + aw)
        row1 = min(H, row0 + ah)
        col0c = max(0, col0); row0c = max(0, row0)
        sl_dst = (slice(row0c, row1), slice(col0c, col1))
        sl_src = (slice(row0c - row0, ah - (col0 + aw - col1)),  # may be off; recompute
                  slice(col0c - col0, aw - (col0 + aw - col1)))
        # Correct src slicing
        src_r0 = row0c - row0
        src_c0 = col0c - col0
        src_r1 = src_r0 + (row1 - row0c)
        src_c1 = src_c0 + (col1 - col0c)
        sl_src = (slice(src_r0, src_r1), slice(src_c0, src_c1))

        z_sub = z[sl_src]
        v_sub = valid[sl_src]
        z_sum[sl_dst] += np.where(v_sub, z_sub, 0)
        z_cnt[sl_dst] += v_sub.astype(np.uint16)
        if i % 10 == 0 or i == len(raster_paths):
            print(f"  [{i:3d}/{len(raster_paths)}]  mu={mu:.0f}  sd={sd:.0f}",
                  flush=True)

    mosaic = np.where(z_cnt > 0, z_sum / np.maximum(z_cnt, 1), -9999.0).astype(np.float32)

    out = DERIV / f"intensity_zscore_{args.tile}_1m.tif"
    profile = dict(
        driver="GTiff", height=H, width=W, count=1, dtype="float32",
        crs=CRS, transform=T_full, nodata=-9999.0,
        compress="deflate", predictor=2, tiled=True,
        blockxsize=512, blockysize=512,
    )
    with rasterio.open(out, "w", **profile) as ds:
        ds.write(mosaic, 1)
    valid_frac = float((mosaic != -9999.0).mean())
    sample = mosaic[mosaic != -9999.0]
    print(f"\nwrote {out}  valid={valid_frac*100:.1f}%  "
          f"z min/p5/p50/p95/max = {sample.min():.2f} / "
          f"{np.percentile(sample,5):.2f} / {np.percentile(sample,50):.2f} / "
          f"{np.percentile(sample,95):.2f} / {sample.max():.2f}")


if __name__ == "__main__":
    main()
