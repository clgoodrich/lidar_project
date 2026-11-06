"""4.2 stage T3. Covariate-adjusted pad minus matched-clearing LST, block bootstrap, gate against delta_T (9t).

Purpose
    Lidar null. OLS of LST on the lidar-null covariates (CHM, slope, aspect, solar loading, antecedent
    rain, NLCD class dummies) with scene fixed effects, fitted on control sites only (clearings and
    forest), so a pad's residual is what the lidar null does not explain. Then, per pair and scene, the
    pad residual minus its matched clearing residual. Scene differences are averaged to the pair (site
    scenes are not independent), then a block bootstrap (B = 2000) of the mean over 375 m blocks.
    Decision with ek.decide (superiority) on sign x contrast against delta_T, sign preregistered in config.
    statsmodels is not installed, so the scene random effect of the framework is replaced by scene fixed
    effects (decision 2026-11-05). Exploratory splits by leaf state are written but not gated.
Inputs
    samples   <run>_thermal_samples_*/thermal_samples_by_scene_9t.csv (from _thermal_extract_samples_9t.py)
Outputs (expansions/4_modalities/4_2_thermal/results/<YYYYMMDD>_thermal_contrast_<hash7>/)
    thermal_contrast_estimates_9t.csv (per pair), thermal_contrast_summary_9t.json, provenance
Run
    python expansions/4_modalities/4_2_thermal/src/_thermal_contrast_model_9t.py [--samples PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _thermal_shared_io as io
from _thermal_shared_io import ek

SHORT = "thermal_contrast"


def design(df: pd.DataFrame, covs: list[str]) -> np.ndarray:
    X = df[covs].astype(float).copy()
    X = X.fillna(X.mean())
    if "nlcd_major" in df.columns and df["nlcd_major"].notna().any():
        X = pd.concat([X, pd.get_dummies(df["nlcd_major"].fillna(-1).astype(int), prefix="nlcd", drop_first=True,
                                         dtype=float)], axis=1)
    return X.to_numpy(float)


def lidar_null_residuals(s: pd.DataFrame, covs: list[str]) -> np.ndarray:
    """Residual LST after scene fixed effects and covariates, model fitted on controls only."""
    d = s.copy()
    ctrl_mean = d[d["site_class"] != "pad"].groupby("scene_id")["lst_K"].mean()
    d["lst_c"] = d["lst_K"] - d["scene_id"].map(ctrl_mean)
    X = design(d, covs)
    Xc = X - pd.DataFrame(X).groupby(d["scene_id"].to_numpy()).transform("mean").to_numpy()
    ctrl = (d["site_class"] != "pad").to_numpy() & np.isfinite(d["lst_c"].to_numpy())
    beta, *_ = np.linalg.lstsq(np.c_[np.ones(ctrl.sum()), Xc[ctrl]], d["lst_c"].to_numpy()[ctrl], rcond=None)
    return d["lst_c"].to_numpy() - np.c_[np.ones(len(d)), Xc] @ beta


def run(cfg: dict, out_root: Path | None = None, samples_path: Path | None = None) -> dict:
    sp = Path(samples_path) if samples_path else io.latest_run(io.EXP, "thermal_samples") / "thermal_samples_by_scene_9t.csv"
    s = pd.read_csv(io.need(sp, "T2 samples"))
    s = s[np.isfinite(s["lst_K"]) & ~s["partial"].astype(bool)].copy()
    s = s[s["pair_id"].notna()]                      # T3 compares matched pairs only
    c = cfg["contrast"]
    g = cfg["gate"]
    sign = int(c["expected_sign"])
    run_dir = ek.new_run(io.EXP, SHORT, {"contrast": c, "delta_T_K": g["delta_T_K"], "samples": str(sp)}, base=out_root,
                         why="T3 covariate-adjusted contrast.")
    s["resid"] = lidar_null_residuals(s, c["null_covariates"])
    p = s[s.site_class == "pad"][["pair_id", "scene_id", "block_id", "resid", "leaf_state"]]
    q = s[s.site_class == "clearing"][["pair_id", "scene_id", "resid"]]
    m = p.merge(q, on=["pair_id", "scene_id"], suffixes=("_pad", "_clear"), how="inner")
    m["diff_K"] = m["resid_pad"] - m["resid_clear"]
    per = m.groupby("pair_id").agg(block_id=("block_id", "first"), diff_K=("diff_K", "mean"),
                                   n_scenes=("scene_id", "nunique")).reset_index()
    ek.assert_unique(per, "pair_id")
    byb = {b: d["diff_K"].to_numpy() for b, d in per.groupby("block_id")}
    blocks = list(byb)
    stat = lambda bl: float(np.mean(np.concatenate([byb[b] for b in bl]))) * sign  # noqa: E731
    pt, lo, hi, dr = ek.block_bootstrap(stat, blocks, B=g["bootstrap_B"], seed=ek.child_seed(cfg["master_seed"], arm=30))
    verdict = ek.decide(lo, hi, g["delta_T_K"], "superiority")
    explo = {}
    for ls, d in m.groupby("leaf_state"):
        explo[str(ls)] = {"n_pairs": int(d["pair_id"].nunique()), "mean_diff_K": float(d["diff_K"].mean())}
    summary = {"stage": "T3", "evidence_level": "(a). A surface difference, never a leak or a well",
               "n_pairs": int(len(per)), "n_blocks": len(blocks), "n_pair_scenes": int(len(m)),
               "expected_sign": sign, "signed_contrast_K": pt, "lo": lo, "hi": hi, "delta_T_K": g["delta_T_K"],
               "undefined_share": ek.undefined_share(dr),
               "verdict": verdict, "exploratory_by_leaf_state": explo,
               "note": "Failure means no detectable contrast at this pixel size. It does not exclude a drone signal"}
    if len(blocks) < 15:
        summary["warning"] = "fewer than 15 blocks, bootstrap unreliable. Add a permutation interval"
    out_c = run_dir / "thermal_contrast_estimates_9t.csv"
    out_j = run_dir / "thermal_contrast_summary_9t.json"
    per.to_csv(out_c, index=False)
    out_j.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return io.finish(run_dir, summary, inputs=[sp], outputs=[out_c, out_j], params=c, seeds={"master": cfg["master_seed"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--samples", type=Path, default=None)
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.out_root, a.samples), indent=1, default=str))


if __name__ == "__main__":
    main()
