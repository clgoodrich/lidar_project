"""Product 3: texture and edge features of the temporal-mean power image (per track).

The mean over all dates of one track is strongly despeckled, so local statistics are usable at 5 m.

Bands (suffix _tNNN):
  cv3, cv7      local std / mean of linear power in a 3 x 3 and a 7 x 7 window
  sd_db7        local std of the dB image, 7 x 7 (a contrast measure)
  ent_db        local entropy of the 5-bit-quantised dB image, disk radius 3 (skimage, if installed)
  roa_edge      ratio-of-averages edge strength, max over 4 orientations, 1 - min(m1/m2, m2/m1)
                (Touzi et al. 1988 constant-false-alarm edge detector, half-windows 4 x 9 px)

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_texture_9t.py [--area warren]
"""
import numpy as np
from scipy.ndimage import correlate, uniform_filter

import _nisar_feat_common as C

HALF = 4      # half-window length (pixels) on each side of the edge
WIDTH = 9     # window extent along the edge (pixels)


def local_cv(p, w):
    m = uniform_filter(p, w)
    v = np.maximum(uniform_filter(p * p, w) - m * m, 0)
    return np.sqrt(v) / m


def half_kernels():
    """Pairs of normalised half-plane masks for 0, 45, 90 and 135 degree edge normals."""
    r = HALF
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1].astype(float)
    out = []
    for ang in (0, 45, 90, 135):
        a = np.radians(ang)
        along = xx * np.cos(a) + yy * np.sin(a)          # distance along the normal
        across = -xx * np.sin(a) + yy * np.cos(a)        # distance along the edge
        inside = np.abs(across) <= (WIDTH - 1) / 2
        k1 = ((along >= 1) & inside).astype(float)
        k2 = ((along <= -1) & inside).astype(float)
        out.append((k1 / k1.sum(), k2 / k2.sum()))
    return out


def main():
    idx, stack, tf, shape = C.load()
    try:
        from skimage.filters.rank import entropy
        from skimage.morphology import disk
    except ImportError:
        entropy = None
    kers = half_kernels()
    bands = {}
    for t, g in C.by_track(idx):
        hh = np.abs(C.cube(g, stack, 0)) ** 2
        ok = np.all(np.isfinite(hh) & (hh > 0), axis=0)
        p = np.where(ok, hh.mean(0), np.nan)
        fill = np.where(ok, p, np.nanmedian(p))
        d = C.db(fill)
        tag = f"_t{t:03d}"
        m = lambda a: np.where(ok, a, np.nan)  # noqa: E731
        bands["cv3" + tag] = m(local_cv(fill, 3))
        bands["cv7" + tag] = m(local_cv(fill, 7))
        md = uniform_filter(d, 7)
        bands["sd_db7" + tag] = m(np.sqrt(np.maximum(uniform_filter(d * d, 7) - md * md, 0)))
        if entropy is not None:
            lo, hi = np.nanpercentile(d, [1, 99])
            q = np.clip((d - lo) / (hi - lo) * 31, 0, 31).astype(np.uint8)
            bands["ent_db" + tag] = m(entropy(q, disk(3)).astype(np.float32))
        edge = np.zeros(shape, np.float32)
        for k1, k2 in kers:
            m1, m2 = correlate(fill, k1, mode="nearest"), correlate(fill, k2, mode="nearest")
            edge = np.maximum(edge, 1 - np.minimum(m1 / m2, m2 / m1))
        bands["roa_edge" + tag] = m(edge)
        print(f"track {t}: {len(g)} dates", flush=True)
    C.write_bands("texture", bands, tf, shape)


if __name__ == "__main__":
    main()
