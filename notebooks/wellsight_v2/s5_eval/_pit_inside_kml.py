"""Write the pit_inside layer (pit interiors) as a KML for Google Earth.

Outlines only, one placemark per pit, in WGS84. Name is the pit_inside_id. The description gives the pad id, the area in m2,
and the matching pit_full id. No fill, so the imagery shows through.

Run:
  python notebooks/wellsight_v2/s5_eval/_pit_inside_kml.py
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"
OUT = ROOT / "data/_results/pit_inside_outlines_gearth.kml"
COLOR = "ffffff00"   # KML is aabbggrr, so this is opaque cyan


def ring(coords):
    return " ".join(f"{x:.7f},{y:.7f},0" for x, y in coords)


def polygon(p):
    s = f"<Polygon><tessellate>1</tessellate><outerBoundaryIs><LinearRing><coordinates>{ring(p.exterior.coords)}</coordinates></LinearRing></outerBoundaryIs>"
    for h in p.interiors:
        s += f"<innerBoundaryIs><LinearRing><coordinates>{ring(h.coords)}</coordinates></LinearRing></innerBoundaryIs>"
    return s + "</Polygon>"


def main():
    pi = gpd.read_file(G, layer="pit_inside")
    pf = gpd.read_file(G, layer="pit_full").dropna(subset=["pit_inside_id"]).set_index("pit_inside_id")["pit_full_id"]
    area = pi.geometry.area
    pi = pi.to_crs(4326)
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
             "<name>Pit interiors (pit_inside), 9t</name>",
             f'<Style id="in"><LineStyle><color>{COLOR}</color><width>2</width></LineStyle><PolyStyle><fill>0</fill><outline>1</outline></PolyStyle></Style>']
    for (i, r), a in zip(pi.iterrows(), area):
        g = r.geometry
        polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
        geom = polys[0] and (polygon(polys[0]) if len(polys) == 1 else "<MultiGeometry>" + "".join(polygon(p) for p in polys) + "</MultiGeometry>")
        full = pf.get(r.pit_inside_id)
        desc = f"pit_inside_id {int(r.pit_inside_id)}; pad_id {'' if r.pad_id != r.pad_id else int(r.pad_id)}; area {a:.0f} m2; pit_full_id {'' if full is None else int(full)}"
        parts.append(f"<Placemark><name>{int(r.pit_inside_id)}</name><description>{escape(desc)}</description><styleUrl>#in</styleUrl>{geom}</Placemark>")
    parts.append("</Document></kml>")
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(len(pi), "placemarks ->", OUT)


if __name__ == "__main__":
    main()
