"""A true cross-section: cut a line anywhere, buffer it, project the points onto it.

WHAT THIS IS
------------
Draw a line across the ground at any azimuth. Buffer it left and right. Take
every return inside that corridor and project it onto the line, so a point 1.8 m
off to the side plots at the station where it meets the line rather than at its
own easting. The result reads as though every point in the corridor lay exactly
on the cut.

    station s = (P - A) . u        distance along the line
    offset  o = (P - A) . n        perpendicular distance, kept if |o| <= width

That is the difference from an axis-aligned slice, which only works if the
feature you care about happens to run north-south.

The cut is drawn three ways:

    as delivered        two classes, and a third of the points "unassigned"
    reclassified        the same points separated by height above ground
    ground close up     the same again on its own vertical scale, because a
                        1.5 m pit is invisible against 25 m of canopy

plus a locator map of the corridor, built from the ground returns in the crop.

DEFINING THE CUT
----------------
    --line x1,y1,x2,y2          explicit, in EPSG:6346
    --center x,y --azimuth deg  centre, bearing (0 = north, 90 = east), --length
    --pit / --pad               auto: cut the long axis of an annotated feature

CLASSIFICATION
--------------
Height above ground from PDAL `filters.hag_nn`, banded per the USGS 3DEP Lidar
Base Specification (ASPRS 3 / 4 / 5 at 2 m and 5 m). Returns below the surface
are split into coherent and isolated by fitting a local plane and measuring the
residual -- NOT the raw vertical range, which on a 20% hillside spends most of
its budget on slope and throws away real surfaces for being tilted.

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md). The tile is cropped to the corridor
plus a margin, so this runs in seconds rather than scanning a whole tile.

Run:
    python notebooks/wellsight_v2/s7_analysis/_cross_section_classification.py
    ... --pit --tile 616591
    ... --line 617560,4592230,617610,4592265 --width 2.5
    ... --center 617583.8,4592245.4 --azimuth 135 --length 60
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

import numpy as np

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "_source" / "lidar" / "westernpa"
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
#: Cross-sections are presentation material, not an intermediate product,
#: so they live with the rest of the deck figures and are tracked in git.
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "cross_sections"
PDAL = "pdal"

MARGIN = 25.0       # crop margin around the corridor, so hag_nn has ground context
GRID = 0.5          # locator hillshade cell size

#: ASPRS bands, USGS 3DEP Lidar Base Specification
BANDS = [(-1e9, -0.15, 7), (-0.15, 0.15, 1), (0.15, 2.0, 3),
         (2.0, 5.0, 4), (5.0, 60.0, 5), (60.0, 1e9, 18)]

SURFACE, INK, INK2, MUTED, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a887e", "#d8d7cf"
#: Colourblind-safe, and checked rather than eyeballed. Validated with the
#: dataviz palette validator (all pairs, light surface):
#:
#:   categorical  unassigned / ground / vegetation / below ground
#:                worst pair #C43E1C vs #4FA352  dE 8.5 deutan, 14.6 tritan  PASS
#:                normal vision worst pair       dE 18.2                     PASS
#:
#: Vegetation is ORDERED by height, so it is a sequential single-hue ramp
#: (L 0.75 -> 0.48 -> 0.21, monotonic) rather than three categorical hues --
#: three greens cannot be told apart reliably under deuteranopia, and here the
#: y-axis already encodes the height, so colour does not need to.
#:
#: Brown was the obvious choice for ground and had to go: dark green against
#: brown measures dE 1.2 under protanopia, the single worst pair tested.
#:
#: The two below-ground classes share one hue and are separated by MARKER
#: SHAPE, not colour -- a sixth hue would not have cleared the floor.
GREY, BLUE, VERM = "#B0B0B0", "#1F5FA8", "#C43E1C"
VEG_LOW, VEG_MED, VEG_HIGH = "#A9DCA0", "#4FA352", "#18512F"
COL = {1: (GREY, "unassigned (at ground)", "o"),
       2: (BLUE, "ground", "o"),
       3: (VEG_LOW, "low veg 0.15-2 m", "o"),
       4: (VEG_MED, "medium veg 2-5 m", "o"),
       5: (VEG_HIGH, "high veg > 5 m", "o"),
       6: (VERM, "below ground, coherent", "o"),
       7: (VERM, "below ground, isolated", "x"),
       9: ("#56B4E9", "water", "o"), 17: ("#7B3FA0", "bridge deck", "o"),
       18: (VERM, "high noise", "x"), 20: (GREY, "vendor class 20", "o")}


def run_pipeline(stages, label, timeout=1800):
    """Write the pipeline to a temp file and shell out. See CLAUDE.md."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-1200:])
        print(r.stderr[-1200:])
        raise SystemExit(f"{label} failed, exit {r.returncode}")


