"""P1 core. Deterministic CV block splits, list hashing and window-leakage geometry for tile 9t.

Purpose
    One module that every P1 stage script imports. It holds no data paths of its own except through
    the historical trainers' constants, which it reads lazily so the trainers stay the source of truth.
    Nothing here edits the trainers.

What is here
    trainer(task)                     the historical trainer module (_pit_unet_cv5 / _pad_unet_cv5), lazily
    load_manifest(task)               manifest DataFrame with canonical id columns
    held_out_folds(man, k, seed, fn)  historical held-out assignment (assign_folds, NaN dropped by groupby)
    inner_split(man, held, k, ...)    inner val / train per fold, mode "historical" (NaN kept, the bug) or "fixed"
    make_splits(...)                  {fold: {"held_out", "inner_val", "train"}} for every fold
    canonical(obj), lists_hash(obj)   canonical JSON and its SHA-256 (the identity of a split)
    window_boxes(r0, c0, patch, tf)   pixel windows as world rectangles
    count_window_leaks(boxes, polys)  how many windows overlap a forbidden polygon with positive area
    receptive_field_px(model, ...)    receptive field of a model, measured from gradient support

Inputs (through the trainers)
    data/9t/derived/05/pit_dataset_manifest.csv, pad_dataset_manifest.csv, pit_blocks_9t.gpkg, pad_blocks_9t.gpkg

Outputs
    None. Library only.

Run
    Not a script. `python -m pytest -q expansions/0_prerequisites/p1_splits_manifests/src/test_p1.py -p no:cacheprovider`
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

S3_TRAIN = ek.REPO / "notebooks" / "wellsight_v2" / "s3_train"
TASKS = ("pit", "pad")
TRAINER = {"pit": "_pit_unet_cv5", "pad": "_pad_unet_cv5"}
ID_COL = {"pit": "pit_inside_id", "pad": "pad_id"}
COUNT_COL = {"pit": "n_pits", "pad": "n_pads"}
ROLES = ("held_out", "inner_val", "train")
BUFFER_ROLE = "buffer"          # train blocks removed by the P1 S4 buffer (block mode). Never trained or scored.


# ----------------------------------------------------------------------------- trainer access
def trainer(task: str):
    """Import the historical trainer module read-only. Importing it trains nothing."""
    if str(S3_TRAIN) not in sys.path:
        sys.path.insert(0, str(S3_TRAIN))
    return importlib.import_module(TRAINER[task])


def load_manifest(task: str, path: Path | None = None) -> pd.DataFrame:
    from _common import normalize_ids
    p = Path(path) if path else trainer(task).MANIFEST
    if not p.exists():
        raise FileNotFoundError(f"manifest for {task} not found at {p}")
    return normalize_ids(pd.read_csv(p))


def task_params(task: str) -> dict:
    """Seed, inner fraction, patch and jitter exactly as the trainer defines them."""
    t = trainer(task)
    return dict(seed=int(t.CV_SEED), inner_val_frac=float(t.INNER_VAL_FRAC), patch=int(t.PATCH),
                jitter_m=float(t.JITTER_M), assign_folds=t.assign_folds,
                manifest=Path(t.MANIFEST), blocks=Path(t.BLOCKS))


# ----------------------------------------------------------------------------- splits
def held_out_folds(man: pd.DataFrame, k: int, seed: int, assign_folds, count_col: str = "n") -> dict[int, list[int]]:
    """Historical held-out lists. groupby drops NaN block ids, exactly as the trainers do."""
    n_per = man.groupby("block_id").size().rename(count_col).reset_index()
    fold_of = assign_folds(n_per[["block_id", count_col]], k, seed)
    out = {f: [] for f in range(k)}
    for b, f in fold_of.items():
        out[int(f)].append(int(b))
    return {f: sorted(v) for f, v in out.items()}


def inner_split(man: pd.DataFrame, held: list[int], fold: int, seed: int, frac: float,
                mode: str = "fixed") -> tuple[list, list]:
    """Inner validation and training blocks for one fold.

    historical  rest = sorted(set(man.block_id.unique()) - set(held)). NaN stays in the set and lands at a
                position that depends on the process (hash(nan) is id-based on Python >= 3.10).
    fixed       NaN dropped and ids cast to int before the sort (P1 S2 step 4).
    The draw is np.random.default_rng(seed + 1000 * fold).permutation(rest), first round(frac * n) are val.
    """
    if mode == "historical":
        rest = sorted(set(man.block_id.unique()) - set(held))
    elif mode == "fixed":
        rest = sorted(int(b) for b in set(man.block_id.dropna().astype(int).unique()) - set(int(h) for h in held))
    else:
        raise ValueError(mode)
    rng = np.random.default_rng(ek.child_seed(seed, fold))
    shuf = list(rng.permutation(np.array(rest, dtype=float if mode == "historical" else np.int64)))
    nv = max(1, int(round(frac * len(shuf))))
    val, tr = sorted(shuf[:nv]), sorted(shuf[nv:])
    if mode == "fixed":
        return [int(b) for b in val], [int(b) for b in tr]
    # keep NaN visible as None so the historical lists can be hashed and compared
    def clean(v):
        return [None if (isinstance(b, float) and math.isnan(b)) else int(b) for b in v]
    return clean(val), clean(tr)


def make_splits(man: pd.DataFrame, k: int, seed: int, frac: float, assign_folds, mode: str = "fixed") -> dict:
    held = held_out_folds(man, k, seed, assign_folds)
    out = {}
    for f in range(k):
        val, tr = inner_split(man, held[f], f, seed, frac, mode)
        out[f] = {"held_out": held[f], "inner_val": val, "train": tr}
    return out


def check_roles(splits: dict, expected_blocks: set[int] | None = None) -> list[str]:
    """QC. No NaN, no block in two roles within a fold, union equals the expected block set."""
    problems = []
    for f, roles in splits.items():
        seen: dict[int, str] = {}
        for role in ROLES + ((BUFFER_ROLE,) if BUFFER_ROLE in roles else ()):
            for b in roles[role]:
                if b is None or (isinstance(b, float) and math.isnan(b)):
                    problems.append(f"fold {f}: NaN block in {role}")
                    continue
                if b in seen:
                    problems.append(f"fold {f}: block {b} in {seen[b]} and {role}")
                seen[b] = role
        if expected_blocks is not None and set(seen) != set(expected_blocks):
            problems.append(f"fold {f}: union of roles {len(seen)} blocks != expected {len(expected_blocks)}")
    held_all = [b for r in splits.values() for b in r["held_out"]]
    if len(held_all) != len(set(held_all)):
        problems.append("a block is held out in more than one fold")
    return problems


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def lists_hash(obj) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def fold_hashes(splits: dict) -> dict:
    return {str(f): {role: lists_hash(r[role]) for role in ROLES + (BUFFER_ROLE,) if role in r}
            for f, r in splits.items()}


def near_held_out(splits: dict, blocks_gdf, buffer_m: float) -> dict[int, list[int]]:
    """Per fold, the train blocks that overlap the held-out ground dilated by buffer_m (positive area).

    Same test as the P2 block buffer (mitre join, overlap area above 1e-6 m2). Raises if a listed block has
    no polygon, so a missing geometry can never pass as 'far away'."""
    g = blocks_gdf.assign(block_id=blocks_gdf.block_id.astype(int)).set_index("block_id").geometry
    out = {}
    for f, roles in splits.items():
        missing = sorted((set(roles["held_out"]) | set(roles["train"])) - set(g.index))
        if missing:
            raise AssertionError(f"fold {f}: blocks without a polygon {missing[:10]}")
        held = g.loc[roles["held_out"]].union_all().buffer(buffer_m, join_style="mitre")
        out[f] = sorted(int(b) for b in roles["train"] if g.loc[b].intersection(held).area > 1e-6)
    return out


def apply_block_buffer(splits: dict, blocks_gdf, buffer_m: float) -> tuple[dict, dict[int, list[int]]]:
    """Block-mode buffer. Train blocks within buffer_m of held-out ground move to role 'buffer'.

    Deterministic (pure geometry, no draw). Held-out and inner-validation lists are unchanged.
    Returns (new splits, removed ids per fold)."""
    near = near_held_out(splits, blocks_gdf, buffer_m)
    out = {}
    for f, roles in splits.items():
        rm = set(near[f])
        out[f] = {**roles, "train": [b for b in roles["train"] if b not in rm], BUFFER_ROLE: sorted(rm)}
    return out, near


# ----------------------------------------------------------------------------- window geometry
def window_boxes(r0, c0, patch: int, transform):
    """Pixel windows (top-left row, col, square side) to shapely boxes in world coordinates."""
    import shapely
    r0, c0 = np.asarray(r0, float), np.asarray(c0, float)
    a, e, x0, y0 = transform.a, transform.e, transform.c, transform.f
    xmin, xmax = x0 + c0 * a, x0 + (c0 + patch) * a
    ya, yb = y0 + r0 * e, y0 + (r0 + patch) * e
    return shapely.box(xmin, np.minimum(ya, yb), xmax, np.maximum(ya, yb))


def count_window_leaks(boxes, polys, eps: float = 1e-6) -> tuple[int, np.ndarray]:
    """Windows that overlap any forbidden polygon with positive area. Shared edges do not count.

    Returns (count, boolean array per window).
    """
    import shapely
    from shapely.strtree import STRtree
    boxes = np.asarray(boxes)
    hit = np.zeros(len(boxes), bool)
    polys = list(polys)
    if not len(boxes) or not polys:
        return 0, hit
    shrunk = shapely.buffer(boxes, -eps, join_style="mitre")
    tree = STRtree(polys)
    idx = tree.query(shrunk, predicate="intersects")
    if idx.size:
        hit[np.unique(idx[0])] = True
    return int(hit.sum()), hit


# ----------------------------------------------------------------------------- receptive field
def receptive_field_px(model, in_ch: int, size: int = 512, seed: int = 0) -> dict:
    """Receptive field of the centre output pixel, measured as the support of its input gradient.

    Random input, eval mode, CPU. The support is the set of input pixels with a non-zero gradient.
    Returns the full width and the radius in pixels. Raises if the support touches the input border,
    which means `size` was too small to measure it.
    """
    import torch
    torch.manual_seed(seed)
    m = model.cpu().eval()
    x = torch.randn(1, in_ch, size, size, requires_grad=True)
    y = m(x)
    c = size // 2
    y[0, :, c, c].sum().backward()
    g = x.grad.abs().sum(1)[0].numpy() > 0
    rows, cols = np.where(g.any(1))[0], np.where(g.any(0))[0]
    if rows.min() == 0 or cols.min() == 0 or rows.max() == size - 1 or cols.max() == size - 1:
        raise RuntimeError(f"receptive field reaches the {size} px border. Use a larger size.")
    width = int(max(rows.max() - rows.min() + 1, cols.max() - cols.min() + 1))
    radius = int(max(c - rows.min(), rows.max() - c, c - cols.min(), cols.max() - c))
    return {"width_px": width, "radius_px": radius, "measured_on_px": size}
