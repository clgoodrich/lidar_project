"""Product 8 (bands): transient bright and dark outliers in the HH time series (per track).

For each pixel, each date's dB value is scored against the pixel's own median and MAD
(z = (x - median) / (1.4826 MAD)). A rig, truck or new equipment on a pad shows as a few dates
with high z. The truth check against DEP spud dates is a separate step (_nisar_events_vs_spud_9t.py,
not written yet).

Bands (suffix _tNNN):
  hi_share   share of dates with z > 3
  lo_share   share of dates with z < -3
  z_max      largest z
  z_min      smallest z
  run_hi     longest run of consecutive dates with z > 2

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_events_9t.py [--area warren]
"""
import numpy as np

import _nisar_feat_common as C


def longest_run(mask):
    """Longest run of True along axis 0 of (date, y, x)."""
    best = np.zeros(mask.shape[1:], np.int16)
    cur = np.zeros_like(best)
    for m in mask:
        cur = np.where(m, cur + 1, 0)
        best = np.maximum(best, cur)
    return best


def main():
    idx, stack, tf, shape = C.load()
    bands = {}
    for t, g in C.by_track(idx):
        p = np.abs(C.cube(g, stack, 0)) ** 2
        ok = np.all(np.isfinite(p) & (p > 0), axis=0)
        y = C.db(p)
        med = np.nanmedian(y, 0)
        mad = np.nanmedian(np.abs(y - med), 0)
        z = (y - med) / np.maximum(1.4826 * mad, 0.1)       # floor 0.1 dB so flat pixels do not blow up
        tag = f"_t{t:03d}"
        m = lambda a: np.where(ok, a, np.nan)  # noqa: E731
        bands["hi_share" + tag] = m((z > 3).mean(0))
        bands["lo_share" + tag] = m((z < -3).mean(0))
        bands["z_max" + tag] = m(np.nanmax(z, 0))
        bands["z_min" + tag] = m(np.nanmin(z, 0))
        bands["run_hi" + tag] = m(longest_run(z > 2))
        print(f"track {t}: {len(g)} dates", flush=True)
    C.write_bands("events", bands, tf, shape)


if __name__ == "__main__":
    main()
