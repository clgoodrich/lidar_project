"""Cross section along the user's test line over 9t, with pads, pits and roads marked.

Line: test_line_cross_section.gpkg (repo root, layer test_line), drawn in EPSG:4326 and
reprojected to the lidar CRS EPSG:6346 (NAD83(2011) UTM 17N).

Top panel: 2019 lidar ground (1 m DEM) and first-return top (1 m DSM), sampled every 0.25 m
with bilinear interpolation.
Bottom panel: NISAR L-band summer 2026 mean backscatter (track 162), HH and HV, at its own
5 m pixels. Separate panel, never a second y-axis.

Feature spans come from qgis/annotations/annotations_proj.gpkg:
  pads  = plat, pits = pit_outside (whole pit incl. rim), pit floor = pit_inside,
  roads = roads centrelines. Roads have no width in the annotations, so each crossing is
  drawn as the centreline +/- ROAD_HALF_WIDTH_M (an assumption, stated on the figure).

Palette: pad #1F5FA8, pit #D97706, road #A31515 (lost/found trio).
dataviz validate_palette.js --mode light --pairs all: worst pair #A31515/#D97706
dE 21.1 deutan, 22.6 normal, all >= 3:1. Each band also has its own hatch and a direct label.
Ground #2B2F36 and canopy #8E959B are neutral inks, not categories.

  python notebooks/wellsight_v2/s7_analysis/_cross_section_test_line_9t.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import map_coordinates
from shapely.geometry import LineString, Point
from shapely.ops import transform as shp_transform
from pyproj import Transformer

REPO = Path(__file__).resolve().parents[3]
LINE = REPO / "test_line_cross_section.gpkg"
ANN = REPO / "qgis" / "annotations" / "annotations_proj.gpkg"
DEM = REPO / "data" / "9t" / "derived" / "1m" / "dem_9t_1m.tif"
DSM = REPO / "data" / "9t" / "derived" / "1m" / "dsm_9t_1m.tif"
NISAR = REPO / "data" / "9t" / "derived" / "nisar_gslc_5m"
# Local relief model = DEM minus an N-pixel moving mean (_build_derivatives.py). At 1 m, N pixels = N metres.
LRM = {11: REPO / "data" / "9t" / "derived" / "1m" / "lrm_11_9t_1m.tif",
       25: REPO / "data" / "9t" / "derived" / "1m" / "lrm_25_9t_1m.tif"}
OUT = REPO / "data" / "9t" / "results" / "cross_sections"
CRS = "EPSG:6346"
STEP_M = 0.25
ROAD_HALF_WIDTH_M = 2.5

PAD, PIT, ROAD = "#1F5FA8", "#D97706", "#A31515"
GROUND, CANOPY, INK = "#2B2F36", "#8E959B", "#2B2F36"


def sample(path, xs, ys, order=1):
    with rasterio.open(path) as src:
        a = src.read(1).astype("float64")
        if src.nodata is not None:
            a[a == src.nodata] = np.nan
        inv = ~src.transform
        cols, rows = inv * (np.asarray(xs), np.asarray(ys))
        # pixel centres sit at +0.5
        return map_coordinates(a, [rows - 0.5, cols - 0.5], order=order, mode="nearest", cval=np.nan)


def spans(line, geoms):
    """(start, end) distances along the line for each polygon it crosses."""
    out = []
    for g in geoms:
        hit = line.intersection(g)
        if hit.is_empty:
            continue
        parts = getattr(hit, "geoms", [hit])
        for p in parts:
            if p.length > 0:
                d = sorted(line.project(Point(c)) for c in p.coords)
                out.append((d[0], d[-1]))
    return sorted(out)


def draw_feature_strip(fx, others, pad_sp, pit_sp, floor_sp, road_sp):
    """One row per class with colour + hatch + row label; dashed edge guides on the other panels."""
    rows = [("pad", PAD, "\\\\\\", pad_sp),
            ("pit, incl. rim", PIT, "///", pit_sp),
            (f"road (±{ROAD_HALF_WIDTH_M:g} m)", ROAD, "xx", road_sp)]
    # feature track: one row per class, colour + hatch + row label, so never colour alone
    for i, (name, c, h, sp) in enumerate(rows):
        yb = len(rows) - 1 - i
        fx.broken_barh([(a_, b_ - a_) for a_, b_ in sp], (yb + 0.15, 0.7), facecolor=c, alpha=0.25,
                       edgecolor=c, hatch=h, lw=1.0)
        if name.startswith("pit"):
            fx.broken_barh([(a_, b_ - a_) for a_, b_ in floor_sp], (yb + 0.15, 0.7), facecolor=c, lw=0)
            for a_, b_ in floor_sp:
                fx.text((a_ + b_) / 2, yb + 0.5, "floor", ha="center", va="center", color="white",
                        fontsize=8.5, fontweight="bold")
        # thin edge guides through the other two panels
        for a_, b_ in sp:
            for axis in others:
                for v in (a_, b_):
                    axis.axvline(v, color=c, lw=1.0, ls=(0, (3, 2)), zorder=0)
    fx.set_ylim(0, len(rows))
    fx.set_yticks([len(rows) - 1 - i + 0.5 for i in range(len(rows))], [r[0] for r in rows])
    fx.tick_params(axis="y", length=0)
    for sp_ in ("top", "right", "left"):
        fx.spines[sp_].set_visible(False)


def save_fig(fig, path, dpi=200):
    """Save, retrying briefly: an image viewer holding the PNG open makes Windows refuse the write."""
    import time
    for _ in range(5):
        try:
            fig.savefig(path, dpi=dpi, facecolor="white")
            return True
        except OSError:
            time.sleep(1.0)
    print(f"WARNING: could not write {path} (open in another program?); skipped")
    return False


def run_line(line, n):
    """All figures and the profile table for one line; n is its 1-based number in the gpkg."""
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    bearing = (np.degrees(np.arctan2(x1 - x0, y1 - y0)) + 360) % 360
    compass = lambda b: ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW",
                         "WSW", "W", "WNW", "NW", "NNW"][int((b + 11.25) % 360 // 22.5)]

    d = np.arange(0, line.length + 1e-9, STEP_M)
    pts = [line.interpolate(v) for v in d]
    xs, ys = np.array([p.x for p in pts]), np.array([p.y for p in pts])
    ground, top = sample(DEM, xs, ys), sample(DSM, xs, ys)

    box = tuple(line.buffer(50).bounds)
    read = lambda lyr: gpd.read_file(ANN, layer=lyr, bbox=box).to_crs(CRS)
    pads, pits, floors, roads = read("plat"), read("pit_outside"), read("pit_inside"), read("roads")
    pad_sp, pit_sp, floor_sp = spans(line, pads.geometry), spans(line, pits.geometry), spans(line, floors.geometry)
    road_d = []
    for g in roads.geometry:
        hit = line.intersection(g)
        for p in getattr(hit, "geoms", [hit]):
            if not p.is_empty and p.geom_type == "Point":
                road_d.append(line.project(p))
    road_sp = [(max(0, r - ROAD_HALF_WIDTH_M), min(line.length, r + ROAD_HALF_WIDTH_M)) for r in sorted(road_d)]

    # NISAR summer 2026, track 162, at its own 5 m pixels
    with rasterio.open(NISAR / "nisar_hv_summer_2026_track162_9t_5m.tif") as src:
        ncrs = src.crs
    tr = Transformer.from_crs(CRS, ncrs, always_xy=True)
    nline = shp_transform(tr.transform, line)
    nd = np.arange(0, nline.length + 1e-9, STEP_M)
    npts = [nline.interpolate(v) for v in nd]
    nx, ny = [p.x for p in npts], [p.y for p in npts]
    hv = sample(NISAR / "nisar_hv_summer_2026_track162_9t_5m.tif", nx, ny, order=0)
    hh = sample(NISAR / "nisar_hh_summer_2026_track162_9t_5m.tif", nx, ny, order=0)
    nd = nd * line.length / nline.length  # same distance axis as the lidar

    def zone(v):
        z = []
        if any(a <= v <= b for a, b in pad_sp): z.append("pad")
        if any(a <= v <= b for a, b in floor_sp): z.append("pit_floor")
        elif any(a <= v <= b for a, b in pit_sp): z.append("pit_rim_or_wall")
        if any(a <= v <= b for a, b in road_sp): z.append("road")
        return "+".join(z) or "background"
    prof = pd.DataFrame({"distance_m": d, "x_epsg6346": xs, "y_epsg6346": ys,
                         "ground_dem_m": ground, "surface_dsm_m": top,
                         "canopy_height_m": top - ground,
                         "nisar_hv_summer2026_t162_db": np.interp(d, nd, hv),
                         "nisar_hh_summer2026_t162_db": np.interp(d, nd, hh),
                         "zone": [zone(v) for v in d]})
    stem = f"cross_section_test_line{n}_dem_dsm_nisar_summer2026_t162_with_pads_pits_roads_9t_1m"
    prof.to_csv(OUT / f"{stem}.csv", index=False)

    # ---------- figure ----------
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#8E959B", "axes.labelcolor": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig, (ax, fx, bx) = plt.subplots(3, 1, figsize=(12, 8), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 0.75, 1.3], "hspace": 0.1})
    draw_feature_strip(fx, (ax, bx), pad_sp, pit_sp, floor_sp, road_sp)
    for axis in (ax, bx):
        axis.grid(axis="y", color="#E3E5E8", lw=0.6)
        axis.spines[["top", "right"]].set_visible(False)

    ax.fill_between(d, ground, top, where=np.isfinite(top), color=CANOPY, alpha=0.25, lw=0)
    ax.plot(d, top, color=CANOPY, lw=1.2, label="surface top: canopy, brush, structures (lidar DSM)")
    ax.plot(d, ground, color=GROUND, lw=2, label="ground (lidar DEM)")
    lo, hi = np.nanmin(ground), np.nanmax(top)
    ax.set_ylim(lo - 1, hi + 1)
    ax.set_ylabel("Elevation (m, NAVD88)")
    ax.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=INK)
    for a_, b_ in floor_sp:
        i = np.argmin(np.abs(d - (a_ + b_) / 2))
        y0, y1 = ax.get_ylim()
        dy = -28 if (ground[i] - y0) / (y1 - y0) > 0.15 else 30  # flip above when the ground hugs the axis
        ax.annotate("pit floor", (d[i], ground[i]), xytext=(0, dy), textcoords="offset points",
                    ha="center", color=INK, fontsize=9, arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))

    bx.step(nd, hv, where="mid", color=GROUND, lw=1.6)
    bx.step(nd, hh, where="mid", color=CANOPY, lw=1.6, ls="--")
    bx.text(nd[-1] + 0.6, hv[-1], "HV", va="center", color=INK, fontsize=9)
    bx.text(nd[-1] + 0.6, hh[-1], "HH (dashed)", va="center", color=INK, fontsize=9)
    bx.set_ylabel("NISAR summer\nbackscatter (dB)")
    bx.set_xlabel(f"Distance along line (m), {compass((bearing + 180) % 360)} → {compass(bearing)}")
    bx.set_xlim(0, line.length)

    relief = np.nanmax(ground) - np.nanmin(ground)
    fig.suptitle(f"Cross section along test line {n}, 9t", x=0.06, ha="left", fontsize=13, color=INK)
    ax.set_title(f"{line.length:.0f} m long, ground relief {relief:.1f} m. "
                 "Lidar 2019 at 1 m. NISAR is the Jun–Sep 2026 mean on track 162, 5 m pixels, not shifted to the lidar.",
                 loc="left", fontsize=9, color="#5B6168")
    fig.text(0.06, 0.01, f"Roads are centrelines in the annotations, so their width here is an assumed "
             f"±{ROAD_HALF_WIDTH_M:g} m. The pit bar is the whole pit including its rim. The solid part is the pit floor.",
             fontsize=8.5, color="#5B6168")
    fig.subplots_adjust(left=0.11, right=0.9, top=0.9, bottom=0.1)
    png = OUT / "figures" / f"{stem}.png"
    png.parent.mkdir(exist_ok=True)
    save_fig(fig, png, dpi=200)

    # ---------- LRM figure: same line, local relief instead of elevation ----------
    lrm = {k: sample(v, xs, ys) for k, v in LRM.items()}
    for k, v in lrm.items():
        prof[f"lrm_{k}m_m"] = v
    prof.to_csv(OUT / f"{stem}.csv", index=False)
    fig, (lx, fx, gx) = plt.subplots(3, 1, figsize=(12, 7.6), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 0.75, 1.1], "hspace": 0.1})
    draw_feature_strip(fx, (lx, gx), pad_sp, pit_sp, floor_sp, road_sp)
    for axis in (lx, gx):
        axis.grid(axis="y", color="#E3E5E8", lw=0.6)
        axis.spines[["top", "right"]].set_visible(False)
    lx.axhline(0, color="#8E959B", lw=0.8)
    lx.fill_between(d, 0, lrm[25], where=lrm[25] < 0, color=GROUND, alpha=0.12, lw=0)
    lx.plot(d, lrm[25], color=GROUND, lw=2, label="LRM, 25 m window (pad and pit scale)")
    lx.plot(d, lrm[11], color=CANOPY, lw=1.4, ls="--", label="LRM, 11 m window (rim and small-feature scale)")
    m = np.nanmax(np.abs([lrm[11], lrm[25]])) * 1.15
    lx.set_ylim(-m, m)
    lx.set_ylabel("Local relief (m)\nabove / below the local mean")
    lx.legend(loc="best", frameon=False, fontsize=9, labelcolor=INK)
    for a_, b_ in floor_sp:
        i = np.argmin(np.abs(d - (a_ + b_) / 2))
        lx.annotate("pit floor", (d[i], lrm[25][i]), xytext=(0, -26), textcoords="offset points",
                    ha="center", color=INK, fontsize=9, arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))
    gx.plot(d, ground, color=GROUND, lw=1.6)
    gx.set_ylabel("Ground (m)")
    gx.set_xlabel(f"Distance along line (m), {compass((bearing + 180) % 360)} → {compass(bearing)}")
    gx.set_xlim(0, line.length)
    fig.suptitle(f"Local relief along test line {n}, 9t", x=0.06, ha="left", fontsize=13, color=INK)
    lx.set_title("2019 lidar at 1 m. LRM is the DEM minus its moving average, so the hillslope is removed. "
                 "Below zero is lower than its surroundings.", loc="left", fontsize=9, color="#5B6168")
    fig.text(0.06, 0.01, f"Roads are centrelines in the annotations, so their width here is an assumed "
             f"±{ROAD_HALF_WIDTH_M:g} m. The pit bar is the whole pit including its rim. The solid part is the pit floor.",
             fontsize=8.5, color="#5B6168")
    fig.subplots_adjust(left=0.11, right=0.9, top=0.9, bottom=0.1)
    lstem = f"cross_section_test_line{n}_lrm_11m_25m_with_pads_pits_roads_9t_1m"
    save_fig(fig, OUT / "figures" / f"{lstem}.png", dpi=200)
    print("wrote", OUT / "figures" / f"{lstem}.png")
    for name, (a_, b_) in [("pit floor", f) for f in floor_sp]:
        sel = (d >= a_) & (d <= b_)
        print(f"{name} {a_:.0f}-{b_:.0f} m: lrm25 min {np.nanmin(lrm[25][sel]):.2f} m, lrm11 min {np.nanmin(lrm[11][sel]):.2f} m, "
              f"canopy max {np.nanmax((top - ground)[sel]):.1f} m")
    for name, sp in (("pad", pad_sp), ("road", road_sp)):
        for a_, b_ in sp:
            sel = (d >= a_) & (d <= b_)
            print(f"{name}: lrm25 range {np.nanmin(lrm[25][sel]):.2f}..{np.nanmax(lrm[25][sel]):.2f} m")

    # ---------- true-scale figure: 1 m across = 1 m up, no exaggeration ----------
    # Axes are placed in inches so each panel's height/width equals its data range ratio exactly.
    W_IN, GRID_M = 10.0, 5.0
    in_per_m = W_IN / line.length
    e_lo = np.floor((np.nanmin(ground) - 1) / GRID_M) * GRID_M
    e_hi = np.ceil((np.nanmax(top) + 1) / GRID_M) * GRID_M
    l_hi = np.ceil(np.nanmax(np.abs([lrm[11], lrm[25]])) + 0.5)
    h_elev, h_lrm, h_strip = (e_hi - e_lo) * in_per_m, 2 * l_hi * in_per_m, 0.75
    left, right, top_m, bot, gap = 1.5, 1.9, 0.85, 0.75, 0.32
    fig_h = top_m + h_elev + gap + h_lrm + gap + h_strip + bot
    fig_w = left + W_IN + right
    fig = plt.figure(figsize=(fig_w, fig_h))
    def place(y0, h):
        return fig.add_axes([left / fig_w, y0 / fig_h, W_IN / fig_w, h / fig_h])
    y = bot
    fx = place(y, h_strip); y += h_strip + gap
    lx = place(y, h_lrm); y += h_lrm + gap
    ex = place(y, h_elev)
    for axis, lo_, hi_ in ((ex, e_lo, e_hi), (lx, -l_hi, l_hi)):
        axis.set_xlim(0, line.length); axis.set_ylim(lo_, hi_)
        axis.set_aspect("equal", adjustable="box")
        axis.set_xticks(np.arange(0, line.length + 1e-9, GRID_M), minor=True)
        axis.set_yticks(np.arange(lo_, hi_ + 1e-9, 1.0 if axis is lx else GRID_M), minor=True)
        axis.grid(which="both", color="#E3E5E8", lw=0.5)
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(labelbottom=False)
    ex.set_yticks(np.arange(e_lo, e_hi + 1e-9, 10.0))
    lx.set_yticks([-l_hi, 0, l_hi])  # 1 m minor grid stays; labels only at the ends and zero
    fx.set_xlim(0, line.length)
    draw_feature_strip(fx, (ex, lx), pad_sp, pit_sp, floor_sp, road_sp)
    ex.fill_between(d, ground, top, where=np.isfinite(top), color=CANOPY, alpha=0.25, lw=0)
    ex.plot(d, top, color=CANOPY, lw=1.0)
    ex.plot(d, ground, color=GROUND, lw=1.6)
    ex.text(line.length + 1, top[-1] + 1.2, "surface top\n(lidar DSM)", va="bottom", color=INK, fontsize=8.5)
    ex.text(line.length + 1, ground[-1] - 1.2, "ground\n(lidar DEM)", va="top", color=INK, fontsize=8.5)
    ex.set_ylabel("Elevation (m)")
    lx.axhline(0, color="#8E959B", lw=0.6)
    lx.plot(d, lrm[25], color=GROUND, lw=1.4)
    lx.plot(d, lrm[11], color=CANOPY, lw=1.0, ls="--")
    lx.text(line.length + 1, 0.4, "LRM 25 m (solid)\nLRM 11 m (dashed)", va="center", color=INK, fontsize=8.5)
    lx.set_ylabel("LRM (m)")
    fx.set_xlabel(f"Distance along line (m), {compass((bearing + 180) % 360)} → {compass(bearing)}")
    fx.tick_params(labelbottom=True)
    fig.text(left / fig_w, 1 - 0.3 / fig_h, f"Cross section along test line {n} at true scale, 9t",
             fontsize=13, color=INK, va="top")
    fig.text(left / fig_w, 1 - 0.58 / fig_h, "No exaggeration: 1 m across equals 1 m up in both panels. "
             "Grid squares are 5 m by 5 m (1 m tall in the LRM panel). 2019 lidar at 1 m.",
             fontsize=9, color="#5B6168", va="top")
    tstem = f"cross_section_test_line{n}_true_scale_1to1_dem_dsm_lrm_with_pads_pits_roads_9t_1m"
    save_fig(fig, OUT / "figures" / f"{tstem}.png", dpi=220)
    print("wrote", OUT / "figures" / f"{tstem}.png", f"({fig_w:.1f} x {fig_h:.1f} in)")

    # line in the lidar CRS, for QGIS
    print(f"line {n}: {line.length:.1f} m, bearing {bearing:.0f} deg; pads {pad_sp}; pits {pit_sp}; "
          f"floors {floor_sp}; roads {[round(r, 1) for r in road_d]}")
    print(f"ground {np.nanmin(ground):.2f}-{np.nanmax(ground):.2f} m; nan ground {np.isnan(ground).sum()}")
    print("wrote", png); print("wrote", OUT / f"{stem}.csv")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    g = gpd.read_file(LINE, layer="test_line").to_crs(CRS)
    lines = []
    for geom in g.geometry:
        # each feature is its own line; a multipart feature is joined in drawing order
        if geom.geom_type == "MultiLineString":
            geom = LineString([c for part in geom.geoms for c in part.coords])
        lines.append(geom)
    for n, line in enumerate(lines, start=1):
        run_line(line, n)
    gpd.GeoDataFrame({"line": range(1, len(lines) + 1),
                      "length_m": [round(l.length, 2) for l in lines]},
                     geometry=lines, crs=CRS).to_file(OUT / "test_lines_cross_section_epsg6346_9t.gpkg",
                                                      layer="test_lines", driver="GPKG")


if __name__ == "__main__":
    main()
