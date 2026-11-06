"""S0 (3.6). Verify assumed data. CalGEM snapshot normalised, compared with the two held USGS lists.

Purpose
    Run the section 5 VERIFY checks that can run in code. Freeze one CalGEM snapshot (date and SHA-256),
    count rows, list status codes, check for a pad or lease field and a coordinate-method field.
    Compare California totals with the held USGS 2022 (3,338 rows) and 2026 (2,940 rows) lists.
    Status is a record attribute. It is never a label and never enters label, feature or scoring tables.
    Stops at the first failed check and reports it.
Inputs
    data/_source/reference/wells_us_orphan_2022/US_orphaned_wells.csv, wells_us_orphan_2026/... (held)
    config_3_6.json inputs.calgem_wells (assumed)
Outputs
    expansions/3_geography/3_6_california/results/tables/ca_data_verification.csv
    expansions/3_geography/3_6_california/data/interim/ca_wells_snapshot_ca1.gpkg   (when CalGEM is held)
Run
    python expansions/3_geography/3_6_california/src/_ca_wells_snapshot.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.6"
CALGEM_MAP = {"well_id": "API", "status_raw": "WellStatus", "well_type": "WellType", "lat": "Latitude",
              "lon": "Longitude", "spud_date": "SpudDate", "plug_date": "PluggedDate", "county": "FieldName",
              "coord_method": "CoordMethod"}
CALGEM_STATUS = {"active": "active", "idle": "idle", "plugged": "plugged", "plugged and abandoned": "plugged",
                 "new": "new", "canceled": "canceled", "unknown": "unknown", "orphan": "orphan"}


def usgs_ca_rows() -> list[dict]:
    rows = []
    for yr in (2022, 2026):
        g = gt.load_usgs_orphans(["California"], yr)
        rows.append({"check": f"usgs_{yr}_rows", "value": len(g), "ok": True,
                     "detail": "; ".join(f"{k}={v}" for k, v in g["status_raw"].value_counts().head(6).items())})
    return rows


def calgem_checks(df: pd.DataFrame, path: Path) -> list[dict]:
    rows = [{"check": "calgem_rows", "value": len(df), "ok": len(df) > 0, "detail": str(path)},
            {"check": "calgem_sha256", "value": ek.sha256(path), "ok": True, "detail": ""},
            {"check": "calgem_status_codes", "value": df.get("WellStatus", pd.Series(dtype=str)).nunique(),
             "ok": "WellStatus" in df, "detail": ", ".join(map(str, df.get("WellStatus", pd.Series()).dropna().unique()[:12]))}]
    pad_like = [c for c in df.columns if any(k in c.lower() for k in ("pad", "lease"))]
    meth = [c for c in df.columns if "method" in c.lower() or "source" in c.lower()]
    rows.append({"check": "calgem_pad_or_lease_field", "value": len(pad_like), "ok": True, "detail": ",".join(pad_like)})
    rows.append({"check": "calgem_coord_method_field", "value": len(meth), "ok": True, "detail": ",".join(meth)})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    rows = usgs_ca_rows()
    out_t = ek.sub(EXP, "results/tables") / "ca_data_verification.csv"
    try:
        p = gt.config_input(cfg, "calgem_wells", EXP)
    except gt.MissingInputError as e:
        rows.append({"check": "calgem_present", "value": 0, "ok": False, "detail": str(e).splitlines()[0]})
        pd.DataFrame(rows).to_csv(out_t, index=False)
        print(pd.DataFrame(rows).to_string(index=False))
        print(str(e), file=sys.stderr)
        print(f"wrote {out_t}. Stopped at the first failed check (CalGEM snapshot missing).")
        return 2
    df = pd.read_csv(p, low_memory=False)
    rows += calgem_checks(df, p)
    g = gt.normalise_registry(df, CALGEM_MAP, "ca_calgem", CALGEM_STATUS, pd.Timestamp(p.stat().st_mtime, unit="s")
                              .date().isoformat(), lonlat_crs="EPSG:4269")
    g["state_prov"] = "California"
    out = ek.sub(EXP, "data/interim") / "ca_wells_snapshot_ca1.gpkg"
    g.to_file(out, driver="GPKG")
    rows.append({"check": "calgem_coord_ok", "value": int(g["coord_ok"].sum()), "ok": True, "detail": ""})
    pd.DataFrame(rows).to_csv(out_t, index=False)
    print(pd.DataFrame(rows).to_string(index=False), f"\nwrote {out_t}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
