"""3.0 S4. Projected interval width for a transfer test, before any annotation time is spent.

Purpose
    The pool is the 9t out-of-fold blocks at the primary K, with per-block hits and truth counts. For each
    planned target size n, draw n blocks from the pool `reps` times. For each draw, take the independent
    block-bootstrap interval of (target recall minus 9t recall) with `ek.bootstrap_diff`. Report the median
    interval width and, for each margin, the share of draws whose lower bound clears minus the margin. The
    draws have no true loss, so that share is the chance of a success verdict when transfer is perfect.
    fw_00 rule. If the median width exceeds twice the margin, change the design before labelling.
    `--density` restricts the pool to blocks within 50% of a target feature density, a crude way to
    forecast over plausible target densities.

Inputs
    default pool. The archival per-block counts rebuilt from the operating-point sweep at K (pit or pad)
    or --blocks-csv, a `transfer_blocks_<area>.csv` from `_transfer_score_run.py` (columns hits, n_truth, area_km2)

Outputs
    <out-dir>/projected_ci_width_<task>_9t.csv   n_blocks, median_width, p10/p90 width, share_success_<margin>
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/transfer/
    Run record under expansions/3_geography/3_0_transfer_protocol/results/<run_id>/

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_ci_width_9t.py --task pit [--k 40] [--n-blocks 10 20 30] [--margins 0.05 0.1]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _transfer_score_lib as tl  # noqa: E402
ek = tl.ek
CFG = json.loads((HERE.parent / "config_3_0.json").read_text(encoding="utf-8"))


def archival_pool(task: str, k: float) -> pd.DataFrame:
    """Per held-out block hits and truth at budget k, from the sweep's own fold data and rules."""
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2" / "s5_eval"))
    import _operating_point_policy_sweep_pit_pad_9t as ops
    rows = []
    for f in ops.fold_data(task):
        keep = ops.apply_rule(f, ops.rule_budget(f, k))
        for b in f["held_blocks"]:
            m = keep & (f["held_block"] == b)
            rows.append({"fold": f["k"], "block_id": int(b), "hits": int((m & f["held_tp"]).sum()),
                         "n_truth": int(f["held_gt"].get(int(b), 0)), "area_km2": float(f["area"][int(b)])})
    return pd.DataFrame(rows)


def projected(pool: pd.DataFrame, n_blocks, margins, reps: int, B: int, seed: int) -> pd.DataFrame:
    h, n = pool.hits.to_numpy(float), pool.n_truth.to_numpy(float)

    def stat(idx):
        idx = np.asarray(idx, int)
        d = n[idx].sum()
        return h[idx].sum() / d if d else np.nan

    ref = list(range(len(pool)))
    rng = np.random.default_rng(seed)
    out = []
    for nb in n_blocks:
        widths, los = [], []
        for r in range(reps):
            pick = list(rng.choice(len(pool), nb, replace=len(pool) < nb))
            _, lo, hi = ek.bootstrap_diff(stat, pick, stat, ref, B=B, seed=ek.child_seed(seed, r, nb))
            widths.append(hi - lo)
            los.append(lo)
        w, los = np.array(widths), np.array(los)
        row = {"n_blocks": nb, "median_width": float(np.nanmedian(w)), "p10_width": float(np.nanpercentile(w, 10)),
               "p90_width": float(np.nanpercentile(w, 90)), "reps": reps, "B": B}
        for m in margins:
            row[f"share_success_{m:g}"] = float(np.mean(los > -m))
            row[f"width_ok_{m:g}"] = bool(row["median_width"] <= 2 * m)
        out.append(row)
    return pd.DataFrame(out)


def main(argv=None) -> int:
    c = CFG["ci_width"]
    ap = argparse.ArgumentParser(description="3.0 S4 projected interval width")
    ap.add_argument("--task", choices=("pit", "pad"), default="pit")
    ap.add_argument("--k", type=float, default=CFG["scoring_defaults"]["k_per_km2"])
    ap.add_argument("--blocks-csv", type=Path, default=None)
    ap.add_argument("--n-blocks", type=int, nargs="+", default=c["n_blocks"])
    ap.add_argument("--margins", type=float, nargs="+", default=c["margins"])
    ap.add_argument("--reps", type=int, default=c["reps"])
    ap.add_argument("--B", type=int, default=c["B"])
    ap.add_argument("--seed", type=int, default=c["seed"])
    ap.add_argument("--density", type=float, default=None, help="features per km2 to centre the pool on")
    ap.add_argument("--out-dir", type=Path, default=None)
    a = ap.parse_args(argv)
    pool = pd.read_csv(a.blocks_csv) if a.blocks_csv else archival_pool(a.task, a.k)
    if a.density is not None:
        dens = pool.n_truth / pool.area_km2
        pool = pool[(dens >= 0.5 * a.density) & (dens <= 1.5 * a.density)].reset_index(drop=True)
        if len(pool) < 10:
            raise SystemExit(f"only {len(pool)} 9t blocks lie within 50% of density {a.density}. Forecast not possible.")
    t = projected(pool, a.n_blocks, a.margins, a.reps, a.B, a.seed)
    t["k_per_km2"], t["task"], t["pool_blocks"] = a.k, a.task, len(pool)
    out = a.out_dir or (ek.area_dir("9t") / "results" / "transfer")
    out.mkdir(parents=True, exist_ok=True)
    csv = out / f"projected_ci_width_{a.task}_9t.csv"
    t.to_csv(csv, index=False)
    run = ek.new_run("3.0", f"ci_width_{a.task}", {k: str(v) for k, v in vars(a).items()}, why="S4 projected width.")
    ek.write_provenance(run, inputs=[a.blocks_csv] if a.blocks_csv else [], outputs=[csv], seeds={"draw": a.seed})
    print(t.to_string(index=False))
    print(f"wrote {csv}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
