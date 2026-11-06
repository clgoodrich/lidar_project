"""S0. Data audit for risk ranking on 9t (fw_5_3 section 6 S0).

Purpose
    Read every configured layer. Report present or missing, assumed or held, rows, CRS (asserted after
    reprojection to EPSG:6346), rows inside the 9t bbox, positional error where a column states it, and the
    missing share of every column. A missing assumed layer is a row in the audit, not a crash.
    Endpoint layers (inspections, complaints, flux) are audited for presence and row count only. Their values
    are not read here, so nothing about the endpoint is seen before the preregistration.
Inputs (config_5_3.json "inputs", every entry)
    held     dep_wells, pit_blocks, roads, counties, candidates_fallback (and candidates_full once 5.6 S0 runs)
    assumed  water_wells, public_supply, buildings, streams, wetlands, protected, landcover, dep_inspections,
             complaints, field_flux, subsurface_tops, agency_list, prereg
Outputs
    @exp:5.3/results/tables/risk_data_audit_9t.csv    one row per layer
    @exp:5.3/results/tables/risk_data_missing_9t.csv  one row per layer and column, missing share
    run folder @exp:5.3/results/runs/<YYYYMMDD>_risk_audit_<hash>/ with _PROVENANCE.json
Run
    python expansions/5_tasks/5_3_risk_ranking/src/_risk_data_audit_9t.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _risk_io_9t as rio  # noqa: E402

ek = th.ek


def audit_layer(name: str, ent, cfg) -> tuple[dict, list]:
    p = th.inp(cfg, name, must_exist=False)
    assumed = bool(ent.get("assumed")) if isinstance(ent, dict) else False
    endpoint = bool(ent.get("endpoint")) if isinstance(ent, dict) else False
    row = dict(layer=name, path=str(p), assumed=assumed, endpoint=endpoint, present=p.exists(),
               rows=None, rows_in_bbox=None, crs_source=None, crs_ok=None, median_pos_error_m=None, note="")
    miss = []
    if not p.exists():
        row["note"] = "missing. " + (ent.get("hint", "") if isinstance(ent, dict) else "")
        return row, miss
    suf = p.suffix.lower()
    try:
        if suf in (".csv",):
            if endpoint:
                with open(p, encoding="utf-8", errors="replace") as f:
                    row["rows"] = max(sum(1 for _ in f) - 1, 0)
                row["note"] = "endpoint layer. Values not read before preregistration"
                return row, miss
            df = pd.read_csv(p)
            row["rows"] = len(df)
        elif suf in (".json",):
            row["rows"] = 1
            return row, miss
        elif suf in (".tif", ".tiff"):
            import rasterio
            with rasterio.open(p) as r:
                row["crs_source"] = str(r.crs)
                row["rows"] = int(r.width * r.height)
                row["note"] = f"raster {r.width}x{r.height} res {r.res}"
            return row, miss
        else:
            import geopandas as gpd
            layer = "blocks" if name == "pit_blocks" else ("matched" if name == "candidates_fallback" else None)
            g = gpd.read_file(p, layer=layer) if layer else gpd.read_file(p)
            row["crs_source"] = g.crs.to_string() if g.crs is not None else None
            g = g.to_crs(cfg["crs"]) if g.crs is not None else g
            ek.assert_crs(g, cfg["crs"])
            row["crs_ok"] = True
            row["rows"] = len(g)
            bb = cfg["bbox"]
            row["rows_in_bbox"] = int(len(g.cx[bb[0]:bb[2], bb[1]:bb[3]]))
            df = pd.DataFrame(g.drop(columns="geometry"))
        if "pos_error_m" in df:
            row["median_pos_error_m"] = float(df["pos_error_m"].median())
        for c in df.columns:
            miss.append(dict(layer=name, column=c, missing_share=round(float(df[c].isna().mean()), 4)))
    except Exception as e:  # noqa: BLE001  an unreadable layer is an audit finding
        row["note"] = f"unreadable: {type(e).__name__}: {e}"
    return row, miss


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    run = rio.start_run(cfg, "risk_audit", "S0 data audit.", ["bbox"])
    rows, miss = [], []
    for name, ent in cfg["inputs"].items():
        r, m = audit_layer(name, ent, cfg)
        rows.append(r)
        miss += m
        print(f"  {name:20s} present={r['present']!s:5s} rows={r['rows']} {r['note'][:70]}")
    A = pd.DataFrame(rows)
    out = th.outp(cfg, "audit")
    A.to_csv(out, index=False)
    out2 = th.outp(cfg, "audit_missing")
    pd.DataFrame(miss, columns=["layer", "column", "missing_share"]).to_csv(out2, index=False)
    present = [Path(r["path"]) for r in rows if r["present"] and not r["endpoint"]]
    ek.write_provenance(run, inputs=present, outputs=[out, out2], params={"n_layers": len(rows)})
    n_ass_missing = int(((A.assumed) & (~A.present)).sum())
    print(f"wrote {out}\nwrote {out2}\n{n_ass_missing} assumed layers missing. Run folder {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
