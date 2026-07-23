"""Experimental *linear-feature* channels for road/trail detection.

Reads an existing derivative-stack tile dir (built by ``_build_derivatives.py``)
and writes extra channels that specifically enhance elongated anthropogenic
earthworks (roads, skid trails, hollow ways). These are the techniques a
LiDAR-archaeology practitioner flagged as keying hardest on linear treads:

    slope_residual_{r}m   slope - focal_mean(slope, r); the tread is a linear
                          band of anomalously LOW slope -> negative residual.
    diff_openness         openness_pos - openness_neg (Chiba RRIM base; the
                          differential that makes linear cuts pop).
    rough_aniso           structure-tensor coherence of the roughness field:
    rough_orient          the anisotropy ratio ("smooth along, rough across")
                          plus feature orientation (deg, along-feature).
    profile_curv          WBT profile curvature (signed).
    curv_doublet          cut/fill DOUBLET score: concave on one side x convex
                          on the other, sampled +/- across the local feature
                          orientation -> rejects single natural breaks.
    sllac_len             slope local length of auto-correlation: directional
    sllac_aniso           persistence of the slope field (max-dir length) and
                          its anisotropy. Documented APPROXIMATION (4 dirs).
    frangi_lrm            multiscale Frangi vesselness (dark ridges) on LRM and
    frangi_slresid        on slope-residual -- Hessian elongated-structure resp.
    ridge_sato            Sato tubeness (Steger-family ridge response) plus the
    ridge_orient          Hessian ORIENTATION field (deg, along-ridge) -- the
                          per-pixel direction that later enables gap-linking.

All outputs are float32 GeoTIFFs written into the SAME tile dir, named
``<stem>_<sfx>.tif``. NaN where the DEM is NaN. These are experimental; the
winners get folded into ``_build_derivatives.py`` later.

CLI:
  python notebooks/wellsight_v2/build/_build_extra_channels.py \
      --dir data/derivatives/tiles/613590_05 --sfx 613590_05 --res 0.5
"""
from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.ndimage import uniform_filter, gaussian_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import write_tif  # noqa: E402

EPS = 1e-6


# ---------------------------------------------------------------------------
# small NaN-aware helpers
# ---------------------------------------------------------------------------

def focal_mean(a: np.ndarray, size: int) -> np.ndarray:
    """NaN-aware box mean (separable uniform_filter, O(N) in window size)."""
    v = np.isfinite(a).astype(np.float32)
    a0 = np.where(v > 0, a, 0).astype(np.float32)
    sm = uniform_filter(a0, size=size, mode="nearest")
    sc = uniform_filter(v, size=size, mode="nearest")
    out = np.full(a.shape, np.nan, np.float32)
    np.divide(sm, sc, out=out, where=sc > 0.5)
    return out


def fill_nan(a: np.ndarray, size: int = 25) -> np.ndarray:
    """Replace NaN with a local box mean so Hessian/gradient ops stay finite."""
    out = a.copy()
    m = ~np.isfinite(a)
    if m.any():
        fm = focal_mean(a, size)
        out[m] = fm[m]
        still = ~np.isfinite(out)
        if still.any():
            out[still] = np.nanmedian(a)
    return out.astype(np.float32)


# ---------------------------------------------------------------------------
# channels
# ---------------------------------------------------------------------------

def ch_slope_residual(slope, res, nanmask, radii_m=(12, 24)):
    for r_m in radii_m:
        size = int(round(2 * r_m / res)) | 1
        sr = (slope - focal_mean(slope, size)).astype(np.float32)
        sr[nanmask] = np.nan
        yield f"slope_residual_{r_m}m", sr


def ch_diff_openness(op_pos, op_neg, nanmask):
    d = (op_pos - op_neg).astype(np.float32)
    d[nanmask] = np.nan
    yield "diff_openness", d


