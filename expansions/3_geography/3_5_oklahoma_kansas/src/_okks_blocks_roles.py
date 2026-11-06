"""S5 (3.5). Blocks and roles per window, stratified by slope tercile, and the common footprint.

Purpose
    Roles follow the window design. Train windows (Okmulgee, Creek, Washington) split their blocks into
    train and val by a seeded draw stratified by slope tercile. Test windows (Rogers, Nowata, and the
    Kansas joint contrast) are all test. Kay (or Pawnee) is the audit window, opened once.
    Slope terciles are cut on the pooled training-window block means so cut points never see test ground.
    The common footprint keeps blocks present in both modalities and inside the imagery date rule.
Inputs
    data/<area>/derived/05/slope_<area>_05.tif                  (core 'derive')
    data/<area>/results/modality/mod_coverage_dates_<area>.csv  (S0)
Outputs
    data/<area>/results/modality/mod_blocks_roles_<area>.gpkg   (block_id, role, slope_mean, slope_tercile,
        date_eligible, common_footprint, eligible)
Run
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_blocks_roles.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.5"


def block_means(raster: Path, blocks) -> np.ndarray:
    import rasterio
    from rasterio.windows import from_bounds
    out = []
    with rasterio.open(raster) as r:
        ek.assert_crs(r, blocks.crs)
        for geom in blocks.geometry:
            a = r.read(1, window=from_bounds(*geom.bounds, r.transform).round_offsets().round_lengths()).astype(float)
            if r.nodata is not None:
                a[a == r.nodata] = np.nan
            out.append(np.nanmean(a) if np.isfinite(a).any() else np.nan)
    return np.array(out)


def tercile_cuts(train_values: np.ndarray) -> list[float]:
    v = train_values[np.isfinite(train_values)]
    return list(np.percentile(v, [100 / 3, 200 / 3]))


def apply_terciles(values, cuts) -> list[str]:
    return ["unknown" if not np.isfinite(v) else ("low", "mid", "high")[int(np.searchsorted(cuts, v, "right"))]
            for v in values]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    per = {}
    try:
        for area, ac in cfg["areas"].items():
            b = gt._blocks_for_area(cfg, area, EXP)
            b["slope_mean"] = block_means(gt.require_input(ek.area_dir(area) / "derived" / "05" / f"slope_{area}_05.tif",
                                                           f"0.5 m slope for {area}", "core 'derive'"), b)
            per[area] = b
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    train_vals = np.concatenate([per[a]["slope_mean"].to_numpy() for a, c in cfg["areas"].items() if c["role"] == "train"])
    cuts = tercile_cuts(train_vals)
    for k, (area, ac) in enumerate(cfg["areas"].items()):
        b = per[area]
        b["slope_tercile"] = apply_terciles(b["slope_mean"], cuts)
        g = gt.assign_roles(b, ac["role_fractions"], ek.child_seed(int(pr["master_seed"]), k, 0),
                            float(pr["buffer_m"]), protect=("val", "test", "audit"), strata_col="slope_tercile")
        cov_p = ek.area_dir(area) / "results" / "modality" / f"mod_coverage_dates_{area}.csv"
        if cov_p.exists():
            cov = pd.read_csv(cov_p)[["block_id", "covered", "date_eligible"]]
            g = g.merge(cov, on="block_id", how="left")
        else:
            g["covered"], g["date_eligible"] = False, False
        g["common_footprint"] = g["covered"].fillna(False).astype(bool)
        g["eligible"] = ~g["edge"] & g["common_footprint"] & (g["role"] != "buffer")
        out = ek.area_dir(area) / "results" / "modality" / f"mod_blocks_roles_{area}.gpkg"
        out.parent.mkdir(parents=True, exist_ok=True)
        g.to_file(out, driver="GPKG")
        print(area, g["role"].value_counts().to_dict(), f"-> {out}")
    print(f"slope tercile cuts (training windows only) = {np.round(cuts, 2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
