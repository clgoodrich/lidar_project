"""6.2 S4 and S6. Mine-class U-Net (M, S, H) and the well model with mine negatives. Wrapper on 6.3, no edits.

Purpose
    --make-split  Save the coal block folds before any training (protocol section 3 rule 1). Five folds balanced
                  on adjudicated mine-feature count (the trainer's own greedy assign_folds), 20% inner validation
                  per fold seeded per fold, audit blocks excluded from every role.
    --burn        Burn adjudicated polygons into two label rasters.
                    mine task     bg 0, M 1, S 2, H 3. W and O stay 0 and become centred negative windows.
                    wellneg task  mine pixels 3 (the 6.3 confuser class), W pixels 255 (ignored), else 0.
                  Polygons come from adjudicated M S H W O candidates plus polygons reviewers drew.
                  Inventory records are never labels before the S0 gate passes.
    --task mine     (S4) 4-class model on the coal area, classes bg M S H, W and O as explicit negatives,
                    3 seeds x 5 folds, fold-local normalisation, whole-window guard (6.3 IsolatedSampler path).
    --task wellneg  (S6) The 6.3 pit model trained on 9t windows plus coal-area windows centred on M S H
                    polygons as the negative class (torch ConcatDataset). Arms baseline, confuser (mine
                    negatives) and random come from the 6.3 trainer. Normalisation is fitted on the pooled
                    training windows of both areas. Scoring uses the 6.3 pooled blind scorer with this config.
    Default is a dry run (plan JSON and leakage assertions). --train trains on the GPU.
Inputs
    data/greene/results/coal/confuser_labels_adjudicated_greene.csv, confuser_sheet_key_greene.csv (S2)
    data/greene/results/coal/candidates/coal_well_candidates_greene.gpkg (S1), coal_polygons_greene.gpkg (optional)
    data/greene/derived/05/features_pit_greene_05.tif and coal_blocks_greene.gpkg (S1)
    9t inputs for wellneg from config_6_3.json (features, labels, manifest, P1 split, P2 audit)
Outputs
    expansions/6_adjacent/6_2_coal_features/results/tables/coal_split_blocks_greene.csv
    expansions/6_adjacent/6_2_coal_features/data/processed/labels_coal_{mine,wellneg}_greene_05.tif, coal manifest CSV
    expansions/6_adjacent/6_2_coal_features/models/unet_coal_cv5/<task>/<arm>/seed<s>/fold<k>/ (git-ignored)
    expansions/6_adjacent/6_2_coal_features/results/tables/coal_train_plan_greene.json
Run
    python expansions/6_adjacent/6_2_coal_features/src/_coal_unet_cv5_coal.py --make-split
    python expansions/6_adjacent/6_2_coal_features/src/_coal_unet_cv5_coal.py --burn
    python expansions/6_adjacent/6_2_coal_features/src/_coal_unet_cv5_coal.py --task mine            (dry run)
    python expansions/6_adjacent/6_2_coal_features/src/_coal_unet_cv5_coal.py --task wellneg --train --seeds 0 --only-folds 0
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _coal_common as K
from _coal_common import C, ek

MINE_CODE = {"M": 1, "S": 2, "H": 3}


def labelled_polygons(cfg: dict, adjudicated: pd.DataFrame, key: pd.DataFrame, cands, drawn=None):
    import geopandas as gpd
    a = adjudicated.merge(key[["sheet_id", "uid"]], on="sheet_id", how="left", suffixes=("", "_k"))
    if "uid_k" in a:
        a["uid"] = a["uid"].fillna(a["uid_k"])
    keep = a[a["class"].isin(["M", "S", "H", "W", "O"])]
    g = cands[["uid", "geometry"]].merge(keep[["uid", "class"]], on="uid", how="inner")
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=cands.crs)
    if drawn is not None and len(drawn):
        g = gpd.GeoDataFrame(pd.concat([g, drawn[["class", "geometry"]].assign(uid="drawn")], ignore_index=True),
                             crs=cands.crs)
    return g.reset_index(drop=True)


def burn(template: Path, polys, out_path: Path, task: str) -> dict:
    import rasterio
    from rasterio.features import rasterize
    with rasterio.open(template) as r:
        shape, tf, crs = (r.height, r.width), r.transform, r.crs
    ek.assert_crs(crs, polys.crs)
    lab = np.zeros(shape, np.uint8)
    order = ["W", "O", "H", "S", "M"]          # later classes win on overlap
    for cls in order:
        sel = polys[polys["class"] == cls]
        if not len(sel):
            continue
        m = rasterize([(g, 1) for g in sel.geometry], out_shape=shape, transform=tf, fill=0, dtype="uint8") == 1
        if task == "mine":
            lab[m] = MINE_CODE.get(cls, 0)
        elif task == "wellneg":
            lab[m] = 3 if cls in MINE_CODE else (255 if cls == "W" else 0)
        else:                                   # wellnegbg, the random arm. Mine pixels stay background
            lab[m] = 255 if cls == "W" else 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prof = dict(driver="GTiff", width=shape[1], height=shape[0], count=1, dtype="uint8", crs=crs, transform=tf,
                compress="deflate", tiled=True, blockxsize=512, blockysize=512, nodata=None)
    with rasterio.open(out_path, "w", **prof) as w:
        w.write(lab, 1)
    vals, cnt = np.unique(lab, return_counts=True)
    return {int(v): int(c) for v, c in zip(vals, cnt)}


def make_split(cfg: dict, manifest: pd.DataFrame, blocks, audit: list[int], k: int, seed: int) -> pd.DataFrame:
    import sys
    sys.path.insert(0, str(C.TRAIN_DIR))
    sys.path.insert(0, str(C.TRAIN_DIR.parent))
    from _pit_unet_cv5 import assign_folds
    elig = blocks[~blocks.block_id.isin(audit)]
    n = manifest[manifest.cls.isin(list(MINE_CODE))].groupby("block_id").size()
    bn = pd.DataFrame({"block_id": elig.block_id.astype(int), "n": elig.block_id.map(n).fillna(0).astype(int)})
    fold_of = assign_folds(bn[["block_id", "n"]], k, seed)
    rows = []
    for f in range(k):
        held = sorted(b for b, ff in fold_of.items() if ff == f)
        rest = sorted(b for b, ff in fold_of.items() if ff != f)
        rng = np.random.default_rng(ek.child_seed(seed, f, 0))
        sh = list(rng.permutation(rest))
        nv = max(1, int(round(0.2 * len(sh))))
        rows += [{"fold": f, "role": "held_out", "block_id": b} for b in held]
        rows += [{"fold": f, "role": "inner_val", "block_id": int(b)} for b in sorted(sh[:nv])]
        rows += [{"fold": f, "role": "train", "block_id": int(b)} for b in sorted(sh[nv:])]
    return pd.DataFrame(rows)


def _samplers(TR, feats, labels, blocks, fb, policies, audit_polys, t, seed, n_ch):
    """Training and validation IsolatedSamplers for one area. Training windows avoid held-out, inner-val and audit."""
    import rasterio
    _, Iso = TR.import_trainers()
    polys = lambda ids: list(blocks.loc[blocks.block_id.isin(ids)].geometry)  # noqa: E731
    bounds = lambda ids: np.array([g.bounds for g in polys(ids)])  # noqa: E731
    with rasterio.open(feats) as r:
        tf = r.transform
    z, o = np.zeros(n_ch, np.float32), np.ones(n_ch, np.float32)
    tr = Iso(feat_path=feats, lbl_path=labels, policies=policies["train"], block_bounds=bounds(fb["train"]),
             transform=tf, mu=z, sd=o, patch=t["patch"], augment=True, seed=seed,
             forbid=polys(fb["held_out"]) + polys(fb["inner_val"]) + audit_polys)
    va = Iso(feat_path=feats, lbl_path=labels, policies=policies["val"], block_bounds=bounds(fb["inner_val"]),
             transform=tf, mu=z, sd=o, patch=t["patch"], augment=False, seed=seed + 1,
             forbid=polys(fb["held_out"]) + audit_polys)
    return tr, va


def _fit(TR, model, tr_ds, va_ds, n_classes, alpha, names, out, t, extra, score):
    import torch
    from torch.utils.data import DataLoader
    _dl, _ = TR.import_trainers()
    out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(extra["seed"])
    _dl.train_loop(model=model, train_loader=DataLoader(tr_ds, batch_size=t["batch"], shuffle=True),
                   val_loader=DataLoader(va_ds, batch_size=t["batch"], shuffle=False),
                   loss_fn=_dl.FocalCE(alpha=alpha, gamma=t["focal_gamma"]), epochs=t["epochs"], lr=t["lr"],
                   n_classes=n_classes, out_dir=out, checkpoint_extra=extra, score=score, extra_iou_names=names)
    return {"trained": str(out / "best.pt")}


def train_mine(cfg, p, feats, labels, blocks, fb, man, audit_polys):
    """S4. Classes bg M S H. One centred policy per mine class plus W and O negatives."""
    import rasterio
    import _confuser_unet_cv5_9t as TR
    _dl, _ = TR.import_trainers()
    t = cfg["train"]
    with rasterio.open(feats) as r:
        n_ch = r.count

    def xy(ids, cls):
        return man.loc[man.block_id.isin(ids) & man.cls.isin(cls), ["centroid_x", "centroid_y"]].to_numpy()
    pol = {"train": [(c, xy(fb["train"], [c]), t["jitter_m"]) for c in ("M", "S", "H")]
                    + [("neg", xy(fb["train"], ["W", "O"]), t["jitter_m"])],
           "val": [(c, xy(fb["inner_val"], [c]), t["jitter_m"]) for c in ("M", "S", "H")]}
    tr, va = _samplers(TR, feats, labels, blocks, fb, pol, audit_polys, t, p["child_seed"], n_ch)
    mu, sd, n = TR.fold_stats(tr, t["stats_windows"], n_ch)
    tr.mu, tr.sd, va.mu, va.sd = mu, sd, mu, sd
    out = Path(p["out"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "fold_stats.json").write_text(json.dumps({"mu": mu.tolist(), "sd": sd.tolist(), "n_windows": n}))
    model = _dl.UNet(in_ch=n_ch, n_classes=4, base=32)
    return _fit(TR, model, tr, va, 4, t["mine_focal_alpha"], tuple(t["mine_classes"]), out, t,
                {"mu": mu, "sd": sd, "fold": p["fold"], "seed": p["child_seed"], "held_out_blocks": fb["held_out"]},
                score=lambda iou: float(np.nanmean(iou[1:])))


def pooled_stats(stats):
    """Combine per-area (mu, sd, n_windows) into one mean and sd (law of total variance)."""
    w = np.array([s[2] for s in stats], float)
    mu = np.average([s[0] for s in stats], axis=0, weights=w)
    var = np.average([s[1].astype(float) ** 2 + (s[0] - mu) ** 2 for s in stats], axis=0, weights=w)
    return mu.astype(np.float32), np.sqrt(var).astype(np.float32)


def train_wellneg(cfg, p, feats_coal, blocks_coal, fb_coal, man, audit_polys_coal):
    """S6. 9t pit windows (6.3 config, P1 split, P2 audit) plus coal windows centred on mine polygons.
    Arms baseline (9t only), confuser (coal mine pixels are class 3), random (same count of random coal centres,
    mine pixels left as background). Normalisation pooled over both areas' training windows."""
    import rasterio
    from torch.utils.data import ConcatDataset
    import _confuser_unet_cv5_9t as TR
    _dl, _ = TR.import_trainers()
    c3 = C.load_config()
    t = cfg["train"]
    split9 = TR.read_split(c3)
    audit9 = C.read_block_ids(C.input_path(c3, "audit_blocks"))
    b9 = C.read_vector(C.input_path(c3, "blocks"), c3["crs"], layer="blocks")
    m9 = pd.read_csv(C.input_path(c3, "manifest"))
    fb9 = TR.fold_blocks(split9, p["fold"], audit9)
    f9 = C.input_path(c3, "features")
    with rasterio.open(f9) as r9, rasterio.open(feats_coal) as rc:
        if r9.count != rc.count:
            raise AssertionError("9t and coal feature stacks have different channel counts")
        n_ch = r9.count

    def pit(ids):
        return m9.loc[m9.block_id.isin(ids), ["centroid_x", "centroid_y"]].to_numpy()
    a9 = list(b9.loc[b9.block_id.isin(audit9)].geometry)
    tr9, va9 = _samplers(TR, f9, C.input_path(c3, "labels_pit"), b9, fb9,
                         {"train": [("pit", pit(fb9["train"]), t["jitter_m"])],
                          "val": [("pit", pit(fb9["inner_val"]), t["jitter_m"])]},
                         a9, t, p["child_seed"], n_ch)
    parts = [tr9]
    stats = [TR.fold_stats(tr9, t["stats_windows"], n_ch)]
    if p["arm"] != "baseline":
        mine = man[man.block_id.isin(fb_coal["train"]) & man.cls.isin(list(MINE_CODE))]
        if p["arm"] == "confuser":
            cen, lbl = mine[["centroid_x", "centroid_y"]].to_numpy(), "wellneg"
        else:
            import geopandas as gpd
            fake = gpd.GeoDataFrame(geometry=gpd.points_from_xy(mine.centroid_x, mine.centroid_y).buffer(1),
                                    crs=cfg["crs"])
            tr_polys = list(blocks_coal.loc[blocks_coal.block_id.isin(fb_coal["train"])].geometry)
            cen, lbl = TR.negative_centres("random", fake, tr_polys, p["child_seed"]), "wellnegbg"
        trc, _ = _samplers(TR, feats_coal, ek.sub("6.2", "data/processed") / f"labels_coal_{lbl}_{cfg['area']}_05.tif",
                           blocks_coal, fb_coal, {"train": [("neg", cen, t["jitter_m"])], "val": []},
                           audit_polys_coal, t, p["child_seed"] + 7, n_ch)
        parts.append(trc)
        stats.append(TR.fold_stats(trc, t["stats_windows"], n_ch))
    mu, sd = pooled_stats(stats)
    for d in parts + [va9]:
        d.mu, d.sd = mu, sd
    nc = 4 if (p["arm"] == "confuser" and t["mode"] == "class") else 3
    alpha = list(t["focal_alpha_pit"]) + ([t["focal_alpha_confuser"]] if nc == 4 else [])
    model = _dl.UNet(in_ch=n_ch, n_classes=nc, base=32)
    return _fit(TR, model, ConcatDataset(parts), va9, nc, alpha,
                ("bg", "floor", "wall") + (("mine",) if nc == 4 else ()), Path(p["out"]), t,
                {"mu": mu, "sd": sd, "fold": p["fold"], "arm": p["arm"], "seed": p["child_seed"]},
                score=lambda iou: float(np.nanmean(iou[1:3])))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--make-split", action="store_true")
    ap.add_argument("--burn", action="store_true")
    ap.add_argument("--task", choices=["mine", "wellneg"], default="mine")
    ap.add_argument("--arms", default="baseline,confuser,random", help="wellneg only")
    ap.add_argument("--seeds", default=None)
    ap.add_argument("--only-folds", default="")
    ap.add_argument("--train", action="store_true")
    a = ap.parse_args()
    cfg = K.load_config(a.config)
    t = cfg["train"]
    ar = cfg["area"]
    out = C.results_dir(cfg)
    blocks = C.read_vector(C.input_path(cfg, "blocks"), cfg["crs"], layer="blocks")
    man_p = ek.sub("6.2", "data/processed") / f"coal_dataset_manifest_{ar}.csv"
    split_p = C.resolve(cfg["inputs"]["split_file"])
    audit = C.read_block_ids(C.input_path(cfg, "audit_blocks"))
    import _confuser_sample_9t as S1
    if a.burn or a.make_split:
        lp, kp = out / f"confuser_labels_adjudicated_{ar}.csv", out / f"confuser_sheet_key_{ar}.csv"
        if not lp.exists():
            raise K.MissingInput(f"{lp} missing. Finish S2 labelling and the 6.3 agreement step first.")
        drawn_p = C.input_path(cfg, "confuser_polys", required=False)
        polys = labelled_polygons(cfg, pd.read_csv(lp), pd.read_csv(kp), S1.load_candidates(cfg),
                                  C.read_vector(drawn_p, cfg["crs"]) if drawn_p else None)
        cxy = np.column_stack([polys.geometry.centroid.x, polys.geometry.centroid.y])
        man = pd.DataFrame({"uid": polys.uid, "cls": polys["class"], "centroid_x": cxy[:, 0], "centroid_y": cxy[:, 1],
                            "block_id": C.block_of_points(cxy, blocks)})
        man.to_csv(man_p, index=False)
        if a.burn:
            feats = C.input_path(cfg, "features")
            for task in ("mine", "wellneg", "wellnegbg"):
                p = ek.sub("6.2", "data/processed") / f"labels_coal_{task}_{ar}_05.tif"
                print(task, burn(feats, polys, p, task), f"wrote {p}")
        if a.make_split:
            if split_p.exists():
                raise FileExistsError(f"{split_p} exists. Splits are immutable once saved.")
            s = make_split(cfg, man, blocks, audit, t["folds"], t["master_seed"])
            split_p.parent.mkdir(parents=True, exist_ok=True)
            s.to_csv(split_p, index=False)
            print(f"wrote {split_p}")
        return 0

    import _confuser_unet_cv5_9t as TR
    seeds = [int(s) for s in a.seeds.split(",")] if a.seeds else t["seeds"]
    split = TR.read_split(cfg)
    folds = [int(f) for f in a.only_folds.split(",") if f.strip()] or list(range(t["folds"]))
    if not man_p.exists():
        raise K.MissingInput(f"{man_p} missing. Run --burn first.")
    man = pd.read_csv(man_p)
    plan = []
    for k in folds:
        fb = TR.fold_blocks(split, k, audit)
        for s in seeds:
            if a.task == "mine":
                tr = man[man.block_id.isin(fb["train"])]
                plan.append({"task": "mine", "fold": k, "seed_index": s,
                             "child_seed": ek.child_seed(t["master_seed"], k, s),
                             "n_train_by_class": tr.cls.value_counts().to_dict(),
                             "n_train_blocks": len(fb["train"]), "n_val_blocks": len(fb["inner_val"]),
                             "classes": t["mine_classes"], "negatives": ["W", "O"],
                             "out": str(ek.sub("6.2", "models") / "unet_coal_cv5" / "mine" / f"seed{s}" / f"fold{k}")})
            else:
                for arm in a.arms.split(","):
                    plan.append({"task": "wellneg", "arm": arm, "fold": k, "seed_index": s,
                                 "child_seed": ek.child_seed(t["master_seed"], k, 100 * TR.ARM_INDEX[arm] + s),
                                 "coal_negative_centres": int(man[man.block_id.isin(fb["train"]) & man.cls.isin(list(MINE_CODE))].shape[0]) if arm != "baseline" else 0,
                                 "9t_config": "config_6_3.json (P1 split, P2 audit)",
                                 "out": str(ek.sub("6.2", "models") / "unet_coal_cv5" / "wellneg" / arm / f"seed{s}" / f"fold{k}")})
    if a.train:
        feats = C.input_path(cfg, "features")
        audit_polys = list(blocks.loc[blocks.block_id.isin(audit)].geometry)
        for p in plan:
            fb = TR.fold_blocks(split, p["fold"], audit)
            if p["task"] == "mine":
                p.update(train_mine(cfg, p, feats, ek.sub("6.2", "data/processed") / f"labels_coal_mine_{ar}_05.tif",
                                    blocks, fb, man, audit_polys))
            else:
                p.update(train_wellneg(cfg, p, feats, blocks, fb, man, audit_polys))
    pp = ek.sub("6.2", "results/tables") / f"coal_train_plan_{ar}.json"
    pp.write_text(json.dumps({"task": a.task, "train": a.train, "plan": plan}, indent=2, default=str), encoding="utf-8")
    print(pd.DataFrame(plan).to_string(index=False))
    print(f"wrote {pp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
