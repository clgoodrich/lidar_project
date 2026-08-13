"""Per-threshold PAD products: what each probability cutoff claims, and what it misses.

Pad counterpart to `_pit_threshold_products_9t.py`. Same question, same
ground-truth rule, so the two are directly comparable.

Ground truth is the hand-drawn `plat` polygons. Held out = the val + test rows
of `plat_dataset_manifest.csv`, i.e. exactly the pads the U-Net never trained on.
No state well list is involved.

MEASURING A PAD -- WHY THREE CRITERIA AND NOT ONE
--------------------------------------------------
The pit script uses one rule: a prediction's centroid must land inside the
annotated feature. Carried to pads unchanged, that rule breaks at low
thresholds, and the failure is not the model's.

Pad probability has a high floor (tile mean 0.162 versus 0.039 for roads). Drop
the cutoff and predictions stop being pad-shaped and merge into a handful of
tile-spanning super-blobs -- at 0.05 the whole tile is 188 polygons covering
58% of it. A super-blob's centroid sits in the middle of nowhere, inside no
individual pad, so "found" reads 0/194 at the very threshold that claims the
most ground. The number is an artifact of blob merging, not a detection result.

So three criteria are reported, and they fail in different directions:

  pred_centroid_in_gt   a prediction's centroid lies inside the pad.
                        Strict about over-merging. Degenerates to 0 when
                        predictions merge, as above.
  gt_centroid_covered   the pad's centroid lies inside a prediction.
                        Immune to merging. Degenerates to ~everything when the
                        threshold claims most of the tile, so it is an upper
                        bound, not a score.
  iou >= 0.30           best IoU against any single prediction.
                        Penalised by BOTH failure modes, so it is the only one
                        of the three that stays honest across the whole sweep.
                        This is the headline.

Read all three together. Where they disagree, the disagreement is the finding.

Two products per threshold:
  rasters      pad_unet_mask_thrXpXX_9t_05.tif / pad_unet_prob_thrXpXX_9t_05.tif
  gpkg         pad_found_vs_missed / pad_found / pad_missed / centroid_missed /
               locator_missed / model_geometry, self-styling green-vs-red
  bookmarks    pad_missed_bookmarks_thrXpXX_9t.xml -- import via
               View > Show Spatial Bookmark Manager > Import
  contactsheet hillshade crop of every miss in one PNG

Plus a full sweep table over every threshold in THRESHOLDS_SWEEP, which is the
"% of tile claimed vs pads found" curve.

Note on scale: pads are ~50x a pit floor (median annotated pad 1,343 m2 versus
median annotated pit floor 26 m2), so MIN_AREA_M2 is 100 here rather than 4.
The smallest annotated pad is 261 m2, so 100 cannot filter out a real pad.

Run:
  python notebooks/wellsight_v2/s5_eval/_pad_threshold_products_9t.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _threshold_common import (CRS, bookmarks_xml, contact_sheet, embed_style,
                               polygonize, style_qml, tag, write_raster)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
NINE_T = path_for("nine_t")
PROB = NINE_T / "plat_unet" / "plat_prob.tif"
RASTER_DIR = NINE_T / "plat_unet"
HILLSHADE = NINE_T / "hillshade_9t_05.tif"
ANN_GPKG = path_for("truth") / "annotations_proj.gpkg"
OUT = path_for("results") / "9t" / "pad" / "thresholds"
OUT.mkdir(parents=True, exist_ok=True)

MIN_AREA_M2 = 100.0        # see docstring -- smallest annotated pad is 261 m2
LOCATOR_R = 200.0          # metres; pads are bigger than pits, so is the circle
BOOKMARK_PAD = 150.0
CROP_HALF_M = 150.0

IOU_THR = 0.30             # headline criterion, see docstring
THRESHOLDS_SWEEP = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45,
                    0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90]
THRESHOLDS_PRODUCTS = [0.40, 0.50, 0.60, 0.70]


def main() -> int:
    print("== per-threshold PAD products (ground truth = hand-drawn plats) ==\n")

    plat = gpd.read_file(ANN_GPKG, layer="plat").to_crs(CRS)
    man = pd.read_csv(NINE_T / "plat_dataset_manifest.csv")
    held = set(man.loc[man.split.isin(("val", "test")), "plat_id"])
    plat = plat[["plat_id", "geometry"]].dissolve(by="plat_id").reset_index()
    plat = plat.merge(man[["plat_id", "split"]], on="plat_id", how="inner")
    held_g = plat[plat.plat_id.isin(held)].reset_index(drop=True)
    print(f"  annotated pads: {len(plat)}   held out (val+test): {len(held_g)}")
    print(f"  held-out pad area: median {held_g.area.median():.0f} m2, "
          f"total {held_g.area.sum() / 1e4:.2f} ha\n")

    with rasterio.open(PROB) as r:
        prob = r.read(1).astype(np.float32)
        if r.nodata is not None:
            prob = np.where(prob == r.nodata, 0.0, prob)
        tf, pcrs, prof = r.transform, r.crs, r.profile.copy()
        px = abs(r.transform.a) * abs(r.transform.e)
    tile_ha = prob.size * px / 1e4

    # ---- threshold-free: strongest pad probability inside each held-out pad ----
    from rasterio.features import rasterize
    pid = rasterize(((g, i + 1) for i, g in enumerate(held_g.geometry)),
                    out_shape=prob.shape, transform=tf, fill=0, dtype="int32")
    idx = np.arange(1, len(held_g) + 1)
    held_g["max_prob"] = np.round(ndi.maximum(prob, labels=pid, index=idx), 3)
    mp = held_g["max_prob"].to_numpy()
    print("  max pad-probability inside each held-out pad "
          f"(threshold-free): min {mp.min():.3f}  p05 {np.percentile(mp, 5):.3f}"
          f"  median {np.median(mp):.3f}  max {mp.max():.3f}")
    print(f"    pads with NO pad-like signal at all (max_prob < 0.05): "
          f"{int((mp < 0.05).sum())}/{len(mp)}\n")

    # ---- full sweep ----
    n_h = len(held_g)
    print(f"  sweep over {n_h} held-out pads. IoU>=0.30 is the headline "
          f"(see docstring).")
    print(f"  {'thr':>5} {'poly':>6} {'ha':>9} {'%tile':>7}  "
          f"{'IoU>=.3':>8} {'predC_in':>9} {'gtC_cov':>8}  {'MISSED':>7}")
    sweep = []
    for t in THRESHOLDS_SWEEP:
        m = prob >= t
        pred = polygonize(prob, tf, pcrs, t, MIN_AREA_M2)
        h = _hits(held_g, pred)
        ha = m.sum() * px / 1e4
        sweep.append(dict(threshold=t, n_polygons=len(pred),
                          ha_claimed=round(ha, 2),
                          pct_of_tile=round(100 * m.mean(), 3),
                          n_heldout=n_h,
                          found_iou30=int(h["iou"].sum()),
                          missed_iou30=int((~h["iou"]).sum()),
                          recall_iou30=round(h["iou"].mean(), 3),
                          found_pred_centroid_in_gt=int(h["pred_centroid_in_gt"].sum()),
                          found_gt_centroid_covered=int(h["gt_centroid_covered"].sum()),
                          median_best_iou=round(float(np.median(h["best_iou"])), 3)))
        print(f"  {t:5.2f} {len(pred):6d} {ha:9.2f} {100 * m.mean():7.3f}  "
              f"{int(h['iou'].sum()):8d} "
              f"{int(h['pred_centroid_in_gt'].sum()):9d} "
              f"{int(h['gt_centroid_covered'].sum()):8d}  "
              f"{int((~h['iou']).sum()):7d}")
    sw = pd.DataFrame(sweep)
    sw.to_csv(OUT / "pad_threshold_sweep_9t.csv", index=False)
    best = sw.loc[sw.recall_iou30.idxmax()]
    print(f"\n  best IoU>=0.30 recall: {best.recall_iou30:.3f} "
          f"({int(best.found_iou30)}/{n_h}) at threshold {best.threshold:.2f}, "
          f"claiming {best.pct_of_tile:.2f}% of tile")
    print(f"  wrote {OUT / 'pad_threshold_sweep_9t.csv'}\n")

    # ---- full products at the selected thresholds ----
    summary = []
    for t in THRESHOLDS_PRODUCTS:
        tg = tag(t)
        m = prob >= t
        pred = polygonize(prob, tf, pcrs, t, MIN_AREA_M2)
        h = _hits(held_g, pred)
        found = h["iou"]                       # headline criterion

        rv = held_g.copy()
        rv["verdict"] = np.where(found, "found", "missed")
        rv["threshold"] = t
        rv["best_iou"] = np.round(h["best_iou"], 3)
        rv["pred_centroid_in_gt"] = h["pred_centroid_in_gt"]
        rv["gt_centroid_covered"] = h["gt_centroid_covered"]
        miss = rv[rv.verdict == "missed"].reset_index(drop=True)
        print(f"  thr {t:.2f}: {len(pred)} polygons, "
              f"{m.sum() * px / 1e4:.2f} ha, found {int(found.sum())}"
              f"/{len(held_g)} at IoU>=0.30, MISSED {len(miss)}")

        write_raster(RASTER_DIR / f"pad_unet_mask_{tg}_9t_05.tif",
                     m.astype(np.uint8), prof, dict(dtype="uint8", nodata=0),
                     dict(THRESHOLD=str(t), SOURCE=PROB.name,
                          MEANING="1 = pad probability >= threshold"))
        write_raster(RASTER_DIR / f"pad_unet_prob_{tg}_9t_05.tif",
                     np.where(m, prob, np.nan).astype(np.float32), prof,
                     dict(dtype="float32", nodata=np.nan, predictor=2),
                     dict(THRESHOLD=str(t), SOURCE=PROB.name,
                          MEANING="pad probability where >= threshold"))

        gp = OUT / f"pad_heldout_found_vs_missed_{tg}_9t.gpkg"
        if gp.exists():
            gp.unlink()
        rv.to_file(gp, layer="pad_found_vs_missed", driver="GPKG")
        rv[rv.verdict == "found"].to_file(gp, layer="pad_found", driver="GPKG")
        if len(miss):
            miss.to_file(gp, layer="pad_missed", driver="GPKG")
            c = miss.copy(); c["geometry"] = miss.geometry.centroid
            c.to_file(gp, layer="centroid_missed", driver="GPKG")
            loc = miss.copy()
            loc["geometry"] = miss.geometry.centroid.buffer(LOCATOR_R)
            loc.to_file(gp, layer="locator_missed", driver="GPKG")
        if len(pred):
            pred.to_file(gp, layer="model_geometry", driver="GPKG")
        embed_style(gp, "pad_found_vs_missed", style_qml(),
                    f"green found / red missed at threshold {t}")
        (OUT / f"pad_heldout_found_vs_missed_{tg}_9t.qml").write_text(style_qml())

        bmp = OUT / f"pad_missed_bookmarks_{tg}_9t.xml"
        bmp.write_text(bookmarks_xml(
            [(f"MISSED {i:02d}/{len(miss)} plat_id={rr.plat_id} @{t}",
              rr.geometry.centroid.x, rr.geometry.centroid.y)
             for i, rr in enumerate(miss.itertuples(), 1)],
            group=f"pad missed {t}", id_prefix=f"padmiss_{tg}",
            pad=BOOKMARK_PAD))

        contact_sheet(
            OUT / f"pad_missed_contactsheet_{tg}_9t.png", HILLSHADE, miss, pred,
            f"Held-out PADS missed at threshold {t}  "
            f"(red = annotated pad, green = model geometry nearby)",
            CROP_HALF_M,
            lambda rr: (f"plat_id {rr.plat_id}  ({rr.split})\n"
                        f"max_prob {rr.max_prob:.3f}  best_iou {rr.best_iou:.2f}\n"
                        f"{rr.geometry.centroid.x:.0f}, "
                        f"{rr.geometry.centroid.y:.0f}"))

        summary.append(dict(threshold=t, n_polygons=len(pred),
                            ha_claimed=round(m.sum() * px / 1e4, 2),
                            pct_of_tile=round(100 * m.mean(), 3),
                            found_iou30=int(found.sum()), missed_iou30=len(miss),
                            n_heldout=len(held_g)))

    pd.DataFrame(summary).to_csv(
        OUT / "pad_threshold_found_vs_missed_summary_9t.csv", index=False)
    held_g.drop(columns="geometry").to_csv(
        OUT / "pad_heldout_max_prob_9t.csv", index=False)
    print(f"\n  tile = {tile_ha:.0f} ha")
    print(f"  all products in {OUT}")
    print(f"  rasters in {RASTER_DIR}")
    return 0


def _hits(gt: gpd.GeoDataFrame, pred: gpd.GeoDataFrame,
          iou_thr: float = IOU_THR) -> dict[str, np.ndarray]:
    """Three found/missed criteria per held-out pad. See MEASURING A PAD above.

    pred_centroid_in_gt   a prediction's centroid lies inside the pad
    gt_centroid_covered   the pad's centroid lies inside a prediction
    iou                   best IoU against any single prediction >= iou_thr
    """
    n = len(gt)
    out = {k: np.zeros(n, bool) for k in
           ("pred_centroid_in_gt", "gt_centroid_covered", "iou")}
    best = np.zeros(n)
    if not len(pred):
        out["best_iou"] = best
        return out
    sidx = pred.sindex
    pcent = pred.geometry.centroid
    for i, rr in enumerate(gt.itertuples()):
        g = rr.geometry
        gc = g.centroid
        for pj in sidx.intersection(g.bounds):
            pg = pred.geometry.iloc[pj]
            if not out["pred_centroid_in_gt"][i] and g.contains(pcent.iloc[pj]):
                out["pred_centroid_in_gt"][i] = True
            if not out["gt_centroid_covered"][i] and pg.contains(gc):
                out["gt_centroid_covered"][i] = True
            inter = g.intersection(pg).area
            if inter > 0:
                union = g.area + pg.area - inter
                best[i] = max(best[i], inter / union if union else 0.0)
    out["iou"] = best >= iou_thr
    out["best_iou"] = best
    return out


if __name__ == "__main__":
    sys.exit(main())
