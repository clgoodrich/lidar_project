"""P1 S4. Derive the spatial buffer from the model receptive field and an empirical residual semivariogram.

Purpose
    1. Residual. r = p - y per pixel for the pit floor class, p from the out-of-fold probability raster
       (uint8 DN / 254, 255 nodata), y = 1 where the label raster is the floor class. Both are read on a
       5 m grid (decimated nearest read) so the whole tile fits in memory.
    2. Semivariogram. Exact masked estimator over every pair on the 5 m grid, computed with FFT
       cross-correlations, binned in 25 m lags to 2,000 m. Sill is the mean semivariance over the last
       quarter of lags. Range is the first lag whose semivariance reaches 95% of the sill.
    3. Receptive field. Measured from the input-gradient support of the `UNet` in `_dl.py` (base 32, 7
       channels, n_classes of the task), in pixels and metres at the raster resolution.
    4. Buffer. framework formula `buffer = receptive_field_radius + range`, rounded up to 25 m.
       The protocol (section 3 rule 4) also names patch support. The patch-support variant
       `patch_half + range` is reported beside it and is not the primary value (decisions_p1.md).
    5. Separation. Per fold, minimum distance from held-out features to any other-fold feature and the
       share within 40 m.

Inputs
    data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif   (--prob)
    data/9t/derived/05/labels_pit_9t_05.tif                            (--labels, floor class 1)
    split file from P1 S2 (for the separation table), the pit manifest

Outputs
    <out-dir>/buffer_derivation_9t.json      receptive field, semivariogram table, sill, range, buffer, separation
    <out-dir>/residual_semivariogram_9t.png  semivariogram with sill and range marked
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/splits/
    Run record under expansions/0_prerequisites/p1_splits_manifests/results/<run_id>/

Run
    python expansions/0_prerequisites/p1_splits_manifests/src/_split_buffer_derive_9t.py --splits data/9t/results/splits/cv_splits_future_9t_v1.json [--step-m 5] [--out-dir DIR]
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


def sill_and_range(lags, gamma, frac: float = 0.95, tail: float = 0.25) -> tuple[float, float]:
    ok = np.isfinite(gamma)
    lg, gm = lags[ok], gamma[ok]
    sill = float(np.mean(gm[lg >= lg.max() * (1 - tail)]))
    above = np.where(gm >= frac * sill)[0]
    return sill, float(lg[above[0]]) if len(above) else float("nan")


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


def derive(prob: Path, labels: Path, step_m: float, floor_class: int, n_classes: int, patch_px: int,
           lag_m: float = 25.0, max_m: float = 2000.0, rf_size: int = 512) -> dict:
    p, tf, nd, res = read_decimated(prob, step_m)
    y, tf2, _, _ = read_decimated(labels, step_m)
    if p.shape != y.shape or not np.allclose(tuple(tf)[:6], tuple(tf2)[:6]):
        raise AssertionError("probability and label rasters are not on the same grid")
    if p.dtype == np.uint8:
        mask = p != (nd if nd is not None else 255)
        pv = p.astype(np.float64) / 254.0
    else:
        pv = p.astype(np.float64)
        mask = np.isfinite(pv) & ((pv != nd) if nd is not None else True)
    r = pv - (y == floor_class).astype(np.float64)
    cell = abs(tf.a)
    lags, gamma, npairs = semivariogram(r, mask, cell, lag_m, max_m)
    sill, rng = sill_and_range(lags, gamma)
    from _dl import UNet
    rf = sc.receptive_field_px(UNet(in_ch=7, n_classes=n_classes, base=32), 7, size=rf_size)
    rf_radius_m = rf["radius_px"] * res
    patch_half_m = patch_px * res / 2
    up = lambda x: float(math.ceil(x / 25.0) * 25.0)  # noqa: E731
    return {
        "step_m": cell, "native_res_m": res, "n_valid_cells": int(mask.sum()),
        "receptive_field": {**rf, "radius_m": rf_radius_m, "width_m": rf["width_px"] * res},
        "patch_px": patch_px, "patch_half_m": patch_half_m,
        "semivariogram": {"lag_m": lags.tolist(), "gamma": [None if not np.isfinite(g) else float(g) for g in gamma],
                          "pairs": npairs.astype(int).tolist(), "sill": sill, "range_m": rng,
                          "rule": "range = first lag reaching 95% of sill. sill = mean over last 25% of lags"},
        "buffer_m": up(rf_radius_m + rng) if np.isfinite(rng) else None,
        "buffer_formula": "receptive_field_radius + correlogram_range, rounded up to 25 m",
        "buffer_patch_support_variant_m": up(patch_half_m + rng) if np.isfinite(rng) else None,
    }


def figure(res: dict, path: Path) -> None:
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
    if sv["range_m"] == sv["range_m"]:
        ax.axvline(sv["range_m"], color=ek.PALETTE["orange"], ls=":", lw=1.5, label=f"range {sv['range_m']:.0f} m")
    ax.set_xlabel("lag distance (m)")
    ax.set_ylabel("semivariance of p - y")
    ax.set_title("Out-of-fold pit floor residual, 9t", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P1 S4 derive the spatial buffer")
    ap.add_argument("--prob", type=Path, default=None, help="default the pit out-of-fold mosaic")
    ap.add_argument("--labels", type=Path, default=None, help="default the 9t pit label raster")
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
    res = derive(prob, labels, a.step_m, floor_class=1, n_classes=int(t.N_CLASSES), patch_px=int(t.PATCH),
                 lag_m=a.lag_m, max_m=a.max_m)
    if a.splits:
        from _split_future_write_9t import split_file_for
        res["separation_by_fold"] = separation(sc.load_manifest("pit"), split_file_for("pit", a.splits))
    out = a.out_dir or (ek.path_for("results_9t") / "splits")
    out.mkdir(parents=True, exist_ok=True)
    js, png = out / "buffer_derivation_9t.json", out / "residual_semivariogram_9t.png"
    res["inputs"] = {"prob": str(prob), "labels": str(labels)}
    js.write_text(json.dumps(res, indent=1), encoding="utf-8")
    figure(res, png)
    run = ek.new_run("p1", "buffer_derive", {"step_m": a.step_m, "lag_m": a.lag_m, "max_m": a.max_m},
                     why="S4 derive the buffer from receptive field and residual semivariogram.")
    ek.write_provenance(run, inputs=[prob, labels] + ([a.splits] if a.splits else []), outputs=[js, png])
    rf = res["receptive_field"]
    print(f"receptive field {rf['width_px']} px wide, radius {rf['radius_m']:.1f} m. "
          f"sill {res['semivariogram']['sill']:.5f}, range {res['semivariogram']['range_m']} m. "
          f"buffer {res['buffer_m']} m (patch-support variant {res['buffer_patch_support_variant_m']} m)")
    print(f"wrote {js}\nwrote {png}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
