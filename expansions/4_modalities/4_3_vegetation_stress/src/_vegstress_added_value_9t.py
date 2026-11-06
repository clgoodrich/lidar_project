"""4.3 stage V3, Question A. Do vegetation indices add pad-versus-control ranking gain beyond lidar? (9t)

Purpose
    Site table of pads (label 1) and non-well disturbance (label 0) from the unmatched population layer of
    the match run (review 4.3-02). On the matched layer lidar is uninformative by construction, so the
    verdict there is not_identifiable. Undefined bootstrap draws are counted and reported (SH-01).
    Lidar features from the matching table. Index features are the per-season site means of each index's site-minus-ring
    difference from V2 (repeated scenes averaged to the site, so site-seasons are not counted as
    independent). Out-of-fold logistic ranking, lidar only versus lidar plus index, same folds and
    blocks, recall at K = 40 per km2 and AUC with a paired block bootstrap (4.2 added_value code).
    Decision with ek.decide (superiority) against delta_gain on recall at K. V3 is primary A of two
    primaries (V3, V4 all labels). The stage verdict is unadjusted. The gate is Holm over both primaries in
    _vegstress_primary_holm_9t.py, from p_success and p_failure on recall at K.
Inputs
    sites     <run>_vegstress_match_*/vegstress_matched_sites_9t.gpkg
    by_site   <run>_vegstress_sites_*/vegstress_by_site_9t.csv
    folds     expansions/4_modalities/4_3_vegetation_stress/data/raw/transfer_blocks.csv (assumed)
Outputs (expansions/4_modalities/4_3_vegetation_stress/results/<YYYYMMDD>_vegstress_added_<hash7>/)
    vegstress_added_value_9t.csv, vegstress_added_value_9t.json, vegstress_added_value_9t.png, provenance
Run
    python expansions/4_modalities/4_3_vegetation_stress/src/_vegstress_added_value_9t.py [--sites P] [--by-site P] [--folds P | --fallback-folds 5]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _vegstress_shared_io as io
from _vegstress_shared_io import ek
from _thermal_added_value_9t import assign_folds, identifiability   # 4.2 code

SHORT = "vegstress_added"


def site_features(by_site: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    cols = [c for c in by_site.columns if c.endswith("_diff")]
    w = by_site.pivot_table(index="site_id", columns="season", values=cols, aggfunc="mean")
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    w = w.loc[:, w.notna().any()]
    return w, list(w.columns)


def figure(r: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 3.2))
    for i, (k, lab) in enumerate((("recall_at_k", "Recall at K"), ("auc", "AUC"))):
        d = r[k]
        ax.errorbar([d["diff"]], [i], xerr=[[d["diff"] - d["lo"]], [d["hi"] - d["diff"]]], fmt="o" if i else "s",
                    color=ek.PALETTE["blue"] if i == 0 else ek.PALETTE["orange"], capsize=4)
    ax.axvline(0, color=ek.PALETTE["grey"], lw=1)
    ax.axvline(r["delta_gain"], color=ek.PALETTE["charcoal"], lw=1, ls="--")
    ax.set_yticks([0, 1], ["Recall at K", "AUC"])
    ax.set_xlabel("Lidar plus index minus lidar only (95% block bootstrap)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(cfg: dict, out_root: Path | None = None, sites_path=None, by_site_path=None, folds_path=None,
        fallback_folds: int | None = None, layer: str = "population") -> dict:
    import geopandas as gpd
    av = cfg["added_value"]
    sp = Path(sites_path) if sites_path else io.latest_run("vegstress_match") / "vegstress_matched_sites_9t.gpkg"
    bp = Path(by_site_path) if by_site_path else io.latest_run("vegstress_sites") / "vegstress_by_site_9t.csv"
    sites = gpd.read_file(io.need(sp, "matched sites"), layer=layer).drop(columns="geometry")
    ident, ident_msg = identifiability(sites, layer)
    w, extra = site_features(pd.read_csv(io.need(bp, "V2 per-site table")))
    t = sites.merge(w, left_on="site_id", right_index=True, how="left")
    gone = ~t["site_id"].isin(w.index)
    if gone.any():
        raise RuntimeError(f"{int(gone.sum())} of {len(t)} sites in layer {layer!r} have no V2 row. "
                           f"Run V2 with --layer {layer} on the same match run")
    t["label"] = (t["site_class"] == "pad").astype(int)
    fp = Path(folds_path) if folds_path else io.resolve(cfg["inputs"]["folds"])
    t["fold"], fold_src = assign_folds(t["block_id"].astype(str), fp, fallback_folds)
    area = {b: (io.BLOCK_M / 1000) ** 2 for b in t["block_id"].unique()}
    run_dir = ek.new_run(io.EXP, SHORT, {"added_value": av, "folds": fold_src, "extra": extra}, base=out_root,
                         why="V3 Question A added value.")
    r = io.added_value(t, av["lidar_features"], extra, "label", "fold", "block_id", area, av["k_per_km2"],
                       B=av["bootstrap_B"], seed=ek.child_seed(cfg["master_seed"], arm=30),
                       max_undefined=float(av.get("max_undefined", 0.0)), margin=float(av["delta_gain"]))
    scores = r.pop("scores")
    rk = r["recall_at_k"]
    v = ek.decide(rk["lo"], rk["hi"], av["delta_gain"], "superiority") if ident else "not_identifiable"
    r.update(stage="V3", question="A disturbance and morphology", layer=layer, identifiable=ident,
             identifiability=ident_msg, fold_source=fold_src, extra_features=extra,
             delta_gain=av["delta_gain"], verdict_unadjusted=v,
             gated_by="Holm over V3 and V4 all labels (_vegstress_primary_holm_9t.py)",
             note="Failure means the CHM and land cover hold the signal. A difference in disturbed ground, not leakage")
    out_c, out_j, out_p = (run_dir / "vegstress_added_value_9t.csv", run_dir / "vegstress_added_value_9t.json",
                           run_dir / "vegstress_added_value_9t.png")
    pd.concat([t[["site_id", "site_class", "block_id", "fold", "label"]].reset_index(drop=True),
               scores.reset_index(drop=True)], axis=1).to_csv(out_c, index=False)
    out_j.write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
    if np.isfinite(r["recall_at_k"]["lo"]) and np.isfinite(r["auc"]["lo"]):
        figure(r, out_p)
    else:
        out_p = None
    return io.finish(run_dir, r, inputs=[sp, bp], outputs=[x for x in (out_c, out_j, out_p) if x], params=av,
                     seeds={"master": cfg["master_seed"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--sites", type=Path, default=None)
    ap.add_argument("--by-site", type=Path, default=None)
    ap.add_argument("--folds", type=Path, default=None)
    ap.add_argument("--fallback-folds", type=int, default=None)
    ap.add_argument("--layer", choices=("population", "sites"), default="population",
                    help="population (default) is identifiable. sites is matched on lidar and gives not_identifiable")
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.out_root, a.sites, a.by_site, a.folds, a.fallback_folds, a.layer),
                     indent=1, default=str))


if __name__ == "__main__":
    main()
