"""Export the inner pit rims (qgis/annotations/pit_inside.shp) to KML for 9t and 613590.

Clip = the area's 1 m lidar extent. Names <area>_pit_inside_NNN numbered north to south; centroid in the description.
Writes qgis/annotations/kml/pit_inside_<area>.kml.   Run: python tools/_export_pit_inside_kml.py
"""
from pathlib import Path
import geopandas as gpd
import rasterio
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
src = gpd.read_file(ROOT / "qgis" / "annotations" / "pit_inside.shp")
for area in ("9t", "613590"):
    with rasterio.open(ROOT / "data" / area / "derived" / "1m" / f"slope_{area}_1m.tif") as s:
        b, crs = s.bounds, s.crs
    g = src.to_crs(crs)
    g = g[g.geometry.centroid.within(box(*b))].copy()
    g = g.assign(cy=g.geometry.centroid.y).sort_values("cy", ascending=False)
    w = g.to_crs(4326)
    c = w.geometry.centroid
    w["Name"] = [f"{area}_pit_inside_{i + 1:03d}" for i in range(len(w))]
    w["Description"] = [f"Inner pit rim (pit_inside id {k}). Centroid {y:.6f}, {x:.6f}" for k, x, y in zip(w["id"], c.x, c.y)]
    out = ROOT / "qgis" / "annotations" / "kml" / f"pit_inside_{area}.kml"
    w[["Name", "Description", "geometry"]].to_file(out, driver="KML")
    print(out, len(w))
