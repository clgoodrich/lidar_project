"""How many HELD-OUT hand-drawn annotations does the model's geometry overlap?

Ground truth here is the hand-drawn annotation set and nothing else. No state
well list is used anywhere in this script -- DEP coordinates are not reliable
enough to score against (measured: median 26 m from our own hand-drawn pits,
only 20% within 10 m).

The question:
  * we hand-drew 426 pits and 650 pads
  * the model trained on the TRAIN split only
  * the VAL + TEST annotations were never shown to it -- those are the skipped ones
  * vectorize the model's probability raster
  * how many skipped annotations does that geometry land on?

Three overlap tests, loosest to strictest, because "found it" is a judgement
call and the answer should not hinge on one arbitrary cutoff:
  touch        the model geometry intersects the annotation at all
  centroid     a model polygon contains the annotation's centroid
  iou>=0.3     the standard detection bar, for continuity with the leaderboard

Outputs (data/05_results/9t/heldout_overlap/):
  heldout_overlap_9t.csv     counts per model / split / threshold / criterion
  heldout_<model>.gpkg       every skipped annotation, flagged found / missed
  heldout_overlap_9t.png     bar summary + a map of hits and misses
  _heldout_9t.json           summary

Run:
  python notebooks/wellsight_v2/s5_eval/_heldout_overlap_9t.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from scipy import ndimage as ndi
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
NINE_T = path_for("nine_t")
ANN_GPKG = path_for("truth") / "annotations_proj.gpkg"
OUT = path_for("results") / "9t" / "heldout_overlap"
OUT.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:6346"
MIN_AREA_M2 = 4.0
THRESHOLDS = [0.3, 0.5, 0.6, 0.7]
MAIN_THR = {"pit_unet_v2": 0.60, "plat_unet": 0.50}   # val-selected earlier

MODELS = {
    # pits: floor probability. The wall band is a separate class and the
    # annotation being scored (pit_inside) is the floor.
    "pit_unet_v2": ("pit", path_for("models") / "pit" / "unet_v2" / "pit_prob_floor.tif"),
    "plat_unet":   ("pad", path_for("models") / "plat" / "unet" / "plat_prob.tif"),
}


def polygonize(prob, transform, crs, thresh, min_area=MIN_AREA_M2):
    mask = prob >= thresh
    if not mask.any():
        return gpd.GeoDataFrame({"score": []}, geometry=[], crs=crs)
    lbl, n = ndi.label(mask)
    means = ndi.mean(prob, labels=lbl, index=np.arange(1, n + 1))
    rows = []
    for geom, val in shapes(lbl.astype(np.int32), mask=mask, transform=transform):
        i = int(val)
        if i < 1:
            continue
        g = shape(geom)
        if g.area < min_area:
            continue
        rows.append({"score": float(means[i - 1]), "geometry": g})
    return (gpd.GeoDataFrame(rows, crs=crs) if rows
            else gpd.GeoDataFrame({"score": []}, geometry=[], crs=crs))


def overlap_flags(gt: gpd.GeoDataFrame, pred: gpd.GeoDataFrame):
    """Per GT polygon: touched, centroid-covered, best IoU, overlap fraction."""
    n = len(gt)
    touched = np.zeros(n, bool)
    cent = np.zeros(n, bool)
    best_iou = np.zeros(n)
    frac = np.zeros(n)          # share of the annotation's area covered
    if pred is None or len(pred) == 0:
        return touched, cent, best_iou, frac
    sidx = pred.sindex
    for i, r in enumerate(gt.itertuples()):
        g = r.geometry
        c = g.centroid
        inter_tot = 0.0
        for pj in sidx.intersection(g.bounds):
            p = pred.geometry.iloc[pj]
            if not g.intersects(p):
                continue
            touched[i] = True
            a = g.intersection(p).area
            inter_tot += a
            u = g.union(p).area
            if u > 0:
                best_iou[i] = max(best_iou[i], a / u)
            if p.contains(c):
                cent[i] = True
        frac[i] = inter_tot / g.area if g.area > 0 else 0.0
    return touched, cent, best_iou, frac


def main() -> int:
    print("== held-out hand-drawn annotations vs model geometry ==")
    print("   (ground truth = hand annotations only; no state well list used)\n")

    ann = {}
    for kind, layer, man, idcol in (
        ("pit", "pit_inside", "pit_dataset_manifest.csv", "pit_id"),
        ("pad", "plat", "plat_dataset_manifest.csv", "plat_id"),
    ):
        g = gpd.read_file(ANN_GPKG, layer=layer).to_crs(CRS)
        g = g.rename(columns={idcol: "inst_id"})[["inst_id", "geometry"]]
        m = pd.read_csv(NINE_T / man).rename(columns={idcol: "inst_id"})
        g = g.merge(m[["inst_id", "split"]], on="inst_id", how="inner")
        ann[kind] = g
        held = g[g.split.isin(("val", "test"))]
        print(f"  {kind}: {len(g)} hand-drawn "
              f"({dict(g.split.value_counts())})  -> {len(held)} held out")

    rows, summary = [], {}
    for name, (kind, path) in MODELS.items():
        if not path.exists():
            print(f"  !! {name} missing"); continue
        with rasterio.open(path) as r:
            prob = r.read(1).astype(np.float32)
            if r.nodata is not None:
                prob = np.where(prob == r.nodata, 0.0, prob)
            tf, pcrs = r.transform, r.crs

        g = ann[kind]
        print(f"\n  {name}")
        for thr in THRESHOLDS:
            pred = polygonize(prob, tf, pcrs, thr)
            for split in ("val", "test", "heldout", "train"):
                sub = (g[g.split.isin(("val", "test"))] if split == "heldout"
                       else g[g.split == split])
                if not len(sub):
                    continue
                t, c, iou, fr = overlap_flags(sub, pred)
                rows.append(dict(model=name, kind=kind, threshold=thr,
                                 split=split, n=len(sub),
                                 touch=int(t.sum()), centroid=int(c.sum()),
                                 iou30=int((iou >= 0.3).sum()),
                                 frac_touch=float(t.mean()),
                                 frac_centroid=float(c.mean()),
                                 frac_iou30=float((iou >= 0.3).mean()),
                                 median_cover=float(np.median(fr))))
                if split == "heldout":
                    print(f"    thr {thr:.2f}  n_pred={len(pred):5d}  "
                          f"HELD-OUT n={len(sub):3d}: "
                          f"touch {int(t.sum()):3d} ({100*t.mean():5.1f}%)  "
                          f"centroid {int(c.sum()):3d} ({100*c.mean():5.1f}%)  "
                          f"IoU>=.3 {int((iou>=0.3).sum()):3d} "
                          f"({100*(iou>=0.3).mean():5.1f}%)")
                if split == "heldout" and abs(thr - MAIN_THR[name]) < 1e-9:
                    sv = sub.reset_index(drop=True).copy()
                    sv["touched"] = t; sv["centroid_hit"] = c
                    sv["best_iou"] = np.round(iou, 3)
                    sv["cover_frac"] = np.round(fr, 3)
                    sv["verdict"] = np.where(t, "found", "missed")
                    sv["model"] = name; sv["threshold"] = thr
                    sv.to_file(OUT / f"heldout_{name}.gpkg", layer="heldout",
                               driver="GPKG")
                    pred.to_file(OUT / f"heldout_{name}.gpkg",
                                 layer="model_geometry", driver="GPKG")
                    summary[name] = dict(
                        kind=kind, threshold=thr, n_heldout=len(sub),
                        touch=int(t.sum()), centroid=int(c.sum()),
                        iou30=int((iou >= 0.3).sum()),
                        pct_touch=round(100 * float(t.mean()), 1),
                        pct_centroid=round(100 * float(c.mean()), 1),
                        pct_iou30=round(100 * float((iou >= 0.3).mean()), 1))

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "heldout_overlap_9t.csv", index=False)
    print(f"\n  wrote {OUT / 'heldout_overlap_9t.csv'}")

    # ---- figure ----
    fig, ax = plt.subplots(1, 3, figsize=(19, 5.6))
    h = df[df.split == "heldout"]
    for i, (name, g_) in enumerate(h.groupby("model")):
        ax[0].plot(g_.threshold, g_.frac_touch, marker="o",
                   label=f"{name} touch")
        ax[0].plot(g_.threshold, g_.frac_centroid, marker="s", ls="--",
                   label=f"{name} centroid")
        ax[0].plot(g_.threshold, g_.frac_iou30, marker="^", ls=":",
                   label=f"{name} IoU>=0.3")
    ax[0].set_xlabel("probability threshold")
    ax[0].set_ylabel("fraction of held-out annotations found")
    ax[0].set_ylim(0, 1.02); ax[0].grid(alpha=0.3); ax[0].legend(fontsize=7)
    ax[0].set_title("Held-out annotations recovered")

    names = list(summary)
    x = np.arange(len(names)); w = 0.26
    for k, (lab, col) in enumerate((("pct_touch", "#1a9641"),
                                    ("pct_centroid", "#4575b4"),
                                    ("pct_iou30", "#d7191c"))):
        vals = [summary[n][lab] for n in names]
        ax[1].bar(x + (k - 1) * w, vals, w, label=lab.replace("pct_", ""),
                  color=col)
        for xi, v in zip(x + (k - 1) * w, vals):
            ax[1].text(xi, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)
    ax[1].set_xticks(x)
    ax[1].set_xticklabels([f"{n}\nthr={summary[n]['threshold']:.2f}, "
                           f"n={summary[n]['n_heldout']}" for n in names],
                          fontsize=8)
    ax[1].set_ylabel("% of held-out annotations found"); ax[1].legend(fontsize=8)
    ax[1].set_title("At the val-selected threshold")

    with rasterio.open(NINE_T / "hillshade_9t_05.tif") as r:
        hs = r.read(1)
        ext = (r.bounds.left, r.bounds.right, r.bounds.bottom, r.bounds.top)
    ax[2].imshow(hs, cmap="gray", extent=ext, alpha=0.9)
    shown = names[0] if names else None
    if shown:
        sv = gpd.read_file(OUT / f"heldout_{shown}.gpkg", layer="heldout")
        sv[sv.verdict == "found"].plot(ax=ax[2], color="#1a9641", markersize=14)
        sv[sv.verdict == "missed"].plot(ax=ax[2], color="#d7191c", markersize=22)
        ax[2].set_title(f"{shown}: held-out found (green) vs missed (red)")
    ax[2].set_xticks([]); ax[2].set_yticks([]); ax[2].set_aspect("equal")
    fig.suptitle("Held-out hand-drawn annotations vs vectorized model output "
                 "(no state well list involved)")
    fig.tight_layout()
    fig.savefig(OUT / "heldout_overlap_9t.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {OUT / 'heldout_overlap_9t.png'}")

    (OUT / "_heldout_9t.json").write_text(json.dumps(summary, indent=2))
    print(f"  wrote {OUT / '_heldout_9t.json'}\n")
    for n, s in summary.items():
        print(f"  {n}: of {s['n_heldout']} held-out {s['kind']}s, "
              f"model geometry touches {s['touch']} ({s['pct_touch']}%), "
              f"covers centroid of {s['centroid']} ({s['pct_centroid']}%), "
              f"IoU>=0.3 on {s['iou30']} ({s['pct_iou30']}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
