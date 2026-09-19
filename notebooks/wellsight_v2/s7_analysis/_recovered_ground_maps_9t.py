"""The 9t area with the discarded ground put back: three maps and a section.

WHAT THIS SHOWS
---------------
The PA WesternPA 2019 D20 March-2020 block stops calling anything ground past
18 degrees off nadir, so the delivered ground surface has holes in it that run in
stripes along the edges of the flight swaths. `_smrf_reclassify_ground.py`
measured what filling them back in does on two tiles. This draws it, over the
whole 9t training area, as four pictures:

    1  the ground we were given          vendor class 2 only, holes in red
    2  the ground that was thrown away   the recovered returns, nothing else
    3  the two together                  what is left unmeasured after
    4  a section through a hole          the same ground seen edge-on

THREE SURFACES, ONE GRID
------------------------
Every raster is built the same way from the same points, so a difference between
two of them is a difference in which points were allowed to be ground, and
nothing else:

    vendor            VendorClass == 2
    recovered only    Classification == 2 && VendorClass != 2
    both              Classification == 2 || VendorClass != 2 ... see below

"Both" is the union, not the SMRF answer. SMRF also drops a few hundred points
per tile that the vendor called ground, and this is a picture of adding data,
not of replacing it, so those stay in.

WHY SMRF AND NOT "EVERY RETURN NEAR THE GROUND"
-----------------------------------------------
Height above ground is computed FROM class 2, so inside a hole there is no
surface to measure height against and the answer is an extrapolation. That is
exactly where the recovered points are, which makes "returns within 15 cm of the
ground" circular right where it matters. SMRF classifies ground from scratch with
no reference to the vendor's labels and no angle rule, so it can speak inside the
holes. Its agreement with the vendor where the vendor HAS ground is 0.3% of cells
differing by more than 10 cm, measured in the run this builds on.

THE SECTION LINE IS CHOSEN BY THE DATA
--------------------------------------
Not by eye. The 200 m window holding the most recovered ground is found first,
then every azimuth in 5-degree steps through it is scored by how much recovered
ground the line crosses, and the best one is used. The line therefore cuts across
a hole rather than along one, which is the only orientation that shows anything.

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md). DEMs are Delaunay TIN + faceraster at
0.5 m, which is what `phase_1_derivative_generation.ipynb` builds, so these
surfaces are comparable with every other product in the project.

Run:
    python notebooks/wellsight_v2/s7_analysis/_recovered_ground_maps_9t.py
    ... --workers 3 --slope 0.35
    ... --skip-smrf          reuse the per-tile rasters, redraw only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "_source" / "lidar" / "westernpa" / "OTHER_DATA"
OUT = ROOT / "data" / "9t" / "results" / "recovered_ground_9t"
FIG = ROOT / "docs" / "presentation" / "figures_30to45min" / "1_data_qa" / "recovered_ground_9t"
PDAL = "pdal"

RES = 0.5
BBOX = (619500.0, 4593000.0, 624000.0, 4597500.0)   # the 9t training area
TILES = ["619593", "619594", "619596", "621593", "621594", "621596",
         "622593", "622594", "622596"]

#: Same meaning in all four figures, and NO GREEN ANYWHERE -- a red/green pair
#: is the one a deuteranope cannot read, and the section panel puts the "hole"
#: wash directly behind the "recovered" dots, so they must survive it.
#: Checked with the dataviz validator over ALL pairs, not just adjacent ones:
#:      worst pair #A31515 <-> #D97706   dE 21.1 deutan / 21.5 protan / 22.6 normal
#:      every colour >= 3:1 against the paper
#: The hole wash also carries a hatch, so it is never colour alone.
PAPER, INK, INK2, MUTED, RULE = "#f7f8f6", "#141a1f", "#545c63", "#8a887e", "#d7dad4"
KEPT = "#1F5FA8"      # ground the survey delivered
FOUND = "#D97706"     # ground it recorded and threw away
HOLE = "#A31515"      # no ground measurement here at all

#: Selection expressions. VendorClass is ferried in by the SMRF pass.
#: occupancy is also counted for "anyreturn" -- the denominator for a void is
#: cells the laser actually reached, which is how
#: `_smrf_reclassify_ground.py` measured 15.99% and 12.36%.
SURFACES = {
    "vendorground": "VendorClass == 2",
    "recoveredonly": "Classification == 2 && VendorClass != 2",
    "vendorplusrecovered": "Classification == 2 || VendorClass == 2",
}


# --------------------------------------------------------------------------
def run_pipeline(stages, label, timeout=7200):
    """Write the pipeline to a temp file and shell out. See CLAUDE.md."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    t0 = time.time()
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-1200:]); print(r.stderr[-1200:])
        raise RuntimeError(f"{label} failed, exit {r.returncode}")
    return time.time() - t0


