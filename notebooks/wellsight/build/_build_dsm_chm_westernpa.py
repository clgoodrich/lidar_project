"""Build DSM + CHM for every WesternPA D20 3x3 block.

Northcentral B19 blocks already have DSM + CHM from
``_build_chm_mckean.py`` -- those are skipped automatically.

Per block:
  dsm_<key>_1m.tif   first-return max-Z on the same grid as dem_<key>_1m.tif
  chm_<key>_1m.tif   max(dsm - dem, 0)

Source LAZ:
  data/files/USGS_LPC_PA_WesternPA_2019_D20_17T<band><e><n>.laz
  (member-tile discovery delegated to _build_3x3_hillshades.enumerate_blocks)

CLI:
  python notebooks/wellsight/build/_build_dsm_chm_westernpa.py
  python notebooks/wellsight/build/_build_dsm_chm_westernpa.py --only 604590,609594
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DERIV, ROOT, make_profile, run_pdal
from _build_3x3_hillshades import discover_tiles, enumerate_blocks  # type: ignore

ROOT_3X3 = DERIV / "data_3x3" / "westernpa_d20"
RES = 1.0


def build_dsm_chm(key: str, out_dir: Path, members: list[Path], *,
                  skip_existing: bool = True) -> None:
    dem_path = out_dir / f"dem_{key}_1m.tif"
    dsm_path = out_dir / f"dsm_{key}_1m.tif"
    chm_path = out_dir / f"chm_{key}_1m.tif"
    if not dem_path.exists():
        print(f"[{key}] no DEM, skipping"); return
    if skip_existing and chm_path.exists() and dsm_path.exists():
        print(f"[{key}] DSM+CHM already present, skipping"); return

    with rasterio.open(dem_path) as r:
        dem = r.read(1).astype(np.float32)
        nodata = r.nodata
        H, W = r.height, r.width
        transform = r.transform
        crs = r.crs
        left, top = transform.c, transform.f
        bottom = top - H * RES

    # DSM via first-return max-Z, snapped to DEM grid.
    if not (dsm_path.exists() and skip_existing):
        stages = [
            *[str(p) for p in members],
            {"type": "filters.merge"},
            {"type": "filters.range", "limits": "ReturnNumber[1:1]"},
            {"type": "writers.gdal",
             "filename": str(dsm_path),
             "resolution": RES, "output_type": "max", "data_type": "float32",
             "origin_x": left, "origin_y": bottom, "width": W, "height": H,
             "nodata": -9999.0},
        ]
        print(f"[{key}] DSM ({W}x{H}) from 9 LAZ ...")
        run_pdal(stages, label=f"dsm_{key}", tmp_dir=out_dir, timeout=3600)

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
    ap.add_argument("--only", help="comma-separated block keys")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None

    tiles = discover_tiles()
    blocks = enumerate_blocks(tiles)
    keys = {b["key"]: list(b["members"]) for b in blocks}

    # Restrict to blocks that actually have a subdir on disk.
    todo = []
    for sub in sorted(p for p in ROOT_3X3.iterdir() if p.is_dir()):
        key = sub.name
        if only and key not in only:
            continue
        members = keys.get(key)
        if not members:
            print(f"[{key}] no member tiles from enumerator, skipping"); continue
        todo.append((key, sub, members))

    print(f"will process {len(todo)} block(s)")
    t0_all = time.time()
    for key, out_dir, members in todo:
        t0 = time.time()
        try:
            build_dsm_chm(key, out_dir, members, skip_existing=(not args.overwrite))
        except Exception as e:
            print(f"[{key}] FAILED: {e}")
            continue
        print(f"[{key}] elapsed {time.time()-t0:.1f}s")
    print(f"\nALL DONE in {(time.time()-t0_all)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
