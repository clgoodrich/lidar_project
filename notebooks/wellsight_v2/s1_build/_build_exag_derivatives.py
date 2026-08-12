"""Vertically-exaggerated openness + slope from an existing DEM (annotation aid).

For MANUAL picking only: openness and slope are nonlinear in elevation (atan-based),
so a vertical exaggeration genuinely sharpens incised/concave linear features
(roads, drainage) for the eye. (LRM/TPI are linear -> exaggeration is inert there,
so they are intentionally NOT produced here; tune their color stretch instead.)

Each grid is processed at its OWN cell size (read from the DEM): 9t = 0.5 m,
permian = 1 m. The openness search radius is held fixed in METRES (default 25 m),
so L_cells adapts to resolution.

Outputs (to --out):
  openness_pos_<sfx>_z<Z>.tif
  openness_neg_<sfx>_z<Z>.tif
  slope_<sfx>_z<Z>.tif        (WBT slope with zfactor=Z)

CLI:
  python notebooks/wellsight_v2/s1_build/_build_exag_derivatives.py \
      --dem data/derivatives/tiles/9t/dem_9t_05.tif --sfx 9t_05 \
      --out data/derivatives/tiles/9t/exag3x --z 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import ROOT, read_tif, write_tif          # noqa: E402
from _build_derivatives import openness                 # type: ignore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True, help="input DEM tif")
    ap.add_argument("--out", required=True, help="output dir")
    ap.add_argument("--sfx", required=True, help="name suffix, e.g. 9t_05 or permian_01_1m")
    ap.add_argument("--z", type=float, default=3.0, help="vertical exaggeration factor")
    ap.add_argument("--radius", type=float, default=25.0, help="openness search radius (m)")
    args = ap.parse_args()

    dem_path = (ROOT / args.dem) if not Path(args.dem).is_absolute() else Path(args.dem)
    out_dir = (ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    zf = args.z; zt = f"z{zf:g}"

    with rasterio.open(dem_path) as r:
        res = abs(r.transform.a); tf = r.transform; crs = r.crs
    dem = read_tif(dem_path)
    L = max(int(round(args.radius / res)), 1)
    print(f"== exag {zt}  {args.sfx}  res={res:g} m  openness L={L} cells ({args.radius:g} m) ==")

    # openness from exaggerated relief (nonlinear -> exaggeration matters)
    op_pos, op_neg = openness(dem * zf, L_cells=L, cellsize=res)
    write_tif(out_dir / f"openness_pos_{args.sfx}_{zt}.tif", op_pos, transform=tf, crs=crs)
    write_tif(out_dir / f"openness_neg_{args.sfx}_{zt}.tif", op_neg, transform=tf, crs=crs)
    print(f"  wrote openness_pos/neg ({zt})")

    # slope with WBT zfactor (== slope of the exaggerated surface)
    import whitebox
    wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
    rc = wbt.slope(dem=str(dem_path.resolve()),
                   output=str((out_dir / f"slope_{args.sfx}_{zt}.tif").resolve()),
                   zfactor=zf, units="degrees")
    print(f"  slope {zt}: {'ok' if rc == 0 else 'FAILED rc=%d' % rc}")
    print(f"DONE -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
