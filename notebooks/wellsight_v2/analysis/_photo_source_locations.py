"""Georeference the field-photo sources found in the 2026-07-20 web sweep.

Builds a QGIS-ready GeoPackage with two layers (EPSG:6346, styles embedded):

  vpasec_wells    1,926 GPS'd abandoned/plugged wells from the Venango PA
                  Senior Environmental Corps public Google map (KML archived
                  at data/external/vpasec/vpasec_wells_venango.kml).
                  Categorized by source folder (Oil Creek SP, SGL 39/45/253,
                  DEP-plugged). None fall inside the 9t tile — closest
                  distances are recorded per point.

  photo_sources   Manually georeferenced locations of ground photos of
                  wells/pits/pads found online (Pithole, Penn-Brad rig,
                  Bradford-area shots, etc). `precision` says how exact the
                  location is: exact / site / vicinity / area / town.
                  `url` links the photo/page.

Distances to both study blocks (9t and mkf/McKean) are computed for every
feature (dist_9t_km, dist_mck_km).

Reproduce: python notebooks/wellsight_v2/analysis/_photo_source_locations.py
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).parent))
from _export_well_age_qgis import embed_styles, qml_categorized  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
KML = ROOT / "data/external/vpasec/vpasec_wells_venango.kml"
OUT_DIR = ROOT / "data/derivatives/experiments/well_photo_locations"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "well_photo_locations.gpkg"
CRS = "EPSG:6346"

B9 = box(619311, 4592854, 624172, 4597660)     # 9t raster footprint
BMK = box(696000, 4645000, 706000, 4655000)    # mkf_1m footprint

# lat, lon, name, source, url, what_shown, precision
PHOTO_SOURCES = [
    (41.517417, -79.685278, "VPASEC photo well #1",
     "VPASEC found-wells map",
     "http://vpasec.org/albums/AbandonedWells/album/index.html",
     "Casing photo embedded in map placemark (Oil Creek SP)", "exact"),
    (41.545, -79.660, "VPASEC Abandoned Wells album (50 photos)",
     "VPASEC / Friends of OCSP",
     "http://vpasec.org/albums/AbandonedWells/album/index.html",
     "Wood casing in depression, open holes in pits, wooden tanks, "
     "bare-ground depressions — Oil Creek SP + Venango game lands "
     "(album not per-photo georefed; point = OCSP south end)", "area"),
    (41.5230, -79.5789, "Pithole City historic site",
     "PA Bucket List / Belt Magazine",
     "https://pabucketlist.com/exploring-the-ghost-town-of-pithole-in-venango-county-pa/",
     "Mowed street grid, town field, 1865-95 archive views; adjacent to "
     "9t NW corner", "site"),
    (41.593, -79.675, "Indigenous oil pits (oblong troughs)",
     "Belt Magazine (Maynard 2022)",
     "https://beltmag.com/uncovering-america-first-oil-landscape/",
     "Pre-colonial dug oil pits along Oil Creek, visible as troughs",
     "area"),
    (41.6112, -79.6641, "Drake Well Museum (Mather archive)",
     "Drake Well Museum",
     "https://www.phmc.pa.gov/museums/drake-well",
     "John Mather 1860s-80s glass plates incl. Allegheny River wells at "
     "President; ask-the-museum lead", "site"),
    (41.8994, -78.6470, "Penn-Brad Oil Museum rig",
     "Uncovering PA",
     "https://uncoveringpa.com/visiting-penn-brad-oil-museum",
     "Standing 72-ft Bradford-field standard rig, period tools", "site"),
    (41.90, -78.66, "Rusty casing south of Bradford",
     "StateImpact PA (2012)",
     "https://stateimpact.npr.org/pennsylvania/2012/10/11/perilous-pathways-hunting-for-hidden-wells/",
     "Jagged rusty pipe in ground near ANF south of Bradford", "vicinity"),
    (41.95, -78.65, "Abandoned well in McKean County stream",
     "StateImpact PA (2012)",
     "https://www.witf.io/wp-content/uploads/2012/10/IMG_2468-1440x1080.jpg",
     "Laurie Barr pointing to casing mid-stream; county-level location",
     "town"),
    (41.9767, -78.5525, "Derrick City oil field (1930 photos)",
     "mindat.org Foster Twp page",
     "https://www.mindat.org/loc-424434.html",
     "Historic Derrick oil field photographs; INSIDE mkf block east edge",
     "town"),
    (41.9553, -78.4930, "Duke Center project gallery",
     "Save Our Streams PA (Barr)",
     "http://www.smugmug.com/gallery/37146615_hrCPhs",
     "GPS-tagged well photos, Duke Center (2011-era link, may be dead)",
     "town"),
]


def parse_kml(path):
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    doc = ET.parse(path).getroot().find("k:Document", ns)
    rows = []
    for f in doc.findall(".//k:Folder", ns):
        fname = f.findtext("k:name", "", ns)
        for pm in f.findall(".//k:Placemark", ns):
            c = pm.findtext(".//k:coordinates", "", ns).strip().split(",")
            desc = (pm.findtext("k:description", "", ns) or "")
            img = ""
            if "<img src=" in desc:
                img = desc.split('<img src="')[1].split('"')[0]
            rows.append({"folder": fname,
                         "name": pm.findtext("k:name", "", ns),
                         "img_url": img,
                         "lon": float(c[0]), "lat": float(c[1])})
    return pd.DataFrame(rows)


def add_dists(g):
    g["dist_9t_km"] = (g.distance(B9) / 1000).round(2)
    g["dist_mck_km"] = (g.distance(BMK) / 1000).round(2)
    return g


def main():
    wells = parse_kml(KML)
    gw = gpd.GeoDataFrame(
        wells, geometry=[Point(xy) for xy in zip(wells.lon, wells.lat)],
        crs="EPSG:4326").to_crs(CRS)
    gw = add_dists(gw)
    print(f"vpasec wells: {len(gw)}; with photo: {(gw.img_url != '').sum()}")
    print("min dist to 9t:", gw["dist_9t_km"].min(), "km")

    ps = pd.DataFrame(PHOTO_SOURCES, columns=[
        "lat", "lon", "name", "source", "url", "what_shown", "precision"])
    gp = gpd.GeoDataFrame(
        ps, geometry=[Point(xy) for xy in zip(ps.lon, ps.lat)],
        crs="EPSG:4326").to_crs(CRS)
    gp = add_dists(gp)
    print(gp[["name", "precision", "dist_9t_km", "dist_mck_km"]].to_string(
        index=False))

    if OUT.exists():
        OUT.unlink()
    gw.drop(columns=["lon", "lat"]).to_file(OUT, layer="vpasec_wells",
                                            driver="GPKG")
    gp.drop(columns=["lon", "lat"]).to_file(OUT, layer="photo_sources",
                                            driver="GPKG", mode="a")

    folder_colors = [
        ("Oil Creek SP-Abandoned-Wells", "Oil Creek SP found wells (841)",
         "31,120,180"),
        ("Game Land 39 Abandoned Wells", "SGL 39 (46)", "106,61,154"),
        ("Game Land 45 Abandoned Wells", "SGL 45 (43)", "255,127,0"),
        ("Game Land 253 Abandoned Wells", "SGL 253 (76)", "227,26,28"),
        ("Wells Plugged by DEP", "DEP plugged (920)", "150,150,150")]
    prec_colors = [("exact", "exact", "227,26,28"),
                   ("site", "site", "255,127,0"),
                   ("vicinity", "vicinity", "31,120,180"),
                   ("area", "area (approximate)", "106,61,154"),
                   ("town", "town-level", "141,211,199")]
    embed_styles(str(OUT), [
        ("vpasec_wells", "geom",
         qml_categorized("point", "folder", folder_colors)),
        ("photo_sources", "geom",
         qml_categorized("point", "precision", prec_colors))])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
