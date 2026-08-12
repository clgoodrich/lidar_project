"""Generic road-model inference: load any road best.pt and predict a tile.

Reads the channel list from the checkpoint (all our road trainers save it), so
the same CLI serves the recall / corrected / sweep-variant models. Loads into a
plain UNet with strict=False, which also accepts a UNetOrient checkpoint (the
extra orientation-head weights are dropped; the segmentation path is identical
in eval mode).

Writes road_prob.tif, drainage_prob.tif, road_argmax.tif to --outdir.

CLI:
  python -u notebooks/wellsight_v2/s4_infer/_road_infer.py \
      --checkpoint <best.pt> --features <feat.tif> --stats <stats.json> \
      --outdir <dir> [--patch 256 --overlap 64]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import rasterio
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import make_profile, write_tif
from _dl import DEVICE, UNet, load_stats, predict_full_tile

N_CLASSES = 3
# 1 m vs 0.5 m stacks differ only in the 7th channel name.
CH_1M = ("lrm_25", "lrm_5", "slope", "tpi_05",
         "openness_pos", "openness_neg", "roughness_5")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--features", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--patch", type=int, default=256)
    ap.add_argument("--overlap", type=int, default=64)
    a = ap.parse_args()

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    ck = torch.load(a.checkpoint, map_location="cpu", weights_only=False)
    channels = tuple(ck.get("channels", CH_1M))
    print(f"checkpoint ep {ck.get('epoch')} score {ck.get('score')}  "
          f"channels={channels}", flush=True)

    mu, sd = load_stats(Path(a.stats), channels)
    model = UNet(in_ch=len(channels), n_classes=N_CLASSES, base=32)
    missing, unexpected = model.load_state_dict(ck["state_dict"], strict=False)
    if unexpected:
        print(f"  (dropped {len(unexpected)} non-UNet keys, e.g. "
              f"{unexpected[0]})", flush=True)
    model.to(DEVICE)

    prob, argmax, prof = predict_full_tile(
        model, Path(a.features), mu, sd, patch=a.patch, overlap=a.overlap,
        n_classes=N_CLASSES)
    tf, crs = prof["transform"], prof["crs"]
    write_tif(out / "road_prob.tif", prob[1], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    write_tif(out / "drainage_prob.tif", prob[2], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    p = make_profile(width=argmax.shape[1], height=argmax.shape[0],
                     transform=tf, crs=crs, dtype="uint8", nodata=255)
    with rasterio.open(out / "road_argmax.tif", "w", **p) as dst:
        dst.write(argmax, 1)
    print(f"road>=0.5 px = {int((prob[1] >= 0.5).sum()):,}\nDONE -> {out}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
