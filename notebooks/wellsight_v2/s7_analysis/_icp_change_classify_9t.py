"""Destripe the 9t DoD, segment significant change, and separate erosional
(natural, water-driven) change from everything else.

Motivation: the raw 2006-2008 -> 2019 DoD over 9t is usable (median +0.003 m,
robust sigma 0.136 m, registration QC clean -- see docs/iterations/icp_change_9t.md)
but its noise floor is set by along-track swath striping in the older survey
(+/-0.22 m). Removing that first buys real detections.

Classification is rule-based and deliberately transparent -- no model, no
training data. The core discriminator is WHERE WATER GOES. Erosion and
deposition concentrate in channels; a large change patch sitting on a hillslope
with no upslope contributing area is not fluvial.

Classes:
  fluvial       on/near a channel, or high contributing area -- natural
  mass_wasting  steep ground, cut upslope of fill -- natural (landslide/slump)
  anthropogenic off-channel, gentle slope -- grading, pads, cuts, fills
  ambiguous     fails to satisfy any rule cleanly

Outputs (data/_experiments/icp/change_9t/, <tag> = 9t_singleicp by default):
  dod_<tag>_destriped_2m.tif                  DoD after row/column median destripe
  dod_<tag>_highpass_2m.tif                   + 400 m background removed
  change_class_<tag>_2m.tif                   every patch, 1 fluvial 2 mass wasting 3 non-erosional
  change_class_reliable_<tag>_2m.tif          only patches above the IAAFT null cutoff
  dod_<tag>_nonerosional_{allpatches,reliable}_2m.tif
  change_patches_<tag>.gpkg                   every patch, attributed and classified
  change_classified_<tag>.png                 overview: destripe effect + classes
  top_changes_<tag>.png                       crops of the largest non-erosional patches
  _classify_<tag>.json                        summary numbers

Run:
  python notebooks/wellsight_v2/s7_analysis/_icp_change_classify_9t.py [--source singleicp|original]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import geopandas as gpd
from matplotlib.colors import LightSource, TwoSlopeNorm
from rasterio.features import rasterize, shapes
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from scipy import ndimage as ndi
from shapely.geometry import shape

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
ICP = path_for("experiments") / "icp"
NINE_T = path_for("nine_t")
ANN = path_for("truth")
OUT = ICP / "change_9t"

BBOX = (619500.0, 4593000.0, 624000.0, 4597500.0)
RES = 2.0
N = 2250
TF = from_origin(BBOX[0], BBOX[3], RES, RES)
CRS = "EPSG:6346"

MIN_AREA_M2 = 200.0     # below this a patch is not worth interpreting
SIG_K = 3.0             # detection threshold in robust sigma
SEED_T = 5000           # stream_seed_t<T> raster to use as the channel network
CHANNEL_LOGA = 4.0      # log10(contributing cells) that also counts as channel
CHANNEL_BUF_M = 40.0    # fluvial influence distance from a channel
STEEP_DEG = 18.0        # above this, mass wasting is plausible
ROAD_BUF_M = 30.0       # "road-adjacent" distance
BG_BLOCK = 8            # background estimate: block-median downsample factor
BG_RADIUS = 12          # ... then median filter radius, in coarse cells
BG_WIN_M = (2 * BG_RADIUS + 1) * BG_BLOCK * RES   # 400 m effective window
N_NULL = 32             # Monte-Carlo null simulations (was 8 before 2026-09-23)
N_PLACE = 200           # random placements per patch in the channel-test null
IAAFT_ITERS = 12        # spectrum/histogram alternations per surrogate

# Which DoD to classify -> (input filename, output tag).
# 'singleicp' is the 2026-07-31 rebuild (one ICP solve across all four
# 2006-2008 tiles); 'original' is the superseded 2026-05-21 product whose four
# independent solves left 0.103 m of per-tile stepping. Outputs are tagged so
# the two runs never overwrite each other.
SOURCES = {
    "original":  ("dod_9t_2m.tif", "9t"),
    "singleicp": ("dod_9t_singleicp_2m.tif", "9t_singleicp"),
}
SRC_DOD, TAG = SOURCES["singleicp"]


def robust(v):
    med = float(np.median(v))
    return med, 1.4826 * float(np.median(np.abs(v - med)))


def to_grid(path, resamp=Resampling.bilinear):
    dst = np.full((N, N), np.nan, np.float32)
    with rasterio.open(path) as s:
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform,
                  src_crs=s.crs, dst_transform=TF, dst_crs=CRS,
                  resampling=resamp, src_nodata=s.nodata, dst_nodata=np.nan)
    return dst


def write(path, arr):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0],
                       width=arr.shape[1], count=1, dtype="float32", crs=CRS,
                       transform=TF, nodata=np.nan, compress="deflate",
                       predictor=2, tiled=True) as d:
        d.write(arr.astype(np.float32), 1)
    print(f"  wrote {path}")


def savefig_safe(fig, path, **kw):
    """Save to a temp name, then swap it in. On Windows a viewer, indexer or
    scanner can briefly hold the target, and a direct overwrite then fails with
    OSError 22 (seen 2026-09-23). The temp file is never contended."""
    import os, time
    tmp = path.with_name(path.stem + "_tmp_writing" + path.suffix)
    fig.savefig(tmp, **kw)
    for attempt in range(10):
        try:
            os.replace(tmp, path)
            return
        except OSError:
            time.sleep(1.0 + attempt)
    raise OSError(f"could not replace {path}; new figure left at {tmp}")


def destripe(d, n_iter=3):
    """Remove per-row and per-column MEDIAN offsets.

    Medians, not means: real change patches are a small fraction of any row or
    column, so the median tracks the swath bias while ignoring them. A mean
    would let a big fill patch drag the whole row's correction.
    """
    out = d.copy()
    for _ in range(n_iter):
        r = np.nanmedian(out, axis=1)
        out -= np.nan_to_num(r)[:, None]
        c = np.nanmedian(out, axis=0)
        out -= np.nan_to_num(c)[None, :]
    return out.astype(np.float32)


def highpass(d, block=BG_BLOCK, radius=BG_RADIUS):
    """Remove the local background level, keeping only compact change.

    Row/column destriping removes 1D structure only. What survives it here is a
    2D bias field with TWO components: smooth blobs (per-swath vertical error)
    and sharp-edged rectangular blocks (per-tile bias in the 2006-2008 mosaic).
    A Gaussian high-pass handles the blobs but cannot remove a step edge -- it
    just blurs it into a halo.

    So the background is estimated with a large MEDIAN filter, which is
    edge-preserving: it tracks the step instead of smearing it, and subtracting
    it removes the block. Implemented as block-median downsample -> median
    filter -> bilinear upsample, which is orders of magnitude faster than a
    direct large-window median and equivalent for a slowly-varying field.

    Window is 400 m, well above any plausible earthwork, so real pads and cuts
    survive. This CANNOT distinguish a genuine 400 m+ change from bias -- that
    is an accepted cost, documented in the write-up.
    """
    m = np.isfinite(d)
    H, W = d.shape
    hb, wb = H // block, W // block
    v = np.where(m, d, np.nan)[:hb * block, :wb * block]
    coarse = np.nanmedian(v.reshape(hb, block, wb, block), axis=(1, 3))
    coarse = np.nan_to_num(coarse, nan=float(np.nanmedian(coarse)))
    sm = ndi.median_filter(coarse, size=2 * radius + 1, mode="nearest")
    bg = ndi.zoom(sm, (H / hb, W / wb), order=1)[:H, :W]
    return np.where(m, d - bg, np.nan).astype(np.float32)


def main() -> int:
    print("== 9t change classification ==")

    dod = to_grid(OUT / SRC_DOD)
    print(f"  source DoD: {SRC_DOD}   output tag: {TAG}")
    ok = np.isfinite(dod)
    m0, s0 = robust(dod[ok])

    # ---- 1. destripe, then remove the broad bias field ----
    ds = destripe(dod)
    _, s_ds = robust(ds[ok])
    row_before = float(np.nanstd(np.nanmedian(dod, axis=1)))
    row_after = float(np.nanstd(np.nanmedian(ds, axis=1)))
    print(f"  destripe:  sigma {s0:.4f} -> {s_ds:.4f} m   "
          f"row-median std {row_before:.4f} -> {row_after:.4f} m")

    dd = highpass(ds)
    m1, s1 = robust(dd[ok])
    trend_amp = float(np.nanstd(ds - dd))
    print(f"  high-pass: sigma {s_ds:.4f} -> {s1:.4f} m   "
          f"(removed broad field of std {trend_amp:.4f} m, "
          f"window {BG_WIN_M:.0f} m)")
    write(OUT / f"dod_{TAG}_destriped_2m.tif", ds)
    write(OUT / f"dod_{TAG}_highpass_2m.tif", dd)

    # ---- 2. context rasters ----
    dem = to_grid(NINE_T / "dem_breached_9t_1m.tif")
    gy, gx = np.gradient(dem, RES)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)

    # Channels are 1-2 px wide at 1 m. Bilinear resampling to the 2 m grid
    # averages their maxima away (observed: range 7.14 -> 4.64, so a fixed
    # threshold caught almost nothing). Use MAX resampling for both the flow
    # accumulation and the stream-seed mask so thin channels survive.
    loga = to_grid(NINE_T / "flow_accum_log_9t_1m.tif", Resampling.max)
    seed = to_grid(NINE_T / f"stream_seed_t{SEED_T}_9t_1m.tif", Resampling.max)
    print(f"  flow_accum_log range {np.nanmin(loga):.2f}..{np.nanmax(loga):.2f}")

    # Channel = the purpose-built stream seed OR high contributing area.
    channel = (np.nan_to_num(seed) > 0.5) | (np.isfinite(loga) & (loga >= CHANNEL_LOGA))
    chan_dist = ndi.distance_transform_edt(~channel, sampling=RES).astype(np.float32)
    print(f"  channel pixels (log a >= {CHANNEL_LOGA}): {channel.sum()} "
          f"({100 * channel.mean():.2f}%)")

    roads = gpd.read_file(ANN / "roads.shp").set_crs(4326, allow_override=True).to_crs(CRS)
    rmask = rasterize(((g, 1) for g in roads.geometry if g is not None),
                      out_shape=(N, N), transform=TF, fill=0, dtype="uint8") > 0
    road_dist = ndi.distance_transform_edt(~rmask, sampling=RES).astype(np.float32)

    wells = gpd.read_file(ANN / "well_head_pts_reprojected.gpkg").to_crs(CRS)
    wmask = rasterize(((g, 1) for g in wells.geometry if g is not None),
                      out_shape=(N, N), transform=TF, fill=0, dtype="uint8") > 0
    well_dist = ndi.distance_transform_edt(~wmask, sampling=RES).astype(np.float32)

    # ---- 2b. Monte-Carlo null: how much of this survives from noise alone? ----
    # The DoD residual is spatially CORRELATED (integral range ~16-20 px, i.e. one
    # independent sample per ~1300 m2), so thresholding it produces sizeable blobs
    # even with no real change at all. Comparing against a synthetic field with a
    # matched autocorrelation is the only way to know what the patch counts mean.
    #
    # Until 2026-09-23 the null was a Gaussian-smoothed white field whose
    # smoothing sigma was grid-searched over 3.0..13.5 px to match the ACF. That
    # was wrong twice over. The measured ACF is not Gaussian: it drops 1.0 ->
    # 0.58 at lag 1 (a nugget) and still holds 0.18 at lag 8 (a long tail), so
    # no single sigma fits it. And the search floor was 3.0 px, where the fit
    # was pinned -- the unconstrained best was 1.75 px, at which the null makes
    # NO patches at all. The reliability cutoff was therefore set by the grid
    # floor, not the data.
    #
    # Fix: IAAFT surrogates (iterative amplitude-adjusted Fourier transform,
    # Schreiber & Schmitz 1996). Each surrogate keeps BOTH the residual's own
    # Fourier amplitude spectrum (so its ACF, by Wiener-Khinchin) AND its exact
    # value distribution, and scrambles everything else.
    #
    # A plain phase-randomised surrogate is not enough. It keeps the ACF but
    # makes the values Gaussian, and a Gaussian field with this ACF produced
    # ZERO patches >= 200 m2 in 32 runs. That only rules out Gaussian noise.
    # The artifacts that matter here -- dipoles across terrain edges, ground
    # classification differences -- are heavy-tailed, and the tails are what
    # clear a 3-sigma threshold. IAAFT keeps the tails.
    #
    # Both the spectrum and the histogram still contain the real change, so
    # the null is conservative: it asks whether the extreme values are more
    # spatially clustered than their own ACF and distribution imply.
    rng = np.random.default_rng(0)

    def _acf(a, ax, L=9):
        a = a - a.mean(); var = (a * a).mean()
        return np.array([(a * np.roll(a, l, axis=ax)).mean() / var
                         for l in range(L)])

    resid = np.nan_to_num(dd - m1)
    acf_obs = (_acf(resid, 0) + _acf(resid, 1)) / 2
    amp = np.abs(np.fft.rfft2(resid))

    sorted_vals = np.sort(resid.ravel())

    def _surrogate(n_iter=IAAFT_ITERS):
        # start from a random shuffle of the real values
        x = rng.permutation(resid.ravel()).reshape(N, N)
        for _ in range(n_iter):
            X = np.fft.rfft2(x)                       # impose the spectrum
            x = np.fft.irfft2(amp * X / np.maximum(np.abs(X), 1e-12), s=(N, N))
            r = np.empty(N * N, np.int64)             # impose the histogram
            r[np.argsort(x, axis=None)] = np.arange(N * N)
            x = sorted_vals[r].reshape(N, N)
        return x.astype(np.float32)

    def _segment(field, sigma):
        m = np.abs(field - np.median(field)) > SIG_K * sigma
        m = ndi.binary_closing(ndi.binary_opening(m, np.ones((3, 3))),
                               np.ones((3, 3)))
        l, _ = ndi.label(m, structure=np.ones((3, 3)))
        c = np.bincount(l.ravel())[1:]
        return c[c >= int(MIN_AREA_M2 / (RES * RES))]

    null = []
    for _ in range(N_NULL):
        f = _surrogate()   # IAAFT keeps the real values; no rescale
        c = _segment(f, s1)
        null.append((len(c), c.sum() * RES * RES / 1e4,
                     c.max() * RES * RES if len(c) else 0))
    n_null = np.array([x[0] for x in null])
    a_null = np.array([x[1] for x in null])
    mx_null = np.array([x[2] for x in null])
    # Cutoff = the largest patch noise produced in ANY of the N_NULL fields, so
    # roughly a 1-in-(N_NULL+1) chance that noise alone yields one patch this
    # big somewhere in the 20 km2 block.
    reliable_area = float(mx_null.max())
    acf_sur = (_acf(f, 0) + _acf(f, 1)) / 2
    acf_err = float(np.abs(acf_sur - acf_obs).mean())
    print(f"  null (IAAFT surrogate, ACF err {acf_err:.4f} over lags "
          f"0-8, {N_NULL} sims):")
    print(f"    noise alone -> {n_null.mean():.0f}+/-{n_null.std():.0f} patches, "
          f"{a_null.mean():.2f} ha, largest {mx_null.mean():.0f} m2 "
          f"(max {reliable_area:.0f})")
    print(f"    => a patch is 'reliable' only above {reliable_area:.0f} m2")

    # ---- 3. segment significant change ----
    thr = SIG_K * s1
    sig = ok & (np.abs(dd - m1) > thr)
    sig = ndi.binary_opening(sig, np.ones((3, 3)))      # drop salt-and-pepper
    sig = ndi.binary_closing(sig, np.ones((3, 3)))
    lbl, nlab = ndi.label(sig, structure=np.ones((3, 3)))
    print(f"  threshold {thr:.3f} m -> {sig.sum()} px in {nlab} raw components")

    px_area = RES * RES
    min_px = int(MIN_AREA_M2 / px_area)
    keep = np.array([0] + [1 if c >= min_px else 0
                           for c in np.bincount(lbl.ravel())[1:]])
    lbl = np.where(keep[lbl] > 0, lbl, 0)
    ids = [i for i in np.unique(lbl) if i > 0]
    print(f"  {len(ids)} patches >= {MIN_AREA_M2:.0f} m2")

    # ---- 4. attribute + classify ----
    recs, geoms = [], []
    objs = ndi.find_objects(lbl)
    for i in ids:
        sl = objs[i - 1]
        m = lbl[sl] == i
        dv = dd[sl][m]
        area = float(m.sum() * px_area)
        mean_dz = float(dv.mean())
        volume = float(dv.sum() * px_area)          # net m3, + = gain
        sl_m = float(np.nanmean(slope[sl][m]))
        cd = float(np.nanmin(chan_dist[sl][m]))
        la = float(np.nanmax(loga[sl][m]))
        rd = float(np.nanmin(road_dist[sl][m]))
        wd = float(np.nanmin(well_dist[sl][m]))

        # shape: compactness 4*pi*A/P^2 (1 = circle, low = elongated/ragged)
        per = float((ndi.binary_dilation(m) & ~m).sum() * RES)
        comp = float(4 * np.pi * area / per ** 2) if per > 0 else 0.0

        # --- rules ---
        fluvial = (cd <= CHANNEL_BUF_M) or (la >= CHANNEL_LOGA)
        steep = sl_m >= STEEP_DEG
        if fluvial:
            cls = "fluvial"
            why = f"channel {cd:.0f} m / log a {la:.1f}"
        elif steep:
            cls = "mass_wasting"
            why = f"off-channel but {sl_m:.0f} deg slope"
        else:
            cls = "anthropogenic"
            why = (f"off-channel ({cd:.0f} m), gentle ({sl_m:.0f} deg)"
                   + (f", road {rd:.0f} m" if rd <= ROAD_BUF_M else ""))

        recs.append(dict(
            patch_id=int(i), area_m2=round(area, 1), mean_dz_m=round(mean_dz, 3),
            volume_m3=round(volume, 1), abs_volume_m3=round(abs(volume), 1),
            sign="fill" if mean_dz > 0 else "cut",
            slope_deg=round(sl_m, 1), chan_dist_m=round(cd, 1),
            log_flowacc=round(la, 2), road_dist_m=round(rd, 1),
            well_dist_m=round(wd, 1), compactness=round(comp, 3),
            road_adjacent=bool(rd <= ROAD_BUF_M), cls=cls, reason=why,
            reliable=bool(area >= reliable_area),
        ))
        sub = np.zeros_like(lbl, bool); sub[sl] = m
        geoms.append(shape(next(g for g, v in shapes(
            sub.astype("uint8"), mask=sub, transform=TF) if v == 1)))

    gdf = gpd.GeoDataFrame(recs, geometry=geoms, crs=CRS)
    gdf = gdf.sort_values("abs_volume_m3", ascending=False).reset_index(drop=True)
    gpkg = OUT / f"change_patches_{TAG}.gpkg"
    gdf.to_file(gpkg, layer="change_patches", driver="GPKG")
    print(f"  wrote {gpkg}")

    summary = {"sigma_raw": s0, "sigma_destriped": s_ds, "sigma_highpass": s1,
               "broad_field_std_removed": trend_amp,
               "bg_window_m": BG_WIN_M,
               "row_median_std_before": row_before,
               "row_median_std_after": row_after,
               "threshold_m": float(thr), "n_patches": len(gdf),
               "null": {"method": "iaaft_surrogate", "iaaft_iters": IAAFT_ITERS,
                        "acf_observed_lags0to8": [round(float(v), 4) for v in acf_obs],
                        "acf_err": acf_err,
                        "n_sims": N_NULL,
                        "patches_mean": float(n_null.mean()),
                        "patches_std": float(n_null.std()),
                        "area_ha_mean": float(a_null.mean()),
                        "largest_m2_mean": float(mx_null.mean()),
                        "largest_m2_max": reliable_area},
               "observed_over_null": {
                   "patches": None, "area": None},
               "reliable_area_m2": reliable_area,
               "min_area_m2": MIN_AREA_M2,
               "params": dict(channel_loga=CHANNEL_LOGA,
                              channel_buf_m=CHANNEL_BUF_M,
                              steep_deg=STEEP_DEG, road_buf_m=ROAD_BUF_M),
               "by_class": {}}
    summary["observed_over_null"] = {
        "patches": round(len(gdf) / max(n_null.mean(), 1e-9), 2),
        "area": round((gdf.area_m2.sum() / 1e4) / max(a_null.mean(), 1e-9), 2)}
    print(f"\n  OBSERVED {len(gdf)} patches / {gdf.area_m2.sum() / 1e4:.2f} ha "
          f"vs NULL {n_null.mean():.0f} / {a_null.mean():.2f} ha  ->  "
          f"{len(gdf) / n_null.mean():.1f}x patches, "
          f"{(gdf.area_m2.sum() / 1e4) / a_null.mean():.1f}x area."
          f"  In aggregate the change exceeds the null; see the reliable "
          f"flag for individual patches.")

    rel = gdf[gdf.reliable]
    print(f"\n  class           all  reliable   area (ha)   |vol| (m3)")
    for c in ("fluvial", "mass_wasting", "anthropogenic"):
        g = gdf[gdf.cls == c]; gr = rel[rel.cls == c]
        summary["by_class"][c] = dict(n=int(len(g)), n_reliable=int(len(gr)),
                                      area_ha=round(gr.area_m2.sum() / 1e4, 2),
                                      abs_vol_m3=round(gr.abs_volume_m3.sum(), 1))
        print(f"  {c:14s} {len(g):4d}      {len(gr):4d}   "
              f"{gr.area_m2.sum() / 1e4:8.2f}   {gr.abs_volume_m3.sum():10.0f}")

    # Does REAL change actually concentrate near channels? This tests the
    # fluvial rule itself rather than assuming it.
    #
    # The null must be a PATCH, not a point. A patch counts as near a channel
    # if ANY of its pixels is within CHANNEL_BUF_M, and a 3,000 m2 patch
    # reaches much further than a pixel. Before 2026-09-23 the null was the
    # block-area fraction within the buffer (a point null), which overstated
    # enrichment. Now each patch's own footprint is dropped at N_PLACE random
    # positions and the hit rate is averaged.
    point_null = float((chan_dist <= CHANNEL_BUF_M).mean())
    objs_l = ndi.find_objects(lbl)
    shape_null = {}
    for pid in gdf.patch_id:
        sl = objs_l[pid - 1]
        rr, cc = np.nonzero(lbl[sl] == pid)
        r0 = rng.integers(0, N - rr.max(), N_PLACE)
        c0 = rng.integers(0, N - cc.max(), N_PLACE)
        hits = chan_dist[rr[None, :] + r0[:, None],
                         cc[None, :] + c0[:, None]].min(axis=1) <= CHANNEL_BUF_M
        shape_null[pid] = float(hits.mean())
    gdf["chan_null_p"] = gdf.patch_id.map(shape_null)
    summary["channel_fraction"] = {"point_null": round(point_null, 3)}
    for lab, sel in (("all patches", gdf), ("reliable only", gdf[gdf.reliable])):
        if len(sel):
            near = float((sel.chan_dist_m <= CHANNEL_BUF_M).mean())
            exp = float(sel.chan_null_p.mean())
            z = (near - exp) / np.sqrt(
                (sel.chan_null_p * (1 - sel.chan_null_p)).sum()) * len(sel)
            summary["channel_fraction"][lab] = dict(
                observed=round(near, 3), shape_null=round(exp, 3),
                enrichment=round(near / exp, 3), z=round(float(z), 2))
            print(f"  {lab:14s}: {100 * near:4.0f}% within {CHANNEL_BUF_M:.0f} m "
                  f"of a channel.  Same-shape null {100 * exp:4.1f}% -> "
                  f"enrichment {near / exp:.2f}x, z = {z:.1f}   "
                  f"(point null {100 * point_null:.0f}% would say "
                  f"{near / point_null:.2f}x)")

    # ALL off-channel gentle-slope patches, not just reliable ones. Under the
    # IAAFT null none of them may be individually reliable, and an empty list
    # helps nobody triage. Each row and crop carries its reliable flag instead.
    nonero = gdf[gdf.cls == "anthropogenic"]
    print(f"\n  top non-erosional changes (by |volume|; "
          f"{int(nonero.reliable.sum())} of {len(nonero)} individually reliable):")
    for _, r in nonero.head(12).iterrows():
        cx, cy = r.geometry.centroid.x, r.geometry.centroid.y
        print(f"   #{r.patch_id:4d} {r['sign']:4s} {r.mean_dz_m:+.2f} m  "
              f"{r.area_m2:8.0f} m2  {r.abs_volume_m3:8.0f} m3  "
              f"slope {r.slope_deg:4.1f}  chan {r.chan_dist_m:5.0f} m  "
              f"road {r.road_dist_m:5.0f} m  well {r.well_dist_m:5.0f} m  "
              f"@ {cx:.0f},{cy:.0f}")
    summary["top_anthropogenic"] = [
        dict(patch_id=int(r.patch_id), sign=r["sign"], mean_dz_m=r.mean_dz_m,
             area_m2=r.area_m2, abs_volume_m3=r.abs_volume_m3,
             slope_deg=r.slope_deg, chan_dist_m=r.chan_dist_m,
             road_dist_m=r.road_dist_m, well_dist_m=r.well_dist_m,
             x=round(r.geometry.centroid.x, 1), y=round(r.geometry.centroid.y, 1))
        for _, r in nonero.head(20).iterrows()]

    # ---- 4b. rasterize the result ----
    # Categorical class raster, with a colour table baked in so QGIS renders it
    # correctly on drag-and-drop with no styling step.
    CODE = {"fluvial": 1, "mass_wasting": 2, "anthropogenic": 3}
    cls_r = np.zeros((N, N), np.uint8)
    rel_r = np.zeros((N, N), np.uint8)
    for c, code in CODE.items():
        g = gdf[gdf.cls == c]
        if len(g):
            cls_r = np.maximum(cls_r, rasterize(
                ((geom, code) for geom in g.geometry), out_shape=(N, N),
                transform=TF, fill=0, dtype="uint8"))
        gr = g[g.reliable]
        if len(gr):
            rel_r = np.maximum(rel_r, rasterize(
                ((geom, code) for geom in gr.geometry), out_shape=(N, N),
                transform=TF, fill=0, dtype="uint8"))

    cmap = {0: (0, 0, 0, 0),                 # transparent where no change
            1: (31, 95, 168, 255),           # fluvial      blue   #1F5FA8
            2: (217, 119, 6, 255),           # mass wasting amber  #D97706
            3: (163, 21, 21, 255)}           # anthropogenic dark red #A31515
    # Palette = the repo's validated lost/found set. dataviz validate_palette.js
    # --pairs all, light: worst pair #A31515/#D97706 dE 21.1 deutan, 22.6
    # normal, tritan 18.9, all >= 3:1 contrast. The previous blue/orange/red
    # FAILED (orange/red dE 10.3 normal, 6.7 deutan), 2026-09-23.
    for name, arr in ((f"change_class_{TAG}_2m.tif", cls_r),
                      (f"change_class_reliable_{TAG}_2m.tif", rel_r)):
        p = OUT / name
        with rasterio.open(p, "w", driver="GTiff", height=N, width=N, count=1,
                           dtype="uint8", crs=CRS, transform=TF, nodata=0,
                           compress="deflate", tiled=True) as d:
            d.write(arr, 1)
            d.write_colormap(1, cmap)
            d.update_tags(1, CLASS_1="fluvial", CLASS_2="mass_wasting",
                          CLASS_3="anthropogenic")
        print(f"  wrote {p}  ({int((arr > 0).sum())} px)")

    # Elevation change restricted to NON-erosional patches -- the "where is the
    # non-fluvial change, and how big" layer. Written twice, and the name says
    # which: every patch, and only those above the null's reliability cutoff.
    for which, src in (("allpatches", cls_r), ("reliable", rel_r)):
        ne = np.where(src == CODE["anthropogenic"], dd, np.nan).astype(np.float32)
        write(OUT / f"dod_{TAG}_nonerosional_{which}_2m.tif", ne)
        n_ne = int(np.isfinite(ne).sum())
        print(f"    ({n_ne} px" + (f", range {np.nanmin(ne):+.2f}.."
                                   f"{np.nanmax(ne):+.2f} m)" if n_ne else ")"))

    # ---- 5. figures ----
    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(np.nan_to_num(dem, nan=float(np.nanmean(dem))),
                      vert_exag=2, dx=RES, dy=RES)
    norm = TwoSlopeNorm(vmin=-5 * s1, vcenter=0.0, vmax=5 * s1)
    COL = {"fluvial": "#1F5FA8", "mass_wasting": "#D97706",   # validated,
           "anthropogenic": "#A31515"}                          # see cmap

    ext = (BBOX[0], BBOX[2], BBOX[1], BBOX[3])   # map coords for every panel
    fig, ax = plt.subplots(1, 4, figsize=(25, 6.6))
    ax[0].imshow(dod, cmap="RdBu_r", norm=norm, extent=ext)
    ax[0].set_title(f"raw  (sigma {s0:.3f} m)\nswath striping")
    ax[1].imshow(ds, cmap="RdBu_r", norm=norm, extent=ext)
    ax[1].set_title(f"destriped  (sigma {s_ds:.3f} m)\nbroad 2D bias remains")
    ax[2].imshow(dd, cmap="RdBu_r", norm=norm, extent=ext)
    ax[2].set_title(f"+ high-pass {BG_WIN_M:.0f} m  (sigma {s1:.3f} m)\n"
                    f"removed broad field std {trend_amp:.3f} m")
    ax[3].imshow(hs, cmap="gray", alpha=0.9, extent=ext)
    from matplotlib.patches import Patch
    for c, col in COL.items():
        g = gdf[gdf.cls == c]
        if len(g):
            g.plot(ax=ax[3], facecolor=col, edgecolor=col, linewidth=0.4,
                   alpha=0.8)
    ax[3].set_xlim(BBOX[0], BBOX[2]); ax[3].set_ylim(BBOX[1], BBOX[3])
    ax[3].set_aspect("equal")
    ax[3].legend(handles=[Patch(facecolor=COL[c], label=f"{c} (n={(gdf.cls == c).sum()})")
                          for c in COL], loc="lower left", fontsize=9,
                 framealpha=0.9)
    ax[3].set_title(f"{len(gdf)} change patches >= {MIN_AREA_M2:.0f} m2, classified")
    for a in ax:
        a.set_xticks([]); a.set_yticks([])
    fig.suptitle("9t  2006-2008 -> 2019 change: artifact removal and classification",
                 y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.94))   # leave room for the suptitle
    p = OUT / f"change_classified_{TAG}.png"
    savefig_safe(fig, p, dpi=130, bbox_inches="tight"); plt.close(fig)
    print(f"\n  wrote {p}")

    # crops of the top non-erosional patches
    top = nonero.head(9)
    if len(top):
        fig, axs = plt.subplots(3, 3, figsize=(15, 15))
        for a, (_, r) in zip(axs.ravel(), top.iterrows()):
            cx, cy = r.geometry.centroid.x, r.geometry.centroid.y
            c0 = int((cx - BBOX[0]) / RES); r0 = int((BBOX[3] - cy) / RES)
            h = max(40, int(np.sqrt(r.area_m2) / RES * 2.5))
            sl = (slice(max(0, r0 - h), min(N, r0 + h)),
                  slice(max(0, c0 - h), min(N, c0 + h)))
            a.imshow(hs[sl], cmap="gray")
            a.imshow(np.where(np.abs(dd[sl] - m1) > thr, dd[sl], np.nan),
                     cmap="RdBu_r", norm=norm, alpha=0.75)
            a.set_title(f"#{r.patch_id} {r['sign']} {r.mean_dz_m:+.2f} m  "
                        f"[{'reliable' if r.reliable else 'within noise'}]  "
                        f"{r.area_m2:.0f} m2\nslope {r.slope_deg:.0f} deg, "
                        f"chan {r.chan_dist_m:.0f} m, road {r.road_dist_m:.0f} m",
                        fontsize=9)
            a.set_xticks([]); a.set_yticks([])
        for a in axs.ravel()[len(top):]:
            a.axis("off")
        fig.suptitle("Largest non-erosional (off-channel, gentle-slope) changes, "
                     "2006-2008 -> 2019\n"
                     f"{int(top.reliable.sum())} of {len(top)} shown clear the "
                     f"IAAFT null (>= {reliable_area:.0f} m2). The rest are "
                     "unvalidated.", fontsize=13)
        fig.tight_layout()
        p = OUT / f"top_changes_{TAG}.png"
        savefig_safe(fig, p, dpi=120, bbox_inches="tight"); plt.close(fig)
        print(f"  wrote {p}")

    jp = OUT / f"_classify_{TAG}.json"
    summary["source_dod"] = SRC_DOD
    summary["tag"] = TAG
    jp.write_text(json.dumps(summary, indent=2))
    print(f"  wrote {jp}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=sorted(SOURCES), default="singleicp",
                    help="which DoD to classify (default: singleicp, the "
                         "2026-07-31 one-solve rebuild; 'original' is the "
                         "superseded 2026-05-21 four-solve mosaic)")
    SRC_DOD, TAG = SOURCES[ap.parse_args().source]
    raise SystemExit(main())
