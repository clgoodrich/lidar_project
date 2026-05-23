"""Smoke-test inference of the trained pit / road / plat U-Nets on the
existing McKean (mkf) derivative stack at 1 m.

Caveats (explicit, see chat thread): models were trained at 0.5 m; mkf is at
1 m. Feature semantics shift -> outputs are approximate. ``roughness_5_mkf_1m``
is substituted for the ``roughness_11`` channel (similar physical kernel).

Outputs land under data/derivatives/mck_inference/:
    features_mkf_1m.tif         (7 bands, float32, NaN nodata) - reusable stack
    pit_argmax_mkf_1m.tif       uint8 0=bg 1=floor 2=wall
    pit_prob_floor_mkf_1m.tif   float32 prob of class 1
    road_argmax_mkf_1m.tif      uint8 0=bg 1=road
    road_prob_mkf_1m.tif        float32 prob of class 1
    plat_argmax_mkf_1m.tif      uint8 0=bg 1=plat
    plat_prob_mkf_1m.tif        float32 prob of class 1
    overlay_mkf_1m.png          hillshade composite with the three classes
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
import torch
from matplotlib.colors import ListedColormap

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, make_profile, write_tif
from _dl import DEVICE, UNet, predict_full_tile

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUT_DIR = DERIV / "mck_inference"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Channel order MUST match what was saved in best.pt['channels']:
#   ['lrm_25', 'lrm_5', 'slope', 'tpi_05', 'openness_pos', 'openness_neg', 'roughness_11']
# For mkf at 1 m we use roughness_5_mkf_1m as the closest physical match.
MKF_CHANNELS: list[tuple[str, Path]] = [
    ("lrm_25",       DERIV / "lrm_25_mkf_1m.tif"),
    ("lrm_5",        DERIV / "lrm_5_mkf_1m.tif"),
    ("slope",        DERIV / "slope_mkf_1m.tif"),
    ("tpi_05",       DERIV / "tpi_05_mkf_1m.tif"),
    ("openness_pos", DERIV / "openness_pos_mkf_1m.tif"),
    ("openness_neg", DERIV / "openness_neg_mkf_1m.tif"),
    ("roughness_11", DERIV / "roughness_5_mkf_1m.tif"),  # 5-cell @ 1 m ≈ 11-cell @ 0.5 m
]

FEATURES_OUT = OUT_DIR / "features_mkf_1m.tif"
HILLSHADE = DERIV / "hillshade_mkf_1m.tif"

TASKS = [
    # name,  checkpoint,                                    n_cls, patch, overlap
    ("pit",  DERIV / "9t" / "pit_unet_v2" / "best.pt",          3,   256,   64),
    ("road", DERIV / "9t" / "road_unet"   / "best.pt",          2,   256,   64),
    ("plat", DERIV / "9t" / "plat_unet"   / "best.pt",          2,   384,   96),
]


# ---------------------------------------------------------------------------
# Stage 1: stack the mkf channels into a multi-band feature raster
# ---------------------------------------------------------------------------

def stack_features() -> None:
    if FEATURES_OUT.exists():
        print(f"reusing existing {FEATURES_OUT.name}")
        return

    missing = [p for _, p in MKF_CHANNELS if not p.exists()]
    if missing:
        raise FileNotFoundError(f"missing mkf derivatives: {missing}")

    with rasterio.open(MKF_CHANNELS[0][1]) as r0:
        H, W = r0.height, r0.width
        transform = r0.transform
        src_crs = r0.crs
    crs = src_crs or DST_CRS  # mkf tifs already in EPSG:6346, fall back gracefully

    profile = make_profile(
        width=W, height=H, transform=transform, crs=crs,
        dtype="float32", nodata=np.nan,
        count=len(MKF_CHANNELS), bigtiff=True,
    )

    print(f"stacking {len(MKF_CHANNELS)} bands -> {FEATURES_OUT.name}  ({W}x{H})")
    with rasterio.open(FEATURES_OUT, "w", **profile) as dst:
        for i, (name, path) in enumerate(MKF_CHANNELS, start=1):
            with rasterio.open(path) as r:
                arr = r.read(1).astype(np.float32)
                if r.nodata is not None:
                    arr = np.where(arr == r.nodata, np.nan, arr)
            dst.write(arr, i)
            dst.set_band_description(i, name)
            finite = np.isfinite(arr).sum() / arr.size * 100
            print(f"  band {i} {name:14s}  finite={finite:.1f}%  range="
                  f"{np.nanmin(arr):+.3f}..{np.nanmax(arr):+.3f}")


# ---------------------------------------------------------------------------
# Stage 2: per-task inference
# ---------------------------------------------------------------------------

def infer_one(name: str, ckpt_path: Path, n_classes: int, patch: int, overlap: int):
    """Load best.pt, run predict_full_tile on FEATURES_OUT, write argmax + prob."""
    print(f"\n=== [{name}] inference ===")
    ck = torch.load(ckpt_path, map_location=DEVICE, weights_only=False)
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)
    print(f"  ckpt ep={ck['epoch']}  channels={ck['channels']}")

    model = UNet(in_ch=len(ck["channels"]), n_classes=n_classes, base=32).to(DEVICE)
    model.load_state_dict(ck["state_dict"])

    t0 = time.time()
    prob, argmax, prof = predict_full_tile(
        model, FEATURES_OUT, mu, sd,
        patch=patch, overlap=overlap, n_classes=n_classes,
    )
    print(f"  done in {time.time()-t0:.1f}s")

    tf, crs = prof["transform"], prof["crs"]
    # Argmax raster (uint8).
    am_profile = make_profile(
        width=argmax.shape[1], height=argmax.shape[0],
        transform=tf, crs=crs, dtype="uint8", nodata=255, bigtiff=True,
    )
    with rasterio.open(OUT_DIR / f"{name}_argmax_mkf_1m.tif", "w", **am_profile) as ds:
        ds.write(argmax, 1)

    # Foreground probability for the most-interesting positive class.
    pos_class = 1 if n_classes == 2 else 1  # pit: class 1 = floor (the more diagnostic class)
    write_tif(
        OUT_DIR / f"{name}_prob_mkf_1m.tif", prob[pos_class],
        transform=tf, crs=crs, dtype="float32", nodata=-1.0, bigtiff=True,
    )
    # For pit, additionally save wall prob (class 2).
    if name == "pit":
        write_tif(
            OUT_DIR / "pit_prob_wall_mkf_1m.tif", prob[2],
            transform=tf, crs=crs, dtype="float32", nodata=-1.0, bigtiff=True,
        )
        # And rename the foreground prob to be explicit.
        (OUT_DIR / "pit_prob_mkf_1m.tif").rename(OUT_DIR / "pit_prob_floor_mkf_1m.tif")

    return argmax


# ---------------------------------------------------------------------------
# Stage 3: composite overlay PNG
# ---------------------------------------------------------------------------

def render_overlay(argmaps: dict[str, np.ndarray]) -> None:
    with rasterio.open(HILLSHADE) as r:
        hs = r.read(1)
        bounds = r.bounds
    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

    # Colour ramps: bg transparent, classes opaque-ish.
    cmap_pit = ListedColormap(["#00000000", "#ff3333aa", "#3399ffaa"])   # floor red, wall blue
    cmap_bin = ListedColormap(["#00000000", "#ffaa00cc"])                # road / plat orange

    fig, axes = plt.subplots(2, 2, figsize=(18, 18))

    # Panel 0: hillshade alone for reference.
    axes[0, 0].imshow(hs, cmap="gray", extent=extent)
    axes[0, 0].set_title("mkf hillshade (1 m)")

    # Panel 1: pit (3 classes).
    axes[0, 1].imshow(hs, cmap="gray", extent=extent)
    axes[0, 1].imshow(argmaps["pit"], cmap=cmap_pit, vmin=0, vmax=2,
                      interpolation="nearest", extent=extent)
    axes[0, 1].set_title("pit argmax  (red=floor, blue=wall)")

    # Panel 2: road.
    axes[1, 0].imshow(hs, cmap="gray", extent=extent)
    axes[1, 0].imshow(argmaps["road"], cmap=cmap_bin, vmin=0, vmax=1,
                      interpolation="nearest", extent=extent)
    axes[1, 0].set_title("road argmax (orange)")

    # Panel 3: plat.
    axes[1, 1].imshow(hs, cmap="gray", extent=extent)
    axes[1, 1].imshow(argmaps["plat"], cmap=cmap_bin, vmin=0, vmax=1,
                      interpolation="nearest", extent=extent)
    axes[1, 1].set_title("plat argmax (orange)")

    for ax in axes.ravel():
        ax.set_xlabel("UTM 17N E (m)"); ax.set_ylabel("UTM 17N N (m)")

    fig.suptitle("mkf inference @ 1 m using 0.5 m-trained models  (resolution-mismatched smoke test)",
                 fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    png = OUT_DIR / "overlay_mkf_1m.png"
    fig.savefig(png, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {png}")


def main() -> int:
    stack_features()
    argmaps: dict[str, np.ndarray] = {}
    for name, ckpt, n_cls, patch, overlap in TASKS:
        argmaps[name] = infer_one(name, ckpt, n_cls, patch, overlap)
    render_overlay(argmaps)
    print(f"\nDONE. outputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
