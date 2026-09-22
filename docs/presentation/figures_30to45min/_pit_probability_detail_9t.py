# -*- coding: utf-8 -*-
"""The pit probability surface, full slide, at readable size.

WHAT IS WRONG WITH THE SMALL VERSION
------------------------------------
The outcome slide shows RRIM and probability side by side, so the probability
panel gets half a slide and is rendered as grey on black. At that size the only
thing legible is that a few bright blobs exist. Everything the surface actually
says -- how sharp each response is, what the model does at a rim versus a
floor, where it fires faintly on something that is not a pit -- is below the
resolution of the panel.

This is a whole slide, with the probability carried on a sequential ramp over a
grey hillshade so terrain context survives.

EVERY PIXEL IS OUT-OF-FOLD
--------------------------
A single fold's raster covers the whole tile, but that model trained on most of
it, so most of its output is a memory rather than a prediction. This builds the
honest surface instead: for each of the five folds, keep only the pixels inside
that fold's own held-out blocks, and mosaic the five together. Every pixel is
then a prediction from a model that never saw that ground.

    fold 0  103 pits     fold 3  100
    fold 1  100          fold 4  101
    fold 2   99          total   503, which is the 9t count exactly

Block-to-fold comes from pit_cv5_fold_assignment_9t.csv. That file carries all
712 annotated floors, but only the 503 inside 9t have a block and a fold; the
rest are NaN and are dropped, which is how the totals reconcile.

WINDOW
------
880 by 480 m, which is the shape of the slide rather than the 400 m square the
outcome slide uses -- an equal-aspect square in a 16:9 frame leaves half the
figure empty and pushes the title off the edge.

It is not chosen by eye. Every position on a 40 m grid is scored by how many
annotated floors fall inside it, and any window containing a single pixel with
no fold assigned is rejected outright. The winner holds 30 annotated floors at
100% out-of-fold coverage. If no fully out-of-fold window of this size existed
the script would stop rather than quietly show one that is part memory.

COLOUR
------
Probability uses `magma`, which is perceptually uniform and has no green in it
at all, so no red/green pair can arise against anything. Terrain underneath is
plain grey. Annotated pit floors are outlined in #1F5FA8, the validated blue,
and the outline is a shape rather than a fill so it never competes with the
ramp for the same pixel.

Run:
    python docs/presentation/figures_30to45min/_pit_probability_detail_9t.py
Writes:
    data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif
    docs/presentation/figures_30to45min/v6/pit_probability_detail_880x480m_9t_05.png
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
CV = ROOT / "data/9t/models/pit/unet_cv5"
ASSIGN = CV / "pit_cv5_fold_assignment_9t.csv"
BLOCKS = ROOT / "data/9t/derived/05/blocks_unified_9t.gpkg"
PITS = ROOT / "data/9t/derived/05"
ANN = ROOT / "qgis/annotations/annotations_proj.gpkg"
HS = ROOT / "data/9t/derived/05/hillshade_9t_05.tif"
OOF = CV / "pit_prob_floor_outoffold_9t_05.tif"
OUT = ROOT / "docs/presentation/figures_30to45min/v6"

#: A 16:9 slide wants a 16:9 window. The outcome slide's 400 m square left
#: half the figure empty once the map was drawn to equal aspect, so this uses a
#: landscape window of the same height and twice the width.
WIN_W, WIN_H = 880.0, 480.0
#: Searched on a 40 m grid for the window holding the most annotated floors
#: that also has full out-of-fold coverage. Chosen by count, not by eye.
SEARCH_STEP = 40.0
BB = (619500.0, 4593000.0, 624000.0, 4597500.0)
SHOW_FLOOR = 0.05          # below this the ramp is fully transparent
PAPER = "#f7f8f6"
INK = "#141a1f"
MUTED = "#8a887e"
PITBLUE = "#1F5FA8"


def build_oof() -> Path:
    """Mosaic the five fold rasters, each masked to its own held-out blocks."""
    if OOF.exists():
        print(f"  reusing {OOF.name}")
        return OOF
    a = pd.read_csv(ASSIGN).dropna(subset=["block_id", "fold"])
    b2f = (a.groupby("block_id")["fold"].agg(lambda s: s.mode().iat[0])
           .astype(int).to_dict())
    blocks = gpd.read_file(BLOCKS).to_crs(6346)
    blocks["fold"] = blocks["block_id"].map(b2f)
    print(f"  {len(a)} pits with a fold, {blocks['fold'].notna().sum()} "
          f"blocks of {len(blocks)} assigned")

    f0 = CV / "fold0/pit_prob_floor_cvfold0_9t_05.tif"
    with rasterio.open(f0) as s:
        prof = s.profile.copy()
        H, W, tr = s.height, s.width, s.transform
    out = np.zeros((H, W), dtype="float32")
    covered = np.zeros((H, W), dtype=bool)

    for k in range(5):
        geoms = blocks.loc[blocks["fold"] == k, "geometry"].tolist()
        if not geoms:
            raise SystemExit(f"fold {k} has no blocks")
        m = geometry_mask(geoms, out_shape=(H, W), transform=tr, invert=True)
        p = CV / f"fold{k}/pit_prob_floor_cvfold{k}_9t_05.tif"
        with rasterio.open(p) as s:
            v = s.read(1).astype("float32")
        out[m] = v[m]
        covered |= m
        print(f"    fold {k}: {len(geoms):3d} blocks, {m.sum():,} px")

    print(f"  out-of-fold coverage {covered.mean()*100:.1f}% of the tile")
    prof.update(dtype="uint8", count=1, nodata=255, compress="deflate",
                zlevel=9, tiled=True, blockxsize=512, blockysize=512)
    q = np.where(covered, np.clip(out * 254.0, 0, 254), 255).astype("uint8")
    with rasterio.open(OOF, "w", **prof) as dst:
        dst.write(q, 1)
        dst.update_tags(SCALE="probability = DN / 254", NODATA_MEANS="no fold")
    print(f"  wrote {OOF.name}  {OOF.stat().st_size/1e6:.1f} MB")
    return OOF


def read_win(path, win, scale=None):
    with rasterio.open(path) as s:
        w = from_bounds(*win, transform=s.transform)
        a = s.read(1, window=w).astype("float32")
        nd = s.nodata
    if nd is not None:
        a[a == nd] = np.nan
    return a / scale if scale else a


def main() -> int:
    for p in (ASSIGN, BLOCKS, HS, ANN):
        if not p.exists():
            raise SystemExit(f"missing: {p}")
    build_oof()

    import shapely.geometry as sg
    allfloors = gpd.read_file(ANN, layer="pit_inside").to_crs(6346)
    cent = allfloors.geometry.centroid
    cx, cy = cent.x.to_numpy(), cent.y.to_numpy()

    # ---- pick the window: most annotated floors, fully out-of-fold --------
    best, WIN = None, None
    with rasterio.open(OOF) as s:
        for x in np.arange(BB[0], BB[2] - WIN_W + 1, SEARCH_STEP):
            for y in np.arange(BB[1], BB[3] - WIN_H + 1, SEARCH_STEP):
                w = (x, y, x + WIN_W, y + WIN_H)
                n = int(((cx >= w[0]) & (cx < w[2])
                         & (cy >= w[1]) & (cy < w[3])).sum())
                if best is not None and n <= best:
                    continue
                a = s.read(1, window=from_bounds(*w, transform=s.transform))
                if (a == 255).any():          # any pixel with no fold
                    continue
                best, WIN = n, w
    if WIN is None:
        raise SystemExit("no fully out-of-fold window of this size exists")
    print(f"\n  window {WIN[0]:.0f} E {WIN[1]:.0f} N, "
          f"{WIN_W:.0f} x {WIN_H:.0f} m, {best} annotated floors, "
          "100% out-of-fold")

    prob = read_win(OOF, WIN, scale=254.0)
    hs = read_win(HS, WIN)
    for t in (0.20, 0.50, 0.80):
        print(f"    above {t:.2f}: {np.nansum(prob >= t):,} px")

    floors = allfloors[allfloors.intersects(sg.box(*WIN))]
    print(f"  {len(floors)} annotated floors touch the window")

    ext = [WIN[0], WIN[2], WIN[1], WIN[3]]
    plt.rcParams.update({"figure.facecolor": PAPER, "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    # The axes are equal-aspect, so the figure has to carry the window's own
    # ratio plus room for the title and the colourbar, or the map floats in
    # empty space with the title running off the edge.
    fw = 12.4
    fig, ax = plt.subplots(figsize=(fw, fw * WIN_H / WIN_W / 0.95))

    # The probability layer and nothing else. An earlier version laid the ramp
    # over a grey hillshade so terrain context survived; the terrain won, and
    # the slide stopped being about the model's output. This is the raster the
    # way QGIS renders it -- black at 0, white at 1, whole band, nothing
    # masked -- which is also how the right-hand panel on the outcome slide is
    # drawn, so the two read as the same product at two sizes.
    ax.set_facecolor("#000000")
    im = ax.imshow(np.ma.masked_where(~np.isfinite(prob), prob), cmap="gray",
                   vmin=0.0, vmax=1.0, extent=ext, zorder=2,
                   interpolation="nearest")

    ax.set_xlim(WIN[0], WIN[2])
    ax.set_ylim(WIN[1], WIN[3])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#c9ccc6")

    x0, y0 = WIN[0] + 18, WIN[1] + 18
    ax.plot([x0, x0 + 100], [y0, y0], color="#000000", linewidth=6, zorder=6)
    ax.plot([x0, x0 + 100], [y0, y0], color="white", linewidth=2.6, zorder=7)
    ax.text(x0 + 50, y0 + 7, "100 m", fontsize=12, fontweight="bold",
            color="white", ha="center", va="bottom", zorder=7)

    cb = fig.colorbar(im, ax=ax, fraction=0.028, pad=0.012)
    cb.set_label("pit-floor probability", fontsize=12, color=INK)
    cb.ax.tick_params(labelsize=11)

    # No title inside the figure. The slide carries one, and printing it twice
    # is the double-titling this deck has been stripping out everywhere else.
    # It also buys back the vertical space the map needs to fill the slide.
    fig.subplots_adjust(left=0.006, right=0.955, top=0.994, bottom=0.006)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "pit_probability_detail_880x480m_9t_05.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    from PIL import Image
    print(f"\n  {Image.open(p).size[0]}x{Image.open(p).size[1]} px")
    print(f"  {p}")
    print(f"  {OOF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
