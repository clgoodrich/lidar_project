"""Does scan angle decide whether an at-ground return gets called ground?

THE CLAIM BEING TESTED
----------------------
Points sitting within +/- 15 cm of the ground surface that the vendor left
unassigned have a median off-nadir scan angle of 18.6 degrees. Class-2 ground
has 9.4. The suspicion is that ground classification leans on the middle of each
flight swath and thins out towards the edges, and that this is why 17.8% of
0.5 m DEM cells hold no ground return at all.

That is an inference from two medians. This script tries to break it.

WHAT WOULD COUNT AS PROOF, AND WHAT WOULD NOT
---------------------------------------------
Two medians differing is weak. Four things together are not:

  A  The full distributions, not their medians. If the two groups overlap
     heavily and only the centres differ, the story is weak.

  B  The classification rate as a function of angle: of the returns that ARE at
     ground level, what share got called ground, binned by scan angle? This is
     the load-bearing panel. It conditions on "this return reached the ground",
     so canopy occlusion -- which also worsens with angle -- is controlled for.
     A sharp knee means a QC rule. A smooth taper means accuracy, not policy.

  C  Where the DEM holes are. If ground thins at swath edges, the cells with no
     ground return should form STRIPES parallel to the flight lines, not a
     random scatter. Geometry the story predicts in advance.

  D  The swath geometry itself, from median scan angle per cell. If C and D
     stripe together, the mechanism is visible rather than argued.

A confound worth naming: at a wide angle the beam is longer and more oblique, so
it is less likely to reach the ground at all. Panel B controls for this by only
ever looking at returns that already did.

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md). One pass per tile, full density.

Run:
    python notebooks/wellsight_v2/s7_analysis/_scan_angle_vs_ground_classification.py
    ... --tile 616591
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "_source" / "lidar" / "westernpa"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "scan_angle"
PDAL = "pdal"

NEAR = 0.15         # "at ground level" = within this of the ground surface
DEM_RES = 0.5       # the DEM's own cell size -- voids are defined on this grid
MAP_RES = 5.0       # display grid for the two maps

SURFACE, INK, INK2, MUTED, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a887e", "#d8d7cf"
GREY, BLUE, VERM = "#B0B0B0", "#1F5FA8", "#C43E1C"
SEQ = LinearSegmentedColormap.from_list("s", ["#fcfcfb", "#9ec4e8", "#1F5FA8",
                                              "#0b2c52"])


def run_pipeline(stages, label, timeout=3600):
    """Write the pipeline to a temp file and shell out. See CLAUDE.md."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-1200:]); print(r.stderr[-1200:])
        raise SystemExit(f"{label} failed, exit {r.returncode}")


def find_tile(code):
    hits = [f for f in sorted(SRC.rglob("*.laz"))
            if not f.name.startswith("_merged")
            and re.search(rf"17T..{code}(\.copc)?\.laz$", f.name)]
    if not hits:
        raise SystemExit(f"no source file for tile {code}")
    return hits[0]


def load(laz):
    tmp = Path(tempfile.gettempdir()) / f"_sa_{laz.stem}.las"
    run_pipeline([
        str(laz),
        {"type": "filters.hag_nn", "count": 8, "allow_extrapolation": True},
        {"type": "writers.las", "filename": str(tmp),
         "extra_dims": "HeightAboveGround=float32", "compression": "false"},
    ], "hag")
    import laspy
    las = laspy.read(str(tmp))
    d = {"x": np.asarray(las.x), "y": np.asarray(las.y),
         "cls": np.asarray(las.classification).astype("int16"),
         "hag": np.asarray(las.HeightAboveGround, dtype="float32"),
         "psid": np.asarray(las.point_source_id).astype("int32")}
    for a in ("scan_angle", "scan_angle_rank"):
        if hasattr(las, a):
            v = np.asarray(getattr(las, a), dtype="float32")
            d["ang"] = np.abs(v * 0.006 if a == "scan_angle" else v)
            break
    tmp.unlink(missing_ok=True)
    return d


