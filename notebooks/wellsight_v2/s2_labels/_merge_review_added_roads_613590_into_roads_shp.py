"""Fold the corrected 613590 road review into the master annotation file.

Two products of the round-2 active-learning loop go in:

    review_roads_613590.gpkg  layer 'review'  15,057 segments, all status='keep'
    added_roads_613590.gpkg   layer 'added'      487 hand-drawn missed roads

The review layer is the model's own vectorized output, chunked to ~9 m so a bad
stretch can be flagged without splitting a line. 1,911 chunks were deleted by
hand during review; what survives is road. Appending 15,057 nine-metre stubs
would change roads.shp from a file of hand-drawn polylines (2,200 features /
348 km, 158 m mean) into a file of chunks, so the chunks are reassembled first:
dissolve by parent_id, line_merge, then explode. Where deleted chunks left a
gap mid-parent the merge yields several parts, and each becomes its own line --
which is correct, because a gap is a place the annotator said there is no road.

Rejected geometry is NOT carried over. It stays in the review package, where the
retraining script reads it as a hard negative.

A `src` column records provenance so this pass can be audited or undone:
    prior              the 2,200 features already in roads.shp
    613590_review_r2   reassembled model roads the annotator kept
    613590_added_r2    roads the annotator drew in by hand

roads.shp is copied to a dated backup directory before it is rewritten.

Outputs:
    data/derivatives/annotations/roads.shp                  (rewritten in place)
    data/derivatives/annotations/_backup_roads_2026-08-05/  (pre-merge copy)
    data/derivatives/annotations/_merge_613590_roads_summary.json

After this, rerun the projection step so the training mirror stays in sync:
    python notebooks/wellsight_v2/s2_labels/_prep_annotations.py

Reproduce:
  python notebooks/wellsight_v2/s2_labels/_merge_review_added_roads_613590_into_roads_shp.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import linemerge

ROOT = Path(__file__).resolve().parents[3]
ANN = ROOT / "data" / "derivatives" / "annotations"
REVIEW = (ROOT / "data" / "derivatives" / "tiles" / "data_3x3" / "westernpa_d20"
          / "613590" / "review")
ROADS = ANN / "roads.shp"
BACKUP = ANN / "_backup_roads_2026-08-05"
SUMMARY = ANN / "_merge_613590_roads_summary.json"
STAGED = ANN / "roads_with_613590_r2_staged.gpkg"

WORK_CRS = 6346          # project CRS, metres -- all lengths measured here
FILE_CRS = 4326          # roads.shp ships in WGS84; keep it that way
SHP_SIDECARS = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qpj", ".sbn", ".sbx")


def reassemble(seg: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Merge ~9 m review chunks back into contiguous lines, one row per run."""
    parts = []
    for pid, grp in seg.groupby("parent_id"):
        merged = linemerge(list(grp.geometry))
        geoms = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
        for g in geoms:
            parts.append({"parent_id": int(pid), "geometry": g})
    out = gpd.GeoDataFrame(parts, crs=seg.crs)
    return out[~out.geometry.is_empty & out.geometry.notna()].reset_index(drop=True)


