"""Filter 3DEP LPC tile inventory to tiles that intersect Ramachandran Permian
well-pad polygons. Outputs a download manifest with size totals.
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import wkt
from shapely.geometry import box

INV_PATH = Path(r"C:\Users\colto\Documents\GitHub\lidar_project\data\external\usgs_3dep_permian_tx\tile_inventory.parquet")
PADS_CSV = Path(r"C:\Users\colto\Documents\GitHub\lidar_project\data\external\ramachandran_2024\permian_denver_data\deployment\permian_well_pads.csv")
OUT_DIR = INV_PATH.parent


def main():
    inv = pd.read_parquet(INV_PATH)
    inv = inv.dropna(subset=["minX", "minY", "maxX", "maxY", "downloadURL"])
    print(f"Inventory tiles: {len(inv):,}")

    tile_geom = [box(r.minX, r.minY, r.maxX, r.maxY) for r in inv.itertuples()]
    tiles_gdf = gpd.GeoDataFrame(inv, geometry=tile_geom, crs=4326)

    print("Loading well pads...")
    pads = pd.read_csv(PADS_CSV)
    pads["geometry"] = pads["geometry"].map(wkt.loads)
    pads_gdf = gpd.GeoDataFrame(pads, geometry="geometry", crs=4326)
    print(f"Well pads: {len(pads_gdf):,}")

    # Spatial join: tiles that intersect at least one pad
    joined = gpd.sjoin(tiles_gdf, pads_gdf[["wp_id", "geometry"]],
                       predicate="intersects", how="inner")
    keep_ids = joined["sourceId"].unique()
    keep = tiles_gdf[tiles_gdf["sourceId"].isin(keep_ids)].copy()

    # Add count of pads intersected per tile
    pad_counts = joined.groupby("sourceId").size().rename("n_pads_in_tile")
    keep = keep.merge(pad_counts, on="sourceId")

    print(f"\nTiles intersecting >=1 well pad: {len(keep):,} "
          f"({100 * len(keep) / len(tiles_gdf):.1f}% of inventory)")
    print(f"Total LAZ payload: {keep['sizeInBytes'].sum() / 1e9:.1f} GB "
          f"({keep['sizeInBytes'].sum() / 1e12:.2f} TB)")

    print("\nBy project:")
    by_proj = (keep.groupby("project")
               .agg(n_tiles=("sourceId", "size"),
                    gb=("sizeInBytes", lambda s: s.sum() / 1e9),
                    n_pads=("n_pads_in_tile", "sum"))
               .sort_values("gb", ascending=False))
    print(by_proj.to_string())

    out_pq = OUT_DIR / "tiles_intersecting_pads.parquet"
    keep.drop(columns="geometry").to_parquet(out_pq, index=False)
    out_manifest = OUT_DIR / "download_manifest.csv"
    keep[["sourceId", "project", "sizeInBytes", "downloadURL"]].to_csv(out_manifest, index=False)
    print(f"\nSaved: {out_pq}")
    print(f"Saved: {out_manifest}")


if __name__ == "__main__":
    main()
