"""Sentinel-2 and date-mean radar layers sampled on the footprints of a scorer samples file (helper for the follow-up checks).

Optical layers come from _nisar_vs_optical_9t.fetch (cached, 5 m grid): per date (3 Jun 2026, 7 Sep 2026, 27 Oct 2025)
NDVI, NDMI, red and near infrared, the June-minus-October NDVI, and for three of them a 15 m box mean, a box-minus-surround
contrast (15 m against 35 m) and a 25 m local standard deviation, so the optical set has some spatial texture like the radar set.
"Radar basic" is the six date-mean backscatter layers (HH and HV, three tracks, dB) of the radiometric-normalisation product.
Values on a footprint are read with C.sample_values (median over the footprint), the same rule as every other band.
"""
import numpy as np
import rasterio
from scipy.ndimage import uniform_filter

import _nisar_feat_common as C
import _nisar_vs_optical_9t as O


def _box(a, k):
    ok = np.isfinite(a)
    return uniform_filter(np.where(ok, a, 0.0), k) / np.maximum(uniform_filter(ok.astype(float), k), 1e-6)


def grid():
    with rasterio.open(C.FEAT_DIR / f"nisar_check_radnorm_{C.A.TAG}_5m.tif") as r:
        return r.transform, (r.height, r.width)


def optical_layers():
    tf, shape = grid()
    opt = O.fetch(tf, shape)
    L = {}
    for d in ("jun", "sep", "oct"):
        for k in ("ndvi", "ndmi", "red", "nir"):
            L[f"{k}_{d}"] = opt[d][k]
    L["ndvi_jun_minus_oct"] = opt["jun"]["ndvi"] - opt["oct"]["ndvi"]
    for n in ("ndvi_jun", "ndvi_oct", "ndmi_sep"):
        a = L[n]
        b3, b7 = _box(a, 3), _box(a, 7)
        L[f"{n}_box3"], L[f"{n}_contrast"] = b3, b3 - b7
        L[f"{n}_std5"] = np.sqrt(np.maximum(_box(a * a, 5) - _box(a, 5) ** 2, 0))
    return L


def radar_basic_layers():
    tf, shape = grid()
    with rasterio.open(C.FEAT_DIR / f"nisar_check_radnorm_{C.A.TAG}_5m.tif") as r:
        names, arr = list(r.descriptions), r.read()
    return {n: arr[i] for i, n in enumerate(names) if n.startswith("raw_mean_")}


def on_rows(S, layers):
    """(matrix aligned with the rows of load_samples S, names)."""
    z, pads, sel = S["z"], S["pads"], S["sel"]
    names = list(layers)
    P, D = [], []
    for n in names:
        pv, dv = C.sample_values(np.asarray(layers[n], np.float32).ravel(), z)
        P.append(pv[pads])
        D.append(dv[sel])
    return np.vstack([np.array(P).T, np.array(D).T]), names
