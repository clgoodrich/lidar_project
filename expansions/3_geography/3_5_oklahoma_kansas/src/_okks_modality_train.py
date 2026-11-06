"""S8 (3.5). Train the modality arms L1, O1, F1 (from scratch) and L2 (fine-tuned reference) with a trial ledger.

Purpose
    Same U-Net family, isolated patch sampler (whole-window exclusion of val, test and audit ground),
    D4 augmentation, epoch cap and three seeds for every arm. Only the input channel count differs
    between L1 and F1. Matched tuning. The same random-search trial list (n_trials, seeded once, shared by
    every arm), the same GPU-hour cap and the same seeds. Every trial writes a ledger row (config,
    GPU-seconds, validation score, failure text) and failures are kept. Selection uses validation blocks
    only. The final arm is the three-seed mean probability (declared policy).
    --plan (default) writes the shared trial list and checks inputs. --execute trains (GPU).
Inputs
    data/<train area>/derived/05/features_<area>_05.tif | features_optical_<area>_05.tif | features_fusion_<area>_05.tif
    data/<train area>/results/modality/mod_truth_features_<area>.gpkg   (S7, rasterised here)
    data/<train area>/results/modality/mod_blocks_roles_<area>.gpkg     (S5)
Outputs
    expansions/3_geography/3_5_oklahoma_kansas/models/okks_trials_plan.json
    expansions/3_geography/3_5_oklahoma_kansas/models/<arm>/trial<k>/best.pt, seed<k>/best.pt
    expansions/3_geography/3_5_oklahoma_kansas/results/tables/okks_trial_ledger.csv
    data/<area>/derived/05/labels_pitpad_<area>_05.tif                  (--rasterize)
Run
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_modality_train.py --plan
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_modality_train.py --arm F1 --execute
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.5"
STACK = {"L1": "features_{a}_05.tif", "L2": "features_{a}_05.tif", "O1": "features_optical_{a}_05.tif",
         "F1": "features_fusion_{a}_05.tif"}
LIDAR_CHANNELS = ["lrm_25", "lrm_5", "slope", "tpi_05", "openness_pos", "openness_neg", "roughness_11"]
CLASSES = {"pit": 1, "pad": 1}   # one foreground class. Primary truth is all drawn pit and pad features
PATCH_PX = 256


def trial_list(n: int, seed: int) -> list[dict]:
    """One random-search list shared by every arm (matched tuning)."""
    rng = np.random.default_rng(seed)
    return [{"trial": k, "lr": float(10 ** rng.uniform(-4.3, -3.0)), "alpha_fg": float(rng.uniform(0.3, 0.7)),
             "batch": int(rng.choice([4, 8])), "epochs": int(rng.choice([15, 25, 40]))} for k in range(n)]


def rasterize_labels(area: str) -> Path:
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize
    d05 = ek.area_dir(area) / "derived" / "05"
    ref = gt.require_input(d05 / f"features_{area}_05.tif", "lidar stack for grid")
    t = gpd.read_file(gt.require_input(ek.area_dir(area) / "results" / "modality" / f"mod_truth_features_{area}.gpkg",
                                       "adjudicated truth (S7)"))
    with rasterio.open(ref) as r:
        ek.assert_crs(t, r.crs)
        lab = rasterize([(g, CLASSES[c]) for g, c in zip(t.geometry, t["class"]) if c in CLASSES],
                        out_shape=(r.height, r.width), transform=r.transform, fill=0, dtype="uint8")
        prof = r.profile.copy()
    prof.update(count=1, dtype="uint8", nodata=255)
    out = d05 / f"labels_pitpad_{area}_05.tif"
    with rasterio.open(out, "w", **prof) as d:
        d.write(lab, 1)
    return out


def area_sources(arm: str, area: str, role: str, n: int, seed: int, buffer_m: float):
    import geopandas as gpd
    d05 = ek.area_dir(area) / "derived" / "05"
    stack = gt.require_input(d05 / STACK[arm].format(a=area), f"{arm} stack for {area}")
    lab = gt.require_input(d05 / f"labels_pitpad_{area}_05.tif", "label raster (--rasterize)")
    b = gpd.read_file(gt.require_input(ek.area_dir(area) / "results" / "modality" / f"mod_blocks_roles_{area}.gpkg",
                                       "block roles (S5)"))
    b = b[b["eligible"]]
    mine = b[b["role"] == role]
    forb = b[b["role"] != role].geometry.buffer(buffer_m if role == "train" else 0).union_all()
    return stack, lab, gt.sample_windows(mine, forb, PATCH_PX * 0.5, n, seed)


def ledger_row(arm: str, cfgt: dict, seed: int, t0: float, res: dict | None, err: str = "") -> dict:
    return {"arm": arm, **cfgt, "seed": seed, "gpu_seconds": time.time() - t0,
            "val_score": None if res is None else res["best_score"], "failed": bool(err), "error": err}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arm", choices=list(STACK), default="L1")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--rasterize", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--n-train", type=int, default=2000)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    master = int(pr["master_seed"])
    trials = trial_list(int(pr["n_trials"]), ek.child_seed(master, 0, 99))
    mroot = ek.sub(EXP, "models")
    (mroot / "okks_trials_plan.json").write_text(json.dumps({"trials": trials, "seeds_per_arm": pr["seeds_per_arm"],
                                                             "gpu_hour_cap_per_arm": pr["gpu_hour_cap_per_arm"]},
                                                            indent=2), encoding="utf-8")
    print(f"wrote {mroot / 'okks_trials_plan.json'} ({len(trials)} trials shared by every arm)")
    train_areas = [k for k, v in cfg["areas"].items() if v["role"] == "train"]
    try:
        if a.rasterize:
            for ar in train_areas:
                print(f"wrote {rasterize_labels(ar)}")
        if not a.execute:
            return 0
        cap = gt.need_decision(cfg, "gpu_hour_cap_per_arm", "matched GPU-hour cap") * 3600
        tr = [area_sources(a.arm, ar, "train", a.n_train, ek.child_seed(master, i, 1), float(pr["buffer_m"]))
              for i, ar in enumerate(train_areas)]
        va = [area_sources(a.arm, ar, "val", 300, ek.child_seed(master, i, 2), 0.0) for i, ar in enumerate(train_areas)]
    except (gt.MissingInputError, gt.DecisionMissingError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        return 2
    mu, sd = gt.fit_norm_stats_multi(tr)
    try:
        init = gt.transfer_checkpoint(cfg, "pit", EXP) if a.arm == "L2" else None
    except (gt.MissingInputError, gt.DecisionMissingError) as e:
        print(str(e), file=sys.stderr)
        return 2
    # L2 fine-tunes the 3-class 9t pit model into a 2-class head. The head is re-initialised by declaration and the
    # lidar band order must equal the checkpoint's (G-11). Other arms train from scratch.
    l2 = {"reinit": ("out.",), "channels": LIDAR_CHANNELS} if a.arm == "L2" else {}
    led_p = ek.sub(EXP, "results/tables") / "okks_trial_ledger.csv"
    ledger = pd.read_csv(led_p).to_dict("records") if led_p.exists() else []
    spent = 0.0
    for t in trials:
        if spent > cap:
            ledger.append(ledger_row(a.arm, t, master, time.time(), None, "skipped: GPU cap reached"))
            continue
        t0 = time.time()
        try:
            res = gt.train_unet(tr, va, mu, sd, mroot / a.arm / f"trial{t['trial']}", n_classes=2, patch_px=PATCH_PX,
                                epochs=t["epochs"], lr=t["lr"], alpha=[1 - t["alpha_fg"], t["alpha_fg"]],
                                seed=master, batch=t["batch"], init_ckpt=init, extra={"arm": a.arm, "trial": t}, **l2)
            ledger.append(ledger_row(a.arm, t, master, t0, res))
        except Exception as e:  # noqa: BLE001  failures are kept in the ledger
            ledger.append(ledger_row(a.arm, t, master, t0, None, repr(e)))
        spent += time.time() - t0
    pd.DataFrame(ledger).to_csv(led_p, index=False)
    arm_rows = [r for r in ledger if r["arm"] == a.arm and not r["failed"]]
    best = max(arm_rows, key=lambda r: r["val_score"]) if arm_rows else None
    if best is None:
        print("every trial failed. See the ledger.", file=sys.stderr)
        return 1
    for k in range(int(pr["seeds_per_arm"])):
        s = ek.child_seed(master, 0, 10 + k)
        gt.train_unet(tr, va, mu, sd, mroot / a.arm / f"seed{k}", n_classes=2, patch_px=PATCH_PX, epochs=int(best["epochs"]),
                      lr=float(best["lr"]), alpha=[1 - best["alpha_fg"], best["alpha_fg"]], seed=s,
                      batch=int(best["batch"]), init_ckpt=init, extra={"arm": a.arm, "final_seed": k}, **l2)
    print(f"wrote {led_p}\nfinal seeds under {mroot / a.arm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
