"""Export the well-age-vs-morphology results as a QGIS-ready GeoPackage.

Layers (all EPSG:6346, styles embedded in layer_styles → auto-colored on load):
  wells_annotated_area  1,176 catalog wells within 200 m of annotations,
                        colored by era (spud-year bin / historic / no date)
  pads_age              995 annotated pads, colored by matched-well age class
  wells_venango_all     full 20,108-well county catalog, colored by
                        spud_class (real / sentinel_1800 / missing) — context
                        layer showing where undated historic wells live

Companion to _well_age_morphology.py (reuses its well_pad_matches.csv).
Reproduce: python notebooks/wellsight_v2/s7_analysis/_export_well_age_qgis.py
"""
import sqlite3
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
WELLS = path_for("derivatives") / "venango_wells_all.gpkg"
PADS = path_for("truth") / "pad.shp"
MATCHES = path_for("experiments") / "well_age_morphology" / "well_pad_matches.csv"
OUT = path_for("experiments") / "well_age_morphology" / "well_age_morphology.gpkg"
CRS = "EPSG:6346"

ERA_BINS = [(-np.inf, 1956, "pre-1956"), (1956, 1980, "1956-1979"),
            (1980, 2000, "1980-1999"), (2000, np.inf, "2000+")]

HISTORIC = "historic (undated, pre-permit)"
NODATE = "no date"


def era_of(year):
    for lo, hi, name in ERA_BINS:
        if lo <= year < hi:
            return name
    return None


def qml_categorized(geom, attr, cats):
    """Minimal categorized-renderer QML. cats = [(value, label, rgb)]."""
    sym_tag = "marker" if geom == "point" else "fill"
    layer_cls = "SimpleMarker" if geom == "point" else "SimpleFill"
    cat_xml, sym_xml = [], []
    for i, (val, label, rgb) in enumerate(cats):
        cat_xml.append(f'<category render="true" symbol="{i}" '
                       f'value="{val}" label="{label}"/>')
        props = [f'<prop k="color" v="{rgb},255"/>',
                 '<prop k="outline_color" v="35,35,35,255"/>',
                 '<prop k="outline_width" v="0.2"/>']
        if geom == "point":
            props += ['<prop k="size" v="2.4"/>', '<prop k="name" v="circle"/>']
        sym_xml.append(
            f'<symbol type="{sym_tag}" name="{i}" alpha="1" '
            'clip_to_extent="1" force_rhr="0">'
            f'<layer class="{layer_cls}" enabled="1" locked="0" pass="0">'
            + "".join(props) + "</layer></symbol>")
    return ("<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>"
            '<qgis styleCategories="Symbology" version="3.28.0">'
            f'<renderer-v2 type="categorizedSymbol" attr="{attr}" '
            'forceraster="0" enableorderby="0" symbollevels="0">'
            "<categories>" + "".join(cat_xml) + "</categories>"
            "<symbols>" + "".join(sym_xml) + "</symbols>"
            "</renderer-v2></qgis>")