def tile_bounds(laz):
    """Read the footprint from the header rather than decoding the tile name.

    The tile code truncates the easting, so 619500 and 619900 would both write
    themselves "619". Ask the file.
    """
    r = subprocess.run([PDAL, "info", "--summary", str(laz)],
                       capture_output=True, text=True, timeout=300)
    b = json.loads(r.stdout)["summary"]["bounds"]
    return b["minx"], b["miny"], b["maxx"], b["maxy"]


def snap(b):
    """Grid-align a tile footprint to the 9t origin so mosaics line up exactly."""
    x0, y0, x1, y1 = b
    gx, gy = BBOX[0], BBOX[1]
    return (gx + np.floor((x0 - gx) / RES) * RES,
            gy + np.floor((y0 - gy) / RES) * RES,
            gx + np.ceil((x1 - gx) / RES) * RES,
            gy + np.ceil((y1 - gy) / RES) * RES)


def occupancy(las, bounds):
    """Cells that actually contain a ground RETURN, per surface.

    A Delaunay TIN spans its own convex hull, so the DEM has a value everywhere
    including straight across a hole -- those values are interpolation between
    the two rims, not measurement. This is the honest map of where the survey
    put a ground point on the floor, which is what the 15.99% / 12.36% void
    figures in `smrf_ground_reclassification.md` count.
    """
    import laspy
    x0, y0, x1, y1 = bounds
    w, h = int(round((x1 - x0) / RES)), int(round((y1 - y0) / RES))
    f = laspy.read(str(las))
    x, y = np.asarray(f.x), np.asarray(f.y)
    vc = np.asarray(f.VendorClass).astype("int16")
    sc = np.asarray(f.classification).astype("int16")
    del f
    cc = np.floor((x - x0) / RES).astype("int64")
    rr = np.floor((y1 - y) / RES).astype("int64")
    ok = (cc >= 0) & (cc < w) & (rr >= 0) & (rr < h)
    flat = rr[ok] * w + cc[ok]
    sel = {"anyreturn": np.ones(ok.sum(), dtype=bool),
           "vendorground": (vc == 2)[ok],
           "recoveredonly": ((sc == 2) & (vc != 2))[ok],
           "vendorplusrecovered": ((sc == 2) | (vc == 2))[ok]}
    out = {}
    for name, m in sel.items():
        g = np.zeros(w * h, dtype="uint16")
        np.add.at(g, flat[m], 1)
        out[name] = g.reshape(h, w)
    return out


def build_tile(job):
    """SMRF one map square, then rasterise the three surfaces from it."""
    code, slope, keep_las = job
    laz = next(SRC.glob(f"*{code}.laz"))
    las = Path(tempfile.gettempdir()) / f"_rec9t_{code}.las"
    made = []
    try:
        if not (keep_las and las.exists()):
            run_pipeline([
                str(laz),
                {"type": "filters.ferry",
                 "dimensions": "Classification=>VendorClass"},
                {"type": "filters.hag_nn", "count": 8,
                 "allow_extrapolation": True},
                {"type": "filters.outlier", "method": "statistical",
                 "mean_k": 8, "multiplier": 3.0},
                {"type": "filters.smrf", "cell": 1.0, "slope": slope,
                 "window": 18.0, "threshold": 0.5, "scalar": 1.25,
                 "ignore": "Classification[7:7]"},
                {"type": "writers.las", "filename": str(las),
                 "extra_dims": "VendorClass=uint8,HeightAboveGround=float32",
                 "compression": "false"},
            ], f"smrf {code}")

        x0, y0, x1, y1 = snap(tile_bounds(laz))
        w, h = int(round((x1 - x0) / RES)), int(round((y1 - y0) / RES))

        counts = occupancy(las, (x0, y0, x1, y1))
        for name, g in counts.items():
            ctif = OUT / "_tiles" / f"count_{name}_{code}_0p5m.tif"
            ctif.parent.mkdir(parents=True, exist_ok=True)
            write_grid(g, (x0, y0, x1, y1), ctif, "uint16", 0)

        for name, expr in SURFACES.items():
            tif = OUT / "_tiles" / f"{name}_{code}_0p5m.tif"
            tif.parent.mkdir(parents=True, exist_ok=True)
            run_pipeline([
                str(las),
                {"type": "filters.expression", "expression": expr},
                {"type": "filters.delaunay"},
                {"type": "filters.faceraster", "resolution": RES,
                 "origin_x": x0, "origin_y": y0, "width": w, "height": h},
                {"type": "writers.raster", "filename": str(tif),
                 "data_type": "float32"},
            ], f"dem {name} {code}")
            made.append(name)
    except Exception as e:
        return dict(code=code, error=f"{type(e).__name__}: {e}"[:160])
    finally:
        if not keep_las:
            las.unlink(missing_ok=True)
    return dict(code=code, made=made)


