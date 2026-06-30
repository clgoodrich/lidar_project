"""DEM-of-Difference (DoD) change detection between MDV elevation epochs.

Implements the core of Barlow (2026) Ch7: co-register two DEMs onto a common grid,
difference them (new - old), estimate robust uncertainty on stable terrain
(median bias + NMAD), apply a Level-of-Detection threshold (LOD95 = 1.96 * NMAD), report
erosion/deposition volumes, and (optionally) per-stream rates inside the LTER channels.

Epochs (--old / --new): 2001 (ATM 2m lidar) | 2014 (NCALM lidar) | rema (REMA 2021-23
satellite, EPSG:3031 -> reprojected). Co-registration: vertical-bias by default; --icp adds
PDAL point-cloud ICP (helps where there is 3-D relief; on flat floor stick with bias only).

  python _change_detection.py --bbox 24000 43500 26500 46000 --icp        # 2001->2014, ICP
  python _change_detection.py --old 2014 --new rema --bbox 26000 37000 33000 44000
  python _change_detection.py --bbox 26000 37000 33000 44000 --streams     # per-stream rates
"""
from __future__ import annotations

import argparse
import csv
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
REMA_DIR = BARLOW / "rema" / "2m"
STREAM_DIR = BARLOW / "labels" / "gis" / "mcmlter-gis-watershed-shapefiles" / "MDV_streams"
CRS = "EPSG:3294"
RES = 2.0
# representative acquisition year per epoch (for converting volumes to rates)
EPOCH_YEAR = {"2001": 2001.9, "2014": 2015.0, "rema": 2022.0}


def _warp(src, dst, bbox, res, srcnodata=None):
    """Warp to the common grid + CRS. srcnodata MUST be set for the 2001 DEM — it fills
    with -9999 but doesn't *declare* it, so without this gdalwarp bilinear-interpolates the
    fill across nodata edges and injects garbage (-9998.99, -5000 ...) into the difference."""
    x0, y0, x1, y1 = bbox
    cmd = ["gdalwarp", "-overwrite", "-t_srs", CRS, "-te", str(x0), str(y0), str(x1),
           str(y1), "-tr", str(res), str(res), "-r", "bilinear", "-dstnodata", "-9999"]
    if srcnodata is not None:
        cmd += ["-srcnodata", str(srcnodata)]
    subprocess.run([*cmd, str(src), str(dst)], check=True, capture_output=True, text=True)


def prep_dem(name, bbox, out):
    """Materialize one epoch's DEM warped onto the common grid. Returns the .tif path."""
    dst = out / f"dem_{name}_2m.tif"
    if name == "2001":
        ex = out / "_2001src"; ex.mkdir(exist_ok=True)
        zf = zipfile.ZipFile(DEM2001_ZIP)
        tif = [n for n in zf.namelist() if n.lower().endswith(".tif")][0]
        zf.extract(tif, ex)
        _warp(ex / tif, dst, bbox, RES, srcnodata=-9999)
    elif name in ("2014", "rema"):
        src_dir = DEM2014_DIR if name == "2014" else REMA_DIR
        vrt = out / f"_{name}.vrt"
        subprocess.run(["gdalbuildvrt", str(vrt), *[str(t) for t in src_dir.glob("*.tif")]],
                       check=True, capture_output=True, text=True)
        _warp(vrt, dst, bbox, RES)
    else:
        raise ValueError(f"unknown epoch {name}")
    return dst


def _dod(z_new, z_old):
    """Bias-corrected DoD + robust stats. Returns (dod_corrected, valid, dict)."""
    ok = lambda z: (z > -500) & (z < 4000) & np.isfinite(z)
    valid = ok(z_old) & ok(z_new)
    dod = np.where(valid, z_new - z_old, np.nan)
    d = dod[valid]
    med = np.median(d)
    nmad = 1.4826 * np.median(np.abs(d - med))
    dod_c = dod - med
    lod = 1.96 * nmad
    dc = dod_c[valid]
    cell = RES * RES
    return dod_c, valid, {
        "validpct": 100 * valid.mean(), "bias": med, "nmad": nmad, "lod": lod,
        "sigpct": 100 * (np.abs(dc) > lod).mean(),
        "erosion": -dc[dc < -lod].sum() * cell, "deposition": dc[dc > lod].sum() * cell}


