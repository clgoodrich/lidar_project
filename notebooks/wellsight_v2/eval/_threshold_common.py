"""Shared pieces for the per-threshold "what does this cutoff claim?" products.

Used by the pit, pad and road threshold scripts so all three answer the same
question the same way and stay directly comparable:

  * how much of the tile does this probability cutoff claim?
  * how many HELD-OUT hand-drawn annotations does it find, and which does it miss?
  * where exactly are the misses, findable without hunting through the raster?

Ground truth is hand-drawn annotation only. No state well list is involved in
any of the three.

Exports
  tag                 0.30 -> "thr0p30" (shell- and GDAL-safe decimal)
  polygonize          probability raster + cutoff -> polygons with mean score
  write_raster        mask/prob GeoTIFF, tolerant of a Windows lock from QGIS
  style_qml           categorized found/missed QML (fill or line)
  embed_style         write that QML into a GeoPackage's layer_styles table
  bookmarks_xml       QGIS 3 spatial-bookmark XML for a list of (name, x, y)
  contact_sheet       hillshade crops of every miss in one PNG
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.windows import from_bounds
from scipy import ndimage as ndi
from shapely.geometry import shape

__all__ = ["tag", "polygonize", "write_raster", "style_qml", "embed_style",
           "bookmarks_xml", "contact_sheet", "BOOKMARK_SRSID", "CRS"]

CRS = "EPSG:6346"

# QGIS bookmark XML: every field is a CHILD ELEMENT, not an attribute, and the
# group lives in <project>. The attribute form is QGIS 2 and imports as an empty
# extent ("Bookmark extent is empty"). <sr_id> is the internal srs.db row id,
# NOT the EPSG code -- EPSG:6346 is srs_id 28818 in QGIS 3.36 and 3.40. Format
# verified by round-tripping QgsBookmarkManager.exportToFile under QGIS 3.40.10.
BOOKMARK_SRSID = 28818


def tag(t: float) -> str:
    return f"thr{t:.2f}".replace(".", "p")


def polygonize(prob, transform, crs, thresh, min_area):
    """Connected components of ``prob >= thresh``, as polygons with mean score."""
    mask = prob >= thresh
    if not mask.any():
        return gpd.GeoDataFrame({"score": []}, geometry=[], crs=crs)
    lbl, n = ndi.label(mask)
    means = ndi.mean(prob, labels=lbl, index=np.arange(1, n + 1))
    rows = []
    for geom, val in shapes(lbl.astype(np.int32), mask=mask, transform=transform):
        i = int(val)
        if i < 1:
            continue
        g = shape(geom)
        if g.area < min_area:
            continue
        rows.append({"score": float(means[i - 1]), "geometry": g})
    return (gpd.GeoDataFrame(rows, crs=crs) if rows
            else gpd.GeoDataFrame({"score": []}, geometry=[], crs=crs))


def write_raster(path: Path, band: np.ndarray, prof: dict, updates: dict,
                 tags: dict) -> bool:
    """Write one raster, tolerating a Windows lock from an open QGIS session.

    These outputs are deterministic functions of the source probability raster,
    so an already-correct file that happens to be locked is not worth aborting
    a whole sweep over -- the remaining thresholds still need writing.
    """
    p = prof.copy()
    p.update(count=1, compress="deflate", tiled=True, **updates)
    try:
        with rasterio.open(path, "w", **p) as d:
            d.write(band, 1)
            if band.dtype == np.uint8:
                d.write_colormap(1, {0: (0, 0, 0, 0), 1: (215, 25, 28, 255)})
            d.update_tags(1, **tags)
    except Exception as e:
        if "Permission denied" not in str(e):
            raise
        print(f"    !! SKIPPED {path.name} -- locked (open in QGIS?)")
        return False
    return True


def style_qml(attr: str = "verdict", kind: str = "fill") -> str:
    """Categorized green-found / red-missed style. ``kind`` is 'fill' or 'line'."""
    if kind == "line":
        def sym(name, rgba, width):
            return (f'<symbol type="line" name="{name}" alpha="1" '
                    f'clip_to_extent="1" force_rhr="0">'
                    f'<layer class="SimpleLine" enabled="1" locked="0" pass="0">'
                    f'<prop k="line_color" v="{rgba}"/>'
                    f'<prop k="line_width" v="{width}"/>'
                    f'<prop k="line_width_unit" v="MM"/>'
                    f'<prop k="capstyle" v="round"/></layer></symbol>')
        symbols = (sym("0", "26,150,65,255", "0.5")
                   + sym("1", "215,25,28,255", "1.6"))
    else:
        def sym(name, fill, outline, width):
            return (f'<symbol type="fill" name="{name}" alpha="1" '
                    f'clip_to_extent="1" force_rhr="0">'
                    f'<layer class="SimpleFill" enabled="1" locked="0" pass="0">'
                    f'<prop k="color" v="{fill}"/><prop k="style" v="solid"/>'
                    f'<prop k="outline_color" v="{outline}"/>'
                    f'<prop k="outline_style" v="solid"/>'
                    f'<prop k="outline_width" v="{width}"/>'
                    f'<prop k="outline_width_unit" v="MM"/></layer></symbol>')
        symbols = (sym("0", "26,150,65,55", "26,150,65,255", "0.4")
                   + sym("1", "215,25,28,110", "215,25,28,255", "1.4"))
    return f"""<!DOCTYPE qgis PUBLIC 'http://mapserver.org/qgis' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="{attr}" forceraster="0"
               enableorderby="0" symbollevels="0">
    <categories>
      <category value="found" symbol="0" label="found" render="true"/>
      <category value="missed" symbol="1" label="MISSED" render="true"/>
    </categories>
    <symbols>{symbols}</symbols>
  </renderer-v2>
