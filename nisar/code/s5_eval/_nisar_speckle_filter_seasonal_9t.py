"""Seasonal pad/pit test rerun with a speckle filter on every NISAR date.

WHY
---
The seasonal test (`_nisar_gslc_stack_pad_pit_seasonal_9t.py`) used single-look pixels.
Speckle was reduced only by averaging dates. Leaf-off fall has one date per track on 9t,
so that season had no averaging at all. This wrapper filters each date's intensity
before the season means are formed. Everything else is unchanged: same stack (--slc),
same 40 decoys per feature, same seed, so the same decoys and rings.

FILTERS (linear intensity |s|^2, L = 1 look, window --win, default 5 x 5 = 25 m)
  median  scipy median filter.
  frost   Frost et al. 1982. Weights exp(-K * Ci^2 * r), Ci^2 = local var / mean^2, K = 1.
  gamma   Gamma-MAP, Lopes et al. 1990. Cu = 1/sqrt(L), Cmax = sqrt(2) Cu.
  sigma   Improved Lee sigma, Lee et al. 2009. A priori Lee MMSE on 3 x 3, sigma range
          with 90% probability and unbiased truncated mean for L = 1, MMSE on the pixels
          inside the range, point targets (5 or more of 9 pixels above the 98th
          percentile) kept unfiltered.
  none    no filter (reproduces the swap40 baseline).
NaN (no sample) pixels are filled with the local mean for filtering, then set back to NaN.

OUTPUT
  nisar/results/9t/speckle_filters/<filter>_w<win>/  the seasonal script's usual CSV,
  JSON and figure names, plus speckle_filter_check_<filter>_w<win>_9t.json (ENL before/after).

Run:
  python nisar/code/s5_eval/_nisar_speckle_filter_seasonal_9t.py --filter gamma --win 5
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter, uniform_filter
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
L_LOOKS = 1.0


# ---------------------------------------------------------------- helpers
def _fill(img):
    ok = np.isfinite(img)
    if ok.all():
        return img, ok
    f = np.where(ok, img, 0.0)
    w = uniform_filter(ok.astype(np.float64), 9)
    s = uniform_filter(f, 9)
    fill = np.where(w > 1e-6, s / np.maximum(w, 1e-6), np.nanmedian(img))
    return np.where(ok, img, fill), ok


def _stats(img, w):
    mu = uniform_filter(img, w)
    var = np.maximum(uniform_filter(img * img, w) - mu * mu, 0.0)
    return mu, var


def _shifts(img, w):
    """Yield (dy, dx, shifted image) over a w x w window, reflect-padded."""
    h = w // 2
    p = np.pad(img, h, mode="reflect")
    for dy in range(-h, h + 1):
        for dx in range(-h, h + 1):
            yield dy, dx, p[h + dy:h + dy + img.shape[0], h + dx:h + dx + img.shape[1]]


# ---------------------------------------------------------------- filters
def f_median(img, w):
    return median_filter(img, size=w, mode="reflect")


def f_frost(img, w, k=1.0):
    mu, var = _stats(img, w)
    ci2 = var / np.maximum(mu * mu, 1e-20)
    num = np.zeros_like(img)
    den = np.zeros_like(img)
    for dy, dx, s in _shifts(img, w):
        wt = np.exp(-k * ci2 * np.hypot(dy, dx))
        num += wt * s
        den += wt
    return num / den


def f_gamma(img, w):
    L = L_LOOKS
    mu, var = _stats(img, w)
    ci = np.sqrt(var) / np.maximum(mu, 1e-20)
    cu = 1.0 / np.sqrt(L)
    cmax = np.sqrt(2.0) * cu
    with np.errstate(all="ignore"):
        a = (1 + cu ** 2) / (ci ** 2 - cu ** 2)
        b = a - L - 1
        r = (b * mu + np.sqrt(b * b * mu * mu + 4 * a * L * img * mu)) / (2 * a)
    out = np.where(ci <= cu, mu, np.where(ci >= cmax, img, r))
    return np.where(np.isfinite(out), out, mu)


def _sigma_range(p=0.90):
    """[I1, I2] for single-look exponential intensity (mean 1): probability p, truncated mean 1."""
    def tmean(a, b):
        return ((a + 1) * np.exp(-a) - (b + 1) * np.exp(-b)) / (np.exp(-a) - np.exp(-b))

    def b_of(a):  # P(a < x < b) = p
        return -np.log(np.exp(-a) - p)

    a = brentq(lambda a: tmean(a, b_of(a)) - 1.0, 1e-9, -np.log(p) - 1e-9)
    b = b_of(a)
    m2 = ((a * a + 2 * a + 2) * np.exp(-a) - (b * b + 2 * b + 2) * np.exp(-b)) / (np.exp(-a) - np.exp(-b))
    sd = np.sqrt(m2 - 1.0)   # std of the truncated variate (mean 1)
    return a, b, sd


SIG_I1, SIG_I2, SIG_ETA = _sigma_range()


def f_sigma(img, w):
    sv2 = 1.0 / L_LOOKS
    # 1. a priori estimate: Lee MMSE on 3 x 3
    mu3, var3 = _stats(img, 3)
    with np.errstate(all="ignore"):
        k3 = np.clip((var3 - mu3 * mu3 * sv2) / (var3 * (1 + sv2)), 0, 1)
    xh = np.where(np.isfinite(k3), mu3 + k3 * (img - mu3), mu3)
    # 2. point targets: 5+ of 9 pixels in 3 x 3 above the 98th percentile of speckle
    z98 = -np.log(0.02) * xh
    n_hi = np.zeros(img.shape, np.int32)
    for _, _, s in _shifts(img, 3):
        n_hi += (s > z98)
    point = n_hi >= 5
    # 3. MMSE on window pixels inside [I1, I2] * xh
    lo, hi = SIG_I1 * xh, SIG_I2 * xh
    n = np.zeros_like(img); s1 = np.zeros_like(img); s2 = np.zeros_like(img)
    for _, _, s in _shifts(img, w):
        m = (s >= lo) & (s <= hi)
        n += m; s1 += np.where(m, s, 0); s2 += np.where(m, s * s, 0)
    with np.errstate(all="ignore"):
        mu = s1 / n
        var = np.maximum(s2 / n - mu * mu, 0)
        e2 = SIG_ETA ** 2
        k = np.clip((var - mu * mu * e2) / (var * (1 + e2)), 0, 1)
        out = mu + k * (img - mu)
    out = np.where(np.isfinite(out), out, xh)
    return np.where(point, img, out)


FILTERS = {"median": f_median, "frost": f_frost, "gamma": f_gamma, "sigma": f_sigma, "none": None}


def apply(img, name, w):
    if FILTERS[name] is None:
        return img
    full, ok = _fill(img.astype(np.float64))
    return np.where(ok, FILTERS[name](full, w), np.nan)


def enl(img, w=7):
    """Median local ENL (mean^2 / var) over w x w windows; single-look speckle gives about 1."""
    full, ok = _fill(img.astype(np.float64))
    mu, var = _stats(full, w)
    with np.errstate(all="ignore"):
        e = mu * mu / var
    return float(np.nanmedian(e[ok]))


# ---------------------------------------------------------------- run
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", required=True, choices=sorted(FILTERS))
    ap.add_argument("--win", type=int, default=5)
    a = ap.parse_args()
    # the seasonal script reads its own flags at import time: lidar-placed SLC stack, 40 decoys
    sys.argv = [sys.argv[0], "--slc", "--decoys", "40"]
    spec = importlib.util.spec_from_file_location("seasonal", HERE / "_nisar_gslc_stack_pad_pit_seasonal_9t.py")
    S = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(S)

    out = S.A.RESULTS / "speckle_filters" / f"{a.filter}_w{a.win}"
    out.mkdir(parents=True, exist_ok=True)
    S.OUT, S.FIG = out, out / "figures"
    check = {}
    orig_load = S.load_stack

    def load_filtered():
        idx, inten, tf, shape = orig_load()
        t0 = time.time()
        for i, f in enumerate(list(inten)):
            new = tuple(apply(ch, a.filter, a.win).astype(np.float32) for ch in inten[f])
            if i == 0:
                check["date"] = f
                check["enl_hh_before"] = enl(inten[f][0])
                check["enl_hh_after"] = enl(new[0])
                check["mean_hh_ratio_after_over_before"] = float(np.nanmean(new[0]) / np.nanmean(inten[f][0]))
            inten[f] = new
        check["filter_seconds"] = round(time.time() - t0, 1)
        print(f"filter {a.filter} w{a.win}: {check}")
        return idx, inten, tf, shape

    S.load_stack = load_filtered
    rc = S.main()
    check.update(filter=a.filter, window=a.win, looks=L_LOOKS,
                 sigma_range=[SIG_I1, SIG_I2, SIG_ETA] if a.filter == "sigma" else None)
    (out / f"speckle_filter_check_{a.filter}_w{a.win}_{S.A.TAG}.json").write_text(json.dumps(check, indent=1))
    return rc


if __name__ == "__main__":
    sys.exit(main())