def main() -> int:
    rv = gpd.read_file(REVIEW / "review_roads_613590.gpkg", layer="review").to_crs(WORK_CRS)
    ad = gpd.read_file(REVIEW / "added_roads_613590.gpkg", layer="added").to_crs(WORK_CRS)
    rd = gpd.read_file(ROADS)

    if rd.crs is None:
        raise SystemExit("roads.shp has no CRS -- refusing to guess")

    status = rv.status.fillna("<null>").str.lower()
    dropped = int((status != "keep").sum())
    if dropped:
        print(f"  review: dropping {dropped} segments not marked 'keep'")
    keep = rv[status == "keep"].copy()

    print(f"  review  : {len(keep):6d} kept chunks  {keep.length.sum()/1000:7.2f} km"
          f"  ({keep.parent_id.nunique()} parent lines)")
    merged = reassemble(keep)
    print(f"  reassembled -> {len(merged):6d} lines     "
          f"{merged.length.sum()/1000:7.2f} km"
          f"  (mean {merged.length.mean():.0f} m)")
    print(f"  added   : {len(ad):6d} lines       {ad.length.sum()/1000:7.2f} km")

    # sanity: hand-drawn additions should not retrace what the model already got
    dup = ad.geometry.intersection(merged.union_all().buffer(2.0)).length.sum()
    print(f"  added within 2 m of a kept model road: {dup/1000:.2f} km "
          f"({100*dup/max(ad.length.sum(), 1):.1f}% of added)")

    rd_m = rd.to_crs(WORK_CRS)
    new_m = pd.concat([merged.geometry, ad.geometry], ignore_index=True)
    overlap = gpd.GeoSeries(new_m, crs=WORK_CRS).intersects(
        rd_m.union_all().buffer(5.0)).sum()
    print(f"  new lines within 5 m of an existing roads.shp line: {overlap}")

    before_n, before_km = len(rd), rd_m.length.sum() / 1000
    print(f"\n  roads.shp before: {before_n} features  {before_km:.2f} km  {rd.crs}")

    if not BACKUP.exists():
        BACKUP.mkdir(parents=True)
        for ext in SHP_SIDECARS:
            p = ROADS.with_suffix(ext)
            if p.exists():
                shutil.copy2(p, BACKUP / p.name)
        print(f"  backed up roads.* -> {BACKUP}")
    else:
        print(f"  backup already exists, left alone: {BACKUP}")

    rd = rd.copy()
    if "src" not in rd.columns:
        rd["src"] = "prior"
    merged_ll = merged.to_crs(FILE_CRS)
    added_ll = ad.to_crs(FILE_CRS)

    def frame(g, src):
        return gpd.GeoDataFrame({"id": None, "src": src},
                                geometry=g.geometry.values, crs=FILE_CRS,
                                index=range(len(g)))

    out = gpd.GeoDataFrame(
        pd.concat([rd[["id", "src", "geometry"]],
                   frame(merged_ll, "613590_review_r2"),
                   frame(added_ll, "613590_added_r2")], ignore_index=True),
        crs=FILE_CRS)

    bad = int((~out.geometry.is_valid).sum())
    empty = int((out.geometry.is_empty | out.geometry.isna()).sum())
    if bad or empty:
        raise SystemExit(f"refusing to write: {bad} invalid, {empty} empty geoms")

    # QGIS holds a write lock on an open shapefile. Rather than lose the merge,
    # stage it beside roads.shp so the run is repeatable once the layer is closed.
    try:
        out.to_file(ROADS, driver="ESRI Shapefile")
        target = ROADS
    except PermissionError:
        target = STAGED
        if target.exists():
            target.unlink()
        out.to_file(target, layer="roads", driver="GPKG")
        print(f"\n  roads.shp is LOCKED (open in QGIS). Merge staged instead:")
        print(f"    {target}")
        print("  Close the roads layer in QGIS and rerun this script to write "
              "roads.shp in place.")

    chk = gpd.read_file(target)
    chk_m = chk.to_crs(WORK_CRS)
    after_km = chk_m.length.sum() / 1000
    print(f"  roads.shp after : {len(chk)} features  {after_km:.2f} km  {chk.crs}")
    print(chk.src.value_counts().to_string())

    summ = {
        "date": "2026-08-05",
        "source_review": str(REVIEW / "review_roads_613590.gpkg"),
        "source_added": str(REVIEW / "added_roads_613590.gpkg"),
        "review_chunks_kept": int(len(keep)),
        "review_chunks_not_keep_dropped": dropped,
        "review_reassembled_lines": int(len(merged)),
        "review_km": round(float(merged.length.sum() / 1000), 2),
        "added_lines": int(len(ad)),
        "added_km": round(float(ad.length.sum() / 1000), 2),
        "added_km_within_2m_of_model_road": round(float(dup / 1000), 2),
        "new_lines_within_5m_of_existing_roads_shp": int(overlap),
        "roads_shp_before": {"features": before_n, "km": round(float(before_km), 2)},
        "roads_shp_after": {"features": int(len(chk)), "km": round(float(after_km), 2)},
        "crs": str(chk.crs),
        "backup": str(BACKUP),
        "written_to": str(target),
        "roads_shp_updated_in_place": target == ROADS,
    }
    SUMMARY.write_text(json.dumps(summ, indent=2))
    print(f"\nwrote {target}\nwrote {SUMMARY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
