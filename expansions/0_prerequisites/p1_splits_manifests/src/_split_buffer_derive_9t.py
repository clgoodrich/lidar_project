"""P1 S4. Derive the spatial buffer per task from the model receptive field and an empirical residual semivariogram.

Purpose
    1. Residual. r = p - y per pixel for the task's positive class. y = 1 where the label raster holds that
       class. Both are read on a 5 m grid (decimated nearest read) so the whole tile fits in memory.
       pit  p from the out-of-fold floor mosaic (uint8 DN / 254, 255 nodata), floor class 1.
       pad  p from the historical per-fold rasters `pad_prob_cvfold{k}_9t_05.tif`, each taken inside its
            own held-out blocks (exporter lists), which makes an out-of-fold field. Pad class 1.
    2. Semivariogram. Exact masked estimator over every pair on the 5 m grid, computed with FFT
       cross-correlations, binned in 25 m lags to 2,000 m. Sill is the mean semivariance over the last
       quarter of lags. Sigma is the standard deviation of those tail lags (the sill's own wobble).
    3. Range rule (review P1-04). The point range is the first lag at 95% of the sill. On a flat
       semivariogram that lag is decided by noise. So the buffer uses `range_m_upper_bound`, the first
       lag whose semivariance reaches 95% of the sill plus `noise_k` (2) sigma. If the first lag already
       reaches it, the range lies below the first lag. Then `range_m_upper_bound` is the first lag and
       `range_below_first_lag` is true. `first_lag_within_noise` flags a first lag within noise_k sigma of
       the 95% mark. A wobble smaller than the noise band therefore cannot move the buffer.
    4. Receptive field. Measured from the input-gradient support of the `UNet` in `_dl.py` (base 32, 7
       channels, n_classes of the task), in pixels and metres at the raster resolution.
    5. Buffer. framework formula `buffer = receptive_field_radius + range_m_upper_bound`, rounded up to
       25 m. The patch-support variant `patch_half + range_m_upper_bound` is reported beside it.
    6. Separation. Per fold, minimum distance from held-out pit features to any other-fold feature.

Inputs
    data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif   (--prob)
    data/9t/derived/05/labels_pit_9t_05.tif                            (--labels, floor class 1)
    data/9t/models/pad/unet_cv5/fold{k}/pad_prob_cvfold{k}_9t_05.tif   (--pad-prob-dir)
    data/9t/derived/05/labels_pad_9t_05.tif, data/9t/results/splits/cv_split_blocks_pad_9t.csv, pad_blocks_9t.gpkg
    split file from P1 S2 (for the separation table), the pit manifest

Outputs
    <out-dir>/buffer_derivation_9t.json      task = pit for the top-level fields (backward compatible),
                                             buffer_m_by_task {"pit": m, "pad": m or null},
                                             by_task {task: full derivation or the reason it is null}
    <out-dir>/residual_semivariogram_9t.png      pit semivariogram with sill and range marked
    <out-dir>/residual_semivariogram_pad_9t.png  pad semivariogram
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/splits/
    Run record under expansions/0_prerequisites/p1_splits_manifests/results/<run_id>/

Run
    python expansions/0_prerequisites/p1_splits_manifests/src/_split_buffer_derive_9t.py --splits data/9t/results/splits/cv_splits_future_9t_v1.json [--tasks pit,pad] [--step-m 5] [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split_core_lib_9t as sc  # noqa: E402
ek = sc.ek

# NOISE_K 2.0. 2026-11-06. User accepted the default noise band 2 sigma ("take defaults"). Change freely.
FRAC, TAIL, NOISE_K = 0.95, 0.25, 2.0
CLASS = {"pit": 1, "pad": 1}


def read_decimated(path: Path, step_m: float, band: int = 1):
    """Nearest-neighbour read on a step_m grid. Returns (array, transform, nodata, native_res)."""
    import rasterio
    from rasterio.enums import Resampling
    with rasterio.open(path) as r:
        ek.assert_crs(r)
        res = abs(r.transform.a)
        f = max(1, int(round(step_m / res)))
        h, w = r.height // f, r.width // f
        a = r.read(band, out_shape=(h, w), resampling=Resampling.nearest)
        tf = r.transform * r.transform.scale(r.width / w, r.height / h)
        return a, tf, r.nodata, res


def semivariogram(z: np.ndarray, mask: np.ndarray, cell_m: float, lag_m: float = 25.0, max_m: float = 2000.0):
    """Exact masked semivariogram over all pairs, by FFT. Returns (lag centres, gamma, pair counts)."""
    z = np.where(mask, z, 0.0).astype(np.float64)
    m = mask.astype(np.float64)
    H, W = z.shape
    sh = (2 * H, 2 * W)
    F = np.fft.rfft2
    Fi = lambda x: np.fft.irfft2(x, s=sh)  # noqa: E731
    fm, fz, fz2 = F(m, sh), F(z, sh), F(z * z, sh)
    # sum over x of m(x) m(x+h) and the squared difference, for every offset h
    npairs = Fi(np.conj(fm) * fm)
    s = Fi(np.conj(fz2) * fm) + Fi(np.conj(fm) * fz2) - 2 * Fi(np.conj(fz) * fz)
    dy = np.fft.fftfreq(sh[0], 1 / sh[0])[:, None] * cell_m
    dx = np.fft.fftfreq(sh[1], 1 / sh[1])[None, :] * cell_m
    d = np.hypot(dy, dx)
    edges = np.arange(0, max_m + lag_m, lag_m)
    idx = np.digitize(d.ravel(), edges) - 1
    ok = (idx >= 0) & (idx < len(edges) - 1) & (d.ravel() > 0)
    n = np.bincount(idx[ok], weights=np.rint(npairs.ravel()[ok]), minlength=len(edges) - 1)
    g = np.bincount(idx[ok], weights=s.ravel()[ok], minlength=len(edges) - 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        gamma = 0.5 * g / n
    return (edges[:-1] + lag_m / 2), gamma, n


def range_rule(lags, gamma, frac: float = FRAC, tail: float = TAIL, noise_k: float = NOISE_K) -> dict:
    """Sill, point range, noise-robust range upper bound and the flat-variogram flags (review P1-04)."""
    lags, gamma = np.asarray(lags, float), np.asarray(gamma, float)
    ok = np.isfinite(gamma)
    lg, gm = lags[ok], gamma[ok]
    tail_v = gm[lg >= lg.max() * (1 - tail)]
    sill = float(np.mean(tail_v))
    sigma = float(np.std(tail_v))
    thr, thr_hi = frac * sill, frac * sill + noise_k * sigma
    point = np.where(gm >= thr)[0]
    robust = np.where(gm >= thr_hi)[0]
    return {
        "sill": sill, "sill_sigma": sigma, "frac": frac, "noise_k": noise_k,
        "threshold": thr, "threshold_robust": thr_hi,
        "range_m": float(lg[point[0]]) if len(point) else float("nan"),
        "range_m_upper_bound": float(lg[robust[0]]) if len(robust) else float("nan"),
        "range_below_first_lag": bool(gm[0] >= thr_hi),
        "first_lag_within_noise": bool(abs(gm[0] - thr) <= noise_k * sigma),
        "first_lag_share_of_sill": float(gm[0] / sill) if sill else float("nan"),
    }


def sill_and_range(lags, gamma, frac: float = FRAC, tail: float = TAIL) -> tuple[float, float]:
    """(sill, range used for the buffer). Kept for callers of the old two-value form."""
    r = range_rule(lags, gamma, frac, tail)
    return r["sill"], r["range_m_upper_bound"]


def separation(man, splits: dict) -> dict:
    from scipy.spatial import cKDTree
    m = man.dropna(subset=["block_id"]).copy()
    m["block_id"] = m.block_id.astype(int)
    out = {}
    for f, roles in splits.items():
        held = set(roles["held_out"])
        h = m[m.block_id.isin(held)][["centroid_x", "centroid_y"]].to_numpy()
        o = m[~m.block_id.isin(held)][["centroid_x", "centroid_y"]].to_numpy()
        if not len(h) or not len(o):
            continue
        d, _ = cKDTree(o).query(h)
        out[str(f)] = {"min_dist_m": round(float(d.min()), 1), "share_within_40m": round(float((d <= 40).mean()), 4)}
    return out


def prob_field(prob: Path, step_m: float):
    """(values, valid mask, transform, native res) of a single out-of-fold probability raster."""
    p, tf, nd, res = read_decimated(prob, step_m)
    if p.dtype == np.uint8:
        mask = p != (nd if nd is not None else 255)
        pv = p.astype(np.float64) / 254.0
    else:
        pv = p.astype(np.float64)
        mask = np.isfinite(pv) & ((pv != nd) if nd is not None else True)
    return pv, mask, tf, res


def oof_from_folds(fold_rasters: dict[int, Path], held_by_fold: dict[int, list[int]], blocks_gdf, step_m: float):
    """Out-of-fold field from per-fold full-tile rasters. Each fold contributes inside its held-out blocks."""
    from rasterio.features import rasterize
    out = mask = tf0 = res0 = None
    for k in sorted(fold_rasters):
        pv, ok, tf, res = prob_field(fold_rasters[k], step_m)
        if out is None:
            out, mask, tf0, res0 = np.zeros(pv.shape), np.zeros(pv.shape, bool), tf, res
        elif pv.shape != out.shape or not np.allclose(tuple(tf)[:6], tuple(tf0)[:6]):
            raise AssertionError(f"fold {k} raster is not on the fold-0 grid")
        g = blocks_gdf[blocks_gdf.block_id.astype(int).isin(held_by_fold[k])].geometry
        if len(g) != len(set(held_by_fold[k])):
            raise AssertionError(f"fold {k}: held-out blocks without a polygon")
        hm = rasterize([(x, 1) for x in g], out_shape=pv.shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        if (hm & mask).any():
            raise AssertionError(f"fold {k}: held-out ground also held out by an earlier fold")
        sel = hm & ok
        out[sel], mask[sel] = pv[sel], True
    return out, mask, tf0, res0


def derive_field(pv, mask, tf, res, labels: Path, step_m: float, cls: int, n_classes: int, patch_px: int,
                 lag_m: float = 25.0, max_m: float = 2000.0, rf_size: int = 512) -> dict:
    y, tf2, _, _ = read_decimated(labels, step_m)
    if pv.shape != y.shape or not np.allclose(tuple(tf)[:6], tuple(tf2)[:6]):
        raise AssertionError("probability and label rasters are not on the same grid")
    r = pv - (y == cls).astype(np.float64)
    cell = abs(tf.a)
    lags, gamma, npairs = semivariogram(r, mask, cell, lag_m, max_m)
    rr = range_rule(lags, gamma)
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
    from _dl import UNet
    rf = sc.receptive_field_px(UNet(in_ch=7, n_classes=n_classes, base=32), 7, size=rf_size)
    rf_radius_m = rf["radius_px"] * res
    patch_half_m = patch_px * res / 2
    up = lambda x: float(math.ceil(x / 25.0) * 25.0)  # noqa: E731
    rng = rr["range_m_upper_bound"]
    return {
        "step_m": cell, "native_res_m": res, "n_valid_cells": int(mask.sum()),
        "receptive_field": {**rf, "radius_m": rf_radius_m, "width_m": rf["width_px"] * res},
        "patch_px": patch_px, "patch_half_m": patch_half_m,
        "semivariogram": {"lag_m": lags.tolist(), "gamma": [None if not np.isfinite(g) else float(g) for g in gamma],
                          "pairs": npairs.astype(int).tolist(), **rr,
                          "rule": ("sill = mean over last 25% of lags, sigma their sd. range_m = first lag at 95% "
                                   "of sill. range_m_upper_bound = first lag at 95% of sill + 2 sigma; it is the "
                                   "first lag when range_below_first_lag. The buffer uses range_m_upper_bound")},
        "buffer_m": up(rf_radius_m + rng) if np.isfinite(rng) else None,
        "buffer_formula": "receptive_field_radius + range_m_upper_bound, rounded up to 25 m",
        "buffer_patch_support_variant_m": up(patch_half_m + rng) if np.isfinite(rng) else None,
    }


def derive(prob: Path, labels: Path, step_m: float, floor_class: int, n_classes: int, patch_px: int,
           lag_m: float = 25.0, max_m: float = 2000.0, rf_size: int = 512) -> dict:
    """Derivation from one out-of-fold probability raster (the pit mosaic)."""
    pv, mask, tf, res = prob_field(prob, step_m)
    return derive_field(pv, mask, tf, res, labels, step_m, floor_class, n_classes, patch_px, lag_m, max_m, rf_size)


def assemble(by_task: dict[str, dict | str]) -> dict:
    """The buffer JSON. by_task maps a task to its derivation dict, or to a string saying why it is null.

    Top-level fields repeat the pit derivation with task = pit, so a reader of the old single-task file
    still gets the pit numbers. buffer_m_by_task is the schema ek.read_buffer reads (review P1-03)."""
    if not isinstance(by_task.get("pit"), dict):
        raise AssertionError("the pit derivation is required")
    doc = {**by_task["pit"], "task": "pit", "schema": "wellsight.buffer.v2",
           "buffer_m_by_task": {}, "by_task": {}}
    for t in sc.TASKS:
        v = by_task.get(t, "not derived")
        if isinstance(v, dict):
            doc["buffer_m_by_task"][t] = v["buffer_m"]
            doc["by_task"][t] = v
        else:
            doc["buffer_m_by_task"][t] = None
            doc["by_task"][t] = {"buffer_m": None, "reason": str(v)}
    return doc


def write_buffer_json(doc: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


def figure(res: dict, path: Path, title: str = "Out-of-fold pit floor residual, 9t") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sv = res["semivariogram"]
    lag = np.array(sv["lag_m"])
    g = np.array([np.nan if v is None else v for v in sv["gamma"]])
    fig, ax = plt.subplots(figsize=(7, 4))
    # ek.PALETTE blue and orange. Lost/found palette, worst pair dE 21.1 deutan (CLAUDE.md, --pairs all).
    ax.plot(lag, g, color=ek.PALETTE["blue"], marker="o", ms=3, lw=1.5, label="semivariance")
    ax.axhline(sv["sill"], color=ek.PALETTE["grey"], ls="--", lw=1, label="sill")
    ub = sv.get("range_m_upper_bound", sv.get("range_m"))
    if ub == ub:
        lab = f"range upper bound {ub:.1f} m" + (" (below first lag)" if sv.get("range_below_first_lag") else "")
        ax.axvline(ub, color=ek.PALETTE["orange"], ls=":", lw=1.5, label=lab)
    ax.set_xlabel("lag distance (m)")
    ax.set_ylabel("semivariance of p - y")
    ax.set_title(title, loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def pad_derivation(a) -> dict | str:
    """Pad buffer from the historical per-fold rasters, or the reason it cannot be derived."""
    import geopandas as gpd
    import pandas as pd
    t = sc.trainer("pad")
    pdir = a.pad_prob_dir or (ek.path_for("models") / "pad" / "unet_cv5")
    rasters = {k: pdir / f"fold{k}" / f"pad_prob_cvfold{k}_9t_05.tif" for k in range(5)}
    exp = a.pad_folds or (ek.path_for("results_9t") / "splits" / "cv_split_blocks_pad_9t.csv")
    need = list(rasters.values()) + [Path(t.LABELS), exp, Path(t.BLOCKS)]
    miss = [str(q) for q in need if not Path(q).exists()]
    if miss:
        return "pad inputs not held: " + ", ".join(miss)
    e = pd.read_csv(exp)
    held = {k: sorted(e[(e.fold == k) & (e.role == "held_out")].block_id.astype(int)) for k in range(5)}
    blocks = gpd.read_file(t.BLOCKS, layer="blocks")
    ek.assert_crs(blocks)
    pv, mask, tf, res = oof_from_folds(rasters, held, blocks, a.step_m)
    out = derive_field(pv, mask, tf, res, Path(t.LABELS), a.step_m, CLASS["pad"], int(t.N_CLASSES), int(t.PATCH),
                       a.lag_m, a.max_m)
    out["inputs"] = {"fold_rasters": {str(k): str(v) for k, v in rasters.items()}, "labels": str(t.LABELS),
                     "held_out_lists": str(exp)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P1 S4 derive the spatial buffer per task")
    ap.add_argument("--prob", type=Path, default=None, help="default the pit out-of-fold mosaic")
    ap.add_argument("--labels", type=Path, default=None, help="default the 9t pit label raster")
    ap.add_argument("--pad-prob-dir", type=Path, default=None, help="default data/9t/models/pad/unet_cv5")
    ap.add_argument("--pad-folds", type=Path, default=None, help="default exporter cv_split_blocks_pad_9t.csv")
    ap.add_argument("--tasks", default="pit,pad")
    ap.add_argument("--splits", type=Path, default=None, help="P1 S2 split file, for the separation table")
    ap.add_argument("--step-m", type=float, default=5.0)
    ap.add_argument("--lag-m", type=float, default=25.0)
    ap.add_argument("--max-m", type=float, default=2000.0)
    ap.add_argument("--out-dir", type=Path, default=None, help="default data/9t/results/splits/")
    a = ap.parse_args(argv)
    t = sc.trainer("pit")
    prob = a.prob or (ek.path_for("models") / "pit" / "unet_cv5" / "pit_prob_floor_outoffold_9t_05.tif")
    labels = a.labels or Path(t.LABELS)
    for q in (prob, labels):
        if not q.exists():
            raise SystemExit(f"input missing: {q}")
    res = derive(prob, labels, a.step_m, floor_class=CLASS["pit"], n_classes=int(t.N_CLASSES),
                 patch_px=int(t.PATCH), lag_m=a.lag_m, max_m=a.max_m)
    res["inputs"] = {"prob": str(prob), "labels": str(labels)}
    by = {"pit": res}
    by["pad"] = pad_derivation(a) if "pad" in a.tasks.split(",") else "not requested (--tasks)"
    doc = assemble(by)
    if a.splits:
        from _split_future_write_9t import split_file_for
        doc["separation_by_fold"] = separation(sc.load_manifest("pit"), split_file_for("pit", a.splits))
    out = a.out_dir or (ek.path_for("results_9t") / "splits")
    js, png = out / "buffer_derivation_9t.json", out / "residual_semivariogram_9t.png"
    write_buffer_json(doc, js)
    figure(res, png)
    outs = [js, png]
    if isinstance(by["pad"], dict):
        png_pad = out / "residual_semivariogram_pad_9t.png"
        figure(by["pad"], png_pad, "Out-of-fold pad residual, 9t")
        outs.append(png_pad)
    run = ek.new_run("p1", "buffer_derive", {"step_m": a.step_m, "lag_m": a.lag_m, "max_m": a.max_m, "tasks": a.tasks},
                     why="S4 derive the buffer per task from receptive field and residual semivariogram.")
    ek.write_provenance(run, inputs=[prob, labels] + ([a.splits] if a.splits else []), outputs=outs)
    for task, v in doc["by_task"].items():
        if v.get("buffer_m") is None:
            print(f"{task}: buffer null. {v.get('reason', '')}")
            continue
        sv, rf = v["semivariogram"], v["receptive_field"]
        print(f"{task}: receptive field {rf['width_px']} px wide, radius {rf['radius_m']:.1f} m. sill {sv['sill']:.6f} "
              f"sigma {sv['sill_sigma']:.6f}. first lag {sv['first_lag_share_of_sill']:.4f} of sill. point range "
              f"{sv['range_m']} m, upper bound {sv['range_m_upper_bound']} m (below first lag "
              f"{sv['range_below_first_lag']}, first lag within noise {sv['first_lag_within_noise']}). buffer "
              f"{v['buffer_m']} m (patch-support variant {v['buffer_patch_support_variant_m']} m)")
    print("\n".join(f"wrote {p}" for p in outs) + f"\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
