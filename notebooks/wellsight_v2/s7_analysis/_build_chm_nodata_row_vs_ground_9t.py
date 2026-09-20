"""One dropout row, along its length: the canopy surface against the ground.

The across-profile (`_build_chm_nodata_cross_section_9t.py`) establishes that
the bright corduroy in `chm_300m_9t.png` is NoData -- 21 bands at 3.00 m
spacing, bearing 79.0 deg against the 79.4 deg strike measured off the panel by
hand -- and the --along mode shows a band is empty for 38% of its length where
the line 1.5 m beside it is empty for 0%.

This is the view asked for after that: the ROW itself, drawn against the ground,
with CHM and DSM shown directly rather than summarised as a gap fraction.

WHY THE REDUCER MATTERS HERE
----------------------------
The buffer has to stay narrow -- 1 m against a 3 m band spacing -- or the line
straddles two rows. But `np.nanmean` over even a narrow buffer fills a gap from
whichever samples in it are present, which erases the very breaks being drawn.
So the surfaces use `nanmean_strict`: NaN out any position where more than half
the buffered samples are missing. The line then breaks where the data breaks,
which is what makes the row visible as a row.

WHAT EACH PANEL SHOWS
---------------------
    top     CHM on the row and CHM 1.5 m beside it -- half a band spacing away.
            The row breaks repeatedly; its neighbour does not.
    bottom  DSM against DEM on the row. The bare earth is continuous; the
            first-return surface is what has the holes. This is the mechanism:
            no first return on that sweep line, so no DSM, so no CHM.

COLOUR
------
dataviz reference categorical slots 1/2/7:
    node scripts/validate_palette.js "#2a78d6,#eb6834,#4a3aa7" \
         --mode light --pairs all      -> ALL CHECKS PASS
    CVD worst #4a3aa7 <-> #2a78d6 dE 10.4 deutan; normal-vision worst dE 16.3
No red and no green. Every series is directly labelled, and the missing spans
carry a shaded second encoding, so nothing rests on hue.

Run:
    python notebooks/wellsight_v2/s7_analysis/_build_chm_nodata_row_vs_ground_9t.py
    ... --strike 79.0 --half-m 55 --buffer-m 1.0
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
OUT = ROOT / "data/9t/results/chm_striping"
FIG = ROOT / "docs/presentation/figures_30to45min/2_terrain_derivatives"

PAPER, INK, INK2, MUTED, RULE = "#f7f8f6", "#141a1f", "#545c63", "#8a887e", "#c9ccc6"
C_ROW, C_SIDE, C_DEM = "#4a3aa7", "#2a78d6", "#eb6834"
GAPC = "#cfc9e8"


def read_window(path, b):
    with rasterio.open(path) as r:
        w = from_bounds(*b, transform=r.transform)
        a = r.read(1, window=w, boundless=True,
                   fill_value=np.nan).astype("float32")
    a[a < -1000.0] = np.nan
    return a


def band_sample(arrays, bounds, res, x0, y0, bearing_deg, half_m, buffer_m,
                strict=0.5):
    """Sample a narrow buffered band along `bearing_deg`.

    Returns, per array, the mean of the present samples EXCEPT where more than
    `strict` of the band is missing, which is returned as NaN so the drawn line
    breaks there. Also returns the per-position missing fraction.
    """
    th = np.radians(bearing_deg)
    ux, uy = np.sin(th), np.cos(th)
    bx, by = -uy, ux
    offs = np.arange(-buffer_m / 2, buffer_m / 2 + res, res)
    s = np.arange(-half_m, half_m, res)
    stacks = [np.full((len(offs), len(s)), np.nan, np.float32) for _ in arrays]
    for i, o in enumerate(offs):
        X = x0 + o * bx + s * ux
        Y = y0 + o * by + s * uy
        c = (X - bounds[0]) / res - 0.5
        r = (bounds[3] - Y) / res - 0.5
        for a, st in zip(arrays, stacks):
            ny, nx = a.shape
            ok = (c >= 0) & (c < nx - 1) & (r >= 0) & (r < ny - 1)
            ci = np.clip(np.round(c), 0, nx - 1).astype(int)
            ri = np.clip(np.round(r), 0, ny - 1).astype(int)
            v = a[ri, ci].astype(np.float32)
            v[~ok] = np.nan
            st[i] = v
    out, miss = [], None
    for st in stacks:
        frac = np.isnan(st).mean(axis=0)
        if miss is None:
            miss = frac
        with np.errstate(invalid="ignore"):
            m = np.nanmean(st, axis=0)
        m[frac > strict] = np.nan
        out.append(m)
    return s, out, miss, len(offs)


def shade_missing(ax, s, miss, thr=0.5):
    """Shade the spans where the row has no data, as a second encoding."""
    bad = miss > thr
    if not bad.any():
        return 0
    d = np.diff(bad.astype(int))
    starts = list(np.where(d == 1)[0] + 1)
    ends = list(np.where(d == -1)[0] + 1)
    if bad[0]:
        starts = [0] + starts
    if bad[-1]:
        ends = ends + [len(bad) - 1]
    for a0, a1 in zip(starts, ends):
        ax.axvspan(s[a0], s[a1], color=GAPC, alpha=0.75, zorder=1, lw=0)
    return len(starts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=float,
                    default=[41.49264, -79.546127])
    ap.add_argument("--side", type=float, default=300.0)
    ap.add_argument("--res", type=float, default=0.5)
    #: 79.0 is what the nodata pattern itself gives; 79.4 was measured off the
    #: user's drawn lines. They agree to 0.4 deg. The pattern's own value is the
    #: default here because it keeps the line on the band over a longer run.
    ap.add_argument("--strike", type=float, default=79.0)
    ap.add_argument("--buffer-m", type=float, default=1.0)
    ap.add_argument("--half-m", type=float, default=55.0)
    ap.add_argument("--search-m", type=float, default=40.0,
                    help="how far across the strike to hunt for the emptiest row")
    a = ap.parse_args()

    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:6346", always_xy=True)
    cx, cy = tr.transform(a.centre[1], a.centre[0])
    h = a.side / 2.0
    b = (cx - h, cy - h, cx + h, cy + h)

    chm = read_window(D05 / "chm_9t_05.tif", b)
    dsm = read_window(D05 / "dsm_9t_05.tif", b)
    dem = read_window(D05 / "dem_9t_05.tif", b)
    nod = ~np.isfinite(chm)
    ny, nx = chm.shape
    print(f"nodata {nod.sum():,} cells = {100*nod.mean():.2f}% of the window")

    # find the row: step across the strike from the nodata centroid and take the
    # offset whose along-line profile is emptiest.
    rows, cols = np.where(nod)
    ax0 = b[0] + (cols.mean() + 0.5) * a.res
    ay0 = b[3] - (rows.mean() + 0.5) * a.res
    th = np.radians(a.strike)
    vx, vy = np.cos(th), -np.sin(th)
    # Search wide, not just the nearest few bands. A +-6 m sweep around the
    # global nodata centroid found a row that was only 4.1% empty, because the
    # centroid is an average over the whole field and need not sit on a strong
    # row. +-40 m covers about 27 bands at the 3 m spacing.
    best = None
    for off in np.arange(-a.search_m, a.search_m + 0.01, 0.25):
        _, _, miss, _ = band_sample([chm], b, a.res, ax0 + off * vx,
                                    ay0 + off * vy, a.strike, a.half_m,
                                    a.buffer_m)
        # score on the fraction of the length that is properly empty, not the
        # raw mean, so a row that is decisively missing beats one that is
        # marginally thin everywhere.
        sc = float(np.mean(miss > 0.5))
        if best is None or sc > best[0]:
            best = (sc, float(off))
    _, off = best
    rx, ry = ax0 + off * vx, ay0 + off * vy
    print(f"  row found at {off:+.2f} m across the centroid -> {rx:.1f} E {ry:.1f} N")

    s, (c_row, d_row, e_row), miss_row, nsamp = band_sample(
        [chm, dsm, dem], b, a.res, rx, ry, a.strike, a.half_m, a.buffer_m)
    side = 1.5
    s2, (c_side, _, _), miss_side, _ = band_sample(
        [chm, dsm, dem], b, a.res, rx + side * vx, ry + side * vy,
        a.strike, a.half_m, a.buffer_m)
    print(f"  buffer {a.buffer_m:.1f} m -> {nsamp} samples per position")
    print(f"  on the row : missing {100*np.mean(miss_row > 0.5):.1f}% of "
          f"{2*a.half_m:.0f} m,  CHM present mean {np.nanmean(c_row):.2f} m")
    print(f"  {side:.1f} m aside: missing {100*np.mean(miss_side > 0.5):.1f}%,  "
          f"CHM present mean {np.nanmean(c_side):.2f} m")

    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, (axc, axd) = plt.subplots(
        2, 1, figsize=(18.2, 9.4), sharex=True,
        gridspec_kw=dict(height_ratios=[1.0, 1.25], hspace=0.16,
                         left=0.055, right=0.978, top=0.775, bottom=0.085))

    nspan = shade_missing(axc, s, miss_row)
    axc.plot(s2, c_side, color=C_SIDE, linewidth=1.7, zorder=4,
             label=f"{side:.1f} m to the side, between rows")
    axc.plot(s, c_row, color=C_ROW, linewidth=2.3, zorder=5,
             label="on the dropout row")
    axc.set_ylabel("canopy height, m", fontsize=12.5)
    axc.grid(color=RULE, linewidth=0.8, zorder=0)
    axc.set_axisbelow(True)
    for sp_ in ("top", "right"):
        axc.spines[sp_].set_visible(False)
    axc.legend(loc="upper right", fontsize=11.5, framealpha=0.95,
               facecolor="white", edgecolor=RULE)
    axc.set_title(
        f"Canopy height along the row — {nspan} separate breaks, "
        f"{100*np.mean(miss_row > 0.5):.0f}% of {2*a.half_m:.0f} m with no "
        f"value, against {100*np.mean(miss_side > 0.5):.0f}% beside it",
        fontsize=13.5, fontweight="bold", loc="left", color=INK, pad=8)

    shade_missing(axd, s, miss_row)
    axd.fill_between(s, e_row, d_row, where=np.isfinite(d_row),
                     color=C_SIDE, alpha=0.13, zorder=2)
    axd.plot(s, d_row, color=C_SIDE, linewidth=2.0, zorder=5)
    axd.plot(s, e_row, color=C_DEM, linewidth=2.4, zorder=6)
    axd.set_xlabel(f"distance along the row ({a.strike:.1f}° strike), metres",
                   fontsize=12.5)
    axd.set_ylabel("elevation, m", fontsize=12.5)
    axd.grid(color=RULE, linewidth=0.8, zorder=0)
    axd.set_axisbelow(True)
    for sp_ in ("top", "right"):
        axd.spines[sp_].set_visible(False)
    axd.text(0.986, 0.90, "DSM  first-return surface", transform=axd.transAxes,
             ha="right", color=C_SIDE, fontsize=12, fontweight="bold")
    axd.text(0.986, 0.10, "DEM  bare earth", transform=axd.transAxes,
             ha="right", color=C_DEM, fontsize=12, fontweight="bold")
    axd.set_title("the same row against the ground — the bare earth is "
                  "continuous, the first-return surface is not",
                  fontsize=13, fontweight="bold", loc="left", color=INK, pad=7)

    fig.text(0.030, 0.972, "One dropout row, end to end",
             fontsize=25, fontweight="bold", color=INK, va="top")
    fig.text(0.030, 0.905,
             f"Shaded spans are where the row has no CHM value. Buffer is "
             f"{a.buffer_m:.1f} m against a 3.0 m band spacing, so the line "
             f"stays inside one row; a position is drawn as a break when more "
             f"than half of its\n{nsamp} buffered samples are missing, rather "
             f"than averaged from whichever survive. Window centred "
             f"{cx:.0f} E {cy:.0f} N, EPSG:6346.",
             fontsize=12.5, color=INK2, va="top", linespacing=1.55)

    FIG.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    p = FIG / f"chm_nodata_row_vs_ground_b{a.strike:.0f}_300m_9t.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    jp = OUT / f"chm_nodata_row_vs_ground_b{a.strike:.0f}_300m_9t.json"
    jp.write_text(json.dumps(dict(
        strike_deg=a.strike, buffer_m=a.buffer_m, half_m=a.half_m,
        samples_per_position=int(nsamp), row_anchor_en=[rx, ry],
        row_offset_from_centroid_m=off, side_offset_m=side,
        row_missing_pct=float(100 * np.mean(miss_row > 0.5)),
        side_missing_pct=float(100 * np.mean(miss_side > 0.5)),
        n_breaks=int(nspan),
        row_chm_mean_present=float(np.nanmean(c_row)),
        side_chm_mean_present=float(np.nanmean(c_side))), indent=2),
        encoding="utf-8")
    print(f"\n  {p}\n  {jp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
