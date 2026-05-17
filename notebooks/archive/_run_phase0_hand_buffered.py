"""
Recompute HAND using a 1 km-buffered DEM so cells near the subarea edges have
flow paths long enough to reach a stream. Clip the result back to the subarea.

This replaces the earlier HAND output, which had 54% nodata because flow paths
near the subarea boundary left the box without hitting a stream.
"""
import sys
import time
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
import whitebox

sys.path.insert(0, str(Path(__file__).parent))
from _anomaly_utils import write_raster

ROOT = Path(r"C:/Users/colto/Documents/GitHub/lidar_project")
DATA = ROOT / "data"
DEM_MOSAIC = DATA / "full_dem.tif"
SUB = DATA / "derivatives" / "subarea"
BUF = SUB / "_hand_buffer"
BUF.mkdir(exist_ok=True)

TARGET_CRS = "EPSG:26917"

# Subarea bbox
SUB_X0, SUB_Y0 = 619500.0, 4594000.0
SUB_X1, SUB_Y1 = 624500.0, 4599000.0

# Buffer
BUFFER = 1500.0  # meters — larger than any plausible flow path we need
BUF_X0 = SUB_X0 - BUFFER
BUF_Y0 = SUB_Y0 - BUFFER
BUF_X1 = SUB_X1 + BUFFER
BUF_Y1 = SUB_Y1 + BUFFER

# Clip to full DEM extent
with rasterio.open(DEM_MOSAIC) as src:
    fb = src.bounds
BUF_X0 = max(BUF_X0, fb.left)
BUF_Y0 = max(BUF_Y0, fb.bottom)
BUF_X1 = min(BUF_X1, fb.right)
BUF_Y1 = min(BUF_Y1, fb.top)
BUF_BBOX = (BUF_X0, BUF_Y0, BUF_X1, BUF_Y1)

wbt = whitebox.WhiteboxTools()
wbt.set_verbose_mode(False)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


BUF_DEM = BUF / "dem_buffered.tif"
if not BUF_DEM.exists():
    log(f"Clipping buffered DEM: {BUF_BBOX}")
    with rasterio.open(DEM_MOSAIC) as src:
        window = from_bounds(*BUF_BBOX, transform=src.transform)
        window = window.round_offsets().round_lengths()
        data = src.read(1, window=window)
        transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(
            height=data.shape[0], width=data.shape[1], transform=transform,
            crs=TARGET_CRS, compress="deflate", tiled=True,
            blockxsize=256, blockysize=256,
        )
    with rasterio.open(BUF_DEM, "w", **profile) as dst:
        dst.write(data, 1)

# HAND pipeline on the buffered DEM
BREACHED_BUF = BUF / "dem_breached.tif"
D8_PTR_BUF   = BUF / "d8_pointer.tif"
D8_ACC_BUF   = BUF / "d8_accum.tif"
STREAMS_BUF  = BUF / "streams.tif"
HAND_BUF     = BUF / "hand.tif"

if not BREACHED_BUF.exists():
    log("Breach (buffered, dist=200)...")
    wbt.breach_depressions_least_cost(
        dem=str(BUF_DEM), output=str(BREACHED_BUF), dist=200, fill=True,
    )
if not D8_PTR_BUF.exists():
    log("D8 pointer...")
    wbt.d8_pointer(dem=str(BREACHED_BUF), output=str(D8_PTR_BUF))
if not D8_ACC_BUF.exists():
    log("D8 flow accumulation...")
    wbt.d8_flow_accumulation(i=str(BREACHED_BUF), output=str(D8_ACC_BUF), out_type="cells")
if not STREAMS_BUF.exists():
    log("Extract streams (threshold=2000)...")  # lower threshold → denser network
    wbt.extract_streams(flow_accum=str(D8_ACC_BUF), output=str(STREAMS_BUF), threshold=2000)
if not HAND_BUF.exists():
    log("Elevation above stream...")
    wbt.elevation_above_stream(dem=str(BUF_DEM), streams=str(STREAMS_BUF), output=str(HAND_BUF))


# Clip back to subarea
log("Clipping HAND back to subarea...")
HAND_OUT = SUB / "hand.tif"
STREAMS_OUT = SUB / "streams.tif"

def clip_back(src_path, out_path):
    with rasterio.open(src_path) as src:
        window = from_bounds(SUB_X0, SUB_Y0, SUB_X1, SUB_Y1, transform=src.transform)
        window = window.round_offsets().round_lengths()
        data = src.read(1, window=window)
        transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(
            height=data.shape[0], width=data.shape[1], transform=transform,
            crs=TARGET_CRS, compress="deflate", tiled=True,
            blockxsize=256, blockysize=256,
        )
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data, 1)

clip_back(HAND_BUF, HAND_OUT)
clip_back(STREAMS_BUF, STREAMS_OUT)

# Report
with rasterio.open(HAND_OUT) as src:
    h = src.read(1)
    nd = src.nodata
    nd_frac = float((h == nd).mean()) if nd is not None else float(np.isnan(h).mean())
    log(f"HAND clipped: nodata={nd_frac*100:.2f}%, max={h[h != nd].max():.2f} m")

log("DONE")