def tile_index():
    """Every source tile with its footprint, so a cut can find its own tile."""
    import laspy
    out = []
    # The nine tiles that make up 9t live in OTHER_DATA/, not beside the rest,
    # so the search has to recurse. Skip the merged clouds -- they span
    # everything and would always win the containment test.
    files = [f for f in sorted(SRC.rglob("*.laz"))
             if not f.name.startswith("_merged")
             and re.search(r"17T..(\d{6})", f.name)]
    for f in files:
        with laspy.open(f) as fh:
            h = fh.header
            out.append((re.search(r"17T..(\d{6})", f.name).group(1), f,
                        h.mins[0], h.mins[1], h.maxs[0], h.maxs[1]))
    return out


def tile_for(x, y, want=None):
    for code, f, x0, y0, x1, y1 in tile_index():
        if want and code != want:
            continue
        if x0 <= x <= x1 and y0 <= y <= y1:
            return code, f
    raise SystemExit(f"no source tile covers {x:.1f}, {y:.1f}")


def load(laz, bbox):
    tmp = Path(tempfile.gettempdir()) / f"_xs_{abs(hash(bbox)) % 10**8}.las"
    run_pipeline([
        str(laz),
        {"type": "filters.crop",
         "bounds": f"([{bbox[0]},{bbox[2]}],[{bbox[1]},{bbox[3]}])"},
        {"type": "filters.hag_nn", "count": 8, "allow_extrapolation": True},
        {"type": "writers.las", "filename": str(tmp),
         "extra_dims": "HeightAboveGround=float32", "compression": "false"},
    ], "crop+hag")
    import laspy
    las = laspy.read(str(tmp))
    d = {"x": np.asarray(las.x), "y": np.asarray(las.y), "z": np.asarray(las.z),
         "cls": np.asarray(las.classification).astype("int16"),
         "hag": np.asarray(las.HeightAboveGround, dtype="float64"),
         "rn": np.asarray(las.return_number).astype("int16"),
         "nr": np.asarray(las.number_of_returns).astype("int16")}
    tmp.unlink(missing_ok=True)
    return d


def classify(d):
    """Band class 1 by height, then split the below-surface returns properly."""
    from scipy.spatial import cKDTree
    new = d["cls"].copy()
    t = d["cls"] == 1
    fin = np.isfinite(d["hag"])
    for lo, hi, c in BANDS:
        new[t & fin & (d["hag"] >= lo) & (d["hag"] < hi)] = c

    # A flat vertical-range test calls a tilted surface incoherent: at 20% slope
    # a 2 m radius spans 0.4 m of genuine relief. Fit a plane and judge the
    # residual, so slope is removed and only real scatter counts.
    bg = np.flatnonzero(new == 7)
    if bg.size >= 4:
        bx, by, bz = d["x"][bg], d["y"][bg], d["z"][bg]
        nbrs = cKDTree(np.c_[bx, by]).query_ball_point(np.c_[bx, by], r=2.0)
        for i, q in enumerate(nbrs):
            if len(q) - 1 < 3:
                continue
            A = np.c_[bx[q] - bx[i], by[q] - by[i], np.ones(len(q))]
            try:
                c, *_ = np.linalg.lstsq(A, bz[q], rcond=None)
            except np.linalg.LinAlgError:
                continue
            r = bz[q] - A @ c
            if r.max() - r.min() < 0.35:
                new[bg[i]] = 6
    return new


