"""Build a 1 m CHM for the McKean 3x3 block e1423n2238.

DSM is rasterised from first returns (max-Z per cell) on the same 9 source
LAZ tiles used for the block's DEM; CHM = DSM - DEM, clamped at 0.

Outputs (alongside the existing dem/hillshade):
  dsm_e1423n2238_1m.tif   float32   first-return surface
  chm_e1423n2238_1m.tif   float32   canopy height (m), 0 where no canopy
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT, make_profile, run_pdal

KEY = "e1423n2238"
RES = 1.0
SRC_CRS = "EPSG:6350"  # NAD83(2011) Conus Albers (m), matches the LAZ
WORK = DERIV / "mosaic_3x3_mckean" / KEY
SRC_DIR = ROOT / "data" / "mckean"

DEM_PATH = WORK / f"dem_{KEY}_1m.tif"
DSM_PATH = WORK / f"dsm_{KEY}_1m.tif"
CHM_PATH = WORK / f"chm_{KEY}_1m.tif"


def source_tiles() -> list[Path]:
    e0, n0 = 1423, 2238
    paths = []
    for de in range(3):
        for dn in range(3):
            p = SRC_DIR / f"USGS_LPC_PA_Northcentral_2019_B19_e{e0+de}n{n0+dn}.laz"
            if not p.exists():
                raise FileNotFoundError(p)
            paths.append(p)
    return paths


def main() -> int:
    if not DEM_PATH.exists():
        print(f"missing DEM: {DEM_PATH}", file=sys.stderr)
        return 1
    with rasterio.open(DEM_PATH) as r:
        dem = r.read(1).astype(np.float32)
        nodata = r.nodata
        H, W = r.height, r.width
        transform = r.transform
        crs = r.crs
        left, top = transform.c, transform.f
        bottom = top - H * RES
    print(f"DEM grid: {W}x{H}  origin=({left:.1f},{bottom:.1f})..({left+W*RES:.1f},{top:.1f})  crs={crs}")

    # DSM via writers.gdal output_type=max (first-return max-Z per cell).
    stages = [
        *[str(p) for p in source_tiles()],
        {"type": "filters.merge"},
        {"type": "filters.range", "limits": "ReturnNumber[1:1]"},
        {"type": "filters.reprojection", "in_srs": SRC_CRS, "out_srs": DST_CRS},
        {"type": "writers.gdal",
         "filename": str(DSM_PATH),
         "resolution": RES,
         "output_type": "max",
         "data_type": "float32",
         "origin_x": left,
         "origin_y": bottom,
         "width": W,
         "height": H,
         "nodata": -9999.0},
    ]
    print(f"rasterising DSM ({W}x{H}) from 9 LAZ ...")
    run_pdal(stages, label=f"dsm_{KEY}", tmp_dir=WORK, timeout=3600)
    if not DSM_PATH.exists():
        print("DSM not written", file=sys.stderr)
        return 2

    with rasterio.open(DSM_PATH) as r:
        dsm = r.read(1).astype(np.float32)
        dsm_nd = r.nodata

    bad_dem = (dem == nodata) if nodata is not None else ~np.isfinite(dem)
    bad_dsm = (dsm == dsm_nd) if dsm_nd is not None else ~np.isfinite(dsm)
    chm = np.where(bad_dem | bad_dsm, np.nan, dsm - dem)
    chm = np.where(np.isfinite(chm), np.maximum(chm, 0.0), np.nan).astype(np.float32)

    profile = make_profile(width=W, height=H, transform=transform, crs=crs,
                           dtype="float32", nodata=np.nan, bigtiff=False)
    with rasterio.open(CHM_PATH, "w", **profile) as ds:
        ds.write(chm, 1)

    finite = np.isfinite(chm)
    print(f"CHM stats: finite={finite.mean()*100:.1f}%  "
          f"min={np.nanmin(chm):.2f}  p50={np.nanmedian(chm):.2f}  "
          f"p95={np.nanpercentile(chm, 95):.2f}  max={np.nanmax(chm):.2f}")
    print(f"wrote {CHM_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
