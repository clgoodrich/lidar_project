"""Reconstruct the Barlow et al. (2022) U-Net input rasters over Taylor Valley.

Barlow, M.C., Zhu, X. & Glennie, C.L. (2022), "Stream Boundary Detection of a
Hyper-Arid, Polar Region Using a U-Net Architecture: Taylor Valley, Antarctica",
Remote Sensing 14(1):234, doi:10.3390/rs14010234. The U-Net is trained on terrain
rasters derived from the lidar. The dissertation (Ch6) uses elevation, slope, aspect,
curvature, intensity, and flow accumulation:

    1. elevation        - the bare-earth DEM
    2. slope            - WBT slope (degrees)
    3. aspect           - WBT aspect (slope direction)
    4. curvature        - WBT total curvature (convex+/concave-)
    5. flow accumulation- WBT breach -> FD8 *multi-flow-direction* accumulation (log1p);
                          Barlow used ArcGIS MFD, FD8 is the WBT MFD equivalent (NOT D8)
    6. lidar intensity  - mean Intensity rasterized from the point cloud (PDAL)

All at 1 m, EPSG:3294 (Transantarctic Mtns proj), aligned to the DEM grid.
Source data lives off-repo on J:\\barlow_data (DEM tiles + Taylor Valley .laz).

Bootstrap (per CLAUDE.md): run a bounded --bbox pilot first, eyeball it against the
MCM-LTER stream-channel labels, THEN drop --bbox to build the full valley.

CLI:
  # pilot over a small window (xmin ymin xmax ymax in EPSG:3294 metres)
  python _build_barlow_inputs.py --bbox -6000 33000 0 38000
  python _build_barlow_inputs.py            # full Taylor Valley (~11 GB/raster!)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "notebooks" / "wellsight_v2"))
from _common import run_pdal  # noqa: E402

BARLOW = Path("J:/barlow_data")
DEM_DIR = BARLOW / "mdv_lidar" / "be_dem_1m" / "Taylor_Valley"
PC_DIR = BARLOW / "mdv_lidar" / "pc" / "Taylor_Valley"
OUT = BARLOW / "barlow_inputs" / "taylor_valley"
CRS = "EPSG:3294"
RES = 1.0
# filename like ot_000002_-25000_32008_1.laz -> tile origin X=-25000, Y=32008
_PC_XY = re.compile(r"ot_\d+_(-?\d+)_(-?\d+)_\d+\.laz$")


def _gdal(cmd):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def build_elevation(bbox, out):
    """Mosaic the DEM tiles (optionally cropped to bbox) -> elevation.tif."""
    tifs = sorted(DEM_DIR.glob("*.tif"))
    vrt = out / "_dem.vrt"
    _gdal(["gdalbuildvrt", str(vrt), *[str(t) for t in tifs]])
    elev = out / "elevation.tif"
    cmd = ["gdal_translate", "-of", "GTiff", "-co", "COMPRESS=LZW",
           "-co", "TILED=YES", "-co", "BIGTIFF=IF_SAFER"]
    if bbox:
        x0, y0, x1, y1 = bbox
        cmd += ["-projwin", str(x0), str(y1), str(x1), str(y0)]  # ulx uly lrx lry
    cmd += [str(vrt), str(elev)]
    _gdal(cmd)
    return elev


def build_terrain_derivs(elev, out):
    """The DEM-derived Barlow inputs: slope, aspect, curvature, and MFD flow
    accumulation. Barlow uses slope/aspect/curvature (Ch6) + a *multi-flow-direction*
    (MFD) accumulation (Ch4 used ArcGIS MFD) -> WBT FD8 is the MFD equivalent.
    """
    import whitebox
    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)
    a = lambda p: str(Path(p).resolve())
    slope = out / "slope.tif"
    wbt.slope(a(elev), a(slope), units="degrees")
    aspect = out / "aspect.tif"
    wbt.aspect(a(elev), a(aspect))
    curv = out / "curvature.tif"
    # profile curvature is SIGNED (concave-/convex+) along the slope — captures the
    # channel concavity Barlow needs; WBT total_curvature returns magnitude only (>=0).
    wbt.profile_curvature(a(elev), a(curv))
    breached = out / "_breached.tif"
    wbt.breach_depressions_least_cost(a(elev), a(breached), dist=100)
    facc = out / "_flowacc_cells.tif"
    wbt.fd8_flow_accumulation(a(breached), a(facc), out_type="cells")  # MFD, not D8
    # log1p compress the heavy-tailed accumulation (Barlow-style input)
    import rasterio
    import numpy as np
    with rasterio.open(facc) as ds:
        prof = ds.profile; arr = ds.read(1).astype("float32")
    arr = np.log1p(np.clip(arr, 0, None))
    prof.update(dtype="float32", compress="lzw", tiled=True,
                blockxsize=256, blockysize=256, bigtiff="IF_SAFER")
    with rasterio.open(out / "flowacc_log.tif", "w", **prof) as ds:
        ds.write(arr, 1)
    for tmp in (breached, facc):
        Path(tmp).unlink(missing_ok=True)
    return slope, aspect, curv, out / "flowacc_log.tif"


def _select_pc_tiles(bbox, pad=1200):
    """Tiles whose name-encoded origin falls within bbox (+pad). All if no bbox."""
    tiles = sorted(PC_DIR.glob("*.laz"))
    if not bbox:
        return tiles
    x0, y0, x1, y1 = bbox
    keep = []
    for t in tiles:
        m = _PC_XY.search(t.name)
        if not m:
            continue
        x, y = int(m.group(1)), int(m.group(2))
        if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad:
            keep.append(t)
    return keep


def build_intensity(bbox, elev, out):
    """Rasterize mean lidar Intensity from the point cloud, aligned to the DEM."""
    import rasterio
    with rasterio.open(elev) as ds:
        b = ds.bounds
    tiles = _select_pc_tiles(bbox)
    if not tiles:
        print("  no PC tiles intersect bbox; skip intensity"); return None
    print(f"  intensity from {len(tiles)} PC tiles")
    inten = out / "intensity.tif"
    stages = [str(t) for t in tiles]
    stages.append({"type": "filters.crop",
                   "bounds": f"([{b.left},{b.right}],[{b.bottom},{b.top}])"})
    stages.append({"type": "writers.gdal", "filename": str(inten),
                   "dimension": "Intensity", "output_type": "mean",
                   "resolution": RES, "origin_x": b.left, "origin_y": b.bottom,
                   "width": int(round((b.right - b.left) / RES)),
                   "height": int(round((b.top - b.bottom) / RES)),
                   "override_srs": CRS, "data_type": "float32"})
    run_pdal(stages, label="barlow_intensity", timeout=7200)
    return inten


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("XMIN", "YMIN", "XMAX", "YMAX"),
                    help="pilot window in EPSG:3294 metres (omit for full Taylor Valley)")
    ap.add_argument("--skip-intensity", action="store_true", help="DEM-derived only")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    bbox = args.bbox
    print(f"== Barlow inputs -> {OUT} (bbox={bbox or 'FULL'}) ==")
    elev = build_elevation(bbox, OUT)
    print("  elevation ok")
    build_terrain_derivs(elev, OUT)
    print("  slope + aspect + curvature + MFD flowacc ok")
    if not args.skip_intensity:
        build_intensity(bbox, elev, OUT)
        print("  intensity ok")
    print("done:", sorted(p.name for p in OUT.glob("*.tif") if not p.name.startswith("_")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
