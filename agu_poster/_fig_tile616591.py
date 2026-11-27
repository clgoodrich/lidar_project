"""RRIM of tile 616500,4591500 (Area B) with hand-drawn (left) and predicted (right) pads and pits."""
import geopandas as gpd, rasterio, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
plt.rcParams["font.family"] = "Georgia"
R = "data/613590/results"; D = f"{R}/tile616591"
T = (616500, 4591500, 618000, 4593000)
with rasterio.open(f"{R}/rrim/rrim_tile616591_613590.tif") as s:
    img = np.moveaxis(s.read(), 0, -1)
tr = lambda n: gpd.read_file(f"{D}/{n}_tile616591.gpkg")
padT, pitT, padP, pitP = tr("pad_truth_scored"), tr("pit_truth_scored"), tr("pad_pred_ens"), tr("pit_pred_ens")
fig, axs = plt.subplots(1, 2, figsize=(20, 10.4), dpi=200)
fig.subplots_adjust(left=0.05, right=0.99, top=0.99, bottom=0.07, wspace=0.03)
for i, ax in enumerate(axs):
    ax.imshow(img, extent=(T[0], T[2], T[1], T[3]), interpolation="bilinear")
    pa, pi = (padT, pitT) if i == 0 else (padP, pitP)
    pa.boundary.plot(ax=ax, color="#F2C500", linewidth=1.8, linestyle="--")
    pi.boundary.plot(ax=ax, color="#1F5FA8", linewidth=1.8)
    ax.set_xlim(T[0], T[2]); ax.set_ylim(T[1], T[3])
    ax.set_xticks([617000, 617500]); ax.tick_params(labelsize=16)
    ax.set_yticks([4592000, 4592500] if i == 0 else [])
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.text(0.015, 0.985, "(a)" if i == 0 else "(b)", transform=ax.transAxes, va="top", fontsize=26,
            bbox=dict(fc="white", ec="none", pad=3))
ax = axs[0]
x0, y0 = T[0] + 60, T[1] + 60
ax.add_patch(Rectangle((x0 - 20, y0 - 20), 380, 120, fc="white", ec="none", zorder=5))
ax.add_patch(Rectangle((x0, y0), 125, 20, fc="black", ec="black", zorder=6))
ax.add_patch(Rectangle((x0 + 125, y0), 125, 20, fc="white", ec="black", zorder=6))
for dx, t in ((0, "0"), (250, "250 m")):
    ax.text(x0 + dx, y0 + 35, t, fontsize=15, zorder=6)
axs[0].set_ylabel("Northing (m)", fontsize=18)
fig.text(0.52, 0.015, "Easting (m), EPSG:6346", ha="center", fontsize=18)
fig.savefig(f"{D}/fig_rrim_pred_tile616591.png", dpi=200)