def grid(x, y, bb, res, vals=None, how="count"):
    nx = int(np.ceil((bb[2] - bb[0]) / res))
    ny = int(np.ceil((bb[3] - bb[1]) / res))
    c = np.clip(((x - bb[0]) / res).astype(np.int64), 0, nx - 1)
    r = np.clip(((bb[3] - y) / res).astype(np.int64), 0, ny - 1)
    f = r * nx + c
    n = nx * ny
    if how == "count":
        return np.bincount(f, minlength=n).reshape(ny, nx), (nx, ny)
    s = np.bincount(f, weights=vals, minlength=n)
    k = np.bincount(f, minlength=n)
    out = np.divide(s, k, out=np.full(n, np.nan), where=k > 0)
    return out.reshape(ny, nx), (nx, ny)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", default="616591")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    laz = find_tile(args.tile)
    print(f"tile {args.tile}  ({laz.name})")
    d = load(laz)
    bb = (d["x"].min(), d["y"].min(), d["x"].max(), d["y"].max())
    g2 = d["cls"] == 2
    at = np.isfinite(d["hag"]) & (np.abs(d["hag"]) < NEAR)
    ng = at & (d["cls"] == 1)
    print(f"  {d['x'].size:,} pts, {int(g2.sum()):,} ground, "
          f"{int(ng.sum()):,} at-ground unassigned, "
          f"{int(np.unique(d['psid']).size)} flight lines")

    # ---- B: of returns that reached the ground, what share became class 2?
    edges = np.arange(0, 22.5, 1.0)
    mid = 0.5 * (edges[:-1] + edges[1:])
    pool = at & (g2 | (d["cls"] == 1))
    n_pool, _ = np.histogram(d["ang"][pool], bins=edges)
    n_g2, _ = np.histogram(d["ang"][pool & g2], bins=edges)
    rate = np.divide(n_g2, n_pool, out=np.full(mid.size, np.nan),
                     where=n_pool > 50)

    print("\n  scan angle   at-ground returns   became ground")
    for i, m in enumerate(mid):
        if n_pool[i] > 50:
            print(f"    {m:5.1f} deg {n_pool[i]:14,d} {100*rate[i]:14.1f}%")

    # ---- C: DEM void cells on the real 0.5 m grid, shown at MAP_RES
    cnt_g2, _ = grid(d["x"][g2], d["y"][g2], bb, DEM_RES)
    cnt_all, _ = grid(d["x"], d["y"], bb, DEM_RES)
    void = (cnt_all > 0) & (cnt_g2 == 0)
    k = int(MAP_RES / DEM_RES)
    ny, nx = (void.shape[0] // k) * k, (void.shape[1] // k) * k
    voidfrac = void[:ny, :nx].reshape(ny // k, k, nx // k, k).mean(axis=(1, 3))
    cover = (cnt_all[:ny, :nx] > 0).reshape(ny // k, k, nx // k, k).mean(axis=(1, 3))
    voidfrac = np.where(cover > 0.5, voidfrac, np.nan)
    print(f"\n  DEM voids: {100*void.sum()/max((cnt_all>0).sum(),1):.2f}% of "
          f"covered {DEM_RES} m cells")

    # ---- D: swath geometry, median scan angle per cell
    angmap, _ = grid(d["x"], d["y"], bb, MAP_RES, vals=d["ang"].astype("float64"),
                     how="mean")
    angmap = angmap[:voidfrac.shape[0], :voidfrac.shape[1]]

    ok = np.isfinite(voidfrac) & np.isfinite(angmap)
    r = np.corrcoef(voidfrac[ok], angmap[ok])[0, 1]
    print(f"  correlation, void fraction vs mean scan angle: r = {r:+.3f} "
          f"({int(ok.sum()):,} cells)")

    _draw(args.tile, d, g2, ng, edges, mid, n_pool, rate, voidfrac, angmap,
          bb, r)
    return 0


def _draw(code, d, g2, ng, edges, mid, n_pool, rate, voidfrac, angmap, bb, r):
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(2, 2, figsize=(15.4, 12.6))

    # A ---- the two distributions
    a = ax[0, 0]
    for m, col, lab in ((g2, BLUE, f"class 2, ground  ({int(g2.sum()):,})"),
                        (ng, GREY,
                         f"unassigned, at ground level  ({int(ng.sum()):,})")):
        h, _ = np.histogram(d["ang"][m], bins=edges)
        a.step(mid, h / h.sum(), where="mid", color=col, linewidth=2.4,
               label=lab)
        a.fill_between(mid, h / h.sum(), step="mid", color=col, alpha=0.18)
    a.set_xlabel("off-nadir scan angle, degrees", fontsize=11, color=INK2)
    a.set_ylabel("share of the group", fontsize=11, color=INK2)
    a.set_title("A  Where in the swath each group came from", fontsize=13.5,
                fontweight="bold", loc="left", pad=8)
    a.legend(frameon=False, fontsize=10)

    # B ---- the load-bearing panel
    b = ax[0, 1]
    ok = np.isfinite(rate)
    b.plot(mid[ok], 100 * rate[ok], color=BLUE, linewidth=2.6, marker="o",
           markersize=5.5, zorder=3)
    b.fill_between(mid[ok], 0, 100 * rate[ok], color=BLUE, alpha=0.13)
    b.set_ylim(0, 100)
    b.set_xlabel("off-nadir scan angle, degrees", fontsize=11, color=INK2)
    b.set_ylabel("share called ground, %", fontsize=11, color=INK2)
    b.set_title("B  Of returns that DID reach the ground,\n     how many were "
                "classified as ground", fontsize=13.5, fontweight="bold",
                loc="left", pad=8)
    tw = b.twinx()
    tw.bar(mid, n_pool / 1e3, width=0.85, color=MUTED, alpha=0.20, zorder=1)
    tw.set_ylabel("at-ground returns in bin, thousands", fontsize=9.5,
                  color=MUTED)
    tw.tick_params(colors=MUTED, labelsize=9)
    for sp in tw.spines.values():
        sp.set_color(RULE)

    # C, D ---- the maps
    ext = [bb[0], bb[2], bb[1], bb[3]]
    for axx, arr, title, lab, cm in (
            (ax[1, 0], 100 * voidfrac,
             "C  Where the DEM has no ground return",
             "cells with no class-2 return, %", SEQ),
            (ax[1, 1], angmap,
             "D  Swath geometry: mean scan angle",
             "mean off-nadir angle, degrees", SEQ)):
        im = axx.imshow(arr, extent=ext, origin="upper", cmap=cm,
                        interpolation="nearest")
        axx.set_title(title, fontsize=13.5, fontweight="bold", loc="left",
                      pad=8)
        axx.set_xticks([]); axx.set_yticks([]); axx.set_aspect("equal")
        cb = fig.colorbar(im, ax=axx, fraction=0.043, pad=0.015)
        cb.set_label(lab, fontsize=10, color=INK2)
        cb.outline.set_edgecolor(RULE)

    for axx in (ax[0, 0], ax[0, 1]):
        axx.grid(color=RULE, linewidth=0.6, alpha=0.7)
        axx.set_axisbelow(True)
        for sp in ("top", "right"):
            axx.spines[sp].set_visible(False)
    for axx in ax.ravel():
        for sp in axx.spines.values():
            sp.set_color(RULE)
        axx.tick_params(colors=INK2, labelsize=10)

    fig.suptitle(f"Scan angle decides whether an at-ground return becomes "
                 f"class 2   ·   tile {code}",
                 fontsize=16.5, fontweight="bold", x=0.012, ha="left", y=0.985)
    fig.text(0.012, 0.955,
             f"C and D stripe together, r = {r:+.2f} across "
             f"{int(np.isfinite(voidfrac).sum()):,} cells of {MAP_RES:.0f} m",
             fontsize=11, color=INK2)
    fig.subplots_adjust(left=0.055, right=0.965, top=0.915, bottom=0.035,
                        hspace=0.16, wspace=0.14)
    p = OUT / f"scan_angle_vs_ground_classification_{code}.png"
    fig.savefig(p, dpi=185)
    plt.close(fig)
    print(f"\nwrote {p}")


if __name__ == "__main__":
    sys.exit(main())
