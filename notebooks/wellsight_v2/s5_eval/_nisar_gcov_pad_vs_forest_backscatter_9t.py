"""Does NISAR radar brightness separate annotated well pads from the forest around them?

WHY
---
NISAR gives no elevation, so it cannot find pits. The supplement proposal
(`docs/nisar_lidar_supplement_proposal.md`) argues it can still describe the
ground at pad scale. This is the first test of that claim: compare L-band
backscatter over the 995 annotated pads in 9t with the forest ring around each
one.

DATA
----
  * NISAR L2 GCOV beta, 2026-01-20, ascending, left-looking, frequency A.
    10 m grid, EPSG:32617, RTC gamma-0, HH and HV, linear power.
    data/_source/reference/nisar/9t/NISAR_L2_GCOV_BETA_V1/...h5
  * Pads: `plat` layer of qgis/annotations/annotations_proj.gpkg (EPSG:6346).
  * Roads: `roads` layer of the same file, excluded from the forest ring.
  * 2019 lidar canopy height: data/9t/derived/1m/chm_9t_1m.tif. Used to say
    whether a pad was open or grown over when the lidar was flown.

EPSG:6346 and EPSG:32617 differ by about 1 m here. Everything is reprojected
into the NISAR grid, so that 1 m is handled by the transform, not ignored.

DESIGN
------
  * **Pad core pixel:** a 10 m pixel whose centre lies at least 5 m inside the
    pad. Such a pixel sits wholly inside the pad, so it is not a pad/forest mix.
  * **Forest ring pixel:** centre 20-60 m outside the pad, and at least 10 m
    from any pad and any annotated road. The ring is the pad's own local
    comparison, so slope, aspect and incidence angle are close to the pad's.
  * **Per-pad value:** mean linear gamma-0 over the pixels, then dB. Averaging in
    linear power is the standard for backscatter.
  * **Tests:** paired pad-minus-ring difference (Wilcoxon signed-rank), and the
    AUC, meaning the chance a random pad is brighter or darker than a random
    ring in the direction of the median. 95% CIs bootstrap the pads.
  * **Positive control:** all 9t pixels with under 10% canopy in 2019 against
    those over 90%. If radar cannot separate those, it cannot separate pads.
  * **Registration check:** the canopy/backscatter correlation is recomputed with
    the lidar canopy sampled -20..+20 m (5 m steps) off each NISAR pixel. The
    shift with the highest correlation is the measured misregistration. On the
    2026-01-20 beta granule it is dx -10 m, dy -5 m: the ground at lidar
    position (x-10, y-5) lands in the NISAR pixel labelled (x, y), i.e. the
    radar image sits about 10 m east and 5 m north of the lidar.
  * **--align** re-labels the NISAR pixels by that measured shift before any pad
    or ring pixel is chosen. Pixel values are unchanged; only where they are
    said to sit moves. Both runs are kept, suffixed `_asdelivered` and
    `_aligned`. The clipped dB rasters are always written as delivered.

Run:
  python notebooks/wellsight_v2/s5_eval/_nisar_gcov_pad_vs_forest_backscatter_9t.py
  python notebooks/wellsight_v2/s5_eval/_nisar_gcov_pad_vs_forest_backscatter_9t.py --align
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from scipy.stats import mannwhitneyu, spearmanr, wilcoxon
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
from _common import path_for, read_layer  # noqa: E402

H5 = (path_for("data") / "_source" / "reference" / "nisar" / "9t" / "NISAR_L2_GCOV_BETA_V1"
      / "NISAR_L2_PR_GCOV_010_162_A_023_4005_DHDH_A_20260120T101554_20260120T101629_X05010_N_F_J_001.h5")
ANN = path_for("truth") / "annotations_proj.gpkg"
CHM = path_for("data") / "9t" / "derived" / "1m" / "chm_9t_1m.tif"
DER = path_for("data") / "9t" / "derived" / "nisar_10m"
OUT = path_for("results_9t") / "nisar"
FIG = OUT / "figures"

NISAR_CRS = "EPSG:32617"
PIX = 10.0
PAD_CORE_M = 5.0          # pixel centre this far inside the pad => pixel wholly inside
RING_IN, RING_OUT = 20.0, 60.0
EXCL_M = 10.0             # ring keeps clear of every pad and road by this much
CANOPY_H = 2.0            # m; a 1 m CHM cell above this counts as canopy
B = 2000
SEED = 20260926

# Palette: lost/found pair reused. validate_palette.py --mode light --pairs all
# "#1F5FA8,#D97706": worst pair dE 21.1 deutan, 22.6 normal, both >= 3:1 on paper.
# No red or green. Pad vs ring is also split by position (left/right) and marker.
PAD_C, RING_C = "#1F5FA8", "#D97706"
INK, MUTED = "#141A1F", "#6B7278"


def db(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(x)


def read_gcov(bounds_32617):
    """Window the 10 m HH/HV grids to the bounds. Coordinates are pixel centres."""
    with h5py.File(H5) as h:
        g = h["science/LSAR/GCOV/grids/frequencyA"]
        x = g["xCoordinates"][:]
        y = g["yCoordinates"][:]
        x0, y0, x1, y1 = bounds_32617
        ci = np.where((x >= x0) & (x <= x1))[0]
        ri = np.where((y >= y0) & (y <= y1))[0]
        sl = (slice(ri[0], ri[-1] + 1), slice(ci[0], ci[-1] + 1))
        hh = g["HHHH"][sl].astype(np.float64)
        hv = g["HVHV"][sl].astype(np.float64)
        mask = g["mask"][sl]
        looks = g["numberOfLooks"][sl]
    tf = from_origin(x[ci[0]] - PIX / 2, y[ri[0]] + PIX / 2, PIX, PIX)
    valid = np.isfinite(hh) & np.isfinite(hv) & (hh > 0) & (hv > 0) & (mask != 255)
    return hh, hv, valid, looks, tf


def canopy_cover(tf, shape, shift=(0.0, 0.0)):
    """Fraction of 1 m CHM cells > CANOPY_H in each 10 m NISAR pixel (2019)."""
    with rasterio.open(CHM) as r:
        chm = r.read(1, masked=True)
        src = np.where(chm.mask, np.nan, (chm.filled(0) > CANOPY_H).astype(np.float32))
        dst = np.full(shape, np.nan, np.float32)
        t = rasterio.Affine(tf.a, tf.b, tf.c + shift[0], tf.d, tf.e, tf.f + shift[1])
        reproject(src, dst, src_transform=r.transform, src_crs=r.crs, src_nodata=np.nan,
                  dst_transform=t, dst_crs=NISAR_CRS, dst_nodata=np.nan,
                  resampling=Resampling.average)
    return dst


def pixel_centres(tf, shape):
    rows, cols = np.indices(shape)
    xs = tf.c + (cols + 0.5) * tf.a
    ys = tf.f + (rows + 0.5) * tf.e
    return xs, ys


def auc(a, b):
    """P(a > b) + 0.5 P(tie), from the Mann-Whitney U."""
    if len(a) == 0 or len(b) == 0:
        return np.nan
    return mannwhitneyu(a, b).statistic / (len(a) * len(b))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--align", action="store_true",
                    help="shift NISAR georeference by the measured misregistration")
    align = ap.parse_args().align
    tag = "aligned" if align else "asdelivered"
    DER.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    with rasterio.open(CHM) as r:
        tile = gpd.GeoSeries([box(*r.bounds)], crs=r.crs).to_crs(NISAR_CRS)
    x0, y0, x1, y1 = tile.total_bounds
    hh, hv, valid, looks, tf = read_gcov((x0 - 100, y0 - 100, x1 + 100, y1 + 100))
    shape = hh.shape
    print(f"GCOV window {shape}, valid {valid.mean():.3f}, looks median {np.nanmedian(looks):.1f}")

    # Clipped dB rasters: small (~1 MB), reused by any later NISAR figure.
    prof = dict(driver="GTiff", height=shape[0], width=shape[1], count=1, dtype="float32",
                crs=NISAR_CRS, transform=tf, nodata=np.nan, compress="deflate")
    rasters = {}
    for name, arr in (("hh", hh), ("hv", hv)):
        p = DER / f"nisar_gcov_{name}_gamma0_db_20260120_9t_10m.tif"
        with rasterio.open(p, "w", **prof) as d:
            d.write(np.where(valid, db(arr), np.nan).astype(np.float32), 1)
        rasters[name] = p
        print(f"  wrote {p}")

    cover = canopy_cover(tf, shape)
    in_tile = np.isfinite(cover)

    # --- registration check ------------------------------------------------
    reg = []
    hv_db = db(hv)
    for dx in range(-20, 21, 5):
        for dy in range(-20, 21, 5):
            c = canopy_cover(tf, shape, (dx, dy)) if (dx, dy) != (0, 0) else cover
            m = valid & np.isfinite(c)
            reg.append(dict(dx=dx, dy=dy, rho=float(spearmanr(c[m], hv_db[m]).statistic)))
    reg = pd.DataFrame(reg)
    best = reg.loc[reg.rho.idxmax()]
    print(f"registration: rho at 0,0 = {reg.query('dx==0 and dy==0').rho.iat[0]:.3f}; "
          f"best {best.rho:.3f} at dx={best.dx:+.0f} dy={best.dy:+.0f}")
    if align:
        # Canopy sampled at (x+dx, y+dy) matches the pixel labelled (x, y) best,
        # so that pixel really shows ground at (x+dx, y+dy). Move its label there.
        tf = rasterio.Affine(tf.a, tf.b, tf.c + float(best.dx), tf.d, tf.e, tf.f + float(best.dy))
        cover = canopy_cover(tf, shape)
        in_tile = np.isfinite(cover)
        print(f"aligned: NISAR grid moved by dx={best.dx:+.0f} m, dy={best.dy:+.0f} m")

    # --- geometry -----------------------------------------------------------
    pads = read_layer(ANN, "plat").to_crs(NISAR_CRS)
    pads = pads[["pad_id", "area_m2", "geometry"]].dissolve(by="pad_id").reset_index()
    roads = read_layer(ANN, "roads").to_crs(NISAR_CRS)
    excl = pd.concat([pads.geometry.buffer(EXCL_M), roads.geometry.buffer(EXCL_M)]).union_all()

    xs, ys = pixel_centres(tf, shape)
    ok = valid & in_tile

    def pixels_in(geom):
        if geom.is_empty:
            return np.zeros(shape, bool)
        return rasterize([(geom, 1)], out_shape=shape, transform=tf, fill=0,
                         all_touched=False, dtype="uint8").astype(bool) & ok

    rows = []
    pad_px = {"hh": [], "hv": []}
    ring_px = {"hh": [], "hv": []}
    for p in pads.itertuples():
        core = p.geometry.buffer(-PAD_CORE_M)
        ring = p.geometry.buffer(RING_OUT).difference(p.geometry.buffer(RING_IN)).difference(excl)
        pm, rm = pixels_in(core), pixels_in(ring)
        r = dict(pad_id=p.pad_id, area_m2=p.geometry.area, n_core=int(pm.sum()), n_ring=int(rm.sum()))
        for k, arr in (("hh", hh), ("hv", hv)):
            r[f"{k}_pad_db"] = float(db(arr[pm].mean())) if pm.any() else np.nan
            r[f"{k}_ring_db"] = float(db(arr[rm].mean())) if rm.any() else np.nan
            pad_px[k].append(arr[pm]); ring_px[k].append(arr[rm])
        r["canopy_pad_2019"] = float(np.nanmean(cover[pm])) if pm.any() else np.nan
        r["canopy_ring_2019"] = float(np.nanmean(cover[rm])) if rm.any() else np.nan
        rows.append(r)
    df = pd.DataFrame(rows)
    for k in ("hh", "hv"):
        df[f"{k}_diff_db"] = df[f"{k}_pad_db"] - df[f"{k}_ring_db"]
    df["ratio_pad_db"] = df.hh_pad_db - df.hv_pad_db
    df["ratio_ring_db"] = df.hh_ring_db - df.hv_ring_db
    df["ratio_diff_db"] = df.ratio_pad_db - df.ratio_ring_db
    df["stratum"] = pd.cut(df.canopy_pad_2019, [-0.01, 0.25, 0.5, 1.01],
                           labels=["open (<25% canopy)", "partly grown (25-50%)", "grown over (>50%)"])
    use = df[(df.n_core > 0) & (df.n_ring > 0)].reset_index(drop=True)
    print(f"pads {len(df)}; with >=1 core pixel and ring {len(use)}; "
          f"too small for a core pixel {(df.n_core == 0).sum()}")

    # --- statistics -----------------------------------------------------------
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(use), size=(B, len(use)))

    def summarise(sub, label):
        out = dict(group=label, n_pads=len(sub))
        if len(sub) < 5:
            return out
        for k in ("hh", "hv", "ratio"):
            d = sub[f"{k}_diff_db"].to_numpy()
            out[f"{k}_median_diff_db"] = float(np.median(d))
            out[f"{k}_share_pad_brighter"] = float((d > 0).mean())
            out[f"{k}_wilcoxon_p"] = float(wilcoxon(d).pvalue)
            a = auc(sub[f"{k}_pad_db"].to_numpy(), sub[f"{k}_ring_db"].to_numpy())
            out[f"{k}_auc_pad_gt_ring"] = float(a)
            j = rng.integers(0, len(sub), size=(B, len(sub)))
            bd = np.median(d[j], axis=1)
            out[f"{k}_median_diff_ci"] = [float(np.percentile(bd, 2.5)), float(np.percentile(bd, 97.5))]
        return out

    summary = [summarise(use, "all pads")]
    for s in use.stratum.cat.categories:
        summary.append(summarise(use[use.stratum == s], s))
    summ = pd.DataFrame(summary)

    # Positive control: open vs closed canopy anywhere in the tile.
    openm = ok & (cover < 0.10)
    closed = ok & (cover > 0.90)
    control = dict(n_open_px=int(openm.sum()), n_closed_px=int(closed.sum()))
    for k, arr in (("hh", hh), ("hv", hv)):
        a, b = db(arr[openm]), db(arr[closed])
        control[f"{k}_open_median_db"] = float(np.median(a))
        control[f"{k}_closed_median_db"] = float(np.median(b))
        sa = rng.choice(a, min(20000, len(a)), replace=False)
        sb = rng.choice(b, min(20000, len(b)), replace=False)
        control[f"{k}_auc_closed_gt_open"] = float(auc(sb, sa))
    print(json.dumps(control, indent=1))
    print(summ.to_string())

    # --- outputs -------------------------------------------------------------
    per_pad = OUT / f"nisar_gcov_pad_vs_forest_ring20to60m_per_pad_hh_hv_20260120_{tag}_9t.csv"
    df.to_csv(per_pad, index=False)
    summ_path = OUT / f"nisar_gcov_pad_vs_forest_ring20to60m_summary_hh_hv_20260120_{tag}_9t.json"
    summ_path.write_text(json.dumps(dict(
        gcov=str(H5.relative_to(ROOT)), date="2026-01-20", georeference=tag,
        applied_shift_m=[float(best.dx), float(best.dy)] if align else [0.0, 0.0], n_pads_total=len(df),
        n_pads_used=len(use), control_open_lt10_vs_closed_gt90=control,
        registration=reg.to_dict("records"), groups=summary), indent=1, default=str))
    print(f"  wrote {per_pad}\n  wrote {summ_path}")

    # --- figure --------------------------------------------------------------
    fig, ax = plt.subplots(1, 3, figsize=(15.5, 5.2), gridspec_kw=dict(width_ratios=[1.15, 1, 1]))
    # (a) HV map with pads
    b = tile.total_bounds
    img = np.where(valid, hv_db, np.nan)
    ext = (tf.c, tf.c + shape[1] * tf.a, tf.f + shape[0] * tf.e, tf.f)
    lo, hi = np.nanpercentile(img[in_tile], [2, 98])
    im = ax[0].imshow(img, extent=ext, cmap="gray", vmin=lo, vmax=hi, interpolation="nearest")
    pads.boundary.plot(ax=ax[0], color=PAD_C, lw=0.6)
    ax[0].set_xlim(b[0], b[2]); ax[0].set_ylim(b[1], b[3])
    ax[0].set_xticks([]); ax[0].set_yticks([])
    ax[0].set_title("HV radar brightness, 10 m, 20 Jan 2026\nannotated pads outlined", fontsize=10, loc="left")
    cb = fig.colorbar(im, ax=ax[0], fraction=0.04, pad=0.02); cb.set_label("HV gamma-0 (dB)")

    # (b) paired pad vs ring, HH and HV
    for i, k in enumerate(("hh", "hv")):
        pv, rv = use[f"{k}_pad_db"], use[f"{k}_ring_db"]
        xpad, xring = i * 3 + 0, i * 3 + 1
        for a_, c_ in zip(pv, rv):
            ax[1].plot([xring, xpad], [c_, a_], color=MUTED, lw=0.3, alpha=0.25)
        jit = rng.uniform(-0.12, 0.12, len(use))
        ax[1].scatter(xring + jit, rv, s=6, color=RING_C, marker="s", alpha=0.6, lw=0)
        ax[1].scatter(xpad + jit, pv, s=6, color=PAD_C, marker="o", alpha=0.6, lw=0)
        for x_, v_, c_ in ((xring, rv, RING_C), (xpad, pv, PAD_C)):
            ax[1].hlines(np.median(v_), x_ - 0.3, x_ + 0.3, color=INK, lw=2)
    ax[1].set_xticks([0, 1, 3, 4]); ax[1].set_xticklabels(["HH\npad", "HH\nforest ring", "HV\npad", "HV\nforest ring"])
    ax[1].set_ylabel("gamma-0 (dB)")
    ax[1].set_title(f"Each pad against its own forest ring\n{len(use)} pads, lines join pairs, bars are medians",
                    fontsize=10, loc="left")

    # (c) difference by 2019 canopy stratum
    cats = list(use.stratum.cat.categories)
    for i, k in enumerate(("hh", "hv")):
        for j, s in enumerate(cats):
            d = use.loc[use.stratum == s, f"{k}_diff_db"].dropna()
            x = j + (i - 0.5) * 0.35
            c_, m_ = (MUTED, "D") if k == "hh" else (INK, "o")
            if len(d):
                ax[2].scatter(x + rng.uniform(-0.06, 0.06, len(d)), d, s=5, color=c_, alpha=0.35, lw=0)
                ax[2].errorbar(x, np.median(d), yerr=[[np.median(d) - np.percentile(d, 25)],
                               [np.percentile(d, 75) - np.median(d)]], fmt=m_, color=c_, ms=7,
                               capsize=3, label=k.upper() if j == 0 else None)
    ax[2].axhline(0, color=INK, lw=0.8, ls="--")
    ax[2].set_xticks(range(len(cats)))
    ax[2].set_xticklabels([f"{c}\nn={int((use.stratum == c).sum())}" for c in cats], fontsize=8)
    ax[2].set_ylabel("pad minus forest ring (dB)")
    ax[2].set_title("By how open the pad was in 2019 lidar\nabove 0 = pad brighter; markers are medians, bars IQR",
                    fontsize=10, loc="left")
    ax[2].legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fpath = FIG / f"nisar_gcov_pad_vs_forest_ring20to60m_hh_hv_by_2019_canopy_20260120_{tag}_9t.png"
    fig.savefig(fpath, dpi=170)
    print(f"  wrote {fpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
