"""3.3 S2. Confound checks for the slope stratification (size, depth, void across terciles; logistic fit).

Purpose
    A recall difference across slope terciles may reflect pit size or ground voids, not slope.
    This stage (1) compares feature area, depth and void fraction across slope terciles and
    (2) fits a logistic model of the found flag on standardised slope, relief, log area, depth
    and void fraction. Standard errors come from a block bootstrap (resample blocks, refit),
    because pits cluster on pads and blocks. statsmodels is not installed, so sklearn with no
    penalty is used. The slope coefficient is a partial association, not a causal effect.

Inputs
    slope_recall_features_9t.csv from a 3.3 S1 run folder (--run, default the newest
    expansions/3_geography/3_3_low_relief_slope/results/*_slope_recall_*/)

Outputs (written into the same S1 run folder)
    slope_confound_by_tercile_9t.csv   medians and IQR of area, depth, void per slope tercile
    slope_confound_logit_9t.csv        coefficient, bootstrap 95% interval, per covariate
    slope_confound_summary_9t.json     counts, dropped rows, seed, B

Run
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_confound_logit_9t.py
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_confound_logit_9t.py --run <run folder> --B 500
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

COVS = ["slope_25m", "relief_50m", "log_area", "depth_m", "void_frac"]


def latest_run(kind: str = "slope_recall") -> Path:
    runs = sorted(ek.sub("3.3", "results").glob(f"*_{kind}_*"))
    if not runs:
        raise FileNotFoundError("MISSING INPUT: no 3.3 S1 run folder. Run _slope_recall_tercile_9t.py first.")
    return runs[-1]


def fit_logit(X, y):
    from sklearn.linear_model import LogisticRegression
    if len(np.unique(y)) < 2:
        return np.full(X.shape[1] + 1, np.nan)
    m = LogisticRegression(penalty=None, max_iter=2000).fit(X, y)
    return np.r_[m.intercept_, m.coef_.ravel()]


def confound_tables(feat: pd.DataFrame, B: int, seed: int):
    f = feat.copy()
    f["log_area"] = np.log(f.area_m2)
    by = (f.groupby("slope_tercile")[["area_m2", "depth_m", "void_frac"]]
          .describe(percentiles=[0.25, 0.5, 0.75]).loc[:, (slice(None), ["count", "25%", "50%", "75%"])])
    by.columns = [f"{a}_{b}" for a, b in by.columns]
    d = f.dropna(subset=COVS + ["found"])
    dropped = len(f) - len(d)
    mu, sd = d[COVS].mean(), d[COVS].std(ddof=0).replace(0, 1)
    X = ((d[COVS] - mu) / sd).to_numpy()
    y = d.found.astype(int).to_numpy()
    beta = fit_logit(X, y)
    blocks = d.block_id.to_numpy()
    ub = np.unique(blocks)
    rows_of = {b: np.flatnonzero(blocks == b) for b in ub}
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(B):
        pick = rng.choice(ub, len(ub), replace=True)
        idx = np.concatenate([rows_of[b] for b in pick])
        draws.append(fit_logit(X[idx], y[idx]))
    draws = np.array(draws)
    lo, hi = np.nanpercentile(draws, [2.5, 97.5], axis=0)
    coef = pd.DataFrame({"term": ["intercept"] + COVS, "coef_per_sd": beta, "lo": lo, "hi": hi,
                         "odds_ratio_per_sd": np.exp(beta)})
    meta = {"n_used": int(len(d)), "n_dropped_nan": int(dropped), "n_blocks": int(len(ub)), "B": B, "seed": seed,
            "standardisation": {"mean": mu.to_dict(), "sd": sd.to_dict()},
            "note": "partial association with block bootstrap; not slope causation"}
    return by.reset_index(), coef, meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default=None, help="S1 run folder (default newest)")
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args(argv)
    run = Path(a.run) if a.run else latest_run()
    fcsv = run / "slope_recall_features_9t.csv"
    if not fcsv.exists():
        raise FileNotFoundError(f"MISSING INPUT: {fcsv} (3.3 S1 output)")
    feat = pd.read_csv(fcsv)
    by, coef, meta = confound_tables(feat, a.B, ek.child_seed(a.seed, 0, 2))
    o1, o2, o3 = run / "slope_confound_by_tercile_9t.csv", run / "slope_confound_logit_9t.csv", run / "slope_confound_summary_9t.json"
    by.to_csv(o1, index=False)
    coef.to_csv(o2, index=False)
    o3.write_text(json.dumps(meta, indent=2, default=float), encoding="utf-8")
    print(by.to_string(index=False))
    print(coef.to_string(index=False))
    print(f"wrote {o1}\n      {o2}\n      {o3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
