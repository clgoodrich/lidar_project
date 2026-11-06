"""S7 (3.6). Status join (descriptive Q2). Wells per pad and status by pad class, after scoring is frozen.

Purpose
    Join snapshot wells to pad polygons by containment with a status_join_tol_m tolerance (25 m).
    A well inside several buffered pads goes to the nearest pad. Report wells per pad, the status table
    by pad class with Clopper-Pearson intervals, the count of idle or orphan records on equipped (E1)
    pads, wells with no pad and pads with no well. Status describes a pad. It never edits a label.
    This is the only script that reads status, and it refuses to run before the primary JSON exists.
Inputs
    expansions/3_geography/3_6_california/data/interim/ca_wells_snapshot_ca1.gpkg  (S0)
    data/<area>/results/transfer/ca_pads_truth_<area>.gpkg, ca_pad_primary_<area>.json (S5, frozen)
Outputs
    data/<area>/results/transfer/ca_status_by_pad_class_<area>.csv
    data/<area>/results/transfer/ca_wells_per_pad_<area>.csv
Run
    python expansions/3_geography/3_6_california/src/_ca_status_by_pad.py --area ca1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.6"


def join_wells_to_pads(wells, pads, tol_m: float):
    import geopandas as gpd
    ek.assert_crs(wells, pads.crs)
    buf = pads[["truth_id", "class", "geometry"]].copy()
    buf["geometry"] = buf.geometry.buffer(tol_m)
    j = gpd.sjoin(wells, buf, how="left", predicate="within")
    if j.index.duplicated().any():   # nearest pad when buffers overlap
        pg = pads.set_index("truth_id").geometry
        j["dist"] = [w.distance(pg[t]) if pd.notna(t) else float("inf") for w, t in zip(j.geometry, j["truth_id"])]
        j = j.sort_values("dist").loc[lambda d: ~d.index.duplicated()].sort_index()
    ek.assert_rows(j, len(wells), "wells after pad join")
    return j


def status_tables(j, pads) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    on = j[j["truth_id"].notna()]
    per_pad = on.groupby("truth_id").size().reindex(pads["truth_id"]).fillna(0).astype(int).rename("wells").reset_index()
    per_pad = per_pad.merge(pads[["truth_id", "class"]], on="truth_id")
    rows = []
    for cls, g in on.groupby("class"):
        for st, n in g["status_norm"].value_counts().items():
            p, lo, hi = ek.clopper_pearson(int(n), len(g))
            rows.append({"pad_class": cls, "status": st, "n_wells": int(n), "share": p, "lo": lo, "hi": hi,
                         "evidence": "record, not an evidence level"})
    e1 = on[on["class"] == "E1"]
    counts = {"wells_total": int(len(j)), "wells_no_pad": int(j["truth_id"].isna().sum()),
              "pads_no_well": int((per_pad["wells"] == 0).sum()),
              "idle_or_orphan_on_equipped": int(e1["status_norm"].isin(["idle", "orphan"]).sum())}
    return pd.DataFrame(rows), per_pad, counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    import geopandas as gpd
    d = gt.area_transfer_dir(a.area)
    try:
        gt.require_input(d / f"ca_pad_primary_{a.area}.json", "frozen primary result (S5)",
                         verify="Status is read only after scoring is frozen")
        pads = gpd.read_file(gt.config_input(cfg, "pads_truth", EXP, area=a.area))
        wells = gpd.read_file(gt.require_input(ek.sub(EXP, "data/interim") / "ca_wells_snapshot_ca1.gpkg",
                                               "CalGEM snapshot (S0)")).to_crs(pads.crs)
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    j = join_wells_to_pads(wells[wells["coord_ok"]], pads, float(cfg["prereg"]["status_join_tol_m"]))
    st, per_pad, counts = status_tables(j, pads)
    st.to_csv(d / f"ca_status_by_pad_class_{a.area}.csv", index=False)
    per_pad.to_csv(d / f"ca_wells_per_pad_{a.area}.csv", index=False)
    print(counts)
    print(st.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
