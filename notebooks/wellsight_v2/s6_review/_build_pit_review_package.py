"""Build a QGIS review package for human-in-the-loop pit correction on a block.

The polygon analog of `_build_road_review_package.py`. Pits are discrete objects,
so (unlike roads) there is no line-chopping — each candidate pit polygon becomes
ONE reviewable feature with a `status` field. The reviewer flags bad candidates
`reject` (NOT delete) so the false-positive geometry survives as a hard negative,
marks `unsure` to exclude, and draws missed pits in a separate `added` layer.

Outputs (under <block>/review/):
    review_pits_<key>.gpkg           layer 'review'  — candidate pits, status=keep
    review_pits_<key>_ORIGINAL.gpkg  pristine copy for the diff to compare against
    review_pits_<key>.qml            categorized symbology + status edit widget
    added_pits_<key>.gpkg            layer 'added'   — empty; draw missed pits here
    README_EDIT.md                   QGIS instructions

CLI:
  python notebooks/wellsight_v2/s6_review/_build_pit_review_package.py --key 613590
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pyogrio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, path_for

REGION = path_for("data_3x3") / "westernpa_d20"

QML = """<!DOCTYPE qgis>
<qgis version="3.34" styleCategories="Symbology|Fields|Forms|Default">
  <renderer-v2 type="categorizedSymbol" attr="status" forceraster="0" symbollevels="0" enableorderby="0">
    <categories>
      <category value="keep" symbol="0" label="keep" render="true"/>
      <category value="reject" symbol="1" label="reject" render="true"/>
      <category value="unsure" symbol="2" label="unsure" render="true"/>
      <category value="" symbol="3" label="(other)" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="fill" alpha="1" clip_to_extent="1">
        <layer class="SimpleFill" enabled="1">
          <Option type="Map">
            <Option name="color" type="QString" value="0,180,0,60"/>
            <Option name="outline_color" type="QString" value="0,140,0,255"/>
            <Option name="outline_width" type="QString" value="0.5"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="1" type="fill" alpha="1" clip_to_extent="1">
        <layer class="SimpleFill" enabled="1">
          <Option type="Map">
            <Option name="color" type="QString" value="227,26,28,80"/>
            <Option name="outline_color" type="QString" value="180,0,0,255"/>
            <Option name="outline_width" type="QString" value="0.7"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="2" type="fill" alpha="1" clip_to_extent="1">
        <layer class="SimpleFill" enabled="1">
          <Option type="Map">
            <Option name="color" type="QString" value="255,160,0,80"/>
            <Option name="outline_color" type="QString" value="200,120,0,255"/>
            <Option name="outline_width" type="QString" value="0.6"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="3" type="fill" alpha="1" clip_to_extent="1">
        <layer class="SimpleFill" enabled="1">
          <Option type="Map">
            <Option name="color" type="QString" value="150,150,150,50"/>
            <Option name="outline_color" type="QString" value="120,120,120,255"/>
            <Option name="outline_width" type="QString" value="0.4"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <fieldConfiguration>
    <field name="status">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option name="map" type="List">
              <Option type="Map"><Option name="keep" type="QString" value="keep"/></Option>
              <Option type="Map"><Option name="reject" type="QString" value="reject"/></Option>
              <Option type="Map"><Option name="unsure" type="QString" value="unsure"/></Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <defaults>
    <default field="status" expression="'keep'" applyOnUpdate="0"/>
  </defaults>
</qgis>
"""

README = """# Pit review — {key}

Goal: correct the model's candidate pits so we can retrain on YOUR fixes.

## Layers to load (drag into QGIS, in this order)
1. `hillshade_{key}_1m.tif`            (basemap)
2. `pit_prob_floor_{key}_1m.tif`       (optional: model confidence heat-map)
3. `review/review_pits_{key}.gpkg`     (the candidate pits — you edit this)
4. `review/added_pits_{key}.gpkg`      (empty — you DRAW missed pits here)

## How to correct (flag, don't delete)
- Toggle editing (pencil icon) on `review_pits`.
- Click a bad candidate (a tree-throw, pond, shadow — not a real pit). In the
  attribute table or Field Calculator set **status = 'reject'**. DO NOT delete —
  the rejected polygon is used as a hard negative ("not a pit") in training.
- Leave good candidates as **status = 'keep'** (the default).
- If unsure, set **status = 'unsure'** and we'll exclude it from training.
- For real pits the model MISSED: toggle editing on `added_pits`, draw a polygon
  around the depression. status auto = 'added'.
- Save edits (Ctrl+S) and toggle editing off when done.

## Tips
- Style `review_pits` by `status` (keep=green, reject=red) to track progress
  (the bundled .qml does this automatically).
- Sort the attribute table by `confidence` ascending to review the model's
  least-confident candidates first — those are the likeliest false positives.

Each candidate is one polygon — flag the whole thing in a single click.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="613590")
    ap.add_argument("--src", default=None, help="source gpkg (default pits_opt_<key>_1m.gpkg)")
    ap.add_argument("--layer", default="pits_clean",
                    help="layer in src to review (pits_clean | pits_all)")
    args = ap.parse_args()

    blk = REGION / args.key
    src = Path(args.src) if args.src else blk / f"pits_opt_{args.key}_1m.gpkg"
    out_dir = blk / "review"
    out_dir.mkdir(parents=True, exist_ok=True)

    g = gpd.read_file(src, layer=args.layer).to_crs(DST_CRS)
    keep_cols = [c for c in ("area_m2", "circularity", "eccentricity",
                             "mean_pfloor", "confidence", "dist_well_m") if c in g.columns]
    rows = []
    for pid, row in g.reset_index(drop=True).iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        rec = {"pit_inside_id": int(pid), "status": "keep", "geometry": geom}
        for c in keep_cols:
            rec[c] = row[c]
        rows.append(rec)
    review = gpd.GeoDataFrame(rows, crs=DST_CRS)
    review_path = out_dir / f"review_pits_{args.key}.gpkg"
    review.to_file(review_path, layer="review", driver="GPKG")
    # pristine backup for the diff
    orig_path = out_dir / f"review_pits_{args.key}_ORIGINAL.gpkg"
    if orig_path.exists():
        orig_path.unlink()
    shutil.copyfile(review_path, orig_path)
    # symbology
    (out_dir / f"review_pits_{args.key}.qml").write_text(QML, encoding="utf-8")
    print(f"review: {len(review)} candidate pits -> {review_path.name} (+ _ORIGINAL backup, .qml)")

    # empty 'added' layer (Polygon) for drawing missed pits
    added = gpd.GeoDataFrame({"status": gpd.pd.Series([], dtype="object"),
                              "note": gpd.pd.Series([], dtype="object")},
                             geometry=gpd.GeoSeries([], crs=DST_CRS))
    added_path = out_dir / f"added_pits_{args.key}.gpkg"
    pyogrio.write_dataframe(added, added_path, layer="added", geometry_type="Polygon")
    print(f"added : empty draw-here layer -> {added_path.name}")

    (out_dir / "README_EDIT.md").write_text(README.format(key=args.key), encoding="utf-8")
    print(f"note  : README_EDIT.md")
    print(f"\nReview package ready: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
