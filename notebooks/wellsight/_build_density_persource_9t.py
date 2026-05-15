"""Build a per-PointSourceId-normalized ground-return density raster for 9t.

PA 2019 D20 LiDAR has 4+ overlapping flight passes per tile. Each pass has its
own scan-angle-dependent density variation (nadir ~2x edge-of-scan). When all
passes are summed naively, the resulting density raster encodes flight
geometry as much as terrain/canopy — Beck's algorithm then traces the flight
pattern instead of roads.

Fix: rasterize density SEPARATELY per PointSourceId, normalize each to its
own per-pass median (so each pass has median 1.0), then take the MAX across
passes at each cell. A real canopy opening is high-density in at least one
pass; a within-pass nadir-center artifact is only median in any single pass.

Output: ground_density_persource_9t_1m.tif (float32, values in "per-pass
median multiples"; ~1.0 = typical canopy, >~2.0 = clear opening).
"""
import argparse
import time
from pathlib import Path

import laspy
import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
DERIV = ROOT / "data" / "derivatives"
TILE_BASE = ROOT / "data" / "external" / "usgs_3dep_pa_lidar" / "laz"

TILES = {
    "9t":  dict(bbox=(619500.0, 4593000.0, 624000.0, 4597500.0),
                proj="PA_WesternPA_2019_D20",  src_crs="EPSG:6346"),
    "mkf": dict(bbox=(696000.0, 4645000.0, 706000.0, 4655000.0),
                proj="PA_Northcentral_2019_B19", src_crs="EPSG:6350"),
}

RES = 1.0
CRS = "EPSG:6346"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True, choices=list(TILES.keys()))
    args = ap.parse_args()
    cfg = TILES[args.tile]
    X0, Y0, X1, Y1 = cfg["bbox"]
    src_crs = cfg.get("src_crs", "EPSG:6346")
    dst_crs = CRS
    need_reproj = src_crs != dst_crs
    transformer = None
    if need_reproj:
        import pyproj
        transformer = pyproj.Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    W = int((X1 - X0) / RES)
    H = int((Y1 - Y0) / RES)
    T = from_origin(X0, Y1, RES, RES)
    LAZ_DIR = TILE_BASE / cfg["proj"]

    tiles = sorted(LAZ_DIR.glob("*.laz"))
    print(f"tile={args.tile}  proj={cfg['proj']}  src_crs={src_crs}->{dst_crs}  "
          f"input LAZ tiles: {len(tiles)}", flush=True)

    # Pass 1: enumerate all PointSourceIds we'll encounter, accumulate per-source
    # raw counts into a dict of HxW arrays.
    per_source = {}  # source_id -> flat HxW int32 array
    t0 = time.time()
    for i, laz in enumerate(tiles, 1):
        las = laspy.read(str(laz))
        cls = np.asarray(las.classification)
        psid = np.asarray(las.point_source_id)
        xs = np.asarray(las.x); ys = np.asarray(las.y)
        # Reproject from source CRS to grid CRS (UTM 17N) if needed
        if need_reproj:
            xs, ys = transformer.transform(xs, ys)
        # ground only, within the grid bbox
        m = (cls == 2) & (xs >= X0) & (xs < X1) & (ys >= Y0) & (ys < Y1)
        if not m.any():
            if i % 10 == 0 or i == len(tiles):
                print(f"  [{i:3d}/{len(tiles)}] {laz.name}: no ground in grid",
                      flush=True)
            continue
        x = xs[m]; y = ys[m]; s = psid[m]
        cols = np.floor((x - X0) / RES).astype(np.int64)
        rows = np.floor((Y1 - y) / RES).astype(np.int64)
        ok = (cols >= 0) & (cols < W) & (rows >= 0) & (rows < H)
        if not ok.any():
            continue
        flat = rows[ok] * W + cols[ok]
        s = s[ok]
        srcs, inv = np.unique(s, return_inverse=True)
        for k, sid in enumerate(srcs):
            sel = inv == k
            if sel.sum() < 100:
                continue
            cnts = np.bincount(flat[sel], minlength=H * W)[:H * W].astype(np.int32)
            if int(sid) not in per_source:
                per_source[int(sid)] = cnts
            else:
                per_source[int(sid)] += cnts
        if i % 10 == 0 or i == len(tiles):
            print(f"  [{i:3d}/{len(tiles)}] {laz.name}  sources so far: "
                  f"{len(per_source)}  elapsed={time.time()-t0:.0f}s", flush=True)

    print(f"\nunique PointSourceIds in grid: {sorted(per_source.keys())}",
          flush=True)

    # Pass 2: per-source normalization, then MEAN across passes that touched
    # each cell. Mean is invariant to the number of contributing passes (max
    # is not — overlap zones with 3+ passes get spuriously inflated). For
    # each cell c, output = mean_{passes p touching c}(density_p[c] / median_p).
    sum_norm = np.zeros(H * W, dtype=np.float64)
    contributing = np.zeros(H * W, dtype=np.uint16)
    for sid, arr in per_source.items():
        pos = arr[arr > 0]
        if pos.size < 5000:
            print(f"  source {sid}: only {pos.size} cells — skipping (too sparse)",
                  flush=True)
            continue
        med = float(np.median(pos))
        if med < 1.0:
            continue
        norm = arr.astype(np.float64) / med
        # Only contribute where this pass actually touched the cell
        touched = arr > 0
        sum_norm += np.where(touched, norm, 0)
        contributing += touched.astype(np.uint16)
        print(f"  source {sid}: covers {pos.size:9,} cells  median={med:.1f}  "
              f"p95={float(np.percentile(pos,95)):.1f}", flush=True)

    cnt_safe = np.maximum(contributing.astype(np.float32), 1)
    mean_norm = (sum_norm / cnt_safe).astype(np.float32)
    out_mean = mean_norm.reshape(H, W)
    out_mean = np.where(contributing.reshape(H, W) > 0, out_mean, -9999.0)
    out_max = out_mean  # name reused below for write step

    out_path = DERIV / f"ground_density_persource_{args.tile}_1m.tif"
    profile = dict(
        driver="GTiff", height=H, width=W, count=1, dtype="float32",
        crs=CRS, transform=T, nodata=-9999.0,
        compress="deflate", predictor=2, tiled=True,
        blockxsize=512, blockysize=512,
    )
    with rasterio.open(out_path, "w", **profile) as ds:
        ds.write(out_max.astype(np.float32), 1)

    sample = out_max[out_max != -9999.0]
    print(f"\nwrote {out_path}")
    print(f"max-per-pass-normalized density: "
          f"min/p5/p50/p90/p99/max = {sample.min():.2f} / "
          f"{np.percentile(sample,5):.2f} / {np.percentile(sample,50):.2f} / "
          f"{np.percentile(sample,90):.2f} / {np.percentile(sample,99):.2f} / "
          f"{sample.max():.2f}")


if __name__ == "__main__":
    main()
