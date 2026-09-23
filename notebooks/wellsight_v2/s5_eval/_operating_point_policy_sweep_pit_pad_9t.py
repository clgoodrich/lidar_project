"""Phase 3 of the operating-point plan: sweep every policy family and compare.

WHY
---
Phases 1-2 showed that the operating point should be a CUT OF THE RANKED
CANDIDATE LIST, on Platt-calibrated scores. Every policy below cuts that same
list. They differ in three ways only:

  * what input the policy needs from a person
  * where on the curve a given setting lands
  * whether the held-out result keeps the promise the policy makes

So this sweeps each family over a range of settings and scores all of them on
the same held-out candidates. It does not pick one. The user picks.

POLICIES (all per fold k, LEAVE-ONE-FOLD-OUT: every rule is set on the other
--------  four folds' held-out candidates, never on fold k's labels)
  cost      C_FN / C_FP = r. Keep a candidate when its calibrated probability
            p >= 1 / (1 + r) (Elkan 2001). Promise: lowest expected cost.
            Checked by REGRET against the best cut in hindsight on held-out.
  budget    K candidates checked per km2. Keep the top K x area by score.
            Needs no labels at all. Promise: exactly K per km2.
  recall    Conformal risk control (Angelopoulos et al. 2022) for a target
            recall rho. Loss per calibration block = share of its annotated
            features missed. Pick the highest cutoff whose corrected loss
            (n * mean + 1) / (n + 1) is <= 1 - rho. Promise: expected
            held-out block miss rate <= 1 - rho.
  fbeta     The current practice, moved onto the ranked list: the cut that
            maximises F-beta on the calibration folds. beta = 2 is the "miss
            costs 4x" rule already in use. No promise.

REFERENCES (the pixel cutoffs used today, for scale)
----------
  F1 / F2 pixel cutoff   from the CV5 per-fold CSVs
  deployed pixel cutoff  pit 0.60, pad 0.70, from `_postfilter_tile_candidates.py`.
                         The 20/300 m2 area floor and the morphology are NOT
                         applied here, so this row flatters the deployed filter.

KNOWN LIMITS, STATED
--------------------
  * Precision counts unannotated real features as false. Every precision,
    FP density and calibrated probability is a LOWER bound.
  * The CRC guarantee assumes calibration and held-out blocks are
    exchangeable. They are random blocks of one tile, but scored by
    different fold models, so it holds only approximately. It does NOT hold
    across tiles without re-calibration there.
  * About 90 calibration blocks per fold, so the +1/(n+1) CRC correction is
    about 0.01.
  * A matched pair is credited to the block holding the candidate's centroid.
    A pit on a block edge can be credited to its neighbour. Rare.

Run:
  python notebooks/wellsight_v2/s5_eval/_operating_point_policy_sweep_pit_pad_9t.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2" / "s5_eval"))
from _common import path_for  # noqa: E402
import _cv5_pr_calibration_pit_pad_9t as ph  # noqa: E402

OUT, FIG, K, B = ph.OUT, ph.FIG, ph.K, ph.B
TASKS = ("pit", "pad")

COST_RATIOS = (0.5, 1, 2, 4, 8, 16, 32, 64, 128)
BUDGETS = (2, 5, 10, 15, 20, 25, 30, 40, 50)          # candidates per km2
RECALL_TARGETS = (0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95)
BETAS = (0.5, 1, 2, 3, 4)
DEPLOYED = {"pit": 0.60, "pad": 0.70}

# Policy-family palette. The lost/found set plus sky #5FB4E0. Validated
# 2026-09-23 with the dataviz validator, `--mode light --pairs all`:
# worst pair #A31515/#D97706 dE 21.1 deutan, 22.6 normal; all >= 3:1 contrast.
# No green. Every family also has its own marker, and points carry labels.
FAM_COL = {"cost": "#1F5FA8", "budget": "#D97706", "recall": "#A31515",
           "fbeta": "#5FB4E0"}
FAM_MRK = {"cost": "o", "budget": "s", "recall": "^", "fbeta": "D"}
FAM_NAME = {"cost": "cost ratio C_FN/C_FP", "budget": "review budget, candidates/km2",
            "recall": "recall guarantee (conformal)", "fbeta": "F-beta on other folds"}
TASK_COL = {"pit": "#1F5FA8", "pad": "#A31515"}
TASK_MRK = {"pit": "o", "pad": "^"}
INK, MUTED = ph.INK, ph.MUTED


# ---------------------------------------------------------------------------
# data per fold
# ---------------------------------------------------------------------------
def fold_data(name: str):
    """Everything each fold needs, fitted LEAVE-ONE-FOLD-OUT.

    For fold k the proposal cutoff, the Platt calibrator and every rule's
    calibration set come from the other four folds' held-out blocks. Each was
    scored by a model that never saw it. Fold k's labels are read only to score.
    See `_cv5_pr_calibration_pit_pad_9t.py` for why inner val is not used.
    """
    cv = ph.MODELS[name]
    counts = ph.load_counts(name)
    objs = pd.read_csv(OUT / f"cv5_sweep_objects_{name}_thr0p05to0p95_9t.csv.gz")
    objs = objs[objs.tau == 0.3]
    area = ph.block_area_km2(cv)
    held_all = counts[(counts.split == "heldout") & (counts.tau == 0.3)]

    folds = []
    for k in range(K):
        t_prop, _ = ph.proposal_thr(counts, k)
        oc = ph.calibration_blobs(objs, k, t_prop)
        oh = objs[(objs.fold == k) & (objs.split == "heldout") & np.isclose(objs.thr, t_prop)]
        lr, _, _ = ph.fit_platt(oc.score.to_numpy(), oc.is_tp.to_numpy(int))
        cal = lambda x: lr.predict_proba(ph.logit(x)[:, None])[:, 1]  # noqa: E731
        at = held_all[np.isclose(held_all.thr, t_prop)]
        cgt = at[at.fold != k].set_index("block_id").n_gt.to_dict()
        hgt = at[at.fold == k].set_index("block_id").n_gt.to_dict()
        folds.append(dict(
            k=k, t_prop=t_prop,
            cal_p=cal(oc.score.to_numpy()), cal_tp=oc.is_tp.to_numpy(bool),
            cal_block=oc.block_id.to_numpy(int), cal_gt=cgt,
            held_p=cal(oh.score.to_numpy()), held_tp=oh.is_tp.to_numpy(bool),
            held_block=oh.block_id.to_numpy(int),
            held_blocks=np.array(sorted(hgt)), held_gt=hgt,
            held_km2=sum(area[int(b)] for b in hgt),
            area=area))
    return folds


# ---------------------------------------------------------------------------
# rules, set on the other four folds only
# ---------------------------------------------------------------------------
def rule_cost(f, r):
    return ("thr", 1.0 / (1.0 + r))


def rule_budget(f, kpk):
    return ("topn", int(np.floor(kpk * f["held_km2"])))


def rule_fbeta(f, beta):
    """The cut that maximises F-beta on the calibration folds."""
    o = np.argsort(-f["cal_p"], kind="stable")
    tp = np.cumsum(f["cal_tp"][o])
    n = np.arange(1, len(o) + 1)
    n_gt = sum(f["cal_gt"].values())
    P, R = tp / n, tp / n_gt
    b2 = beta ** 2
    F = np.where(P + R > 0, (1 + b2) * P * R / np.maximum(b2 * P + R, 1e-12), 0)
    i = int(np.argmax(F))
    return ("thr", float(f["cal_p"][o][i]))


def rule_crc(f, rho):
    """Highest cutoff whose CRC-corrected calibration block miss rate <= 1 - rho."""
    alpha = 1.0 - rho
    blocks = [b for b, n in f["cal_gt"].items() if n > 0]
    n = len(blocks)
    gt = np.array([f["cal_gt"][b] for b in blocks], float)
    bpos = {b: i for i, b in enumerate(blocks)}
    tp_idx = np.array([bpos.get(int(b), -1) for b in f["cal_block"]])
    cands = np.unique(np.concatenate([f["cal_p"], [0.0]]))[::-1]   # high -> low
    for lam in cands:                       # loss only falls as lam falls
        hit = (f["cal_p"] >= lam) & f["cal_tp"] & (tp_idx >= 0)
        tp_b = np.bincount(tp_idx[hit], minlength=n)
        loss = 1.0 - np.minimum(tp_b, gt) / gt
        if (n * loss.mean() + 1.0) / (n + 1.0) <= alpha:
            return ("thr", float(lam))
    return ("infeasible", 0.0)              # keep everything; flagged in output


def apply_rule(f, rule):
    kind, v = rule
    if kind in ("thr", "infeasible"):
        return f["held_p"] >= v
    keep = np.zeros(len(f["held_p"]), bool)
    keep[np.argsort(-f["held_p"], kind="stable")[:v]] = True
    return keep


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
def score(folds, keeps, W_cache):
    """Pooled held-out metrics, per-fold recall, and a block-bootstrap CI."""
    blocks = np.array([(f["k"], b) for f in folds for b in f["held_blocks"]])
    key = blocks.tobytes()
    if key not in W_cache:
        W_cache[key] = ph.block_plan(blocks)
    W = W_cache[key]
    tp_b = np.zeros(len(blocks)); kept_b = np.zeros(len(blocks)); gt_b = np.zeros(len(blocks))
    km2_b = np.zeros(len(blocks))
    idx = {(int(k), int(b)): i for i, (k, b) in enumerate(blocks)}
    per_fold_R = []
    for f, keep in zip(folds, keeps):
        for b in f["held_blocks"]:
            i = idx[(f["k"], int(b))]
            m = keep & (f["held_block"] == b)
            kept_b[i] = m.sum()
            tp_b[i] = (m & f["held_tp"]).sum()
            gt_b[i] = f["held_gt"].get(int(b), 0)
            km2_b[i] = f["area"][int(b)]
        n_gt_f = sum(f["held_gt"].values())
        per_fold_R.append((keep & f["held_tp"]).sum() / n_gt_f)
    tp, kept, gt, km2 = tp_b.sum(), kept_b.sum(), gt_b.sum(), km2_b.sum()
    # The conformal rule guarantees the MEAN over blocks of the block miss rate,
    # not pooled recall. Report the guaranteed quantity beside the pooled one.
    has = gt_b > 0
    block_mean_recall = float(np.mean(np.minimum(tp_b[has], gt_b[has]) / gt_b[has]))
    R = tp / gt
    P = tp / kept if kept else np.nan
    Rb = (W @ tp_b) / (W @ gt_b)
    with np.errstate(invalid="ignore", divide="ignore"):
        Pb = (W @ tp_b) / (W @ kept_b)
    return dict(
        recall=R, recall_lo=np.percentile(Rb, 2.5), recall_hi=np.percentile(Rb, 97.5),
        precision=P, precision_lo=np.nanpercentile(Pb, 2.5),
        precision_hi=np.nanpercentile(Pb, 97.5),
        candidates=int(kept), tp=int(tp), fp=int(kept - tp), n_gt=int(gt),
        candidates_per_km2=kept / km2, fp_per_km2=(kept - tp) / km2,
        recall_fold_min=float(np.min(per_fold_R)), recall_fold_max=float(np.max(per_fold_R)),
        recall_per_fold=[round(float(x), 4) for x in per_fold_R],
        block_mean_recall=block_mean_recall)


def oracle_regret(folds, keeps, r):
    """(cost of the rule - best achievable cost in hindsight) per annotated feature.

    Cost is in units of one false alarm: FP + r * FN. The hindsight best is the
    best single cutoff on each held-out fold, the most a cutoff rule could do.
    """
    tot, best_all, gt_all = 0.0, 0.0, 0
    for f, keep in zip(folds, keeps):
        n_gt = sum(f["held_gt"].values())
        gt_all += n_gt
        tp, fp = (keep & f["held_tp"]).sum(), (keep & ~f["held_tp"]).sum()
        cost_rule = fp + r * (n_gt - tp)
        o = np.argsort(-f["held_p"], kind="stable")
        ctp = np.concatenate([[0], np.cumsum(f["held_tp"][o])])
        cfp = np.concatenate([[0], np.cumsum(~f["held_tp"][o])])
        best = np.min(cfp + r * (n_gt - ctp))
        tot += cost_rule - best
        best_all += best
    return tot / gt_all, tot / best_all


def reference_rows(name, folds, W_cache):
    """Today's pixel-cutoff operating points, for scale."""
    rows = []
    base = {"pit": path_for("models") / "pit" / "unet_cv5",
            "pad": path_for("models") / "pad" / "unet_cv5"}[name]
    pf = pd.read_csv(base / f"{name}_cv5_per_fold_9t.csv")
    km2 = sum(f["held_km2"] for f in folds)
    for obj in ("f1", "f2"):
        g = pf[pf.objective == obj]
        tp = (g.recall_iou30 * g.n_heldout).round().sum()
        rows.append(dict(task=name, family="reference", setting=f"{obj.upper()} pixel cutoff",
                         recall=tp / g.n_heldout.sum(), precision=tp / g.n_pred_heldout.sum(),
                         candidates=int(g.n_pred_heldout.sum()),
                         candidates_per_km2=g.n_pred_heldout.sum() / km2,
                         fp_per_km2=(g.n_pred_heldout.sum() - tp) / km2,
                         recall_fold_min=g.recall_iou30.min(),
                         recall_fold_max=g.recall_iou30.max(),
                         rule_per_fold=g.prob_threshold.tolist()))
    c = ph.load_counts(name)
    c = c[(c.split == "heldout") & (c.tau == 0.3) & np.isclose(c.thr, DEPLOYED[name])]
    tp, n, gt = c.tp_pred.sum(), c.n_pred.sum(), c.n_gt.sum()
    pr = c.groupby("fold")[["tp_gt", "n_gt"]].sum().pipe(lambda d: d.tp_gt / d.n_gt)
    rows.append(dict(task=name, family="reference",
                     setting=f"deployed pixel cutoff {DEPLOYED[name]:.2f} (no area floor)",
                     recall=c.tp_gt.sum() / gt, precision=tp / n, candidates=int(n),
                     candidates_per_km2=n / km2, fp_per_km2=(n - tp) / km2,
                     recall_fold_min=pr.min(), recall_fold_max=pr.max(),
                     rule_per_fold=[DEPLOYED[name]] * K))
    return rows


