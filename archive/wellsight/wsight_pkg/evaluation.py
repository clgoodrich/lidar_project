"""Per-task evaluation helpers — produces the headline test-set metric tables."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds
import geopandas as gpd


def _load_test_mask(labels_path: Path, blocks_path: Path):
    with rasterio.open(labels_path) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(blocks_path, layer="blocks")
    tbm = rasterize(
        [(g, 1) for g in blocks[blocks.split == "test"].geometry],
        out_shape=(H, W), transform=tf, fill=0, dtype="uint8",
    ).astype(bool)
    return labels, tbm, tf, H, W


def pit_test_eval(argmax: np.ndarray, *,
                  labels_path: Path, blocks_path: Path,
                  manifest_path: Path, annotations_gpkg: Path,
                  out_dir: Optional[Path] = None,
                  pad_m: float = 6.0) -> dict:
    """Per-pit evaluation against the 20 held-out test pits.

    Returns a dict with pixel-class IoUs and per-pit aggregate metrics.
    If `out_dir` is given, also writes test_metrics.json + test_per_pit.csv.
    """
    labels, tbm, tf, H, W = _load_test_mask(labels_path, blocks_path)
    pix_iou = {}
    for cls, name in [(0, "bg"), (1, "floor"), (2, "wall")]:
        p = (argmax == cls) & tbm; t = (labels == cls) & tbm
        inter = int((p & t).sum()); union = int((p | t).sum())
        pix_iou[name] = inter / union if union else None

    man = pd.read_csv(manifest_path)
    tp = man[man.split == "test"]
    pit_in = gpd.read_file(annotations_gpkg, layer="pit_inside")
    rows = []
    for _, row in tp.iterrows():
        pid = int(row.pit_id)
        g = pit_in[pit_in.pit_id == pid].geometry.iloc[0]
        minx, miny, maxx, maxy = g.bounds
        win = from_bounds(minx - pad_m, miny - pad_m, maxx + pad_m, maxy + pad_m, tf)
        r0 = max(int(win.row_off), 0); c0 = max(int(win.col_off), 0)
        wh = min(int(win.height), H - r0); ww = min(int(win.width), W - c0)
        if wh <= 0 or ww <= 0:
            continue
        sub_lbl = labels[r0:r0+wh, c0:c0+ww]
        sub_pred = argmax[r0:r0+wh, c0:c0+ww]
        floor_t = sub_lbl == 1; wall_t = sub_lbl == 2
        pit_t = floor_t | wall_t
        pit_p = (sub_pred == 1) | (sub_pred == 2)
        recall_floor = float((floor_t & (sub_pred == 1)).sum() / max(floor_t.sum(), 1))
        recall_wall = float((wall_t & (sub_pred == 2)).sum() / max(wall_t.sum(), 1))
        recall_any = float((pit_t & pit_p).sum() / max(pit_t.sum(), 1))
        inter = int((pit_t & pit_p).sum()); union = int((pit_t | pit_p).sum())
        loc_iou = inter / union if union else None
        rows.append({"pit_id": pid, "recall_floor": recall_floor,
                     "recall_wall": recall_wall, "recall_any_pit": recall_any,
                     "pit_iou_local": loc_iou})
    df = pd.DataFrame(rows)
    metrics = {
        "pixel_iou": pix_iou,
        "n_test_pits": len(df),
        "n_detected_any": int((df.recall_any_pit > 0.1).sum()),
        "n_solid_iou_gt_0.3": int((df.pit_iou_local.fillna(0) > 0.3).sum()),
        "mean_pit_iou_local": float(df.pit_iou_local.mean()),
        "median_pit_iou_local": float(df.pit_iou_local.median()),
        "mean_recall_any_pit": float(df.recall_any_pit.mean()),
    }
    if out_dir is not None:
        out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
        df.to_csv(out_dir / "test_per_pit.csv", index=False)
    return metrics


def plat_test_eval(argmax: np.ndarray, *,
                   labels_path: Path, blocks_path: Path,
                   manifest_path: Path, annotations_gpkg: Path,
                   out_dir: Optional[Path] = None,
                   pad_m: float = 15.0) -> dict:
    """Per-plat evaluation against the 9 held-out test plats."""
    labels, tbm, tf, H, W = _load_test_mask(labels_path, blocks_path)
    p = argmax == 1; t = labels == 1
    inter = int((p & t & tbm).sum()); union = int(((p | t) & tbm).sum())
    pix_iou = inter / union if union else None

    man = pd.read_csv(manifest_path)
    tp = man[man.split == "test"]
    plat = gpd.read_file(annotations_gpkg, layer="plat")
    rows = []
    for _, row in tp.iterrows():
        pid = int(row.plat_id)
        g = plat[plat.plat_id == pid].geometry.iloc[0]
        minx, miny, maxx, maxy = g.bounds
        win = from_bounds(minx - pad_m, miny - pad_m, maxx + pad_m, maxy + pad_m, tf)
        r0 = max(int(win.row_off), 0); c0 = max(int(win.col_off), 0)
        wh = min(int(win.height), H - r0); ww = min(int(win.width), W - c0)
        if wh <= 0 or ww <= 0:
            continue
        sl = labels[r0:r0+wh, c0:c0+ww] == 1
        sp = argmax[r0:r0+wh, c0:c0+ww] == 1
        recall = float((sl & sp).sum() / max(sl.sum(), 1))
        inter2 = int((sl & sp).sum()); union2 = int((sl | sp).sum())
        loc_iou = inter2 / union2 if union2 else None
        rows.append({"plat_id": pid, "recall": recall, "local_iou": loc_iou})
    df = pd.DataFrame(rows)
    metrics = {
        "pixel_iou_test": pix_iou, "n_test_plats": len(df),
        "n_detected_any_10pct": int((df.recall > 0.1).sum()),
        "n_iou_gt_0.3": int((df.local_iou.fillna(0) > 0.3).sum()),
        "mean_local_iou": float(df.local_iou.mean()),
        "median_local_iou": float(df.local_iou.median()),
        "mean_recall": float(df.recall.mean()),
    }
    if out_dir is not None:
        out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
        df.to_csv(out_dir / "test_per_plat.csv", index=False)
    return metrics


def road_pixel_eval(argmax: np.ndarray, *,
                    labels_path: Path, blocks_path: Path) -> Optional[float]:
    """Just the binary road pixel-IoU within the test blocks."""
    labels, tbm, _, _, _ = _load_test_mask(labels_path, blocks_path)
    p = argmax == 1; t = labels == 1
    inter = int((p & t & tbm).sum()); union = int(((p | t) & tbm).sum())
    return (inter / union) if union else None


def road_line_ap(prob_band: np.ndarray, *,
                 manifest_path: Path, annotations_gpkg: Path,
                 reference_path: Path) -> Optional[float]:
    """Average precision over test lines, ranking by mean prob sampled along each line."""
    with rasterio.open(reference_path) as r:
        tf = r.transform; H, W = r.height, r.width

    man = pd.read_csv(manifest_path)
    roads_t = gpd.read_file(annotations_gpkg, layer="roads")
    not_roads_t = gpd.read_file(annotations_gpkg, layer="not_roads")

    def line_prob(line_g):
        L = line_g.length; n = max(2, int(L)); ps = []
        for i in range(n + 1):
            pt = line_g.interpolate(min(i, L))
            col = (pt.x - tf.c) / tf.a
            row = (pt.y - tf.f) / tf.e
            r0, c0 = int(round(row)), int(round(col))
            if 0 <= r0 < H and 0 <= c0 < W:
                ps.append(prob_band[r0, c0])
        return float(np.mean(ps)) if ps else 0.0

    rows = []
    for kind, gdf in [("road", roads_t), ("not_road", not_roads_t)]:
        for i, row in gdf.reset_index(drop=True).iterrows():
            lid = f"{kind}_{i}"
            mrow = man[man.line_id == lid]
            if not len(mrow):
                continue
            if str(mrow.iloc[0]["split"]) != "test":
                continue
            rows.append({"line_id": lid, "kind": kind, "mean_prob": line_prob(row.geometry)})
    line_df = pd.DataFrame(rows)
    if not len(line_df) or line_df.kind.nunique() < 2:
        return None
    y = (line_df.kind == "road").astype(int).values
    p_vals = line_df.mean_prob.values
    order = np.argsort(-p_vals); y_sorted = y[order]
    tp = np.cumsum(y_sorted); fp = np.cumsum(1 - y_sorted)
    prec = tp / np.maximum(tp + fp, 1); rec = tp / max(y.sum(), 1)
    return float(np.trapz(prec, rec))
