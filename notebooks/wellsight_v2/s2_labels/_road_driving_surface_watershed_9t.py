"""Road driving-surface polygons for 9t by seeded (marker-controlled) watershed.

A forest road on a hillside is a flat tread between two breaks in slope: the convex fill
shoulder on the downhill side and the concave toe of the cut bank on the uphill side
(see docs/iterations/cross_section_test_line_9t.md, line 3). The watershed floods an
"edge" raster from two sets of seeds and draws the boundary where the floods meet, on
the ridges of that raster, i.e. on the breaks in slope.

  edge       = |grad(slope)| on the 0.5 m DEM, both lightly Gaussian-smoothed. Units 1/m.
  road seeds = annotated centreline pixels (roads layer) that are not steeper than SLOPE_BG_DEG.
  bg seeds   = the ring BG_DIST_M from the centreline, plus every corridor pixel steeper than
               SLOPE_BG_DEG. Cut banks and fill slopes are steeper than any drivable grade,
               so these seeds pin the boundary to the slope breaks.
  mask       = pixels within BG_DIST_M of a centreline. Nothing outside can become road.

Method: marker-controlled watershed (Beucher & Meyer 1993) with the flooding of Vincent &
Soille (1991), as implemented in skimage.segmentation.watershed. Logged in
literature/CITATIONS.md.

Pad modes (--pad-mode)
  none    roads only (the 2026-10-01 baseline).
  hybrid  pads become a third class, merging "pads as a barrier" with "pads as their own class":
          * pad core = annotated pad shrunk by PAD_BAND_M -> pad seeds. The road can never enter.
            Pad seeds override the >25 deg steep seeds, so pits on a pad stay pad.
          * the band +/- PAD_BAND_M around the drawn pad edge is unseeded, so the road, pad and
            background floods compete there and the line lands on whatever slope break exists.
          * a pad may not grow beyond its outline + PAD_BAND_M (pixels past that revert to none).
          Output labels: 1 road, 2 pad.

QC
  * transects across every centreline every TRANSECT_STEP_M; width = contiguous road run
    through the centreline point. `hit_limit` marks a run that reaches the BG_DIST_M ring,
    i.e. no break in slope was found on that side and the width there is a cap, not a
    measurement.
  * road crossings of the user's test lines (test_line_cross_section.gpkg) are mapped on
    the 0.5 m hillshade with the polygon, centreline and test line.

  python notebooks/wellsight_v2/s2_labels/_road_driving_surface_watershed_9t.py --pilot   # test-line windows only
  python notebooks/wellsight_v2/s2_labels/_road_driving_surface_watershed_9t.py           # all of 9t
  python notebooks/wellsight_v2/s2_labels/_road_driving_surface_watershed_9t.py --pad-mode hybrid
"""
import argparse
import json
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize, shapes
from rasterio.windows import Window
from scipy.ndimage import binary_fill_holes, distance_transform_edt, gaussian_filter, map_coordinates
from shapely.geometry import LineString, Point, box, shape
from skimage.segmentation import watershed

REPO = Path(__file__).resolve().parents[3]
DEM = REPO / "data" / "9t" / "derived" / "05" / "dem_9t_05.tif"
HILLSHADE = REPO / "data" / "9t" / "derived" / "05" / "hillshade_9t_05.tif"
ANN = REPO / "qgis" / "annotations" / "annotations_proj.gpkg"
TEST_LINES = REPO / "test_line_cross_section.gpkg"
DERIVED = REPO / "data" / "9t" / "derived" / "05"
RESULTS = REPO / "data" / "9t" / "results" / "road" / "driving_surface"
CRS = "EPSG:6346"

SMOOTH_SIGMA_PX = 1.0      # 0.5 m Gaussian on the DEM and on the slope before differencing
BG_DIST_M = 6.0            # background ring; a driving surface wider than ~2x this is not expected
SLOPE_BG_DEG = 25.0        # steeper than this is cut bank or fill slope, never tread
HOLE_MAX_M2 = 4.0          # fill holes in the road mask up to this area
TRANSECT_STEP_M = 5.0
TILE_PX, HALO_PX = 2000, 40
PAD_M = 80.0               # pilot window margin around each test line
PAD_BAND_M = 2.0           # hybrid pad mode: unseeded band either side of the drawn pad edge
PAD_MODE = "none"          # set from --pad-mode

