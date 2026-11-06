"""S7 transportability check to the sentinel stratum for 5.2 (fw_5_2 section 7 S7).

Purpose
    Compare feature distributions of sentinel wells with dated wells, per feature and per era class.
    Overlap coefficient (shared histogram mass, 1 is identical) per feature. Per sentinel well an in-support flag
    is set when every usable feature lies inside the [q_lo, q_hi] quantile range of the dated wells.
    Outside support means any era prediction there is labelled extrapolated. This is an overlap check. It is not
    a domain-classifier verdict, which would show distinguishability only.
    Dated wells are chosen by map visibility and record keeping. They may differ from sentinel wells in more than
    era. Every output says so.

Inputs (config_5_2.json)
    pairs   @exp:5.2/results/tables/era_features_pairs_9t.csv (S4, labels joined)
Outputs
    support_csv    @exp:5.2/results/tables/era_sentinel_support_9t.csv          (one row per sentinel pair)
    support_json   @exp:5.2/results/tables/era_sentinel_support_summary_9t.json (per-feature overlap)
Evidence level
    (a) drawn feature. era_basis = predicted_unvalidated for any U prediction downstream.
Run
    python expansions/5_tasks/5_2_era_classification/src/_era_sentinel_support_9t.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _era_core_tools as ec  # noqa: E402

ek = th.ek
CAVEAT = "Dated wells are selected by map visibility and record keeping. They may differ from sentinel wells in more than era."


def support(pairs: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    s = cfg["support"]
    feats = [c for c in cfg["features"]["morphology"] + cfg["features"]["covariates"] if c in pairs]
    dated = pairs[pairs["lo"].notna() & (pairs["stratum"] != ec.SENTINEL_STRATUM)]
    sent = pairs[pairs["stratum"] == ec.SENTINEL_STRATUM].copy()
    summ = {"n_dated": int(len(dated)), "n_sentinel": int(len(sent)), "caveat": CAVEAT, "features": {}}
    usable = [c for c in feats if dated[c].notna().sum() >= 2 and sent[c].notna().any()]
    flags = np.ones(len(sent), bool)
    for c in usable:
        lo, hi = dated[c].quantile([s["q_lo"], s["q_hi"]])
        inside = sent[c].between(lo, hi) | sent[c].isna()
        flags &= inside.to_numpy()
        per_class = {k: ec.overlap_coefficient(sent[c], g[c], s["n_bins"]) for k, g in dated.groupby("era_class")}
        summ["features"][c] = dict(overlap_all_dated=ec.overlap_coefficient(sent[c], dated[c], s["n_bins"]),
                                   overlap_by_class=per_class, dated_q=[float(lo), float(hi)],
                                   share_sentinel_inside=float(inside.mean()) if len(inside) else None)
    summ["features_skipped"] = sorted(set(feats) - set(usable))
    sent["in_support"] = flags
    sent["era_basis"] = np.where(flags, "predicted_unvalidated", "extrapolated")
    sent["caveat"] = CAVEAT
    summ["share_in_support"] = float(flags.mean()) if len(flags) else None
    out = th.tag(sent[["permit", "pad_id", "block_id", "in_support", "era_basis", "caveat"] + usable], "a", "exploratory")
    return out, summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    pp = th.inp(cfg, "pairs")
    pairs = pd.read_csv(pp)
    if pairs["lo"].notna().sum() == 0:
        raise th.MissingInput("labels", th.inp(cfg, "labels", must_exist=False),
                              "No dated wells in the pairs table. Run S2 (needs 4.6 marks) then S4.")
    out, summ = support(pairs, cfg)
    p1 = th.outp(cfg, "support_csv")
    out.to_csv(p1, index=False)
    p2 = th.write_json(th.outp(cfg, "support_json"), summ)
    run = ek.new_run("5.2", "era_support", cfg["support"], base=th.resolve(cfg["outputs"]["runs"]),
                     why="S7 sentinel support check.")
    ek.write_provenance(run, inputs=[pp], outputs=[p1, p2], params=cfg["support"])
    print(f"sentinel pairs {summ['n_sentinel']}, in support {summ['share_in_support']}")
    print(p1, p2, sep="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
