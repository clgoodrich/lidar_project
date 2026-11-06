"""Build labels and manifests for pad segmentation, road segmentation, and road classification.

WHAT THIS IS FOR
----------------
`_build_pit_dataset_v2.py` decided the train/val/test split by cutting the tile
into a 12x12 grid of blocks and handing each block to a split. This script does
NOT re-decide anything. It reads that block grid and asks, for every pad and
every road, which block do you sit in -- and therefore which split are you.

That inversion is the whole idea. Pits, pads and roads then never disagree about
which ground is held out, so a patch centred on a training pad cannot overlap a
block the pit model is being scored on.

THREE GRANULARITIES, ONE GRID
-----------------------------
    pads   -> one row per polygon
    roads  -> one row per ~40 m CHUNK of a polyline (see CHUNK_M below)
    points -> one row per sample point every 4 m along a line

All three carry a block_id and a split traced back to the same grid.

Outputs (under data/derivatives/tiles/9t/):
    labels_pad_9t_05.tif        uint8  0=bg, 1=pad
    labels_road_9t_05.tif        uint8  0=bg, 1=road  (roads buffered 1.5 m)
    pad_dataset_manifest.csv    one row per pad: pad_id, block_id, split, centroid_x/y
    road_dataset_manifest.csv    one row per road LINE: road_id, kind, block_id, split, mid_x/y
    road_classifier_samples.csv  one row per sample POINT along lines (for the classifier)
    road_chunks_9t.gpkg          the chunk GEOMETRY, so eval can draw what it scored

Reads pit_blocks_9t.gpkg, so it is stale the moment the pit dataset is rebuilt.
Nothing enforces that coupling -- rerun this after every pit dataset rebuild.
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T as D, path_for, read_layer

ANN = path_for("truth") / "annotations_proj.gpkg"
REF = D / "dem_9t_05.tif"
BLOCKS = D / "pit_blocks_9t.gpkg"

ROAD_BUFFER_M = 1.5  # half-width for road rasterization
SAMPLE_STRIDE_M = 4.0  # sample points along lines for the classifier
CHUNK_M = 40.0  # split long road/not_road polylines into ~40 m segments so the
                # U-Net samples patch centers ALONG every road (not just the
                # midpoint) and the eval scores comparable-length units. Drainage
                # already arrives pre-chunked from the cross-section filter.


def chunk_line(line: LineString, chunk_m: float):
    """Split a polyline into ~chunk_m segments (densified to ~5 m vertices).

    Two reasons, both about fairness rather than convenience:

    TRAINING  the sampler centres a patch on each row. Leave a 2 km road as one
              row and the model only ever sees its midpoint.
    EVAL      a 2 km road and a 30 m spur are not the same unit. Scoring them
              as if they were lets one long correct road hide fifty short misses.
    """
    if line is None or line.is_empty:
        return []
    if line.length <= chunk_m:
        return [line]                       # already short enough, leave it alone
    # Cut at evenly spaced distances along the line, so every piece is the same
    # length rather than however the original vertices happened to fall.
    n = int(np.ceil(line.length / chunk_m))
    edges = np.linspace(0.0, line.length, n + 1)
    out = []
    for t0, t1 in zip(edges[:-1], edges[1:]):
        # Re-densify to ~5 m vertices. interpolate() walks the true curve, so a
        # chunk cut from a bend keeps the bend instead of becoming a chord.
        inner = max(2, int(np.ceil((t1 - t0) / 5.0)) + 1)
        ts = np.linspace(t0, t1, inner)
        seg = LineString([(p.x, p.y) for p in (line.interpolate(t) for t in ts)])
        if not seg.is_empty and seg.length > 0:
            out.append(seg)
    return out


def assign_split(geom_or_pt, blocks):
    """Look up which block (and thereby split) a point or geometry falls in.

    This is the inversion described at the top of the file: the feature asks the
    grid, rather than the grid handing out splits. A polygon is reduced to its
    centroid first, so a pad straddling a block boundary lands in exactly one
    block instead of two.

    Anything outside every block returns the literal string "unused" -- the same
    token the pit manifest writes, and the one `_build_pad_road_dataset` consumers
    filter on. It is not None and it is not "test".
    """
    if geom_or_pt is None or getattr(geom_or_pt, "is_empty", True):
        return None, "unused"
    if hasattr(geom_or_pt, "centroid"):
        pt = geom_or_pt.centroid if geom_or_pt.geom_type != "Point" else geom_or_pt
    else:
        pt = geom_or_pt
    hit = blocks[blocks.geometry.contains(pt)]
    if len(hit):
        return int(hit.iloc[0].block_id), str(hit.iloc[0].split)
    return None, "unused"


def sample_along_line(line: LineString, stride_m: float):
    """One point every stride_m along a line, for the road CLASSIFIER.

    Different job from chunk_line. The classifier does not segment; it answers
    "is this spot on a road, yes or no" at a point, so it wants dense point
    samples rather than geometry.
    """
    pts = []
    L = line.length
    if L < 1.0:
        # Shorter than a metre: one sample at the midpoint, or the stride
        # arithmetic below would yield nothing at all.
        pts.append(line.interpolate(0.5, normalized=True))
        return pts
    n = max(1, int(L // stride_m))
    for i in range(n + 1):
        d = min(i * stride_m, L)   # clamp so the last sample lands on the end
        pts.append(line.interpolate(d))
    return pts


def main():
    # Step 1. Take the grid from the DEM. Everything rasterized below has to land
    # on exactly this grid or the labels will not line up with the features.
    with rasterio.open(REF) as r:
        profile = r.profile.copy()
        H, W = r.height, r.width
        tf = r.transform
        crs = r.crs

    # Step 2. Read the block grid the pit builder already decided, plus the four
    # annotation layers. `not_roads` are things a human looked at and ruled out --
    # they are negatives, not missing data, and the classifier needs them.
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    pad = read_layer(ANN, "pad")
    roads = read_layer(ANN, "roads")
    not_roads = read_layer(ANN, "not_roads")
    drainage = (read_layer(ANN, "drainage")
                if "drainage" in gpd.list_layers(ANN)["name"].tolist()
                else gpd.GeoDataFrame(geometry=[], crs=roads.crs))
    print(f"pad={len(pad)}  roads={len(roads)}  not_roads={len(not_roads)}  "
          f"drainage={len(drainage)}")

    # --- Step 3. pad label raster (binary) ---
    # A pad is drawn as a polygon, so it rasterizes directly: every cell whose
    # centre falls inside a pad becomes 1. No buffering needed.
    #
    # WATCH OUT: rasterize() returns an all-zero array for an empty shape list.
    # It does not raise. A label raster of nine million zeros writes, compresses
    # and opens in QGIS exactly like a good one -- check the printed pixel count.
    pad_arr = rasterize(
        [(g, 1) for g in pad.geometry if g and not g.is_empty],
        out_shape=(H, W), transform=tf, fill=0, dtype="uint8",
    )
    p1 = profile.copy()
    p1.update(dtype="uint8", count=1, nodata=255, compress="deflate", predictor=2)
    with rasterio.open(D / "labels_pad_9t_05.tif", "w", **p1) as dst:
        dst.write(pad_arr, 1)
    print(f"labels_pad_9t_05.tif  ({int(pad_arr.sum())} px = {int(pad_arr.sum()*0.25)} m^2)")

    # --- Step 4. road label raster (binary, buffered) ---
    # Roads are drawn as centrelines, which have no width, so rasterizing them
    # raw would give a one-cell thread. Buffer by the half-width first: 1.5 m
    # each side approximates a single-lane haul road.
    buffered = [g.buffer(ROAD_BUFFER_M) for g in roads.geometry if g and not g.is_empty]
    road_arr = rasterize(
        [(g, 1) for g in buffered],
        out_shape=(H, W), transform=tf, fill=0, dtype="uint8",
    )
    with rasterio.open(D / "labels_road_9t_05.tif", "w", **p1) as dst:
        dst.write(road_arr, 1)
    print(f"labels_road_9t_05.tif  ({int(road_arr.sum())} px = {int(road_arr.sum()*0.25)} m^2)")

    # --- Step 5. pad manifest: one row per pad polygon ---
    # The rasters above say WHERE things are. The manifest says which ones the
    # sampler may centre a patch on, and which split each belongs to. Without it
    # the trainer has pixels but no list of examples.
    pad_rows = []
    for _, row in pad.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        bid, split = assign_split(row.geometry, blocks)
        c = row.geometry.centroid
        pad_rows.append({"pad_id": int(row.pad_id), "block_id": bid, "split": split,
                          "centroid_x": c.x, "centroid_y": c.y,
                          "area_m2": float(row.geometry.area)})
    pad_man = pd.DataFrame(pad_rows)
    pad_man.to_csv(D / "pad_dataset_manifest.csv", index=False)
    print(f"pad_dataset_manifest.csv  splits={pad_man['split'].value_counts().to_dict()}")

    # --- Step 6. road CHUNK manifest + chunk geometries (used by the road U-Net) ---
    # Roads/not_roads are long polylines -> chunk them so every ~40 m becomes its
    # own patch center (training) and eval unit. Drainage is already short chunks.
    chunk_rows = []   # -> road_dataset_manifest.csv (centers + split for sampler)
    chunk_geoms = []  # -> road_chunks_9t.gpkg (geometry for eval)
    # Three sources, one loop. `kind` is carried through to the manifest so the
    # trainer can weight them differently: road is the positive, not_road is a
    # human-confirmed negative, drainage is the confuser that used to be scored
    # as a false road. Drainage arrives pre-chunked from the cross-section
    # filter, so do_chunk is False for it.
    for src, kind, do_chunk in [(roads, "road", True),
                                (not_roads, "not_road", True),
                                (drainage, "drainage", False)]:
        for i, row in src.reset_index(drop=True).iterrows():
            g = row.geometry
            if g is None or g.is_empty:
                continue
            segs = chunk_line(g, CHUNK_M) if do_chunk else [g]
            for j, seg in enumerate(segs):
                # The chunk's midpoint decides its split. A 40 m chunk cannot
                # meaningfully straddle a 375 m block, so one lookup is enough.
                mid = seg.interpolate(0.5, normalized=True)
                bid, split = assign_split(mid, blocks)
                lid = f"{kind}_{i}_{j}"
                chunk_rows.append({"line_id": lid, "kind": kind,
                                   "parent_id": i, "seg_idx": j,
                                   "block_id": bid, "split": split,
                                   "mid_x": mid.x, "mid_y": mid.y,
                                   "length_m": float(seg.length)})
                chunk_geoms.append({"line_id": lid, "kind": kind, "split": split,
                                    "geometry": seg})
    road_man = pd.DataFrame(chunk_rows)
    road_man.to_csv(D / "road_dataset_manifest.csv", index=False)
    gchunks = gpd.GeoDataFrame(chunk_geoms, crs=roads.crs)
    gchunks.to_file(D / "road_chunks_9t.gpkg", layer="chunks", driver="GPKG")
    for k in ("road", "not_road", "drainage"):
        sub = road_man[road_man.kind == k]
        if len(sub):
            used = sub[sub.split.isin(["train", "val", "test"])]
            print(f"road_dataset_manifest.csv  {k:9s} chunks={len(sub):5d}  "
                  f"in-tile median_len={used.length_m.median():.0f}m  "
                  f"splits={used['split'].value_counts().to_dict()}")
    print(f"wrote road_chunks_9t.gpkg ({len(gchunks)} chunks)")

    # --- Step 7. road classifier sample points (per POINT along lines) ---
    # A separate, much simpler model from the U-Net: given the terrain channels
    # at one location, is this a road? Trained on points, so it needs points --
    # label 1 from roads, label 0 from the human-rejected not_roads.
    pt_rows = []
    for src, kind, label in [(roads, "road", 1), (not_roads, "not_road", 0)]:
        for i, row in src.reset_index(drop=True).iterrows():
            line_id = f"{kind}_{i}"
            if row.geometry is None or row.geometry.is_empty:
                continue  # keep i aligned with the gpkg row order used by eval
            for pt in sample_along_line(row.geometry, SAMPLE_STRIDE_M):
                bid, split = assign_split(pt, blocks)
                pt_rows.append({"line_id": line_id, "kind": kind, "label": label,
                                "block_id": bid, "split": split,
                                "x": pt.x, "y": pt.y})
    pts_df = pd.DataFrame(pt_rows)
    pts_df.to_csv(D / "road_classifier_samples.csv", index=False)
    by_split = pts_df.groupby(["label", "split"]).size().unstack(fill_value=0)
    print(f"road_classifier_samples.csv  total={len(pts_df)}")
    print(by_split)


if __name__ == "__main__":
    main()
