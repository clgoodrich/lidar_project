"""Shared figure style for the NISAR work (formal, journal-like). Set 2026-11-21.

Why one module: the process figures were restyled on 2026-11-19 (serif, boxed axes, inward ticks,
framed legends, no plot titles). Result and site figures kept the old default look. Importing this
module gives every figure the same look, so a change is made once.

Rules
  * serif text, black boxed axes, inward ticks on all four sides
  * no plot titles; panels carry a letter and a short label, "(a) HH, summer 2026"
  * say "control spots", never "decoys", in anything a reader sees
  * palette: #1F5FA8 blue, #D97706 orange, #A31515 dark red (lost/found palette; dataviz validator,
    light, --pairs all: worst pair dE 21.1 deutan, 22.6 normal). Greys are labelled context only.
  * 300 dpi, white background

Use
  import _nisar_fig_style as S
  S.apply()
  S.panel(ax, "a", "HH, summer 2026")
  S.save(fig, path)
"""
import matplotlib.pyplot as plt

BLUE, ORANGE, RED = "#1F5FA8", "#D97706", "#A31515"
K, GREY, LIGHT = "black", "#6B7280", "#E5E7EB"

RC = {"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 9,
      "mathtext.fontset": "stix", "axes.linewidth": 0.8, "axes.edgecolor": K, "axes.labelcolor": K,
      "axes.titlesize": 9, "xtick.direction": "in", "ytick.direction": "in", "xtick.top": True,
      "ytick.right": True, "xtick.color": K, "ytick.color": K, "legend.frameon": True,
      "legend.edgecolor": K, "legend.fancybox": False, "legend.framealpha": 1, "legend.fontsize": 7.5,
      "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
      "savefig.dpi": 300}


def apply():
    plt.rcParams.update(RC)


def panel(ax, letter, text=""):
    """Panel label above the top-left corner, in place of a title."""
    ax.text(0, 1.02, f"({letter}) {text}".rstrip(), transform=ax.transAxes, ha="left", va="bottom",
            fontsize=9, color=K)


def map_axes(ax):
    """Image panels: keep the black box, drop tick marks and numbers."""
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(True)
        s.set_color(K)
        s.set_linewidth(0.8)


def save(fig, path):
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(path)
