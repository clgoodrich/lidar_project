"""RRIM for tile 9t on a 0.25 m grid, built from a bicubic-upsampled 0.5 m DEM. Set 2026-11-24.

Why
  A CNN with stride 32 can shrink a 2-3 px feature to nothing. Upsampling the input 2x gives the
  network more pixels per feature. Upsampled derivatives also look less blocky.

What it is not
  It adds no information. Every 0.25 m cell is a weighted average of 0.5 m posts. Nothing
  smaller than about 1 m (twice the 0.5 m spacing) is resolved. Don't read the extra detail as real.
  Use it the same way in training and inference, or not at all.

Why upsample the DEM and not the RRIM
  Resampling the finished RGB only blurs colours. Upsampling the DEM and recomputing slope and
  openness gives smooth derivatives on the finer grid, which is the point.

Recipe (same as notebooks/wellsight_v2/s1_build/_make_rrim.py, Chiba et al. 2008)
  1. DEM: dem_9t_05.tif, scipy cubic spline (order 3) zoomed 2x, in tiles with a halo.
  2. Slope: Horn 3x3, degrees.  Openness: 8 directions, 25 m search (100 cells), as in the
     1 m and 0.5 m builds.  D = (pos - neg) / 2.
  3. Colour: D scaled by its own 98th percentile of |D| -> teal/grey/yellow, +18, multiplied by
     white->red slope ramp saturating at 40 deg.  Nodata white.

Output (gitignored by data/**/derived/**)
  data/9t/derived/025/rrim_openness_9t_025.tif   3-band uint8, EPSG:6346, 0.25 m
  data/9t/derived/025/rrim_openness_9t_025_preview.png

Run
  python notebooks/wellsight_v2/s1_build/_rrim_upsample_9t.py            full tile
  python notebooks/wellsight_v2/s1_build/_rrim_upsample_9t.py --pilot    NW 500 m corner only
"""
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402
from s1_build._make_rrim import TEAL, GRAY, YELLOW, WHITE, RED, _diverge  # noqa: E402

SRC = path_for("derived") / "9t" / "derived" / "05" / "dem_9t_05.tif"
OUT_DIR = path_for("derived") / "9t" / "derived" / "025"
OUT = OUT_DIR / "rrim_openness_9t_025.tif"
UP = 2                    # 0.5 m -> 0.25 m
CELL = 0.5 / UP
L_M = 25.0                # openness search, metres
L = int(round(L_M / CELL))
TILE = 1000               # source cells per tile (-> 2000 out)
HALO = L // UP + 4        # source cells; covers the openness search plus spline edge
SLOPE_HI, DO_PCT, BRIGHT = 40.0, 98.0, 18.0


def openness(z, valid):
    """Yokoyama 2002 openness, L cells, 8 directions. Slices, not np.roll, so edges stay invalid."""
    H, W = z.shape
    phi = np.zeros_like(z)
    psi = np.zeros_like(z)
    for dr, dc in [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]:
        step = CELL * np.hypot(dr, dc)
        up = np.full_like(z, -np.inf)
        dn = np.full_like(z, np.inf)
        for k in range(1, L + 1):
            r0, c0 = dr * k, dc * k
            ys, yd = slice(max(r0, 0), H + min(r0, 0)), slice(max(-r0, 0), H + min(-r0, 0))
            xs, xd = slice(max(c0, 0), W + min(c0, 0)), slice(max(-c0, 0), W + min(-c0, 0))
            v = valid[ys, xs]
            t = (z[ys, xs] - z[yd, xd]) / (k * step)
            np.fmax(up[yd, xd], np.where(v, t, -np.inf), out=up[yd, xd])
            np.fmin(dn[yd, xd], np.where(v, t, np.inf), out=dn[yd, xd])
        phi += np.pi / 2 - np.arctan(np.where(np.isfinite(up), up, 0))
        psi += np.pi / 2 + np.arctan(np.where(np.isfinite(dn), dn, 0))
    return np.degrees(phi / 8), np.degrees(psi / 8)


