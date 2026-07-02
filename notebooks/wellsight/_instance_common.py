"""Shared helpers for instance-segmentation experiments on the 9t tile.

Used by:
  * pits/_pit_maskrcnn.py + _pit_maskrcnn_infer.py
  * pits/_pit_yolo.py     + _pit_yolo_infer.py
  * plats/_plat_maskrcnn.py + _plat_maskrcnn_infer.py
  * plats/_plat_yolo.py     + _plat_yolo_infer.py

Responsibilities:
  * Build / cache the 3-channel composite raster (hillshade + slope + LRM) used as
    pretraining-friendly input for Mask R-CNN and YOLO-seg.
  * Read the per-pit / per-plat manifests + matching polygon layers.
  * Sample patch windows centred on annotated instances with random jitter.
  * Convert polygon sets into Mask R-CNN targets (boxes + binary masks + labels)
    and YOLO-seg label text (class + normalized polygon vertices).
  * Stitch per-instance detections back into a full-tile probability raster +
    write the per-detection polygons to GeoPackage.
  * Per-instance recall / IoU evaluation against the test split.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize, shapes
from rasterio.transform import Affine, rowcol
from rasterio.windows import Window
from shapely.geometry import Polygon, box, shape

from _common import DERIV_9T, DST_CRS, make_profile, write_tif

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def set_determinism(seed: int = 0) -> None:
    """Pin every RNG and request deterministic kernels (best effort).

    Seeds the Python / NumPy / torch RNGs (so the random init of the new
    detection heads and every draw is fixed) and forces deterministic cuDNN.
    This removes the *avoidable* sources of run-to-run variance — head init and
    (with a seeded DataLoader generator) batch order.

    IMPORTANT — GPU Mask R-CNN training is NOT bit-for-bit reproducible, even
    with this. ``roi_align``'s backward pass has no deterministic CUDA kernel
    (it uses atomic adds), so ``use_deterministic_algorithms(True)`` would hard
    error; we set ``warn_only=True`` so training still runs. The result is
    *close* run to run, not identical. True bit-exactness would require CPU
    training (deterministic roi_align there), which is impractically slow for a
    full run.

    The reliable way to reproduce a *model's outputs* is therefore not to
    re-train but to load the saved ``best.pt`` and run inference, which IS
    deterministic. This also cannot recreate a checkpoint trained before
    determinism was wired in (the current ``best.pt`` used an unseeded RNG).
    """
    import os
    import random

    # must be set before the CUDA context is created for deterministic cuBLAS
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed)

    import torch
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
    except Exception:
        pass


def seed_worker(worker_id: int) -> None:  # noqa: ARG001
    """DataLoader ``worker_init_fn`` — re-seed each worker deterministically."""
    import random

    import torch
    s = torch.initial_seed() % (2 ** 32)
    np.random.seed(s)
    random.seed(s)


def make_loader_generator(seed: int = 0):
    """A seeded ``torch.Generator`` for DataLoader shuffle reproducibility."""
    import torch
    g = torch.Generator()
    g.manual_seed(seed)
    return g


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ANN_GPKG = DERIV_9T.parent.parent / "annotations" / "annotations_proj.gpkg"  # = data/derivatives/annotations
PIT_MANIFEST = DERIV_9T / "pit_dataset_manifest.csv"
PAD_MANIFEST = DERIV_9T / "plat_dataset_manifest.csv"  # legacy on-disk name
PLAT_MANIFEST = PAD_MANIFEST  # back-compat alias
DEM_REF = DERIV_9T / "dem_9t_05.tif"
RGB3_PATH = DERIV_9T / "rgb3_9t_05.tif"

# Source rasters for the 3-channel composite.
HILLSHADE_SRC = DERIV_9T / "hillshade_az315_alt25_9t_05.tif"
SLOPE_SRC = DERIV_9T / "slope_9t_05.tif"
LRM_SRC = DERIV_9T / "lrm_25_9t_05.tif"


# ---------------------------------------------------------------------------
# 3-channel composite ("RGB3") - one-time-cached input for pretrained backbones
# ---------------------------------------------------------------------------

def _norm_hillshade(x: np.ndarray) -> np.ndarray:
    return np.clip(x.astype(np.float32) / 255.0, 0.0, 1.0)


def _norm_slope(x: np.ndarray) -> np.ndarray:
    # Slope in degrees; pit walls typically <60 deg so clipping at 60 is generous.
    return np.clip(x.astype(np.float32) / 60.0, 0.0, 1.0)


def _norm_lrm(x: np.ndarray) -> np.ndarray:
    # LRM is signed local relief; pit floors are deep negatives, walls positive.
    # Clip to [-3, 3] (meters) then shift to [0, 1].
    return np.clip((x.astype(np.float32) + 3.0) / 6.0, 0.0, 1.0)


def build_rgb3_stack(*, force: bool = False) -> Path:
    """Compose (hillshade, slope, lrm_25) into a single 3-band float32 GeoTIFF.

    Cached at data/derivatives/tiles/9t/rgb3_9t_05.tif.
    """
    if RGB3_PATH.exists() and not force:
        return RGB3_PATH

    with rasterio.open(HILLSHADE_SRC) as r:
        hs_arr = r.read(1, masked=True).filled(0)
        profile = r.profile.copy()
    with rasterio.open(SLOPE_SRC) as r:
        sl_arr = r.read(1, masked=True).filled(0)
    with rasterio.open(LRM_SRC) as r:
        lr_arr = r.read(1, masked=True).filled(0)

    rgb = np.stack([_norm_hillshade(hs_arr),
                    _norm_slope(sl_arr),
                    _norm_lrm(lr_arr)], axis=0).astype(np.float32)

    out_profile = make_profile(
        width=rgb.shape[2], height=rgb.shape[1],
        transform=profile["transform"], crs=profile["crs"],
        dtype="float32", nodata=-1.0, count=3, bigtiff=True,
    )
    with rasterio.open(RGB3_PATH, "w", **out_profile) as dst:
        dst.write(rgb)
    print(f"  wrote {RGB3_PATH} ({rgb.shape})")
    return RGB3_PATH


# ---------------------------------------------------------------------------
# Manifest + polygon loading
# ---------------------------------------------------------------------------

# Class-name -> integer maps. Mask R-CNN reserves 0 for background (1-based
# foreground); YOLO is 0-based. Target builders pick the right map.
MASKRCNN_CLASS_IDS = {"pit": 1, "floor": 1, "wall": 2, "pad": 1}
YOLO_CLASS_IDS = {"floor": 0, "wall": 1, "pit": 0, "pad": 0}


@dataclass(frozen=True)
class InstanceSet:
    """Polygons grouped by split with stable instance IDs.

    gdf carries a 'cls' column (class name string, e.g. 'floor'/'wall'/'pad')
    so the target builders can emit multi-class labels.
    """
    name: str                                     # 'pit' or 'pad'
    gdf: gpd.GeoDataFrame                         # cols: inst_id, cls, geometry
    split_ids: dict[str, list[int]]               # split -> list of inst_id

    def for_split(self, split: str) -> gpd.GeoDataFrame:
        return self.gdf.loc[self.gdf.inst_id.isin(self.split_ids[split])]


def load_pit_set(with_walls: bool = False) -> InstanceSet:
    """Pit floors (pit_inside). With with_walls=True also loads the wall ring
    (pit_outside) as class 'wall', sharing each pit's split via pit_id."""
    floor = gpd.read_file(ANN_GPKG, layer="pit_inside")
    floor = floor.rename(columns={"pit_id": "inst_id"})[["inst_id", "geometry"]]
    floor["cls"] = "floor"
    if with_walls:
        wall = gpd.read_file(ANN_GPKG, layer="pit_outside")
        wall = wall.rename(columns={"pit_id": "inst_id"})[["inst_id", "geometry"]]
        wall["cls"] = "wall"
        gdf = gpd.GeoDataFrame(pd.concat([floor, wall], ignore_index=True),
                               crs=floor.crs)
    else:
        gdf = floor
    manifest = pd.read_csv(PIT_MANIFEST)
    split_ids = {s: manifest.loc[manifest.split == s, "pit_id"].astype(int).tolist()
                 for s in ("train", "val", "test")}
    return InstanceSet("pit", gdf, split_ids)


