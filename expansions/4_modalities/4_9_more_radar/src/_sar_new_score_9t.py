"""S5 of framework 4.9. Paired AUC gain of each SAR arm over the rich lidar baseline, out of fold, by block.

Purpose. Same model family and CV as the NISAR result. fit_predict and oof_probs are imported from
notebooks/wellsight_v2/s5_eval/_nisar_feat_common.py (histogram gradient boosting, band dropping and median
imputation inside the training fold, 5-fold GroupKFold by block, training rows within 250 m of a test row removed).
Repeat 0 is the deterministic GroupKFold. Repeats 1 to n are StratifiedGroupKFold with child seeds. Scores are the
mean out-of-fold probability over repeats. Then per arm and stratum (all, lidar_weak by baseline score)
  gain       AUC(baseline + arm) - AUC(baseline), paired block bootstrap B = 2000 (same blocks for both)
  perm       paired permutation interval when fewer than 15 blocks
  placebo    the arm's columns permuted within block, scored the same way
  decision   success if lo > delta, failure if hi < delta and the stratum is eligible in S1, else inconclusive
  holm       Holm-adjusted one-sided p (gain > 0) over the exploratory arms, shown beside each interval
--heldout fits on all 9t rows, freezes, and scores the 613590 rows. That test is confirmatory.
--baseline-only writes the per-row baseline score file S1 needs.
Inputs.
  expansions/4_modalities/4_9_more_radar/data/processed/sar_rows_<target>_9t.csv (from S4, arm columns arm:<A>:*)
  data/9t/results/sar_new/sar_power_eligibility_9t.json (from S1, optional)
  a 613590 rows CSV with the same columns (assumed, --heldout)
Outputs.
  data/9t/results/sar_new/sar_new_gain_by_arm_9t.csv
  data/9t/results/sar_new/sar_new_heldout_gain_613590.csv (with --heldout)
  expansions/4_modalities/4_9_more_radar/data/processed/sar_baseline_rows_<target>_9t.csv (with --baseline-only)
Run.
  python expansions/4_modalities/4_9_more_radar/src/_sar_new_score_9t.py --target pit --arms A1 A2 [--repeats 10] [--B 2000] [--heldout CSV] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import _sar_kit_4_9 as sk


def nisar_common():
    sys.path.insert(0, str(sk.S5_EVAL))
    argv, sys.argv = sys.argv, sys.argv[:1]
    try:
        import _nisar_feat_common as C
    finally:
        sys.argv = argv
    return C


def oof_mean(C, X, y, grp, xy, buffer_m, repeats, master) -> np.ndarray:
    ps = []
    for r in range(repeats):
        p, _ = C.oof_probs(X, y, grp, xy=xy, buffer_m=buffer_m, seed=None if r == 0 else sk.ek.child_seed(master, r, 0))
        ps.append(p)
    return np.nanmean(np.vstack(ps), 0)


def permute_within_block(X: np.ndarray, blocks: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    Xp = X.copy()
    for b in np.unique(blocks):
        i = np.flatnonzero(blocks == b)
        Xp[i] = X[rng.permutation(i)]
    return Xp


def gain_row(y, sb, sa, blocks, cfg, seed, label) -> dict:
    pr = cfg["prereg"]
    bt = sk.paired_gain_boot(y, sb, sa, blocks, pr["B"], seed)
    r = {"set": label, "n_targets": int(y.sum()), "n_decoys": int((1 - y).sum()), "n_blocks": bt["n_blocks"], "n_target_blocks": bt["n_target_blocks"],
         "auc_base": sk.auc(y, sb), "auc_arm": sk.auc(y, sa), "gain": bt["gain"], "lo": bt["lo"], "hi": bt["hi"],
         "p_gain_le_0": float((bt["draws"] <= 0).mean()) if len(bt["draws"]) else np.nan,
         "bootstrap_unreliable": bt["n_target_blocks"] < pr["min_blocks_bootstrap"]}
    if r["bootstrap_unreliable"]:
        r.update(sk.paired_perm(y, sb, sa, blocks, pr["n_permutations"], seed + 1))
    return r


def decide(r: dict, delta: float, eligible: bool | None) -> str:
    d = sk.ek.decide(r["lo"], r["hi"], delta, "superiority")
    if d == "failure" and eligible is False:
        return "inconclusive (stratum not eligible, no room)"
    return d


def main(argv=None) -> int:
    cfg = sk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", default=pr["primary_target"], choices=sorted(cfg["targets"]))
    ap.add_argument("--arms", nargs="*", default=[])
    ap.add_argument("--rows", default=None)
    ap.add_argument("--repeats", type=int, default=pr["n_repeats"])
    ap.add_argument("--B", type=int, default=pr["B"])
    ap.add_argument("--baseline-only", action="store_true")
    ap.add_argument("--heldout", default=None, help="613590 rows CSV with the same columns")
    ap.add_argument("--eligibility", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    pr["B"] = a.B
    proc = sk.ek.exp_dir("4.9") / "data" / "processed"
    rp = sk.need(Path(a.rows) if a.rows else proc / f"sar_rows_{a.target}_9t.csv", "frozen rows (S4 --rows-only)")
    df = pd.read_csv(rp)
    sk.ek.assert_unique(df, "row")
    sk.ek.assert_no_nan(df.block, "block")
    y, grp, xy = df.y.to_numpy(int), df.block.to_numpy(), df[["x", "ym"]].to_numpy(float)
    base_cols = [c for c in df if c.startswith("base:")]
    C = nisar_common()
    Xb = df[base_cols].to_numpy(float)
    sb = oof_mean(C, Xb, y, grp, xy, pr["cv_buffer_m"], a.repeats, pr["master_seed"])
    if a.baseline_only:
        f = proc / f"sar_baseline_rows_{a.target}_9t.csv"
        pd.DataFrame({"row": df.row, "y": y, "block": grp, "score": sb}).to_csv(f, index=False)
        sk.prov(proc, f"sar_baseline_rows_{a.target}", inputs=[rp], outputs=[f], params={"repeats": a.repeats})
        print(f, "baseline AUC", round(sk.auc(y, sb), 4))
        return 0
    if not a.arms:
        raise ValueError("--arms is needed unless --baseline-only")
    out = Path(a.out) if a.out else sk.resolve(cfg["outputs"]["results"])
    ep = Path(a.eligibility) if a.eligibility else out / "sar_power_eligibility_9t.json"
    elig = json.loads(ep.read_text())["strata"] if ep.exists() else {}
    cut = np.quantile(sb[y == 1], pr["lidar_weak_quantile"])
    strata = {"all": np.ones(len(y), bool), "lidar_weak": (y == 0) | (sb <= cut)}
    rows = []
    for k, arm in enumerate(a.arms):
        ac = [c for c in df if c.startswith(f"arm:{arm}:")]
        if not ac:
            raise ValueError(f"no arm:{arm}:* columns in {rp}. Run S4 for {arm}")
        Xa = df[base_cols + ac].to_numpy(float)
        Xp = np.hstack([Xb, permute_within_block(df[ac].to_numpy(float), grp, sk.ek.child_seed(pr["master_seed"], 0, 900 + k))])
        sa = oof_mean(C, Xa, y, grp, xy, pr["cv_buffer_m"], a.repeats, pr["master_seed"])
        sp = oof_mean(C, Xp, y, grp, xy, pr["cv_buffer_m"], a.repeats, pr["master_seed"])
        for sname, m in strata.items():
            for kind, s in (("arm", sa), ("placebo", sp)):
                r = gain_row(y[m], sb[m], s[m], grp[m], cfg, sk.ek.child_seed(pr["master_seed"], k, len(rows)), f"{arm}:{sname}:{kind}")
                r.update(arm=arm, stratum=sname, kind=kind, primary=bool(arm == pr["primary_arm"] and a.target == pr["primary_target"] and kind == "arm"))
                e = [v["eligible"] for kk, v in elig.items() if kk.endswith(f":{sname}")]
                r["eligible"] = any(e) if e else None
                r["decision"] = decide(r, pr["delta_gain"], r["eligible"]) if kind == "arm" else "placebo"
                rows.append(r)
    tab = pd.DataFrame(rows)
    expl = tab[(tab.kind == "arm") & ~tab.primary]
    adj = sk.holm(dict(zip(expl.set, expl.p_gain_le_0))) if len(expl) else {}
    tab["holm_p"] = tab.set.map(adj)
    tab["label"] = np.where(tab.primary, "primary", np.where(tab.kind == "arm", "exploratory", "placebo"))
    out.mkdir(parents=True, exist_ok=True)
    f = out / "sar_new_gain_by_arm_9t.csv"
    tab.to_csv(f, index=False)
    outs = [f]
    if a.heldout:
        ho = pd.read_csv(sk.need(Path(a.heldout), "613590 held-out rows"))
        hrows = []
        for arm in a.arms:
            ac = [c for c in df if c.startswith(f"arm:{arm}:")]
            miss = [c for c in base_cols + ac if c not in ho]
            if miss:
                raise ValueError(f"held-out rows lack {miss[:3]}")
            hb = C.fit_predict(Xb, y, ho[base_cols].to_numpy(float))
            ha = C.fit_predict(df[base_cols + ac].to_numpy(float), y, ho[base_cols + ac].to_numpy(float))
            r = gain_row(ho.y.to_numpy(int), hb, ha, ho.block.to_numpy(), cfg, pr["master_seed"] + 77, f"{arm}:heldout_613590")
            r["decision"] = decide(r, pr["delta_gain"], None)
            r["label"] = "confirmatory" if arm == pr["primary_arm"] else "exploratory"
            hrows.append(r)
        hf = out / "sar_new_heldout_gain_613590.csv"
        pd.DataFrame(hrows).to_csv(hf, index=False)
        outs.append(hf)
    sk.prov(out, "sar_new_score_9t", inputs=[rp, ep], outputs=outs, params=pr, seeds={"master": pr["master_seed"]})
    print(tab[["set", "gain", "lo", "hi", "decision", "holm_p"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