def main():
    pilot = "--pilot" in sys.argv   # first 1000x1000 source tile only, own file
    out = OUT.with_name(OUT.stem + "_pilot.tif") if pilot else OUT
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    src = rasterio.open(SRC)
    H, W = src.height, src.width
    HO, WO = H * UP, W * UP
    D = np.full((HO, WO), np.nan, np.float32)
    S = np.full((HO, WO), np.nan, np.float16)
    t0 = time.time()
    tiles = [(r, c) for r in range(0, H, TILE) for c in range(0, W, TILE)]
    if pilot:
        tiles = tiles[:1]
    for i, (r, c) in enumerate(tiles):
        r0, c0 = max(r - HALO, 0), max(c - HALO, 0)
        r1, c1 = min(r + TILE + HALO, H), min(c + TILE + HALO, W)
        z = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0)).astype(np.float32)
        ok = z != src.nodata
        if not ok.any():
            continue
        # fill nodata with nearest valid so the spline does not ring off -9999
        idx = ndi.distance_transform_edt(~ok, return_distances=False, return_indices=True)
        zf = z[tuple(idx)]
        zu = ndi.zoom(zf, UP, order=3, mode="nearest", grid_mode=True).astype(np.float32)
        vu = ndi.zoom(ok.astype(np.uint8), UP, order=0, grid_mode=True).astype(bool)
        # Horn slope
        k = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], np.float32) / (8 * CELL)
        gx = ndi.correlate(zu, k, mode="nearest")
        gy = ndi.correlate(zu, k.T, mode="nearest")
        slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        op, on = openness(zu, vu)
        d = (op - on) / 2
        d[~vu] = np.nan
        slope[~vu] = np.nan
        # keep only the core
        a, b = (r - r0) * UP, (c - c0) * UP
        h, w = (min(r + TILE, H) - r) * UP, (min(c + TILE, W) - c) * UP
        D[r * UP:r * UP + h, c * UP:c * UP + w] = d[a:a + h, b:b + w]
        S[r * UP:r * UP + h, c * UP:c * UP + w] = slope[a:a + h, b:b + w]
        print(f"tile {i + 1}/{len(tiles)}  {time.time() - t0:.0f} s", flush=True)

    if pilot:
        HO = WO = TILE * UP
        D, S = D[:HO, :WO], S[:HO, :WO]
    dlim = float(np.nanpercentile(np.abs(D[::4, ::4]), DO_PCT))
    print(f"|D| {DO_PCT:.0f}th percentile = {dlim:.2f} deg")
    prof = src.profile.copy()
    prof.update(width=WO, height=HO, count=3, dtype="uint8", nodata=None, compress="deflate",
                predictor=2, tiled=True, blockxsize=512, blockysize=512, photometric="RGB",
                interleave="pixel", BIGTIFF="IF_SAFER",
                transform=src.transform * src.transform.scale(1 / UP, 1 / UP))
    with rasterio.open(out, "w", **prof) as ds:
        for r in range(0, HO, 2048):
            d = D[r:r + 2048]
            s = S[r:r + 2048].astype(np.float32)
            valid = np.isfinite(d) & np.isfinite(s)
            t = np.nan_to_num(np.clip(d / dlim, -1, 1))
            base = np.clip(_diverge(t, TEAL, YELLOW, GRAY) + BRIGHT, 0, 255)
            u = np.clip(np.nan_to_num(s) / SLOPE_HI, 0, 1)[..., None]
            rgb = np.clip(base * (WHITE + (RED - WHITE) * u) / 255.0, 0, 255)
            rgb[~valid] = 255
            ds.write(np.moveaxis(rgb.astype(np.uint8), -1, 0), window=Window(0, r, WO, d.shape[0]))
    print(f"wrote {out}  ({WO}x{HO}, {out.stat().st_size / 1e6:.0f} MB)")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with rasterio.open(out) as ds:
        prev = np.moveaxis(ds.read(out_shape=(3, 1800, 1800)), 0, -1)
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(prev)
    ax.set_xticks([]); ax.set_yticks([])
    png = out.with_name(out.stem + "_preview.png")
    fig.savefig(png, dpi=130, bbox_inches="tight")
    print(f"wrote {png}")


if __name__ == "__main__":
    main()