</qgis>
"""


_CREATE = """CREATE TABLE IF NOT EXISTS layer_styles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT,
  f_table_schema TEXT, f_table_name TEXT, f_geometry_column TEXT,
  styleName TEXT, styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN,
  description TEXT, owner TEXT, ui TEXT,
  update_time DATETIME DEFAULT (datetime('now')))"""


def embed_style(gpkg: Path, layer: str, qml: str, desc: str) -> None:
    con = sqlite3.connect(gpkg); cur = con.cursor()
    cur.execute(_CREATE)
    cur.execute("DELETE FROM layer_styles WHERE f_table_name = ?", (layer,))
    cur.execute("INSERT INTO layer_styles (f_table_catalog, f_table_schema,"
                " f_table_name, f_geometry_column, styleName, styleQML,"
                " styleSLD, useAsDefault, description, owner, ui)"
                " VALUES ('', '', ?, 'geom', 'found_vs_missed', ?, '', 1, ?,"
                " '', '')", (layer, qml, desc))
    con.commit(); con.close()


def bookmarks_xml(entries, group: str, id_prefix: str, pad: float) -> str:
    """entries = iterable of (label, x, y). Returns QGIS 3 bookmark XML."""
    out = ['<!DOCTYPE qgis_bookmarks>', '<qgis_bookmarks>']
    for i, (label, x, y) in enumerate(entries, 1):
        out += [
            '  <bookmark>',
            f'    <id>{id_prefix}_{i:03d}</id>',
            f'    <name>{escape(label)}</name>',
            f'    <project>{escape(group)}</project>',
            f'    <xmin>{x - pad:.3f}</xmin>',
            f'    <ymin>{y - pad:.3f}</ymin>',
            f'    <xmax>{x + pad:.3f}</xmax>',
            f'    <ymax>{y + pad:.3f}</ymax>',
            '    <rotation>0</rotation>',
            f'    <sr_id>{BOOKMARK_SRSID}</sr_id>',
            '  </bookmark>']
    out.append('</qgis_bookmarks>')
    return "\n".join(out)


def contact_sheet(path: Path, hillshade: Path, misses, pred, title: str,
                  half_m: float, label_fn, crs: str = CRS,
                  max_panels: int = 60) -> int:
    """Hillshade crops of every miss in one PNG. Returns panels drawn.

    ``misses`` is a GeoDataFrame; ``label_fn(row)`` supplies the panel title.
    Capped at ``max_panels`` -- the cap is printed, never silent.
    """
    n_all = len(misses)
    if not n_all:
        return 0
    if n_all > max_panels:
        print(f"    NOTE: contact sheet shows the first {max_panels} of "
              f"{n_all} misses (cap), full set is in the GeoPackage")
        misses = misses.iloc[:max_panels]
    n = len(misses)
    cols = min(4, n); rowsn = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rowsn, cols, figsize=(4.2 * cols, 4.2 * rowsn),
                            squeeze=False)
    with rasterio.open(hillshade) as hr:
        hs_tf = hr.transform
        for a, rr in zip(axs.ravel(), misses.itertuples()):
            c = rr.geometry.centroid
            b = (c.x - half_m, c.y - half_m, c.x + half_m, c.y + half_m)
            try:
                crop = hr.read(1, window=from_bounds(*b, transform=hs_tf))
                a.imshow(crop, cmap="gray",
                         extent=(b[0], b[2], b[1], b[3]))
            except Exception:
                pass
            gpd.GeoSeries([rr.geometry], crs=crs).plot(
                ax=a, facecolor="none", edgecolor="#d7191c", lw=2.0)
            if pred is not None and len(pred):
                sub = pred[pred.intersects(rr.geometry.buffer(half_m))]
                if len(sub):
                    sub.plot(ax=a, facecolor="none", edgecolor="#1a9641",
                             lw=1.2)
            a.set_xlim(b[0], b[2]); a.set_ylim(b[1], b[3])
            a.set_title(label_fn(rr), fontsize=9)
            a.set_xticks([]); a.set_yticks([])
    for a in axs.ravel()[n:]:
        a.axis("off")
    fig.suptitle(title, fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return n
