"""Signal-quality checks on the RSLC windows (backlog item "effective looks, impulse response, RFI, noise floor").

The RSLC windows are in native slant-range, zero-Doppler geometry, so range and azimuth are separate axes. For every
window (HH and HV) this script measures:

  spacing        slant-range sample spacing (m), azimuth sample spacing (m), mean incidence angle
  bandwidth      occupied range bandwidth (MHz) from the mean range power spectrum: bins above half the smoothed plateau
                 times the sampling rate. This checks the nominal 40 MHz against the data.
  looks          coefficient of variation squared of intensity in homogeneous 16 x 16 blocks (blocks within 1 dB of the
                 scene median). One sample of fully developed speckle has CV^2 = 1, so ENL per sample = 1 / CV^2.
                 Lag-1 and lag-2 complex correlation in range and azimuth give the dependence between neighbours.
  impulse        half-power width of the brightest isolated scatterers, after removing the phase ramp per axis and
                 upsampling x8 by FFT. These are uncontrolled scatterers, not corner reflectors, so the widths are upper
                 bounds on the true impulse response.
  rfi            largest spike of the mean range spectrum over its 101-bin running median (dB), number of bins more than
                 3 dB above it, and the share of azimuth lines more than 3 dB above their 51-line running median
  floor          1st, 5th and 50th percentile of 16 x 16 block-mean power (dB) per polarisation: the dynamic range of the
                 scene. The HV floor says how close the darkest ground is to the noise.

Outputs: data/9t/results/nisar/nisar_signal_checks_per_window_9t.csv and nisar_signal_checks_by_track_9t.csv

  python _nisar_signal_checks_9t.py [--area 9t]
"""
import glob

import h5py
import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter, median_filter

import _nisar_feat_common as C

C_LIGHT = 299792458.0
BLK, N_PEAK, UP = 16, 300, 8


def occupied_bw_mhz(rows_z, dr):
    """Occupied range bandwidth: share of range-frequency bins above half the smoothed spectral plateau, times the sampling rate."""
    s = (np.abs(np.fft.fft(rows_z, axis=1)) ** 2).mean(0)
    s = np.fft.fftshift(s)
    sm = median_filter(s, size=101, mode="nearest")
    fs = C_LIGHT / (2 * dr)
    plateau = np.percentile(sm, 90)
    return float((sm > 0.5 * plateau).mean() * fs / 1e6), s, sm


