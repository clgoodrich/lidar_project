"""
Phase 0 — Point-cloud derivatives over the calibration subarea.

Per-tile processing for the 16 LAZ tiles intersecting the calibration subarea:
  - Ground return point density     (quality mask)
  - Total return point density
  - First return point density      (used with total to estimate openness-vs-canopy)
  - Ground return intensity (NN gridding)
  - Digital surface model (DSM) -> CHM = DSM - DEM

Derived products (mosaic-level):
  - point_density_mask.tif
  - chm.tif
  - chm_anomaly.tif
  - intensity_anomaly.tif
  - first_return_fraction.tif      (proxy for "open area" / pulse-was-single)

Expected runtime: 10-25 minutes depending on disk I/O.
"""
import sys
import time
from pathlib import Path
import struct

import numpy as np
import rasterio
from rasterio.merge import merge as rio_merge
import whitebox

sys.path.insert(0, str(Path(__file__).parent))
from _anomaly_utils import read_raster, write_raster, local_zscore

ROOT = Path(r"C:/Users/colto/Documents/GitHub/lidar_project")
DATA = ROOT / "data"
LAZ_DIR = DATA / "files"
SUB = DATA / "derivatives" / "subarea"
SUB.mkdir(parents=True, exist_ok=True)
TMP = SUB / "_tiles"
TMP.mkdir(exist_ok=True)

TARGET_CRS = "EPSG:26917"
SUB_X0, SUB_Y0 = 619500.0, 4594000.0
SUB_X1, SUB_Y1 = 624500.0, 4599000.0
SUB_BBOX = (SUB_X0, SUB_Y0, SUB_X1, SUB_Y1)

SUB_DEM = SUB / "dem.tif"

wbt = whitebox.WhiteboxTools()
wbt.set_verbose_mode(False)
wbt.set_working_dir(str(DATA))


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ───────────────────────────────────────────────────────────────────────────
# Identify the 16 LAZ tiles that cover the subarea
# ───────────────────────────────────────────────────────────────────────────
def read_las_bbox(path: Path):
    with open(path, "rb") as fp:
        hdr = fp.read(256)
    assert hdr[:4] == b"LASF"
    pt_fmt = hdr[104] & 0x3F
    max_x, min_x, max_y, min_y = struct.unpack_from("<dddd", hdr, 179)
    return (min_x, min_y, max_x, max_y, pt_fmt)


sub_tiles = []
for f in sorted(LAZ_DIR.glob("*.laz")):
    mnx, mny, mxx, mxy, pf = read_las_bbox(f)
    if mxx > SUB_X0 and mnx < SUB_X1 and mxy > SUB_Y0 and mny < SUB_Y1:
        sub_tiles.append(f)

log(f"{len(sub_tiles)} tiles cover the calibration subarea")


# ───────────────────────────────────────────────────────────────────────────
# Mosaic helper
# ───────────────────────────────────────────────────────────────────────────
def mosaic_rasters(tile_paths, out_path: Path, bbox: tuple,
                   nodata: float = -9999.0) -> None:
    srcs = [rasterio.open(p) for p in tile_paths]
    data, transform = rio_merge(srcs, bounds=bbox, res=(1.0, 1.0), nodata=nodata)
    profile = srcs[0].profile.copy()
    for s in srcs:
        s.close()
    profile.update(
        height=data.shape[1], width=data.shape[2], transform=transform,
        crs=TARGET_CRS, compress="deflate", tiled=True, count=1,
        dtype="float32", nodata=nodata,
        blockxsize=256, blockysize=256,
    )
    out = data[0].astype("float32")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(out, 1)


# ───────────────────────────────────────────────────────────────────────────
# Per-tile wbt calls with per-derivative caching
# ───────────────────────────────────────────────────────────────────────────
def ensure_per_tile(laz_list, kind: str, runner) -> list[Path]:
    """Run `runner(laz_path, out_path)` for each laz tile, caching to TMP/."""
    outs = []
    for laz in laz_list:
        out = TMP / f"{kind}_{laz.stem}.tif"
        if not out.exists():
            t0 = time.time()
            runner(laz, out)
            log(f"    {kind:15s} {laz.name}  ({time.time()-t0:.1f}s)")
        outs.append(out)
    return outs


EXCLUDE_NOT_GROUND = "0,1,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18"  # keep class 2 only


log("=== Phase 0.3: ground return point density ===")
PTD_GROUND_RAW = SUB / "point_density_ground.tif"
if not PTD_GROUND_RAW.exists():
    def _ground_density(laz, out):
        wbt.lidar_point_density(
            i=str(laz), output=str(out),
            returns="all", resolution=1.0, radius=2.5,
            exclude_cls=EXCLUDE_NOT_GROUND,
        )
    tiles = ensure_per_tile(sub_tiles, "pd_ground", _ground_density)
    mosaic_rasters(tiles, PTD_GROUND_RAW, SUB_BBOX)

