"""
Utility functions for the orphan-well terrain anomaly detection pipeline.

Self-contained (no project-internal imports) so it can be imported by either
the scratch Phase 0 runner or the notebook.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi


# ───────────────────────────────────────────────────────────────────────────
# Raster I/O helpers
# ───────────────────────────────────────────────────────────────────────────
def read_raster(path: Path):
    """Read a single-band raster, return (data as float32, nodata_mask, profile)."""
    with rasterio.open(path) as src:
        data = src.read(1).astype("float32")
        nd = src.nodata
        profile = src.profile.copy()
    nd_mask = (data == nd) if nd is not None else np.isnan(data)
    return data, nd_mask, profile


def write_raster(path: Path, data: np.ndarray, profile_like: dict,
                 dtype: str = "float32", nodata: float = -9999.0) -> None:
    """Write a float raster, always forcing a valid block size."""
    p = profile_like.copy()
    p.update(
        dtype=dtype,
        nodata=nodata,
        compress="deflate",
        tiled=True,
        blockxsize=256,
        blockysize=256,
        count=1,
    )
    out = data.copy()
    if np.issubdtype(out.dtype, np.floating):
        out[np.isnan(out)] = nodata
    with rasterio.open(path, "w", **p) as dst:
        dst.write(out.astype(dtype), 1)


# ───────────────────────────────────────────────────────────────────────────
# Yokoyama et al. 2002 topographic openness
# ───────────────────────────────────────────────────────────────────────────
def topographic_openness(dem: np.ndarray, radius: int = 50,
                         cellsize: float = 1.0,
                         nodata_mask: np.ndarray | None = None,
                         progress: bool = False):
    """
    Compute positive and negative topographic openness per Yokoyama, Shirasawa,
    and Pike (2002), "Visualizing Topography by Openness: A New Application of
    Image Processing to Digital Elevation Models."

    For each cell, in each of 8 azimuth directions, scan outward up to `radius`
    cells and track the maximum elevation angle (β, upward) and maximum
    depression angle (δ, downward). Positive openness in that direction is the
    zenith angle 90° − β; negative openness is the nadir angle 90° − δ. The
    final openness value is the mean across the 8 directions, in degrees.

    Parameters
    ----------
    dem : np.ndarray, shape (H, W)
        Elevation grid. Must be float; nodata represented either by NaN or by
        `nodata_mask`.
    radius : int
        Search distance in grid cells.
    cellsize : float
        Cell resolution in the same units as `dem` (e.g., meters).
    nodata_mask : np.ndarray | None
        Optional boolean mask of invalid cells. If given, the DEM is copied
        and NaN'd at those cells before computation.
    progress : bool
        If True, prints one line per direction.

    Returns
    -------
    pos_openness : np.ndarray
        Positive openness in degrees. High = convex / ridge / pad; low = concave / valley.
    neg_openness : np.ndarray
        Negative openness in degrees. High = concave / valley / road cut; low = convex / ridge.
    """
    dem = dem.astype(np.float32, copy=True)
    if nodata_mask is not None:
        dem[nodata_mask] = np.nan

    H, W = dem.shape

    # 8 azimuth directions: (dy, dx) unit steps. Cardinals first, then diagonals.
    dirs = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]

    pos_sum = np.zeros((H, W), dtype=np.float32)
    neg_sum = np.zeros((H, W), dtype=np.float32)

    NEG_INF = np.float32(-1e9)
    shifted = np.empty((H, W), dtype=np.float32)

    for di, (dy, dx) in enumerate(dirs):
        # Track max slope (dz / horizontal_distance) — atan is monotonic so
        # max slope ⇔ max angle, and we avoid 400 arctan calls on large arrays.
        # Initialize at 0, not -inf: "no obstacle seen" = horizon visible = slope 0.
        # This gives the correct default for edge cells that have no valid neighbor
        # in a given direction — they contribute 90° (open horizon) rather than 180°.
        max_slope_up = np.zeros((H, W), dtype=np.float32)
        max_slope_dn = np.zeros((H, W), dtype=np.float32)

        for k in range(1, radius + 1):
            sdy, sdx = k * dy, k * dx
            horiz = k * cellsize * math.sqrt(dy * dy + dx * dx)

            # shifted[i,j] = dem[i + sdy, j + sdx] — explicit slicing, no wraparound.
            shifted.fill(np.nan)
            if sdy >= 0:
                i_dst = slice(0, H - sdy)
                i_src = slice(sdy, H)
            else:
                i_dst = slice(-sdy, H)
                i_src = slice(0, H + sdy)
            if sdx >= 0:
                j_dst = slice(0, W - sdx)
                j_src = slice(sdx, W)
            else:
                j_dst = slice(-sdx, W)
                j_src = slice(0, W + sdx)
            shifted[i_dst, j_dst] = dem[i_src, j_src]

            dz = shifted - dem  # NaN where either endpoint is nodata or out of bounds
            slope = dz / horiz
            # NaN-safe max update: compute up and down slopes independently.
            # If we negated `slope_safe`, NEG_INF would become POS_INF, corrupting
            # the downward-slope max — bug that caused banding on the neg_open map.
            valid = ~np.isnan(slope)
            slope_up = np.where(valid, slope, NEG_INF)
            slope_dn = np.where(valid, -slope, NEG_INF)
            np.maximum(max_slope_up, slope_up, out=max_slope_up)
            np.maximum(max_slope_dn, slope_dn, out=max_slope_dn)

        # Convert max slopes to angles now (once per direction, not per k)
        beta = np.degrees(np.arctan(max_slope_up))   # elevation angle (max upward)
        delta = np.degrees(np.arctan(max_slope_dn))  # depression angle (max downward)
        # Cells that never saw a valid neighbor remain at NEG_INF → arctan → ~-90°
        # Clamp those back so they don't dominate the mean.
        beta = np.clip(beta, -90.0, 90.0)
        delta = np.clip(delta, -90.0, 90.0)

        pos_sum += 90.0 - beta    # zenith angle to visible sky
        neg_sum += 90.0 - delta   # nadir angle to visible ground

        if progress:
            print(f"    openness dir {di+1}/8 done")

    pos_open = pos_sum / 8.0
    neg_open = neg_sum / 8.0

    # Mask the center-cell nodata
    if nodata_mask is not None:
        pos_open[nodata_mask] = np.nan
        neg_open[nodata_mask] = np.nan

    return pos_open.astype(np.float32), neg_open.astype(np.float32)


# ───────────────────────────────────────────────────────────────────────────
# TPI gradient (magnitude + direction)
# ───────────────────────────────────────────────────────────────────────────
def tpi_gradient(tpi: np.ndarray, nodata_mask: np.ndarray | None = None):
    """Sobel gradient magnitude and direction of a TPI surface."""
    tpi = tpi.astype(np.float32, copy=True)
    if nodata_mask is None:
        nodata_mask = np.isnan(tpi)
    filled = np.where(nodata_mask, 0.0, tpi).astype(np.float32)
    gy = ndi.sobel(filled, axis=0, mode="nearest") / 8.0
    gx = ndi.sobel(filled, axis=1, mode="nearest") / 8.0
    mag = np.sqrt(gx * gx + gy * gy)
    direction = np.arctan2(gy, gx)
    mag[nodata_mask] = np.nan
    direction[nodata_mask] = np.nan
    return mag.astype(np.float32), direction.astype(np.float32)


# ───────────────────────────────────────────────────────────────────────────
# Local z-score anomaly (used for intensity anomaly, CHM anomaly, etc.)
# ───────────────────────────────────────────────────────────────────────────
def local_zscore(arr: np.ndarray, window: int,
                 nodata_mask: np.ndarray | None = None) -> np.ndarray:
    """
    Local z-score using a uniform (box) filter. The scipy-nan pattern fills
    nodata with 0 before filtering and restores nodata to NaN afterward.
    """
    if nodata_mask is None:
        nodata_mask = np.isnan(arr)
    filled = np.where(nodata_mask, 0.0, arr).astype(np.float32)
    mean = ndi.uniform_filter(filled, size=window, mode="reflect")
    sq = ndi.uniform_filter(filled * filled, size=window, mode="reflect")
    var = np.maximum(sq - mean * mean, 1e-6)
    std = np.sqrt(var)
    z = (filled - mean) / std
    z[nodata_mask] = np.nan
    return z.astype(np.float32)
