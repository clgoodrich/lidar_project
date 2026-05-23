"""Find predicted pit components that do not overlap any labeled pit polygon.

These are either (a) false positives or (b) real pits we never labeled.

Reads:
    data/derivatives/9t/pit_unet_v2/pit_argmax.tif
    data/derivatives/9t/labels_pit_9t_05.tif
    data/derivatives/9t/pit_unet_v2/pit_prob_floor.tif
    data/derivatives/9t/pit_unet_v2/pit_prob_wall.tif

Writes:
    data/derivatives/9t/pit_unet_v2/pit_candidates_unlabeled.gpkg
    data/derivatives/9t/pit_unet_v2/pit_candidates_unlabeled.png
"""
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import shapes
from scipy import ndimage
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
PIT_DIR = D / "pit_unet_v2"

MIN_AREA_M2 = 4.0   # filter out tiny noise components
PX_M2 = 0.25        # 0.5 m x 0.5 m


def main():
    with rasterio.open(PIT_DIR / "pit_argmax.tif") as r:
        argmax = r.read(1)
        tf = r.transform
        crs = r.crs
        H, W = r.height, r.width
    with rasterio.open(D / "labels_pit_9t_05.tif") as r:
        labels = r.read(1)
    with rasterio.open(PIT_DIR / "pit_prob_floor.tif") as r:
        prob_floor = r.read(1)
    with rasterio.open(PIT_DIR / "pit_prob_wall.tif") as r:
        prob_wall = r.read(1)

    pred_pit = (argmax == 1) | (argmax == 2)
    label_pit = (labels == 1) | (labels == 2)

    # Connected components on predicted pit pixels (8-connectivity)
    cc, n = ndimage.label(pred_pit, structure=np.ones((3, 3)))
    print(f"Connected components in predictions: {n}")

    # For each component, does any pixel touch a labeled pit?
    # Use sum of label_pit per component.
    overlap = ndimage.sum(label_pit.astype(np.int32), cc, index=np.arange(1, n + 1))
    sizes = ndimage.sum(pred_pit.astype(np.int32), cc, index=np.arange(1, n + 1))
    cents = ndimage.center_of_mass(pred_pit, cc, index=np.arange(1, n + 1))
    max_prob = ndimage.maximum(np.maximum(prob_floor, prob_wall), cc, index=np.arange(1, n+1))

    # Components with zero overlap and reasonable size
    keep = (overlap == 0) & (sizes * PX_M2 >= MIN_AREA_M2)
    cand_ids = np.where(keep)[0] + 1  # 1-based
    print(f"Components with NO overlap to any labeled pit: {(overlap == 0).sum()}")
    print(f"  ... after filtering size >= {MIN_AREA_M2} m^2: {len(cand_ids)}")

    # Build a vector layer of candidates
    rows = []
    for cid in cand_ids:
        mask = (cc == cid).astype(np.uint8)
        polys = list(shapes(mask, mask=mask.astype(bool), transform=tf))
        # combine into one (dissolve)
        from shapely.ops import unary_union
        geom = unary_union([shape(s) for s, _ in polys])
        cy, cx = cents[cid - 1]
        rows.append({
            "candidate_id": int(cid),
            "area_m2": float(sizes[cid - 1] * PX_M2),
            "max_prob": float(max_prob[cid - 1]),
            "centroid_x": float(tf.c + cx * tf.a),
            "centroid_y": float(tf.f + cy * tf.e),
            "geometry": geom,
        })
    df = gpd.GeoDataFrame(rows, crs=crs)
    df = df.sort_values("area_m2", ascending=False).reset_index(drop=True)
    df.to_file(PIT_DIR / "pit_candidates_unlabeled.gpkg", driver="GPKG")
    df.drop(columns=["geometry"]).to_csv(PIT_DIR / "pit_candidates_unlabeled.csv", index=False)
    print(f"\nWrote pit_candidates_unlabeled.gpkg  ({len(df)} candidates)")

    # Size distribution
    print(f"\nSize distribution (m^2):")
    print(df["area_m2"].describe().round(1).to_string())
    print(f"\nMax prob distribution:")
    print(df["max_prob"].describe().round(3).to_string())

    # Render top 12 by size
    n_show = min(12, len(df))
    if n_show == 0:
        print("Nothing to render.")
        return

    with rasterio.open(D / "hillshade_9t_05.tif") as r:
        hs_full = r.read(1)
    with rasterio.open(D / "lrm_25_9t_05.tif") as r:
        lrm_full = r.read(1)

    fig, axes = plt.subplots(n_show, 2, figsize=(7, 3 * n_show))
    if n_show == 1:
        axes = axes[None, :]
    cmap_pred = ListedColormap(["#00000000", "#ffaa00cc", "#00ddffcc"])

    for i in range(n_show):
        row = df.iloc[i]
        cx, cy = row.centroid_x, row.centroid_y
        # 30 m half-side
        half = 20.0
        c0 = int(round((cx - half - tf.c) / tf.a))
        r0 = int(round((cy + half - tf.f) / tf.e))
        ww = int(2 * half / tf.a)
        wh = int(2 * half / (-tf.e))
        c0 = max(0, c0); r0 = max(0, r0)
        wh = min(wh, H - r0); ww = min(ww, W - c0)
        if wh <= 0 or ww <= 0:
            continue
        hs = hs_full[r0:r0+wh, c0:c0+ww]
        lrm = lrm_full[r0:r0+wh, c0:c0+ww]
        sub_pred = argmax[r0:r0+wh, c0:c0+ww]

        for ax in axes[i]: ax.set_xticks([]); ax.set_yticks([])
        axes[i, 0].imshow(hs, cmap="gray")
        axes[i, 0].imshow(sub_pred, cmap=cmap_pred, vmin=0, vmax=2, interpolation="nearest")
        axes[i, 0].set_title(
            f"cand {int(row.candidate_id)}  area={row.area_m2:.0f} m^2  max_p={row.max_prob:.2f}",
            fontsize=9)
        v = np.nanpercentile(np.abs(lrm), 98)
        axes[i, 1].imshow(lrm, cmap="RdBu_r", vmin=-v, vmax=v)
        axes[i, 1].imshow(sub_pred, cmap=cmap_pred, vmin=0, vmax=2, interpolation="nearest")
        axes[i, 1].set_title(f"LRM25 + prediction", fontsize=9)

    plt.tight_layout()
    plt.savefig(PIT_DIR / "pit_candidates_unlabeled.png", dpi=110, bbox_inches="tight")
    plt.close()
    print(f"Wrote pit_candidates_unlabeled.png (top {n_show} by area)")


if __name__ == "__main__":
    main()