def block_mean(p):
    h, w = (p.shape[0] // BLK) * BLK, (p.shape[1] // BLK) * BLK
    return p[:h, :w].reshape(h // BLK, BLK, w // BLK, BLK).mean((1, 3))


def half_power_width(a):
    """Width in samples at half power of a 1-D amplitude profile around its peak (linear interpolation); NaN if not closed."""
    p = a ** 2
    i = int(np.argmax(p))
    hp = p[i] / 2

    def edge(step):
        j = i
        while 0 < j < len(p) - 1 and p[j + step] > hp:
            j += step
        if not (0 < j < len(p) - 1):
            return np.nan
        return j + step * (p[j] - hp) / (p[j] - p[j + step])
    lo, hi = edge(-1), edge(+1)
    return hi - lo


def impulse_widths(z, dr, daz):
    p = np.abs(z) ** 2
    mx = maximum_filter(p, size=21)
    cand = np.argwhere((p == mx) & (p > np.percentile(p, 99.99)))
    cand = [c for c in cand if 12 <= c[0] < p.shape[0] - 12 and 12 <= c[1] < p.shape[1] - 12]
    cand = sorted(cand, key=lambda c: -p[c[0], c[1]])[:N_PEAK]
    wr, wa = [], []
    for r, c in cand:
        chip = z[r - 8:r + 9, c - 8:c + 9].astype(np.complex128)
        rowv, colv = chip[8, :], chip[:, 8]
        ramp_r = np.angle(np.sum(rowv[1:] * np.conj(rowv[:-1])))
        ramp_a = np.angle(np.sum(colv[1:] * np.conj(colv[:-1])))
        chip = chip * np.exp(-1j * ramp_r * np.arange(17))[None, :] * np.exp(-1j * ramp_a * np.arange(17))[:, None]
        F = np.fft.fftshift(np.fft.fft2(chip))
        P = np.zeros((17 * UP, 17 * UP), complex)
        o = (17 * UP - 17) // 2
        P[o:o + 17, o:o + 17] = F
        up = np.abs(np.fft.ifft2(np.fft.ifftshift(P)))
        i, j = np.unravel_index(np.argmax(up), up.shape)
        if not (3 * UP < i < up.shape[0] - 3 * UP and 3 * UP < j < up.shape[1] - 3 * UP):
            continue
        wr.append(half_power_width(up[i, :]) / UP * dr)
        wa.append(half_power_width(up[:, j]) / UP * daz)
    wr, wa = np.array(wr), np.array(wa)
    return (np.nanmedian(wr) if len(wr) else np.nan, np.nanmedian(wa) if len(wa) else np.nan,
            int(np.isfinite(wr).sum()), np.nanpercentile(wr, [25, 75]) if np.isfinite(wr).any() else [np.nan] * 2,
            np.nanpercentile(wa, [25, 75]) if np.isfinite(wa).any() else [np.nan] * 2)


def lag_corr(z, mask_blocks, axis, lag):
    """|complex correlation| at a lag along an axis, over homogeneous blocks."""
    num = den1 = den2 = 0.0
    for bi, bj in np.argwhere(mask_blocks):
        b = z[bi * BLK:(bi + 1) * BLK, bj * BLK:(bj + 1) * BLK]
        a, c = (b[:, lag:], b[:, :-lag]) if axis == 1 else (b[lag:, :], b[:-lag, :])
        num += np.sum(a * np.conj(c))
        den1 += np.sum(np.abs(a) ** 2)
        den2 += np.sum(np.abs(c) ** 2)
    return float(np.abs(num) / np.sqrt(den1 * den2))


def main():
    idx = pd.read_csv(sorted(glob.glob(str(C.A.RSLC / "*index*.csv")))[0])
    rows = []
    for _, r in idx.iterrows():
        with h5py.File(C.A.RSLC / r.file) as h:
            sr, zt = h["slantRange"][:], h["zeroDopplerTime"][:]
            inc = float(np.mean(h["geolocationGrid/incidenceAngle"][:]))
            vel = float(np.mean(h["geolocationGrid/groundTrackVelocity"][:]))
            pol = {"hh": h["HH"][:], "hv": h["HV"][:]}
        dr, daz = float(np.median(np.diff(sr))), float(np.median(np.diff(zt))) * vel
        row = dict(date=r.date, track=int(r.track), collection=r.collection, dr_m=round(dr, 3), daz_m=round(daz, 3), inc_deg=round(inc, 1))
        for name, z in pol.items():
            p = np.abs(z) ** 2
            bw, s, sm = occupied_bw_mhz(z[::2], dr)
            bm = block_mean(p)
            med = np.median(bm)
            homog = np.abs(10 * np.log10(bm / med)) < 1.0
            norm = []
            for bi, bj in np.argwhere(homog):
                b = p[bi * BLK:(bi + 1) * BLK, bj * BLK:(bj + 1) * BLK]
                norm.append((b / b.mean()).ravel())
            norm = np.concatenate(norm)
            cv2 = float(norm.var() / norm.mean() ** 2)
            ratio = s / sm
            rowp = p.mean(1)
            rowr = rowp / median_filter(rowp, size=51, mode="nearest")
            bdb = 10 * np.log10(bm)
            row.update({f"{name}_bw_mhz": round(bw, 1), f"{name}_cv2": round(cv2, 3), f"{name}_enl_per_sample": round(1 / cv2, 3),
                        f"{name}_rho_rg1": round(lag_corr(z, homog, 1, 1), 3), f"{name}_rho_rg2": round(lag_corr(z, homog, 1, 2), 3),
                        f"{name}_rho_az1": round(lag_corr(z, homog, 0, 1), 3), f"{name}_rho_az2": round(lag_corr(z, homog, 0, 2), 3),
                        f"{name}_rfi_spike_db": round(float(10 * np.log10(ratio.max())), 2),
                        f"{name}_rfi_bins_gt3db": int((ratio > 2).sum()),
                        f"{name}_bad_lines_share": round(float((rowr > 2).mean()), 4),
                        f"{name}_homog_blocks": int(homog.sum()),
                        f"{name}_p01_db": round(float(np.percentile(bdb, 1)), 2), f"{name}_p05_db": round(float(np.percentile(bdb, 5)), 2),
                        f"{name}_p50_db": round(float(np.percentile(bdb, 50)), 2)})
        wr, wa, npk, qr, qa = impulse_widths(pol["hh"], dr, daz)
        row.update(dict(irf_range_m=round(float(wr), 2), irf_range_q25=round(float(qr[0]), 2), irf_range_q75=round(float(qr[1]), 2),
                        irf_az_m=round(float(wa), 2), irf_az_q25=round(float(qa[0]), 2), irf_az_q75=round(float(qa[1]), 2), irf_n_peaks=npk))
        rows.append(row)
        print({k: row[k] for k in ("date", "track", "hh_bw_mhz", "hh_cv2", "hh_rho_rg1", "hh_rho_az1", "hh_rfi_spike_db", "irf_range_m", "irf_az_m")}, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(C.OUT / f"nisar_signal_checks_per_window_{C.A.TAG}.csv", index=False)
    num = [c for c in df.columns if c not in ("date", "collection", "track")]
    by = df.groupby("track")[num].median().round(3)
    for c in ("hh_rfi_spike_db", "hv_rfi_spike_db"):
        med = df.groupby("track")[c].transform("median")
        mad = (df[c] - med).abs().groupby(df.track).transform("median") + 1e-3
        df[c.replace("spike_db", "flag")] = ((df[c] - med) / (1.4826 * mad)) > 5
    by["n_windows"] = df.groupby("track").size()
    by["rfi_flagged_windows_hh"] = df.groupby("track")["hh_rfi_flag"].sum()
    by["rfi_flagged_windows_hv"] = df.groupby("track")["hv_rfi_flag"].sum()
    by.to_csv(C.OUT / f"nisar_signal_checks_by_track_{C.A.TAG}.csv")
    pd.set_option("display.width", 250)
    print(by.T.to_string())


if __name__ == "__main__":
    main()