# --------------------------------------------------------------------------
def write_grid(arr, bounds, path, dtype, nodata):
    """One small GeoTIFF on an explicit footprint."""
    import rasterio
    from rasterio.transform import from_origin
    x0, y0, x1, y1 = bounds
    with rasterio.open(
            path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
            count=1, dtype=dtype, crs="EPSG:6346",
            transform=from_origin(x0, y1, RES, RES), nodata=nodata,
            compress="deflate", tiled=True) as ds:
        ds.write(arr.astype(dtype), 1)


def mosaic(name, count=False):
    """Paste the nine per-tile rasters onto one 9t grid."""
    import rasterio
    x0, y0, x1, y1 = BBOX
    W, H = int((x1 - x0) / RES), int((y1 - y0) / RES)
    big = (np.zeros((H, W), dtype="float32") if count
           else np.full((H, W), np.nan, dtype="float32"))
    for code in TILES:
        p = OUT / "_tiles" / f"{'count_' if count else ''}{name}_{code}_0p5m.tif"
        if not p.exists():
            print(f"  missing {p.name}")
            continue
        with rasterio.open(p) as ds:
            a = ds.read(1).astype("float32")
            nod = ds.nodata
            if nod is not None and not count:
                a[a == nod] = np.nan
            b = ds.bounds
            c0 = int(round((b.left - x0) / RES))
            r0 = int(round((y1 - b.top) / RES))
            sl = (slice(max(r0, 0), min(r0 + a.shape[0], H)),
                  slice(max(c0, 0), min(c0 + a.shape[1], W)))
            sub = a[:sl[0].stop - sl[0].start, :sl[1].stop - sl[1].start]
            tgt = big[sl]
            np.copyto(tgt, sub, where=np.isfinite(sub))
    return big


def write_tif(arr, path):
    import rasterio
    from rasterio.transform import from_origin
    x0, y0, x1, y1 = BBOX
    with rasterio.open(
            path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
            count=1, dtype="float32", crs="EPSG:6346",
            transform=from_origin(x0, y1, RES, RES), nodata=np.nan,
            compress="deflate", tiled=True, predictor=3) as ds:
        ds.write(np.nan_to_num(arr, nan=np.nan), 1)
    print(f"  wrote {path}")


