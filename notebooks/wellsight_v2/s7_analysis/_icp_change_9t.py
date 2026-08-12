"""Preliminary 2006-2008 -> 2019 ICP change product over the 9t block.

The ICP alignment and the full-overlap difference-of-DEMs already exist
(built 2026-05-21 by notebooks/wellsight/build/_icp_old_vs_new.py and
_icp_change_map.py). This script does NOT re-run ICP. It clips the existing
2 m DoD to the 9t footprint, runs the quality checks that decide whether the
surface is usable for change detection, and writes the 9t products.

Why the QC matters: a DoD between two acquisitions is only meaningful if the
residual horizontal misregistration is small. Any leftover shift dx turns into
a fake elevation difference of dx * tan(slope), so on steep ground a pure
registration error masquerades as terrain change. The slope-stratified stats
below separate those two causes.

Outputs (data/derivatives/experiments/icp/change_9t/):
  dod_9t_2m.tif           new - old (m), clipped to the 9t footprint
  dod_9t_sig_2m.tif       same, masked to |d| > k*sigma (candidate real change)
  change_9t_quicklook.png hillshade + diverging DoD + slope-stratified panel
  _stats_9t.json          all numbers quoted in the write-up

Run:
  python notebooks/wellsight_v2/s7_analysis/_icp_change_9t.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LightSource, TwoSlopeNorm
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
ICP = ROOT / "data" / "derivatives" / "experiments" / "icp"
NINE_T = ROOT / "data" / "derivatives" / "tiles" / "9t"
OUT = ICP / "change_9t"
OUT.mkdir(parents=True, exist_ok=True)

BBOX = (619500.0, 4593000.0, 624000.0, 4597500.0)   # 9t, EPSG:6346
RES = 2.0
SIG_K = 3.0          # candidate-change threshold, in robust sigma


def robust(v: np.ndarray) -> tuple[float, float]:
    """Median and normal-scaled MAD -- both insensitive to real-change tails."""
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)))
    return med, 1.4826 * mad


def to_grid(src_path: Path, band: int = 1) -> np.ndarray:
    """Resample any raster onto the 9t 2 m grid."""
    dst = np.full((2250, 2250), np.nan, np.float32)
    with rasterio.open(src_path) as s:
        reproject(rasterio.band(s, band), dst,
                  src_transform=s.transform, src_crs=s.crs,
                  dst_transform=from_origin(BBOX[0], BBOX[3], RES, RES),
                  dst_crs=s.crs, resampling=Resampling.bilinear,
                  src_nodata=s.nodata, dst_nodata=np.nan)
    return dst


def write(path: Path, arr: np.ndarray) -> None:
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
        count=1, dtype="float32", crs="EPSG:6346",
        transform=from_origin(BBOX[0], BBOX[3], RES, RES), nodata=np.nan,
        compress="deflate", predictor=2, tiled=True,
    ) as d:
        d.write(arr.astype(np.float32), 1)
    print(f"  wrote {path}")


def main() -> int:
    print(f"== 9t ICP change product  bbox={BBOX}  res={RES} m ==")

    # ---- clip the existing full-overlap DoD to 9t ----
    src = ICP / "change_map" / "dem_diff_2m.tif"
    with rasterio.open(src) as s:
        w = from_bounds(*BBOX, transform=s.transform)
        dod = s.read(1, window=w, masked=True).astype(np.float32).filled(np.nan)
    ok = np.isfinite(dod)
    print(f"  DoD clipped: {dod.shape}, {100 * ok.mean():.1f}% valid")

    # ---- slope from the 9t DEM, on the same grid ----
    dem = to_grid(NINE_T / "dem_breached_9t_1m.tif")
    gy, gx = np.gradient(dem, RES)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)

    v = dod[ok]
    med, sigma = robust(v)
    stats = {
        "bbox": list(BBOX), "res_m": RES,
        "valid_frac": float(ok.mean()),
        "mean": float(v.mean()), "median": med,
        "std": float(v.std()), "robust_sigma_mad": sigma,
        "pct": {f"p{q}": float(np.percentile(v, q))
                for q in (1, 5, 25, 50, 75, 95, 99)},
        "frac_abs_gt": {f"{t}m": float((np.abs(v) > t).mean())
                        for t in (0.25, 0.5, 1.0, 2.0)},
    }
    print(f"  median {med:+.3f} m   robust sigma {sigma:.3f} m   "
          f"raw std {v.std():.3f} m")

    # ---- QC: does |DoD| grow with slope? (residual-misregistration test) ----
    # A leftover planimetric shift dx produces dz = dx*tan(slope). If the
    # spread grows like tan(slope), the tails are registration error, not change.
    bins = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 30), (30, 90)]
    strat = []
    for lo, hi in bins:
        m = ok & (slope >= lo) & (slope < hi)
        if m.sum() < 500:
            continue
        sv = dod[m]
        smed, ssig = robust(sv)
        strat.append({"slope_lo": lo, "slope_hi": hi, "n": int(m.sum()),
                      "median": smed, "robust_sigma": ssig,
                      "tan_mid": float(np.tan(np.radians((lo + hi) / 2)))})
        print(f"    slope {lo:2d}-{hi:2d} deg  n={m.sum():8d}  "
              f"med {smed:+.3f}  sigma {ssig:.3f}")
    stats["slope_stratified"] = strat

    # implied planimetric error from the sigma-vs-tan(slope) trend
    if len(strat) >= 3:
        t = np.array([s["tan_mid"] for s in strat])
        g = np.array([s["robust_sigma"] for s in strat])
        A = np.stack([t, np.ones_like(t)], 1)
        dx_implied, sig0 = np.linalg.lstsq(A, g, rcond=None)[0]
        stats["implied_planimetric_error_m"] = float(dx_implied)
        stats["flat_ground_sigma_m"] = float(sig0)
        print(f"  fit: sigma = {dx_implied:.3f}*tan(slope) + {sig0:.3f}")
        print(f"    -> implied residual planimetric error {dx_implied:.2f} m")
        print(f"    -> flat-ground vertical noise floor  {sig0:.3f} m")

    # ---- candidate real change ----
    thr = SIG_K * sigma
    sig_mask = ok & (np.abs(dod - med) > thr)
    dod_sig = np.where(sig_mask, dod, np.nan).astype(np.float32)
    stats["sig_threshold_m"] = float(thr)
    stats["sig_frac"] = float(sig_mask.sum() / ok.sum())
    print(f"  candidate change |d-med| > {thr:.2f} m: "
          f"{sig_mask.sum()} px ({100 * stats['sig_frac']:.2f}%)")

    write(OUT / "dod_9t_2m.tif", dod)
    write(OUT / "dod_9t_sig_2m.tif", dod_sig)

    # ---- quicklook ----
    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(np.nan_to_num(dem, nan=float(np.nanmean(dem))),
                      vert_exag=2, dx=RES, dy=RES)
    lim = 5 * sigma
    norm = TwoSlopeNorm(vmin=-lim, vcenter=0.0, vmax=lim)

    fig, ax = plt.subplots(1, 3, figsize=(19, 6.6))
    ax[0].imshow(hs, cmap="gray"); ax[0].set_title("9t hillshade (2019)")
    im = ax[1].imshow(dod, cmap="RdBu_r", norm=norm)
    ax[1].set_title(f"DoD 2019 - 2006/08 (m)\nmed {med:+.3f}, sigma {sigma:.3f}")
    fig.colorbar(im, ax=ax[1], shrink=0.8)
    ax[2].imshow(hs, cmap="gray", alpha=0.85)
    ax[2].imshow(dod_sig, cmap="RdBu_r", norm=norm)
    ax[2].set_title(f"candidate change  |d-med| > {SIG_K:g} sigma "
                    f"({thr:.2f} m)\n{100 * stats['sig_frac']:.2f}% of pixels")
    for a in ax:
        a.set_xticks([]); a.set_yticks([])
    fig.suptitle("9t block  2006-2008 PA Statewide N -> 2019 USGS 3DEP D20, "
                 "ICP-aligned  (EPSG:6346, 2 m)")
    fig.tight_layout()
    png = OUT / "change_9t_quicklook.png"
    fig.savefig(png, dpi=130, bbox_inches="tight"); plt.close(fig)
    print(f"  wrote {png}")

    (OUT / "_stats_9t.json").write_text(json.dumps(stats, indent=2))
    print(f"  wrote {OUT / '_stats_9t.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
