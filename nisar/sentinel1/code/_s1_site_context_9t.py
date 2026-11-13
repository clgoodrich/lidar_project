"""Three-panel site figure for one point on 9t: lidar RRIM, lidar canopy height, Sentinel-1 brightness vs surroundings.

Marks DEP wells (white triangles), NISAR steady bright pixels (blue squares, from the lidar-placed SLC run) and the
point itself (orange plus). Annotated pits are outlined in blue, pads in charcoal, roads (roads.shp) as white lines with a charcoal edge on all three panels.
Sentinel-1 panel is the CFAR signal-to-clutter ratio from _s1_metal_cfar_9t.py (32 dates, track 77, water masked).
Colours: lost/found pair #1F5FA8 / #D97706 (dataviz validate_palette.js --pairs all, worst dE 21.1 deutan), plus
charcoal and grey; every class also has its own marker shape. Canopy uses a single-hue green ramp (sequential).

  python nisar/sentinel1/code/_s1_site_context_9t.py <name> <lat> <lon> [half_box_m]
  e.g. python nisar/sentinel1/code/_s1_site_context_9t.py point3 41.499860 -79.514601 75
Writes nisar/sentinel1/results/9t/sites/s1_site_<name>_9t.png
"""
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _s1_metal_cfar_9t as M  # noqa: E402

ROOT = M.ROOT
RRIM = ROOT / "data" / "9t" / "derived" / "05" / "rrim_openness_9t_05.tif"
CHM = ROOT / "data" / "9t" / "derived" / "1m" / "chm_9t_1m.tif"
ANN = ROOT / "qgis" / "annotations"
NISAR_BRIGHT = ROOT / "nisar" / "results" / "9t" / "nisar_bright_targets_points_9t_slc.gpkg"
OUT = ROOT / "nisar" / "sentinel1" / "results" / "9t" / "sites"
BLUE, ORANGE, INK, GREY = "#1F5FA8", "#D97706", "#2B2F36", "#5B6168"


def main():
    name, lat, lon = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    H = float(sys.argv[4]) if len(sys.argv) > 4 else 75.0
    OUT.mkdir(parents=True, exist_ok=True)
    xx, yy = Transformer.from_crs(4326, 6346, always_xy=True).transform(lon, lat)
    to_s1 = Transformer.from_crs(6346, 32617, always_xy=True)
    x, y = to_s1.transform(xx, yy)
    clip = lambda g: g.to_crs(6346).cx[xx - H:xx + H, yy - H:yy + H]
    wells = clip(gpd.read_file(M.WELLS))
    bright = clip(gpd.read_file(NISAR_BRIGHT))
    pits = clip(gpd.read_file(ANN / "pit_full.shp"))
    pads = clip(gpd.read_file(ANN / "pad.shp"))
    roads = clip(gpd.read_file(ANN / "roads.shp"))

    def marks(ax, s1=False):
        for g, kw in ((pads, dict(color=INK, linewidth=1.0)), (pits, dict(color=BLUE, linewidth=1.8))):
            if len(g):
                gg = g.to_crs(32617) if s1 else g
                gg.boundary.plot(ax=ax, **kw)
        if len(roads):
            (roads.to_crs(32617) if s1 else roads).plot(
                ax=ax, color="white", linewidth=1.6, zorder=4,
                path_effects=[pe.Stroke(linewidth=3.4, foreground=INK), pe.Normal()])
        pts = [(wells, dict(marker="^", s=110, facecolor="white", edgecolor=INK, linewidths=1.3, label="DEP well")),
               (bright, dict(marker="s", s=90, facecolor="none", edgecolor=BLUE, linewidths=2, label="NISAR steady bright pixel"))]
        for g, kw in pts:
            gx, gy = g.geometry.x.values, g.geometry.y.values
            if s1 and len(g):
                gx, gy = to_s1.transform(gx, gy)
            ax.scatter(gx, gy, zorder=5, **kw)
        ax.scatter([x if s1 else xx], [y if s1 else yy], marker="+", s=350, color=ORANGE, linewidths=3, zorder=6,
                   label=name)

    fig, axs = plt.subplots(1, 3, figsize=(18, 6.4))
    with rasterio.open(RRIM) as r:
        img = r.read(window=from_bounds(xx - H, yy - H, xx + H, yy + H, r.transform)).transpose(1, 2, 0)
    axs[0].imshow(img, extent=(xx - H, xx + H, yy - H, yy + H))
    marks(axs[0])
    axs[0].set_title("Lidar RRIM, 0.5 m (pits blue, pads charcoal, roads white)", fontsize=10)
    with rasterio.open(CHM) as r:
        c = r.read(1, window=from_bounds(xx - H, yy - H, xx + H, yy + H, r.transform)).astype(float)
    c[c < -100] = np.nan
    im = axs[1].imshow(c, extent=(xx - H, xx + H, yy - H, yy + H), cmap="Greens", vmin=0, vmax=25)
    plt.colorbar(im, ax=axs[1], fraction=0.046, label="canopy height (m)")
    marks(axs[1])
    axs[1].set_title("Lidar canopy height, 1 m", fontsize=10)

    dates, tf, mean_i, _ = M.load()
    scr = M.cfar_scr(mean_i, M.water_mask(mean_i))
    inv = ~tf
    c0, r0 = [int(v) for v in inv * (x - H, y + H)]
    c1, r1 = [int(v) for v in inv * (x + H, y - H)]
    X0, Y1 = tf * (c0, r0)
    X1, Y0 = tf * (c1, r1)
    im = axs[2].imshow(10 * np.log10(scr[r0:r1, c0:c1]), extent=(X0, X1, Y0, Y1), cmap="gray", vmin=-4, vmax=6,
                       interpolation="nearest")
    plt.colorbar(im, ax=axs[2], fraction=0.046, label=f"dB vs surroundings (CFAR cutoff 4.7)")
    marks(axs[2], s1=True)
    axs[2].set_xlim(x - H, x + H); axs[2].set_ylim(y - H, y + H)
    axs[2].set_title(f"Sentinel-1 track 77, {len(dates)} dates: brightness vs surroundings", fontsize=10)
    for a in axs[:2]:
        a.set_xlim(xx - H, xx + H); a.set_ylim(yy - H, yy + H)
    for a in axs:
        a.set_xticks([]); a.set_yticks([])
    L = 50 if H >= 60 else 20
    axs[0].plot([xx - H + 0.1 * H, xx - H + 0.1 * H + L], [yy - H + 0.1 * H] * 2, color="white", lw=3)
    axs[0].text(xx - H + 0.1 * H + L / 2, yy - H + 0.14 * H, f"{L} m", color="white", ha="center", fontsize=9)
    axs[0].plot([], [], color="white", linewidth=1.6, path_effects=[pe.Stroke(linewidth=3.4, foreground=INK), pe.Normal()],
                label="road annotations")
    axs[0].legend(loc="upper right", fontsize=8, framealpha=0.9)
    fig.suptitle(f"{name} ({lat:.6f}, {lon:.6f}), {2 * H:.0f} m box, north up", fontsize=12)
    fig.tight_layout()
    out = OUT / f"s1_site_{name}_9t.png"
    fig.savefig(out, dpi=120)
    print(out)


if __name__ == "__main__":
    main()
