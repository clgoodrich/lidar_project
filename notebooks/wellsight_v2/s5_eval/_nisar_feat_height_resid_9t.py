"""Product 14: scattering height above the lidar ground, and baseline-driven (volume) decorrelation.

Run on the lidar-referenced SLC stack (NISAR_STACK=slc), where the topographic phase of the lidar
bare earth is already flattened out. What is left in a pair's phase that scales with the
perpendicular baseline is the height of the scattering phase centre above that ground:
    phi_pair = kz * h,   kz = 4 pi Bperp / (lambda R sin(theta))        (rad per metre)
Per pixel, over all pairs with gap <= MAX_GAP_DAYS, h is the coherence-weighted least-squares slope of
phi on kz (long-wave phase removed as in the line-of-sight product). Canopy puts the phase centre
metres above the ground, bare graded pads should sit near 0. Coherence is regressed on
[1, gap, |kz|]; the |kz| coefficient measures how fast coherence falls with baseline (volume
decorrelation) once temporal decorrelation is accounted for.

The sign of Bperp is arbitrary per track, so it is fixed so that dense forest (cover > 0.8) has a
positive median height.

Bands (suffix _tNNN):
  height_m         phase-centre height above lidar ground, metres
  height_rms_rad   weighted rms of the phase left after the fit
  coh_kz_slope     change of coherence per 0.01 rad/m of |kz| (negative = baseline decorrelation)

  NISAR_STACK=slc python notebooks/wellsight_v2/s5_eval/_nisar_feat_height_resid_9t.py
"""
import os
import sys
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

os.environ.setdefault("NISAR_STACK", "slc")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "s1_build"))
import _nisar_feat_common as C  # noqa: E402
import _nisar_geometry as geo  # noqa: E402
from _nisar_feat_los_motion_9t import remove_longwave  # noqa: E402

MAX_GAP_DAYS, MIN_COH, WAVELENGTH = 60, 0.35, 0.2384


def orbit_state(rslc_path):
    """Satellite position at closest approach to the scene centre, slant range, incidence angle."""
    with h5py.File(rslc_path, "r") as o:
        orb = geo.Orbit(o["orbit/time"][:], o["orbit/position"][:], o["orbit/velocity"][:])
        gg = o["geolocationGrid"]
        cx, cy = float(gg["coordinateX"][()].mean()), float(gg["coordinateY"][()].mean())
        zt = o["zeroDopplerTime"][:]
        inc = float(np.radians(gg["incidenceAngle"][()].mean()))
    lon, lat = geo.utm_to_lonlat(np.array([cx]), np.array([cy]))
    P = geo.lonlat_to_ecef(lon, lat, np.array([300.0]))
    t, r = geo.zero_doppler(orb, P, np.array([zt[len(zt) // 2]]))
    S, V, _ = orb(t)
    return dict(S=S[0], V=V[0], P=P[0], R=float(r[0]), inc=inc)


def kz_table(g, rs_dir):
    """kz (rad/m) for every pair (i, j) of the rows of g, phase = angle(s_i conj s_j)."""
    st = [orbit_state(rs_dir / f) for f in g.rslc]
    l = st[0]["P"] - st[0]["S"]
    l /= np.linalg.norm(l)
    n = np.cross(l, st[0]["V"] / np.linalg.norm(st[0]["V"]))
    n /= np.linalg.norm(n)
    R, inc = np.mean([s["R"] for s in st]), np.mean([s["inc"] for s in st])
    kz = {}
    for i in range(len(g)):
        for j in range(i + 1, len(g)):
            kz[(i, j)] = 4 * np.pi * float((st[j]["S"] - st[i]["S"]) @ n) / (WAVELENGTH * R * np.sin(inc))
    return kz


def main():
    import importlib
    rg = importlib.import_module("_nisar_regeocode_lidar_9t")
    idx, stack, tf, shape = C.load()
    cover = C.st.canopy_cover(tf, shape)
    bands = {}
    for t, g in C.by_track(idx):
        kz = kz_table(g, rg.RS)
        d = pd.to_datetime(g.date)
        days = (d - d.min()).dt.days.values
        z = lambda: np.zeros(shape, np.float32)  # noqa: E731
        sw, swk2, swkp, swp2 = z(), z(), z(), z()
        n, sg, sk, sgg, sgk, skk, sy, sgy, sky = (z() for _ in range(9))
        pairs = 0
        for (i, j), k in kz.items():
            gap = float(days[j] - days[i])
            if gap > MAX_GAP_DAYS:
                continue
            coh, num = C.ifg.interferogram(stack[g.file[i]][0], stack[g.file[j]][0])
            ph = remove_longwave(num, coh)
            ok = np.isfinite(ph) & (coh >= MIN_COH)
            w = np.where(ok, coh ** 2, 0).astype(np.float32)
            p = np.where(ok, ph, 0)
            sw += w
            swk2 += w * k * k
            swkp += w * k * p
            swp2 += w * p * p
            v = np.isfinite(coh)
            y, m = np.where(v, coh, 0), v.astype(np.float32)
            ak = abs(k) * 0.01
            n += m
            sg += m * gap
            sk += m * ak
            sgg += m * gap * gap
            sgk += m * gap * ak
            skk += m * ak * ak
            sy += y
            sgy += y * gap
            sky += y * ak
            pairs += 1
        h = np.where(swk2 > 1e-9, swkp / np.maximum(swk2, 1e-12), np.nan)
        sgn = 1.0 if np.nanmedian(h[cover > 0.8]) >= 0 else -1.0
        h *= sgn
        rms = np.sqrt(np.maximum(swp2 - 2 * (swkp / np.maximum(swk2, 1e-12)) * swkp
                                 + (swkp / np.maximum(swk2, 1e-12)) ** 2 * swk2, 0) / np.maximum(sw, 1e-9))
        # coherence ~ a + b gap + c |kz|: solve the 3 x 3 normal equations per pixel
        M = np.stack([np.stack([n, sg, sk], -1), np.stack([sg, sgg, sgk], -1), np.stack([sk, sgk, skk], -1)], -2)
        rhs = np.stack([sy, sgy, sky], -1)
        det = np.linalg.det(M)
        sol = np.full(rhs.shape, np.nan, np.float32)
        okm = (det > 1e-6) & (n >= 8)
        sol[okm] = np.linalg.solve(M[okm], rhs[okm][..., None])[..., 0]
        tag = f"_t{t:03d}"
        good = sw > 0
        bands["height_m" + tag] = np.where(good, h, np.nan)
        bands["height_rms_rad" + tag] = np.where(good, rms, np.nan)
        bands["coh_kz_slope" + tag] = sol[..., 2]
        print(f"track {t}: {pairs} pairs, sign {sgn:+.0f}, forest median height {np.nanmedian(h[cover > 0.8]):.1f} m, "
              f"open median {np.nanmedian(h[cover < 0.1]):.1f} m", flush=True)
    C.A.TAG = C.A.TAG.replace("_slc", "")      # the stack tag must not leak into the band file name
    C.write_bands("heightresid", bands, tf, shape)


if __name__ == "__main__":
    main()
