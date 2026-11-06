"""5.6 S0 input. Re-cut the held-out probability rasters at the policy cutoffs (pit 0.35, pad 0.525).

Purpose
    The held-out products that 5.6 S0 used were cut at 0.50 by notebooks/wellsight_v2/s5_eval. ek.policy_for gives
    0.35 for pits and 0.525 for pads. This script thresholds the SAME probability rasters at the policy cutoffs and
    writes the products 5.6 S0 reads. notebooks/ is imported, never edited. User accepted this on 2026-11-06.

    Pits. Same rule as notebooks/wellsight_v2/s5_eval/_build_undecided_pit_candidates_9t.py. Each CV5 fold raster is
    cut only inside its own held-out blocks (40 m score buffer, centroid inside the footprint), min area 4 m2, size
    filter off. Each blob is matched greedily by score to the per-key union of pit_full and pit_inside
    (bidirectional containment, overlap 0.5). Layers matched and undecided. The match is an evaluation label only.
    Pads. Same rule as notebooks/wellsight_v2/s5_eval/_pad_threshold_products_9t.py layer model_geometry. The whole
    tile pad probability raster is cut at the cutoff, min area 100 m2, score is the blob mean.

    --pit-thr 0.50 --pad-thr 0.50 is the reproduction check. Pads reproduce the old product exactly (1005 polygons).
    Pits give 658 blobs, not the old 688. The old pit product (2026-08-12) predates the current CV5 fold rasters
    (2026-09-17) and pit manifest (2026-09-04), so it cannot be rebuilt from them. Checked 2026-11-06.

Inputs
    @models/pit/unet_cv5/fold<k>/pit_prob_floor_cvfold<k>_9t_05.tif   (k = 0..4)
    @models/pad/unet/pad_prob.tif
    @nine_t/pit_dataset_manifest.csv, @nine_t/pit_blocks_9t.gpkg, @truth/annotations_proj.gpkg
Outputs (default cutoffs)
    expansions/5_tasks/5_6_record_association/data/interim/records_pit_recut_policy_9t.gpkg  (matched, undecided)
    expansions/5_tasks/5_6_record_association/data/interim/records_pad_recut_policy_9t.gpkg  (model_geometry)
    expansions/5_tasks/5_6_record_association/data/interim/_PROVENANCE_policy_recut.json
Run
    python expansions/5_tasks/5_6_record_association/src/_records_policy_recut_9t.py [--pit-thr X --pad-thr Y --out-dir D]
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402

ek = th.ek
_NB = ek.REPO / "notebooks" / "wellsight_v2"
for _p in (_NB, _NB / "s3_train", _NB / "s5_eval"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

PIT_MIN_AREA_M2 = 4.0      # as in _build_undecided_pit_candidates_9t.py
PAD_MIN_AREA_M2 = 100.0    # as in _pad_threshold_products_9t.py
SCORE_BUF_M = 40.0
OVERLAP_FRAC = 0.5
CV_SEED, K = 20260727, 5


def recorded_pits(ann):
    """Per-key union of pit_full (rim) and pit_inside (floor). Same key rule as the notebook builder."""
    import geopandas as gpd
    from _common import read_layer
    rims = read_layer(ann, "pit_full").to_crs(th.CRS)
    floors = read_layer(ann, "pit_inside").to_crs(th.CRS)
    for g in (rims, floors):
        g["geometry"] = g.geometry.buffer(0)

    def keyed(g):
        k = g.get("pit_inside_id")
        if "pit_full_id" in g.columns:
            alt = "o" + g["pit_full_id"].astype("Int64").astype(str)
            key = np.where(k.notna(), "p" + k.astype("Int64").astype(str), alt)
        else:
            key = "p" + k.astype("Int64").astype(str)
        out = g[["geometry"]].copy()
        out["pit_key"] = key
        return out

    both = pd.concat([keyed(rims), keyed(floors)], ignore_index=True)
    pits = gpd.GeoDataFrame(both, crs=th.CRS).dissolve(by="pit_key").reset_index()
    pits["geometry"] = pits.geometry.buffer(0)
    return pits[~pits.geometry.is_empty].reset_index(drop=True)


def cut_pits(thr: float):
    """Held-out pit blobs at thr. Returns (matched, undecided, per-fold counts, raster paths)."""
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize
    from _common import normalize_ids
    from _pit_unet_cv5 import assign_folds, polygonize
    from _build_undecided_pit_candidates_9t import build_pairs, greedy
    nine = ek.path_for("nine_t")
    man = normalize_ids(pd.read_csv(nine / "pit_dataset_manifest.csv"))
    blocks = gpd.read_file(nine / "pit_blocks_9t.gpkg", layer="blocks").to_crs(th.CRS)
    nper = man.groupby("block_id").size().rename("n_pits").reset_index()
    fo = assign_folds(nper[["block_id", "n_pits"]], K, CV_SEED)
    man["fold"] = man.block_id.map(fo)
    pits = recorded_pits(ek.path_for("truth") / "annotations_proj.gpkg")
    allpit = pits.geometry.union_all()
    mat, und, counts, rasters = [], [], [], []
    for k in range(K):
        tif = ek.path_for("models") / "pit" / "unet_cv5" / f"fold{k}" / f"pit_prob_floor_cvfold{k}_9t_05.tif"
        if not tif.exists():
            raise th.MissingInput(f"pit_prob_fold{k}", tif, "CV5 fold probability raster")
        rasters.append(tif)
        with rasterio.open(tif) as r:
            prob, tf, rcrs = r.read(1).astype(np.float32), r.transform, r.crs
        hb = sorted(man.loc[man.fold == k, "block_id"].unique())
        foot = blocks.loc[blocks.block_id.isin(hb)].geometry.union_all()
        msk = rasterize([(foot.buffer(SCORE_BUF_M), 1)], out_shape=prob.shape, transform=tf,
                        fill=0, dtype="uint8").astype(bool)
        allp = polygonize(np.where(msk, prob, 0.0).astype(np.float32), tf, rcrs, thr, min_area=PIT_MIN_AREA_M2)
        pr = allp[allp.geometry.centroid.within(foot)].reset_index(drop=True) if len(allp) else allp
        gt = pits[[c.within(foot) for c in pits.geometry.centroid]].reset_index(drop=True)
        _, up = greedy(build_pairs(gt, pr, overlap_frac=OVERLAP_FRAC))
        hit = np.array([i in up for i in range(len(pr))], bool)
        for part, keep in ((mat, hit), (und, ~hit)):
            d = pr[keep].copy()
            d["fold"], d["thr_used"] = k, thr
            part.append(d)
        counts.append(dict(fold=k, n_pred=int(len(pr)), n_matched=int(hit.sum()), n_undecided=int((~hit).sum())))

    def package(parts):
        g = gpd.GeoDataFrame(pd.concat([p for p in parts if len(p)], ignore_index=True), crs=th.CRS)
        c = g.geometry.centroid
        out = gpd.GeoDataFrame({
            "score": g.score.round(3).values, "area_m2": g.geometry.area.round(1).values,
            "near_pit_m": [round(x.distance(allpit), 1) for x in c],
            "dup_on_pit": [int(x.within(allpit)) for x in c],
            "fold": g.fold.astype(int).values, "thr_used": g.thr_used.values,
            "cx": c.x.round(2).values, "cy": c.y.round(2).values}, geometry=g.geometry.values, crs=th.CRS)
        return out.sort_values("score", ascending=False).reset_index(drop=True)

    return package(mat), package(und), counts, rasters


def cut_pads(thr: float):
    """Whole-tile pad polygons at thr (layer model_geometry of the notebook products)."""
    import rasterio
    from _threshold_common import polygonize
    prob_p = ek.path_for("models") / "pad" / "unet" / "pad_prob.tif"
    if not prob_p.exists():
        raise th.MissingInput("pad_prob", prob_p, "pad U-Net probability raster")
    with rasterio.open(prob_p) as r:
        prob = r.read(1).astype(np.float32)
        if r.nodata is not None:
            prob = np.where(prob == r.nodata, 0.0, prob)
        tf, pcrs = r.transform, r.crs
    pred = polygonize(prob, tf, pcrs, thr, PAD_MIN_AREA_M2)
    pred = pred.to_crs(th.CRS) if pred.crs and pred.crs.to_string() != th.CRS else pred
    pred["thr_used"] = thr
    return pred, prob_p


def main(argv=None) -> int:
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pit-thr", type=float)
    ap.add_argument("--pad-thr", type=float)
    ap.add_argument("--out-dir", help="default expansions/5_tasks/5_6_record_association/data/interim")
    a = ap.parse_args(argv)
    pol_pit, pol_pad = ek.policy_for("pit"), ek.policy_for("pad")
    tp = pol_pit["cutoff"] if a.pit_thr is None else a.pit_thr
    td = pol_pad["cutoff"] if a.pad_thr is None else a.pad_thr
    out = Path(a.out_dir) if a.out_dir else ek.exp_dir("5.6") / "data" / "interim"
    out.mkdir(parents=True, exist_ok=True)
    policy = (a.pit_thr is None and a.pad_thr is None)
    sfx = "policy" if policy else ("thr" + f"{tp:g}".replace(".", "p") + "_" + f"{td:g}".replace(".", "p"))
    op, od = out / f"records_pit_recut_{sfx}_9t.gpkg", out / f"records_pad_recut_{sfx}_9t.gpkg"
    mat, und, counts, rasters = cut_pits(tp)
    pad, pad_raster = cut_pads(td)
    for p in (op, od):
        if p.exists():
            p.unlink()
    mat.to_file(op, layer="matched", driver="GPKG")
    und.to_file(op, layer="undecided", driver="GPKG")
    pad.to_file(od, layer="model_geometry", driver="GPKG")
    params = dict(pit_cutoff=tp, pad_cutoff=td, policy_pit=pol_pit, policy_pad=pol_pad, at_policy=policy,
                  pit_min_area_m2=PIT_MIN_AREA_M2, pad_min_area_m2=PAD_MIN_AREA_M2, score_buf_m=SCORE_BUF_M,
                  overlap_frac=OVERLAP_FRAC, cv_seed=CV_SEED, folds=K, per_fold=counts,
                  rows=dict(pit_matched=len(mat), pit_undecided=len(und), pit_total=len(mat) + len(und),
                            pad=len(pad)),
                  rule_source=["notebooks/wellsight_v2/s5_eval/_build_undecided_pit_candidates_9t.py",
                               "notebooks/wellsight_v2/s5_eval/_pad_threshold_products_9t.py"])
    ek.write_provenance(out, inputs=rasters + [pad_raster], outputs=[op, od], params=params,
                        name="policy_recut" if policy else f"recut_{sfx}")
    print(pd.DataFrame(counts).to_string(index=False))
    print(f"pit cutoff {tp}: {len(mat)} matched + {len(und)} undecided = {len(mat) + len(und)}")
    print(f"pad cutoff {td}: {len(pad)} polygons")
    for p in (op, od):
        print("wrote", th.rel(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
