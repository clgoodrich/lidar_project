"""Core functions for expansion 5.2 era classification. Library, not a script.

Purpose
    Date classification (S0), strata (S1), interval labels and era classes (S2), sample draw (S3),
    pad morphology (S4), fold assignment, the interval-censored log-normal AFT model, interval concordance,
    AUC by block (S6), and distribution overlap (S7). The sentinel guard lives here.

Rules enforced here
    The 1800-01-01 sentinel (and 1900-01-01) is a stratum, never a date and never "early".
    assert_no_sentinel() fails if any model input carries a placeholder date or the sentinel stratum.
    Absence from a map gives no label. A map mark on a map dated D gives [first_oil_year, D].

Method source
    Interval-censored accelerated failure time with a log-normal error, fitted by maximum likelihood.
    Likelihood terms follow Klein and Moeschberger (2003), Survival Analysis, 2nd ed., chapter 3
    (exact, left-, right- and interval-censored contributions). Concordance for interval data counts a pair
    only when the two intervals do not overlap, a conservative Harrell-type extension.

Inputs / outputs
    None. DataFrames and arrays in and out.
Run
    Not runnable. Tested by expansions/5_tasks/5_2_era_classification/src/test_5_2.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm

SENTINEL_STRATUM = "sentinel"
YEAR0 = 1858.0          # T = year - YEAR0, so 1859 gives T = 1 and log T = 0


# ----------------------------------------------------------------------------- S0 dates
def classify_dates(s: pd.Series, sentinels, first_year: int, today) -> pd.Series:
    """Per value: null, sentinel_<date>, pre_<first_year>, future, valid."""
    d = pd.to_datetime(s, errors="coerce")
    out = pd.Series("valid", index=s.index, dtype=object)
    out[d.isna()] = "null"
    for sv in sentinels:
        out[d == pd.Timestamp(sv)] = f"sentinel_{sv}"
    ok = out == "valid"
    out[ok & (d.dt.year < first_year)] = f"pre_{first_year}"
    out[ok & (d > pd.Timestamp(today))] = "future"
    return out


def valid_year(s: pd.Series, cls: pd.Series) -> pd.Series:
    """Year where the class is valid, NaN otherwise."""
    y = pd.to_datetime(s, errors="coerce").dt.year.astype(float)
    return y.where(cls == "valid")


def cross_field_flags(df: pd.DataFrame, spud: str, permit: str, plug: str, cls: dict, gap_days: int) -> pd.DataFrame:
    """Impossible orderings among valid dates only."""
    sd, pd_, pl = (pd.to_datetime(df[c], errors="coerce") for c in (spud, permit, plug))
    vs, vp, vl = (cls[k] == "valid" for k in ("spud", "permit", "plug"))
    f = pd.DataFrame(index=df.index)
    f["plug_before_spud"] = vs & vl & (pl < sd)
    f["spud_before_permit_gap"] = vs & vp & ((pd_ - sd).dt.days > gap_days)
    f["permit_minus_spud_years"] = np.where(vs & vp, pd_.dt.year - sd.dt.year, np.nan)
    return f


# ----------------------------------------------------------------------------- S1 / S2 strata and intervals
def era_class(lo: float, hi: float, classes: dict) -> str:
    """Era class from an interval. An interval that spans a boundary is 'spans' (kept for the censored fit)."""
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return "none"
    for name, (a, b) in ((k, v) for k, v in classes.items() if not k.startswith("_")):
        if lo >= a and hi <= b:
            return name
    return "spans"


def early_label(lo: float, hi: float, classes: dict) -> float:
    """1 if the interval lies in E1 or E2 (hi <= end of E2), 0 if in E3, NaN if it spans the E2 to E3 boundary."""
    e2_end = classes["E2"][1]
    e3_start = classes["E3"][0]
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return np.nan
    if hi <= e2_end:
        return 1.0
    if lo >= e3_start:
        return 0.0
    return np.nan


def tightest(intervals: list[tuple]) -> tuple:
    """intervals = [(lo, hi, source, source_date, identity_basis, pos_error_m)]. Narrowest wins, then lowest hi.
    Returns (best, conflict) where conflict is True when any two intervals do not overlap."""
    iv = sorted(intervals, key=lambda t: (t[1] - t[0], t[1]))
    lo_max = max(t[0] for t in intervals)
    hi_min = min(t[1] for t in intervals)
    return iv[0], bool(lo_max > hi_min)


def assert_no_sentinel(df: pd.DataFrame, sentinels=("1800-01-01", "1900-01-01"), year_cols=("lo", "hi")) -> None:
    """Fail if any model input carries the sentinel stratum or a placeholder year. Called by every model step."""
    if "stratum" in df.columns and (df["stratum"] == SENTINEL_STRATUM).any():
        raise AssertionError(f"sentinel stratum in model input ({int((df['stratum'] == SENTINEL_STRATUM).sum())} rows)")
    for c in year_cols:
        if c in df.columns and (pd.to_numeric(df[c], errors="coerce") < 1859).any():
            raise AssertionError(f"year before 1859 in {c} (the 1800 sentinel cannot be a label)")
    if "source_date" in df.columns and df["source_date"].astype(str).str[:10].isin(list(sentinels)).any():
        raise AssertionError("placeholder date used as a label source_date")
    for c in df.columns:
        if df[c].dtype == object and df[c].astype(str).str[:10].isin(list(sentinels)).any():
            raise AssertionError(f"sentinel date string in column {c}")


# ----------------------------------------------------------------------------- S3 sample
def stratified_sample(df: pd.DataFrame, strata_col: str, n: int, seed: int) -> pd.DataFrame:
    """Proportional allocation with at least one per non-empty stratum. Adds incl_prob and weight."""
    rng = np.random.default_rng(seed)
    if len(df) <= n:
        out = df.copy()
        out["incl_prob"] = 1.0
        out["weight"] = 1.0
        return out
    sizes = df[strata_col].value_counts()
    alloc = np.maximum(1, np.floor(sizes / sizes.sum() * n)).astype(int)
    while alloc.sum() < n:
        rem = (sizes / sizes.sum() * n) - alloc
        alloc[rem.idxmax()] += 1
    while alloc.sum() > n:
        alloc[alloc.idxmax()] -= 1
    parts = []
    for s, k in alloc.items():
        g = df[df[strata_col] == s]
        k = min(k, len(g))
        pick = g.iloc[rng.choice(len(g), k, replace=False)].copy()
        pick["incl_prob"] = k / len(g)
        pick["weight"] = len(g) / k
        parts.append(pick)
    return pd.concat(parts)


# ----------------------------------------------------------------------------- S4 morphology
def pad_morphology(geoms) -> pd.DataFrame:
    """Area, perimeter, compactness (4 pi A / P^2) and elongation (long over short side of the min rotated rectangle)."""
    rows = []
    for g in geoms:
        a, p = g.area, g.length
        r = g.minimum_rotated_rectangle
        xs, ys = r.exterior.coords.xy
        e = [np.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(2)]
        lo_, hi_ = min(e), max(e)
        c = g.centroid
        rows.append(dict(area_m2=a, perimeter_m=p, compactness=4 * np.pi * a / p ** 2 if p else np.nan,
                         elongation=hi_ / lo_ if lo_ > 0 else np.nan, cx=c.x, cy=c.y))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- folds
def block_folds(block_ids, n_folds: int, seed: int) -> dict:
    """Provisional block folds (deterministic, sorted ids, NaN dropped). P1's saved split replaces this."""
    b = sorted({int(x) for x in block_ids if pd.notna(x)})
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(b))
    return {b[i]: int(k % n_folds) for k, i in enumerate(perm)}


