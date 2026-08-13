"""Build per-pixel road-orientation label rasters for the `orient` sweep variant.

For every road pixel, the label is the local road bearing binned into N_ORI
direction bins over 0..180 deg (roads are undirected, so mod 180). Non-road
pixels are 255 (ignore). Bearing comes from walking each road centerline in
~STEP m pieces and burning each piece (buffered to road half-width) with its
own bearing bin, so curved roads get locally-correct orientation.

Outputs (uint8, aligned to the matching road-label raster grid):
  data/derivatives/tiles/9t/labels_roadorient_9t_1m.tif
      from annotations_proj.gpkg layer 'roads' (9t)
  .../613590/corrections/labels_roadorient_corr_613590_1m.tif
      from correction_lines_613590.gpkg layers 'added' + 'kept'
      (rejects are seg-negatives -> no orientation; corridor 255 elsewhere)

Reproduce: python notebooks/wellsight_v2/s2_labels/_build_orient_labels.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T, path_for

N_ORI = 8
STEP = 5.0          # bearing-sampling step along each line (m)
ROAD_BUF = 1.5      # matches labels_road_*_1m.tif

ANN = path_for("truth") / "annotations_proj.gpkg"
L1 = DERIV_9T / "labels_road_9t_1m.tif"
OUT_9T = DERIV_9T / "labels_roadorient_9t_1m.tif"

BLOCK = path_for("data_3x3") / "westernpa_d20" / "613590"
CORR = BLOCK / "corrections"
CORR_L = CORR / "labels_road_corr_613590_1m.tif"
CORR_LINES = CORR / "correction_lines_613590.gpkg"
OUT_CORR = CORR / "labels_roadorient_corr_613590_1m.tif"


def bearing_bin(x0, y0, x1, y1):
    theta = np.arctan2(y1 - y0, x1 - x0) % np.pi     # 0..pi (undirected)
    return int(theta / (np.pi / N_ORI)) % N_ORI


def line_pieces(geom):
    """Yield (buffered_piece, bin) walking geom in ~STEP m increments."""
    geoms = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
    for g in geoms:
        if g.is_empty or g.length < 1e-6:
            continue
        ts = np.arange(0, g.length, STEP)
        ts = np.append(ts, g.length)
        for a, b in zip(ts[:-1], ts[1:]):
            pa, pb = g.interpolate(a), g.interpolate(b)
            if pa.distance(pb) < 1e-6:
                continue
            seg = LineString([(pa.x, pa.y), (pb.x, pb.y)])
            yield seg.buffer(ROAD_BUF), bearing_bin(pa.x, pa.y, pb.x, pb.y)


def build(lines_gdf, grid_path, out_path):
    with rasterio.open(grid_path) as r:
        H, W, tf, crs = r.height, r.width, r.transform, r.crs
    shapes = []
    for geom in lines_gdf.geometry:
        if geom is None:
            continue
        shapes.extend(line_pieces(geom))
    print(f"  {len(shapes)} oriented pieces -> {out_path.name}")
    arr = rasterize(shapes, out_shape=(H, W), transform=tf, fill=255,
                    dtype="uint8", merge_alg=rasterio.enums.MergeAlg.replace)
    prof = {"driver": "GTiff", "height": H, "width": W, "count": 1,
            "dtype": "uint8", "crs": crs, "transform": tf, "nodata": 255,
            "compress": "deflate", "tiled": True}
    with rasterio.open(out_path, "w", **prof) as dst:
        dst.write(arr, 1)
    vals, cnts = np.unique(arr[arr != 255], return_counts=True)
    print(f"    bins present: {dict(zip(vals.tolist(), cnts.tolist()))}")


def main():
    print("9t:")
    roads = gpd.read_file(ANN, layer="roads").to_crs("EPSG:6346")
    build(roads, L1, OUT_9T)

    print("613590 corrections (added + kept):")
    added = gpd.read_file(CORR_LINES, layer="added").to_crs("EPSG:6346")
    kept = gpd.read_file(CORR_LINES, layer="kept").to_crs("EPSG:6346")
    both = gpd.GeoDataFrame(
        geometry=list(added.geometry) + list(kept.geometry), crs="EPSG:6346")
    build(both, CORR_L, OUT_CORR)


if __name__ == "__main__":
    main()
