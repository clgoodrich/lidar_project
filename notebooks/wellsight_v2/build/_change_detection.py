"""DEM-of-Difference (DoD) change detection between two MDV lidar epochs.

Implements the core of Barlow (2026) Ch7 at first order: co-register two DEMs onto a
common grid, difference them (new - old), estimate robust uncertainty on stable terrain
(median bias + NMAD), apply a Level-of-Detection threshold (LOD95 = 1.96 * NMAD), and
report erosion/deposition volumes.

Co-registration here is a vertical-bias removal (subtract the stable-terrain median);
Barlow uses full point-to-plane ICP (x/y/z) for sub-pixel alignment — a later refinement.

  python _change_detection.py --bbox 26000 37000 33000 44000   # Von Guerard pilot
"""
from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import rasterio

BARLOW = Path("J:/barlow_data")
DEM2001_ZIP = BARLOW / "mdv_lidar_2001" / "Taylor_Glacier" / "taylore.zip"
DEM2014_DIR = BARLOW / "mdv_lidar" / "be_dem_1m" / "Taylor_Valley"
OUT = BARLOW / "change_detection" / "taylor_2001_2014"
CRS = "EPSG:3294"
RES = 2.0   # work at the coarser (2001) resolution


def _warp(src, dst, bbox, res, srcnodata=None):
    """Warp to the common grid. srcnodata MUST be set for the 2001 DEM — it fills with
    -9999 but doesn't *declare* it, so without this gdalwarp interpolates the fill across
    nodata edges and injects garbage (-9998.99, -5000 ...) into the difference."""
    x0, y0, x1, y1 = bbox
    cmd = ["gdalwarp", "-overwrite", "-t_srs", CRS, "-te", str(x0), str(y0),
           str(x1), str(y1), "-tr", str(res), str(res), "-r", "bilinear",
           "-dstnodata", "-9999"]
    if srcnodata is not None:
        cmd += ["-srcnodata", str(srcnodata)]
    cmd += [str(src), str(dst)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("XMIN", "YMIN", "XMAX", "YMAX"))
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    bbox = args.bbox

    # 2001: extract the ATM tile, warp to common grid
    ex = OUT / "_2001src"; ex.mkdir(exist_ok=True)
    zf = zipfile.ZipFile(DEM2001_ZIP)
    tif01 = [n for n in zf.namelist() if n.lower().endswith(".tif")][0]
    zf.extract(tif01, ex)
    d2001 = OUT / "dem2001_2m.tif"; _warp(ex / tif01, d2001, bbox, RES, srcnodata=-9999)
    # 2014: mosaic tiles -> warp to identical grid
    vrt = OUT / "_2014.vrt"
    subprocess.run(["gdalbuildvrt", str(vrt), *[str(t) for t in DEM2014_DIR.glob("*.tif")]],
                   check=True, capture_output=True, text=True)
    d2014 = OUT / "dem2014_2m.tif"; _warp(vrt, d2014, bbox, RES)

    a01 = rasterio.open(d2001); a14 = rasterio.open(d2014)
    z01 = a01.read(1).astype("float64"); z14 = a14.read(1).astype("float64")
    # plausible-elevation guard (belt-and-suspenders vs any residual nodata-edge artifact)
    ok = lambda z: (z > -500) & (z < 4000) & np.isfinite(z)
    valid = ok(z01) & ok(z14)
    dod = np.where(valid, z14 - z01, np.nan)

    d = dod[valid]
    med = np.median(d)                          # vertical co-registration bias
    nmad = 1.4826 * np.median(np.abs(d - med))  # robust spread on (mostly) stable terrain
    dod_c = dod - med                           # bias-corrected DoD
    lod = 1.96 * nmad
    dc = dod_c[valid]
    sig = np.abs(dc) > lod
    cell = RES * RES
    ero = -dc[(dc < -lod)].sum() * cell         # m^3 eroded (negative change)
    dep = dc[(dc > lod)].sum() * cell           # m^3 deposited

    print(f"== DoD 2014 - 2001  bbox={bbox}  ({RES} m) ==")
    print(f"  valid cells           : {valid.sum():,} ({100*valid.mean():.0f}% of window)")
    print(f"  vertical bias (median): {med:+.3f} m  (removed; ICP would refine x/y too)")
    print(f"  NMAD (stable spread)  : {nmad:.3f} m   -> LOD95 = {lod:.3f} m")
    print(f"  significant change    : {100*sig.mean():.1f}% of cells exceed LOD")
    print(f"  erosion volume        : {ero:,.0f} m^3")
    print(f"  deposition volume     : {dep:,.0f} m^3")
    print(f"  net (dep - ero)       : {dep-ero:,.0f} m^3")

    prof = a14.profile; prof.update(dtype="float32", count=1, nodata=-9999,
                                    compress="lzw", tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(OUT / "dod_2001_2014.tif", "w", **prof) as ds:
        out = np.where(valid, dod_c, -9999).astype("float32"); ds.write(out, 1)
    print(f"  wrote {OUT/'dod_2001_2014.tif'}")
    import shutil; shutil.rmtree(ex, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
