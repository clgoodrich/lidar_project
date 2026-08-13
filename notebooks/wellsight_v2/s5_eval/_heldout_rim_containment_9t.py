"""Held-out pits scored by RIM containment: did predicted floor land inside the rim?

WHY THIS IS A BETTER TEST THAN FLOOR-VS-FLOOR
---------------------------------------------
Scoring predicted floor against annotated floor punishes boundary disagreement.
The U-Net draws pit floors about half the size we do (median 13.5 m2 vs 26.2 m2),
so IoU-based scoring marks a correctly located pit as a partial miss purely
because the outline is tighter.

The rim (`pit_outside`) is the natural target for "did we find this pit". It is
~7.6x the floor area, and the annotated floor sits inside it in 423 of 424 cases.
A predicted floor blob landing inside the rim IS the pit, whatever its exact
outline. That separates LOCATING a pit from DELINEATING one, which are different
questions and were previously conflated.

Because containment is more forgiving, the probability threshold can be pushed
UP. A high threshold means fewer, more confident predictions -- and if those
still land inside the rim, the detection is strong. So the sweep runs to 0.90.

Ground truth is hand-drawn annotation only. No state well list is involved.

Three containment criteria, loosest to strictest:
  intersects    a predicted floor polygon touches the rim at all
  centroid_in   a prediction's centroid lies inside the rim  <- the headline
  fully_within  a prediction lies entirely inside the rim

Outputs (data/05_results/9t/pit/rim_containment/):
  rim_containment_9t.csv        counts per threshold per criterion
  rim_heldout_pits.gpkg         held-out RIM polygons flagged found/missed,
                                self-styling, + floor + model geometry layers
  rim_containment_9t.png        sweep curves + floor-vs-rim comparison + map
  _rim_containment_9t.json      summary

Run:
  python notebooks/wellsight_v2/s5_eval/_heldout_rim_containment_9t.py
"""
from __future__ import annotations

import json
import sqlite3
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
PROB = path_for("models") / "pit" / "unet_v2" / "pit_prob_floor.tif"
OUT = path_for("results_9t") / "pit" / "rim_containment"
OUT.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:6346"
MIN_AREA_M2 = 4.0
THRESHOLDS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50,
              0.60, 0.70, 0.80, 0.90]
HEADLINE = 0.30          # see the per-rim max-probability analysis below

QML = """<!DOCTYPE qgis PUBLIC 'http://mapserver.org/qgis' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="verdict" forceraster="0"
               enableorderby="0" symbollevels="0">
    <categories>
      <category value="found" symbol="0" label="found (floor inside rim)" render="true"/>
      <category value="missed" symbol="1" label="MISSED" render="true"/>
    </categories>
    <symbols>
      <symbol type="fill" name="0" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <prop k="color" v="26,150,65,60"/><prop k="style" v="solid"/>
          <prop k="outline_color" v="26,150,65,255"/>
          <prop k="outline_style" v="solid"/><prop k="outline_width" v="0.5"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
      <symbol type="fill" name="1" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <prop k="color" v="215,25,28,90"/><prop k="style" v="solid"/>
          <prop k="outline_color" v="215,25,28,255"/>
          <prop k="outline_style" v="solid"/><prop k="outline_width" v="1.2"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
"""
CREATE = """CREATE TABLE IF NOT EXISTS layer_styles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT,
  f_table_schema TEXT, f_table_name TEXT, f_geometry_column TEXT,
  styleName TEXT, styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN,
  description TEXT, owner TEXT, ui TEXT,
  update_time DATETIME DEFAULT (datetime('now')))"""


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


def containment(rims, pred):
    """Per rim: does any predicted floor polygon intersect / centre in / sit in it?"""
    n = len(rims)
    inter = np.zeros(n, bool)
    cent = np.zeros(n, bool)
    full = np.zeros(n, bool)
    if pred is None or len(pred) == 0:
        return inter, cent, full
    sidx = pred.sindex
    for i, r in enumerate(rims.itertuples()):
        rim = r.geometry
        for pj in sidx.intersection(rim.bounds):
            p = pred.geometry.iloc[pj]
            if not rim.intersects(p):
                continue
            inter[i] = True
            if rim.contains(p.centroid):
                cent[i] = True
            if rim.contains(p):
                full[i] = True
    return inter, cent, full