def load_pad_set() -> InstanceSet:
    """Well pads. NOTE: the on-disk annotation layer + manifest are still named
    'plat' (legacy misnomer); only the API/outputs use 'pad'."""
    gdf = gpd.read_file(ANN_GPKG, layer="plat")
    gdf = gdf.rename(columns={"plat_id": "inst_id"})[["inst_id", "geometry"]]
    gdf["cls"] = "pad"
    manifest = pd.read_csv(PAD_MANIFEST)
    split_ids = {s: manifest.loc[manifest.split == s, "plat_id"].astype(int).tolist()
                 for s in ("train", "val", "test")}
    return InstanceSet("pad", gdf, split_ids)


# Back-compat alias (older callers).
load_plat_set = load_pad_set


# ---------------------------------------------------------------------------
# Patch sampling
# ---------------------------------------------------------------------------

def patch_window_around(cx: float, cy: float, transform: Affine, patch: int) -> Window:
    """Build a square patch window in pixel space centred on world coord (cx, cy)."""
    row, col = rowcol(transform, cx, cy)
    r0 = int(row) - patch // 2
    c0 = int(col) - patch // 2
    return Window(c0, r0, patch, patch)


def jittered_centers(centers: np.ndarray, jitter_m: float, rng: np.random.Generator,
                     n_per_center: int) -> np.ndarray:
    """Replicate centres n_per_center times with uniform jitter ±jitter_m in each axis."""
    if n_per_center <= 1:
        return centers + rng.uniform(-jitter_m, jitter_m, size=centers.shape)
    rep = np.repeat(centers, n_per_center, axis=0)
    return rep + rng.uniform(-jitter_m, jitter_m, size=rep.shape)


