"""Does radiometric terrain flattening, or per-date gain normalisation, change the bright-target screen?

Two review points (Codex, 2026-10-19) say the steady-bright-target (SBT) screen of
_nisar_steel_9t.py reads raw HH amplitude with neither correction:
  * terrain: a slope facing the radar is bright, a back slope dark, at facet scale. The 250 m median
    removes only broad slopes. The lidar simulation already gives the right normaliser: the facet
    area each radar cell collects relative to flat ground (area projection, Small 2011), written by
    _nisar_lidar_sim_match_9t.py as nisar_lidar_sim_t###_<area>.tif on the GSLC 5 m grid.
  * gain: median HH power moves 1-3 dB between dates of one track. A date-dependent gain does not
    cancel from the amplitude dispersion D_A = std/mean.

Four variants of the same screen (D_A < 0.25 and 6 dB over the 250 m median), same valid pixels:
  raw      amplitude as stored
  gain     each date divided by its scene median amplitude (valid pixels)
  flat     amplitude divided by sqrt(simulated area factor); shadow and layover cells dropped
  both     gain, then flat
The area factor is the bare-earth simulation (kappa 0). It is a distributed-target normaliser,
not a point-target one: a compact reflector has its own response (see the iteration doc).

Reports per track: SBT pixel count per variant, and how well tracks agree: correlation of the
brightness-over-median maps between tracks, and the share of one track's SBT pixels with an SBT of
another track within 15 m.

  python notebooks/wellsight_v2/s5_eval/_nisar_flatten_gain_test_9t.py --slc
  python notebooks/wellsight_v2/s5_eval/_nisar_flatten_gain_test_9t.py --slc --area 613590
"""
import importlib
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import maximum_filter, median_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ifg = importlib.import_module("_nisar_gslc_interferogram_pits_9t")
steel = importlib.import_module("_nisar_steel_9t")
st = ifg.st
AREA = st.A
OUT = st.OUT
GS = AREA.DATA / "derived" / "nisar_gslc_5m"
DA_MAX, BRIGHT_DB, BG_M, R_M = steel.DA_MAX, steel.BRIGHT_DB, steel.BG_M, 15.0
MASK_FRAC = 0.2   # a 5 m cell with more than this share of shadow or layover is dropped from "flat"


def sim_layers(track, tf, shape):
    """Area factor (linear) and shadow/layover mask on the stack's grid, or None."""
    p = GS / f"nisar_lidar_sim_t{track:03d}_{AREA.TAG.replace('_slc', '')}.tif"
    with rasterio.open(p) as s:
        assert abs(s.transform.a - tf.a) < 1e-9, "sim and stack must share the 5 m lattice"
        dc, dr = (tf.c - s.transform.c) / 5.0, (s.transform.f - tf.f) / 5.0
        assert abs(dc - round(dc)) < 1e-6 and abs(dr - round(dr)) < 1e-6, "sim and stack are on different lattices"
        dc, dr = int(round(dc)), int(round(dr))
        full = s.read()
    # sim cell (r, c) sits at stack cell (r - dr, c - dc)
    out = np.full((3,) + tuple(shape), np.nan, np.float32)
    r0, c0 = max(dr, 0), max(dc, 0)
    h = min(full.shape[1] - r0, shape[0] - max(-dr, 0))
    w = min(full.shape[2] - c0, shape[1] - max(-dc, 0))
    out[:, max(-dr, 0):max(-dr, 0) + h, max(-dc, 0):max(-dc, 0) + w] = full[:, r0:r0 + h, c0:c0 + w]
    db, sh, lo = out
    af = 10 ** (db / 10)
    ok = np.isfinite(af) & (af > 0.05) & (sh <= MASK_FRAC) & (lo <= MASK_FRAC)
    return af, ok