ROAD, CENTRE, TESTLINE = "#A31515", "#2B2F36", "#1F5FA8"
PAD, BASELINE = "#1F5FA8", "#8E959B"   # pad = lost/found blue; baseline = neutral grey ink
# lost/found trio: dataviz validate_palette.js --mode light --pairs all, worst #A31515/#D97706
# dE 21.1 deutan; here road #A31515 vs test line #1F5FA8 vs charcoal centreline (neutral ink).
# Road outline is solid, centreline dashed, test line dotted, so colour is never the only cue.

def make_tag():
    t = f"bg{BG_DIST_M:g}m_slope{SLOPE_BG_DEG:g}deg"
    if PAD_MODE == "hybrid":
        t += f"_padhybrid_band{PAD_BAND_M:g}m"
    return t.replace(".", "p")


def edge_and_slope(dem, res):
    valid = np.isfinite(dem)
    z = np.where(valid, dem, np.nanmean(dem) if valid.any() else 0.0)
    z = gaussian_filter(z, SMOOTH_SIGMA_PX)
    gy, gx = np.gradient(z, res)
    grad = np.hypot(gx, gy)                      # rise/run
    slope_deg = np.degrees(np.arctan(grad))
    sy, sx = np.gradient(gaussian_filter(grad, SMOOTH_SIGMA_PX), res)
    edge = np.hypot(sx, sy)                      # change of slope per metre
    edge[~valid] = edge[valid].max() if valid.any() else 0
    return edge.astype(np.float32), slope_deg.astype(np.float32), valid


def burn(geoms, shape_, transform):
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return np.zeros(shape_, bool)
    return rasterize(((g, 1) for g in geoms), out_shape=shape_, transform=transform,
                     all_touched=False, dtype=np.uint8).astype(bool)


def segment_tile(dem, transform, res, roads, pads=None):
    """Return (label uint8: 0 none, 1 road, 2 pad; centreline raster bool) for one tile."""
    shape_ = dem.shape
    use_pads = PAD_MODE == "hybrid" and pads is not None and not pads.empty
    if roads.empty and not use_pads:
        return np.zeros(shape_, np.uint8), np.zeros(shape_, bool)
    centre = burn(roads.geometry, shape_, transform) if not roads.empty else np.zeros(shape_, bool)
    if not roads.empty:
        centre |= rasterize(((g, 1) for g in roads.geometry), out_shape=shape_, transform=transform,
                            all_touched=True, dtype=np.uint8).astype(bool)
    dist = distance_transform_edt(~centre) * res if centre.any() else np.full(shape_, np.inf)
    edge, slope_deg, valid = edge_and_slope(dem, res)
    corridor = dist <= BG_DIST_M
    steep = slope_deg >= SLOPE_BG_DEG
    if use_pads:
        pad_core = burn(pads.geometry.buffer(-PAD_BAND_M), shape_, transform)
        pad_outer = burn(pads.geometry.buffer(PAD_BAND_M), shape_, transform)
        pad_full = burn(pads.geometry, shape_, transform)
        pad_dist = distance_transform_edt(~pad_full) * res
    else:
        pad_core = pad_outer = np.zeros(shape_, bool)
        pad_dist = np.full(shape_, np.inf)
    mask = (corridor | pad_outer) & valid
    markers = np.zeros(shape_, np.int32)
    road_ring = (dist >= BG_DIST_M - res) & ~pad_outer
    pad_ring = pad_outer & (pad_dist >= PAD_BAND_M - res) & ~corridor
    markers[mask & (road_ring | pad_ring | steep)] = 2                # background
    markers[centre & ~steep & mask & ~pad_core] = 1                   # road
    markers[pad_core & mask] = 3                                      # pad (overrides steep)
    lab = watershed(edge, markers, mask=mask)
    pad = (lab == 3) & pad_outer
    road = lab == 1
    # fill small holes only (a big hole is real, e.g. a turnaround island)
    filled = binary_fill_holes(road)
    holes = filled & ~road
    if holes.any():
        from scipy.ndimage import label as cc
        hl, n = cc(holes)
        sizes = np.bincount(hl.ravel()) * res * res
        small = np.isin(hl, np.where(sizes <= HOLE_MAX_M2)[0]) & (hl > 0)
        road |= small
    road &= ~pad
    out = np.zeros(shape_, np.uint8)
    out[road] = 1
    out[pad] = 2
    return out, centre


