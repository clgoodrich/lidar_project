"""Product 2: dual-pol polarimetric features from HH and HV complex (per track).

Covariance C2 = [[<HH HH*>, <HH HV*>], [<HV HH*>, <HV HV*>]], averaged over the dates of one track
and then over a BOX x BOX window. Closed-form eigen-decomposition of the 2 x 2 Hermitian matrix.

Bands (suffix _tNNN):
  rvi     4 HV / (HH + HV), power             Kim and van Zyl 2009 (dual-pol form)
  rfdi    (HH - HV) / (HH + HV), power
  ent     entropy of the eigenvalue shares (bits, 0 to 1)         Cloude and Pottier 1997
  alpha   mean alpha angle (deg, 0 to 90) of the two eigenvectors
  dop     degree of polarisation (l1 - l2) / (l1 + l2)
  rho     |C12| / sqrt(C11 C22), HH-HV correlation magnitude
  phi     angle of C12 (rad), HH-HV phase difference

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_dualpol_9t.py [--area warren]
"""
import numpy as np
from scipy.ndimage import uniform_filter

import _nisar_feat_common as C

BOX = 5


def main():
    idx, stack, tf, shape = C.load()
    bands = {}
    for t, g in C.by_track(idx):
        hh, hv = C.cube(g, stack, 0), C.cube(g, stack, 1)
        ok = np.all(np.isfinite(hh) & np.isfinite(hv) & (hh != 0) & (hv != 0), axis=0)
        c11 = (np.abs(hh) ** 2).mean(0)
        c22 = (np.abs(hv) ** 2).mean(0)
        c12 = (hh * np.conj(hv)).mean(0)
        c11, c22 = uniform_filter(c11, BOX), uniform_filter(c22, BOX)
        c12 = uniform_filter(c12.real, BOX) + 1j * uniform_filter(c12.imag, BOX)
        tr = c11 + c22
        disc = np.sqrt(np.maximum((c11 - c22) ** 2 / 4 + np.abs(c12) ** 2, 0))
        l1, l2 = tr / 2 + disc, np.maximum(tr / 2 - disc, 0)
        p1, p2 = l1 / tr, l2 / tr
        ent = -(p1 * np.log2(np.maximum(p1, 1e-12)) + p2 * np.log2(np.maximum(p2, 1e-12)))
        th = 0.5 * np.arctan2(2 * np.abs(c12), c11 - c22)   # eigenvector 1 = (cos th, sin th e^{i phi})
        alpha = np.degrees(p1 * th + p2 * (np.pi / 2 - th))
        tag = f"_t{t:03d}"
        m = lambda a: np.where(ok, a, np.nan)  # noqa: E731
        bands.update({
            "rvi" + tag: m(4 * c22 / tr), "rfdi" + tag: m((c11 - c22) / tr), "ent" + tag: m(ent),
            "alpha" + tag: m(alpha), "dop" + tag: m((l1 - l2) / tr),
            "rho" + tag: m(np.abs(c12) / np.sqrt(c11 * c22)), "phi" + tag: m(np.angle(c12))})
        print(f"track {t}: {len(g)} dates", flush=True)
    C.write_bands("dualpol", bands, tf, shape)


if __name__ == "__main__":
    main()
