"""Export the pit detections that match no annotated pit -- the undecided set.

Every prediction here comes from the CV5 fold model that did NOT train on the
block it falls in, so these are held-out detections, not memorisation residue.
A prediction that lands on an annotated rim is a true positive and is filtered
out. What remains is either a false positive or a real well nobody has drawn
yet, and nothing in the data distinguishes the two -- that is what the review
decides.

A pit is "recorded" if it appears in EITHER annotation layer, and NO annotated
feature may be dropped on the way in. Two traps, both of which bit earlier
versions of this script:

  * `_prep_annotations.py` pairs floors to rims and writes `pit_id` onto the
    rim only when a pairing succeeded. 137 rims have no floor inside them and
    carry a NULL `pit_id`. `dissolve(by="pit_id")` throws those rows away
    silently, so a prediction sitting squarely on one of them came out
    "undecided" while the annotator could see the rim in QGIS. The key here is
    `pit_id` where present and `o<pit_id_outer>` otherwise, so every rim counts.
  * 105 floors have no rim. Matching on rims alone loses those too.

Match target is therefore the per-key union of `pit_outside` and `pit_inside`:
550 paired pits + 105 floor-only + 137 rim-only.

Matching otherwise follows `_match_rules_pit_pad_9t.py`, so the `undecided`
layer is the false-positive set behind the reported precision:

  * scored against EVERY current annotation inside the held-out footprint, not
    just the ones carried in the fold manifest
  * bidirectional containment -- centroid(pred) in rim, OR centroid(rim) in
    pred, OR area(intersection)/min(area) >= OVERLAP_FRAC
  * greedy 1:1, highest-scoring prediction first, so extra blobs on an
    already-matched pit stay in the undecided pile rather than counting twice
The log10 size filter that `_match_rules_pit_pad_9t.py` applies to pads is OFF
by default here. It does not transfer to pits. Annotated floors run 6 to 115 m2,
and a 3-sigma log cut lands at 6.1 m2 -- ABOVE the smallest real floor. It was
rejecting predictions of 4.2 to 6.0 m2 that sit on annotated pits, turning 8 true
positives into invisible nothings and depressing recall. A filter meant to remove
blobs "far smaller than any annotated feature" must sit below the observed
minimum; this one did not. `--size-filter` re-enables it and the run reports what
it would have cost.

Rerun this after adding annotations. Pits drawn since the last run now match and
disappear from `undecided`, which is the whole point -- the layer shrinks as the
ground truth catches up with the model.

Output layers in pit_candidates_undecided_thr0p50_9t.gpkg (EPSG:6346):
    undecided      unmatched prediction, size-plausible  <- REVIEW THIS ONE
    size_rejected  unmatched but smaller than any annotated floor
    matched        prediction paired with a recorded pit  (context)
    missed_pit     recorded pit holding no prediction     (context)

`status` on `undecided` is empty and is yours to fill: 'pit' / 'not_pit' /
'unsure'. `near_pit_m` is the distance from the blob centroid to the nearest
recorded pit -- a few metres means the model found a known pit but the centroid
drifted outside it, tens of metres means it fired on something else.

Outputs (data/derivatives/eval_9t_centroid_matching/):
    pit_candidates_undecided_thr0p50_9t.gpkg
    _pit_candidates_undecided_thr0p50_9t.json
    README_EDIT_pit_candidates.md

Reproduce:
  python notebooks/wellsight_v2/s5_eval/_build_undecided_pit_candidates_9t.py
  ... --thr 0.50 --n-sd 3.0 --overlap-frac 0.5
"""
from __future__ import annotations

import argparse
import json
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
                str(ROOT / "notebooks" / "wellsight_v2" / "s3_train")]
from _common import DERIV_9T, path_for  # noqa: E402
from _pit_unet_cv5 import assign_folds, polygonize                 # noqa: E402

ANN = path_for("truth") / "annotations_proj.gpkg"
OUT = path_for("derivatives") / "eval_9t_centroid_matching"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"
OUTDIR = DERIV_9T / "pit_unet_cv5"

CRS = "EPSG:6346"
CV_SEED = 20260727          # must match the CV run
K = 5
MIN_AREA_M2 = 4.0
SCORE_BUF_M = 40.0
RIM_LAYER = "pit_outside"   # rims
FLOOR_LAYER = "pit_inside"  # floors -- what the model actually draws
# Match target is the per-pit_id UNION of both. Size reference is floors only.


