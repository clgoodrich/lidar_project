"""Poster Figure 1 on Tile B (616500,4591500 - 618000,4593000): (a) Planet 2023-04-10 aerial, (b) RRIM, (c) pad probability, (d) pit probability.
Probabilities are the five-fold-model mean (Tile B unseen in training). 400 m window with the most hand-drawn pads and pits."""
import geopandas as gpd, rasterio, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm
from matplotlib.patches import Rectangle
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
plt.rcParams["font.family"] = "Georgia"
R = "data/613590/results"; D = f"{R}/tile616591"
T = (616500, 4591500, 618000, 4593000)
tr = lambda n: gpd.read_file(f"{D}/{n}_tile616591.gpkg")
padT, pitT = tr("pad_truth_scored"), tr("pit_truth_scored")
S = 400; best = None
for x0 in range(T[0], T[2] - S + 1, 25):
    for y0 in range(T[1], T[3] - S + 1, 25):
        n = len(padT.cx[x0:x0 + S, y0:y0 + S]) + len(pitT.cx[x0:x0 + S, y0:y0 + S])
        if best is None or n > best[0]: best = (n, (x0, y0, x0 + S, y0 + S))
b = best[1]; x0, y0, x1, y1 = b; print("window", b, best[0])
def crop(path):
    with rasterio.open(path) as r:
        a = r.read(window=from_bounds(*b, r.transform), boundless=True, fill_value=0)
    return a
rrim = np.moveaxis(crop(f"{R}/rrim/rrim_tile616591_613590.tif") if False else np.zeros((3, 1, 1), np.uint8), 0, -1)
with rasterio.open(f"{R}/rrim/rrim_tile616591_613590.tif") as r:
    rrim = np.moveaxis(r.read(window=from_bounds(*b, r.transform)), 0, -1)
def ens(n):
    with rasterio.open(f"{D}/{n}_prob_ens_tile616591.tif") as r:
        return r.read(1, window=from_bounds(*b, r.transform))
pad_p, pit_p = ens("pad"), ens("pit")
sc = "J:/PLanet/planet/PSScene-20230410_154649_17_2490/assets/ortho_visual/20230410_154649_17_2490_3B_Visual.tif"
with rasterio.open(sc) as s:
    air = np.moveaxis(s.read([1, 2, 3], window=from_bounds(*transform_bounds(6346, s.crs, *b), s.transform), boundless=True, fill_value=0), 0, -1)
W, H = 28.3, 8.0
fig = plt.figure(figsize=(W, H), dpi=200)
side, gap, left, bottom = 6.1, 0.35, 1.65, 1.8
axs = [fig.add_axes([(left + i * (side + gap)) / W, bottom / H, side / W, side / H]) for i in range(4)]
ext = (x0, x1, y0, y1)
axs[0].imshow(air, extent=ext, interpolation="bicubic")
axs[1].imshow(rrim, extent=ext, interpolation="bilinear")
im = axs[2].imshow(pad_p, cmap="gray", vmin=0, vmax=1, extent=ext, interpolation="nearest")
im2 = axs[3].imshow(pit_p, cmap="gray", norm=PowerNorm(1.0, vmin=0, vmax=0.5), extent=ext, interpolation="nearest")
for g, ax, col, ls, lw in ((padT, axs[2], "#F2C500", "--", 2.0), (pitT, axs[3], "#1F5FA8", "-", 0.9)):
    gg = g.cx[x0:x1, y0:y1]
    if len(gg): gg.boundary.plot(ax=ax, color=col, linewidth=lw, linestyle=ls)
for i, ax in enumerate(axs):
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_xticks([x0 + 100, x0 + 300]); ax.set_yticks([y0 + 100, y0 + 300] if i == 0 else [])
    ax.ticklabel_format(useOffset=False, style="plain"); ax.tick_params(labelsize=22, length=7, width=1.5)
    for s in ax.spines.values(): s.set_linewidth(1.5)
    ax.text(0.03, 0.97, "(" + "abcd"[i] + ")", transform=ax.transAxes, va="top", fontsize=34,
            bbox=dict(fc="white", ec="none", pad=3))
axs[0].set_ylabel("Northing (m)", fontsize=24)
fig.text((left + side + gap / 2) / W, 0.62 / H, "Easting (m), EPSG:6346", ha="center", fontsize=24)
a = axs[1]; sx, sy = x0 + 20, y0 + 20
a.add_patch(Rectangle((sx - 10, sy - 10), 170, 55, fc="white", ec="none", zorder=5))
a.add_patch(Rectangle((sx, sy), 50, 8, fc="black", ec="black", zorder=6)); a.add_patch(Rectangle((sx + 50, sy), 50, 8, fc="white", ec="black", zorder=6))
a.text(sx, sy + 14, "0", fontsize=20, zorder=6); a.text(sx + 100, sy + 14, "100 m", fontsize=20, zorder=6, ha="center")
a.annotate("", xy=(x1 - 25, y1 - 22), xytext=(x1 - 25, y1 - 75), arrowprops=dict(arrowstyle="-|>", color="white", lw=3, mutation_scale=30))
a.text(x1 - 25, y1 - 82, "N", ha="center", va="top", fontsize=28, color="white")
for i, (imx, lab) in ((2, (im, "Pad probability")), (3, (im2, "Pit probability (white at 0.5 and above)"))):
    cax = fig.add_axes([(left + i * (side + gap) + 0.4) / W, 0.75 / H, (side - 0.8) / W, 0.2 / H])
    cb = fig.colorbar(imx, cax=cax, orientation="horizontal", ticks=[0, 0.25, 0.5] if i == 3 else [0, 0.5, 1], extend="max" if i == 3 else "neither")
    cb.ax.tick_params(labelsize=22, length=6); cb.set_label(lab, fontsize=22, labelpad=4)
fig.savefig("agu_poster/figures/poster_hero_tileB.png", dpi=200)
