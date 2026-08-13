"""Reproject, validate, and spatial-join annotation layers.

Inputs (EPSG:4326 shapefiles in data/derivatives/annotations/):
    roads, not_roads, pit_outside, pit_inside, plat

Output: data/derivatives/annotations/annotations_proj.gpkg with layers:
    plat, pit_inside, pit_outside, pit_wall, roads, not_roads
All reprojected to EPSG:6346 (project CRS), with plat_id joined onto every feature.
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS as TARGET_CRS, path_for

SRC = path_for("truth")
OUT = SRC / "annotations_proj.gpkg"


def load(name: str, *, assume_epsg: int | None = None) -> gpd.GeoDataFrame:
    g = gpd.read_file(SRC / f"{name}.shp")
    # drainage.shp ships without a .prj but is already in EPSG:6346 (UTM 17N
    # metres). Stamp the CRS before reprojecting so to_crs doesn't choke on a
    # naive geometry.
    if g.crs is None and assume_epsg is not None:
        print(f"  {name}: no CRS on file; assuming EPSG:{assume_epsg}")
        g = g.set_crs(epsg=assume_epsg)
    g = g.to_crs(TARGET_CRS)
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy()
    g["valid"] = g.geometry.is_valid
    bad = (~g["valid"]).sum()
    if bad:
        print(f"  {name}: fixing {bad} invalid geoms with buffer(0)")
        g.loc[~g["valid"], "geometry"] = g.loc[~g["valid"], "geometry"].buffer(0)
    g = g.drop(columns=["valid"])
    return g


def assign_plat_id(features: gpd.GeoDataFrame, plats: gpd.GeoDataFrame, kind: str) -> gpd.GeoDataFrame:
    """Attach plat_id to features. Polygons -> by centroid; lines -> by majority overlap (buffered)."""
    f = features.copy()
    if kind == "polygon":
        probes = gpd.GeoDataFrame(geometry=f.geometry.centroid, crs=f.crs)
    else:  # line
        probes = gpd.GeoDataFrame(geometry=f.geometry, crs=f.crs)
    j = gpd.sjoin(probes, plats[["plat_id", "geometry"]], how="left", predicate="intersects")
    j = j[~j.index.duplicated(keep="first")]
    f["plat_id"] = j["plat_id"].values
    return f


def main():
    print(f"Reading from {SRC}")
    print(f"Target CRS: {TARGET_CRS}\n")

    plat = load("plat")
    pit_in = load("pit_inside")
    pit_out = load("pit_outside")
    roads = load("roads")
    not_roads = load("not_roads")
    drainage = load("drainage", assume_epsg=6346)  # hand/filter-derived channels
    print(f"  drainage: {len(drainage)} channel segments")

    # Stable plat_id
    plat = plat.reset_index(drop=True)
    plat["plat_id"] = plat.index.astype(int)
    plat["area_m2"] = plat.geometry.area

    # Pit wall = pit_outside MINUS pit_inside, matched 1:1 by intersection
    pit_in = pit_in.reset_index(drop=True)
    pit_in["pit_id"] = pit_in.index.astype(int)
    pit_out = pit_out.reset_index(drop=True)
    pit_out["pit_id_outer"] = pit_out.index.astype(int)

    # Match each inner pit to its enclosing outer pit by max overlap
    pairs = gpd.overlay(
        pit_in[["pit_id", "geometry"]],
        pit_out[["pit_id_outer", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    pairs["overlap_area"] = pairs.geometry.area
    pairs = pairs.sort_values("overlap_area", ascending=False).drop_duplicates("pit_id")
    in2out = dict(zip(pairs["pit_id"], pairs["pit_id_outer"]))

    matched_inner = set(in2out.keys())
    matched_outer = set(in2out.values())
    print(f"Pit pairing: {len(in2out)} matched | "
          f"inner unmatched={len(pit_in)-len(matched_inner)} | "
          f"outer unmatched={len(pit_out)-len(matched_outer)}")

    # Build pit_wall = outer - inner per matched pair
    walls = []
    for pid_in, pid_out in in2out.items():
        ring = pit_out.loc[pit_out.pit_id_outer == pid_out, "geometry"].iloc[0].difference(
            pit_in.loc[pit_in.pit_id == pid_in, "geometry"].iloc[0]
        )
        if not ring.is_empty:
            walls.append({"pit_id": pid_in, "geometry": ring})
    pit_wall = gpd.GeoDataFrame(walls, crs=TARGET_CRS)
    print(f"Pit wall geometries built: {len(pit_wall)}")

    # Tag pit_outside with its inner pit_id for downstream joins
    pit_out["pit_id"] = pit_out["pit_id_outer"].map({v: k for k, v in in2out.items()})

    # Spatial join plat_id onto everything
    pit_in = assign_plat_id(pit_in, plat, "polygon")
    pit_out = assign_plat_id(pit_out, plat, "polygon")
    pit_wall = assign_plat_id(pit_wall, plat, "polygon")
    roads = assign_plat_id(roads, plat, "line")
    not_roads = assign_plat_id(not_roads, plat, "line")
    drainage = assign_plat_id(drainage, plat, "line")

    # Stats
    def coverage(name, gdf):
        n = len(gdf)
        on_plat = gdf["plat_id"].notna().sum()
        print(f"  {name:14s} n={n:4d}  on_plat={on_plat:4d}  off_plat={n-on_plat:4d}")

    print("\nplat coverage (features falling on a labeled plat):")
    coverage("pit_inside",  pit_in)
    coverage("pit_outside", pit_out)
    coverage("pit_wall",    pit_wall)
    coverage("roads",       roads)
    coverage("not_roads",   not_roads)

    # Per-plat counts
    pit_per_plat = pit_in.dropna(subset=["plat_id"]).groupby("plat_id").size().rename("n_pits")
    road_per_plat = roads.dropna(subset=["plat_id"]).groupby("plat_id").size().rename("n_roads")
    notroad_per_plat = not_roads.dropna(subset=["plat_id"]).groupby("plat_id").size().rename("n_not_roads")
    plat = plat.merge(pit_per_plat, on="plat_id", how="left") \
               .merge(road_per_plat, on="plat_id", how="left") \
               .merge(notroad_per_plat, on="plat_id", how="left")
    for col in ("n_pits", "n_roads", "n_not_roads"):
        plat[col] = plat[col].fillna(0).astype(int)

    print(f"\nPlats: {len(plat)} total")
    print(f"  with >=1 pit:        {(plat.n_pits>0).sum()}")
    print(f"  with >=1 road:       {(plat.n_roads>0).sum()}")
    print(f"  with >=1 not_road:   {(plat.n_not_roads>0).sum()}")
    print(f"  median pits/plat:    {plat.n_pits.median():.1f}")
    print(f"  median area (m^2):   {plat.area_m2.median():.0f}")

    # Write
    if OUT.exists():
        OUT.unlink()
    plat.to_file(OUT, layer="plat", driver="GPKG")
    pit_in.to_file(OUT, layer="pit_inside", driver="GPKG")
    pit_out.to_file(OUT, layer="pit_outside", driver="GPKG")
    pit_wall.to_file(OUT, layer="pit_wall", driver="GPKG")
    roads.to_file(OUT, layer="roads", driver="GPKG")
    not_roads.to_file(OUT, layer="not_roads", driver="GPKG")
    drainage.to_file(OUT, layer="drainage", driver="GPKG")
    print(f"\nWrote {OUT}  (+ drainage layer, {len(drainage)} segments)")


if __name__ == "__main__":
    main()
