"""Red Relief Image Map (RRIM) for a WellSight tile.

Classic Chiba et al. (2008) recipe: a red-tinted *slope* layer multiplied over a
*differential-openness* base (ridges bright, valleys/pits dark). Uses the openness
rasters already produced by the derivatives pipeline (no recompute). An optional
--simple mode swaps the openness base for a Local Relief Model base, reproducing
Auld-Thomas' (2022) patent-free "Simple Red Relief".

Refs (papers/ in repo root):
  Chiba, Kaneta & Suzuki 2008 — Red Relief Image Map, IAPRS XXXVII.
  Auld-Thomas 2022 — "A Recipe for Simple Red Relief".

Outputs (into the tile's derivative dir):
  rrim_<tile>_1m.tif    georeferenced 3-band uint8 RGB
  plus a downsampled preview PNG next to it for quick viewing.
"""
import argparse
import os
import sys
import numpy as np
import rasterio
from rasterio.enums import Resampling

sys.stdout.reconfigure(errors="replace")

# --- Simple Red Relief color stops (Auld-Thomas 2022), reused as the RRIM palette ---
TEAL = np.array([0, 158, 162], float)     # concave  (valley / pit)  -> depression tint
GRAY = np.array([138, 138, 138], float)   # flat
YELLOW = np.array([254, 255, 172], float) # convex   (ridge)         -> ridge tint
WHITE = np.array([255, 255, 255], float)  # slope 0  (flat)
RED = np.array([182, 39, 0], float)       # slope high (steep)       -> vivid red


def _read(path, out_shape=None):
    with rasterio.open(path) as ds:
        a = ds.read(1, out_shape=out_shape, resampling=Resampling.bilinear).astype("float32")
        a = np.where(a == ds.nodata, np.nan, a)
        return a, ds.profile


def _diverge(t, neg_color, pos_color, mid_color):
    """t in [-1,1] -> RGB via mid->neg (t<0) / mid->pos (t>0). Returns (...,3)."""
    t = t[..., None]
    lo = mid_color + (neg_color - mid_color) * (-t)   # t<0
    hi = mid_color + (pos_color - mid_color) * (t)    # t>=0
    return np.where(t < 0, lo, hi)


def build_rrim(tile_dir, tile, simple=False, slope_hi=40.0, do_pct=98.0,
               base_brightness=18.0, suffix="1m"):
    # Input filenames are `<name>_<tile>_<suffix>.tif` — suffix is "1m" for the
    # data_3x3 build, "05" for the native 0.5 m 9t stack (slope_9t_05.tif, etc.).
    slope, prof = _read(os.path.join(tile_dir, f"slope_{tile}_{suffix}.tif"))
    valid = np.isfinite(slope)

    if simple:
        # Local Relief Model base (Simple Red Relief). Prefer the 11-cell LRM.
        lrm_path = os.path.join(tile_dir, f"lrm_11_{tile}_{suffix}.tif")
        base_raw, _ = _read(lrm_path)
        dlim = np.nanpercentile(np.abs(base_raw), do_pct)
        t = np.clip(base_raw / dlim, -1, 1)
        base_label = "LRM-11 (Simple Red Relief)"
    else:
        op, _ = _read(os.path.join(tile_dir, f"openness_pos_{tile}_{suffix}.tif"))
        on, _ = _read(os.path.join(tile_dir, f"openness_neg_{tile}_{suffix}.tif"))
        do = (op - on) / 2.0                    # differential openness (deg)
        valid &= np.isfinite(op) & np.isfinite(on)
        dlim = np.nanpercentile(np.abs(do[np.isfinite(do)]), do_pct)
        t = np.clip(do / dlim, -1, 1)
        base_label = f"differential openness (±{dlim:.2f} deg)"

    t = np.nan_to_num(t, nan=0.0)
    base = _diverge(t, TEAL, YELLOW, GRAY) + base_brightness
    base = np.clip(base, 0, 255)

    # red slope overlay: 0 deg -> white, slope_hi -> vivid red
    u = np.clip(np.nan_to_num(slope, nan=0.0) / slope_hi, 0, 1)[..., None]
    slope_rgb = WHITE + (RED - WHITE) * u

    rrim = base * slope_rgb / 255.0             # multiply blend
    rrim = np.clip(rrim, 0, 255)
    rrim[~valid] = 255.0                        # nodata -> white
    rrim = rrim.astype("uint8")

    return rrim, prof, base_label, dlim, slope_hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", default="613590")
    ap.add_argument("--dir", default="data/derivatives/tiles/data_3x3/westernpa_d20/613590")
    ap.add_argument("--suffix", default="1m",
                    help="input resolution suffix, e.g. '1m' (data_3x3) or '05' (9t 0.5 m)")
    ap.add_argument("--simple", action="store_true", help="LRM base (Simple Red Relief)")
    ap.add_argument("--slope-hi", type=float, default=40.0)
    args = ap.parse_args()

    rrim, prof, base_label, dlim, shi = build_rrim(
        args.dir, args.tile, simple=args.simple, slope_hi=args.slope_hi,
        suffix=args.suffix)
    H, W, _ = rrim.shape
    base = "simple" if args.simple else "openness"
    out_tif = os.path.join(args.dir, f"rrim_{base}_{args.tile}_{args.suffix}.tif")

    prof.update(count=3, dtype="uint8", nodata=None, compress="deflate",
                predictor=2, tiled=True, blockxsize=512, blockysize=512, photometric="RGB")
    with rasterio.open(out_tif, "w", **prof) as ds:
        for b in range(3):
            ds.write(rrim[:, :, b], b + 1)
    sz = os.path.getsize(out_tif) / 1e6
    print(f"wrote {out_tif}  ({W}x{H}, {sz:.1f} MB)  base={base_label}  slope_hi={shi}")

    # preview PNG (downsampled) next to the tif
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        step = max(1, int(max(H, W) / 1600))
        prev = rrim[::step, ::step]
        fig, ax = plt.subplots(figsize=(9, 9))
        ax.imshow(prev)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"RRIM · {args.tile} ({args.suffix}) · {base_label}", fontsize=11)
        out_png = os.path.join(args.dir, f"rrim_{base}_{args.tile}_{args.suffix}_preview.png")
        fig.savefig(out_png, dpi=130, bbox_inches="tight")
        plt.close(fig)
        print(f"wrote {out_png}  ({prev.shape[1]}x{prev.shape[0]})")
    except Exception as e:
        print("preview skipped:", type(e).__name__, e)


if __name__ == "__main__":
    main()
