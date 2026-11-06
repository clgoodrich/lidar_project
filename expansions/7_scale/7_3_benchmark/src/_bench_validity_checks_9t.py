"""Benchmark validity checks H1, H2, H3 and the label ceiling (7.3 S4).

Purpose
    H1 known-difference control. Paired block bootstrap of model A minus model B (unetpp minus plain U-Net).
       Superiority test with threshold 0 (ek.decide).
    H2 sham control. Seed A minus seed B of one model. Passes if the interval contains 0 and the point
       estimate is under half the H1 point estimate.
    H3 projected width. Median 95% interval width when n_test blocks are drawn from the out-of-fold pool
       (ek.projected_width). The leaderboard margin is 0.03 (user default 2026-11-06, config). The H3 width
       target is still a user decision (config leaderboard.h3_width_target). While it is null the H3 decision
       stays pending. The framework rule 2 x margin is reported beside it for reference.
    Label ceiling. Second reviewer scored against the first annotator (IoU 0.3 one-to-one). A ceiling,
       not folded into any score.

Inputs
    Candidate and block CSVs written by _bench_evaluate_recall_k.py (--candidates-out, --blocks-out), one
    pair per arm, all scored on the same blocks. Second-reviewer and annotator GeoPackages for the ceiling.
Outputs
    --out JSON (default expansions/7_scale/7_3_benchmark/results/tables/bench_validity_terrain_v1.json)

Run
    python expansions/7_scale/7_3_benchmark/src/_bench_validity_checks_9t.py \
        --h1 unetpp_cands.csv unetpp_blocks.csv unet_cands.csv unet_blocks.csv \
        --h2 seedA_cands.csv seedA_blocks.csv seedB_cands.csv seedB_blocks.csv \
        --h3-pool unet_cands.csv unet_blocks.csv --n-test 24
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_evaluate_recall_k as sc  # noqa: E402

LEADERBOARD = json.loads((Path(__file__).resolve().parent / "config_7_3.json").read_text(encoding="utf-8"))["leaderboard"]


def h3_decision(width: float, n_test: int, margin: float, target: float | None) -> dict:
    """H3 with the leaderboard margin (default 0.03) and the open width target. Null target keeps it pending."""
    return {"median_width": width, "n_test": n_test, "margin": margin, "width_target": target,
            "framework_rule_2x_margin": 2 * margin, "passes_2x_margin_reference": bool(width <= 2 * margin),
            "decision": ("pending H3 width target (user decision)" if target is None
                         else "pass" if width <= target else "fail")}


def load_arm(cands_csv: str, blocks_csv: str):
    return pd.read_csv(cands_csv), pd.read_csv(blocks_csv)


def paired_diff(arm_a, arm_b, k_per_km2: float, B: int, seed: int):
    """Difference in pooled recall at K, A minus B, same resampled blocks for both arms."""
    ca, ba = arm_a
    cb, bb = arm_b
    common = sorted(set(ba["block_id"]) & set(bb["block_id"]))
    if set(ba["block_id"]) != set(bb["block_id"]):
        raise AssertionError("arms were scored on different blocks; a paired test needs the same blocks")
    pa = sc.payload_from_files(ca, ba, common, strict=True)
    pb = sc.payload_from_files(cb, bb, common, strict=True)
    idx = list(range(len(common)))
    fa = lambda ix: sc.pooled_recall([pa[i] for i in ix], k_per_km2)  # noqa: E731
    fb = lambda ix: sc.pooled_recall([pb[i] for i in ix], k_per_km2)  # noqa: E731
    point, lo, hi = ek.bootstrap_diff(fa, idx, fb, idx, B=B, seed=seed, paired=True)
    out = {"point": point, "lo": lo, "hi": hi, "n_blocks": len(common), "B": B}
    if len(common) < 15:
        out["permutation"] = sign_flip_interval(pa, pb, k_per_km2, B, seed)
        out["note"] = "fewer than 15 blocks. The bootstrap is unreliable. See the permutation result."
    return out


def sign_flip_interval(pa, pb, k_per_km2, B, seed):
    """Paired permutation. Swap arm labels per block at random. Returns observed diff and two-sided p."""
    rng = np.random.default_rng(seed + 1)
    obs = sc.pooled_recall(pa, k_per_km2) - sc.pooled_recall(pb, k_per_km2)
    null = []
    for _ in range(B):
        flip = rng.random(len(pa)) < 0.5
        a = [pb[i] if f else pa[i] for i, f in enumerate(flip)]
        b = [pa[i] if f else pb[i] for i, f in enumerate(flip)]
        null.append(sc.pooled_recall(a, k_per_km2) - sc.pooled_recall(b, k_per_km2))
    null = np.asarray(null)
    return {"observed": float(obs), "p_two_sided": float((np.sum(np.abs(null) >= abs(obs)) + 1) / (B + 1))}


def h3_width(pool_arm, n_test: int, k_per_km2: float, B: int, seed: int, reps: int = 50):
    c, b = pool_arm
    payload = sc.payload_from_files(c, b, strict=True)
    return ek.projected_width(lambda bl: sc.pooled_recall(bl, k_per_km2), payload, n_target=n_test, B=B,
                              reps=reps, seed=seed)


def label_ceiling(second_gpkg: str, first_gpkg: str, layer: str, iou_thr: float = 0.3):
    import geopandas as gpd
    s = gpd.read_file(second_gpkg, layer=layer)
    f = gpd.read_file(first_gpkg, layer=layer).to_crs(s.crs)
    s = s.reset_index(drop=True)
    s["cand_id"] = [f"r{i:06d}" for i in range(len(s))]
    f = f.reset_index(drop=True)
    f["truth_id"] = [f"t{i:06d}" for i in range(len(f))]
    m, _ = sc.match_greedy_iou(s, f, iou_thr)
    k = len({x for x in m if x is not None})
    p, lo, hi = ek.clopper_pearson(k, len(f))
    return {"matched": k, "n_first": len(f), "n_second": len(s), "recall_ceiling": p, "lo": lo, "hi": hi,
            "method": "second reviewer as candidates, greedy IoU 0.3, Clopper-Pearson (features not independent)"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Benchmark validity checks (7.3 S4).")
    ap.add_argument("--h1", nargs=4, metavar=("A_CANDS", "A_BLOCKS", "B_CANDS", "B_BLOCKS"))
    ap.add_argument("--h2", nargs=4, metavar=("S1_CANDS", "S1_BLOCKS", "S2_CANDS", "S2_BLOCKS"))
    ap.add_argument("--h3-pool", nargs=2, metavar=("CANDS", "BLOCKS"))
    ap.add_argument("--n-test", type=int, default=None, help="hidden-test block count")
    ap.add_argument("--margin", type=float, default=LEADERBOARD["margin"],
                    help="leaderboard margin. Default config 0.03 (user default 2026-11-06)")
    ap.add_argument("--width-target", type=float, default=LEADERBOARD.get("h3_width_target"),
                    help="H3 width target. Default config (null, still a user decision)")
    ap.add_argument("--ceiling", nargs=3, metavar=("SECOND_GPKG", "FIRST_GPKG", "LAYER"))
    ap.add_argument("--k-per-km2", type=float, default=ek.PROPOSAL_POLICY["k_per_km2"])
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261105)
    ap.add_argument("--out", default=str(ek.sub("7.3", "results/tables") / "bench_validity_terrain_v1.json"))
    a = ap.parse_args(argv)
    for grp in (a.h1, a.h2, a.h3_pool, a.ceiling[:2] if a.ceiling else None):
        for p in grp or []:
            if not Path(p).exists():
                print(f"missing input: {p}", file=sys.stderr)
                return 2
    res: dict = {"evidence_level": "a", "k_per_km2": a.k_per_km2}
    if a.h1:
        h1 = paired_diff(load_arm(*a.h1[:2]), load_arm(*a.h1[2:]), a.k_per_km2, a.B, a.seed)
        h1["decision"] = ek.decide(h1["lo"], h1["hi"], 0.0, "superiority")
        res["H1_known_difference"] = h1
    if a.h2:
        h2 = paired_diff(load_arm(*a.h2[:2]), load_arm(*a.h2[2:]), a.k_per_km2, a.B, a.seed)
        contains0 = h2["lo"] <= 0 <= h2["hi"]
        small = ("H1_known_difference" in res and abs(h2["point"]) < 0.5 * abs(res["H1_known_difference"]["point"]))
        h2["decision"] = "pass" if contains0 and small else "fail" if not contains0 else "pending H1" if "H1_known_difference" not in res else "fail"
        res["H2_sham"] = h2
    if a.h3_pool:
        if a.n_test is None:
            print("--n-test is required for H3", file=sys.stderr)
            return 2
        w = h3_width(load_arm(*a.h3_pool), a.n_test, a.k_per_km2, a.B, a.seed)
        res["H3_projected_width"] = h3_decision(w, a.n_test, a.margin, a.width_target)
    if a.ceiling:
        res["label_ceiling"] = label_ceiling(*a.ceiling)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    print(json.dumps(res, indent=2, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