# ----------------------------------------------------------------------------- interval-censored AFT
class IntervalLogNormalAFT:
    """log(year - 1858) ~ Normal(X beta, sigma), fitted to interval-censored [lo, hi] by maximum likelihood.

    Exact rows (lo == hi) contribute the density. Others contribute Phi(z_hi) - Phi(z_lo).
    Features are standardised with statistics from the training rows only. A ridge penalty keeps small folds stable.
    """

    def __init__(self, ridge: float = 1.0):
        self.ridge = ridge

    def fit(self, X, lo, hi):
        X = np.asarray(X, float)
        self.mu_, self.sd_ = X.mean(0), X.std(0)
        self.sd_[self.sd_ == 0] = 1.0
        Z = np.c_[np.ones(len(X)), (X - self.mu_) / self.sd_]
        llo = np.log(np.asarray(lo, float) - YEAR0)
        lhi = np.log(np.asarray(hi, float) - YEAR0)
        exact = np.isclose(llo, lhi)
        p = Z.shape[1]

        def nll(theta):
            b, s = theta[:p], np.exp(theta[p])
            m = Z @ b
            ll = np.zeros(len(m))
            if exact.any():
                ll[exact] = norm.logpdf(llo[exact], m[exact], s)
            ie = ~exact
            if ie.any():
                pr = norm.cdf((lhi[ie] - m[ie]) / s) - norm.cdf((llo[ie] - m[ie]) / s)
                ll[ie] = np.log(np.clip(pr, 1e-300, None))
            return -ll.sum() + 0.5 * self.ridge * np.sum(b[1:] ** 2)
        mid = 0.5 * (llo + lhi)
        x0 = np.r_[mid.mean(), np.zeros(p - 1), np.log(max(mid.std(), 0.1))]
        r = minimize(nll, x0, method="L-BFGS-B")
        self.coef_, self.sigma_, self.converged_ = r.x[:p], float(np.exp(r.x[p])), bool(r.success)
        return self

    def predict_log(self, X):
        Z = np.c_[np.ones(len(X)), (np.asarray(X, float) - self.mu_) / self.sd_]
        return Z @ self.coef_

    def predict_year(self, X):
        return YEAR0 + np.exp(self.predict_log(X))


