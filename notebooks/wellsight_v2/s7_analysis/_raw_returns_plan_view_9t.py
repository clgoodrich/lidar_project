"""The raw returns over 9t, looking straight down, on the same ground as
`ground_thrown_away_9t.png`.

WHY
---
`ground_thrown_away_9t.png` shows the ground the vendor discarded, as a density
of recovered points. It is a derived product, and three orange bands on a pale
sheet do not tell a reader what the delivery itself looks like. This puts the
raw returns beside it, over exactly the same 4.5 km square, so the bands can be
found in the data rather than taken on trust.

TWO PANELS
----------
LEFT   every return, all classes, all angles -- the delivery as flown. Density
       per square metre at 5 m. The flight lines are visible as the brighter
       ribbons: that is where two passes overlap and the coverage doubles.
LEFT is deliberately NOT the discard map recoloured. It is total coverage, so a
band on it means "more data here", the opposite of what a band on the discard
map means. A reader who sees them side by side and reads both as the same thing
has been misled by the figure, which is why the captions say it plainly.

RIGHT  a 300 m window inside one of those bands, every return drawn as a point,
       coloured by whether the vendor's 18 degree rule threw it out of the
       ground class. Chosen by the data: the window holding the most discarded
       returns, not one picked by eye.

EXTENT comes from dem_9t_05.tif so the square matches the other 9t products
exactly, rather than being typed in.

Run:
    python notebooks/wellsight_v2/s7_analysis/_raw_returns_plan_view_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/raw_returns_plan_view_9t.png
"""
from __future__ import annotations

from pathlib import Path

import laspy
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
NPZ = (ROOT / "data/9t/results/nonground_classification"
       / "cut_returns_and_voids_9t_5m.npz")
FIG = ROOT / "docs/presentation/figures_30to45min/v6"

#: Venango 2020-03 stopped calling returns ground past this angle.
CUT_DEG = 18.0
#: LAS 1.4 point format 6 stores scan angle in 0.006 degree units.
SCALE = 0.006
#: Side of the detail window, metres.
ZOOM = 300.0

#: Validated lost/found palette. No green here, so the binding constraint is
#: that kept and discarded stay separable: #1F5FA8 against #D97706, worst pair
#: dE 21.1 deutan, 22.6 normal. Discarded also gets the denser, brighter draw
#: order, so it is never carried by colour alone.
C_KEPT, C_CUT = "#1F5FA8", "#D97706"
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def laz_files():
    seen, out = set(), []
    for d in ("data/_source/lidar/westernpa",
              "data/_source/lidar/westernpa/OTHER_DATA"):
        for f in sorted((ROOT / d).glob("*.laz")):
            if ".copc." in f.name or f.name in seen:
                continue
            seen.add(f.name)
            out.append(f)
    return out


def main() -> int:
    with rasterio.open(D05 / "dem_9t_05.tif") as r:
        B = tuple(r.bounds)
    print(f"extent {B[0]:.0f} {B[1]:.0f} {B[2]:.0f} {B[3]:.0f}  "
          f"({(B[2]-B[0])/1000:.1f} x {(B[3]-B[1])/1000:.1f} km)")

    with np.load(NPZ) as d:
        n_all, n_cut, G = d["n_all"], d["n_cut"], float(d["grid"])
        nb = tuple(d["bounds"])
    assert np.allclose(nb, B, atol=1.0), (nb, B)
    dens = n_all / (G * G)
    print(f"  raw returns {int(n_all.sum()):,}, "
          f"median {np.median(dens[dens>0]):.2f} per m2")

    # the 300 m window holding the most discarded returns, chosen by the data
    k = int(round(ZOOM / G))
    ny, nx = n_cut.shape
    cs = np.cumsum(np.cumsum(n_cut, axis=0), axis=1)
    cs = np.pad(cs, ((1, 0), (1, 0)))
    box = (cs[k:, k:] - cs[:-k, k:] - cs[k:, :-k] + cs[:-k, :-k])
    r0, c0 = np.unravel_index(int(np.argmax(box)), box.shape)
    zx0 = B[0] + c0 * G
    zy1 = B[3] - r0 * G
    zb = (zx0, zy1 - ZOOM, zx0 + ZOOM, zy1)
    print(f"  detail window {zb[0]:.0f} {zb[1]:.0f} {zb[2]:.0f} {zb[3]:.0f}"
          f"  ({int(box.max()):,} discarded returns)")

    X, Y, A = [], [], []
    for f in laz_files():
        with laspy.open(f) as rd:
            lo, hi = rd.header.mins, rd.header.maxs
        if lo[0] > zb[2] or hi[0] < zb[0] or lo[1] > zb[3] or hi[1] < zb[1]:
            continue
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x >= zb[0]) & (x < zb[2]) & (y >= zb[1]) & (y < zb[3])
        if not m.any():
            continue
        X.append(x[m]); Y.append(y[m])
        A.append(np.abs(np.asarray(las.scan_angle)[m].astype("float32")*SCALE))
    x = np.concatenate(X); y = np.concatenate(Y); a = np.concatenate(A)
    cut = a >= CUT_DEG
    print(f"  {len(x):,} returns in the detail window, "
          f"{int(cut.sum()):,} past the cut ({100*cut.mean():.1f}%)")

    draw(B, dens, zb, x, y, cut, G)
    return 0


