"""Is the corduroy in the CHM flight-line striping, or is it terrain?

WHY
---
The canopy-height panel in the talk shows a regular corrugation -- "corn rows"
-- over the 300 m derivative window. Every derivative panel is drawn from the
same `window_bounds()` in `_build_derivative_panel.py`, so it is not a framing
artifact: that pattern is in the data. The question is whether it is survey
geometry or ground.

CHM is the derivative where swath artifacts show worst, and there is a reason.
CHM = DSM - DEM. The DSM comes from first returns, whose density and look angle
vary systematically across a swath, and the subtraction stacks the DSM's
scan-pattern noise on top of the DEM's. Bare-earth products smooth theirs away;
the canopy product does not.

THE THREE CHECKS
----------------
1. **Orientation and wavelength**, from the 2D power spectrum of the detrended
   CHM. A flight-line artifact is periodic and directional; terrain roughness is
   not. This reports the dominant wavelength in metres and its bearing.
2. **Flight lines**, from `point_source_id` in the source LAZ. If the ridge
   spacing matches the flight-line spacing, or the ridges sit on the seams
   between lines, that is the swaths. This is the direct evidence.
3. **Ground density**, from `ground_density_9t_05.tif`. Density striping and CHM
   striping lining up is the same finding from the other direction, and it needs
   no point cloud.

Plus a **cross-section drawn perpendicular to the ridges**, which is the view
that shows the corrugation as an amplitude in metres rather than as a texture.
The transect is placed on the measured bearing from check 1, not by eye, and the
same transect is drawn through the CHM, the DSM, the DEM and the ground density
so it is visible which surface carries the ripple.

COLOUR
------
CHM and density are sequential (magnitude), so each gets a single-hue ramp.
Flight lines are categorical; the tile has few of them and they take the
validated dataviz categorical slots, checked --pairs all with the numbers
recorded beside the constant below. No red/green pair anywhere in the figure.

Run:
    python notebooks/wellsight_v2/s7_analysis/_test_chm_corduroy_striping_9t.py
    ... --side 300 --centre 41.49264 -79.546127
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
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
OUT = ROOT / "data/9t/results/chm_striping"
FIG = ROOT / "docs/presentation/figures_30to45min/2_terrain_derivatives"

PAPER, INK, INK2, MUTED, RULE = "#f7f8f6", "#141a1f", "#545c63", "#8a887e", "#c9ccc6"

#: Sequential, single hue, light->dark. Lightness is monotonic, which is the
#: check that applies to a magnitude ramp (not the categorical CVD checks).
CM_SEQ = LinearSegmentedColormap.from_list(
    "seq", ["#f2f6fb", "#a8c6e6", "#4a87c8", "#1f5fa8", "#0d3057"])
CM_AMP = LinearSegmentedColormap.from_list(
    "amp", ["#fdf3e7", "#f6c78a", "#e08a1e", "#a85c06", "#5c3103"])

#: Flight lines are categorical. dataviz reference slots 1/2/3/7, validated:
#:   node scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a,#4a3aa7" \
#:        --mode light --pairs all   -> ALL CHECKS PASS
#:   CVD worst #1baf7a<->#eb6834 dE 9.2 deutan / 9.6 tritan (target >= 8)
#:   normal-vision worst #4a3aa7<->#2a78d6 dE 16.3
#: No red present; the orange/aqua pair is the colourblind-safe substitute FOR
#: a red/green pair. Lines also carry a direct numeric label in the legend.
LINE_COLS = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7",
             "#8a887e", "#0d3057", "#a85c06", "#111111"]


def window_bounds(lat, lon, side):
    """Same centre and box the derivative panels use, recomputed here."""
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:6346", always_xy=True)
    x, y = tr.transform(lon, lat)
    h = side / 2.0
    return (x - h, y - h, x + h, y + h), (x, y)


def read_window(path, bounds):
    with rasterio.open(path) as r:
        w = from_bounds(*bounds, transform=r.transform)
        a = r.read(1, window=w, boundless=True, fill_value=np.nan).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = np.nan
    return a


# ---------------------------------------------------------------- check 1
def spectrum(a, res):
    """Dominant wavelength and bearing of the periodic component.

    The plane is removed first: a tilted surface puts all its power at the
    origin and drowns the periodic peak. The DC cell and its immediate
    neighbours are then masked, because a residual mean is not a stripe.
    """
    z = np.where(np.isfinite(a), a, np.nanmean(a))
    ny, nx = z.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    A = np.c_[xx.ravel(), yy.ravel(), np.ones(z.size)]
    coef, *_ = np.linalg.lstsq(A, z.ravel(), rcond=None)
    z = z - (A @ coef).reshape(z.shape)
    z *= np.outer(np.hanning(ny), np.hanning(nx))

    P = np.abs(np.fft.fftshift(np.fft.fft2(z))) ** 2
    fy = np.fft.fftshift(np.fft.fftfreq(ny, d=res))
    fx = np.fft.fftshift(np.fft.fftfreq(nx, d=res))
    FX, FY = np.meshgrid(fx, fy)
    rad = np.hypot(FX, FY)
    # ignore anything longer than a third of the window -- that is trend, and
    # anything shorter than 4 samples, which is pixel noise near Nyquist
    ok = (rad > 3.0 / (min(ny, nx) * res)) & (rad < 1.0 / (4 * res))
    Pm = np.where(ok, P, 0.0)

    k = np.unravel_index(np.argmax(Pm), Pm.shape)
    kfx, kfy = FX[k], FY[k]
    wavelength = 1.0 / np.hypot(kfx, kfy)
    # bearing of the WAVE VECTOR = direction of fastest change = across the
    # ridges. The ridges themselves run 90 deg from this.
    across = (np.degrees(np.arctan2(kfx, kfy))) % 180.0
    along = (across + 90.0) % 180.0
    # how peaked: the max against the median of the searched band
    band = Pm[ok]
    prom = float(Pm[k] / np.median(band[band > 0])) if np.any(band > 0) else np.nan
    return dict(wavelength_m=float(wavelength), across_bearing_deg=float(across),
                ridge_bearing_deg=float(along), peak_prominence=prom), P, (fx, fy)


# ---------------------------------------------------------------- check 2
def flight_lines(bounds, res):
    """Modal point_source_id per cell over the window, from the source LAZ."""
    import laspy
    l, b, r_, t = bounds
    nx = int(round((r_ - l) / res))
    ny = int(round((t - b) / res))
    grid = np.full((ny, nx), -1, np.int32)
    counts = {}
    hits = 0
    for f in sorted(SRC.glob("*.laz")):
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x >= l) & (x < r_) & (y >= b) & (y < t)
        if not m.any():
            continue
        hits += 1
        psid = np.asarray(las.point_source_id)[m].astype(np.int32)
        cx = ((x[m] - l) / res).astype(np.int64)
        cy = ((t - y[m]) / res).astype(np.int64)
        np.clip(cx, 0, nx - 1, out=cx)
        np.clip(cy, 0, ny - 1, out=cy)
        # last writer wins is fine: lines are spatially coherent blocks, and
        # the seam is what matters, not which line owns a contested cell
        grid[cy, cx] = psid
        for v, c in zip(*np.unique(psid, return_counts=True)):
            counts[int(v)] = counts.get(int(v), 0) + int(c)
    return grid, counts, hits


# ---------------------------------------------------------------- transect
def transect(a, res, bearing_deg, centre_frac=0.5, length_frac=0.92):
    """Sample a raster along a line through the centre on a given bearing.

    Bearing is the ACROSS-ridge direction from the spectrum, so the profile
    cuts the corrugation at right angles and its amplitude is the ripple depth.
    """
    ny, nx = a.shape
    cy, cx = ny * centre_frac, nx * centre_frac
    th = np.radians(bearing_deg)
    dx, dy = np.sin(th), -np.cos(th)
    half = length_frac * 0.5 * min(ny, nx)
    s = np.linspace(-half, half, int(2 * half))
    xs, ys = cx + s * dx, cy + s * dy
    ok = (xs >= 0) & (xs < nx - 1) & (ys >= 0) & (ys < ny - 1)
    xs, ys, s = xs[ok], ys[ok], s[ok]
    x0, y0 = xs.astype(int), ys.astype(int)
    fx, fy = xs - x0, ys - y0
    v = (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy)
         + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)
    return s * res, v, (xs, ys)


# ---------------------------------------------------------------- figure
def imshow(ax, a, ext, cm, title, vlo=2, vhi=98, cat=False, ncat=0):
    if cat:
        ax.imshow(a, extent=ext, origin="upper", cmap=cm, vmin=-0.5,
                  vmax=ncat - 0.5, interpolation="nearest")
    else:
        lo, hi = np.nanpercentile(a, [vlo, vhi])
        ax.imshow(a, extent=ext, origin="upper", cmap=cm, vmin=lo, vmax=hi,
                  interpolation="nearest")
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left", color=INK,
                 pad=6)
    ax.set_xticks([])
    ax.set_yticks([])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=float,
                    default=[41.49264, -79.546127])
    ap.add_argument("--side", type=float, default=300.0)
    ap.add_argument("--res", type=float, default=0.5)
    a = ap.parse_args()

    bounds, (cx, cy) = window_bounds(a.centre[0], a.centre[1], a.side)
    print(f"centre {cx:.1f} E, {cy:.1f} N   window {a.side:.0f} m")

    chm = read_window(D05 / "chm_9t_05.tif", bounds)
    dsm = read_window(D05 / "dsm_9t_05.tif", bounds)
    dem = read_window(D05 / "dem_9t_05.tif", bounds)
    den = read_window(D05 / "ground_density_9t_05.tif", bounds)
    print(f"  CHM {chm.shape}  {np.nanmin(chm):.2f}..{np.nanmax(chm):.2f} m")

    # ---- check 1
    res = {}
    for name, arr in (("chm", chm), ("dsm", dsm), ("dem", dem), ("density", den)):
        s, _, _ = spectrum(arr, a.res)
        res[name] = s
        print(f"  {name:8s} wavelength {s['wavelength_m']:6.2f} m   ridges bear "
              f"{s['ridge_bearing_deg']:5.1f} deg   peak/median "
              f"{s['peak_prominence']:.1f}")
    across = res["chm"]["across_bearing_deg"]

    # ---- check 2
    grid, counts, nfiles = flight_lines(bounds, a.res)
    ids = sorted(counts)
    print(f"  flight lines in window: {ids}  (from {nfiles} source tile(s))")
    for i in ids:
        print(f"    psid {i}: {counts[i]:,} points")
    lut = {v: k for k, v in enumerate(ids)}
    gshow = np.full(grid.shape, np.nan)
    for v, k in lut.items():
        gshow[grid == v] = k

    # ---- transects, all on the SAME line
    t_chm = transect(chm, a.res, across)
    t_dsm = transect(dsm, a.res, across)
    t_dem = transect(dem, a.res, across)
    t_den = transect(den, a.res, across)

    def ripple(v):
        """Amplitude of the corrugation: residual after a 15 m running mean."""
        w = max(3, int(round(15.0 / a.res)) | 1)
        k = np.ones(w) / w
        sm = np.convolve(np.nan_to_num(v, nan=np.nanmean(v)), k, mode="same")
        r = v - sm
        good = np.isfinite(r)
        edge = w // 2
        good[:edge] = False
        good[-edge:] = False
        return float(np.nanstd(r[good])), float(np.nanpercentile(np.abs(r[good]), 95))

    amps = {n: ripple(t[1]) for n, t in
            (("chm", t_chm), ("dsm", t_dsm), ("dem", t_dem), ("density", t_den))}
    print("\n  corrugation amplitude on the transect (sd, p95 |residual|)")
    for n, (sd, p95) in amps.items():
        print(f"    {n:8s} sd {sd:7.3f}   p95 {p95:7.3f}")

    # ---- figure
    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig = plt.figure(figsize=(19.0, 11.4))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.0, 0.82], left=0.028,
                          right=0.985, top=0.845, bottom=0.075, hspace=0.24,
                          wspace=0.10)
    ext = [bounds[0], bounds[2], bounds[1], bounds[3]]

    ax0 = fig.add_subplot(gs[0, 0])
    imshow(ax0, chm, ext, CM_SEQ, "Canopy height (CHM)")
    ax1 = fig.add_subplot(gs[0, 1])
    imshow(ax1, den, ext, CM_AMP, "Ground-return density")
    ax2 = fig.add_subplot(gs[0, 2])
    cm_cat = ListedColormap(LINE_COLS[:max(len(ids), 1)])
    imshow(ax2, gshow, ext, cm_cat, "Flight line (point_source_id)",
           cat=True, ncat=max(len(ids), 1))
    hs = [plt.Line2D([], [], marker="s", ls="", markersize=11,
                     color=LINE_COLS[k], label=f"line {v}")
          for v, k in lut.items()]
    ax2.legend(handles=hs, loc="lower left", fontsize=10, framealpha=0.92,
               facecolor="white", edgecolor=RULE)

    # the transect, drawn on every map so the line is unambiguous
    xs, ys = t_chm[2]
    wx = bounds[0] + xs * a.res
    wy = bounds[3] - ys * a.res
    for ax in (ax0, ax1, ax2):
        ax.plot(wx, wy, color="#ffffff", linewidth=3.2, zorder=6)
        ax.plot(wx, wy, color=INK, linewidth=1.5, zorder=7,
                linestyle=(0, (6, 3)))

    ax3 = fig.add_subplot(gs[0, 3])
    s, P, (fx, fy) = spectrum(chm, a.res)
    Pl = np.log10(P + 1e-9)
    ax3.imshow(Pl, origin="lower", cmap=CM_SEQ,
               extent=[fx[0], fx[-1], fy[0], fy[-1]],
               vmin=np.percentile(Pl, 55), vmax=np.percentile(Pl, 99.9))
    ax3.set_xlim(-0.12, 0.12)
    ax3.set_ylim(-0.12, 0.12)
    ax3.set_title("CHM power spectrum", fontsize=13, fontweight="bold",
                  loc="left", color=INK, pad=6)
    ax3.set_xlabel("cycles / m", fontsize=10.5)
    ax3.set_xticks([-0.1, 0, 0.1])
    ax3.set_yticks([-0.1, 0, 0.1])
    ax3.tick_params(labelsize=9.5)

    # profiles
    axp = fig.add_subplot(gs[1, :])
    d, v = t_chm[0], t_chm[1]
    axp.plot(d, v, color="#1f5fa8", linewidth=1.9, label="CHM (canopy height)")
    axp.set_xlabel(f"distance along the transect, metres "
                   f"(bearing {across:.0f} deg, perpendicular to the ridges)",
                   fontsize=12)
    axp.set_ylabel("canopy height, m", fontsize=12, color="#1f5fa8")
    axp.grid(color=RULE, linewidth=0.8)
    axp.set_axisbelow(True)
    axp.spines["top"].set_visible(False)
    axt = axp.twinx()
    axt.plot(t_den[0], t_den[1], color="#e08a1e", linewidth=1.5,
             label="ground-return density")
    axt.set_ylabel("ground returns per cell", fontsize=12, color="#a85c06")
    axt.tick_params(axis="y", colors="#a85c06")
    axt.spines["top"].set_visible(False)
    h1, l1 = axp.get_legend_handles_labels()
    h2, l2 = axt.get_legend_handles_labels()
    axp.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=11,
               framealpha=0.92, facecolor="white", edgecolor=RULE)
    axp.set_title(
        f"Cross-section, cut perpendicular to the ridges  -  CHM ripple "
        f"sd {amps['chm'][0]:.2f} m, p95 {amps['chm'][1]:.2f} m   |   "
        f"bare earth sd {amps['dem'][0]:.2f} m",
        fontsize=13.5, fontweight="bold", loc="left", color=INK, pad=8)

    strong = res["chm"]["peak_prominence"] > 6
    fig.text(0.028, 0.975,
             "The corduroy in the canopy model is survey geometry"
             if strong else
             "Is the corduroy in the canopy model flight-line striping?",
             fontsize=26, fontweight="bold", color=INK, va="top")
    fig.text(0.028, 0.918,
             f"Same {a.side:.0f} m window as every derivative panel, centred "
             f"{cx:.0f} E {cy:.0f} N (EPSG:6346). The dominant periodic "
             f"component of the CHM has a wavelength of "
             f"{res['chm']['wavelength_m']:.0f} m, ridges bearing "
             f"{res['chm']['ridge_bearing_deg']:.0f} deg.\nThe bare-earth DEM "
             f"over the same ground ripples at {amps['dem'][0]:.2f} m against "
             f"the canopy's {amps['chm'][0]:.2f} m. CHM = DSM minus DEM, so it "
             f"carries both surfaces' scan-pattern noise.",
             fontsize=13, color=INK2, va="top", linespacing=1.55)

    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / f"chm_corduroy_striping_{a.side:.0f}m_9t.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)

    j = OUT / f"chm_corduroy_striping_{a.side:.0f}m_9t.json"
    j.write_text(json.dumps(
        dict(centre_en=[cx, cy], side_m=a.side, res_m=a.res,
             spectrum=res, transect_bearing_deg=across,
             ripple_sd_p95=amps,
             flight_lines={str(k): v for k, v in counts.items()}),
        indent=2), encoding="utf-8")
    print(f"\n  {p}")
    print(f"  {j}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
