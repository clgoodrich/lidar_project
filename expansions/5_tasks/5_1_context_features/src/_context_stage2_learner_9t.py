"""5.1 S5 and S7. Stage-2 context learner with nested spatial folds, scored at K = 40 per km2 (tile 9t).

Purpose
    Q2 of fw_5_1. Does a second stage built on out-of-fold context features raise recall at K over stage 1?
    For each outer fold k (shared scheme) the learner trains on candidates in the other folds' blocks and scores
    candidates in fold k. Hyperparameters are chosen by inner folds (grouped by block fold) inside the training
    blocks only. Imputation and scaling are fitted on training rows only.
    Arms
        stage1        the first-stage score (no learning)
        gbm           gradient boosting, depth 3, 200 trees (primary, decision in docs/decisions_5_1.md)
        logit         L2 logistic regression (secondary)
        gbm_ablation  gbm without road distance and nearby-pit counts (annotation-habit check, fw_5_1 section 8)
    Scoring (S7)
        Recall at K = 40 per km2 of scored block area, pooled over outer folds, with ek.recall_at_k (ties by larger
        area, then id). Complete blocks including blocks with no candidate. Duplicates take budget and score nothing.
        Paired block bootstrap (B = 2000, same draws for both arms) of gbm minus stage1 with ek.bootstrap_diff.
        ek.decide(..., 'superiority') against delta_gain (user decision, config). One threshold serves both sides.
        Secondary. Same at K = 30, logit and ablation arms, calibration (ek.calibration), permutation importance.
    A failed or missing S6 audit voids the result. --allow-void runs anyway and stamps VOID on every output.

Inputs (config_5_1.json)
    inputs.stage2_features -> expansions/5_tasks/5_1_context_features/data/processed/stage2_features_9t.parquet (S4)
    outputs.stage2_usage   -> .../data/processed/stage2_upstream_usage_9t.json (S4, truth counts per block)
    outputs.leakage_audit  -> .../results/tables/context_leakage_audit_9t.json (S6)
Outputs
    outputs.stage2_scores  -> expansions/5_tasks/5_1_context_features/results/tables/stage2_scores_9t.csv
    run folder             -> expansions/5_tasks/5_1_context_features/results/<YYYYMMDD>_stage2_<hash7>/
                              stage2_summary.json, stage2_scores.csv, _CONFIG.json, _RUN.md, _PROVENANCE.json
Run
    python expansions/5_tasks/5_1_context_features/src/_context_stage2_learner_9t.py [--allow-void] [--B 2000]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek


def repo_rel(p) -> str:
    """Repo-relative POSIX path for outputs. Never an absolute path."""
    p = Path(p)
    try:
        return p.resolve().relative_to(ek.REPO.resolve()).as_posix()
    except ValueError:
        return p.name
FEATURES = ["stage1", "road_dist_m", "pad_mean_25m", "pad_mean_50m", "pad_mean_100m",
            "n_pit_50m", "n_pit_100m", "slope", "area_m2"]


# ----------------------------------------------------------------------------- recall at K
class Scorer:
    """Pooled recall at K over a list of blocks (with repeats, for the bootstrap).

    recall(arm, blocks)       calls ek.recall_at_k (the shared definition). Used for point estimates.
    recall_fast(arm, blocks)  the same rule in numpy (score desc, area desc, id asc, distinct truth in top K).
                              Used inside the bootstrap. test_5_1.py asserts the two agree.
    """

    def __init__(self, scored: pd.DataFrame, n_truth_by_block: dict, block_km2: float, k_per_km2: float):
        self.by_block = {int(b): g for b, g in scored.groupby("block_id")}
        self.nt = {int(b): int(n) for b, n in n_truth_by_block.items()}
        self.block_km2, self.k = block_km2, k_per_km2
        codes = {t: i for i, t in enumerate(sorted({t for t in scored.matched_truth if t}))}
        self._np = {b: dict(a=g.area_m2.to_numpy(float), i=g.cand_id.to_numpy(np.int64),
                            t=np.array([codes[t] if t else -1 for t in g.matched_truth], np.int64), g=g)
                    for b, g in self.by_block.items()}
        self._ntruth_codes = len(codes) + 1

    def recall(self, arm: str, blocks) -> float:
        parts, ntb = [], {}
        for c, b in enumerate(blocks):
            ntb[c] = self.nt.get(int(b), 0)
            g = self.by_block.get(int(b))
            if g is not None and len(g):
                parts.append(pd.DataFrame({"s": g[arm].to_numpy(), "a": g.area_m2.to_numpy(),
                                           "i": g.cand_id.to_numpy() + c * 10_000_000,
                                           "t": [f"{c}_{t}" if t else None for t in g.matched_truth]}))
        if not sum(ntb.values()):
            return float("nan")
        d = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame({"s": [], "a": [], "i": [], "t": []})
        r = ek.recall_at_k(d.s.to_numpy(), d.t.tolist(), None, ntb, len(blocks) * self.block_km2, self.k,
                           areas=d.a.to_numpy(), cand_ids=d.i.to_numpy())
        return r["recall"]

    def recall_fast(self, arm: str, blocks) -> float:
        S, A, I, T = [], [], [], []
        n_truth = 0
        for c, b in enumerate(blocks):
            n_truth += self.nt.get(int(b), 0)
            d = self._np.get(int(b))
            if d is None:
                continue
            S.append(d["g"][arm].to_numpy(float))
            A.append(d["a"])
            I.append(d["i"] + c * 10_000_000)
            T.append(np.where(d["t"] >= 0, d["t"] + c * self._ntruth_codes, -1))
        if not n_truth:
            return float("nan")
        if not S:
            return 0.0
        S, A, I, T = map(np.concatenate, (S, A, I, T))
        order = np.lexsort((I, -A, -S))
        k = int(round(self.k * len(blocks) * self.block_km2))
        top = T[order[:k]]
        return len(np.unique(top[top >= 0])) / n_truth


def inner_recall(df: pd.DataFrame, score: np.ndarray, nt: dict, block_km2: float, k: float) -> float:
    """Recall at K on one inner fold. nt holds every block of that fold, including blocks with no candidate."""
    return Scorer(df.assign(_s=score), nt, block_km2, k).recall_fast("_s", sorted(nt))


# ----------------------------------------------------------------------------- models
def make_model(kind: str, param: float, cfg: dict, seed: int):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    g = cfg["stage2"]["gbm"]
    if kind == "gbm":
        return GradientBoostingClassifier(max_depth=g["max_depth"], n_estimators=g["n_estimators"], learning_rate=param,
                                          random_state=seed)
    if kind == "logit":
        return make_pipeline(StandardScaler(), LogisticRegression(C=param, max_iter=2000))
    raise ValueError(kind)


def fit_predict(kind, param, cfg, seed, Xtr, ytr, Xte):
    med = np.nanmedian(Xtr, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    fill = lambda X: np.where(np.isfinite(X), X, med)  # noqa: E731
    if len(np.unique(ytr)) < 2:
        return np.full(len(Xte), float(ytr.mean()) if len(ytr) else 0.0), None, med
    m = make_model(kind, param, cfg, seed).fit(fill(Xtr), ytr)
    return m.predict_proba(fill(Xte))[:, 1], m, med


def choose_param(kind, grid, train: pd.DataFrame, feats, cfg, seed, nt_all, b2f, block_km2, k):
    """Inner folds grouped by block fold. Returns the grid value with the best mean inner recall at K."""
    folds = sorted(train.block_fold.unique())
    n_in = min(int(cfg["stage2"]["inner_folds"]), len(folds))
    if n_in < 2:
        return grid[0], {}
    groups = [folds[i::n_in] for i in range(n_in)]
    scores = {}
    for p in grid:
        vals = []
        for gi, g in enumerate(groups):
            te = train[train.block_fold.isin(g)]
            tr = train[~train.block_fold.isin(g)]
            pr, _, _ = fit_predict(kind, p, cfg, ek.child_seed(seed, gi, 1), tr[feats].to_numpy(float),
                                   tr.y.to_numpy(), te[feats].to_numpy(float))
            nt = {b: n for b, n in nt_all.items() if b2f.get(b) in g}
            vals.append(inner_recall(te, pr, nt, block_km2, k))
        scores[p] = float(np.nanmean(vals)) if np.isfinite(vals).any() else float("nan")
    best = max(grid, key=lambda p: (np.nan_to_num(scores[p], nan=-1), -grid.index(p)))
    return best, scores


def run_cv(feat: pd.DataFrame, cfg: dict, nt_all: dict, b2f: dict, seed: int):
    """Outer loop. Returns scored test rows (one per candidate) and the fitted models per fold."""
    s2 = cfg["stage2"]
    block_km2 = cfg["block_m"] ** 2 / 1e6
    abl = [f for f in FEATURES if f not in s2["ablation_drop"]]
    out, models, chosen = [], {}, {}
    for k in sorted(feat.outer_fold.unique()):
        rows = feat[feat.outer_fold == k]
        tr, te = rows[rows.block_fold != k], rows[rows.block_fold == k].copy()
        te["stage1_arm"] = te.stage1.to_numpy()
        nt_tr = {b: n for b, n in nt_all.items() if b2f.get(b) != k}
        for arm, kind, grid, fs in (("gbm", "gbm", s2["gbm_lr_grid"], FEATURES),
                                    ("logit", "logit", s2["logit_C_grid"], FEATURES),
                                    ("gbm_ablation", "gbm", s2["gbm_lr_grid"], abl)):
            p, sc = choose_param(kind, list(grid), tr, fs, cfg, ek.child_seed(seed, int(k), 0), nt_tr, b2f, block_km2,
                                 cfg["k_per_km2"])
            pred, m, med = fit_predict(kind, p, cfg, ek.child_seed(seed, int(k), 2), tr[fs].to_numpy(float),
                                       tr.y.to_numpy(), te[fs].to_numpy(float))
            te[arm] = pred
            models[(int(k), arm)] = (m, med, fs)
            chosen[f"fold{k}_{arm}"] = dict(param=p, inner=sc)
        out.append(te)
    scored = pd.concat(out, ignore_index=True)
    ek.assert_unique(scored, "cand_id")
    return scored, models, chosen


def permutation_importance(scored, feat, models, scorer: Scorer, blocks, n_perm, seed):
    rng = np.random.default_rng(seed)
    base = scorer.recall("gbm", blocks)
    res = {}
    for f in FEATURES:
        drops = []
        for _ in range(n_perm):
            s = scored.copy()
            for k in sorted(s.outer_fold.unique()):
                m, med, fs = models[(int(k), "gbm")]
                idx = s.outer_fold == k
                X = s.loc[idx, fs].to_numpy(float).copy()
                X[:, fs.index(f)] = rng.permutation(X[:, fs.index(f)])
                s.loc[idx, "gbm"] = m.predict_proba(np.where(np.isfinite(X), X, med))[:, 1] if m is not None else s.loc[idx, "gbm"]
            drops.append(base - Scorer(s, scorer.nt, scorer.block_km2, scorer.k).recall_fast("gbm", blocks))
        res[f] = dict(mean_drop=float(np.mean(drops)), sd=float(np.std(drops)))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--allow-void", action="store_true", help="score even when the S6 audit failed. Output is VOID")
    ap.add_argument("--B", type=int, help="bootstrap draws (default config stage2.bootstrap_B)")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    s2 = cfg["stage2"]
    audit_p = th.resolve(cfg["outputs"]["leakage_audit"])
    audit = json.loads(audit_p.read_text()) if audit_p.exists() else None
    void = not (audit and audit.get("passed"))
    if void and not a.allow_void:
        if audit is None:
            raise th.MissingInput("leakage_audit", audit_p, "run _context_leakage_audit_9t.py (S6) first")
        raise SystemExit(f"S6 leakage audit FAILED ({audit['n_failed']} entries). Run is void. "
                         "Use --allow-void only to test the pipeline.")
    fp = th.inp(cfg, "stage2_features")
    feat = pd.read_parquet(fp)
    feat["matched_truth"] = feat.matched_truth.fillna("").astype(str)
    usage = json.loads(th.resolve(cfg["outputs"]["stage2_usage"]).read_text())
    nt = {int(b): int(n) for b, n in usage["n_truth_by_block"].items()}
    b2f = {int(b): int(f) for b, f in usage["block_to_fold"].items()}
    seed = int(cfg["seed"])
    scored, models, chosen = run_cv(feat, cfg, nt, b2f, seed)
    scored["stage1"] = scored["stage1_arm"]
    blocks = sorted(nt)
    km2 = cfg["block_m"] ** 2 / 1e6
    B = a.B or int(s2["bootstrap_B"])
    summary = dict(void=void, audit=repo_rel(audit_p), audit_passed=bool(audit and audit.get("passed")),
                   mode=usage.get("mode"), n_candidates=int(len(scored)), n_blocks=len(blocks),
                   n_truth=int(sum(nt.values())), evidence_level="a", analysis="exploratory" if void else "confirmatory",
                   hyperparameters=chosen, results={})
    for kk, tagk in ((cfg["k_per_km2"], "K40"), (cfg["k_sensitivity_per_km2"], "K30_sensitivity")):
        sc = Scorer(scored, nt, km2, kk)
        res = {arm: sc.recall(arm, blocks) for arm in ("stage1", "gbm", "logit", "gbm_ablation")}
        for arm in ("gbm", "logit", "gbm_ablation"):
            d, lo, hi = ek.bootstrap_diff(lambda bl, arm=arm: sc.recall_fast(arm, bl), blocks,
                                          lambda bl: sc.recall_fast("stage1", bl), blocks, B=B, seed=seed, paired=True)
            res[f"{arm}_minus_stage1"] = dict(diff=d, lo=lo, hi=hi)
        summary["results"][tagk] = res
    prim = summary["results"]["K40"]["gbm_minus_stage1"]
    dg = s2.get("delta_gain")
    summary["primary"] = dict(statistic="recall at K=40/km2, gbm minus stage1, paired block bootstrap",
                              B=B, delta_gain=dg, **prim,
                              decision=("VOID (leakage audit failed)" if void else
                                        ek.decide(prim["lo"], prim["hi"], dg, "superiority") if dg is not None
                                        else "no margin set (delta_gain is a user decision)"))
    summary["calibration_gbm"] = ek.calibration(scored.y, scored.gbm)
    summary["permutation_importance_gbm"] = permutation_importance(
        scored, feat, models, Scorer(scored, nt, km2, cfg["k_per_km2"]), blocks, int(s2["n_perm"]), seed)
    run = ek.new_run("5.1", "stage2", {k: v for k, v in cfg.items() if not k.startswith("_")},
                     base=th.resolve(cfg["outputs"]["runs"]),
                     why=("VOID pipeline test. " if void else "") + "Stage-2 context learner, recall at K=40.")
    cols = ["cand_id", "block_id", "outer_fold", "y", "matched_truth", "is_dup", "area_m2", "stage1", "gbm", "logit", "gbm_ablation"]
    sc_out = scored[cols].assign(void=void, evidence_level="a")
    sc_out.to_csv(run / "stage2_scores.csv", index=False)
    sc_out.to_csv(th.outp(cfg, "stage2_scores"), index=False)
    th.write_json(run / "stage2_summary.json", summary)
    ek.write_provenance(run, inputs=[fp, th.resolve(cfg["outputs"]["stage2_usage"]), audit_p],
                        outputs=[run / "stage2_scores.csv", run / "stage2_summary.json"],
                        params=dict(k_per_km2=cfg["k_per_km2"], B=B, delta_gain=dg), seeds=dict(master=seed))
    print(json.dumps(summary["results"]["K40"], indent=1))
    print(f"primary decision: {summary['primary']['decision']}")
    print(f"wrote {run}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except th.MissingInput as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(2)