def read_rgb3_patch(rgb_path: Path, window: Window) -> np.ndarray:
    """Read a 3xHxW patch with edge-padding when window straddles tile bounds."""
    with rasterio.open(rgb_path) as r:
        return r.read(window=window, boundless=True, fill_value=0.0).astype(np.float32)


# ---------------------------------------------------------------------------
# 7-band UNet feature stack (the inputs the UNet trained on) — used by the
# Mask R-CNN path via first-conv widening. Same bands + normalisation as _dl.
# ---------------------------------------------------------------------------

FEATURES_PATH = DERIV_9T / "features_pit_9t_05.tif"
FEAT_STATS = DERIV_9T / "feature_stats.json"
FEATURE_CHANNELS = (
    "lrm_25", "lrm_5", "slope", "tpi_05",
    "openness_pos", "openness_neg", "roughness_11",
)
N_FEATURE_CHANNELS = len(FEATURE_CHANNELS)


def load_feature_stats() -> tuple[np.ndarray, np.ndarray]:
    """Per-channel (mean, std) for the 7-band stack, matching _dl.load_stats."""
    stats = json.loads(FEAT_STATS.read_text())
    mu = np.array([stats[c]["mean"] for c in FEATURE_CHANNELS], dtype=np.float32)
    sd = np.array([max(stats[c]["std"], 1e-6) for c in FEATURE_CHANNELS], dtype=np.float32)
    return mu, sd


def feature_parent_transform() -> Affine:
    with rasterio.open(FEATURES_PATH) as r:
        return r.transform


def feature_tile_size() -> tuple[int, int]:
    with rasterio.open(FEATURES_PATH) as r:
        return r.width, r.height


