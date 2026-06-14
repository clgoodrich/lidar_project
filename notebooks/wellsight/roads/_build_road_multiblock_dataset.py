"""Build a MULTI-BLOCK road-training dataset across the data_3x3 blocks.

Why: the deployed road_unet_1m trained on the 9t slice only (a few km of road)
AND on a roughness_5 channel-7, while every data_3x3 block stores roughness_11.
This builds road+drainage labels on the 6 blocks that actually carry hand-drawn
road (191 km total) using each block's own roughness_11 feature stack, so the
retrained model trains and infers on the SAME channels and far more terrain.

Spatial-block split (no leakage; whole blocks held out):
    train : 618594 (86.3 km), 622591 (11.1 km), 613603 (4.8 km), 613608 (0.1 km)
    val   : 618591 (42.5 km)
    test  : 622594 (46.9 km)
613590 (the inference target) has ~0 km road GT and stays a pure inference tile.

Outputs (under data/derivatives/tiles/road_multiblock/):
    labels_road_<key>_1m.tif         uint8 0=bg 1=road 2=drainage, 255=nodata
    road_mb_manifest.csv             one row per chunk: block,key,kind,split,mid_x,mid_y,length_m
    road_mb_chunks.gpkg              chunk geometries (for eval)
    feature_stats_road_mb.json       per-channel mean/std over TRAIN blocks only

Matches _prep_road_1m.py label recipe: road buffer 1.5 m, drainage buffer 2.0 m,
drainage painted first then road on top (culverts stay road).

CLI:  python notebooks/wellsight/roads/_build_road_multiblock_dataset.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS

ANN = DERIV / "annotations" / "annotations_proj.gpkg"
BLOCKDIR = DERIV / "tiles" / "data_3x3" / "westernpa_d20"
OUTDIR = DERIV / "tiles" / "road_multiblock"

ROAD_BUFFER_M = 1.5
DRAIN_BUFFER_M = 2.0
CHUNK_M = 40.0  # roads/not_roads split into ~40 m segments; drainage native

SPLITS = {
    "618594": "train", "622591": "train", "613603": "train", "613608": "train",
    "618591": "val",
    "622594": "test",
}

CHANNELS = ("lrm_25", "lrm_5", "slope", "tpi_05",
            "openness_pos", "openness_neg", "roughness_11")


def chunk_line(line: LineString, chunk_m: float):
    if line is None or line.is_empty:
        return []
    if line.length <= chunk_m:
        return [line]
    n = int(np.ceil(line.length / chunk_m))
    edges = np.linspace(0.0, line.length, n + 1)
    out = []
    for t0, t1 in zip(edges[:-1], edges[1:]):
        inner = max(2, int(np.ceil((t1 - t0) / 5.0)) + 1)
        ts = np.linspace(t0, t1, inner)
        seg = LineString([(p.x, p.y) for p in (line.interpolate(t) for t in ts)])
        if not seg.is_empty and seg.length > 0:
            out.append(seg)
    return out


def feat_path(key: str) -> Path:
    return BLOCKDIR / key / f"features_{key}_1m.tif"


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    roads = gpd.read_file(ANN, layer="roads").to_crs(DST_CRS)
    not_roads = gpd.read_file(ANN, layer="not_roads").to_crs(DST_CRS)
    layers = gpd.list_layers(ANN)["name"].tolist()
    drainage = (gpd.read_file(ANN, layer="drainage").to_crs(DST_CRS)
                if "drainage" in layers else gpd.GeoDataFrame(geometry=[], crs=DST_CRS))

    manifest_rows, chunk_geoms = [], []
    stats_accum = {c: [] for c in CHANNELS}  # train-only sample pools

    for key, split in SPLITS.items():
        fp = feat_path(key)
        if not fp.exists():
            raise FileNotFoundError(fp)
        from shapely.geometry import box as _box
        with rasterio.open(fp) as r:
            H, W = r.height, r.width
            tf = r.transform
            crs = r.crs
            bands = [r.descriptions[i] for i in range(r.count)]
            band1 = r.read(1)  # for nodata mask
            bbox = _box(*r.bounds)
            assert tuple(bands) == CHANNELS, f"{key} band order {bands} != {CHANNELS}"
        nodata = ~np.isfinite(band1)

        # --- label raster: drainage (2) first, road (1) on top ---
        label = np.zeros((H, W), dtype="uint8")
        dr_b = drainage.clip(bbox)
        if len(dr_b):
            dbuf = [g.buffer(DRAIN_BUFFER_M) for g in dr_b.geometry if g and not g.is_empty]
            if dbuf:
                da = rasterize([(g, 1) for g in dbuf], out_shape=(H, W),
                               transform=tf, fill=0, dtype="uint8")
                label[da == 1] = 2
        rd_b = roads.clip(bbox)
        if len(rd_b):
            rbuf = [g.buffer(ROAD_BUFFER_M) for g in rd_b.geometry if g and not g.is_empty]
            if rbuf:
                ra = rasterize([(g, 1) for g in rbuf], out_shape=(H, W),
                               transform=tf, fill=0, dtype="uint8")
                label[ra == 1] = 1
        label[nodata] = 255  # ignore no-data in the loss

        prof = dict(driver="GTiff", height=H, width=W, count=1, dtype="uint8",
                    crs=crs, transform=tf, nodata=255, compress="deflate", predictor=2)
        outlbl = OUTDIR / f"labels_road_{key}_1m.tif"
        with rasterio.open(outlbl, "w", **prof) as dst:
            dst.write(label, 1)
        print(f"[{key}:{split:5s}] road_px={int((label==1).sum()):7d} "
              f"drain_px={int((label==2).sum()):7d} -> {outlbl.name}")

        # --- chunks/manifest (clip to block) ---
        for src, kind, do_chunk in [(rd_b, "road", True),
                                    (not_roads.clip(bbox), "not_road", True),
                                    (dr_b, "drainage", False)]:
            for i, row in src.reset_index(drop=True).iterrows():
                g = row.geometry
                if g is None or g.is_empty or g.geom_type not in ("LineString",):
                    # MultiLineString from clip -> explode
                    if g is not None and g.geom_type == "MultiLineString":
                        parts = list(g.geoms)
                    else:
                        continue
                else:
                    parts = [g]
                for part in parts:
                    segs = chunk_line(part, CHUNK_M) if do_chunk else [part]
                    for j, seg in enumerate(segs):
                        mid = seg.interpolate(0.5, normalized=True)
                        lid = f"{key}_{kind}_{i}_{j}"
                        manifest_rows.append({
                            "line_id": lid, "block": key, "kind": kind, "split": split,
                            "mid_x": mid.x, "mid_y": mid.y, "length_m": float(seg.length)})
                        chunk_geoms.append({"line_id": lid, "block": key, "kind": kind,
                                            "split": split, "geometry": seg})

        # --- train-only stats sample (subsample finite px per band) ---
        if split == "train":
            with rasterio.open(fp) as r:
                for bi, c in enumerate(CHANNELS, start=1):
                    a = r.read(bi).astype(np.float32)
                    a = a[np.isfinite(a)]
                    if a.size > 400_000:  # subsample to bound memory
                        a = a[np.random.default_rng(0).integers(0, a.size, 400_000)]
                    stats_accum[c].append(a)

    man = pd.DataFrame(manifest_rows)
    man.to_csv(OUTDIR / "road_mb_manifest.csv", index=False)
    gpd.GeoDataFrame(chunk_geoms, crs=DST_CRS).to_file(
        OUTDIR / "road_mb_chunks.gpkg", layer="chunks", driver="GPKG")

    stats = {}
    for c in CHANNELS:
        v = np.concatenate(stats_accum[c])
        stats[c] = {"mean": float(v.mean()), "std": float(v.std()),
                    "p2": float(np.percentile(v, 2)), "p98": float(np.percentile(v, 98))}
    (OUTDIR / "feature_stats_road_mb.json").write_text(json.dumps(stats, indent=2))

    print("\n=== manifest summary (chunks) ===")
    for split in ("train", "val", "test"):
        s = man[man.split == split]
        by = s.groupby("kind").size().to_dict()
        km = s.groupby("kind").length_m.sum().div(1000).round(1).to_dict()
        print(f"  {split:5s}: {dict(by)}  km={km}")
    print("\n=== train-block normalization (roughness_11 channel set) ===")
    for c in CHANNELS:
        print(f"  {c:14s} mean={stats[c]['mean']:8.3f} std={stats[c]['std']:8.3f}")
    print(f"\nwrote {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
