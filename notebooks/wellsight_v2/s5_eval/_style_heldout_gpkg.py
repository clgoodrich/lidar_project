"""Make the held-out GeoPackages self-styling in QGIS.

The `heldout` layer already carries a `verdict` column ('found' / 'missed'), but
QGIS draws every feature in one colour until someone manually categorizes it, so
the answer the file exists to show is invisible on load.

This writes a QGIS style into the GeoPackage's `layer_styles` table, which QGIS
reads automatically when the layer is added. Green = the model found it, red =
it did not. It also splits out standalone `found` and `missed` layers, so the
file is usable even if the embedded style is ignored (older QGIS, GDAL-only
tooling, or a different GIS entirely).

Run:
  python notebooks/wellsight_v2/s5_eval/_style_heldout_gpkg.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = path_for("results_9t") / "heldout_overlap"

TARGETS = ["heldout_pit_unet_v2.gpkg", "heldout_pad_unet.gpkg"]

# found: green, semi-transparent fill, solid outline
# missed: red, heavier outline so the failures stand out at any zoom
QML = """<!DOCTYPE qgis PUBLIC 'http://mapserver.org/qgis' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="verdict" forceraster="0"
               enableorderby="0" symbollevels="0">
    <categories>
      <category value="found" symbol="0" label="found by model" render="true"/>
      <category value="missed" symbol="1" label="MISSED by model" render="true"/>
    </categories>
    <symbols>
      <symbol type="fill" name="0" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <prop k="color" v="26,150,65,70"/>
          <prop k="style" v="solid"/>
          <prop k="outline_color" v="26,150,65,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.5"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
      <symbol type="fill" name="1" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <prop k="color" v="215,25,28,90"/>
          <prop k="style" v="solid"/>
          <prop k="outline_color" v="215,25,28,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="1.2"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <blendMode>0</blendMode>
  <featureBlendMode>0</featureBlendMode>
  <layerOpacity>1</layerOpacity>
</qgis>
"""

CREATE = """CREATE TABLE IF NOT EXISTS layer_styles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  f_table_catalog TEXT, f_table_schema TEXT, f_table_name TEXT,
  f_geometry_column TEXT, styleName TEXT, styleQML TEXT, styleSLD TEXT,
  useAsDefault BOOLEAN, description TEXT, owner TEXT, ui TEXT,
  update_time DATETIME DEFAULT (datetime('now')))"""


def main() -> int:
    for fn in TARGETS:
        p = OUT / fn
        if not p.exists():
            print(f"  !! {p} missing"); continue

        g = gpd.read_file(p, layer="heldout")
        n_f = int((g.verdict == "found").sum())
        n_m = int((g.verdict == "missed").sum())

        # standalone layers, so the split is visible without any styling at all
        g[g.verdict == "found"].to_file(p, layer="found", driver="GPKG")
        g[g.verdict == "missed"].to_file(p, layer="missed", driver="GPKG")

        con = sqlite3.connect(p)
        cur = con.cursor()
        cur.execute(CREATE)
        cur.execute("DELETE FROM layer_styles WHERE f_table_name = 'heldout'")
        cur.execute(
            "INSERT INTO layer_styles (f_table_catalog, f_table_schema,"
            " f_table_name, f_geometry_column, styleName, styleQML, styleSLD,"
            " useAsDefault, description, owner, ui) VALUES"
            " ('', '', 'heldout', 'geom', 'found_vs_missed', ?, '', 1,"
            " 'green = model found it, red = model missed it', '', '')",
            (QML,))
        con.commit(); con.close()

        # a plain .qml sidecar too, for anything that ignores layer_styles
        (OUT / (p.stem + ".qml")).write_text(QML)

        print(f"  {fn}: {len(g)} held-out  ->  {n_f} found / {n_m} missed")
        print(f"    layers now: heldout (auto-styled), found, missed, "
              f"model_geometry")
    print(f"\n  all in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
