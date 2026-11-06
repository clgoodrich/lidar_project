"""Registry loader (3.5). OK RBDMS, OK orphan list and KS KGS wells normalised to one schema, per window.

Purpose
    Load the held Oklahoma and Kansas registries, normalise to the shared well schema
    (_geo_transfer_core.WELL_COLS), clip to each 25 km2 window and count status classes.
    Coordinate method comes from the source (KS LONGITUDE_LATITUDE_SOURCE, OK quarter calls or footage).
    Records are level (b) only. They are handed to 5.6 (S11) and never shown to annotators.
    Active wells give a pad-level positive control in 5.6. Pit-level association is not validated.
Inputs (held)
    data/_source/reference/wells_ok_occ/RBDMS_WELLS.zip, orphan-well-list.xlsx
    data/_source/reference/wells_ks_kgs/ks_kgs_oil_gas_wells.csv.gz
Outputs
    expansions/3_geography/3_5_oklahoma_kansas/data/interim/okks_wells_norm_windows.gpkg
    expansions/3_geography/3_5_oklahoma_kansas/results/tables/okks_wells_status_by_window.csv
Run
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_registry_wells.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.5"
# From rbdms-wells-data-dictionary.xlsx tab Well_Status_Ref_Codes (held, read 2026-11-05).
OK_STATUS = {"AC": "active", "ACRT": "active", "DUC": "drilled_uncompleted", "EX": "permit_expired",
             "ND": "new_drill", "NE": "no_evidence_at_location", "OR": "orphan", "PA": "plugged",
             "PAFF": "plugged", "PASF": "plugged", "PASUR": "plugged", "PASURSF": "plugged",
             "SFAW": "state_funds_award"}
KS_STATUS = {"OIL": "active", "GAS": "active", "EOR": "active", "SWD": "active", "D&A": "plugged",
             "OIL-P&A": "plugged", "GAS-P&A": "plugged", "EOR-P&A": "plugged", "SWD-P&A": "plugged",
             "OTHER-P&A": "plugged", "LOC": "permit_only", "OTHER": "other"}


def ok_coord_method(df: pd.DataFrame) -> pd.Series:
    """OK RBDMS has no method field. Footage calls are finer than quarter calls. Label which is present."""
    foot = pd.to_numeric(df.get("FOOTAGE_EW"), errors="coerce").fillna(0) + \
        pd.to_numeric(df.get("FOOTAGE_NS"), errors="coerce").fillna(0)
    q = df[[c for c in ("QTR4", "QTR3", "QTR2", "QTR1") if c in df]].notna().sum(axis=1)
    return pd.Series(np.where(foot > 0, "footage", np.where(q > 0, "quarter_calls_" + q.astype(str), "unknown")),
                     index=df.index)


def load_ok_rbdms(bbox_ll: tuple | None = None):
    import pyogrio
    z = gt.require_input(ek.path_for("reference") / "wells_ok_occ" / "RBDMS_WELLS.zip", "OK RBDMS wells")
    df = pyogrio.read_dataframe(f"zip://{z}!RBDMS_WELLS.shp", bbox=bbox_ll, read_geometry=False)
    df["coord_method"] = ok_coord_method(df)
    return gt.normalise_registry(df, {"well_id": "API", "county": "COUNTY", "status_raw": "WELLSTATUS",
                                      "well_type": "WELLTYPE", "lat": "SH_LAT", "lon": "SH_LON",
                                      "coord_method": "coord_method"}, "ok_occ_rbdms", OK_STATUS,
                                 lonlat_crs="EPSG:4326")


def load_ok_orphans():
    x = gt.require_input(ek.path_for("reference") / "wells_ok_occ" / "orphan-well-list.xlsx", "OK orphan list")
    df = pd.read_excel(x)
    df["coord_method"] = ok_coord_method(df.rename(columns={"FootageEW": "FOOTAGE_EW", "FootageNS": "FOOTAGE_NS",
                                                           "QuarterQuarterQuarterQuarter": "QTR4",
                                                           "QuarterQuarterQuarter": "QTR3",
                                                           "QuarterQuarter": "QTR2", "Quarter": "QTR1"}))
    return gt.normalise_registry(df, {"well_id": "API", "county": "CountyName", "status_raw": "WellStatus",
                                      "well_type": "WellType", "lat": "Y", "lon": "X",
                                      "coord_method": "coord_method"}, "ok_occ_orphan", OK_STATUS,
                                 lonlat_crs="EPSG:4326")


def load_ks_kgs(bbox_ll: tuple | None = None):
    p = gt.require_input(ek.path_for("reference") / "wells_ks_kgs" / "ks_kgs_oil_gas_wells.csv.gz", "KS KGS wells")
    cols = ["KID", "API_NUMBER", "COUNTY", "STATUS", "WELL_CLASS", "lon", "lat", "LONGITUDE_LATITUDE_SOURCE",
            "SPUD_DATE_TXT", "PLUG_DATE_TXT"]
    df = pd.read_csv(p, usecols=cols, low_memory=False)
    if bbox_ll:
        x0, y0, x1, y1 = bbox_ll
        df = df[df.lon.between(x0, x1) & df.lat.between(y0, y1)].reset_index(drop=True)
    return gt.normalise_registry(df, {"well_id": "KID", "county": "COUNTY", "status_raw": "STATUS",
                                      "well_type": "WELL_CLASS", "lat": "lat", "lon": "lon",
                                      "coord_method": "LONGITUDE_LATITUDE_SOURCE", "spud_date": "SPUD_DATE_TXT",
                                      "plug_date": "PLUG_DATE_TXT"}, "ks_kgs", KS_STATUS, lonlat_crs="EPSG:4326")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--areas", default="", help="comma list (default all areas in config)")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    import geopandas as gpd
    areas = a.areas.split(",") if a.areas else list(cfg["areas"])
    parts, rows = [], []
    try:
        orphans = load_ok_orphans()
        for area in areas:
            ac = cfg["areas"][area]
            w = gpd.GeoSeries([gt.window_box(*ac["centre_lonlat"], ac["crs"])], crs=ac["crs"]).to_crs(4326).iloc[0]
            srcs = [load_ks_kgs(w.bounds)] if area.startswith("ks_") else [load_ok_rbdms(w.bounds), orphans]
            for g in srcs:
                sub = g[g.within(w)].copy()
                sub["area"] = area
                parts.append(sub)
                for (st, cm), n in sub.groupby(["status_norm", "coord_method"], dropna=False).size().items():
                    rows.append({"area": area, "source": g["source"].iloc[0] if len(g) else "", "status_norm": st,
                                 "coord_method": cm, "n": int(n)})
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    allw = pd.concat(parts, ignore_index=True)
    allw["evidence_level"] = "(b) administrative"
    out = ek.sub(EXP, "data/interim") / "okks_wells_norm_windows.gpkg"
    gpd.GeoDataFrame(allw, geometry="geometry", crs="EPSG:4326").to_file(out, driver="GPKG")
    tab = pd.DataFrame(rows)
    tp = ek.sub(EXP, "results/tables") / "okks_wells_status_by_window.csv"
    tab.to_csv(tp, index=False)
    print(tab.pivot_table(index="area", columns="status_norm", values="n", aggfunc="sum", fill_value=0).to_string())
    print(f"wrote {out}\nwrote {tp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
