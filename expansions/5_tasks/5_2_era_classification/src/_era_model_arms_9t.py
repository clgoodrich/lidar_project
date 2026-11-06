"""S5, S6 and S8. Block-split era models, primary test and figures for 5.2 (fw_5_2 sections 7 and 8).

Purpose
    S5  Folds come from the P1 split file (block_id, fold, role). Audit blocks are dropped from training, tuning
        and selection. --provisional-folds builds deterministic block folds instead and labels the run provisional.
    S6  Four arms. M0 location (easting, northing, squares and product), M1 covariates, M2 morphology,
        M3 morphology plus covariates. Primary family is an interval-censored log-normal AFT fitted inside each
        fold (normalisation from training rows only). Secondary is a gradient-boosted E1 versus E3 classifier.
        Out-of-fold predictions only.
        Primary statistic. AUC of the M3 early score for (E1 or E2) against E3, minus the AUC of M1, paired block
        bootstrap (same blocks both arms, B = 2000). ek.decide superiority against delta_era.
        Under 15 blocks a paired block-swap permutation range is added and the bootstrap is called unreliable.
        Secondary. Interval concordance, Spearman of predicted year against interval midpoint, GBM AUC and
        calibration. Label-noise sensitivity re-runs the primary after reassigning a share p of intervals.
        Readiness gate. At least 100 identity-resolved wells and 20 each in E1 and E2. Below that the script
        writes counts only, unless --force-exploratory.
    S8  era_auc_by_arm_9t.png (AUC with block interval per arm. M3 blue, M0 orange, M1 grey, M2 charcoal,
        distinct marker shapes and direct labels) and era_pred_vs_interval_9t.png.
    The sentinel never enters. assert_no_sentinel runs on the model table.

Inputs (config_5_2.json)
    pairs          @exp:5.2/results/tables/era_features_pairs_9t.csv (S4 with S2 labels joined)
    split_file     ASSUMED @results_9t/splits/cv_splits_future_pit_9t_v1.csv (P1 _split_future_csv_9t.py). Read with
                   ek.read_split_csv, so P1 role words (val, heldout) map to inner_val, held_out.
    audit_blocks   ASSUMED @results_9t/splits/audit_blocks_9t_v1.csv (P2). Read with ek.require_audit (hash-checked,
                   audit and buffer roles excluded). Missing is allowed only with --provisional-folds, and the run
                   is then labelled "no audit exclusion, exploratory".
Outputs
    predictions_csv  @exp:5.2/results/tables/era_predictions_9t.csv
    model_json       @exp:5.2/results/tables/era_model_summary_9t.json
    fig_auc          @exp:5.2/results/figures/era_auc_by_arm_9t.png
    fig_interval     @exp:5.2/results/figures/era_pred_vs_interval_9t.png
    run folder       @exp:5.2/results/<YYYYMMDD>_era_model_<hash>/
Evidence level
    (a) drawn feature with era as an attribute. Silent on sentinel wells and on whether a feature is a well.
Run
    python expansions/5_tasks/5_2_era_classification/src/_era_model_arms_9t.py
    python expansions/5_tasks/5_2_era_classification/src/_era_model_arms_9t.py --provisional-folds --force-exploratory
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _era_core_tools as ec  # noqa: E402

ek = th.ek
ARM_COLOURS = {"M3": ek.PALETTE["blue"], "M0": ek.PALETTE["orange"], "M1": ek.PALETTE["grey"],
               "M2": ek.PALETTE["charcoal"]}
ARM_MARKERS = {"M3": "o", "M0": "s", "M1": "^", "M2": "D"}


def arms_from_cfg(cfg: dict) -> dict:
    f = cfg["features"]
    loc = f["location"] + ["easting_sq", "northing_sq", "east_x_north"]
    return {"M0": loc, "M1": f["covariates"], "M2": f["morphology"], "M3": f["morphology"] + f["covariates"]}


def add_location_terms(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    e = df["easting_km"] - df["easting_km"].mean()
    n = df["northing_km"] - df["northing_km"].mean()
    df["easting_sq"], df["northing_sq"], df["east_x_north"] = e * e, n * n, e * n
    return df


def readiness(df: pd.DataFrame, cfg: dict) -> dict:
    r = cfg["model"]["readiness"]
    one = df.drop_duplicates("permit")
    c = one["era_class"].value_counts().to_dict()
    n = int(len(one))
    ok = n >= r["min_wells"] and c.get("E1", 0) >= r["min_E1"] and c.get("E2", 0) >= r["min_E2"]
    return dict(n_wells=n, by_class={k: int(v) for k, v in c.items()}, ready=bool(ok), rule=r)


def usable_cols(train: pd.DataFrame, cols: list) -> list:
    keep = []
    for c in cols:
        if c in train and train[c].notna().any() and train[c].nunique(dropna=True) > 1:
            keep.append(c)
    return keep


def fit_predict_fold(tr: pd.DataFrame, te: pd.DataFrame, cols: list, cfg: dict) -> dict:
    """AFT (all labelled rows) and GBM (E1 vs E3 rows) on one fold. Imputation by training median."""
    from sklearn.ensemble import GradientBoostingClassifier
    cols = usable_cols(tr, cols)
    med = tr[cols].median() if cols else pd.Series(dtype=float)
    Xtr = tr[cols].fillna(med).to_numpy(float) if cols else np.zeros((len(tr), 0))
    Xte = te[cols].fillna(med).to_numpy(float) if cols else np.zeros((len(te), 0))
    m = ec.IntervalLogNormalAFT(cfg["model"]["ridge"]).fit(Xtr, tr["lo"], tr["hi"])
    out = {"year": m.predict_year(Xte), "score": -m.predict_log(Xte), "cols": cols, "converged": m.converged_}
    g = tr["era_class"].isin(["E1", "E3"])
    y = (tr.loc[g, "era_class"] == "E1").astype(int)
    if cols and y.nunique() == 2:
        gb = GradientBoostingClassifier(random_state=ek.child_seed(cfg["master_seed"], 0, 7), **cfg["model"]["gbm"])
        gb.fit(Xtr[g.to_numpy()], y)
        out["gbm_p"] = gb.predict_proba(Xte)[:, 1]
    else:
        out["gbm_p"] = np.full(len(te), np.nan)
    return out


def oof(df: pd.DataFrame, arms: dict, cfg: dict) -> tuple[pd.DataFrame, dict]:
    pred = df[["permit", "pad_id", "block_id", "fold", "lo", "hi", "era_class", "early"]].copy()
    used = {}
    for arm, cols in arms.items():
        for c in ("year", "score", "gbm_p"):
            pred[f"{arm}_{c}"] = np.nan
        used[arm] = {}
        for k in sorted(df["fold"].unique()):
            tr, te = df[df.fold != k], df[df.fold == k]
            if not len(te) or not len(tr):
                continue
            r = fit_predict_fold(tr, te, cols, cfg)
            for c in ("year", "score", "gbm_p"):
                pred.loc[te.index, f"{arm}_{c}"] = r[c]
            used[arm][int(k)] = dict(cols=r["cols"], aft_converged=r["converged"])
    return pred, used


NO_AUDIT_LABEL = "no audit exclusion, exploratory"
UNDEFINED_RULE = ("A resample with one class has no AUC. Undefined draws are kept. With max_undefined unset (0) "
                  "any undefined draw makes the interval NaN and the decision inconclusive.")


def max_undefined(cfg: dict) -> float:
    """Declared tolerated share of undefined bootstrap draws. fw_5_2 declares none, so 0 unless config sets it."""
    v = cfg["model"].get("max_undefined")
    return 0.0 if v is None else float(v)


def repo_rel(p) -> str:
    """Repo-relative POSIX path for outputs (never an absolute path)."""
    p = Path(p)
    try:
        return p.resolve().relative_to(ek.REPO.resolve()).as_posix()
    except ValueError:
        return p.name


def primary(pred: pd.DataFrame, cfg: dict) -> dict:
    mcfg = cfg["model"]
    e = pred[pred["early"].notna()]
    blocks = sorted(e["block_id"].unique())
    f3 = ec.auc_over_blocks(e, "early", "M3_score")
    f1 = ec.auc_over_blocks(e, "early", "M1_score")
    mu = max_undefined(cfg)
    d, lo, hi, draws = ek.bootstrap_diff(f3, blocks, f1, blocks, B=mcfg["bootstrap_B"],
                                         seed=ek.child_seed(cfg["master_seed"], 0, 1), paired=True,
                                         max_undefined=mu, return_draws=True)
    res = dict(statistic="AUC(M3) - AUC(M1), early (E1 or E2) vs E3, out-of-fold, non-audit blocks",
               n_rows=int(len(e)), n_blocks=int(len(blocks)), diff=d, lo=lo, hi=hi,
               undefined_share=ek.undefined_share(draws), max_undefined=mu,
               undefined_rule=UNDEFINED_RULE,
               delta_era=mcfg["delta_era"], decision=ek.decide(lo, hi, mcfg["delta_era"], "superiority"))
    if len(blocks) < mcfg["min_blocks_for_bootstrap"]:
        rng = np.random.default_rng(ek.child_seed(cfg["master_seed"], 0, 2))
        draws = []
        for _ in range(mcfg["bootstrap_B"] // 4):
            swap = set(b for b in blocks if rng.random() < 0.5)
            t = e.copy()
            m = t["block_id"].isin(swap)
            t.loc[m, ["M3_score", "M1_score"]] = t.loc[m, ["M1_score", "M3_score"]].to_numpy()
            draws.append(ec.auc(t.early, t.M3_score) - ec.auc(t.early, t.M1_score))
        draws = np.asarray(draws, float)
        res["permutation_undefined_share"] = ek.undefined_share(draws)
        res["permutation_null_95"] = ([float(x) for x in np.percentile(draws, [2.5, 97.5])]
                                      if np.isfinite(draws).all() else [float("nan"), float("nan")])
        res["note"] = f"fewer than {mcfg['min_blocks_for_bootstrap']} blocks. Bootstrap unreliable."
    return res


def secondary(pred: pd.DataFrame, cfg: dict) -> dict:
    out = {}
    blocks = sorted(pred["block_id"].unique())
    for arm in ("M0", "M1", "M2", "M3"):
        e = pred[pred["early"].notna()]
        f = ec.auc_over_blocks(e, "early", f"{arm}_score")
        pt, lo, hi, dr = ek.block_bootstrap(f, sorted(e.block_id.unique()), B=cfg["model"]["bootstrap_B"] // 4,
                                            seed=ek.child_seed(cfg["master_seed"], 0, 10),
                                            max_undefined=max_undefined(cfg))
        mid = 0.5 * (pred.lo + pred.hi)
        rho = spearmanr(pred[f"{arm}_year"], mid, nan_policy="omit")[0] if len(pred) > 2 else np.nan
        out[arm] = dict(auc=pt, auc_lo=lo, auc_hi=hi, auc_undefined_share=ek.undefined_share(dr),
                        interval_concordance=ec.interval_concordance(pred[f"{arm}_year"], pred.lo, pred.hi),
                        spearman_pred_vs_mid=float(rho))
        g = pred[pred["era_class"].isin(["E1", "E3"]) & pred[f"{arm}_gbm_p"].notna()]
        if len(g) and g.era_class.nunique() == 2:
            y = (g.era_class == "E1").astype(int)
            out[arm]["gbm_e1_vs_e3_auc"] = ec.auc(y, g[f"{arm}_gbm_p"])
            out[arm]["gbm_calibration"] = ek.calibration(y, g[f"{arm}_gbm_p"])
    out["n_blocks"] = len(blocks)
    return out


def label_noise(df: pd.DataFrame, arms: dict, cfg: dict) -> dict:
    """Reassign a share p of intervals to random other wells (a link error), refit, recompute the primary point."""
    res = {}
    for i, p in enumerate(cfg["model"]["label_noise_p"]):
        rng = np.random.default_rng(ek.child_seed(cfg["master_seed"], 0, 100 + i))
        vals = []
        for _ in range(cfg["model"]["label_noise_reps"]):
            t = df.copy()
            m = rng.random(len(t)) < p
            src = rng.choice(len(t), int(m.sum()))
            for c in ("lo", "hi", "era_class", "early"):
                t.loc[t.index[m], c] = t[c].to_numpy()[src]
            pr, _ = oof(t, {"M1": arms["M1"], "M3": arms["M3"]}, cfg)
            e = pr[pr.early.notna()]
            vals.append(ec.auc(e.early, e.M3_score) - ec.auc(e.early, e.M1_score))
        v = np.asarray(vals, float)
        ok = np.isfinite(v).all() and len(v)
        res[str(p)] = dict(median=float(np.median(v)) if ok else float("nan"),
                           p05=float(np.percentile(v, 5)) if ok else float("nan"),
                           undefined_share=ek.undefined_share(v))
    return res


def figures(pred: pd.DataFrame, sec: dict, cfg: dict) -> list:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    p1 = th.outp(cfg, "fig_auc")
    fig, ax = plt.subplots(figsize=(6, 3.6))
    for i, arm in enumerate(["M0", "M1", "M2", "M3"]):
        s = sec[arm]
        ax.errorbar(i, s["auc"], yerr=[[s["auc"] - s["auc_lo"]], [s["auc_hi"] - s["auc"]]], fmt=ARM_MARKERS[arm],
                    color=ARM_COLOURS[arm], capsize=4, ms=8)
        ax.annotate(f"{arm} {s['auc']:.2f}", (i, s["auc_hi"]), textcoords="offset points", xytext=(0, 6),
                    ha="center", fontsize=9, color=ARM_COLOURS[arm])
    ax.axhline(0.5, color=ek.PALETTE["grey"], ls=":", lw=1)
    ax.set_xticks(range(4), ["M0 location", "M1 covariates", "M2 morphology", "M3 morph. + cov."])
    ax.set_ylabel("out-of-fold AUC, early vs permit era")
    ax.set_title("Era AUC by arm with block-bootstrap 95% interval (drawn features)", fontsize=10)
    fig.tight_layout()
    fig.savefig(p1, dpi=140)
    plt.close(fig)
    p2 = th.outp(cfg, "fig_interval")
    fig, ax = plt.subplots(figsize=(6, 4))
    q = pred.sort_values("M3_year").reset_index(drop=True)
    ax.vlines(q.index, q.lo, q.hi, color=ek.PALETTE["grey"], lw=1, label="label interval")
    ax.scatter(q.index, q.M3_year, s=10, color=ek.PALETTE["blue"], marker="o", label="M3 predicted year", zorder=3)
    ax.set_xlabel("well-feature pair (sorted by predicted year)")
    ax.set_ylabel("construction year")
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title("Predicted year against label interval, out-of-fold", fontsize=10)
    fig.tight_layout()
    fig.savefig(p2, dpi=140)
    plt.close(fig)
    return [p1, p2]


def load_folds(cfg: dict, df: pd.DataFrame, provisional: bool) -> tuple[pd.DataFrame, dict]:
    info = {}
    audit_df = ek.require_audit(th.inp(cfg, "audit_blocks", must_exist=False), allow_missing=provisional)
    if audit_df is None:
        audit = set()
        info["audit"] = NO_AUDIT_LABEL
    else:
        audit = ek.audit_ids(audit_df, roles=("audit", "buffer"))
        info["audit"] = "P2 audit and buffer blocks excluded"
        info["audit_sha256"] = audit_df.attrs.get("sha256")
    if provisional:
        fo = ec.block_folds(df["block_id"], cfg["model"]["n_folds"], ek.child_seed(cfg["master_seed"]))
        info["folds"] = "provisional (deterministic block folds, not the P1 split)"
    else:
        sp = ek.read_split_csv(th.inp(cfg, "split_file"))    # P1-01: canonical role names (heldout -> held_out)
        th.require_columns(sp, ["block_id", "fold", "role"], "split_file")
        h = sp[sp.role == "held_out"]
        if not len(h):
            raise SystemExit(f"split_file {th.inp(cfg, 'split_file')} has no held_out rows")
        fo = dict(zip(h.block_id.astype(int), h.fold.astype(int)))
        info["folds"] = "P1 split file, held_out roles"
        info["split_sha256"] = ek.sha256(th.inp(cfg, "split_file"))
        info["split_file"] = repo_rel(th.inp(cfg, "split_file"))
    df = df[~df["block_id"].isin(audit) & (df["block_id"] >= 0)].copy()
    df["fold"] = df["block_id"].map(fo)
    ek.assert_no_nan(df["fold"], "fold of model rows")
    info["n_audit_blocks_dropped"] = len(audit)
    return df, info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--provisional-folds", action="store_true")
    ap.add_argument("--force-exploratory", action="store_true", help="run below the readiness gate, labelled")
    ap.add_argument("--skip-noise", action="store_true")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    pairs_p = th.inp(cfg, "pairs")
    pairs = pd.read_csv(pairs_p)
    df = pairs[pairs["lo"].notna() & pairs["hi"].notna()].copy()
    if cfg["link"]["exclude_position_only_from_primary"] and "primary" in df:
        df = df[df["primary"].astype(str).str.lower().isin(["true", "1", "1.0"])]
    ec.assert_no_sentinel(df)
    df = add_location_terms(df) if len(df) else df
    ready = readiness(df, cfg)
    summ = {"readiness": ready, "evidence_level": "a", "era_basis": "interval"}
    if not ready["ready"] and not a.force_exploratory:
        js = th.write_json(th.outp(cfg, "model_json"), dict(summ, status="descriptive_only",
                                                            note="Below the readiness gate. Counts only."))
        print(f"below readiness gate {ready}. Wrote counts to {js}")
        return 0
    df, finfo = load_folds(cfg, df, a.provisional_folds)
    df = df.reset_index(drop=True)
    arms = arms_from_cfg(cfg)
    pred, used = oof(df, arms, cfg)
    prim = primary(pred, cfg)
    sec = secondary(pred, cfg)
    summ.update(status="exploratory" if (not ready["ready"] or a.provisional_folds
                                          or finfo.get("audit") == NO_AUDIT_LABEL) else "confirmatory",
                folds=finfo, features_used=used, primary=prim, secondary=sec)
    if not a.skip_noise:
        summ["label_noise"] = label_noise(df, arms, cfg)
    pred = th.tag(pred, "a", summ["status"])
    pred["era_basis"] = "interval"
    pc = th.outp(cfg, "predictions_csv")
    pred.to_csv(pc, index=False)
    js = th.write_json(th.outp(cfg, "model_json"), summ)
    figs = figures(pred, sec, cfg)
    run = ek.new_run("5.2", "era_model", {"model": cfg["model"], "features": cfg["features"],
                                          "provisional": a.provisional_folds},
                     base=th.resolve(cfg["outputs"]["runs"]), why="S5 to S8 era models and primary test.")
    ek.write_provenance(run, inputs=[pairs_p], outputs=[pc, js, *figs], params=cfg["model"],
                        seeds={"master": cfg["master_seed"]})
    print(f"primary {prim['diff']:.3f} [{prim['lo']:.3f}, {prim['hi']:.3f}] -> {prim['decision']}")
    print(pc, js, *figs, sep="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
