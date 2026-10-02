"""Flat-surface fill for 9t with NO shapefile seeds: let the watershed run and see what it takes.

Same flooding as _road_driving_surface_watershed_9t.py (marker-controlled watershed on the change of
slope, Beucher & Meyer 1993), but the seeds come from the terrain alone:
  flat seeds        slope < FLAT_SEED_DEG (the median slope on the 9t road fill is 5.0 deg)
  background seeds  slope >= STEEP_SEED_DEG (the road fill's 90th percentile is 12.4 deg)
  everything else   contested; the floods meet on the strongest break in slope.
No corridor and no pad limit. Roads, pads and natural flats are one class.
The annotations are used only afterwards, to score what the fill took.

  python notebooks/wellsight_v2/s2_labels/_flat_surface_watershed_seedless_9t.py
"""
import importlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.windows import Window
from scipy.ndimage import binary_fill_holes
from shapely.geometry import box, shape
from skimage.segmentation import watershed

sys.path.insert(0, str(Path(__file__).resolve().parent))
ws = importlib.import_module("_road_driving_surface_watershed_9t")   # DEM, paths, edge_and_slope

FLAT_SEED_DEG = 5.0
STEEP_SEED_DEG = 15.0
TILE_PX, HALO_PX = 3000, 100
CRS = ws.CRS
TAG = f"seedless_flat{FLAT_SEED_DEG:g}deg_steep{STEEP_SEED_DEG:g}deg"
STEM = f"flat_surface_watershed_{TAG}_9t_05"
RES = ws.RESULTS
# single-hue fill plus neutral charcoal for annotations: no red/green pair. Blue #1F5FA8 is the
# lost/found "delivered" blue (dataviz validate_palette.js --mode light --pairs all, worst pair dE 21.1 deutan).
FLAT, INK, MUTED = "#1F5FA8", "#2B2F36", "#5B6168"


def segment(dem, res):
    edge, slope, valid = ws.edge_and_slope(dem, res)
    markers = np.zeros(dem.shape, np.int32)
    markers[valid & (slope < FLAT_SEED_DEG)] = 1
    markers[valid & (slope >= STEEP_SEED_DEG)] = 2
    lab = watershed(edge, markers, mask=valid)
    return lab == 1


