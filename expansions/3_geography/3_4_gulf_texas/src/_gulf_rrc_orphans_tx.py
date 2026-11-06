"""S0 (3.4). Texas RRC orphan wells. Paged fetch (gated), schema read, normalisation, reliability table.

Purpose
    Page RRC layer 2 "Orphan Wells" with a completeness ledger (successful-empty, failed and incomplete
    pages kept apart, returned total compared with retrieved). Normalise to the shared well schema.
    Tabulate the location reliability and coordinate source classes (unknown is its own class).
    RRC rows are administrative evidence, level (b). They are never labels and never shown to annotators.
Inputs
    config_3_4.json inputs.rrc_layer2_url (assumed), inputs.rrc_raw (written by --execute),
    or inputs.rrc_permian_sample (held, data/_experiments/permian_sample/rrc_orphan_wells_permian.gpkg)
Outputs
    data/_source/reference/wells_rrc_orphans_tx/rrc_orphans_layer2_tx.csv.gz      (--execute only)
    data/_source/reference/wells_rrc_orphans_tx/rrc_fetch_ledger_tx.json         (--execute only)
    expansions/3_geography/3_4_gulf_texas/data/interim/rrc_orphans_norm_tx.gpkg
    expansions/3_geography/3_4_gulf_texas/results/tables/rrc_schema_fields_tx.csv
    expansions/3_geography/3_4_gulf_texas/results/tables/rrc_reliability_classes_tx.csv
Run
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_rrc_orphans_tx.py --source permian
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_rrc_orphans_tx.py --source layer2 --execute
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.4"
# Assumed field names. VERIFY against the real layer schema and edit here or in the config.
RRC_COLMAP = {"well_id": "API", "status_raw": "status", "county": "COUNTY_NAME", "well_type": "WELL_TYPE",
              "lat": "lat", "lon": "lon", "coord_method": "LOC_SOURCE", "coord_reliability": "LOC_RELIABILITY"}
RRC_STATUS = {"orphan_confirmed": "orphan", "orphan": "orphan", "delinquent": "delinquent", "plugged": "plugged"}


def schema_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"field": df.columns, "dtype": [str(t) for t in df.dtypes],
                         "n_non_null": df.notna().sum().to_numpy(),
                         "n_unique": [df[c].astype(str).nunique() for c in df.columns],
                         "example": [str(df[c].dropna().iloc[0]) if df[c].notna().any() else "" for c in df.columns]})


def normalise_rrc(df: pd.DataFrame, colmap: dict = RRC_COLMAP, snapshot: str = ""):
    missing = [v for k, v in colmap.items() if v not in df.columns and k in ("well_id", "lat", "lon")]
    if missing:
        raise gt.MissingInputError(f"RRC table lacks required fields {missing}. Read the real schema "
                                   f"(rrc_schema_fields_tx.csv) and edit RRC_COLMAP")
    g = gt.normalise_registry(df, colmap, "tx_rrc_layer2", RRC_STATUS, snapshot, lonlat_crs="EPSG:4326")
    g["state_prov"] = "Texas"
    return g


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", choices=["permian", "layer2"], default="permian")
    ap.add_argument("--execute", action="store_true", help="network fetch of layer 2 (gated, D13)")
    ap.add_argument("--page", type=int, default=1000)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    try:
        if a.source == "layer2":
            raw_p = gt.resolve(cfg["inputs"]["rrc_raw"]["path"])
            if a.execute:
                url = gt.config_input(cfg, "rrc_layer2_url", EXP).read_text().strip()
                df, ledger = gt.arcgis_paged_query(url, page=a.page)
                raw_p.parent.mkdir(parents=True, exist_ok=True)
                if not ledger["complete"]:
                    print("WARNING. Query incomplete. Ledger lists failed and incomplete pages.", file=sys.stderr)
                df.to_csv(raw_p, index=False, compression="gzip")
                (raw_p.parent / "rrc_fetch_ledger_tx.json").write_text(json.dumps(ledger, indent=2))
                ek.write_provenance(raw_p.parent, outputs=[raw_p], params={"url": url, "ledger": ledger})
            df = pd.read_csv(gt.config_input(cfg, "rrc_raw", EXP), low_memory=False)
            snap = pd.Timestamp(raw_p.stat().st_mtime, unit="s").date().isoformat()
            colmap = RRC_COLMAP
        else:
            import geopandas as gpd
            g0 = gpd.read_file(gt.config_input(cfg, "rrc_permian_sample", EXP))
            df = pd.DataFrame({"API": g0["API"], "status": g0["status"], "lon": g0.geometry.x, "lat": g0.geometry.y})
            snap, colmap = "permian_sample", {"well_id": "API", "status_raw": "status", "lat": "lat", "lon": "lon"}
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    tables = ek.sub(EXP, "results/tables")
    schema_table(df).to_csv(tables / "rrc_schema_fields_tx.csv", index=False)
    g = normalise_rrc(df, colmap, snap)
    rel = g["coord_reliability"].astype(str).value_counts().rename_axis("class").reset_index(name="n")
    rel.to_csv(tables / "rrc_reliability_classes_tx.csv", index=False)
    out = ek.sub(EXP, "data/interim") / "rrc_orphans_norm_tx.gpkg"
    g.to_file(out, driver="GPKG")
    s = gt.registry_summary(g)
    ek.write_provenance(out.parent, outputs=[out], params={"source": a.source, "summary": s})
    print(json.dumps(s, indent=2, default=str))
    print(f"wrote {out}\nwrote {tables / 'rrc_schema_fields_tx.csv'}\nwrote {tables / 'rrc_reliability_classes_tx.csv'}")
    if a.source == "permian":
        print("NOTE. Permian sample is West Texas and has no reliability field. It stands in until layer 2 is paged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
