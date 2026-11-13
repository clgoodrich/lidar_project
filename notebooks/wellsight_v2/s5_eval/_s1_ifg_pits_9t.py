"""Sentinel-1 C-band interferograms over the pits, Oct-Nov 2025: the NISAR pit test repeated at C-band.

Data. OPERA CSLC-S1 V1 bursts (geocoded complex SLC, VV, 5 m x 10 m UTM 17N, flattened), fetched by
_s1_cslc_fetch_9t.py into data/_source/s1_cslc/. Two Sentinel-1A orbits cover 9t and 613590:
track 4 (ascending) and track 77, five dates each at 12 days, 2025-10-07 to 2025-11-29.

Method. Identical to _nisar_gslc_interferogram_pits_9t.py except the radar:
  * Interferogram s1 * conj(s2) of consecutive dates on one burst (12 days).
  * Coherence and multilooked phase on the native grid with a 2 x 4 pixel boxcar (20 m x 20 m, 8 looks),
    the nearest match to the NISAR 3 x 3 at 5 m (15 m, 9 looks).
  * Coherence and the multilooked interferogram resampled (nearest) onto the area's 5 m NISAR SLC grid,
    so pits, rings and decoys are the very same pixel sets as the NISAR run (same seed).
  * Coherence excess = (pit - ring) - median(decoy - ring). Phase as LOS mm with lambda 5.547 cm.
Pits are the annotated outer rims (pit_outside). Registration as delivered by OPERA.

  python notebooks/wellsight_v2/s5_eval/_s1_ifg_pits_9t.py --slc [--area 613590]
"""
import importlib
import json
import sys
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject
from scipy.ndimage import uniform_filter
from scipy.stats import wilcoxon

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
st = importlib.import_module("_nisar_gslc_stack_pad_pit_seasonal_9t")
from _common import read_layer  # noqa: E402

A, ANN, CRS = st.A, st.ANN, st.CRS
ROOT = HERE.parents[2]
SRC = ROOT / "data" / "_source" / "s1_cslc"
AREA = A.TAG.replace("_slc", "")
OUT = ROOT / "data" / AREA / "results" / "s1"
WIN_YX = (2, 4)              # rows (10 m) x cols (5 m) = 20 m x 20 m
MIN_VALID_SHARE = 0.5
LAMBDA_M = 0.05547
MM_PER_RAD = LAMBDA_M / (4 * np.pi) * 1000
N_DECOY, SEED, B = 5, 20261005, 2000


def burst_windows(tf, shape):
    """Per burst id: date -> complex VV window covering the area grid (+200 m), and its transform."""
    x0, y1 = tf.c - 200, tf.f + 200
    x1, y0 = tf.c + shape[1] * tf.a + 200, tf.f + shape[0] * tf.e - 200
    out = {}
    for f in sorted(SRC.glob("OPERA_L2_CSLC-S1_*.h5")):
        p = f.stem.split("_")
        burst, date = p[3], f"{p[4][:4]}-{p[4][4:6]}-{p[4][6:8]}"
        with h5py.File(f, "r") as h:
            if int(h["data/projection"][()]) != 32617:
                raise SystemExit(f"unexpected projection in {f.name}")
            xs, ys = h["data/x_coordinates"][:], h["data/y_coordinates"][:]
            c = np.where((xs >= x0) & (xs <= x1))[0]
            r = np.where((ys >= y0) & (ys <= y1))[0]
            if len(c) < 50 or len(r) < 25:
                continue
            vv = h["data/VV"][r.min():r.max() + 1, c.min():c.max() + 1]
            dx, dy = float(h["data/x_spacing"][()]), float(h["data/y_spacing"][()])
            wtf = Affine(dx, 0, xs[c.min()] - dx / 2, 0, dy, ys[r.min()] - dy / 2)
            pas = h["identification/orbit_pass_direction"][()].decode()
        d = out.setdefault(burst, {"tf": wtf, "pass": pas, "dates": {}})
        if d["tf"] != wtf:
            raise SystemExit(f"grid differs between dates in burst {burst}")
        d["dates"][date] = np.where(np.isfinite(vv), vv, 0).astype(np.complex64)
    return out