def main():
    with rasterio.open(ws.DEM) as src:
        res = src.res[0]
        H, W = src.height, src.width
        flat = np.zeros((H, W), bool)
        for r in range(0, H, TILE_PX):
            for c in range(0, W, TILE_PX):
                h, w = min(TILE_PX, H - r), min(TILE_PX, W - c)
                r0, c0 = max(0, r - HALO_PX), max(0, c - HALO_PX)
                r1, c1 = min(H, r + h + HALO_PX), min(W, c + w + HALO_PX)
                dem = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0)).astype(np.float32)
                dem[dem == src.nodata] = np.nan
                m = segment(dem, res)
                flat[r:r + h, c:c + w] = m[r - r0:r - r0 + h, c - c0:c - c0 + w]
        tf, prof, bounds = src.transform, src.profile, src.bounds
    prof.update(dtype="uint8", nodata=0, count=1, compress="deflate", predictor=1)
    with rasterio.open(ws.DERIVED / f"{STEM}_mask.tif", "w", **prof) as dst:
        dst.write(flat.astype(np.uint8), 1)

    polys = [shape(g) for g, v in shapes(flat.astype(np.uint8), mask=flat, transform=tf) if v == 1]
    gdf = gpd.GeoDataFrame(geometry=polys, crs=CRS)
    gdf["area_m2"] = gdf.area.round(1)

    tile = box(*bounds)
    roads = gpd.read_file(ws.ANN, layer="roads").to_crs(CRS)
    pads = gpd.read_file(ws.ANN, layer="plat").to_crs(CRS)
    roads, pads = roads[roads.intersects(tile)], pads[pads.intersects(tile)]
    road_line = roads.geometry.intersection(tile).union_all()
    pads_u = pads.geometry.union_all()
    known = road_line.buffer(6.0).union(pads_u.buffer(2.0))      # same limits as the seeded runs
    sidx = gdf.sindex
    gdf["touches_annotated_road_or_pad"] = False
    hit = sidx.query(known, predicate="intersects")
    gdf.loc[gdf.index[hit], "touches_annotated_road_or_pad"] = True
    gdf.to_file(RES / f"{STEM}.gpkg", layer="flat_surface", driver="GPKG")

    flat_u = gdf.geometry.union_all()
    tile_ha = tile.area / 1e4
    hyb = ws.DERIVED / "road_driving_surface_watershed_bg6m_slope25deg_padhybrid_band2m_full_9t_05_mask.tif"
    with rasterio.open(hyb) as h:
        hl = h.read(1)
    seeded = hl > 0
    summary = {
        "params": {"flat_seed_deg": FLAT_SEED_DEG, "steep_seed_deg": STEEP_SEED_DEG,
                   "smooth_sigma_px": ws.SMOOTH_SIGMA_PX, "dem": str(ws.DEM.relative_to(ws.REPO))},
        "tile_ha": round(tile_ha, 1),
        "flat_area_ha": round(flat.sum() * res * res / 1e4, 1),
        "flat_share_of_tile": round(float(flat.mean()), 3),
        "polygons": int(len(gdf)),
        "polygons_over_100m2": int((gdf.area_m2 > 100).sum()),
        "largest_polygon_ha": round(float(gdf.area_m2.max()) / 1e4, 1),
        "annotated_centreline_km": round(road_line.length / 1000, 1),
        "annotated_centreline_km_inside_flat": round(road_line.intersection(flat_u).length / 1000, 1),
        "annotated_pad_area_ha": round(pads_u.area / 1e4, 1),
        "annotated_pad_area_inside_flat_ha": round(pads_u.intersection(flat_u).area / 1e4, 1),
        "seeded_hybrid_road_plus_pad_ha": round(seeded.sum() * res * res / 1e4, 1),
        "seeded_hybrid_area_inside_flat_share": round(float(flat[seeded].mean()), 3),
        "flat_area_within_6m_of_road_or_2m_of_pad_ha": round(flat_u.intersection(known).area / 1e4, 1),
        "flat_area_elsewhere_ha": round(flat_u.difference(known).area / 1e4, 1),
    }
    with open(RES / f"{STEM}_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))

    # figure: whole tile (left) and two 120 m windows, one on test line 2 and one on test line 3
    tl = gpd.read_file(ws.TEST_LINES, layer="test_line").to_crs(CRS)
    fig = plt.figure(figsize=(14.5, 7.6))
    gsp = fig.add_gridspec(2, 3, width_ratios=[2, 1, 1], wspace=0.06, hspace=0.16)
    with rasterio.open(ws.HILLSHADE) as hs:
        def panel(ax, bb, step, title, lw):
            w = rasterio.windows.from_bounds(*bb, transform=hs.transform)
            img = hs.read(1, window=w, boundless=True, out_shape=(int(w.height // step), int(w.width // step)))
            ax.imshow(img, cmap="gray", extent=(bb[0], bb[2], bb[1], bb[3]), interpolation="nearest")
            r0, r1 = int((tf.f - bb[3]) / res), int((tf.f - bb[1]) / res)
            c0, c1 = int((bb[0] - tf.c) / res), int((bb[2] - tf.c) / res)
            sub = flat[max(0, r0):r1:step, max(0, c0):c1:step]
            ax.imshow(np.ma.masked_where(~sub, sub), cmap=matplotlib.colors.ListedColormap([FLAT]), alpha=0.55,
                      extent=(bb[0], bb[2], bb[1], bb[3]), interpolation="nearest")
            cl = box(*bb)
            roads.clip(cl).plot(ax=ax, color=INK, lw=lw, linestyle="--")
            pads.clip(cl).boundary.plot(ax=ax, color=INK, lw=lw, linestyle=":")
            ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3]); ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(title, fontsize=9.5, color=INK, loc="left")
        panel(fig.add_subplot(gsp[:, 0]), tuple(bounds), 8,
              f"All of 9t: {summary['flat_share_of_tile']:.0%} of the tile filled", 0.4)
        for k, (ax_pos, n) in enumerate([(gsp[0, 1], 2), (gsp[0, 2], 3), (gsp[1, 1], 1), (gsp[1, 2], 4)]):
            c = tl.geometry.iloc[n - 1].centroid
            panel(fig.add_subplot(ax_pos), (c.x - 60, c.y - 60, c.x + 60, c.y + 60), 1, f"Around test line {n}, 120 m", 1.0)
    fig.suptitle("Flat-surface fill with no shapefile seeds (flat < 5°, steep ≥ 15°)", x=0.02, ha="left",
                 fontsize=12, color=INK)
    fig.text(0.02, 0.01, "Blue fill: what the fill took.  Dashed charcoal: your road centrelines.  "
             "Dotted charcoal: your pad outlines.", fontsize=8.5, color=MUTED)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.05)
    fp = RES / "figures" / f"{STEM}_overview_and_test_lines_on_hillshade.png"
    fig.savefig(fp, dpi=160, facecolor="white")
    print("wrote", fp)


if __name__ == "__main__":
    main()
