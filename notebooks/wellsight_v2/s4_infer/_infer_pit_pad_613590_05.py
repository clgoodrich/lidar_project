"""Run the 9t pit and pad U-Nets across 613590, with no retraining.

613590 is the out-of-domain tile. Road and drainage probability rasters for it
already exist; pit and pad did not, only the extracted candidate vectors. This
produces the missing probability surfaces so the two tiles can be compared on
the same footing.

WHY THIS AND NOT `_predict_on_tile.py`
--------------------------------------
That script rebuilds the 7-band stack from the per-channel rasters. For 613590
those channels were removed in the 2026-09-18 cleanup; only the assembled
`features_613590_05.tif` survives (restored from the E: mirror). So this reads
the assembled stack directly and skips the rebuild.

mu and sd come OUT OF THE CHECKPOINT, never off disk. The model has to see
inputs normalised exactly the way they were in training -- recomputing stats on
this tile shifts every input by a couple of percent, nothing errors, and the
numbers quietly get worse.

Outputs (data/613590/derived/inference_05/):
    pit_prob_floor_613590_05.tif    float32, 0-1
    pit_prob_wall_613590_05.tif     float32, 0-1
    pit_argmax_613590_05.tif        uint8, 0 bg / 1 floor / 2 wall
    pad_prob_613590_05.tif          float32, 0-1
    pad_argmax_613590_05.tif        uint8, 0 bg / 1 pad

Run:
    python notebooks/wellsight_v2/s4_infer/_infer_pit_pad_613590_05.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import rasterio
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import make_profile, write_tif  # noqa: E402
from _dl import DEVICE, UNet, predict_full_tile  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FEATURES = ROOT / "data/613590/derived/inference_05/features_613590_05.tif"
OUTDIR = ROOT / "data/613590/derived/inference_05"
SFX = "613590_05"

#: (name, checkpoint, n_classes, patch, overlap) -- patch/overlap copied from
#: _predict_on_tile.TASKS so this matches how the models were run on 9t.
TASKS = [
    ("pit", ROOT / "data/9t/models/pit/unet_v2/best.pt", 3, 256, 64),
    ("pad", ROOT / "data/9t/models/pad/unet/best.pt", 2, 384, 96),
]


def infer(name, ckpt_path, n_classes, patch, overlap):
    print(f"\n=== [{name}] ===")
    ck = torch.load(ckpt_path, map_location=DEVICE, weights_only=False)
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)
    print(f"  ckpt epoch {ck.get('epoch')}  channels {ck['channels']}")

    model = UNet(in_ch=len(ck["channels"]), n_classes=n_classes,
                 base=32).to(DEVICE)
    model.load_state_dict(ck["state_dict"])
    model.eval()

    t0 = time.time()
    prob, argmax, prof = predict_full_tile(
        model, FEATURES, mu, sd, patch=patch, overlap=overlap,
        n_classes=n_classes)
    print(f"  inference {time.time() - t0:.1f}s  -> {argmax.shape}")

    tf, crs = prof["transform"], prof["crs"]
    am = make_profile(width=argmax.shape[1], height=argmax.shape[0],
                      transform=tf, crs=crs, dtype="uint8", nodata=255,
                      bigtiff=True)
    p = OUTDIR / f"{name}_argmax_{SFX}.tif"
    with rasterio.open(p, "w", **am) as ds:
        ds.write(argmax, 1)
    print(f"  wrote {p.name}")

    if name == "pit":
        # 3-class, so "the foreground probability" is ambiguous. Name the floor
        # explicitly and write the wall out separately.
        write_tif(OUTDIR / f"pit_prob_floor_{SFX}.tif", prob[1], transform=tf,
                  crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
        write_tif(OUTDIR / f"pit_prob_wall_{SFX}.tif", prob[2], transform=tf,
                  crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
        print("  wrote pit_prob_floor, pit_prob_wall")
    else:
        write_tif(OUTDIR / f"{name}_prob_{SFX}.tif", prob[1], transform=tf,
                  crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
        print(f"  wrote {name}_prob_{SFX}.tif")

    for c in range(n_classes):
        print(f"    class {c}: {int((argmax == c).sum()):,} px, "
              f"mean p {float(np.nanmean(prob[c])):.4f}")


def main() -> int:
    if not FEATURES.exists():
        raise SystemExit(
            f"missing {FEATURES}\n"
            "Restore it from a mirror: "
            r"E:\Colton\_BACKUPS\lidar_project_MIRROR\<same relative path>")
    with rasterio.open(FEATURES) as r:
        print(f"features: {r.width} x {r.height} @ {r.res[0]:g} m, "
              f"{r.count} bands, {r.crs}")
    OUTDIR.mkdir(parents=True, exist_ok=True)

    for name, ckpt, n_cls, patch, overlap in TASKS:
        if not ckpt.exists():
            print(f"  MISSING checkpoint {ckpt}")
            continue
        infer(name, ckpt, n_cls, patch, overlap)

    print(f"\nDONE. outputs in {OUTDIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