def sweep(name):
    folds = fold_data(name)
    W_cache, rows = {}, []
    fams = (("cost", COST_RATIOS, rule_cost), ("budget", BUDGETS, rule_budget),
            ("recall", RECALL_TARGETS, rule_crc), ("fbeta", BETAS, rule_fbeta))
    for fam, settings, rule_fn in fams:
        for s in settings:
            rules = [rule_fn(f, s) for f in folds]
            keeps = [apply_rule(f, r) for f, r in zip(folds, rules)]
            m = score(folds, keeps, W_cache)
            row = dict(task=name, family=fam, setting=s, **m,
                       rule_per_fold=[round(r[1], 4) if r[0] != "topn" else r[1] for r in rules],
                       infeasible_folds=sum(r[0] == "infeasible" for r in rules))
            if fam == "cost":
                row["regret_per_feature"], row["regret_relative"] = oracle_regret(folds, keeps, s)
            if fam == "recall":
                row["target_met_pooled"] = bool(m["recall"] >= s)
                row["target_met_block_mean"] = bool(m["block_mean_recall"] >= s)
                row["folds_meeting_target"] = int(sum(x >= s for x in m["recall_per_fold"]))
            rows.append(row)
            print(f"  {name} {fam:7s} {str(s):>5s}: R {m['recall']:.3f} "
                  f"[{m['recall_lo']:.3f}-{m['recall_hi']:.3f}] P {m['precision']:.3f} "
                  f"cand/km2 {m['candidates_per_km2']:5.1f} FP/km2 {m['fp_per_km2']:5.1f} "
                  f"fold R {m['recall_fold_min']:.3f}-{m['recall_fold_max']:.3f}"
                  + (f" regret {row['regret_per_feature']:.3f} ({100 * row['regret_relative']:.1f}%)"
                     if fam == "cost" else "")
                  + (f" block-mean R {m['block_mean_recall']:.3f}" if fam == "recall" else "")
                  + (f" infeasible {row['infeasible_folds']}" if row["infeasible_folds"] else ""))
    rows += reference_rows(name, folds, W_cache)
    return rows, folds


