"""Diagnose elongated false positives in pit predictions.

Hypothesis: the parallel-elongated polygons the user is seeing are road shoulders /
ditches that the pit U-Net is over-firing on because they share local features with
pit floors (negative LRM, locally low elevation, sharp slope transitions on either side).

Approach:
  1. Read the iter 04 mean ensemble pit_argmax (best pit predictions to date).
  2. Connected-component analysis on (argmax == 1 | argmax == 2).
  3. Compute per-component shape stats:
       area_m2, eccentricity, aspect_ratio (major/minor axis), solidity,
       max_road_prob (sampling iter 04 road_prob within the component bbox),
       overlaps_labeled_pit (against pit_inside annotations).
  4. Classify each component as:
       TRUE_PIT       — overlaps a labeled pit
       LIKELY_ROAD_FP — high road_prob AND elongated
       OTHER_FP       — high pit prob, low road prob, doesn't match a labeled pit
       (tiny components below MIN_AREA_M2 are dropped).
  5. Render a sample grid of LIKELY_ROAD_FP candidates next to hillshade + road_prob
     so the user can visually confirm.
  6. Print summary counts.

Outputs (under data/derivatives/9t/diagnostics/elongated_fps/):
  components_summary.gpkg        every component with all attrs + classification
  components_summary.csv         tabular dump for quick review
  fp_render_road.png             grid of LIKELY_ROAD_FP samples
  fp_render_other.png            grid of OTHER_FP samples
  histograms.png                 distribution plots (area, eccentricity, road_prob)
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape, box
from shapely.ops import unary_union
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
ANN = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
OUTDIR = D / "diagnostics" / "elongated_fps_maxpit"; OUTDIR.mkdir(parents=True, exist_ok=True)

PIT_ARGMAX = D / "iterations" / "04_ensemble_01_03" / "ensemble_maxpit_argmax.tif"
PIT_PROB_FLOOR = D / "iterations" / "04_ensemble_01_03" / "ensemble_maxpit_prob_floor.tif"
PIT_PROB_WALL = D / "iterations" / "04_ensemble_01_03" / "ensemble_maxpit_prob_wall.tif"
ROAD_PROB = D / "road_unet" / "road_prob.tif"
ROAD_ARGMAX = D / "road_unet" / "road_argmax.tif"
HILLSHADE = D / "hillshade_9t_05.tif"
LRM = D / "lrm_25_9t_05.tif"

MIN_AREA_M2 = 4.0
PX_M2 = 0.25
N_RENDER_ROAD_FP = 12
N_RENDER_OTHER_FP = 8


def main():
    print("Loading rasters...")
    with rasterio.open(PIT_ARGMAX) as r:
        argmax = r.read(1)
        tf = r.transform
        crs = r.crs
        H, W = r.height, r.width
    with rasterio.open(PIT_PROB_FLOOR) as r:
        prob_floor = r.read(1)
    with rasterio.open(PIT_PROB_WALL) as r:
        prob_wall = r.read(1)
    with rasterio.open(ROAD_PROB) as r:
        road_prob = r.read(1)

    pred_pit = (argmax == 1) | (argmax == 2)
    print(f"Pred-pit pixels (any class): {pred_pit.sum():,} = "
          f"{pred_pit.sum()*PX_M2:,.0f} m^2")

    print("Labeling connected components (8-conn)...")
    cc, n = ndimage.label(pred_pit, structure=np.ones((3, 3)))
    print(f"  total components: {n}")

    # Per-component basics
    sizes = ndimage.sum(pred_pit.astype(np.int32), cc, index=np.arange(1, n + 1))
    keep = sizes * PX_M2 >= MIN_AREA_M2
    cand_ids = np.where(keep)[0] + 1
    print(f"  components area >= {MIN_AREA_M2} m^2: {len(cand_ids)}")

    # Per-component statistics — we'll compute by iterating components
    label_pit_in = gpd.read_file(ANN, layer="pit_inside")

    print("Computing per-component shape + cross-feature stats...")
    rows = []
    for cid in cand_ids:
        mask = cc == cid
        # Bounding-box slice for cheap measurements
        ys, xs = np.where(mask)
        if len(ys) == 0:
            continue
        r0, r1 = ys.min(), ys.max() + 1
        c0, c1 = xs.min(), xs.max() + 1
        local = mask[r0:r1, c0:c1]
        area_px = int(local.sum())
        area_m2 = area_px * PX_M2

        # Bounding-box aspect (px-wise; both axes same scale so equivalent to m)
        bbox_h = r1 - r0
        bbox_w = c1 - c0
        aspect_ratio = max(bbox_h, bbox_w) / max(min(bbox_h, bbox_w), 1)

        # Moments-based eccentricity (PCA on pixel coordinates)
        ys_local = ys - ys.mean()
        xs_local = xs - xs.mean()
        cov = np.cov(np.stack([ys_local, xs_local]))
        eigs = np.linalg.eigvalsh(cov)
        eigs = np.maximum(eigs, 1e-6)
        ecc = float(np.sqrt(1 - eigs[0] / eigs[1])) if eigs[1] > 0 else 0.0
        major = float(2 * np.sqrt(eigs[1]))   # in px (= 2*sqrt(major eigenvalue)) -> approx
        minor = float(2 * np.sqrt(eigs[0]))
        elongation = major / max(minor, 1.0)

        # Solidity: area / convex-hull area (rough approx via bbox-area)
        solidity_bbox = area_px / max(bbox_h * bbox_w, 1)

        # Road prob: max + mean inside the component
        sub_road = road_prob[r0:r1, c0:c1][local]
        sub_road = sub_road[np.isfinite(sub_road) & (sub_road >= 0)]
        road_prob_max = float(sub_road.max()) if len(sub_road) else 0.0
        road_prob_mean = float(sub_road.mean()) if len(sub_road) else 0.0

        # Pit prob max/mean
        sub_pf = prob_floor[r0:r1, c0:c1][local]
        sub_pw = prob_wall[r0:r1, c0:c1][local]
        pit_prob_max = float(np.maximum(sub_pf, sub_pw).max())

        # World coords for centroid
        cy_px = ys.mean()
        cx_px = xs.mean()
        wx = tf.c + cx_px * tf.a
        wy = tf.f + cy_px * tf.e

        # Polygonize this component for the GPKG output
        polys = list(shapes(local.astype(np.uint8), mask=local, transform=rasterio.transform.from_bounds(
            tf.c + c0 * tf.a, tf.f + r1 * tf.e,
            tf.c + c1 * tf.a, tf.f + r0 * tf.e, c1 - c0, r1 - r0,
        )))
        if polys:
            geom = unary_union([shape(s) for s, _ in polys])
        else:
            geom = box(tf.c + c0 * tf.a, tf.f + r1 * tf.e,
                       tf.c + c1 * tf.a, tf.f + r0 * tf.e)

        # Overlap with labeled pit?
        overlaps_label = False
        nearby = label_pit_in[label_pit_in.intersects(geom)]
        if len(nearby):
            overlaps_label = True

        rows.append({
            "component_id": int(cid),
            "area_m2": float(area_m2),
            "bbox_h_px": int(bbox_h),
            "bbox_w_px": int(bbox_w),
            "aspect_ratio_bbox": float(aspect_ratio),
            "eccentricity": ecc,
            "elongation_pca": float(elongation),
            "solidity_bbox": float(solidity_bbox),
            "road_prob_max": road_prob_max,
            "road_prob_mean": road_prob_mean,
            "pit_prob_max": pit_prob_max,
            "centroid_x": float(wx),
            "centroid_y": float(wy),
            "overlaps_labeled_pit": bool(overlaps_label),
            "geometry": geom,
        })

    print(f"Built {len(rows)} component records.")
    gdf = gpd.GeoDataFrame(rows, crs=crs)

    # Classify
    def classify(row):
        if row.overlaps_labeled_pit:
            return "TRUE_PIT_LABELED"
        # "Elongated" = elongation_pca > 3 OR aspect_ratio_bbox > 4
        elong = (row.elongation_pca > 3.0) or (row.aspect_ratio_bbox > 4.0)
        road_like = row.road_prob_max > 0.5 or row.road_prob_mean > 0.25
        if elong and road_like:
            return "LIKELY_ROAD_FP"
        if elong:
            return "ELONGATED_OTHER"
        if road_like:
            return "ROAD_LIKE_COMPACT"
        return "COMPACT_OTHER_FP"

    gdf["classification"] = gdf.apply(classify, axis=1)

    cls_counts = gdf["classification"].value_counts().to_dict()
    print("\nClassification breakdown:")
    for k, v in sorted(cls_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:25s} {v:5d}")

    gdf.to_file(OUTDIR / "components_summary.gpkg", driver="GPKG")
    gdf.drop(columns=["geometry"]).to_csv(OUTDIR / "components_summary.csv", index=False)
    (OUTDIR / "classification_counts.json").write_text(
        json.dumps(cls_counts, indent=2, default=int))
    print(f"\nWrote components_summary.gpkg / .csv  ({len(gdf)} rows)")

    # Histograms
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    axes[0, 0].hist(np.log10(gdf.area_m2 + 1), bins=40)
    axes[0, 0].set_xlabel("log10(area_m2 + 1)"); axes[0, 0].set_title("Area")
    axes[0, 1].hist(gdf.elongation_pca.clip(upper=10), bins=40)
    axes[0, 1].axvline(3, color="red", linestyle="--", label="elongated threshold")
    axes[0, 1].set_xlabel("elongation (PCA major/minor)"); axes[0, 1].legend()
    axes[0, 1].set_title("Elongation")
    axes[1, 0].hist(gdf.road_prob_max, bins=40)
    axes[1, 0].axvline(0.5, color="red", linestyle="--", label="road-like threshold")
    axes[1, 0].set_xlabel("road_prob_max in component"); axes[1, 0].legend()
    axes[1, 0].set_title("Road probability (max in component)")
    axes[1, 1].scatter(gdf.elongation_pca.clip(upper=10), gdf.road_prob_max,
                       s=4, alpha=0.5,
                       c=gdf.overlaps_labeled_pit.map({True: "green", False: "gray"}))
    axes[1, 1].axvline(3, color="red", linestyle="--", alpha=0.5)
    axes[1, 1].axhline(0.5, color="red", linestyle="--", alpha=0.5)
    axes[1, 1].set_xlabel("elongation (clipped at 10)")
    axes[1, 1].set_ylabel("road_prob_max")
    axes[1, 1].set_title("green = overlaps a labeled pit")
    plt.tight_layout()
    plt.savefig(OUTDIR / "histograms.png", dpi=110, bbox_inches="tight")
    plt.close()
    print(f"Wrote histograms.png")

    # Render samples
    with rasterio.open(HILLSHADE) as r:
        hs_full = r.read(1)
    with rasterio.open(LRM) as r:
        lrm_full = r.read(1)

    cmap_pred = ListedColormap(["#00000000", "#ffaa00cc", "#00ddffcc"])

    def render_grid(subset, n, title, out_name):
        if len(subset) == 0:
            print(f"  ({title}): no candidates to render")
            return
        sample = subset.sort_values("area_m2", ascending=False).head(n).reset_index(drop=True)
        rows_n = len(sample)
        fig, axes = plt.subplots(rows_n, 3, figsize=(10, 3 * rows_n))
        if rows_n == 1:
            axes = axes[None, :]
        for i, row in sample.iterrows():
            cx, cy = row.centroid_x, row.centroid_y
            half = 25.0
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
            sub_road = road_prob[r0:r0+wh, c0:c0+ww]

            for ax in axes[i]: ax.set_xticks([]); ax.set_yticks([])
            axes[i, 0].imshow(hs, cmap="gray")
            axes[i, 0].imshow(sub_pred, cmap=cmap_pred, vmin=0, vmax=2, interpolation="nearest")
            axes[i, 0].set_title(f"cid={int(row.component_id)} area={row.area_m2:.0f}m^2 "
                                  f"elong={row.elongation_pca:.1f}",
                                  fontsize=8)
            v = np.nanpercentile(np.abs(lrm), 98)
            axes[i, 1].imshow(lrm, cmap="RdBu_r", vmin=-v, vmax=v)
            axes[i, 1].imshow(sub_pred, cmap=cmap_pred, vmin=0, vmax=2, interpolation="nearest")
            axes[i, 1].set_title(f"LRM25 + pit prediction", fontsize=8)
            axes[i, 2].imshow(hs, cmap="gray")
            axes[i, 2].imshow(np.clip(sub_road, 0, 1), cmap="hot", alpha=0.55, vmin=0, vmax=1)
            axes[i, 2].set_title(f"Road prob (max={row.road_prob_max:.2f})", fontsize=8)
        plt.suptitle(title, fontsize=10)
        plt.tight_layout()
        plt.savefig(OUTDIR / out_name, dpi=110, bbox_inches="tight")
        plt.close()
        print(f"Wrote {out_name}")

    render_grid(gdf[gdf.classification == "LIKELY_ROAD_FP"],
                N_RENDER_ROAD_FP, "Likely road FPs (elongated + road-prob high)",
                "fp_render_road.png")
    render_grid(gdf[gdf.classification == "ELONGATED_OTHER"],
                N_RENDER_OTHER_FP, "Elongated but NOT road-like (interesting!)",
                "fp_render_elong_other.png")
    render_grid(gdf[gdf.classification == "COMPACT_OTHER_FP"],
                N_RENDER_OTHER_FP, "Compact other FPs (potential unlabeled pits?)",
                "fp_render_compact.png")

    print(f"\nAll outputs in {OUTDIR}")


if __name__ == "__main__":
    main()
