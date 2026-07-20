"""Tag venango_wells_all with reporting-provenance flags (bounty-era proxy).

The public DEP export has no "reported via bounty / date-entered" field, so
bounty-reported wells cannot be isolated directly. This builds the best
available proxies by (a) status class and (b) a temporal diff against the
older DEP orphan snapshot:

  NEW: data/derivatives/venango_wells_all.gpkg
       (from OilGasLocations_ConventionalUnconventional 2026-04, 20,108 wells)
  OLD: data/external/legacy_data/US_Documented_Orphan_Wells.csv
       (DEP orphan list, Data file date 2022-05-09, 4,786 Venango orphans)

Both key on (county_id, permit_int):
  OLD Well_ident "API:37121000860000" -> county 121, permit 86
  NEW PERMIT_NUM "121-27187"          -> county 121, permit 27187
All 4,786 OLD keys resolve into NEW (parse verified).

Flags written:
  provenance            operator_permitted | dep_found
                        (dep_found = WELL_STATU in the DEP-catalogued legacy
                        set: DEP Orphan/Abandoned List, Abandoned,
                        Cannot Be Located, Plugged Unverified)
  in_2022_orphan_list   key present in the 2022-05-09 orphan snapshot
  newly_documented      dep_found AND not in 2022 list -> entered the
                        abandoned/orphan inventory 2022-05 .. 2026-04.
                        **This is the bounty-era proxy** (the June-2025 bounty
                        falls inside this window). CAVEAT: 4-year window, not
                        1-year; also catches wells reclassified from
                        active/plugged, not only newly field-located ones.
  fed_plugging_program  SITE_NAME matches IIJA/MERP/GRANT/PLUG CONTRACT
  prov_class            combined category for styling

Outputs:
  data/derivatives/experiments/well_provenance/well_provenance.gpkg
      layer 'wells' (styled: categorized by prov_class)
  data/derivatives/experiments/well_provenance/summary.json

Reproduce: python notebooks/wellsight_v2/analysis/_well_provenance_flags.py
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _export_well_age_qgis import embed_styles, qml_categorized  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
NEW = ROOT / "data/derivatives/venango_wells_all.gpkg"
OLD = ROOT / "data/external/legacy_data/US_Documented_Orphan_Wells.csv"
OUT_DIR = ROOT / "data/derivatives/experiments/well_provenance"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "well_provenance.gpkg"

DEP_FOUND = {"DEP Orphan List", "DEP Abandoned List", "Abandoned",
             "Cannot Be Located", "Plugged Unverified"}
FED_RE = r"IIJA|MERP|MReP|GRANT CONTRACT|PLUG CONTRACT"


def old_key(s):
    s = str(s).replace("API:", "")
    if len(s) < 10:
        return None
    try:
        return f"{int(s[2:5])}-{int(s[5:10])}"
    except ValueError:
        return None


def new_key(s):
    try:
        c, p = str(s).split("-")
        return f"{int(c)}-{int(p)}"
    except (ValueError, AttributeError):
        return None


def prov_class(row):
    if row["newly_documented"]:
        return "newly documented 2022-2026 (bounty-era proxy)"
    if row["dep_found"]:
        return "DEP-found, pre-2022"
    return "operator-permitted"


def main():
    old = pd.read_csv(OLD, low_memory=False)
    old_keys = set(old["Well_ident"].map(old_key).dropna())
    old_date = old["Data file date"].dropna().iloc[0]
    print(f"OLD orphan snapshot {old_date}: {len(old_keys)} keys")

    g = gpd.read_file(NEW)
    g["key"] = g["PERMIT_NUM"].map(new_key)
    matched = int(g["key"].isin(old_keys).sum())
    print(f"NEW export: {len(g)} wells; {matched} match the 2022 list "
          f"(all {len(old_keys)} old keys should resolve)")

    g["dep_found"] = g["WELL_STATU"].isin(DEP_FOUND)
    g["in_2022_orphan_list"] = g["key"].isin(old_keys)
    g["newly_documented"] = g["dep_found"] & ~g["in_2022_orphan_list"]
    g["fed_plugging_program"] = g["SITE_NAME"].str.contains(
        FED_RE, case=False, na=False)
    g["provenance"] = g["dep_found"].map(
        {True: "dep_found", False: "operator_permitted"})
    g["prov_class"] = g.apply(prov_class, axis=1)

    summary = {
        "new_export": "OilGasLocations 2026-04",
        "old_snapshot_date": str(old_date),
        "n_total": len(g),
        "n_operator_permitted": int((~g["dep_found"]).sum()),
        "n_dep_found": int(g["dep_found"].sum()),
        "n_in_2022_orphan_list": int(g["in_2022_orphan_list"].sum()),
        "n_newly_documented": int(g["newly_documented"].sum()),
        "newly_documented_by_status":
            g.loc[g["newly_documented"], "WELL_STATU"].value_counts().to_dict(),
        "n_fed_plugging_program": int(g["fed_plugging_program"].sum()),
        "caveat": ("newly_documented is the bounty-era proxy; window is "
                   "2022-05 .. 2026-04 (4 yr, not bounty-only) and includes "
                   "status reclassifications, not just new field locations."),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    keep = ["PERMIT_NUM", "WELL_NAME", "WELL_STATU", "SPUD_DATE",
            "DATE_PLUGG", "SITE_NAME", "provenance", "in_2022_orphan_list",
            "newly_documented", "fed_plugging_program", "prov_class",
            "geometry"]
    keep = [c for c in keep if c in g.columns]
    if OUT.exists():
        OUT.unlink()
    g[keep].to_file(OUT, layer="wells", driver="GPKG")

    cats = [
        ("newly documented 2022-2026 (bounty-era proxy)",
         f"newly documented 2022-2026 ({summary['n_newly_documented']})",
         "227,26,28"),
        ("DEP-found, pre-2022",
         f"DEP-found, pre-2022 ({summary['n_dep_found'] - summary['n_newly_documented']})",
         "255,127,0"),
        ("operator-permitted",
         f"operator-permitted ({summary['n_operator_permitted']})",
         "140,150,170")]
    embed_styles(str(OUT), [("wells", "geom",
                             qml_categorized("point", "prov_class", cats))])
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
