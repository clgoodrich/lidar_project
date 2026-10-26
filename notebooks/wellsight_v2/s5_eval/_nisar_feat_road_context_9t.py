"""Product 4: road context of each pixel, from the annotated road lines (not a radar measurement).

Pads are served by an access road that usually ends at the pad. Per 5 m pixel:
  dist_road_m      distance to the nearest road line
  dist_dead_end_m  distance to the nearest dead end (a segment end with no other road within JOIN_M)

These come from the annotations, which were drawn to reach the pads, so they are circular for a pad
test. They are kept as a separate band group ("context") and never mixed into the NISAR sets. For
deployment they would come from the road U-Net output instead.

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_road_context_9t.py
"""
import numpy as np
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree

import _nisar_feat_common as C

JOIN_M = 3.0


def dead_ends(lines):
    ends = np.array([c for g in lines for c in (g.coords[0], g.coords[-1])])
    other = [(i, g) for i, g in enumerate(lines)]
    tree = cKDTree(ends)
    pts = []
    for k, e in enumerate(ends):
        if len(tree.query_ball_point(e, JOIN_M)) > 1:       # another segment end is here
            continue
        seg = k // 2
        if any(g.distance(__import__("shapely.geometry", fromlist=["Point"]).Point(e)) <= JOIN_M for i, g in other
               if i != seg and g.bounds[0] - JOIN_M <= e[0] <= g.bounds[2] + JOIN_M
               and g.bounds[1] - JOIN_M <= e[1] <= g.bounds[3] + JOIN_M):
            continue                                        # sits on the side of another road
        pts.append(e)
    return np.array(pts)


def main():
    idx, stack, tf, shape = C.load()
    del stack
    roads = C.ifg.read_layer(C.ifg.ANN, "roads").to_crs(C.CRS)
    lines = [g for g in roads.geometry.explode(index_parts=False) if g.geom_type == "LineString" and not g.is_empty]
    mask = rasterize([(g, 1) for g in lines], out_shape=shape, transform=tf, fill=0, dtype="uint8", all_touched=True)
    d_road = distance_transform_edt(mask == 0) * abs(tf.a)
    ends = dead_ends(lines)
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    px = np.c_[tf.c + (xx.ravel() + 0.5) * tf.a, tf.f + (yy.ravel() + 0.5) * tf.e]
    d_end = cKDTree(ends).query(px)[0].reshape(shape)
    print(f"{len(lines)} road lines, {len(ends)} dead ends", flush=True)
    C.write_bands("context", {"dist_road_m": d_road, "dist_dead_end_m": d_end}, tf, shape)


if __name__ == "__main__":
    main()
