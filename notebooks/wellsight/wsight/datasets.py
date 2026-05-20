"""Datasets for pit / plat / road segmentation tasks.

All three follow the same shape:
- Read a feature raster and a label raster (same grid).
- Maintain a list of "positive" centroids (from the task's manifest CSV).
- Per __getitem__, decide whether to sample around a positive or sample a
  random background patch inside the split's spatial blocks.
- Read a PATCH x PATCH window, z-score normalize via train-block stats,
  optionally augment (4-way rotation + horizontal flip).

Differences captured in the BG_PER_POS, jitter range, and __len__ formulas.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
import torch
from torch.utils.data import Dataset


class SegmentationTiles(Dataset):
    """Generic pit/plat/road segmentation sampler.

    Parameters
    ----------
    feature_path, label_path : Path
        Float32 feature TIF (N channels) and uint8 label TIF (same grid).
    centroids : ndarray of shape (N, 2)
        World-coordinate (x, y) centroids of positives in this split.
    split_block_bounds : ndarray of shape (B, 4)
        Bounds of the spatial blocks belonging to this split (minx, miny,
        maxx, maxy).
    transform : rasterio.Affine
        Affine of the feature raster — used to convert world coords to row/col.
    mu, sd : ndarray of shape (C,)
        Per-channel mean and std for z-score normalization. Computed on
        TRAIN-block pixels only.
    patch : int
        Window size in pixels (must be square).
    jitter_m : float
        Half-range of uniform jitter (in meters) applied to positive centroids.
    bg_per_pos : int
        How many random background patches to draw per positive per epoch.
    augment : bool
        Enable rotations + flips. Set False for val.
    """

    def __init__(self, feature_path: Path, label_path: Path,
                 centroids, split_block_bounds, transform, mu, sd,
                 patch: int = 256, jitter_m: float = 30.0,
                 bg_per_pos: int = 1, augment: bool = True):
        self.feature_path = Path(feature_path)
        self.label_path = Path(label_path)
        self.centroids = np.asarray(centroids, dtype=np.float64)
        self.block_bounds = np.asarray(split_block_bounds, dtype=np.float64)
        self.transform = transform
        self.mu = mu.astype(np.float32)
        self.sd = sd.astype(np.float32)
        self.patch = int(patch)
        self.jitter_m = float(jitter_m)
        self.bg_per_pos = int(bg_per_pos)
        self.augment = bool(augment)
        self._feat = None
        self._lbl = None

    def _open(self):
        if self._feat is None:
            self._feat = rasterio.open(self.feature_path)
            self._lbl = rasterio.open(self.label_path)

    def __len__(self):
        return max(len(self.centroids), 1) * (1 + self.bg_per_pos)

    def _world_to_rowcol(self, x, y):
        tf = self.transform
        col = (x - tf.c) / tf.a
        row = (y - tf.f) / tf.e
        return row, col

    def __getitem__(self, idx):
        self._open()
        rng = np.random.default_rng()
        is_pos = idx < len(self.centroids) and len(self.centroids) > 0
        if is_pos:
            cx, cy = self.centroids[idx]
            cx += rng.uniform(-self.jitter_m, self.jitter_m)
            cy += rng.uniform(-self.jitter_m, self.jitter_m)
        else:
            bb = self.block_bounds[rng.integers(0, len(self.block_bounds))]
            cx = rng.uniform(bb[0], bb[2])
            cy = rng.uniform(bb[1], bb[3])
        row, col = self._world_to_rowcol(cx, cy)
        r0 = int(round(row)) - self.patch // 2
        c0 = int(round(col)) - self.patch // 2
        H, W = self._feat.height, self._feat.width
        r0 = int(np.clip(r0, 0, H - self.patch))
        c0 = int(np.clip(c0, 0, W - self.patch))
        win = Window(c0, r0, self.patch, self.patch)
        feat = self._feat.read(window=win).astype(np.float32)
        lbl = self._lbl.read(1, window=win).astype(np.int64)
        feat = np.where(np.isfinite(feat), feat, 0.0)
        feat = (feat - self.mu[:, None, None]) / self.sd[:, None, None]
        if self.augment:
            k = int(rng.integers(0, 4))
            if k:
                feat = np.rot90(feat, k, axes=(1, 2)).copy()
                lbl = np.rot90(lbl, k).copy()
            if rng.random() < 0.5:
                feat = feat[:, :, ::-1].copy()
                lbl = lbl[:, ::-1].copy()
        return torch.from_numpy(feat), torch.from_numpy(lbl)


class RoadTiles(Dataset):
    """Three-mode sampler used by all road U-Net iterations.

    Modes (cycled by idx % 3):
      0  road-centered  (positive)
      1  not_road-centered  (hard negative)
      2  random background in this split's blocks

    The `not_roads` lines are the *key* signal — they're hand-drawn linear
    features that look like roads but aren't. Used at LABEL = 0 during
    training so the encoder learns to discriminate cut-and-fill roads
    from natural lineaments.
    """

    def __init__(self, feature_path: Path, label_path: Path,
                 roads_xy, not_roads_xy, split_block_bounds, transform, mu, sd,
                 patch: int = 256, jitter_m: float = 30.0, augment: bool = True):
        self.feature_path = Path(feature_path)
        self.label_path = Path(label_path)
        self.roads = np.asarray(roads_xy, dtype=np.float64)
        self.not_roads = np.asarray(not_roads_xy, dtype=np.float64)
        self.block_bounds = np.asarray(split_block_bounds, dtype=np.float64)
        self.transform = transform
        self.mu = mu.astype(np.float32)
        self.sd = sd.astype(np.float32)
        self.patch = int(patch)
        self.jitter_m = float(jitter_m)
        self.augment = bool(augment)
        self._feat = None
        self._lbl = None

    def _open(self):
        if self._feat is None:
            self._feat = rasterio.open(self.feature_path)
            self._lbl = rasterio.open(self.label_path)

    def __len__(self):
        return max(len(self.roads), 1) * 3

    def _world_to_rowcol(self, x, y):
        tf = self.transform
        col = (x - tf.c) / tf.a
        row = (y - tf.f) / tf.e
        return row, col

    def __getitem__(self, idx):
        self._open()
        rng = np.random.default_rng()
        mode = idx % 3
        if mode == 0 and len(self.roads):
            cx, cy = self.roads[rng.integers(0, len(self.roads))]
            cx += rng.uniform(-self.jitter_m, self.jitter_m)
            cy += rng.uniform(-self.jitter_m, self.jitter_m)
        elif mode == 1 and len(self.not_roads):
            cx, cy = self.not_roads[rng.integers(0, len(self.not_roads))]
            cx += rng.uniform(-self.jitter_m, self.jitter_m)
            cy += rng.uniform(-self.jitter_m, self.jitter_m)
        else:
            bb = self.block_bounds[rng.integers(0, len(self.block_bounds))]
            cx = rng.uniform(bb[0], bb[2])
            cy = rng.uniform(bb[1], bb[3])
        row, col = self._world_to_rowcol(cx, cy)
        r0 = int(round(row)) - self.patch // 2
        c0 = int(round(col)) - self.patch // 2
        H, W = self._feat.height, self._feat.width
        r0 = int(np.clip(r0, 0, H - self.patch))
        c0 = int(np.clip(c0, 0, W - self.patch))
        win = Window(c0, r0, self.patch, self.patch)
        feat = self._feat.read(window=win).astype(np.float32)
        lbl = self._lbl.read(1, window=win).astype(np.int64)
        feat = np.where(np.isfinite(feat), feat, 0.0)
        feat = (feat - self.mu[:, None, None]) / self.sd[:, None, None]
        if self.augment:
            k = int(rng.integers(0, 4))
            if k:
                feat = np.rot90(feat, k, axes=(1, 2)).copy()
                lbl = np.rot90(lbl, k).copy()
            if rng.random() < 0.5:
                feat = feat[:, :, ::-1].copy()
                lbl = lbl[:, ::-1].copy()
        return torch.from_numpy(feat), torch.from_numpy(lbl)


class RoadPatchDataset(Dataset):
    """Per-point dataset for the binary road-vs-not-road CNN classifier.

    Each row is a sample point along a road or not_road line (every 4 m).
    Returns a (C, P, P) feature crop centered on that point and a binary
    label (1=road, 0=not_road).
    """

    def __init__(self, df, feature_path: Path, mu, sd,
                 patch: int = 64, augment: bool = True):
        self.df = df.reset_index(drop=True)
        self.feature_path = Path(feature_path)
        self.mu = mu.astype(np.float32)
        self.sd = sd.astype(np.float32)
        self.patch = int(patch)
        self.augment = bool(augment)
        self._feat = None
        with rasterio.open(self.feature_path) as r:
            self._tf = r.transform
            self.H, self.W = r.height, r.width

    def _open(self):
        if self._feat is None:
            self._feat = rasterio.open(self.feature_path)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        self._open()
        row = self.df.iloc[idx]
        col = (row.x - self._tf.c) / self._tf.a
        rrow = (row.y - self._tf.f) / self._tf.e
        r0 = int(round(rrow)) - self.patch // 2
        c0 = int(round(col)) - self.patch // 2
        r0 = int(np.clip(r0, 0, self.H - self.patch))
        c0 = int(np.clip(c0, 0, self.W - self.patch))
        feat = self._feat.read(window=Window(c0, r0, self.patch, self.patch)).astype(np.float32)
        feat = np.where(np.isfinite(feat), feat, 0.0)
        feat = (feat - self.mu[:, None, None]) / self.sd[:, None, None]
        if self.augment:
            rng = np.random.default_rng()
            k = int(rng.integers(0, 4))
            if k:
                feat = np.rot90(feat, k, axes=(1, 2)).copy()
            if rng.random() < 0.5:
                feat = feat[:, :, ::-1].copy()
            if rng.random() < 0.5:
                feat = feat[:, ::-1, :].copy()
        return torch.from_numpy(feat), float(row.label)
