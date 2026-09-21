"""OpenTopography's mitigation, applied: grid the DEM by averaging across
scan lines instead of triangulating between them.

THE REASONING, SHORT
--------------------
OpenTopography's FAQ on corduroy says three things. The corduroy is in the raw
data, so the point cloud cannot be repaired by us -- the real fix, strip
adjustment, needs trajectory files a LAZ delivery does not carry. Failing that,
coarsen the grid; failing that, switch to local gridding.

Coarsening is anti-aliasing against a known wavelength. The ripple's wavelength
is the scan-line spacing, about 0.65 m. A 0.5 m cell is SMALLER than that, so a
cell can be dominated by one line and the ripple survives at full amplitude.
1 m straddles about 1.5 lines, which is why it only took the RRIM from x3.70 to
x2.72 -- a quarter off, no more.

Local gridding is a different lever, and this is the point. A Delaunay TIN
honours every point exactly and its support is the triangle, so it CANNOT
average across scan lines at any cell size -- that is what a TIN is, not a
tuning choice. Local gridding gathers everything inside a RADIUS, and the radius
is independent of the cell. So smoothing stops costing resolution.

That matters because a median pit floor is 6 m across: 3 cells at a 2 m grid,
but 12 cells at 0.5 m with a 2 m radius.

WHY MEAN AND NOT IDW, AND WHY NOT PDAL'S DEFAULT RADIUS
-------------------------------------------------------
An earlier attempt used output_type=idw with power 2, which weights by 1/d^2 --
a point at 0.2 m outweighs one at 3 m by 225 times. Despite a 3 m radius it
behaved far more like nearest-neighbour than like an average, and only halved
the spike. Here the job is uniform averaging ACROSS lines, so output_type=mean
with an explicit radius is the right tool.

PDAL's default radius is resolution * sqrt(2), 0.71 m at a 0.5 m cell. That is
barely one line spacing and would do essentially nothing. The radius is the
whole mechanism and the default is useless for this.

RADIUS IS A TRADE, NOT A FREE PARAMETER
---------------------------------------
Too small and it spans too few lines to cancel the ripple. Too large and it
blurs the 6 m pit the whole project is trying to detect. 1.5 m spans roughly
five line spacings while staying well inside a pit, so that is the default, and
the sweep below shows what each choice costs.

WHAT IS NOT CLAIMED
-------------------
Nothing here explains WHY the ripple varies from place to place. Two mechanisms
were proposed and both were refuted by measurement -- per-sweep alternation
(the lag-1 correlation came out positive, and higher in the CLEAN window) and
scan-angle-driven attitude error (the highest-angle window measured is the
cleanest of the three). Terrain roughness tracks it across three windows, which
is suggestive and no more. The mitigation does not depend on the mechanism.

METHOD: PDAL CLI via subprocess with a pipeline JSON. The Python bindings do not
function in this environment (CLAUDE.md).

Run:
    python notebooks/wellsight_v2/s7_analysis/_destripe_dem_mean_radius_9t.py
    ... --radii 0.75 1.5 2.5 --side 600
Writes, into data/9t/derived/destripe_spot/:
    dem_tin_spot_9t_0p5m.tif
    dem_mean_r{R}_spot_9t_0p5m.tif    one per radius
    rrim_mean_r{R}_spot_9t_0p5m.tif
    destripe_spike_9t.json
and docs/presentation/figures_30to45min/v6/destripe_dem_mean_radius_9t.png
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks/wellsight_v2/s1_build"))
OUT = ROOT / "data/9t/derived/destripe_spot"
FIG = ROOT / "docs/presentation/figures_30to45min/v6"
PDAL = "pdal"

#: The spot the artefact was reported at: 41.496597, -79.516534.
CX, CY = 623822.4, 4594948.6
CELL = 0.5
#: Openness look distance, 25 m, matching every other 9t product.
OPENNESS_M = 25.0
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
        print(r.stdout[-1200:]); print(r.stderr[-1200:])
        raise RuntimeError(f"{label} failed, exit {r.returncode}")


def tiles_covering(b):
    """Both source directories. Searching only OTHER_DATA once left 20% of a
    window empty and put a 600 m straight edge through every measurement."""
    import laspy
    seen, out = set(), []
    for d in (ROOT / "data/_source/lidar/westernpa",
              ROOT / "data/_source/lidar/westernpa/OTHER_DATA"):
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
        nod, res, prof = r.nodata, abs(r.transform.a), r.profile
    if nod is not None:
        a[a == nod] = np.nan
    a[a < -1e6] = np.nan
    return a, res, prof


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
        return np.nan
    return float(np.nanmax(sc[d <= HALF]) / base)


def derive(dem, res):
    """Slope and the two openness rasters, by the project's own functions."""
    from _build_derivatives import openness
    z = dem.astype("float32")
    gy, gx = np.gradient(z, res)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    op, on = openness(z, L_cells=int(OPENNESS_M / res), cellsize=res)
    return slope, op, on


