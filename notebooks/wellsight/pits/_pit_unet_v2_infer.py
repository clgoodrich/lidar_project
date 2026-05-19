"""Run full-tile inference + test-set eval for pit_unet_v2.

Reads:
    data/derivatives/9t/features_pit_9t_05.tif
    data/derivatives/9t/labels_pit_9t_05.tif
    data/derivatives/9t/pit_blocks_9t.gpkg
    data/derivatives/9t/pit_dataset_manifest.csv
    data/derivatives/9t/pit_unet_v2/best.pt

Writes:
    data/derivatives/9t/pit_unet_v2/pit_prob_floor.tif
    data/derivatives/9t/pit_unet_v2/pit_prob_wall.tif
    data/derivatives/9t/pit_unet_v2/pit_argmax.tif
    data/derivatives/9t/pit_unet_v2/test_metrics.json
    data/derivatives/9t/pit_unet_v2/test_preds.png
"""
import json, time
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window, from_bounds
import geopandas as gpd
from rasterio.features import rasterize
import torch
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import sys

sys.path.insert(0, str(Path(__file__).parent))
from _pit_unet_v2 import UNet  # reuse architecture

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
OUTDIR = D / "pit_unet_v2"
FEATURES = D / "features_pit_9t_05.tif"
LABELS = D / "labels_pit_9t_05.tif"
BLOCKS = D / "pit_blocks_9t.gpkg"
MANIFEST = D / "pit_dataset_manifest.csv"
CKPT = OUTDIR / "best.pt"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
PATCH = 256
OVERLAP = 64
N_CLASSES = 3


