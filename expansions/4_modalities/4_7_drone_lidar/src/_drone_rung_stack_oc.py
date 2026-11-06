"""S4 of framework 4.7. Rebuild DEMs (and optionally the full 9t feature stack plus inference) for every ladder rung.

Purpose. Every rung and seed gets the same grid, taken from the native cloud's extent snapped to stack_res_m, so
rungs are paired cell for cell. Two modes.
  --dem-only   PDAL CLI only. Ground IDW DEM, ground count and void fraction per rung. Cheap, CPU, runnable on any
               ladder. This is the density effect on the DEM itself.
  full         calls build() in notebooks/wellsight_v2/s1_build/_build_derivatives.py with the 9t builders at the same
               grid, writing data/<sfx>/derived/, then runs notebooks/wellsight_v2/s4_infer/_predict_on_tile.py
               --suffix <sfx> (frozen 9t models, same normalisation). Needs the GPU. Skip inference with --no-infer.
sfx is oc_drone_r<rate>_s<k>_05 (rate and seed differ between side-by-side rungs, so both are in the name).
Inputs.
  <stem>_ladder_oc.csv from S3 (default data/oilcreek/derived/drone_thinned/)
Outputs.
  dem-only  <out>/<sfx>/dem_<sfx>.tif, ground_count_<sfx>.tif (default out data/oilcreek/derived/drone_thinned/stacks/)
  full      data/<sfx>/derived/* and data/<sfx>/derived/inference/pit_prob_floor_<sfx>.tif
  both      <ladder stem>_rungs_oc.csv   one row per rung and seed with sfx, paths, void fraction, DEM NaN share
Run.
  python expansions/4_modalities/4_7_drone_lidar/src/_drone_rung_stack_oc.py --ladder CSV [--dem-only] [--no-infer] [--res 0.5] [--out DIR]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import _drone_kit_4_7 as dk


def dem_only(las: Path, sfx: str, out: Path, res: float, grid) -> dict:
    d = out / sfx
    d.mkdir(parents=True, exist_ok=True)
    x0, y0, W, H = grid
    dem_p = d / f"dem_{sfx}.tif"
    dk.run_pdal([{"type": "readers.las", "filename": str(las)},
                 {"type": "filters.range", "limits": "Classification[2:2]"},
                 {"type": "writers.gdal", "filename": str(dem_p), "output_type": "idw", "resolution": res,
                  "origin_x": x0, "origin_y": y0, "width": W, "height": H, "window_size": 3,
                  "data_type": "float32", "nodata": -9999}], label=f"dem_{sfx}", tmp_dir=d, verbose=False)
    gc = dk.count_raster(las, d / f"ground_count_{sfx}.tif", res, grid, "Classification[2:2]", d, f"gc_{sfx}")
    dem = dk.read_tif(dem_p)
    return {"dem": str(dem_p), "void_fraction": float((gc == 0).mean()), "dem_nan_share": float(np.isnan(dem).mean())}


def full_stack(las: Path, sfx: str, res: float, grid, crs: str, infer: bool, cfg: dict) -> dict:
    sys.path.insert(0, str(dk.ek.REPO / "notebooks" / "wellsight_v2" / "s1_build"))
    from _build_derivatives import build
    x0, y0, W, H = grid
    out_dir = dk.ek.path_for("derived") / sfx / "derived"
    build([las], x0=x0, y0=y0, x1=x0 + W * res, y1=y0 + H * res, res=res, sfx=sfx, dst_crs=crs, out_dir=out_dir)
    gd = dk.read_tif(out_dir / f"ground_density_{sfx}.tif")
    r = {"stack_dir": str(out_dir), "void_fraction": float((np.nan_to_num(gd) == 0).mean()),
         "dem_nan_share": float(np.isnan(dk.read_tif(out_dir / f"dem_{sfx}.tif")).mean())}
    prob = out_dir / "inference" / cfg["score"]["prob_name"].format(sfx=sfx)
    if infer:
        subprocess.run([sys.executable, str(dk.ek.REPO / cfg["infer"]["predictor"]), "--suffix", sfx], check=True)
    r["prob"] = str(prob)
    r["prob_exists"] = prob.exists()
    return r


def main(argv=None) -> int:
    cfg = dk.load_cfg()
    L = cfg["ladder"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ladder", required=True)
    ap.add_argument("--dem-only", action="store_true")
    ap.add_argument("--no-infer", action="store_true")
    ap.add_argument("--res", type=float, default=L["stack_res_m"])
    ap.add_argument("--out", default=None, help="dem-only output root")
    a = ap.parse_args(argv)
    lad_p = dk.need(Path(a.ladder), "S3 ladder table (run _drone_thin_ladder_oc.py first)")
    lad = pd.read_csv(lad_p)
    dk.ek.assert_unique(lad.assign(k=lad.rate.astype(str) + "_" + lad.seed_idx.astype(str)), "k")
    native = Path(lad.loc[lad.rate == 1.0, "path"].iloc[0])
    info = dk.las_info(dk.need(native, "native cloud named in the ladder"))
    grid = dk.grid_of(info["mins"], info["maxs"], a.res)
    out = Path(a.out) if a.out else dk.resolve(cfg["outputs"]["thinned"]) / "stacks"
    rows = []
    for r in lad.itertuples():
        sfx = dk.rung_sfx(cfg["area_tag"], r.rate, r.seed_idx, a.res)
        las = dk.need(Path(r.path), f"thinned cloud {sfx}")
        res = dem_only(las, sfx, out, a.res, grid) if a.dem_only else full_stack(las, sfx, a.res, grid, cfg["crs"], not a.no_infer, cfg)
        rows.append({"sfx": sfx, "rate": r.rate, "seed_idx": r.seed_idx, "ground_ppsm": r.ground_ppsm, **res})
    df = pd.DataFrame(rows)
    dk.ek.assert_rows(df, len(lad), "rungs")
    f = lad_p.with_name(lad_p.stem.replace("_ladder_oc", "") + "_rungs_oc.csv")
    df.to_csv(f, index=False)
    dk.prov(f.parent, "drone_rung_stack", inputs=[lad_p], outputs=[f], params={"res": a.res, "dem_only": a.dem_only, "grid": grid})
    print(df[["sfx", "ground_ppsm", "void_fraction", "dem_nan_share"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
