"""DEP POSITIONAL RELIABILITY CHECK -- NOT A MODEL SCORE.

READ THIS BEFORE QUOTING ANY NUMBER THIS SCRIPT PRINTS.

This started as "how many uncounted DEP wells does the model find" and that
framing is WRONG for scoring a model. The PA DEP oil & gas layer is a record of
wells that exist; it is not a reliable statement of WHERE they are. Measured
against our own hand-drawn pits on 9t:

    distance from a hand-drawn pit to the nearest DEP point
      median 26.4 m,  p75 67 m,  p90 98 m
      only 20% within 10 m, 49% within 25 m

We drew those pits off the lidar, so they sit on the actual surface feature. The
disagreement is DEP coordinate error. A 25 m match radius therefore discards more
than half of all true correspondences, and any "recovery rate" computed this way
measures DEP's positional accuracy far more than it measures the model.

A DEP record also cannot be tied to a surface expression at all unless something
visible is found near it -- many catalogued wells are plugged, reclaimed,
regraded, under canopy, or never had a pit.

So the recovery percentages below are NOT model performance and must not be put
on the leaderboard or in a paper as such. The script is kept for the one thing it
does measure honestly: how far DEP coordinates sit from real surface features.

For actual held-out performance use `_heldout_overlap_9t.py`, which scores the
model against hand-drawn annotations it never saw and involves no state list:
    pits: 109/128 held-out found (85.2%) at thr 0.60
    pads: 187/194 held-out found (96.4%) at thr 0.50

Outputs (data/05_results/9t/wells/uncounted/):
  uncounted_recovery_9t.csv     hit rate vs match radius -- DEP position study
  uncounted_wells_9t.gpkg       DEP points with distance to nearest detection
  recovered_uncounted_9t.gpkg   DEP points that do sit near a detection
  uncounted_recovery_9t.png     radius sweep + distance histogram + map
  _uncounted_9t.json            summary

Run:
  python notebooks/wellsight_v2/s5_eval/_uncounted_well_recovery_9t.py
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
from shapely.geometry import box, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
NINE_T = path_for("nine_t")
ANN_DIR = path_for("truth")
ANN_GPKG = ANN_DIR / "annotations_proj.gpkg"
OUT = path_for("results") / "9t" / "wells" / "uncounted"
OUT.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:6346"
BBOX = (619500.0, 4593000.0, 624000.0, 4597500.0)
RADII = [10, 15, 20, 25, 30, 40, 50, 75, 100]
REPORT_R = 25.0                    # headline radius, same as prior work
MIN_AREA_M2 = 4.0

# Thresholds carried over from the val selection in
# _reeval_instance_precision_9t.py so this is not a second tuning pass.
UNET = {
    "pit_unet_v2": ("pit", path_for("models") / "pit" / "unet_v2" / "pit_prob_floor.tif", 0.60),
    "plat_unet":   ("pad", path_for("models") / "plat" / "unet" / "plat_prob.tif", 0.50),
}
# "Counted" = a catalogued well close enough to an annotation that the model
# effectively saw it as a label. Pads are big, pits are small, so the radius
# that means "this well is represented by that polygon" differs.
COUNTED_R = {"pit": 25.0, "pad": 40.0}


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


def nearest_dist(pts: gpd.GeoDataFrame, polys: gpd.GeoDataFrame) -> np.ndarray:
    """Distance from each point to the nearest polygon (0 if inside)."""
    if polys is None or len(polys) == 0:
        return np.full(len(pts), np.inf)
    sidx = polys.sindex
    out = np.empty(len(pts))
    geoms = polys.geometry.values
    for i, p in enumerate(pts.geometry.values):
        idx = list(sidx.nearest(p, return_all=False, max_distance=None))
        # sindex.nearest returns [[input_idx],[tree_idx]]
        j = idx[1][0] if idx and len(idx) > 1 and len(idx[1]) else None
        out[i] = p.distance(geoms[j]) if j is not None else np.inf
    return out


def main() -> int:
    print("== uncounted-well recovery on 9t ==")

    aoi = box(*BBOX)
    blocks = gpd.read_file(NINE_T / "blocks_unified_9t.gpkg").to_crs(CRS)

    # ---- catalogued wells inside 9t ----
    wells = gpd.read_file(ANN_DIR / "oil_gas_locations.gpkg").to_crs(CRS)
    wells = gpd.clip(wells, aoi).reset_index(drop=True)
    keep = [c for c in ("PERMIT_NUM", "WELL_NAME", "OPERATOR_N", "WELL_TYPE_",
                        "WELL_STA_1", "SPUD_DATE", "PERMIT_DAT") if c in wells.columns]
    wells = wells[keep + ["geometry"]]
    print(f"  catalogued wells in 9t: {len(wells)}")

    # ---- annotations, and which split block each falls in ----
    ann = {
        "pit": gpd.read_file(ANN_GPKG, layer="pit_inside").to_crs(CRS),
        "pad": gpd.read_file(ANN_GPKG, layer="plat").to_crs(CRS),
    }
    man = {
        "pit": pd.read_csv(NINE_T / "pit_dataset_manifest.csv").rename(
            columns={"pit_id": "inst_id"}),
        "pad": pd.read_csv(NINE_T / "plat_dataset_manifest.csv").rename(
            columns={"plat_id": "inst_id"}),
    }
    for k in ann:
        idcol = "pit_id" if k == "pit" else "plat_id"
        ann[k] = ann[k].rename(columns={idcol: "inst_id"})[["inst_id", "geometry"]]
        ann[k] = ann[k].merge(man[k][["inst_id", "split"]], on="inst_id",
                              how="inner")
        print(f"  annotated {k}: {len(ann[k])} "
              f"({dict(ann[k].split.value_counts())})")

    # which split block does each WELL sit in
    wb = gpd.sjoin(wells[["geometry"]], blocks[["split", "geometry"]],
                   how="left", predicate="within")
    wb = wb[~wb.index.duplicated(keep="first")]
    wells["block_split"] = wb["split"].fillna("outside").values

    rows, per_well = [], []
    for name, (kind, path, thr) in UNET.items():
        if not path.exists():
            print(f"  !! {name} missing"); continue
        with rasterio.open(path) as r:
            prob = r.read(1).astype(np.float32)
            if r.nodata is not None:
                prob = np.where(prob == r.nodata, 0.0, prob)
            pred = polygonize(prob, r.transform, r.crs, thr)
        print(f"\n  {name}: {len(pred)} predictions over the whole tile "
              f"(thr {thr:.2f}, val-selected)")

        # A well is COUNTED if an annotation of this kind is within COUNTED_R.
        d_ann = nearest_dist(wells, ann[kind])
        counted = d_ann <= COUNTED_R[kind]
        unc = wells.loc[~counted].copy()
        print(f"    counted (within {COUNTED_R[kind]:.0f} m of an annotation): "
              f"{int(counted.sum())}   uncounted: {len(unc)}")

        d_pred = nearest_dist(unc, pred)
        unc["dist_to_pred_m"] = np.round(d_pred, 1)
        unc["model"] = name
        unc["recovered_25m"] = d_pred <= REPORT_R
        per_well.append(unc)

        for bt in ("test", "val", "train", "all"):
            sub = unc if bt == "all" else unc[unc.block_split == bt]
            if not len(sub):
                continue
            d = sub.dist_to_pred_m.values
            for R in RADII:
                rows.append(dict(model=name, kind=kind, block_split=bt,
                                 radius_m=R, n_uncounted=len(sub),
                                 n_recovered=int((d <= R).sum()),
                                 frac=float((d <= R).mean())))
            n25 = int((d <= REPORT_R).sum())
            print(f"    {bt:5s}: {len(sub):4d} uncounted, "
                  f"{n25:4d} recovered @{REPORT_R:.0f} m "
                  f"({100 * n25 / len(sub):.1f}%)   "
                  f"median dist {np.median(d[np.isfinite(d)]):.0f} m")

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "uncounted_recovery_9t.csv", index=False)
    allw = gpd.GeoDataFrame(pd.concat(per_well, ignore_index=True), crs=CRS)
    allw.to_file(OUT / "uncounted_wells_9t.gpkg", layer="uncounted",
                 driver="GPKG")
    rec = allw[allw.recovered_25m]
    rec.to_file(OUT / "recovered_uncounted_9t.gpkg", layer="recovered",
                driver="GPKG")
    print(f"\n  wrote {OUT / 'uncounted_recovery_9t.csv'}")
    print(f"  wrote {OUT / 'uncounted_wells_9t.gpkg'}  ({len(allw)} rows)")
    print(f"  wrote {OUT / 'recovered_uncounted_9t.gpkg'}  ({len(rec)} rows)")

    # ---- figures ----
    fig, ax = plt.subplots(1, 3, figsize=(19, 5.6))
    for (m_, bt), g in df[df.block_split.isin(("test", "val", "train"))].groupby(
            ["model", "block_split"]):
        ls = {"test": "-", "val": "--", "train": ":"}[bt]
        ax[0].plot(g.radius_m, g.frac, ls, marker="o", ms=3,
                   label=f"{m_} [{bt}]")
    ax[0].axvline(REPORT_R, color="k", lw=0.8, alpha=0.5)
    ax[0].set_xlabel("match radius (m)")
    ax[0].set_ylabel("fraction of uncounted wells recovered")
    ax[0].set_title("Recovery vs match radius\n(DEP coords are not survey-grade)")
    ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3)

    for m_, g in allw.groupby("model"):
        d = g.dist_to_pred_m.values
        d = d[np.isfinite(d)]
        ax[1].hist(np.clip(d, 0, 200), bins=40, alpha=0.55, label=m_)
    ax[1].axvline(REPORT_R, color="k", lw=0.8)
    ax[1].set_xlabel("distance from uncounted well to nearest detection (m)")
    ax[1].set_ylabel("wells"); ax[1].legend(fontsize=8)
    ax[1].set_title("Distance distribution")

    with rasterio.open(NINE_T / "hillshade_9t_05.tif") as r:
        hs = r.read(1)
        ext = (r.bounds.left, r.bounds.right, r.bounds.bottom, r.bounds.top)
    ax[2].imshow(hs, cmap="gray", extent=ext, alpha=0.9)
    sub = allw[allw.model == "plat_unet"]
    sub[~sub.recovered_25m].plot(ax=ax[2], color="#d7191c", markersize=4,
                                 label="not recovered")
    sub[sub.recovered_25m].plot(ax=ax[2], color="#1a9641", markersize=6,
                                label="recovered")
    ax[2].set_xlim(BBOX[0], BBOX[2]); ax[2].set_ylim(BBOX[1], BBOX[3])
    ax[2].set_xticks([]); ax[2].set_yticks([]); ax[2].set_aspect("equal")
    ax[2].legend(fontsize=8, loc="lower left")
    ax[2].set_title(f"plat_unet: uncounted wells @{REPORT_R:.0f} m")
    fig.suptitle("Uncounted catalogued wells recovered by the U-Nets "
                 "(lower bound: many catalogued wells have no surface expression)")
    fig.tight_layout()
    fig.savefig(OUT / "uncounted_recovery_9t.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {OUT / 'uncounted_recovery_9t.png'}")

    summ = {"n_catalogued_9t": int(len(wells)), "report_radius_m": REPORT_R,
            "counted_radius_m": COUNTED_R,
            "headline": df[(df.radius_m == REPORT_R)].to_dict("records")}
    (OUT / "_uncounted_9t.json").write_text(json.dumps(summ, indent=2))
    print(f"  wrote {OUT / '_uncounted_9t.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