def run_area(src, roads, win, pads=None):
    """Segment one window (rasterio Window) in tiles with a halo. Returns mask, centre, transform."""
    res = src.res[0]
    out = np.zeros((int(win.height), int(win.width)), np.uint8)
    cen = np.zeros_like(out, bool)
    r0, c0 = int(win.row_off), int(win.col_off)
    for tr in range(0, out.shape[0], TILE_PX):
        for tc in range(0, out.shape[1], TILE_PX):
            h = min(TILE_PX, out.shape[0] - tr)
            w = min(TILE_PX, out.shape[1] - tc)
            rr0 = max(0, r0 + tr - HALO_PX); cc0 = max(0, c0 + tc - HALO_PX)
            rr1 = min(src.height, r0 + tr + h + HALO_PX); cc1 = min(src.width, c0 + tc + w + HALO_PX)
            tw = Window(cc0, rr0, cc1 - cc0, rr1 - rr0)
            dem = src.read(1, window=tw).astype(np.float32)
            if src.nodata is not None:
                dem[dem == src.nodata] = np.nan
            t = src.window_transform(tw)
            tb = box(*rasterio.windows.bounds(tw, src.transform))
            sub = roads[roads.intersects(tb)]
            psub = pads[pads.intersects(tb)] if pads is not None else None
            m, c = segment_tile(dem, t, res, sub, psub)
            ir, ic = r0 + tr - rr0, c0 + tc - cc0
            out[tr:tr + h, tc:tc + w] = m[ir:ir + h, ic:ic + w]
            cen[tr:tr + h, tc:tc + w] = c[ir:ir + h, ic:ic + w]
    return out, cen, src.window_transform(win)


def transect_widths(mask, transform, roads, clip_geom):
    """Width of the road run through each centreline station, across the local direction."""
    inv = ~transform
    res = transform.a
    offs = np.arange(-BG_DIST_M - 1.0, BG_DIST_M + 1.0 + 1e-9, 0.25)
    rows = []
    for rid, g in zip(roads.index, roads.geometry):
        g = g.intersection(clip_geom)
        for part in getattr(g, "geoms", [g]):
            if part.is_empty or part.length < 2 * TRANSECT_STEP_M:
                continue
            for s in np.arange(TRANSECT_STEP_M / 2, part.length, TRANSECT_STEP_M):
                p = part.interpolate(s)
                a, b = part.interpolate(max(0, s - 1.0)), part.interpolate(min(part.length, s + 1.0))
                dx, dy = b.x - a.x, b.y - a.y
                n = np.hypot(dx, dy)
                if n == 0:
                    continue
                nx, ny = -dy / n, dx / n
                xs, ys = p.x + offs * nx, p.y + offs * ny
                cc, rr = inv * (xs, ys)
                v = map_coordinates(mask, [rr - 0.5, cc - 0.5], order=0, mode="constant", cval=0)
                mid = len(offs) // 2
                # start from the nearest road sample to the centreline point (centreline may sit 1 px off)
                on = np.where(v[max(0, mid - 4):mid + 5] > 0)[0]
                if on.size == 0:
                    rows.append((rid, p.x, p.y, 0.0, False, False))
                    continue
                k = max(0, mid - 4) + on[np.argmin(np.abs(on + max(0, mid - 4) - mid))]
                lo = k
                while lo > 0 and v[lo - 1]:
                    lo -= 1
                hi = k
                while hi < len(v) - 1 and v[hi + 1]:
                    hi += 1
                width = (hi - lo + 1) * 0.25
                lim = BG_DIST_M - res
                rows.append((rid, p.x, p.y, width, abs(offs[lo]) >= lim, abs(offs[hi]) >= lim))
    return pd.DataFrame(rows, columns=["road_fid", "x", "y", "width_m", "hit_limit_left", "hit_limit_right"])


