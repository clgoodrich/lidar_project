"""Road U-Net fine-tuned on the human corrections for 613590 (active learning).

Takes the champion recall model (`road_unet_1m_recall`, focal-alpha road 0.72)
and fine-tunes it on 9t (clean, fully labelled) PLUS the corridor-supervised
613590 corrections built by `_build_road_corrections_613590.py`:

    added   roads the model missed        -> positives (fix recall)
    reject  segments the human deleted    -> hard negatives (fix precision)
    kept    segments the human confirmed  -> positives (prevent forgetting)

Training set is ConcatDataset(9t train, 613590 train). Model selection stays on
**9t val road IoU** — the same score the champion was picked on, so the number
is comparable and a drop means the corrections hurt in-domain.

Honest evaluation (nothing tuned on it):
  * 9t held-out test  — pixel IoU + line AP, regression check vs champion
  * 613590 held-out TEST cells — mean P(road) on added / reject / kept lines,
    before (champion raster) vs after, plus added-vs-reject separation AP.
    Training centers were eroded by patch-half + jitter from cell edges, so no
    training patch ever overlapped a val/test cell.

CLI:
  python notebooks/wellsight_v2/s3_train/_road_unet_1m_corrected.py --epochs 15
  ... --scratch          train from random init instead of fine-tuning
  ... --eval-only        just re-run evaluation with the saved best.pt
  ... --tag r2           write to road_unet_1m_corrected_r2 (one dir per
                         active-learning round, so round 1 stays comparable)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import torch
from rasterio.features import rasterize
from torch.utils.data import ConcatDataset, DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T, make_profile, write_tif
from _dl import (DEVICE, CenteredPatchSampler, FocalCE, UNet, load_stats,
                 predict_full_tile, train_loop)

OUTDIR = DERIV_9T / "road_unet_1m_corrected"   # overridden by --tag
CHAMPION = DERIV_9T / "road_unet_1m_recall"

FEATURES = DERIV_9T / "features_pit_9t_1m.tif"
LABELS = DERIV_9T / "labels_road_9t_1m.tif"
STATS = DERIV_9T / "feature_stats_1m.json"
BLOCKS = DERIV_9T / "pit_blocks_9t.gpkg"
MANIFEST = DERIV_9T / "road_dataset_manifest.csv"
CHUNKS = DERIV_9T / "road_chunks_9t.gpkg"

BLOCK = DERIV / "tiles" / "data_3x3" / "westernpa_d20" / "613590"
CORR = BLOCK / "corrections"
CORR_FEATURES = BLOCK / "features_613590_1m.tif"
CORR_LABELS = CORR / "labels_road_corr_613590_1m.tif"
CORR_CENTERS = CORR / "correction_centers_613590.csv"
CORR_LINES = CORR / "correction_lines_613590.gpkg"
BASELINE_PROB = CHAMPION / "road_prob_613590_1m.tif"

CHANNELS_1M = ("lrm_25", "lrm_5", "slope", "tpi_05",
               "openness_pos", "openness_neg", "roughness_5")
PATCH, OVERLAP, N_CLASSES = 256, 64, 3
JITTER_M = 30.0
FOCAL_ALPHA = (0.10, 0.72, 0.25)
FOCAL_GAMMA = 2.0
WEIGHT_DECAY = 2e-4
KEPT_CAP = 1200          # caps 613590 epoch length ~= 39% of 9t's
SAMPLE_SEED = 11


def build_9t_dataset(split, manifest, blocks, tf, mu, sd, *, augment, seed):
    m = manifest[manifest.split == split]
    pol = []
    for kind in ("road", "not_road", "drainage"):
        pts = m.loc[m.kind == kind, ["mid_x", "mid_y"]].to_numpy()
        if len(pts):
            pol.append((kind, pts, JITTER_M))
    bounds = np.array([g.bounds for g in
                       blocks.loc[blocks.split == split].geometry])
    return CenteredPatchSampler(
        feat_path=FEATURES, lbl_path=LABELS, policies=pol,
        block_bounds=bounds, transform=tf, mu=mu, sd=sd, patch=PATCH,
        augment=augment, seed=seed)


def build_corr_dataset(split, centers, cells, tf, mu, sd, *, augment, seed):
    """613590 sampler: policies on added / reject / kept correction centers."""
    c = centers[centers.split == split]
    rng = np.random.default_rng(SAMPLE_SEED)
    pol = []
    for kind in ("added", "reject", "kept"):
        pts = c.loc[c.kind == kind, ["x", "y"]].to_numpy()
        if kind == "kept" and len(pts) > KEPT_CAP:
            pts = pts[rng.choice(len(pts), KEPT_CAP, replace=False)]
        if len(pts):
            pol.append((kind, pts, JITTER_M))
    bounds = np.array([g.bounds for g in
                       cells.loc[cells.split == split].geometry])
    return CenteredPatchSampler(
        feat_path=CORR_FEATURES, lbl_path=CORR_LABELS, policies=pol,
        block_bounds=bounds, transform=tf, mu=mu, sd=sd, patch=PATCH,
        augment=augment, seed=seed)


def sample_line_prob(prob_path, lines, band=1):
    """Mean raster value along each line (1 m step)."""
    with rasterio.open(prob_path) as r:
        arr = r.read(band if r.count > 1 else 1)
        tf, H, W = r.transform, r.height, r.width
    out = []
    for g in lines.geometry:
        if g is None or g.is_empty:
            out.append(np.nan); continue
        gg = (max(g.geoms, key=lambda s: s.length)
              if g.geom_type == "MultiLineString" else g)
        n = max(2, int(gg.length))
        vals = []
        for i in range(n + 1):
            p = gg.interpolate(min(i, gg.length))
            r0 = int(round((p.y - tf.f) / tf.e))
            c0 = int(round((p.x - tf.c) / tf.a))
            if 0 <= r0 < H and 0 <= c0 < W and arr[r0, c0] >= 0:
                vals.append(float(arr[r0, c0]))
        out.append(float(np.mean(vals)) if vals else np.nan)
    return np.array(out)


def average_precision(scores, labels):
    """AP for positives=1 ranked by score."""
    ok = np.isfinite(scores)
    scores, labels = scores[ok], labels[ok]
    if len(scores) == 0 or labels.sum() == 0 or labels.sum() == len(labels):
        return None
    order = np.argsort(-scores)
    ys = labels[order]
    tp = np.cumsum(ys); fp = np.cumsum(1 - ys)
    prec = tp / np.maximum(tp + fp, 1)
    rec = tp / max(int(labels.sum()), 1)
    return float(np.trapezoid(prec, rec))


def evaluate_corrections(prob_after, prob_before=BASELINE_PROB):
    """Held-out correction metrics on 613590, before vs after fine-tuning."""
    layers = {k: gpd.read_file(CORR_LINES, layer=k)
              for k in ("added", "reject", "kept")}
    res = {}
    for split in ("val", "test"):
        block = {}
        for kind, g in layers.items():
            sub = g[g.split == split]
            if not len(sub):
                continue
            b = sample_line_prob(prob_before, sub)
            a = sample_line_prob(prob_after, sub)
            block[kind] = {
                "n": int(len(sub)),
                "km": round(float(sub.length.sum() / 1000), 2),
                "mean_Proad_before": round(float(np.nanmean(b)), 4),
                "mean_Proad_after": round(float(np.nanmean(a)), 4),
                "delta": round(float(np.nanmean(a) - np.nanmean(b)), 4),
                "frac_over_0.5_before": round(float(np.nanmean(b >= 0.5)), 3),
                "frac_over_0.5_after": round(float(np.nanmean(a >= 0.5)), 3),
            }
        # can the model separate real missed roads from false positives?
        if "added" in block and "reject" in block:
            ad, rj = layers["added"], layers["reject"]
            ad, rj = ad[ad.split == split], rj[rj.split == split]
            for tag, path in (("before", prob_before), ("after", prob_after)):
                s = np.concatenate([sample_line_prob(path, ad),
                                    sample_line_prob(path, rj)])
                y = np.concatenate([np.ones(len(ad)), np.zeros(len(rj))])
                block[f"ap_added_vs_reject_{tag}"] = average_precision(s, y)
        res[split] = block
    return res


def evaluate_9t(argmax, prob):
    with rasterio.open(LABELS) as r:
        labels = r.read(1); H, W, tf = r.height, r.width, r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    tmask = rasterize(
        [(g, 1) for g in blocks.loc[blocks.split == "test", "geometry"]],
        out_shape=(H, W), transform=tf, fill=0, dtype="uint8").astype(bool)
    p, t = argmax == 1, labels == 1
    union = int(((p | t) & tmask).sum())
    pix_iou = int((p & t & tmask).sum()) / union if union else None

    chunks = gpd.read_file(CHUNKS, layer="chunks")
    ct = chunks[chunks.split == "test"]

    def lp(line, cls=1):
        if line is None or line.is_empty:
            return 0.0
        n = max(2, int(line.length)); vals = []
        for i in range(n + 1):
            pt = line.interpolate(min(i, line.length))
            r0 = int(round((pt.y - tf.f) / tf.e))
            c0 = int(round((pt.x - tf.c) / tf.a))
            if 0 <= r0 < H and 0 <= c0 < W:
                vals.append(float(prob[cls, r0, c0]))
        return float(np.mean(vals)) if vals else 0.0

    df = pd.DataFrame([{"kind": r.kind, "p_road": lp(r.geometry)}
                       for _, r in ct.iterrows()])

    def ap_vs(neg):
        sub = df[df.kind.isin(["road", neg])]
        if not len(sub) or sub.kind.nunique() < 2:
            return None
        return average_precision(sub.p_road.to_numpy(),
                                 (sub.kind == "road").astype(int).to_numpy())

    return {
        "pixel_iou_road_test": pix_iou,
        "ap_road_vs_not_road": ap_vs("not_road"),
        "ap_road_vs_drainage": ap_vs("drainage"),
        "mean_Proad_on_road_test": float(df[df.kind == "road"].p_road.mean()),
        "mean_Proad_on_drainage_test":
            float(df[df.kind == "drainage"].p_road.mean())
            if (df.kind == "drainage").any() else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--scratch", action="store_true")
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--tag", default=None,
                    help="suffix for the output dir, e.g. 'r2' -> "
                         "road_unet_1m_corrected_r2. Each active-learning "
                         "round gets its own so earlier metrics stay readable.")
    args = ap.parse_args()

    global OUTDIR
    if args.tag:
        OUTDIR = OUTDIR.with_name(f"{OUTDIR.name}_{args.tag}")
    print(f"output dir: {OUTDIR}")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(MANIFEST)
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    centers = pd.read_csv(CORR_CENTERS)
    cells = gpd.read_file(CORR / "correction_split_cells_613590.gpkg",
                          layer="cells")
    mu, sd = load_stats(STATS, CHANNELS_1M)
    with rasterio.open(FEATURES) as r:
        tf9 = r.transform
    with rasterio.open(CORR_FEATURES) as r:
        tfc = r.transform

    model = UNet(in_ch=len(CHANNELS_1M), n_classes=N_CLASSES, base=32)

    if not args.eval_only:
        if not args.scratch:
            ck = torch.load(CHAMPION / "best.pt", map_location="cpu",
                            weights_only=False)
            model.load_state_dict(ck["state_dict"])
            print(f"fine-tuning from champion ep {ck['epoch']} "
                  f"(val road IoU {ck['score']:.3f}), lr={args.lr}")
        else:
            print(f"training from scratch, lr={args.lr}")

        tr9 = build_9t_dataset("train", manifest, blocks, tf9, mu, sd,
                               augment=True, seed=42)
        trc = build_corr_dataset("train", centers, cells, tfc, mu, sd,
                                 augment=True, seed=44)
        val9 = build_9t_dataset("val", manifest, blocks, tf9, mu, sd,
                                augment=False, seed=43)
        print(f"9t train tiles/ep={len(tr9)}  613590 train tiles/ep={len(trc)}"
              f"  ({100*len(trc)/(len(tr9)+len(trc)):.0f}% corrections)")
        print("  613590 policies: " + ", ".join(
            f"{n}={len(p)}" for n, p, _ in trc.policies))

        train_loader = DataLoader(ConcatDataset([tr9, trc]),
                                  batch_size=args.batch, shuffle=True,
                                  num_workers=0, pin_memory=True)
        val_loader = DataLoader(val9, batch_size=args.batch, shuffle=False,
                                num_workers=0, pin_memory=True)
        train_loop(
            model=model, train_loader=train_loader, val_loader=val_loader,
            loss_fn=FocalCE(alpha=FOCAL_ALPHA, gamma=FOCAL_GAMMA),
            epochs=args.epochs, lr=args.lr, n_classes=N_CLASSES,
            out_dir=OUTDIR, weight_decay=WEIGHT_DECAY,
            checkpoint_extra={"mu": mu, "sd": sd,
                              "channels": list(CHANNELS_1M), "patch": PATCH,
                              "init": "scratch" if args.scratch
                              else "road_unet_1m_recall"},
            score=lambda iou: float(iou[1]),
            extra_iou_names=("bg", "road", "drainage"))

    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE,
                    weights_only=False)
    model.to(DEVICE).load_state_dict(ck["state_dict"])
    print(f"\nLoaded best (ep {ck['epoch']}, 9t val road IoU {ck['score']:.3f})")

    prob, argmax, prof = predict_full_tile(model, FEATURES, mu, sd,
                                           patch=PATCH, overlap=OVERLAP,
                                           n_classes=N_CLASSES)
    m9 = evaluate_9t(argmax, prob)
    print("\n=== 9t held-out test ===")
    for k, v in m9.items():
        if v is not None:
            print(f"  {k:30s} {v:.4f}")

    prob_c, argmax_c, prof_c = predict_full_tile(
        model, CORR_FEATURES, mu, sd, patch=PATCH, overlap=OVERLAP,
        n_classes=N_CLASSES)
    tfp, crsp = prof_c["transform"], prof_c["crs"]
    out_prob = OUTDIR / "road_prob_613590_1m.tif"
    write_tif(out_prob, prob_c[1], transform=tfp, crs=crsp, dtype="float32",
              nodata=-1.0, bigtiff=True)
    write_tif(OUTDIR / "drainage_prob_613590_1m.tif", prob_c[2],
              transform=tfp, crs=crsp, dtype="float32", nodata=-1.0,
              bigtiff=True)
    p = make_profile(width=argmax_c.shape[1], height=argmax_c.shape[0],
                     transform=tfp, crs=crsp, dtype="uint8", nodata=255)
    with rasterio.open(OUTDIR / "road_argmax_613590_1m.tif", "w", **p) as dst:
        dst.write(argmax_c, 1)
    print(f"\n613590: road>=0.5 px = {int((prob_c[1] >= 0.5).sum()):,} "
          f"(champion raster for comparison below)")

    corr = evaluate_corrections(out_prob)
    print("\n=== 613590 held-out corrections (before -> after) ===")
    for split in ("val", "test"):
        print(f"  [{split}]")
        for kind in ("added", "reject", "kept"):
            d = corr[split].get(kind)
            if d:
                print(f"    {kind:7s} n={d['n']:4d} {d['km']:5.2f} km  "
                      f"P(road) {d['mean_Proad_before']:.3f} -> "
                      f"{d['mean_Proad_after']:.3f}  ({d['delta']:+.3f})   "
                      f"frac>=0.5 {d['frac_over_0.5_before']:.2f} -> "
                      f"{d['frac_over_0.5_after']:.2f}")
        for tag in ("before", "after"):
            v = corr[split].get(f"ap_added_vs_reject_{tag}")
            if v is not None:
                print(f"    AP added-vs-reject {tag:6s} {v:.4f}")

    metrics = {"init": ck.get("init"), "best_epoch": ck["epoch"],
               "9t_val_road_iou": ck["score"], "9t_test": m9,
               "corrections_613590": corr,
               "focal_alpha": list(FOCAL_ALPHA),
               "kept_cap": KEPT_CAP, "lr": args.lr, "epochs": args.epochs}
    (OUTDIR / "test_metrics.json").write_text(
        json.dumps(metrics, indent=2, default=float))
    print(f"\nDONE. Outputs in {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
