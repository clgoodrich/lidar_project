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
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "notebooks" / "wellsight_v2"))
from _common import run_pdal  # noqa: E402  (shared PDAL CLI helper, used for filters.icp)

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


def _dod(z14, z01):
    """Bias-corrected DoD + robust stats. Returns (dod_corrected, valid, dict)."""
    ok = lambda z: (z > -500) & (z < 4000) & np.isfinite(z)
    valid = ok(z01) & ok(z14)
    dod = np.where(valid, z14 - z01, np.nan)
    d = dod[valid]
    med = np.median(d)
    nmad = 1.4826 * np.median(np.abs(d - med))
    dod_c = dod - med
    lod = 1.96 * nmad
    dc = dod_c[valid]
    cell = RES * RES
    return dod_c, valid, {
        "valid": int(valid.sum()), "validpct": 100 * valid.mean(),
        "bias": med, "nmad": nmad, "lod": lod,
        "sigpct": 100 * (np.abs(dc) > lod).mean(),
        "erosion": -dc[dc < -lod].sum() * cell, "deposition": dc[dc > lod].sum() * cell}


def _report(tag, s):
    print(f"  [{tag}] valid {s['validpct']:.0f}%  bias {s['bias']:+.3f}m  "
          f"NMAD {s['nmad']:.3f}m  LOD95 {s['lod']:.3f}m  sig {s['sigpct']:.1f}%  "
          f"ero {s['erosion']:,.0f}  dep {s['deposition']:,.0f} m^3")


def icp_coregister(d2001, d2014, out_dir, voxel=6.0):
    """PDAL filters.icp (same approach as WellSight _icp_old_vs_new): rasterize both
    DEMs to points, voxel-sample, ICP (fixed=2014, moving=2001) for the transform, then
    apply it to the full-res 2001 DEM and re-grid onto the 2014 grid. Returns the new
    2001 path + the ICP metadata (transform/fitness)."""
    rng = {"type": "filters.range", "limits": "Z[-500:4000]"}
    vox = {"type": "filters.voxelcenternearestneighbor", "cell": voxel}
    aligned = out_dir / "_icp_aligned.las"
    meta_path = run_pdal([
        {"type": "readers.gdal", "filename": str(d2014), "header": "Z", "tag": "f0"},
        {**rng, "inputs": ["f0"], "tag": "f1"}, {**vox, "inputs": ["f1"], "tag": "fixed"},
        {"type": "readers.gdal", "filename": str(d2001), "header": "Z", "tag": "m0"},
        {**rng, "inputs": ["m0"], "tag": "m1"}, {**vox, "inputs": ["m1"], "tag": "moving"},
        {"type": "filters.icp", "inputs": ["fixed", "moving"]},
        {"type": "writers.las", "filename": str(aligned), "minor_version": 4,
         "dataformat_id": 6, "a_srs": CRS},
    ], label="barlow_icp", tmp_dir=out_dir, capture_meta=True, timeout=3600)
    icp = json.loads(meta_path.read_text()).get("stages", {}).get("filters.icp", {})
    mat = icp.get("composed") or icp.get("transform")
    mat_str = (" ".join(str(x) for x in np.array(mat).flatten())
               if isinstance(mat, list) else " ".join(str(mat).split()))
    # apply transform to the FULL-res 2001 DEM, re-grid to the 2014 grid
    with rasterio.open(d2014) as r:
        b = r.bounds; W, H = r.width, r.height
    out_tif = out_dir / "dem2001_icp_2m.tif"
    run_pdal([
        {"type": "readers.gdal", "filename": str(d2001), "header": "Z"},
        {"type": "filters.range", "limits": "Z[-500:4000]"},
        {"type": "filters.transformation", "matrix": mat_str},
        {"type": "writers.gdal", "filename": str(out_tif), "dimension": "Z",
         "output_type": "mean", "resolution": RES, "origin_x": b.left, "origin_y": b.bottom,
         "width": W, "height": H, "override_srs": CRS, "data_type": "float32", "nodata": -9999},
    ], label="barlow_icp_apply", tmp_dir=out_dir, timeout=3600)
    return out_tif, icp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("XMIN", "YMIN", "XMAX", "YMAX"))
    ap.add_argument("--icp", action="store_true",
                    help="add point-cloud ICP fine co-registration (PDAL filters.icp)")
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

    a14 = rasterio.open(d2014); z14 = a14.read(1).astype("float64")
    print(f"== DoD 2014 - 2001  bbox={bbox}  ({RES} m) ==")

    # baseline: vertical-bias co-registration only
    z01 = rasterio.open(d2001).read(1).astype("float64")
    dod_c, valid, s = _dod(z14, z01); _report("vertical-bias", s)
    out_dod = OUT / "dod_2001_2014.tif"

    if args.icp:
        d2001_icp, icp = icp_coregister(d2001, d2014, OUT)
        print(f"  ICP converged={icp.get('converged')} fitness={icp.get('fitness')}")
        z01i = rasterio.open(d2001_icp).read(1).astype("float64")
        dod_c, valid, s2 = _dod(z14, z01i); _report("after-ICP   ", s2)
        better = "lower (better)" if s2["nmad"] < s["nmad"] else "NOT lower"
        print(f"  -> ICP NMAD {s2['nmad']:.3f} vs {s['nmad']:.3f} m  ({better})")
        out_dod = OUT / "dod_2001_2014_icp.tif"

    prof = a14.profile; prof.update(dtype="float32", count=1, nodata=-9999,
                                    compress="lzw", tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(out_dod, "w", **prof) as ds:
        ds.write(np.where(valid, dod_c, -9999).astype("float32"), 1)
    print(f"  wrote {out_dod}")
    import shutil; shutil.rmtree(ex, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
