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
    P2 audit CSV (config inputs.audit_blocks), read only through ek.require_audit (review 7.1-01).
    Audit and buffer blocks leave train and inner validation. Audit blocks also leave the held-out lists.
    A missing audit file stops the run unless --allow-no-audit. The JSON is then labelled
    "no audit exclusion, exploratory".
Outputs
    expansions/7_scale/7_1_pretraining/data/processed/ssl_label_subsets_9t.json
        {"split_source", "audit_guard", "audit_sha256", "audit_excluded", "buffer_excluded", "folds": [...], "subsets": {"<fold>|<seed>|<f>": {"blocks": [...], "sha256": ...}},
         "empty_share": {f: share}, "dropped_fractions": [...]}

Run
    python expansions/7_scale/7_1_pretraining/src/_ssl_label_subsets_9t.py
    python expansions/7_scale/7_1_pretraining/src/_ssl_label_subsets_9t.py --historical
    python expansions/7_scale/7_1_pretraining/src/_ssl_label_subsets_9t.py --historical --allow-no-audit   (exploratory)
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


NO_AUDIT = "no audit exclusion, exploratory"


def audit_sets(cfg: dict, audit_csv: Path | None = None, allow_no_audit: bool = False,
               allow_unfrozen: bool = False) -> dict:
    """P2 audit through the shared reader. Never an empty set in place of a missing file (7.1-01)."""
    p = Path(audit_csv) if audit_csv is not None else cfg_path(cfg["inputs"]["audit_blocks"])
    df = ek.require_audit(p, allow_missing=allow_no_audit, allow_unfrozen=allow_unfrozen)
    if df is None:
        return {"guard": NO_AUDIT, "sha256": None, "audit": set(), "buffer": set(), "path": str(p)}
    aud = ek.audit_ids(df, ("audit",))
    return {"guard": "P2 audit list applied", "sha256": df.attrs.get("sha256"), "audit": aud,
            "buffer": ek.audit_ids(df) - aud, "path": str(p)}


def exclude_audit(folds: list[dict], au: dict) -> list[dict]:
    """Audit and buffer blocks never train or validate. Audit blocks are never scored as held-out."""
    no_train = au["audit"] | au["buffer"]
    return [{"fold": f["fold"], "train": [b for b in f["train"] if b not in no_train],
             "val": [b for b in f["val"] if b not in no_train],
             "heldout": [b for b in f["heldout"] if b not in au["audit"]]} for f in folds]


def build(cfg: dict, historical: bool, audit: dict | None = None) -> dict:
    """audit is the dict from audit_sets(). It is required (pass audit_sets(cfg, allow_no_audit=True)
    explicitly for an exploratory run)."""
    if audit is None:
        raise ValueError("build() needs the audit dict from audit_sets(). It never assumes an empty audit set")
    import geopandas as gpd
    b = gpd.read_file(need(cfg_path(cfg["inputs"]["blocks_9t"]), "blocks"))
    ek.assert_unique(b, "block_id")
    n_feat = dict(zip(b["block_id"].astype(int), b["n_feat"].fillna(0).astype(int)))
    ft = cfg["finetune"]
    folds = (folds_historical(cfg_path(cfg["inputs"]["split_historical"]), cfg["master_seed"],
                              ft["inner_val_share_historical"]) if historical
             else folds_future(cfg_path(cfg["inputs"]["split_future"])))
    folds = exclude_audit(folds, audit)
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
    for f in folds:
        ek.assert_disjoint(f["train"] + f["val"], audit["audit"] | audit["buffer"], f"fold {f['fold']} train/val vs audit")
        ek.assert_disjoint(f["heldout"], audit["audit"], f"fold {f['fold']} heldout vs audit")
    return {"split_source": "historical PROVISIONAL" if historical else "P1 future", "audit_guard": audit["guard"],
            "audit_sha256": audit["sha256"], "audit_path": audit["path"],
            "audit_excluded": sorted(int(b) for b in audit["audit"]),
            "buffer_excluded": sorted(int(b) for b in audit["buffer"]), "folds": folds,
            "subsets": subsets, "empty_share": empty_share,
            "dropped_fractions": [k for k, v in empty_share.items() if v > 0.20]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Nested label subsets (7.1).")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--historical", action="store_true")
    ap.add_argument("--audit", default=None, help="P2 audit CSV (default config inputs.audit_blocks)")
    ap.add_argument("--allow-no-audit", action="store_true",
                    help="run without the P2 audit file. The output is labelled 'no audit exclusion, exploratory'")
    ap.add_argument("--out", default=str(ek.sub("7.1", "data/processed") / "ssl_label_subsets_9t.json"))
    a = ap.parse_args(argv)
    try:
        cfg = load_cfg(Path(a.config))
        res = build(cfg, a.historical, audit_sets(cfg, Path(a.audit) if a.audit else None, a.allow_no_audit))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({"split_source": res["split_source"], "audit_guard": res["audit_guard"], "n_subsets": len(res["subsets"]),
                      "empty_share": res["empty_share"], "dropped": res["dropped_fractions"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
