"""Product 13: cumulative line-of-sight displacement per pixel (settling or compaction of pads).

Chain of consecutive-pair interferograms (gap <= MAX_GAP_DAYS), 3 x 3 boxcar. Each pair's phase has
its long-wave component removed (coherence-weighted phasor mean over LP_PX pixels, about 500 m),
which takes out orbit and troposphere ramps. Phases are summed over the chain and converted to mm
(positive toward the satellite). Pixels need coherence >= MIN_COH in at least MIN_SHARE of the pairs.

Bands (suffix _tNNN):
  los_total_mm    sum of all pair displacements (first to last date)
  los_range_mm    max - min of the cumulative series
  los_rate_mm_yr  least-squares slope of the cumulative series, mm per year
  coh_share       share of pairs with coherence >= MIN_COH

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_los_motion_9t.py [--area warren]
"""
import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter

import _nisar_feat_common as C

MAX_GAP_DAYS, MIN_COH, MIN_SHARE, LP_PX = 24, 0.45, 0.7, 101


def remove_longwave(num, coh):
    ok = np.isfinite(num) & np.isfinite(coh)
    ph = np.where(ok, num / np.where(np.abs(num) > 0, np.abs(num), 1), 0)
    w = ph * np.where(ok, coh, 0)
    lp = uniform_filter(w.real, LP_PX) + 1j * uniform_filter(w.imag, LP_PX)
    return np.where(ok, np.angle(num * np.conj(lp)), np.nan)


def main():
    idx, stack, tf, shape = C.load()
    bands = {}
    for t, g in C.by_track(idx):
        d = pd.to_datetime(g.date)
        days = (d - d.min()).dt.days.values.astype(float)
        steps, tmid, good = [], [], []
        for i in range(len(g) - 1):
            if days[i + 1] - days[i] > MAX_GAP_DAYS:
                continue
            coh, num = C.ifg.interferogram(stack[g.file[i]][0], stack[g.file[i + 1]][0])
            ph = remove_longwave(num, coh)
            steps.append(ph * C.ifg.MM_PER_RAD)
            good.append(coh >= MIN_COH)
            tmid.append((days[i] + days[i + 1]) / 2)
        tag = f"_t{t:03d}"
        if len(steps) < 3:
            print(f"track {t}: only {len(steps)} usable pairs, skipped", flush=True)
            continue
        steps, good, tmid = np.stack(steps), np.stack(good), np.array(tmid)
        share = good.mean(0)
        use = share >= MIN_SHARE
        s = np.where(good, steps, 0)          # an incoherent pair adds nothing
        cum = np.cumsum(s, 0)
        tt = tmid - tmid.mean()
        rate = (tt[:, None, None] * (cum - cum.mean(0))).sum(0) / (tt ** 2).sum() * 365.25
        m = lambda a: np.where(use, a, np.nan)  # noqa: E731
        bands["los_total_mm" + tag] = m(cum[-1])
        bands["los_range_mm" + tag] = m(cum.max(0) - cum.min(0))
        bands["los_rate_mm_yr" + tag] = m(rate)
        bands["coh_share" + tag] = share
        print(f"track {t}: {len(steps)} pairs, usable {use.mean():.1%}", flush=True)
    C.write_bands("losmotion", bands, tf, shape)


if __name__ == "__main__":
    main()
