"""S7 (3.5). Adjudicate the two blind annotation passes into one truth with seen_in and activity.

Purpose
    Pass L (lidar derivatives and hillshade only) and pass O (imagery only), drawn by different reviewers
    with no model output and no well records. Match L to O greedily by IoU 0.3 within class.
    Matched pairs keep the union polygon and seen_in = both. Unmatched keep seen_in = lidar or optical.
    activity comes from pass O when present, else 'unclear'. Primary truth is the union. The
    intersection (seen_in = both) is a sensitivity. Minutes per block per pass are summarised.
Inputs
    expansions/3_geography/3_5_oklahoma_kansas/data/raw/labels/pass_L_<area>.gpkg, pass_O_<area>.gpkg
Outputs
    data/<area>/results/modality/mod_truth_features_<area>.gpkg   (truth_id, class, seen_in, activity, block_id)
    data/<area>/results/modality/mod_annotation_minutes_<area>.csv
Run
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_truth_adjudicate.py --area ok_rogers
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.5"


def adjudicate(L, O):
    import geopandas as gpd
    ek.assert_crs(L, O.crs)
    rows = []
    usedL, usedO = set(), set()
    for cls in sorted(set(L["class"]) | set(O["class"])):
        l, o = L[L["class"] == cls], O[O["class"] == cls]
        m = gt.polygon_f1(l.reset_index(drop=True), o.reset_index(drop=True))
        for i, j in m["pairs"]:
            li, oj = l.index[i], o.index[j]
            usedL.add(li)
            usedO.add(oj)
            rows.append({"class": cls, "seen_in": "both", "activity": O.loc[oj].get("activity", "unclear"),
                         "geometry": L.loc[li].geometry.union(O.loc[oj].geometry)})
    for idx, r in L.drop(index=list(usedL)).iterrows():
        rows.append({"class": r["class"], "seen_in": "lidar", "activity": "unclear", "geometry": r.geometry})
    for idx, r in O.drop(index=list(usedO)).iterrows():
        rows.append({"class": r["class"], "seen_in": "optical", "activity": r.get("activity", "unclear"),
                     "geometry": r.geometry})
    t = gpd.GeoDataFrame(rows, geometry="geometry", crs=L.crs)
    t["activity"] = t["activity"].fillna("unclear")
    t["truth_id"] = range(1, len(t) + 1)
    ek.assert_rows(t, len(L) + len(O) - (len(usedL)), "adjudicated truth")
    return t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    import geopandas as gpd
    try:
        pl = gt.config_input(cfg, "truth_pass_L", EXP, area=a.area)
        po = gt.config_input(cfg, "truth_pass_O", EXP, area=a.area)
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    L, O = gpd.read_file(pl), gpd.read_file(po)
    t = adjudicate(L, O)
    b = gpd.read_file(ek.area_dir(a.area) / "results" / "modality" / f"mod_blocks_roles_{a.area}.gpkg")
    j = gpd.sjoin(gpd.GeoDataFrame(t[["truth_id"]], geometry=t.geometry.centroid, crs=t.crs),
                  b[["block_id", "geometry"]], how="left", predicate="within")
    t["block_id"] = j.drop_duplicates("truth_id").set_index("truth_id")["block_id"].reindex(t["truth_id"]).to_numpy()
    out = ek.area_dir(a.area) / "results" / "modality" / f"mod_truth_features_{a.area}.gpkg"
    t.to_file(out, driver="GPKG")
    mins = pd.concat([L.assign(pass_="L"), O.assign(pass_="O")]).groupby(["pass_", "block_id"])["minutes"].max()
    mp = out.with_name(f"mod_annotation_minutes_{a.area}.csv")
    mins.reset_index().to_csv(mp, index=False)
    print(t.groupby(["class", "seen_in"]).size().to_string(), f"\nwrote {out}\nwrote {mp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
