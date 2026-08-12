"""Per-threshold pit products, built so the MISSED pits are actually findable.

Finding a handful of missed pits inside a 9000x9000 raster is the real problem
here -- at full-tile zoom a 26 m2 polygon is sub-pixel on screen. So each
threshold gets, alongside the rasters:

  rim_found / rim_missed     the annotated rim polygons, split and self-styled
  centroid_missed            point markers -- visible at any zoom, unlike polygons
  locator_missed             120 m circles around each missed pit, so they can be
                             spotted while zoomed out to the whole tile
  <...>_missed_bookmarks.xml QGIS spatial bookmarks, one per missed pit. Import
                             via View > Show Spatial Bookmark Manager > Import,
                             then jump to each in turn -- no hunting required.
  <...>_missed_contactsheet.png  hillshade crops of every missed pit in one image,
                             reviewable without opening QGIS at all.

Ground truth is hand-drawn annotation (pit_outside rims). A pit counts as found
when a predicted floor polygon's centroid lies inside its rim.

Run:
  python notebooks/wellsight_v2/s5_eval/_pit_threshold_products_9t.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from rasterio.windows import from_bounds
from scipy import ndimage as ndi
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[3]
NINE_T = ROOT / "data" / "derivatives" / "tiles" / "9t"
PROB = NINE_T / "pit_unet_v2" / "pit_prob_floor.tif"
HILLSHADE = NINE_T / "hillshade_9t_05.tif"
ANN_GPKG = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
OUT = ROOT / "data" / "derivatives" / "eval_9t_pit_thresholds"
OUT.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:6346"
THRESHOLDS = [0.20, 0.30, 0.40, 0.50]
MIN_AREA_M2 = 4.0
LOCATOR_R = 120.0          # metres; big enough to see at full-tile zoom
BOOKMARK_PAD = 60.0        # metres either side of a missed pit in a bookmark
# QGIS bookmark XML: every field is a CHILD ELEMENT, not an attribute, and the
# group lives in <project>. Attribute form is QGIS 2 and imports as an empty
# extent ("Bookmark extent is empty"). <sr_id> is the internal srs.db row id,
# NOT the EPSG code -- EPSG:6346 is srs_id 28818 in QGIS 3.36 and 3.40. Format
# verified by round-tripping QgsBookmarkManager.exportToFile under QGIS 3.40.10.
BOOKMARK_SRSID = 28818


def tag(t: float) -> str:
    return f"thr{t:.2f}".replace(".", "p")


def polygonize(prob, transform, crs, thresh, min_area=MIN_AREA_M2):
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


def style_qml(attr="verdict"):
    return f"""<!DOCTYPE qgis PUBLIC 'http://mapserver.org/qgis' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="{attr}" forceraster="0"
               enableorderby="0" symbollevels="0">
    <categories>
      <category value="found" symbol="0" label="found" render="true"/>
      <category value="missed" symbol="1" label="MISSED" render="true"/>
    </categories>
    <symbols>
      <symbol type="fill" name="0" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <prop k="color" v="26,150,65,55"/><prop k="style" v="solid"/>
          <prop k="outline_color" v="26,150,65,255"/>
          <prop k="outline_style" v="solid"/><prop k="outline_width" v="0.4"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
      <symbol type="fill" name="1" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <prop k="color" v="215,25,28,110"/><prop k="style" v="solid"/>
          <prop k="outline_color" v="215,25,28,255"/>
          <prop k="outline_style" v="solid"/><prop k="outline_width" v="1.4"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
