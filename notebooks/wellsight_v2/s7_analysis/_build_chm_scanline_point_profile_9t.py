"""Point-cloud profile along the strike the user drew on the CHM panel.

WHY NOT THE RASTER
------------------
Several raster profiles were tried across this feature and all of them
under-report it. The streaks are rows of individual bright cells one to two
pixels wide with gaps between them, so:

  a one-pixel transect ALONG the marked strike returns 0 spikes and a DSM that
    tracks the DEM to within a metre over 128 m, because it runs in the gap;
  a one-pixel transect ACROSS them finds 4 spikes where the eye sees dozens,
    because it lands between the dots;
  a 12 m swath average across them recovers 6-8, still far short.

The raster is a 0.5 m grid built from the points. Going back to the points
removes the gridding entirely, and the point attributes are what identify the
mechanism anyway: `_test_chm_scanline_streaks_9t.py` showed the streak returns
are 21% single-return against 70% elsewhere, at the same scan angle as their
surroundings, in 20 discrete GPS-time bands.

THE GEOMETRY IS MEASURED FROM THE USER'S OWN ANNOTATION
--------------------------------------------------------
Three automatic bearing estimates disagreed with the panel (129, 135, 139 deg)
and were discarded. The strike here is read off the two yellow lines drawn on
`chm_300m_9t - Copy.png` by fitting the yellow pixels:

    upper line  +10.28 deg above horizontal
    lower line  +10.88 deg
    mean strike  79.4 deg bearing, centre 66.4% across / 19.6% down,
    lines 12.4 m apart, 127 m long

so the corridor is 12.4 m wide on bearing 79.4 deg, which is what this profiles.

WHAT IS PLOTTED
---------------
Every return inside the corridor, as height above the bare-earth DEM against
distance along the strike. First returns and later returns are drawn separately
because that is the discriminator: the streaks are made of pulses that returned
more than once.

COLOUR
------
Two point classes on one axis, from the dataviz reference categorical slots 1
and 2:
    node scripts/validate_palette.js "#2a78d6,#eb6834" --mode light --pairs all
    -> CVD worst dE 24.5 deutan, normal dE 33.8, both well clear.
No red and no green. The two classes also differ in marker and in height, so
colour is not the only cue.

Run:
    python notebooks/wellsight_v2/s7_analysis/_build_chm_scanline_point_profile_9t.py
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

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
OUT = ROOT / "data/9t/results/chm_striping"
FIG = ROOT / "docs/presentation/figures_30to45min/2_terrain_derivatives"

PAPER, INK, INK2, MUTED, RULE = "#f7f8f6", "#141a1f", "#545c63", "#8a887e", "#c9ccc6"
C_FIRST, C_LATER = "#2a78d6", "#eb6834"

#: Read off the user's annotation, see the module docstring.
STRIKE_DEG = 79.4
CENTRE_FRAC = (0.664, 0.196)
CORRIDOR_M = 12.4
HALF_M = 64.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=float,
                    default=[41.49264, -79.546127])
    ap.add_argument("--side", type=float, default=300.0)
    ap.add_argument("--strike", type=float, default=STRIKE_DEG)
    ap.add_argument("--at", nargs=2, type=float, default=list(CENTRE_FRAC))
    ap.add_argument("--corridor-m", type=float, default=CORRIDOR_M)
    ap.add_argument("--half-m", type=float, default=HALF_M)
    a = ap.parse_args()

    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:6346", always_xy=True)
    cx, cy = tr.transform(a.centre[1], a.centre[0])
    h = a.side / 2.0
    b = (cx - h, cy - h, cx + h, cy + h)
    ax0 = b[0] + a.at[0] * (b[2] - b[0])
    ay0 = b[3] - a.at[1] * (b[3] - b[1])
    th = np.radians(a.strike)
    ux, uy = np.sin(th), np.cos(th)          # along strike
    vx, vy = np.cos(th), -np.sin(th)         # across
    print(f"corridor centre {ax0:.1f} E {ay0:.1f} N, strike {a.strike:.1f} deg, "
          f"{a.corridor_m:.1f} m wide, {2*a.half_m:.0f} m long")

    with rasterio.open(D05 / "dem_9t_05.tif") as r:
        w = from_bounds(*b, transform=r.transform)
        dem = r.read(1, window=w, boundless=True,
                     fill_value=np.nan).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            dem[dem == r.nodata] = np.nan
    res = a.side / dem.shape[0]

    import laspy
    S, H, RN, NR = [], [], [], []
    for f in sorted(SRC.glob("*.laz")):
        las = laspy.read(f)
        x, y, z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
        m = (x >= b[0]) & (x < b[2]) & (y >= b[1]) & (y < b[3])
        if not m.any():
            continue
        x, y, z = x[m], y[m], z[m]
        rn = np.asarray(las.return_number)[m].astype(np.int16)
        nr = np.asarray(las.number_of_returns)[m].astype(np.int16)
        s = (x - ax0) * ux + (y - ay0) * uy          # along
        d = (x - ax0) * vx + (y - ay0) * vy          # across
        k = (np.abs(d) <= a.corridor_m / 2) & (np.abs(s) <= a.half_m)
        if not k.any():
            continue
        xs, ys, zs = x[k], y[k], z[k]
        c = np.clip(((xs - b[0]) / res).astype(int), 0, dem.shape[1] - 1)
        rr = np.clip(((b[3] - ys) / res).astype(int), 0, dem.shape[0] - 1)
        hag = zs - dem[rr, c]
        S.append(s[k]); H.append(hag); RN.append(rn[k]); NR.append(nr[k])
        print(f"  {f.name}: {k.sum():,} returns in the corridor")
    if not S:
        raise SystemExit("no returns in the corridor")
    S = np.concatenate(S); H = np.concatenate(H)
    RN = np.concatenate(RN); NR = np.concatenate(NR)
    ok = np.isfinite(H)
    S, H, RN, NR = S[ok], H[ok], RN[ok], NR[ok]

    single = NR == 1
    multi = ~single
    print(f"  {len(S):,} returns   single-return {100*single.mean():.1f}%   "
          f"multi {100*multi.mean():.1f}%")
    hi = H > 2.0
    print(f"  {hi.sum():,} returns above 2 m; of those "
          f"{100*multi[hi].mean():.1f}% are multi-return")

    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(figsize=(18.0, 8.2))
    ax.axhline(0, color=MUTED, linewidth=1.4, zorder=2)
    ax.scatter(S[single], H[single], s=5, c=C_FIRST, marker="o",
               alpha=0.55, linewidths=0, zorder=3,
               label=f"single return ({single.sum():,})")
    ax.scatter(S[multi], H[multi], s=9, c=C_LATER, marker="^",
               alpha=0.75, linewidths=0, zorder=4,
               label=f"multi-return pulse ({multi.sum():,})")
    ax.set_xlabel(f"distance along the strike you marked ({a.strike:.1f}°), metres",
                  fontsize=13)
    ax.set_ylabel("height above bare earth, m", fontsize=13)
    ax.grid(color=RULE, linewidth=0.8)
    ax.set_axisbelow(True)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    ax.legend(loc="upper right", fontsize=12, framealpha=0.94,
              facecolor="white", edgecolor=RULE, markerscale=2.4)
    ax.set_title(
        f"Every return inside your {a.corridor_m:.1f} m corridor, "
        f"{2*a.half_m:.0f} m long — {100*multi[hi].mean():.0f}% of everything "
        f"above 2 m is a multi-return pulse",
        fontsize=15, fontweight="bold", loc="left", color=INK, pad=10)
    fig.text(0.012, 0.975,
             "The canopy streaks, profiled from the points rather than the grid",
             fontsize=23, fontweight="bold", color=INK, va="top")
    fig.text(0.012, 0.925,
             f"Strike {a.strike:.1f}° and the corridor width are measured from "
             f"the two yellow lines drawn on chm_300m_9t, not estimated — three "
             f"automatic bearing estimates disagreed with the panel and were "
             f"discarded.\nHeight is above the bare-earth DEM, so 0 is the "
             f"ground. Centre {ax0:.0f} E {ay0:.0f} N, EPSG:6346.",
             fontsize=12.5, color=INK2, va="top", linespacing=1.55)
    fig.tight_layout(rect=(0, 0, 1, 0.885))

    FIG.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    p = FIG / f"chm_scanline_point_profile_b{a.strike:.0f}_300m_9t.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    jp = OUT / f"chm_scanline_point_profile_b{a.strike:.0f}_300m_9t.json"
    jp.write_text(json.dumps(dict(
        strike_deg=a.strike, centre_en=[ax0, ay0], corridor_m=a.corridor_m,
        half_m=a.half_m, n_returns=int(len(S)),
        single_return_pct=float(100 * single.mean()),
        above_2m=int(hi.sum()),
        above_2m_multi_pct=float(100 * multi[hi].mean())), indent=2),
        encoding="utf-8")
    print(f"\n  {p}\n  {jp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
