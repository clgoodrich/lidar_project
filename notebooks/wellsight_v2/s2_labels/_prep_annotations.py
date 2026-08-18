"""Reproject, validate, and spatial-join annotation layers.

Inputs (EPSG:4326 shapefiles in data/derivatives/annotations/):
    roads, not_roads, pit_outside, pit_inside, plat

Output: data/derivatives/annotations/annotations_proj.gpkg with layers:
    plat, pit_inside, pit_outside, pit_wall, roads, not_roads
All reprojected to EPSG:6346 (project CRS), with plat_id joined onto every feature.
"""
import sys                                  # used to edit Python's import search path below
from pathlib import Path                    # file paths as objects, works on Windows and Linux

import geopandas as gpd                     # pandas, except every row also carries a shape
import pandas as pd                         # plain tables (NOTE: never actually used in this file)

# Put notebooks/wellsight_v2/ on the import path so `from _common import ...` works
# no matter what directory you launch the script from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS as TARGET_CRS, path_for  # shared paths + the project CRS

SRC = path_for("truth")                      # the folder holding the hand-drawn shapefiles
OUT = SRC / "annotations_proj.gpkg"          # the one file this whole script produces


def load(name: str, *, assume_epsg: int | None = None) -> gpd.GeoDataFrame:
    g = gpd.read_file(SRC / f"{name}.shp")   # read one shapefile into a table of shapes
    # drainage.shp ships without a .prj but is already in EPSG:6346 (UTM 17N
    # metres). Stamp the CRS before reprojecting so to_crs doesn't choke on a
    # naive geometry.
    if g.crs is None and assume_epsg is not None:
        print(f"  {name}: no CRS on file; assuming EPSG:{assume_epsg}")  # say out loud that we guessed
        g = g.set_crs(epsg=assume_epsg)      # attach a CRS label; does NOT move the coordinates
    g = g.to_crs(TARGET_CRS)                 # convert degrees -> metres; this DOES move them
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy()  # drop rows with a missing or blank shape
    g["valid"] = g.geometry.is_valid         # flag shapes that self-cross or are otherwise malformed
    bad = (~g["valid"]).sum()                # count how many are malformed
    if bad:
        print(f"  {name}: fixing {bad} invalid geoms with buffer(0)")  # report the repair count
        # buffer(0) grows the shape by zero metres. Sounds pointless, but rebuilding
        # it forces the library to untangle self-crossings. Standard repair trick.
        g.loc[~g["valid"], "geometry"] = g.loc[~g["valid"], "geometry"].buffer(0)
    g = g.drop(columns=["valid"])            # scratch column, nothing downstream needs it
    return g                                 # hand back the cleaned, reprojected layer


def assign_plat_id(features: gpd.GeoDataFrame, plats: gpd.GeoDataFrame, kind: str) -> gpd.GeoDataFrame:
    """Attach plat_id to features. Polygons -> by centroid; lines -> by majority overlap (buffered)."""
    f = features.copy()                      # work on a copy so the caller's table is untouched
    if kind == "polygon":
        probes = gpd.GeoDataFrame(geometry=f.geometry.centroid, crs=f.crs)  # test using each polygon's centre point
    else:  # line
        probes = gpd.GeoDataFrame(geometry=f.geometry, crs=f.crs)  # test using the whole line
    # For every probe, look up which pad polygon it falls inside. how="left" keeps
    # features that land on no pad at all (they get a blank plat_id).
    j = gpd.sjoin(probes, plats[["plat_id", "geometry"]], how="left", predicate="intersects")
    j = j[~j.index.duplicated(keep="first")]  # a probe touching 2 pads gets 2 rows; keep the first, arbitrarily
    f["plat_id"] = j["plat_id"].values        # copy the matched pad number onto the feature
    return f                                  # same table as before, plus a plat_id column


