"""
Phase 0 — DEM-only derivatives over the calibration subarea.

Runs: subarea DEM clip, topographic openness (Yokoyama 2002, numpy impl since
WhiteboxTools openness is a licensed extension), TPI 15m + gradient, HAND
pipeline, multidirectional hillshade.

Expected runtime: ~3-8 minutes. Point-cloud-heavy steps are in
_run_phase0_pointcloud.py.

Idempotent — existing outputs are reused. Delete them to force a rebuild.
"""
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds
import whitebox

# Local utilities (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from _anomaly_utils import topographic_openness, tpi_gradient, read_raster, write_raster

ROOT = Path(r"C:/Users/colto/Documents/GitHub/lidar_project")
DATA = ROOT / "data"
DEM_MOSAIC = DATA / "full_dem.tif"
SUB = DATA / "derivatives" / "subarea"
SUB.mkdir(parents=True, exist_ok=True)

TARGET_CRS = "EPSG:26917"
SUB_X0, SUB_Y0 = 619500.0, 4594000.0
SUB_X1, SUB_Y1 = 624500.0, 4599000.0
SUB_BBOX = (SUB_X0, SUB_Y0, SUB_X1, SUB_Y1)

wbt = whitebox.WhiteboxTools()
wbt.set_verbose_mode(False)
wbt.set_working_dir(str(DATA))


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ───────────────────────────────────────────────────────────────────────────
# 0.1 Clip DEM to subarea
# ───────────────────────────────────────────────────────────────────────────
SUB_DEM = SUB / "dem.tif"
if not SUB_DEM.exists():
    log("Clipping DEM to subarea...")
    with rasterio.open(DEM_MOSAIC) as src:
        window = from_bounds(*SUB_BBOX, transform=src.transform)
        window = window.round_offsets().round_lengths()
        data = src.read(1, window=window)
        transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(
            height=data.shape[0], width=data.shape[1], transform=transform,
            crs=TARGET_CRS, compress="deflate", tiled=True,
            blockxsize=256, blockysize=256,
        )
    with rasterio.open(SUB_DEM, "w", **profile) as dst:
        dst.write(data, 1)

with rasterio.open(SUB_DEM) as src:
    log(f"Subarea DEM: {src.width} x {src.height} @ {src.res} m, nodata={src.nodata}")
    d = src.read(1)
    valid = d[d != src.nodata]
    log(f"  Elev {valid.min():.1f} - {valid.max():.1f} m, nodata {(d == src.nodata).mean()*100:.2f}%")


# ───────────────────────────────────────────────────────────────────────────
# 0.4a Topographic openness (numpy implementation, Yokoyama 2002)
# ───────────────────────────────────────────────────────────────────────────
OPEN_POS = SUB / "openness_positive.tif"
OPEN_NEG = SUB / "openness_negative.tif"
if not OPEN_POS.exists() or not OPEN_NEG.exists():
    log("Running topographic openness (numpy, Yokoyama 2002, radius=50 m)...")
    t0 = time.time()
    dem, nd_mask, prof = read_raster(SUB_DEM)
    pos_open, neg_open = topographic_openness(
        dem, radius=50, cellsize=1.0, nodata_mask=nd_mask, progress=True,
    )
    write_raster(OPEN_POS, pos_open, prof)
    write_raster(OPEN_NEG, neg_open, prof)
    log(f"  openness done in {time.time()-t0:.1f}s")
else:
    log("Openness already exists - skipping")


# ───────────────────────────────────────────────────────────────────────────
# 0.4b TPI at 15 m + gradient
# ───────────────────────────────────────────────────────────────────────────
TPI15 = SUB / "tpi_15m.tif"
TPI15_GRAD_MAG = SUB / "tpi_15m_gradient_magnitude.tif"
TPI15_GRAD_DIR = SUB / "tpi_15m_gradient_direction.tif"

