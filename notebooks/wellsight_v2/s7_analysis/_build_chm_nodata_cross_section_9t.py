"""Cross-section across the CHM's scan-line NODATA bands, buffered along strike.

WHAT THE STREAKS ACTUALLY ARE
-----------------------------
The bright lines in `chm_300m_9t.png` are **NoData**, not canopy. Matplotlib
paints NaN as the figure background, which on this near-white paper reads as the
brightest thing in a black-to-white ramp. Every earlier attempt here hunted for
TALL pixels and therefore measured tree crowns:

    a 99.3-percentile CHM mask returned ZERO pixels in the open ground where the
      streaks are clearest
    the "on streak" point sample came back 95.8% single-return open ground
    a profile drawn along the marked strike found 0 spikes, DSM tracking DEM to
      within a metre over 128 m
    three automatic bearing estimates (129 / 135 / 139 deg) disagreed with the
      panel, because all three were built on masks of bright VALUES

Keyed on nodata instead, the pattern is unambiguous and matches the strike the
user measured off the panel by hand:

    nodata                     11,603 cells, 3.22% of the window
    pattern bearing            79.0 deg      (hand-measured strike 79.4 deg)
    bands                      26, median spacing 3.00 m

    TREAT THAT SPACING AS THRESHOLD-DEPENDENT, NOT AS A MEASUREMENT. A band
    faint enough to fall under the detector merges two gaps into one, so the
    figure moves with the threshold and with the extent -- 3.00 m over one
    window, 3.62 m over another, and the autocorrelation of the same profile
    has no clean periodic peak at all. The bearing is solid; the spacing is
    not. See `_measure_scanner_geometry_9t.py`.

So these are sweep lines where no first return was recorded at all: no DSM
value, so no CHM. Dropouts in the scan pattern rather than artifacts in it.

WHY THE BUFFER, AND WHY NOT nanmean
------------------------------------
A one-pixel transect across 3 m bands lands between them and under-reports
badly. Buffering ALONG the strike and reducing across gives ~25 samples per
across-position, which turns the gaps into a clean waveform.

The reduction must be the FRACTION OF CELLS THAT ARE NODATA. An earlier version
used `np.nanmean` over the band, which skips NaN by definition -- it filled the
gaps from their neighbours and averaged the signal out of existence. The thing
being measured is the absence, so the absence has to be what is counted.

Buffer width is bounded by strike error, not by preference. Over a 128 m
profile, a 0.4 deg strike error (the gap between 79.0 measured and 79.4 drawn)
drifts ~0.9 m, under a third of the 3.0 m spacing, so the bands stay separated.
A buffer much wider than the profile is long would not.

COLOUR
------
Sequential single-hue ramp for the map (magnitude, so lightness monotonic is the
check that applies). The profile carries three series from the dataviz reference
categorical slots 1/2/7:
    node scripts/validate_palette.js "#2a78d6,#eb6834,#4a3aa7" \
         --mode light --pairs all      -> ALL CHECKS PASS
    CVD worst #4a3aa7 <-> #2a78d6 dE 10.4 deutan; normal worst dE 16.3
No red, no green. Each series is directly labelled and sits on its own axis
range, so colour is never the only cue.

Run:
    python notebooks/wellsight_v2/s7_analysis/_build_chm_nodata_cross_section_9t.py
    ... --strike 79.4 --buffer-m 12.4 --half-m 40
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
from matplotlib.colors import LinearSegmentedColormap
from rasterio.windows import from_bounds
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
OUT = ROOT / "data/9t/results/chm_striping"
FIG = ROOT / "docs/presentation/figures_30to45min/2_terrain_derivatives"

PAPER, INK, INK2, MUTED, RULE = "#f7f8f6", "#141a1f", "#545c63", "#8a887e", "#c9ccc6"
C_GAP, C_DSM, C_DEM = "#4a3aa7", "#2a78d6", "#eb6834"
CM_SEQ = LinearSegmentedColormap.from_list(
    "seq", ["#f2f6fb", "#a8c6e6", "#4a87c8", "#1f5fa8", "#0d3057"])


def read_window(path, b, mask_below=-1000.0):
    with rasterio.open(path) as r:
        w = from_bounds(*b, transform=r.transform)
        a = r.read(1, window=w, boundless=True,
                   fill_value=np.nan).astype("float32")
    a[a < mask_below] = np.nan
    return a


def buffered_profile(arrays, reducers, bounds, res, x0, y0, across_deg,
                     half_m, buffer_m):
    """Sample a buffered band and reduce it per across-position.

    `across_deg` is the profile axis. The buffer is swept perpendicular to it,
    i.e. ALONG the strike, +-buffer_m/2. Each entry of `reducers` says how to
    collapse that band for the matching array: "nodata_frac" counts absence,
    "nanmean" averages the values present.
    """
    th = np.radians(across_deg)
    ax_dx, ax_dy = np.sin(th), np.cos(th)          # across
    bx, by = -ax_dy, ax_dx                          # along the strike
    offs = np.arange(-buffer_m / 2, buffer_m / 2 + res, res)
    s = np.arange(-half_m, half_m, res)

    stacks = [np.full((len(offs), len(s)), np.nan, np.float32) for _ in arrays]
    for i, o in enumerate(offs):
        X = x0 + o * bx + s * ax_dx
        Y = y0 + o * by + s * ax_dy
        c = (X - bounds[0]) / res - 0.5
        r = (bounds[3] - Y) / res - 0.5
        for a, st in zip(arrays, stacks):
            ny, nx = a.shape
            ok = (c >= 0) & (c < nx - 1) & (r >= 0) & (r < ny - 1)
            ci = np.clip(np.round(c), 0, nx - 1).astype(int)
            ri = np.clip(np.round(r), 0, ny - 1).astype(int)
            v = a[ri, ci].astype(np.float32)
            # NEAREST, not bilinear: bilinear interpolation across a NaN edge
            # spreads the gap into its neighbours and blurs the band boundary,
            # which is the measurement.
            v[~ok] = np.nan
            st[i] = v

    out = []
    for st, how in zip(stacks, reducers):
        if how == "nodata_frac":
            out.append(np.isnan(st).mean(axis=0))
        else:
            with np.errstate(invalid="ignore"):
                out.append(np.nanmean(st, axis=0))
    return s, out, len(offs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=float,
                    default=[41.49264, -79.546127])
    ap.add_argument("--side", type=float, default=300.0)
    ap.add_argument("--res", type=float, default=0.5)
    #: 79.4 deg is measured off the two yellow lines the user drew on the panel;
    #: the nodata pattern independently gives 79.0. Neither is estimated from a
    #: brightness mask, which is what went wrong three times before.
    ap.add_argument("--strike", type=float, default=79.4)
    ap.add_argument("--buffer-m", type=float, default=12.4)
    ap.add_argument("--half-m", type=float, default=40.0)
    ap.add_argument("--along", action="store_true",
                    help="profile ALONG the strike, on a band and off it, "
                         "instead of across")
    ap.add_argument("--along-buffer-m", type=float, default=1.0,
                    help="buffer for the along-strike profile; must stay well "
                         "under the 3 m band spacing or it straddles two bands")
    ap.add_argument("--along-half-m", type=float, default=55.0)
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
    print(f"window {a.side:.0f} m, {nx}x{ny} @ {a.res} m")
    print(f"  nodata {nod.sum():,} cells = {100*nod.mean():.2f}%")

    # anchor on the densest part of the nodata field, not on a guess
    rows, cols = np.where(nod)
    px = b[0] + (cols.mean() + 0.5) * a.res
    py = b[3] - (rows.mean() + 0.5) * a.res
    print(f"  nodata centroid {px:.1f} E {py:.1f} N "
          f"(frac {cols.mean()/nx:.3f} across, {rows.mean()/ny:.3f} down)")

    across = (a.strike + 90.0) % 180.0
    s, (gap, v_dsm, v_dem), nsamp = buffered_profile(
        [chm, dsm, dem], ["nodata_frac", "nanmean", "nanmean"],
        b, a.res, px, py, across, a.half_m, a.buffer_m)
    print(f"  profile across {across:.1f} deg, buffered {a.buffer_m:.1f} m "
          f"along {a.strike:.1f} deg -> {nsamp} samples per position")

    thr0 = np.radians(across)
    adx, ady = np.sin(thr0), np.cos(thr0)
    pk, _ = find_peaks(gap, height=0.25, distance=int(round(1.5 / a.res)))
    sp = float(np.median(np.diff(s[pk]))) if len(pk) >= 3 else None
    print(f"  {len(pk)} gap bands crossed, median spacing "
          f"{'n/a' if sp is None else f'{sp:.2f} m'}")
    print(f"  gap fraction: peak {gap.max():.2f}, mean {gap.mean():.2f}")


    if a.along:
        # Anchor on the strongest dropout found by the across-profile, then run
        # ALONG the strike from there. A second line is offset by half the band
        # spacing, so it sits BETWEEN bands. If these are continuous scan lines
        # the first stays empty end to end and the second stays full; if they
        # were random holes both would look alike.
        k = int(np.argmax(gap))
        on_x = px + s[k] * adx
        on_y = py + s[k] * ady
        half_sp = (sp or 3.0) / 2.0
        off_x = on_x + half_sp * adx
        off_y = on_y + half_sp * ady
        print(f"\n  ALONG mode: on-band anchor {on_x:.1f} E {on_y:.1f} N "
              f"(gap {gap[k]:.2f}), off-band anchor offset {half_sp:.2f} m")

        res_on = buffered_profile([chm, dsm, dem],
                                  ["nodata_frac", "nanmean", "nanmean"],
                                  b, a.res, on_x, on_y, a.strike,
                                  a.along_half_m, a.along_buffer_m)
        res_off = buffered_profile([chm, dsm, dem],
                                   ["nodata_frac", "nanmean", "nanmean"],
                                   b, a.res, off_x, off_y, a.strike,
                                   a.along_half_m, a.along_buffer_m)
        t_on, (g_on, d_on, e_on), n_on = res_on
        t_off, (g_off, d_off, e_off), n_off = res_off
        print(f"  on  band: mean gap {np.nanmean(g_on):.3f}, "
              f"{100*np.mean(g_on > 0.5):.1f}% of its length more than half empty")
        print(f"  off band: mean gap {np.nanmean(g_off):.3f}, "
              f"{100*np.mean(g_off > 0.5):.1f}%")

        fig2 = plt.figure(figsize=(18.0, 8.6))
        g2 = fig2.add_gridspec(2, 1, height_ratios=[1.0, 1.0], left=0.055,
                               right=0.982, top=0.780, bottom=0.085, hspace=0.30)
        axa = fig2.add_subplot(g2[0, 0])
        axa.fill_between(t_on, 0, g_on, color=C_GAP, alpha=0.30, zorder=3)
        axa.plot(t_on, g_on, color=C_GAP, linewidth=2.0, zorder=4,
                 label=f"on a dropout band  (mean {np.nanmean(g_on):.2f})")
        axa.plot(t_off, g_off, color=C_DSM, linewidth=2.0, zorder=5,
                 label=f"{half_sp:.1f} m to the side, between bands  "
                       f"(mean {np.nanmean(g_off):.2f})")
        axa.set_ylabel("fraction with no CHM value", fontsize=12)
        axa.set_ylim(-0.03, 1.05)
        axa.grid(color=RULE, linewidth=0.8)
        axa.set_axisbelow(True)
        for sp_ in ("top", "right"):
            axa.spines[sp_].set_visible(False)
        axa.legend(loc="center right", fontsize=11.5, framealpha=0.94,
                   facecolor="white", edgecolor=RULE)
        axa.set_title(
            f"A dropout band stays empty for its whole length — "
            f"{100*np.mean(g_on > 0.5):.0f}% of {2*a.along_half_m:.0f} m more "
            f"than half empty, against {100*np.mean(g_off > 0.5):.0f}% beside it",
            fontsize=13.5, fontweight="bold", loc="left", color=INK, pad=8)

        axb = fig2.add_subplot(g2[1, 0], sharex=axa)
        axb.plot(t_on, e_on, color=C_DEM, linewidth=2.2, zorder=5)
        axb.plot(t_on, d_on, color=C_DSM, linewidth=1.9, zorder=4)
        axb.set_xlabel(f"distance along the {a.strike:.1f}° strike, metres",
                       fontsize=12.5)
        axb.set_ylabel("elevation, m", fontsize=12)
        axb.grid(color=RULE, linewidth=0.8)
        axb.set_axisbelow(True)
        for sp_ in ("top", "right"):
            axb.spines[sp_].set_visible(False)
        axb.text(0.985, 0.88, "DSM", transform=axb.transAxes, ha="right",
                 color=C_DSM, fontsize=12, fontweight="bold")
        axb.text(0.985, 0.12, "DEM", transform=axb.transAxes, ha="right",
                 color=C_DEM, fontsize=12, fontweight="bold")
        axb.set_title("the surfaces on that same band — gaps in the DSM, "
                      "none in the bare earth",
                      fontsize=12.5, fontweight="bold", loc="left", color=INK,
                      pad=6)

        fig2.text(0.030, 0.972,
                  "Along the strike: the dropouts are continuous scan lines",
                  fontsize=24, fontweight="bold", color=INK, va="top")
        fig2.text(0.030, 0.900,
                  f"Same {a.strike:.1f}° strike, now profiled ALONG it "
                  f"rather than across. Buffer is {a.along_buffer_m:.1f} m, well "
                  f"under the {sp or 3.0:.1f} m band spacing, so the line stays "
                  f"inside one band instead of straddling two.\nThe second "
                  f"trace is the same profile shifted half a spacing sideways. "
                  f"Random holes would make the two look alike; a scan line "
                  f"makes one empty and the other full.",
                  fontsize=12.5, color=INK2, va="top", linespacing=1.55)

        p2 = FIG / f"chm_nodata_along_strike_b{a.strike:.0f}_300m_9t.png"
        fig2.savefig(p2, dpi=150)
        plt.close(fig2)
        jp2 = OUT / f"chm_nodata_along_strike_b{a.strike:.0f}_300m_9t.json"
        jp2.write_text(json.dumps(dict(
            strike_deg=a.strike, along_buffer_m=a.along_buffer_m,
            along_half_m=a.along_half_m, band_spacing_m=sp,
            on_band_anchor_en=[on_x, on_y], side_offset_m=half_sp,
            on_band_mean_gap=float(np.nanmean(g_on)),
            off_band_mean_gap=float(np.nanmean(g_off)),
            on_band_pct_over_half=float(100 * np.mean(g_on > 0.5)),
            off_band_pct_over_half=float(100 * np.mean(g_off > 0.5))),
            indent=2), encoding="utf-8")
        print(f"\n  {p2}\n  {jp2}")
        return 0

    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig = plt.figure(figsize=(18.4, 9.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.55],
                          height_ratios=[1.35, 1.0], left=0.030, right=0.978,
                          top=0.800, bottom=0.085, wspace=0.12, hspace=0.34)

    # map: nodata in the hue, everything else pale
    ax = fig.add_subplot(gs[:, 0])
    ax.imshow(np.where(nod, 1.0, 0.0), extent=[b[0], b[2], b[1], b[3]],
              origin="upper", cmap=CM_SEQ, vmin=0, vmax=1.35,
              interpolation="nearest")
    bx, by = -ady, adx
    for o in (-a.buffer_m / 2, a.buffer_m / 2):
        ax.plot([px + o * bx - a.half_m * adx, px + o * bx + a.half_m * adx],
                [py + o * by - a.half_m * ady, py + o * by + a.half_m * ady],
                color="#ffd400", linewidth=1.6, zorder=6,
                linestyle=(0, (5, 3)))
    ax.plot([px - a.half_m * adx, px + a.half_m * adx],
            [py - a.half_m * ady, py + a.half_m * ady],
            color="#ffd400", linewidth=2.8, zorder=7)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Where the CHM has no data", fontsize=13.5,
                 fontweight="bold", loc="left", color=INK, pad=7)
    ax.text(0.5, -0.028,
            f"profile {across:.0f}°, buffered {a.buffer_m:.1f} m along the "
            f"{a.strike:.1f}° strike",
            transform=ax.transAxes, ha="center", va="top", fontsize=11.5,
            color=INK2)

    axg = fig.add_subplot(gs[0, 1])
    axg.fill_between(s, 0, gap, color=C_GAP, alpha=0.30, zorder=3)
    axg.plot(s, gap, color=C_GAP, linewidth=2.0, zorder=4)
    axg.scatter(s[pk], gap[pk], s=34, facecolor="white", edgecolor=C_GAP,
                linewidth=1.6, zorder=6)
    axg.set_ylabel("fraction of the band with\nno CHM value", fontsize=12)
    axg.set_ylim(0, max(1.0, gap.max() * 1.15))
    axg.grid(color=RULE, linewidth=0.8)
    axg.set_axisbelow(True)
    for s_ in ("top", "right"):
        axg.spines[s_].set_visible(False)
    axg.set_title(
        f"{len(pk)} dropout bands" +
        (f", median spacing {sp:.1f} m" if sp else "") +
        f"  —  {nsamp} samples per position",
        fontsize=13.5, fontweight="bold", loc="left", color=INK, pad=8)

    axs = fig.add_subplot(gs[1, 1], sharex=axg)
    axs.plot(s, v_dsm, color=C_DSM, linewidth=1.9, zorder=4)
    axs.plot(s, v_dem, color=C_DEM, linewidth=2.2, zorder=5)
    for k in pk:
        axs.axvspan(s[k] - 0.75, s[k] + 0.75, color=C_GAP, alpha=0.12, zorder=1)
    axs.set_xlabel(f"distance across the bands, metres "
                   f"(profile bearing {across:.1f}°)", fontsize=12.5)
    axs.set_ylabel("elevation, m", fontsize=12)
    axs.grid(color=RULE, linewidth=0.8)
    axs.set_axisbelow(True)
    for s_ in ("top", "right"):
        axs.spines[s_].set_visible(False)
    axs.text(0.985, 0.90, "DSM", transform=axs.transAxes, ha="right",
             color=C_DSM, fontsize=12, fontweight="bold")
    axs.text(0.985, 0.14, "DEM", transform=axs.transAxes, ha="right",
             color=C_DEM, fontsize=12, fontweight="bold")
    axs.set_title("the surfaces through the same bands (shaded)", fontsize=12.5,
                  fontweight="bold", loc="left", color=INK, pad=6)

    fig.text(0.030, 0.972,
             "The corduroy in the canopy model is missing data, not canopy",
             fontsize=24, fontweight="bold", color=INK, va="top")
    fig.text(0.030, 0.912,
             f"The bright lines are NoData. Matplotlib paints NaN as the figure "
             f"background, which on this paper is the brightest thing in a "
             f"black-to-white ramp — so scan lines with no first return "
             f"read as tall canopy.\nThere is no DSM value there, so no CHM. "
             f"{nod.sum():,} cells, {100*nod.mean():.2f}% of the window, in "
             f"bands bearing 79.0° against the {a.strike:.1f}° strike "
             f"measured off the panel by hand.",
             fontsize=12.5, color=INK2, va="top", linespacing=1.55)

    FIG.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    p = FIG / f"chm_nodata_cross_section_buf{a.buffer_m:.0f}m_300m_9t.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    jp = OUT / f"chm_nodata_cross_section_buf{a.buffer_m:.0f}m_300m_9t.json"
    jp.write_text(json.dumps(dict(
        strike_deg=a.strike, profile_bearing_deg=across,
        buffer_m=a.buffer_m, samples_per_position=int(nsamp),
        half_m=a.half_m, anchor_en=[px, py],
        nodata_cells=int(nod.sum()), nodata_pct=float(100 * nod.mean()),
        bands_crossed=int(len(pk)), median_spacing_m=sp,
        peak_gap_fraction=float(gap.max())), indent=2), encoding="utf-8")
    print(f"\n  {p}\n  {jp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
