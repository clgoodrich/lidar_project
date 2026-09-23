"""Phase 1 + 2 of the operating-point plan: threshold-free PR, FROC and calibration.

WHY
---
Every pit and pad number we quote so far is read at ONE cutoff, picked on
inner val by F1 or F2. The F2 choice says a miss costs four false alarms. That
ratio is ours, not the data's. Comparing two models at their own chosen
cutoffs mixes "which model ranks better" with "where did we cut".

Phase 1 separates the two. It scores the whole held-out precision-recall curve
at once, so no cutoff has to be defended to compare models.

HEADLINE -- the ranked candidate list. Each fold's candidates are the blobs at
its PROPOSAL cutoff (see Phase 2 below for how that cutoff is chosen), ranked
by score. Walking down the list traces the curve.

  AP        area under the held-out precision-recall curve, VOC-style: at each
            recall the precision is the best achieved at that recall or higher
            (Everingham et al. 2010).
  FROC      recall against false positives per km2 of held-out ground
            (Chakraborty 1989). Phase 3's review-budget policy reads from it.
  CI        95% block bootstrap, resampling 375 m blocks within each fold.
            Blocks are the unit the folds were split on, so resampling pits
            would understate the spread (pits cluster on pads).
  paired    vendor vs SMRF ground: per-fold AP difference, paired t, and a
            paired bootstrap on the same resampled blocks.

SECONDARY -- the pixel-cutoff sweep, 0.05 to 0.95. Kept, and clearly labelled,
because it was the first design and it shows something useful. Raising the
cutoff shrinks blobs to their cores, so they stop matching the annotated
outline. Pit precision peaks near cutoff 0.58 and then FALLS. The sweep curve
therefore mixes outlining with ranking. Raising the pixel cutoff is the wrong
lever for precision.

Phase 2 asks whether a score means a probability. Two levels:

  object    candidate blobs at a PROPOSAL cutoff: for fold k, the cutoff with
            the highest recall pooled over the OTHER four folds' held-out
            blocks (ties -> higher cutoff). Recall is the only criterion, so
            this cutoff decides what reaches the ranked list, not the
            precision/recall balance. Each blob's score is its mean probability
            (as in the CV scripts). A Platt fit (Platt 1999) and an isotonic fit
            (Zadrozny & Elkan 2002) are trained on the other four folds'
            held-out blobs and checked on fold k's.
  pixel     the raw floor/pad probability against the label raster. A Platt fit
            on logit(p), again trained on the other four folds' held-out
            pixels, is temperature scaling (Guo et al. 2017) plus a bias
            term. Only one class probability was saved, so the full softmax
            temperature cannot be fitted. The fitted slope says whether the
            net is over- or under-confident; the intercept shows how far focal
            alpha has shifted the scores.

  ECE       expected calibration error (Naeini et al. 2015): the weighted gap
            between mean score and hit rate across bins.

Both calibrators are monotone, so neither changes AP. They change what a score
MEANS, which Phase 3's cost-ratio policy needs.

WHY LEAVE-ONE-FOLD-OUT, NOT INNER VAL
-------------------------------------
The first run fitted everything on each fold's inner-val blocks. That split
cannot be reproduced. The manifests hold features with no block (209 pits, 345
pads), so the CV scripts' `sorted(set(block_id))` contains NaN. NaN's hash is
per-object and sorting around it depends on input order, so the inner-val draw
changes between processes. The pit training log shows 64 inner-val pits in
fold 2, and a re-draw gives 63 or 61. Matching the logged counts leaves 2-6
candidate sets in 8 of 10 folds, so the true sets cannot be recovered. A
re-drawn "inner val" can therefore include blocks the fold's model trained on.

Fold k's other-fold held-out blocks were each scored by a model that never saw
them. Fitting on them is clean and reproducible, and it never reads fold k's
labels. It assumes the five fold models behave alike. That is also the honest
deployment case, where a calibrator fitted on known ground meets a new tile.

KNOWN BIAS, STATED
------------------
Precision counts any unannotated real pit as a false positive. The 2026 pad
review moved pad precision from 0.623 to 0.898. So every precision, AP, FP/km2
and calibrated probability here is a LOWER bound. Phase 5 fixes this.

Inputs are written by `_cv5_pr_sweep_records_pit_pad_9t.py`. CPU only.

Run:
  python notebooks/wellsight_v2/s5_eval/_cv5_pr_calibration_pit_pad_9t.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize as _rasterize
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2" / "s3_train"))
from _common import normalize_ids, path_for  # noqa: E402
import _pad_unet_cv5 as padcv  # noqa: E402
import _pit_unet_cv5 as pitcv  # noqa: E402

OUT = path_for("results_9t") / "operating_point"
FIG = OUT / "figures"
K = 5
B = 2000
SEED = 20260923
FP_DENSITIES = (1, 2, 5, 10, 20, 50)          # FP per km2, reported points on FROC
N_BINS_OBJ = 10                                # equal-count bins, ~70 blobs each
N_BINS_PIX = 15                                # equal-width, as in Guo et al. 2017
PIX_SAMPLE = 2_000_000                         # pixels sampled per split per fold

MODELS = {"pit": pitcv, "pit_smrf": pitcv, "pad": padcv}
LABEL = {"pit": "pit, vendor ground", "pit_smrf": "pit, SMRF ground",
         "pad": "pad, vendor ground"}
# Reused lost/found palette from CLAUDE.md. Re-validated 2026-09-23 with the
# dataviz validator, `--mode light --pairs all`, surface #fcfcfb: worst pair
# #A31515/#D97706 dE 21.1 deutan, 22.6 normal, tritan 18.9; all >= 3:1 contrast.
# No green anywhere. Every series also has its own marker shape.
COL = {"pit": "#1F5FA8", "pit_smrf": "#D97706", "pad": "#A31515"}
MRK = {"pit": "o", "pit_smrf": "s", "pad": "^"}
CAL_COL = {"raw": "#A31515", "platt": "#1F5FA8", "isotonic": "#D97706"}
CAL_MRK = {"raw": "^", "platt": "o", "isotonic": "s"}
INK, MUTED = "#1d1d1b", "#6b6b66"


# ---------------------------------------------------------------------------
# curve arithmetic
# ---------------------------------------------------------------------------
def ap_envelope(R: np.ndarray, P: np.ndarray) -> float:
    """VOC-style AP from (recall, precision) points of a threshold sweep."""
    ok = np.isfinite(R) & np.isfinite(P)
    R, P = R[ok], P[ok]
    if not len(R):
        return 0.0
    o = np.argsort(R, kind="stable")
    R, P = R[o], P[o]
    env = np.maximum.accumulate(P[::-1])[::-1]
    dR = np.diff(np.concatenate([[0.0], R]))
    return float((dR * env).sum())


def recall_at_fp(R, FPd, d):
    """Best recall reached at or under FP density d. Conservative: no interpolation."""
    ok = FPd <= d
    return float(R[ok].max()) if ok.any() else 0.0


def curve(tpg, ng, tpp, npred):
    with np.errstate(invalid="ignore", divide="ignore"):
        R = tpg / ng
        P = np.where(npred > 0, tpp / npred, np.nan)
    return R, P


# ---------------------------------------------------------------------------
# Phase 1
# ---------------------------------------------------------------------------
def load_counts(name):
    df = pd.read_csv(OUT / f"cv5_sweep_counts_per_block_{name}_thr0p05to0p95_9t.csv")
    return df


def block_area_km2(cv) -> dict[int, float]:
    blocks = gpd.read_file(cv.BLOCKS, layer="blocks").to_crs(cv.CRS)
    return dict(zip(blocks.block_id.astype(int), blocks.geometry.area / 1e6))


def sanity_vs_cv5(name, held):
    """At cutoff 0.30 the pooled held-out numbers must equal the CV5 run's own."""
    base = name.split("_")[0]
    cv_dir = {"pit": path_for("models") / "pit" / "unet_cv5",
              "pit_smrf": path_for("models") / "pit" / "unet_cv5_smrf",
              "pad": path_for("models") / "pad" / "unet_cv5"}[name]
    cf = cv_dir / f"{base}_cv5_recovery_curve_9t.csv"
    if not cf.exists():
        return "no recovery-curve CSV to compare against"
    c = pd.read_csv(cf)
    c = c[np.isclose(c.prob_threshold, 0.30)]
    h = held[(np.isclose(held.thr, 0.30)) & (held.tau == 0.3)]
    msgs = []
    for k in range(K):
        a = c[c.fold == k].iloc[0]
        b = h[h.fold == k]
        r = b.tp_gt.sum() / b.n_gt.sum()
        if b.n_gt.sum() != a.n_heldout or b.n_pred.sum() != a.n_pred_heldout \
                or not np.isclose(r, a.recall_iou30):
            msgs.append(f"fold {k}: sweep n_gt {b.n_gt.sum()} n_pred {b.n_pred.sum()} "
                        f"R {r:.4f} vs CV5 {a.n_heldout} {a.n_pred_heldout} "
                        f"{a.recall_iou30:.4f}")
    return "MATCH at 0.30 on every fold" if not msgs else "; ".join(msgs)