def build_pairs(gt, pred, *, overlap_frac):
    """(gt_index, pred_index, score) under bidirectional containment."""
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
            if not ok and p.contains(gc.iloc[gi]):
                ok = True
            if not ok:
                denom = min(g.area, p.area)
                ok = denom > 0 and g.intersection(p).area / denom >= overlap_frac
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
    ap.add_argument("--thr", type=float, default=0.50)
    ap.add_argument("--n-sd", type=float, default=3.0)
    ap.add_argument("--overlap-frac", type=float, default=0.5)
    ap.add_argument("--size-filter", action="store_true",
                    help="re-enable the log10 size cut (off by default: for "
                         "pits it lands above the smallest annotated floor)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"thr{args.thr:.2f}".replace(".", "p")

    with rasterio.open(FEATURES) as r:
        tf, rcrs = r.transform, r.crs

    man = pd.read_csv(DERIV_9T / "pit_dataset_manifest.csv")
    blocks = gpd.read_file(DERIV_9T / "pit_blocks_9t.gpkg", layer="blocks").to_crs(CRS)
    nper = man.groupby("block_id").size().rename("n_pits").reset_index()
    fo = assign_folds(nper[["block_id", "n_pits"]], K, CV_SEED)
    man["fold"] = man.block_id.map(fo)
    blocks["fold"] = blocks.block_id.map(fo)

    # EVERY current annotation, not only manifest rows. A pit counts as recorded
    # if it appears in either layer, so the target is the per-pit_id union.
    rims = gpd.read_file(ANN, layer=RIM_LAYER).to_crs(CRS)
    floors = gpd.read_file(ANN, layer=FLOOR_LAYER).to_crs(CRS)
    for g in (rims, floors):
        g["geometry"] = g.geometry.buffer(0)

    # Key on pit_id where prep managed to pair a floor to a rim, and on
    # pit_id_outer otherwise. Dissolving on pit_id alone drops every rim that
    # has no floor -- 137 of them -- which is how real rims went missing.
    def keyed(g, prefix):
        k = g.get("pit_id")
        if "pit_id_outer" in g.columns:
            alt = "o" + g["pit_id_outer"].astype("Int64").astype(str)
            key = np.where(k.notna(), prefix + k.astype("Int64").astype(str), alt)
        else:
            key = prefix + k.astype("Int64").astype(str)
        out = g[["geometry"]].copy()
        out["pit_key"] = key
        return out

    both = pd.concat([keyed(rims, "p"), keyed(floors, "p")], ignore_index=True)
    n_rim_nokey = int(rims.pit_id.isna().sum())
    pits = gpd.GeoDataFrame(both, crs=CRS).dissolve(by="pit_key").reset_index()
    pits["geometry"] = pits.geometry.buffer(0)
    pits = pits[~pits.geometry.is_empty].reset_index(drop=True)

    rid = set(rims.pit_id.dropna().unique())
    fid = set(floors.pit_id.dropna().unique())

    a = floors[~floors.geometry.is_empty].geometry.area.to_numpy()
    la = np.log10(a[a > 0])
    cut = 10 ** (la.mean() - args.n_sd * la.std()) if args.size_filter else 0.0
    print(f"annotations: {len(rims)} rim feats ({n_rim_nokey} with no pit_id), "
          f"{len(floors)} floor feats -> {len(pits)} recorded pits")
    print(f"  {len(rid & fid)} paired, {len(fid - rid)} floor-only, "
          f"{n_rim_nokey} rim-only")
    print(f"floor area: min {a.min():.0f}, mean {a.mean():.0f}, max {a.max():.0f} m2")
    if args.size_filter:
        print(f"size cut ON: log10 {args.n_sd:.1f} sd -> {cut:.1f} m2")
        if cut > a.min():
            print(f"  WARNING: cut {cut:.1f} is ABOVE the smallest annotated "
                  f"floor ({a.min():.0f} m2) and will reject real pits")
    else:
        would = 10 ** (la.mean() - args.n_sd * la.std())
        print(f"size cut OFF (would have been {would:.1f} m2, above the "
              f"{a.min():.0f} m2 smallest annotated floor)")

    und, rej, mat, mis = [], [], [], []
    for k in range(K):
        tif = OUTDIR / f"fold{k}" / f"pit_prob_floor_cvfold{k}_9t_05.tif"
        if not tif.exists():
            print(f"  fold {k}: MISSING {tif} -- skipped")
            continue
        with rasterio.open(tif) as r:
            prob = r.read(1).astype(np.float32)
        hb = sorted(man.loc[man.fold == k, "block_id"].unique())
        foot = blocks.loc[blocks.block_id.isin(hb)].geometry.union_all()
        msk = _rast([(foot.buffer(SCORE_BUF_M), 1)], out_shape=prob.shape,
                    transform=tf, fill=0, dtype="uint8").astype(bool)
        allp = polygonize(np.where(msk, prob, 0.0).astype(np.float32),
                          tf, rcrs, args.thr, min_area=MIN_AREA_M2)
        pr = (allp[allp.geometry.centroid.within(foot)].reset_index(drop=True)
              if len(allp) else allp)
        gt = pits[[c.within(foot) for c in pits.geometry.centroid]].reset_index(drop=True)

        big = pr[pr.geometry.area >= cut].reset_index(drop=True)
        small = pr[pr.geometry.area < cut].reset_index(drop=True)
        ug, up = greedy(build_pairs(gt, big, overlap_frac=args.overlap_frac))

        m = big[[i in up for i in range(len(big))]].copy()
        u = big[[i not in up for i in range(len(big))]].copy()
        miss = gt[[i not in ug for i in range(len(gt))]].copy()
        for df in (m, u, small):
            df["fold"] = k
            df["thr_used"] = args.thr
        miss["fold"] = k
        mat.append(m); und.append(u); rej.append(small); mis.append(miss)
        print(f"  fold {k}: {len(pr):4d} pred ({len(small)} below size cut) | "
              f"{len(m):4d} matched, {len(u):4d} undecided | "
              f"{len(gt):3d} pits, {len(miss):3d} missed")

    def cat(parts):
        parts = [p for p in parts if len(p)]
        if not parts:
            return gpd.GeoDataFrame(geometry=[], crs=CRS)
        return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)

    und, rej, mat, mis = cat(und), cat(rej), cat(mat), cat(mis)
    allpit = pits.geometry.union_all()

    def package(g, with_status):
        if not len(g):
            return g
        out = gpd.GeoDataFrame({
            "cand_id": np.arange(1, len(g) + 1),
            "status": "" if with_status else None,
            "score": g.score.round(3).values,
            "area_m2": g.geometry.area.round(1).values,
            "near_pit_m": [round(x.centroid.distance(allpit), 1) for x in g.geometry],
            # 1 = centroid sits inside a pit you already drew, but a
            # higher-scoring blob claimed it first. Not a new find; the model
            # split one pit into two. Filter these out when reviewing.
            "dup_on_pit": [int(x.centroid.within(allpit)) for x in g.geometry],
            "fold": g.fold.astype(int).values,
            "thr_used": g.thr_used.values,
            "cx": g.geometry.centroid.x.round(2).values,
            "cy": g.geometry.centroid.y.round(2).values},
            geometry=g.geometry.values, crs=CRS)
        out = out.sort_values("score", ascending=False).reset_index(drop=True)
        out["cand_id"] = np.arange(1, len(out) + 1)
        if not with_status:
            out = out.drop(columns=["status"])
        return out

    und_p, rej_p, mat_p = package(und, True), package(rej, False), package(mat, False)

    # QGIS holds a lock on an open GeoPackage. Stage beside it rather than lose
    # the run; the file name says plainly that it is not the live one.
    gpkg = OUT / f"pit_candidates_undecided_{tag}_9t.gpkg"
    if gpkg.exists():
        try:
            gpkg.unlink()
        except PermissionError:
            gpkg = OUT / f"pit_candidates_undecided_{tag}_9t_PENDING.gpkg"
            print(f"\n  target is LOCKED (open in QGIS). Writing to {gpkg.name} "
                  f"instead.\n  Close the layer and rerun to replace the live file.")
            if gpkg.exists():
                gpkg.unlink()
    for nm, g in (("undecided", und_p), ("size_rejected", rej_p),
                  ("matched", mat_p), ("missed_pit", mis)):
        if len(g):
            g.reset_index(drop=True).to_file(gpkg, layer=nm, driver="GPKG")

    n_pred = len(und) + len(mat)
    prec = len(mat) / max(n_pred, 1)
    rec = len(mat) / max(len(mat) + len(mis), 1)
    print(f"\nthr {args.thr:.2f}, current annotations:")
    print(f"  {n_pred} size-plausible predictions, {len(mat)} matched, "
          f"{len(und)} UNDECIDED  (precision {prec:.3f})")
    print(f"  {len(mat) + len(mis)} recorded pits in held-out footprints, "
          f"{len(mis)} missed  (recall {rec:.3f})")
    print(f"  {len(rej)} blobs below the size cut, kept in 'size_rejected'")
    if len(und_p):
        d = und_p.near_pit_m
        print("\n  undecided, by distance to the nearest recorded pit:")
        for lo, hi in ((0, 5), (5, 15), (15, 50), (50, 1e9)):
            n = int(((d >= lo) & (d < hi)).sum())
            lab = f"{lo}-{hi:g} m" if hi < 1e9 else f">{lo} m"
            print(f"    {lab:>10s}: {n:4d} ({100 * n / len(und_p):.1f}%)")
        print(f"    median {d.median():.1f} m   score range "
              f"{und_p.score.min():.2f}-{und_p.score.max():.2f}")

    summ = {"date": "2026-08-05", "threshold": args.thr, "n_sd": args.n_sd,
            "overlap_frac": args.overlap_frac, "size_cut_m2": round(float(cut), 1),
            "match_target": "per-key union of pit_outside and pit_inside; key is "
                            "pit_id where prep paired them, pit_id_outer otherwise",
            "size_filter_on": bool(args.size_filter),
            "recorded_pits": int(len(pits)),
            "rim_feats": int(len(rims)), "floor_feats": int(len(floors)),
            "rims_with_no_pit_id": n_rim_nokey,
            "paired_pits": int(len(rid & fid)), "floor_only_pits": int(len(fid - rid)),
            "n_pred_size_plausible": int(n_pred), "n_matched": int(len(mat)),
            "n_undecided": int(len(und)), "n_size_rejected": int(len(rej)),
            "n_pits_heldout": int(len(mat) + len(mis)), "n_missed": int(len(mis)),
            "precision": round(prec, 3), "recall": round(rec, 3),
            "gpkg": str(gpkg)}
    js = OUT / f"_pit_candidates_undecided_{tag}_9t.json"
    js.write_text(json.dumps(summ, indent=2))

    readme = OUT / "README_EDIT_pit_candidates.md"
    readme.write_text(f"""# Pit candidate review — 9t, threshold {args.thr:.2f}

`{gpkg.name}` layer **undecided** holds {len(und)} held-out detections that match
no recorded pit. A pit counts as recorded if it appears in EITHER `pit_outside`
(rim) or `pit_inside` (floor): {len(fid - rid)} are drawn as a floor with no rim and
{n_rim_nokey} as a rim with no floor, and all of them count. Each candidate is either a
false positive or a well nobody has drawn yet.

## How to review
1. Load `{DERIV_9T / 'hillshade_9t_05.tif'}` as a basemap.
2. Load the `undecided` layer from `{gpkg}`.
3. Toggle editing. For each candidate set **status**:
   - `pit` — it is a real pit. Draw it into `pit_inside` / `pit_outside` as usual.
   - `not_pit` — it is not.
   - `unsure` — leave it out of the scoring either way.
4. Save edits.

## Reading the fields
- `score` — model confidence, {0 if not len(und_p) else und_p.score.min():.2f} to \
{0 if not len(und_p) else und_p.score.max():.2f}. Sorted descending, so `cand_id` 1 is the most confident.
- `near_pit_m` — metres to the nearest recorded pit (rim or floor). A few metres
  usually means the model found a known pit but the blob centroid drifted outside
  it; tens of metres means it fired on something else.
- `dup_on_pit` — 1 means the blob centroid sits inside a pit you already drew,
  but a higher-scoring blob claimed that pit first, so this one is a second piece
  of the same pit rather than a new find. Filter `dup_on_pit = 0` to review only
  genuine candidates.
- `fold` — which CV fold model produced it. None of them trained on this block.

## Other layers (context, do not edit)
- `size_rejected` — {len(rej)} blobs smaller than any annotated floor
  (below {cut:.1f} m2). Excluded from precision, kept here so nothing is hidden.
- `matched` — {len(mat)} predictions already paired with a recorded pit.
- `missed_pit` — {len(mis)} recorded pits the model did not find.

Rerun after annotating and the undecided list shrinks:
`python notebooks/wellsight_v2/s5_eval/_build_undecided_pit_candidates_9t.py`
""")

    print(f"\nwrote {gpkg}")
    print(f"wrote {js}")
    print(f"wrote {readme}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
