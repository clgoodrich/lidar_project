"""Pilot A: quantify whether Ramachandran well-pad polygons have a distinct
LiDAR-derived terrain signature vs surrounding non-pad terrain.

For each tile:
  1. Compute slope (degrees) from DEM via gdaldem.
  2. Mask DEM + slope arrays by pad polygons (inside) and a random control set
     of equally-shaped polygons offset from each pad (outside).
  3. Stats per pad: elev_std, elev_range, slope_mean, slope_std, roughness (DEM std-3x3).
  4. Welch t-test on inside vs outside distributions across all pads.
"""
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from scipy import ndimage, stats
from shapely import wkt
from shapely.affinity import translate

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
DERIV = ROOT / "data/derivatives/pilot_A"
PADS_CSV = ROOT / "data/external/ramachandran_2024/permian_denver_data/deployment/permian_well_pads.csv"


def ensure_slope(dem_path, slope_path):
    if slope_path.exists():
        return
    subprocess.run(
        ["gdaldem", "slope", str(dem_path), str(slope_path),
         "-of", "GTiff", "-compute_edges", "-s", "1.0"],
        check=True, capture_output=True, text=True, timeout=120,
    )


def stats_in_polygon(dem, slope, transform, geom, pad=2):
    """Per-pad stats. Returns dict of features or None if too few pixels."""
    mask = geometry_mask([geom], out_shape=dem.shape, transform=transform,
                         invert=True, all_touched=True)
    if mask.sum() < 9:
        return None
    elev = dem[mask]
    elev = elev[elev > -9000]  # drop nodata
    if elev.size < 9:
        return None
    slp = slope[mask]
    slp = slp[(slp >= 0) & (slp < 90)]
    # Roughness: local std-3x3 over the bbox window covering the polygon
    return dict(
        n_px=int(mask.sum()),
        elev_mean=float(elev.mean()),
        elev_std=float(elev.std()),
        elev_range=float(elev.max() - elev.min()),
        slope_mean=float(slp.mean()) if slp.size else np.nan,
        slope_std=float(slp.std()) if slp.size else np.nan,
        slope_p95=float(np.percentile(slp, 95)) if slp.size else np.nan,
    )


def control_polygon(geom, dx, dy):
    return translate(geom, xoff=dx, yoff=dy)


def main():
    pads = pd.read_csv(PADS_CSV)
    pads["geometry"] = pads["geometry"].map(wkt.loads)
    pads_gdf = gpd.GeoDataFrame(pads, geometry="geometry", crs=4326)

    rows_in, rows_out = [], []
    dem_files = sorted(DERIV.glob("*_dem_1m.tif"))

    for dem_path in dem_files:
        name = dem_path.stem.replace("_dem_1m", "")
        slope_path = DERIV / f"{name}_slope_1m.tif"
        ensure_slope(dem_path, slope_path)

        with rasterio.open(dem_path) as src:
            dem = src.read(1).astype(np.float32)
            transform = src.transform
            tile_crs = src.crs
            bounds = src.bounds
        with rasterio.open(slope_path) as src:
            slope = src.read(1).astype(np.float32)

        pads_local = pads_gdf.to_crs(tile_crs)
        from shapely.geometry import box as shp_box
        tile_box = shp_box(*bounds)
        clipped = pads_local[pads_local.intersects(tile_box)].copy()

        rng = np.random.default_rng(42)
        for _, row in clipped.iterrows():
            geom = row.geometry
            if not geom.is_valid:
                continue
            cx, cy = geom.centroid.x, geom.centroid.y

            s_in = stats_in_polygon(dem, slope, transform, geom)
            if s_in is None:
                continue
            s_in.update(tile=name, wp_id=row["wp_id"], kind="pad")
            rows_in.append(s_in)

            # 3 random controls per pad, 200-400m offset, kept inside tile bounds
            attempts, made = 0, 0
            while made < 3 and attempts < 20:
                attempts += 1
                ang = rng.uniform(0, 2 * np.pi)
                r = rng.uniform(200, 400)
                dx, dy = r * np.cos(ang), r * np.sin(ang)
                ctrl = control_polygon(geom, dx, dy)
                if not tile_box.contains(ctrl):
                    continue
                # avoid overlap with any pad
                if clipped.intersects(ctrl).any():
                    continue
                s_out = stats_in_polygon(dem, slope, transform, ctrl)
                if s_out is None:
                    continue
                s_out.update(tile=name, wp_id=row["wp_id"], kind="control")
                rows_out.append(s_out)
                made += 1

    df = pd.DataFrame(rows_in + rows_out)
    out_csv = DERIV / "terrain_stats_pads_vs_controls.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved {len(df)} rows -> {out_csv}")

    # Summary table & Welch t-test
    print("\n=== Per-feature: pad vs control (Welch t-test) ===")
    metrics = ["elev_std", "elev_range", "slope_mean", "slope_std", "slope_p95"]
    pad_df = df[df.kind == "pad"]
    ctl_df = df[df.kind == "control"]
    print(f"n_pads={len(pad_df)}, n_controls={len(ctl_df)}")
    rows = []
    for m in metrics:
        a = pad_df[m].dropna().to_numpy()
        b = ctl_df[m].dropna().to_numpy()
        t, p = stats.ttest_ind(a, b, equal_var=False)
        rows.append(dict(metric=m,
                         pad_mean=a.mean(), pad_std=a.std(),
                         ctl_mean=b.mean(), ctl_std=b.std(),
                         pct_diff=100 * (a.mean() - b.mean()) / b.mean() if b.mean() else np.nan,
                         t=t, p=p))
    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    summary.to_csv(DERIV / "terrain_stats_summary.csv", index=False)


if __name__ == "__main__":
    main()
