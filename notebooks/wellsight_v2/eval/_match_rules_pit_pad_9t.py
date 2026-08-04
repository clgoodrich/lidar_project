"""Matching rules for pit/pad scoring: fix a defect, then test two relaxations.

The centroid rule used so far (`containment` / `locate`) is
`centroid(prediction) inside annotation`. Three problems, addressed in order so
each one's effect on precision and recall is visible separately.

RULE 0  baseline, as previously scored.

DEFECT  the annotation set was restricted to features carried in the fold
        manifest. Annotated features outside the manifest were invisible, so a
        prediction sitting on a real pad counted as a false positive. Fixed by
        scoring against EVERY annotation inside the held-out footprint. This is
        a bug fix, not a loosened rule -- it can only move numbers toward truth.

RULE 1  bidirectional containment. A prediction much LARGER than the annotation
        can enclose it while its own centroid falls on ground outside, and a
        prediction much SMALLER can sit inside a concave annotation whose
        centroid lies in a notch. Both are located, not missed. Match if
        centroid(pred) in ann, OR centroid(ann) in pred, OR
        area(intersection) / min(area) >= OVERLAP_FRAC.

RULE 2  size plausibility. A blob far smaller than any annotated feature of that
        class is not that class. Areas are strongly right-skewed, so the cut is
        taken in log10 space: reject below mean(log10 area) - N_SD * sd. The
        linear-space equivalent is reported alongside for comparison, and it is
        the wrong cut -- for pads it lands below zero.

Rejected predictions are dropped from BOTH the precision denominator and the
candidate list, so the filter cannot flatter precision for free.

Outputs (data/derivatives/eval_9t_centroid_matching/):
    match_rule_ablation_pit_pad_9t.csv          one row per target per rule
    pad_candidates_filtered_heldout_9t.shp      survivors, ranked by score
    pit_candidates_filtered_heldout_9t.shp      survivors, ranked by score

Reproduce:
  python notebooks/wellsight_v2/eval/_match_rules_pit_pad_9t.py
  ... --n-sd 3.0 --overlap-frac 0.5
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize as _rast

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "notebooks" / "wellsight_v2"),
                str(ROOT / "notebooks" / "wellsight_v2" / "pits")]
from _common import DERIV_9T                                      # noqa: E402
from _pit_unet_cv5 import assign_folds, polygonize                # noqa: E402

ANN = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
OUT = ROOT / "data" / "derivatives" / "eval_9t_centroid_matching"
CRS = "EPSG:6346"
CV_SEED = 20260727
K = 5

TARGETS = {
    "pit": dict(outdir=DERIV_9T / "pit_unet_cv5", per_fold="pit_cv5_per_fold_9t.csv",
                blocks=DERIV_9T / "pit_blocks_9t.gpkg",
                manifest=DERIV_9T / "pit_dataset_manifest.csv",
                id_col="pit_id", n_col="n_pits", gt_layer="pit_outside",
                # The model predicts FLOORS; the match target is the RIM. Size
                # plausibility must therefore be judged against annotated
                # floors, not rims, or every prediction is rejected.
                size_layer="pit_inside",
                prob="pit_prob_floor_cvfold{k}_9t_05.tif",
                min_area=4.0, buf=40.0),
    "pad": dict(outdir=DERIV_9T / "pad_unet_cv5", per_fold="pad_cv5_per_fold_9t.csv",
                blocks=DERIV_9T / "plat_blocks_9t.gpkg",
                manifest=DERIV_9T / "plat_dataset_manifest.csv",
                id_col="plat_id", n_col="n_pads", gt_layer="plat",
                prob="pad_prob_cvfold{k}_9t_05.tif",
                min_area=100.0, buf=80.0),
}


def build_pairs(gt, pred, *, bidirectional, overlap_frac):
    """Candidate (gt_index, pred_index, score) pairs under the chosen rule."""
    if not len(gt) or not len(pred):
        return []
    pc = pred.geometry.centroid
    gc = gt.geometry.centroid
    sidx = pred.sindex
    sc = pred["score"].to_numpy()
    pairs = []
    for gi, r in enumerate(gt.itertuples()):
        g = r.geometry
        for pj in sidx.intersection(g.bounds):
            pj = int(pj)
            p = pred.geometry.iloc[pj]
            ok = g.contains(pc.iloc[pj])
            if not ok and bidirectional:
                if p.contains(gc.iloc[gi]):
                    ok = True
                else:
                    inter = g.intersection(p).area
                    denom = min(g.area, p.area)
                    ok = denom > 0 and inter / denom >= overlap_frac
            if ok:
                pairs.append((gi, pj, float(sc[pj])))
    return pairs


def greedy(pairs):
    ug, up = set(), set()
    for gi, pj, _ in sorted(pairs, key=lambda t: -t[2]):
        if gi in ug or pj in up:
            continue
        ug.add(gi); up.add(pj)
    return ug, up


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-sd", type=float, default=3.0)
    ap.add_argument("--overlap-frac", type=float, default=0.5)
    ap.add_argument("--objective", default="f1", choices=("f1", "f2"))
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    with rasterio.open(DERIV_9T / "features_pit_9t_05.tif") as r:
        tf, rcrs = r.transform, r.crs

    rows = []
    for name, cfg in TARGETS.items():
        man = pd.read_csv(cfg["manifest"])
        blocks = gpd.read_file(cfg["blocks"], layer="blocks").to_crs(CRS)
        nper = man.groupby("block_id").size().rename(cfg["n_col"]).reset_index()
        fo = assign_folds(nper[["block_id", cfg["n_col"]]], K, CV_SEED)
        man["fold"] = man.block_id.map(fo)
        blocks["fold"] = blocks.block_id.map(fo)

        # EVERY annotation, not only manifest rows -- this is the defect fix.
        ann_all = gpd.read_file(ANN, layer=cfg["gt_layer"]).to_crs(CRS)
        ann_all = ann_all[[cfg["id_col"], "geometry"]].dissolve(
            by=cfg["id_col"]).reset_index()
        ann_all["geometry"] = ann_all.geometry.buffer(0)
        ann_all = ann_all[~ann_all.geometry.is_empty].reset_index(drop=True)
        ann_man = ann_all[ann_all[cfg["id_col"]].isin(man[cfg["id_col"]])]

        # Size reference is the layer the model actually draws, which for pits
        # is the floor, not the rim it is matched against.
        size_lyr = cfg.get("size_layer", cfg["gt_layer"])
        ref = gpd.read_file(ANN, layer=size_lyr).to_crs(CRS)
        ref["geometry"] = ref.geometry.buffer(0)
        a = ref[~ref.geometry.is_empty].geometry.area.to_numpy()
        print(f"  size reference layer: {size_lyr}")
        la = np.log10(a[a > 0])
        cut_log = 10 ** (la.mean() - args.n_sd * la.std())
        cut_lin = a.mean() - args.n_sd * a.std()
        print(f"\n=== {name} ===")
        print(f"  annotated area m2: mean {a.mean():.0f}  sd {a.std():.0f}  "
              f"min {a.min():.0f}")
        print(f"  size cut  log10-space {args.n_sd:.1f} sd -> {cut_log:.1f} m2"
              f"   (linear-space would be {cut_lin:.0f} m2)")

        sel = pd.read_csv(cfg["outdir"] / cfg["per_fold"])
        per_fold = []
        for k in range(K):
            tif = cfg["outdir"] / f"fold{k}" / cfg["prob"].format(k=k)
            if not tif.exists():
                print(f"  fold {k}: MISSING {tif}"); continue
            thr = float(sel[(sel.fold == k) &
                            (sel.objective == args.objective)].prob_threshold.iloc[0])
            with rasterio.open(tif) as r:
                prob = r.read(1).astype(np.float32)
            hb = sorted(man.loc[man.fold == k, "block_id"].unique())
            foot = blocks.loc[blocks.block_id.isin(hb)].geometry.union_all()
            msk = _rast([(foot.buffer(cfg["buf"]), 1)], out_shape=prob.shape,
                        transform=tf, fill=0, dtype="uint8").astype(bool)
            allp = polygonize(np.where(msk, prob, 0.0).astype(np.float32),
                              tf, rcrs, thr, min_area=cfg["min_area"])
            pr = (allp[allp.geometry.centroid.within(foot)].reset_index(drop=True)
                  if len(allp) else allp)
            pr = pr.copy(); pr["fold"] = k; pr["thr"] = thr
            gt_man = ann_man[[c.within(foot) for c in ann_man.geometry.centroid]]
            gt_all = ann_all[[c.within(foot) for c in ann_all.geometry.centroid]]
            per_fold.append((pr, gt_man.reset_index(drop=True),
                             gt_all.reset_index(drop=True)))

        def score(rule, *, use_all, bidir, size):
            TP = NG = NP = 0
            leftovers = []
            for pr, gt_man, gt_all in per_fold:
                gt = gt_all if use_all else gt_man
                p = pr[pr.geometry.area >= cut_log].reset_index(drop=True) if size else pr
                ug, up = greedy(build_pairs(gt, p, bidirectional=bidir,
                                            overlap_frac=args.overlap_frac))
                TP += len(ug); NG += len(gt); NP += len(p)
                if len(p):
                    leftovers.append(p[[i not in up for i in range(len(p))]])
            P = TP / max(NP, 1); R = TP / max(NG, 1)
            rows.append(dict(target=name, rule=rule, n_truth=NG, n_pred=NP,
                             matched=TP, precision=round(P, 3), recall=round(R, 3),
                             f1=round(2 * P * R / max(P + R, 1e-9), 3),
                             unmatched=NP - TP, missed=NG - TP))
            return (gpd.GeoDataFrame(pd.concat(leftovers, ignore_index=True), crs=CRS)
                    if leftovers else None)

        score("0 baseline (centroid, manifest only)", use_all=False, bidir=False, size=False)
        score("1 + all annotations (DEFECT FIX)", use_all=True, bidir=False, size=False)
        score("2 + bidirectional containment", use_all=True, bidir=True, size=False)
        left = score("3 + size filter", use_all=True, bidir=True, size=True)

        if left is not None and len(left):
            annu = ann_all.geometry.union_all()
            out = gpd.GeoDataFrame({
                "cand_id": 0, "score": left.score.round(3).values,
                "area_m2": left.geometry.area.round(0).values,
                "near_ann": [round(g.centroid.distance(annu), 1) for g in left.geometry],
                "thr_used": left.thr.values, "fold": left.fold.astype(int).values,
                "cx": left.geometry.centroid.x.round(2).values,
                "cy": left.geometry.centroid.y.round(2).values},
                geometry=left.geometry.values, crs=CRS)
            out = out.sort_values("score", ascending=False).reset_index(drop=True)
            out["cand_id"] = np.arange(1, len(out) + 1)
            shp = OUT / f"{name}_candidates_filtered_heldout_9t.shp"
            out.to_file(shp, driver="ESRI Shapefile")
            print(f"  -> {shp}  ({len(out)} candidates)")

    df = pd.DataFrame(rows)
    csv = OUT / "match_rule_ablation_pit_pad_9t.csv"
    df.to_csv(csv, index=False)
    print("\n" + "=" * 78)
    for name in TARGETS:
        print(f"\n{name.upper()}")
        print(df[df.target == name].drop(columns=["target"]).to_string(index=False))
    print(f"\nwrote {csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