# --------------------------------------------------------------------------
def hillshade(z, az=315.0, alt=45.0, zf=1.4):
    """Plain Horn hillshade. NaN stays NaN so holes cannot be shaded over."""
    filled = np.where(np.isfinite(z), z, np.nanmedian(z))
    gy, gx = np.gradient(filled, RES, RES)
    slope = np.arctan(zf * np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, z0 = np.radians(az), np.radians(alt)
    hs = (np.sin(z0) * np.cos(slope) +
          np.cos(z0) * np.sin(slope) * np.cos(a - aspect))
    hs = np.clip(hs, 0, 1)
    return np.where(np.isfinite(z), hs, np.nan)


def coarsen(a, k):
    """Block mean that ignores NaN, for a PNG that does not need 81 Mpx."""
    if k <= 1:
        return a
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return np.nanmean(b, axis=(1, 3))


def blocks(a, k, how="mean"):
    """Aggregate to k x k blocks."""
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    return b.sum(axis=(1, 3)) if how == "sum" else b.mean(axis=(1, 3))


def void_fraction(ground, anyret, k):
    """Of the cells the laser reached in this block, what share has no ground.

    A single empty 0.5 m cell is normal -- at ~4.8 points per square metre the
    expected count in a 0.25 m2 cell is about one, so half of them come up empty
    by chance alone. A hole is a REGION where that fraction is high, which is
    why this is drawn as a density and not as a mask.
    """
    g = blocks((ground > 0).astype("float32"), k, "sum")
    a = blocks((anyret > 0).astype("float32"), k, "sum")
    out = np.full(g.shape, np.nan, dtype="float32")
    np.divide(a - g, a, out=out, where=a > 0)
    return out


def density(cnt, k):
    """Ground points per square metre in each block."""
    return blocks(cnt.astype("float32"), k, "sum") / (k * RES) ** 2


def red_overlay(frac, colour, gamma=0.75, amax=0.92):
    """Translucent wash whose opacity IS the value. No second scale to read."""
    rgba = np.zeros(frac.shape + (4,), dtype="float32")
    c = np.array(matplotlib.colors.to_rgb(colour), dtype="float32")
    rgba[..., :3] = c
    v = np.clip(np.nan_to_num(frac, nan=0.0), 0, 1) ** gamma
    rgba[..., 3] = v * amax
    return rgba


def plate(ax, x, y, w, h):
    """Opaque panel behind map furniture, so no label is read off terrain."""
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, transform=ax.transAxes, zorder=7,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        facecolor=PAPER, edgecolor=RULE, linewidth=0.8, alpha=0.93,
        mutation_aspect=1.0))


def scalebar(ax, extent, metres=1000):
    x0, x1, y0, y1 = extent
    plate(ax, 0.655, 0.022, 0.325, 0.062)
    pad = 0.055 * (x1 - x0)
    xa, ya = x1 - pad - metres, y0 + pad * 0.5
    ax.plot([xa, xa + metres], [ya, ya], color=INK, linewidth=4.0,
            solid_capstyle="butt", zorder=9)
    ax.text(xa + metres / 2, ya + 0.011 * (y1 - y0), f"{metres} m",
            ha="center", va="bottom", fontsize=11.5, color=INK,
            fontweight="bold", zorder=9)
    ax.annotate("", xy=(x0 + pad * 0.6, y1 - pad * 0.42),
                xytext=(x0 + pad * 0.6, y1 - pad * 1.30),
                ha="center", va="top", fontsize=13, color=INK,
                fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.2),
                zorder=9)
    ax.text(x0 + pad * 0.6, y1 - pad * 1.42, "N", ha="center", va="top",
            fontsize=13, color=INK, fontweight="bold", zorder=9)
    plate(ax, 0.022, 0.895, 0.062, 0.082)


def base_map(title, subtitle):
    fig, ax = plt.subplots(figsize=(9.6, 10.1))
    ax.set_title(title, fontsize=20, fontweight="bold", loc="left", pad=30,
                 color=INK)
    ax.text(0, 1.012, subtitle, transform=ax.transAxes, fontsize=13,
            color=INK2, va="bottom")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    return fig, ax


def save(fig, name):
    p = FIG / name
    fig.savefig(p, dpi=170, bbox_inches="tight", pad_inches=0.3,
                facecolor=PAPER)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:6.0f} KB  {p}")


def wash_legend(ax, colour, label, lo="none", hi="all of it"):
    """A strip showing what the opacity means, since opacity IS the scale."""
    plate(ax, 0.022, 0.022, 0.56, 0.085)
    cax = ax.inset_axes([0.045, 0.040, 0.30, 0.022])
    ramp = np.linspace(0, 1, 256)[None, :]
    cax.imshow(red_overlay(np.repeat(ramp, 8, axis=0), colour), aspect="auto",
               zorder=8)
    cax.set_zorder(8)
    cax.set_xticks([]); cax.set_yticks([])
    for sp in cax.spines.values():
        sp.set_color(RULE)
    cax.text(0, 1.5, label, transform=cax.transAxes, fontsize=11.5,
             color=INK, fontweight="bold", va="bottom")
    cax.text(0, -0.5, lo, transform=cax.transAxes, fontsize=10, color=INK2,
             va="top")
    cax.text(1, -0.5, hi, transform=cax.transAxes, fontsize=10, color=INK2,
             va="top", ha="right")


