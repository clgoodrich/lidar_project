"""Build a QGIS project of the NISAR GSLC seasonal stack over 9t.

Run with QGIS's python, not the repo venv:
  "C:/Program Files/QGIS 3.40.10/bin/python-qgis-ltr.bat" notebooks/wellsight_v2/s6_review/_build_nisar_gslc_qgis_project_9t.py

What it holds:
  * 24 NISAR rasters from _nisar_gslc_stack_pad_pit_seasonal_9t.py, one group per track.
    Season means are grey (dark = low backscatter). Leaf-on minus fall change is a
    diverging blue-white-orange ramp centred on that raster's own median, because the
    tile median differs by track (beta/provisional calibration offset).
  * 9t lidar hillshade underneath, and the 1 m DEM set as the project terrain, so
    View > 3D Map View drapes the radar on the lidar surface.
  * Pads (plat) and pits (pit_outside) outlines on top.
Colours: blue #1F5FA8 / orange #D97706 are the validated lost/found pair
(validate_palette.py --mode light --pairs all, worst-pair dE 21.1 deutan).
Pads and pits also differ by line style (solid vs dashed), so never colour alone.
"""
import glob, os, re, sys
import numpy as np
from qgis.core import (Qgis, QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer,
    QgsSingleBandGrayRenderer, QgsContrastEnhancement, QgsSingleBandPseudoColorRenderer,
    QgsRasterShader, QgsColorRampShader, QgsFillSymbol, QgsRasterDemTerrainProvider,
    QgsCoordinateReferenceSystem, QgsReferencedRectangle)
from qgis.PyQt.QtGui import QColor

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
NISAR_DIR = os.path.join(REPO, "data", "9t", "derived", "nisar_gslc_5m")
DEM = os.path.join(REPO, "data", "9t", "derived", "1m", "dem_9t_1m.tif")
HILLSHADE = os.path.join(REPO, "data", "9t", "derived", "1m", "hillshade_9t_1m.tif")
ANN = os.path.join(REPO, "qgis", "annotations", "annotations_proj.gpkg")
OUT = os.path.join(REPO, "qgis", "nisar_gslc_seasonal_backscatter_draped_on_lidar_dem_9t_5m.qgz")

BLUE, ORANGE = "#1F5FA8", "#D97706"
SEASON_LABEL = {"leafoff_fall": "fall leaf-off mean (Oct-Nov 2025)",
                "winter": "winter mean (Dec 2025-Jan 2026)",
                "leafon": "summer leaf-on mean (Jun-Sep 2026)",
                "change_leafon_vs_fall": "change, leaf-on minus fall"}
TRACK_LABEL = {"t162A": "track 162 ascending", "t090A": "track 090 ascending",
               "t026D": "track 026 descending"}
ORDER = ["change_leafon_vs_fall", "leafon", "winter", "leafoff_fall"]


def pct(layer, lo, hi):
    from osgeo import gdal
    ds = gdal.Open(layer.source()); b = ds.GetRasterBand(1)
    a = b.ReadAsArray().astype("float64").ravel()
    nd = b.GetNoDataValue()
    a = a[np.isfinite(a) & ((a != nd) if nd is not None else True)]
    return [float(v) for v in np.percentile(a, [lo, 50, hi])]


def grey(layer):
    lo, _, hi = pct(layer, 2, 98)
    r = QgsSingleBandGrayRenderer(layer.dataProvider(), 1)
    ce = QgsContrastEnhancement(layer.dataProvider().dataType(1))
    ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
    ce.setMinimumValue(lo); ce.setMaximumValue(hi)
    r.setContrastEnhancement(ce)
    layer.setRenderer(r)


def diverging(layer, half_width_db=3.0):
    _, med, _ = pct(layer, 2, 98)
    sh = QgsColorRampShader(med - half_width_db, med + half_width_db)
    sh.setColorRampType(QgsColorRampShader.Interpolated)
    sh.setColorRampItemList([
        QgsColorRampShader.ColorRampItem(med - half_width_db, QColor(BLUE), f"{-half_width_db:+.0f} dB vs tile median"),
        QgsColorRampShader.ColorRampItem(med, QColor("#F7F7F7"), f"tile median {med:+.1f} dB"),
        QgsColorRampShader.ColorRampItem(med + half_width_db, QColor(ORANGE), f"{half_width_db:+.0f} dB vs tile median")])
    rs = QgsRasterShader(); rs.setRasterShaderFunction(sh)
    layer.setRenderer(QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, rs))