def embed_styles(gpkg, styles):
    """styles = [(layer_name, geom_col, qml_xml)] → layer_styles table."""
    con = sqlite3.connect(gpkg)
    con.execute("""CREATE TABLE IF NOT EXISTS layer_styles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        f_table_catalog TEXT(256), f_table_schema TEXT(256),
        f_table_name TEXT(256), f_geometry_column TEXT(256),
        styleName TEXT(30), styleQML TEXT, styleSLD TEXT,
        useAsDefault BOOLEAN, description TEXT, owner TEXT(30),
        ui TEXT(30), update_time DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("INSERT OR IGNORE INTO gpkg_contents "
                "(table_name, data_type, identifier) VALUES "
                "('layer_styles','attributes','layer_styles')")
    for name, gcol, qml in styles:
        con.execute(
            "INSERT INTO layer_styles (f_table_catalog, f_table_schema, "
            "f_table_name, f_geometry_column, styleName, styleQML, styleSLD, "
            "useAsDefault, description, owner) VALUES ('','',?,?,?,?,'',1,"
            "'well_age_morphology default','')", (name, gcol, name, qml))
    con.commit()
    con.close()


def main():
    wells = gpd.read_file(WELLS).to_crs(CRS)
    sd = pd.to_datetime(wells["SPUD_DATE"], errors="coerce")
    wells["spud_year"] = sd.dt.year
    wells["spud_class"] = "missing"
    wells.loc[wells["spud_year"].notna(), "spud_class"] = "real"
    wells.loc[wells["spud_year"] == 1800, "spud_class"] = "sentinel_1800"

    def disp(row):
        if row["spud_class"] == "sentinel_1800":
            return HISTORIC
        if row["spud_class"] == "real":
            return era_of(row["spud_year"])
        return NODATE

    wells["era_display"] = wells.apply(disp, axis=1)

    m = pd.read_csv(MATCHES)
    keep = ["PERMIT_NUM", "WELL_STATU", "spud_year", "spud_class",
            "era_display", "geometry"]
    in_area = wells.merge(m[["PERMIT_NUM", "has_pad", "has_pit", "d_pad",
                             "d_pit", "pad_idx", "wells_on_pad"]],
                          on="PERMIT_NUM", how="inner")
    in_area = gpd.GeoDataFrame(in_area, geometry="geometry", crs=CRS)
    print(f"in-area wells: {len(in_area)}")

    pads = gpd.read_file(PADS).to_crs(CRS).reset_index(names="pad_idx")
    pads.geometry = pads.geometry.make_valid()
    pads = pads[pads.geometry.notna() & ~pads.geometry.is_empty].copy()

    per_pad = m[m["pad_idx"].notna()].groupby("pad_idx").agg(
        n_wells_50m=("PERMIT_NUM", "size"),
        n_dated=("spud_year", lambda s: int((s.notna() & (s != 1800)).sum())),
        med_spud_year=("spud_year",
                       lambda s: s[s.notna() & (s != 1800)].median()),
        n_sentinel=("spud_class",
                    lambda s: int((s == "sentinel_1800").sum())))
    pads = pads.merge(per_pad, on="pad_idx", how="left")

    def pad_class(row):
        if pd.isna(row["n_wells_50m"]):
            return "no catalog well within 50 m"
        if row["n_dated"] > 0:
            return f"dated: {era_of(row['med_spud_year'])}"
        if row["n_sentinel"] > 0:
            return "historic wells only (undated)"
        return "wells without dates"

    pads["age_class"] = pads.apply(pad_class, axis=1)
    print(pads["age_class"].value_counts())

    pad_cols = ["pad_idx", "area_m2", "age_class", "n_wells_50m", "n_dated",
                "med_spud_year", "n_sentinel", "geometry"]
    pad_cols = [c for c in pad_cols if c in pads.columns]

    if OUT.exists():
        OUT.unlink()
    in_area[keep + ["has_pad", "has_pit", "d_pad", "d_pit",
                    "wells_on_pad"]].to_file(
        OUT, layer="wells_annotated_area", driver="GPKG")
    pads[pad_cols].to_file(OUT, layer="pads_age", driver="GPKG", mode="a")
    wells[keep].to_file(OUT, layer="wells_venango_all", driver="GPKG",
                        mode="a")

    era_colors = [
        ("1956-1979", "1956–1979", "253,174,97"),
        ("1980-1999", "1980–1999", "171,221,164"),
        ("2000+", "2000+", "43,131,186"),
        (HISTORIC, "historic (undated, pre-permit)", "215,25,28"),
        (NODATE, "no date", "150,150,150")]
    class_colors = [
        ("real", "dated (real spud year)", "67,162,202"),
        ("sentinel_1800", "sentinel 1800 (undated historic)", "215,25,28"),
        ("missing", "no date", "150,150,150")]
    pad_colors = [
        ("dated: 1956-1979", "dated: 1956–1979", "253,174,97"),
        ("dated: 1980-1999", "dated: 1980–1999", "171,221,164"),
        ("dated: 2000+", "dated: 2000+", "43,131,186"),
        ("historic wells only (undated)", "historic wells only (undated)",
         "215,25,28"),
        ("wells without dates", "wells without dates", "255,255,191"),
        ("no catalog well within 50 m", "no catalog well within 50 m",
         "200,200,200")]
    embed_styles(str(OUT), [
        ("wells_annotated_area", "geom",
         qml_categorized("point", "era_display", era_colors)),
        ("pads_age", "geom", qml_categorized("fill", "age_class", pad_colors)),
        ("wells_venango_all", "geom",
         qml_categorized("point", "spud_class", class_colors))])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
