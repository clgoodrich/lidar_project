"""Generate elevation contours from each per-block DEM in a data_3x3 region.

Runs the GDAL `gdal_contour` CLI (PDAL/GDAL toolchain, per CLAUDE.md) on every
`dem_<key>_1m.tif` and writes `contours_<int>m_<key>_1m.gpkg` (layer `contours`,
attribute `elev`) alongside it.

DEMs are EPSG:6346 (UTM 17N, metres), so --interval is in metres.

Outputs are heavy regenerable vectors (~37 MB/block at 2 m) -> gitignored via
`data/derivatives/data_3x3/**/contours_*.gpkg` (added with this script).

CLI:
  python notebooks/wellsight/build/_build_contours_data_3x3.py                 # all blocks, 2 m
  python notebooks/wellsight/build/_build_contours_data_3x3.py --interval 5
  python notebooks/wellsight/build/_build_contours_data_3x3.py --only 613590
  python notebooks/wellsight/build/_build_contours_data_3x3.py --overwrite
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV  # noqa: E402

GDAL_CONTOUR = shutil.which("gdal_contour") or "gdal_contour"


def block_dems(region: str):
    root = DERIV / "data_3x3" / region
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        dem = d / f"dem_{d.name}_1m.tif"
        if dem.exists():
            out.append((d.name, dem))
    return out


def build_one(key: str, dem: Path, interval: float, *, overwrite: bool) -> dict:
    out = dem.parent / f"contours_{interval:g}m_{key}_1m.gpkg"
    if out.exists() and not overwrite:
        print(f"  [{key}] skip (exists)")
        return {"key": key, "skipped": True}
    if out.exists():
        out.unlink()
    with rasterio.open(dem) as r:
        nodata = r.nodata
    cmd = [GDAL_CONTOUR, "-a", "elev", "-i", str(interval)]
    if nodata is not None:
        cmd += ["-snodata", str(nodata)]
    cmd += ["-nln", "contours", str(dem), str(out)]
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    dt = time.time() - t0
    if res.returncode != 0:
        print(f"  [{key}] FAILED rc={res.returncode}: {res.stderr[-300:]}")
        return {"key": key, "ok": False}
    size_mb = out.stat().st_size / 1e6
    print(f"  [{key}] {out.name}  ({size_mb:.1f} MB, {dt:.1f}s)")
    return {"key": key, "ok": True, "mb": size_mb}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="westernpa_d20")
    ap.add_argument("--interval", type=float, default=2.0, help="metres")
    ap.add_argument("--only", help="single block key")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    dems = block_dems(args.region)
    if args.only:
        dems = [(k, p) for k, p in dems if k == args.only]
        if not dems:
            print(f"no block {args.only}", file=sys.stderr); return 1
    print(f"contours: interval={args.interval:g} m on {len(dems)} DEM(s) "
          f"in {args.region}")
    t0 = time.time()
    rows = [build_one(k, p, args.interval, overwrite=args.overwrite) for k, p in dems]
    ok = [r for r in rows if r.get("ok")]
    print(f"\nDONE {len(ok)}/{len(dems)} built in {(time.time()-t0)/60:.1f} min"
          + (f"  ({sum(r['mb'] for r in ok):.0f} MB total)" if ok else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
