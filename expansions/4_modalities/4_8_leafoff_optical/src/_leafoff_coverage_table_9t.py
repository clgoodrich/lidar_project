"""S0 of framework 4.8. Coverage and season table of optical programs over the study areas.

Purpose. Merge the programs already known from repo scripts (config sources) with the search log, flag each
program leaf-off, leaf-on or undated from its acquisition months, and measure its cover share of each study area
with a bbox on file. Coverage first, usefulness second. A program with no verified date is "undated" and cannot
supply usable chips until its date is checked.
Inputs.
  expansions/4_modalities/4_8_leafoff_optical/data/raw/leafoff_programs.csv (assumed search log, schema in config_4_8.json; optional)
  expansions/4_modalities/4_8_leafoff_optical/src/config_4_8.json (known sources)
Outputs.
  expansions/4_modalities/4_8_leafoff_optical/results/tables/leafoff_coverage_9t.csv
  expansions/4_modalities/4_8_leafoff_optical/results/tables/leafoff_coverage_9t.md   (copy to docs/iterations/leafoff_coverage_probe.md)
Run.
  python expansions/4_modalities/4_8_leafoff_optical/src/_leafoff_coverage_table_9t.py [--programs CSV] [--out DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import _leafoff_kit_4_8 as lk


def season(start, end, months) -> str:
    a, b = lk.is_leafoff(start, months), lk.is_leafoff(end if end else start, months)
    if a is None and b is None:
        return "undated"
    if a and (b is None or b):
        return "leaf-off"
    if a is False and b is False:
        return "leaf-on"
    return "mixed"


def cover(row, bbox_ll) -> float:
    if any(pd.isna(row.get(k)) for k in ("west", "south", "east", "north")):
        return float("nan")
    bw, bs, be, bn = bbox_ll
    iw, ie = max(row["west"], bw), min(row["east"], be)
    is_, in_ = max(row["south"], bs), min(row["north"], bn)
    return 0.0 if ie <= iw or in_ <= is_ else (ie - iw) * (in_ - is_) / ((be - bw) * (bn - bs))


def known_rows(cfg) -> list[dict]:
    rows = []
    for sid, s in cfg["sources"].items():
        if s["kind"] == "naip_stac":
            for y in s["years"]:
                rows.append({"program": "NAIP", "source_id": f"naip_{y[:4]}", "date_start": y, "date_end": y,
                             "access": "Planetary Computer STAC", "note": s["note"]})
        else:
            rows.append({"program": sid, "source_id": sid, "date_start": s.get("date"), "date_end": s.get("date"),
                         "gsd_m": s.get("gsd_m"), "access": s["kind"], "note": s.get("note")})
    return rows


def main(argv=None) -> int:
    from pyproj import Transformer
    cfg = lk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--programs", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    df = pd.DataFrame(known_rows(cfg))
    spec = cfg["inputs"]["programs"]
    pp = Path(a.programs) if a.programs else lk.resolve(spec)
    if pp.exists():
        log = pd.read_csv(pp)
        miss = [c for c in spec["schema"] if c not in log.columns]
        if miss:
            raise ValueError(f"{pp} lacks {miss}")
        df = pd.concat([df, log], ignore_index=True)
    else:
        print(f"note: no search log at {pp}. Table holds the known sources only")
    df = df.drop_duplicates("source_id", keep="last").reset_index(drop=True)
    lk.ek.assert_unique(df, "source_id")
    df["season"] = [season(r.date_start, r.date_end, pr["leafoff_months"]) for r in df.itertuples()]
    t = Transformer.from_crs(cfg["crs"], "EPSG:4326", always_xy=True)
    for area, bb in cfg["areas"].items():
        if area.startswith("_") or bb is None:
            continue
        (w, s), (e, n) = t.transform(bb[0], bb[1]), t.transform(bb[2], bb[3])
        df[f"cover_{area}"] = [cover(r, (w, s, e, n)) for r in df.to_dict("records")]
    out = Path(a.out) if a.out else lk.resolve(cfg["outputs"]["tables"])
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "leafoff_coverage_9t.csv", index=False)
    cols = [c for c in ["program", "source_id", "date_start", "season", "gsd_m", "access"] + [c for c in df if c.startswith("cover_")] if c in df]
    md = ["# Leaf-off coverage probe", "", f"Written {lk.today()} by `_leafoff_coverage_table_9t.py`. Leaf-off months {pr['leafoff_months']}.",
          "Undated programs cannot give usable chips until the flight date is verified.", "",
          "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df[cols].itertuples(index=False)]
    (out / "leafoff_coverage_9t.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    lk.prov(out, "leafoff_coverage_table_9t", inputs=[pp], outputs=[out / "leafoff_coverage_9t.csv"], params=pr)
    print(df[["source_id", "season"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
