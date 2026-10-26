"""Product 16: per-pixel temporal statistics of amplitude and of the HH/HV pair, and cross-track contrasts.

Bands (suffix _tNNN per track unless noted):
  da_hh, da_hv           amplitude dispersion std(|a|) / mean(|a|) over dates (Ferretti 2001 stability index)
  cvp_hh, cvp_hv         temporal std / mean of power
  iqr_hh, range_hh       interquartile range and max - min of the HH dB series
  iqr_hv, range_hv       same for HV
  ratio_mean             mean over dates of HV - HH in dB
  ratio_sd               temporal std of HV - HH in dB (does the volume share move?)
  corr_hhhv              temporal Pearson correlation of the HH and HV dB series
  rho_t                  |sum(HH conj HV)| / sqrt(sum|HH|^2 sum|HV|^2) over dates (co/cross-pol correlation in time)
  span_db                10 log10 of the mean total power (HH + HV)
Cross-track (no suffix; need an ascending and a descending track):
  hh_asc_minus_desc      mean HH dB, mean of ascending tracks minus the descending one
  hv_asc_minus_desc      same for HV
  hh_track_sd            std of the per-track mean HH dB (all tracks)
  hvhh_track_sd          std of the per-track mean HV - HH dB

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_temporal_9t.py [--area warren]
"""
import numpy as np

import _nisar_feat_common as C


def main():
    idx, stack, tf, shape = C.load()
    bands, mean_hh, mean_hv, asc = {}, {}, {}, {}
    for t, g in C.by_track(idx):
        a = [np.abs(C.cube(g, stack, p)) for p in (0, 1)]
        c = [C.cube(g, stack, p) for p in (0, 1)]
        ok = np.all([np.all(np.isfinite(x) & (x > 0), axis=0) for x in a], axis=0)
        pw = [x ** 2 for x in a]
        d = [C.db(x) for x in pw]
        tag = f"_t{t:03d}"
        m = lambda z: np.where(ok, z, np.nan)  # noqa: E731
        for k, i in (("hh", 0), ("hv", 1)):
            bands[f"da_{k}" + tag] = m(a[i].std(0) / a[i].mean(0))
            bands[f"cvp_{k}" + tag] = m(pw[i].std(0) / pw[i].mean(0))
            q1, q3 = np.nanpercentile(d[i], [25, 75], axis=0)
            bands[f"iqr_{k}" + tag] = m(q3 - q1)
            bands[f"range_{k}" + tag] = m(np.nanmax(d[i], 0) - np.nanmin(d[i], 0))
        r = d[1] - d[0]
        bands["ratio_mean" + tag] = m(np.nanmean(r, 0))
        bands["ratio_sd" + tag] = m(np.nanstd(r, 0))
        x, y = d[0] - np.nanmean(d[0], 0), d[1] - np.nanmean(d[1], 0)
        bands["corr_hhhv" + tag] = m((x * y).sum(0) / np.sqrt((x * x).sum(0) * (y * y).sum(0) + 1e-12))
        bands["rho_t" + tag] = m(np.abs((c[0] * np.conj(c[1])).sum(0)) / np.sqrt(pw[0].sum(0) * pw[1].sum(0)))
        bands["span_db" + tag] = m(C.db((pw[0] + pw[1]).mean(0)))
        mean_hh[t], mean_hv[t] = m(C.db(pw[0].mean(0))), m(C.db(pw[1].mean(0)))
        asc[t] = g.direction.iloc[0].upper().startswith("A")
        print(f"track {t}: {len(g)} dates", flush=True)
    A_ = [t for t in asc if asc[t]]
    D_ = [t for t in asc if not asc[t]]
    if A_ and D_:
        bands["hh_asc_minus_desc"] = np.nanmean([mean_hh[t] for t in A_], 0) - np.nanmean([mean_hh[t] for t in D_], 0)
        bands["hv_asc_minus_desc"] = np.nanmean([mean_hv[t] for t in A_], 0) - np.nanmean([mean_hv[t] for t in D_], 0)
    if len(mean_hh) >= 2:
        bands["hh_track_sd"] = np.nanstd([mean_hh[t] for t in mean_hh], 0)
        bands["hvhh_track_sd"] = np.nanstd([mean_hv[t] - mean_hh[t] for t in mean_hh], 0)
    C.write_bands("temporal", bands, tf, shape)


if __name__ == "__main__":
    main()
