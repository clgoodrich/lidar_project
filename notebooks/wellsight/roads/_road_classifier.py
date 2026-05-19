"""Small CNN classifier: given a 64x64 LiDAR feature patch (32 m square) centered
on a point, predict road (1) vs not-road (0).

The 37 hand-drawn not_roads are the hard-negative set.

Outputs:
    data/derivatives/9t/road_classifier/best.pt
    data/derivatives/9t/road_classifier/train_log.csv
    data/derivatives/9t/road_classifier/test_metrics.json
    data/derivatives/9t/road_classifier/test_predictions.csv
"""
import argparse, json, time, sys
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
OUTDIR = D / "road_classifier"; OUTDIR.mkdir(exist_ok=True)
FEATURES = D / "features_pit_9t_05.tif"
STATS = D / "feature_stats.json"
SAMPLES = D / "road_classifier_samples.csv"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
PATCH = 64    # 32 m square at 0.5 m -- enough to see road + shoulders
N_CH = 7


class RoadCNN(nn.Module):
    def __init__(self, in_ch=7):
        super().__init__()
        def cb(ic, oc):
            return nn.Sequential(
                nn.Conv2d(ic, oc, 3, padding=1, bias=False),
                nn.BatchNorm2d(oc), nn.ReLU(inplace=True))
        self.net = nn.Sequential(
            cb(in_ch, 32), cb(32, 32), nn.MaxPool2d(2),          # 64 -> 32
            cb(32, 64),    cb(64, 64), nn.MaxPool2d(2),          # 32 -> 16
            cb(64, 128),   cb(128, 128), nn.MaxPool2d(2),        # 16 -> 8
            cb(128, 256),  cb(256, 256), nn.AdaptiveAvgPool2d(1) # -> 1x1
        )
        self.head = nn.Linear(256, 1)

    def forward(self, x):
        z = self.net(x).flatten(1)
        return self.head(z).squeeze(1)


class PatchDataset(Dataset):
    def __init__(self, df, mu, sd, augment=True):
        self.df = df.reset_index(drop=True)
        self.augment = augment
        self.mu = mu.astype(np.float32); self.sd = sd.astype(np.float32)
        self._feat = None
        self._tf = None
        with rasterio.open(FEATURES) as r:
            self._tf = r.transform
            self.H, self.W = r.height, r.width

    def _open(self):
        if self._feat is None:
            self._feat = rasterio.open(FEATURES)

    def __len__(self): return len(self.df)

    def __getitem__(self, idx):
        self._open()
        row = self.df.iloc[idx]
        col = (row.x - self._tf.c) / self._tf.a
        rrow = (row.y - self._tf.f) / self._tf.e
        r0 = int(round(rrow)) - PATCH // 2
        c0 = int(round(col)) - PATCH // 2
        r0 = int(np.clip(r0, 0, self.H - PATCH)); c0 = int(np.clip(c0, 0, self.W - PATCH))
        feat = self._feat.read(window=Window(c0, r0, PATCH, PATCH)).astype(np.float32)
        feat = np.where(np.isfinite(feat), feat, 0.0)
        feat = (feat - self.mu[:, None, None]) / self.sd[:, None, None]
        if self.augment:
            rng = np.random.default_rng()
            k = int(rng.integers(0, 4))
            if k: feat = np.rot90(feat, k, axes=(1, 2)).copy()
            if rng.random() < 0.5: feat = feat[:, :, ::-1].copy()
            if rng.random() < 0.5: feat = feat[:, ::-1, :].copy()
        return torch.from_numpy(feat), float(row.label)


def run_epoch(model, loader, opt, scaler, criterion, train=True):
    model.train() if train else model.eval()
    total_loss = 0.0; n = 0
    correct = 0; total = 0
    probs_all = []; labels_all = []
    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for x, y in loader:
            x = x.to(DEVICE, non_blocking=True)
            y = y.to(DEVICE, non_blocking=True).float()
            if train: opt.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type="cuda", enabled=DEVICE.type=="cuda"):
                logit = model(x)
                loss = criterion(logit, y)
            if train:
                scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
            total_loss += loss.item(); n += 1
            p = torch.sigmoid(logit).detach().cpu().numpy()
            yy = y.detach().cpu().numpy()
            pred = (p > 0.5).astype(int)
            correct += int((pred == yy.astype(int)).sum()); total += len(yy)
            probs_all.append(p); labels_all.append(yy)
    probs = np.concatenate(probs_all); labels = np.concatenate(labels_all)
    return total_loss / max(n, 1), correct / max(total, 1), probs, labels