def predict_full_tile(model, mu, sd):
    with rasterio.open(FEATURES) as r:
        H, W = r.height, r.width
        profile = r.profile.copy()
    step = PATCH - OVERLAP
    prob = np.zeros((N_CLASSES, H, W), dtype=np.float32)
    count = np.zeros((H, W), dtype=np.float32)

    rs = list(range(0, H - PATCH + 1, step))
    cs = list(range(0, W - PATCH + 1, step))
    if rs[-1] != H - PATCH: rs.append(H - PATCH)
    if cs[-1] != W - PATCH: cs.append(W - PATCH)
    print(f"Inference grid: {len(rs)} x {len(cs)} = {len(rs)*len(cs)} patches")

    src = rasterio.open(FEATURES)
    model.eval()
    t0 = time.time()
    BATCH = 16
    buf_x, buf_pos = [], []

    def flush():
        if not buf_x:
            return
        x = torch.from_numpy(np.stack(buf_x)).to(DEVICE)
        with torch.no_grad(), torch.amp.autocast(device_type="cuda", enabled=DEVICE.type=="cuda"):
            p = torch.softmax(model(x), 1).cpu().numpy()
        for arr, (r0, c0) in zip(p, buf_pos):
            prob[:, r0:r0+PATCH, c0:c0+PATCH] += arr
            count[r0:r0+PATCH, c0:c0+PATCH] += 1
        buf_x.clear(); buf_pos.clear()

    for r0 in rs:
        for c0 in cs:
            win = Window(c0, r0, PATCH, PATCH)
            feat = src.read(window=win).astype(np.float32)
            feat = np.where(np.isfinite(feat), feat, 0.0)
            feat = (feat - mu[:, None, None]) / sd[:, None, None]
            buf_x.append(feat); buf_pos.append((r0, c0))
            if len(buf_x) >= BATCH:
                flush()
    flush()
    src.close()
    print(f"Inference done in {time.time()-t0:.1f} s")

    count = np.maximum(count, 1)
    prob = prob / count
    argmax = prob.argmax(0).astype(np.uint8)

    # Write outputs
    p1 = profile.copy()
    p1.update(dtype="float32", count=1, compress="deflate", predictor=3,
              tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES", nodata=-1.0)
    for cls, name in [(1, "pit_prob_floor.tif"), (2, "pit_prob_wall.tif")]:
        with rasterio.open(OUTDIR / name, "w", **p1) as dst:
            dst.write(prob[cls], 1)
        print(f"  wrote {name}")

    p2 = profile.copy()
    p2.update(dtype="uint8", count=1, compress="deflate", predictor=2,
              tiled=True, blockxsize=512, blockysize=512, nodata=255)
    with rasterio.open(OUTDIR / "pit_argmax.tif", "w", **p2) as dst:
        dst.write(argmax, 1)
    print(f"  wrote pit_argmax.tif")

    return prob, argmax


def test_eval(argmax, prob):
    """Pixel- and pit-level metrics restricted to TEST blocks."""
    with rasterio.open(LABELS) as r:
        labels = r.read(1)
        H, W = r.height, r.width
        tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    test_blocks = blocks[blocks.split == "test"]
    test_mask = rasterize([(g, 1) for g in test_blocks.geometry],
                          out_shape=(H, W), transform=tf, fill=0, dtype="uint8").astype(bool)

    # Pixel-level confusion + IoU on test region
    valid = test_mask
    pix_iou = {}
    for cls, name in [(0, "bg"), (1, "floor"), (2, "wall")]:
        p = (argmax == cls) & valid
        t = (labels == cls) & valid
        inter = int((p & t).sum()); union = int((p | t).sum())
        pix_iou[name] = inter / union if union else None
    print(f"\nTEST pixel IoU: bg={pix_iou['bg']:.3f}  "
          f"floor={pix_iou['floor']:.3f}  wall={pix_iou['wall']:.3f}")

    # Per-pit recall: for each test pit's floor pixels, fraction recovered (any pit class)
    man = pd.read_csv(MANIFEST)
    test_pits = man[man.split == "test"]
    pit_in = gpd.read_file(D / "../annotations/annotations_proj.gpkg", layer="pit_inside")
    pit_wall = gpd.read_file(D / "../annotations/annotations_proj.gpkg", layer="pit_wall")

    recall_rows = []
    for _, row in test_pits.iterrows():
        pid = int(row.pit_id)
        # Rasterize this pit's floor + wall locally
        ginner = pit_in[pit_in.pit_id == pid].geometry.iloc[0]
        gwall = pit_wall[pit_wall.pit_id == pid].geometry
        minx, miny, maxx, maxy = ginner.bounds
        pad = 6.0
        win = from_bounds(minx - pad, miny - pad, maxx + pad, maxy + pad, tf)
        r0, c0 = int(win.row_off), int(win.col_off)
        wh, ww = int(win.height), int(win.width)
        r0 = max(r0, 0); c0 = max(c0, 0)
        wh = min(wh, H - r0); ww = min(ww, W - c0)
        if wh <= 0 or ww <= 0:
            continue
        sub_lbl = labels[r0:r0+wh, c0:c0+ww]
        sub_pred = argmax[r0:r0+wh, c0:c0+ww]

        floor_t = sub_lbl == 1
        wall_t = sub_lbl == 2
        pit_t = floor_t | wall_t
        pit_p = (sub_pred == 1) | (sub_pred == 2)
        recall_floor = (floor_t & (sub_pred == 1)).sum() / max(floor_t.sum(), 1)
        recall_wall = (wall_t & (sub_pred == 2)).sum() / max(wall_t.sum(), 1)
        recall_any = (pit_t & pit_p).sum() / max(pit_t.sum(), 1)
        # IoU of pit-vs-bg in this window
        inter = int((pit_t & pit_p).sum()); union = int((pit_t | pit_p).sum())
        pit_iou = inter / union if union else None
        recall_rows.append({"pit_id": pid, "recall_floor": float(recall_floor),
                            "recall_wall": float(recall_wall), "recall_any_pit": float(recall_any),
                            "pit_iou_local": pit_iou})

    df = pd.DataFrame(recall_rows)
    print(f"\nPer-pit recall on TEST ({len(df)} pits):")
    print(df.describe()[["recall_floor", "recall_wall", "recall_any_pit", "pit_iou_local"]]
          .round(3).to_string())
    # Detection counts
    n_detected_any = int((df.recall_any_pit > 0.1).sum())
    print(f"\nPits with any pit pixels predicted (>=10% recall): {n_detected_any}/{len(df)}")
    n_solid = int((df.pit_iou_local > 0.3).sum())
    print(f"Pits with local IoU > 0.3:                          {n_solid}/{len(df)}")

    metrics = {"pixel_iou": pix_iou, "n_test_pits": len(df),
               "n_detected_any": n_detected_any, "n_solid_iou_gt_0.3": n_solid,
               "mean_pit_iou_local": float(df.pit_iou_local.mean()),
               "mean_recall_any_pit": float(df.recall_any_pit.mean())}
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2))
    df.to_csv(OUTDIR / "test_per_pit.csv", index=False)
    print(f"\nWrote test_metrics.json and test_per_pit.csv")
    return df, pix_iou


