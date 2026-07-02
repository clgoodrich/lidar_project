"""Cross-reference the 4 instance-model detections against known well locations.

Ground truth: PA DEP Oil & Gas locations shapefile (all wells) clipped to the 9t
tile extent. For each model's predicted instances, report:
  * how many known wells have a detection within MATCH_RADIUS_M;
  * detection count + implied precision context;
  * nearest-known-well distance distribution for detections.

This is the CLAUDE.md "validate detection algorithms against known well coordinate
data" step. Writes a markdown summary + per-model CSVs under
data/derivatives/tiles/9t/iterations/known_well_validation/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DERIV_9T, DST_CRS  # noqa: E402

OG_SHP = (DERIV_9T.parent.parent.parent / "external" /
          "OilGasLocations_ConventionalUnconventional2026_04" /
          "OilGasLocations_ConventionalUnconventional2026_04.shp")
DEM_REF = DERIV_9T / "dem_9t_05.tif"
OUTDIR = DERIV_9T / "iterations" / "known_well_validation"

MATCH_RADIUS_M = 25.0  # a detection counts as matching a well if centroid within this

MODELS = [
    ("pit_07_maskrcnn", "pits"),
    ("pit_08_yolo", "pits"),
    ("pad_05_maskrcnn", "pads"),
    ("pad_06_yolo", "pads"),
]


def tile_extent_geom() -> tuple[box, str]:
    with rasterio.open(DEM_REF) as r:
        b = r.bounds
        crs = r.crs
    return box(b.left, b.bottom, b.right, b.top), crs


def load_known_wells_in_tile(extent: box, tile_crs) -> gpd.GeoDataFrame:
    wells = gpd.read_file(OG_SHP)
    if wells.crs is None:
        raise RuntimeError("PA O&G shapefile has no CRS")
    wells = wells.to_crs(tile_crs)
    extent_gdf = gpd.GeoDataFrame(geometry=[extent], crs=tile_crs)
    clipped = gpd.sjoin(wells, extent_gdf, predicate="within", how="inner")
    return clipped.drop(columns=[c for c in clipped.columns if c.startswith("index_")])


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    extent, tile_crs = tile_extent_geom()
    print(f"9t extent: {extent.bounds}  CRS={tile_crs}")

    known = load_known_wells_in_tile(extent, tile_crs)
    print(f"Known wells (PA DEP O&G) inside 9t: {len(known)}")
    if len(known) == 0:
        print("No known wells in tile — cannot validate against external ground truth.")
        print("(The 110 hand-annotated pits remain the internal validation set.)")
        (OUTDIR / "SUMMARY.md").write_text(
            "# Known-well validation\n\n"
            f"PA DEP O&G wells inside the 9t extent: **0**.\n\n"
            "The 9t tile does not overlap any PA DEP-catalogued oil & gas wells, so "
            "external ground-truth validation is not possible on this tile. The "
            "110 hand-annotated pits / 79 plats remain the internal validation set "
            "(see LEADERBOARD.md).\n"
        )
        return 0

    known = known.reset_index(drop=True)
    known["geometry"] = known.geometry.centroid
    known_xy = np.array([[g.x, g.y] for g in known.geometry])

    rows = []
    for iter_name, layer in MODELS:
        gpkg = DERIV_9T / "iterations" / iter_name / "instances.gpkg"
        if not gpkg.exists():
            print(f"  {iter_name}: no instances.gpkg, skipping")
            continue
        pred = gpd.read_file(gpkg, layer=layer)
        pred_cent = pred.geometry.centroid
        pred_xy = np.array([[g.x, g.y] for g in pred_cent])

        # For each known well, nearest detection distance.
        matched = 0
        nearest_d = []
        for wx, wy in known_xy:
            d = np.hypot(pred_xy[:, 0] - wx, pred_xy[:, 1] - wy)
            dmin = float(d.min())
            nearest_d.append(dmin)
            if dmin <= MATCH_RADIUS_M:
                matched += 1
        rows.append({
            "model": iter_name,
            "n_detections": len(pred),
            "n_known_wells": len(known),
            "n_wells_matched": matched,
            "well_recall": matched / len(known),
            "median_nearest_m": float(np.median(nearest_d)),
        })
        per_well = known.copy()
        per_well["nearest_det_m"] = nearest_d
        per_well["matched"] = np.array(nearest_d) <= MATCH_RADIUS_M
        keep_cols = [c for c in per_well.columns if c != "geometry"][:8] + \
                    ["nearest_det_m", "matched"]
        per_well[keep_cols].to_csv(OUTDIR / f"{iter_name}_per_well.csv", index=False)
        print(f"  {iter_name}: {matched}/{len(known)} wells matched "
              f"(<= {MATCH_RADIUS_M} m), {len(pred)} detections")

    summary = pd.DataFrame(rows)
    summary.to_csv(OUTDIR / "summary.csv", index=False)

    md = ["# Known-well validation (PA DEP O&G vs instance models)\n",
          f"- Ground truth: PA DEP Oil & Gas locations, clipped to 9t extent = "
          f"**{len(known)} wells**.",
          f"- Match radius: detection centroid within **{MATCH_RADIUS_M} m** of a known well.\n",
          "| Model | Detections | Wells matched | Well recall | Median nearest (m) |",
          "|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['model']} | {r['n_detections']} | "
                  f"{r['n_wells_matched']} / {r['n_known_wells']} | "
                  f"{r['well_recall']:.2f} | {r['median_nearest_m']:.1f} |")
    (OUTDIR / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nWrote {OUTDIR / 'SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
