"""S0 (3.7). Provincial inventory pull, normalisation and verification ladder levels V0 and V1.

Purpose
    For each province (Alberta, British Columbia, Ontario) load the regulator well list and the orphan
    list, normalise both to the shared schema, map the coordinate method to a class and a stated
    uncertainty (legal land descriptions can be off by hundreds of metres), and assign ladder levels.
      V0  record exists, coordinates unverified (every orphan-list row starts here)
      V1  coordinate method documented and an uncertainty stated or bounded
    V2 needs independent agreement (S6) and V3 a field visit. Neither is assigned here.
    With --execute and an arcgis_url in the config the list is paged with the completeness ledger
    (successful-empty, failed, incomplete kept apart, totals compared). Stops at the first failure.
Inputs
    config_3_7.json provinces.<p>.wells / orphans (assumed paths under data/_source/reference/wells_can/)
Outputs
    data/_source/reference/wells_can/<p>/<p>_fetch_ledger.json          (--execute only)
    expansions/3_geography/3_7_canada/data/interim/can_inventory_rows.gpkg
    expansions/3_geography/3_7_canada/results/tables/can_inventory_summary.csv
Run
    python expansions/3_geography/3_7_canada/src/_can_inventory_rows.py --provinces ab,bc,on
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.7"


def coord_class(method, cmap: dict) -> str:
    if method is None or pd.isna(method) or str(method).strip() == "":
        return "unknown"
    m = str(method).lower()
    for k, v in cmap.items():
        if k in m:
            return v
    return "other_documented"


def ladder(g, cmap: dict, unc: dict) -> pd.DataFrame:
    g = g.copy()
    g["coord_class"] = [coord_class(m, cmap) for m in g["coord_method"]]
    g["uncertainty_m"] = [unc.get(c, 10.0 if c == "surveyed" else None) for c in g["coord_class"]]
    g["v_level"] = ["V1" if (c not in ("unknown", "other_documented") and u is not None) else "V0"
                    for c, u in zip(g["coord_class"], g["uncertainty_m"])]
    return g


def load_source(prov: str, kind: str, spec: dict, execute: bool):
    p = gt.resolve(spec["path"])
    if execute and spec.get("arcgis_url"):
        df, led = gt.arcgis_paged_query(spec["arcgis_url"])
        p.parent.mkdir(parents=True, exist_ok=True)
        (p.parent / f"{prov}_{kind}_fetch_ledger.json").write_text(json.dumps(led, indent=2))
        if not led["complete"]:
            raise RuntimeError(f"{prov} {kind}: incomplete query {led}. Stopped. Rows were not used")
        df.to_csv(p, index=False)
    p = gt.require_input(p, f"{prov} {kind} list", spec.get("schema"), spec.get("verify", ""))
    df = pd.read_csv(p, low_memory=False)
    return gt.normalise_registry(df, spec["colmap"], f"{prov}_{kind}", None,
                                 pd.Timestamp(p.stat().st_mtime, unit="s").date().isoformat(), "EPSG:4269"), p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provinces", default="ab,bc,on")
    ap.add_argument("--execute", action="store_true", help="page ArcGIS sources (network, gated)")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    parts, rows, failed = [], [], []
    for prov in a.provinces.split(","):
        pc = cfg["provinces"][prov]
        for kind in ("wells", "orphans"):
            try:
                g, p = load_source(prov, kind, pc[kind], a.execute)
            except (gt.MissingInputError, RuntimeError) as e:
                failed.append({"province": prov, "kind": kind, "error": str(e).splitlines()[0]})
                print(str(e), file=sys.stderr)
                continue
            g = ladder(g, cfg["coord_method_map"], cfg["prereg"]["lsd_uncertainty_m"])
            if kind == "orphans":
                g["v_level"] = "V0"         # orphan rows are never above V0 without evidence
            g["province"] = prov
            g["list"] = kind
            parts.append(g)
            s = gt.registry_summary(g)
            rows.append({"province": prov, "list": kind, "rows": s["rows"], "coord_ok": s["coord_ok"],
                         "sha256": ek.sha256(p), "snapshot": g["snapshot_date"].iloc[0] if len(g) else "",
                         **{f"coord_{k}": v for k, v in g["coord_class"].value_counts().items()},
                         **{f"v_{k}": v for k, v in g["v_level"].value_counts().items()}})
    tables = ek.sub(EXP, "results/tables")
    summ = pd.DataFrame(rows + [{"province": f["province"], "list": f["kind"], "rows": 0, "error": f["error"]}
                                for f in failed])
    summ.to_csv(tables / "can_inventory_summary.csv", index=False)
    print(summ.to_string(index=False), f"\nwrote {tables / 'can_inventory_summary.csv'}")
    if parts:
        import geopandas as gpd
        out = ek.sub(EXP, "data/interim") / "can_inventory_rows.gpkg"
        gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs="EPSG:4326").to_file(out, driver="GPKG")
        print(f"wrote {out}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