def _report(tag, s):
    print(f"  [{tag}] valid {s['validpct']:.0f}%  bias {s['bias']:+.3f}m  "
          f"NMAD {s['nmad']:.3f}m  LOD95 {s['lod']:.3f}m  sig {s['sigpct']:.1f}%  "
          f"ero {s['erosion']:,.0f}  dep {s['deposition']:,.0f} m^3")


def icp_coregister(d_old, d_new, out_dir, voxel=6.0):
    """PDAL filters.icp (same approach as WellSight _icp_old_vs_new): rasterize both DEMs to
    points, voxel-sample, ICP (fixed=new, moving=old) for the transform, apply it to the
    full-res OLD DEM, re-grid onto the NEW grid. Returns (new_old_tif, icp_meta)."""
    rng = {"type": "filters.range", "limits": "Z[-500:4000]"}
    vox = {"type": "filters.voxelcenternearestneighbor", "cell": voxel}
    meta_path = run_pdal([
        {"type": "readers.gdal", "filename": str(d_new), "header": "Z", "tag": "f0"},
        {**rng, "inputs": ["f0"], "tag": "f1"}, {**vox, "inputs": ["f1"], "tag": "fixed"},
        {"type": "readers.gdal", "filename": str(d_old), "header": "Z", "tag": "m0"},
        {**rng, "inputs": ["m0"], "tag": "m1"}, {**vox, "inputs": ["m1"], "tag": "moving"},
        {"type": "filters.icp", "inputs": ["fixed", "moving"]},
        {"type": "writers.las", "filename": str(out_dir / "_icp_aligned.las"),
         "minor_version": 4, "dataformat_id": 6, "a_srs": CRS},
    ], label="barlow_icp", tmp_dir=out_dir, capture_meta=True, timeout=3600)
    icp = json.loads(meta_path.read_text()).get("stages", {}).get("filters.icp", {})
    mat = icp.get("composed") or icp.get("transform")
    mat_str = (" ".join(str(x) for x in np.array(mat).flatten())
               if isinstance(mat, list) else " ".join(str(mat).split()))
    with rasterio.open(d_new) as r:
        b = r.bounds; W, H = r.width, r.height
    out_tif = out_dir / "dem_old_icp_2m.tif"
    run_pdal([
        {"type": "readers.gdal", "filename": str(d_old), "header": "Z"},
        {"type": "filters.range", "limits": "Z[-500:4000]"},
        {"type": "filters.transformation", "matrix": mat_str},
        {"type": "writers.gdal", "filename": str(out_tif), "dimension": "Z",
         "output_type": "mean", "resolution": RES, "origin_x": b.left, "origin_y": b.bottom,
         "width": W, "height": H, "override_srs": CRS, "data_type": "float32", "nodata": -9999},
    ], label="barlow_icp_apply", tmp_dir=out_dir, timeout=3600)
    return out_tif, icp


