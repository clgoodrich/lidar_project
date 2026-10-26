"""Products 6 and 12: coherence decay, coherence by polarisation and season, phase closure.

For each track and each polarisation (HH, HV), the 3 x 3 coherence of every date pair is computed
(ifg.interferogram). Per pixel the pair coherences are fitted with
    gamma(dt) = ginf + (g0 - ginf) * exp(-dt / tau)
by a grid over tau (TAUS days) and a linear solve for ginf and (g0 - ginf). Stable ground should keep
a high ginf and a long tau. Canopy and bare moving soil decorrelate.

Bands (suffix _{pol}_tNNN):
  ginf, g0, tau, rmse         decay fit
  coh_short, coh_long         mean coherence of pairs with gap <= 12 d and > 36 d
  coh_leafon, coh_leafoff     HH only: pairs inside Jun-Sep, inside Dec-Mar (gap <= 36 d)
  closure                     HH only: mean |closure phase| (rad) of consecutive triplets spanning <= 36 d
                              closure = angle(I12 I23 conj(I13)); non-zero means the phase is not a single
                              surface value (volume, moisture change)

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_coherence_9t.py [--area warren]
"""
import numpy as np
import pandas as pd

import _nisar_feat_common as C

TAUS = np.array([6.0, 12.0, 24.0, 48.0, 96.0, 200.0])
MAX_PAIR_DAYS = 400      # pairs beyond this gap carry no information for the fit


def fit_decay(dts, coh):
    """coh: (pair, y, x) with NaN for invalid. Returns ginf, g0, tau, rmse (each y, x)."""
    v = np.isfinite(coh).astype(np.float32)
    y = np.where(np.isfinite(coh), coh, 0).astype(np.float32)
    n = v.sum(0)
    sy, syy = y.sum(0), (y * y).sum(0)
    best = None
    for tau in TAUS:
        x = np.exp(-dts / tau).astype(np.float32)[:, None, None] * v
        sx, sxx, sxy = x.sum(0), (x * x).sum(0), (x * y).sum(0)
        den = n * sxx - sx * sx
        b = np.where(den > 1e-6, (n * sxy - sx * sy) / np.where(den > 1e-6, den, 1), np.nan)
        a = (sy - b * sx) / np.maximum(n, 1)
        sse = syy - 2 * a * sy - 2 * b * sxy + n * a * a + 2 * a * b * sx + b * b * sxx
        sse = np.where(np.isfinite(b), sse, np.inf)
        if best is None:
            best = [sse, a, b, np.full(sse.shape, tau, np.float32)]
        else:
            upd = sse < best[0]
            for k, new in enumerate((sse, a, b, np.full(sse.shape, tau, np.float32))):
                best[k] = np.where(upd, new, best[k])
    sse, a, b, tau = best
    bad = ~np.isfinite(sse) | (n < 6)
    ginf, g0 = a, a + b
    rmse = np.sqrt(np.maximum(sse, 0) / np.maximum(n, 1))
    return [np.where(bad, np.nan, z) for z in (ginf, g0, tau, rmse)]


def main():
    idx, stack, tf, shape = C.load()
    bands = {}
    for t, g in C.by_track(idx):
        d = pd.to_datetime(g.date)
        mon = d.dt.month.values
        days = (d - d.min()).dt.days.values
        n = len(g)
        for pol, name in ((0, "hh"), (1, "hv")):
            dts, cohs, inter = [], [], {}
            for i in range(n):
                for j in range(i + 1, n):
                    dt = int(days[j] - days[i])
                    if dt > MAX_PAIR_DAYS:
                        continue
                    coh, num = C.ifg.interferogram(stack[g.file[i]][pol], stack[g.file[j]][pol])
                    dts.append(dt)
                    cohs.append(coh)
                    if pol == 0 and j == i + 1:
                        inter[(i, j)] = num
                    if pol == 0 and j == i + 2:
                        inter[(i, j)] = num
            dts, cube = np.array(dts, np.float32), np.stack(cohs)
            tag = f"_{name}_t{t:03d}"
            ginf, g0, tau, rmse = fit_decay(dts, cube)
            bands.update({"ginf" + tag: ginf, "g0" + tag: g0, "tau" + tag: tau, "rmse" + tag: rmse})
            for k, sel in (("coh_short", dts <= 12), ("coh_long", dts > 36)):
                if sel.sum():
                    bands[k + tag] = np.nanmean(cube[sel], 0)
            if pol == 0:
                pi = [(i, j) for i in range(n) for j in range(i + 1, n) if days[j] - days[i] <= MAX_PAIR_DAYS]
                pairs_dt = dict(zip(pi, dts))
                for k, months in (("coh_leafon", (6, 7, 8, 9)), ("coh_leafoff", (12, 1, 2, 3))):
                    sel = np.array([pairs_dt[p] <= 36 and mon[p[0]] in months and mon[p[1]] in months for p in pi])
                    if sel.sum() >= 2:
                        bands[k + tag] = np.nanmean(cube[sel], 0)
                clo = []
                for i in range(n - 2):
                    if days[i + 2] - days[i] <= 36 and (i, i + 1) in inter and (i + 1, i + 2) in inter:
                        # I12 I23 conj(I13); inter holds the unnormalised boxcar sums
                        trip = inter[(i, i + 1)] * inter[(i + 1, i + 2)] * np.conj(inter[(i, i + 2)])
                        clo.append(np.abs(np.angle(trip)))
                if clo:
                    bands["closure" + tag] = np.nanmean(np.stack(clo), 0)
            print(f"track {t} {name}: {n} dates, {len(dts)} pairs", flush=True)
    C.write_bands("coherence", bands, tf, shape)


if __name__ == "__main__":
    main()
