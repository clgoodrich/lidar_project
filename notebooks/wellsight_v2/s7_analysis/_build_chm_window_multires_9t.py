"""Rebuild the CHM-panel window at 0.5, 1 and 2 m, and see what the corn rows do.

WHY
---
`_void_rate_vs_cell_size_9t.py` measured the RAW exposure: at 0.5 m, 43.4% of
cells over the tile hold no first return, falling to 6.5% at 1 m and 0.1% at
2 m. That is occupancy, not product. The delivered 0.5 m DSM is only 2.04% empty
because the TIN closes nearly all of it, so the question the occupancy table
cannot answer is the one that matters: how much of the REMAINDER -- the corn
rows -- survives a coarser grid.

This builds the same three surfaces the project already builds, by the same
route, at three cell sizes over one window, and counts what is left empty.

SAME ROUTE ON PURPOSE. Delaunay TIN plus faceraster, which is what
phase_1_derivative_generation.ipynb builds and what every other 9t product came
from. Changing the interpolator at the same time as the cell size would leave
two variables moving and the comparison would mean nothing.

THE WINDOW is the CHM panel's own 300 m square, from LAT/LON/SIDE_M in
docs/presentation/figures_30to45min/_build_derivative_panel.py, so the result
lays directly over the slide.

GRIDS ARE ALIGNED, NOT MERELY THE SAME SIZE. Every origin is snapped to a
multiple of its own cell so a 2 m cell contains exactly four 1 m cells and
sixteen 0.5 m cells. Without that the void percentages would differ partly
because the grids are offset from each other.

CHM IS DSM MINUS DEM AT THE SAME RESOLUTION, computed here rather than resampled
from the 0.5 m product -- resampling would carry the 0.5 m holes into the
coarser grid and guarantee the answer this is trying to measure.

METHOD: PDAL CLI via subprocess with a pipeline JSON. The Python bindings do not
function in this environment (CLAUDE.md).

Run:
    python notebooks/wellsight_v2/s7_analysis/_build_chm_window_multires_9t.py
Writes, into data/9t/derived/multires_chm_window/:
    dsm_chmwindow_9t_{0p5,1,2}m.tif
    dem_chmwindow_9t_{0p5,1,2}m.tif
    chm_chmwindow_9t_{0p5,1,2}m.tif
    void_rate_by_resolution_chmwindow_9t.json
and the figure
    docs/presentation/figures_30to45min/v6/chm_window_multires_9t.png
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
OUT = ROOT / "data/9t/derived/multires_chm_window"
FIG = ROOT / "docs/presentation/figures_30to45min/v6"
PDAL = "pdal"

#: The CHM panel's window, from _build_derivative_panel.py.
CX, CY, SIDE = 621359.6, 4594467.4, 300.0
#: Cell sizes, and the filename token each uses (Descriptive-filename rule:
#: decimals are written 0p5, never 0.5, so the name stays shell and GDAL safe).
CELLS = ((0.5, "0p5m"), (1.0, "1m"), (2.0, "2m"))

#: THE TWO SURFACES ARE NOT BUILT THE SAME WAY, and copying one route for both
#: is what made the first run of this script meaningless.
#:
#:   DEM   ground class -> filters.delaunay -> filters.faceraster. A TIN spans
#:         every gap no matter how wide, so the DEM has no holes at all. That
#:         is why dem_9t_05.tif measures 0.00% void, and it is a property of
#:         the interpolator, not of the coverage.
#:
#:   DSM   first returns -> writers.gdal, output_type "max". No TIN. Each point
#:         fills every cell within PDAL's default radius, which is
#:         resolution * sqrt(2) -- 0.71 m at a 0.5 m cell. So the DSM DOES have
#:         holes: the cells with no first return inside that reach.
#:
#: Both from _build_derivatives.py, which is what produced every 9t product.
#: The reach scaling with the cell is the reason this comparison is worth
#: running at all: coarsening widens the search as well as the cell.
DEM_EXPR = "Classification == 2"
DSM_EXPR = "ReturnNumber == 1"


def run_pipeline(stages, label, timeout=3600):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-1500:])
        print(r.stderr[-1500:])
        raise RuntimeError(f"{label} failed, exit {r.returncode}")


def tiles_covering(b):
    import laspy
    out = []
    for f in sorted(SRC.glob("*.laz")):
        with laspy.open(f) as rd:
            lo, hi = rd.header.mins, rd.header.maxs
        if lo[0] > b[2] or hi[0] < b[0] or lo[1] > b[3] or hi[1] < b[1]:
            continue
        out.append(str(f))
    return out


def read(path):
    with rasterio.open(path) as r:
        a = r.read(1).astype("float32")
        nod = r.nodata
    if nod is not None:
        a[a == nod] = np.nan
    a[a < -1000.0] = np.nan
    return a


def main() -> int:
    h = SIDE / 2.0
    b = (CX - h, CY - h, CX + h, CY + h)
    OUT.mkdir(parents=True, exist_ok=True)
    laz = tiles_covering(b)
    print(f"window {b[0]:.1f} {b[1]:.1f} {b[2]:.1f} {b[3]:.1f}")
    print(f"  {len(laz)} source tiles")

    res = {"window": list(b), "by_cell": []}
    grids = {}
    for cell, tok in CELLS:
        # snap the origin down to a whole multiple of this cell, so the three
        # grids nest instead of merely matching in size
        x0 = np.floor(b[0] / cell) * cell
        y0 = np.floor(b[1] / cell) * cell
        w = int(np.ceil((b[2] - x0) / cell))
        ht = int(np.ceil((b[3] - y0) / cell))
        print(f"\n{cell} m  origin {x0:.1f} {y0:.1f}  {w} x {ht}")

        # EXPLICIT MERGE on both. Without it PDAL ran the chain once per reader
        # and the writer kept only the last, so everything north of the
        # 4594500 tile seam came out empty -- 39% void at every cell size and
        # identical for DSM and DEM, which is the tell: a real void rate cannot
        # match to two decimal places across two different filters.
        head = laz + [
            {"type": "filters.merge"},
            {"type": "filters.crop",
             "bounds": f"([{b[0]},{b[2]}],[{b[1]},{b[3]}])"},
        ]
        made = {}

        dem_tif = OUT / f"dem_chmwindow_9t_{tok}.tif"
        run_pipeline(head + [
            {"type": "filters.expression", "expression": DEM_EXPR},
            {"type": "filters.delaunay"},
            {"type": "filters.faceraster", "resolution": cell,
             "origin_x": x0, "origin_y": y0, "width": w, "height": ht},
            {"type": "writers.raster", "filename": str(dem_tif),
             "data_type": "float32"},
        ], f"dem at {cell} m")
        made["dem"] = read(dem_tif)
        print(f"  {dem_tif.name}  void "
              f"{100*np.mean(~np.isfinite(made['dem'])):.2f}%")

        dsm_tif = OUT / f"dsm_chmwindow_9t_{tok}.tif"
        run_pipeline(head + [
            {"type": "filters.expression", "expression": DSM_EXPR},
            {"type": "writers.gdal", "filename": str(dsm_tif),
             "output_type": "max", "resolution": cell,
             "origin_x": x0, "origin_y": y0, "width": w, "height": ht,
             "data_type": "float32"},
        ], f"dsm at {cell} m")
        made["dsm"] = read(dsm_tif)
        print(f"  {dsm_tif.name}  void "
              f"{100*np.mean(~np.isfinite(made['dsm'])):.2f}%")

        # The outermost ring of cells sits outside the Delaunay hull, so the
        # TIN cannot reach it and every DEM comes out with a one-cell border of
        # NoData. That is an artefact of cropping a small window, not a hole in
        # the data, and it scales with the cell -- 0.34% at 0.5 m, 0.67% at
        # 1 m, 1.33% at 2 m, which is just 2/n. Reporting it would exactly
        # invert the finding. Statistics are taken on the interior.
        interior = np.zeros(made["dem"].shape, bool)
        interior[1:-1, 1:-1] = True

        chm = made["dsm"] - made["dem"]
        ctif = OUT / f"chm_chmwindow_9t_{tok}.tif"
        with rasterio.open(OUT / f"dsm_chmwindow_9t_{tok}.tif") as r:
            prof = r.profile
        prof.update(dtype="float32", nodata=float("nan"), count=1)
        with rasterio.open(ctif, "w", **prof) as d:
            d.write(chm.astype("float32"), 1)
        made["chm"] = chm
        print(f"  {ctif.name}  void {100*np.mean(~np.isfinite(chm)):.2f}%")

        grids[cell] = made

        def vpct(a):
            return float(100 * np.mean(~np.isfinite(a[interior])))
        res["by_cell"].append(dict(
            cell_m=cell, shape=[ht, w], n_interior=int(interior.sum()),
            void_dsm=vpct(made["dsm"]), void_dem=vpct(made["dem"]),
            void_chm=vpct(chm)))
        print(f"  interior void   DSM {vpct(made['dsm']):.2f}%   "
              f"DEM {vpct(made['dem']):.2f}%   CHM {vpct(chm):.2f}%")

    print("\nVOID RATE IN THIS WINDOW, BY CELL SIZE")
    print("  cell      DSM       DEM       CHM")
    for r_ in res["by_cell"]:
        print(f"  {r_['cell_m']:.1f} m   {r_['void_dsm']:6.2f}%   "
              f"{r_['void_dem']:6.2f}%   {r_['void_chm']:6.2f}%")

    j = OUT / "void_rate_by_resolution_chmwindow_9t.json"
    j.write_text(json.dumps(res, indent=2), encoding="utf-8")
    figure(grids, res)
    print(f"\n  {OUT}")
    print(f"  {j}")
    return 0


def figure(grids, res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    #: NoData paint, matching NODATA_RGB in _build_derivative_panel.py: the one
    #: candidate clear of the 6-8 relief band against every step of a black to
    #: white ramp, 12.6 protan against #808080. The greyscale carries no green,
    #: so the binding constraint is that this must not read as a grey LEVEL.
    NODATA = "#D97706"
    INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"

    cells = [c for c, _ in CELLS]
    fig, axes = plt.subplots(1, len(cells), figsize=(5.0 * len(cells), 5.9))
    fig.patch.set_facecolor(PAPER)

    # one stretch for all three, so a difference on screen is a difference in
    # the data and not in the scaling
    allv = np.concatenate([grids[c]["chm"][1:-1, 1:-1][
        np.isfinite(grids[c]["chm"][1:-1, 1:-1])].ravel() for c in cells])
    vmin, vmax = 0.0, float(np.percentile(allv, 99))
    cmap = matplotlib.colormaps["gray"].with_extremes(bad=NODATA)

    for ax, c in zip(axes, cells):
        # interior only, same as the statistics: the one-cell hull border is a
        # crop artefact and drawing it would put a NoData frame on every panel
        chm = grids[c]["chm"][1:-1, 1:-1]
        ax.imshow(np.ma.masked_invalid(chm), cmap=cmap, vmin=vmin, vmax=vmax,
                  interpolation="nearest")
        v = 100 * np.mean(~np.isfinite(chm))
        ax.set_title(f"{c:g} m cell", loc="left", fontsize=15,
                     fontweight="bold", color=INK)
        ax.set_xlabel(f"{v:.2f}% of cells have no value",
                      fontsize=12.5, color=NODATA if v > 0.5 else MUTED)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")

    # up beside the title, not bottom-right, where it sat on top of the third
    # panel's caption
    fig.legend(handles=[Patch(facecolor=NODATA, edgecolor="none",
                              label="no data")],
               loc="upper right", bbox_to_anchor=(0.995, 0.995),
               frameon=False, fontsize=12.5)
    fig.suptitle("Canopy height over the same 300 m, built three times",
                 x=0.012, ha="left", fontsize=17, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "chm_window_multires_9t.png"
    fig.savefig(p, dpi=170, facecolor=PAPER)
    plt.close(fig)
    print(f"\n  {p}")


if __name__ == "__main__":
    raise SystemExit(main())
