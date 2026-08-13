"""Tag DEP wells with reporting-provenance flags (bounty-era proxy where possible).

The public DEP export has no "reported via bounty / date-entered" field, so
bounty-reported wells cannot be isolated directly. This builds the best
available proxies by (a) status class and (b) — only where a dated older
snapshot exists — a temporal diff.

Regions:
  venango  NEW venango_wells_all.gpkg (DEP 2026-04, pre-clipped, 20,108)
           OLD US_Documented_Orphan_Wells.csv (2022-05-09, 4,786 Venango
           orphans) -> temporal diff AVAILABLE.
  mckean   NEW clipped live from the statewide 2026-04 export (COUNTY_ID 42,
           ~38,110). OLD baseline NOT on disk (the 2022 file is Venango-only)
           -> temporal diff NOT available; status-based flags only.

Both key on (county_id, permit_int):
  OLD Well_ident "API:37121000860000" -> county 121, permit 86
  NEW PERMIT_NUM "121-27187"          -> county 121, permit 27187

Flags per region:
  provenance            operator_permitted | dep_found (WELL_STATU in the
                        DEP-catalogued legacy set)
  fed_plugging_program  SITE_NAME matches IIJA/MERP/GRANT/PLUG CONTRACT
  in_2022_orphan_list / newly_documented / prov_class
                        only populated where a temporal baseline exists;
                        otherwise prov_class collapses to dep_found vs operator.

Outputs (per region, under data/derivatives/experiments/well_provenance/):
  well_provenance_<region>.gpkg  layer 'wells' (styled by prov_class)
  summary_<region>.json

Reproduce: python notebooks/wellsight_v2/s7_analysis/_well_provenance_flags.py
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).parent))
from _export_well_age_qgis import embed_styles, qml_categorized  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DERIV = path_for("derivatives")
STATEWIDE = (path_for("reference") / "OilGasLocations_ConventionalUnconventional2026_04" / "OilGasLocations_ConventionalUnconventional2026_04.shp")
OLD_VENANGO = path_for("reference") / "legacy_data" / "US_Documented_Orphan_Wells.csv"
OUT_DIR = path_for("experiments") / "well_provenance"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:6346"

DEP_FOUND = {"DEP Orphan List", "DEP Abandoned List", "Abandoned",
             "Cannot Be Located", "Plugged Unverified"}
FED_RE = r"IIJA|MERP|MReP|GRANT CONTRACT|PLUG CONTRACT"

REGIONS = {
    "venango": {
        "new_gpkg": path_for("dep_wells") / "venango_wells_all.gpkg",
        "county_id": 121,
        "old_csv": OLD_VENANGO,
        "block": box(619311, 4592854, 624172, 4597660),  # 9t
        "block_name": "9t",
    },
    "mckean": {
        "new_gpkg": None,          # clip live from statewide
        "county_id": 42,
        "old_csv": None,           # no 2022 McKean baseline on disk
        "block": box(696000, 4645000, 706000, 4655000),  # mkf_1m
        "block_name": "mkf",
    },
}


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


def load_new(cfg):
    if cfg["new_gpkg"] is not None:
        return gpd.read_file(cfg["new_gpkg"]).to_crs(CRS)
    # clip live from the statewide export by county id
    g = gpd.read_file(STATEWIDE, where=f"COUNTY_ID = {cfg['county_id']}")
    return g.to_crs(CRS)


def process(region, cfg):
    g = load_new(cfg)
    g["key"] = g["PERMIT_NUM"].map(new_key)
    g["dep_found"] = g["WELL_STATU"].isin(DEP_FOUND)
    g["fed_plugging_program"] = g["SITE_NAME"].str.contains(
        FED_RE, case=False, na=False)
    g["provenance"] = g["dep_found"].map(
        {True: "dep_found", False: "operator_permitted"})

    has_baseline = cfg["old_csv"] is not None
    old_date = None
    if has_baseline:
        old = pd.read_csv(cfg["old_csv"], low_memory=False)
        old_keys = set(old["Well_ident"].map(old_key).dropna())
        old_date = str(old["Data file date"].dropna().iloc[0])
        g["in_2022_orphan_list"] = g["key"].isin(old_keys)
        g["newly_documented"] = g["dep_found"] & ~g["in_2022_orphan_list"]

        def pc(r):
            if r["newly_documented"]:
                return "newly documented since baseline (bounty-era proxy)"
            if r["dep_found"]:
                return "DEP-found, in baseline"
            return "operator-permitted"
        g["prov_class"] = g.apply(pc, axis=1)
    else:
        g["in_2022_orphan_list"] = pd.NA
        g["newly_documented"] = pd.NA
        g["prov_class"] = g["dep_found"].map(
            {True: "DEP-found (no temporal baseline)",
             False: "operator-permitted"})

    blk = cfg["block"]
    g["in_block"] = g.within(blk)
    g["near_block_2km"] = g.within(blk.buffer(2000))

    summary = {
        "region": region, "new_export": "OilGasLocations 2026-04",
        "old_snapshot_date": old_date, "temporal_diff": has_baseline,
        "n_total": len(g),
        "n_operator_permitted": int((~g["dep_found"]).sum()),
        "n_dep_found": int(g["dep_found"].sum()),
        "n_fed_plugging_program": int(g["fed_plugging_program"].sum()),
        "n_dep_found_in_block": int((g["dep_found"] & g["in_block"]).sum()),
        "n_dep_found_near_block_2km":
            int((g["dep_found"] & g["near_block_2km"]).sum()),
        "block": cfg["block_name"],
    }
    if has_baseline:
        summary["n_newly_documented"] = int(g["newly_documented"].sum())
        summary["n_newly_documented_in_block"] = int(
            (g["newly_documented"] == True).__and__(g["in_block"]).sum())  # noqa: E712
        summary["newly_documented_by_status"] = (
            g.loc[g["newly_documented"] == True, "WELL_STATU"]  # noqa: E712
            .value_counts().to_dict())
    else:
        summary["note"] = ("no 2022 McKean orphan baseline on disk (the "
                           "US_Documented file is Venango-only) -> bounty-era "
                           "temporal proxy not computable; status-based flags "
                           "only. Provide a dated McKean orphan snapshot to "
                           "enable the diff.")
    (OUT_DIR / f"summary_{region}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    keep = ["PERMIT_NUM", "WELL_NAME", "WELL_STATU", "SPUD_DATE",
            "DATE_PLUGG", "SITE_NAME", "provenance", "in_2022_orphan_list",
            "newly_documented", "fed_plugging_program", "prov_class",
            "in_block", "near_block_2km", "geometry"]
    keep = [c for c in keep if c in g.columns]
    out = OUT_DIR / f"well_provenance_{region}.gpkg"
    if out.exists():
        out.unlink()
    g[keep].to_file(out, layer="wells", driver="GPKG")

    if has_baseline:
        cats = [("newly documented since baseline (bounty-era proxy)",
                 f"newly documented ({summary['n_newly_documented']})",
                 "227,26,28"),
                ("DEP-found, in baseline",
                 f"DEP-found, pre-baseline "
                 f"({summary['n_dep_found'] - summary['n_newly_documented']})",
                 "255,127,0"),
                ("operator-permitted",
                 f"operator-permitted ({summary['n_operator_permitted']})",
                 "140,150,170")]
    else:
        cats = [("DEP-found (no temporal baseline)",
                 f"DEP-found ({summary['n_dep_found']})", "255,127,0"),
                ("operator-permitted",
                 f"operator-permitted ({summary['n_operator_permitted']})",
                 "140,150,170")]
    embed_styles(str(out), [("wells", "geom",
                             qml_categorized("point", "prov_class", cats))])
    print(f"wrote {out}\n")


def main():
    for region, cfg in REGIONS.items():
        print(f"=== {region} ===")
        process(region, cfg)


if __name__ == "__main__":
    main()
