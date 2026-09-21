"""RRIM built from the vendor's clipped ground, and from the unclipped ground.

THE COMPARISON
--------------
Same window as the corn-row slide -- 240 m at 623822 E 4594949 N, 0.5 m cells.
Two surfaces, differing only in which ground returns went into them:

    vendor clipped    Classification[2:2] only. Everything past 18 deg of scan
                      angle was deleted before delivery. This is what every
                      model in the deck actually reads.
    unclipped         the same, plus the 13.7 M ground returns the survey
                      discarded, recovered and put back.

From each, the full Chiba red-relief recipe, computed identically so the only
difference is the input:

    Yokoyama positive and negative openness, 8 directions, 25 m radius
    differential openness (pos - neg) / 2, stretched to its own 98th percentile
    teal for concave, yellow for convex, grey flat
    multiplied by a white-to-red slope overlay, 0 to 40 deg

Both stretches are computed on the VENDOR panel and reused for the unclipped
one. Letting each panel pick its own would rescale the second image and hide
the very difference the figure is for.

A HALO IS READ AND THEN CUT
---------------------------
Openness searches 25 m in eight directions, so cells within 25 m of the window
edge would see off-window ground as infinitely far away and come out wrong. The
rasters are read 30 m larger all round and trimmed back after the derivation.

Run:
    python notebooks/wellsight_v2/s7_analysis/_rrim_vendor_vs_unclipped_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/rrim_vendor_vs_unclipped_9t.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks/wellsight_v2/s1_build"))
from _build_derivatives import openness            # noqa: E402

REC = ROOT / "data/9t/results/recovered_ground_9t"
CLIPPED = REC / "dem_vendorground_9t_0p5m.tif"
UNCLIPPED = REC / "dem_vendorplusrecovered_slope0p35_9t_0p5m.tif"
OUT = (ROOT / "docs/presentation/figures_30to45min/v6"
       / "rrim_vendor_vs_unclipped_9t.png")

#: the window the corn-row slide uses
CX, CY = 623822.4, 4594948.6
SIDE = 240.0
CELL = 0.5
HALO_M = 30.0
OPEN_RADIUS_M = 25.0
SLOPE_HI = 40.0
DO_PCT = 98.0
BASE_BRIGHTNESS = 18.0

TEAL = np.array([0, 158, 162], float)
GRAY = np.array([138, 138, 138], float)
YELLOW = np.array([254, 255, 172], float)
WHITE = np.array([255, 255, 255], float)
RED = np.array([182, 39, 0], float)

INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def read(path, b):
    with rasterio.open(path) as s:
        a = s.read(1, window=from_bounds(*b, transform=s.transform))
        nd = s.nodata
    a = a.astype("float32")
    if nd is not None:
        a[a == nd] = np.nan
    return a


def diverge(t, neg, pos, mid):
    t = t[..., None]
    lo = mid + (neg - mid) * (-t)
    hi = mid + (pos - mid) * t
    return np.where(t < 0, lo, hi)


def rrim_from(z, dlim=None):
    """Chiba red relief from a bare-earth surface. Returns (rgb, dlim)."""
    gy, gx = np.gradient(np.nan_to_num(z, nan=float(np.nanmean(z))), CELL, CELL)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    L = int(round(OPEN_RADIUS_M / CELL))
    op, on = openness(z, L_cells=L, cellsize=CELL)
    do = (op - on) / 2.0

    if dlim is None:
        dlim = float(np.nanpercentile(np.abs(do[np.isfinite(do)]), DO_PCT))
    t = np.nan_to_num(np.clip(do / dlim, -1, 1), nan=0.0)

    base = np.clip(diverge(t, TEAL, YELLOW, GRAY) + BASE_BRIGHTNESS, 0, 255)
    u = np.clip(np.nan_to_num(slope, nan=0.0) / SLOPE_HI, 0, 1)[..., None]
    rgb = np.clip(base * (WHITE + (RED - WHITE) * u) / 255.0, 0, 255)
    return rgb.astype("uint8"), dlim


def main() -> int:
    for p in (CLIPPED, UNCLIPPED):
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    h = SIDE / 2 + HALO_M
    bb = (CX - h, CY - h, CX + h, CY + h)
    trim = int(round(HALO_M / CELL))

    zc, zu = read(CLIPPED, bb), read(UNCLIPPED, bb)
    print(f"  window {SIDE:.0f} m at {CX:.0f} E {CY:.0f} N "
          f"(+{HALO_M:.0f} m halo for openness)")

    rgb_c, dlim = rrim_from(zc)
    rgb_u, _ = rrim_from(zu, dlim=dlim)         # same stretch, or no comparison
    cut = (slice(trim, -trim), slice(trim, -trim))
    rgb_c, rgb_u = rgb_c[cut], rgb_u[cut]
    dz = np.abs(zu - zc)[cut]

    fig, axes = plt.subplots(1, 2, figsize=(14.6, 7.6))
    fig.patch.set_facecolor(PAPER)
    for ax, rgb, title, sub in (
            (axes[0], rgb_c, "Vendor ground, as delivered",
             "everything past 18° scan angle deleted"),
            (axes[1], rgb_u, "With the deleted returns put back",
             "the same ground, nothing else changed")):
        ax.imshow(rgb)
        ax.set_title(f"{title}\n{sub}", loc="left", fontsize=16,
                     fontweight="bold", color=INK, pad=10)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")

    fig.suptitle("RRIM over the same ground, clipped and unclipped",
                 x=0.007, y=0.985, ha="left", va="top", fontsize=21,
                 fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.012, 1, 0.935))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=160, facecolor=PAPER)
    plt.close(fig)

    diff = np.abs(rgb_u.astype(int) - rgb_c.astype(int)).max(axis=2)
    print(f"  differential-openness stretch ±{dlim:.2f} deg, "
          f"shared by both panels")
    print(f"  surface differs in {np.mean(dz > 0.001) * 100:.1f}% of cells, "
          f"median |dz| {np.nanmedian(dz) * 100:.2f} cm")
    print(f"  RRIM pixels differing by >5/255: "
          f"{np.mean(diff > 5) * 100:.1f}%  (>20/255: "
          f"{np.mean(diff > 20) * 100:.1f}%)")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
