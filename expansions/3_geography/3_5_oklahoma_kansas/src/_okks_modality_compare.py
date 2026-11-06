"""S9 and S10 (3.5). Score every arm once on the same test blocks, paired, plus strata tables.

Purpose
    Primary. G = recall(F1) - recall(L1) at K = 40 per km2 over complete eligible test blocks in the
    Oklahoma test windows (Rogers, Nowata). Paired block bootstrap, the same resampled blocks for every
    arm, resampling stratified by window (block keys carry the window). Superiority against delta_gain.
    Descriptive. L1 - O1, F1 - O1. L0 and L2 sit beside, never in the primary contrast.
    Kansas windows are a separate joint-contrast table. Strata. Recall by seen_in, activity, imagery
    gap stratum and slope tercile. Unmatched top-K candidates go to the 6.3 codebook list.
    Pits and pads are scored apart (2026-11-06). Each class uses its own truth and ek.policy_for(class).
    L0 (frozen 9t pit model) is scored on pits only. Gains are plotted without clipping.
Inputs
    data/<test area>/results/modality/<arm>_prob_<area>.tif         (three-seed mean per arm, from S8 models)
    data/<test area>/results/modality/mod_truth_features_<area>.gpkg, mod_blocks_roles_<area>.gpkg
Outputs
    expansions/3_geography/3_5_oklahoma_kansas/results/tables/okks_arm_compare.json
    expansions/3_geography/3_5_oklahoma_kansas/results/tables/okks_recall_strata.csv
    expansions/3_geography/3_5_oklahoma_kansas/results/figures/okks_recall_by_arm.png
    expansions/3_geography/3_5_oklahoma_kansas/data/processed/okks_unmatched_for_6_3.csv
Run
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_modality_compare.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.5"
ARMS = ["L0", "L1", "O1", "F1", "L2"]


def stratified_tables(per_area: dict) -> dict:
    """Merge per-window tables with window-prefixed block keys (resampling then spans windows)."""
    return {f"{area}|{b}": t for area, tabs in per_area.items() for b, t in tabs.items()}


def subset_truth(tabs: dict, keep_ids: set) -> dict:
    """Tables for a truth subset (a stratum). Hits on truth outside the subset count as unmatched.

    Each table must carry 'truth_ids', the denominator truth owned by that block (core score_raster).
    """
    out = {}
    for b, t in tabs.items():
        c = t["c"].copy()
        c["truth_id"] = [v if v in keep_ids else None for v in c["truth_id"]]
        ids = [v for v in t["truth_ids"] if v in keep_ids]
        out[b] = {**{k: v for k, v in t.items() if k not in ("c", "truth_ids", "n_truth")},
                  "c": c, "n_truth": len(ids), "truth_ids": ids, "km2": t["km2"]}
    return out


STACK = {"L0": "features_{a}_05.tif", "L1": "features_{a}_05.tif", "L2": "features_{a}_05.tif",
         "O1": "features_optical_{a}_05.tif", "F1": "features_fusion_{a}_05.tif"}


def infer_arm(arm: str, area: str, cfg: dict) -> Path:
    """Run each seed checkpoint once on the test stack and write the three-seed mean (declared policy)."""
    md = ek.area_dir(area) / "results" / "modality"
    stack = ek.area_dir(area) / "derived" / "05" / STACK[arm].format(a=area)
    if arm == "L0":                            # provisional transfer model, five-fold 9t ensemble (fold_mean)
        ckpts, shas, _ = gt.transfer_checkpoints(cfg, "pit", EXP)
        for c, h in zip(ckpts, shas):
            gt.check_checkpoint(c, h)
    else:
        ckpts = sorted((ek.exp_dir(EXP) / "models" / arm).glob("seed*/best.pt"))
    if not ckpts:
        raise gt.MissingInputError(f"no seed checkpoints for {arm}. Train with _okks_modality_train.py --execute")
    task = "pit" if arm == "L0" else "pad"     # trained arms are 2-class (bg, pit-or-pad)
    probs = [gt.frozen_infer(stack, c, task, md / f"_{arm}_{c.parent.name}", f"{arm}_{c.parent.name}_{area}")
             for c in ckpts]                   # L0 hashes checked above
    return gt.mean_rasters(probs, md / f"{arm}_prob_{area}.tif")


CLASS_TASKS = ("pit", "pad")      # each class scored on its own truth at its own policy (G-13, F02)


def arms_for(cls: str) -> list[str]:
    """L0 is the frozen 9t pit model. It has no pad output, so it is scored on pits only."""
    return [a for a in ARMS if not (a == "L0" and cls != "pit")]


def score_arm(arm: str, area: str, task: str):
    """Score one arm's probability raster on one class (task pit or pad) with ek.policy_for(task)."""
    import geopandas as gpd
    md = ek.area_dir(area) / "results" / "modality"
    prob = gt.require_input(md / f"{arm}_prob_{area}.tif", f"{arm} probability raster for {area}",
                            "three-seed mean of the S8 seed checkpoints, written by core frozen_infer")
    blocks = gpd.read_file(gt.require_input(md / f"mod_blocks_roles_{area}.gpkg", "roles (S5)"))
    blocks = blocks[blocks["role"] == "test"]
    truth = gt.class_truth(gpd.read_file(gt.require_input(md / f"mod_truth_features_{area}.gpkg", "truth (S7)")),
                           task)
    tabs, cands = gt.score_raster(prob, truth, blocks, task=task)
    return tabs, cands, truth


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--infer", action="store_true", help="GPU. Run seed checkpoints on test stacks first (once)")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    ok_test = [k for k, v in cfg["areas"].items() if v["role"] == "test"]
    ks_test = [k for k, v in cfg["areas"].items() if v["role"] == "test_ks"]
    try:
        dg = float(gt.need_decision(cfg, "delta_gain", "extra recall at K that pays for imagery"))
        if a.infer:
            for arm in ARMS:
                for area in ok_test + ks_test:
                    print(f"wrote {infer_arm(arm, area, cfg)}")
        res, strata_rows, unmatched = {}, [], []
        for group, areas in (("oklahoma", ok_test), ("kansas_joint_contrast", ks_test)):
            res[group] = {}
            for cls in CLASS_TASKS:
                per_arm, policy = {}, None
                for arm in arms_for(cls):
                    per = {}
                    for area in areas:
                        tabs, cands, truth = score_arm(arm, area, cls)
                        policy = cands.attrs["policy"]
                        per[area] = tabs
                        if arm == "F1":
                            unmatched.append(cands[cands["truth_id"].isna()].assign(area=area, arm=arm, task=cls))
                        for col in ("seen_in", "activity"):
                            for val, g in truth.groupby(col):
                                st = subset_truth(tabs, set(g["truth_id"]))
                                strata_rows.append({"group": group, "task": cls, "area": area, "arm": arm,
                                                    "stratum": f"{col}={val}", "recall": gt.pooled_recall_at_k(st, list(st)),
                                                    "n_truth": sum(v["n_truth"] for v in st.values())})
                    per_arm[arm] = stratified_tables(per)
                fam = list(cfg["multiplicity"]["family"])
                gate = f"F1-L1:{cls}:{group}"
                g = {"primary_F1_minus_L1": gt.paired_arm_difference(per_arm["F1"], per_arm["L1"], dg, B=a.B,
                                                                     seed=int(pr["master_seed"]),
                                                                     gate=gate if gate in fam else None, family=fam)}
                for x, y in (("L1", "O1"), ("F1", "O1"), ("L0", "L1"), ("L2", "L1")):
                    if x not in per_arm:
                        continue
                    d = gt.paired_arm_difference(per_arm[x], per_arm[y], dg, B=a.B, seed=int(pr["master_seed"]))
                    d["label"] = "descriptive, no gate"
                    g[f"{x}_minus_{y}"] = d
                if group != "oklahoma":
                    for v in g.values():
                        v["label"] = "joint state and program contrast, exploratory"
                g["policy"] = policy
                g["note"] = ("pits and pads are scored apart, each at its own policy. A pooled pit-and-pad primary "
                             "needs one declared policy for the merged class (user decision)")
                res[group][cls] = g
    except (gt.MissingInputError, gt.DecisionMissingError) as e:
        print(str(e), file=sys.stderr)
        return 2
    tables, figs = ek.sub(EXP, "results/tables"), ek.sub(EXP, "results/figures")
    (tables / "okks_arm_compare.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    sdf = pd.DataFrame(strata_rows)
    sdf.to_csv(tables / "okks_recall_strata.csv", index=False)
    fig_rows = gain_rows(res)
    gt.plot_recall_strata(pd.DataFrame(fig_rows), figs / "okks_recall_by_arm.png", "Paired gain by contrast (level a)",
                          ylabel="paired gain in recall at K = 40 per km2", ylim=None)
    pd.concat(unmatched).to_csv(ek.sub(EXP, "data/processed") / "okks_unmatched_for_6_3.csv", index=False)
    print(json.dumps({c: res["oklahoma"][c]["primary_F1_minus_L1"] for c in CLASS_TASKS}, indent=2, default=str))
    return 0


def gain_rows(res: dict) -> list[dict]:
    """One figure row per contrast, group and class. Gains can be negative and are plotted as they are."""
    return [{"arm": k.split("_minus_")[0], "stratum": f"{grp} {cls}", "recall": v["gain"], "lo": v["gain_ci"][0],
             "hi": v["gain_ci"][1]}
            for grp, by_cls in res.items() for cls, g in by_cls.items() for k, v in g.items() if isinstance(v, dict)
            and "gain" in v]


if __name__ == "__main__":
    raise SystemExit(main())
