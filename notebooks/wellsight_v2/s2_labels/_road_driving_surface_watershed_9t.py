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

QC
  * transects across every centreline every TRANSECT_STEP_M; width = contiguous road run
    through the centreline point. `hit_limit` marks a run that reaches the BG_DIST_M ring,
    i.e. no break in slope was found on that side and the width there is a cap, not a
    measurement.
  * road crossings of the user's test lines (test_line_cross_section.gpkg) are mapped on
    the 0.5 m hillshade with the polygon, centreline and test line.

  python notebooks/wellsight_v2/s2_labels/_road_driving_surface_watershed_9t.py --pilot   # test-line windows only
  python notebooks/wellsight_v2/s2_labels/_road_driving_surface_watershed_9t.py           # all of 9t
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

ROAD, CENTRE, TESTLINE = "#A31515", "#2B2F36", "#1F5FA8"
# lost/found trio: dataviz validate_palette.js --mode light --pairs all, worst #A31515/#D97706
# dE 21.1 deutan; here road #A31515 vs test line #1F5FA8 vs charcoal centreline (neutral ink).
# Road outline is solid, centreline dashed, test line dotted, so colour is never the only cue.

TAG = f"bg{BG_DIST_M:g}m_slope{SLOPE_BG_DEG:g}deg".replace(".", "p")


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


def segment_tile(dem, transform, res, roads):
    """Return (road mask uint8, centreline raster bool) for one tile."""
    shape_ = dem.shape
    if roads.empty:
        return np.zeros(shape_, np.uint8), np.zeros(shape_, bool)
    centre = rasterize(((g, 1) for g in roads.geometry), out_shape=shape_, transform=transform,
                       all_touched=True, dtype=np.uint8).astype(bool)
    if not centre.any():
        return np.zeros(shape_, np.uint8), centre
    dist = distance_transform_edt(~centre) * res
    edge, slope_deg, valid = edge_and_slope(dem, res)
    mask = (dist <= BG_DIST_M) & valid
    steep = slope_deg >= SLOPE_BG_DEG
    markers = np.zeros(shape_, np.int32)
    markers[mask & ((dist >= BG_DIST_M - res) | steep)] = 2          # background
    markers[centre & ~steep & mask] = 1                               # road
    lab = watershed(edge, markers, mask=mask)
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
    return road.astype(np.uint8), centre


def run_area(src, roads, win):
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
            sub = roads[roads.intersects(box(*rasterio.windows.bounds(tw, src.transform)))]
            m, c = segment_tile(dem, t, res, sub)
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pilot", action="store_true", help="only windows around the user's test lines")
    args = ap.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "figures").mkdir(exist_ok=True)
    roads_all = gpd.read_file(ANN, layer="roads").to_crs(CRS)
    tl = gpd.read_file(TEST_LINES, layer="test_line").to_crs(CRS)
    tl["line"] = range(1, len(tl) + 1)
    scope = "pilot_testlines" if args.pilot else "full"

    with rasterio.open(DEM) as src:
        tile_box = box(*src.bounds)
        roads = roads_all[roads_all.intersects(tile_box)].copy()
        if args.pilot:
            area = tl.geometry.buffer(PAD_M).union_all().envelope.intersection(tile_box)
        else:
            area = tile_box
        win = rasterio.windows.from_bounds(*area.bounds, transform=src.transform).round_offsets().round_lengths()
        mask, centre, tf = run_area(src, roads, win)
        prof = src.profile

    stem = f"road_driving_surface_watershed_{TAG}_{scope}_9t_05"
    if not args.pilot:
        prof.update(dtype="uint8", nodata=0, count=1, compress="deflate", predictor=1,
                    width=mask.shape[1], height=mask.shape[0], transform=tf)
        DERIVED.mkdir(exist_ok=True)
        with rasterio.open(DERIVED / f"{stem}_mask.tif", "w", **prof) as dst:
            dst.write(mask, 1)

    polys = [shape(g) for g, v in shapes(mask, mask=mask > 0, transform=tf) if v == 1]
    gdf = gpd.GeoDataFrame(geometry=polys, crs=CRS)
    gdf["area_m2"] = gdf.area.round(1)
    gdf.to_file(RESULTS / f"{stem}.gpkg", layer="driving_surface", driver="GPKG")

    clip_geom = box(*area.bounds)
    tw = transect_widths(mask, tf, roads, clip_geom)
    tw["hit_limit_any"] = tw.hit_limit_left | tw.hit_limit_right
    tw.to_csv(RESULTS / f"{stem}_transect_widths_every{TRANSECT_STEP_M:g}m.csv", index=False)
    # same stations as points, so measured vs capped edges can be styled in QGIS
    gpd.GeoDataFrame(tw, geometry=gpd.points_from_xy(tw.x, tw.y), crs=CRS).to_file(
        RESULTS / f"{stem}.gpkg", layer=f"transect_widths_every{TRANSECT_STEP_M:g}m", driver="GPKG")
    found = tw[tw.width_m > 0]
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
    }

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
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
