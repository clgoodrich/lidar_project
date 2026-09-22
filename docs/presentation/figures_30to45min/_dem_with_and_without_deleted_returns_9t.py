"""The bare-earth surface, built without and with the deleted returns.

WHAT THIS ANSWERS
-----------------
The data-QA section shows that returns were deleted, that they were good, and
that holes appear where they used to be. It never shows the thing that actually
matters downstream: **what the ground surface looks like either way.**

Both DEMs are 0.00% void, because a triangulated surface spans every gap by
construction. So the vendor-only DEM is not full of holes -- it is full of
*guesses*, straight-line interpolation across stripes up to a swath edge wide.
This figure puts the guess next to the measurement.

PANELS
------
    left    vendor ground only, hillshaded. The cells where the vendor had no
            ground at all are tinted, so you can see which parts of this
            surface are interpolation rather than measurement.
    middle  vendor ground plus the recovered returns, same hillshade, same
            stretch.
    right   new surface minus old, in centimetres.

WINDOW
------
Chosen by measurement, not by eye, and not on the obvious criterion. The
window with the MOST missing ground is 62.6% void, but the recovered returns
reach only 2.9% of its cells, so both surfaces look identical there. The script
instead maximises the share of cells that were void and are now measured, which
is the population this figure is about.

COLOUR
------
The difference panel is a diverging blue-to-orange ramp built from the repo's
validated pair, #1F5FA8 and #D97706 (worst pair dE 21.1 deutan, 22.6 normal).
No red/green pair appears anywhere, and the void class on the left panel is the
same orange, which is also labelled.

The left panel carries the only categorical split in the figure: measured
ground against no ground. It is encoded twice, because colour alone was not
enough at 52% coverage -- grey against orange, AND full contrast against
compressed contrast. The second cue means the split still reads in greyscale,
which is the worst case for any colour-vision deficiency.

Run:
    python docs/presentation/figures_30to45min/_dem_with_and_without_deleted_returns_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/dem_with_and_without_deleted_returns_9t.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import Patch
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
REC = ROOT / "data/9t/results/recovered_ground_9t"
OLD = REC / "dem_vendorground_9t_0p5m.tif"
NEW = REC / "dem_vendorplusrecovered_slope0p35_9t_0p5m.tif"
CNT = REC / "count_vendorground_9t_0p5m.tif"
RECCNT = REC / "count_recoveredground_slope0p35_9t_0p5m.tif"
OUT = (ROOT / "docs/presentation/figures_30to45min/v6"
       / "dem_with_and_without_deleted_returns_9t.png")

SIDE = 300.0
BLUE, ORANGE = "#1F5FA8", "#D97706"
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def hillshade(z, res=0.5, az=315.0, alt=45.0):
    """Standard hillshade, so both panels are lit identically."""
    gy, gx = np.gradient(z, res, res)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, z0 = np.radians(az), np.radians(alt)
    hs = (np.sin(z0) * np.cos(slope)
          + np.cos(z0) * np.sin(slope) * np.cos(a - aspect))
    return np.clip(hs, 0, 1)


def worst_window():
    """The window where the deleted returns do the most work.

    The obvious criterion -- most cells with no vendor ground -- picks the
    wrong place. The worst such window on this tile is 62.6% void, but the
    recovered returns only reach 2.9% of its cells, so the two surfaces are
    nearly identical there and the figure shows nothing.

    What matters is where a vendor void is actually FILLED by a recovered
    return, so that is what this maximises.
    """
    with rasterio.open(CNT) as cs, rasterio.open(RECCNT) as rs:
        step = 600                       # 300 m at 0.5 m cells
        best, where = -1.0, None
        for r in range(0, cs.height - step, step):
            for c in range(0, cs.width - step, step):
                win = ((r, r + step), (c, c + step))
                v = cs.read(1, window=win, masked=True).filled(0)
                g = rs.read(1, window=win, masked=True).filled(0)
                frac = float(((v <= 0) & (g > 0)).mean())
                if frac > best:
                    best, where = frac, (r, c)
        r, c = where
        x0, y1 = cs.xy(r, c, offset="ul")
        return (x0, y1 - SIDE, x0 + SIDE, y1), best


def read(path, b):
    with rasterio.open(path) as s:
        w = from_bounds(*b, transform=s.transform)
        a = s.read(1, window=w).astype("float32")
        nd = s.nodata
    if nd is not None:
        a[a == nd] = np.nan
    return a


def main() -> int:
    for p in (OLD, NEW, CNT, RECCNT):
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    b, frac = worst_window()
    old, new = read(OLD, b), read(NEW, b)
    cnt = read(CNT, b)
    novoid = np.nan_to_num(cnt, nan=0.0) <= 0
    diff = (new - old) * 100.0            # centimetres

    lo, hi = np.nanpercentile(hillshade(old), (2, 98))
    fig, axes = plt.subplots(1, 3, figsize=(16.4, 6.3))
    fig.patch.set_facecolor(PAPER)

    # A flat orange wash at alpha 0.30 over a grey hillshade did not read:
    # the void covers half the window, so the whole panel went warm and the
    # boundary between "measured" and "guessed" was invisible. Two changes.
    #
    #  1  hue is categorical, not a wash. Measured cells keep the plain grey
    #     hillshade. Void cells are rendered by multiplying the same shading
    #     through a normalised orange, which keeps the terrain readable but
    #     puts the two classes in different colour families.
    #  2  void cells also get their contrast compressed. That is a SECOND
    #     encoding, so the split survives without colour -- and it is honest,
    #     because an interpolated surface really does carry less detail than a
    #     measured one.
    hs = hillshade(old)
    hn = np.clip((hs - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
    rgb = np.repeat(hn[..., None], 3, axis=2)
    oc = np.asarray(mcolors.to_rgb(ORANGE), dtype="float32")
    oc = oc / oc.max()                       # normalise so it multiplies clean
    flat = 0.58 + (hn - 0.5) * 0.42          # compressed, slightly lifted
    warm = flat[..., None] * oc[None, None, :]
    rgb[novoid] = (0.85 * warm + 0.15 * np.repeat(flat[..., None], 3, axis=2)
                   )[novoid]
    axes[0].imshow(np.clip(rgb, 0, 1))
    axes[0].set_title("Vendor ground only\nthe surface as delivered",
                      loc="left", fontsize=15, fontweight="bold",
                      color=INK, pad=9)
    axes[0].set_xlabel(f"{novoid.mean()*100:.0f}% of this window had no ground "
                       "return at all", fontsize=12.5, color=ORANGE,
                       fontweight="bold")
    axes[0].legend(handles=[
        Patch(facecolor=ORANGE, edgecolor="none",
              label="no ground measured — interpolated"),
        Patch(facecolor="#9a9a9a", edgecolor="none",
              label="measured ground")],
        loc="upper right", fontsize=10.5, framealpha=0.94)

    axes[1].imshow(hillshade(new), cmap="gray", vmin=lo, vmax=hi)
    axes[1].set_title("Vendor ground plus the deleted returns\n"
                      "the same ground, measured",
                      loc="left", fontsize=15, fontweight="bold",
                      color=INK, pad=9)
    axes[1].set_xlabel("same hillshade, same stretch",
                       fontsize=12.5, color=MUTED, fontweight="bold")

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "bo", [BLUE, "#F2F2EE", ORANGE])
    v = float(np.nanpercentile(np.abs(diff), 99)) or 1.0
    im = axes[2].imshow(diff, cmap=cmap, vmin=-v, vmax=v)
    axes[2].set_title("What changed\nnew surface minus old",
                      loc="left", fontsize=15, fontweight="bold",
                      color=INK, pad=9)
    # Only the cells that were void AND are now measured are the population
    # this figure is about. Taking the median over every void cell dilutes it
    # with the ones the recovered returns never reached, which reads as 0 cm
    # and understates the change to nothing.
    reccnt = read(RECCNT, b)
    filled = novoid & (np.nan_to_num(reccnt, nan=0.0) > 0)
    med = float(np.nanmedian(np.abs(diff[filled]))) if filled.any() else 0.0
    p90 = float(np.nanpercentile(np.abs(diff[filled]), 90)) if filled.any() else 0.0
    axes[2].set_xlabel(f"where a void was filled: median {med:.0f} cm, "
                       f"90th percentile {p90:.0f} cm",
                       fontsize=12.5, color=MUTED, fontweight="bold")
    cb = fig.colorbar(im, ax=axes[2], fraction=0.046, pad=0.02)
    cb.set_label("centimetres", fontsize=11, color=MUTED)
    cb.ax.tick_params(labelsize=9.5, colors=MUTED)

    for ax in axes:
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")

    fig.suptitle("The bare-earth surface, without and with the deleted returns",
                 x=0.006, y=0.985, ha="left", va="top", fontsize=21,
                 fontweight="bold", color=INK)
    # No caption baked into the image: explanatory text belongs in the
    # slide's own left-hand column, not burned into the PNG where it
    # cannot be edited, re-wrapped or read at presentation size.
    fig.tight_layout(rect=(0, 0.055, 1, 0.94))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=155, facecolor=PAPER)
    plt.close(fig)
    print(f"  window {b[0]:.0f} E {b[1]:.0f} N, chosen on filled voids: "
          f"{frac*100:.1f}% of cells were void and are now measured")
    print(f"  median |change| where interpolated: {med:.1f} cm")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
