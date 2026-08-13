"""Run the trained road U-Net over every data_3x3 block in a region.

The generic `_predict_on_tile.py` resolves channels from `data/derivatives/<sfx>/`
or the flat layout; the data_3x3 blocks live one level deeper at
`data/derivatives/tiles/data_3x3/<region>/<key>/` with suffix `<key>_1m`, so this
script targets that layout and runs ONLY the road model.

Resolution note: the road U-Net was trained at 0.5 m (roughness_11). The 3x3
blocks are 1 m, so we substitute roughness_5 (closest physical kernel) exactly
as `_predict_on_tile.py` does for 1 m tiles. Cross-resolution inference is an
accepted project approximation.

Per block, writes into the block dir:
    features_<key>_1m.tif     reusable 7-band stack (gitignored *.tif)
    road_prob_<key>_1m.tif    float32 P(road)
    road_argmax_<key>_1m.tif  uint8 0=bg 1=road
    road_overlay_<key>_1m.png hillshade + road overlay

CLI:
  python notebooks/wellsight/build/_infer_roads_data_3x3.py --list
  python notebooks/wellsight/build/_infer_roads_data_3x3.py --only 613590
  python notebooks/wellsight/build/_infer_roads_data_3x3.py            # all blocks
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
import torch
from matplotlib.colors import ListedColormap

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, make_profile, write_tif, path_for
from _dl import DEVICE, UNet, predict_full_tile

TRAINING_CHANNELS = (
    "lrm_25", "lrm_5", "slope", "tpi_05",
    "openness_pos", "openness_neg", "roughness_11",
)
ROAD_CKPT = path_for("nine_t") / "road_unet_1m" / "best.pt"  # 1 m model, matches blocks
# 3-class road model: 0=bg, 1=road, 2=drainage (drainage learned as a class so it
# is no longer predicted as road). See docs/iterations/road_unet_1m.md.
PATCH, OVERLAP, N_CLASSES = 256, 64, 3


def block_dirs(region: str) -> list[Path]:
    root = path_for("data_3x3") / region
    return sorted(p for p in root.iterdir()
                  if p.is_dir() and (p / f"dem_{p.name}_1m.tif").exists())


def find_channels(block: Path, sfx: str) -> list[tuple[str, Path]]:
    """7 channels from the block dir; roughness_11 -> roughness_5 at 1 m."""
    rough = "roughness_11" if sfx.endswith("_05") else "roughness_5"
    out = []
    for name in TRAINING_CHANNELS:
        on_disk = rough if name == "roughness_11" else name
        p = block / f"{on_disk}_{sfx}.tif"
        if not p.exists():
            raise FileNotFoundError(f"{name}: missing {p}")
        out.append((name, p))
    return out


def stack_features(block: Path, sfx: str) -> Path:
    out_path = block / f"features_{sfx}.tif"
    if out_path.exists():
        print(f"  reusing {out_path.name}")
        return out_path
    chans = find_channels(block, sfx)
    with rasterio.open(chans[0][1]) as r0:
        H, W, tf, crs = r0.height, r0.width, r0.transform, r0.crs
    profile = make_profile(width=W, height=H, transform=tf, crs=crs,
                           dtype="float32", nodata=np.nan,
                           count=len(chans), bigtiff=True)
    print(f"  stacking {len(chans)} bands -> {out_path.name} ({W}x{H})")
    with rasterio.open(out_path, "w", **profile) as dst:
        for i, (name, path) in enumerate(chans, start=1):
            with rasterio.open(path) as r:
                arr = r.read(1).astype(np.float32)
                if r.nodata is not None:
                    arr = np.where(arr == r.nodata, np.nan, arr)
            dst.write(arr, i)
            dst.set_band_description(i, name)
    return out_path


def infer_block(block: Path, mu, sd) -> dict:
    key = block.name
    sfx = f"{key}_1m"
    feats = stack_features(block, sfx)
    model = UNet(in_ch=len(mu), n_classes=N_CLASSES, base=32).to(DEVICE)
    ck = torch.load(ROAD_CKPT, map_location=DEVICE, weights_only=False)
    model.load_state_dict(ck["state_dict"])
    t0 = time.time()
    prob, argmax, prof = predict_full_tile(
        model, feats, mu, sd, patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES)
    tf, crs = prof["transform"], prof["crs"]
    am_prof = make_profile(width=argmax.shape[1], height=argmax.shape[0],
                           transform=tf, crs=crs, dtype="uint8", nodata=255,
                           bigtiff=True)
    with rasterio.open(block / f"road_argmax_{sfx}.tif", "w", **am_prof) as ds:
        ds.write(argmax, 1)
    write_tif(block / f"road_prob_{sfx}.tif", prob[1], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    if N_CLASSES >= 3:
        write_tif(block / f"drainage_prob_{sfx}.tif", prob[2], transform=tf,
                  crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
    road_px = int((argmax == 1).sum())
    drain_px = int((argmax == 2).sum())
    total = int(argmax.size)
    # overlay: road (orange) + drainage (cyan) so the split is visible
    with rasterio.open(block / f"hillshade_{sfx}.tif") as r:
        hs = r.read(1); b = r.bounds
    ext = [b.left, b.right, b.bottom, b.top]
    fig, ax = plt.subplots(figsize=(11, 11))
    ax.imshow(hs, cmap="gray", extent=ext)
    if N_CLASSES >= 3:
        ax.imshow(np.ma.masked_where(argmax != 2, argmax),
                  cmap=ListedColormap(["#00d0d0"]), alpha=0.8, vmin=2, vmax=2,
                  interpolation="nearest", extent=ext)
    ax.imshow(np.ma.masked_where(argmax != 1, argmax),
              cmap=ListedColormap(["#ffaa00"]), alpha=0.85, vmin=1, vmax=1,
              interpolation="nearest", extent=ext)
    ax.set_title(f"road inference {sfx}  road {100*road_px/total:.2f}% "
                 f"(orange) | drainage {100*drain_px/total:.2f}% (cyan)")
    ax.set_xlabel("UTM17N E"); ax.set_ylabel("UTM17N N")
    fig.tight_layout()
    fig.savefig(block / f"road_overlay_{sfx}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    dt = time.time() - t0
    print(f"  [{key}] road={road_px} ({100*road_px/total:.2f}%) "
          f"drainage={drain_px} ({100*drain_px/total:.2f}%)  {dt:.1f}s")
    return {"key": key, "road_px": road_px, "drain_px": drain_px,
            "total_px": total, "road_frac": road_px / total, "sec": dt}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="westernpa_d20")
    ap.add_argument("--only", help="comma-separated block keys")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    blocks = block_dirs(args.region)
    if args.only:
        keep = set(args.only.split(","))
        blocks = [b for b in blocks if b.name in keep]
    print(f"{len(blocks)} block(s) in {args.region}: {', '.join(b.name for b in blocks)}")
    if args.list:
        return 0
    if not ROAD_CKPT.exists():
        print(f"missing road ckpt: {ROAD_CKPT}", file=sys.stderr); return 1
    ck = torch.load(ROAD_CKPT, map_location="cpu", weights_only=False)
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)
    print(f"road ckpt ep={ck['epoch']}  channels={ck['channels']}")

    rows = []
    t_all = time.time()
    for blk in blocks:
        print(f"\n=== {blk.name} ===")
        try:
            rows.append(infer_block(blk, mu, sd))
        except Exception as e:
            print(f"  [{blk.name}] FAILED: {e}")
    print(f"\nDONE {len(rows)}/{len(blocks)} in {(time.time()-t_all)/60:.1f} min")
    for r in sorted(rows, key=lambda x: -x["road_frac"]):
        print(f"  {r['key']:>7}  road={100*r['road_frac']:.2f}%  ({r['road_px']} px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
