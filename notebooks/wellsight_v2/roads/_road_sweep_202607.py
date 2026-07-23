"""Road U-Net top-5 optimization sweep (2026-07-20).

Trains 5 variants, one optimization each, and writes a 9t road_prob.tif per
variant under data/derivatives/tiles/9t/road_sweep_202607/<variant>/. All 1 m
variants also predict 613590 and run the held-out corrections eval. Everything
is seeded (torch/np/random + deterministic algos + fixed val patches) so the
5 can be ranked honestly against run-to-run noise.

Variants (see docs/handoff/ROAD_SWEEP_HANDOFF.md):
  cldice    1m, finetune corrected, FocalCE + 0.3*(1-softclDice) on road class
  alpha078  1m, finetune corrected, FocalCE alpha_road 0.72->0.78
  boundary  1m, finetune corrected, FocalCE with 3x weight on road edges
  orient    1m, SCRATCH, seg head + auxiliary orientation head (8 dir bins)
  res05     0.5m, SCRATCH, FocalCE alpha 0.72, 9t-only (no 613590 0.5m stack)

Baselines for the leaderboard (not retrained): road_unet_1m_recall,
road_unet_1m_corrected.

CLI:
  python -u notebooks/wellsight_v2/roads/_road_sweep_202607.py --variant cldice
  ... --epochs N   override epoch count (smoke test)
  ... --eval-only  re-eval + re-predict from the saved best.pt
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import torch
import torch.nn as nn
import torch.nn.functional as F
from rasterio.features import rasterize
from torch.utils.data import ConcatDataset, DataLoader

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
from _common import DERIV, DERIV_9T, make_profile, write_tif  # noqa: E402
from _dl import (DEVICE, CenteredPatchSampler, FocalCE, UNet, load_stats,  # noqa: E402
                 normalize, predict_full_tile)
from _road_unet_1m_corrected import (  # noqa: E402
    average_precision, evaluate_corrections, sample_line_prob)

SWEEP = DERIV_9T / "road_sweep_202607"
BLOCK = DERIV / "tiles" / "data_3x3" / "westernpa_d20" / "613590"
CORR = BLOCK / "corrections"

# ---- McKean full-extent road labels (1 m) — separate-model experiment ----
# roads.shp has ~137 km of road annotations in McKean beyond the 9t area.
# cfg["mkf"]=True appends these (feature stack + labels + sampled centers)
# to the TRAIN set only; val stays 9t so metrics remain comparable.
MKF_DIR = DERIV / "tiles" / "mkf_road_1m"
MKF_F = MKF_DIR / "features_mkf_road_1m.tif"
MKF_L = MKF_DIR / "labels_road_mkf_road_1m.tif"
MKF_CENTERS = MKF_DIR / "mkf_road_centers.csv"

# ---- shared 9t inputs (1 m) ----
F1 = DERIV_9T / "features_pit_9t_1m.tif"
L1 = DERIV_9T / "labels_road_9t_1m.tif"
S1 = DERIV_9T / "feature_stats_1m.json"
CH1 = ("lrm_25", "lrm_5", "slope", "tpi_05",
       "openness_pos", "openness_neg", "roughness_5")
# ---- 9t inputs (0.5 m) ----
F05 = DERIV_9T / "features_pit_9t_05.tif"
L05 = DERIV_9T / "labels_road_9t_05.tif"
S05 = DERIV_9T / "feature_stats.json"
CH05 = ("lrm_25", "lrm_5", "slope", "tpi_05",
        "openness_pos", "openness_neg", "roughness_11")
# ---- shared vector eval assets (resolution-independent) ----
BLOCKS = DERIV_9T / "pit_blocks_9t.gpkg"
MANIFEST = DERIV_9T / "road_dataset_manifest.csv"
CHUNKS = DERIV_9T / "road_chunks_9t.gpkg"
# ---- 613590 corrections (1 m) ----
CORR_F = BLOCK / "features_613590_1m.tif"
CORR_L = CORR / "labels_road_corr_613590_1m.tif"
CORR_CENTERS = CORR / "correction_centers_613590.csv"
CORR_CELLS = CORR / "correction_split_cells_613590.gpkg"
# ---- orientation labels (built by _build_orient_labels.py) ----
ORI_9T = DERIV_9T / "labels_roadorient_9t_1m.tif"
ORI_CORR = CORR / "labels_roadorient_corr_613590_1m.tif"

CORRECTED = DERIV_9T / "road_unet_1m_corrected" / "best.pt"
BASELINE_PROB = DERIV_9T / "road_unet_1m_recall" / "road_prob_613590_1m.tif"

PATCH, OVERLAP, N_CLASSES = 256, 64, 3
JITTER_M = 30.0
GAMMA = 2.0
WD = 2e-4
KEPT_CAP = 1200
N_ORI = 8            # orientation direction bins over 0..180 deg
SEED = 1234

VARIANTS = {
    "cldice":   dict(res="1m", init="corrected", loss="cldice",
                     model="unet", ep=12, lr=2e-4, corr=True, alpha=(0.10, 0.72, 0.25)),
    "alpha078": dict(res="1m", init="corrected", loss="focal",
                     model="unet", ep=12, lr=2e-4, corr=True, alpha=(0.10, 0.78, 0.25)),
    "boundary": dict(res="1m", init="corrected", loss="boundary",
                     model="unet", ep=12, lr=2e-4, corr=True, alpha=(0.10, 0.72, 0.25)),
    "orient":   dict(res="1m", init="scratch", loss="orient",
                     model="orient", ep=30, lr=1e-3, corr=True, alpha=(0.10, 0.72, 0.25)),
    "res05":    dict(res="05", init="scratch", loss="focal",
                     model="unet", ep=30, lr=1e-3, corr=False, alpha=(0.10, 0.72, 0.25)),
}


# ===========================================================================
# seeding
# ===========================================================================
def seed_all(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.benchmark = False


# ===========================================================================
# losses
# ===========================================================================
def _soft_erode(x):      # min-pool 3x3
    return -F.max_pool2d(-x, 3, 1, 1)


def _soft_dilate(x):
    return F.max_pool2d(x, 3, 1, 1)


def _soft_skel(x, iters=6):
    """Soft skeleton (Shit et al. 2021). x: (B,1,H,W) in [0,1]."""
    x1 = _soft_dilate(_soft_erode(x))
    skel = F.relu(x - x1)
    for _ in range(iters):
        x = _soft_erode(x)
        x1 = _soft_dilate(_soft_erode(x))
        d = F.relu(x - x1)
        skel = skel + F.relu(d - skel * d)
    return skel


class ClDiceFocal(nn.Module):
    """FocalCE + w*(1 - soft clDice) on the road class (ignore-safe)."""

    def __init__(self, alpha, gamma=GAMMA, w=0.3, iters=6, ignore=255):
        super().__init__()
        self.focal = FocalCE(alpha=alpha, gamma=gamma, ignore=ignore)
        self.w, self.iters, self.ignore = w, iters, ignore

    def forward(self, logits, target):
        loss = self.focal(logits, target)
        valid = (target != self.ignore).float().unsqueeze(1)
        p_road = torch.softmax(logits, 1)[:, 1:2] * valid
        t_road = ((target == 1).float().unsqueeze(1)) * valid
        if t_road.sum() < 1:
            return loss
        sk_p, sk_t = _soft_skel(p_road, self.iters), _soft_skel(t_road, self.iters)
        tprec = (torch.sum(sk_p * t_road) + 1.0) / (torch.sum(sk_p) + 1.0)
        tsens = (torch.sum(sk_t * p_road) + 1.0) / (torch.sum(sk_t) + 1.0)
        cldice = 2.0 * tprec * tsens / (tprec + tsens)
        return loss + self.w * (1.0 - cldice)


class BoundaryFocal(nn.Module):
    """FocalCE with per-pixel weight 3x within 1 px of a road-class edge."""

    def __init__(self, alpha, gamma=GAMMA, edge_w=3.0, ignore=255):
        super().__init__()
        self.gamma, self.ignore, self.edge_w = gamma, ignore, edge_w
        self.register_buffer("alpha", torch.tensor(alpha, dtype=torch.float32))

    def forward(self, logits, target):
        log_p = F.log_softmax(logits, 1)
        p = log_p.exp()
        valid = target != self.ignore
        t = target.clone()
        t[~valid] = 0
        oh = F.one_hot(t, logits.shape[1]).permute(0, 3, 1, 2).float()
        focal = (1 - p) ** self.gamma
        a = self.alpha.view(1, -1, 1, 1)
        per_pix = -(oh * a * focal * log_p).sum(1)           # (B,H,W)
        road = (target == 1).float().unsqueeze(1)
        edge = (_soft_dilate(road) - road).squeeze(1) > 0     # 1-px road ring
        w = torch.ones_like(per_pix)
        w[edge] = self.edge_w
        if not bool(valid.any()):
            return (logits * 0.0).sum()
        return (per_pix * w)[valid].mean()


# ===========================================================================
# orientation model + sampler
# ===========================================================================
class UNetOrient(UNet):
    """UNet + auxiliary orientation head off the final decoder feature.

    Training: forward returns (seg_logits, orient_logits).
    Eval:     forward returns seg_logits only (so predict_full_tile works)."""

    def __init__(self, in_ch=7, n_classes=3, base=32, n_ori=N_ORI):
        super().__init__(in_ch, n_classes, base)
        self.ori = nn.Conv2d(base, n_ori, 1)

    def forward(self, x):
        d1 = self.d1(x)
        d2 = self.d2(self.pool(d1))
        d3 = self.d3(self.pool(d2))
        d4 = self.d4(self.pool(d3))
        b = self.bot(self.pool(d4))
        u4 = self.u4(torch.cat([self.up4(b), d4], 1))
        u3 = self.u3(torch.cat([self.up3(u4), d3], 1))
        u2 = self.u2(torch.cat([self.up2(u3), d2], 1))
        u1 = self.u1(torch.cat([self.up1(u2), d1], 1))
        seg = self.out(u1)
        if self.training:
            return seg, self.ori(u1)
        return seg


class OrientSampler(CenteredPatchSampler):
    """Like CenteredPatchSampler but returns (feat, seg_lbl, orient_lbl)."""

    def __init__(self, *a, ori_path, **kw):
        super().__init__(*a, **kw)
        self.ori_path = ori_path
        self._ori = None

    def __getitem__(self, idx):
        self._open()
        if self._ori is None:
            self._ori = rasterio.open(self.ori_path)
        cx, cy = self._pick_center(idx)
        row, col = self._world_to_rowcol(cx, cy)
        H, W = self._feat.height, self._feat.width
        from rasterio.windows import Window
        r0 = int(np.clip(row - self.patch // 2, 0, H - self.patch))
        c0 = int(np.clip(col - self.patch // 2, 0, W - self.patch))
        win = Window(c0, r0, self.patch, self.patch)
        feat = self._feat.read(window=win).astype(np.float32)
        lbl = self._lbl.read(1, window=win).astype(np.int64)
        ori = self._ori.read(1, window=win).astype(np.int64)
        feat = normalize(feat, self.mu, self.sd)
        if self.augment:
            # D4 on feat+lbl only; orientation bins are direction-sensitive so
            # we skip geometric aug for the orient variant (keep it simple/honest)
            pass
        return (torch.from_numpy(feat), torch.from_numpy(lbl),
                torch.from_numpy(ori))


# ===========================================================================
# datasets
# ===========================================================================
def nine_t_policies(split, manifest, blocks):
    m = manifest[manifest.split == split]
    pol = []
    for kind in ("road", "not_road", "drainage"):
        pts = m.loc[m.kind == kind, ["mid_x", "mid_y"]].to_numpy()
        if len(pts):
            pol.append((kind, pts, JITTER_M))
    bounds = np.array([g.bounds for g in
                       blocks.loc[blocks.split == split].geometry])
    return pol, bounds


def corr_policies(split, centers, cells):
    c = centers[centers.split == split]
    rng = np.random.default_rng(11)
    pol = []
    for kind in ("added", "reject", "kept"):
        pts = c.loc[c.kind == kind, ["x", "y"]].to_numpy()
        if kind == "kept" and len(pts) > KEPT_CAP:
            pts = pts[rng.choice(len(pts), KEPT_CAP, replace=False)]
        if len(pts):
            pol.append((kind, pts, JITTER_M))
    bounds = np.array([g.bounds for g in
                       cells.loc[cells.split == split].geometry])
    return pol, bounds


def mkf_policies(centers_csv, feat_path):
    """McKean centers: patches centered on road pixels + sampled background."""
    c = pd.read_csv(centers_csv)
    pol = []
    for kind in ("road", "not_road"):
        pts = c.loc[c.kind == kind, ["x", "y"]].to_numpy()
        if len(pts):
            pol.append((kind, pts, JITTER_M))
    with rasterio.open(feat_path) as r:
        b = r.bounds
    bounds = np.array([[b.left, b.bottom, b.right, b.top]])
    return pol, bounds


def build_datasets(cfg, mu, sd):
    """Returns (train_ds, val_ds, dual)."""
    res = cfg["res"]
    feat, lbl = (F1, L1) if res == "1m" else (F05, L05)
    tf = rasterio.open(feat).transform
    manifest = pd.read_csv(MANIFEST)
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    dual = cfg["model"] == "orient"

    def mk(pol, bounds, path_f, path_l, seed, augment, ori_path=None):
        if dual:
            return OrientSampler(
                feat_path=path_f, lbl_path=path_l, policies=pol,
                block_bounds=bounds, transform=rasterio.open(path_f).transform,
                mu=mu, sd=sd, patch=PATCH, augment=augment, seed=seed,
                ori_path=ori_path)
        return CenteredPatchSampler(
            feat_path=path_f, lbl_path=path_l, policies=pol,
            block_bounds=bounds, transform=rasterio.open(path_f).transform,
            mu=mu, sd=sd, patch=PATCH, augment=augment, seed=seed)

    pol9, b9 = nine_t_policies("train", manifest, blocks)
    tr9 = mk(pol9, b9, feat, lbl, 42, True, ORI_9T)
    train_sets = [tr9]
    if cfg["corr"]:
        centers = pd.read_csv(CORR_CENTERS)
        cells = gpd.read_file(CORR_CELLS, layer="cells")
        polc, bc = corr_policies("train", centers, cells)
        trc = mk(polc, bc, CORR_F, CORR_L, 44, True, ORI_CORR)
        train_sets.append(trc)
    if cfg.get("mkf"):
        # McKean full-extent roads -> TRAIN only. Seg-only (no orient labels
        # there); force a plain CenteredPatchSampler even if the model is dual.
        polm, bm = mkf_policies(MKF_CENTERS, MKF_F)
        trm = CenteredPatchSampler(
            feat_path=str(MKF_F), lbl_path=str(MKF_L), policies=polm,
            block_bounds=bm, transform=rasterio.open(MKF_F).transform,
            mu=mu, sd=sd, patch=PATCH, augment=True, seed=46)
        train_sets.append(trm)
        print(f"  + McKean train set: {sum(len(p[1]) for p in polm)} centers")
    train_ds = ConcatDataset(train_sets) if len(train_sets) > 1 else train_sets[0]

    # val is always seg-only single-head (eval mode), deterministic
    polv, bv = nine_t_policies("val", manifest, blocks)
    val_ds = CenteredPatchSampler(
        feat_path=feat, lbl_path=lbl, policies=polv, block_bounds=bv,
        transform=tf, mu=mu, sd=sd, patch=PATCH, augment=False, seed=43)
    return train_ds, val_ds, dual, train_sets


# ===========================================================================
# train loop (seeded; single- or dual-head)
# ===========================================================================
def road_iou_val(model, val_ds, batch=16):
    """Deterministic val road-class IoU (resets sampler RNG for fixed patches)."""
    val_ds._rng = None; val_ds._feat = None; val_ds._lbl = None
    loader = DataLoader(val_ds, batch_size=batch, shuffle=False, num_workers=0)
    model.eval()
    inter = union = 0
    with torch.no_grad(), torch.amp.autocast("cuda", enabled=DEVICE.type == "cuda"):
        for x, y in loader:
            x = x.to(DEVICE); y = y.to(DEVICE)
            pred = model(x).argmax(1)
            pm, tm = pred == 1, y == 1
            inter += int((pm & tm).sum()); union += int((pm | tm).sum())
    return inter / union if union else 0.0


def train_variant(model, train_ds, val_ds, loss_fn, cfg, out_dir, dual,
                  ori_w=0.3):
    out_dir.mkdir(parents=True, exist_ok=True)
    g = torch.Generator(); g.manual_seed(SEED)
    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True,
                              num_workers=2, pin_memory=True,
                              persistent_workers=True, generator=g)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=WD)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg["ep"])
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type == "cuda")
    ori_ce = nn.CrossEntropyLoss(ignore_index=255)
    model.to(DEVICE); loss_fn.to(DEVICE)
    best, rows = -1.0, []
    for ep in range(1, cfg["ep"] + 1):
        model.train()
        t0 = time.time(); tot = 0.0; nb = 0
        for batch in train_loader:
            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=DEVICE.type == "cuda"):
                if dual:
                    x, y, yori = batch
                    x = x.to(DEVICE); y = y.to(DEVICE); yori = yori.to(DEVICE)
                    seg, ori = model(x)
                    loss = loss_fn(seg, y) + ori_w * ori_ce(ori, yori)
                else:
                    x, y = batch
                    x = x.to(DEVICE); y = y.to(DEVICE)
                    loss = loss_fn(model(x), y)
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update()
            tot += float(loss); nb += 1
        sched.step()
        score = road_iou_val(model, val_ds)
        dt = time.time() - t0
        print(f"ep {ep:3d}/{cfg['ep']}  tr_loss={tot/max(nb,1):.4f}  "
              f"val_road_iou={score:.4f}  {dt:.1f}s", flush=True)
        rows.append({"epoch": ep, "tr_loss": tot / max(nb, 1),
                     "val_road_iou": score, "sec": dt})
        if score > best:
            best = score
            torch.save({"state_dict": model.state_dict(), "epoch": ep,
                        "score": score, "variant": cfg.get("_name"),
                        "channels": cfg["_channels"]},
                       out_dir / "best.pt")
            print(f"    -> new best {score:.4f}", flush=True)
    pd.DataFrame(rows).to_csv(out_dir / "train_log.csv", index=False)
    return best


# ===========================================================================
# evaluation
# ===========================================================================
def evaluate_9t_res(prob, argmax, label_path):
    with rasterio.open(label_path) as r:
        labels = r.read(1); H, W, tf = r.height, r.width, r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    tmask = rasterize(
        [(g, 1) for g in blocks.loc[blocks.split == "test", "geometry"]],
        out_shape=(H, W), transform=tf, fill=0, dtype="uint8").astype(bool)
    p, t = argmax == 1, labels == 1
    union = int(((p | t) & tmask).sum())
    pix_iou = int((p & t & tmask).sum()) / union if union else None
    ct = gpd.read_file(CHUNKS, layer="chunks")
    ct = ct[ct.split == "test"]

    def lp(line, cls=1):
        if line is None or line.is_empty:
            return 0.0
        n = max(2, int(line.length)); v = []
        for i in range(n + 1):
            pt = line.interpolate(min(i, line.length))
            r0 = int(round((pt.y - tf.f) / tf.e))
            c0 = int(round((pt.x - tf.c) / tf.a))
            if 0 <= r0 < H and 0 <= c0 < W:
                v.append(float(prob[cls, r0, c0]))
        return float(np.mean(v)) if v else 0.0

    df = pd.DataFrame([{"kind": r.kind, "p": lp(r.geometry)}
                      for _, r in ct.iterrows()])

    def apv(neg):
        s = df[df.kind.isin(["road", neg])]
        if not len(s) or s.kind.nunique() < 2:
            return None
        return average_precision(s.p.to_numpy(),
                                 (s.kind == "road").astype(int).to_numpy())
    return {"pixel_iou_road_test": pix_iou,
            "ap_road_vs_not_road": apv("not_road"),
            "ap_road_vs_drainage": apv("drainage"),
            "mean_Proad_on_road_test": float(df[df.kind == "road"].p.mean()),
            "mean_Proad_on_drainage_test":
                float(df[df.kind == "drainage"].p.mean())
                if (df.kind == "drainage").any() else None}


# ===========================================================================
# driver
# ===========================================================================
def run_variant(name, epochs_override=None, eval_only=False):
    cfg = dict(VARIANTS[name]); cfg["_name"] = name
    if epochs_override:
        cfg["ep"] = epochs_override
    res = cfg["res"]
    feat, lbl, stats, chans = ((F1, L1, S1, CH1) if res == "1m"
                               else (F05, L05, S05, CH05))
    cfg["_channels"] = list(chans)
    out_dir = SWEEP / name
    out_dir.mkdir(parents=True, exist_ok=True)
    mu, sd = load_stats(stats, chans)
    seed_all()

    if cfg["model"] == "orient":
        model = UNetOrient(in_ch=len(chans), n_classes=N_CLASSES, base=32)
    else:
        model = UNet(in_ch=len(chans), n_classes=N_CLASSES, base=32)

    if not eval_only:
        if cfg["init"] == "corrected":
            ck = torch.load(CORRECTED, map_location="cpu", weights_only=False)
            model.load_state_dict(ck["state_dict"], strict=False)
            print(f"[{name}] finetune from corrected (ep {ck['epoch']}, "
                  f"IoU {ck['score']:.3f}); loss={cfg['loss']} ep={cfg['ep']} "
                  f"lr={cfg['lr']}", flush=True)
        else:
            print(f"[{name}] scratch; loss={cfg['loss']} ep={cfg['ep']} "
                  f"lr={cfg['lr']} res={res}", flush=True)

        train_ds, val_ds, dual, tsets = build_datasets(cfg, mu, sd)
        print(f"[{name}] train tiles/ep="
              f"{sum(len(t) for t in tsets)} dual={dual}", flush=True)
        alpha = tuple(cfg["alpha"])
        if cfg["loss"] == "cldice":
            loss_fn = ClDiceFocal(alpha=alpha, w=cfg.get("cldice_w", 0.3),
                                  iters=int(cfg.get("cldice_iters", 6)))
        elif cfg["loss"] == "boundary":
            loss_fn = BoundaryFocal(alpha=alpha, edge_w=cfg.get("edge_w", 3.0))
        else:
            loss_fn = FocalCE(alpha=alpha, gamma=cfg.get("gamma", GAMMA))
        best = train_variant(model, train_ds, val_ds, loss_fn, cfg,
                             out_dir, dual, ori_w=cfg.get("ori_w", 0.3))
        print(f"[{name}] best val road IoU {best:.4f}", flush=True)

    ck = torch.load(out_dir / "best.pt", map_location=DEVICE, weights_only=False)
    if cfg["model"] == "orient":
        model = UNetOrient(in_ch=len(chans), n_classes=N_CLASSES, base=32)
    else:
        model = UNet(in_ch=len(chans), n_classes=N_CLASSES, base=32)
    model.to(DEVICE).load_state_dict(ck["state_dict"])
    print(f"[{name}] loaded best ep {ck['epoch']} (IoU {ck['score']:.3f})",
          flush=True)

    prob, argmax, prof = predict_full_tile(model, feat, mu, sd, patch=PATCH,
                                           overlap=OVERLAP, n_classes=N_CLASSES)
    write_tif(out_dir / "road_prob.tif", prob[1], transform=prof["transform"],
              crs=prof["crs"], dtype="float32", nodata=-1.0, bigtiff=True)
    m9 = evaluate_9t_res(prob, argmax, lbl)
    print(f"[{name}] 9t test: " + "  ".join(
        f"{k}={v:.4f}" for k, v in m9.items() if v is not None), flush=True)

    corr = None
    if cfg["corr"]:
        pc, ac, pfc = predict_full_tile(model, CORR_F, mu, sd, patch=PATCH,
                                        overlap=OVERLAP, n_classes=N_CLASSES)
        op = out_dir / "road_prob_613590_1m.tif"
        write_tif(op, pc[1], transform=pfc["transform"], crs=pfc["crs"],
                  dtype="float32", nodata=-1.0, bigtiff=True)
        write_tif(out_dir / "drainage_prob_613590_1m.tif", pc[2],
                  transform=pfc["transform"], crs=pfc["crs"], dtype="float32",
                  nodata=-1.0, bigtiff=True)
        corr = evaluate_corrections(op, prob_before=BASELINE_PROB)
        for split in ("val", "test"):
            for kind in ("added", "reject"):
                d = corr[split].get(kind)
                if d:
                    print(f"[{name}] {split} {kind}: P {d['mean_Proad_before']:.3f}"
                          f"->{d['mean_Proad_after']:.3f}", flush=True)

    metrics = {"variant": name, "config": {k: v for k, v in cfg.items()
                                           if not k.startswith("_")},
               "best_epoch": ck["epoch"], "val_road_iou": ck["score"],
               "9t_test": m9, "corrections_613590": corr,
               "channels": list(chans), "res": res}
    (out_dir / "test_metrics.json").write_text(
        json.dumps(metrics, indent=2, default=float))
    print(f"[{name}] DONE -> {out_dir}", flush=True)


def register_config(cfg: dict) -> str:
    """Register a custom variant from a config dict (from Model Lab) and return
    its name. `base` (optional) names a preset to inherit defaults from; every
    other key overrides. Requires a unique `name`."""
    name = cfg.get("name") or cfg.get("_name")
    if not name:
        raise SystemExit("custom config needs a 'name'")
    base = dict(VARIANTS.get(cfg.get("base", ""), VARIANTS["cldice"]))
    base.update({k: v for k, v in cfg.items()
                 if k not in ("name", "base")})
    VARIANTS[name] = base
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=list(VARIANTS),
                    help="run a built-in preset")
    ap.add_argument("--config", type=str, default=None,
                    help="path to a custom variant JSON (from Model Lab)")
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--eval-only", action="store_true")
    a = ap.parse_args()
    if a.config:
        cfg = json.loads(Path(a.config).read_text())
        name = register_config(cfg)
        run_variant(name, a.epochs, a.eval_only)
    elif a.variant:
        run_variant(a.variant, a.epochs, a.eval_only)
    else:
        ap.error("give --variant NAME or --config PATH")


if __name__ == "__main__":
    main()