def make_rrim(slope, op, on, slope_hi=40.0, do_pct=98.0, base_bright=18.0):
    """Chiba 2008 RRIM, the same arithmetic as _make_rrim.build_rrim, taking
    arrays instead of filenames so it can run on a surface that is not on disk
    under the project's naming convention."""
    TEAL = np.array([0, 158, 162], float)
    GRAY = np.array([138, 138, 138], float)
    YELLOW = np.array([254, 255, 172], float)
    WHITE = np.array([255, 255, 255], float)
    RED = np.array([182, 39, 0], float)
    do = (op - on) / 2.0
    valid = np.isfinite(slope) & np.isfinite(do)
    dlim = np.nanpercentile(np.abs(do[np.isfinite(do)]), do_pct)
    t = np.nan_to_num(np.clip(do / dlim, -1, 1), nan=0.0)[..., None]
    base = np.where(t < 0, GRAY + (TEAL - GRAY) * (-t),
                    GRAY + (YELLOW - GRAY) * t) + base_bright
    u = np.clip(np.nan_to_num(slope, nan=0.0) / slope_hi, 0, 1)[..., None]
    rrim = np.clip(base, 0, 255) * (WHITE + (RED - WHITE) * u) / 255.0
    rrim = np.clip(rrim, 0, 255)
    rrim[~valid] = 255.0
    return rrim.astype("uint8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", type=float, default=600.0)
    ap.add_argument("--radii", type=float, nargs="+", default=[0.75, 1.5, 2.5])
    a = ap.parse_args()

    h = a.side / 2.0
    b = (CX - h, CY - h, CX + h, CY + h)
    OUT.mkdir(parents=True, exist_ok=True)
    laz = tiles_covering(b)
    x0 = np.floor(b[0] / CELL) * CELL
    y0 = np.floor(b[1] / CELL) * CELL
    w = int(np.ceil((b[2] - x0) / CELL))
    ht = int(np.ceil((b[3] - y0) / CELL))
    print(f"{a.side:.0f} m at {CX} E {CY} N, {len(laz)} tiles, "
          f"{w}x{ht} at {CELL} m")

    # filters.merge is required: without it PDAL runs the chain once per reader
    # and the writer keeps only the last, blanking everything past a tile seam
    head = laz + [
        {"type": "filters.merge"},
        {"type": "filters.crop",
         "bounds": f"([{b[0]},{b[2]}],[{b[1]},{b[3]}])"},
        {"type": "filters.expression", "expression": "Classification == 2"},
    ]
    grid = dict(resolution=CELL, origin_x=x0, origin_y=y0,
                width=w, height=ht)

    builds = []
    p_tin = OUT / f"dem_tin_spot_9t_0p5m.tif"
    run_pipeline(head + [
        {"type": "filters.delaunay"},
        {"type": "filters.faceraster", **grid},
        {"type": "writers.raster", "filename": str(p_tin),
         "data_type": "float32"},
    ], "TIN")
    builds.append(("TIN (current)", p_tin))

    for R in a.radii:
        tok = f"{R:g}".replace(".", "p")
        p = OUT / f"dem_mean_r{tok}_spot_9t_0p5m.tif"
        run_pipeline(head + [
            {"type": "writers.gdal", "filename": str(p),
             "output_type": "mean", "radius": R,
             "data_type": "float32", **grid},
        ], f"mean r={R}")
        builds.append((f"mean, radius {R:g} m", p))

    res_j = {"window": list(b), "cell_m": CELL, "results": []}
    panels = []
    print("\n  surface                spike: DEM   slope   op_neg    RRIM   void")
    for label, p in builds:
        dem, r_, prof = read(p)
        slope, op, on = derive(np.nan_to_num(dem, nan=np.nanmean(dem)), r_)
        rrim = make_rrim(slope, op, on)
        lum = (0.299 * rrim[..., 0] + 0.587 * rrim[..., 1]
               + 0.114 * rrim[..., 2]).astype("float32")
        s = dict(dem=spike(dem, r_), slope=spike(slope, r_),
                 op_neg=spike(on, r_), rrim=spike(lum, r_),
                 void_pct=float(100 * np.mean(~np.isfinite(dem))))
        res_j["results"].append(dict(surface=label, path=str(p), **s))
        panels.append((label, rrim, s))
        print(f"  {label:<22} {s['dem']:7.2f} {s['slope']:7.2f} "
              f"{s['op_neg']:7.2f} {s['rrim']:7.2f}  {s['void_pct']:5.2f}%")

        if label != "TIN (current)":
            tok = p.stem.split("_")[2]
            rp = OUT / f"rrim_mean_{tok}_spot_9t_0p5m.tif"
            pr = dict(prof)
            pr.update(count=3, dtype="uint8", nodata=None, compress="deflate",
                      photometric="RGB")
            with rasterio.open(rp, "w", **pr) as ds:
                for i in range(3):
                    ds.write(rrim[..., i], i + 1)

    print("\n  1.00 would mean no spike at the scan bearing at all.")
    (OUT / "destripe_spike_9t.json").write_text(
        json.dumps(res_j, indent=2), encoding="utf-8")
    figure(panels)
    print(f"\n  {OUT}")
    return 0


def figure(panels):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(4.7 * n, 5.7))
    fig.patch.set_facecolor(PAPER)
    for ax, (label, rrim, s) in zip(np.atleast_1d(axes), panels):
        ax.imshow(rrim, interpolation="nearest")
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")
        ax.set_title(label, loc="left", fontsize=14, fontweight="bold",
                     color=INK)
        good = s["rrim"] < 1.5
        ax.set_xlabel(f"RRIM spike ×{s['rrim']:.2f}   "
                      f"DEM ×{s['dem']:.2f}",
                      fontsize=12.5, fontweight="bold",
                      color=("#1F5FA8" if good else "#A31515"))
    fig.suptitle("Averaging across the scan lines, instead of triangulating "
                 "between them",
                 x=0.008, y=0.985, ha="left", va="top", fontsize=17,
                 fontweight="bold", color=INK)
    fig.text(0.008, 0.932,
             "all at 0.5 m cells — only the radius changes  ·  "
             "×1.0 would mean no scan-line stripe at all",
             fontsize=12, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "destripe_dem_mean_radius_9t.png"
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p}")


if __name__ == "__main__":
    raise SystemExit(main())