_PLANS: dict[bytes, np.ndarray] = {}


def block_plan(blocks: np.ndarray) -> np.ndarray:
    """Bootstrap weights, B x n_blocks, resampling blocks WITHIN each fold.

    Cached by block list and seeded, so every model and every analysis that
    sees the same blocks gets the SAME replicates. That is what makes the
    vendor/SMRF comparison paired.
    """
    key = blocks.tobytes()
    if key not in _PLANS:
        rng = np.random.default_rng(SEED)
        W = np.zeros((B, len(blocks)))
        for k in range(K):
            idx = np.where(blocks[:, 0] == k)[0]
            W[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1 / len(idx)), size=B)
        _PLANS[key] = W
    return _PLANS[key]


def paired_compare(summary, boot_store, names):
    """SMRF minus vendor: per-fold AP difference, paired t, paired bootstrap."""
    paired = {}
    if "pit" not in names or "pit_smrf" not in names:
        return paired
    for tau in (0.3, 0.5):
        a, b = boot_store[("pit_smrf", tau)], boot_store[("pit", tau)]
        d_fold = a["per_fold"] - b["per_fold"]
        t = d_fold.mean() / (d_fold.std(ddof=1) / np.sqrt(K))
        d_b = a["ap"] - b["ap"]
        paired[f"iou{tau}"] = {
            "delta_AP_smrf_minus_vendor": round(
                summary["pit_smrf"][f"iou{tau}"]["AP"] - summary["pit"][f"iou{tau}"]["AP"], 4),
            "per_fold_delta": [round(float(x), 4) for x in d_fold],
            "paired_t_df4": round(float(t), 2),
            "paired_bootstrap_ci95": [round(float(np.percentile(d_b, 2.5)), 4),
                                      round(float(np.percentile(d_b, 97.5)), 4)],
            "share_of_replicates_smrf_better": round(float((d_b > 0).mean()), 3),
        }
        print(f"  paired SMRF-vendor IoU {tau}: {paired[f'iou{tau}']}")
    return paired


