"""Learning curves, stopping rule, primary paired test and discovery accounting for 7.2 (S4, S5, S6).

Purpose
    Works on replay output or on live rounds, which share one schema.
    Stopping rule (S4). Stop when cumulative minutes reach the budget, or when the random control's
    stopping-set recall changes by under 0.01 for two rounds. Uses the stopping set only.
    The rule is enforced (review 7.2 minor). Curves, scores and inclusion logs are cut at the stop round
    before any estimate. If the loop stops before B*, the primary is read at the stop round and flagged.
    Primary (section 8). Recall at K on the stopping set at B* reviewer-minutes, U minus R, the mean over
    selection seeds inside each block resample (paired block bootstrap, B = 2000). The stopping set has
    about 20 blocks, so a paired sign-flip permutation p-value is reported beside it.
    G comes from config_7_2.json ("G") or the preregistration JSON (--prereg, key "G"), set before scoring
    (review 7.2-01). It is never chosen from the replay it judges and never floored. With G unset the
    decision is inconclusive. G_raw (R recall at the budget minus at 75% of it) is always reported as a
    diagnostic only. Superiority decision with ek.decide.
    H3. Policy ranking by recall at equal minutes and at equal label count, side by side.
    Discovery (S6). Horvitz-Thompson estimates over sampled discovery windows with their pi. Features the
    pool never proposed per window, pool recall, and yield per reviewer-hour. Interval by bootstrap over windows.

Inputs (expansions/7_scale/7_2_active_learning/results/tables/)
    al_replay_curves_9t.csv, al_replay_scores_9t.csv.gz, al_replay_inclusion_9t.csv.gz (or live equivalents)
    al_stop_cands_9t.csv, al_stop_blocks_9t.csv, al_oracle_9t.csv
Outputs
    results/tables/<prefix>_G_frozen_9t.json, <prefix>_primary_decision_9t.json, <prefix>_policy_ranking_9t.csv
    results/figures/<prefix>_curves_minutes_9t.png      (prefix al_replay or al_live)

Run
    python expansions/7_scale/7_2_active_learning/src/_al_curve_score_9t.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _al_policies_select_9t import CFG, ek, load_cfg, need  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "7_3_benchmark" / "src"))
import _bench_evaluate_recall_k as sc  # noqa: E402


def round_at(curves: pd.DataFrame, policy: str, seed: int, minutes: float) -> int:
    c = curves[(curves["policy"] == policy) & (curves["seed"] == seed) & (curves["cum_minutes"] <= minutes)]
    return int(c["round"].max()) if len(c) else 0


def payload_by_block(stop_c, stop_b, scores_long, policy, seed, rnd) -> dict:
    s = scores_long[(scores_long["policy"] == policy) & (scores_long["seed"] == seed) & (scores_long["round"] == rnd)]
    c = stop_c.drop(columns="score").merge(s[["cand_id", "score"]], on="cand_id", how="left")
    if c["score"].isna().any():
        raise AssertionError(f"missing stopping-set scores for {policy} seed {seed} round {rnd}")
    return dict(zip(sorted(stop_b["block_id"]), sc.payload_from_files(c, stop_b, sorted(stop_b["block_id"]), strict=True)))


def check_stop(curves: pd.DataFrame, cfg: dict, control: str = "R") -> dict:
    r = curves[curves["policy"] == control].groupby("round").agg(rec=("recall_stop", "mean"), m=("cum_minutes", "mean"))
    d = r["rec"].diff().abs()
    small = (d < cfg["stop"]["delta"]).astype(int)
    run = small.groupby((small != small.shift()).cumsum()).cumsum() * small
    hit = run[run >= cfg["stop"]["rounds"]]
    budget = r[r["m"] >= cfg["budget_minutes"]]
    if len(hit):
        return {"stop": True, "reason": f"plateau under {cfg['stop']['delta']} for {cfg['stop']['rounds']} rounds", "round": int(hit.index[0])}
    if len(budget):
        return {"stop": True, "reason": "budget reached", "round": int(budget.index[0])}
    return {"stop": False, "round": int(r.index.max())}


class GUnset(ValueError):
    """G is null in the config and in the preregistration. The config default is 0.02 (user default 2026-11-06)."""


def G_raw(curves, cfg, control: str) -> float:
    """Control recall at the budget minus at 75% of it. Diagnostic only (review 7.2-01)."""
    seeds = sorted(curves.loc[curves["policy"] == control, "seed"].unique())
    rec = lambda m: float(np.mean([curves[(curves["policy"] == control) & (curves["seed"] == s) &  # noqa: E731
                                          (curves["round"] == round_at(curves, control, s, m))]["recall_stop"].iloc[0] for s in seeds]))
    b = cfg["budget_minutes"]
    return rec(b) - rec(0.75 * b)


def resolve_G(cfg, curves, path: Path, control: str, prereg: dict | None = None) -> dict:
    """Review 7.2-01. G is set before scoring, from the config or the preregistration. It is never chosen
    from the replay it is tested on and never floored. G_raw is always reported beside it."""
    if cfg.get("G") is not None:
        G, src = float(cfg["G"]), "config_7_2.json G (set before scoring)"
    elif prereg and prereg.get("G") is not None:
        G, src = float(prereg["G"]), f"preregistration {prereg.get('_path', '')} G (set before scoring)"
    else:
        raise GUnset("G is null in config_7_2.json and the preregistration. The user default is 0.02")
    g = {"G": G, "source": src, "G_raw": G_raw(curves, cfg, control),
         "G_raw_note": f"{control} recall at the budget minus at 75% of it, from the same curves that are scored. "
                       "Diagnostic only. Never used as the margin and never floored",
         "seeds": [int(s) for s in sorted(curves.loc[curves["policy"] == control, "seed"].unique())]}
    path.write_text(json.dumps(g, indent=2), encoding="utf-8")
    return g


def enforce_stop(curves, scores, incl, stop: dict):
    """Cut every policy at the stop round (review 7.2 minor: the stop rule was computed and then ignored)."""
    r = stop["round"]
    cut = lambda d: d[d["round"] <= r] if len(d) and "round" in d else d  # noqa: E731
    return cut(curves), cut(scores), cut(incl)


def primary(cfg, curves, scores, stop_c, stop_b, G: float | None, B: int, stop: dict | None = None) -> dict:
    pol, ctl = cfg["primary"]["policy"], cfg["primary"]["control"]
    bstar = cfg["B_star_share"] * cfg["budget_minutes"]
    stopped_early = bool(stop and stop["stop"] and curves.loc[curves["round"] <= stop["round"], "cum_minutes"].max() < bstar)
    seeds = sorted(set(curves.loc[curves["policy"] == pol, "seed"]) & set(curves.loc[curves["policy"] == ctl, "seed"]))
    kpk = cfg["scoring"]["k_per_km2"]
    pa = {s: payload_by_block(stop_c, stop_b, scores, pol, s, round_at(curves, pol, s, bstar)) for s in seeds}
    pb = {s: payload_by_block(stop_c, stop_b, scores, ctl, s, round_at(curves, ctl, s, bstar)) for s in seeds}
    blocks = sorted(stop_b["block_id"])
    stat = lambda bl: float(np.mean([sc.pooled_recall([pa[s][b] for b in bl], kpk) -  # noqa: E731
                                     sc.pooled_recall([pb[s][b] for b in bl], kpk) for s in seeds]))
    point, lo, hi, _ = ek.block_bootstrap(stat, blocks, B=B, seed=cfg["master_seed"])
    rng = np.random.default_rng(cfg["master_seed"] + 1)
    null = []
    for _ in range(B):
        flip = rng.random(len(blocks)) < 0.5
        null.append(np.mean([sc.pooled_recall([(pb if f else pa)[s][b] for b, f in zip(blocks, flip)], kpk) -
                             sc.pooled_recall([(pa if f else pb)[s][b] for b, f in zip(blocks, flip)], kpk) for s in seeds]))
    p = float((np.sum(np.abs(null) >= abs(point)) + 1) / (B + 1))
    return {"policy": pol, "control": ctl, "B_star_minutes": bstar, "diff": point, "lo": lo, "hi": hi, "G": G,
            "n_seeds": len(seeds), "n_blocks": len(blocks), "permutation_p": p,
            "bootstrap_unreliable": len(blocks) < 15,
            "stopped_before_B_star": stopped_early,
            "read_at": "stop round (the loop stopped before B*)" if stopped_early else "B* minutes",
            "decision": ("void (fewer than 3 seeds)" if len(seeds) < 3
                         else ek.decide(lo, hi, G, "superiority"))}


def ranking(curves: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    bstar = cfg["B_star_share"] * cfg["budget_minutes"]
    rows = []
    at_min = {}
    for (pol, s), g in curves.groupby(["policy", "seed"]):
        at_min.setdefault(pol, []).append(g[g["round"] == round_at(curves, pol, s, bstar)]["recall_stop"].iloc[0])
    n_eq = int(curves[curves["cum_minutes"] <= bstar]["n_labels"].median())
    for pol, g in curves.groupby("policy"):
        lab = [gs[gs["n_labels"] <= n_eq]["recall_stop"].iloc[-1] if (gs["n_labels"] <= n_eq).any() else np.nan
               for _, gs in g.groupby("seed")]
        rows.append({"policy": pol, "recall_at_Bstar_minutes": float(np.mean(at_min[pol])),
                     "recall_at_equal_labels": float(np.nanmean(lab)), "equal_labels_n": n_eq})
    t = pd.DataFrame(rows)
    t["rank_minutes"] = t["recall_at_Bstar_minutes"].rank(ascending=False, method="min")
    t["rank_labels"] = t["recall_at_equal_labels"].rank(ascending=False, method="min")
    return t


def discovery(incl: pd.DataFrame, oracle: pd.DataFrame, cost_w: float, B: int, seed: int) -> dict:
    w = incl[(incl["type"] == "W") & incl["selected"]].merge(oracle, on="item_id", how="left")
    if not len(w):
        return {"note": "no discovery windows sampled"}
    w = w.drop_duplicates(["seed", "item_id"]) if "seed" in w else w.drop_duplicates("item_id")
    def est(d):
        miss = (d["n_missed_block"] / d["pi"]).sum()
        tot = (d["n_truth_block"] / d["pi"]).sum()
        return {"missed_ht": float(miss), "truth_ht": float(tot), "pool_recall": float(1 - miss / tot) if tot else float("nan"),
                "missed_per_hour": float(d["n_missed_block"].sum() / (len(d) * cost_w / 60))}
    point = est(w)
    rng = np.random.default_rng(seed)
    draws = [est(w.iloc[rng.integers(0, len(w), len(w))])["pool_recall"] for _ in range(B)]
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return {**point, "pool_recall_ci95": [float(lo), float(hi)], "n_windows": int(len(w)),
            "note": "Horvitz-Thompson with pi from the window draw. Windows pooled over seeds in replay"}


def figure(curves: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # ek.PALETTE lost/found set, worst pair dE 21.1 deutan / 22.6 normal (dataviz validator --pairs all,
    # recorded in expkit). Every policy also has its own marker, so colour is never the only cue.
    col = {"R": ek.PALETTE["charcoal"], "U": ek.PALETTE["blue"], "D": ek.PALETTE["orange"],
           "H": ek.PALETTE["dark_red"], "B": ek.PALETTE["grey"]}
    mk = {"R": "o", "U": "s", "D": "^", "H": "D", "B": "v"}
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for pol, g in curves.groupby("policy"):
        m = g.groupby("round").agg(x=("cum_minutes", "mean"), n=("n_labels", "mean"), y=("recall_stop", "mean"))
        axs[0].plot(m["x"] / 60, m["y"], marker=mk.get(pol, "x"), color=col.get(pol, "black"), label=pol)
        axs[1].plot(m["n"], m["y"], marker=mk.get(pol, "x"), color=col.get(pol, "black"), label=pol)
    axs[0].set_xlabel("Cumulative reviewer-hours")
    axs[1].set_xlabel("Labels acquired")
    axs[0].set_ylabel("Stopping-set recall at 40 per km2")
    axs[0].set_title("By effort")
    axs[1].set_title("By label count")
    axs[1].legend(title="Policy", frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.2 curves, stopping rule and decision.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--tables", default=str(ek.sub("7.2", "results/tables")))
    ap.add_argument("--prefix", default="al_replay", help="al_replay or a live prefix with the same schema")
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--prereg", default=None, help="preregistration JSON with key G (used when config G is null)")
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    prereg = {**json.loads(Path(a.prereg).read_text(encoding="utf-8")), "_path": a.prereg} if a.prereg else None
    t = Path(a.tables)
    try:
        curves = pd.read_csv(need(t / f"{a.prefix}_curves_9t.csv", "curves"))
        scores = pd.read_csv(need(t / f"{a.prefix}_scores_9t.csv.gz", "stopping-set scores"))
        incl = pd.read_csv(need(t / f"{a.prefix}_inclusion_9t.csv.gz", "inclusion log"))
        stop_c = pd.read_csv(need(t / "al_stop_cands_9t.csv", "stopping candidates"))
        stop_b = pd.read_csv(need(t / "al_stop_blocks_9t.csv", "stopping blocks"))
        oracle = pd.read_csv(need(t / "al_oracle_9t.csv", "oracle"))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    res = analyse(cfg, curves, scores, incl, stop_c, stop_b, oracle, a.B, t, ek.sub("7.2", "results/figures"), a.prefix,
                  prereg)
    print(json.dumps(res["primary"], indent=2, default=float))
    return 0


def analyse(cfg, curves, scores, incl, stop_c, stop_b, oracle, B, tables: Path, figs: Path, prefix: str = "al_replay",
            prereg: dict | None = None) -> dict:
    """prefix keeps replay and live products apart. G comes from the config or the preregistration only."""
    if incl["pi"].le(0).any():
        raise AssertionError("an item with pi = 0 was logged (bug)")
    ctl = cfg["primary"]["control"]
    G = resolve_G(cfg, curves, tables / f"{prefix}_G_frozen_9t.json", ctl, prereg)
    stop = check_stop(curves, cfg, ctl)
    n_rounds_run = int(curves["round"].max())
    curves, scores, incl = enforce_stop(curves, scores, incl, stop)
    stop = {**stop, "enforced": True, "rounds_run": n_rounds_run, "rounds_kept": int(curves["round"].max())}
    res = {"evidence_level": "a", "exploratory": ("replay oracle is the annotator's own labels" if prefix == "al_replay" else "live loop"),
           "stop_rule": stop, "G": G,
           "n_seeds": int(curves["seed"].nunique()),
           "primary": primary(cfg, curves, scores, stop_c, stop_b, G["G"], B, stop),
           "discovery": discovery(incl, oracle, cfg["cost_minutes"]["W"], B, cfg["master_seed"])}
    rk = ranking(curves, cfg)
    rk.to_csv(tables / f"{prefix}_policy_ranking_9t.csv", index=False)
    res["H3_rankings_differ"] = bool((rk["rank_minutes"] != rk["rank_labels"]).any())
    figure(curves, figs / f"{prefix}_curves_minutes_9t.png")
    (tables / f"{prefix}_primary_decision_9t.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    return res


if __name__ == "__main__":
    sys.exit(main())
