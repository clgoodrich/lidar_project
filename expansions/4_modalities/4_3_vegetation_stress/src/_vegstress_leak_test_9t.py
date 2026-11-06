"""4.3 stage V4, Question B. Does a stress index separate labelled leak from non-leak pads beyond covariates? (9t)

Purpose
    Refuses to run unless the V0 gate JSON says success. Site-level table of labelled pads. Covariates
    (pad age, mean CHM, open share) and stress features (per-season site-minus-ring index differences
    from V2, plus the mean anomaly when V2 had several years). Nested spatial cross-validation grouped by
    lease. Outer GroupKFold by lease. Inner GroupKFold picks the logistic C. AUC of covariates only
    versus covariates plus stress, paired cluster bootstrap over leases (ek.bootstrap_diff, paired).
    Decision with ek.decide (superiority) against delta_gain. Run for all labels, strong labels only and
    weak labels only, reported separately. All labels is primary B (one of two primaries with V3). Strong and
    weak are secondary. Stage verdicts are unadjusted. The gate is Holm in _vegstress_primary_holm_9t.py. A success is a screening association with the stated label
    type. It is not leak detection and not well identity.
Inputs
    V0 gate     <run>_vegstress_labels_*/vegstress_label_counts_9t.json
    V0 labels   <run>_vegstress_labels_*/vegstress_label_audit_9t.csv
    V2 table    <run>_vegstress_sites_*/vegstress_by_site_9t.csv
    pads, chm   held (config_4_3.json)
Outputs (expansions/4_modalities/4_3_vegetation_stress/results/<YYYYMMDD>_vegstress_leak_<hash7>/)
    vegstress_leak_test_9t.json, vegstress_leak_scores_9t.csv, provenance
Run
    python expansions/4_modalities/4_3_vegetation_stress/src/_vegstress_leak_test_9t.py [--labels-dir RUN] [--by-site P]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _vegstress_shared_io as io
from _vegstress_shared_io import ek

SHORT = "vegstress_leak"


def nested_oof(X, y, groups, lt: dict, seed: int) -> np.ndarray:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GridSearchCV, GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    p = np.full(len(y), np.nan)
    outer = GroupKFold(n_splits=min(lt["outer_folds"], len(np.unique(groups))))
    for tr, te in outer.split(X, y, groups):
        if len(np.unique(y[tr])) < 2:
            continue
        pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(max_iter=2000, random_state=seed))
        k_in = min(lt["inner_folds"], len(np.unique(groups[tr])))
        if k_in >= 2:
            gs = GridSearchCV(pipe, {"logisticregression__C": lt["C_grid"]}, cv=GroupKFold(n_splits=k_in),
                              scoring="roc_auc")
            gs.fit(X[tr], y[tr], groups=groups[tr])
            m = gs.best_estimator_
        else:
            m = pipe.fit(X[tr], y[tr])
        p[te] = m.predict_proba(X[te])[:, 1]
    return p


def site_table(labels: pd.DataFrame, by_site: pd.DataFrame, pads, chm: Path, id_col: str) -> tuple[pd.DataFrame, list[str]]:
    b = by_site[by_site["site_class"] == "pad"].copy()
    b["pad_id"] = b["site_id"].str.replace("pad_", "", n=1)
    diff_cols = [c for c in b.columns if c.endswith("_diff")]
    w = b.pivot_table(index="pad_id", columns="season", values=diff_cols, aggfunc="mean")
    w.columns = [f"{a}_{s}" for a, s in w.columns]
    if b["anomaly_ref"].astype(str).str.startswith("same season").any():
        an = b.groupby("pad_id")[[c for c in b.columns if c.endswith("_anomaly")]].mean()
        w = w.join(an)
    w = w.loc[:, w.notna().any()]
    p = pads.rename(columns={id_col: "pad_id"})
    p["pad_id"] = p["pad_id"].astype(str)
    p = p[p["pad_id"].isin(labels["pad_id"].astype(str))]
    cov = pd.DataFrame({"pad_id": p["pad_id"],
                        "chm_mean_m": io.zonal(chm, p, "pad_id").reindex(p["pad_id"]).to_numpy(),
                        "open_frac": io.zonal(chm, p, "pad_id", fn=lambda v: np.nanmean(v < 2.0)).reindex(p["pad_id"]).to_numpy()})
    L = labels.assign(pad_id=labels["pad_id"].astype(str))
    L = L[L["label"].isin(["leak", "nonleak"])]
    t = L.merge(cov, on="pad_id", how="left").merge(w, left_on="pad_id", right_index=True, how="left")
    t["y"] = (t["label"] == "leak").astype(int)
    return t, list(w.columns)


def run(cfg: dict, out_root: Path | None = None, labels_dir: Path | None = None, by_site_path: Path | None = None) -> dict:
    lt = cfg["leak_test"]
    ld = Path(labels_dir) if labels_dir else io.latest_run("vegstress_labels")
    gate = json.loads(io.need(ld / "vegstress_label_counts_9t.json", "V0 gate summary").read_text())
    if gate.get("verdict") != "success":
        raise RuntimeError(f"V0 label gate is {gate.get('verdict')!r}, not success. Question B does not run "
                           "(framework 4.3 section 10, pre-specified)")
    labels = pd.read_csv(io.need(ld / "vegstress_label_audit_9t.csv", "V0 label table"))
    bp = Path(by_site_path) if by_site_path else io.latest_run("vegstress_sites") / "vegstress_by_site_9t.csv"
    by_site = pd.read_csv(io.need(bp, "V2 per-site table"))
    pin = cfg["inputs"]["pads"]
    pads = io.read_polys(io.resolve(pin), pin.get("layer"), pin["id_col"], "pad polygons")
    chm = io.need(io.resolve(cfg["inputs"]["chm"]), "CHM raster")
    t, stress = site_table(labels, by_site, pads, chm, pin["id_col"])
    covs = [c for c in lt["covariates"] if c in t.columns]
    run_dir = ek.new_run(io.EXP, SHORT, {"leak_test": lt, "labels": str(ld), "by_site": str(bp)}, base=out_root,
                         why="V4 Question B leak association.")
    from sklearn.metrics import roc_auc_score
    res, score_parts = {}, []
    for name, keep in (("all", {"strong", "weak"}), ("strong", {"strong"}), ("weak", {"weak"})):
        d = t[t["strength"].isin(keep)].reset_index(drop=True)
        if d["y"].nunique() < 2 or d["lease_id"].nunique() < 4:
            res[name] = {"status": "skipped", "n": int(len(d)), "reason": "one class or fewer than 4 leases"}
            continue
        g = d["lease_id"].astype(str).to_numpy()
        seed = ek.child_seed(cfg["master_seed"], arm=40 + len(res))
        pa = nested_oof(d[covs].to_numpy(float), d["y"].to_numpy(), g, lt, seed)
        pb = nested_oof(d[covs + stress].to_numpy(float), d["y"].to_numpy(), g, lt, seed)
        d = d.assign(score_cov=pa, score_cov_stress=pb)
        by_lease = {k: v for k, v in d.groupby("lease_id")}
        def auc(col):
            def f(bl):
                x = pd.concat([by_lease[b] for b in bl])
                x = x[np.isfinite(x[col])]
                return roc_auc_score(x["y"], x[col]) if x["y"].nunique() == 2 else np.nan
            return f
        leases = list(by_lease)
        mu = float(lt.get("max_undefined", 0.0))
        pt, lo, hi, dr = ek.bootstrap_diff(auc("score_cov_stress"), leases, auc("score_cov"), leases,
                                           B=lt["bootstrap_B"], seed=seed, paired=True, max_undefined=mu,
                                           return_draws=True)
        res[name] = {"status": "ok", "n": int(len(d)), "n_leak": int(d.y.sum()), "n_leases": len(leases),
                     "auc_cov": float(auc("score_cov")(leases)), "auc_cov_stress": float(auc("score_cov_stress")(leases)),
                     "auc_gain": pt, "lo": lo, "hi": hi, "undefined_share": ek.undefined_share(dr),
                     "max_undefined": mu, "verdict_unadjusted": ek.decide(lo, hi, lt["delta_gain"], "superiority"),
                     "primary": name == "all", **io._t.one_sided_shares(dr, lt["delta_gain"], mu)}
        score_parts.append(d[["pad_id", "label", "strength", "lease_id", "score_cov", "score_cov_stress"]].assign(subset=name))
    summary = {"stage": "V4", "question": "B leak association", "covariates": covs, "stress_features": stress,
               "delta_gain": lt["delta_gain"], "results": res,
               "gated_by": "Holm over V3 and V4 all labels (_vegstress_primary_holm_9t.py)",
               "note": "A positive result is an association with the stated label type. Not leak detection, not well identity"}
    out_j, out_c = run_dir / "vegstress_leak_test_9t.json", run_dir / "vegstress_leak_scores_9t.csv"
    out_j.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (pd.concat(score_parts) if score_parts else pd.DataFrame()).to_csv(out_c, index=False)
    return io.finish(run_dir, summary, inputs=[ld / "vegstress_label_audit_9t.csv", bp, chm], outputs=[out_j, out_c],
                     params=lt, seeds={"master": cfg["master_seed"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--labels-dir", type=Path, default=None)
    ap.add_argument("--by-site", type=Path, default=None)
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.out_root, a.labels_dir, a.by_site), indent=1, default=str))


if __name__ == "__main__":
    main()