def ch_structure_tensor(dem, res, nanmask, rough_win_m=5.0, smooth_sig=2.0):
    """Anisotropy (coherence) + orientation of the local roughness field."""
    win = int(round(rough_win_m / res)) | 1
    resid = dem - focal_mean(dem, win)           # high-pass roughness signal
    resid = fill_nan(resid, 25)
    gy, gx = np.gradient(resid, res)
    del resid
    jxx = gaussian_filter(gx * gx, smooth_sig).astype(np.float32)
    jyy = gaussian_filter(gy * gy, smooth_sig).astype(np.float32)
    jxy = gaussian_filter(gx * gy, smooth_sig).astype(np.float32)
    del gx, gy
    tmp = np.sqrt(np.maximum(((jxx - jyy) * 0.5) ** 2 + jxy * jxy, 0)).astype(np.float32)
    half = (jxx + jyy) * 0.5
    lam1 = half + tmp
    lam2 = half - tmp
    coh = ((lam1 - lam2) / (lam1 + lam2 + EPS)).astype(np.float32)  # 0..1
    # gradient orientation -> feature runs perpendicular to mean gradient
    grad_ang = 0.5 * np.arctan2(2 * jxy, jxx - jyy)
    feat_ang = (np.degrees(grad_ang) + 90.0) % 180.0
    del jxx, jyy, jxy, tmp, half, lam1, lam2
    coh[nanmask] = np.nan
    feat_ang = feat_ang.astype(np.float32)
    feat_ang[nanmask] = np.nan
    yield "rough_aniso", coh
    yield "rough_orient", feat_ang


def ch_profile_curv_doublet(dem, res, out_dir, sfx, nanmask, feat_orient_deg,
                            offset_m=2.5, dem_name=None):
    """WBT profile curvature + a cut/fill doublet score across feature orient."""
    import whitebox
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(out_dir.resolve()))
    wbt.set_verbose_mode(False)
    wbt.profile_curvature(dem=dem_name or f"dem_{sfx}.tif",
                          output=f"profile_curv_{sfx}.tif")
    with rasterio.open(out_dir / f"profile_curv_{sfx}.tif") as r:
        curv = r.read(1).astype(np.float32)
        cnod = r.nodata
    if cnod is not None:
        curv[curv == cnod] = np.nan
    curv = np.nan_to_num(curv, nan=0.0)
    # sample curvature +/- offset along the PERPENDICULAR to feature orientation
    d = offset_m / res
    ang = np.deg2rad(np.nan_to_num(feat_orient_deg, nan=0.0))
    pdy = np.cos(ang + np.pi / 2).astype(np.float32)   # perpendicular unit
    pdx = np.sin(ang + np.pi / 2).astype(np.float32)
    rows, cols = np.indices(curv.shape, dtype=np.float32)
    cp = ndi.map_coordinates(curv, [rows + d * pdy, cols + d * pdx], order=1,
                             mode="nearest").astype(np.float32)
    cm = ndi.map_coordinates(curv, [rows - d * pdy, cols - d * pdx], order=1,
                             mode="nearest").astype(np.float32)
    del rows, cols, pdy, pdx, ang
    # opposite signs on the two sides -> genuine cut/fill pair
    doublet = (np.maximum(cp, 0) * np.maximum(-cm, 0)
               + np.maximum(-cp, 0) * np.maximum(cm, 0))
    doublet = np.sqrt(np.maximum(doublet, 0)).astype(np.float32)
    del cp, cm
    curv[nanmask] = np.nan
    doublet[nanmask] = np.nan
    # profile_curv already written by WBT; re-yield cleaned version + doublet
    yield "profile_curv", curv
    yield "curv_doublet", doublet


def ch_sllac(slope, res, nanmask, win_m=7.5, max_lag_m=10.0, thr=0.4):
    """Slope Local Length of Auto-Correlation (directional persistence).

    APPROXIMATION: 4 orientations via integer shifts (0/45/90/135). Per dir,
    the contiguous lag run (from lag 1) over which local auto-correlation of the
    detrended slope stays > thr; length in metres. Output max-dir length and the
    anisotropy (max/mean over dirs)."""
    win = int(round(win_m / res)) | 1
    s = (slope - focal_mean(slope, win)).astype(np.float32)
    s = np.nan_to_num(s, nan=0.0)
    var = focal_mean(s * s, win)
    var = np.where(np.isfinite(var), var, 0) + EPS
    dirs = [(0, 1), (1, 1), (1, 0), (1, -1)]
    K = int(round(max_lag_m / res))
    lens = []
    for dr, dc in dirs:
        length = np.zeros(s.shape, np.float32)
        still = np.ones(s.shape, bool)
        step = res * np.hypot(dr, dc)
        for k in range(1, K + 1):
            sh = np.roll(s, shift=(dr * k, dc * k), axis=(0, 1))
            ac = focal_mean(s * sh, win) / var
            cont = still & (ac > thr)
            length = np.where(cont, k * step, length)
            still &= cont
        lens.append(length)
    lens = np.stack(lens).astype(np.float32)
    sllac_len = lens.max(0)
    sllac_aniso = (lens.max(0) / (lens.mean(0) + EPS)).astype(np.float32)
    del lens, s, var
    sllac_len[nanmask] = np.nan
    sllac_aniso[nanmask] = np.nan
    yield "sllac_len", sllac_len
    yield "sllac_aniso", sllac_aniso


