"""Run trained pit / road / plat U-Nets on a tile suffix's derivative stack.

Generalisation of ``_predict_on_mkf.py``: given a ``--suffix`` (e.g.
``mck_e1423n2238_05``), discovers the 7 channel rasters from the standard
WellSight naming convention, stacks them, and runs all three trained models.

Channel resolution: if the suffix ends in ``_05`` we look for ``roughness_11``
(matches the 0.5 m training); otherwise we fall back to ``roughness_5``
(closest physical kernel at 1 m).

CLI:
  python notebooks/wellsight/build/_predict_on_tile.py --suffix mck_e1423n2238_05

Outputs land under data/derivatives/inference_<suffix>/:
    features_<sfx>.tif          reusable 7-band feature stack
    pit_argmax_<sfx>.tif        uint8: 0=bg 1=floor 2=wall
    pit_prob_floor_<sfx>.tif    float32 prob of class 1
    pit_prob_wall_<sfx>.tif     float32 prob of class 2
    road_argmax_<sfx>.tif       uint8: 0=bg 1=road
    road_prob_<sfx>.tif         float32
    plat_argmax_<sfx>.tif       uint8: 0=bg 1=plat
    plat_prob_<sfx>.tif         float32
    overlay_<sfx>.png           4-panel hillshade + predictions composite
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
from _common import DERIV, make_profile, write_tif
from _dl import DEVICE, UNet, predict_full_tile

# Channel order MUST match what was saved in best.pt['channels']:
TRAINING_CHANNELS = (
    "lrm_25", "lrm_5", "slope", "tpi_05",
    "openness_pos", "openness_neg", "roughness_11",
)

# Per-task config: name, ckpt subdir, n_classes, patch, overlap.
TASKS = [
    ("pit",  "pit_unet_v2", 3, 256, 64),
    ("road", "road_unet",   2, 256, 64),
    ("plat", "plat_unet",   2, 384, 96),
]


def find_channel_files(sfx: str) -> list[tuple[str, Path]]:
    """Resolve the 7 training-channel files for a tile suffix.

    Tries the new layout first
    (``data/derivatives/<sfx>/<channel>_<sfx>.tif``), then falls back to the
    legacy flat layout (``data/derivatives/<channel>_<sfx>.tif``).
    """
    # 0.5 m derivatives use roughness_11; 1 m derivatives use roughness_5.
    rough_band = "roughness_11" if sfx.endswith("_05") else "roughness_5"
    files: list[tuple[str, Path]] = []
    for name in TRAINING_CHANNELS:
        on_disk = rough_band if name == "roughness_11" else name
        candidates = [
            DERIV / "tiles" / sfx / f"{on_disk}_{sfx}.tif",   # new layout (subdir + descriptive name)
            DERIV / f"{on_disk}_{sfx}.tif",          # legacy flat
        ]
        for p in candidates:
            if p.exists():
                files.append((name, p))
                break
        else:
            raise FileNotFoundError(
                f"channel {name} missing: tried {candidates[0]} and {candidates[1]}"
            )
    return files


def stack_features(sfx: str, out_path: Path) -> Path:
    if out_path.exists():
        print(f"reusing existing {out_path.name}")
        return out_path
    channels = find_channel_files(sfx)
    with rasterio.open(channels[0][1]) as r0:
        H, W = r0.height, r0.width
        transform = r0.transform
        crs = r0.crs
    profile = make_profile(
        width=W, height=H, transform=transform, crs=crs,
        dtype="float32", nodata=np.nan,
        count=len(channels), bigtiff=True,
    )
    print(f"stacking {len(channels)} bands -> {out_path.name}  ({W}x{H})")
    with rasterio.open(out_path, "w", **profile) as dst:
        for i, (name, path) in enumerate(channels, start=1):
            with rasterio.open(path) as r:
                arr = r.read(1).astype(np.float32)
                if r.nodata is not None:
                    arr = np.where(arr == r.nodata, np.nan, arr)
            dst.write(arr, i)
            dst.set_band_description(i, name)
            finite = np.isfinite(arr).sum() / arr.size * 100
            print(f"  band {i} {name:14s}  finite={finite:.1f}%  "
                  f"range={np.nanmin(arr):+.3f}..{np.nanmax(arr):+.3f}")
    return out_path


def infer_one(name: str, ckpt: Path, n_classes: int, patch: int, overlap: int,
              features: Path, out_dir: Path, sfx: str) -> np.ndarray:
    print(f"\n=== [{name}] inference ===")
    ck = torch.load(ckpt, map_location=DEVICE, weights_only=False)
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)
    print(f"  ckpt ep={ck['epoch']}  channels={ck['channels']}")
    model = UNet(in_ch=len(ck["channels"]), n_classes=n_classes, base=32).to(DEVICE)
    model.load_state_dict(ck["state_dict"])

    t0 = time.time()
    prob, argmax, prof = predict_full_tile(
        model, features, mu, sd,
        patch=patch, overlap=overlap, n_classes=n_classes,
    )
    print(f"  done in {time.time()-t0:.1f}s")

    tf, crs = prof["transform"], prof["crs"]
    am_profile = make_profile(
        width=argmax.shape[1], height=argmax.shape[0],
        transform=tf, crs=crs, dtype="uint8", nodata=255, bigtiff=True,
    )
    with rasterio.open(out_dir / f"{name}_argmax_{sfx}.tif", "w", **am_profile) as ds:
        ds.write(argmax, 1)
    write_tif(out_dir / f"{name}_prob_{sfx}.tif", prob[1],
              transform=tf, crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
    if name == "pit":
        # rename foreground prob to be explicit, and add wall prob.
        (out_dir / f"pit_prob_{sfx}.tif").rename(out_dir / f"pit_prob_floor_{sfx}.tif")
        write_tif(out_dir / f"pit_prob_wall_{sfx}.tif", prob[2],
                  transform=tf, crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
    return argmax


def render_overlay(argmaps: dict[str, np.ndarray], sfx: str, out_dir: Path) -> None:
    hs_path = DERIV / f"hillshade_{sfx}.tif"
    with rasterio.open(hs_path) as r:
        hs = r.read(1); b = r.bounds
    extent = [b.left, b.right, b.bottom, b.top]
    cmap_pit = ListedColormap(["#00000000", "#ff3333aa", "#3399ffaa"])  # red floor, blue wall
    cmap_bin = ListedColormap(["#00000000", "#ffaa00cc"])               # orange foreground

    fig, axes = plt.subplots(2, 2, figsize=(18, 18))
    axes[0, 0].imshow(hs, cmap="gray", extent=extent)
    axes[0, 0].set_title(f"hillshade {sfx}")
    axes[0, 1].imshow(hs, cmap="gray", extent=extent)
    axes[0, 1].imshow(argmaps["pit"], cmap=cmap_pit, vmin=0, vmax=2,
                      interpolation="nearest", extent=extent)
    axes[0, 1].set_title("pit argmax (red=floor, blue=wall)")
    axes[1, 0].imshow(hs, cmap="gray", extent=extent)
    axes[1, 0].imshow(argmaps["road"], cmap=cmap_bin, vmin=0, vmax=1,
                      interpolation="nearest", extent=extent)
    axes[1, 0].set_title("road argmax (orange)")
    axes[1, 1].imshow(hs, cmap="gray", extent=extent)
    axes[1, 1].imshow(argmaps["plat"], cmap=cmap_bin, vmin=0, vmax=1,
                      interpolation="nearest", extent=extent)
    axes[1, 1].set_title("plat argmax (orange)")
    for ax in axes.ravel():
        ax.set_xlabel("UTM 17N E (m)"); ax.set_ylabel("UTM 17N N (m)")
    fig.suptitle(f"Inference on {sfx}", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    png = out_dir / f"overlay_{sfx}.png"
    fig.savefig(png, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {png}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", required=True,
                    help="Tile suffix matching the per-channel rasters "
                         "(e.g. mck_e1423n2238_05)")
    args = ap.parse_args()

    out_dir = DERIV / f"inference_{args.suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)
    features = stack_features(args.suffix, out_dir / f"features_{args.suffix}.tif")

    argmaps: dict[str, np.ndarray] = {}
    for name, sub, n_cls, patch, overlap in TASKS:
        ckpt = DERIV / "tiles" / "9t" / sub / "best.pt"
        argmaps[name] = infer_one(name, ckpt, n_cls, patch, overlap,
                                  features, out_dir, args.suffix)
    render_overlay(argmaps, args.suffix, out_dir)
    print(f"\nDONE. outputs in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
