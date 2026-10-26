"""Product 11: amplitude order statistics, seasonal means and the yearly trend (per track, HH and HV).

Bands (suffix _{pol}_tNNN, pol = hh or hv; all in dB of power):
  med, p10, p90        order statistics over the dates of the track
  leafon, leafoff      mean of Jun-Sep and of Dec-Mar dates
  season_diff          leafon - leafoff
  trend                least-squares slope, dB per 100 days
  trend_r2             r squared of that line

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_amp_trend_9t.py [--area warren]
"""
import numpy as np
import pandas as pd

import _nisar_feat_common as C


def main():
    idx, stack, tf, shape = C.load()
    bands = {}
    for t, g in C.by_track(idx):
        days = (pd.to_datetime(g.date) - pd.to_datetime(g.date).min()).dt.days.values.astype(float)
        mon = pd.to_datetime(g.date).dt.month.values
        for pol, name in ((0, "hh"), (1, "hv")):
            p = np.abs(C.cube(g, stack, pol)) ** 2
            ok = np.all(np.isfinite(p) & (p > 0), axis=0)
            y = C.db(p)                                   # (date, y, x)
            tag = f"_{name}_t{t:03d}"
            m = lambda a: np.where(ok, a, np.nan)  # noqa: E731
            bands["med" + tag] = m(np.nanmedian(y, 0))
            bands["p10" + tag] = m(np.nanpercentile(y, 10, 0))
            bands["p90" + tag] = m(np.nanpercentile(y, 90, 0))
            on, off = np.isin(mon, (6, 7, 8, 9)), np.isin(mon, (12, 1, 2, 3))
            if on.sum() >= 2 and off.sum() >= 2:
                bands["leafon" + tag] = m(y[on].mean(0))
                bands["leafoff" + tag] = m(y[off].mean(0))
                bands["season_diff" + tag] = bands["leafon" + tag] - bands["leafoff" + tag]
            dd = days - days.mean()
            ym = y - y.mean(0)
            sxy = (dd[:, None, None] * ym).sum(0)
            sxx = (dd ** 2).sum()
            syy = (ym ** 2).sum(0)
            slope = sxy / sxx
            bands["trend" + tag] = m(slope * 100)
            bands["trend_r2" + tag] = m(np.where(syy > 0, sxy ** 2 / (sxx * syy), np.nan))
        print(f"track {t}: {len(g)} dates, span {days.max():.0f} days", flush=True)
    C.write_bands("amp", bands, tf, shape)


if __name__ == "__main__":
    main()