def read_feat_patch(window: Window, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """Read a (C,P,P) feature patch, z-score per channel; NaN/nodata -> 0
    (the channel mean in normalised space). Edge-padded via boundless read.

    Per-call file read (~160 ms). For training/full-tile inference use
    load_feature_array() + slice_feat_patch() instead (350x faster)."""
    with rasterio.open(FEATURES_PATH) as r:
        arr = r.read(window=window, boundless=True, fill_value=np.nan).astype(np.float32)
    arr = (arr - mu[:, None, None]) / sd[:, None, None]
    return np.nan_to_num(arr, nan=0.0)


# In-RAM normalised feature stack — loaded once, sliced per patch. The 9t stack
# is 7x9000x9000 float32 = 2.27 GB; reading it whole once (~23 s) then slicing
# (~0.5 ms/patch) is far cheaper than ~160 ms/patch file reads in the loader.
_FEAT_ARRAY: np.ndarray | None = None


def load_feature_array(mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """Load + normalise the full feature stack once, cache, and return (C,H,W)."""
    global _FEAT_ARRAY
    if _FEAT_ARRAY is None:
        with rasterio.open(FEATURES_PATH) as r:
            arr = r.read().astype(np.float32)
        arr = (arr - mu[:, None, None]) / sd[:, None, None]
        _FEAT_ARRAY = np.nan_to_num(arr, nan=0.0)
    return _FEAT_ARRAY


def slice_feat_patch(arr: np.ndarray, window: Window) -> np.ndarray:
    """Slice a (C,P,P) patch from a cached (C,H,W) array, zero-padding any part
    of the window outside the tile (matches read_feat_patch's boundless fill)."""
    C, H, W = arr.shape
    r0, c0 = int(window.row_off), int(window.col_off)
    pr, pc = int(window.height), int(window.width)
    out = np.zeros((C, pr, pc), dtype=np.float32)
    rr0, cc0 = max(r0, 0), max(c0, 0)
    rr1, cc1 = min(r0 + pr, H), min(c0 + pc, W)
    if rr1 > rr0 and cc1 > cc0:
        out[:, rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0] = arr[:, rr0:rr1, cc0:cc1]
    return out


def patch_transform(parent: Affine, window: Window) -> Affine:
    """World-coord transform of a sub-patch defined by `window` of `parent`."""
    return rasterio.windows.transform(window, parent)


# ---------------------------------------------------------------------------
# Polygon -> Mask R-CNN target
# ---------------------------------------------------------------------------

def polygons_intersecting(gdf: gpd.GeoDataFrame, window: Window, parent: Affine
                          ) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = rasterio.windows.bounds(window, parent)
    sub = gdf.iloc[gdf.sindex.intersection((minx, miny, maxx, maxy))]
    return sub[sub.intersects(box(minx, miny, maxx, maxy))]


def build_maskrcnn_target(polys: gpd.GeoDataFrame, window: Window, parent: Affine,
                          patch: int) -> dict:
    """Return a torchvision-detection target dict for one patch.

    boxes: (N, 4) xyxy in pixel coords
    labels: (N,) int64, per-polygon class via MASKRCNN_CLASS_IDS (default 1)
    masks: (N, patch, patch) uint8 binary per-instance
    """
    import torch
    tf = patch_transform(parent, window)
    minx, miny, maxx, maxy = rasterio.windows.bounds(window, parent)
    patch_box = box(minx, miny, maxx, maxy)
    has_cls = "cls" in polys.columns

    boxes, masks, labels = [], [], []
    for row in polys.itertuples():
        geom = row.geometry
        clipped = geom.intersection(patch_box)
        if clipped.is_empty or clipped.area < 1.0:
            continue
        m = rasterize([(clipped, 1)], out_shape=(patch, patch),
                      transform=tf, fill=0, dtype="uint8")
        if m.sum() < 4:
            continue
        ys, xs = np.where(m > 0)
        x0, y0, x1, y1 = float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        cls_name = getattr(row, "cls", None) if has_cls else None
        labels.append(MASKRCNN_CLASS_IDS.get(cls_name, 1))
        boxes.append([x0, y0, x1, y1])
        masks.append(m)

    if not boxes:
        return {
            "boxes": torch.zeros((0, 4), dtype=torch.float32),
            "labels": torch.zeros((0,), dtype=torch.int64),
            "masks": torch.zeros((0, patch, patch), dtype=torch.uint8),
        }
    return {
        "boxes": torch.tensor(boxes, dtype=torch.float32),
        "labels": torch.tensor(labels, dtype=torch.int64),
        "masks": torch.tensor(np.stack(masks), dtype=torch.uint8),
    }


# ---------------------------------------------------------------------------
# Polygon -> YOLO-seg label text
# ---------------------------------------------------------------------------

def build_yolo_seg_lines(polys: gpd.GeoDataFrame, window: Window, parent: Affine,
                         patch: int, class_id: int = 0) -> list[str]:
    """Return YOLO-seg label lines `<class> x1 y1 x2 y2 ...` with coords in [0, 1]."""
    tf = patch_transform(parent, window)
    minx, miny, maxx, maxy = rasterio.windows.bounds(window, parent)
    patch_box = box(minx, miny, maxx, maxy)
    has_cls = "cls" in polys.columns
    lines: list[str] = []
    for row in polys.itertuples():
        geom = row.geometry
        clipped = geom.intersection(patch_box)
        if clipped.is_empty or clipped.area < 1.0:
            continue
        cls_name = getattr(row, "cls", None) if has_cls else None
        cid = YOLO_CLASS_IDS.get(cls_name, class_id)
        # Multi-part: emit one line per ring with area > threshold.
        geoms = list(clipped.geoms) if clipped.geom_type.startswith("Multi") else [clipped]
        for g in geoms:
            if not isinstance(g, Polygon) or g.area < 1.0:
                continue
            xs, ys = g.exterior.coords.xy
            cols, rows = [], []
            for x, y in zip(xs, ys):
                r, c = rowcol(tf, x, y)
                cols.append(np.clip(c / patch, 0.0, 1.0))
                rows.append(np.clip(r / patch, 0.0, 1.0))
            if len(cols) < 3:
                continue
            coord_str = " ".join(f"{cx:.5f} {ry:.5f}" for cx, ry in zip(cols, rows))
            lines.append(f"{cid} {coord_str}")
    return lines


# ---------------------------------------------------------------------------
# Inference output assembly
# ---------------------------------------------------------------------------

def stitch_prob_raster(detections: Iterable[dict], ref_profile: dict, out_path: Path
                       ) -> np.ndarray:
    """Compose per-instance score masks into a max-score float32 raster.

    Each detection dict needs:
        bbox: (x0, y0, x1, y1) in tile pixel coords
        mask: (h, w) float32 in [0, 1] aligned with bbox
        score: float
    """
    H, W = ref_profile["height"], ref_profile["width"]
    prob = np.zeros((H, W), dtype=np.float32)
    for det in detections:
        x0, y0, x1, y1 = [int(round(v)) for v in det["bbox"]]
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, W), min(y1, H)
        if x1 <= x0 or y1 <= y0:
            continue
        h, w = y1 - y0, x1 - x0
        m = det["mask"][:h, :w]
        s = float(det["score"]) * m
        prob[y0:y1, x0:x1] = np.maximum(prob[y0:y1, x0:x1], s)

    write_tif(out_path, prob, transform=ref_profile["transform"],
              crs=ref_profile["crs"], dtype="float32", nodata=-1.0, bigtiff=True)
    print(f"  wrote {out_path.name}")
    return prob


def detections_to_gpkg(detections: Sequence[dict], ref_profile: dict, out_path: Path,
                       layer: str, score_thresh: float = 0.3) -> int:
    """Polygonise each detection mask (binarised at 0.5) and write to GeoPackage."""
    H, W = ref_profile["height"], ref_profile["width"]
    tf = ref_profile["transform"]
    rows: list[dict] = []
    for det in detections:
        if det["score"] < score_thresh:
            continue
        x0, y0, x1, y1 = [int(round(v)) for v in det["bbox"]]
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, W), min(y1, H)
        if x1 <= x0 or y1 <= y0:
            continue
        h, w = y1 - y0, x1 - x0
        bin_mask = (det["mask"][:h, :w] > 0.5).astype(np.uint8)
        if bin_mask.sum() < 4:
            continue
        # Build a transform offset for the sub-window so polygons land in world coords.
        sub_tf = rasterio.windows.transform(Window(x0, y0, w, h), tf)
        for geom, val in shapes(bin_mask, mask=bin_mask.astype(bool), transform=sub_tf):
            if val != 1:
                continue
            g = shape(geom)
            if g.area < 4.0:
                continue
            rec = {"score": float(det["score"]), "geometry": g}
            if "cls" in det:
                rec["cls"] = det["cls"]
            rows.append(rec)
    if not rows:
        print(f"  no detections above score {score_thresh}; skipping {out_path.name}")
        return 0
    gdf = gpd.GeoDataFrame(rows, crs=DST_CRS)
    gdf.to_file(out_path, layer=layer, driver="GPKG")
    print(f"  wrote {out_path.name} ({len(gdf)} instances)")
    return len(gdf)


