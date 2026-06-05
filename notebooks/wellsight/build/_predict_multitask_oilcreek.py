"""Run the multitask U-Net (best.pt from 9t/multitask_unet) over the 22-tile
Oil Creek mosaic.

Pipeline:
  1. Build the 7-channel feature stack from dem_oilcreek_22tile_1m.tif
     -- exact same formulas as notebooks/.../build/_build_derivatives.py, but
     directly from the existing DEM (no LAZ roundtrip).
  2. Sliding-window inference with the MultiHeadUNet at PATCH=384.
  3. Emit argmax + foreground prob rasters for pit / road / plat.
  4. Composite 4-panel overlay PNG on the existing hillshade.

Caveat (same as the McKean smoke test): the multitask checkpoint was trained
on 0.5 m features and is running here on 1 m features. Kernel sizes are
matched in meters: lrm_5 -> 5-cell, lrm_25 -> 25-cell, tpi_05 -> 5 m disk,
openness L=25 cells, roughness -> 5x5 stdev (the "roughness_11" channel
name in the checkpoint is the 0.5 m-era label for what is physically a
~5 m kernel).

Outputs under data/derivatives/oilcreek_inference/:
  features_oilcreek_22tile_1m.tif
  pit_argmax_oilcreek_22tile_1m.tif         uint8 0=bg 1=floor 2=wall
  pit_prob_floor_oilcreek_22tile_1m.tif     float32
  pit_prob_wall_oilcreek_22tile_1m.tif      float32
  road_argmax_oilcreek_22tile_1m.tif        uint8 0/1
  road_prob_oilcreek_22tile_1m.tif          float32
  plat_argmax_oilcreek_22tile_1m.tif        uint8 0/1
  plat_prob_oilcreek_22tile_1m.tif          float32
  overlay_oilcreek_22tile_1m.png            hillshade + 3 head argmax panels
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
from rasterio.windows import Window
from scipy.ndimage import convolve, uniform_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, make_profile, write_tif
from _dl import DEVICE, normalize
from build._build_derivatives import (disk_kernel, nanmean_filter, openness)  # type: ignore
from multitask._multitask_unet import MultiHeadUNet  # type: ignore

# ---------------------------------------------------------------------------
SRC_DIR = DERIV / "extras" / "oilcreek_22tile"
OUT_DIR = DERIV / "oilcreek_inference"
DEM_PATH = SRC_DIR / "dem_oilcreek_22tile_1m.tif"
HILLSHADE = SRC_DIR / "hillshade_az315_alt25_oilcreek_22tile_1m.tif"
FEATURES_OUT = OUT_DIR / "features_oilcreek_22tile_1m.tif"

CKPT = DERIV / "9t" / "multitask_unet" / "best.pt"
SFX = "oilcreek_22tile_1m"
RES = 1.0
PATCH = 384
OVERLAP = 96
BATCH = 8

CHANNELS = ("lrm_25", "lrm_5", "slope", "tpi_05",
            "openness_pos", "openness_neg", "roughness_11")


# ---------------------------------------------------------------------------
# Stage 1: build the 7-channel feature stack from the existing 1 m DEM
# ---------------------------------------------------------------------------

def _lrm(dem: np.ndarray, size_cells: int) -> np.ndarray:
    valid = np.isfinite(dem).astype(np.float32)
    z0 = np.where(valid.astype(bool), dem, 0).astype(np.float32)
    sm = uniform_filter(z0, size=size_cells, mode="nearest")
    sc = uniform_filter(valid, size=size_cells, mode="nearest")
    smooth = np.where(sc > 0, sm / sc, np.nan)
    return (dem - smooth).astype(np.float32)


def _roughness_5(dem: np.ndarray) -> np.ndarray:
    WIN = 5
    k = np.ones((WIN, WIN), dtype=np.float32)
    v = np.isfinite(dem).astype(np.float32)
    z0 = np.where(v.astype(bool), dem, 0).astype(np.float32)
    s = convolve(z0, k, mode="nearest")
    s2 = convolve(z0 * z0, k, mode="nearest")
    n = convolve(v, k, mode="nearest")
    var = np.where(n > 1,
                   (s2 - s * s / np.maximum(n, 1)) / np.maximum(n - 1, 1),
                   np.nan)
    r = np.sqrt(np.clip(var, 0, None)).astype(np.float32)
    r[n < WIN * WIN] = np.nan
    return r


def build_features() -> None:
    if FEATURES_OUT.exists():
        print(f"reusing existing {FEATURES_OUT.name}")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"loading DEM: {DEM_PATH.name}")
    with rasterio.open(DEM_PATH) as r:
        dem = r.read(1).astype(np.float32)
        nodata = r.nodata
        transform = r.transform
        crs = r.crs
        H, W = r.height, r.width
    if nodata is not None:
        dem[dem == nodata] = np.nan
    print(f"  shape={H}x{W}  finite={np.isfinite(dem).mean()*100:.1f}%")

    print("  computing channels ...")
    bands: dict[str, np.ndarray] = {}
    bands["lrm_25"] = _lrm(dem, 25)
    bands["lrm_5"] = _lrm(dem, 5)

    # Slope via central differences (WBT would give the same numeric Horn slope,
    # but we already have the DEM in memory and don't need a file roundtrip).
    gy, gx = np.gradient(dem, RES)
    bands["slope"] = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)

    bands["tpi_05"] = (dem - nanmean_filter(dem, disk_kernel(5.0 / RES))).astype(np.float32)

    op_pos, op_neg = openness(dem, L_cells=int(25 / RES), cellsize=RES)
    bands["openness_pos"] = op_pos
    bands["openness_neg"] = op_neg

    bands["roughness_11"] = _roughness_5(dem)  # see module docstring

    print(f"  stacking {len(CHANNELS)} bands -> {FEATURES_OUT.name}")
    profile = make_profile(width=W, height=H, transform=transform, crs=crs,
                            dtype="float32", nodata=np.nan,
                            count=len(CHANNELS), bigtiff=True)
    with rasterio.open(FEATURES_OUT, "w", **profile) as dst:
        for i, name in enumerate(CHANNELS, 1):
            arr = bands[name]
            dst.write(arr, i)
            dst.set_band_description(i, name)
            print(f"    band {i} {name:14s}  range="
                  f"{np.nanmin(arr):+.3f}..{np.nanmax(arr):+.3f}")


# ---------------------------------------------------------------------------
# Stage 2: multitask inference
# ---------------------------------------------------------------------------

def predict_multitask() -> dict[str, np.ndarray]:
    ck = torch.load(CKPT, map_location=DEVICE, weights_only=False)
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)
    print(f"\nckpt ep={ck['epoch']}  score={ck['score']:.3f}  "
          f"channels={ck['channels']}")
    head_classes = ck.get("head_classes", (3, 2, 2))

    model = MultiHeadUNet(in_ch=len(ck["channels"]), base=32,
                          head_classes=head_classes).to(DEVICE)
    model.load_state_dict(ck["state_dict"])
    model.eval()

    step = PATCH - OVERLAP
    with rasterio.open(FEATURES_OUT) as r:
        H, W = r.height, r.width
        tf, crs = r.transform, r.crs

    def grid(extent: int) -> list[int]:
        xs = list(range(0, max(extent - PATCH + 1, 1), step))
        if not xs or xs[-1] != extent - PATCH:
            xs.append(extent - PATCH)
        return sorted(set(max(x, 0) for x in xs))

    rs, cs = grid(H), grid(W)
    n_patches = len(rs) * len(cs)
    print(f"inference grid: {len(rs)}x{len(cs)} = {n_patches} patches")

    nc_pit, nc_road, nc_plat = head_classes
    prob = {"pit":  np.zeros((nc_pit,  H, W), dtype=np.float32),
            "road": np.zeros((nc_road, H, W), dtype=np.float32),
            "plat": np.zeros((nc_plat, H, W), dtype=np.float32)}
    cnt = np.zeros((H, W), dtype=np.float32)
    use_amp = DEVICE.type == "cuda"
    buf_x, buf_pos = [], []

    def flush() -> None:
        if not buf_x:
            return
        x = torch.from_numpy(np.stack(buf_x)).to(DEVICE)
        with torch.no_grad(), torch.amp.autocast(device_type="cuda", enabled=use_amp):
            outs = model(x)
            p_pit  = torch.softmax(outs[0], 1).cpu().numpy()
            p_road = torch.softmax(outs[1], 1).cpu().numpy()
            p_plat = torch.softmax(outs[2], 1).cpu().numpy()
        for i, (r0, c0) in enumerate(buf_pos):
            prob["pit"][:,  r0:r0+PATCH, c0:c0+PATCH] += p_pit[i]
            prob["road"][:, r0:r0+PATCH, c0:c0+PATCH] += p_road[i]
            prob["plat"][:, r0:r0+PATCH, c0:c0+PATCH] += p_plat[i]
            cnt[r0:r0+PATCH, c0:c0+PATCH] += 1
        buf_x.clear(); buf_pos.clear()

    t0 = time.time()
    done = 0
    with rasterio.open(FEATURES_OUT) as src:
        for r0 in rs:
            for c0 in cs:
                f = src.read(window=Window(c0, r0, PATCH, PATCH)).astype(np.float32)
                buf_x.append(normalize(f, mu, sd))
                buf_pos.append((r0, c0))
                if len(buf_x) >= BATCH:
                    flush()
                    done += BATCH
                    if done % (BATCH * 20) == 0:
                        print(f"  {done}/{n_patches}  "
                              f"({time.time()-t0:.0f}s)")
        flush()
    print(f"  inference total {time.time()-t0:.1f}s")

    np.maximum(cnt, 1, out=cnt)
    for k in prob:
        prob[k] /= cnt

    argmax = {k: prob[k].argmax(0).astype(np.uint8) for k in prob}

    # Write outputs.
    for name in ("pit", "road", "plat"):
        am_prof = make_profile(width=W, height=H, transform=tf, crs=crs,
                                dtype="uint8", nodata=255, bigtiff=True)
        with rasterio.open(OUT_DIR / f"{name}_argmax_{SFX}.tif", "w", **am_prof) as ds:
            ds.write(argmax[name], 1)

    write_tif(OUT_DIR / f"pit_prob_floor_{SFX}.tif", prob["pit"][1],
              transform=tf, crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
    write_tif(OUT_DIR / f"pit_prob_wall_{SFX}.tif", prob["pit"][2],
              transform=tf, crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
    write_tif(OUT_DIR / f"road_prob_{SFX}.tif", prob["road"][1],
              transform=tf, crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
    write_tif(OUT_DIR / f"plat_prob_{SFX}.tif", prob["plat"][1],
              transform=tf, crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
    print(f"  wrote {sum(1 for _ in OUT_DIR.glob(f'*{SFX}*'))} files in {OUT_DIR}")
    return argmax


# ---------------------------------------------------------------------------
# Stage 3: overlay PNG
# ---------------------------------------------------------------------------

def render_overlay(argmaps: dict[str, np.ndarray]) -> None:
    if not HILLSHADE.exists():
        print(f"hillshade missing, skip overlay: {HILLSHADE}")
        return
    with rasterio.open(HILLSHADE) as r:
        hs = r.read(1)
        bounds = r.bounds
    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

    cmap_pit = ListedColormap(["#00000000", "#ff3333aa", "#3399ffaa"])
    cmap_bin = ListedColormap(["#00000000", "#ffaa00cc"])

    fig, axes = plt.subplots(2, 2, figsize=(18, 18))
    axes[0, 0].imshow(hs, cmap="gray", extent=extent)
    axes[0, 0].set_title("hillshade az315 alt25 (1 m)")
    axes[0, 1].imshow(hs, cmap="gray", extent=extent)
    axes[0, 1].imshow(argmaps["pit"], cmap=cmap_pit, vmin=0, vmax=2,
                       interpolation="nearest", extent=extent)
    axes[0, 1].set_title("pit  (red=floor, blue=wall)")
    axes[1, 0].imshow(hs, cmap="gray", extent=extent)
    axes[1, 0].imshow(argmaps["road"], cmap=cmap_bin, vmin=0, vmax=1,
                       interpolation="nearest", extent=extent)
    axes[1, 0].set_title("road")
    axes[1, 1].imshow(hs, cmap="gray", extent=extent)
    axes[1, 1].imshow(argmaps["plat"], cmap=cmap_bin, vmin=0, vmax=1,
                       interpolation="nearest", extent=extent)
    axes[1, 1].set_title("plat")
    for ax in axes.ravel():
        ax.set_xlabel("UTM 17N E (m)"); ax.set_ylabel("UTM 17N N (m)")
    fig.suptitle("multitask iter 07 (ep 32) on Oil Creek 22-tile @ 1 m "
                 "[resolution-mismatched -- trained at 0.5 m]", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    png = OUT_DIR / f"overlay_{SFX}.png"
    fig.savefig(png, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {png.name}")


def main() -> int:
    build_features()
    argmaps = predict_multitask()
    render_overlay(argmaps)
    print(f"\nDONE. outputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
