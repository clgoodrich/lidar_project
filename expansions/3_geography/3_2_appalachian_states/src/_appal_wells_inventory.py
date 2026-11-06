"""3.2 S0. Desk inventory of the state well-record sources (NY, OH, WV, KY, US orphan lists).

Purpose
    One row per source. Path, SHA-256, raw row count, rows after the state filter, columns,
    rows with coordinates, coordinate decimals (median), declared datum and its state
    (held or assumed, VERIFY), status values with counts, date fields with range, rows with
    the 1800 sentinel date, rows dated before 1930, and records with a NAD27 shift measured.
    Status definitions are not in the files. They must come from each data dictionary, so the
    inventory lists the raw codes for that lookup.

Inputs (held)
    data/_source/reference/wells_ny_dec/ny_oil_gas_regulated_wells_since_1860.csv, ny_orphaned_wells.csv
    data/_source/reference/wells_oh_odnr/oh_odnr_wells.csv.gz
    data/_source/reference/wells_wv_dep/wv_dep_all_wells.csv.gz
    data/_source/reference/wells_ky_kgs/kyog_dd.zip
    data/_source/reference/wells_us_orphan_2026/US_orphaned_wells_2026.csv, wells_us_orphan_2022/US_orphaned_wells.csv

Outputs
    expansions/3_geography/3_2_appalachian_states/results/tables/state_inventory_appal.csv
    expansions/3_geography/3_2_appalachian_states/results/tables/state_inventory_appal.json  (status value counts per source)

Run
    python expansions/3_geography/3_2_appalachian_states/src/_appal_wells_inventory.py
    python expansions/3_geography/3_2_appalachian_states/src/_appal_wells_inventory.py --only ny_dec_orphan oh_odnr
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _appal_wells_loaders as wl  # noqa: E402
xl, ek = wl.xl, wl.ek


def summarise(name, src, n_raw, df):
    p = xl.resolve_path(src["path"])
    dates = {k: [str(df[k].min()), str(df[k].max()), int(df[k].notna().sum())] for k in ("date_spud", "date_complete", "date_plug")
             if df[k].notna().any()}
    return {"source": name, "path": str(p), "sha256": ek.sha256(p), "bytes": p.stat().st_size, "rows_raw": n_raw,
            "rows_in_scope": len(df), "rows_with_coords": int(df.has_coords.sum()),
            "coord_dp_median": float(np.nanmedian(df.coord_dp)) if np.isfinite(df.coord_dp).any() else None,
            "rows_low_precision": int(df.low_precision.sum()), "datum": src.get("datum"), "datum_state": src.get("datum_state"),
            "datum_shift_m_median": float(np.nanmedian(df.datum_shift_m)) if np.isfinite(df.datum_shift_m).any() else None,
            "rows_sentinel_1800": int(df.date_unknown_sentinel.sum()), "rows_early_dated": int(df.early_dated.sum()),
            "dates": json.dumps(dates), "states": json.dumps(df.state.value_counts().to_dict())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(wl.CFG))
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    import pandas as pd
    rows, status = [], {}
    for name, n_raw, df in wl.load_all(cfg, a.only):
        src = cfg["wells"]["sources"][name]
        rows.append(summarise(name, src, n_raw, df))
        status[name] = {"raw_codes": df.status_orig.value_counts().head(60).to_dict(),
                        "harmonised": df.status_h.value_counts().to_dict()}
        print(f"  {name}: {n_raw} raw, {len(df)} in scope, {int(df.has_coords.sum())} with coords")
    out = ek.sub("3.2", "results/tables")
    csv, js = out / "state_inventory_appal.csv", out / "state_inventory_appal.json"
    pd.DataFrame(rows).to_csv(csv, index=False)
    js.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
    print(f"wrote {csv}\n      {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