def per_stream(dod_c, valid, ref_tif, lod, years, out_csv):
    """Per-stream erosion/deposition/net rates inside the LTER channel polygons.
    Channels are WGS84 polar-stereographic (lat0 -71) -> reproject to EPSG:3294."""
    import geopandas as gpd
    from rasterio.features import rasterize
    with rasterio.open(ref_tif) as r:
        transform, shape = r.transform, (r.height, r.width)
    cell = RES * RES
    rows = []
    for shp in sorted(STREAM_DIR.glob("*_channel.shp")):
        name = shp.stem.replace("_stream_channel", "").replace("_channel", "")
        g = gpd.read_file(shp).to_crs(CRS)
        m = rasterize([(geom, 1) for geom in g.geometry], out_shape=shape,
                      transform=transform, fill=0).astype(bool) & valid
        if m.sum() == 0:
            continue
        dc = dod_c[m]
        ero = -dc[dc < -lod].sum() * cell
        dep = dc[dc > lod].sum() * cell
        area = m.sum() * cell
        rows.append({"stream": name, "area_m2": round(area),
                     "erosion_m3": round(ero), "deposition_m3": round(dep),
                     "net_m3": round(dep - ero), "gross_m3": round(ero + dep),
                     "net_rate_m3_yr": round((dep - ero) / years, 1),
                     "gross_rate_m3_yr": round((ero + dep) / years, 1)})
    if not rows:
        print("  no stream channels intersect this window"); return
    rows.sort(key=lambda r: -r["gross_m3"])
    print(f"  per-stream ({years:.0f} yr, inside LTER channels):")
    print(f"    {'stream':16s} {'area_m2':>9s} {'gross/yr':>10s} {'net/yr':>10s}")
    for r in rows:
        print(f"    {r['stream']:16s} {r['area_m2']:>9,} {r['gross_rate_m3_yr']:>10,.0f} "
              f"{r['net_rate_m3_yr']:>+10,.0f}")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"  wrote {out_csv}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("XMIN", "YMIN", "XMAX", "YMAX"))
    ap.add_argument("--old", default="2001", choices=["2001", "2014", "rema"])
    ap.add_argument("--new", default="2014", choices=["2001", "2014", "rema"])
    ap.add_argument("--icp", action="store_true", help="add PDAL point-cloud ICP co-registration")
    ap.add_argument("--streams", action="store_true", help="per-stream rates inside LTER channels")
    args = ap.parse_args()
    OUT = BARLOW / "change_detection" / f"taylor_{args.old}_{args.new}"
    OUT.mkdir(parents=True, exist_ok=True)
    years = EPOCH_YEAR[args.new] - EPOCH_YEAR[args.old]
    print(f"== DoD {args.new} - {args.old}  bbox={args.bbox}  ({RES} m, {years:.0f} yr) ==")

    d_old = prep_dem(args.old, args.bbox, OUT)
    d_new = prep_dem(args.new, args.bbox, OUT)
    z_new = rasterio.open(d_new).read(1).astype("float64")

    dod_c, valid, s = _dod(z_new, rasterio.open(d_old).read(1).astype("float64"))
    _report("vertical-bias", s); stats = s
    out_dod = OUT / f"dod_{args.old}_{args.new}.tif"

    if args.icp:
        d_old_icp, icp = icp_coregister(d_old, d_new, OUT)
        # 'fitness' = PDAL/PCL ICP registration score = mean squared distance between
        # corresponding points after alignment (m^2; LOWER = tighter fit). It measures how
        # well the two clouds match, NOT whether change-detection improved -> we also
        # compare gridded-DoD NMAD before/after, which is the decision metric.
        fit = icp.get("fitness")
        print(f"  ICP converged={icp.get('converged')}  "
              f"fitness={fit:.3f} m^2 (mean sq correspondence dist; lower=better)")
        dod_c, valid, s2 = _dod(z_new, rasterio.open(d_old_icp).read(1).astype("float64"))
        _report("after-ICP   ", s2)
        print(f"  -> ICP NMAD {s2['nmad']:.3f} vs {s['nmad']:.3f} m  "
              f"({'lower (better)' if s2['nmad'] < s['nmad'] else 'NOT lower'})")
        stats = s2; out_dod = OUT / f"dod_{args.old}_{args.new}_icp.tif"

    if args.streams:
        per_stream(dod_c, valid, d_new, stats["lod"], years,
                   OUT / f"per_stream_{args.old}_{args.new}.csv")

    prof = rasterio.open(d_new).profile
    prof.update(dtype="float32", count=1, nodata=-9999, compress="lzw",
                tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(out_dod, "w", **prof) as ds:
        ds.write(np.where(valid, dod_c, -9999).astype("float32"), 1)
    print(f"  wrote {out_dod}")
    import shutil; shutil.rmtree(OUT / "_2001src", ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
