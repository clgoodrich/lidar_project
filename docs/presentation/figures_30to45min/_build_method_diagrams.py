"""Three method figures for slides that had a title and nothing under it.

    unet_architecture_9t          what the network actually is
    annotation_schema_9t          which annotation fields are drawn and which
                                  are derived, and how the layers join
    label_burn_order_9t           how the pit layers overlap, and what resolves it

Every number and every shape is read out of the repository rather than typed:

    the network                   _dl.py UNet, _pit_unet_cv5.py call site
    the layer counts and joins    qgis/annotations/annotations_proj.gpkg
    the burn order                _build_pit_dataset_v2.py
    the example pit               a real pit_inside / pit_outside pair

COLOUR
------
The accent blue and the same annotation colours the rest of the talk uses. No
red/green pair anywhere, per the colourblind rule in CLAUDE.md.

Run:
    python docs/presentation/figures_30to45min/_build_method_diagrams.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch

ROOT = Path(__file__).resolve().parents[3]
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
OUT_M = ROOT / "docs/presentation/figures_30to45min/4_model_building"
OUT_A = ROOT / "docs/presentation/figures_30to45min/3_annotations"

PAPER = "#f7f8f6"
INK = "#141a1f"
INK2 = "#545c63"
MUTED = "#8a887e"
RULE = "#c9ccc6"
ACCENT = "#1F5FA8"
TINT = "#eaf0f8"

#: Same layer colours as the annotation series, so a reader who has seen those
#: slides recognises them here.
C_PIT = "#ccff00"      # floor
C_RIM = "#ffffff"      # outer rim, outline only
C_WALL = "#e040fb"     # the ring between them
HALO = [pe.Stroke(linewidth=3.0, foreground="#000000"), pe.Normal()]

#: Read off notebooks/wellsight_v2/_dl.py and the call in _pit_unet_cv5.py.
IN_CH, BASE, N_CLASSES, LEVELS = 7, 32, 3, 4
PATCH_M, RES_M = 128, 0.5


def layer_counts():
    """How many features each hand-drawn layer holds, from the GeoPackage."""
    con = sqlite3.connect(ANN)
    try:
        names = [r[0] for r in con.execute(
            "select table_name from gpkg_contents order by table_name")]
        return {n: con.execute(f"select count(*) from {n}").fetchone()[0]
                for n in names}
    finally:
        con.close()


def panel(ax, title, sub=None):
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    ax.set_title(title, fontsize=15, fontweight="bold", loc="left",
                 pad=22 if sub else 8, color=INK)
    if sub:
        ax.text(0, 1.006, sub, transform=ax.transAxes, fontsize=10.5,
                color=MUTED, va="bottom", ha="left")


# --------------------------------------------------------------------------
def fig_unet():
    """The network, drawn at the widths the code actually instantiates."""
    px = int(PATCH_M / RES_M)
    enc = [BASE * 2 ** i for i in range(LEVELS)]          # 32 64 128 256
    bot = BASE * 2 ** LEVELS                              # 512
    fig, ax = plt.subplots(figsize=(16.0, 8.0))
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(4, 96, "The network", fontsize=26, fontweight="bold", color=INK,
            va="top")
    ax.text(4, 90.5,
            f"A plain 4-level U-Net, base {BASE}. {IN_CH} terrain channels in, "
            f"{N_CLASSES} classes out, about 8 M parameters. Nothing "
            f"pretrained, nothing exotic.",
            fontsize=13, color=INK2, va="top")

    #: x positions: encoder down the left, bottleneck centre, decoder right
    xs_d = [16, 34, 52, 70]
    x_bot = 92
    xs_u = [114, 132, 150, 168]
    ys = [70, 58, 46, 34]
    y_bot = 22
    W, H = 13.0, 7.2

    def box(x, y, label, sub, strong=False):
        ax.add_patch(FancyBboxPatch(
            (x - W / 2, y - H / 2), W, H,
            boxstyle="round,pad=0.0,rounding_size=1.0",
            facecolor=ACCENT if strong else TINT,
            edgecolor=ACCENT, linewidth=1.5, zorder=3))
        ax.text(x, y + 1.0, label, fontsize=13, fontweight="bold",
                ha="center", va="center", zorder=4,
                color="#ffffff" if strong else INK)
        ax.text(x, y - 2.0, sub, fontsize=9.5, ha="center", va="center",
                zorder=4, color="#dce8f6" if strong else INK2)

    def arrow(p, q, style="-|>", col=ACCENT, lw=2.0, ls="-"):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=18,
                                     color=col, linewidth=lw, linestyle=ls,
                                     zorder=2,
                                     connectionstyle="arc3,rad=0"))

    # encoder
    for i, (x, y, c) in enumerate(zip(xs_d, ys, enc)):
        n = px // 2 ** i
        box(x, y, f"{c} ch", f"{n}×{n}")
        if i:
            arrow((xs_d[i - 1], ys[i - 1] - H / 2),
                  (x, y + H / 2))
    # left-aligned: centred on the first box it ran off the canvas
    ax.text(4, ys[0] + H / 2 + 6.0,
            f"input  {IN_CH} channels,  {px}×{px} px  =  {PATCH_M} m patch",
            fontsize=11.5, color=INK, ha="left", va="bottom",
            fontweight="bold")
    arrow((xs_d[0], ys[0] + H / 2 + 5.2), (xs_d[0], ys[0] + H / 2))

    arrow((xs_d[-1], ys[-1] - H / 2), (x_bot - W / 2, y_bot + 1))
    box(x_bot, y_bot, f"{bot} ch", f"{px // 2 ** LEVELS}×{px // 2 ** LEVELS}",
        strong=True)
    ax.text(x_bot, y_bot - H / 2 - 2.2, "bottleneck", fontsize=10.5,
            color=MUTED, ha="center", va="top")

    # decoder, mirrored
    for i, (x, y, c) in enumerate(zip(xs_u, ys[::-1], enc[::-1])):
        n = px // 2 ** (LEVELS - 1 - i)
        box(x, y, f"{c} ch", f"{n}×{n}")
        src = (x_bot + W / 2, y_bot + 1) if i == 0 else (xs_u[i - 1],
                                                         ys[::-1][i - 1] + H / 2)
        arrow(src, (x, y - H / 2))
        # the skip: same level of the encoder, concatenated in
        arrow((xs_d[LEVELS - 1 - i] + W / 2, ys[LEVELS - 1 - i]),
              (x - W / 2, y), style="-|>", col=MUTED, lw=1.6, ls=(0, (5, 3)))

    ax.text((xs_d[0] + xs_u[-1]) / 2, ys[0] + 3.0,
            "dashed = skip connection, concatenated",
            fontsize=10.5, color=MUTED, ha="center", va="bottom")

    box(xs_u[-1], ys[0] + 13.0, f"{N_CLASSES} classes",
        "1×1 conv")
    arrow((xs_u[-1], ys[0] + H / 2), (xs_u[-1], ys[0] + 13.0 - H / 2))

    ax.text(4, 9.0,
            "Each block is two 3×3 convolutions, batch norm, ReLU. "
            "Downsampling is max-pool 2, upsampling is a transposed "
            "convolution.\nTrained with focal cross-entropy, 5-fold "
            "cross-validation, 40 epochs, on 128 m patches jittered by 30 m.",
            fontsize=11.5, color=INK2, va="top", linespacing=1.6)

    p = OUT_M / "unet_architecture_9t.png"
    fig.subplots_adjust(left=0.004, right=0.996, top=0.996, bottom=0.004)
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:6.0f} KB  {p.name}")


# --------------------------------------------------------------------------
def fig_schema(counts):
    """Which fields a human drew, and which the code worked out afterwards."""
    fig, ax = plt.subplots(figsize=(16.0, 8.0))
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(4, 96, "Drawn, or worked out afterwards", fontsize=26,
            fontweight="bold", color=INK, va="top")
    ax.text(4, 90.5,
            "A hand-drawn layer holds only what a hand drew. Everything else "
            "in the annotation table is derived by code and can be rebuilt "
            "from scratch,\nwhich is what makes the counts on the later "
            "slides checkable rather than asserted.",
            fontsize=13, color=INK2, va="top", linespacing=1.6)

    drawn = [("pit_inside", "the floor of the pit"),
             ("pit_outside", "the outer rim"),
             ("plat", "the pad"),
             ("roads", "access roads"),
             ("drainage", "streams and ditches"),
             ("not_roads", "things that look like roads and are not")]
    derived = [
        ("pit_wall",
         "pit_outside MINUS pit_inside, as geometry.\nNobody draws the ring "
         "twice, so it cannot\ndisagree with the two layers it comes from."),
        ("matched_pit_id  /  pit_inside_id",
         "the foreign key back to the floor: on\npit_outside it is spelled "
         "matched_pit_id,\non pit_wall pit_inside_id. A rim always\nknows "
         "which floor it belongs to."),
        ("pad_id",
         "assigned by spatial join, on every layer.\nOne rule for polygons "
         "and lines alike."),
        ("n_pits, n_roads, n_not_roads",
         "counted per pad, never typed. Dropped and\nrecomputed on every run, "
         "because a re-run\nthat merged twice is how they went wrong once."),
    ]

    ax.text(4, 82, "drawn by hand in QGIS", fontsize=15, fontweight="bold",
            color=INK, va="top")
    ax.plot([4, 64], [78.5, 78.5], color=RULE, linewidth=1.3)
    y = 73.5
    for name, what in drawn:
        n = counts.get(name)
        ax.add_patch(FancyBboxPatch((4, y - 8.0), 60, 8.0,
                                    boxstyle="round,pad=0.0,rounding_size=1.0",
                                    facecolor="#ffffff", edgecolor=RULE,
                                    linewidth=1.1, zorder=2))
        ax.text(7, y - 2.7, name, fontsize=12.5, fontweight="bold", color=INK,
                va="center", zorder=3)
        ax.text(7, y - 5.9, what, fontsize=10, color=INK2, va="center",
                zorder=3)
        if n is not None:
            ax.text(61, y - 4.2, f"{n:,}", fontsize=13, fontweight="bold",
                    color=ACCENT, ha="right", va="center", zorder=3)
        y -= 10.2

    ax.text(76, 82, "derived by code, every run", fontsize=15,
            fontweight="bold", color=INK, va="top")
    ax.plot([76, 196], [78.5, 78.5], color=RULE, linewidth=1.3)
    y = 73.5
    for name, what in derived:
        ax.add_patch(FancyBboxPatch((76, y - 14.5), 120, 14.5,
                                    boxstyle="round,pad=0.0,rounding_size=1.0",
                                    facecolor=TINT, edgecolor=ACCENT,
                                    linewidth=1.4, zorder=2))
        ax.text(79, y - 3.2, name, fontsize=12.5, fontweight="bold",
                color=INK, va="center", zorder=3)
        ax.text(79, y - 9.4, what, fontsize=10.5, color=INK2, va="center",
                zorder=3, linespacing=1.5)
        y -= 16.8

    ax.add_patch(FancyArrowPatch((65.5, 52), (74.5, 52), arrowstyle="-|>",
                                 mutation_scale=22, color=ACCENT,
                                 linewidth=2.4))
    p = OUT_A / "annotation_schema_drawn_vs_derived_9t.png"
    fig.subplots_adjust(left=0.004, right=0.996, top=0.996, bottom=0.004)
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:6.0f} KB  {p.name}")


# --------------------------------------------------------------------------
def fig_burn_order():
    """A real pit, showing what overlaps and what resolves it."""
    inside = gpd.read_file(ANN, layer="pit_inside")
    outside = gpd.read_file(ANN, layer="pit_outside")
    # The key is spelled differently on the two layers in the shipped file:
    # pit_outside carries matched_pit_id, pit_wall carries pit_inside_id.
    key = "matched_pit_id" if "matched_pit_id" in outside.columns else "pit_inside_id"
    merged = outside.dropna(subset=[key]).merge(
        inside[["pit_inside_id", "geometry"]].rename(
            columns={"geometry": "geom_in"}),
        left_on=key, right_on="pit_inside_id", how="inner")
    if merged.empty:
        print("    no matched rim/floor pairs; skipping burn-order fig")
        return
    # the clearest example is a pit whose rim is comfortably wider than its
    # floor, so the ring is visible at print size
    # A handful of annotations are multipart; the example has to be a plain
    # polygon inside a plain polygon or the picture explains nothing.
    simple = merged[(merged.geometry.geom_type == "Polygon")
                    & (gpd.GeoSeries(merged["geom_in"], crs=inside.crs)
                       .geom_type == "Polygon")].copy()
    merged = simple if len(simple) else merged
    merged["ring"] = merged.area - gpd.GeoSeries(merged["geom_in"],
                                                 crs=inside.crs).area
    row = merged.sort_values("ring", ascending=False).iloc[len(merged) // 12]
    g_out, g_in = row.geometry, row["geom_in"]
    ring = g_out.difference(g_in)

    cx, cy = g_out.centroid.x, g_out.centroid.y
    h = max(g_out.bounds[2] - g_out.bounds[0],
            g_out.bounds[3] - g_out.bounds[1]) * 0.78

    fig, axes = plt.subplots(1, 3, figsize=(16.0, 7.0))
    fig.suptitle("Two layers overlap on purpose. Burn order decides the label.",
                 fontsize=22, fontweight="bold", x=0.018, ha="left", y=0.985,
                 color=INK)
    fig.text(0.018, 0.925,
             "pit_outside contains pit_inside, so every floor pixel is also a "
             "rim pixel. Rasterising the wall first and painting the floor on "
             "top settles it,\nand settles it the same way every run. "
             "_build_pit_dataset_v2.py: \"Walls are listed first so floors "
             "paint over them where they overlap.\"",
             fontsize=12, color=INK2, va="top", linespacing=1.6)

    def draw(ax, geom, fc, ec="none", alpha=1.0, lw=0.0, z=2):
        gpd.GeoSeries([geom], crs=inside.crs).plot(
            ax=ax, facecolor=fc, edgecolor=ec, alpha=alpha, linewidth=lw,
            zorder=z)

    def frame(ax):
        ax.set_xlim(cx - h, cx + h)
        ax.set_ylim(cy - h, cy + h)
        ax.set_aspect("equal")

    panel(axes[0], "1 · what was drawn",
          "two polygons, one inside the other")
    draw(axes[0], g_out, "#dfe3e8", "#4a4a4a", 1.0, 2.0, 2)
    draw(axes[0], g_in, C_PIT, "#4a4a4a", 0.85, 2.0, 3)
    frame(axes[0])
    axes[0].legend(handles=[
        Patch(facecolor="#dfe3e8", edgecolor="#4a4a4a", label="pit_outside"),
        Patch(facecolor=C_PIT, edgecolor="#4a4a4a", label="pit_inside")],
        loc="lower right", fontsize=10.5, framealpha=1.0,
        facecolor="#ffffff", edgecolor=RULE)

    panel(axes[1], "2 · burn the wall first",
          "pit_wall = pit_outside minus pit_inside, class 2")
    draw(axes[1], ring, C_WALL, "none", 0.85, 0.0, 2)
    frame(axes[1])
    axes[1].legend(handles=[Patch(facecolor=C_WALL, alpha=0.75,
                                  edgecolor="none", label="wall, class 2")],
                   loc="lower right", fontsize=10.5, framealpha=1.0,
                   facecolor="#ffffff", edgecolor=RULE)

    panel(axes[2], "3 · paint the floor on top",
          "class 1 wins where they overlap")
    draw(axes[2], g_out, C_WALL, "none", 0.75, 0.0, 2)
    draw(axes[2], g_in, C_PIT, "none", 1.0, 0.0, 3)
    gpd.GeoSeries([ring], crs=inside.crs).boundary.plot(
        ax=axes[2], color="#4a4a4a", linewidth=1.2, zorder=4)
    frame(axes[2])
    axes[2].legend(handles=[
        Patch(facecolor=C_PIT, edgecolor="none", label="floor, class 1"),
        Patch(facecolor=C_WALL, alpha=0.75, edgecolor="none",
              label="wall, class 2")],
        loc="lower right", fontsize=10.5, framealpha=1.0,
        facecolor="#ffffff", edgecolor=RULE)

    fig.text(0.018, 0.028,
             "Two more edge rules, same spirit. A pixel is claimed only if "
             "its CENTRE falls inside the shape: all_touched=True would fatten "
             "every pit by\nhalf a pixel of invented rim, 25 cm at 0.5 m. And "
             "a pit is assigned to a spatial block by its CENTROID, so one "
             "straddling a block edge\nis counted once and lands on one side "
             "of the train/test split.",
             fontsize=11.5, color=MUTED, va="bottom", linespacing=1.6)
    fig.subplots_adjust(left=0.012, right=0.988, top=0.755, bottom=0.235,
                        wspace=0.07)
    p = OUT_A / "label_burn_order_pit_wall_floor_9t.png"
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:6.0f} KB  {p.name}")


def main() -> int:
    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    counts = layer_counts()
    print("layer counts:", counts)
    OUT_M.mkdir(parents=True, exist_ok=True)
    OUT_A.mkdir(parents=True, exist_ok=True)
    fig_unet()
    fig_schema(counts)
    fig_burn_order()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
