"""Generalized YOLOv8-seg inference (pit + pad models) on an arbitrary 0.5 m tile.

The per-model infer scripts (_pit_yolo_infer / _pad_yolo_infer) are hardwired to
9t via ic.RGB3_PATH / ic.reference_profile(). This runs the same trained weights
on any tile suffix by building that tile's rgb3 stack (hillshade az315/alt25,
slope, lrm_25 -> ic._norm_*), then reusing ic.yolo_sliding_inference +
detections_to_gpkg with the tile's own grid. Detections whose centroid falls on
no-data DEM are dropped.

CLI:
  python notebooks/wellsight/build/_yolo_infer_tile.py --suffix 613590_05
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, make_profile, path_for
import _instance_common as ic  # noqa: E402

PATCH, OVERLAP, IMGSZ = 256, 64, 640
SCORE_THRESH, NMS_IOU = 0.10, 0.4


def ensure_hillshade_alt25(tile_dir: Path, sfx: str) -> Path:
    p = tile_dir / f"hillshade_az315_alt25_{sfx}.tif"
    if not p.exists():
        import whitebox
        wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
        wbt.set_working_dir(str(tile_dir.resolve()))
        wbt.hillshade(dem=f"dem_{sfx}.tif", output=p.name, azimuth=315.0, altitude=25.0)
    return p


def build_rgb3(tile_dir: Path, sfx: str) -> Path:
    out = tile_dir / f"rgb3_{sfx}.tif"
    if out.exists():
        return out
    hs = ensure_hillshade_alt25(tile_dir, sfx)
    with rasterio.open(hs) as r:
        hs_arr = r.read(1, masked=True).filled(0); prof = r.profile.copy()
    with rasterio.open(tile_dir / f"slope_{sfx}.tif") as r:
        sl_arr = r.read(1, masked=True).filled(0)
    with rasterio.open(tile_dir / f"lrm_25_{sfx}.tif") as r:
        lr_arr = r.read(1, masked=True).filled(0)
    rgb = np.stack([ic._norm_hillshade(hs_arr), ic._norm_slope(sl_arr),
                    ic._norm_lrm(lr_arr)], axis=0).astype(np.float32)
    op = make_profile(width=rgb.shape[2], height=rgb.shape[1],
                      transform=prof["transform"], crs=prof["crs"],
                      dtype="float32", nodata=-1.0, count=3, bigtiff=True)
    with rasterio.open(out, "w", **op) as d:
        d.write(rgb)
    print(f"  built {out.name} {rgb.shape}")
    return out


def run_model(ckpt: Path, rgb_path: Path, ref_profile: dict, out_gpkg: Path,
              cls_map: dict, layer: str, valid: np.ndarray):
    from ultralytics import YOLO
    import torch
    from torchvision.ops import nms
    import geopandas as gpd

    model = YOLO(str(ckpt))
    dets = ic.yolo_sliding_inference(model, rgb_path, PATCH, OVERLAP,
                                     score_thresh=SCORE_THRESH, imgsz=IMGSZ)
    for d in dets:
        d["cls"] = cls_map.get(d.get("cls_id", 0), list(cls_map.values())[0])
    kept = []
    for cls in set(d["cls"] for d in dets):
        grp = [d for d in dets if d["cls"] == cls]
        if not grp:
            continue
        bt = torch.tensor([d["bbox"] for d in grp], dtype=torch.float32)
        st = torch.tensor([d["score"] for d in grp], dtype=torch.float32)
        kept.extend(grp[i] for i in nms(bt, st, NMS_IOU).tolist())
    if out_gpkg.exists():
        out_gpkg.unlink()
    ic.detections_to_gpkg(kept, ref_profile, out_gpkg, layer=layer,
                          score_thresh=SCORE_THRESH)
    # drop detections whose centroid sits on no-data DEM
    n_before = len(kept)
    if out_gpkg.exists():
        g = gpd.read_file(out_gpkg, layer=layer)
        tf = ref_profile["transform"]
        H, W = valid.shape
        keep_rows = []
        for geom in g.geometry:
            cx, cy = geom.centroid.x, geom.centroid.y
            col = int((cx - tf.c) / tf.a); row = int((cy - tf.f) / tf.e)
            keep_rows.append(0 <= row < H and 0 <= col < W and bool(valid[row, col]))
        g = g[keep_rows]
        g.to_file(out_gpkg, layer=layer, driver="GPKG")
        print(f"  {layer}: {n_before} dets -> {len(g)} after no-data filter")
        return len(g)
    print(f"  {layer}: 0 detections")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", default="613590_05")
    args = ap.parse_args()
    sfx = args.suffix
    tile_dir = path_for("derived") / sfx
    out_dir = DERIV / f"inference_{sfx}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rgb_path = build_rgb3(tile_dir, sfx)
    with rasterio.open(tile_dir / f"dem_{sfx}.tif") as r:
        ref_profile = r.profile.copy()
        dem = r.read(1); nd = r.nodata
    valid = np.isfinite(dem) & (dem != nd if nd is not None else True)

    pit_ck = path_for("models_retired") / "pit_08_yolo" / "best.pt"
    pad_ck = path_for("models_retired") / "pad_06_yolo" / "best.pt"
    n_pit = run_model(pit_ck, rgb_path, ref_profile,
                      out_dir / f"pit_yolo_candidates_{sfx}.gpkg",
                      {0: "floor", 1: "wall"}, "pit_yolo", valid)
    n_pad = run_model(pad_ck, rgb_path, ref_profile,
                      out_dir / f"pad_yolo_candidates_{sfx}.gpkg",
                      {0: "pad"}, "pad_yolo", valid)
    print(f"[{sfx}] YOLO candidates: pit={n_pit}  pad={n_pad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
