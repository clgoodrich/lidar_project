"""5.4 S5. Two-source capture-recapture diagnostic (records and detector). Not a lower bound.

Purpose
    Source 1 is the documented population N_doc (DEP wells in the footprint). Source 2 is the detector's candidate
    sites scaled by an assumed well share p (n2 = D_sites x p). The overlap is the number of documented wells with a
    candidate site within radius_m under one-to-one assignment, scaled by an assumed link precision q (the share of
    those links that are the same well, unknown until 5.6 adjudication). Chapman estimator per (p, q), pooled and
    stratified by block halves of record density. A large pooled-minus-stratified gap shows capture heterogeneity.
    When q equals p the two scalings cancel, so the grid keeps them separate.
    Assumptions it needs and that likely fail here. Independent sources, closed population, homogeneous capture.
    Records cluster where drilling was permitted and lidar sees cleared ground better, so positive dependence is
    likely and the pooled estimate is biased low. It is a diagnostic, not a floor.

Inputs (config_5_4.json)
    sites, accounting (S1), dep_wells, pit_blocks
Outputs
    expansions/5_tasks/5_4_undocumented_density/results/tables/density_capture_recapture_9t.csv
Run
    python expansions/5_tasks/5_4_undocumented_density/src/_density_capture_recapture_9t.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402
import _records_assoc_core as core  # noqa: E402
import _density_distinct_wells_9t as dw  # noqa: E402

ek = th.ek


def chapman(n1: float, n2: float, m: float) -> tuple[float, float]:
    """Chapman (1951) estimate and variance. Inputs may be fractional when scaled by p."""
    m = min(m, n1, n2)
    N = (n1 + 1) * (n2 + 1) / (m + 1) - 1
    var = (n1 + 1) * (n2 + 1) * (n1 - m) * (n2 - m) / ((m + 1) ** 2 * (m + 2))
    return float(N), float(var)


def strata_counts(sites, wells, matched_wells, blocks_ids, rec_per_block):
    med = np.median([rec_per_block.get(b, 0) for b in blocks_ids])
    hi = {b for b in blocks_ids if rec_per_block.get(b, 0) > med}
    out = {}
    for name, ids in (("high_record_density", hi), ("low_record_density", set(blocks_ids) - hi)):
        out[name] = dict(n1=int(wells.block_id.isin(ids).sum()), n_sites=int(sites.block_id.isin(ids).sum()),
                         overlap=int(matched_wells.block_id.isin(ids).sum()), blocks=len(ids))
    return out


def run(cfg) -> pd.DataFrame:
    sites = pd.read_csv(th.inp(cfg, "sites"))
    blocks = th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")
    fp = blocks[blocks.n_pits > 0]
    ids = sorted(fp.block_id.astype(int))
    dep = th.load_dep(th.inp(cfg, "dep_wells"), bbox=tuple(fp.total_bounds))
    dep = dep[~dep.WELL_STATU.isin(cfg["doc_statuses_exclude"])].copy()
    dep["block_id"] = th.block_id_of(np.c_[dep.x, dep.y], blocks)
    dep = dep[dep.block_id.isin(ids)].reset_index(drop=True)
    lab = dw.merge_points(np.c_[dep.x, dep.y], cfg["record_merge_m"])
    wells = dep.groupby(lab).agg(x=("x", "mean"), y=("y", "mean"), block_id=("block_id", "first")).reset_index(drop=True)
    i, j, _ = core.hungarian(np.c_[wells.x, wells.y], np.c_[sites.cx, sites.cy], cfg["capture_recapture"]["radius_m"])
    matched = wells.iloc[i]
    rpb = wells.groupby("block_id").size().to_dict()
    st = strata_counts(sites, wells, matched, ids, rpb)
    rows = []
    for p in cfg["capture_recapture"]["p_values"]:
        for q in cfg["capture_recapture"]["q_values"]:
            N, v = chapman(len(wells), len(sites) * p, len(matched) * q)
            Ns = sum(chapman(s["n1"], s["n_sites"] * p, s["overlap"] * q)[0] for s in st.values())
            rows.append(dict(p=p, q_link_precision=q, n1_records=len(wells), n2_expected_wells=len(sites) * p,
                             links=len(matched), overlap_scaled=min(len(matched) * q, len(wells), len(sites) * p),
                             chapman_pooled=N, chapman_se=np.sqrt(max(v, 0)), chapman_stratified=Ns,
                             heterogeneity_gap=Ns - N, undocumented_pooled=N - len(wells),
                             degenerate=int(len(matched) * q >= min(len(wells), len(sites) * p)),
                             label="diagnostic, not a lower bound; assumes independence and closure"))
    R = th.tag(pd.DataFrame(rows), "a", "diagnostic")
    R.attrs["strata"] = st
    return R


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    R = run(cfg)
    out = th.outp(cfg, "capture")
    R.to_csv(out, index=False)
    th.write_json(out.with_suffix(".json"), dict(strata=R.attrs["strata"], radius_m=cfg["capture_recapture"]["radius_m"]))
    print(R.round(1).to_string(index=False), "\nwrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
