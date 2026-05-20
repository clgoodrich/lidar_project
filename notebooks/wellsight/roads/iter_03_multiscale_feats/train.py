"""Road U-Net iter 03 — SMP + 11-channel multi-scale + curvature + geomorphons.

Same architecture as road iter 02 (SMP + ResNet34 + ImageNet) but with the
iter 03 11-channel feature stack.

Hypothesis: roads are linear cut-and-fill features. Multi-scale LRM captures
the cut-into-hillslope signature at multiple radii; curvature is non-zero
along road edges (drainage); geomorphons may class roads as footslope/valley.

Open question: did multi-scale features hurt plats (uniform flat) — will
they help roads (uniform linear) or hurt the same way?
"""
import argparse, json, time, sys
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window, from_bounds
from rasterio.features import rasterize
import geopandas as gpd
import torch
from torch.utils.data import Dataset, DataLoader
import segmentation_models_pytorch as smp

sys.path.insert(0, str(Path(__file__).parent.parent))
from _road_unet import run_epoch, D, ANN, LABELS_ROAD, BLOCKS, MANIFEST, DEVICE

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "pits"))
from _pit_unet_v2 import FocalCE

FEATURES_11CH = D / "iterations" / "03_multiscale_feats" / "features_pit_v2_9t_05.tif"
STATS_11CH = D / "iterations" / "03_multiscale_feats" / "feature_stats_v2.json"
OUTDIR = D / "iterations" / "road_03_multiscale_feats"; OUTDIR.mkdir(parents=True, exist_ok=True)

PATCH = 256
N_CLASSES = 2
N_CH = 11
ENCODER_NAME = "resnet34"

CH_ORDER = ["lrm_25", "lrm_5", "slope", "tpi_05", "openness_pos", "openness_neg",
            "roughness_11", "lrm_11", "lrm_51", "curvature", "geomorphons"]


class RoadTiles11(Dataset):
    """Same sampling as RoadTiles but reads from the 11-channel feature TIF."""
    def __init__(self, split, manifest, blocks_gdf, transform, mu, sd, augment=True):
        self.augment = augment
        self.transform = transform
        self.mu = mu.astype(np.float32); self.sd = sd.astype(np.float32)
        m = manifest[manifest.split == split]
        self.roads = m[m.kind == "road"][["mid_x", "mid_y"]].values
        self.not_roads = m[m.kind == "not_road"][["mid_x", "mid_y"]].values
        bs = blocks_gdf[blocks_gdf.split == split]
        self.block_bounds = np.array([g.bounds for g in bs.geometry])
        self._feat = None; self._lbl = None

    def _open(self):
        if self._feat is None:
            self._feat = rasterio.open(FEATURES_11CH)
            self._lbl = rasterio.open(LABELS_ROAD)

    def __len__(self):
        return max(len(self.roads), 1) * 3

    def _w2p(self, x, y):
        tf = self.transform
        return (y - tf.f) / tf.e, (x - tf.c) / tf.a

    def __getitem__(self, idx):
        self._open()
        rng = np.random.default_rng()
        mode = idx % 3
        if mode == 0 and len(self.roads):
            cx, cy = self.roads[rng.integers(0, len(self.roads))]
            cx += rng.uniform(-30, 30); cy += rng.uniform(-30, 30)
        elif mode == 1 and len(self.not_roads):
            cx, cy = self.not_roads[rng.integers(0, len(self.not_roads))]
            cx += rng.uniform(-30, 30); cy += rng.uniform(-30, 30)
        else:
            bb = self.block_bounds[rng.integers(0, len(self.block_bounds))]
            cx = rng.uniform(bb[0], bb[2]); cy = rng.uniform(bb[1], bb[3])
        row, col = self._w2p(cx, cy)
        r0 = int(round(row)) - PATCH // 2
        c0 = int(round(col)) - PATCH // 2
        H, W = self._feat.height, self._feat.width
        r0 = int(np.clip(r0, 0, H - PATCH)); c0 = int(np.clip(c0, 0, W - PATCH))
        feat = self._feat.read(window=Window(c0, r0, PATCH, PATCH)).astype(np.float32)
        lbl = self._lbl.read(1, window=Window(c0, r0, PATCH, PATCH)).astype(np.int64)
        feat = np.where(np.isfinite(feat), feat, 0.0)
        feat = (feat - self.mu[:, None, None]) / self.sd[:, None, None]
        if self.augment:
            k = rng.integers(0, 4)
            if k:
                feat = np.rot90(feat, k, axes=(1, 2)).copy()
                lbl = np.rot90(lbl, k).copy()
            if rng.random() < 0.5:
                feat = feat[:, :, ::-1].copy()
                lbl = lbl[:, ::-1].copy()
        return torch.from_numpy(feat), torch.from_numpy(lbl)


