"""Diff a human-corrected road review against the pristine original.

Classifies every original ~40 m segment and folds in newly-drawn roads:
  keep   (present, status=keep)        -> true positive  -> POSITIVE label
  reject (deleted OR status=reject)    -> false positive -> HARD NEGATIVE label
  unsure (status=unsure)               -> excluded from training
  added  (drawn in added_roads layer)  -> false negative -> POSITIVE label

Handles BOTH correction styles: flag (status field) and delete (segment missing
vs original). Writes corrections_diff_<key>.gpkg (layers keep/reject/unsure/added)
+ prints a summary. Step 3 (label rasterization + retrain) consumes this.

CLI:
  python notebooks/wellsight/build/_road_corrections_diff.py --key 613590
  # custom paths (e.g. dry-run):
  python ..._road_corrections_diff.py --key 613590 --edited <gpkg> --original <gpkg>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, path_for

REGION = path_for("data_3x3") / "westernpa_d20"


def km(gdf):
    return round(float(gdf.length.sum()) / 1000, 2) if len(gdf) else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="613590")
    ap.add_argument("--original", default=None)
    ap.add_argument("--edited", default=None)
    ap.add_argument("--added", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rev = REGION / args.key / "review"
    original = Path(args.original) if args.original else rev / f"review_roads_{args.key}_ORIGINAL.gpkg"
    edited = Path(args.edited) if args.edited else rev / f"review_roads_{args.key}.gpkg"
    added_p = Path(args.added) if args.added else rev / f"added_roads_{args.key}.gpkg"
    out = Path(args.out) if args.out else rev / f"corrections_diff_{args.key}.gpkg"

    orig = gpd.read_file(original).to_crs(DST_CRS).set_index("seg_id", drop=False)
    ed = gpd.read_file(edited).to_crs(DST_CRS)
    ed_by_id = ed.set_index("seg_id", drop=False)
    ed_status = ed_by_id["status"].to_dict() if "status" in ed_by_id.columns else {}
    present = set(ed_by_id.index)

    keep_ids, reject_ids, unsure_ids = [], [], []
    for sid in orig.index:
        if sid not in present:
            reject_ids.append(sid)                 # deleted -> false positive
            continue
        st = str(ed_status.get(sid, "keep")).lower()
        if st == "reject":
            reject_ids.append(sid)
        elif st == "unsure":
            unsure_ids.append(sid)
        else:
            keep_ids.append(sid)

    keep = orig.loc[keep_ids]; reject = orig.loc[reject_ids]; unsure = orig.loc[unsure_ids]

    added = gpd.GeoDataFrame(geometry=[], crs=DST_CRS)
    if added_p.exists():
        try:
            a = gpd.read_file(added_p)
            if len(a):
                added = a.to_crs(DST_CRS)
        except Exception:
            pass

    # write layers
    if out.exists():
        out.unlink()
    for name, g in [("keep", keep), ("reject", reject), ("unsure", unsure), ("added", added)]:
        if len(g):
            g.reset_index(drop=True).to_file(out, layer=name, driver="GPKG")

    n0 = len(orig)
    print(f"=== corrections diff [{args.key}] ===")
    print(f"original segments : {n0}  ({km(orig)} km)")
    print(f"  keep   (TP -> positive)      : {len(keep):5d}  {km(keep):7.2f} km")
    print(f"  reject (FP -> hard negative) : {len(reject):5d}  {km(reject):7.2f} km")
    print(f"  unsure (excluded)            : {len(unsure):5d}  {km(unsure):7.2f} km")
    print(f"  added  (FN -> positive)      : {len(added):5d}  {km(added):7.2f} km")
    corrected = len(reject) + len(unsure) + (len(added) > 0)
    print(f"corrections made : {len(reject)} rejected, {len(unsure)} unsure, {len(added)} added")
    if corrected == 0:
        print("NOTE: no corrections detected (edited == original). Nothing to learn yet.")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
