"""6.2 S0b. Inventory audit summary, re-chosen tolerances and the S0 readiness gate (Q1, descriptive).

Purpose
    From the reviewer-filled audit file, compute per class the identity share (record shows a feature of that
    class) with a Clopper-Pearson interval, the 50th and 90th percentile offset to the nearest visible feature,
    and the re-chosen tolerance (90th percentile, rounded up to 5 m for point rules). From the completeness
    blocks, completeness is matched records over visible features with an exact interval. The S0 gate is decided
    per layer and class. Ready when the identity share reaches the preregistered minimum and the 90th
    percentile offset is under the tolerance. Otherwise the verdict is to label from imagery and lidar only.
    Inventory records are never training labels before this gate passes.
Inputs (data/greene/results/coal/)
    coal_audit_records.csv (identity in {same, other, nothing, uncertain}, offset_m), coal_completeness_blocks.csv
Outputs
    data/greene/results/coal/coal_audit_summary.json
Run
    python expansions/6_adjacent/6_2_coal_features/src/_coal_inventory_audit_coal.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _coal_common as K
from _coal_common import C, ek

IDENTITY = {"same", "other", "nothing", "uncertain"}


def summarise(cfg: dict, audit: pd.DataFrame, comp: pd.DataFrame | None) -> dict:
    a = audit.copy()
    a["identity"] = a["identity"].astype(str).str.strip().str.lower()
    filled = a[a.identity.isin(IDENTITY)]
    bad = set(a.identity) - IDENTITY - {"", "nan"}
    if bad:
        raise AssertionError(f"identity values outside {sorted(IDENTITY)}: {sorted(bad)}")
    g = cfg["audit_gate"]
    res = {"n_rows": int(len(a)), "n_filled": int(len(filled)), "per_class": {}, "per_layer": {}}
    for cls, s in filled.groupby("cls"):
        k, n = int((s.identity == "same").sum()), len(s)
        p, lo, hi = ek.clopper_pearson(k, n)
        off = pd.to_numeric(s.loc[s.identity == "same", "offset_m"], errors="coerce").dropna()
        p50, p90 = (float(np.percentile(off, 50)), float(np.percentile(off, g["offset_percentile"]))) if len(off) else (np.nan, np.nan)
        tol = cfg["tolerance"][cls]
        current = tol.get("offset_m", tol.get("m"))
        rechosen = float(np.ceil(p90 / 5) * 5) if np.isfinite(p90) else None
        # point share against the preregistered minimum (framework section 10). The interval is reported beside it.
        ready = bool(p >= g["min_identity_share"] and np.isfinite(p90) and current is not None and p90 <= current)
        res["per_class"][cls] = {"k_same": k, "n": n, "identity_share": p, "lo95": lo, "hi95": hi,
                                 "offset_p50_m": p50, f"offset_p{g['offset_percentile']}_m": p90,
                                 "tolerance_m_now": current, "tolerance_m_rechosen": rechosen,
                                 "exploratory": n < 15,
                                 "verdict": "use records as match targets" if ready else
                                            "label from imagery and lidar only"}
    for lyr, s in filled.groupby("layer"):
        k, n = int((s.identity == "same").sum()), len(s)
        res["per_layer"][lyr] = dict(zip(("identity_share", "lo95", "hi95"), ek.clopper_pearson(k, n))) | {"n": n}
    if comp is not None and len(comp):
        cc = {}
        for cls in ("M", "S", "H"):
            vis = pd.to_numeric(comp[f"n_visible_{cls}"], errors="coerce").sum()
            mat = pd.to_numeric(comp[f"n_matched_{cls}"], errors="coerce").sum()
            if vis > 0:
                p, lo, hi = ek.clopper_pearson(int(mat), int(vis))
                cc[cls] = {"matched": int(mat), "visible": int(vis), "completeness": p, "lo95": lo, "hi95": hi,
                           "note": "blocks are clusters. The exact interval treats features as independent and is too narrow."}
        res["completeness"] = cc
    res["gate_rule"] = (f"identity share at least {g['min_identity_share']} and p{g['offset_percentile']} offset "
                        "at or under the current tolerance")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cfg = K.load_config(a.config)
    out = C.results_dir(cfg, a.out)
    ap_ = out / "coal_audit_records.csv"
    if not ap_.exists():
        raise K.MissingInput(f"{ap_} missing. Run _coal_inventory_sample_coal.py and fill identity and offset_m.")
    cp = out / "coal_completeness_blocks.csv"
    res = summarise(cfg, pd.read_csv(ap_), pd.read_csv(cp) if cp.exists() else None)
    js = out / "coal_audit_summary.json"
    js.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    C.provenance(cfg, out, "coalauditsum", inputs=[ap_], outputs=[js])
    print(json.dumps(res["per_class"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
