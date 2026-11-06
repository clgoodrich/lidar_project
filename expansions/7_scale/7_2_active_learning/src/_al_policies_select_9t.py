"""Selection policies with exact inclusion probabilities, and the per-round batch draw (7.2 S3 step 1).

Purpose
    Every policy draws by Poisson sampling. Item i enters the batch independently with probability
    pi_i = min(1, c w_i), where w_i is the policy weight and c is set by bisection so the expected
    reviewer-minutes of the batch equal the batch budget. pi_i is therefore known exactly for every
    item, is above 0 for every eligible item, and feeds inverse-probability weights and Horvitz-Thompson
    estimates (fw_7_2 section 8). Sampling, not top-k.
    R  uniform over candidates (type C)
    U  softmax of binary entropy of the candidate score, temperature T
    B  U divided by the square root of the candidate count in the same tile (spreads the batch)
    D  uniform over random discovery windows (type W, one 375 m block annotated in full)
    H  70% of the minute budget to U and 30% to D, drawn as two independent parts
    Items already labelled are not eligible. Stopping and audit blocks never enter a pool (asserted).

Inputs
    --pool    item table CSV (item_id, type C or W, block_id, tile_id, score, area_m2, cx, cy, cost_min)
    --split   al_split_9t_v1.json from _al_split_pool_stop_9t.py
    --labelled  optional CSV of item_id already labelled
Outputs (round folder, default expansions/7_scale/7_2_active_learning/results/live/round_<nn>/)
    batch_<policy>.csv           selected items with pi
    inclusion_log.csv            every eligible item, policy, round, pi, selected, model hash, seed

Run
    python expansions/7_scale/7_2_active_learning/src/_al_policies_select_9t.py --pool pool.csv --round 1 \
        --policies R U H --model-hash <sha256 of the round model>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

HERE = Path(__file__).resolve().parent
CFG = HERE / "config_7_2.json"
POLICIES = ("R", "U", "D", "H", "B")


def load_cfg(path: Path = CFG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cfg_path(entry: dict) -> Path:
    return ek.path_for(entry["key"]) / entry["rel"]


def need(path: Path, what: str) -> Path:
    if not Path(path).exists():
        raise FileNotFoundError(f"missing input for 7.2 ({what}): {path}. See config_7_2.json")
    return Path(path)


# ----------------------------------------------------------------------------- weights
def entropy(p) -> np.ndarray:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(p * np.log(p) + (1 - p) * np.log(1 - p))


def weights(items: pd.DataFrame, spec: dict) -> np.ndarray:
    kind = spec["weight"]
    if kind == "uniform":
        return np.ones(len(items))
    h = entropy(items["score"]) / np.log(2)          # 0 to 1
    w = np.exp((h - h.max()) / spec["temperature"])
    if kind == "entropy_softmax_tile_cap":
        n_tile = items.groupby("tile_id")["item_id"].transform("count").to_numpy()
        w = w / np.sqrt(n_tile)
    return w / w.sum()


def poisson_pi(w: np.ndarray, cost: np.ndarray, budget: float) -> np.ndarray:
    """pi = min(1, c w) with sum(pi cost) = budget (or every item when the budget covers all)."""
    w = np.asarray(w, float); cost = np.asarray(cost, float)
    if len(w) == 0:
        return w
    if (cost.sum() <= budget) or budget <= 0:
        return np.ones(len(w)) if budget > 0 else np.zeros(len(w))
    lo, hi = 0.0, 1.0 / max(w[w > 0].min(), 1e-300)
    for _ in range(200):
        c = 0.5 * (lo + hi)
        if (np.minimum(1.0, c * w) * cost).sum() > budget:
            hi = c
        else:
            lo = c
    return np.minimum(1.0, lo * w)


def draw_policy(pool: pd.DataFrame, policy: str, cfg: dict, budget_min: float, rng: np.random.Generator) -> pd.DataFrame:
    """Return the eligible items of this policy with pi and selected columns."""
    pspec = cfg["policies"][policy]
    if "parts" in pspec:
        parts = [draw_policy(pool, p["policy"], cfg, budget_min * p["share"], rng) for p in pspec["parts"]]
        out = pd.concat(parts, ignore_index=True)
        out["policy"] = policy
        return out
    el = pool[pool["type"] == pspec["pool"]].reset_index(drop=True).copy()
    el["pi"] = poisson_pi(weights(el, pspec), el["cost_min"].to_numpy(), budget_min) if len(el) else []
    el["selected"] = rng.random(len(el)) < el["pi"].to_numpy() if len(el) else []
    el["policy"] = policy
    return el


def eligible_pool(items: pd.DataFrame, split: dict, labelled: set) -> pd.DataFrame:
    stop = set(split["stopping"]) | set(split.get("audit", []))
    bad = items[items["block_id"].isin(stop)]
    if len(bad):
        raise AssertionError(f"{len(bad)} pool items sit in stopping or audit blocks")
    ek.assert_unique(items, "item_id")
    return items[~items["item_id"].isin(labelled)].reset_index(drop=True)


def select_round(items, split, labelled, policies, cfg, rnd: int, seed: int, model_hash: str) -> dict[str, pd.DataFrame]:
    pool = eligible_pool(items, split, labelled)
    out = {}
    for i, pol in enumerate(policies):
        rng = np.random.default_rng(ek.child_seed(seed, rnd, i))
        d = draw_policy(pool, pol, cfg, cfg["batch_minutes"], rng)
        if len(d) and (d["pi"] <= 0).any():
            raise AssertionError(f"policy {pol}: an eligible item has pi = 0 (bug)")
        d["round"] = rnd
        d["model_hash"] = model_hash
        d["selection_seed"] = ek.child_seed(seed, rnd, i)
        out[pol] = d
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.2 per-round batch draw.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--pool", required=True)
    ap.add_argument("--split", default=str(ek.sub("7.2", "results/tables") / "al_split_9t_v1.json"))
    ap.add_argument("--labelled", default=None)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--policies", nargs="+", default=["R", "U", "H"], choices=POLICIES)
    ap.add_argument("--model-hash", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    try:
        items = pd.read_csv(need(Path(a.pool), "item pool"))
        split = json.loads(need(Path(a.split), "AL split (run _al_split_pool_stop_9t.py)").read_text())
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    lab = set(pd.read_csv(a.labelled)["item_id"]) if a.labelled else set()
    out = Path(a.out) if a.out else ek.sub("7.2", f"results/live/round_{a.round:02d}")
    out.mkdir(parents=True, exist_ok=True)
    res = select_round(items, split, lab, a.policies, cfg, a.round, cfg["master_seed"], a.model_hash)
    log = []
    for pol, d in res.items():
        d[d["selected"]].to_csv(out / f"batch_{pol}.csv", index=False)
        log.append(d[["item_id", "type", "policy", "round", "pi", "selected", "model_hash", "selection_seed"]])
        print(f"{pol}: {int(d['selected'].sum())} items, expected minutes {float((d['pi'] * d['cost_min']).sum()):.0f}")
    lp = out / "inclusion_log.csv"
    pd.concat(log).to_csv(lp, mode="a", header=not lp.exists(), index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
