"""S0 of framework 4.6. Turn the source search log into a coverage table with a verdict per source.

Purpose. The search itself is manual (Library of Congress, David Rumsey, Penn State, USGS Library, state archives).
This script prints the 9t corner in lon/lat for those searches, then reads the search log, measures how much of 9t
each record covers and writes the table. Verdict is "candidate" (covers at least min_coverage_share of 9t),
"no coverage" (covers none) or "unknown" (bounds missing or partial cover below the share).
Inputs.
  expansions/4_modalities/4_6_historic_maps_aerials/data/raw/hist_sources_9t.csv (assumed, schema in config_4_6.json)
Outputs.
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_source_search_9t.csv
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_source_search_9t.md
  (copy the .md to docs/iterations/historic_source_search_9t.md when the lead logs the pass)
Run.
  python expansions/4_modalities/4_6_historic_maps_aerials/src/_hist_source_search_9t.py [--bbox-only] [--sources CSV] [--out DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd

import _hist_kit_4_6 as hk

KINDS = {"topo", "oil_region_map", "atlas", "aerial", "state_map"}


def verdicts(df: pd.DataFrame, box_ll, min_share: float) -> pd.DataFrame:
    df = df.copy()
    shares, verdict = [], []
    for _, r in df.iterrows():
        b = [r.get(k) for k in ("west", "south", "east", "north")]
        if any(pd.isna(v) for v in b):
            shares.append(float("nan"))
            verdict.append("unknown")
            continue
        s = hk.cover_share(*map(float, b), box_ll)
        shares.append(round(s, 4))
        verdict.append("no coverage" if s == 0 else "candidate" if s >= min_share else "unknown")
    df["cover_share_9t"] = shares
    df["verdict"] = verdict
    return df


def to_markdown(df: pd.DataFrame, box_ll) -> str:
    cols = ["source_id", "kind", "date", "scale", "archive", "cover_share_9t", "scan_dpi", "rights", "verdict"]
    lines = ["# Historic source search, tile 9t", "",
             f"Written {dt.date.today()} by `_hist_source_search_9t.py`. Search box (EPSG:4326) "
             f"W {box_ll[0]:.5f} S {box_ll[1]:.5f} E {box_ll[2]:.5f} N {box_ll[3]:.5f}.",
             "A catalogue record is not a usable scan. Candidate means coverage only.", "",
             "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(r.get(c)) else str(r.get(c)) for c in cols) + " |")
    dates = sorted(set(df.get("searched_on", pd.Series(dtype=str)).dropna().astype(str)))
    lines += ["", f"Dates searched. {', '.join(dates) if dates else 'not recorded'}.",
              f"Counts. {df.verdict.value_counts().to_dict()}."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    cfg = hk.load_cfg()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sources", default=None, help="search log CSV (default from config)")
    ap.add_argument("--out", default=None, help="output folder (default results/tables)")
    ap.add_argument("--bbox-only", action="store_true", help="print the lon/lat search box and stop")
    a = ap.parse_args(argv)
    box_ll = hk.bbox_lonlat(cfg["bbox_9t"], cfg["crs"])
    print(f"9t search box lon/lat W {box_ll[0]:.5f} S {box_ll[1]:.5f} E {box_ll[2]:.5f} N {box_ll[3]:.5f}")
    if a.bbox_only:
        return 0
    spec = cfg["inputs"]["source_list"]
    src = hk.need(Path(a.sources) if a.sources else hk.resolve(spec), "source search log", spec)
    df = pd.read_csv(src)
    missing = [c for c in spec["schema"] if c not in df.columns]
    if missing:
        raise ValueError(f"{src} lacks columns {missing}")
    bad = set(df.kind.dropna()) - KINDS
    if bad:
        raise ValueError(f"unknown kind values {bad}; allowed {sorted(KINDS)}")
    hk.ek.assert_unique(df, "source_id")
    out_df = verdicts(df, box_ll, cfg["prereg"]["min_coverage_share"])
    hk.ek.assert_rows(out_df, len(df), "verdict table")
    out = Path(a.out) if a.out else hk.resolve(cfg["outputs"]["tables"])
    out.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out / "hist_source_search_9t.csv", index=False)
    (out / "hist_source_search_9t.md").write_text(to_markdown(out_df, box_ll), encoding="utf-8")
    hk.prov(out, "hist_source_search_9t", inputs=[src], outputs=[out / "hist_source_search_9t.csv"],
                           params={"min_coverage_share": cfg["prereg"]["min_coverage_share"]})
    print(out / "hist_source_search_9t.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