def render_test_grid(df, argmax, prob, n=8):
    """Side-by-side: hillshade + label, hillshade + prediction. Worst-by-IoU first."""
    df_sorted = df.sort_values("pit_iou_local").head(n).reset_index(drop=True)
    man = pd.read_csv(MANIFEST)
    pit_in = gpd.read_file(D / "../annotations/annotations_proj.gpkg", layer="pit_inside")
    with rasterio.open(D / "hillshade_9t_05.tif") as r:
        tf = r.transform; H, W = r.height, r.width
        hs_full = r.read(1)
    with rasterio.open(LABELS) as r:
        lbl_full = r.read(1)

    cmap_lbl = ListedColormap(["#00000000", "#ff3333aa", "#3399ffaa"])
    cmap_pred = ListedColormap(["#00000000", "#ffaa00cc", "#00ddffcc"])

    fig, axes = plt.subplots(n, 2, figsize=(6, 3*n))
    for i, row in df_sorted.iterrows():
        pid = int(row.pit_id)
        g = pit_in[pit_in.pit_id == pid].geometry.iloc[0]
        minx, miny, maxx, maxy = g.bounds
        pad = 8.0
        win = from_bounds(minx-pad, miny-pad, maxx+pad, maxy+pad, tf)
        r0, c0 = int(win.row_off), int(win.col_off)
        wh, ww = int(win.height), int(win.width)
        r0 = max(r0,0); c0 = max(c0,0)
        wh = min(wh, H-r0); ww = min(ww, W-c0)
        hs = hs_full[r0:r0+wh, c0:c0+ww]
        sub_lbl = lbl_full[r0:r0+wh, c0:c0+ww]
        sub_pred = argmax[r0:r0+wh, c0:c0+ww]

        for ax in axes[i]: ax.set_xticks([]); ax.set_yticks([])
        axes[i,0].imshow(hs, cmap="gray")
        axes[i,0].imshow(sub_lbl, cmap=cmap_lbl, vmin=0, vmax=2, interpolation="nearest")
        axes[i,0].set_title(f"pit {pid}  LABEL  IoU={row.pit_iou_local:.2f}", fontsize=8)
        axes[i,1].imshow(hs, cmap="gray")
        axes[i,1].imshow(sub_pred, cmap=cmap_pred, vmin=0, vmax=2, interpolation="nearest")
        axes[i,1].set_title(f"pit {pid}  PRED  recall_any={row.recall_any_pit:.2f}", fontsize=8)
    plt.tight_layout()
    plt.savefig(OUTDIR / "test_preds.png", dpi=110, bbox_inches="tight")
    plt.close()
    print(f"Wrote test_preds.png ({n} test pits, worst-IoU first)")


def main():
    print(f"Device: {DEVICE}")
    ckpt = torch.load(CKPT, map_location=DEVICE, weights_only=False)
    mu = ckpt["mu"].astype(np.float32)
    sd = ckpt["sd"].astype(np.float32)
    print(f"Loaded checkpoint from epoch {ckpt['epoch']} -> channels: {ckpt['channels']}")
    model = UNet(in_ch=len(ckpt["channels"]), n_classes=N_CLASSES, base=32).to(DEVICE)
    model.load_state_dict(ckpt["state_dict"])

    prob, argmax = predict_full_tile(model, mu, sd)
    df, pix_iou = test_eval(argmax, prob)
    render_test_grid(df, argmax, prob, n=min(8, len(df)))


if __name__ == "__main__":
    main()
