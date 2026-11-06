"""P1 S3 and S6. Isolated 5-fold pit U-Net on 9t. Splits from file, whole-window rejection, fold-local normalisation.

Purpose
    The pit counterpart of `_pad_unet_iso_cv5.py`, with every P1 fix. Architecture, loss, channels, patch,
    jitter and epochs are the historical pit trainer's (`_pit_unet_cv5.py`, imported read-only). Changes.
    1. Splits are read from the P1 S2 split file. They are never rebuilt. The file hash is checked and saved
       in every checkpoint.
    2. Training windows are drawn with `IsolatedSampler`. A draw is rejected if the whole window touches any
       held-out or inner-validation block (dilated by `--buffer-m`). Background draws obey the same rule.
       Audit blocks from P2 (`--audit-file`) join the forbidden set and the P2 guard refuses any audit
       block in a training or validation list.
    3. Fold-local normalisation. Mean and standard deviation per channel from `--norm-windows` training
       windows (default 20,000) read on a decimated grid. Saved as `norm_stats_fold{k}.npz` with the window
       origins, so P1 S5 can trace every fitted number to training ground.
    4. Validation windows lie wholly inside inner-validation blocks.
    5. Best epoch and both cutoffs (F1, F2) are chosen on inner validation only. The held-out fold is scored once.
    6. The out-of-fold mosaic is float32, not uint8, so scores and ties are not quantised.
    `--dry-run` builds every split, sampler and normalisation object on a small sample and trains nothing.
    `--measure-epoch` trains one epoch of fold 0 and writes the measured time and a GPU-hour estimate (S6).
    Full training is a user decision (P1 S6). Do not run it without that decision.

Inputs
    split file data/9t/results/splits/cv_splits_future_9t_v1.json (--splits, required)
    data/9t/derived/05/features_pit_9t_05.tif, labels_pit_9t_05.tif, pit_blocks_9t.gpkg, pit_dataset_manifest.csv
    qgis/annotations/annotations_proj.gpkg layers pit_inside, pit_full (through the pit trainer constants)
    optional P2 audit file and its registry (--audit-file)

Outputs (default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/models/pit/unet_iso_cv5/)
    fold{k}/best.pt, fold{k}/train_log.csv, fold{k}/norm_stats_fold{k}.npz, fold{k}/pit_prob_floor_isofold{k}_9t_05.tif
    pit_prob_floor_outoffold_iso_9t_05.tif, pit_iso_cv5_per_fold_9t.csv, pit_iso_epoch_time_9t.json (S6)
    Run record under expansions/0_prerequisites/p1_splits_manifests/results/<run_id>/

Run
    python expansions/0_prerequisites/p1_splits_manifests/src/_pit_unet_iso_train_9t.py --splits data/9t/results/splits/cv_splits_future_9t_v1.json --dry-run
    python expansions/0_prerequisites/p1_splits_manifests/src/_pit_unet_iso_train_9t.py --splits data/9t/results/splits/cv_splits_future_9t_v1.json --measure-epoch
    python expansions/0_prerequisites/p1_splits_manifests/src/_pit_unet_iso_train_9t.py --splits data/9t/results/splits/cv_splits_future_9t_v1.json --epochs 40
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _split_core_lib_9t as sc  # noqa: E402
from _split_future_write_9t import split_file_for  # noqa: E402
from _split_sampler_leakage_9t import draw_windows, forbidden_polys, isolated_module  # noqa: E402
ek = sc.ek

P2_SRC = HERE.parents[2] / "p2_audit_set" / "src"


def fold_norm_stats(feat_path: Path, rc: np.ndarray, patch: int, read_px: int, n_ch: int):
    """Per-channel mean and sd over the given windows, NaN ignored. Each window is read at read_px x read_px."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import Window
    s1 = np.zeros(n_ch); s2 = np.zeros(n_ch); n = np.zeros(n_ch)
    with rasterio.open(feat_path) as r:
        for r0, c0 in rc:
            a = r.read(window=Window(int(c0), int(r0), patch, patch), out_shape=(n_ch, read_px, read_px),
                       resampling=Resampling.nearest).astype(np.float64)
            ok = np.isfinite(a)
            if r.nodata is not None and np.isfinite(r.nodata):
                ok &= a != r.nodata
            a = np.where(ok, a, 0.0)
            s1 += a.sum((1, 2)); s2 += (a * a).sum((1, 2)); n += ok.sum((1, 2))
    mu = s1 / np.maximum(n, 1)
    sd = np.sqrt(np.maximum(s2 / np.maximum(n, 1) - mu * mu, 0))
    return mu.astype(np.float32), np.maximum(sd, 1e-6).astype(np.float32), n.astype(np.int64)


