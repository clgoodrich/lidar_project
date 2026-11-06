"""S1 (3.4). East Texas window rule and window boxes for T1, T2, adaptation and C0.

Purpose
    Apply the preregistered rule. Among East Texas candidate counties with usable lidar
    (QL2 or better, flown 2015 or later) and at least 15 eligible km2, pick the highest
    documented-orphan density. Ties go to the newer acquisition. If no county passes,
    East Texas is reported unscored. Then write one 25 km2 box per area in its own UTM CRS.
    The rule is fixed before any picture of candidate windows is viewed.
Inputs
    data/_source/reference/wells_us_orphan_2026/area_orphan_counts_by_county_us.csv   (held)
    config_3_4.json inputs.east_tx_lidar_listing (assumed, paged listing per county)
Outputs
    expansions/3_geography/3_4_gulf_texas/results/tables/gulf_east_tx_county_rank.csv
    expansions/3_geography/3_4_gulf_texas/data/interim/gulf_window_boxes.gpkg
Run
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_window_choice_tx.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.4"
QL_OK = {"QL0", "QL1", "QL2"}


def rank_counties(counts: pd.DataFrame, listing: pd.DataFrame | None, min_km2: float = 15.0,
                  min_year: int = 2015) -> pd.DataFrame:
    """Gate on usable lidar and eligible area, then lexicographic: density desc, flight year desc."""
    c = counts.copy()
    if listing is None or listing.empty:
        c["usable_lidar"] = False
        c["eligible_km2"] = float("nan")
        c["flight_year"] = float("nan")
        c["note"] = "no paged listing yet (VERIFY)"
    else:
        best = (listing.assign(ok=listing["ql"].isin(QL_OK) & (listing["flight_year"] >= min_year))
                .sort_values(["ok", "flight_year"], ascending=False).drop_duplicates("county"))
        c = c.merge(best[["county", "project", "ql", "flight_year", "eligible_km2", "ok"]], on="county", how="left")
        c["usable_lidar"] = c["ok"].fillna(False).astype(bool) & (c["eligible_km2"] >= min_km2)
        c["note"] = ""
    c["passes_gate"] = c["usable_lidar"]
    return gt.lexicographic_rank(c, [("passes_gate", True), ("per_km2", True), ("flight_year", True)])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-km2", type=float, default=15.0)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    counts_p = ek.path_for("reference") / "wells_us_orphan_2026" / "area_orphan_counts_by_county_us.csv"
    counts = pd.read_csv(gt.require_input(counts_p, "USGS county orphan counts"))
    tx = counts[(counts["state"] == "Texas") & counts["county"].isin(cfg["east_tx_candidates"])]
    missing = sorted(set(cfg["east_tx_candidates"]) - set(tx["county"]))
    for m in missing:   # counties with no orphan rows still appear, with zero density
        tx = pd.concat([tx, pd.DataFrame([{"state": "Texas", "county": m, "orphans": 0, "per_km2": 0.0}])])
    try:
        listing = pd.read_csv(gt.config_input(cfg, "east_tx_lidar_listing", EXP))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        listing = None
    ranked = rank_counties(tx, listing, a.min_km2)
    tables = ek.sub(EXP, "results/tables")
    ranked.to_csv(tables / "gulf_east_tx_county_rank.csv", index=False)
    print(ranked[["rank", "county", "orphans", "per_km2", "passes_gate", "note"]].to_string(index=False))
    chosen = ranked[ranked["passes_gate"]].head(1)
    if chosen.empty:
        print("No East Texas county passes the rule. T2 is unscored. Report that East Texas is unscored.")
    import geopandas as gpd
    rows = []
    for area, ac in cfg["areas"].items():
        if ac["centre_lonlat"] is None:
            continue
        lon, lat = ac["centre_lonlat"]
        if gt.utm_epsg_nad83_2011(lon) != int(ac["crs"].split(":")[1]):
            raise AssertionError(f"{area} CRS {ac['crs']} is not the UTM zone of lon {lon}")
        box = gt.window_box(lon, lat, ac["crs"], ac.get("side_km", 5.0))
        rows.append(gpd.GeoDataFrame({"area": [area], "role": [ac["role"]], "crs": [ac["crs"]]},
                                     geometry=[box], crs=ac["crs"]).to_crs("EPSG:4326"))
    out = ek.sub(EXP, "data/interim") / "gulf_window_boxes.gpkg"
    pd.concat(rows).to_file(out, driver="GPKG")
    print(f"wrote {tables / 'gulf_east_tx_county_rank.csv'}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