def _disk(r):
    r = int(r)
    y, x = np.ogrid[-r:r+1, -r:r+1]
    return (x * x + y * y) <= r * r


def _sg2d_kernel(win):
    """2D Savitzky-Golay kernel that returns the local quadratic least-squares
    fit evaluated AT the window centre (the constant-term row of the design
    pseudo-inverse). Correlating a field with it yields the fitted trend."""
    r = win // 2
    ys, xs = np.mgrid[-r:r+1, -r:r+1].astype(np.float64)
    x, y = xs.ravel(), ys.ravel()
    M = np.stack([np.ones_like(x), x, y, x * x, y * y, x * y], 1)
    return np.linalg.pinv(M)[0].reshape(win, win).astype(np.float32)


def _sg_residual(z, win):
    fit = ndi.correlate(z, _sg2d_kernel(win), mode="nearest")
    return (z - fit).astype(np.float32)


def ch_savgol(dem, res, nanmask, tread_m=3.0, scales=(4, 6, 8)):
    """Quadratic (2D Savitzky-Golay) residual: subtracts the local slope AND
    curvature, so only genuine departures from a smooth hillslope survive =
    anthropogenic benches. Fixes the curvature contamination of the LRM unsharp
    mask (LRM = DEM - focal_mean, which leaks ~(sigma^2/2)*Laplacian). Window
    ~4-8x tread width; multiscale keeps the largest-magnitude signed residual."""
    z = fill_nan(dem, 25)
    prim = int(round(6 * tread_m / res)) | 1
    r_prim = _sg_residual(z, prim)
    r_prim[nanmask] = np.nan
    yield f"savgol_resid_{prim}px", r_prim
    wins = sorted({int(round(s * tread_m / res)) | 1 for s in scales})
    best = np.zeros(z.shape, np.float32)
    for w in wins:
        r = _sg_residual(z, w)
        best = np.where(np.abs(r) > np.abs(best), r, best)
    best = best.astype(np.float32)
    best[nanmask] = np.nan
    yield "savgol_resid_msmax", best


def ch_tophat(dem, res, nanmask, tread_m=3.0):
    """White/black morphological top-hat of the quadratic residual. The bench is
    a step: material removed above (cut) and added below (fill). white top-hat
    (r - opening) captures the fill lip; black top-hat (closing - r) captures the
    cut. Run on the SavGol residual, NOT raw elevation (grey morphology needs the
    slope+curvature trend removed first). SE just wider than the tread."""
    z = fill_nan(dem, 25)
    base = _sg_residual(z, int(round(6 * tread_m / res)) | 1)
    se = _disk(max(2, int(round(0.7 * tread_m / res))))
    wth = (base - ndi.grey_opening(base, footprint=se)).astype(np.float32)
    bth = (ndi.grey_closing(base, footprint=se) - base).astype(np.float32)
    wth[nanmask] = np.nan
    bth[nanmask] = np.nan
    yield "tophat_white", wth
    yield "tophat_black", bth


def _frangi(base, nanmask, sigmas):
    from skimage.filters import frangi
    img = fill_nan(base, 25)
    # normalise to stabilise the Hessian eigenvalue scaling
    lo, hi = np.nanpercentile(img, [1, 99])
    img = np.clip((img - lo) / (hi - lo + EPS), 0, 1).astype(np.float32)
    resp = frangi(img, sigmas=sigmas, black_ridges=True).astype(np.float32)
    resp[nanmask] = np.nan
    return resp


def ch_frangi(lrm5, slope_resid12, nanmask, sigmas=(1, 2, 3, 4)):
    yield "frangi_lrm", _frangi(lrm5, nanmask, sigmas)
    gc.collect()
    yield "frangi_slresid", _frangi(slope_resid12, nanmask, sigmas)
    gc.collect()


