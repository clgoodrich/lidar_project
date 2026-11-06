"""4.3 stage V0. Label gate. Independent leak and non-leak labels per pad, before any imagery work (9t).

Purpose
    Join DEP complaint, inspection and measurement records to pads within radius_m (100 m). A pad is
    'leak' if any record in the year window carries a leak code, 'nonleak' if it has a clean inspection or clean measurement
    and no leak record, else unlabelled. A label is strong only from a measurement source (handheld or
    flux). A complaint is a person's report and is weak. Counts per class and per strength, and
    independent leases per class. Gate. Success at >= 40 per class and >= 15 leases per class. Failure
    below 20 in either class. Pre-specified CLOSE of Question B on failure. Question A continues.
    Also the Hanley and McNeil (1982) arithmetic check that 40 vs 40 at AUC 0.70 gives a lower bound
    above 0.5. That check needs no records and runs now (--hm-only).
    Pad age from the nearest DEP well spud date within radius_m. The 1800 sentinel is its own stratum.
Inputs
    pads      truth/annotations_proj_v2.gpkg layer pad (held)
    records   expansions/4_modalities/4_3_vegetation_stress/data/raw/dep_complaints_inspections_9t.csv (assumed)
    DEP wells dep_wells/venango_wells_all.gpkg (held, read only)
Outputs (expansions/4_modalities/4_3_vegetation_stress/results/<YYYYMMDD>_vegstress_labels_<hash7>/)
    vegstress_label_audit_9t.csv (per pad), vegstress_label_counts_9t.json (gate), provenance
Run
    python expansions/4_modalities/4_3_vegetation_stress/src/_vegstress_label_audit_9t.py [--hm-only] [--records PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _vegstress_shared_io as io
from _vegstress_shared_io import ek

SHORT = "vegstress_labels"
RECORD_COLS = ["record_id", "source", "date", "code", "lease_id"]


def hm_check(L: dict) -> dict:
    a, n = L["hm_auc"], L["min_per_class"]
    se = io.hanley_mcneil_se(a, n, n)
    return {"auc": a, "n_per_class": n, "se": se, "lower_95": a - 1.959964 * se,
            "passes_floor_0p5": bool(a - 1.959964 * se > 0.5), "min_n_per_class_for_floor": io.min_n_per_class(a),
            "note": "Simple random sampling. Lease clustering widens this. Count independent leases too"}


def records_gdf(path: Path):
    import geopandas as gpd
    r = pd.read_csv(io.need(path, "DEP complaint and inspection records", "see config inputs.records._schema"),
                    parse_dates=["date"])
    miss = [c for c in RECORD_COLS if c not in r.columns]
    if miss:
        raise KeyError(f"records {path}: missing columns {miss}")
    ek.assert_unique(r, "record_id")
    if {"x", "y"} <= set(r.columns) and r[["x", "y"]].notna().all().all():
        g = gpd.GeoDataFrame(r, geometry=gpd.points_from_xy(r.x, r.y), crs=6346)
    elif {"lat", "lon"} <= set(r.columns):
        g = gpd.GeoDataFrame(r, geometry=gpd.points_from_xy(r.lon, r.lat), crs=4326).to_crs(6346)
    else:
        raise KeyError("records need x, y (EPSG:6346) or lat, lon (EPSG:4326)")
    return g


def pad_age(pads, wells_path: Path, layer, radius: float, year_now: int = 2026) -> pd.DataFrame:
    import geopandas as gpd
    if wells_path is None or not Path(wells_path).exists():
        return pd.DataFrame({"pad_id": pads["pad_id"], "pad_age_yr": np.nan, "age_stratum": "no_record"})
    w = gpd.read_file(wells_path, layer=layer, columns=["PERMIT_NUM", "SPUD_DATE"])
    ek.assert_crs(w, "EPSG:6346")
    j = gpd.sjoin_nearest(pads[["pad_id", "geometry"]], w, max_distance=radius, how="left", distance_col="d_m")
    j = j.sort_values("d_m").drop_duplicates("pad_id")
    yr = pd.to_datetime(j["SPUD_DATE"], errors="coerce").dt.year
    strat = np.where(yr.isna(), "no_record", np.where(yr <= 1800, "unknown_date_1800", "dated"))
    age = np.where(strat == "dated", year_now - yr, np.nan)
    return pd.DataFrame({"pad_id": j["pad_id"].to_numpy(), "pad_age_yr": age, "age_stratum": strat,
                         "permit_num": j["PERMIT_NUM"].to_numpy()})


def run(cfg: dict, out_root: Path | None = None, records_path: Path | None = None, hm_only: bool = False) -> dict:
    import geopandas as gpd
    L = cfg["labels"]
    hm = hm_check(L)
    run_dir = ek.new_run(io.EXP, SHORT, {"labels": L, "hm_only": hm_only}, base=out_root, why="V0 label gate.")
    summary = {"stage": "V0", "hanley_mcneil": hm}
    outs = []
    if hm_only:
        summary.update(verdict="not_run", reason="--hm-only. Records not read")
    else:
        inp = cfg["inputs"]
        pin = inp["pads"]
        pp = io.resolve(pin)
        pads = io.read_polys(pp, pin.get("layer"), pin["id_col"], "pad polygons").rename(columns={pin["id_col"]: "pad_id"})
        rp = Path(records_path) if records_path else io.resolve(inp["records"])
        rec = records_gdf(rp)
        rec = rec[(rec["date"].dt.year >= L["years"][0]) & (rec["date"].dt.year <= L["years"][1])]
        j = gpd.sjoin_nearest(rec, pads[["pad_id", "geometry"]], max_distance=L["radius_m"], how="inner",
                              distance_col="dist_m")
        j = j.sort_values("dist_m").drop_duplicates("record_id")   # one record, one pad
        ek.assert_unique(j, "record_id")
        code = j["code"].astype(str).str.upper()
        j["is_leak"] = code.isin([c.upper() for c in L["leak_codes"]])
        j["is_clean"] = code.isin([c.upper() for c in L["clean_codes"]]) & j["source"].isin(["inspection"] + L["strong_sources"])
        j["is_strong"] = j["source"].isin(L["strong_sources"])
        g = j.groupby("pad_id")
        per = pd.DataFrame({"n_records": g.size(), "any_leak": g["is_leak"].any(), "any_clean": g["is_clean"].any(),
                            "strong_leak": g.apply(lambda d: bool((d.is_leak & d.is_strong).any()), include_groups=False),
                            "strong_any": g["is_strong"].any(),
                            "lease_id": g["lease_id"].agg(lambda v: v.dropna().astype(str).mode().iloc[0] if v.notna().any() else None),
                            "first_date": g["date"].min(), "coord_precision_m": g["coord_precision_m"].max()
                            if "coord_precision_m" in j.columns else np.nan}).reset_index()
        per["label"] = np.where(per.any_leak, "leak", np.where(per.any_clean, "nonleak", "unlabelled"))
        per["strength"] = np.where(per.label == "leak", np.where(per.strong_leak, "strong", "weak"),
                                   np.where(per.label == "nonleak", np.where(per.strong_any, "strong", "weak"), ""))
        per["lease_id"] = per["lease_id"].fillna("pad_" + per["pad_id"].astype(str))
        wp = io.resolve(inp["dep_wells"])
        age = pad_age(pads, wp, inp["dep_wells"].get("layer"), L["radius_m"])
        per = per.merge(age, on="pad_id", how="left")
        counts = {}
        for lab in ("leak", "nonleak"):
            d = per[per.label == lab]
            counts[lab] = {"n": int(len(d)), "n_strong": int((d.strength == "strong").sum()),
                           "n_weak": int((d.strength == "weak").sum()), "n_leases": int(d["lease_id"].nunique())}
        nmin = min(counts["leak"]["n"], counts["nonleak"]["n"])
        lmin = min(counts["leak"]["n_leases"], counts["nonleak"]["n_leases"])
        if nmin >= L["min_per_class"] and lmin >= L["min_leases_per_class"]:
            v = "success"
        elif nmin < L["fail_below_per_class"]:
            v = "failure"
        else:
            v = "inconclusive"
        summary.update(n_records_in_window=int(len(rec)), n_records_joined=int(len(j)), counts=counts, verdict=v,
                       action={"success": "Question B may run (V4)",
                               "failure": "Question B CLOSED by pre-specification. Question A continues",
                               "inconclusive": "Question B on hold. Seek more labels"}[v],
                       note="Complaint labels are weak. Strong labels reported alone as sensitivity")
        out_c = run_dir / "vegstress_label_audit_9t.csv"
        per.to_csv(out_c, index=False)
        outs.append(out_c)
    out_j = run_dir / "vegstress_label_counts_9t.json"
    out_j.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    outs.append(out_j)
    return io.finish(run_dir, summary, outputs=outs, params=L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--records", type=Path, default=None)
    ap.add_argument("--hm-only", action="store_true")
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.out_root, a.records, a.hm_only), indent=1, default=str))


if __name__ == "__main__":
    main()