def main():
    print(f"Reading from {SRC}")             # echo the input folder so a run is traceable
    print(f"Target CRS: {TARGET_CRS}\n")     # echo the CRS everything gets converted to

    plat = load("plat")                      # well pad outlines
    pit_in = load("pit_inside")              # the pit floor, inner polygon
    pit_out = load("pit_outside")            # the pit plus its raised rim, outer polygon
    roads = load("roads")                    # access roads you traced
    not_roads = load("not_roads")            # things that look like roads but aren't (hard negatives)
    drainage = load("drainage", assume_epsg=6346)  # stream channels, the other big road look-alike
    print(f"  drainage: {len(drainage)} channel segments")  # sanity count

    # Stable plat_id
    plat = plat.reset_index(drop=True)       # renumber rows 0,1,2,... with no gaps
    plat["plat_id"] = plat.index.astype(int)  # that row number IS the pad's permanent ID
    plat["area_m2"] = plat.geometry.area     # pad size in m^2; free because the CRS is already metres

    # Pit wall = pit_outside MINUS pit_inside, matched 1:1 by intersection
    pit_in = pit_in.reset_index(drop=True)   # clean, gapless numbering
    pit_in["pit_id"] = pit_in.index.astype(int)  # row number becomes the pit's ID
    pit_out = pit_out.reset_index(drop=True)  # same clean numbering for the outer rings
    pit_out["pit_id_outer"] = pit_out.index.astype(int)  # separate ID, since inner and outer are different layers

    # Match each inner pit to its enclosing outer pit by max overlap
    # overlay(how="intersection") cuts every inner pit against every outer ring and
    # returns just the overlapping pieces, one row per (inner, outer) pair that touch.
    pairs = gpd.overlay(
        pit_in[["pit_id", "geometry"]],
        pit_out[["pit_id_outer", "geometry"]],
        how="intersection",
        keep_geom_type=True,                 # only keep polygon results, discard stray lines/points
    )
    pairs["overlap_area"] = pairs.geometry.area  # how much each pairing actually overlaps
    # Biggest overlap wins. drop_duplicates on pit_id means each inner pit keeps
    # exactly one outer ring, so the pairing is 1:1.
    pairs = pairs.sort_values("overlap_area", ascending=False).drop_duplicates("pit_id")
    in2out = dict(zip(pairs["pit_id"], pairs["pit_id_outer"]))  # lookup: inner pit ID -> its outer ring ID

    matched_inner = set(in2out.keys())       # inner pits that found a partner
    matched_outer = set(in2out.values())     # outer rings that got claimed by some inner pit
    print(f"Pit pairing: {len(in2out)} matched | "
          f"inner unmatched={len(pit_in)-len(matched_inner)} | "
          f"outer unmatched={len(pit_out)-len(matched_outer)}")  # report what failed to pair

    # Build pit_wall = outer - inner per matched pair
    walls = []                               # collect the finished ring shapes here
    for pid_in, pid_out in in2out.items():   # walk every matched pair
        # Outer shape minus inner shape = the rim, a donut. .iloc[0] pulls the single
        # matching row's geometry out of the one-row filter result.
        ring = pit_out.loc[pit_out.pit_id_outer == pid_out, "geometry"].iloc[0].difference(
            pit_in.loc[pit_in.pit_id == pid_in, "geometry"].iloc[0]
        )
        if not ring.is_empty:
            walls.append({"pit_id": pid_in, "geometry": ring})  # keep it, tagged with the INNER pit's ID
    pit_wall = gpd.GeoDataFrame(walls, crs=TARGET_CRS)  # turn the plain list into a real map layer
    print(f"Pit wall geometries built: {len(pit_wall)}")  # count check against the pairing above

    # Tag pit_outside with its inner pit_id for downstream joins
    # Flip the lookup (outer -> inner) so the outer layer can be joined on pit_id too.
    pit_out["pit_id"] = pit_out["pit_id_outer"].map({v: k for k, v in in2out.items()})

    # Spatial join plat_id onto everything
    pit_in = assign_plat_id(pit_in, plat, "polygon")      # which pad is this pit floor on
    pit_out = assign_plat_id(pit_out, plat, "polygon")    # same for the outer ring
    pit_wall = assign_plat_id(pit_wall, plat, "polygon")  # same for the rim donut
    roads = assign_plat_id(roads, plat, "line")           # which pad does this road serve
    not_roads = assign_plat_id(not_roads, plat, "line")   # same for the fake roads
    drainage = assign_plat_id(drainage, plat, "line")     # same for stream channels

    # Stats
    def coverage(name, gdf):
        n = len(gdf)                          # total features in this layer
        on_plat = gdf["plat_id"].notna().sum()  # how many landed on a labelled pad
        print(f"  {name:14s} n={n:4d}  on_plat={on_plat:4d}  off_plat={n-on_plat:4d}")  # one summary line

    print("\nplat coverage (features falling on a labeled plat):")  # header for the block below
    coverage("pit_inside",  pit_in)          # off_plat here means a pit with no pad drawn around it
    coverage("pit_outside", pit_out)
    coverage("pit_wall",    pit_wall)
    coverage("roads",       roads)
    coverage("not_roads",   not_roads)

    # Per-plat counts
    # dropna first so features with no pad don't get counted; groupby+size counts
    # rows per pad; rename gives the resulting column its final name.
    pit_per_plat = pit_in.dropna(subset=["plat_id"]).groupby("plat_id").size().rename("n_pits")
    road_per_plat = roads.dropna(subset=["plat_id"]).groupby("plat_id").size().rename("n_roads")
    notroad_per_plat = not_roads.dropna(subset=["plat_id"]).groupby("plat_id").size().rename("n_not_roads")
    plat = plat.merge(pit_per_plat, on="plat_id", how="left") \
               .merge(road_per_plat, on="plat_id", how="left") \
               .merge(notroad_per_plat, on="plat_id", how="left")  # attach the three counts as columns
    for col in ("n_pits", "n_roads", "n_not_roads"):
        plat[col] = plat[col].fillna(0).astype(int)  # a pad with nothing on it gets 0, not blank

    print(f"\nPlats: {len(plat)} total")                              # how many pads exist
    print(f"  with >=1 pit:        {(plat.n_pits>0).sum()}")          # how many have at least one pit
    print(f"  with >=1 road:       {(plat.n_roads>0).sum()}")         # ...at least one road
    print(f"  with >=1 not_road:   {(plat.n_not_roads>0).sum()}")     # ...at least one hard negative
    print(f"  median pits/plat:    {plat.n_pits.median():.1f}")       # typical pits per pad
    print(f"  median area (m^2):   {plat.area_m2.median():.0f}")      # typical pad size

    # Write
    if OUT.exists():
        OUT.unlink()                         # delete the old file so we never half-overwrite it
    plat.to_file(OUT, layer="plat", driver="GPKG")  # a GeoPackage holds many layers in one file
    pit_in.to_file(OUT, layer="pit_inside", driver="GPKG")    # each call appends another layer
    pit_out.to_file(OUT, layer="pit_outside", driver="GPKG")
    pit_wall.to_file(OUT, layer="pit_wall", driver="GPKG")
    roads.to_file(OUT, layer="roads", driver="GPKG")
    not_roads.to_file(OUT, layer="not_roads", driver="GPKG")
    drainage.to_file(OUT, layer="drainage", driver="GPKG")
    print(f"\nWrote {OUT}  (+ drainage layer, {len(drainage)} segments)")  # final confirmation


if __name__ == "__main__":
    main()