def ch_ridge(lrm5, res, nanmask, sigmas=(1, 2, 3, 4), orient_sigma=2.0):
    """Sato tubeness + Hessian along-ridge orientation field."""
    from skimage.filters import sato
    img = fill_nan(lrm5, 25)
    lo, hi = np.nanpercentile(img, [1, 99])
    imgn = np.clip((img - lo) / (hi - lo + EPS), 0, 1).astype(np.float32)
    resp = sato(imgn, sigmas=sigmas, black_ridges=True).astype(np.float32)
    resp[nanmask] = np.nan
    yield "ridge_sato", resp
    del imgn, resp
    gc.collect()
    # Hessian at a single representative scale -> along-ridge orientation
    s = orient_sigma
    hxx = gaussian_filter(img, s, order=(0, 2)).astype(np.float32)
    hyy = gaussian_filter(img, s, order=(2, 0)).astype(np.float32)
    hxy = gaussian_filter(img, s, order=(1, 1)).astype(np.float32)
    # eigenvector of the LARGER |eigenvalue| points across a dark ridge;
    # along-ridge = that direction + 90 deg.
    ang_across = 0.5 * np.arctan2(2 * hxy, hxx - hyy)
    along = (np.degrees(ang_across) + 90.0) % 180.0
    along = along.astype(np.float32)
    along[nanmask] = np.nan
    del hxx, hyy, hxy, ang_across
    yield "ridge_orient", along


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="Existing tile dir")
    ap.add_argument("--sfx", required=True, help="Suffix in filenames")
    ap.add_argument("--res", type=float, required=True)
    ap.add_argument("--only", default=None,
                    help="Comma list of channel groups to run "
                         "(slope_residual,diff_openness,rough,curv,sllac,frangi,ridge,savgol,tophat)")
    ap.add_argument("--dem-name", default=None,
                    help="Override DEM filename (default dem_<sfx>.tif). Use e.g. "
                         "dem_breached_9t_1m.tif for dirs holding only a consolidated stack.")
    args = ap.parse_args()

    d = Path(args.dir)
    sfx = args.sfx
    res = args.res
    only = set(args.only.split(",")) if args.only else None

    def rd(stem):
        with rasterio.open(d / f"{stem}_{sfx}.tif") as r:
            a = r.read(1).astype(np.float32)
            nod = r.nodata
        if nod is not None:
            a[a == nod] = np.nan
        return a

    dem_path = d / (args.dem_name if args.dem_name else f"dem_{sfx}.tif")
    with rasterio.open(dem_path) as r:
        transform, crs = r.transform, r.crs
        dem = r.read(1).astype(np.float32)
        nod = r.nodata
    if nod is not None:
        dem[dem == nod] = np.nan
    nanmask = ~np.isfinite(dem)
    print(f"[extra] {sfx}  grid {dem.shape}  nan {100*nanmask.mean():.2f}%  dem={dem_path.name}")

    # lazy per-channel reads: savgol/curv/rough need only the DEM, so tiles that
    # hold just a DEM (e.g. 9t 1 m consolidated stack) still work with --only.
    _cache = {}
    def lazy(stem):
        if stem not in _cache:
            _cache[stem] = rd(stem)
        return _cache[stem]

    def emit(stem, arr):
        write_tif(d / f"{stem}_{sfx}.tif", arr, transform=transform, crs=crs)
        print(f"  wrote {stem}_{sfx}.tif")

    def want(g):
        return only is None or g in only

    if want("slope_residual"):
        for stem, arr in ch_slope_residual(lazy("slope"), res, nanmask):
            emit(stem, arr)

    if want("diff_openness"):
        for stem, arr in ch_diff_openness(lazy("openness_pos"), lazy("openness_neg"), nanmask):
            emit(stem, arr)

    feat_orient = None
    if want("rough"):
        for stem, arr in ch_structure_tensor(dem, res, nanmask):
            emit(stem, arr)
            if stem == "rough_orient":
                feat_orient = arr

    if want("curv"):
        if feat_orient is None:
            feat_orient = rd("rough_orient") if (d / f"rough_orient_{sfx}.tif").exists() \
                else np.zeros(dem.shape, np.float32)
        for stem, arr in ch_profile_curv_doublet(dem, res, d, sfx, nanmask, feat_orient,
                                                  dem_name=args.dem_name):
            emit(stem, arr)
        gc.collect()

    if want("sllac"):
        for stem, arr in ch_sllac(lazy("slope"), res, nanmask):
            emit(stem, arr)
        gc.collect()

    if want("frangi"):
        slresid12 = (lazy("slope_residual_12m")
                     if (d / f"slope_residual_12m_{sfx}.tif").exists()
                     else (lazy("slope") - focal_mean(lazy("slope"), int(round(24 / res)) | 1)))
        for stem, arr in ch_frangi(lazy("lrm_5"), slresid12, nanmask):
            emit(stem, arr)

    if want("ridge"):
        for stem, arr in ch_ridge(lazy("lrm_5"), res, nanmask):
            emit(stem, arr)

    if want("savgol"):
        for stem, arr in ch_savgol(dem, res, nanmask):
            emit(stem, arr)
        gc.collect()

    if want("tophat"):
        for stem, arr in ch_tophat(dem, res, nanmask):
            emit(stem, arr)
        gc.collect()

    print(f"[extra] {sfx} DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
