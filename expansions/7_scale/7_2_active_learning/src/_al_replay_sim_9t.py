"""Simulation replay of the selection policies on existing labels (7.2 S1). Exploratory, level (a).

Purpose
    Choose temperature, batch size and hybrid split, and find bugs, before any reviewer time is spent.
    The oracle is the same annotator's drawn labels, so the replay is never evidence for the live claim.
    Each policy starts from the same round-0 labelled set and keeps its own labelled set afterwards.
    Each round. Draw the batch with exact pi (_al_policies_select_9t.py). Label from the oracle. Charge
    the simulated minutes. Refit the learner with inverse-probability weights (1 / pi, self-normalised,
    clipped at the 95th percentile). Re-rank the stopping-set candidates and score recall at K.
    The default learner is a logistic re-ranker on candidate score, area and circularity. It is cheap and real but it
    can only re-rank proposals. It cannot learn from discovery windows. The live loop retrains the U-Net
    (_al_retrain_round_9t.py), which can. D windows still cost minutes and add to discovery yield here.

Inputs (from _al_split_pool_stop_9t.py --build-items)
    al_items_9t.csv, al_oracle_9t.csv, al_stop_cands_9t.csv, al_stop_blocks_9t.csv, al_split_9t_v1.json
Outputs (expansions/7_scale/7_2_active_learning/results/tables/)
    al_replay_curves_9t.csv    policy, seed, round, cum_minutes, n_labels, n_C, n_W, recall_stop, discovered
    al_replay_scores_9t.csv.gz policy, seed, round, cand_id, score (stopping-set re-ranked scores)
    al_replay_inclusion_9t.csv.gz  every eligible item per round with pi and selected

Run
    python expansions/7_scale/7_2_active_learning/src/_al_replay_sim_9t.py --seeds 10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _al_policies_select_9t import CFG, ek, load_cfg, need, select_round  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "7_3_benchmark" / "src"))
import _bench_evaluate_recall_k as sc  # noqa: E402


def ipw(pi: np.ndarray, clip_q: float | None) -> np.ndarray:
    w = 1.0 / np.asarray(pi, float)
    if clip_q is not None and len(w):
        w = np.minimum(w, np.quantile(w, clip_q))
    return w / w.mean() if len(w) else w


def features(df: pd.DataFrame) -> np.ndarray:
    """Logit score, log area, and circularity with its square when present (shape lets the learner re-rank)."""
    p = np.clip(df["score"].to_numpy(float), 1e-4, 1 - 1e-4)
    cols = [np.log(p / (1 - p)), np.log1p(df["area_m2"].to_numpy(float))]
    if "circ" in df.columns:
        c = df["circ"].fillna(0).to_numpy(float)
        cols += [c, c * c]
    return np.column_stack(cols)


def fit_rerank(lab: pd.DataFrame, stop: pd.DataFrame, clip_q) -> np.ndarray:
    """Logistic re-ranker. Falls back to the raw score with fewer than 2 classes."""
    y = lab["y"].to_numpy(int)
    if len(lab) < 4 or len(set(y)) < 2:
        return stop["score"].to_numpy(float)
    from sklearn.linear_model import LogisticRegression
    m = LogisticRegression(max_iter=1000).fit(features(lab), y, sample_weight=ipw(lab["pi"], clip_q))
    return m.predict_proba(features(stop))[:, 1]


def stop_recall(stop_payload_fn, scores: np.ndarray, k_per_km2: float) -> float:
    return sc.pooled_recall(stop_payload_fn(scores), k_per_km2)


def make_payload_fn(stop_c: pd.DataFrame, stop_b: pd.DataFrame):
    base = stop_c.copy()

    def fn(scores):
        base["score"] = scores
        return sc.payload_from_files(base, stop_b, strict=True)
    return fn


def replay(cfg, items, oracle, stop_c, stop_b, split, policies, n_seeds=None, clip_q=None, max_rounds=200):
    """n_seeds None reads config replay.seeds (10, preregistered)."""
    n_seeds = cfg["replay"]["seeds"] if n_seeds is None else n_seeds
    clip_q = cfg["ipw_clip_quantile"] if clip_q is None else clip_q
    kpk = cfg["scoring"]["k_per_km2"]
    orc = oracle.set_index("item_id")
    y_of = lambda ids: orc.loc[ids, "matched_truth"].notna().astype(int).to_numpy()  # noqa: E731
    pay = make_payload_fn(stop_c, stop_b)
    curves, scores_long, incl = [], [], []
    C = items[items["type"] == "C"]
    for s in range(n_seeds):
        seed = ek.child_seed(cfg["master_seed"], s, 99)
        rng0 = np.random.default_rng(seed)
        r0 = C.iloc[rng0.permutation(len(C))[: cfg["replay"]["round0_items"]]].copy()
        r0["pi"] = min(1.0, cfg["replay"]["round0_items"] / max(len(C), 1))
        r0["y"] = y_of(r0["item_id"])
        for pol in policies:
            keep = [c for c in ("item_id", "type", "score", "area_m2", "circ", "pi", "y", "cost_min") if c in r0.columns]
            lab = r0[keep].copy()
            cum, disc, rnd, prev = 0.0, 0.0, 0, []
            while True:
                sc_stop = fit_rerank(lab[lab["type"] == "C"], stop_c, clip_q)
                rec = stop_recall(pay, sc_stop, kpk)
                curves.append({"policy": pol, "seed": s, "round": rnd, "cum_minutes": cum, "n_labels": len(lab),
                               "n_C": int((lab["type"] == "C").sum()), "n_W": int((lab["type"] == "W").sum()),
                               "recall_stop": rec, "discovered": disc})
                scores_long.append(pd.DataFrame({"policy": pol, "seed": s, "round": rnd,
                                                 "cand_id": stop_c["cand_id"].to_numpy(), "score": sc_stop}))
                prev.append(rec)
                if cum >= cfg["budget_minutes"] or rnd >= max_rounds:
                    break
                rnd += 1
                d = select_round(items, split, set(lab["item_id"]), [pol], cfg, rnd, seed, "replay")[pol]
                if not len(d):
                    break                                      # pool exhausted (nothing left to draw)
                d["selected"] = d["selected"].astype(bool)
                incl.append(d.assign(seed=s)[["item_id", "type", "policy", "round", "pi", "selected", "seed"]])
                pick = d[d["selected"]].copy()
                if not len(pick):
                    if (d["pi"] >= 1).all() or not len(d):
                        break                                  # pool exhausted
                    continue
                pick["y"] = y_of(pick["item_id"])
                cum += float(pick["cost_min"].sum())
                if (pick["type"] == "W").any():
                    disc += float(orc.loc[pick.loc[pick["type"] == "W", "item_id"], "n_missed_block"].fillna(0).sum())
                lab = pd.concat([lab, pick[lab.columns]], ignore_index=True)
    return (pd.DataFrame(curves), pd.concat(scores_long, ignore_index=True),
            pd.concat(incl, ignore_index=True) if incl else pd.DataFrame())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.2 S1 simulation replay.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--tables", default=str(ek.sub("7.2", "results/tables")))
    ap.add_argument("--policies", nargs="+", default=["R", "U", "D", "H", "B"])
    ap.add_argument("--seeds", type=int, default=None)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    t = Path(a.tables)
    try:
        items = pd.read_csv(need(t / "al_items_9t.csv", "item table (run S0 --build-items)"))
        oracle = pd.read_csv(need(t / "al_oracle_9t.csv", "oracle"))
        stop_c = pd.read_csv(need(t / "al_stop_cands_9t.csv", "stopping candidates"))
        stop_b = pd.read_csv(need(t / "al_stop_blocks_9t.csv", "stopping blocks"))
        split = json.loads(need(t / "al_split_9t_v1.json", "split").read_text())
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    cur, scores, incl = replay(cfg, items, oracle, stop_c, stop_b, split, a.policies, a.seeds or cfg["replay"]["seeds"])
    cur.to_csv(t / "al_replay_curves_9t.csv", index=False)
    scores.to_csv(t / "al_replay_scores_9t.csv.gz", index=False)
    incl.to_csv(t / "al_replay_inclusion_9t.csv.gz", index=False)
    print(cur.groupby(["policy"]).agg(rounds=("round", "max"), final_recall=("recall_stop", "last")).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
