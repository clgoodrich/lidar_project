"""Diff a human-corrected pit review against the pristine original.

The polygon analog of `_road_corrections_diff.py`. Classifies every original
candidate pit and folds in newly-drawn pits:
  keep   (present, status=keep)        -> true positive  -> POSITIVE label
  reject (deleted OR status=reject)    -> false positive -> HARD NEGATIVE label
  unsure (status=unsure)               -> excluded from training
  added  (drawn in added_pits layer)   -> false negative -> POSITIVE label

Handles BOTH correction styles: flag (status field) and delete (pit missing vs
original). Writes corrections_diff_pits_<key>.gpkg (layers keep/reject/unsure/added)
+ prints a summary. The retrain step (rasterize positives as floor, hard negatives
as bg) consumes this.

CLI:
  python notebooks/wellsight_v2/s6_review/_pit_corrections_diff.py --key 613590
  # custom paths (e.g. dry-run):
  python ..._pit_corrections_diff.py --key 613590 --edited <gpkg> --original <gpkg>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, path_for

REGION = path_for("data_3x3") / "westernpa_d20"


def stat(gdf):
    """count, total area (ha)."""
    if not len(gdf):
        return 0, 0.0
    return len(gdf), round(float(gdf.area.sum()) / 1e4, 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="613590")
    ap.add_argument("--original", default=None)
    ap.add_argument("--edited", default=None)
    ap.add_argument("--added", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rev = REGION / args.key / "review"
    original = Path(args.original) if args.original else rev / f"review_pits_{args.key}_ORIGINAL.gpkg"
    edited = Path(args.edited) if args.edited else rev / f"review_pits_{args.key}.gpkg"
    added_p = Path(args.added) if args.added else rev / f"added_pits_{args.key}.gpkg"
    out = Path(args.out) if args.out else rev / f"corrections_diff_pits_{args.key}.gpkg"

    orig = gpd.read_file(original).to_crs(DST_CRS).set_index("pit_inside_id", drop=False)
    ed = gpd.read_file(edited).to_crs(DST_CRS)
    ed_by_id = ed.set_index("pit_inside_id", drop=False)
    ed_status = ed_by_id["status"].to_dict() if "status" in ed_by_id.columns else {}
    present = set(ed_by_id.index)

    keep_ids, reject_ids, unsure_ids = [], [], []
    for pid in orig.index:
        if pid not in present:
            reject_ids.append(pid)                 # deleted -> false positive
            continue
        st = str(ed_status.get(pid, "keep")).lower()
        if st == "reject":
            reject_ids.append(pid)
        elif st == "unsure":
            unsure_ids.append(pid)
        else:
            keep_ids.append(pid)

    keep = orig.loc[keep_ids]; reject = orig.loc[reject_ids]; unsure = orig.loc[unsure_ids]

    added = gpd.GeoDataFrame(geometry=[], crs=DST_CRS)
    if added_p.exists():
        try:
            a = gpd.read_file(added_p)
            if len(a):
                added = a.to_crs(DST_CRS)
        except Exception:
            pass

    if out.exists():
        out.unlink()
    for name, g in [("keep", keep), ("reject", reject), ("unsure", unsure), ("added", added)]:
        if len(g):
            g.reset_index(drop=True).to_file(out, layer=name, driver="GPKG")

    n0 = len(orig)
    nk, ak = stat(keep); nr, ar = stat(reject); nu, au = stat(unsure); na, aa = stat(added)
    print(f"=== pit corrections diff [{args.key}] ===")
    print(f"original candidates : {n0}")
    print(f"  keep   (TP -> positive)      : {nk:5d}  {ak:7.3f} ha")
    print(f"  reject (FP -> hard negative) : {nr:5d}  {ar:7.3f} ha")
    print(f"  unsure (excluded)            : {nu:5d}  {au:7.3f} ha")
    print(f"  added  (FN -> positive)      : {na:5d}  {aa:7.3f} ha")
    corrected = nr + nu + (na > 0)
    print(f"corrections made : {nr} rejected, {nu} unsure, {na} added")
    if corrected == 0:
        print("NOTE: no corrections detected (edited == original). Nothing to learn yet.")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