def outline(layer, colour, dashed):
    # white halo underneath so the outline stays visible on the blue/orange change ramp
    sym = QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_color": "255,255,255,230",
        "outline_width": "1.1", "outline_style": "solid"})
    top = QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_color": colour,
        "outline_width": "0.5", "outline_style": "dash" if dashed else "solid"}).symbolLayer(0).clone()
    sym.appendSymbolLayer(top)
    layer.renderer().setSymbol(sym)


def main():
    qgs = QgsApplication([], False); qgs.initQgis()
    proj = QgsProject.instance(); proj.clear()
    root = proj.layerTreeRoot()

    # annotations on top
    g_ann = root.addGroup("annotations (2019 lidar)")
    for lyr_name, label, colour, dashed in (("plat", "pads (solid blue)", BLUE, False),
                                            ("pit_outside", "pits incl. rim (dashed orange)", ORANGE, True)):
        v = QgsVectorLayer(f"{ANN}|layername={lyr_name}", label, "ogr")
        assert v.isValid(), lyr_name
        outline(v, colour, dashed)
        proj.addMapLayer(v, False); g_ann.addLayer(v)

    files = sorted(glob.glob(os.path.join(NISAR_DIR, "nisar_gslc_*_mean_db_t*_asdelivered_9t_5m.tif")))
    assert len(files) == 24, len(files)
    pat = re.compile(r"nisar_gslc_(hh|hv)_(.+)_mean_db_(t\d{3}[AD])_asdelivered")
    g_nisar = root.addGroup("NISAR L-band GSLC, 5 m, as delivered (no shift)")
    first = True
    for track in ("t162A", "t090A", "t026D"):
        g_t = g_nisar.addGroup(TRACK_LABEL[track])
        g_t.setExpanded(track == "t162A")
        for metric in ORDER:
            for pol in ("hv", "hh"):
                f = next(p for p in files if pat.search(os.path.basename(p)).groups() == (pol, metric, track))
                lyr = QgsRasterLayer(f, f"{pol.upper()} {SEASON_LABEL[metric]}", "gdal")
                assert lyr.isValid(), f
                (diverging if metric.startswith("change") else grey)(lyr)
                proj.addMapLayer(lyr, False)
                if first:
                    first_raster, first = lyr, False
                node = g_t.addLayer(lyr)
                # show one layer to start: track 162 HV leaf-on
                on = track == "t162A" and pol == "hv" and metric == "leafon"
                node.setItemVisibilityChecked(on)
        g_t.setItemVisibilityChecked(track == "t162A")

    g_base = root.addGroup("lidar base")
    hs = QgsRasterLayer(HILLSHADE, "hillshade 9t 1 m (2019 lidar)", "gdal")
    dem = QgsRasterLayer(DEM, "DEM 9t 1 m (2019 lidar), 3D terrain", "gdal")
    for l in (hs, dem):
        assert l.isValid(); proj.addMapLayer(l, False); g_base.addLayer(l)
    grey(dem)
    g_base.findLayer(dem.id()).setItemVisibilityChecked(False)
    g_base.findLayer(hs.id()).setItemVisibilityChecked(True)

    # lidar DEM as the project terrain: 3D Map View drapes whatever is visible on it
    tp = QgsRasterDemTerrainProvider(); tp.setLayer(dem)
    proj.elevationProperties().setTerrainProvider(tp)

    proj.setCrs(QgsCoordinateReferenceSystem("EPSG:32617"))
    # annotations run far past 9t, so open on the NISAR window, not the full extent
    proj.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(first_raster.extent(), first_raster.crs()))
    proj.setFilePathStorage(Qgis.FilePathType.Relative)  # relative paths so the project survives a repo move
    proj.setTitle("NISAR GSLC seasonal backscatter on the 9t lidar surface")
    assert proj.write(OUT), OUT
    print("wrote", OUT)
    qgs.exitQgis()


if __name__ == "__main__":
    main()