def main():
    global PAD_MODE, PAD_BAND_M
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pilot", action="store_true", help="only windows around the user's test lines")
    ap.add_argument("--pad-mode", choices=["none", "hybrid"], default="none")
    ap.add_argument("--pad-band-m", type=float, default=PAD_BAND_M)
    args = ap.parse_args()
    PAD_MODE, PAD_BAND_M = args.pad_mode, args.pad_band_m
    TAG = make_tag()
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "figures").mkdir(exist_ok=True)
    roads_all = gpd.read_file(ANN, layer="roads").to_crs(CRS)
    tl = gpd.read_file(TEST_LINES, layer="test_line").to_crs(CRS)
    tl["line"] = range(1, len(tl) + 1)
    scope = "pilot_testlines" if args.pilot else "full"

    with rasterio.open(DEM) as src:
        tile_box = box(*src.bounds)
        roads = roads_all[roads_all.intersects(tile_box)].copy()
        pads_all = gpd.read_file(ANN, layer="plat").to_crs(CRS)
        pads = pads_all[pads_all.intersects(tile_box)].copy()
        if args.pilot:
            area = tl.geometry.buffer(PAD_M).union_all().envelope.intersection(tile_box)
        else:
            area = tile_box
        win = rasterio.windows.from_bounds(*area.bounds, transform=src.transform).round_offsets().round_lengths()
        labels, centre, tf = run_area(src, roads, win, pads if PAD_MODE == "hybrid" else None)
        mask = (labels == 1).astype(np.uint8)
        prof = src.profile

    stem = f"road_driving_surface_watershed_{TAG}_{scope}_9t_05"
    if not args.pilot:
        prof.update(dtype="uint8", nodata=0, count=1, compress="deflate", predictor=1,
                    width=mask.shape[1], height=mask.shape[0], transform=tf)
        DERIVED.mkdir(exist_ok=True)
        with rasterio.open(DERIVED / f"{stem}_mask.tif", "w", **prof) as dst:
            dst.write(labels, 1)   # 1 road, 2 pad (pad only in hybrid mode)

    polys = [shape(g) for g, v in shapes(mask, mask=mask > 0, transform=tf) if v == 1]
    gdf = gpd.GeoDataFrame(geometry=polys, crs=CRS)
    gdf["area_m2"] = gdf.area.round(1)
    gdf.to_file(RESULTS / f"{stem}.gpkg", layer="driving_surface", driver="GPKG")
    pad_gdf = None
    if PAD_MODE == "hybrid":
        pp = [shape(g) for g, v in shapes(labels, mask=labels == 2, transform=tf) if v == 2]
        pad_gdf = gpd.GeoDataFrame(geometry=pp, crs=CRS)
        pad_gdf["area_m2"] = pad_gdf.area.round(1)
        pad_gdf.to_file(RESULTS / f"{stem}.gpkg", layer="pad_surface", driver="GPKG")

    clip_geom = box(*area.bounds)
    tw = transect_widths(mask, tf, roads, clip_geom)
    tw["hit_limit_any"] = tw.hit_limit_left | tw.hit_limit_right
    # stations on a pad core are pad by construction in hybrid mode; flag them so stats can skip them
    core_u = pads.geometry.buffer(-PAD_BAND_M).union_all()
    tw["station_in_pad_core"] = gpd.GeoSeries(gpd.points_from_xy(tw.x, tw.y), crs=CRS).within(core_u).values
    pads_u = pads.geometry.union_all()
    tw["near_pad_8m"] = gpd.GeoSeries(gpd.points_from_xy(tw.x, tw.y), crs=CRS).distance(pads_u).values < 8.0
    tw.to_csv(RESULTS / f"{stem}_transect_widths_every{TRANSECT_STEP_M:g}m.csv", index=False)
    # same stations as points, so measured vs capped edges can be styled in QGIS
    gpd.GeoDataFrame(tw, geometry=gpd.points_from_xy(tw.x, tw.y), crs=CRS).to_file(
        RESULTS / f"{stem}.gpkg", layer=f"transect_widths_every{TRANSECT_STEP_M:g}m", driver="GPKG")
    found = tw[(tw.width_m > 0) & ~tw.station_in_pad_core]
    summary = {
        "scope": scope, "params": {"smooth_sigma_px": SMOOTH_SIGMA_PX, "bg_dist_m": BG_DIST_M,
                                   "slope_bg_deg": SLOPE_BG_DEG, "hole_max_m2": HOLE_MAX_M2,
                                   "transect_step_m": TRANSECT_STEP_M, "dem": str(DEM.relative_to(REPO))},
        "road_km_in_area": round(roads.geometry.intersection(clip_geom).length.sum() / 1000, 2),
        "polygon_area_ha": round(gdf.area.sum() / 1e4, 2),
        "transects": int(len(tw)),
        "transects_no_road_at_centreline": int((tw.width_m == 0).sum()),
        "width_m_median": round(float(found.width_m.median()), 2),
        "width_m_p10_p90": [round(float(found.width_m.quantile(q)), 2) for q in (0.1, 0.9)],
        "share_hit_limit_one_side": round(float((found.hit_limit_left ^ found.hit_limit_right).mean()), 3),
        "share_hit_limit_both_sides": round(float((found.hit_limit_left & found.hit_limit_right).mean()), 3),
        "median_width_where_no_limit_hit": round(float(found[~found.hit_limit_any].width_m.median()), 2),
        "pad_mode": PAD_MODE, "pad_band_m": PAD_BAND_M if PAD_MODE == "hybrid" else None,
        "transects_on_pad_core_skipped": int(tw.station_in_pad_core.sum()),
        "share_hit_limit_any_near_pads_8m": round(float(found[found.near_pad_8m].hit_limit_any.mean()), 3),
        "share_hit_limit_any_away_from_pads": round(float(found[~found.near_pad_8m].hit_limit_any.mean()), 3),
    }
    road_u = gdf.geometry.union_all()
    on_pad = road_u.intersection(pads_u).area
    touched = pads[pads.intersects(road_u)]
    cover = touched.geometry.intersection(road_u).area / touched.area
    summary.update({
        "road_area_on_annotated_pads_ha": round(on_pad / 1e4, 2),
        "road_area_on_annotated_pads_share": round(on_pad / road_u.area, 3),
        "pads_touched_by_road": int(len(touched)), "pads_total": int(len(pads)),
        "pads_over_25pct_covered_by_road": int((cover > 0.25).sum()),
    })
    if pad_gdf is not None:
        pad_u = pad_gdf.geometry.union_all()
        ious = []
        for g in pads.geometry:
            inter = g.intersection(pad_u).area
            uni = g.union(pad_u.intersection(g.buffer(PAD_BAND_M + 0.5))).area
            ious.append(inter / uni if uni else np.nan)
        summary.update({
            "pad_surface_area_ha": round(pad_u.area / 1e4, 2),
            "annotated_pad_area_ha": round(pads_u.area / 1e4, 2),
            "pad_iou_vs_annotation_median": round(float(np.nanmedian(ious)), 3),
            "pad_iou_vs_annotation_p10": round(float(np.nanpercentile(ious, 10)), 3),
        })

    # test-line crossings: where along each line the polygon is, against the road centreline
    cross = []
    poly_u = gdf.geometry.union_all()
    for n, g in zip(tl.line, tl.geometry):
        g = LineString([c for p in getattr(g, "geoms", [g]) for c in p.coords])
        for r in roads.geometry:
            hit = g.intersection(r)
            for p in getattr(hit, "geoms", [hit]):
                if p.is_empty or p.geom_type != "Point":
                    continue
                dc = g.project(p)
                seg = g.intersection(poly_u)
                spans = [sorted(g.project(Point(c)) for c in q.coords)
                         for q in getattr(seg, "geoms", [seg]) if not q.is_empty and q.length > 0]
                spans = [(s[0], s[-1]) for s in spans if s[0] - 1.0 <= dc <= s[-1] + 1.0]
                a, b = (spans[0] if spans else (np.nan, np.nan))
                cross.append({"line": n, "centreline_at_m": round(dc, 1), "polygon_from_m": round(a, 1),
                              "polygon_to_m": round(b, 1), "width_along_line_m": round(b - a, 1),
                              "x": p.x, "y": p.y})
    cross = pd.DataFrame(cross).drop_duplicates(subset=["line", "centreline_at_m"])
    cross.to_csv(RESULTS / f"{stem}_test_line_crossings.csv", index=False)
    summary["test_line_crossings"] = cross.drop(columns=["x", "y"]).to_dict("records")
    with open(RESULTS / f"{stem}_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)

    # QC figure: one 50 m panel per test-line road crossing, on the 0.5 m hillshade
    k = len(cross)
    if k:
        ncol = min(3, k); nrow = int(np.ceil(k / ncol))
        fig, axs = plt.subplots(nrow, ncol, figsize=(4.4 * ncol, 4.9 * nrow), squeeze=False,
                                gridspec_kw={"hspace": 0.18})
        with rasterio.open(HILLSHADE) as hs:
            for ax, (_, c) in zip(axs.ravel(), cross.iterrows()):
                half = 25.0
                bb = (c.x - half, c.y - half, c.x + half, c.y + half)
                w = rasterio.windows.from_bounds(*bb, transform=hs.transform)
                img = hs.read(1, window=w, boundless=True)
                ax.imshow(img, cmap="gray", extent=(bb[0], bb[2], bb[1], bb[3]), interpolation="nearest")
                gpd.GeoSeries([poly_u], crs=CRS).clip(box(*bb)).boundary.plot(ax=ax, color=ROAD, lw=1.8)
                roads.clip(box(*bb)).plot(ax=ax, color=CENTRE, lw=1.0, linestyle="--")
                tl[tl.line == c.line].clip(box(*bb)).plot(ax=ax, color=TESTLINE, lw=1.6, linestyle=":")
                ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3]); ax.set_xticks([]); ax.set_yticks([])
                ax.set_title(f"Line {int(c.line)} at {c.centreline_at_m:.0f} m: {c.width_along_line_m:.1f} m across",
                             fontsize=9.5, color=CENTRE, loc="left")
        for ax in axs.ravel()[k:]:
            ax.axis("off")
        fig.suptitle("Road driving surface by seeded watershed, at your test-line crossings (50 m windows)",
                     x=0.02, ha="left", fontsize=12, color=CENTRE)
        fig.text(0.02, 0.005, "Solid red: watershed polygon edge. Dashed charcoal: annotated centreline. "
                 "Dotted blue: your test line. Width is measured along the test line, which may cross at an angle.",
                 fontsize=8.5, color="#5B6168")
        fig.tight_layout(rect=(0, 0.03, 1, 0.95))
        fig.savefig(RESULTS / "figures" / f"{stem}_test_line_crossings_on_hillshade.png", dpi=180, facecolor="white")
    if PAD_MODE == "hybrid":
        base_gpkg = RESULTS / f"road_driving_surface_watershed_bg{BG_DIST_M:g}m_slope{SLOPE_BG_DEG:g}deg_{scope}_9t_05.gpkg".replace("bg6.", "bg6p")
        if base_gpkg.exists():
            base_u = gpd.read_file(base_gpkg, layer="driving_surface").geometry.union_all()
            bt = pads[pads.intersects(base_u)].copy()
            bt["base_cover"] = bt.geometry.intersection(base_u).area / bt.area
            pick = bt.sort_values("base_cover", ascending=False).head(6)
            fig, axs = plt.subplots(2, 3, figsize=(13.2, 9.8), squeeze=False, gridspec_kw={"hspace": 0.18})
            pad_u = pad_gdf.geometry.union_all()
            with rasterio.open(HILLSHADE) as hs:
                for ax, (_, pr) in zip(axs.ravel(), pick.iterrows()):
                    c = pr.geometry.centroid
                    half = max(30.0, 0.5 * max(pr.geometry.bounds[2] - pr.geometry.bounds[0],
                                               pr.geometry.bounds[3] - pr.geometry.bounds[1]) + 15)
                    bb = (c.x - half, c.y - half, c.x + half, c.y + half)
                    w = rasterio.windows.from_bounds(*bb, transform=hs.transform)
                    ax.imshow(hs.read(1, window=w, boundless=True), cmap="gray",
                              extent=(bb[0], bb[2], bb[1], bb[3]), interpolation="nearest")
                    cl = box(*bb)
                    gpd.GeoSeries([base_u], crs=CRS).clip(cl).boundary.plot(ax=ax, color=BASELINE, lw=1.4, linestyle="--")
                    gpd.GeoSeries([road_u], crs=CRS).clip(cl).boundary.plot(ax=ax, color=ROAD, lw=1.8)
                    gpd.GeoSeries([pad_u], crs=CRS).clip(cl).boundary.plot(ax=ax, color=PAD, lw=1.8)
                    pads.clip(cl).boundary.plot(ax=ax, color=CENTRE, lw=1.0, linestyle=":")
                    ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3]); ax.set_xticks([]); ax.set_yticks([])
                    after = pr.geometry.intersection(road_u).area / pr.geometry.area
                    ax.set_title(f"Pad {int(pr.pad_id) if 'pad_id' in pr and pd.notna(pr.pad_id) else ''}: "
                                 f"road covered {pr.base_cover:.0%} before, {after:.0%} after",
                                 fontsize=9.5, color=CENTRE, loc="left")
            fig.suptitle("Roads with pads as a third class (hybrid), on the six pads the baseline road flooded most",
                         x=0.02, ha="left", fontsize=12, color=CENTRE)
            fig.text(0.02, 0.005, "Dashed grey: baseline road edge. Solid red: hybrid road edge. "
                     "Solid blue: hybrid pad edge. Dotted charcoal: your pad annotation.",
                     fontsize=8.5, color="#5B6168")
            fig.tight_layout(rect=(0, 0.03, 1, 0.95))
            fig.savefig(RESULTS / "figures" / f"{stem}_pads_baseline_flooded_most_before_after_on_hillshade.png",
                        dpi=170, facecolor="white")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