def guard_lists(audit_file: Path | None, roles: dict, buffer_m: float = 0.0) -> list[int]:
    """P2 guard. Raises if an audit block is in train or inner_val. Returns the audit ids to forbid."""
    if audit_file is None:
        return []
    sys.path.insert(0, str(P2_SRC))
    import _audit_guard_lib as ag
    audit = ag.load_audit(audit_file)
    ag.assert_no_audit(roles["train"] + roles["inner_val"], audit, label="isolated pit trainer lists")
    need = float(audit.attrs.get("header", {}).get("buffer_m", 0.0))
    if buffer_m < need:
        raise AssertionError(f"--buffer-m {buffer_m} is below the audit file's buffer {need} m")
    return sorted(audit["block_id"].astype(int).tolist())        # audit and buffer rows both forbidden


def build_fold(k, roles, man, blocks, feat, lbl, tf, mu_sd, patch, jitter, buffer_m, audit_ids, seed_base=100):
    from _dl import DEFAULT_CHANNELS  # noqa: F401
    Iso = isolated_module().IsolatedSampler
    tr, va = roles["train"], roles["inner_val"]
    pts = lambda ids: man.loc[man.block_id.isin(ids), ["centroid_x", "centroid_y"]].to_numpy()  # noqa: E731
    bb = lambda ids: np.array([g.bounds for g in blocks[blocks.block_id.astype(int).isin(ids)].geometry])  # noqa: E731
    mu, sd = mu_sd
    forbid_tr = forbidden_polys(blocks, roles["held_out"] + va + audit_ids, buffer_m)
    forbid_va = forbidden_polys(blocks, roles["held_out"] + tr + audit_ids, 0.0)
    tr_ds = Iso(feat_path=feat, lbl_path=lbl, policies=[("pit", pts(tr), jitter)], block_bounds=bb(tr),
                transform=tf, mu=mu, sd=sd, patch=patch, augment=True, seed=seed_base + k, forbid=forbid_tr)
    va_ds = Iso(feat_path=feat, lbl_path=lbl, policies=[("pit", pts(va), jitter)], block_bounds=bb(va),
                transform=tf, mu=mu, sd=sd, patch=patch, augment=False, seed=2 * seed_base + k, forbid=forbid_va)
    return tr_ds, va_ds, forbid_tr


