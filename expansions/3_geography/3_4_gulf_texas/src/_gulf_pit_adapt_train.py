"""S9b (3.4). A1 adaptation arm. Fine-tune the isolated pit checkpoint on adaptation windows.

Purpose
    Own preregistration. Fine-tune from the isolated 9t pit checkpoint on the relief-normalised
    stacks of the adaptation windows (AR Ouachita, LA Ouachita or Morehouse). Whole-window exclusion
    rejects any patch that touches test or audit ground or the buffer. Normalisation statistics are
    fitted on adaptation-train windows only. Three seeds. The stopping set (adapt_stop blocks) is
    separate from the audit. The arm policy is the mean probability over seeds (scored by core 'score'
    with --arm A1 on the same test blocks as A0, then paired with core.paired_arm_difference).
    GPU training. Default is --plan, which writes the window plan and stats only (CPU, cheap).
Inputs
    data/<adapt area>/derived/05/features_reliefnorm_<area>_05.tif   (S9a)
    data/<adapt area>/derived/05/labels_pit_<area>_05.tif            (rasterised adaptation labels, assumed)
    data/<adapt area>/results/transfer/xfer_blocks_roles_<area>.gpkg (roles adapt_train, adapt_stop)
    config_3_4.json model.pit.transfer_checkpoint                     (user decision, unset. Refuses until set)
Outputs
    expansions/3_geography/3_4_gulf_texas/models/pit_adapt_gulf/seed<k>/best.pt, train_log.csv
    expansions/3_geography/3_4_gulf_texas/models/pit_adapt_gulf/adapt_plan_gulf.json
Run
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_pit_adapt_train.py --areas ar_ouachita --plan
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_pit_adapt_train.py --areas ar_ouachita --execute
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.4"
PATCH_PX, CELL = 256, 0.5
FORBIDDEN_ROLES = ("test", "audit", "buffer", "adapt_stop")
A1_CHANNELS = ["lrm_25", "lrm_5", "slope", "tpi_05", "openness_pos", "openness_neg", "roughness_11", "elev_rn"]
# The 8-band relief-normalised stack cannot load the 7-band first conv. It is re-initialised by declaration and
# recorded in best.pt 'init_load' (review G-11). Every other layer must load or training refuses.
A1_REINIT = ("d1.0.",)


def plan_area(area: str, n_train: int, n_val: int, seed: int, buffer_m: float):
    import geopandas as gpd
    b = gpd.read_file(gt.require_input(gt.area_transfer_dir(area) / f"xfer_blocks_roles_{area}.gpkg", "block roles"))
    tr = b[b["role"] == "adapt_train"]
    va = b[b["role"] == "adapt_stop"]
    forb_tr = b[b["role"].isin(FORBIDDEN_ROLES)].geometry.buffer(buffer_m).union_all() if len(b) else None
    forb_va = b[~b["role"].isin(["adapt_stop"])].geometry.union_all()
    w_tr = gt.sample_windows(tr, forb_tr, PATCH_PX * CELL, n_train, seed)
    w_va = gt.sample_windows(va, forb_va, PATCH_PX * CELL, n_val, seed + 7)
    return w_tr, w_va


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--areas", required=True, help="comma list of adaptation areas")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--n-train", type=int, default=2000)
    ap.add_argument("--n-val", type=int, default=300)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--execute", action="store_true", help="GPU training. Measure one epoch first")
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    master = int(pr["master_seed"])
    out_root = ek.sub(EXP, "models/pit_adapt_gulf")
    try:
        ckpt = gt.transfer_checkpoint(cfg, "pit", EXP)
        gt.check_checkpoint(ckpt, cfg["model"]["pit"].get("sha256"))
        sources_tr, sources_va, plan = [], [], {}
        for area in a.areas.split(","):
            d05 = ek.area_dir(area) / "derived" / "05"
            stack = gt.require_input(d05 / f"features_reliefnorm_{area}_05.tif", "relief-normalised stack (S9a)")
            lab = gt.require_input(d05 / f"labels_pit_{area}_05.tif", "adaptation pit labels",
                                   "uint8 0 bg, 1 floor, 2 wall, 255 ignore, same grid as the stack")
            w_tr, w_va = plan_area(area, a.n_train, a.n_val, ek.child_seed(master, 0, 1), float(pr["buffer_m"]))
            sources_tr.append((stack, lab, w_tr))
            sources_va.append((stack, lab, w_va))
            plan[area] = {"n_train": len(w_tr), "n_val": len(w_va)}
    except (gt.MissingInputError, gt.DecisionMissingError, RuntimeError, AssertionError) as e:
        print(str(e), file=sys.stderr)
        return 2
    mu, sd = gt.fit_norm_stats_multi(sources_tr)
    plan.update({"mu": mu.tolist(), "sd": sd.tolist(), "fitted_on": "adapt_train windows only",
                 "checkpoint": str(ckpt)})
    (out_root / "adapt_plan_gulf.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"wrote {out_root / 'adapt_plan_gulf.json'}")
    if not a.execute:
        print("plan only. Add --execute to train (GPU).")
        return 0
    for k in range(a.seeds):
        seed = ek.child_seed(master, 0, 10 + k)
        res = gt.train_unet(sources_tr, sources_va, mu, sd, out_root / f"seed{k}", n_classes=3, patch_px=PATCH_PX,
                            epochs=a.epochs, lr=a.lr, alpha=[0.25, 0.5, 0.25], seed=seed, init_ckpt=ckpt,
                            channels=A1_CHANNELS, reinit=A1_REINIT, extra={"arm": "A1"})
        print(f"seed {k}: best {res['best_score']:.3f}")
    ek.write_provenance(out_root, outputs=[out_root / f"seed{k}" / "best.pt" for k in range(a.seeds)],
                        params=vars(a), seeds={"master": master})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
