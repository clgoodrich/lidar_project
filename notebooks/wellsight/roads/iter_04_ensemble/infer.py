"""Road U-Net iter 04 — inference-only ensemble of road iter 01 + road iter 03.

Mirror of pit iter 04. Custom UNet (7ch, iter 01) + SMP-ResNet34 (11ch, iter 03)
ensembled via mean softmax. Each model runs with 8-fold TTA per patch.
"""
import json, time, sys
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window, from_bounds
from rasterio.features import rasterize
import geopandas as gpd
import torch
import segmentation_models_pytorch as smp

sys.path.insert(0, str(Path(__file__).parent.parent))
from _road_unet import D, ANN, LABELS_ROAD, BLOCKS, MANIFEST, DEVICE

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "pits"))
from _pit_unet_v2 import UNet

OUTDIR = D / "iterations" / "road_04_ensemble"; OUTDIR.mkdir(parents=True, exist_ok=True)
FEATURES_7CH = D / "features_pit_9t_05.tif"
FEATURES_11CH = D / "iterations" / "03_multiscale_feats" / "features_pit_v2_9t_05.tif"
CKPT_01 = D / "iterations" / "road_01_tta_miou" / "best.pt"
CKPT_03 = D / "iterations" / "road_03_multiscale_feats" / "best.pt"

PATCH = 256
OV = 64
N_CLASSES = 2
ENCODER_NAME = "resnet34"


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


def load_01():
    ck = torch.load(CKPT_01, map_location=DEVICE, weights_only=False)
    n_ch = len(ck["channels"])
    model = UNet(in_ch=n_ch, n_classes=N_CLASSES, base=32).to(DEVICE)
    model.load_state_dict(ck["state_dict"]); model.eval()
    print(f"[road 01] loaded ep {ck['epoch']} road IoU={ck['iou_road']:.3f}")
    return model, np.asarray(ck["mu"], dtype=np.float32), np.asarray(ck["sd"], dtype=np.float32)


def load_03():
    ck = torch.load(CKPT_03, map_location=DEVICE, weights_only=False)
    n_ch = len(ck["channels"])
    model = smp.Unet(encoder_name=ENCODER_NAME, encoder_weights=None,
                     in_channels=n_ch, classes=N_CLASSES).to(DEVICE)
    model.load_state_dict(ck["state_dict"]); model.eval()
    print(f"[road 03] loaded ep {ck['epoch']} road IoU={ck['iou_road']:.3f}")
    return model, np.asarray(ck["mu"], dtype=np.float32), np.asarray(ck["sd"], dtype=np.float32)


def infer_ensemble():
    model_01, mu_01, sd_01 = load_01()
    model_03, mu_03, sd_03 = load_03()
    with rasterio.open(FEATURES_7CH) as r:
        H, W = r.height, r.width
    step = PATCH - OV
    rs = sorted(set(list(range(0, H - PATCH + 1, step)) + [H - PATCH]))
    cs = sorted(set(list(range(0, W - PATCH + 1, step)) + [W - PATCH]))
    print(f"Inference grid: {len(rs)}x{len(cs)} = {len(rs)*len(cs)} patches (TTA 8x, both models)")
    prob_mean = np.zeros((N_CLASSES, H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)
    src_01 = rasterio.open(FEATURES_7CH)
    src_03 = rasterio.open(FEATURES_11CH)
    BATCH = 8
    buf_x01, buf_x03, buf_pos = [], [], []
    def flush():
        if not buf_x01: return
        x01 = torch.from_numpy(np.stack(buf_x01)).to(DEVICE)
        x03 = torch.from_numpy(np.stack(buf_x03)).to(DEVICE)
        with torch.no_grad():
            p_a = tta_predict_batch(model_01, x01).cpu().numpy()
            p_b = tta_predict_batch(model_03, x03).cpu().numpy()
        p_mean = 0.5 * (p_a + p_b)
        for arr, (r0, c0) in zip(p_mean, buf_pos):
            prob_mean[:, r0:r0+PATCH, c0:c0+PATCH] += arr
            cnt[r0:r0+PATCH, c0:c0+PATCH] += 1
        buf_x01.clear(); buf_x03.clear(); buf_pos.clear()
    t0 = time.time()
    for r0 in rs:
        for c0 in cs:
            win = Window(c0, r0, PATCH, PATCH)
            f01 = src_01.read(window=win).astype(np.float32)
            f01 = np.where(np.isfinite(f01), f01, 0.0)
            f01 = (f01 - mu_01[:, None, None]) / sd_01[:, None, None]
            f03 = src_03.read(window=win).astype(np.float32)
            f03 = np.where(np.isfinite(f03), f03, 0.0)
            f03 = (f03 - mu_03[:, None, None]) / sd_03[:, None, None]
            buf_x01.append(f01); buf_x03.append(f03); buf_pos.append((r0, c0))
            if len(buf_x01) >= BATCH: flush()
    flush(); src_01.close(); src_03.close()
    print(f"  ensemble inference done in {time.time()-t0:.1f}s")
    cnt = np.maximum(cnt, 1); prob_mean = prob_mean / cnt
    argmax = prob_mean.argmax(0).astype(np.uint8)
    with rasterio.open(LABELS_ROAD) as r:
        profile = r.profile.copy()
    p1 = profile.copy()
    p1.update(dtype="float32", count=1, compress="deflate", predictor=3,
              tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES", nodata=-1.0)
    with rasterio.open(OUTDIR / "ensemble_mean_prob.tif", "w", **p1) as d:
        d.write(prob_mean[1], 1)
    p2 = profile.copy()
    p2.update(dtype="uint8", count=1, compress="deflate", predictor=2,
              tiled=True, blockxsize=512, blockysize=512, nodata=255)
    with rasterio.open(OUTDIR / "ensemble_mean_argmax.tif", "w", **p2) as d:
        d.write(argmax, 1)
    return prob_mean, argmax


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
    print(f"Device: {DEVICE}")
    prob, argmax = infer_ensemble()
    test_eval(argmax, prob)
    print(f"Outputs in {OUTDIR}")


if __name__ == "__main__":
    main()
