"""S9a (3.4). Relief-normalised channels for the A1 adaptation arm.

Purpose
    Per 375 m block, deterministic and label-free. Fit a least-squares plane to the 0.5 m DEM in the
    block, remove it, and divide by the block's robust relief (p95 - p5 of the residual, floored).
    Elevation-unit channels of the 9t stack (lrm_25, lrm_5, tpi_05) are divided by the same relief.
    Slope, openness and roughness are left as they are. Normalisation statistics for the adapted model
    are fitted later on adaptation windows only (S9b), never here.
Inputs
    data/<area>/derived/05/dem_<area>_05.tif and features_<area>_05.tif (core 'derive')
    data/<area>/results/transfer/xfer_blocks_roles_<area>.gpkg
Outputs
    data/<area>/derived/05/features_reliefnorm_<area>_05.tif   (8 bands, 9t order plus elev_rn)
    data/<area>/derived/05/relief_by_block_<area>.csv
Run
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_relief_norm_channels.py --area ar_ouachita
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.4"
ELEV_BANDS = (0, 1, 3)        # lrm_25, lrm_5, tpi_05 in the 9t channel order
RELIEF_FLOOR_M = 0.25


def plane_residual(z: np.ndarray) -> np.ndarray:
    """z minus its least-squares plane (NaN ignored)."""
    h, w = z.shape
    yy, xx = np.mgrid[0:h, 0:w]
    m = np.isfinite(z)
    if m.sum() < 3:
        return np.full_like(z, np.nan)
    A = np.c_[xx[m], yy[m], np.ones(m.sum())]
    coef, *_ = np.linalg.lstsq(A, z[m], rcond=None)
    return z - (coef[0] * xx + coef[1] * yy + coef[2])


def robust_relief(r: np.ndarray, floor: float = RELIEF_FLOOR_M) -> float:
    v = r[np.isfinite(r)]
    if v.size == 0:
        return float("nan")
    lo, hi = np.percentile(v, [5, 95])
    return max(float(hi - lo), floor)


def normalise_block(dem: np.ndarray, feats: np.ndarray) -> tuple[np.ndarray, float]:
    """Returns (8 x H x W array, relief). Band 8 is the plane-removed elevation over relief."""
    res = plane_residual(dem)
    rel = robust_relief(res)
    out = np.concatenate([feats.astype(np.float32), (res / rel)[None].astype(np.float32)], axis=0)
    for b in ELEV_BANDS:
        out[b] = out[b] / rel
    return out, rel


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    a = ap.parse_args(argv)
    import geopandas as gpd
    import rasterio
    from rasterio.windows import from_bounds
    d05 = ek.area_dir(a.area) / "derived" / "05"
    try:
        dem_p = gt.require_input(d05 / f"dem_{a.area}_05.tif", "0.5 m DEM")
        fea_p = gt.require_input(d05 / f"features_{a.area}_05.tif", "7-band 0.5 m feature stack (9t order)")
        blocks = gpd.read_file(gt.require_input(gt.area_transfer_dir(a.area) / f"xfer_blocks_roles_{a.area}.gpkg",
                                                "block roles"))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    out_p = d05 / f"features_reliefnorm_{a.area}_05.tif"
    rows = []
    with rasterio.open(dem_p) as rd, rasterio.open(fea_p) as rf:
        ek.assert_crs(rd, blocks.crs)
        ek.assert_crs(rf, blocks.crs)
        if rd.transform != rf.transform or rd.shape != rf.shape:
            raise AssertionError("DEM and feature stack grids differ")
        prof = rf.profile.copy()
        prof.update(count=rf.count + 1, dtype="float32", nodata=np.nan, BIGTIFF="YES")
        with rasterio.open(out_p, "w", **prof) as dst:
            for _, b in blocks.iterrows():
                win = from_bounds(*b.geometry.bounds, rd.transform).round_offsets().round_lengths()
                z = rd.read(1, window=win).astype(np.float32)
                if rd.nodata is not None:
                    z[z == rd.nodata] = np.nan
                arr, rel = normalise_block(z, rf.read(window=win))
                dst.write(arr, window=win)
                rows.append({"block_id": b.block_id, "relief_m": rel})
    rp = d05 / f"relief_by_block_{a.area}.csv"
    pd.DataFrame(rows).to_csv(rp, index=False)
    ek.write_provenance(d05, inputs=[dem_p, fea_p], outputs=[out_p, rp], params={"relief_floor_m": RELIEF_FLOOR_M})
    print(f"wrote {out_p}\nwrote {rp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