def resolve_line(args):
    """Turn whatever the user gave us into two endpoints plus a subject label."""
    import geopandas as gpd
    from shapely.geometry import box as sbox

    if args.line:
        v = [float(t) for t in args.line.replace(" ", "").split(",")]
        return (v[0], v[1]), (v[2], v[3]), "user-defined line", None

    if args.center:
        cx, cy = [float(t) for t in args.center.replace(" ", "").split(",")]
        th = np.deg2rad(90.0 - args.azimuth)      # bearing -> math angle
        h = (args.length or 60.0) / 2
        u = np.array([np.cos(th), np.sin(th)])
        return ((cx - h * u[0], cy - h * u[1]),
                (cx + h * u[0], cy + h * u[1]),
                f"azimuth {args.azimuth:.0f}°", None)

    layer = "plat" if args.pad else "pit_inside"
    gdf = gpd.read_file(ANN, layer=layer)
    if args.tile:
        code, f = next(((c, p) for c, p, *_ in
                        [(c, p, a, b, cc, dd) for c, p, a, b, cc, dd
                         in tile_index()] if c == args.tile), (None, None))
        if f is None:
            raise SystemExit(f"tile {args.tile} not found")
        import laspy
        with laspy.open(f) as fh:
            h = fh.header
            gdf = gdf[gdf.centroid.within(
                sbox(h.mins[0], h.mins[1], h.maxs[0], h.maxs[1]))]
    gdf = gdf.reset_index(drop=True)
    if gdf.empty:
        raise SystemExit("no annotated features to cut through")
    if args.index is not None:
        g = gdf.iloc[args.index].geometry
    else:
        g = gdf.iloc[int(np.argmax(gdf.geometry.area.values))].geometry

    # cut the long axis of the feature's minimum rotated rectangle
    rect = np.array(g.minimum_rotated_rectangle.exterior.coords)[:4]
    e = [(rect[i], rect[(i + 1) % 4]) for i in range(4)]
    p0, p1 = max(e, key=lambda s: np.hypot(*(s[1] - s[0])))
    u = (p1 - p0) / np.hypot(*(p1 - p0))
    c = np.array(g.centroid.coords[0])
    h = (args.length or max(40.0, 5 * np.hypot(*(p1 - p0)))) / 2
    kind = "pad" if args.pad else "pit"
    return (tuple(c - h * u), tuple(c + h * u),
            f"long axis of an annotated {kind} ({g.area:.0f} m²)", g)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--line", help="x1,y1,x2,y2 in EPSG:6346")
    ap.add_argument("--center", help="x,y in EPSG:6346")
    ap.add_argument("--azimuth", type=float, default=90.0,
                    help="bearing of the cut, 0 = north, 90 = east")
    ap.add_argument("--length", type=float, default=0.0)
    ap.add_argument("--width", type=float, default=2.0,
                    help="corridor HALF-width; points further off are dropped")
    ap.add_argument("--pit", action="store_true")
    ap.add_argument("--pad", action="store_true")
    ap.add_argument("--tile", help="restrict the feature search to this tile")
    ap.add_argument("--index", type=int, help="which annotated feature")
    ap.add_argument("--zoom", action="store_true",
                    help="add a third panel showing the ground on its own scale")
    ap.add_argument("--name", default="", help="suffix for the output filename")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    A, B, subject, geom = resolve_line(args)
    A, B = np.asarray(A, float), np.asarray(B, float)
    L = float(np.hypot(*(B - A)))
    u = (B - A) / L
    n = np.array([-u[1], u[0]])
    az = (90.0 - np.rad2deg(np.arctan2(u[1], u[0]))) % 360
    print(f"cut: {A[0]:.1f},{A[1]:.1f} -> {B[0]:.1f},{B[1]:.1f}")
    print(f"     {L:.1f} m long, azimuth {az:.1f}°, "
          f"corridor +/-{args.width:.1f} m  ({subject})")

    code, laz = tile_for(*((A + B) / 2), want=args.tile)
    print(f"     tile {code}")
    xs, ys = [A[0], B[0]], [A[1], B[1]]
    bbox = (min(xs) - MARGIN, min(ys) - MARGIN,
            max(xs) + MARGIN, max(ys) + MARGIN)
    d = load(laz, bbox)
    print(f"     {d['z'].size:,} points in the crop")

    # ---- project every point onto the line -------------------------------
    rel = np.c_[d["x"] - A[0], d["y"] - A[1]]
    s = rel @ u
    o = rel @ n
    keep = (np.abs(o) <= args.width) & (s >= 0) & (s <= L)
    if keep.sum() < 60:
        raise SystemExit(f"only {int(keep.sum())} points in the corridor; "
                         "widen --width or move the line")
    print(f"     {int(keep.sum()):,} points in the corridor")

    new = classify(d)
    where = None
    if geom is not None:
        from shapely.geometry import LineString
        cut = geom.intersection(LineString([tuple(A), tuple(B)]))
        if not cut.is_empty:
            pts = np.array(cut.coords) if cut.geom_type == "LineString" else \
                np.vstack([np.array(g.coords) for g in cut.geoms])
            ss = (pts - A) @ u
            where = (float(ss.min()), float(ss.max()))

    _draw(code, A, B, L, u, n, s[keep], o[keep], d, keep, new[keep], args,
          subject, az, where, geom)
    return 0


