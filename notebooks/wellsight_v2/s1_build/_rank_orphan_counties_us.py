"""Rank US counties by documented orphan wells using the USGS 2026 release, with the 2022 count beside it.

Inputs  data/_source/reference/wells_us_orphan_2026/US_orphaned_wells_2026.csv
        data/_source/reference/wells_us_orphan_2022/area_orphan_counts_by_county_us.csv (for the 2022 column)
        data/_source/reference/census_boundaries/cb_2023_us_county_5m.zip
Output  data/_source/reference/wells_us_orphan_2026/area_orphan_counts_by_county_us.csv
Run     python notebooks/wellsight_v2/s1_build/_rank_orphan_counties_us.py
Notes   Counts come from the state and county names in the database. Area and bounding box come from the Census county polygon matched
        by normalised name. Rows that do not match a Census county are listed on screen and kept out of the ranking.
        The 2026 release differs from 2022 (Illinois down 4,494, Venango down 418). Cause not known (status definitions or de-duplication).
"""
from __future__ import annotations

import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
REF = ROOT / "data/_source/reference"
W26 = REF / "wells_us_orphan_2026/US_orphaned_wells_2026.csv"
R22 = REF / "wells_us_orphan_2022/area_orphan_counts_by_county_us.csv"
CEN = REF / "census_boundaries/cb_2023_us_county_5m.zip"
OUT = REF / "wells_us_orphan_2026/area_orphan_counts_by_county_us.csv"


def norm(s):
    return re.sub(r"\b(county|parish|borough|census area|city and borough|municipality)\b", "", str(s).lower()).replace(".", "").replace("'", "").replace("-", " ").strip()


def main():
    w = pd.read_csv(W26, low_memory=False)
    w["state"] = w.state.str.strip().str.title()
    w["ck"] = w.state + "|" + w.county.map(norm)
    cnt = w.groupby("ck").size().rename("orphans").reset_index()
    cen = gpd.read_file(f"zip://{CEN}")
    cen["ck"] = cen.STATE_NAME.str.title() + "|" + cen.NAME.map(norm)
    cen = cen.drop_duplicates("ck")
    g5070 = cen.to_crs(5070)
    cen["km2"] = g5070.area / 1e6
    b = cen.to_crs(4326).geometry.bounds
    cen[["minx", "miny", "maxx", "maxy"]] = b[["minx", "miny", "maxx", "maxy"]]
    m = cnt.merge(cen[["ck", "STATE_NAME", "NAME", "km2", "minx", "miny", "maxx", "maxy"]], on="ck", how="left")
    miss = m[m.km2.isna()]
    print("unmatched names", len(miss), "wells", int(miss.orphans.sum()), "of", len(w))
    print(miss.sort_values("orphans", ascending=False).head(10).to_string(index=False))
    m = m.dropna(subset=["km2"])
    m["state"], m["county"] = m.STATE_NAME, m.NAME
    m["per_km2"] = m.orphans / m.km2
    old = pd.read_csv(R22)[["state", "county", "orphans"]].rename(columns={"orphans": "orphans_2022"})
    old["ck"] = old.state.str.title() + "|" + old.county.map(norm)
    m = m.merge(old[["ck", "orphans_2022"]], on="ck", how="left")
    m["orphans_2022"] = m.orphans_2022.fillna(0).astype(int)
    m["diff"] = m.orphans - m.orphans_2022
    m = m.sort_values("orphans", ascending=False)
    m[["state", "county", "orphans", "km2", "per_km2", "minx", "miny", "maxx", "maxy", "orphans_2022", "diff"]].to_csv(OUT, index=False)
    print(len(m), "counties ->", OUT)
    print(m[["state", "county", "orphans", "orphans_2022", "diff", "per_km2"]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
