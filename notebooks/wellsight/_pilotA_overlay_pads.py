"""Pilot A: render PNGs of each hillshade with intersecting Ramachandran
well-pad polygons overlaid. Pads are reprojected from EPSG:4326 to each tile's
native UTM zone before plotting.
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.plot import show
from shapely import wkt
from shapely.geometry import box

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
DERIV = ROOT / "data/derivatives/pilot_A"
PADS_CSV = ROOT / "data/external/ramachandran_2024/permian_denver_data/deployment/permian_well_pads.csv"
PNG_DIR = DERIV / "overlays"
PNG_DIR.mkdir(exist_ok=True)


def load_pads_gdf():
    df = pd.read_csv(PADS_CSV)
    df["geometry"] = df["geometry"].map(wkt.loads)
    return gpd.GeoDataFrame(df, geometry="geometry", crs=4326)


def main():
    pads = load_pads_gdf()
    print(f"loaded {len(pads):,} well pads")

    hs_files = sorted(DERIV.glob("*_hs_1m.tif"))
    rows = []
    for hs_path in hs_files:
        name = hs_path.stem.replace("_hs_1m", "")
        with rasterio.open(hs_path) as src:
            tile_crs = src.crs
            tile_bounds = src.bounds  # in tile CRS
            arr = src.read(1)
            transform = src.transform

        # Reproject pads to tile CRS and clip to tile bbox
        pads_proj = pads.to_crs(tile_crs)
        tile_box = box(*tile_bounds)
        clipped = pads_proj[pads_proj.intersects(tile_box)].copy()

        # Plot
        fig, ax = plt.subplots(figsize=(10, 10), dpi=120)
        ax.imshow(arr, cmap="gray",
                  extent=(tile_bounds.left, tile_bounds.right,
                          tile_bounds.bottom, tile_bounds.top),
                  vmin=0, vmax=255)
        if len(clipped) > 0:
            clipped.boundary.plot(ax=ax, edgecolor="red", linewidth=1.2)
            clipped.plot(ax=ax, facecolor="red", alpha=0.15)
        ax.set_title(f"{name}\n{len(clipped)} well-pad polygon(s) overlaid  |  EPSG:{tile_crs.to_epsg()}",
                     fontsize=9)
        ax.set_xlabel("Easting (m)")
        ax.set_ylabel("Northing (m)")
        ax.set_aspect("equal")
        out_png = PNG_DIR / f"{name}.png"
        plt.tight_layout()
        plt.savefig(out_png, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"  {name}: {len(clipped)} pads -> {out_png.name}")
        rows.append({"tile": name, "epsg": tile_crs.to_epsg(),
                     "n_pads_intersecting": len(clipped),
                     "tile_bounds": tuple(tile_bounds)})

    pd.DataFrame(rows).to_csv(DERIV / "pad_intersect_summary.csv", index=False)
    print(f"\nSummary: {DERIV/'pad_intersect_summary.csv'}")


if __name__ == "__main__":
    main()
