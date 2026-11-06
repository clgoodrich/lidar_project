"""4.2 stage T4. Does LST add pad-versus-clearing ranking gain beyond lidar? Recall at K = 40 per km2 and AUC (9t).

Purpose
    Site-level table of pads (label 1) and clearings (label 0) from the unmatched population layer of the
    match run (review 4.2-01). On the caliper-matched layer lidar is uninformative by construction, so the
    verdict there is not_identifiable. Lidar features from the matching table. LST features are the mean lidar-null residual per leaf-state season from T2 samples (residual
    model from _thermal_contrast_model_9t.py). Out-of-fold logistic ranking, lidar only versus lidar plus
    LST, on the 3.0 scorer block folds. Paired block bootstrap of the differences (_thermal_shared_io.added_value).
    Decision with ek.decide (superiority) against delta_gain on recall at K. Undefined bootstrap draws are
    counted and reported (SH-01). Above added_value.max_undefined the interval is undefined and the verdict
    is inconclusive. T4 is one of two primaries (T3, T4). The stage verdict is unadjusted. The gate is Holm
    over both primaries in _thermal_primary_holm_9t.py, from p_success and p_failure on recall at K.
Inputs
    sites     <run>_thermal_match_*/thermal_matched_sites_9t.gpkg
    samples   <run>_thermal_samples_*/thermal_samples_by_scene_9t.csv (T2 run with --layer population)
    folds     expansions/4_modalities/4_2_thermal/data/raw/transfer_blocks.csv (assumed, block_id, fold)
Outputs (expansions/4_modalities/4_2_thermal/results/<YYYYMMDD>_thermal_added_<hash7>/)
    thermal_added_value_9t.csv (out-of-fold scores per site), thermal_added_value_9t.json, provenance
Run
    python expansions/4_modalities/4_2_thermal/src/_thermal_added_value_9t.py [--sites P] [--samples P] [--folds P | --fallback-folds 5]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _thermal_shared_io as io
from _thermal_shared_io import ek
from _thermal_contrast_model_9t import lidar_null_residuals

SHORT = "thermal_added"


def assign_folds(blocks: pd.Series, folds_path: Path | None, fallback: int | None) -> tuple[np.ndarray, str]:
    if folds_path is not None and Path(folds_path).exists():
        f = pd.read_csv(folds_path)
        f["block_id"] = f["block_id"].astype(str)
        mp = dict(zip(f["block_id"], f["fold"]))
        miss = sorted(set(blocks) - set(mp))
        if miss:
            raise AssertionError(f"blocks without a fold: {miss[:5]}")
        return blocks.map(mp).to_numpy(), "3.0 scorer folds"
    if not fallback:
        io.need(folds_path, "block folds", "CSV block_id, fold")
    ub = np.array(sorted(set(blocks)))
    rng = np.random.default_rng(0)
    mp = dict(zip(ub, rng.permutation(len(ub)) % fallback))
    return blocks.map(mp).to_numpy(), f"fallback {fallback} random block folds (not the shared scheme, exploratory)"


def site_table(sites: pd.DataFrame, samples: pd.DataFrame, covs: list[str]) -> tuple[pd.DataFrame, list[str]]:
    s = samples[np.isfinite(samples["lst_K"])].copy()
    s["resid"] = lidar_null_residuals(s, covs)
    s["leaf_state"] = s["leaf_state"].fillna("unknown")
    w = s.pivot_table(index="site_id", columns="leaf_state", values="resid", aggfunc="mean")
    w.columns = [f"lst_resid_{c}" for c in w.columns]
    t = sites[sites.site_class.isin(["pad", "clearing"])].drop(columns="geometry").merge(w, left_on="site_id",
                                                                                          right_index=True, how="left")
    t["label"] = (t["site_class"] == "pad").astype(int)
    return t, list(w.columns)


def identifiability(sites: pd.DataFrame, layer: str) -> tuple[bool, str]:
    """Review 4.2-01. Added value over lidar is identifiable only on a population not matched on the lidar
    covariates. On the caliper-matched set lidar is uninformative by construction (lidar AUC near 0.5),
    so any gain is an artefact of the design. Decision 2026-11-06, see docs/decisions_4_2.md."""
    pop = set(sites["population"].dropna().astype(str)) if "population" in sites.columns else set()
    if pop == {"unmatched"}:
        return True, "unmatched population (every pad and eligible clearing)"
    return False, (f"layer {layer!r} is matched on the lidar covariates (population {sorted(pop) or 'unlabelled'}). "
                   "Lidar is uninformative there by construction, so added value is not identifiable")


def run(cfg: dict, out_root: Path | None = None, sites_path=None, samples_path=None, folds_path=None,
        fallback_folds: int | None = None, layer: str = "population") -> dict:
    import geopandas as gpd
    av = cfg["added_value"]
    sp = Path(sites_path) if sites_path else io.latest_run(io.EXP, "thermal_match") / "thermal_matched_sites_9t.gpkg"
    tp = Path(samples_path) if samples_path else io.latest_run(io.EXP, "thermal_samples") / "thermal_samples_by_scene_9t.csv"
    sites = gpd.read_file(io.need(sp, "matched sites"), layer=layer)
    ident, ident_msg = identifiability(sites, layer)
    samples = pd.read_csv(io.need(tp, "T2 samples"))
    t, extra = site_table(sites, samples, cfg["contrast"]["null_covariates"])
    no_lst = t[extra].isna().all(axis=1) if extra else pd.Series(True, index=t.index)
    if no_lst.any():
        raise RuntimeError(f"{int(no_lst.sum())} of {len(t)} sites in layer {layer!r} have no T2 sample. "
                           f"Run T2 with --layer {layer} on the same match run")
    fp = Path(folds_path) if folds_path else io.resolve(cfg["inputs"]["folds"])
    t["fold"], fold_src = assign_folds(t["block_id"].astype(str), fp, fallback_folds)
    area = {b: (io.BLOCK_M / 1000) ** 2 for b in t["block_id"].unique()}
    run_dir = ek.new_run(io.EXP, SHORT, {"added_value": av, "folds": fold_src, "extra": extra}, base=out_root,
                         why="T4 added value of LST over lidar.")
    r = io.added_value(t, av["lidar_features"], extra, "label", "fold", "block_id", area, av["k_per_km2"],
                       B=cfg["gate"]["bootstrap_B"], seed=ek.child_seed(cfg["master_seed"], arm=40),
                       max_undefined=float(av.get("max_undefined", 0.0)), margin=float(av["delta_gain"]))
    scores = r.pop("scores")
    rk = r["recall_at_k"]
    v = ek.decide(rk["lo"], rk["hi"], av["delta_gain"], "superiority") if ident else "not_identifiable"
    r.update(stage="T4", layer=layer, identifiable=ident, identifiability=ident_msg, fold_source=fold_src,
             extra_features=extra, delta_gain=av["delta_gain"], verdict_unadjusted=v,
             gated_by="Holm over T3 and T4 (_thermal_primary_holm_9t.py)",
             note="Failure means lidar already holds the signal. Evidence level (a)")
    out_c = run_dir / "thermal_added_value_9t.csv"
    out_j = run_dir / "thermal_added_value_9t.json"
    pd.concat([t[["site_id", "site_class", "block_id", "fold", "label"]].reset_index(drop=True), scores.reset_index(drop=True)],
              axis=1).to_csv(out_c, index=False)
    out_j.write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
    return io.finish(run_dir, r, inputs=[sp, tp] + ([fp] if fp and Path(fp).exists() else []), outputs=[out_c, out_j],
                     params=av, seeds={"master": cfg["master_seed"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--sites", type=Path, default=None)
    ap.add_argument("--samples", type=Path, default=None)
    ap.add_argument("--folds", type=Path, default=None)
    ap.add_argument("--fallback-folds", type=int, default=None)
    ap.add_argument("--layer", choices=("population", "sites"), default="population",
                    help="population (default) is identifiable. sites is matched on lidar and gives not_identifiable")
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.out_root, a.sites, a.samples, a.folds, a.fallback_folds, a.layer),
                     indent=1, default=str))


if __name__ == "__main__":
    main()
