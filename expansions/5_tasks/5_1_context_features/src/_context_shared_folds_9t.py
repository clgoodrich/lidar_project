"""5.1 S1. One shared block-fold scheme for pit, pad and road models (tile 9t).

Purpose
    Assign every 375 m block of 9t to one outer fold so that pit, pad and road models can be stacked without
    leakage (protocol section 8). Balance pit count and pad count jointly by greedy deficit. Audit blocks from
    P2 are excluded before assignment and listed separately. Ordering is deterministic. Block ids are sorted
    integers and the only randomness is one seeded permutation for tie order (never a Python set order, which
    caused the inner-split drift in protocol section 3).

Algorithm
    1. Blocks = all blocks of the pit grid (144 on 9t), with n_pits and n_pads (0 where none). NaN ids rejected.
    2. Drop audit blocks.
    3. Order by n_pits + n_pads descending, ties by a seeded permutation.
    4. Each block goes to the fold whose larger post-assignment share, max(pit_f / pit_total, pad_f / pad_total),
       is lowest (joint deficit, so neither count can run ahead). The sum of shares breaks near-ties.
       Ties go to the fold with fewer blocks, then the lower fold number. Empty blocks go to the fold with the
       fewest blocks.

Inputs (config_5_1.json)
    inputs.pit_blocks    @nine_t/pit_blocks_9t.gpkg   (data/9t/derived/05/pit_blocks_9t.gpkg, layer blocks)
    inputs.pad_blocks    @nine_t/pad_blocks_9t.gpkg   (layer blocks)
    inputs.audit_blocks  @results_9t/splits/audit_blocks_9t_v1.csv  ASSUMED (P2 S2). Column block_id.
Outputs
    outputs.shared_folds              -> expansions/5_tasks/5_1_context_features/results/tables/shared_folds_9t_v1.json
    outputs.shared_folds_provisional  -> .../results/tables/shared_folds_9t_provisional.json (with --allow-no-audit)
    The provisional file must not feed any retraining. It exists to test the pipeline.
Run
    python expansions/5_tasks/5_1_context_features/src/_context_shared_folds_9t.py
    python expansions/5_tasks/5_1_context_features/src/_context_shared_folds_9t.py --allow-no-audit
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek


def assign_shared(blocks: pd.DataFrame, k: int, seed: int, audit: list[int] | None = None) -> dict[int, int]:
    """blocks has block_id, n_pits, n_pads. Returns block_id -> fold for non-audit blocks."""
    ek.assert_no_nan(blocks["block_id"], "block_id")
    ek.assert_unique(blocks, "block_id")
    b = blocks.copy()
    b["block_id"] = b["block_id"].astype(int)
    b = b.sort_values("block_id").reset_index(drop=True)
    audit = sorted({int(x) for x in (audit or [])})
    b = b[~b.block_id.isin(audit)].reset_index(drop=True)
    rng = np.random.default_rng(seed)
    b["tie"] = rng.permutation(len(b))
    b["load"] = b.n_pits + b.n_pads
    b = b.sort_values(["load", "tie"], ascending=[False, True]).reset_index(drop=True)
    tp, td = max(b.n_pits.sum(), 1), max(b.n_pads.sum(), 1)
    pit_f, pad_f, nb = np.zeros(k), np.zeros(k), np.zeros(k, int)
    out = {}
    for r in b.itertuples(index=False):
        a_, b_ = (pit_f + r.n_pits) / tp, (pad_f + r.n_pads) / td
        cost = np.maximum(a_, b_) + 1e-3 * (a_ + b_)      # minimax on the two shares, then their sum
        if r.load == 0:   # empty blocks spread by block count, so every fold scores some empty ground
            order = np.lexsort((np.arange(k), np.round(cost, 12), nb))
        else:
            order = np.lexsort((np.arange(k), nb, np.round(cost, 12)))
        f = int(order[0])
        out[int(r.block_id)] = f
        pit_f[f] += r.n_pits
        pad_f[f] += r.n_pads
        nb[f] += 1
    return dict(sorted(out.items()))


def fold_summary(blocks: pd.DataFrame, m: dict[int, int], k: int) -> list[dict]:
    b = blocks.assign(fold=blocks.block_id.astype(int).map(m)).dropna(subset=["fold"])
    rows = []
    for f in range(k):
        s = b[b.fold == f]
        rows.append(dict(fold=f, n_blocks=int(len(s)), n_pits=int(s.n_pits.sum()), n_pads=int(s.n_pads.sum()),
                         n_empty_blocks=int(((s.n_pits + s.n_pads) == 0).sum())))
    return rows


def load_blocks(cfg: dict) -> pd.DataFrame:
    pit = th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")
    pad = th.read_vector(th.inp(cfg, "pad_blocks"), layer="blocks")
    b = pit[["block_id", "n_pits"]].merge(pad[["block_id", "n_pads"]], on="block_id", how="outer")
    b = b.fillna({"n_pits": 0, "n_pads": 0}).astype({"n_pits": int, "n_pads": int})
    ek.assert_rows(b, len(pit), "pit and pad block grids share block ids")
    return b


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--allow-no-audit", action="store_true",
                    help="write a PROVISIONAL fold file when the P2 audit list is missing")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    blocks = load_blocks(cfg)
    provisional = False
    if th.has(cfg, "audit_blocks"):
        audit = pd.read_csv(th.inp(cfg, "audit_blocks"))
        th.require_columns(audit, ["block_id"], "audit_blocks")
        audit_ids = sorted(audit.block_id.dropna().astype(int).unique().tolist())
    elif a.allow_no_audit:
        audit_ids, provisional = [], True
        print("WARNING. No P2 audit list. Writing a PROVISIONAL fold file. Do not retrain on it.")
    else:
        th.inp(cfg, "audit_blocks")  # raises MissingInput with the hint
    k, seed = int(cfg["n_folds"]), int(cfg["seed"])
    m = assign_shared(blocks, k, seed, audit_ids)
    ek.assert_disjoint(m.keys(), audit_ids, "audit blocks in folds")
    body = {"block_to_fold": {str(b): f for b, f in m.items()}}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    doc = dict(version="v1", provisional=provisional, written=dt.datetime.now().isoformat(timespec="seconds"),
               seed=seed, k=k, rule="greedy joint deficit on pit and pad counts, ties by seeded permutation",
               audit_blocks=audit_ids, n_blocks=len(m), folds=fold_summary(blocks, m, k),
               assignment_sha256=digest, **body)
    out = th.outp(cfg, "shared_folds_provisional" if provisional else "shared_folds")
    th.write_json(out, doc)
    print(pd.DataFrame(doc["folds"]).to_string(index=False))
    print(f"wrote {out}  (sha256 {digest[:12]})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except th.MissingInput as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(2)
