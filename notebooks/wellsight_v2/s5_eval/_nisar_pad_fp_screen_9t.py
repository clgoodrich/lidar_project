"""Can NISAR (or lidar texture) tell the pad detector's true positives from its false positives? (backlog: pad false-positive
screen, precision at fixed recall, confusers) on 9t.

Candidates are the connected regions of the pad U-Net's out-of-fold probability raster above TAU, one raster per CV fold,
each fold read only inside its held-out blocks (so every candidate comes from a model that never saw that block).
A candidate is a true positive (TP) if its IoU with an annotated pad is at least 0.3, otherwise a false positive (FP).
"Strict FP" means no overlap at all with an annotated pad (annotation is incomplete, so some FPs are unlabelled pads).

Per candidate: the detector score (mean probability), and the median of every band (NISAR products, lidar controls and
lidar texture, as the main scorer) over the candidate's core (polygon shrunk 5 m, else the polygon), on the 5 m radar grid.

Tests (rows grouped by 500 m block):
  * AUC of the detector score, and of each band, TP against FP (block-bootstrap p, BH q).
  * Repeated shuffled grouped CV (REPEATS) of gradient boosting: score alone, score + rich lidar texture, score + NISAR,
    score + NISAR + rich lidar texture. Gain over "score alone" with a block-bootstrap interval on repeat-averaged
    out-of-fold probabilities.
  * Precision at fixed recall: candidates ranked by the detector score, and by the out-of-fold combined probability.
    Recall here is the share of TP candidates kept (a screen cannot recover pads the detector missed).

  UNET_DIR=unet_cv5_iso TAU=0.3 python _nisar_pad_fp_screen_9t.py
"""
import os
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy.stats import mannwhitneyu
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C
import _nisar_feat_repeat_9t as R
import _nisar_feat_score_9t as SC

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "s3_train"))
import _pad_unet_cv5 as U  # noqa: E402  (polygonize, MIN_AREA_M2, paths)

UNET_DIR = os.environ.get("UNET_DIR", "unet_cv5_iso")
TAU = float(os.environ.get("TAU", 0.3))
REPEATS, SEED = int(os.environ.get("REPEATS", 10)), 20261027
TAGU = f"{UNET_DIR.replace('unet_cv5', 'cv5').strip('_')}_tau{TAU:.2f}".replace(".", "p")


