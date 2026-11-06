"""3.2 S11 (Q3, conditional). Adapt on the companion window, evaluate paired on the primary window's test blocks.

Purpose
    Runs only when the primary window's preregistered score is a failure (read from its S8
    score JSON), unless --design-test. The companion window's zero-shot score must already be
    recorded, then the companion is burned for adaptation. Steps.
      1. Labels. Rasterise the companion truth (pit_inside = 1 floor, pit_full minus floor = 2
         wall) on the companion 0.5 m stack grid.
      2. Normalisation. mu and sd fitted on the companion adaptation blocks only.
      3. Fine-tune from the isolated checkpoint (P1, assumed) with the repo trainer
         (_dl.CenteredPatchSampler, _dl.FocalCE, _dl.train_loop). Inner validation is a
         seeded 20% of companion blocks, saved to a split file before training.
      4. Paired evaluation. Zero-shot and adapted models scored on the same primary test
         blocks, the same truth, the same K. Paired block bootstrap (same draws for both arms).
    Own preregistration. One run. GPU. Measure one epoch first (epoch time was under-reported
    by 1.8 times, BACKLOG).

Inputs
    companion   data/processed/<pair>/05/features_pit_<pair>_05.tif, assumed.truth for <pair>,
                results/tables/<pair>/xfer_blocks_roles_<pair>.gpkg
    primary     results/<run>/xfer_score_k40_<tag>.json (decision), its prob raster, roles and truth
    model       assumed.isolated_ckpt (pit)

Outputs
    expansions/3_geography/3_2_appalachian_states/models/adapt_<pair>/best.pt, train_log.csv, split_adapt_<pair>.csv
    expansions/3_geography/3_2_appalachian_states/data/processed/<tag>/05/pit_prob_adapt_<tag>_05.tif
    expansions/3_geography/3_2_appalachian_states/results/<run_id>/xfer_adapt_paired_<tag>.json

Run (GPU, gated; not run by the build agent)
    python expansions/3_geography/3_2_appalachian_states/src/_appal_adapt_finetune.py --tag ky_lee --epochs 1
    python expansions/3_geography/3_2_appalachian_states/src/_appal_adapt_finetune.py --tag ky_lee --epochs 30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
SRC31 = HERE.parents[2] / "3_1_warren_forest_mckean" / "src"
sys.path.insert(0, str(SRC31))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_2.json"


def rasterize_pit_labels(floors, rims, features_tif: Path, out: Path) -> Path:
    import rasterio
    from rasterio.features import rasterize
    with rasterio.open(features_tif) as r:
        ek.assert_crs(r)
        shp, tf = (r.height, r.width), r.transform
    lab = np.zeros(shp, np.uint8)
    if len(rims):
        lab = rasterize(((g, 2) for g in rims.geometry), out_shape=shp, transform=tf, fill=0, dtype="uint8")
    if len(floors):
        fl = rasterize(((g, 1) for g in floors.geometry), out_shape=shp, transform=tf, fill=0, dtype="uint8")
        lab[fl == 1] = 1
    from _common import write_tif
    write_tif(out, lab, transform=tf, crs=ek.DST_CRS, dtype="uint8", nodata=255)
    return out


def fit_norm(features_tif: Path, blocks, max_px: int = 2_000_000, seed: int = 0):
    """Per-channel mean and std from cells inside adaptation blocks only."""
    import rasterio
    from rasterio.windows import from_bounds
    rng = np.random.default_rng(seed)
    acc = []
    with rasterio.open(features_tif) as r:
        for g in blocks.geometry:
            w = from_bounds(*g.bounds, transform=r.transform).round_offsets().round_lengths()
            a = r.read(window=w).reshape(r.count, -1)
            acc.append(a[:, rng.choice(a.shape[1], min(a.shape[1], max_px // max(len(blocks), 1)), replace=False)])
    x = np.concatenate(acc, axis=1)
    return np.nanmean(x, 1).astype(np.float32), np.maximum(np.nanstd(x, 1), 1e-6).astype(np.float32)


def paired_eval(rows_zero, rows_adapt, B, seed):
    """Same blocks, same draws. Returns adapted minus zero-shot pooled recall with interval."""
    rz, ra = [tuple(r) for r in rows_zero], [tuple(r) for r in rows_adapt]
    d, lo, hi = ek.bootstrap_diff(xl.pooled_recall, ra, xl.pooled_recall, rz, B=B, seed=seed, paired=True)
    return {"adapted_minus_zero_shot": d, "lo": lo, "hi": hi, "n_blocks": len(rz)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--tag", required=True, help="primary window tag")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--design-test", action="store_true", help="run even if the primary did not fail (labelled)")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    A = cfg["areas"][a.tag]
    pair = A["pair"]
    import geopandas as gpd
    import torch
    from torch.utils.data import DataLoader
    from _common import read_layer
    from _dl import CenteredPatchSampler, FocalCE, UNet
    from _dl import train_loop
    sys.path.insert(0, str(SRC31))
    from _xfer_score_k40_wfm import candidates_in_blocks
    res_dir = ek.sub("3.2", "results")
    runs = sorted(res_dir.glob(f"*_xfer_score_{a.tag}_*"))
    if not runs:
        raise xl.MissingInput(f"MISSING INPUT: primary score run for {a.tag} (3.1 _xfer_score_k40_wfm.py with this config)")
    prim = json.loads((runs[-1] / f"xfer_score_k40_{a.tag}.json").read_text())
    if prim["primary"]["decision"] != "failure" and not a.design_test:
        print(f"primary decision {prim['primary']['decision']}; Q3 not triggered")
        return 0
    if not sorted(res_dir.glob(f"*_xfer_score_{pair}_*")):
        raise xl.MissingInput(f"MISSING INPUT: companion {pair} zero-shot score must be recorded before it is burned")
    cctx, pctx = xl.area_ctx(cfg, pair), xl.area_ctx(cfg, a.tag)
    feats_c = xl.need(cctx["heavy"] / f"features_pit_{pair}_05.tif", f"{pair} stack")
    roles_c = gpd.read_file(xl.need(cctx["tables"] / f"xfer_blocks_roles_{pair}.gpkg", f"{pair} roles"), layer="blocks")
    tc = xl.assumed_path(cfg, "truth", pair)
    floors = read_layer(tc, "pit_inside").to_crs(ek.DST_CRS)
    rims = read_layer(tc, "pit_full").to_crs(ek.DST_CRS)
    adapt = roles_c[roles_c.eligible.astype(bool)].copy()
    seed = ek.child_seed(cfg["master_seed"], 0, 11)
    rng = np.random.default_rng(seed)
    ids = adapt.block_id.to_numpy().copy(); rng.shuffle(ids)
    n_val = max(1, int(round(0.2 * len(ids))))
    adapt["split"] = np.where(adapt.block_id.isin(ids[:n_val]), "val", "train")
    mdir = ek.sub("3.2", f"models/adapt_{pair}")
    adapt[["block_id", "split"]].to_csv(mdir / f"split_adapt_{pair}.csv", index=False)   # saved before training
    labels = rasterize_pit_labels(floors, rims, feats_c, cctx["heavy"] / f"labels_pit_{pair}_05.tif")
    mu, sd = fit_norm(feats_c, adapt[adapt.split == "train"], seed=seed)
    ck = xl.assumed_path(cfg, "isolated_ckpt", task="pit", k=0)
    model, _, _, ch, _ = xl.load_ckpt(ck, 3)
    xl.check_channels(feats_c, ch)
    import rasterio
    with rasterio.open(feats_c) as r:
        tf = r.transform

    def loader(split, aug):
        b = adapt[adapt.split == split]
        pts = np.c_[floors.geometry.representative_point().x, floors.geometry.representative_point().y]
        inside = gpd.GeoSeries(gpd.points_from_xy(pts[:, 0], pts[:, 1]), crs=ek.DST_CRS).within(b.geometry.union_all())
        ds = CenteredPatchSampler(feats_c, labels, [("pit", pts[inside.to_numpy()], 30.0)], b.geometry.bounds.to_numpy(),
                                  tf, mu, sd, patch=256, augment=aug, seed=seed)
        return DataLoader(ds, batch_size=8, shuffle=False, num_workers=0)
    out = train_loop(model=model, train_loader=loader("train", True), val_loader=loader("val", False),
                     loss_fn=FocalCE(alpha=(0.05, 0.475, 0.475), gamma=2.0), epochs=a.epochs, lr=a.lr, n_classes=3,
                     out_dir=mdir, checkpoint_extra={"channels": list(ch), "mu": mu, "sd": sd, "source_ckpt": str(ck),
                                                     "adapt_window": pair},
                     score=lambda iou: float(iou[1]), extra_iou_names=("bg", "floor", "wall"))
    feats_p = xl.need(pctx["heavy"] / f"features_pit_{a.tag}_05.tif", f"{a.tag} stack")
    prob, prof, _ = xl.ensemble_prob(feats_p, [mdir / "best.pt"], n_classes=3, patch=256, overlap=64, cls=1)
    pa = pctx["heavy"] / f"pit_prob_adapt_{a.tag}_05.tif"
    pr = dict(prof); pr.update(count=1, dtype="float32", nodata=-1.0, compress="deflate")
    with rasterio.open(pa, "w", **pr) as d:
        d.write(prob, 1)
    roles_p = gpd.read_file(pctx["tables"] / f"xfer_blocks_roles_{a.tag}.gpkg", layer="blocks")
    test = roles_p[(roles_p.role == "test") & roles_p.eligible.astype(bool)]
    tp = read_layer(xl.assumed_path(cfg, "truth", a.tag), "pit_inside").to_crs(ek.DST_CRS)
    tp = tp[["pit_inside_id", "geometry"]].dissolve(by="pit_inside_id").reset_index().rename(columns={"pit_inside_id": "truth_id"})
    thr = prim["proposal_thr"]
    _, per_z, _, _ = xl.score_area(candidates_in_blocks(Path(prim["prob"]), test, thr, cfg["min_blob_m2"]), tp, test)
    _, per_a, _, _ = xl.score_area(candidates_in_blocks(pa, test, thr, cfg["min_blob_m2"]), tp, test)
    res = paired_eval(zip(per_z.hits, per_z.n_truth), zip(per_a.hits, per_a.n_truth), cfg["bootstrap_B"], seed)
    res.update({"tag": a.tag, "adapt_window": pair, "design_test": a.design_test, "train": out["best_score"]})
    run = ek.new_run("3.2", f"xfer_adapt_{a.tag}", {"tag": a.tag, "pair": pair, "epochs": a.epochs, "lr": a.lr})
    js = run / f"xfer_adapt_paired_{a.tag}.json"
    js.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    ek.write_provenance(run, inputs=[feats_c, feats_p, ck, tc], outputs=[mdir / "best.pt", pa, js], seeds={"adapt": seed})
    print(json.dumps(res, indent=2, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
