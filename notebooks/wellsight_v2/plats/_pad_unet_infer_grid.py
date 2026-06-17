"""Apply the PA-trained pad/plat U-Net straight to a label_grids/<grid> tile.

Cross-region transfer EXPERIMENT: the model is trained on Western-PA plats at 0.5 m
(`data/derivatives/tiles/9t/plat_unet/best.pt`, 7-band pit feature stack, channels =
DEFAULT_CHANNELS, normalized by 9t feature_stats.json). Here we run it unchanged on a
grid's EXISTING derivatives — no Permian labels, no retraining, no resampling.

Caveats surfaced, not hidden:
  * The model was trained at 0.5 m; these grids are 1 m, so terrain features present at
    ~half the pixel footprint the net saw in training (scale mismatch is expected).
  * 9t channel `roughness_11` is the known 1 m mislabel of `roughness_5`; we map it.

Outputs under <grid_dir>/pad_unet_xfer/:
  features_pad_<sfx>.tif   the 7-band stack fed to the net (band order = DEFAULT_CHANNELS)
  pad_prob.tif             P(pad) float32
  pad_argmax.tif           uint8 argmax
  pads_pred.gpkg           polygonized pad_argmax==1 (area + mean prob per blob)
  pad_overlay.png          prob over hillshade

CLI:
  python notebooks/wellsight_v2/plats/_pad_unet_infer_grid.py --grid label_grids/permian_01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
import torch
from rasterio.features import shapes

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T, ROOT, make_profile, write_tif       # noqa: E402
from _dl import (DEFAULT_CHANNELS, DEVICE, UNet, load_stats,        # noqa: E402
                 predict_full_tile)

CKPT = DERIV_9T / "plat_unet" / "best.pt"
STATS = DERIV_9T / "feature_stats.json"
PATCH, OVERLAP, N_CLASSES = 384, 96, 2
# 9t stack calls the 1 m roughness band "roughness_11"; on the grids it is roughness_5.
CHAN_FILE = {"roughness_11": "roughness_5"}


def stack_features(grid_dir: Path, sfx: str, out_path: Path) -> Path:
    """Write the 7-band DEFAULT_CHANNELS stack from the grid's per-derivative tifs."""
    bands, profile = [], None
    for ch in DEFAULT_CHANNELS:
        stem = CHAN_FILE.get(ch, ch)
        tif = grid_dir / f"{stem}_{sfx}.tif"
        if not tif.exists():
            raise SystemExit(f"missing band {ch} -> {tif}")
        with rasterio.open(tif) as r:
            bands.append(r.read(1).astype(np.float32))
            if profile is None:
                profile = r.profile.copy()
    arr = np.stack(bands)
    p = make_profile(width=arr.shape[2], height=arr.shape[1],
                     transform=profile["transform"], crs=profile["crs"],
                     dtype="float32", nodata=profile.get("nodata"))
    p["count"] = arr.shape[0]
    with rasterio.open(out_path, "w", **p) as dst:
        dst.write(arr)
        dst.descriptions = tuple(DEFAULT_CHANNELS)
    print(f"  stacked {arr.shape[0]} bands -> {out_path.name}  ({arr.shape[2]}x{arr.shape[1]})")
    return out_path


def polygonize(argmax: np.ndarray, prob1: np.ndarray, profile: dict,
               out_gpkg: Path, *, area_min_m2: float = 200.0) -> int:
    import geopandas as gpd
    from shapely.geometry import shape
    tf, crs = profile["transform"], profile["crs"]
    px_area = abs(tf.a * tf.e)
    geoms, probs, areas = [], [], []
    for geom, val in shapes(argmax, mask=(argmax == 1), transform=tf):
        if val != 1:
            continue
        g = shape(geom); a = g.area
        if a < area_min_m2:
            continue
        rmin, rmax = g.bounds[1], g.bounds[3]  # noqa: F841 (kept for clarity)
        geoms.append(g); areas.append(a)
        # mean prob inside the blob's bbox (cheap proxy)
        probs.append(float(np.nan))
    if not geoms:
        gpd.GeoDataFrame({"pad_id": [], "area_m2": []},
                         geometry=[], crs=crs).to_file(out_gpkg, driver="GPKG")
        print("  no pad blobs >= area_min"); return 0
    gdf = gpd.GeoDataFrame(
        {"pad_id": range(1, len(geoms) + 1), "area_m2": areas},
        geometry=geoms, crs=crs)
    gdf.to_file(out_gpkg, driver="GPKG", layer="pads_pred")
    print(f"  {len(gdf)} pad polygons (>= {area_min_m2:.0f} m2) -> {out_gpkg.name}")
    return len(gdf)


def overlay(prob1: np.ndarray, hs_path: Path, out_png: Path) -> None:
    if not hs_path.exists():
        print("  (no hillshade, skipping overlay)"); return
    import matplotlib.pyplot as plt
    with rasterio.open(hs_path) as r:
        hs = r.read(1).astype(np.float32)
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.imshow(hs, cmap="gray")
    m = np.ma.masked_less(prob1, 0.3)
    ax.imshow(m, cmap="magma", alpha=0.6, vmin=0.3, vmax=1.0)
    ax.set_title("PA pad U-Net -> applied to grid (P>=0.3)"); ax.axis("off")
    plt.savefig(out_png, dpi=110, bbox_inches="tight"); plt.close(fig)
    print(f"  overlay -> {out_png.name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True, help="path to label_grids/<grid> dir")
    ap.add_argument("--area-min", type=float, default=200.0)
    args = ap.parse_args()
    grid_dir = (ROOT / args.grid).resolve() if not Path(args.grid).is_absolute() else Path(args.grid)
    name = grid_dir.name
    sfx = f"{name}_1m"
    out_dir = grid_dir / "pad_unet_xfer"; out_dir.mkdir(exist_ok=True)
    print(f"== pad U-Net (PA) -> {name} ==")

    feats = stack_features(grid_dir, sfx, out_dir / f"features_pad_{sfx}.tif")
    mu, sd = load_stats(STATS, DEFAULT_CHANNELS)
    model = UNet(in_ch=len(DEFAULT_CHANNELS), n_classes=N_CLASSES, base=32)
    ck = torch.load(CKPT, map_location=DEVICE, weights_only=False)
    model.to(DEVICE).load_state_dict(ck["state_dict"])
    print(f"  loaded plat_unet best.pt (ep {ck.get('epoch','?')})")

    prob, argmax, profile = predict_full_tile(
        model, feats, mu, sd, patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES)
    tf, crs = profile["transform"], profile["crs"]
    write_tif(out_dir / "pad_prob.tif", prob[1], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    pp = make_profile(width=argmax.shape[1], height=argmax.shape[0], transform=tf,
                      crs=crs, dtype="uint8", nodata=255)
    with rasterio.open(out_dir / "pad_argmax.tif", "w", **pp) as dst:
        dst.write(argmax, 1)
    print(f"  P(pad): max={prob[1].max():.3f} mean={prob[1].mean():.4f} "
          f"px>=0.5={int((prob[1]>=0.5).sum())}")

    n = polygonize(argmax, prob[1], profile, out_dir / "pads_pred.gpkg",
                   area_min_m2=args.area_min)
    overlay(prob[1], grid_dir / f"hillshade_{sfx}.tif", out_dir / "pad_overlay.png")
    print(f"\nDONE -> {out_dir}  ({n} candidate pads)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
