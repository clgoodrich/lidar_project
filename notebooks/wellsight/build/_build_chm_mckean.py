"""Build 1 m CHM for any McKean 3x3 block (one or all).

CHM = DSM(first-return max-Z) - DEM, clamped at 0. Uses the existing per-block
DEM as the grid template, and rasterises the DSM from the same 9 source LAZ
tiles in data/source_laz/mckean/ (NAD83(2011) Conus Albers -> UTM 17N inside PDAL).

CLI:
  python notebooks/wellsight/build/_build_chm_mckean.py           # all 4 blocks
  python notebooks/wellsight/build/_build_chm_mckean.py --key e1423n2238
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT, make_profile, run_pdal

RES = 1.0
SRC_CRS = "EPSG:6350"
ROOT_OUT = DERIV / "tiles" / "mosaic_3x3_mckean"
SRC_DIR = ROOT / "data" / "source_laz" / "mckean"
KEY_RE = re.compile(r"^e(\d{4})n(\d{4})$")


def source_tiles(key: str) -> list[Path]:
    m = KEY_RE.match(key)
    if not m:
        raise ValueError(f"bad key: {key}")
    e0, n0 = int(m.group(1)), int(m.group(2))
    paths = []
    for de in range(3):
        for dn in range(3):
            p = SRC_DIR / f"USGS_LPC_PA_Northcentral_2019_B19_e{e0+de}n{n0+dn}.laz"
            if not p.exists():
                raise FileNotFoundError(p)
            paths.append(p)
    return paths


def build_one(key: str, *, skip_existing: bool = True) -> None:
    work = ROOT_OUT / key
    dem_path = work / f"dem_{key}_1m.tif"
    dsm_path = work / f"dsm_{key}_1m.tif"
    chm_path = work / f"chm_{key}_1m.tif"
    if not dem_path.exists():
        print(f"[{key}] missing DEM: {dem_path}", file=sys.stderr)
        return
    if skip_existing and chm_path.exists():
        print(f"[{key}] skip (CHM exists)")
        return

    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        nodata = r.nodata
        H, W = r.height, r.width
        transform = r.transform
        crs = r.crs
        left, top = transform.c, transform.f
        bottom = top - H * RES

    stages = [
        *[str(p) for p in source_tiles(key)],
        {"type": "filters.merge"},
        {"type": "filters.range", "limits": "ReturnNumber[1:1]"},
        {"type": "filters.reprojection", "in_srs": SRC_CRS, "out_srs": DST_CRS},
        {"type": "writers.gdal",
         "filename": str(dsm_path),
         "resolution": RES, "output_type": "max", "data_type": "float32",
         "origin_x": left, "origin_y": bottom, "width": W, "height": H,
         "nodata": -9999.0},
    ]
    print(f"[{key}] DSM ({W}x{H}) ...")
    run_pdal(stages, label=f"dsm_{key}", tmp_dir=work, timeout=3600)

    with rasterio.open(dsm_path) as r:
        dsm = r.read(1).astype(np.float32)
        dsm_nd = r.nodata

    bad_dem = (dem == nodata) if nodata is not None else ~np.isfinite(dem)
    bad_dsm = (dsm == dsm_nd) if dsm_nd is not None else ~np.isfinite(dsm)
    chm = np.where(bad_dem | bad_dsm, np.nan, dsm - dem)
    chm = np.where(np.isfinite(chm), np.maximum(chm, 0.0), np.nan).astype(np.float32)

    profile = make_profile(width=W, height=H, transform=transform, crs=crs,
                           dtype="float32", nodata=np.nan, bigtiff=False)
    with rasterio.open(chm_path, "w", **profile) as ds:
        ds.write(chm, 1)
    finite = np.isfinite(chm)
    print(f"[{key}] CHM finite={finite.mean()*100:.1f}%  "
          f"p50={np.nanmedian(chm):.2f}  p95={np.nanpercentile(chm,95):.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", help="single block key (e.g. e1423n2238)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.key:
        keys = [args.key]
    else:
        keys = sorted(p.name for p in ROOT_OUT.iterdir()
                      if p.is_dir() and KEY_RE.match(p.name))
    for k in keys:
        build_one(k, skip_existing=not args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
