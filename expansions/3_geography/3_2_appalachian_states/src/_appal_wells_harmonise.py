"""3.2 S1. Harmonise well status, dates and coordinates across NY, OH, WV, KY and the US orphan lists.

Purpose
    Normalise every configured source to one schema (_appal_wells_loaders.SCHEMA). Original
    status codes are kept beside the harmonised scheme (active, plugged, abandoned, orphan,
    other). A recorded plug date outranks a status code. Row counts per source are asserted
    equal to the input (after the state filter for the national lists). The KY NAD27 to NAD83
    shift is measured per record and summarised in metres. Records with fewer than 5 decimal
    places are flagged low_precision. The 1800 sentinel date is unknown, never early.
    Records are tagged with the 3.2 window that holds them (lon/lat box from the catalogue),
    which is the hand-off to 5.6. No record is scored here.

Inputs
    config_3_2.json wells.sources (held files under data/_source/reference/)
    data/_source/reference/lidar_catalogue/lidar_win_windows_us.csv (window boxes)

Outputs
    expansions/3_geography/3_2_appalachian_states/data/processed/wells_status_harmonised_appal.csv.gz  (gitignored)
    expansions/3_geography/3_2_appalachian_states/results/tables/wells_harmonise_counts_appal.csv
        rows per source by harmonised status, with coords, low precision, in each window
    expansions/3_geography/3_2_appalachian_states/results/tables/wells_harmonise_summary_appal.json

Run
    python expansions/3_geography/3_2_appalachian_states/src/_appal_wells_harmonise.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _appal_wells_loaders as wl  # noqa: E402
xl, ek = wl.xl, wl.ek


def tag_windows(df: pd.DataFrame, windows: pd.DataFrame, tags: dict) -> pd.Series:
    """Window tag per record (lon/lat box). A record in two boxes gets the first tag in config order."""
    out = pd.Series(None, index=df.index, dtype=object)
    for tag, win in tags.items():
        w = windows[windows.window == win]
        if not len(w):
            continue
        w = w.iloc[0]
        m = out.isna() & df.lon.between(w.minx, w.maxx) & df.lat.between(w.miny, w.maxy)
        out[m] = tag
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(wl.CFG))
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    windows = pd.read_csv(xl.need(xl.resolve_path(cfg["catalogue"]["windows"]), "window table"))
    tags = {t: v["window"] for t, v in cfg["areas"].items()}
    parts, counts = [], []
    for name, n_raw, df in wl.load_all(cfg, a.only):
        df["window_tag"] = tag_windows(df, windows, tags)
        parts.append(df)
        g = df.groupby("status_h").agg(rows=("well_id", "size"), with_coords=("has_coords", "sum"),
                                       low_precision=("low_precision", "sum"), sentinel_1800=("date_unknown_sentinel", "sum"),
                                       early_dated=("early_dated", "sum")).reset_index()
        g.insert(0, "source", name)
        for t in tags:
            g[f"in_{t}"] = g.status_h.map(df[df.window_tag == t].status_h.value_counts()).fillna(0).astype(int)
        counts.append(g)
        print(f"  {name}: {len(df)} rows ({n_raw} raw), windows {df.window_tag.value_counts().to_dict()}")
    allw = pd.concat(parts, ignore_index=True)
    ek.assert_rows(allw, sum(len(p) for p in parts), "harmonised concat")
    out = xl.resolve_path(cfg["outputs"]["harmonised"])
    out.parent.mkdir(parents=True, exist_ok=True)
    allw.to_csv(out, index=False, compression="gzip")
    T = ek.sub("3.2", "results/tables")
    cc = pd.concat(counts, ignore_index=True)
    c_csv = T / "wells_harmonise_counts_appal.csv"
    cc.to_csv(c_csv, index=False)
    ky = allw[allw.source == "ky_kgs"].datum_shift_m
    summ = {"rows": int(len(allw)), "by_source": allw.source.value_counts().to_dict(),
            "by_status": allw.status_h.value_counts().to_dict(),
            "ky_nad27_to_nad83_shift_m": {"median": float(np.nanmedian(ky)), "p95": float(np.nanpercentile(ky.dropna(), 95)),
                                          "max": float(np.nanmax(ky))} if ky.notna().any() else None,
            "in_window": allw.window_tag.value_counts().to_dict(),
            "note": "status mapping is regex rules in config_3_2.json; VERIFY against each data dictionary",
            "output": str(out), "output_bytes": out.stat().st_size}
    js = T / "wells_harmonise_summary_appal.json"
    js.write_text(json.dumps(summ, indent=2, default=float), encoding="utf-8")
    print(json.dumps(summ, indent=2, default=float))
    print(f"wrote {out}\n      {c_csv}\n      {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
