"""Nested, stratified label-fraction subsets of training blocks per fold and seed (7.1 S3 prerequisite).

Purpose
    Label fraction f is the share of a fold's training blocks whose labels the fine-tune may use.
    Blocks are stratified by feature-count tercile (pit-bearing blocks) plus one stratum for blocks with
    no pits. A seeded permutation inside each stratum is cut at ceil(f x n), so the 5% set sits inside
    the 10% set and so on. The same subset is used by every arm for a given seed (fw_7_1 section 9 item 4).
    Each subset gets a SHA-256 hash. A fraction is flagged when over 20% of its subsets hold no pits.

Inputs
    blocks GeoPackage with block_id and n_feat (config inputs.blocks_9t, held)
    future split JSON from P1 (config inputs.split_future), wellsight.cv_splits.v1.
    Uses the pit task and verifies its content hash through the producer's reader.
    --historical builds a PROVISIONAL split from the held historical held-out lists. Inner validation is
    then a seeded 15% of the training blocks. It is labelled provisional and never feeds the primary claim.
Outputs
    expansions/7_scale/7_1_pretraining/data/processed/ssl_label_subsets_9t.json
        {"split_source", "folds": [...], "subsets": {"<fold>|<seed>|<f>": {"blocks": [...], "sha256": ...}},
         "empty_share": {f: share}, "dropped_fractions": [...]}

Run
    python expansions/7_scale/7_1_pretraining/src/_ssl_label_subsets_9t.py
    python expansions/7_scale/7_1_pretraining/src/_ssl_label_subsets_9t.py --historical
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ssl_pretrain_objectives_us import CFG, cfg_path, ek, load_cfg, need  # noqa: E402


def folds_future(path: Path) -> list[dict]:
    sys.path.insert(0, str(ek.sub("p1", "src")))
    from _split_future_write_9t import split_file_for
    folds = split_file_for("pit", need(path, "P1 future split"))
    return [{"fold": k, "train": sorted(map(int, f["train"])), "val": sorted(map(int, f["inner_val"])),
             "heldout": sorted(map(int, f["held_out"]))} for k, f in sorted(folds.items())]


def folds_historical(path: Path, master: int, val_share: float) -> list[dict]:
    h = pd.read_csv(need(path, "historical split"))
    h = h[h["role"].astype(str).str.startswith("held")].dropna(subset=["block_id"])
    held = {int(k): sorted(int(b) for b in g["block_id"]) for k, g in h.groupby("fold")}
    allb = sorted(set().union(*held.values()))
    out = []
    for k in sorted(held):
        rest = [b for b in allb if b not in set(held[k])]
        rng = np.random.default_rng(ek.child_seed(master, k, 0))
        perm = list(rng.permutation(rest))
        nv = max(1, int(round(val_share * len(rest))))
        out.append({"fold": k, "val": sorted(int(b) for b in perm[:nv]), "train": sorted(int(b) for b in perm[nv:]),
                    "heldout": held[k]})
    return out


def strata(train: list[int], n_feat: dict) -> dict[str, list[int]]:
    pos = [b for b in train if n_feat.get(b, 0) > 0]
    zero = [b for b in train if n_feat.get(b, 0) == 0]
    out = {"zero": sorted(zero)}
    if pos:
        q = np.quantile([n_feat[b] for b in pos], [1 / 3, 2 / 3])
        for b in pos:
            t = 0 if n_feat[b] <= q[0] else 1 if n_feat[b] <= q[1] else 2
            out.setdefault(f"t{t}", []).append(b)
    return {k: sorted(v) for k, v in out.items()}


def nested_subsets(train: list[int], n_feat: dict, fractions: list[float], seed: int) -> dict[float, list[int]]:
    rng = np.random.default_rng(seed)
    perms = {k: list(rng.permutation(v)) for k, v in sorted(strata(train, n_feat).items())}
    out = {}
    for f in sorted(fractions):
        sel = []
        for k, p in perms.items():
            sel += p[: min(len(p), math.ceil(f * len(p)))]
        out[f] = sorted(int(b) for b in sel)
    return out


def subset_hash(blocks: list[int]) -> str:
    return hashlib.sha256(json.dumps(sorted(blocks)).encode()).hexdigest()


def build(cfg: dict, historical: bool) -> dict:
    import geopandas as gpd
    b = gpd.read_file(need(cfg_path(cfg["inputs"]["blocks_9t"]), "blocks"))
    ek.assert_unique(b, "block_id")
    n_feat = dict(zip(b["block_id"].astype(int), b["n_feat"].fillna(0).astype(int)))
    ft = cfg["finetune"]
    folds = (folds_historical(cfg_path(cfg["inputs"]["split_historical"]), cfg["master_seed"],
                              ft["inner_val_share_historical"]) if historical
             else folds_future(cfg_path(cfg["inputs"]["split_future"])))
    for f in folds:
        ek.assert_disjoint(f["train"], f["heldout"], f"fold {f['fold']} train/heldout")
        ek.assert_disjoint(f["val"], f["heldout"], f"fold {f['fold']} val/heldout")
        ek.assert_disjoint(f["train"], f["val"], f"fold {f['fold']} train/val")
    subsets, empty = {}, {}
    for f in folds:
        for s in ft["seeds"]:
            ns = nested_subsets(f["train"], n_feat, ft["fractions"], ek.child_seed(cfg["master_seed"], f["fold"], 10 + s))
            prev: set = set()
            for frac in sorted(ns):
                cur = set(ns[frac])
                if not prev <= cur:
                    raise AssertionError("subsets are not nested")
                prev = cur
                subsets[f"{f['fold']}|{s}|{frac}"] = {"blocks": ns[frac], "sha256": subset_hash(ns[frac]),
                                                      "n_pit_blocks": int(sum(n_feat.get(x, 0) > 0 for x in ns[frac]))}
                empty.setdefault(frac, []).append(subsets[f"{f['fold']}|{s}|{frac}"]["n_pit_blocks"] == 0)
    empty_share = {str(k): float(np.mean(v)) for k, v in empty.items()}
    return {"split_source": "historical PROVISIONAL" if historical else "P1 future", "folds": folds,
            "subsets": subsets, "empty_share": empty_share,
            "dropped_fractions": [k for k, v in empty_share.items() if v > 0.20]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Nested label subsets (7.1).")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--historical", action="store_true")
    ap.add_argument("--out", default=str(ek.sub("7.1", "data/processed") / "ssl_label_subsets_9t.json"))
    a = ap.parse_args(argv)
    try:
        res = build(load_cfg(Path(a.config)), a.historical)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({"split_source": res["split_source"], "n_subsets": len(res["subsets"]),
                      "empty_share": res["empty_share"], "dropped": res["dropped_fractions"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
