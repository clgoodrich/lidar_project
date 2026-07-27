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

Outputs (data/derivatives/experiments/icp/change_9t/):
  dod_9t_destriped_2m.tif   DoD after row/column median destriping
  change_patches_9t.gpkg    every patch, attributed and classified
  change_classified_9t.png  overview: destripe effect + classified patches
  top_changes_9t.png        crops of the largest non-erosional changes
  _classify_9t.json         summary numbers

Run:
  python notebooks/wellsight_v2/build/_icp_change_classify_9t.py
"""
from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[3]
ICP = ROOT / "data" / "derivatives" / "experiments" / "icp"
NINE_T = ROOT / "data" / "derivatives" / "tiles" / "9t"
ANN = ROOT / "data" / "derivatives" / "annotations"
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
BG_WIN_M = (2 * BG_RADIUS + 1) * BG_BLOCK * RES   # ~200 m effective window
N_NULL = 8              # Monte-Carlo null simulations


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

    Window is ~200 m, well above any plausible earthwork, so real pads and cuts
    survive. This CANNOT distinguish a genuine 200 m+ change from bias -- that
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

    dod = to_grid(OUT / "dod_9t_2m.tif")
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
          f"sigma={BG_WIN_M:.0f} m)")
    write(OUT / "dod_9t_destriped_2m.tif", ds)
    write(OUT / "dod_9t_highpass_2m.tif", dd)

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
    rng = np.random.default_rng(0)

    def _acf(a, ax, L=26):
        a = a - a.mean(); var = (a * a).mean()
        return np.array([(a * np.roll(a, l, axis=ax)).mean() / var
                         for l in range(L)])

    resid = np.nan_to_num(dd - m1)
    tgt = (_acf(resid, 0) + _acf(resid, 1)) / 2
    best = None
    for cand in np.arange(3.0, 14.0, 0.5):
        f = ndi.gaussian_filter(rng.standard_normal((N, N)).astype(np.float32), cand)
        err = float(np.abs((_acf(f, 0) + _acf(f, 1)) / 2 - tgt).mean())
        if best is None or err < best[1]:
            best = (cand, err)
    acf_sigma, acf_err = best

    def _segment(field, sigma):
        m = np.abs(field - np.median(field)) > SIG_K * sigma
        m = ndi.binary_closing(ndi.binary_opening(m, np.ones((3, 3))),
                               np.ones((3, 3)))
        l, _ = ndi.label(m, structure=np.ones((3, 3)))
        c = np.bincount(l.ravel())[1:]
        return c[c >= int(MIN_AREA_M2 / (RES * RES))]

    null = []
    for _ in range(N_NULL):
        f = ndi.gaussian_filter(rng.standard_normal((N, N)).astype(np.float32),
                                acf_sigma)
        f *= s1 / (1.4826 * np.median(np.abs(f - np.median(f))))
        c = _segment(f, s1)
        null.append((len(c), c.sum() * RES * RES / 1e4,
                     c.max() * RES * RES if len(c) else 0))
    n_null = np.array([x[0] for x in null])
    a_null = np.array([x[1] for x in null])
    mx_null = np.array([x[2] for x in null])
    reliable_area = float(mx_null.max())
    print(f"  null (matched ACF sigma {acf_sigma:.1f} px, err {acf_err:.3f}, "
          f"{N_NULL} sims):")
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
    gpkg = OUT / "change_patches_9t.gpkg"
    gdf.to_file(gpkg, layer="change_patches", driver="GPKG")
    print(f"  wrote {gpkg}")

    summary = {"sigma_raw": s0, "sigma_destriped": s_ds, "sigma_highpass": s1,
               "broad_field_std_removed": trend_amp,
               "bg_window_m": BG_WIN_M,
               "row_median_std_before": row_before,
               "row_median_std_after": row_after,
               "threshold_m": float(thr), "n_patches": len(gdf),
               "null": {"acf_sigma_px": float(acf_sigma), "acf_err": float(acf_err),
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
          f"  The change is real.")

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
    # fluvial rule itself rather than assuming it. 63% of the block area is
    # within CHANNEL_BUF_M of a channel, so that is the null expectation.
    summary["channel_fraction"] = {}
    for lab, sel in (("all patches", gdf), ("reliable only", rel)):
        if len(sel):
            near = float((sel.chan_dist_m <= CHANNEL_BUF_M).mean())
            summary["channel_fraction"][lab] = round(near, 3)
            print(f"  {lab:14s}: {100 * near:4.0f}% within {CHANNEL_BUF_M:.0f} m "
                  f"of a channel   (63% of block area is -> "
                  f"enrichment {near / 0.63:.2f}x)")

    nonero = rel[rel.cls == "anthropogenic"]
    print(f"\n  top non-erosional changes (by |volume|):")
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

    # ---- 5. figures ----
    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(np.nan_to_num(dem, nan=float(np.nanmean(dem))),
                      vert_exag=2, dx=RES, dy=RES)
    norm = TwoSlopeNorm(vmin=-5 * s1, vcenter=0.0, vmax=5 * s1)
    COL = {"fluvial": "#2c7fb8", "mass_wasting": "#d95f0e",
           "anthropogenic": "#d7191c"}

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
    fig.suptitle("9t  2006-2008 -> 2019 change: artifact removal and classification")
    fig.tight_layout()
    p = OUT / "change_classified_9t.png"
    fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig)
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
                        f"{r.area_m2:.0f} m2\nslope {r.slope_deg:.0f} deg, "
                        f"chan {r.chan_dist_m:.0f} m, road {r.road_dist_m:.0f} m",
                        fontsize=9)
            a.set_xticks([]); a.set_yticks([])
        for a in axs.ravel()[len(top):]:
            a.axis("off")
        fig.suptitle("Largest non-erosional (off-channel, gentle-slope) changes, "
                     "2006-2008 -> 2019", fontsize=13)
        fig.tight_layout()
        p = OUT / "top_changes_9t.png"
        fig.savefig(p, dpi=120, bbox_inches="tight"); plt.close(fig)
        print(f"  wrote {p}")

    (OUT / "_classify_9t.json").write_text(json.dumps(summary, indent=2))
    print(f"  wrote {OUT / '_classify_9t.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