# ---------------------------------------------------------------------------
# Evaluation against test instances
# ---------------------------------------------------------------------------

def per_instance_metrics(pred_gdf: gpd.GeoDataFrame, gt: InstanceSet,
                         split: str = "test") -> tuple[pd.DataFrame, dict]:
    """For each ground-truth instance in `split`, compute best-match IoU + recall."""
    gt_split = gt.for_split(split)
    if pred_gdf is None or pred_gdf.empty:
        rows = [{"inst_id": int(r.inst_id), "best_iou": 0.0, "recall": 0.0,
                 "matched": False} for r in gt_split.itertuples()]
        df = pd.DataFrame(rows)
    else:
        # Build sindex on predictions once.
        sidx = pred_gdf.sindex
        rows = []
        for r in gt_split.itertuples():
            g = r.geometry
            cand_ix = list(sidx.intersection(g.bounds))
            best_iou = 0.0
            best_score = 0.0
            for ix in cand_ix:
                p = pred_gdf.geometry.iloc[ix]
                inter = g.intersection(p).area
                if inter <= 0:
                    continue
                union = g.union(p).area
                iou = inter / union if union > 0 else 0.0
                if iou > best_iou:
                    best_iou = iou
                    best_score = float(pred_gdf.iloc[ix].get("score", 0.0))
            rows.append({"inst_id": int(r.inst_id), "best_iou": float(best_iou),
                         "best_pred_score": best_score,
                         "matched": best_iou >= 0.1})
        df = pd.DataFrame(rows)

    metrics = {
        "n_test_instances": int(len(df)),
        "recall_at_iou_0.1": float((df.best_iou >= 0.1).mean()) if len(df) else 0.0,
        "recall_at_iou_0.3": float((df.best_iou >= 0.3).mean()) if len(df) else 0.0,
        "recall_at_iou_0.5": float((df.best_iou >= 0.5).mean()) if len(df) else 0.0,
        "mean_best_iou": float(df.best_iou.mean()) if len(df) else 0.0,
        "median_best_iou": float(df.best_iou.median()) if len(df) else 0.0,
    }
    return df, metrics