def map_vendor(vend, cnt_v, cnt_a, k, kb, extent, stats):
    hs = coarsen(hillshade(vend), k)
    vf = void_fraction(cnt_v, cnt_a, kb)
    fig, ax = base_map("1 — The ground we were given",
                       "the delivered ground surface, and where it rests on "
                       "nothing")
    ax.imshow(hs, cmap="Greys_r", vmin=0.15, vmax=1.0, extent=extent,
              interpolation="bilinear", zorder=1)
    ax.imshow(red_overlay(vf, HOLE), extent=extent, interpolation="bilinear",
              zorder=2)
    wash_legend(ax, HOLE, "share of the ground with no measurement under it")
    scalebar(ax, extent)
    ax.text(0.5, -0.022, f"{stats['void_v']:.1f}% of this area has no ground "
            f"measurement — the surface there is a guess between two rims",
            transform=ax.transAxes, ha="center", va="top", fontsize=13,
            color=HOLE, fontweight="bold")
    save(fig, "map_1_ground_as_delivered_9t_0p5m.png")


def map_recovered(cnt_r, k, kb, extent, stats):
    de = density(cnt_r, kb)
    top = float(np.nanpercentile(de[de > 0], 98)) if (de > 0).any() else 1.0
    fig, ax = base_map("2 — The ground that was thrown away",
                       "the same area, showing only the discarded ground "
                       "points")
    ax.imshow(np.zeros(de.shape), cmap=LinearSegmentedColormap.from_list(
        "p", ["#eceee9", "#eceee9"]), extent=extent, vmin=0, vmax=1, zorder=1)
    ax.imshow(red_overlay(de / max(top, 1e-9), FOUND), extent=extent,
              interpolation="bilinear", zorder=2)
    wash_legend(ax, FOUND, "discarded ground points per square metre",
                "none", f"{top:.1f}")
    scalebar(ax, extent)
    ax.text(0.5, -0.022, f"{stats['rec_pts']:,} ground measurements, thrown "
            f"away in stripes along the edges of the flight paths",
            transform=ax.transAxes, ha="center", va="top", fontsize=13,
            color=FOUND, fontweight="bold")
    save(fig, "map_2_ground_thrown_away_9t_0p5m.png")


def map_both(both, cnt_b, cnt_a, k, kb, extent, stats):
    hs = coarsen(hillshade(both), k)
    vf = void_fraction(cnt_b, cnt_a, kb)
    fig, ax = base_map("3 — Both together",
                       "delivered ground plus the discarded ground, one "
                       "surface")
    ax.imshow(hs, cmap="Greys_r", vmin=0.15, vmax=1.0, extent=extent,
              interpolation="bilinear", zorder=1)
    ax.imshow(red_overlay(vf, HOLE), extent=extent, interpolation="bilinear",
              zorder=2)
    wash_legend(ax, HOLE, "share of the ground with no measurement under it")
    scalebar(ax, extent)
    ax.text(0.5, -0.022, f"{stats['void_b']:.1f}% left with no measurement, "
            f"down from {stats['void_v']:.1f}% — "
            f"{stats['closed']:,} cells filled in",
            transform=ax.transAxes, ha="center", va="top", fontsize=13,
            color=FOUND, fontweight="bold")
    save(fig, "map_3_ground_both_together_9t_0p5m.png")