def candidates():
    pads = U.read_layer(U.ANN_GPKG, "pad").to_crs(U.CRS)
    pads = pads[["pad_id", "geometry"]].dissolve(by="pad_id").reset_index()
    blocks = gpd.read_file(U.BLOCKS, layer="blocks").to_crs(U.CRS)
    cvdir = U.path_for("models") / "pad" / UNET_DIR
    asg = pd.read_csv(U.path_for("models") / "pad" / "unet_cv5" / "pad_cv5_fold_assignment_9t.csv").dropna().drop_duplicates("block_id")
    fold_of = dict(zip(asg.block_id.astype(int), asg.fold.astype(int)))
    blocks["fold"] = blocks.block_id.map(lambda b: fold_of.get(int(b), -1))
    out = []
    for k in range(5):
        with rasterio.open(cvdir / f"fold{k}" / f"pad_prob_cvfold{k}_9t_05.tif") as r:
            prob, tf, crs = r.read(1).astype(np.float32), r.transform, r.crs
        foot = blocks.loc[blocks.fold == k].geometry.union_all()
        keep = rasterize([(foot.buffer(U.SCORE_BUF_M), 1)], out_shape=prob.shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        poly = U.polygonize(np.where(keep, prob, 0.0).astype(np.float32), tf, crs, TAU)
        del prob
        poly = poly[poly.geometry.centroid.within(foot)].reset_index(drop=True)
        poly["fold"] = k
        out.append(poly)
        print(f"fold {k}: {len(poly)} candidates", flush=True)
    cand = pd.concat(out, ignore_index=True)
    cand = gpd.GeoDataFrame(cand, geometry="geometry", crs=U.CRS)
    sidx = pads.sindex
    iou, inter_any = [], []
    for g in cand.geometry:
        best, anyov = 0.0, False
        for j in sidx.query(g, predicate="intersects"):
            p = pads.geometry.iloc[j]
            i = g.intersection(p).area
            if i > 0:
                anyov = True
                best = max(best, i / (g.area + p.area - i))
        iou.append(best)
        inter_any.append(anyov)
    cand["iou"], cand["overlaps_pad"] = iou, inter_any
    cand["tp"] = (cand.iou >= 0.3).astype(int)
    return cand


def features(cand):
    idx, stack, tf, shape = C.load()
    del stack
    grids = C.lidar_grids(tf, shape)
    feats = {k: v for k, v in C.read_all().items() if not k.startswith("heightresid:")}
    p1 = C.FEAT_DIR / f"nisar_feature_stack_{C.A.TAG}_5m.tif"
    if p1.exists():
        with rasterio.open(p1) as r:
            for i, d in enumerate(r.descriptions, 1):
                if not d.startswith("lidar_"):
                    feats[f"amp_stats:{d}"] = r.read(i)
    feats["control:cover"], feats["control:slope"], feats["control:rough"] = grids["cover"], grids["slope"], grids["rough"]
    feats.update(SC.lidar_texture(grids))
    names = list(feats)
    g32 = cand.to_crs(C.CRS)
    X = np.full((len(cand), len(names)), np.nan)
    pxs = []
    for i, g in enumerate(g32.geometry):
        core = g.buffer(-5)
        px = C.st.pixel_index(core, tf, shape) if not core.is_empty else np.array([], int)
        if len(px) < 4:
            px = C.st.pixel_index(g, tf, shape)
        pxs.append(px)
    for j, n in enumerate(names):
        f = feats[n].ravel()
        for i, px in enumerate(pxs):
            v = f[px] if len(px) else np.array([])
            v = v[np.isfinite(v)]
            if len(v) >= 4:
                X[i, j] = np.median(v)
    rc = rasterio.transform.rowcol(tf, [g.centroid.x for g in g32.geometry], [g.centroid.y for g in g32.geometry])
    r_, c_ = np.clip(rc[0], 0, shape[0] - 1), np.clip(rc[1], 0, shape[1] - 1)
    grp = (r_ * 5 // 500) * 100000 + (c_ * 5 // 500)
    xy = np.array([[g.centroid.x, g.centroid.y] for g in g32.geometry])
    return names, X, grp, xy, np.array([len(p) for p in pxs])


def pca_logistic_oof(score, X, y, grp, xy, seed, n_pc=10):
    """Low-capacity combiner: logistic regression on logit(score) and the first n_pc principal components of the standardised
    bands. Bands more than 20% missing in a training class are dropped and the rest median-imputed inside each training fold;
    the PCA is fitted on the training fold only."""
    from scipy.spatial import cKDTree
    from sklearn.decomposition import PCA
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.preprocessing import StandardScaler
    lg = np.log(np.clip(score, 1e-3, 1 - 1e-3) / (1 - np.clip(score, 1e-3, 1 - 1e-3)))
    p = np.full(len(y), np.nan)
    for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(X, y, grp):
        d, _ = cKDTree(xy[te]).query(xy[tr])
        tr = tr[d > C.CV_BUFFER_M]
        nr = np.stack([np.isnan(X[tr][y[tr] == 1]).mean(0), np.isnan(X[tr][y[tr] == 0]).mean(0)]).max(0)
        good = nr <= 0.20
        med = np.nanmedian(X[tr][:, good], 0)
        fill = lambda A: np.where(np.isnan(A), med, A)  # noqa: E731
        sc = StandardScaler().fit(fill(X[tr][:, good]))
        pca = PCA(n_pc, random_state=0).fit(sc.transform(fill(X[tr][:, good])))
        f = lambda i: np.hstack([lg[i, None], pca.transform(sc.transform(fill(X[i][:, good])))])  # noqa: E731
        s2 = StandardScaler().fit(f(tr))
        m = LogisticRegression(C=0.3, max_iter=2000).fit(s2.transform(f(tr)), y[tr])
        p[te] = m.predict_proba(s2.transform(f(te)))[:, 1]
    return p


def precision_at_recall(y, score, recalls=(0.5, 0.7, 0.9)):
    o = np.argsort(-score)
    tp = np.cumsum(y[o])
    prec = tp / np.arange(1, len(y) + 1)
    rec = tp / y.sum()
    return {r: float(prec[np.searchsorted(rec, r)]) for r in recalls}, float(y.mean())


def main():
    cand = candidates()
    names, X, grp, xy, npx = features(cand)
    y, score = cand.tp.values, cand.score.values
    ok = np.isfinite(X[:, names.index("control:cover")]) & (npx >= 4)
    cand = cand[ok].reset_index(drop=True)
    X, grp, xy, y, score = X[ok], grp[ok], xy[ok], y[ok], score[ok]
    print(f"{len(y)} candidates with features: {int(y.sum())} TP, {int((1 - y).sum())} FP "
          f"({int(((1 - y) & ~cand.overlaps_pad.values.astype(bool)).sum())} strict FP); blocks {len(np.unique(grp))}", flush=True)
    prod = np.array([n.split(":")[0] for n in names])
    ctl, lt, ctx, sar = C.feature_groups(prod)
    S1 = score[:, None]
    sets = {"detector score alone": S1, "score + rich lidar texture": np.hstack([S1, X[:, ctl | lt]]),
            "score + NISAR": np.hstack([S1, X[:, sar]]), "score + NISAR + rich lidar texture": np.hstack([S1, X[:, sar | ctl | lt]]),
            "rich lidar texture alone": X[:, ctl | lt], "NISAR alone": X[:, sar]}
    rows = [dict(feature_set="detector score, raw AUC", auc_mean=roc_auc_score(y, score), auc_sd=0.0)]
    runs = [R.one_repeat({k: v for k, v in sets.items() if k != "detector score alone"}, y, grp, xy, r) for r in range(REPEATS)]
    for k in runs[0]:
        a = np.array([roc_auc_score(y, rr[k]) for rr in runs])
        rows.append(dict(feature_set=k, auc_mean=a.mean(), auc_sd=a.std(ddof=1), auc_min=a.min(), auc_max=a.max()))
    rng = np.random.default_rng(SEED)
    for nm, M in (("score + NISAR, 10 PCs (logistic)", X[:, sar]), ("score + rich lidar texture, 10 PCs (logistic)", X[:, ctl | lt])):
        pl = [pca_logistic_oof(score, M, y, grp, xy, SEED + r) for r in range(REPEATS)]
        for rr, q in zip(runs, pl):
            rr[nm] = q
        sets[nm] = None
        a = np.array([roc_auc_score(y, q) for q in pl])
        rows.append(dict(feature_set=nm, auc_mean=a.mean(), auc_sd=a.std(ddof=1), auc_min=a.min(), auc_max=a.max()))
    pm = {k: np.mean([rr[k] for rr in runs], 0) for k in runs[0]}
    LOW = ("score + NISAR, 10 PCs (logistic)", "score + rich lidar texture, 10 PCs (logistic)")
    for k in ("score + rich lidar texture", "score + NISAR", "score + NISAR + rich lidar texture") + LOW:
        d = np.array([roc_auc_score(y, rr[k]) for rr in runs]) - roc_auc_score(y, score)
        # block bootstrap of AUC(combined) - AUC(score) on repeat-averaged out-of-fold probabilities
        ug = np.unique(grp)
        where = {g: np.flatnonzero(grp == g) for g in ug}
        bd = []
        for _ in range(500):
            ix = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
            if len(set(y[ix])) == 2:
                bd.append(roc_auc_score(y[ix], pm[k][ix]) - roc_auc_score(y[ix], score[ix]))
        lo, hi = np.percentile(bd, [2.5, 97.5])
        rows.append(dict(feature_set=f"gain over raw score: {k}", auc_mean=d.mean(), auc_sd=d.std(ddof=1), auc_min=d.min(), auc_max=d.max(), boot_lo=lo, boot_hi=hi))
    res = pd.DataFrame(rows).round(4)
    print(res.to_string(index=False))
    res.to_csv(C.OUT / f"nisar_pad_fp_screen_auc_{C.A.TAG}_{TAGU}.csv", index=False)

    # precision at fixed recall, TP candidates kept
    pr = []
    for label, s in [("detector score", score)] + [(k, pm[k]) for k in ("score + rich lidar texture", "score + NISAR", "score + NISAR + rich lidar texture") + LOW]:
        p, base = precision_at_recall(y, s)
        pr.append(dict(ranking=label, base_precision=round(base, 3), **{f"precision_at_recall_{int(r * 100)}": round(v, 3) for r, v in p.items()}))
    # block bootstrap of the precision difference (combined ranking minus detector score) at each recall
    ug = np.unique(grp)
    where = {g: np.flatnonzero(grp == g) for g in ug}
    for row in pr:
        if row["ranking"] == "detector score":
            continue
        d = {r: [] for r in (0.5, 0.7, 0.9)}
        for _ in range(500):
            ix = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
            if y[ix].sum() == 0:
                continue
            a_, _ = precision_at_recall(y[ix], pm[row["ranking"]][ix])
            b_, _ = precision_at_recall(y[ix], score[ix])
            for r in d:
                d[r].append(a_[r] - b_[r])
        for r in d:
            lo, hi = np.percentile(d[r], [2.5, 97.5])
            row[f"diff_at_recall_{int(r * 100)}_95ci"] = f"{row[f'precision_at_recall_{int(r * 100)}'] - pr[0][f'precision_at_recall_{int(r * 100)}']:+.3f} ({lo:+.3f} to {hi:+.3f})"
    pr = pd.DataFrame(pr)
    print(pr.to_string(index=False))
    pr.to_csv(C.OUT / f"nisar_pad_fp_screen_precision_{C.A.TAG}_{TAGU}.csv", index=False)

    # single bands, TP against FP, block-clustered bootstrap
    auc = R.band_aucs(X, y)
    ug = np.unique(grp)
    where = {g: np.flatnonzero(grp == g) for g in ug}
    bs = np.full((300, X.shape[1]), np.nan)
    for b in range(300):
        ix = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
        if len(set(y[ix])) == 2:
            bs[b] = R.band_aucs(X[ix], y[ix])
    with np.errstate(all="ignore"):
        p = np.clip(2 * np.minimum(np.nanmean(bs <= 0.5, 0), np.nanmean(bs >= 0.5, 0)), 1 / 300, 1)
    fin = np.isfinite(auc)
    df = pd.DataFrame(dict(band=np.array(names)[fin], auc=auc[fin], p_cluster=p[fin]))
    df["q_cluster"] = R.bh(df.p_cluster.values)
    df["dev"] = (df.auc - 0.5).abs()
    df = df.sort_values("dev", ascending=False).drop(columns="dev")
    sarb = ~df.band.str.split(":").str[0].isin(["control", "lidartex", "context"])
    print(f"bands q<0.05 (clustered): {int((df.q_cluster < 0.05).sum())} of {len(df)}; SAR only {int((df.q_cluster[sarb] < 0.05).sum())} of {int(sarb.sum())}")
    print(df.head(15).round(3).to_string(index=False))
    df.round(4).to_csv(C.OUT / f"nisar_pad_fp_screen_bands_{C.A.TAG}_{TAGU}.csv", index=False)
    cand.drop(columns="geometry").assign(block=grp).to_csv(C.OUT / f"nisar_pad_fp_screen_candidates_{C.A.TAG}_{TAGU}.csv", index=False)


if __name__ == "__main__":
    main()
