"""Corn rows in cross-section, with the rows taken from the hand digitisation.

WHERE THE ROW POSITIONS COME FROM
---------------------------------
`data/cornrows.gpkg` -- nine lines drawn by hand over the striping. Their
geometry is the ground truth here: the bearing, the spacing and the position of
every crest on the chart are read off those lines, not inferred from the
raster.

Measured from them, after reprojecting out of EPSG:4326 (bearings computed in
degrees of latitude and longitude are distorted and came out 3 deg wrong):

    bearing   79.31 deg, sd 0.36, range 78.86-79.98 over 9 lines
    spacing   median 3.35 m between adjacent rows
    extent    354 m of line, centred near 623463 E 4594787 N

THREE INDEPENDENT MEASUREMENTS THAT AGREE
-----------------------------------------
    79.31 deg   these hand-drawn lines
    79    deg   2-D FFT of the local relief raster over this window
    78    deg   the point cloud's own scan-line geometry, from GPS times and
                scan angles in the LAS file

The first is a person with a mouse, the second a spectrum of a downstream
raster, the third the sensor's recorded pointing. Nothing is shared between
them, so the agreement is real evidence that the striping follows the scan
lines.

Two earlier attempts at the direction are worth recording as failures. A
rotate-and-take-the-most-variable-profile sweep returned 100 deg (a two-sample
interpolation spike), then 173 deg (swath-scale banding, once the spike was
median-filtered out), then 13 deg (nothing dominant, once the banding was
high-passed away). Three answers from one method is a method problem. The FFT
gives one answer with a peak 13x the median across bearings.

WHY LRM
-------
Raw elevation across this ground drops metres while the ripple is under a
centimetre, so the corduroy is about one part in a thousand of the range and
invisible. Local relief is elevation minus a smoothed copy of itself, so the
hillside is already gone. It is also one of the seven channels the model reads.

Run:
    python docs/presentation/figures_30to45min/_cornrow_rows_measured_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/cornrow_rows_measured_9t.png
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[3]
LRM = ROOT / "data/9t/derived/05/lrm_5_9t_05.tif"
ROWS = ROOT / "data/cornrows.gpkg"
OUT = (ROOT / "docs/presentation/figures_30to45min/v6"
       / "cornrow_rows_measured_9t.png")

CRS = 6346
CELL = 0.5
PAD_M = 45.0                    # window padding around the drawn lines
SCAN_BEARING = 78.0             # from the point cloud's scan geometry

BLUE, ORANGE = "#1F5FA8", "#D97706"
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def axial_mean(bearings, weights):
    """Mean of undirected lines: average the DOUBLED angles, then halve."""
    th = np.radians(np.asarray(bearings) * 2.0)
    return (np.degrees(np.arctan2(np.average(np.sin(th), weights=weights),
                                  np.average(np.cos(th), weights=weights)))
            / 2.0) % 180.0


def main() -> int:
    for p in (LRM, ROWS):
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    # stored as MultiLineString; explode so each row is its own geometry
    g = gpd.read_file(ROWS).to_crs(CRS).explode(index_parts=False)
    bearings, lengths, mids = [], [], []
    for geom in g.geometry:
        c = np.asarray(geom.coords)
        dx, dy = c[-1, 0] - c[0, 0], c[-1, 1] - c[0, 1]
        bearings.append(np.degrees(np.arctan2(dx, dy)) % 180.0)
        lengths.append(float(np.hypot(dx, dy)))
        mids.append(c.mean(axis=0))
    bearings, lengths = np.array(bearings), np.array(lengths)
    mids = np.array(mids)
    bearing = axial_mean(bearings, lengths)

    b = np.radians(bearing)
    perp = np.array([np.cos(b), np.sin(b)])        # unit vector across rows
    row_s = np.sort(mids @ perp)
    gaps = np.diff(row_s)
    spacing = float(np.median(gaps))

    allc = np.vstack([np.asarray(gm.coords) for gm in g.geometry])
    cx, cy = allc[:, 0].mean(), allc[:, 1].mean()
    half = float(np.abs(allc - [cx, cy]).max()) + PAD_M
    bb = (cx - half, cy - half, cx + half, cy + half)

    with rasterio.open(LRM) as s:
        a = s.read(1, window=from_bounds(*bb, transform=s.transform))
        nd = s.nodata
    a = a.astype("float64")
    if nd is not None:
        a[a == nd] = np.nan
    a = np.nan_to_num(a, nan=float(np.nanmean(a)))

    # cross-strike profile: project every cell onto the across-rows axis
    n = a.shape[0]
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    E = bb[0] + (xx + 0.5) * CELL
    N = bb[3] - (yy + 0.5) * CELL
    s_all = E * perp[0] + N * perp[1]
    # Average only along the stretch the lines were actually drawn over.
    # Averaging the whole square instead pulls in ground the rows do not cross
    # and washes the ripple out -- it took the amplitude down to 0.85 cm and
    # left the drawn crests sitting on nothing in particular.
    along = np.array([-np.sin(b), np.cos(b)])      # unit vector along the rows
    u_all = E * along[0] + N * along[1]
    u_line = allc @ along
    band = (u_all >= u_line.min()) & (u_all <= u_line.max())

    s0 = s_all[band].min()
    idx = np.clip(((s_all[band] - s0) / CELL).astype(int), 0, None)
    nb = idx.max() + 1
    tot = np.bincount(idx, weights=a[band], minlength=nb)
    cnt = np.bincount(idx, minlength=nb)
    keep = cnt >= 0.35 * np.percentile(cnt, 90)    # drop thin end bins
    prof = np.where(cnt > 0, tot / cnt.clip(1), np.nan) * 100.0
    xs = np.arange(nb) * CELL
    xs, prof = xs[keep], prof[keep]
    prof = prof - ndimage.uniform_filter1d(prof, 61, mode="nearest")
    row_x = row_s - s0                   # drawn rows on the same axis

    fig, axes = plt.subplots(1, 2, figsize=(16.2, 6.4),
                             gridspec_kw=dict(width_ratios=[1, 1.45]))
    fig.patch.set_facecolor(PAPER)

    ax = axes[0]
    lo, hi = np.nanpercentile(a, (2, 98))
    ax.imshow(a, cmap="gray", vmin=lo, vmax=hi,
              extent=(bb[0], bb[2], bb[1], bb[3]))
    for geom in g.geometry:
        c = np.asarray(geom.coords)
        ax.plot(c[:, 0], c[:, 1], color=ORANGE, lw=2.2, alpha=0.95)
    ax.set_title("Local relief, 0.5 m, with the nine drawn rows",
                 loc="left", fontsize=15, fontweight="bold", color=INK, pad=9)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor("#c8c8c0")

    ax = axes[1]
    ax.plot(xs, prof, color=BLUE, lw=1.5)
    for i, r in enumerate(row_x):
        ax.axvline(r, color=ORANGE, lw=1.6, alpha=0.8,
                   label="drawn row" if i == 0 else None)
    ax.axhline(0, color="#c8c8c0", lw=1)
    ax.set_title("The same ground, cut across the rows",
                 loc="left", fontsize=15, fontweight="bold", color=INK, pad=9)
    ax.set_xlabel("distance across the rows, metres", fontsize=12,
                  color=MUTED)
    ax.set_ylabel("local relief, centimetres", fontsize=12, color=MUTED)
    ax.set_xlim(max(0, row_x.min() - 12), row_x.max() + 12)
    ax.legend(fontsize=11, framealpha=0.9, loc="upper right")
    ax.grid(axis="y", color="#e9e9e1", lw=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=10.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_edgecolor("#c8c8c0")

    fig.suptitle("Corn rows in cross-section, against the rows as drawn",
                 x=0.006, y=0.985, ha="left", va="top", fontsize=20,
                 fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.015, 1, 0.935))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=155, facecolor=PAPER)
    plt.close(fig)

    win = (xs >= row_x.min()) & (xs <= row_x.max())
    amp = float(np.percentile(prof[win], 95) - np.percentile(prof[win], 5))
    print(f"  {len(g)} drawn rows, {lengths.sum():.0f} m of line")
    print(f"  bearing   {bearing:6.2f} deg  (sd {bearings.std():.2f}, "
          f"scan geometry predicts {SCAN_BEARING:.0f})")
    print(f"  spacing   median {spacing:.2f} m, "
          f"gaps {gaps.min():.2f}-{gaps.max():.2f} m")
    print(f"  amplitude {amp:.2f} cm across the drawn extent (5-95%)")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
