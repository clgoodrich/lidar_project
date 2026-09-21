"""The corn rows in the RRIM, at 0.5 m and at 1 m. Nothing else claimed.

WHY A NEW FIGURE
----------------
Two figures for this already exist and neither can go on a slide:

  rrim_05_vs_1m_9t.png     its subtitle says "the grain runs with the flight
                           lines, not the scan lines" and "1 m does not reduce
                           it". Both came from an argmax-over-bearing test that
                           could not see a narrow spike next to a broad hump,
                           and both were withdrawn.
  rrim_grain_bearing_9t.png  same method, and its legend still shows the 120
                           deg answer that test produced.

So this one shows the thing and says nothing about mechanism. Same window,
same colour treatment, two cell sizes. The viewer can see the stripes at 0.5 m
and see them gone at 1 m, which is the only claim the slides make.

WINDOW
------
623822 E 4594949 N (41.496597 N, -79.516534 W), 240 m. This is the spot the
striping was reported at by eye, so it is the fair place to show it. The
earlier corn-row window 2.5 km west shows the texture much more weakly and
would have understated the problem.

COLOUR
------
RRIM is a 3-band composite and is shown as raw RGB with no enhancement, which
is how QGIS renders it in the project. Its palette is the Chiba red-relief
ramp: reddish where relief is strong, cyan-grey where it is not. There is no
green carrying a separate meaning, so the CLAUDE.md red/green pair rule is not
engaged. The labels are the only added ink and they are neutral.

Run:
    python docs/presentation/figures_30to45min/_rrim_corn_rows_05_vs_1m_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/rrim_corn_rows_05_vs_1m_9t.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
SRC = {
    "0.5 m cell": ROOT / "data/9t/derived/05/rrim_openness_9t_05.tif",
    "1 m cell": ROOT / "data/9t/derived/1m/rrim_openness_9t_1m.tif",
}
OUT = (ROOT / "docs/presentation/figures_30to45min/v6"
       / "rrim_corn_rows_05_vs_1m_9t.png")

#: 41.496597 N, -79.516534 W -- the spot where the stripes were
#: reported by eye on the RRIM, not a window picked to flatter the
#: comparison.
CX, CY = 623822.4, 4594948.6
SIDE = 240.0

INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def read_rgb(path, b):
    with rasterio.open(path) as s:
        w = from_bounds(*b, transform=s.transform)
        a = s.read(window=w, boundless=True, fill_value=0)
    a = a[:3].astype("float32")
    if a.max() > 1.5:                       # 8-bit composite
        a /= 255.0
    return np.clip(np.moveaxis(a, 0, -1), 0, 1)


def main() -> int:
    missing = [str(p) for p in SRC.values() if not p.exists()]
    if missing:
        raise SystemExit("missing RRIM:\n  " + "\n  ".join(missing))

    h = SIDE / 2.0
    b = (CX - h, CY - h, CX + h, CY + h)

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 7.0))
    fig.patch.set_facecolor(PAPER)
    for ax, (label, path) in zip(axes, SRC.items()):
        ax.imshow(read_rgb(path, b), extent=(b[0], b[2], b[1], b[3]))
        ax.set_title(label, loc="left", fontsize=17, fontweight="bold",
                     color=INK, pad=9)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")

    fig.suptitle("The corn rows in the RRIM, and what one metre does to them",
                 x=0.008, y=0.985, ha="left", va="top", fontsize=21,
                 fontweight="bold", color=INK)
    fig.text(0.008, 0.055,
             f"Same {SIDE:.0f} m window at {CX:.0f} E {CY:.0f} N, same colour "
             "treatment. Only the cell size changes.",
             fontsize=12.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.075, 1, 0.945))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=165, facecolor=PAPER)
    plt.close(fig)
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
