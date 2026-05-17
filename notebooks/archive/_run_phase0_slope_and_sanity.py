"""
Phase 0 — Compute slope over the subarea and render a sanity visualization
of all DEM-only derivatives produced so far. Run this while the point cloud
work runs in parallel.
"""
import sys
import time
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import rasterio
import whitebox

sys.path.insert(0, str(Path(__file__).parent))
from _anomaly_utils import read_raster, write_raster

ROOT = Path(r"C:/Users/colto/Documents/GitHub/lidar_project")
SUB = ROOT / "data" / "derivatives" / "subarea"

SUB_DEM = SUB / "dem.tif"
SLOPE = SUB / "slope.tif"
ROUGHNESS = SUB / "roughness.tif"
LOCAL_RELIEF = SUB / "local_relief.tif"
PLAN_CURV = SUB / "plan_curvature.tif"

wbt = whitebox.WhiteboxTools()
wbt.set_verbose_mode(False)
wbt.set_working_dir(str(ROOT / "data"))


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Slope (degrees) ───────────────────────────────────────────────────────
if not SLOPE.exists():
    log("Slope...")
    wbt.slope(dem=str(SUB_DEM), output=str(SLOPE), units="degrees")

# ── Plan curvature ────────────────────────────────────────────────────────
if not PLAN_CURV.exists():
    log("Plan curvature...")
    wbt.plan_curvature(dem=str(SUB_DEM), output=str(PLAN_CURV))

# ── Local relief (elev range in 10 m window) ──────────────────────────────
if not LOCAL_RELIEF.exists():
    log("Local relief (max-min, filter 11)...")
    # Use min_max difference via two filter calls
    MAXF = SUB / "_local_max.tif"
    MINF = SUB / "_local_min.tif"
    wbt.maximum_filter(i=str(SUB_DEM), output=str(MAXF), filterx=11, filtery=11)
    wbt.minimum_filter(i=str(SUB_DEM), output=str(MINF), filterx=11, filtery=11)
    with rasterio.open(MAXF) as a, rasterio.open(MINF) as b:
        lr = a.read(1).astype("float32") - b.read(1).astype("float32")
        prof = a.profile.copy()
    # Restore nodata
    dem_nd = rasterio.open(SUB_DEM).read(1) == -32768.0
    lr[dem_nd] = np.nan
    write_raster(LOCAL_RELIEF, lr, prof)
    MAXF.unlink(); MINF.unlink()

# ── Roughness = std dev of slope in ~5 m window ───────────────────────────
if not ROUGHNESS.exists():
    log("Roughness (std-of-slope, filter 5)...")
    # Use wbt standard_deviation_filter on the slope raster
    wbt.standard_deviation_filter(
        i=str(SLOPE), output=str(ROUGHNESS), filterx=5, filtery=5,
    )

# ── Sanity visualization of all DEM-only derivatives ──────────────────────
PANELS = [
    (SUB_DEM,                               "DEM",              "cividis",  None, None),
    (SUB / "hillshade.tif",                 "Hillshade",        "gray",     None, None),
    (SUB / "openness_positive.tif",         "Openness (pos)",   "cividis",  None, None),
    (SUB / "openness_negative.tif",         "Openness (neg)",   "cividis",  None, None),
    (SLOPE,                                 "Slope (deg)",      "cividis",  0, 45),
    (PLAN_CURV,                             "Plan curvature",   "coolwarm_r", -0.5, 0.5),
    (LOCAL_RELIEF,                          "Local relief",     "cividis",  0, 10),
    (ROUGHNESS,                             "Roughness",        "cividis",  None, None),
    (SUB / "tpi_15m.tif",                   "TPI 15m",          "coolwarm_r", -3, 3),
    (SUB / "tpi_15m_gradient_magnitude.tif","TPI15 gradient",   "cividis",  None, None),
    (SUB / "hand.tif",                      "HAND",             "cividis",  0, 50),
    (SUB / "streams.tif",                   "Streams",          "Blues",    0, 1),
]

HSHADE_PATH = SUB / "hillshade.tif"
with rasterio.open(HSHADE_PATH) as s:
    hs = s.read(1).astype("float32")

fig, axes = plt.subplots(3, 4, figsize=(22, 17))
for ax, (path, title, cmap, vmn, vmx) in zip(axes.flat, PANELS):
    if not path.exists():
        ax.set_title(f"{title} (missing)"); ax.axis("off"); continue
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nd = src.nodata
    if nd is not None:
        arr[arr == nd] = np.nan
    if vmn is None or vmx is None:
        vmn, vmx = np.nanpercentile(arr, [2, 98])
    ax.imshow(hs, cmap="gray", alpha=0.55)
    im = ax.imshow(arr, cmap=cmap, vmin=vmn, vmax=vmx, alpha=0.75)
    ax.set_title(title, fontsize=11)
    ax.axis("off")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

fig.suptitle("Phase 0 DEM-only derivatives — calibration subarea (5 × 5 km)",
             fontsize=14, y=1.00)
plt.tight_layout()
out_png = SUB / "derivatives_preview_dem.png"
plt.savefig(out_png, dpi=120, bbox_inches="tight")
log(f"Saved: {out_png}")
plt.close()

# ── Print diagnostic stats per derivative ─────────────────────────────────
log("Diagnostic stats:")
for path, title, *_ in PANELS:
    if not path.exists():
        continue
    with rasterio.open(path) as src:
        a = src.read(1).astype("float32")
        nd = src.nodata
    if nd is not None:
        a[a == nd] = np.nan
    finite = np.isfinite(a).sum()
    total = a.size
    if finite == 0:
        log(f"  {title:20s}  ALL NAN")
        continue
    p2, p50, p98 = np.nanpercentile(a, [2, 50, 98])
    log(f"  {title:20s}  valid={finite/total*100:5.1f}%  p2={p2:8.2f}  p50={p50:8.2f}  p98={p98:8.2f}")

log("DONE")
