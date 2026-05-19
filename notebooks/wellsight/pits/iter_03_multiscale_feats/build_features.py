"""Build an 11-channel feature stack for iter 03.

Channels (in order):
   0 lrm_25         existing
   1 lrm_5          existing
   2 slope          existing
   3 tpi_05         existing
   4 openness_pos   existing
   5 openness_neg   existing
   6 roughness_11   existing
   7 lrm_11         existing on disk (multi-scale residual, intermediate)
   8 lrm_51         existing on disk (multi-scale residual, coarse)
   9 curvature      NEW: Laplacian of DTM, lightly smoothed
  10 geomorphons    NEW: whitebox terrain classifier (10 classes, 1..10)

Outputs:
    data/derivatives/9t/iterations/03_multiscale_feats/features_pit_v2_9t_05.tif
    data/derivatives/9t/iterations/03_multiscale_feats/feature_stats_v2.json
    data/derivatives/9t/iterations/03_multiscale_feats/curvature_9t_05.tif   (intermediate)
    data/derivatives/9t/iterations/03_multiscale_feats/geomorphons_9t_05.tif (intermediate)
"""
import json, tempfile, os
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import rasterize
import geopandas as gpd
from scipy.ndimage import laplace, gaussian_filter
import whitebox

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
OUTDIR = D / "iterations" / "03_multiscale_feats"; OUTDIR.mkdir(parents=True, exist_ok=True)

EXISTING_CHANNELS = [
    ("lrm_25",       "lrm_25_9t_05.tif"),
    ("lrm_5",        "lrm_5_9t_05.tif"),
    ("slope",        "slope_9t_05.tif"),
    ("tpi_05",       "tpi_05_9t_05.tif"),
    ("openness_pos", "openness_pos_9t_05.tif"),
    ("openness_neg", "openness_neg_9t_05.tif"),
    ("roughness_11", "roughness_11_9t_05.tif"),
    ("lrm_11",       "lrm_11_9t_05.tif"),
    ("lrm_51",       "lrm_51_9t_05.tif"),
]


def compute_curvature(dem_path, out_path):
    """Laplacian of DTM (light Gaussian smoothing first to suppress noise).

    Negative values = concave (pit-like), positive = convex (rim/ridge).
    """
    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        nd = r.nodata
        profile = r.profile.copy()
    if nd is not None:
        bad = (dem == nd) | ~np.isfinite(dem)
    else:
        bad = ~np.isfinite(dem)
    # Fill nodata with local mean before differentiating
    dem_filled = np.where(bad, np.nan, dem)
    # Interpolate NaNs cheaply via mean for derivative stability
    if bad.any():
        fill = np.nanmean(dem_filled)
        dem_filled = np.where(bad, fill, dem_filled)
    smoothed = gaussian_filter(dem_filled, sigma=1.0)
    curv = laplace(smoothed).astype(np.float32)
    # Put NaN back where DEM was nodata
    curv = np.where(bad, np.nan, curv)
    profile.update(dtype="float32", count=1, compress="deflate", predictor=3,
                   tiled=True, blockxsize=512, blockysize=512, nodata=np.nan)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(curv, 1)
    return curv


def compute_geomorphons(dem_path, out_path):
    """WhiteboxTools Geomorphons classifier. Outputs uint8 raster 1..10."""
    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(out_path.parent))
    # Use absolute paths to be safe
    rc = wbt.geomorphons(
        dem=str(dem_path),
        output=str(out_path),
        search=50,         # search distance in pixels (50 px = 25 m at 0.5 m)
        threshold=0.0,     # flatness threshold (degrees)
        fdist=0,           # flatness distance (0 = use search/3)
        skip=0,
        forms=True,        # output classification (10 forms) not ternary code
    )
    if rc != 0:
        raise RuntimeError(f"whitebox geomorphons failed with rc={rc}")
    return out_path


def main():
    dem_path = D / "dem_9t_05.tif"
    curv_path = OUTDIR / "curvature_9t_05.tif"
    geom_path = OUTDIR / "geomorphons_9t_05.tif"

    print("Computing DTM curvature (Laplacian)...")
    compute_curvature(dem_path, curv_path)
    print(f"  -> {curv_path.name}")

    print("Computing geomorphons via WhiteboxTools...")
    compute_geomorphons(dem_path, geom_path)
    print(f"  -> {geom_path.name}")

    # Verify reference grid
    with rasterio.open(EXISTING_CHANNELS[0][1] if Path(EXISTING_CHANNELS[0][1]).is_absolute()
                       else D / EXISTING_CHANNELS[0][1]) as r0:
        H, W = r0.height, r0.width
        profile = r0.profile.copy()
        ref_transform = r0.transform

    print(f"Reference grid: {W} x {H} @ 0.5 m")
    all_channels = EXISTING_CHANNELS + [
        ("curvature", str(curv_path)),
        ("geomorphons", str(geom_path)),
    ]

    # Load TRAIN block mask for stats
    blocks = gpd.read_file(D / "pit_blocks_9t.gpkg", layer="blocks")
    train_blocks = blocks[blocks.split == "train"]
    train_mask = rasterize(
        [(g, 1) for g in train_blocks.geometry],
        out_shape=(H, W), transform=ref_transform, fill=0, dtype="uint8",
    ).astype(bool)

    out_path = OUTDIR / "features_pit_v2_9t_05.tif"
    profile.update(count=len(all_channels), dtype="float32", compress="deflate",
                   predictor=3, tiled=True, blockxsize=512, blockysize=512,
                   BIGTIFF="YES", nodata=np.nan)

    stats = {}
    print(f"Writing {out_path.name} ({len(all_channels)} bands)")
    with rasterio.open(out_path, "w", **profile) as dst:
        for i, (name, src) in enumerate(all_channels, start=1):
            spath = D / src if not Path(src).is_absolute() else Path(src)
            with rasterio.open(spath) as r:
                arr = r.read(1).astype(np.float32)
                if r.nodata is not None:
                    arr = np.where(arr == r.nodata, np.nan, arr)
            vals = arr[train_mask]; vals = vals[np.isfinite(vals)]
            mu, sd = float(np.mean(vals)), float(np.std(vals))
            if sd < 1e-6: sd = 1.0
            stats[name] = {"mean": mu, "std": sd,
                           "p2": float(np.percentile(vals, 2)),
                           "p98": float(np.percentile(vals, 98))}
            print(f"  band {i:2d} {name:14s}  mean={mu:8.3f}  std={sd:8.3f}  "
                  f"p2={stats[name]['p2']:8.2f}  p98={stats[name]['p98']:8.2f}")
            dst.write(arr, i)
            dst.set_band_description(i, name)

    (OUTDIR / "feature_stats_v2.json").write_text(json.dumps(stats, indent=2))
    print(f"\nWrote feature_stats_v2.json")


if __name__ == "__main__":
    main()