def to_1m(cnt):
    """Sum the 0.5 m counts into 1 m cells.

    A 0.5 m cell holds about one ground return on average, so an empty one
    means nothing. A 1 m cell holds about four, and an empty 1 m cell with
    returns around it is a real absence. Every gap statement in the section is
    made at this scale.
    """
    h, w = (cnt.shape[0] // 2) * 2, (cnt.shape[1] // 2) * 2
    return cnt[:h, :w].reshape(h // 2, 2, w // 2, 2).sum(axis=(1, 3))


def line_gaps(g1v, g1b, g1a, cx, cy, az, length, n=None):
    """Walk a line over the 1 m grids and report where ground is missing."""
    n = n or int(length) + 1
    t = np.radians(90.0 - az)
    u = np.array([np.cos(t), np.sin(t)])
    ss = np.linspace(0, length, n)
    A = np.array([cx, cy]) - u * length / 2
    px, py = A[0] + u[0] * ss, A[1] + u[1] * ss
    cc = np.floor((px - BBOX[0]) / 1.0).astype(int)
    rr = np.floor((BBOX[3] - py) / 1.0).astype(int)
    ok = (cc >= 0) & (cc < g1v.shape[1]) & (rr >= 0) & (rr < g1v.shape[0])
    hv = np.zeros(n, dtype=bool); hb = np.zeros(n, dtype=bool)
    val = np.zeros(n, dtype=bool)
    hv[ok] = g1v[rr[ok], cc[ok]] > 0
    hb[ok] = g1b[rr[ok], cc[ok]] > 0
    # "no ground here" only means something where the laser reached at all
    val[ok] = g1a[rr[ok], cc[ok]] > 0
    return ss, hv, hb, val


def pick_line(closed, length=300.0, win=None, g1v=None, g1b=None,
              g1a=None):
    """Centre on the worst hole the recovery actually closes, then cross it.

    Scored, not eyeballed. The target is NOT "where are the recovered points"
    -- most of those land in the swath overlap where the vendor already had
    ground, and a line through there shows two identical panels. The target is
    cells where the vendor had NO ground return and the discarded points supply
    one, which is the only place the before/after picture differs.
    """
    k = 100                                   # 50 m blocks
    cov = blocks(closed.astype("float32"), k)
    if win is not None:
        # the section is drawn from ONE tile's points, so the line has to land
        # inside that tile or the corridor comes back empty
        r0, r1, c0, c1 = [v // k for v in win]
        # inset by half the line length, or the line runs off the tile and the
        # far end of the section is drawn from no points at all
        pad = int(np.ceil((length / 2) / (k * RES))) + 1
        m = np.zeros(cov.shape, dtype=bool)
        m[r0 + pad:max(r1 - pad, r0 + pad + 1),
          c0 + pad:max(c1 - pad, c0 + pad + 1)] = True
        cov = np.where(m, cov, -1.0)
    # score the CANDIDATES the panel will actually be judged on: how much of
    # the line has no delivered ground under it but does once the discarded
    # points are added. Top 40 blocks, every azimuth in 5 degree steps.
    flat = np.argsort(cov, axis=None)[::-1][:40]
    best = (None, None, None, -1.0)
    for f in flat:
        r, c = np.unravel_index(f, cov.shape)
        if cov[r, c] <= 0:
            break
        cx = BBOX[0] + (c + 0.5) * k * RES
        cy = BBOX[3] - (r + 0.5) * k * RES
        for az in range(0, 180, 5):
            _, hv, hb, val = line_gaps(g1v, g1b, g1a, cx, cy, az, length)
            if val.sum() < 0.98 * val.size:
                continue
            score = float((~hv & hb).mean())      # missing, then supplied
            if score > best[3]:
                best = (cx, cy, float(az), score)
    return best


def sample(arr, px, py):
    cc = np.rint((px - BBOX[0]) / RES - 0.5).astype(int)
    rr = np.rint((BBOX[3] - py) / RES - 0.5).astype(int)
    ok = (cc >= 0) & (cc < arr.shape[1]) & (rr >= 0) & (rr < arr.shape[0])
    out = np.full(px.size, np.nan, dtype="float32")
    out[ok] = arr[rr[ok], cc[ok]]
    return out


def cross_section(vend, both, cnt_v, cnt_b, cnt_a, code, slope,
                  width=2.0, length=300.0):
    """The same ground edge-on, before and after."""
    import laspy
    las = Path(tempfile.gettempdir()) / f"_rec9t_{code}.las"
    if not las.exists():
        print("  no retained LAS; skipping the section")
        return
    tx0, ty0, tx1, ty1 = snap(tile_bounds(next(SRC.glob(f"*{code}.laz"))))
    win = (int((BBOX[3] - ty1) / RES), int((BBOX[3] - ty0) / RES),
           int((tx0 - BBOX[0]) / RES), int((tx1 - BBOX[0]) / RES))
    closed = (cnt_v == 0) & (cnt_b > 0)
    g1v, g1b, g1a = to_1m(cnt_v), to_1m(cnt_b), to_1m(cnt_a)
    cx, cy, az, score = pick_line(closed, length, win, g1v, g1b, g1a)
    if cx is None:
        print("  no candidate line fits inside the section tile")
        return
    print(f"  section centre {cx:.0f},{cy:.0f}  azimuth {az:.0f} deg  "
          f"crosses ground-that-was-missing on {100*score:.0f}% of its length")

    t = np.radians(90.0 - az)
    u = np.array([np.cos(t), np.sin(t)])
    n = np.array([-u[1], u[0]])
    A = np.array([cx, cy]) - u * length / 2

    f = laspy.read(str(las))
    xy = np.c_[np.asarray(f.x) - A[0], np.asarray(f.y) - A[1]]
    s = xy @ u
    o = xy @ n
    keep = (np.abs(o) <= width) & (s >= 0) & (s <= length)
    if keep.sum() < 500:
        print(f"  only {keep.sum()} points in the corridor; skipping")
        return
    s = s[keep]
    z = np.asarray(f.z)[keep]
    vc = np.asarray(f.VendorClass).astype("int16")[keep]
    sc = np.asarray(f.classification).astype("int16")[keep]
    del f

    is_vend = vc == 2
    is_rec = (sc == 2) & (vc != 2)
    other = ~is_vend & ~is_rec

    ss = np.linspace(0, length, int(length / RES) + 1)
    px, py = A[0] + u[0] * ss, A[1] + u[1] * ss
    zv, zb = sample(vend, px, py), sample(both, px, py)

    _, hit_v, hit_b, valid = line_gaps(g1v, g1b, g1a, cx, cy, az,
                                       length, ss.size)

    fig, ax = plt.subplots(2, 1, figsize=(13.2, 9.0), sharex=True,
                           gridspec_kw={"height_ratios": [1, 1], "hspace": 0.17})
    lo = np.nanmin(z[is_vend | is_rec]) - 1.5
    hi = np.nanmax(np.concatenate([zv[np.isfinite(zv)], zb[np.isfinite(zb)]])) + 2.5

    for i, (title, show_rec) in enumerate([
            ("Before — only the ground points we were given", False),
            ("After — the discarded ground points added back", True)]):
        a = ax[i]
        a.scatter(s[other], z[other], s=1.6, color="#cdd2cc", linewidths=0,
                  zorder=1, label="everything else (trees, brush)")
        a.scatter(s[is_vend], z[is_vend], s=5.5, color=KEPT, linewidths=0,
                  zorder=3, label="ground the survey kept")
        if show_rec:
            a.scatter(s[is_rec], z[is_rec], s=4.5, color=FOUND, linewidths=0,
                      zorder=2, alpha=0.9, label="ground it threw away")
        zz = zb if show_rec else zv
        # a hole is "no ground return within 1 m of the line here", not
        # "the TIN has no value" -- the TIN spans its own convex hull
        gap = valid & ~(hit_b if show_rec else hit_v)
        a.plot(ss, zz, color=INK, linewidth=1.9, zorder=5,
               label="the ground surface this produces")
        # paint the stretch the surface cannot reach
        if gap.any():
            runs = np.flatnonzero(np.diff(np.r_[0, gap.view("i1"), 0]))
            for b0, b1 in zip(runs[::2], runs[1::2]):
                a.axvspan(ss[b0], ss[min(b1, ss.size - 1)],
                          facecolor=HOLE, alpha=0.12, zorder=0,
                          edgecolor=HOLE, linewidth=0.0, hatch="///")
            a.text(0.5, 0.045, f"{100*gap.sum()/max(valid.sum(),1):.0f}%"
                   f" of this line has no "
                   f"ground under it", transform=a.transAxes, ha="center",
                   fontsize=12.5, color=HOLE, fontweight="bold", zorder=6)
        else:
            a.text(0.5, 0.045, "the line is continuous end to end",
                   transform=a.transAxes, ha="center", fontsize=12.5,
                   color=FOUND, fontweight="bold", zorder=6)
        a.set_ylim(lo, hi)
        a.set_xlim(float(ss[valid].min()), float(ss[valid].max()))
        a.set_title(title, fontsize=16, fontweight="bold", loc="left", pad=8,
                    color=INK)
        a.set_ylabel("elevation, m", fontsize=12, color=INK2)
        a.grid(color=RULE, linewidth=0.7)
        a.set_axisbelow(True)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            a.spines[sp].set_color(RULE)
        a.tick_params(colors=INK2, labelsize=11)
        a.legend(frameon=True, facecolor=PAPER, edgecolor=RULE, fontsize=10.5,
                 loc="upper right", markerscale=3.0, ncol=2)
    ax[1].set_xlabel(f"distance along the line, m  "
                     f"(bearing {az:.0f}°, {2*width:.0f} m wide corridor)",
                     fontsize=12, color=INK2)
    fig.suptitle("The same slice of ground, before and after", fontsize=20,
                 fontweight="bold", x=0.062, ha="left", y=0.985, color=INK)
    fig.subplots_adjust(top=0.90)
    save(fig, f"cross_section_before_after_{code}_{int(length)}m_"
              f"az{int(az)}_w{width:.0f}p0_slope{str(slope).replace('.','p')}.png")
    return cx, cy, az


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--slope", type=float, default=0.35)
    ap.add_argument("--section-tile", default="621594")
    ap.add_argument("--skip-smrf", action="store_true",
                    help="reuse the per-tile rasters and redraw")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})

    if not args.skip_smrf:
        jobs = [(c, args.slope, c == args.section_tile) for c in TILES]
        print(f"SMRF + 3 surfaces on {len(jobs)} map squares, "
              f"{args.workers} at a time")
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(build_tile, j): j[0] for j in jobs}
            for i, fu in enumerate(as_completed(futs), 1):
                r = fu.result()
                tag = r.get("error") or f"{len(r['made'])} surfaces"
                print(f"  [{i}/{len(jobs)}] {r['code']}  {tag}")
        print(f"  {(time.time()-t0)/60:.1f} min")

    print("mosaicking")
    vend = mosaic("vendorground")
    both = mosaic("vendorplusrecovered")
    cnt_a = mosaic("anyreturn", count=True)
    cnt_v = mosaic("vendorground", count=True)
    cnt_r = mosaic("recoveredonly", count=True)
    cnt_b = mosaic("vendorplusrecovered", count=True)

    inside = cnt_a > 0            # cells the laser actually reached
    n = int(inside.sum())
    stats = dict(
        cells=n,
        void_v=100 * float((inside & (cnt_v == 0)).sum() / n),
        void_b=100 * float((inside & (cnt_b == 0)).sum() / n),
        rec_cells=int((cnt_r > 0).sum()),
        rec_pts=int(cnt_r.sum()),
        closed=int((inside & (cnt_v == 0) & (cnt_b > 0)).sum()))
    print(f"  {n:,} cells of 0.5 m in the area\n"
          f"  no ground return, as delivered            : {stats['void_v']:.2f}%\n"
          f"  no ground return, with the discarded back : {stats['void_b']:.2f}%\n"
          f"  cells closed                              : {stats['closed']:,}\n"
          f"  discarded ground points                   : {stats['rec_pts']:,}")

    write_tif(vend, OUT / "dem_vendorground_9t_0p5m.tif")
    write_grid(cnt_r, BBOX, OUT / f"count_recoveredground_slope"
               f"{str(args.slope).replace('.','p')}_9t_0p5m.tif", "uint16", 0)
    write_grid(cnt_v, BBOX, OUT / "count_vendorground_9t_0p5m.tif",
               "uint16", 0)
    write_tif(both, OUT / f"dem_vendorplusrecovered_slope"
                          f"{str(args.slope).replace('.','p')}_9t_0p5m.tif")

    k = 3                                    # 1.5 m pixels for the hillshade
    kb = 10                                  # 5 m blocks for the density wash
    extent = (BBOX[0], BBOX[2], BBOX[1], BBOX[3])
    print("drawing")
    map_vendor(vend, cnt_v, cnt_a, k, kb, extent, stats)
    map_recovered(cnt_r, k, kb, extent, stats)
    map_both(both, cnt_b, cnt_a, k, kb, extent, stats)
    cross_section(vend, both, cnt_v, cnt_b, cnt_a, args.section_tile,
                  args.slope)

    with open(OUT / "recovered_ground_9t_summary.json", "w") as f:
        json.dump(dict(stats, slope=args.slope, res=RES, bbox=BBOX,
                       tiles=TILES), f, indent=2)
    print(f"  wrote {OUT / 'recovered_ground_9t_summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