if not TPI15.exists():
    log("Running relative_topographic_position (15x15)...")
    t0 = time.time()
    wbt.relative_topographic_position(
        dem=str(SUB_DEM),
        output=str(TPI15),
        filterx=15,
        filtery=15,
    )
    log(f"  TPI15 done in {time.time()-t0:.1f}s")

if not TPI15_GRAD_MAG.exists() or not TPI15_GRAD_DIR.exists():
    log("Computing TPI15 gradient...")
    tpi, tpi_nd, prof = read_raster(TPI15)
    mag, direction = tpi_gradient(tpi, nodata_mask=tpi_nd)
    write_raster(TPI15_GRAD_MAG, mag, prof)
    write_raster(TPI15_GRAD_DIR, direction, prof)
    log("  TPI15 gradient written")


# ───────────────────────────────────────────────────────────────────────────
# 0.4c HAND pipeline
# ───────────────────────────────────────────────────────────────────────────
BREACHED   = SUB / "dem_breached.tif"
D8_POINTER = SUB / "d8_pointer.tif"
D8_ACCUM   = SUB / "d8_accum.tif"
STREAMS    = SUB / "streams.tif"
HAND       = SUB / "hand.tif"

if not BREACHED.exists():
    log("Breaching depressions (least cost, dist=100)...")
    t0 = time.time()
    wbt.breach_depressions_least_cost(
        dem=str(SUB_DEM), output=str(BREACHED), dist=100, fill=True,
    )
    log(f"  breach done in {time.time()-t0:.1f}s")

if not D8_POINTER.exists():
    log("D8 pointer...")
    t0 = time.time()
    wbt.d8_pointer(dem=str(BREACHED), output=str(D8_POINTER))
    log(f"  d8_pointer done in {time.time()-t0:.1f}s")

if not D8_ACCUM.exists():
    log("D8 flow accumulation...")
    t0 = time.time()
    wbt.d8_flow_accumulation(i=str(BREACHED), output=str(D8_ACCUM), out_type="cells")
    log(f"  d8_accum done in {time.time()-t0:.1f}s")

if not STREAMS.exists():
    log("Extracting streams (threshold=5000 cells)...")
    t0 = time.time()
    wbt.extract_streams(flow_accum=str(D8_ACCUM), output=str(STREAMS), threshold=5000)
    log(f"  extract_streams done in {time.time()-t0:.1f}s")

if not HAND.exists():
    log("Computing HAND (elevation_above_stream)...")
    t0 = time.time()
    wbt.elevation_above_stream(dem=str(SUB_DEM), streams=str(STREAMS), output=str(HAND))
    log(f"  HAND done in {time.time()-t0:.1f}s")


# ───────────────────────────────────────────────────────────────────────────
# 0.6a Hillshade
# ───────────────────────────────────────────────────────────────────────────
HSHADE = SUB / "hillshade.tif"
if not HSHADE.exists():
    log("Building multidirectional hillshade...")
    wbt.multidirectional_hillshade(dem=str(SUB_DEM), output=str(HSHADE))


# ───────────────────────────────────────────────────────────────────────────
# Report
# ───────────────────────────────────────────────────────────────────────────
log("Phase 0 DEM outputs:")
for name, p in [
    ("DEM",        SUB_DEM),
    ("open_pos",   OPEN_POS),
    ("open_neg",   OPEN_NEG),
    ("TPI15",      TPI15),
    ("TPI15 gmag", TPI15_GRAD_MAG),
    ("TPI15 gdir", TPI15_GRAD_DIR),
    ("breached",   BREACHED),
    ("d8_ptr",     D8_POINTER),
    ("d8_accum",   D8_ACCUM),
    ("streams",    STREAMS),
    ("HAND",       HAND),
    ("hillshade",  HSHADE),
]:
    status = f"{p.stat().st_size/1e6:.1f} MB" if p.exists() else "MISSING"
    log(f"  {name:14s}  {status}")
log("DONE")