def select_and_score(pit, floor, tf, crs, floors, rims, blocks, roles):
    """F1 and F2 cutoffs chosen on inner val, then held-out scored once at each. Historical scoring code."""
    from rasterio.features import rasterize
    val_ids = roles["inner_val"]; held_ids = roles["held_out"]
    foot = lambda ids: blocks[blocks.block_id.astype(int).isin(ids)].geometry.union_all()  # noqa: E731
    fv, fh = foot(val_ids), foot(held_ids)
    keep = rasterize([(fv.buffer(pit.SCORE_BUF_M), 1), (fh.buffer(pit.SCORE_BUF_M), 1)], out_shape=floor.shape,
                     transform=tf, fill=0, dtype="uint8").astype(bool)
    fs = np.where(keep, floor, 0.0).astype(np.float32)
    gv = floors[floors.block_id.isin(val_ids)]; gh = floors[floors.block_id.isin(held_ids)]
    rh = rims[rims.block_id.isin(held_ids)]
    val_by, held_by = {}, {}
    for t in pit.PROB_GRID:
        allp = pit.polygonize(fs, tf, crs, float(t))
        cen = allp.geometry.centroid if len(allp) else allp.geometry
        pv = allp[cen.within(fv)].reset_index(drop=True) if len(allp) else allp
        ph = allp[cen.within(fh)].reset_index(drop=True) if len(allp) else allp
        val_by[float(t)] = pit.match_scores(gv, pv)
        held_by[float(t)] = (pit.match_scores(gh, ph), pit.containment(rh, ph), len(ph))
    rows = []
    for obj in ("f1", "f2"):
        bt = max(val_by, key=lambda t: val_by[t][pit.SEL_TAU][obj])
        m, c, npred = held_by[bt]
        rows.append(dict(objective=obj, prob_threshold=bt, val_score=val_by[bt][pit.SEL_TAU][obj],
                         n_heldout=len(gh), n_pred_heldout=npred, recall_iou30=m[0.3]["recall"],
                         precision_iou30=m[0.3]["precision"], recall_iou50=m[0.5]["recall"],
                         containment=c[0], containment_hits=c[1], n_rims=len(rh)))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P1 S3 isolated pit U-Net CV on 9t")
    ap.add_argument("--splits", type=Path, required=True)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--only-folds", default="")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--norm-windows", type=int, default=20_000)
    ap.add_argument("--norm-read-px", type=int, default=32, help="each norm window read at this size")
    ap.add_argument("--buffer-m", type=float, default=0.0, help="dilate forbidden blocks (P1 S4 buffer)")
    ap.add_argument("--audit-file", type=Path, default=None, help="P2 audit_blocks_9t_v1.csv")
    ap.add_argument("--features", type=Path, default=None)
    ap.add_argument("--labels", type=Path, default=None)
    ap.add_argument("--manifest", type=Path, default=None)
    ap.add_argument("--blocks", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None, help="default data/9t/models/pit/unet_iso_cv5/")
    ap.add_argument("--dry-run", action="store_true", help="build splits, samplers and norm on a sample. No training")
    ap.add_argument("--measure-epoch", action="store_true", help="S6. Time one epoch of fold 0")
    a = ap.parse_args(argv)

    import geopandas as gpd
    import rasterio
    pit = sc.trainer("pit")
    feat = a.features or Path(pit.FEATURES); lbl = a.labels or Path(pit.LABELS)
    blocks_p = a.blocks or Path(pit.BLOCKS); man_p = a.manifest or Path(pit.MANIFEST)
    for q in (a.splits, feat, lbl, blocks_p, man_p):
        if not Path(q).exists():
            raise SystemExit(f"input missing: {q}")
    split_sha = ek.sha256(a.splits)
    splits = split_file_for("pit", a.splits)
    man = sc.load_manifest("pit", man_p)
    blocks = gpd.read_file(blocks_p, layer="blocks")
    ek.assert_crs(blocks)
    with rasterio.open(feat) as r:
        ek.assert_crs(r)
        tf, crs, n_ch = r.transform, r.crs, r.count
    from _dl import DEFAULT_CHANNELS
    if n_ch != len(DEFAULT_CHANNELS):
        raise AssertionError(f"{feat} has {n_ch} bands, model expects {len(DEFAULT_CHANNELS)}")
    out = a.out_dir or (ek.path_for("models") / "pit" / "unet_iso_cv5")
    out.mkdir(parents=True, exist_ok=True)
    want = {int(x) for x in a.only_folds.split(",") if x.strip()} or set(range(a.folds))
    if a.measure_epoch:
        want, a.epochs = {0}, 1
    n_norm = min(a.norm_windows, 256) if a.dry_run else a.norm_windows
    cfg = {k: str(v) for k, v in vars(a).items()} | {"split_sha256": split_sha}
    run = ek.new_run("p1", "pit_iso_train" + ("_dry" if a.dry_run else ""), cfg,
                     why="S3 isolated pit trainer" + (" dry run" if a.dry_run else ""))
    summary, fold_rows = {"split_sha256": split_sha, "folds": {}}, []

    for k in sorted(want):
        roles = splits[k]
        problems = sc.check_roles({k: roles})
        if problems:
            raise AssertionError("; ".join(problems))
        audit_ids = guard_lists(a.audit_file, roles, a.buffer_m)
        fd = out / f"fold{k}"
        fd.mkdir(parents=True, exist_ok=True)
        unit = (np.zeros(n_ch, np.float32), np.ones(n_ch, np.float32))
        tr0, _, forbid_tr = build_fold(k, roles, man, blocks, feat, lbl, tf, unit, pit.PATCH, pit.JITTER_M,
                                       a.buffer_m, audit_ids)
        rc = draw_windows(tr0, n_norm, tr0.H, tr0.W, n_ch, seed=ek.child_seed(20261105, k))
        boxes = sc.window_boxes(rc[:, 0], rc[:, 1], pit.PATCH, tf)
        leaks, _ = sc.count_window_leaks(boxes, forbid_tr)
        if leaks:
            raise AssertionError(f"fold {k}: {leaks} normalisation windows touch forbidden ground")
        mu, sd, npx = fold_norm_stats(feat, rc, pit.PATCH, a.norm_read_px, n_ch)
        npz = fd / f"norm_stats_fold{k}.npz"
        np.savez(npz, mu=mu, sd=sd, n_px=npx, r0=rc[:, 0], c0=rc[:, 1], patch=pit.PATCH, fold=k,
                 split_sha256=split_sha, channels=np.array(DEFAULT_CHANNELS))
        tr_ds, va_ds, _ = build_fold(k, roles, man, blocks, feat, lbl, tf, (mu, sd), pit.PATCH, pit.JITTER_M,
                                     a.buffer_m, audit_ids)
        summary["folds"][str(k)] = {"n_train_blocks": len(roles["train"]), "n_val_blocks": len(roles["inner_val"]),
                                    "n_held_blocks": len(roles["held_out"]), "norm_windows": int(len(rc)),
                                    "norm_mu": mu.round(5).tolist(), "draw_failures": draw_windows.last_failures}
        print(f"fold {k}: train {len(roles['train'])} / val {len(roles['inner_val'])} / held "
              f"{len(roles['held_out'])} blocks, norm on {len(rc)} windows, mu {np.round(mu, 3).tolist()}")
        if a.dry_run:
            xb, yb = tr_ds[0]
            xv, yv = va_ds[0]
            assert tuple(xb.shape) == (n_ch, pit.PATCH, pit.PATCH) and tuple(xv.shape) == tuple(xb.shape)
            continue

        import torch
        from torch.utils.data import DataLoader
        from _dl import UNet, FocalCE, train_loop, predict_full_tile
        model = UNet(in_ch=n_ch, n_classes=pit.N_CLASSES, base=32)
        t0 = time.time()
        train_loop(model=model,
                   train_loader=DataLoader(tr_ds, batch_size=a.batch, shuffle=True, num_workers=a.workers, pin_memory=True),
                   val_loader=DataLoader(va_ds, batch_size=a.batch, shuffle=False, num_workers=a.workers, pin_memory=True),
                   loss_fn=FocalCE(alpha=pit.FOCAL_ALPHA, gamma=pit.FOCAL_GAMMA), epochs=a.epochs, lr=a.lr,
                   n_classes=pit.N_CLASSES, out_dir=fd,
                   checkpoint_extra={"mu": mu, "sd": sd, "fold": k, "channels": list(DEFAULT_CHANNELS),
                                     "patch": pit.PATCH, "held_out_blocks": roles["held_out"],
                                     "inner_val_blocks": roles["inner_val"], "train_blocks": roles["train"],
                                     "split_sha256": split_sha, "norm_stats": str(npz), "buffer_m": a.buffer_m},
                   score=lambda iou: float(np.nanmean(iou[1:])), extra_iou_names=("bg", "floor", "wall"))
        if a.measure_epoch:
            sec = time.time() - t0
            est = {"epoch_seconds_fold0": sec, "epochs_planned": 40, "folds": a.folds,
                   "gpu_hours_estimate": sec * 40 * a.folds / 3600,
                   "note": "first epoch includes warm-up. Backlog says epoch time was under-reported 1.8 times."}
            (out / "pit_iso_epoch_time_9t.json").write_text(json.dumps(est, indent=2), encoding="utf-8")
            print(json.dumps(est, indent=2))
            break
        ck = torch.load(fd / "best.pt", map_location="cpu", weights_only=False)
        model.load_state_dict(ck["model"] if "model" in ck else ck["state_dict"])
        prob, _, prof = predict_full_tile(model, feat, mu, sd, patch=pit.PATCH, overlap=pit.OVERLAP,
                                          n_classes=pit.N_CLASSES, batch=a.batch)
        floor = prob[1].astype(np.float32)
        del prob
        ptif = fd / f"pit_prob_floor_isofold{k}_9t_05.tif"
        with rasterio.open(ptif, "w", driver="GTiff", height=floor.shape[0], width=floor.shape[1], count=1,
                           dtype="float32", crs=prof["crs"], transform=prof["transform"], nodata=-1.0,
                           compress="deflate", predictor=2, tiled=True, BIGTIFF="YES") as d:
            d.write(floor, 1)
        from _common import read_layer
        idc = man.dropna(subset=["block_id"])[["pit_inside_id", "block_id"]].astype({"block_id": int})
        fl = read_layer(pit.ANN_GPKG, "pit_inside").to_crs(crs)[["pit_inside_id", "geometry"]]
        fl = fl.dissolve(by="pit_inside_id").reset_index().merge(idc, on="pit_inside_id")
        rm = read_layer(pit.ANN_GPKG, "pit_full").to_crs(crs)[["pit_inside_id", "geometry"]]
        rm = rm.dissolve(by="pit_inside_id").reset_index().merge(idc, on="pit_inside_id")
        for row in select_and_score(pit, floor, tf, crs, fl, rm, blocks, roles):
            fold_rows.append({"fold": k, **row})
        pd.DataFrame(fold_rows).to_csv(out / "pit_iso_cv5_per_fold_9t.csv", index=False)

    if not a.dry_run and not a.measure_epoch and want == set(range(a.folds)):
        mosaic = None
        for k in range(a.folds):
            with rasterio.open(out / f"fold{k}" / f"pit_prob_floor_isofold{k}_9t_05.tif") as r:
                p = r.read(1); prof = r.profile
            if mosaic is None:
                mosaic = np.full(p.shape, -1.0, np.float32)
            from rasterio.features import rasterize
            hm = rasterize([(g, 1) for g in blocks[blocks.block_id.astype(int).isin(splits[k]["held_out"])].geometry],
                           out_shape=p.shape, transform=prof["transform"], fill=0, dtype="uint8").astype(bool)
            mosaic[hm] = p[hm]
        prof.update(nodata=-1.0)
        with rasterio.open(out / "pit_prob_floor_outoffold_iso_9t_05.tif", "w", **prof) as d:
            d.write(mosaic, 1)
    js = run / "pit_iso_summary.json"
    js.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    ek.write_provenance(run, inputs=[a.splits, man_p, blocks_p], outputs=[js] + sorted(out.glob("fold*/norm_stats_fold*.npz")),
                        params=cfg, seeds={"norm_draw": "child_seed(20261105, fold)", "sampler": "100 + fold"})
    print(f"{'dry run done' if a.dry_run else 'done'}. outputs in {out}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
