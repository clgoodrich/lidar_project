"""Product 17: more spatial descriptors of the temporal-mean image, HH and HV (per track).

Bands (suffix _{pol}_tNNN):
  sd3, sd11, sd15     local std of the dB image at 3, 11 and 15 pixels (multi-scale contrast)
  skew7, kurt7        local skewness and excess kurtosis of dB, 7 x 7
  grad                Sobel gradient magnitude of dB (smoothed 1 px)
  dog                 difference of Gaussians of dB, sigma 1 minus sigma 4 (centre vs surround)
  aniso               structure-tensor coherence of the dB gradient, 7 x 7 (1 = one dominant edge direction,
                      0 = isotropic); straight pad edges and roads raise it
  glcm_con, glcm_hom  contrast and homogeneity of adjacent-pixel dB differences averaged over 4 directions,
                      5 x 5 (a fast stand-in for the grey-level co-occurrence matrix at distance 1)
  tex_hv_minus_hh     (HV sd7) minus (HH sd7), written once per track as cross_sd7

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_spatial_9t.py [--area warren]
"""
import numpy as np
from scipy.ndimage import gaussian_filter, sobel, uniform_filter

import _nisar_feat_common as C

SHIFTS = [(0, 1), (1, 0), (1, 1), (1, -1)]


def local_sd(d, w):
    m = uniform_filter(d, w)
    return np.sqrt(np.maximum(uniform_filter(d * d, w) - m * m, 0))


def local_moments(d, w):
    m = uniform_filter(d, w)
    c = d - m
    v = uniform_filter(c * c, w)
    s = uniform_filter(c ** 3, w) / np.maximum(v, 1e-6) ** 1.5
    k = uniform_filter(c ** 4, w) / np.maximum(v, 1e-6) ** 2 - 3
    return s, k


def main():
    idx, stack, tf, shape = C.load()
    bands = {}
    for t, g in C.by_track(idx):
        tag_t = f"_t{t:03d}"
        sd7 = {}
        for pol, name in ((0, "hh"), (1, "hv")):
            p = np.abs(C.cube(g, stack, pol)) ** 2
            ok = np.all(np.isfinite(p) & (p > 0), axis=0)
            mean = np.where(ok, p.mean(0), np.nan)
            d = C.db(np.where(ok, mean, np.nanmedian(mean)))
            tag = f"_{name}{tag_t}"
            m = lambda a: np.where(ok, a, np.nan)  # noqa: E731
            for w in (3, 11, 15):
                bands[f"sd{w}" + tag] = m(local_sd(d, w))
            sd7[name] = local_sd(d, 7)
            s, k = local_moments(d, 7)
            bands["skew7" + tag], bands["kurt7" + tag] = m(s), m(k)
            ds = gaussian_filter(d, 1)
            gy, gx = sobel(ds, 0), sobel(ds, 1)
            bands["grad" + tag] = m(np.hypot(gx, gy))
            bands["dog" + tag] = m(gaussian_filter(d, 1) - gaussian_filter(d, 4))
            jxx, jyy, jxy = (uniform_filter(a, 7) for a in (gx * gx, gy * gy, gx * gy))
            bands["aniso" + tag] = m(np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / np.maximum(jxx + jyy, 1e-9))
            con = np.zeros(shape, np.float32)
            hom = np.zeros(shape, np.float32)
            for dy, dx in SHIFTS:
                diff = d - np.roll(d, (dy, dx), (0, 1))
                con += diff ** 2 / len(SHIFTS)
                hom += 1 / (1 + diff ** 2) / len(SHIFTS)
            bands["glcm_con" + tag], bands["glcm_hom" + tag] = m(uniform_filter(con, 5)), m(uniform_filter(hom, 5))
        bands["cross_sd7" + tag_t] = np.where(np.isfinite(bands["sd3_hh" + tag_t]), sd7["hv"] - sd7["hh"], np.nan)
        print(f"track {t}: {len(g)} dates", flush=True)
    C.write_bands("spatial", bands, tf, shape)


if __name__ == "__main__":
    main()