def screen(A, ok):
    """SBT mask, D_A and brightness-over-median for amplitude cube A (date, y, x) on valid pixels ok."""
    A = np.where(ok, A, np.nan)
    mA = np.nanmean(A, 0)
    da = np.nanstd(A, 0) / mA
    mdb = 10 * np.log10(np.nanmean(A ** 2, 0))
    k = int(BG_M / 5) | 1
    bg = median_filter(np.where(ok, mdb, np.nanmedian(mdb)), size=k)
    bright = mdb - bg
    return ok & (da < DA_MAX) & (bright >= BRIGHT_DB), bright


def main():
    idx, stack, tf, shape = ifg.load_complex()
    res, sbt_all, br_all, ok_all = [], {}, {}, {}
    for t, g in idx.groupby("track"):
        t = int(t)
        A = np.stack([np.abs(stack[f][0]) for f in g.file]).astype(np.float32)
        valid = np.all(np.isfinite(A) & (A > 0), axis=0)
        af, sok = sim_layers(t, tf, shape)
        ok = valid & sok
        # per-date scene gain: the median amplitude of the valid pixels of that date
        gain = np.array([np.median(a[ok]) for a in A])
        Ag = A / gain[:, None, None]
        Af = A / np.sqrt(af)[None]
        Agf = Ag / np.sqrt(af)[None]
        row = dict(track=t, dates=len(g), valid_px=int(ok.sum()),
                   gain_range_db=round(float(20 * np.log10(gain.max() / gain.min())), 2))
        for name, cube in (("raw", A), ("gain", Ag), ("flat", Af), ("both", Agf)):
            sbt, bright = screen(cube, ok)
            row[f"sbt_{name}"] = int(sbt.sum())
            sbt_all[(t, name)], br_all[(t, name)] = sbt, bright
        ok_all[t] = ok
        res.append(row)
        print(row)

    near = int(np.ceil(R_M / 5))
    yy, xx = np.mgrid[-near:near + 1, -near:near + 1]
    fp = (xx ** 2 + yy ** 2) * 25 <= R_M ** 2
    agree = []
    for a, b in combinations(sorted(ok_all), 2):
        both = ok_all[a] & ok_all[b]
        for name in ("raw", "gain", "flat", "both"):
            ba, bb = br_all[(a, name)], br_all[(b, name)]
            m = both & np.isfinite(ba) & np.isfinite(bb)
            r = float(np.corrcoef(ba[m], bb[m])[0, 1])
            sa, sb = sbt_all[(a, name)] & both, sbt_all[(b, name)] & both
            nb = maximum_filter(sb.astype(np.uint8), footprint=fp).astype(bool)
            share = float(nb[sa].mean()) if sa.any() else float("nan")
            # chance level: the same share for track b's mask shifted far away
            sh = np.roll(sb, 400, axis=1)
            chance = float(maximum_filter(sh.astype(np.uint8), footprint=fp).astype(bool)[sa].mean()) if sa.any() else float("nan")
            agree.append(dict(track_a=a, track_b=b, variant=name, brightness_corr=round(r, 3),
                              sbt_a_with_sbt_b_within_15m=round(share, 3), chance_share=round(chance, 3),
                              n_sbt_a=int(sa.sum())))
    df = pd.DataFrame(agree)
    print(df.to_string())
    stem = f"nisar_flatten_gain_test"
    pd.DataFrame(res).to_csv(OUT / f"{stem}_counts_{AREA.TAG}.csv", index=False)
    df.to_csv(OUT / f"{stem}_track_agreement_{AREA.TAG}.csv", index=False)
    json.dump(dict(params=dict(da_max=DA_MAX, bright_db=BRIGHT_DB, bg_m=BG_M, mask_frac=MASK_FRAC),
                   counts=res, agreement=agree), open(OUT / f"{stem}_summary_{AREA.TAG}.json", "w"), indent=2)
    print("wrote", OUT / f"{stem}_*_{AREA.TAG}.csv")


if __name__ == "__main__":
    main()