def tta_predict_batch(model, x):
    outs = []
    for k in range(4):
        for flip in (False, True):
            x_aug = x
            if k: x_aug = torch.rot90(x_aug, k=k, dims=(2, 3))
            if flip: x_aug = torch.flip(x_aug, dims=(3,))
            with torch.amp.autocast(device_type="cuda", enabled=DEVICE.type == "cuda"):
                logits = model(x_aug)
            p = torch.softmax(logits, dim=1)
            if flip: p = torch.flip(p, dims=(3,))
            if k: p = torch.rot90(p, k=-k, dims=(2, 3))
            outs.append(p.float())
    return torch.stack(outs, dim=0).mean(dim=0)


def infer_full(model, mu, sd):
    OV = 64
    with rasterio.open(FEATURES_11CH) as r:
        H, W = r.height, r.width
    step = PATCH - OV
    prob = np.zeros((N_CLASSES, H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)
    rs = sorted(set(list(range(0, H - PATCH + 1, step)) + [H - PATCH]))
    cs = sorted(set(list(range(0, W - PATCH + 1, step)) + [W - PATCH]))
    print(f"Inference grid: {len(rs)}x{len(cs)} = {len(rs)*len(cs)} patches (TTA 8x)")
    src = rasterio.open(FEATURES_11CH); model.eval()
    BATCH = 8; buf_x, buf_pos = [], []
    def flush():
        if not buf_x: return
        x = torch.from_numpy(np.stack(buf_x)).to(DEVICE)
        with torch.no_grad():
            p = tta_predict_batch(model, x).cpu().numpy()
        for arr, (r0, c0) in zip(p, buf_pos):
            prob[:, r0:r0+PATCH, c0:c0+PATCH] += arr
            cnt[r0:r0+PATCH, c0:c0+PATCH] += 1
        buf_x.clear(); buf_pos.clear()
    t0 = time.time()
    for r0 in rs:
        for c0 in cs:
            f = src.read(window=Window(c0, r0, PATCH, PATCH)).astype(np.float32)
            f = np.where(np.isfinite(f), f, 0.0)
            f = (f - mu[:, None, None]) / sd[:, None, None]
            buf_x.append(f); buf_pos.append((r0, c0))
            if len(buf_x) >= BATCH: flush()
    flush(); src.close()
    print(f"  TTA inference done in {time.time()-t0:.1f}s")
    cnt = np.maximum(cnt, 1); prob = prob / cnt
    argmax = prob.argmax(0).astype(np.uint8)
    with rasterio.open(LABELS_ROAD) as r:
        profile = r.profile.copy()
    p1 = profile.copy()
    p1.update(dtype="float32", count=1, compress="deflate", predictor=3,
              tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES", nodata=-1.0)
    with rasterio.open(OUTDIR / "road_prob.tif", "w", **p1) as d:
        d.write(prob[1], 1)
    p2 = profile.copy()
    p2.update(dtype="uint8", count=1, compress="deflate", predictor=2,
              tiled=True, blockxsize=512, blockysize=512, nodata=255)
    with rasterio.open(OUTDIR / "road_argmax.tif", "w", **p2) as d:
        d.write(argmax, 1)
    return prob, argmax


def test_eval(argmax, prob):
    with rasterio.open(LABELS_ROAD) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    tbm = rasterize([(g, 1) for g in blocks[blocks.split == "test"].geometry],
                    out_shape=(H, W), transform=tf, fill=0, dtype="uint8").astype(bool)
    p = argmax == 1; t = labels == 1
    inter = int((p & t & tbm).sum()); union = int(((p | t) & tbm).sum())
    pix_iou = inter / union if union else None

    man = pd.read_csv(MANIFEST)
    roads_t = gpd.read_file(ANN, layer="roads")
    not_roads_t = gpd.read_file(ANN, layer="not_roads")
    def line_prob(line_g):
        L = line_g.length; n = max(2, int(L)); ps = []
        for i in range(n + 1):
            pt = line_g.interpolate(min(i, L))
            col = (pt.x - tf.c) / tf.a
            row = (pt.y - tf.f) / tf.e
            r0, c0 = int(round(row)), int(round(col))
            if 0 <= r0 < H and 0 <= c0 < W:
                ps.append(prob[1, r0, c0])
        return float(np.mean(ps)) if ps else 0.0
    rows = []
    for kind, gdf in [("road", roads_t), ("not_road", not_roads_t)]:
        for i, row in gdf.reset_index(drop=True).iterrows():
            lid = f"{kind}_{i}"
            mrow = man[man.line_id == lid]
            if not len(mrow): continue
            if str(mrow.iloc[0]["split"]) != "test": continue
            rows.append({"line_id": lid, "kind": kind, "mean_prob": line_prob(row.geometry)})
    line_df = pd.DataFrame(rows)
    if len(line_df) and line_df.kind.nunique() == 2:
        y = (line_df.kind == "road").astype(int).values
        p_vals = line_df.mean_prob.values
        order = np.argsort(-p_vals); y_sorted = y[order]
        tp = np.cumsum(y_sorted); fp = np.cumsum(1 - y_sorted)
        prec = tp / np.maximum(tp + fp, 1); rec = tp / max(y.sum(), 1)
        ap = float(np.trapz(prec, rec))
    else:
        ap = None
    metrics = {
        "pixel_iou_road_test": pix_iou,
        "line_average_precision_test": ap,
        "n_test_lines_evaluated": int(len(line_df)),
    }
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    line_df.to_csv(OUTDIR / "test_per_line.csv", index=False)
    print(f"\nTEST pixel IoU (road): {pix_iou:.3f}")
    print(f"Per-line AP on test:   {ap}")
    return metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()
    print(f"Device: {DEVICE}")
    manifest = pd.read_csv(MANIFEST)
    blocks_gdf = gpd.read_file(BLOCKS, layer="blocks")
    stats = json.loads(Path(STATS_11CH).read_text())
    mu = np.array([stats[c]["mean"] for c in CH_ORDER], dtype=np.float32)
    sd = np.array([max(stats[c]["std"], 1e-6) for c in CH_ORDER], dtype=np.float32)
    with rasterio.open(FEATURES_11CH) as r: tf = r.transform

    train_ds = RoadTiles11("train", manifest, blocks_gdf, tf, mu, sd, augment=True)
    val_ds = RoadTiles11("val", manifest, blocks_gdf, tf, mu, sd, augment=False)
    print(f"train roads={len(train_ds.roads)} not_roads={len(train_ds.not_roads)} tiles/ep={len(train_ds)}")
    print(f"val   roads={len(val_ds.roads)} not_roads={len(val_ds.not_roads)} tiles/ep={len(val_ds)}")
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False, num_workers=0, pin_memory=True)

    print(f"Building SMP U-Net (encoder={ENCODER_NAME}, ImageNet, in_ch={N_CH}, classes={N_CLASSES})")
    model = smp.Unet(encoder_name=ENCODER_NAME, encoder_weights="imagenet",
                     in_channels=N_CH, classes=N_CLASSES).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"SMP UNet params: {n_params/1e6:.2f} M")
    loss_fn = FocalCE(alpha=(0.10, 0.90), gamma=2.0).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type == "cuda")

    log = []; best_iou = -1.0
    for ep in range(1, args.epochs + 1):
        t0 = time.time()
        tr_loss, _ = run_epoch(model, train_loader, opt, loss_fn, scaler, train=True)
        va_loss, va_iou = run_epoch(model, val_loader, opt, loss_fn, scaler, train=False)
        sched.step(); dt = time.time() - t0
        iou_road = va_iou[1]
        print(f"ep {ep:3d}/{args.epochs}  tr_loss={tr_loss:.4f} va_loss={va_loss:.4f}  "
              f"va_iou bg={va_iou[0]:.3f} road={va_iou[1]:.3f}  {dt:.1f}s")
        log.append({"epoch": ep, "tr_loss": tr_loss, "va_loss": va_loss,
                    "iou_bg": va_iou[0], "iou_road": va_iou[1], "sec": dt})
        if iou_road > best_iou:
            best_iou = iou_road
            torch.save({"state_dict": model.state_dict(), "mu": mu, "sd": sd,
                        "channels": CH_ORDER, "patch": PATCH, "epoch": ep,
                        "iou_road": iou_road, "encoder": ENCODER_NAME},
                       OUTDIR / "best.pt")
            print("    -> new best, saved")
    pd.DataFrame(log).to_csv(OUTDIR / "train_log.csv", index=False)
    print(f"\nBest val road IoU: {best_iou:.3f}")

    model = smp.Unet(encoder_name=ENCODER_NAME, encoder_weights=None,
                     in_channels=N_CH, classes=N_CLASSES).to(DEVICE)
    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.load_state_dict(ck["state_dict"])
    print(f"\nLoaded best ep {ck['epoch']} (road IoU={ck['iou_road']:.3f}). TTA inference...")
    prob, argmax = infer_full(model, mu, sd)
    test_eval(argmax, prob)
    print(f"Outputs in {OUTDIR}")


if __name__ == "__main__":
    main()
