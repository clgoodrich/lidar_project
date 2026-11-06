"""3.2 S12. Descriptive state table (one row per window, no pooled gate) and the 5.6 hand-off.

Purpose
    Collects each window's newest score run (3.1 _xfer_score_k40_wfm.py run with config_3_2)
    into one descriptive table. Columns per window. Recall at K = 40 with interval, the 9t
    difference with interval and the decision, density-scaled and K = 30 secondaries, target
    density, ground density, union cover and the stamp (preregistered or not). Windows not
    yet scored appear with their readiness state from S2 and S3. No between-state statistic
    and no pooled gate are computed (two windows per state give a pair, not a variance).
    Multiplicity (user default 2026-11-06). Holm over the four primary windows in config multiplicity.family.
    When results/tables/xfer_holm_family_appal.json exists (3.0 _transfer_holm_gate.py over the four primary
    score JSONs) its verdict replaces the single-run decision. Companion windows are never gated.
    The hand-off writes the harmonised records that fall inside each window for 5.6 without
    scoring them.

Inputs
    expansions/3_geography/3_2_appalachian_states/results/*_xfer_score_<tag>_*/xfer_score_k40_<tag>.json
    results/tables/lidar_win_union_cover_appal.csv, xfer_density_void_windows_appal.csv (S2, S3)
    data/processed/wells_status_harmonised_appal.csv.gz (S1)

Outputs
    expansions/3_geography/3_2_appalachian_states/results/tables/state_transfer_table_appal.csv
    expansions/3_geography/3_2_appalachian_states/data/processed/wells_window_handoff_appal.csv.gz  (for 5.6)

Run
    python expansions/3_geography/3_2_appalachian_states/src/_appal_state_table.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "3_1_warren_forest_mckean" / "src"))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_2.json"


def window_row(tag, area, score: dict | None, cover: pd.DataFrame, dens: pd.DataFrame, holm: dict | None = None):
    r = {"tag": tag, "state": area["state"], "window": area["window"], "role": area["role"], "program": area.get("program")}
    c = cover[(cover.tag == tag) & (cover.configured.eq(True))] if len(cover) else cover
    r["union_cover"] = float(c.cover.iloc[0]) if len(c) else None
    d = dens[dens.tag == tag] if len(dens) else dens
    r["ground_per_m2"] = float(d.ground_per_m2_median.iloc[0]) if len(d) and "ground_per_m2_median" in d and pd.notna(d.ground_per_m2_median.iloc[0]) else None
    if score is None:
        r["status"] = "not scored"
        return r
    p = score["primary"]
    r.update({"status": "scored", "stamp": score.get("stamp") or "preregistered", "recall_k40": p["recall"],
              "hits": p["hits"], "n_truth": p["n_truth"], "n_blocks": p["n_blocks"],
              "truth_density_per_km2": p["truth_density_per_km2"], "diff_vs_9t": p["diff"], "lo": p["lo"], "hi": p["hi"],
              "decision": p["decision"], "permutation_p": p.get("permutation_p"),
              "decision_basis": p.get("decision_basis", "not gated (companion)")})
    if holm and tag in holm:
        r.update({"decision": holm[tag]["decision"], "p_holm": holm[tag]["p_holm"],
                  "decision_basis": f"Holm over {holm[tag]['family']}"})
    for k in ("density_scaled", "k30", "superblock"):
        if k in score:
            r[f"{k}_diff"], r[f"{k}_lo"], r[f"{k}_hi"] = score[k]["diff"], score[k]["lo"], score[k]["hi"]
    return r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    T = ek.sub("3.2", "results/tables")
    cover = pd.read_csv(T / "lidar_win_union_cover_appal.csv") if (T / "lidar_win_union_cover_appal.csv").exists() else pd.DataFrame()
    dens = pd.read_csv(T / "xfer_density_void_windows_appal.csv") if (T / "xfer_density_void_windows_appal.csv").exists() else pd.DataFrame()
    hf = T / "xfer_holm_family_appal.json"
    holm = json.loads(hf.read_text(encoding="utf-8")) if hf.exists() else None
    rows = []
    for tag, area in cfg["areas"].items():
        runs = sorted(ek.sub("3.2", "results").glob(f"*_xfer_score_{tag}_*"))
        sc = json.loads((runs[-1] / f"xfer_score_k40_{tag}.json").read_text()) if runs else None
        rows.append(window_row(tag, area, sc, cover, dens, holm))
    tab = pd.DataFrame(rows)
    out = T / "state_transfer_table_appal.csv"
    tab.to_csv(out, index=False)
    print(tab.to_string(index=False))
    hp = xl.resolve_path(cfg["outputs"]["harmonised"])
    if hp.exists():
        w = pd.read_csv(hp, low_memory=False)
        h = w[w.window_tag.notna()].assign(evidence_level="(b) historical record, not scored here")
        ho = hp.parent / "wells_window_handoff_appal.csv.gz"
        h.to_csv(ho, index=False, compression="gzip")
        print(f"hand-off {len(h)} records -> {ho}")
    else:
        print(f"no harmonised records at {hp}; run _appal_wells_harmonise.py for the 5.6 hand-off")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
