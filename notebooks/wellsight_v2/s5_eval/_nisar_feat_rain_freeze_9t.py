"""Product 7: how each pixel's brightness responds to recent rain and to frozen ground.

Weather is PRISM daily rain and min/max temperature at the area centre (_weather_prism_daily_9t.py).
Per date: API = sum of rain over the 10 days before the pass, each day weighted 0.85 ** age (antecedent
precipitation index, a soil-wetness proxy); frozen = day mean temperature below -1 C. Per track and
pixel, HH and HV dB are regressed on the API (and compared frozen against thawed). Bare, compacted or
graded ground (pads) should react to wetness more than canopy does.

Bands (suffix _tNNN):
  api_slope_hh, api_slope_hv   dB per 10 mm of API, least squares over the track's dates
  api_r_hh, api_r_hv           correlation of dB with API
  wet_dry_hh                   mean HH dB of dates with API >= median minus those below
  frozen_hh, frozen_hv         mean dB of frozen dates minus thawed (needs >= 2 frozen and >= 3 thawed dates)
  ratio_api_slope              dB per 10 mm of API of the HV - HH ratio

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_rain_freeze_9t.py
"""
import numpy as np
import pandas as pd

import _nisar_feat_common as C

W = C.A.DATA / "derived" / "weather" / "weather_prism_daily_9t.csv"
DECAY, N_DAYS, FROZEN_C = 0.85, 10, -1.0


def api_and_frozen(dates):
    w = pd.read_csv(W, parse_dates=["date"]).set_index("date")
    out = []
    for d in pd.to_datetime(dates):
        past = [w.ppt.get(d - pd.Timedelta(days=i + 1), np.nan) for i in range(N_DAYS)]
        api = float(np.nansum([p * DECAY ** i for i, p in enumerate(past)]))
        t = (w.tmin.get(d, np.nan) + w.tmax.get(d, np.nan)) / 2
        out.append((api, t < FROZEN_C))
    return np.array([o[0] for o in out]), np.array([o[1] for o in out])


def slope_r(x, y):
    """Per-pixel least-squares slope and correlation of y (date, y, x) on x (date)."""
    xm = x - x.mean()
    ym = y - np.nanmean(y, 0)
    sxy = (xm[:, None, None] * ym).sum(0)
    sxx = (xm ** 2).sum()
    syy = (ym ** 2).sum(0)
    return sxy / sxx, sxy / np.sqrt(sxx * syy + 1e-12)


def main():
    idx, stack, tf, shape = C.load()
    bands = {}
    for t, g in C.by_track(idx):
        api, frozen = api_and_frozen(g.date)
        print(f"track {t}: {len(g)} dates, API {api.min():.1f}-{api.max():.1f} mm, frozen {int(frozen.sum())}", flush=True)
        p = [np.abs(C.cube(g, stack, k)) ** 2 for k in (0, 1)]
        ok = np.all([np.all(np.isfinite(x) & (x > 0), axis=0) for x in p], axis=0)
        d = [C.db(x) for x in p]
        tag = f"_t{t:03d}"
        m = lambda a: np.where(ok, a, np.nan)  # noqa: E731
        x10 = api / 10
        for name, y in (("hh", d[0]), ("hv", d[1])):
            s, r = slope_r(x10, y)
            bands[f"api_slope_{name}" + tag], bands[f"api_r_{name}" + tag] = m(s), m(r)
        s, _ = slope_r(x10, d[1] - d[0])
        bands["ratio_api_slope" + tag] = m(s)
        wet = api >= np.median(api)
        if wet.sum() and (~wet).sum():
            bands["wet_dry_hh" + tag] = m(d[0][wet].mean(0) - d[0][~wet].mean(0))
        if frozen.sum() >= 2 and (~frozen).sum() >= 3:
            for name, y in (("hh", d[0]), ("hv", d[1])):
                bands[f"frozen_{name}" + tag] = m(y[frozen].mean(0) - y[~frozen].mean(0))
    C.write_bands("rainfreeze", bands, tf, shape)


if __name__ == "__main__":
    main()