def backdrop(folds):
    """Pooled ranked curve with each fold cut at the same calibrated cutoff."""
    grid = np.linspace(0, 1, 401)[::-1]
    gt = sum(sum(f["held_gt"].values()) for f in folds)
    km2 = sum(f["held_km2"] for f in folds)
    R, P, C = [], [], []
    for lam in grid:
        tp = sum((f["held_tp"] & (f["held_p"] >= lam)).sum() for f in folds)
        n = sum((f["held_p"] >= lam).sum() for f in folds)
        R.append(tp / gt); P.append(tp / n if n else np.nan); C.append(n / km2)
    return np.array(R), np.array(P), np.array(C)


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------
# Label a sparse subset. The high-recall corner is crowded, so only the
# settings a reader is likely to pick are named there.
LABEL_SETTINGS = {"cost": {1}, "budget": {5, 10, 20, 30, 40},
                  "recall": {0.7, 0.9}, "fbeta": {2}}


def fig_operating_points(df, bd):
    FIG.mkdir(parents=True, exist_ok=True)
    paths = []
    for kind in ("recall_vs_candidates", "precision_vs_recall"):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
        for ax, name in zip(axes, TASKS):
            R, P, C = bd[name]
            if kind == "recall_vs_candidates":
                ax.plot(C, R, color=MUTED, lw=1.2, zorder=1, label="all cuts of the ranked list")
            else:
                ax.plot(R, P, color=MUTED, lw=1.2, zorder=1, label="all cuts of the ranked list")
            d = df[df.task == name]
            for fam in FAM_COL:
                g = d[d.family == fam]
                x, y = ((g.candidates_per_km2, g.recall) if kind == "recall_vs_candidates"
                        else (g.recall, g.precision))
                ax.scatter(x, y, s=46, color=FAM_COL[fam], marker=FAM_MRK[fam],
                           edgecolor="white", linewidth=1.2, zorder=3, label=FAM_NAME[fam])
                for xi, yi, s in zip(x, y, g.setting):
                    if float(s) in LABEL_SETTINGS[fam]:
                        ax.annotate(f"{s:g}", (xi, yi), xytext=(4, -9), textcoords="offset points",
                                    fontsize=6.5, color=INK)
            ref = d[d.family == "reference"]
            for (_, r), mk in zip(ref.iterrows(), ("x", "+", "*")):
                x, y = ((r.candidates_per_km2, r.recall) if kind == "recall_vs_candidates"
                        else (r.recall, r.precision))
                ax.scatter([x], [y], s=60, color=INK, marker=mk, zorder=4,
                           label=f"today: {r.setting}")
            ph._style(ax)
            if kind == "recall_vs_candidates":
                ax.set_xlabel("candidates to check per km2 (held-out)", color=INK, fontsize=9)
                ax.set_ylabel("recall (held-out, IoU 0.3)", color=INK, fontsize=9)
                ax.set_ylim(0, 1); ax.set_xlim(0, None)
            else:
                ax.set_xlabel("recall (held-out, IoU 0.3)", color=INK, fontsize=9)
                ax.set_ylabel("precision (held-out, lower bound)", color=INK, fontsize=9)
                ax.set_xlim(0, 1); ax.set_ylim(0, 1)
            ax.set_title(name, color=INK, fontsize=10, loc="left")
            ax.legend(fontsize=6.5, frameon=False, labelcolor=INK, loc="lower right")
        head = ("Where each policy lands: recall against candidates checked per km2"
                if kind == "recall_vs_candidates"
                else "Where each policy lands: precision against recall")
        fig.suptitle(head + " - 5-fold held-out, 9t", color=INK, fontsize=11, x=0.01, ha="left")
        fig.text(0.01, 0.005, "Every policy cuts the same ranked list of Platt-calibrated candidates. "
                 "Labels are the policy setting. Rules were set on the other four folds; points are held-out.",
                 color=MUTED, fontsize=7)
        fig.tight_layout(rect=(0, 0.03, 1, 0.95))
        p = FIG / f"policy_sweep_{kind}_cost_budget_conformal_fbeta_heldout_cv5_iou0p30_pit_pad_9t.png"
        fig.savefig(p, dpi=200)
        plt.close(fig)
        paths.append(p)
    return paths