# ---------------------------------------------------------------------------
# YOLO-seg dataset export + inference
# ---------------------------------------------------------------------------

def export_yolo_dataset(inst: "InstanceSet", rgb_path: Path, out_root: Path,
                        patch: int, jitter_m: float, patches_per_inst: int,
                        class_name, seed: int = 0) -> Path:
    """Materialise patches as PNGs + YOLO-seg .txt labels and a data.yaml.

    class_name: str (single class) or list[str] (multi-class, index = class id;
    must match YOLO_CLASS_IDS ordering, e.g. ['floor', 'wall']).

    Returns the data.yaml path (ready to feed to YOLO.train(data=...)).
    """
    from PIL import Image
    out_root.mkdir(parents=True, exist_ok=True)
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (out_root / sub).mkdir(parents=True, exist_ok=True)

    with rasterio.open(rgb_path) as r:
        parent_tf = r.transform

    rng = np.random.default_rng(seed)
    for split, subdir in (("train", "train"), ("val", "val")):
        gdf_split = inst.for_split(split)
        centers = np.array([[g.centroid.x, g.centroid.y] for g in gdf_split.geometry])
        if split == "train":
            centers = jittered_centers(centers, jitter_m, rng, patches_per_inst)
        for i, (cx, cy) in enumerate(centers):
            win = patch_window_around(float(cx), float(cy), parent_tf, patch)
            rgb = read_rgb3_patch(rgb_path, win)            # (3, P, P) float32
            img8 = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
            img8 = np.transpose(img8, (1, 2, 0))            # (P, P, 3)
            stem = f"{split}_{i:04d}"
            Image.fromarray(img8).save(out_root / "images" / subdir / f"{stem}.png")
            polys = polygons_intersecting(inst.gdf, win, parent_tf)
            lines = build_yolo_seg_lines(polys, win, parent_tf, patch, class_id=0)
            (out_root / "labels" / subdir / f"{stem}.txt").write_text("\n".join(lines))

    names = [class_name] if isinstance(class_name, str) else list(class_name)
    names_block = "".join(f"  {i}: {nm}\n" for i, nm in enumerate(names))
    data_yaml = out_root / "data.yaml"
    data_yaml.write_text(
        f"path: {out_root.resolve().as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n{names_block}"
    )
    return data_yaml


