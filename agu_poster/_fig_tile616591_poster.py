"""Poster Figure 4: northern 750 m of tile 616500,4591500 (Area B). (a) RRIM + hand outlines, (b) RRIM + ensemble predictions."""
import geopandas as gpd, rasterio, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
plt.rcParams["font.family"] = "Georgia"
R = "data/613590/results"; D = f"{R}/tile616591"
W = (616500, 4592250, 618000, 4593000)
with rasterio.open(f"{R}/rrim/rrim_tile616591_613590.tif") as s:
    img = np.moveaxis(s.read(), 0, -1)
T = (616500, 4591500, 618000, 4593000)
tr = lambda n: gpd.read_file(f"{D}/{n}_tile616591.gpkg")
padT, pitT, padP, pitP = tr("pad_truth_scored"), tr("pit_truth_scored"), tr("pad_pred_ens"), tr("pit_pred_ens")
fig, axs = plt.subplots(1, 2, figsize=(13.47, 3.55), dpi=300)
fig.subplots_adjust(left=0.085, right=0.995, top=0.995, bottom=0.2, wspace=0.03)
for i, ax in enumerate(axs):
    ax.imshow(img, extent=(T[0], T[2], T[1], T[3]), interpolation="bilinear")
    pa, pi = (padT, pitT) if i == 0 else (padP, pitP)
    pa.boundary.plot(ax=ax, color="#F2C500", linewidth=1.6, linestyle="--")
    pi.boundary.plot(ax=ax, color="#1F5FA8", linewidth=1.6)
    ax.set_xlim(W[0], W[2]); ax.set_ylim(W[1], W[3])
    ax.set_xticks([617000, 617500]); ax.tick_params(labelsize=14, length=5)
    ax.set_yticks([4592500, 4592750] if i == 0 else [])
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.text(0.012, 0.965, "(a)" if i == 0 else "(b)", transform=ax.transAxes, va="top", fontsize=22,
            bbox=dict(fc="white", ec="none", pad=2))
ax = axs[0]; x0, y0 = W[0] + 50, W[1] + 30
ax.add_patch(Rectangle((x0 - 15, y0 - 12), 390, 100, fc="white", ec="none", zorder=5))
ax.add_patch(Rectangle((x0, y0), 125, 14, fc="black", ec="black", zorder=6))
ax.add_patch(Rectangle((x0 + 125, y0), 125, 14, fc="white", ec="black", zorder=6))
for dx, t in ((0, "0"), (250, "250 m")): ax.text(x0 + dx, y0 + 26, t, fontsize=12, zorder=6)
axs[0].set_ylabel("Northing (m)", fontsize=15)
fig.text(0.54, 0.02, "Easting (m), EPSG:6346", ha="center", fontsize=15)
fig.savefig("agu_poster/figures/poster_pred_tile616591.png", dpi=300)