def fig_promises(df):
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.3))
    ax = axes[0]
    ax.plot([0.55, 1], [0.55, 1], color=MUTED, lw=1, ls="--", label="realized = target")
    for name in TASKS:
        g = df[(df.task == name) & (df.family == "recall")]
        ax.plot(g.setting, g.recall, color=TASK_COL[name], marker=TASK_MRK[name], lw=2,
                label=f"{name}, pooled")
        ax.vlines(g.setting.astype(float), g.recall_fold_min, g.recall_fold_max,
                  color=TASK_COL[name], lw=1, alpha=0.6)
    ph._style(ax)
    ax.set_xlabel("target recall", color=INK, fontsize=9)
    ax.set_ylabel("held-out recall (bar = fold min-max)", color=INK, fontsize=9)
    ax.set_title("Recall guarantee: is the target met?", color=INK, fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False, labelcolor=INK)

    ax = axes[1]
    for name in TASKS:
        g = df[(df.task == name) & (df.family == "cost")]
        ax.plot(g.setting, 100 * g.regret_relative, color=TASK_COL[name], marker=TASK_MRK[name],
                lw=2, label=name)
    ax.set_xscale("log", base=2)
    ph._style(ax)
    ax.set_xlabel("cost ratio C_FN / C_FP (log2)", color=INK, fontsize=9)
    ax.set_ylabel("cost above best cut in hindsight (%)", color=INK, fontsize=9)
    ax.set_ylim(0, None)
    ax.set_title("Cost ratio: cost above the best cut in hindsight", color=INK, fontsize=10,
                 loc="left")
    ax.legend(fontsize=7, frameon=False, labelcolor=INK)

    ax = axes[2]
    for name in TASKS:
        g = df[(df.task == name) & (df.family == "budget")]
        ax.plot(g.setting, g.recall, color=TASK_COL[name], marker=TASK_MRK[name], lw=2, label=name)
        ax.fill_between(g.setting.astype(float), g.recall_lo, g.recall_hi,
                        color=TASK_COL[name], alpha=0.15, lw=0)
    ph._style(ax)
    ax.set_ylim(0, 1)
    ax.set_xlabel("review budget, candidates per km2", color=INK, fontsize=9)
    ax.set_ylabel("held-out recall (band = 95% block bootstrap)", color=INK, fontsize=9)
    ax.set_title("Review budget: recall bought per unit of effort", color=INK, fontsize=10,
                 loc="left")
    ax.legend(fontsize=7, frameon=False, labelcolor=INK)
    fig.suptitle("Does each policy keep its promise? 5-fold held-out, 9t, IoU 0.3",
                 color=INK, fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    p = FIG / "policy_sweep_promise_check_conformal_cost_regret_budget_heldout_cv5_iou0p30_pit_pad_9t.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p


def main() -> int:
    allrows, bd = [], {}
    for name in TASKS:
        print(f"== {name} ==")
        rows, folds = sweep(name)
        allrows += rows
        bd[name] = backdrop(folds)
    df = pd.DataFrame(allrows)
    csv = OUT / "policy_sweep_cost_budget_conformal_fbeta_heldout_cv5_iou0p30_pit_pad_9t.csv"
    df.to_csv(csv, index=False)
    js = OUT / "policy_sweep_cost_budget_conformal_fbeta_heldout_cv5_iou0p30_pit_pad_9t.json"
    js.write_text(json.dumps(json.loads(df.to_json(orient="records")), indent=1))
    figs = fig_operating_points(df, bd) + [fig_promises(df)]
    print(f"\nwrote {csv}\nwrote {js}")
    for f in figs:
        print(f"wrote {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