def yolo_sliding_inference(model, rgb_path: Path, patch: int, overlap: int,
                           score_thresh: float = 0.3,
                           imgsz: int = 640) -> list[dict]:
    """Slide window over tile, run YOLO seg, return detections in tile pixel coords.

    Uses ultralytics' native `masks.xy` (polygons in original image coords) to
    avoid letterbox/resize coordinate bugs that surface when mixing
    `masks.data` (model-input resolution) with `boxes.xyxy` (original-image
    resolution). Each detection stores a rasterised binary mask cropped to its
    bbox.
    """
    from rasterio.features import rasterize as _rasterize
    from shapely.geometry import Polygon as _Polygon
    with rasterio.open(rgb_path) as r:
        W, H = r.width, r.height
    step = patch - overlap
    xs = list(range(0, max(W - patch, 0) + 1, step))
    ys = list(range(0, max(H - patch, 0) + 1, step))
    if xs and xs[-1] != W - patch:
        xs.append(W - patch)
    if ys and ys[-1] != H - patch:
        ys.append(H - patch)
    if not xs: xs = [0]
    if not ys: ys = [0]

    detections: list[dict] = []
    n_windows = len(xs) * len(ys)
    print(f"YOLO sliding inference: {n_windows} windows (patch={patch}, imgsz={imgsz})")
    i = 0
    for y in ys:
        for x in xs:
            i += 1
            if i % 50 == 0:
                print(f"  window {i}/{n_windows}")
            win = Window(x, y, patch, patch)
            rgb = read_rgb3_patch(rgb_path, win)
            img8 = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
            img8 = np.transpose(img8, (1, 2, 0))
            # CRITICAL: training PNGs were written RGB by PIL and re-read BGR
            # by ultralytics' cv2-based dataloader, so the model learned a
            # BGR channel ordering. Match that here by flipping RGB->BGR.
            img8 = img8[..., ::-1]
            r_out = model.predict(img8, imgsz=imgsz, conf=score_thresh, verbose=False)[0]
            if r_out.masks is None or r_out.boxes is None or len(r_out.boxes) == 0:
                continue
            scores = r_out.boxes.conf.cpu().numpy()
            cls_ids = r_out.boxes.cls.cpu().numpy().astype(int)
            # masks.xy is a list of (N_points, 2) polygon arrays already in
            # original-image pixel coords (here: 256x256 / patch x patch).
            polys_xy = r_out.masks.xy
            for s, poly_xy, cid in zip(scores, polys_xy, cls_ids):
                if poly_xy is None or len(poly_xy) < 3:
                    continue
                # Build a shapely polygon in patch-local pixel coords; rasterise
                # it onto a (patch, patch) grid using an identity transform; then
                # crop to its bounding box. This avoids any mask-resize bugs.
                try:
                    py = _Polygon(poly_xy)
                    if not py.is_valid:
                        py = py.buffer(0)
                    if py.is_empty or py.area < 2.0:
                        continue
                except Exception:
                    continue
                lx0, ly0, lx1, ly1 = py.bounds
                lx0 = max(int(np.floor(lx0)), 0)
                ly0 = max(int(np.floor(ly0)), 0)
                lx1 = min(int(np.ceil(lx1)), patch)
                ly1 = min(int(np.ceil(ly1)), patch)
                if lx1 <= lx0 or ly1 <= ly0:
                    continue
                h, w = ly1 - ly0, lx1 - lx0
                # Rasterise polygon onto a (h, w) grid using a translation transform.
                from rasterio.transform import Affine as _Affine
                local_tf = _Affine(1, 0, lx0, 0, 1, ly0)
                m = _rasterize([(py, 1.0)], out_shape=(h, w),
                               transform=local_tf, fill=0.0, dtype="float32")
                detections.append({
                    "score": float(s),
                    "cls_id": int(cid),
                    "bbox": (float(x + lx0), float(y + ly0),
                             float(x + lx1), float(y + ly1)),
                    "mask": m,
                })
    return detections


def reference_profile() -> dict:
    """Profile of the 9t reference grid (matches all derivatives)."""
    with rasterio.open(DEM_REF) as r:
        return r.profile.copy()


def save_metrics(metrics: dict, out_dir: Path, name: str = "test_metrics.json") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_text(json.dumps(metrics, indent=2))
    print(f"  wrote {name}: {metrics}")