def proposal_thr(counts: pd.DataFrame, k: int) -> tuple[float, float]:
    """Fold k's proposal cutoff: highest recall pooled over the OTHER folds'
    held-out blocks, at IoU 0.3, ties -> higher.

    Recall is the only criterion. This cutoff decides which blobs reach the
    ranked list. It does not set the precision/recall balance -- the rank
    cut in Phase 3 does that. Fold k's own labels are never read here.
    """
    h = counts[(counts.split == "heldout") & (counts.tau == 0.3) & (counts.fold != k)]
    g = h.groupby("thr")[["tp_gt", "n_gt"]].sum()
    r = (g.tp_gt / g.n_gt).to_numpy()
    best = r.max()
    return float(g.index.to_numpy()[np.isclose(r, best)].max()), float(best)


def calibration_blobs(objs: pd.DataFrame, k: int, thr: float) -> pd.DataFrame:
    """The other four folds' held-out blobs at fold k's proposal cutoff."""
    return objs[(objs.split == "heldout") & (objs.fold != k) & np.isclose(objs.thr, thr)]


def ranked_curves(order_w: np.ndarray, tp: np.ndarray, n_gt: np.ndarray,
                  km2: np.ndarray):
    """Vectorised ranked-list curves. order_w is (reps x n_obj) object weights
    already in descending-score order; n_gt and km2 are per replicate."""
    ctp = np.cumsum(order_w * tp, axis=1)
    cn = np.cumsum(order_w, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        R = ctp / n_gt[:, None]
        P = np.where(cn > 0, ctp / cn, 0.0)
    FPd = (cn - ctp) / km2[:, None]
    env = np.maximum.accumulate(P[:, ::-1], axis=1)[:, ::-1]
    dR = np.diff(np.concatenate([np.zeros((len(R), 1)), R], axis=1), axis=1)
    ap = (dR * env).sum(1)
    rfp = {d: np.where(FPd <= d, R, 0.0).max(1) for d in FP_DENSITIES}
    return R, P, FPd, ap, rfp


def phase1_ranked(names):
    """HEADLINE Phase 1 metric: AP of the ranked candidate list.

    Candidates are the blobs at each fold's proposal cutoff, ranked by score.
    This is standard detection AP. Its recall ceiling is the recall at the
    proposal cutoff. The cutoff SWEEP (phase1_sweep) is not used for this,
    because raising the pixel cutoff shrinks blobs to their cores and they
    stop matching the annotated outline -- the sweep measures delineation
    and ranking at once.

    Scores from five fold models are pooled into one ranking for the pooled
    curve and its bootstrap. The per-fold APs, each from one model, carry the
    paired test.
    """
    summary, curve_rows, boot_store, props = {}, [], {}, {}
    for name in names:
        cv = MODELS[name]
        counts = load_counts(name)
        held = counts[counts.split == "heldout"]
        area = block_area_km2(cv)
        objs = pd.read_csv(OUT / f"cv5_sweep_objects_{name}_thr0p05to0p95_9t.csv.gz")
        blocks = held[["fold", "block_id"]].drop_duplicates().sort_values(
            ["fold", "block_id"]).to_numpy()
        W = block_plan(blocks)
        km2 = np.array([area[int(b)] for b in blocks[:, 1]])
        bidx = {(int(f), int(b)): i for i, (f, b) in enumerate(blocks)}
        props[name] = {k: proposal_thr(counts, k) for k in range(K)}
        summary[name] = {"proposal_thr_per_fold": {k: v[0] for k, v in props[name].items()},
                         "other_folds_recall_at_proposal": {k: round(v[1], 4)
                                                            for k, v in props[name].items()}}
        for tau in (0.3, 0.5):
            sel_o, ngt_b = [], np.zeros(len(blocks))
            for k in range(K):
                t = props[name][k][0]
                o = objs[(objs.fold == k) & (objs.split == "heldout") & (objs.tau == tau)
                         & np.isclose(objs.thr, t)]
                sel_o.append(o)
                h = held[(held.fold == k) & (held.tau == tau) & np.isclose(held.thr, t)]
                for r in h.itertuples():
                    ngt_b[bidx[(k, int(r.block_id))]] = r.n_gt
            o = pd.concat(sel_o).sort_values("score", ascending=False, kind="stable")
            oi = np.array([bidx[(int(f), int(b))] for f, b in zip(o.fold, o.block_id)])
            tp = o.is_tp.to_numpy(float)
            # point estimate = the all-ones replicate
            R, P, FPd, ap, rfp = ranked_curves(np.ones((1, len(o))), tp,
                                               np.array([ngt_b.sum()]), np.array([km2.sum()]))
            per_fold = []
            for k in range(K):
                m = o.fold.to_numpy() == k
                fb = blocks[:, 0] == k
                per_fold.append(float(ranked_curves(np.ones((1, m.sum())), tp[m],
                                                    np.array([ngt_b[fb].sum()]),
                                                    np.array([km2[fb].sum()]))[3][0]))
            _, _, _, ap_b, rfp_b = ranked_curves(W[:, oi], tp, W @ ngt_b, W @ km2)
            boot_store[(name, tau)] = {"ap": ap_b, "per_fold": np.array(per_fold)}
            summary[name][f"iou{tau}"] = {
                "AP": round(float(ap[0]), 4),
                "AP_ci95": [round(float(np.percentile(ap_b, 2.5)), 4),
                            round(float(np.percentile(ap_b, 97.5)), 4)],
                "AP_per_fold": [round(x, 4) for x in per_fold],
                "AP_per_fold_mean": round(float(np.mean(per_fold)), 4),
                "AP_per_fold_sd": round(float(np.std(per_fold, ddof=1)), 4),
                "recall_ceiling_at_proposal": round(float(R[0, -1]), 4),
                "n_candidates": int(len(o)), "n_gt": int(ngt_b.sum()),
                "heldout_area_km2": round(float(km2.sum()), 3),
                "recall_at_fp_per_km2": {
                    str(d): {"recall": round(float(rfp[d][0]), 4),
                             "ci95": [round(float(np.percentile(rfp_b[d], 2.5)), 4),
                                      round(float(np.percentile(rfp_b[d], 97.5)), 4)]}
                    for d in FP_DENSITIES},
            }
            for i in range(len(o)):
                curve_rows.append(dict(model=name, tau=tau, rank=i + 1,
                                       score=float(o.score.iloc[i]), recall=R[0, i],
                                       precision=P[0, i], fp_per_km2=FPd[0, i]))
            print(f"    {name} IoU {tau}: ranked AP {ap[0]:.3f} "
                  f"[{np.percentile(ap_b, 2.5):.3f}, {np.percentile(ap_b, 97.5):.3f}]  "
                  f"per-fold {np.mean(per_fold):.3f} sd {np.std(per_fold, ddof=1):.3f}  "
                  f"ceiling {R[0, -1]:.3f}")
    return summary, paired_compare(summary, boot_store, names), pd.DataFrame(curve_rows), props


def phase1_sweep(names):
    """SECONDARY: AP of the curve traced by sweeping the pixel cutoff.

    Kept because it shows the cutoff is the wrong precision lever: pit
    precision peaks near 0.58 and then FALLS, because blobs shrink to their
    cores and miss IoU against the annotated outline.
    """
    summary, curves_rows, boot_store = {}, [], {}
    for name in names:
        cv = MODELS[name]
        df = load_counts(name)
        held = df[df.split == "heldout"]
        area = block_area_km2(cv)
        summary[name] = {"sanity_vs_cv5_at_0p30": sanity_vs_cv5(name, held)}
        print(f"  {name}: {summary[name]['sanity_vs_cv5_at_0p30']}")
        thr = np.sort(held.thr.unique())
        blocks = held[["fold", "block_id"]].drop_duplicates().sort_values(
            ["fold", "block_id"]).to_numpy()
        W = block_plan(blocks)
        km2 = np.array([area[int(b)] for b in blocks[:, 1]])
        for tau in (0.3, 0.5):
            h = held[held.tau == tau]
            cube = {c: h.pivot_table(index=["fold", "block_id"], columns="thr",
                                     values=c, aggfunc="sum")
                    .reindex(pd.MultiIndex.from_arrays(blocks.T), fill_value=0)[thr]
                    .to_numpy(float)
                    for c in ("tp_gt", "n_gt", "tp_pred", "n_pred")}
            tg, ng, tp, npd = (cube[c].sum(0) for c in ("tp_gt", "n_gt", "tp_pred", "n_pred"))
            R, P = curve(tg, ng, tp, npd)
            FPd = (npd - tp) / km2.sum()
            ap = ap_envelope(R, P)
            per_fold = []
            for k in range(K):
                m = blocks[:, 0] == k
                s = {c: cube[c][m].sum(0) for c in cube}
                per_fold.append(ap_envelope(*curve(s["tp_gt"], s["n_gt"],
                                                   s["tp_pred"], s["n_pred"])))
            # bootstrap
            bs = {c: W @ cube[c] for c in cube}
            bkm2 = W @ km2
            ap_b = np.array([ap_envelope(*curve(bs["tp_gt"][i], bs["n_gt"][i],
                                                bs["tp_pred"][i], bs["n_pred"][i]))
                             for i in range(B)])
            rfp = {d: recall_at_fp(R, FPd, d) for d in FP_DENSITIES}
            rfp_b = {d: np.array([recall_at_fp(
                bs["tp_gt"][i] / bs["n_gt"][i],
                (bs["n_pred"][i] - bs["tp_pred"][i]) / bkm2[i], d) for i in range(B)])
                for d in FP_DENSITIES}
            boot_store[(name, tau)] = {"ap": ap_b, "per_fold": np.array(per_fold)}
            summary[name][f"iou{tau}"] = {
                "AP": round(ap, 4),
                "AP_ci95": [round(float(np.percentile(ap_b, 2.5)), 4),
                            round(float(np.percentile(ap_b, 97.5)), 4)],
                "AP_per_fold": [round(x, 4) for x in per_fold],
                "AP_per_fold_sd": round(float(np.std(per_fold, ddof=1)), 4),
                "max_recall": round(float(np.nanmax(R)), 4),
                "thr_at_max_recall": float(thr[np.nanargmax(R)]),
                "n_gt": int(ng[0]),
                "heldout_area_km2": round(float(km2.sum()), 3),
                "recall_at_fp_per_km2": {
                    str(d): {"recall": round(rfp[d], 4),
                             "ci95": [round(float(np.percentile(rfp_b[d], 2.5)), 4),
                                      round(float(np.percentile(rfp_b[d], 97.5)), 4)]}
                    for d in FP_DENSITIES},
            }
            for i, t in enumerate(thr):
                curves_rows.append(dict(model=name, tau=tau, thr=t, recall=R[i],
                                        precision=P[i], fp_per_km2=FPd[i],
                                        n_pred=int(npd[i]), tp=int(tg[i]), n_gt=int(ng[i])))
            print(f"    IoU {tau}: AP {ap:.3f} [{np.percentile(ap_b, 2.5):.3f}, "
                  f"{np.percentile(ap_b, 97.5):.3f}]  per-fold sd "
                  f"{np.std(per_fold, ddof=1):.3f}  max R {np.nanmax(R):.3f}")

    return summary, paired_compare(summary, boot_store, names), pd.DataFrame(curves_rows)


# ---------------------------------------------------------------------------
# Phase 2
# ---------------------------------------------------------------------------
def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def ece(p, y, n_bins, equal_count):
    if equal_count:
        o = np.argsort(p)
        bins = np.array_split(o, n_bins)
    else:
        edges = np.linspace(0, 1, n_bins + 1)
        idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
        bins = [np.where(idx == i)[0] for i in range(n_bins)]
    tot, rows = 0.0, []
    for b in bins:
        if not len(b):
            continue
        mp, my = float(p[b].mean()), float(y[b].mean())
        tot += len(b) / len(p) * abs(mp - my)
        rows.append((mp, my, len(b)))
    return tot, rows


def fit_platt(x, y):
    lr = LogisticRegression(C=1e6, max_iter=1000)
    lr.fit(logit(x)[:, None], y)
    return lr, float(lr.coef_[0, 0]), float(lr.intercept_[0])


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def nll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def phase2_objects(name):
    """Blob-level calibration at each fold's proposal cutoff (see proposal_thr).

    The label is "matched an annotated feature at IoU 0.3". Unannotated real
    features count as misses, so calibrated probabilities are lower bounds.
    """
    counts = load_counts(name)
    held = counts[(counts.split == "heldout") & (counts.tau == 0.3)]
    objs = pd.read_csv(OUT / f"cv5_sweep_objects_{name}_thr0p05to0p95_9t.csv.gz")
    objs = objs[objs.tau == 0.3]
    out = {"per_fold": []}
    pooled = {m: [] for m in ("raw", "platt", "isotonic")}
    pooled_y = []
    for k in range(K):
        t_prop, best = proposal_thr(counts, k)
        ov = calibration_blobs(objs, k, t_prop)
        oh = objs[(objs.fold == k) & (objs.split == "heldout") & np.isclose(objs.thr, t_prop)]
        xv, yv = ov.score.to_numpy(), ov.is_tp.to_numpy(int)
        xh, yh = oh.score.to_numpy(), oh.is_tp.to_numpy(int)
        lr, a, b = fit_platt(xv, yv)
        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(xv, yv)
        ph = {"raw": xh, "platt": lr.predict_proba(logit(xh)[:, None])[:, 1],
              "isotonic": iso.predict(xh)}
        for m in pooled:
            pooled[m].append(ph[m])
        pooled_y.append(yh)
        n_gt = int(held[(held.fold == k) & np.isclose(held.thr, t_prop)].n_gt.sum())
        per = dict(fold=k, proposal_thr=t_prop, other_folds_recall_at_proposal=round(best, 4),
                   n_calibration_blobs=len(ov), n_heldout_blobs=len(oh), heldout_tp=int(yh.sum()),
                   heldout_recall_at_proposal=round(yh.sum() / n_gt, 4),
                   platt_slope=round(a, 3), platt_intercept=round(b, 3))
        for m in pooled:
            per[f"heldout_ECE_{m}"] = round(ece(ph[m], yh, N_BINS_OBJ, True)[0], 4)
        out["per_fold"].append(per)
    y = np.concatenate(pooled_y)
    res, rel = {}, {}
    for m in pooled:
        p = np.concatenate(pooled[m])
        e, rows = ece(p, y, N_BINS_OBJ, equal_count=True)
        res[m] = dict(ECE=round(e, 4), brier=round(brier(p, y), 4), nll=round(nll(p, y), 4))
        rel[m] = rows
    out["heldout_pooled"] = res
    out["heldout_n_blobs"] = int(len(y))
    out["heldout_base_rate"] = round(float(y.mean()), 4)
    return out, rel


def phase2_pixels(name):
    """Pixel reliability of the raw probability, and a leave-one-fold-out Platt fit.

    Every fold's held-out pixels are sampled first. Fold k's calibrator is then
    fitted on the other four folds' samples, each scored by its own model.
    """
    cv = MODELS[name]
    man = normalize_ids(pd.read_csv(cv.MANIFEST))
    mdir = {"pit": path_for("models") / "pit" / "unet_cv5",
            "pad": path_for("models") / "pad" / "unet_cv5"}[name]
    assign = normalize_ids(pd.read_csv(mdir / f"{name}_cv5_fold_assignment_9t.csv"))
    fold_of_block = assign.drop_duplicates("block_id").set_index("block_id")["fold"].to_dict()
    man["fold"] = man.block_id.map(fold_of_block)
    blocks = gpd.read_file(cv.BLOCKS, layer="blocks").to_crs(cv.CRS)
    prob_name = {"pit": "pit_prob_floor_cvfold{k}_9t_05.tif",
                 "pad": "pad_prob_cvfold{k}_9t_05.tif"}[name]
    with rasterio.open(cv.LABELS) as r:
        lab = r.read(1)
        tf = r.transform
    rng = np.random.default_rng(SEED)
    samp = {}
    for k in range(K):
        held_blocks = sorted(man.loc[man.fold == k, "block_id"].unique())
        with rasterio.open(mdir / f"fold{k}" / prob_name.format(k=k)) as r:
            prob = r.read(1)
        m = _rasterize([(g, 1) for g in blocks[blocks.block_id.isin(held_blocks)].geometry],
                       out_shape=prob.shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        m &= (lab != 255) & (prob >= 0)
        idx = np.flatnonzero(m)
        if len(idx) > PIX_SAMPLE:
            idx = rng.choice(idx, PIX_SAMPLE, replace=False)
        samp[k] = (prob.ravel()[idx].astype(float), (lab.ravel()[idx] == 1).astype(int))
        del prob
    per_fold, ph_all, yh_all, raw_all = [], [], [], []
    for k in range(K):
        xc = np.concatenate([samp[j][0] for j in range(K) if j != k])
        yc = np.concatenate([samp[j][1] for j in range(K) if j != k])
        sub = rng.choice(len(xc), min(len(xc), PIX_SAMPLE), replace=False)
        lr, a, b = fit_platt(xc[sub], yc[sub])
        xh, yh = samp[k]
        ph = lr.predict_proba(logit(xh)[:, None])[:, 1]
        e_raw, _ = ece(xh, yh, N_BINS_PIX, equal_count=False)
        e_pl, _ = ece(ph, yh, N_BINS_PIX, equal_count=False)
        per_fold.append(dict(fold=k, platt_slope=round(a, 3), platt_intercept=round(b, 3),
                             temperature=round(1 / a, 3), heldout_ECE_raw=round(e_raw, 5),
                             heldout_ECE_platt=round(e_pl, 5),
                             heldout_positive_rate=round(float(yh.mean()), 5)))
        raw_all.append(xh); ph_all.append(ph); yh_all.append(yh)
        print(f"    {name} pixel fold {k}: slope {a:.3f} (T {1/a:.2f}) "
              f"intercept {b:.3f}  ECE raw {e_raw:.4f} -> platt {e_pl:.4f}")
    x, p, y = map(np.concatenate, (raw_all, ph_all, yh_all))
    rel = {}
    res = {}
    for m, v in (("raw", x), ("platt", p)):
        e, rows = ece(v, y, N_BINS_PIX, equal_count=False)
        # Positives are rare, so the all-pixel ECE is dominated by confident
        # background. The ECE over pixels the model flags at all is the part a
        # cutoff actually operates on.
        f = v >= 0.05
        e_f, _ = ece(v[f], y[f], N_BINS_PIX, equal_count=False)
        res[m] = dict(ECE_all=round(e, 5), ECE_p_ge_0p05=round(e_f, 4),
                      brier=round(brier(v, y), 5))
        rel[m] = rows
    return {"per_fold": per_fold, "heldout_pooled": res}, rel


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------
def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK, labelsize=8)
    ax.grid(True, color="#e6e6e3", lw=0.6)
    ax.set_axisbelow(True)


def fig_curves(curves, summary, kind, source):
    """kind: 'pr' or 'froc'. source: 'ranked' (headline) or 'sweep' (secondary)."""
    FIG.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, tau in zip(axes, (0.3, 0.5)):
        for name in curves.model.unique():
            c = curves[(curves.model == name) & (curves.tau == tau)]
            s = summary[name][f"iou{tau}"]
            if kind == "pr":
                c = c.dropna(subset=["precision"])
                if source == "sweep":
                    c = c.sort_values("thr")
                lab = f"{LABEL[name]}  AP {s['AP']:.3f} [{s['AP_ci95'][0]:.3f}-{s['AP_ci95'][1]:.3f}]"
                ax.plot(c.recall, c.precision, color=COL[name], lw=2, label=lab,
                        marker=MRK[name], ms=4,
                        markevery=(max(1, len(c) // 12) if source == "ranked" else 1))
            else:
                c = c[c.fp_per_km2 > 0]
                ax.plot(c.fp_per_km2, c.recall, color=COL[name], lw=2, label=LABEL[name],
                        marker=MRK[name], ms=4,
                        markevery=(max(1, len(c) // 12) if source == "ranked" else 1))
        _style(ax)
        if kind == "pr":
            ax.set_xlabel("recall (held-out)", color=INK, fontsize=9)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            if tau == 0.3:
                ax.set_ylabel("precision (held-out)", color=INK, fontsize=9)
        else:
            ax.set_xscale("log")
            ax.set_xlabel("false positives per km2 of held-out ground (log)", color=INK, fontsize=9)
            ax.set_ylim(0, 1)
            if tau == 0.3:
                ax.set_ylabel("recall (held-out)", color=INK, fontsize=9)
        ax.set_title(f"match rule: IoU >= {tau}", color=INK, fontsize=10, loc="left")
        ax.legend(fontsize=7, frameon=False, labelcolor=INK,
                  loc="lower left" if kind == "pr" else "upper left")
    if source == "ranked":
        head = ("Precision against recall, candidates ranked by score"
                if kind == "pr" else "Recall against false alarms per km2, candidates ranked by score")
        foot = ("Candidates are the blobs at each fold's proposal cutoff (highest recall on the other folds). "
                "Precision counts unannotated real features as false, so it is a lower bound. "
                "Brackets: 95% block bootstrap.")
    else:
        head = ("SECONDARY: precision against recall as the pixel cutoff sweeps 0.05-0.95"
                if kind == "pr" else "SECONDARY: recall against false alarms per km2, pixel-cutoff sweep")
        foot = ("Raising the cutoff shrinks blobs until they miss the annotated outline, so precision "
                "falls at high cutoffs. This curve mixes outlining with ranking.")
    fig.suptitle(head + " - 5-fold held-out, 9t", color=INK, fontsize=11, x=0.01, ha="left")
    fig.text(0.01, 0.005, foot, color=MUTED, fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    stem = {"pr": "pr_curve", "froc": "froc_recall_vs_fp_per_km2"}[kind]
    tag = {"ranked": "ranked_candidates_at_proposal_cutoff",
           "sweep": "pixel_cutoff_sweep_0p05to0p95"}[source]
    p = FIG / f"{stem}_{tag}_heldout_cv5_iou0p30_iou0p50_pit_pitsmrf_pad_9t.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p


def fig_reliability(rels, level, names):
    fig, axes = plt.subplots(1, len(names), figsize=(4.6 * len(names), 4.4))
    axes = np.atleast_1d(axes)
    for ax, name in zip(axes, names):
        ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls="--", label="perfect calibration")
        for m, rows in rels[name].items():
            mp, my, _ = zip(*rows)
            ax.plot(mp, my, color=CAL_COL[m], lw=2, marker=CAL_MRK[m], ms=5,
                    label={"raw": "raw score", "platt": "Platt, fit on other folds",
                           "isotonic": "isotonic, fit on other folds"}[m])
        _style(ax)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.set_xlabel("mean predicted probability in bin", color=INK, fontsize=9)
        ax.set_ylabel("observed hit rate in bin", color=INK, fontsize=9)
        ax.set_title(name, color=INK, fontsize=10, loc="left")
        ax.legend(fontsize=7, frameon=False, loc="upper left", labelcolor=INK)
    what = ("candidate blobs at the proposal cutoff, 10 equal-count bins"
            if level == "object" else "pixels, 15 equal-width bins")
    fig.suptitle(f"Does a score mean a probability? Held-out {what}", color=INK,
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = FIG / (f"reliability_{level}_level_heldout_cv5_raw_platt"
               f"{'_isotonic' if level == 'object' else ''}_{'_'.join(names)}_9t.png")
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    names = ["pit", "pit_smrf", "pad"]
    print("== Phase 1a (headline): ranked candidate list ==")
    rk_sum, rk_paired, rk_curves, props = phase1_ranked(names)
    print("== Phase 1b (secondary): pixel-cutoff sweep ==")
    sw_sum, sw_paired, sw_curves = phase1_sweep(names)
    rk_csv = OUT / "pr_froc_curve_points_ranked_candidates_heldout_cv5_pit_pitsmrf_pad_9t.csv"
    sw_csv = OUT / "pr_froc_curve_points_pixel_cutoff_sweep_heldout_cv5_pit_pitsmrf_pad_9t.csv"
    rk_curves.to_csv(rk_csv, index=False)
    sw_curves.to_csv(sw_csv, index=False)
    figs = [fig_curves(rk_curves, rk_sum, k, "ranked") for k in ("pr", "froc")]
    figs += [fig_curves(sw_curves, sw_sum, k, "sweep") for k in ("pr", "froc")]

    print("== Phase 2: calibration ==")
    obj, obj_rel, pix, pix_rel = {}, {}, {}, {}
    for name in names:
        obj[name], obj_rel[name] = phase2_objects(name)
        print(f"  {name} object: {obj[name]['heldout_pooled']}  base rate "
              f"{obj[name]['heldout_base_rate']}")
    for name in ("pit", "pad"):
        pix[name], pix_rel[name] = phase2_pixels(name)
        print(f"  {name} pixel pooled: {pix[name]['heldout_pooled']}")
    figs.append(fig_reliability(obj_rel, "object", names))
    figs.append(fig_reliability(pix_rel, "pixel", ["pit", "pad"]))

    js = OUT / "pr_ap_froc_calibration_summary_cv5_pit_pitsmrf_pad_9t.json"
    js.write_text(json.dumps({
        "phase1_ranked_headline": rk_sum, "phase1_ranked_paired_smrf_vs_vendor": rk_paired,
        "phase1_sweep_secondary": sw_sum, "phase1_sweep_paired_smrf_vs_vendor": sw_paired,
        "phase2_object": obj, "phase2_pixel": pix,
        "bootstrap_B": B, "seed": SEED}, indent=2, default=float))
    print(f"\nwrote {js}")
    print(f"wrote {rk_csv}")
    print(f"wrote {sw_csv}")
    for f in figs:
        print(f"wrote {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
