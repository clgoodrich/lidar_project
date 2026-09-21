"""Does IDW gridding remove the scan-line spike that TIN leaves in the DEM?

WHERE THIS CAME FROM
--------------------
The corn rows are visible on the RRIM at 41.496597, -79.516534. Measuring the
prominence of the spike at the 78 degree scan bearing, against the local
baseline 15 to 45 degrees away, at that spot:

    DEM           9.03        slope          1.68
    lrm_5        10.14        openness_neg   3.71
    hillshade     6.70        RRIM           3.70

and at the corn-row panel 300 m away, the same layers score about 1.0. So it is
real, it is strong, and it is LOCAL -- which is why three hand-picked windows
missed it and reported the RRIM clean.

IT ORIGINATES IN THE DEM, NOT THE DSM. The DSM's corn rows are missing data,
and the DEM has no voids at all. But the DEM still scores 9.03 here, and every
layer built from it inherits that. The DSM is a separate problem that stops at
the CHM.

WHY, AND IT IS NOT WHAT I FIRST GUESSED. Sparse ground returns was the obvious
explanation and it is wrong: ground density at this spot is 0.601 returns per
cell against 0.376 at the clean panel. Denser, not sparser.

`notebooks/wellsight/preprocessing/dem_idw_builder.py` already documents the
real one, from OpenTopography's FAQ on exactly this artefact: interswath
inconsistency. Where two flight lines disagree slightly about the ground, a
Delaunay TIN renders the disagreement as long stretched triangles aligned with
the strip edge. The published mitigation is, in order, a coarser grid, and if
that fails, a different gridding algorithm -- IDW, which averages every ground
return within a radius instead of triangulating between them.

The 9t audit recorded in that module found 19.6% of overlap cells exceed the
USGS Delta-z 8 cm spec on this delivery, so the precondition holds.

Step one has now been tried: 1 m takes the RRIM from 3.70 to 2.72. Better, not
fixed. This tests step two.

WHAT IT BUILDS
--------------
A 600 m window at the spot, four DEMs: TIN and IDW, each at 0.5 m and 1 m, all
on nested origins so the grids line up. Then the spike prominence of each.

METHOD: PDAL CLI via subprocess with a pipeline JSON. The Python bindings do
not function in this environment (CLAUDE.md).

Run:
    python notebooks/wellsight_v2/s7_analysis/_dem_tin_vs_idw_spike_9t.py
Writes, into data/9t/derived/tin_vs_idw_spot/:
    dem_tin_spot_9t_{0p5m,1m}.tif
    dem_idw_spot_9t_{0p5m,1m}.tif
    tin_vs_idw_spike_9t.json
and docs/presentation/figures_30to45min/v6/dem_tin_vs_idw_9t.png
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
OUT = ROOT / "data/9t/derived/tin_vs_idw_spot"
FIG = ROOT / "docs/presentation/figures_30to45min/v6"
PDAL = "pdal"

#: The spot the artefact was reported at.
CX, CY = 623822.4, 4594948.6
SIDE = 600.0
CELLS = ((0.5, "0p5m"), (1.0, "1m"))

#: IDW radius. PDAL's default is resolution * sqrt(2), which is barely wider
#: than one cell and cannot average across a strip edge. The point of IDW here
#: is to span the disagreement, so the radius has to exceed it -- 3 m, about
#: three times the scan-line spacing.
IDW_RADIUS_M = 3.0
IDW_POWER = 2.0

SCAN_BRG, HALF, BASE_LO, BASE_HI, HP_M = 78.0, 6.0, 15.0, 45.0, 8.0
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


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
    """Every source tile touching the window, from BOTH source directories.

    Searching only OTHER_DATA found one tile for this window and left 20% of
    it empty, which put a 600 m straight edge through the raster and inflated
    every directional measurement taken on it. The same tile can appear in both
    directories, so they are keyed by filename and counted once.
    """
    import laspy
    seen, out = set(), []
    for d in (ROOT / "data/_source/lidar/westernpa", SRC):
        for f in sorted(d.glob("*.laz")):
            if ".copc." in f.name or f.name in seen:
                continue
            with laspy.open(f) as rd:
                lo, hi = rd.header.mins, rd.header.maxs
            if lo[0] > b[2] or hi[0] < b[0] or lo[1] > b[3] or hi[1] < b[1]:
                continue
            seen.add(f.name)
            out.append(str(f))
    return out


def read(path):
    with rasterio.open(path) as r:
        a = r.read(1).astype("float32")
        nod = r.nodata
        res = abs(r.transform.a)
    if nod is not None:
        a[a == nod] = np.nan
    a[a < -1e6] = np.nan
    return a, res


def power(a, brg, res):
    ny, nx = a.shape
    yy, xx = np.mgrid[0:ny, 0:nx].astype("float32")
    r = np.radians(brg)
    perp = (xx * np.cos(r) + yy * np.sin(r)) * res
    fin = np.isfinite(a)
    if fin.sum() < 1500:
        return np.nan
    v = a[fin] - np.nanmean(a[fin])
    p = perp[fin]
    bins = np.arange(p.min(), p.max() + res, res)
    idx = np.clip(((p - bins[0]) / res).astype(int), 0, len(bins) - 2)
    cnt = np.bincount(idx, minlength=len(bins) - 1)
    tot = np.bincount(idx, weights=v, minlength=len(bins) - 1)
    ok = cnt > 15
    if ok.sum() < 40:
        return np.nan
    prof = (tot / np.maximum(cnt, 1))[ok]
    w = max(3, int(round(HP_M / res)) | 1)
    hp = prof - np.convolve(prof, np.ones(w) / w, mode="same")
    if len(hp) > 2 * w + 10:
        hp = hp[w:-w]
    return float(np.var(hp))


def spike(a, res):
    brgs = np.arange(0.0, 180.0, 1.0)
    sc = np.array([power(a, b, res) for b in brgs])
    d = np.minimum(np.abs(brgs - SCAN_BRG), 180 - np.abs(brgs - SCAN_BRG))
    base = np.nanmedian(sc[(d >= BASE_LO) & (d <= BASE_HI)])
    if not np.isfinite(base) or base <= 0:
        return np.nan, sc
    return float(np.nanmax(sc[d <= HALF]) / base), sc


def main() -> int:
    h = SIDE / 2.0
    b = (CX - h, CY - h, CX + h, CY + h)
    OUT.mkdir(parents=True, exist_ok=True)
    laz = tiles_covering(b)
    print(f"window {SIDE:.0f} m at {CX} E {CY} N, {len(laz)} tiles")

    grids, res_j = {}, {"window": list(b), "idw_radius_m": IDW_RADIUS_M,
                        "results": []}
    for cell, tok in CELLS:
        x0 = np.floor(b[0] / cell) * cell
        y0 = np.floor(b[1] / cell) * cell
        w = int(np.ceil((b[2] - x0) / cell))
        ht = int(np.ceil((b[3] - y0) / cell))
        # filters.merge is required: without it PDAL runs the chain once per
        # reader and the writer keeps only the last one
        head = laz + [
            {"type": "filters.merge"},
            {"type": "filters.crop",
             "bounds": f"([{b[0]},{b[2]}],[{b[1]},{b[3]}])"},
            {"type": "filters.expression", "expression": "Classification == 2"},
        ]

        p_tin = OUT / f"dem_tin_spot_9t_{tok}.tif"
        run_pipeline(head + [
            {"type": "filters.delaunay"},
            {"type": "filters.faceraster", "resolution": cell,
             "origin_x": x0, "origin_y": y0, "width": w, "height": ht},
            {"type": "writers.raster", "filename": str(p_tin),
             "data_type": "float32"},
        ], f"TIN {cell} m")

        p_idw = OUT / f"dem_idw_spot_9t_{tok}.tif"
        run_pipeline(head + [
            {"type": "writers.gdal", "filename": str(p_idw),
             "output_type": "idw", "resolution": cell,
             "radius": IDW_RADIUS_M, "power": IDW_POWER,
             "origin_x": x0, "origin_y": y0, "width": w, "height": ht,
             "data_type": "float32"},
        ], f"IDW {cell} m")

        for how, p in (("TIN", p_tin), ("IDW", p_idw)):
            a, r_ = read(p)
            s, _ = spike(a, r_)
            grids[(how, cell)] = a
            res_j["results"].append(dict(method=how, cell_m=cell,
                                         spike=s, path=str(p)))
            print(f"  {how} {cell:g} m   spike {s:6.2f}   "
                  f"void {100*np.mean(~np.isfinite(a)):.2f}%   {p.name}")

    print("\n  prominence 1.0 = no spike at the scan bearing.")
    (OUT / "tin_vs_idw_spike_9t.json").write_text(
        json.dumps(res_j, indent=2), encoding="utf-8")
    figure(grids, res_j)
    print(f"\n  {OUT}")
    return 0


def figure(grids, res_j):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = [("TIN", 0.5), ("IDW", 0.5), ("TIN", 1.0), ("IDW", 1.0)]
    fig, axes = plt.subplots(1, 4, figsize=(19.4, 5.6))
    fig.patch.set_facecolor(PAPER)
    look = {r["method"] + str(r["cell_m"]): r["spike"] for r in res_j["results"]}

    for ax, k in zip(axes, keys):
        a = grids[k]
        # a hillshade of each DEM, because striping in an elevation ramp is
        # invisible and striping in a shaded relief is the whole complaint
        gy, gx = np.gradient(np.nan_to_num(a, nan=np.nanmean(a)))
        az, alt = np.radians(315.0), np.radians(45.0)
        slope = np.arctan(np.hypot(gx, gy))
        aspect = np.arctan2(-gx, gy)
        hs = (np.sin(alt) * np.cos(slope)
              + np.cos(alt) * np.sin(slope) * np.cos(az - aspect))
        ax.imshow(hs, cmap="gray", vmin=np.nanpercentile(hs, 2),
                  vmax=np.nanpercentile(hs, 98), interpolation="nearest")
        s = look[k[0] + str(k[1])]
        ax.set_title(f"{k[0]}, {k[1]:g} m", loc="left", fontsize=14,
                     fontweight="bold", color=INK)
        ax.set_xlabel(f"scan-line spike  ×{s:.2f}", fontsize=12.5,
                      color=("#A31515" if s > 1.8 else "#1F5FA8"),
                      fontweight="bold")
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")

    fig.suptitle("The DEM is where the striping starts — TIN against IDW",
                 x=0.008, y=0.985, ha="left", va="top", fontsize=17,
                 fontweight="bold", color=INK)
    fig.text(0.008, 0.935,
             f"hillshaded so the striping is visible  ·  "
             f"{SIDE:.0f} m at {CX:.0f} E {CY:.0f} N  ·  "
             f"IDW radius {IDW_RADIUS_M:g} m  ·  "
             "×1.0 would mean no spike at the scan bearing",
             fontsize=12, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "dem_tin_vs_idw_9t.png"
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p}")


if __name__ == "__main__":
    raise SystemExit(main())