def metrics_at_threshold(probs, labels, thr):
    pred = (probs > thr).astype(int)
    labels = labels.astype(int)
    tp = int(((pred == 1) & (labels == 1)).sum())
    fp = int(((pred == 1) & (labels == 0)).sum())
    fn = int(((pred == 0) & (labels == 1)).sum())
    tn = int(((pred == 0) & (labels == 0)).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return dict(thr=thr, tp=tp, fp=fp, fn=fn, tn=tn, prec=prec, rec=rec, f1=f1)


def pick_high_precision_threshold(probs, labels, target_prec=0.95):
    grid = np.linspace(0.05, 0.99, 95)
    best = None
    for t in grid:
        m = metrics_at_threshold(probs, labels, t)
        if m["prec"] >= target_prec:
            if best is None or m["rec"] > best["rec"]:
                best = m
    if best is None:
        # fall back to max F1
        best = max((metrics_at_threshold(probs, labels, t) for t in grid), key=lambda m: m["f1"])
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()
    print(f"Device: {DEVICE}")

    stats = json.loads(Path(STATS).read_text())
    ch_order = ["lrm_25","lrm_5","slope","tpi_05","openness_pos","openness_neg","roughness_11"]
    mu = np.array([stats[c]["mean"] for c in ch_order], dtype=np.float32)
    sd = np.array([max(stats[c]["std"], 1e-6) for c in ch_order], dtype=np.float32)

    samp = pd.read_csv(SAMPLES)
    print(f"Samples: total={len(samp)}  "
          f"by split: {samp['split'].value_counts().to_dict()}  "
          f"by label: {samp['label'].value_counts().to_dict()}")
    samp = samp[samp.split.isin(["train","val","test"])].copy()

    train_df = samp[samp.split == "train"]
    val_df = samp[samp.split == "val"]
    test_df = samp[samp.split == "test"]
    # pos weight to balance imbalance
    n_pos = (train_df.label == 1).sum(); n_neg = (train_df.label == 0).sum()
    pos_weight = float(n_neg / max(n_pos, 1))
    print(f"train pos={n_pos} neg={n_neg}  pos_weight={pos_weight:.3f}")

    train_loader = DataLoader(PatchDataset(train_df, mu, sd, augment=True),
                              batch_size=args.batch, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(PatchDataset(val_df, mu, sd, augment=False),
                            batch_size=args.batch, shuffle=False, num_workers=0, pin_memory=True)
    test_loader = DataLoader(PatchDataset(test_df, mu, sd, augment=False),
                             batch_size=args.batch, shuffle=False, num_workers=0, pin_memory=True)

    model = RoadCNN(in_ch=N_CH).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"RoadCNN params: {n_params/1e6:.2f} M")
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([1.0/pos_weight if pos_weight>1 else pos_weight], device=DEVICE))
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type=="cuda")

    log = []; best_val_acc = -1.0
    for ep in range(1, args.epochs+1):
        t0 = time.time()
        tr_loss, tr_acc, _, _ = run_epoch(model, train_loader, opt, scaler, criterion, train=True)
        va_loss, va_acc, va_p, va_y = run_epoch(model, val_loader, opt, scaler, criterion, train=False)
        sched.step(); dt = time.time()-t0
        # F1 at 0.5
        m05 = metrics_at_threshold(va_p, va_y, 0.5)
        print(f"ep {ep:2d}/{args.epochs}  tr_loss={tr_loss:.3f} tr_acc={tr_acc:.3f}  "
              f"va_loss={va_loss:.3f} va_acc={va_acc:.3f}  "
              f"val P={m05['prec']:.3f} R={m05['rec']:.3f} F1={m05['f1']:.3f}  {dt:.1f}s")
        log.append({"epoch": ep, "tr_loss": tr_loss, "tr_acc": tr_acc,
                    "va_loss": va_loss, "va_acc": va_acc,
                    "val_p_at_0.5": m05["prec"], "val_r_at_0.5": m05["rec"],
                    "val_f1_at_0.5": m05["f1"], "sec": dt})
        if va_acc > best_val_acc:
            best_val_acc = va_acc
            torch.save({"state_dict": model.state_dict(), "mu": mu, "sd": sd,
                        "channels": ch_order, "patch": PATCH, "epoch": ep},
                       OUTDIR / "best.pt")
    pd.DataFrame(log).to_csv(OUTDIR / "train_log.csv", index=False)

    # Load best, evaluate on test
    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.load_state_dict(ck["state_dict"])
    print(f"\nLoaded best from epoch {ck['epoch']}. Evaluating on test...")
    _, te_acc, te_p, te_y = run_epoch(model, test_loader, opt, scaler, criterion, train=False)
    # Pick threshold on VAL targeting 95% precision, apply to test
    _, _, va_p, va_y = run_epoch(model, val_loader, opt, scaler, criterion, train=False)
    hp = pick_high_precision_threshold(va_p, va_y, target_prec=0.95)
    print(f"Threshold from val @ ~95% prec: thr={hp['thr']:.2f}  val_R={hp['rec']:.3f}")
    te_m = metrics_at_threshold(te_p, te_y, hp["thr"])
    print(f"TEST @ thr={hp['thr']:.2f}:  P={te_m['prec']:.3f}  R={te_m['rec']:.3f}  F1={te_m['f1']:.3f}")
    te_05 = metrics_at_threshold(te_p, te_y, 0.5)
    print(f"TEST @ thr=0.50:           P={te_05['prec']:.3f}  R={te_05['rec']:.3f}  F1={te_05['f1']:.3f}")

    out = {"best_epoch": int(ck["epoch"]),
           "best_val_acc": float(best_val_acc),
           "test_at_hp_thr": te_m, "test_at_05": te_05,
           "hp_thr_from_val": float(hp["thr"]),
           "n_test_samples": int(len(test_df)),
           "n_test_pos": int((test_df.label == 1).sum()),
           "n_test_neg": int((test_df.label == 0).sum())}
    (OUTDIR / "test_metrics.json").write_text(json.dumps(out, indent=2, default=float))
    pd.DataFrame({"x": test_df.x.values, "y": test_df.y.values, "kind": test_df.kind.values,
                  "label": te_y, "prob": te_p}).to_csv(OUTDIR / "test_predictions.csv", index=False)
    print(f"\nOutputs in {OUTDIR}")


if __name__ == "__main__":
    main()