def interval_concordance(pred, lo, hi) -> float:
    """Share of comparable pairs ranked correctly. A pair is comparable when hi_i < lo_j. Ties in pred count half."""
    pred, lo, hi = (np.asarray(a, float) for a in (pred, lo, hi))
    comp = hi[:, None] < lo[None, :]
    if not comp.any():
        return float("nan")
    d = pred[:, None] - pred[None, :]
    conc = (d < 0) & comp
    tie = (d == 0) & comp
    return float((conc.sum() + 0.5 * tie.sum()) / comp.sum())


def auc(y, s) -> float:
    from sklearn.metrics import roc_auc_score
    y, s = np.asarray(y, float), np.asarray(s, float)
    m = np.isfinite(y) & np.isfinite(s)
    if m.sum() < 2 or len(np.unique(y[m])) < 2:
        return float("nan")
    return float(roc_auc_score(y[m], s[m]))


def auc_over_blocks(df: pd.DataFrame, ycol: str, scol: str):
    """stat_fn for ek.block_bootstrap: AUC over the pooled rows of a list of blocks (repeats allowed)."""
    groups = {b: g for b, g in df.groupby("block_id")}

    def f(blocks):
        parts = [groups[b] for b in blocks if b in groups]
        if not parts:
            return float("nan")
        d = pd.concat(parts)
        return auc(d[ycol], d[scol])
    return f


# ----------------------------------------------------------------------------- S7 overlap
def overlap_coefficient(a, b, n_bins: int = 20) -> float:
    """Histogram overlap (sum of bin-wise minima of the two normalised histograms). 1 is identical support."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if not len(a) or not len(b):
        return float("nan")
    lo, hi = min(a.min(), b.min()), max(a.max(), b.max())
    if hi == lo:
        return 1.0
    edges = np.linspace(lo, hi, n_bins + 1)
    ha = np.histogram(a, edges)[0] / len(a)
    hb = np.histogram(b, edges)[0] / len(b)
    return float(np.minimum(ha, hb).sum())