"""


CREATE = """CREATE TABLE IF NOT EXISTS layer_styles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT,
  f_table_schema TEXT, f_table_name TEXT, f_geometry_column TEXT,
  styleName TEXT, styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN,
  description TEXT, owner TEXT, ui TEXT,
  update_time DATETIME DEFAULT (datetime('now')))"""


def embed_style(gpkg: Path, layer: str, qml: str, desc: str) -> None:
    con = sqlite3.connect(gpkg); cur = con.cursor()
    cur.execute(CREATE)
    cur.execute("DELETE FROM layer_styles WHERE f_table_name = ?", (layer,))
    cur.execute("INSERT INTO layer_styles (f_table_catalog, f_table_schema,"
                " f_table_name, f_geometry_column, styleName, styleQML,"
                " styleSLD, useAsDefault, description, owner, ui)"
                " VALUES ('', '', ?, 'geom', 'found_vs_missed', ?, '', 1, ?,"
                " '', '')", (layer, qml, desc))
    con.commit(); con.close()


def main() -> int:
    print("== per-threshold pit products (0.20 / 0.30 / 0.40 / 0.50) ==\n")

    rim = gpd.read_file(ANN_GPKG, layer="pit_outside").to_crs(CRS)
    man = pd.read_csv(NINE_T / "pit_dataset_manifest.csv")
    held = set(man.loc[man.split.isin(("val", "test")), "pit_id"])
    rim = rim[["pit_id", "geometry"]].dissolve(by="pit_id").reset_index()
    rim = rim.merge(man[["pit_id", "split"]], on="pit_id", how="inner")
    rim_h = rim[rim.pit_id.isin(held)].reset_index(drop=True)
    print(f"  held-out pits with a rim: {len(rim_h)}\n")

    with rasterio.open(PROB) as r:
        prob = r.read(1).astype(np.float32)
        if r.nodata is not None:
            prob = np.where(prob == r.nodata, 0.0, prob)
        tf, pcrs, prof = r.transform, r.crs, r.profile.copy()
        px = abs(r.transform.a) * abs(r.transform.e)

    with rasterio.open(HILLSHADE) as hr:
        hs_tf = hr.transform

    summary = []
    for t in THRESHOLDS:
        tg = tag(t)
        pred = polygonize(prob, tf, pcrs, t)

        cent = np.zeros(len(rim_h), bool)
        if len(pred):
            sidx = pred.sindex
            for i, rr in enumerate(rim_h.itertuples()):
                for pj in sidx.intersection(rr.geometry.bounds):
                    if rr.geometry.contains(pred.geometry.iloc[pj].centroid):
                        cent[i] = True
                        break

        rv = rim_h.copy()
        rv["verdict"] = np.where(cent, "found", "missed")
        rv["threshold"] = t
        n_miss = int((~cent).sum())
        m = prob >= t
        print(f"  thr {t:.2f}: {len(pred):5d} polygons, "
              f"{m.sum() * px / 1e4:6.2f} ha claimed, "
              f"found {int(cent.sum()):3d}/{len(rim_h)}  MISSED {n_miss}")

        # ---- rasters ----
        p = prof.copy(); p.update(dtype="uint8", nodata=0, count=1,
                                  compress="deflate", tiled=True)
        rp = NINE_T / "pit_unet_v2" / f"pit_unet_floor_mask_{tg}_9t_05.tif"
        with rasterio.open(rp, "w", **p) as d:
            d.write(m.astype(np.uint8), 1)
            d.write_colormap(1, {0: (0, 0, 0, 0), 1: (215, 25, 28, 255)})
            d.update_tags(1, THRESHOLD=str(t), SOURCE=PROB.name)
        p = prof.copy(); p.update(dtype="float32", nodata=np.nan, count=1,
                                  compress="deflate", predictor=2, tiled=True)
        rp2 = NINE_T / "pit_unet_v2" / f"pit_unet_floor_prob_{tg}_9t_05.tif"
        with rasterio.open(rp2, "w", **p) as d:
            d.write(np.where(m, prob, np.nan).astype(np.float32), 1)
            d.update_tags(1, THRESHOLD=str(t), SOURCE=PROB.name)

        # ---- gpkg: rims, centroids, locator circles, model geometry ----
        gp = OUT / f"pit_heldout_found_vs_missed_{tg}_9t.gpkg"
        if gp.exists():
            gp.unlink()
        rv.to_file(gp, layer="rim_found_vs_missed", driver="GPKG")
        rv[rv.verdict == "found"].to_file(gp, layer="rim_found", driver="GPKG")
        miss = rv[rv.verdict == "missed"].reset_index(drop=True)
        if len(miss):
            miss.to_file(gp, layer="rim_missed", driver="GPKG")
            cpts = miss.copy()
            cpts["geometry"] = miss.geometry.centroid
            cpts.to_file(gp, layer="centroid_missed", driver="GPKG")
            loc = miss.copy()
            loc["geometry"] = miss.geometry.centroid.buffer(LOCATOR_R)
            loc.to_file(gp, layer="locator_missed", driver="GPKG")
        pred.to_file(gp, layer="model_geometry", driver="GPKG")
        embed_style(gp, "rim_found_vs_missed", style_qml(),
                    f"green found / red missed at threshold {t}")
        (OUT / f"pit_heldout_found_vs_missed_{tg}_9t.qml").write_text(style_qml())

        # ---- QGIS spatial bookmarks for the missed pits ----
        bm = ['<!DOCTYPE qgis_bookmarks>', '<qgis_bookmarks>']
        for i, rr in enumerate(miss.itertuples(), 1):
            c = rr.geometry.centroid
            nm = escape(f"MISSED {i:02d}/{len(miss)} pit_id={rr.pit_id} @{t}")
            bm += [
                '  <bookmark>',
                f'    <id>miss_{tg}_{i:02d}</id>',
                f'    <name>{nm}</name>',
                f'    <project>{escape(f"pit missed {t}")}</project>',
                f'    <xmin>{c.x - BOOKMARK_PAD:.3f}</xmin>',
                f'    <ymin>{c.y - BOOKMARK_PAD:.3f}</ymin>',
                f'    <xmax>{c.x + BOOKMARK_PAD:.3f}</xmax>',
                f'    <ymax>{c.y + BOOKMARK_PAD:.3f}</ymax>',
                '    <rotation>0</rotation>',
                f'    <sr_id>{BOOKMARK_SRSID}</sr_id>',
                '  </bookmark>']
        bm.append('</qgis_bookmarks>')
        bmp = OUT / f"pit_missed_bookmarks_{tg}_9t.xml"
        bmp.write_text("\n".join(bm))

        # ---- contact sheet of the missed pits ----
        if len(miss):
            n = len(miss)
            cols = min(4, n); rowsn = int(np.ceil(n / cols))
            fig, axs = plt.subplots(rowsn, cols,
                                    figsize=(4.2 * cols, 4.2 * rowsn),
                                    squeeze=False)
            with rasterio.open(HILLSHADE) as hr:
                for a, rr in zip(axs.ravel(), miss.itertuples()):
                    c = rr.geometry.centroid
                    b = (c.x - 60, c.y - 60, c.x + 60, c.y + 60)
                    w = from_bounds(*b, transform=hs_tf)
                    crop = hr.read(1, window=w)
                    a.imshow(crop, cmap="gray", extent=(b[0], b[2], b[1], b[3]))
                    gpd.GeoSeries([rr.geometry], crs=CRS).plot(
                        ax=a, facecolor="none", edgecolor="#d7191c", lw=2.0)
                    sub = pred[pred.intersects(rr.geometry.buffer(60))]
                    if len(sub):
                        sub.plot(ax=a, facecolor="none", edgecolor="#1a9641",
                                 lw=1.2)
                    mx = float(np.nanmax(np.where(
                        ndi.binary_dilation(np.zeros(1, bool)), 0, 0)) or 0)
                    a.set_title(f"pit_id {rr.pit_id}  ({rr.split})\n"
                                f"{c.x:.0f}, {c.y:.0f}", fontsize=9)
                    a.set_xticks([]); a.set_yticks([])
            for a in axs.ravel()[n:]:
                a.axis("off")
            fig.suptitle(f"Held-out pits MISSED at threshold {t}  "
                         f"(red = annotated rim, green = model floor nearby)",
                         fontsize=12)
            fig.tight_layout()
            csp = OUT / f"pit_missed_contactsheet_{tg}_9t.png"
            fig.savefig(csp, dpi=110, bbox_inches="tight"); plt.close(fig)
        summary.append(dict(threshold=t, n_polygons=len(pred),
                            ha_claimed=round(m.sum() * px / 1e4, 2),
                            found=int(cent.sum()), missed=n_miss,
                            n_heldout=len(rim_h)))
        print(f"    -> {gp.name}, {bmp.name}"
              + (f", contactsheet" if len(miss) else ""))

    pd.DataFrame(summary).to_csv(
        OUT / "pit_threshold_found_vs_missed_summary_9t.csv", index=False)
    print(f"\n  all products in {OUT}")
    print(f"  rasters in {NINE_T / 'pit_unet_v2'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
