"""3.1 S8. Error review after scoring. Misses by size, slope and void; unmatched candidates to the confuser queue.

Purpose
    Characterise missed truth features by area, 25 m slope (1 m slope raster), void fraction
    (S3 void raster) and block ground density. Compare with found features (medians, counts).
    Unmatched kept candidates are written to a confuser review queue for the 6.3 codebook.
    They are never labelled negatives here. An exploratory weighted least-squares fit of block
    recall on void fraction and ground density is reported, labelled exploratory.

Inputs
    S7b run folder  xfer_found_missed_<area>.gpkg (truth_scored, candidates_kept), xfer_score_blocks_<area>.csv
    S1 roles        results/tables/<area>/xfer_blocks_roles_<area>.gpkg
    rasters         config areas.<area>.slope_1m, data/processed/<area>/05/void_<area>_05.tif

Outputs (in the S7b run folder)
    xfer_error_misses_<area>.csv        one row per truth feature with covariates and found flag
    xfer_confuser_queue_<area>.csv      unmatched kept candidates (class blank, "not negatives")
    xfer_error_review_<area>.json       found vs missed medians, exploratory block regression

Run
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_error_review_wfm.py --area warren
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_1.json"


def sample_raster(path, xs, ys, window_px=1, reducer=np.nanmean):
    import rasterio
    from rasterio.windows import Window
    out = []
    with rasterio.open(path) as r:
        for x, y in zip(xs, ys):
            rr, cc = r.index(x, y)
            h = window_px // 2
            a = r.read(1, window=Window(cc - h, rr - h, window_px, window_px), boundless=True,
                       fill_value=np.nan if r.dtypes[0].startswith("float") else 0).astype(float)
            if r.nodata is not None:
                a[a == r.nodata] = np.nan
            out.append(float(reducer(a)) if np.isfinite(a).any() else np.nan)
    return np.array(out)


def wls(y, X, w):
    X1 = np.c_[np.ones(len(X)), X]
    W = np.sqrt(w)[:, None]
    beta, *_ = np.linalg.lstsq(X1 * W, y * W[:, 0], rcond=None)
    return beta


def review(truth, kept, blocks):
    t = truth.merge(blocks[["block_id", "ground_per_m2", "void_frac", "slope_mean"]], on="block_id", how="left",
                    suffixes=("", "_block"))
    cols = [c for c in ("area_m2", "slope_25m", "void_local", "ground_per_m2") if c in t]
    comp = {c: {"found_median": float(t.loc[t.found, c].median()), "missed_median": float(t.loc[~t.found, c].median())}
            for c in cols}
    q = kept[kept.matched.isin(["nan", "None"]) | kept.matched.isna()].copy()
    q["class"] = ""
    q["note"] = "unmatched candidate for the 6.3 codebook; not a negative"
    return t, q, {"n_truth": int(len(t)), "n_missed": int((~t.found).sum()), "found_vs_missed": comp,
                  "n_confuser_queue": int(len(q))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--run", default=None, help="S7b run folder (default newest *_xfer_score_<area>_*)")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    import geopandas as gpd
    runs = sorted(xl.resolve_path({"exp": cfg["exp_id"], "rel": "results"}).glob(f"*_xfer_score_{a.area}_*"))
    run = Path(a.run) if a.run else (runs[-1] if runs else None)
    if run is None:
        raise xl.MissingInput(f"MISSING INPUT: S7b score run for {a.area}")
    gp = xl.need(run / f"xfer_found_missed_{a.area}.gpkg", "S7b found/missed")
    truth = gpd.read_file(gp, layer="truth_scored")
    kept = gpd.read_file(gp, layer="candidates_kept")
    blocks = gpd.read_file(ctx["tables"] / f"xfer_blocks_roles_{a.area}.gpkg", layer="blocks")
    rp = truth.geometry.representative_point()
    truth["area_m2"] = truth.geometry.area
    if ctx.get("slope_1m") and Path(ctx["slope_1m"]).exists():
        truth["slope_25m"] = sample_raster(ctx["slope_1m"], rp.x, rp.y, 25)
    vr = ctx["heavy"] / f"void_{a.area}_05.tif"
    if vr.exists():
        truth["void_local"] = sample_raster(vr, rp.x, rp.y, 21)
    t, q, meta = review(truth, kept, blocks)
    per = pd.read_csv(run / f"xfer_score_blocks_{a.area}.csv").merge(
        blocks[["block_id", "void_frac", "ground_per_m2"]], on="block_id")
    per = per[per.n_truth > 0].dropna(subset=["void_frac", "ground_per_m2"])
    if len(per) >= 5:
        beta = wls((per.hits / per.n_truth).to_numpy(), per[["void_frac", "ground_per_m2"]].to_numpy(), per.n_truth.to_numpy(float))
        meta["exploratory_block_wls"] = {"intercept": beta[0], "void_frac": beta[1], "ground_per_m2": beta[2],
                                         "n_blocks": int(len(per)), "label": "exploratory"}
    o1, o2, o3 = run / f"xfer_error_misses_{a.area}.csv", run / f"xfer_confuser_queue_{a.area}.csv", run / f"xfer_error_review_{a.area}.json"
    t.drop(columns="geometry").to_csv(o1, index=False)
    q.drop(columns="geometry").assign(x=q.geometry.centroid.x, y=q.geometry.centroid.y).to_csv(o2, index=False)
    o3.write_text(json.dumps(meta, indent=2, default=float), encoding="utf-8")
    print(json.dumps(meta, indent=2, default=float))
    print(f"wrote {o1}\n      {o2}\n      {o3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