def main() -> int:
    print("== held-out pits: predicted FLOOR inside annotated RIM ==")
    print("   ground truth = hand-drawn annotations only\n")

    ins = gpd.read_file(ANN_GPKG, layer="pit_inside").to_crs(CRS)
    rim = gpd.read_file(ANN_GPKG, layer="pit_outside").to_crs(CRS)
    man = pd.read_csv(NINE_T / "pit_dataset_manifest.csv")
    held_ids = set(man.loc[man.split.isin(("val", "test")), "pit_id"])

    rim = rim[["pit_id", "geometry"]].dissolve(by="pit_id").reset_index()
    rim = rim.merge(man[["pit_id", "split"]], on="pit_id", how="inner")
    rim_h = rim[rim.pit_id.isin(held_ids)].reset_index(drop=True)
    floor_h = ins[ins.pit_id.isin(held_ids)].reset_index(drop=True)
    print(f"  held-out pits: {len(held_ids)}  with a rim polygon: {len(rim_h)}")
    print(f"  rim median area {rim_h.geometry.area.median():.0f} m2 vs "
          f"floor {floor_h.geometry.area.median():.0f} m2 "
          f"({rim_h.geometry.area.median() / floor_h.geometry.area.median():.1f}x)\n")

    with rasterio.open(PROB) as r:
        prob = r.read(1).astype(np.float32)
        if r.nodata is not None:
            prob = np.where(prob == r.nodata, 0.0, prob)
        tf, pcrs = r.transform, r.crs

    # ---- threshold-free: how much floor signal exists inside each rim? ----
    # This answers "are the missed pits actually blank, or just sub-threshold?"
    # directly, without reference to any cut. Rasterize each rim, take the max
    # floor probability inside it.
    from rasterio.features import rasterize as _rasterize
    rid = _rasterize(((g, i + 1) for i, g in enumerate(rim_h.geometry)),
                     out_shape=prob.shape, transform=tf, fill=0, dtype="int32")
    idx = np.arange(1, len(rim_h) + 1)
    rim_h["max_prob"] = np.round(
        ndi.maximum(prob, labels=rid, index=idx), 3)
    rim_h["mean_prob"] = np.round(ndi.mean(prob, labels=rid, index=idx), 3)
    mp = rim_h["max_prob"].values
    print("  max floor-probability inside each held-out rim "
          "(threshold-free):")
    for q in (5, 10, 25, 50, 75, 90):
        print(f"    p{q:02d}  {np.percentile(mp, q):.3f}")
    print(f"    rims with max_prob < 0.05 (genuinely no signal): "
          f"{int((mp < 0.05).sum())}/{len(mp)}")
    print()

    rows, keep = [], {}
    print(f"  {'thr':>5} {'n_pred':>7} | rim: {'inter':>6} {'centroid':>9} "
          f"{'within':>7} | floor IoU>=0.3")
    for thr in THRESHOLDS:
        pred = polygonize(prob, tf, pcrs, thr)
        it, ce, fu = containment(rim_h, pred)

        # floor-vs-floor at the same threshold, for the side-by-side
        sidx = pred.sindex if len(pred) else None
        f_iou = np.zeros(len(floor_h))
        if sidx is not None:
            for i, r_ in enumerate(floor_h.itertuples()):
                g = r_.geometry
                for pj in sidx.intersection(g.bounds):
                    p = pred.geometry.iloc[pj]
                    if not g.intersects(p):
                        continue
                    u = g.union(p).area
                    if u > 0:
                        f_iou[i] = max(f_iou[i], g.intersection(p).area / u)

        rows.append(dict(threshold=thr, n_pred=len(pred), n_rim=len(rim_h),
                         intersects=int(it.sum()), centroid_in=int(ce.sum()),
                         fully_within=int(fu.sum()),
                         frac_intersects=float(it.mean()),
                         frac_centroid_in=float(ce.mean()),
                         frac_fully_within=float(fu.mean()),
                         floor_iou30=int((f_iou >= 0.3).sum()),
                         frac_floor_iou30=float((f_iou >= 0.3).mean())))
        print(f"  {thr:5.2f} {len(pred):7d} | "
              f"{int(it.sum()):6d} {int(ce.sum()):9d} {int(fu.sum()):7d} | "
              f"{int((f_iou >= 0.3).sum()):6d}   "
              f"({100*ce.mean():5.1f}% vs {100*(f_iou>=0.3).mean():5.1f}%)")
        if abs(thr - HEADLINE) < 1e-9:
            keep = dict(pred=pred, inter=it, cent=ce, full=fu)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "rim_containment_9t.csv", index=False)
    print(f"\n  wrote {OUT / 'rim_containment_9t.csv'}")

    # ---- export at the headline threshold ----
    rv = rim_h.copy()
    rv["intersects"] = keep["inter"]
    rv["centroid_in"] = keep["cent"]
    rv["fully_within"] = keep["full"]
    rv["verdict"] = np.where(keep["cent"], "found", "missed")
    rv["threshold"] = HEADLINE
    gp = OUT / "rim_heldout_pits.gpkg"
    rv.to_file(gp, layer="rim_heldout", driver="GPKG")
    rv[rv.verdict == "found"].to_file(gp, layer="found", driver="GPKG")
    rv[rv.verdict == "missed"].to_file(gp, layer="missed", driver="GPKG")
    floor_h.to_file(gp, layer="floor_annotation", driver="GPKG")
    keep["pred"].to_file(gp, layer="model_geometry", driver="GPKG")

    con = sqlite3.connect(gp); cur = con.cursor()
    cur.execute(CREATE)
    cur.execute("DELETE FROM layer_styles WHERE f_table_name = 'rim_heldout'")
    cur.execute("INSERT INTO layer_styles (f_table_catalog, f_table_schema,"
                " f_table_name, f_geometry_column, styleName, styleQML,"
                " styleSLD, useAsDefault, description, owner, ui) VALUES"
                " ('', '', 'rim_heldout', 'geom', 'found_vs_missed', ?, '', 1,"
                " 'green = predicted floor centred inside this rim', '', '')",
                (QML,))
    con.commit(); con.close()
    (OUT / "rim_heldout_pits.qml").write_text(QML)
    print(f"  wrote {gp}  (rim_heldout auto-styled, + found/missed/"
          f"floor_annotation/model_geometry)")

    # ---- figure ----
    fig, ax = plt.subplots(1, 3, figsize=(19, 5.6))
    ax[0].plot(df.threshold, df.frac_intersects, marker="o", label="rim: intersects")
    ax[0].plot(df.threshold, df.frac_centroid_in, marker="s",
               label="rim: centroid inside", lw=2.4)
    ax[0].plot(df.threshold, df.frac_fully_within, marker="^",
               label="rim: fully within")
    ax[0].plot(df.threshold, df.frac_floor_iou30, marker="x", ls="--",
               color="0.4", label="floor-vs-floor IoU>=0.3")
    ax[0].axvline(HEADLINE, color="k", lw=0.8, alpha=0.6)
    ax[0].set_xlabel("probability threshold on pit_prob_floor")
    ax[0].set_ylabel(f"fraction of {len(rim_h)} held-out pits found")
    ax[0].set_ylim(0, 1.02); ax[0].grid(alpha=0.3); ax[0].legend(fontsize=8)
    ax[0].set_title("Rim containment tolerates a much higher threshold")

    ax[1].plot(df.threshold, df.n_pred, marker="o", color="#d7191c")
    ax[1].set_xlabel("threshold"); ax[1].set_ylabel("model polygons tile-wide")
    ax[1].grid(alpha=0.3)
    ax[1].set_title("Prediction count falls as the threshold rises")

    with rasterio.open(NINE_T / "hillshade_9t_05.tif") as r:
        hs = r.read(1)
        ext = (r.bounds.left, r.bounds.right, r.bounds.bottom, r.bounds.top)
    ax[2].imshow(hs, cmap="gray", extent=ext, alpha=0.9)
    rv[rv.verdict == "found"].plot(ax=ax[2], facecolor="none",
                                   edgecolor="#1a9641", linewidth=1.0)
    rv[rv.verdict == "missed"].plot(ax=ax[2], facecolor="none",
                                    edgecolor="#d7191c", linewidth=2.0)
    ax[2].set_xticks([]); ax[2].set_yticks([]); ax[2].set_aspect("equal")
    ax[2].set_title(f"held-out rims @ thr {HEADLINE:.2f}: "
                    f"{int(keep['cent'].sum())} found / "
                    f"{int((~keep['cent']).sum())} missed")
    fig.suptitle("Held-out pits: is the predicted floor inside the annotated rim?")
    fig.tight_layout()
    fig.savefig(OUT / "rim_containment_9t.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {OUT / 'rim_containment_9t.png'}")

    summ = dict(n_heldout_rims=len(rim_h), headline_threshold=HEADLINE,
                headline=df[df.threshold == HEADLINE].to_dict("records")[0],
                table=df.to_dict("records"))
    (OUT / "_rim_containment_9t.json").write_text(json.dumps(summ, indent=2))
    print(f"  wrote {OUT / '_rim_containment_9t.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