# Build the binary quality mask
PTD_MASK = SUB / "point_density_mask.tif"
DENSITY_THRESHOLD = 1.0  # ground pts per m²
if not PTD_MASK.exists():
    with rasterio.open(PTD_GROUND_RAW) as src:
        dens = src.read(1)
        profile = src.profile.copy()
    mask_arr = (dens >= DENSITY_THRESHOLD).astype("uint8")
    mask_arr[dens < 0] = 255
    profile.update(dtype="uint8", nodata=255,
                   compress="deflate", tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(PTD_MASK, "w", **profile) as dst:
        dst.write(mask_arr, 1)
    log(f"  Quality mask: {(mask_arr == 1).mean()*100:.1f}% cells pass >= {DENSITY_THRESHOLD} pts/m²")


log("=== Phase 0.5a: DSM and CHM ===")
DSM_MOS = SUB / "dsm.tif"
CHM = SUB / "chm.tif"
if not DSM_MOS.exists():
    def _dsm(laz, out):
        wbt.lidar_digital_surface_model(
            i=str(laz), output=str(out),
            resolution=1.0, radius=0.5,
        )
    tiles = ensure_per_tile(sub_tiles, "dsm", _dsm)
    mosaic_rasters(tiles, DSM_MOS, SUB_BBOX)

if not CHM.exists():
    with rasterio.open(DSM_MOS) as sdsm, rasterio.open(SUB_DEM) as sdem:
        dsm = sdsm.read(1).astype("float32")
        dem = sdem.read(1).astype("float32")
        prof = sdsm.profile.copy()
    dem_nd = (dem == -32768.0)
    dsm_nd = (dsm == -9999.0) | np.isnan(dsm)
    chm = dsm - dem
    chm[dem_nd | dsm_nd] = np.nan
    chm[chm < 0] = 0.0
    write_raster(CHM, chm, prof)
    log(f"  CHM: shape={chm.shape}, p50={np.nanpercentile(chm,50):.1f} m, p98={np.nanpercentile(chm,98):.1f} m")


log("=== Phase 0.5b: CHM anomaly ===")
CHM_ANOM = SUB / "chm_anomaly.tif"
if not CHM_ANOM.exists():
    chm, chm_nd, prof = read_raster(CHM)
    anom = local_zscore(chm, window=101, nodata_mask=chm_nd)
    write_raster(CHM_ANOM, anom, prof)
    log(f"  CHM anomaly written")


log("=== Phase 0.5c: ground return intensity ===")
INTENSITY = SUB / "intensity.tif"
if not INTENSITY.exists():
    def _intensity(laz, out):
        wbt.lidar_nearest_neighbour_gridding(
            i=str(laz), output=str(out),
            parameter="intensity", returns="all",
            resolution=1.0, radius=1.5,
            exclude_cls=EXCLUDE_NOT_GROUND,
        )
    tiles = ensure_per_tile(sub_tiles, "intensity", _intensity)
    mosaic_rasters(tiles, INTENSITY, SUB_BBOX)


log("=== Phase 0.5d: intensity anomaly ===")
INT_ANOM = SUB / "intensity_anomaly.tif"
if not INT_ANOM.exists():
    ii, ii_nd, prof = read_raster(INTENSITY)
    anom = local_zscore(ii, window=51, nodata_mask=ii_nd)
    write_raster(INT_ANOM, anom, prof)
    log(f"  Intensity anomaly written")


log("=== Phase 0.5e: first-return fraction (open-area proxy) ===")
PTD_TOTAL = SUB / "point_density_total.tif"
PTD_FIRST = SUB / "point_density_first.tif"
FIRST_FRAC = SUB / "first_return_fraction.tif"

if not PTD_TOTAL.exists():
    def _total(laz, out):
        wbt.lidar_point_density(
            i=str(laz), output=str(out),
            returns="all", resolution=1.0, radius=2.5,
        )
    tiles = ensure_per_tile(sub_tiles, "pd_total", _total)
    mosaic_rasters(tiles, PTD_TOTAL, SUB_BBOX)

if not PTD_FIRST.exists():
    def _first(laz, out):
        wbt.lidar_point_density(
            i=str(laz), output=str(out),
            returns="first", resolution=1.0, radius=2.5,
        )
    tiles = ensure_per_tile(sub_tiles, "pd_first", _first)
    mosaic_rasters(tiles, PTD_FIRST, SUB_BBOX)

if not FIRST_FRAC.exists():
    with rasterio.open(PTD_TOTAL) as t, rasterio.open(PTD_FIRST) as f:
        tot = t.read(1).astype("float32")
        fir = f.read(1).astype("float32")
        prof = t.profile.copy()
    frac = np.where(tot > 0, fir / np.maximum(tot, 1e-6), 0.0).astype("float32")
    frac[tot <= 0] = np.nan
    write_raster(FIRST_FRAC, frac, prof)
    log(f"  First-return fraction: p50={np.nanpercentile(frac,50):.2f}, p90={np.nanpercentile(frac,90):.2f}")


log("Phase 0.3 + 0.5 outputs:")
for name, p in [
    ("pd_ground",   PTD_GROUND_RAW),
    ("pd_total",    PTD_TOTAL),
    ("pd_first",    PTD_FIRST),
    ("quality mask",PTD_MASK),
    ("DSM",         DSM_MOS),
    ("CHM",         CHM),
    ("CHM anom",    CHM_ANOM),
    ("intensity",   INTENSITY),
    ("int anom",    INT_ANOM),
    ("first frac",  FIRST_FRAC),
]:
    status = f"{p.stat().st_size/1e6:.1f} MB" if p.exists() else "MISSING"
    log(f"  {name:14s}  {status}")
log("DONE")
