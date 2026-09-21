"""What a corn row looks like in cross-section, at centimetre scale.

THE PROBLEM WITH A RAW ELEVATION PROFILE
----------------------------------------
Cutting a line across the corn rows and plotting the DEM gives you a hillside.
The ground drops several metres over 60 m, and the corduroy is a few
centimetres on top of that, so it is invisible -- about one part in a hundred
of the vertical range.

Two ways to see it, both shown here:

  detrended DEM   the elevation profile with a smooth fit subtracted, leaving
                  only the short-wavelength residual. This is the raw
                  measurement with the hillside taken out, and it is the
                  honest answer to "what does the data actually do".

  LRM             the Local Relief Model, which IS that subtraction, done as a
                  raster: elevation minus a smoothed copy of itself. It is
                  already in the model's input stack, so this profile is
                  literally one row of a channel the network sees.

They should agree. Showing both is the check.

WHY A STACKED MEAN AS WELL
--------------------------
One transect carries the corduroy plus everything else at that spot -- a root,
a rut, a stone. Averaging many parallel transects cancels what is not periodic
and leaves what is. If the corduroy is real and regular, the stacked profile
keeps its ripple while the single profile looks noisier. If the ripple
disappears under averaging, it was never periodic.

GEOMETRY, AND WHAT THE CONTROL ACTUALLY SHOWED
----------------------------------------------
The corn rows run at 78 deg, so the transect runs at 168 deg -- straight across
them. The control is the same measurement ALONG the rows, at 78 deg, stacked
the same way over the same number of lines.

The expectation written here first was that the along-rows control would show
"almost nothing". **It does not.** Stacked over 81 lines, both directions come
out at roughly the same few-centimetre amplitude. So at this spot, in the
elevation model, a cross-section does not isolate a directional ripple -- what
it shows is ground roughness and measurement noise of the same size.

That is worth stating rather than hiding: the corduroy is plain in the
shape-derived layers and is not separable by direction in a bare elevation
profile.

Run:
    python docs/presentation/figures_30to45min/_cornrow_cross_section_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/cornrow_cross_section_9t.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
DEM = D05 / "dem_9t_05.tif"
LRM = D05 / "lrm_5_9t_05.tif"
RRIM = D05 / "rrim_openness_9t_05.tif"
OUT = (ROOT / "docs/presentation/figures_30to45min/v6"
       / "cornrow_cross_section_9t.png")

#: the spot the striping was reported at by eye
CX, CY = 623822.4, 4594948.6
ROW_BEARING = 78.0          # measured bearing of the scan lines / corn rows
LEN_M = 60.0                # transect length
STEP_M = 0.25               # sample spacing, half the cell size
N_STACK = 81                # parallel transects for the stacked mean
STACK_SPACING = 0.5

BLUE, ORANGE = "#1F5FA8", "#D97706"
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def sample(path, xs, ys):
    with rasterio.open(path) as s:
        vals = np.array([v[0] for v in s.sample(np.c_[xs, ys])],
                        dtype="float32")
        nd = s.nodata
    if nd is not None:
        vals[vals == nd] = np.nan
    return vals


def line(cx, cy, bearing_deg, length, step):
    """Points along a line of the given map bearing, centred on (cx, cy)."""
    b = np.radians(bearing_deg)
    dx, dy = np.sin(b), np.cos(b)
    t = np.arange(-length / 2, length / 2 + step, step)
    return cx + t * dx, cy + t * dy, t


TREND_WIN_M = 12.0
#: the reflect-pad makes the detrended residual unreliable within half a
#: smoothing window of each end. Those edges swung +/-30 cm and dominated the
#: y-scale, hiding the few centimetres the figure is about, so they are cut.
TRIM_M = TREND_WIN_M / 2


def detrend(t, z, win_m=TREND_WIN_M):
    """Subtract a smooth fit, leaving the short-wavelength residual."""
    k = max(3, int(round(win_m / (t[1] - t[0]))) | 1)
    pad = k // 2
    zp = np.pad(z, pad, mode="reflect")
    ker = np.ones(k) / k
    sm = np.convolve(zp, ker, mode="valid")
    return z - sm


def trim(t, *arrays):
    """Drop the edges the detrend cannot be trusted on."""
    m = np.abs(t) <= (t.max() - TRIM_M)
    return (t[m],) + tuple(a[m] for a in arrays)


def main() -> int:
    for p in (DEM, LRM, RRIM):
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    across = (ROW_BEARING + 90.0) % 360.0

    xs, ys, t = line(CX, CY, across, LEN_M, STEP_M)
    dem = sample(DEM, xs, ys)
    lrm = sample(LRM, xs, ys)
    dem_res = detrend(t, dem) * 100.0            # cm
    lrm_cm = lrm * 100.0

    # control: the same length ALONG the rows, where there should be no ripple
    ax_, ay_, t_al = line(CX, CY, ROW_BEARING, LEN_M, STEP_M)
    along_res = detrend(t_al, sample(DEM, ax_, ay_)) * 100.0

    def stack_along(profile_bearing, offset_bearing):
        """Mean of N parallel profiles, stepped perpendicular to themselves."""
        ob = np.radians(offset_bearing)
        off = (np.arange(N_STACK) - N_STACK // 2) * STACK_SPACING
        rows = []
        for o in off:
            ox, oy = CX + o * np.sin(ob), CY + o * np.cos(ob)
            sx, sy, st = line(ox, oy, profile_bearing, LEN_M, STEP_M)
            z = sample(DEM, sx, sy)
            if np.isfinite(z).all():
                rows.append(detrend(st, z) * 100.0)
        return np.nanmean(np.array(rows), axis=0), len(rows)

    # Stack BOTH directions. Comparing an 81-line average against a single
    # line is not a test of anything -- averaging alone cuts noise by sqrt(81).
    # Stacking both ways makes the only difference the direction, which is the
    # question: is the ripple directional, or is the ground just rough?
    stacked, n_across = stack_along(across, ROW_BEARING)
    stacked_along, n_along = stack_along(ROW_BEARING, across)
    stack = [0] * n_across

    # cut the untrustworthy ends off everything, consistently
    t, dem_res, lrm_cm = trim(t, dem_res, lrm_cm)
    t_al, along_res = trim(t_al, along_res)
    _, stacked_along = trim(
        np.arange(-LEN_M / 2, LEN_M / 2 + STEP_M, STEP_M)[:len(stacked_along)],
        stacked_along)
    _, stacked = trim(np.arange(-LEN_M / 2, LEN_M / 2 + STEP_M, STEP_M)[:len(stacked)],
                      stacked)

    # --- the map, for context -------------------------------------------
    half = LEN_M / 2 + 10
    bb = (CX - half, CY - half, CX + half, CY + half)
    with rasterio.open(RRIM) as s:
        rr = s.read(window=from_bounds(*bb, transform=s.transform))[:3]
    rr = rr.astype("float32")
    if rr.max() > 1.5:
        rr /= 255.0
    rr = np.clip(np.moveaxis(rr, 0, -1), 0, 1)

    fig = plt.figure(figsize=(15.2, 7.6))
    fig.patch.set_facecolor(PAPER)
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.65], hspace=0.38,
                          wspace=0.16)

    axm = fig.add_subplot(gs[:, 0])
    axm.imshow(rr, extent=(bb[0], bb[2], bb[1], bb[3]))
    axm.plot(xs, ys, color=ORANGE, lw=2.6)
    axm.plot(ax_, ay_, color=BLUE, lw=1.8, ls=(0, (5, 3)))
    axm.set_title("RRIM, 0.5 m\nthe two transects",
                  loc="left", fontsize=14, fontweight="bold", color=INK, pad=8)
    axm.set_xticks([]); axm.set_yticks([])
    axm.legend(handles=[
        plt.Line2D([], [], color=ORANGE, lw=2.6,
                   label=f"across the rows ({across:.0f}°)"),
        plt.Line2D([], [], color=BLUE, lw=1.8, ls=(0, (5, 3)),
                   label=f"along the rows ({ROW_BEARING:.0f}°)")],
        loc="lower center", fontsize=10.5, framealpha=0.92)

    ax1 = fig.add_subplot(gs[0, 1])
    ax1.plot(t, dem_res, color=ORANGE, lw=1.7,
             label="elevation, hillside removed")
    ax1.plot(t, lrm_cm, color=BLUE, lw=1.4, alpha=0.85,
             label="LRM (5-cell), the same thing as a raster")
    ax1.axhline(0, color="#c8c8c0", lw=1)
    ax1.set_title("One line across the corn rows",
                  loc="left", fontsize=14, fontweight="bold", color=INK, pad=8)
    ax1.set_ylabel("centimetres", fontsize=11.5, color=MUTED)
    ax1.legend(fontsize=10, loc="upper right", framealpha=0.9)

    ax2 = fig.add_subplot(gs[1, 1], sharex=ax1)
    ax2.plot(t, stacked, color=ORANGE, lw=2.2,
             label=f"mean of {n_across} lines ACROSS the rows")
    ax2.plot(t_al, stacked_along, color=BLUE, lw=1.8, alpha=0.85,
             label=f"mean of {n_along} lines ALONG the rows")
    ax2.axhline(0, color="#c8c8c0", lw=1)
    ax2.set_title("Same averaging, both directions",
                  loc="left", fontsize=14, fontweight="bold", color=INK, pad=8)
    ax2.set_xlabel("distance along the transect, metres",
                   fontsize=11.5, color=MUTED)
    ax2.set_ylabel("centimetres", fontsize=11.5, color=MUTED)
    ax2.legend(fontsize=10, loc="upper right", framealpha=0.9)

    for ax in (ax1, ax2):
        ax.grid(axis="y", color="#e9e9e1", lw=0.9)
        ax.set_axisbelow(True)
        ax.tick_params(colors=MUTED, labelsize=10)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_edgecolor("#c8c8c0")

    span = lambda a: float(np.nanpercentile(a, 95) - np.nanpercentile(a, 5))
    amp, one = span(stacked), span(dem_res)
    amp_al = span(stacked_along)
    fig.suptitle("What a corn row looks like in cross-section",
                 x=0.006, y=0.985, ha="left", va="top", fontsize=21,
                 fontweight="bold", color=INK)
    # No caption baked into the image: explanatory text belongs in the
    # slide's own left-hand column, not burned into the PNG where it
    # cannot be edited, re-wrapped or read at presentation size.
    fig.tight_layout(rect=(0, 0.045, 1, 0.945))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=155, facecolor=PAPER)
    plt.close(fig)

    print(f"  transect across the rows at {across:.0f} deg")
    print(f"  single line            5-95% span {one:5.1f} cm")
    print(f"  stacked ACROSS ({n_across})    5-95% span {amp:5.1f} cm")
    print(f"  stacked ALONG  ({n_along})    5-95% span {amp_al:5.1f} cm")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