def interferogram(s1, s2):
    i = s1 * np.conj(s2)
    ok = (s1 != 0) & (s2 != 0) & np.isfinite(i)
    i0 = np.where(ok, i, 0)
    share = uniform_filter(ok.astype(np.float32), WIN_YX)
    num = uniform_filter(i0.real, WIN_YX) + 1j * uniform_filter(i0.imag, WIN_YX)
    p1 = uniform_filter(np.where(ok, np.abs(s1) ** 2, 0), WIN_YX)
    p2 = uniform_filter(np.where(ok, np.abs(s2) ** 2, 0), WIN_YX)
    coh = np.abs(num) / np.sqrt(np.maximum(p1 * p2, 1e-30))
    bad = ~ok | (share < MIN_VALID_SHARE)
    coh[bad], num[bad] = np.nan, np.nan
    return coh.astype(np.float32), num.astype(np.complex64)


def to_grid(a, src_tf, tf, shape):
    dst = np.full(shape, np.nan, np.float32)
    reproject(a.astype(np.float32), dst, src_transform=src_tf, src_crs="EPSG:32617", dst_transform=tf,
              dst_crs=CRS, resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
    return dst


def boot_ci(v, rng):
    v = np.asarray(v)[np.isfinite(v)]
    if len(v) < 3:
        return (np.nan, np.nan)
    return tuple(np.percentile(np.median(rng.choice(v, (B, len(v))), axis=1), [2.5, 97.5]).round(4))


def pit_pixels(g, tf, shape):
    px = st.pixel_index(g, tf, shape)
    if len(px):
        return px
    c = g.centroid
    col, row = int((c.x - tf.c) / tf.a), int((c.y - tf.f) / tf.e)
    return np.array([row * shape[1] + col]) if 0 <= row < shape[0] and 0 <= col < shape[1] else px


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    _, _, tf, shape = st.load_stack()
    bursts = burst_windows(tf, shape)
    print({b: (d["pass"], sorted(d["dates"])) for b, d in bursts.items()})

    # pit, ring and decoy pixel sets: same construction and seed as the NISAR run
    pits = read_layer(ANN, "pit_outside").to_crs(CRS).reset_index(drop=True)
    roads = read_layer(ANN, "roads").to_crs(CRS)
    pads = read_layer(ANN, "plat").to_crs(CRS)
    cover = st.canopy_cover(tf, shape)
    in_tile = np.isfinite(cover)
    pits = pits[[in_tile.ravel()[pit_pixels(g, tf, shape)].any() if len(pit_pixels(g, tf, shape)) else False
                 for g in pits.geometry]].reset_index(drop=True)
    feat = rasterize([(g, 1) for g in pd.concat([pads.buffer(20), pits.buffer(20), roads.buffer(20)])],
                     out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
    ok_flat, bg_flat = in_tile.ravel(), (in_tile & ~feat).ravel()
    excl = pd.concat([pits.buffer(st.PIT_EXCL), roads.buffer(st.PIT_EXCL)]).union_all()
    sets = []
    for g in pits.geometry:
        core = pit_pixels(g, tf, shape)
        core = core[ok_flat[core]]
        rg = st.pixel_index(st.ring_geom(g, st.PIT_RING, excl), tf, shape)
        rg = rg[ok_flat[rg]]
        sets.append((core, rg, st.placebo_sets(g, 0, st.PIT_RING, excl, tf, shape, ok_flat, bg_flat, rng, N_DECOY)))
    pit_cover = np.array([np.nanmean(cover.ravel()[pit_pixels(g, tf, shape)]) for g in pits.geometry])

    rows = []
    for b, d in bursts.items():
        dates = sorted(d["dates"])
        for d1, d2 in zip(dates[:-1], dates[1:]):
            coh_n, ifg_n = interferogram(d["dates"][d1], d["dates"][d2])
            coh = to_grid(coh_n, d["tf"], tf, shape)
            ifg = to_grid(ifg_n.real, d["tf"], tf, shape) + 1j * to_grid(ifg_n.imag, d["tf"], tf, shape)
            cf, iff = coh.ravel(), ifg.ravel()
            tile_med = float(np.nanmedian(coh[in_tile]))
            valid = np.isfinite(cf)      # pixels inside this burst; outside ones must not enter a sum as 0
            for k, (core, rg, dec) in enumerate(sets):
                core, rg = core[valid[core]], rg[valid[rg]]
                if len(core) == 0 or len(rg) < 10:
                    continue
                dec = [(a[valid[a]], bb[valid[bb]]) for a, bb in dec]
                dec = [(a, bb) for a, bb in dec if len(a) and len(bb) >= 10]
                c_pit, c_ring = np.nanmean(cf[core]), np.nanmean(cf[rg])
                ph = np.angle(np.nansum(iff[core]) * np.conj(np.nansum(iff[rg])))
                dc = [np.nanmean(cf[a]) - np.nanmean(cf[bb]) for a, bb in dec]
                dp = [np.angle(np.nansum(iff[a]) * np.conj(np.nansum(iff[bb]))) for a, bb in dec]
                rows.append(dict(burst=b, orbit_pass=d["pass"], d1=d1, d2=d2, pit=k, pit_cover=pit_cover[k],
                                 tile_coh_median=tile_med, coh_pit=c_pit, coh_ring=c_ring,
                                 coh_pit_minus_ring=c_pit - c_ring,
                                 coh_decoy_minus_ring_median=np.nanmedian(dc) if dc else np.nan,
                                 los_pit_minus_ring_mm=-ph * MM_PER_RAD,
                                 los_decoy_minus_ring_mm_median=-np.median(dp) * MM_PER_RAD if dp else np.nan,
                                 los_decoy_abs_mm_median=np.median(np.abs(dp)) * MM_PER_RAD if dp else np.nan))
    df = pd.DataFrame(rows)
    df["coh_excess"] = df.coh_pit_minus_ring - df.coh_decoy_minus_ring_median
    df["los_excess_mm"] = df.los_pit_minus_ring_mm - df.los_decoy_minus_ring_mm_median
    df.to_csv(OUT / f"s1_ifg_pits_per_pit_{AREA}.csv", index=False)

    per_pair = []
    for (b, d1, d2), g in df.groupby(["burst", "d1", "d2"]):
        e = g.coh_excess.dropna()
        per_pair.append(dict(burst=b, orbit_pass=g.orbit_pass.iloc[0], d1=d1, d2=d2, n_pits=len(e),
                             tile_coh_median=round(g.tile_coh_median.iloc[0], 3),
                             pit_coh_median=round(g.coh_pit.median(), 3), ring_coh_median=round(g.coh_ring.median(), 3),
                             coh_excess_median=round(e.median(), 4), coh_excess_ci95=boot_ci(e, rng),
                             wilcoxon_p=round(float(wilcoxon(e).pvalue), 4) if len(e) > 10 else np.nan,
                             los_excess_mm_median=round(g.los_excess_mm.median(), 2),
                             los_decoy_abs_mm_median=round(g.los_decoy_abs_mm_median.median(), 2)))
    per_pair = pd.DataFrame(per_pair)
    per_pair.to_csv(OUT / f"s1_ifg_pits_by_pair_{AREA}.csv", index=False)
    print(per_pair.to_string())

    pooled = df.groupby("pit").agg(coh_excess=("coh_excess", "mean"), los=("los_excess_mm", "mean"))
    e = pooled.coh_excess.dropna()
    summary = {"source": "OPERA CSLC-S1 V1, VV", "window_m": "20 x 20 (2 x 4 native px)",
               "bursts": {b: {"pass": d["pass"], "dates": sorted(d["dates"])} for b, d in bursts.items()},
               "pairs": int(len(per_pair)), "pits": int(len(pits)),
               "tile_coherence_median_over_pairs": round(float(per_pair.tile_coh_median.median()), 3),
               "coh_excess_pooled_per_pit_median": round(float(e.median()), 4),
               "coh_excess_pooled_ci95": boot_ci(e, rng),
               "coh_excess_pooled_wilcoxon_p": round(float(wilcoxon(e).pvalue), 4),
               "los_excess_mm_pooled_median": round(float(pooled.los.median()), 2),
               "los_excess_mm_pooled_ci95": boot_ci(pooled.los, rng)}
    json.dump(summary, open(OUT / f"s1_ifg_pits_summary_{AREA}.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
