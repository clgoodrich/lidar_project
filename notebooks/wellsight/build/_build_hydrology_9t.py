"""Build a full hydrology / drainage stack for the 9t (Venango) mosaic.

Outputs land in data/derivatives/9t/ alongside the DEMs:

  dem_breached_9t_1m.tif      hydrologically conditioned DEM
                              (depressions breached / filled)
  flow_accum_log_9t_1m.tif    log10(contributing cells) — the classic
                              dendritic drainage visualisation
  stream_seed_t1k_9t_1m.tif   binary streams, threshold 1,000  cells (~0.1 ha)
  stream_seed_t10k_9t_1m.tif  binary streams, threshold 10,000 cells (~1 ha)
  stream_seed_t100k_9t_1m.tif binary streams, threshold 100,000 cells (~10 ha)
                              (mainstem class, what we used for the
                              synthetic-water polygons)
  twi_9t_1m.tif               Topographic Wetness Index
                              = ln(A / tan(slope))  -- high values mark
                              areas that tend to be wet / saturated
  spi_9t_1m.tif               Stream Power Index
                              = A * tan(slope)  -- high values mark areas
                              where moving water has the most erosion power

These are unitless per-cell rasters; visualise in QGIS with a log/stretched
colour ramp. The seed rasters are 0/1 (or NoData) -- overlay directly on the
hillshade.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, make_profile

OUT_DIR = DERIV / "9t"
# 1m DEM lives flat in data/derivatives/, not in 9t/ subdir; copy is via WBT
# working-dir mechanics so we point WBT at the parent and write outputs into
# 9t/ explicitly.
DEM_FLAT = DERIV / "dem_9t_1m.tif"
DEM = OUT_DIR / "_dem_9t_1m_link.tif"  # local reference (hard link or copy)
SFX = "9t_1m"
THRESHOLDS = [1_000, 10_000, 100_000]


def main() -> int:
    if not DEM_FLAT.exists():
        print(f"missing DEM: {DEM_FLAT}", file=sys.stderr); return 1
    print(f"source DEM: {DEM_FLAT}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Mirror the flat-file DEM into 9t/ as a stable working name so all WBT
    # outputs live alongside each other.
    if not DEM.exists():
        import shutil; shutil.copy2(DEM_FLAT, DEM)
    import whitebox
    wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(OUT_DIR.resolve()))

    # 1) Condition the DEM: breach + fill so flow routing isn't blocked.
    breach = f"dem_breached_{SFX}.tif"
    if not (OUT_DIR / breach).exists():
        t0 = time.time()
        rc = wbt.breach_depressions_least_cost(
            dem=DEM.name, output=breach, dist=50, flat_increment=1e-3)
        print(f"breach -> rc={rc}  ({time.time()-t0:.1f}s)")

    # 2) D8 flow routing.
    pntr = f"_d8pntr_{SFX}.tif"
    accum_raw = f"_d8accum_{SFX}.tif"
    rc = wbt.d8_pointer(dem=breach, output=pntr); print(f"d8_pointer rc={rc}")
    rc = wbt.d8_flow_accumulation(i=breach, output=accum_raw,
                                   out_type="cells", log=False)
    print(f"d8_flow_accumulation rc={rc}")

    # 3) Save log10(accum) for visualisation.
    with rasterio.open(OUT_DIR / accum_raw) as r:
        accum = r.read(1).astype(np.float32)
        prof = r.profile.copy()
        nd = r.nodata
    log_accum = np.where(accum > 0, np.log10(np.maximum(accum, 1.0)), np.nan)
    log_accum = log_accum.astype(np.float32)
    log_path = OUT_DIR / f"flow_accum_log_{SFX}.tif"
    lprof = prof.copy()
    lprof.update(dtype="float32", nodata=np.nan, compress="lzw")
    with rasterio.open(log_path, "w", **lprof) as ds:
        ds.write(log_accum, 1)
    print(f"wrote {log_path.name}  "
          f"(p50={np.nanmedian(log_accum):.1f}  "
          f"p95={np.nanpercentile(log_accum,95):.1f}  "
          f"max={np.nanmax(log_accum):.1f})")

    # 4) Stream networks at multiple thresholds (binary uint8).
    for th in THRESHOLDS:
        tmp = f"_streams_t{th}_{SFX}.tif"
        rc = wbt.extract_streams(flow_accum=accum_raw, output=tmp, threshold=th)
        with rasterio.open(OUT_DIR / tmp) as r:
            arr = r.read(1)
            r_nd = r.nodata
        seed = np.isfinite(arr) & (arr != (r_nd if r_nd is not None else -9999))
        out_name = f"stream_seed_t{th}_{SFX}.tif"
        prof_u8 = prof.copy()
        prof_u8.update(dtype="uint8", nodata=255, compress="lzw")
        with rasterio.open(OUT_DIR / out_name, "w", **prof_u8) as ds:
            ds.write(seed.astype(np.uint8), 1)
        n = int(seed.sum())
        print(f"  streams thresh={th:>7,d}  cells={n:>9,}  -> {out_name}")
        (OUT_DIR / tmp).unlink(missing_ok=True)

    # 5) Topographic Wetness Index (TWI).
    # WBT 'WetnessIndex' takes a specific contributing area (SCA) and slope.
    sca = f"_sca_{SFX}.tif"
    slope_deg = f"_slope_deg_{SFX}.tif"
    rc = wbt.d8_flow_accumulation(i=breach, output=sca, out_type="sca", log=False)
    print(f"d8 SCA rc={rc}")
    rc = wbt.slope(dem=breach, output=slope_deg, units="degrees")
    print(f"slope rc={rc}")
    twi = f"twi_{SFX}.tif"
    rc = wbt.wetness_index(sca=sca, slope=slope_deg, output=twi)
    print(f"wetness_index rc={rc}  -> {twi}")

    # 6) Stream Power Index (SPI).
    spi = f"spi_{SFX}.tif"
    rc = wbt.stream_power_index(sca=sca, slope=slope_deg, output=spi)
    print(f"stream_power_index rc={rc}  -> {spi}")

    # Clean throwaway intermediates.
    for tmp in (pntr, accum_raw, sca, slope_deg):
        (OUT_DIR / tmp).unlink(missing_ok=True)
    print(f"\nDONE. outputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