def draw(B, dens, zb, x, y, cut, G):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Rectangle
    from matplotlib.lines import Line2D

    fig, axes = plt.subplots(1, 2, figsize=(14.6, 8.2))
    fig.patch.set_facecolor(PAPER)

    # ---- left: coverage over the whole square --------------------------
    ax = axes[0]
    ax.set_facecolor("#ffffff")
    ramp = LinearSegmentedColormap.from_list("d", ["#ffffff", "#2B2F36"])
    vmax = float(np.percentile(dens[dens > 0], 98))
    ax.imshow(np.where(dens > 0, dens, np.nan),
              extent=(B[0], B[2], B[1], B[3]), origin="upper",
              cmap=ramp, vmin=0, vmax=vmax, interpolation="nearest")
    ax.add_patch(Rectangle((zb[0], zb[1]), zb[2]-zb[0], zb[3]-zb[1],
                           fill=False, edgecolor=C_CUT, linewidth=2.4,
                           zorder=5))
    ax.annotate("detail, right", xy=(zb[2], zb[3]),
                xytext=(zb[2] + 260, zb[3] + 420), fontsize=12.5,
                fontweight="bold", color=C_CUT,
                arrowprops=dict(arrowstyle="->", color=C_CUT, lw=1.8))
    ax.set_title("Every return, looking straight down",
                 loc="left", fontsize=15, fontweight="bold", color=INK)
    ax.set_xlabel("the same 4.5 km square as ground_thrown_away_9t.png\n"
                  f"darker is denser, up to {vmax:.0f} returns per "
                  "m²", fontsize=11.5, color=MUTED)

    # 1 km scale bar
    x0 = B[0] + 250
    yb = B[1] + 260
    ax.plot([x0, x0 + 1000], [yb, yb], color=INK, lw=3.4, zorder=6)
    ax.text(x0 + 500, yb + 90, "1 km", ha="center", fontsize=12,
            fontweight="bold", color=INK, zorder=6)

    # ---- right: the raw points -----------------------------------------
    ax = axes[1]
    ax.set_facecolor("#ffffff")
    ax.scatter(x[~cut], y[~cut], s=0.10, c=C_KEPT, linewidths=0, alpha=0.55)
    ax.scatter(x[cut], y[cut], s=0.16, c=C_CUT, linewidths=0, alpha=0.85)
    ax.set_xlim(zb[0], zb[2]); ax.set_ylim(zb[1], zb[3])
    ax.set_title(f"{int(zb[2]-zb[0])} m of it, one dot per return",
                 loc="left", fontsize=15, fontweight="bold", color=INK)
    ax.set_xlabel(f"{len(x):,} returns\n"
                  f"{100*cut.mean():.0f}% past the {CUT_DEG:.0f}° cut, "
                  "so never called ground", fontsize=11.5, color=MUTED)
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", markersize=7, color=C_KEPT,
               label="kept — inside the vendor's angle rule"),
        Line2D([], [], marker="o", ls="", markersize=7, color=C_CUT,
               label=f"discarded — past {CUT_DEG:.0f}°")],
        loc="upper right", fontsize=11, frameon=True, framealpha=0.95)
    x0 = zb[0] + 18
    yb = zb[1] + 18
    ax.plot([x0, x0 + 50], [yb, yb], color=INK, lw=3.4, zorder=6)
    ax.text(x0 + 25, yb + 6, "50 m", ha="center", fontsize=11.5,
            fontweight="bold", color=INK, zorder=6)

    for ax in axes:
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_aspect("equal")
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")

    fig.suptitle("The raw delivery over the ground the discard map covers",
                 x=0.012, ha="left", fontsize=18, fontweight="bold", color=INK)
    # leave room top and bottom: the suptitle and both x-labels sit
    # outside the axes and tight_layout will happily clip them
    fig.tight_layout(rect=(0, 0.035, 1, 0.94))
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "raw_returns_plan_view_9t.png"
    fig.savefig(p, dpi=165, facecolor=PAPER)
    plt.close(fig)
    print(f"\n  {p}")


if __name__ == "__main__":
    raise SystemExit(main())