def _draw(code, A, B, L, u, n, s, o, d, keep, cls, args, subject, az, where,
          geom):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource
    from matplotlib.gridspec import GridSpec
    from scipy.interpolate import LinearNDInterpolator
    from scipy.spatial import Delaunay

    z, hag = d["z"][keep], d["hag"][keep]
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE,
                         "font.family": "DejaVu Sans", "text.color": INK})
    nrow = 3 if args.zoom else 2
    fig = plt.figure(figsize=(17.2, 11.4 if args.zoom else 8.4))
    gs = GridSpec(nrow, 2, width_ratios=[1.0, 2.75], hspace=0.16, wspace=0.09,
                  left=0.008, right=0.988, top=0.945, bottom=0.075)
    mp = fig.add_subplot(gs[:, 0])
    ax = [fig.add_subplot(gs[i, 1]) for i in range(nrow)]
    for a in ax[1:]:
        a.sharex(ax[0])
    ax[1].sharey(ax[0])

    # ---- locator: hillshade from the ground returns in the crop ----------
    g2 = d["cls"] == 2
    bb = (d["x"].min(), d["y"].min(), d["x"].max(), d["y"].max())
    gx = np.arange(bb[0], bb[2], GRID)
    gy = np.arange(bb[3], bb[1], -GRID)
    if g2.sum() > 500:
        f = LinearNDInterpolator(Delaunay(np.c_[d["x"][g2], d["y"][g2]]),
                                 d["z"][g2])
        X, Y = np.meshgrid(gx, gy)
        dem = f(X, Y)
        hs = LightSource(315, 45).hillshade(
            np.nan_to_num(dem, nan=float(np.nanmedian(dem))),
            vert_exag=2.2, dx=GRID, dy=GRID)
        mp.imshow(hs, extent=[bb[0], bb[2], bb[1], bb[3]], cmap="gray",
                  origin="upper")
    corner = np.array([A + n * args.width, B + n * args.width,
                       B - n * args.width, A - n * args.width,
                       A + n * args.width])
    mp.plot(corner[:, 0], corner[:, 1], color="#2a78d6", linewidth=1.5,
            alpha=0.9)
    mp.fill(corner[:, 0], corner[:, 1], color="#2a78d6", alpha=0.13)
    mp.plot([A[0], B[0]], [A[1], B[1]], color="#2a78d6", linewidth=2.2)
    for p, lab in ((A, "A"), (B, "B")):
        mp.scatter(*p, s=46, color="#2a78d6", zorder=5, edgecolor="white",
                   linewidth=1.4)
        mp.annotate(lab, p, textcoords="offset points", xytext=(7, 6),
                    fontsize=12, fontweight="bold", color="#1b5390")
    if geom is not None:
        import geopandas as gpd
        gpd.GeoSeries([geom]).boundary.plot(ax=mp, color="#eb6834",
                                            linewidth=1.8)
    mp.set_xlim(bb[0], bb[2]); mp.set_ylim(bb[1], bb[3])
    mp.set_aspect("equal"); mp.set_xticks([]); mp.set_yticks([])
    mp.set_title("where the cut is", fontsize=12.5, fontweight="bold",
                 loc="left", pad=8)
    for sp in mp.spines.values():
        sp.set_color(RULE)
    bar = 10 ** int(np.floor(np.log10((bb[2] - bb[0]) / 3)))
    bx0, by0 = bb[0] + (bb[2] - bb[0]) * 0.06, bb[1] + (bb[3] - bb[1]) * 0.06
    mp.plot([bx0, bx0 + bar], [by0, by0], color="white", linewidth=5,
            solid_capstyle="butt")
    mp.plot([bx0, bx0 + bar], [by0, by0], color=INK, linewidth=2.2,
            solid_capstyle="butt")
    mp.text(bx0 + bar / 2, by0 + (bb[3] - bb[1]) * 0.022, f"{bar:.0f} m",
            ha="center", fontsize=9.5, color=INK,
            bbox=dict(boxstyle="round,pad=0.14", fc="#ffffffdd", ec="none"))

    # ---- the three cuts ---------------------------------------------------
    # points nearer the line are drawn more solidly, so the corridor's depth
    # of field is visible rather than silently flattened
    alpha = np.clip(1.0 - 0.55 * (np.abs(o) / max(args.width, 1e-9)), 0.3, 1.0)
    titles = ["As delivered  —  two classes; everything else is "
              "“unassigned”",
              "Reclassified by height above ground  —  the same points, "
              "told apart",
              "The ground surface, close up  —  its own vertical scale"]
    panels = [(ax[0], d["cls"][keep], titles[0]), (ax[1], cls, titles[1])]
    if args.zoom:
        panels.append((ax[2], cls, titles[2]))
    for a, cc, title in panels:
        if where is not None:
            a.axvspan(*where, color="#eb6834", alpha=0.10, zorder=0)
            for xv in where:
                a.axvline(xv, color="#eb6834", linewidth=1.3, alpha=0.6,
                          zorder=1)
        for c in sorted(np.unique(cc)):
            k = cc == c
            col, lab, mk = COL.get(int(c), ("#000000", f"class {c}", "o"))
            a.scatter(s[k], z[k], s=9.0 if mk == "x" else 6.0, c=col,
                      marker=mk, linewidths=0.8 if mk == "x" else 0,
                      alpha=alpha[k])
            a.scatter([], [], s=34, c=col, marker=mk,
                      linewidths=1.0 if mk == "x" else 0,
                      label=f"{lab}  ({int(k.sum()):,})")
        a.set_title(title, fontsize=12.8, fontweight="bold", loc="left", pad=7)
        a.legend(frameon=False, fontsize=9, markerscale=1.0, ncol=4,
                 loc="upper left", handletextpad=0.4, columnspacing=1.1)
        a.set_ylabel("elevation, m NAVD88", fontsize=10.5, color=INK2)
        a.grid(color=RULE, linewidth=0.6, alpha=0.7)
        a.set_axisbelow(True)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            a.spines[sp].set_color(RULE)
        a.tick_params(colors=INK2, labelsize=9.5)
    gz = z[np.isfinite(hag) & (np.abs(hag) < 0.8)]
    if args.zoom and gz.size > 10:
        lo, hi = np.percentile(gz, [0.5, 99.5])
        pad = max(0.6, 0.35 * (hi - lo))
        ax[2].set_ylim(lo - pad, hi + pad)
    ax[-1].set_xlabel(f"station along the cut, m   (A = 0, B = {L:.0f})",
                     fontsize=10.5, color=INK2)
    ax[0].set_xlim(0, L)

    ve = ((ax[-1].get_xlim()[1] - ax[-1].get_xlim()[0]) /
          max(ax[-1].get_ylim()[1] - ax[-1].get_ylim()[0], 1e-9)) * \
        (ax[-1].get_position().height / ax[-1].get_position().width)

    tag = args.name or ("pad" if args.pad else "pit" if args.pit else "line")
    p = OUT / (f"cross_section_{tag}_{code}_{L:.0f}m_az{az:.0f}_"
               f"w{str(args.width).replace('.', 'p')}.png")
    fig.savefig(p, dpi=185)
    plt.close(fig)
    print(f"\nwrote {p}")


if __name__ == "__main__":
    sys.exit(main())
