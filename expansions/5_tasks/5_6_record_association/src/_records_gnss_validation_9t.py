"""5.6 S6. Independent coordinate validation of proposed links (blocked until GNSS or NETL points arrive).

Purpose
    For every record with an independent position, compare the position error before (record to GNSS) and after
    (proposed candidate centroid to GNSS). Report the paired change, wrong matches (after worse than before by more
    than the margin), abstentions (records with an independent point but no proposal) and a block-bootstrap interval
    over 375 m blocks. Decision by ek.decide. Superiority (error drops by more than margin_m) and non-inferiority.
    Proximity excess alone never passes coordinate correction. A pad centroid is not a borehole, so pad-level
    proposals are reported separately and never pooled with pit-level ones.

Inputs
    gnss_points  assumed, @reference/independent_coords/gnss_wells_9t.gpkg (PERMIT_NUM, method, h_acc_m, Point)
    --proposals  proposals.csv from a _records_assoc_v2_9t.py run (default newest)
Outputs
    expansions/5_tasks/5_6_record_association/results/tables/records_gnss_position_error_9t.csv
    expansions/5_tasks/5_6_record_association/results/tables/records_gnss_validation_9t.json
Run
    python expansions/5_tasks/5_6_record_association/src/_records_gnss_validation_9t.py [--proposals <csv>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _records_link_ppv_sample_9t as ppv  # noqa: E402

ek = th.ek


def paired_errors(P: pd.DataFrame, G: pd.DataFrame, origin, size) -> pd.DataFrame:
    """Join proposals to independent points by permit. Returns one row per (permit, level)."""
    th.require_columns(G, ["PERMIT_NUM", "gx", "gy"], "gnss points")
    m = P.merge(G[["PERMIT_NUM", "gx", "gy"]], left_on="permit", right_on="PERMIT_NUM", how="inner")
    m["err_before_m"] = np.hypot(m.rec_x - m.gx, m.rec_y - m.gy)
    m["err_after_m"] = np.hypot(m.det_x - m.gx, m.det_y - m.gy)
    m["change_m"] = m.err_before_m - m.err_after_m          # positive = proposal moved the point closer
    ij = th.block_cells(np.c_[m.gx, m.gy], origin, size)
    m["block"] = [f"{a}_{b}" for a, b in ij]
    return m


def summarise(m: pd.DataFrame, G: pd.DataFrame, margin: float, B: int, seed: int) -> dict:
    out = {}
    for level, x in m.groupby("level"):
        blocks = sorted(x.block.unique())
        by = {b: x.loc[x.block == b, "change_m"].to_numpy() for b in blocks}

        def stat(bl):
            v = np.concatenate([by[b] for b in bl]) if bl else np.array([])
            return float(np.median(v)) if len(v) else float("nan")
        pt, lo, hi, _ = ek.block_bootstrap(stat, blocks, B=B, seed=seed)
        out[level] = dict(n=int(len(x)), n_blocks=len(blocks), median_change_m=pt, lo=lo, hi=hi,
                          wrong_matches=int((x.change_m < -margin).sum()),
                          superiority=ek.decide(lo, hi, margin, "superiority"),
                          noninferiority=ek.decide(lo, hi, margin, "noninferiority"),
                          few_blocks_warning=len(blocks) < 15)
    out["abstentions"] = int(len(set(G.PERMIT_NUM) - set(m.permit)))
    out["_note"] = "Pit and pad levels are never pooled. A pad centroid is not a borehole."
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--proposals")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    G = th.read_vector(th.inp(cfg, "gnss_points"))
    th.require_columns(G, ["PERMIT_NUM"], "gnss points")
    G["gx"], G["gy"] = G.geometry.x, G.geometry.y
    src = Path(a.proposals) if a.proposals else ppv.newest_proposals(cfg)
    m = paired_errors(pd.read_csv(src), pd.DataFrame(G.drop(columns="geometry")), cfg["block_origin"], cfg["block_m"])
    res = summarise(m, G, cfg["validation"]["margin_m"], cfg["validation"]["B"], int(cfg["seed"]) + 61)
    o1 = th.outp(cfg, "validation")
    m.to_csv(o1, index=False)
    o2 = th.write_json(th.outp(cfg, "validation_summary"), res)
    print(res, "\nwrote", o1, "\nwrote", o2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
