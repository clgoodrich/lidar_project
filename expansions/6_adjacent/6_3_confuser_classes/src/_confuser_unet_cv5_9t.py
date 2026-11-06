"""6.3 S4. Pit U-Net CV5 with confuser negatives, a matched random-negative arm and a baseline (wrapper, no edits).

Purpose
    Train three arms on identical non-audit blocks and identical saved splits, at least 3 seeds each. This is the
    root-cause fix the user prefers. The confusing class goes into training as a negative, the way the road model
    learned drainage as its own class (notebooks/wellsight_v2/s3_train/_road_unet_1m_recall.py), instead of a
    post-hoc filter. Nothing under notebooks/ is edited. The wrapper imports
      UNet, FocalCE, train_loop, predict_full_tile, normalize   from notebooks/wellsight_v2/_dl.py
      IsolatedSampler (whole-window guard)                      from s3_train/_pad_unet_iso_cv5.py
    Arms
      baseline  pit centres plus the usual random background draw. Labels bg, floor, wall.
      confuser  plus one centred policy on adjudicated confuser polygons (C Q K R H B X).
                mode "class" burns confuser pixels as class 3 (a 4-class head, like road drainage).
                mode "bg" keeps them as background and changes only the sampling.
      random    plus the same number of centres drawn at random inside the same training blocks.
    Leakage rules (protocol section 3). Splits are read from the saved P1 file, never from a seed. A training
    window may not touch any held-out, inner-validation or audit block. A validation window may not touch any
    held-out or audit block. Normalisation statistics are fitted per fold on training windows only.
    Child seeds are master + 1000 * fold + (100 * arm_index + seed_index).
    Default is a dry run that writes the plan and runs every leakage assertion. --train is needed to train.
Inputs
    split_file    data/9t/results/splits/cv_splits_future_pit_9t_v1.csv (P1 CSV, ek.read_split_csv) or the P1 JSON (ek.read_split)
    audit_blocks  data/9t/results/splits/audit_blocks_9t_v1.csv (P2, read with ek.require_audit)           assumed (P2)
    data/9t/results/confusers/confuser_labels_adjudicated_9t.csv and confuser_sheet_key_9t.csv (S3)
    features_pit_9t_05.tif, labels_pit_9t_05.tif, pit_dataset_manifest.csv, pit_blocks_9t.gpkg (held)
Outputs
    expansions/6_adjacent/6_3_confuser_classes/models/unet_confuser_cv5/<arm>/seed<s>/fold<k>/
        best.pt, train_log.csv, fold_stats.json, pit_prob_floor_cvfold<k>_9t_05.tif (with --predict)
    expansions/6_adjacent/6_3_confuser_classes/data/processed/labels_pit_confuser_9t_05.tif (class mode)
    expansions/6_adjacent/6_3_confuser_classes/results/tables/confuser_train_plan_9t.json
    The models/ and data/ folders are git-ignored (expansions/*/*/models/**), so the >100 MB rasters stay out of git.
Run
    python expansions/6_adjacent/6_3_confuser_classes/src/_confuser_unet_cv5_9t.py                  (dry run, plan only)
    python expansions/6_adjacent/6_3_confuser_classes/src/_confuser_unet_cv5_9t.py --train --arms confuser --seeds 0 --only-folds 0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import _confuser_common_9t as C
from _confuser_common_9t import ek

ARM_INDEX = {"baseline": 0, "confuser": 1, "random": 2}
CONFUSER_CLASS = 3


def import_trainers():
    """Import from notebooks/wellsight_v2 without editing it."""
    nb = C.TRAIN_DIR.parent
    for p in (nb, C.TRAIN_DIR):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import _dl
    from _pad_unet_iso_cv5 import IsolatedSampler
    return _dl, IsolatedSampler


def read_split(cfg: dict, override=None) -> pd.DataFrame:
    """Long split frame (fold, role, block_id) with canonical roles train / inner_val / held_out.

    A .json path is the P1 split document, read with ek.read_split (hash-checked). Anything else is the P1 long
    CSV, read with ek.read_split_csv, which maps the legacy words val and heldout. P1 role 'buffer' gets no row.
    """
    p = C.input_path(cfg, "split_file", override)
    if p.suffix.lower() == ".json":
        doc = ek.read_split("pit", p)
        s = pd.DataFrame([(int(f), r, int(b)) for f, roles in doc.items() for r, ids in roles.items() for b in ids],
                         columns=["fold", "role", "block_id"])
    else:
        s = ek.read_split_csv(p)
    for col in ("fold", "role", "block_id"):
        if col not in s:
            raise C.MissingInput(f"{p} lacks column {col}. Schema {cfg['inputs']['split_file']['schema']}")
    ek.assert_no_nan(s.block_id, "split block_id")
    s["block_id"] = s.block_id.astype(int)
    s["fold"] = s.fold.astype(int)
    return s


def fold_blocks(split: pd.DataFrame, fold: int, audit: list[int]) -> dict:
    f = split[split.fold == fold]
    d = {r: sorted(f.loc[f.role == r, "block_id"]) for r in ("train", "inner_val", "held_out")}
    ek.assert_disjoint(d["train"], d["held_out"], f"fold {fold} train vs held_out")
    ek.assert_disjoint(d["train"], d["inner_val"], f"fold {fold} train vs inner_val")
    ek.assert_disjoint(d["inner_val"], d["held_out"], f"fold {fold} inner_val vs held_out")
    ek.assert_disjoint(d["train"] + d["inner_val"], audit, f"fold {fold} training lists vs audit")
    return d


def confuser_polygons(cfg: dict, adjudicated: pd.DataFrame, key: pd.DataFrame, cands, drawn=None):
    """Adjudicated confuser candidates (their polygons) plus any polygons reviewers drew."""
    import geopandas as gpd
    conf = set(cfg["classes"]["confuser"])
    a = adjudicated[adjudicated["class"].isin(conf)][["sheet_id", "class"]]
    a = a.merge(key[["sheet_id", "uid"]], on="sheet_id", how="left")
    g = cands[["uid", "geometry"]].merge(a, on="uid", how="inner")
    ek.assert_rows(g, len(a), "confuser labels to candidate polygons")
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=cands.crs)
    if drawn is not None and len(drawn):
        g = gpd.GeoDataFrame(pd.concat([g, drawn[["sheet_id", "class", "geometry"]]], ignore_index=True), crs=cands.crs)
    return g.reset_index(drop=True)


def burn_confuser_labels(base_labels: Path, polys, out_path: Path) -> dict:
    """Class mode. Confuser pixels become class 3 only where the base label is background."""
    import rasterio
    from rasterio.features import rasterize
    with rasterio.open(base_labels) as r:
        base = r.read(1)
        prof = r.profile.copy()
        if r.crs is None:
            raise AssertionError(f"{base_labels} has no CRS")
        ek.assert_crs(r, polys.crs)
        m = rasterize([(g, 1) for g in polys.geometry], out_shape=base.shape, transform=r.transform,
                      fill=0, dtype="uint8") if len(polys) else np.zeros_like(base, dtype="uint8")
    out = base.copy()
    sel = (m == 1) & (base == 0)
    out[sel] = CONFUSER_CLASS
    prof.update(compress="deflate", tiled=True, blockxsize=512, blockysize=512)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **prof) as w:
        w.write(out, 1)
    return {"confuser_pixels": int(sel.sum()), "overlap_with_pit_pixels": int(((m == 1) & (base > 0)).sum())}


def negative_centres(arm: str, polys, train_polys, seed: int, truth=None, truth_excl_m: float = 0.0) -> np.ndarray:
    """confuser: polygon centroids inside training blocks. random: same count, uniform inside the same blocks.

    Review 6.3-01. A confuser label can sit on a candidate that matched a drawn pit. No negative centre may lie
    within truth_excl_m of any truth geometry, for either arm. Random draws that land near truth are redrawn.
    """
    from shapely.geometry import Point
    from shapely.ops import unary_union
    tr = unary_union(list(train_polys)) if len(train_polys) else None
    if arm == "baseline" or tr is None:
        return np.zeros((0, 2))
    cen = np.array([(g.centroid.x, g.centroid.y) for g in polys.geometry if tr.contains(g.centroid)],
                   float).reshape(-1, 2)
    cen = cen[C.drop_near_truth(cen, truth, truth_excl_m)]
    if arm == "confuser":
        return cen
    rng = np.random.default_rng(seed)
    out = []
    tp = list(train_polys)
    tries = 0
    while len(out) < len(cen):
        tries += 1
        if tries > 1000 * max(len(cen), 1):
            raise RuntimeError("cannot place random negatives away from truth inside the training blocks")
        b = tp[int(rng.integers(len(tp)))]
        x0, y0, x1, y1 = b.bounds
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if b.contains(Point(x, y)) and C.drop_near_truth(np.array([[x, y]]), truth, truth_excl_m)[0]:
            out.append((x, y))
    return np.array(out, float).reshape(-1, 2)


def truth_exclusion_m(cfg: dict) -> float:
    """Declared radius around truth that no negative centre may enter. null in the config means jitter_m."""
    v = cfg["train"].get("neg_truth_exclusion_m")
    return float(cfg["train"]["jitter_m"] if v is None else v)


def read_truth(cfg: dict):
    spec = cfg["inputs"]["truth"]
    return C.read_vector(C.input_path(cfg, "truth"), cfg["crs"], layer=spec.get("layer"))


def confuser_label_raster(base_lbl: Path, polys, conf_lbl: Path) -> Path:
    """Reuse the burned label raster only when its sidecar records the same base raster and polygons."""
    want = {"base_sha256": ek.sha256(base_lbl),
            "polys_sha256": ek.config_hash({"wkb": sorted(g.wkb_hex for g in polys.geometry)}),
            "confuser_class": CONFUSER_CLASS}
    meta = conf_lbl.with_suffix(".json")
    if not C.label_cache_ok(conf_lbl, meta, want):
        info = burn_confuser_labels(base_lbl, polys, conf_lbl)
        meta.write_text(json.dumps(want | info, indent=2), encoding="utf-8")
        print(f"burned {conf_lbl} {info}")
    return conf_lbl


def fold_stats(sampler, n_windows: int, n_ch: int) -> tuple[np.ndarray, np.ndarray, int]:
    """Per-channel mean and sd over isolated training windows only (QC 5b)."""
    from rasterio.windows import Window
    sampler._open()
    s1 = np.zeros(n_ch)
    s2 = np.zeros(n_ch)
    n = np.zeros(n_ch)
    got = 0
    for idx in range(n_windows * 3):
        if got >= n_windows:
            break
        cx, cy = sampler._pick_center(idx)
        row, col = sampler._world_to_rowcol(cx, cy)
        r0 = int(np.clip(row - sampler.patch // 2, 0, sampler.H - sampler.patch))
        c0 = int(np.clip(col - sampler.patch // 2, 0, sampler.W - sampler.patch))
        if not sampler._clear(r0, c0):
            continue
        a = sampler._feat.read(window=Window(c0, r0, sampler.patch, sampler.patch)).astype(np.float64)
        if sampler._feat.nodata is not None:
            a[a == sampler._feat.nodata] = np.nan
        a = a.reshape(n_ch, -1)
        ok = np.isfinite(a)
        s1 += np.where(ok, a, 0).sum(1)
        s2 += np.where(ok, a * a, 0).sum(1)
        n += ok.sum(1)
        got += 1
    if got == 0:
        raise RuntimeError("no isolated training window for fold statistics")
    mu = s1 / np.maximum(n, 1)
    sd = np.sqrt(np.maximum(s2 / np.maximum(n, 1) - mu * mu, 1e-12))
    return mu.astype(np.float32), np.maximum(sd, 1e-6).astype(np.float32), got


def plan_fold(cfg: dict, arm: str, seed_i: int, fold: int, fb: dict, pits_xy: dict, neg_xy: np.ndarray, audit) -> dict:
    t = cfg["train"]
    return {"arm": arm, "seed_index": seed_i, "fold": fold,
            "child_seed": ek.child_seed(t["master_seed"], fold, 100 * ARM_INDEX[arm] + seed_i),
            "n_train_blocks": len(fb["train"]), "n_val_blocks": len(fb["inner_val"]),
            "n_held_out_blocks": len(fb["held_out"]), "n_audit_blocks": len(audit),
            "n_train_pits": int(len(pits_xy["train"])), "n_val_pits": int(len(pits_xy["val"])),
            "n_negative_centres": int(len(neg_xy)), "mode": t["mode"],
            "n_classes": 4 if (arm == "confuser" and t["mode"] == "class") else 3,
            "out": str(model_dir(cfg, arm, seed_i, fold))}


def model_dir(cfg: dict, arm: str, seed_i: int, fold: int) -> Path:
    return ek.sub(cfg["exp_id"], "models") / "unet_confuser_cv5" / arm / f"seed{seed_i}" / f"fold{fold}"


def train_one(cfg: dict, p: dict, feats: Path, labels: Path, blocks, fb: dict, pits_xy: dict, neg_xy: np.ndarray,
              audit_polys, predict: bool, workers: int = 0) -> dict:
    import torch
    from torch.utils.data import DataLoader
    _dl, IsolatedSampler = import_trainers()
    t = cfg["train"]
    polys = lambda ids: list(blocks.loc[blocks.block_id.isin(ids)].geometry)  # noqa: E731
    bounds = lambda ids: np.array([g.bounds for g in polys(ids)])  # noqa: E731
    with __import__("rasterio").open(feats) as r:
        tf, n_ch = r.transform, r.count
    seed = p["child_seed"]
    torch.manual_seed(seed)
    pol_tr = [("pit", pits_xy["train"], t["jitter_m"])] + ([("neg", neg_xy, t["jitter_m"])] if p["arm"] != "baseline" else [])
    zero = np.zeros(n_ch, np.float32)
    one = np.ones(n_ch, np.float32)
    forbid_tr = polys(fb["held_out"]) + polys(fb["inner_val"]) + audit_polys
    forbid_va = polys(fb["held_out"]) + audit_polys
    tr = IsolatedSampler(feat_path=feats, lbl_path=labels, policies=pol_tr, block_bounds=bounds(fb["train"]),
                         transform=tf, mu=zero, sd=one, patch=t["patch"], augment=True, seed=seed, forbid=forbid_tr)
    mu, sd, n_win = fold_stats(tr, t["stats_windows"], n_ch)
    tr.mu, tr.sd = mu, sd
    va = IsolatedSampler(feat_path=feats, lbl_path=labels, policies=[("pit", pits_xy["val"], t["jitter_m"])],
                         block_bounds=bounds(fb["inner_val"]), transform=tf, mu=mu, sd=sd, patch=t["patch"],
                         augment=False, seed=seed + 1, forbid=forbid_va)
    out = Path(p["out"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "fold_stats.json").write_text(json.dumps({"mu": mu.tolist(), "sd": sd.tolist(), "n_windows": n_win,
                                                    "fitted_on": "isolated training windows of this fold"}, indent=2))
    nc = p["n_classes"]
    alpha = list(t["focal_alpha_pit"]) + ([t["focal_alpha_confuser"]] if nc == 4 else [])
    names = ("bg", "floor", "wall") + (("confuser",) if nc == 4 else ())
    model = _dl.UNet(in_ch=n_ch, n_classes=nc, base=32)
    _dl.train_loop(model=model,
                   train_loader=DataLoader(tr, batch_size=t["batch"], shuffle=True, num_workers=workers, pin_memory=True),
                   val_loader=DataLoader(va, batch_size=t["batch"], shuffle=False, num_workers=workers, pin_memory=True),
                   loss_fn=_dl.FocalCE(alpha=alpha, gamma=t["focal_gamma"]), epochs=t["epochs"], lr=t["lr"],
                   n_classes=nc, out_dir=out,
                   checkpoint_extra={"mu": mu, "sd": sd, "fold": p["fold"], "arm": p["arm"], "seed": seed,
                                     "held_out_blocks": fb["held_out"], "mode": t["mode"]},
                   score=lambda iou: float(np.nanmean(iou[1:3])), extra_iou_names=names)
    res = {"trained": str(out / "best.pt")}
    if predict:
        ck = torch.load(out / "best.pt", map_location="cpu", weights_only=False)
        model.load_state_dict(ck["state_dict"])
        prob, _, prof = _dl.predict_full_tile(model, feats, mu, sd, patch=t["patch"], overlap=t["overlap"], n_classes=nc)
        sys.path.insert(0, str(C.TRAIN_DIR.parent))
        from _common import write_tif
        tif = out / f"pit_prob_floor_cvfold{p['fold']}_{cfg['area']}_05.tif"
        write_tif(tif, prob[1].astype(np.float32), transform=prof["transform"], crs=prof["crs"])
        res["prob"] = str(tif)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--arms", default="baseline,confuser,random")
    ap.add_argument("--seeds", default=None, help="comma list of seed indices (default from config)")
    ap.add_argument("--only-folds", default="")
    ap.add_argument("--mode", choices=["class", "bg"], default=None)
    ap.add_argument("--train", action="store_true", help="actually train (GPU). Default is a dry run")
    ap.add_argument("--predict", action="store_true", help="write the full-tile floor probability after training")
    ap.add_argument("--split-file", default=None)
    ap.add_argument("--audit-blocks", default=None)
    ap.add_argument("--allow-no-audit", action="store_true",
                    help="dry run only. Plan with no P2 audit exclusion, labelled exploratory")
    ap.add_argument("--results", default=None, help="confuser results dir (default data/9t/results/confusers/)")
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    t = cfg["train"]
    if a.mode:
        t["mode"] = a.mode
    arms = a.arms.split(",")
    seeds = [int(s) for s in a.seeds.split(",")] if a.seeds else t["seeds"]
    if len(seeds) < 3 and not a.train:
        print("note: fewer than 3 seeds per arm. The protocol needs at least 3 for the scored run.")
    folds = [int(f) for f in a.only_folds.split(",") if f.strip()] or list(range(t["folds"]))

    split = read_split(cfg, a.split_file)
    if a.allow_no_audit and a.train:
        raise SystemExit("--allow-no-audit is for dry runs only. Training needs the frozen P2 audit set.")
    audit = C.audit_block_ids(cfg, a.audit_blocks, roles=("audit", "buffer"), allow_missing=a.allow_no_audit)
    audit_note = "audit and buffer blocks excluded"
    if audit is None:
        audit, audit_note = [], "no audit exclusion, exploratory"
    truth = read_truth(cfg)
    excl_m = truth_exclusion_m(cfg)
    blocks = C.read_vector(C.input_path(cfg, "blocks"), cfg["crs"], layer=cfg["inputs"]["blocks"]["layer"])
    man = pd.read_csv(C.input_path(cfg, "manifest"))
    res_dir = C.results_dir(cfg, a.results)
    adj_p = res_dir / f"confuser_labels_adjudicated_{cfg['area']}.csv"
    key_p = res_dir / f"confuser_sheet_key_{cfg['area']}.csv"
    need_conf = any(x in arms for x in ("confuser", "random"))
    if need_conf and not adj_p.exists():
        raise C.MissingInput(f"{adj_p} missing. Run S1 to S3 (sample, sheets, labels, agreement) first.")
    import _confuser_sample_9t as S1
    if need_conf:
        cands = S1.load_candidates(cfg)
        drawn_p = C.input_path(cfg, "confuser_polys", required=False)
        polys = confuser_polygons(cfg, pd.read_csv(adj_p), pd.read_csv(key_p), cands,
                                  C.read_vector(drawn_p, cfg["crs"]) if drawn_p else None)
    else:
        polys = None
    feats = C.input_path(cfg, "features")
    base_lbl = C.input_path(cfg, "labels_pit")
    conf_lbl = ek.sub(cfg["exp_id"], "data/processed") / f"labels_pit_confuser_{cfg['area']}_05.tif"
    audit_polys = list(blocks.loc[blocks.block_id.isin(audit)].geometry)
    plan = []
    for k in folds:
        fb = fold_blocks(split, k, audit)
        in_blocks = lambda ids: man.loc[man.block_id.isin(ids), ["centroid_x", "centroid_y"]].to_numpy()  # noqa: E731
        pits_xy = {"train": in_blocks(fb["train"]), "val": in_blocks(fb["inner_val"])}
        tr_polys = list(blocks.loc[blocks.block_id.isin(fb["train"])].geometry)
        for arm in arms:
            for s in seeds:
                p0 = ek.child_seed(t["master_seed"], k, 100 * ARM_INDEX[arm] + s)
                neg = (negative_centres(arm, polys, tr_polys, p0, truth, excl_m) if arm != "baseline"
                       else np.zeros((0, 2)))
                p = plan_fold(cfg, arm, s, k, fb, pits_xy, neg, audit)
                plan.append(p)
                if a.train:
                    lbl = base_lbl
                    if arm == "confuser" and t["mode"] == "class":
                        lbl = confuser_label_raster(base_lbl, polys, conf_lbl)
                    p.update(train_one(cfg, p, feats, lbl, blocks, fb, pits_xy, neg, audit_polys, a.predict))
    # random arm count must equal confuser arm count per fold and seed (same count, same procedure)
    pdf = pd.DataFrame(plan)
    if {"confuser", "random"} <= set(arms):
        c = pdf[pdf.arm == "confuser"].set_index(["fold", "seed_index"]).n_negative_centres
        r = pdf[pdf.arm == "random"].set_index(["fold", "seed_index"]).n_negative_centres
        assert (c == r).all(), "random-negative count differs from confuser count"
    out = ek.sub(cfg["exp_id"], "results/tables") / f"confuser_train_plan_{cfg['area']}.json"
    out.write_text(json.dumps({"train": a.train, "config": t, "audit_exclusion": audit_note,
                               "neg_truth_exclusion_m": excl_m, "plan": plan}, indent=2, default=str), encoding="utf-8")
    print(pdf.to_string(index=False))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
