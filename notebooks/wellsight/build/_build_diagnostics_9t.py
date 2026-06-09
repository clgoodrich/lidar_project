"""Diagnostic DEM derivatives for the 9t tile (curvature / hydrology / texture).

Generates the "second wave" of geomorphometric layers we don't already have
(see docs/iterations/diagnostics_9t.md), straight from the existing bare-earth
DEM — no point-cloud reprocessing. Diagnostic-only: these are for eyeballing in
QGIS to see which actually separate pits / pads / roads. None are wired into the
trained models. If one earns a slot, recompute it at 0.5 m to match the feature
stack.

Input : data/derivatives/dem_9t_1m.tif   (1 m bare-earth DEM, EPSG:6346)
Output: data/derivatives/tiles/9t/diagnostics/<name>_9t_1m.tif

Run:
  python notebooks/wellsight/build/_build_diagnostics_9t.py
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV  # noqa: E402

SFX = "9t_1m"
DEM_SRC = DERIV / "dem_9t_1m.tif"
OUT_DIR = DERIV / "tiles" / "9t" / "diagnostics"


def _subtract_to_depth(filled: Path, dem: Path, out_path: Path) -> None:
    """depth-in-sink = filled - original, clipped at 0 (closed-depression depth)."""
    with rasterio.open(filled) as f, rasterio.open(dem) as d:
        fa = f.read(1).astype(np.float32)
        da = d.read(1).astype(np.float32)
        prof = d.profile.copy()
        nd = d.nodata
    depth = fa - da
    if nd is not None:
        bad = (da == nd) | (fa == nd)
    else:
        bad = ~np.isfinite(da) | ~np.isfinite(fa)
    depth[depth < 0] = 0.0
    depth[bad] = -9999.0
    prof.update(dtype="float32", nodata=-9999.0, compress="lzw")
    with rasterio.open(out_path, "w", **prof) as ds:
        ds.write(depth.astype(np.float32), 1)


def main() -> int:
    if not DEM_SRC.exists():
        print(f"missing DEM: {DEM_SRC}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    import whitebox
    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(OUT_DIR.resolve()))

    # WBT works most reliably on files inside the working dir; copy DEM in once.
    dem = f"_dem_{SFX}.tif"
    if not (OUT_DIR / dem).exists():
        shutil.copy2(DEM_SRC, OUT_DIR / dem)

    def name(stem: str) -> str:
        return f"{stem}_{SFX}.tif"

    results: list[tuple[str, str]] = []

    def run(label: str, fn, *args, **kwargs):
        t0 = time.time()
        try:
            rc = fn(*args, **kwargs)
            ok = "ok" if rc == 0 else f"rc={rc}"
        except Exception as e:  # keep the batch alive on a single failure
            ok = f"ERR {type(e).__name__}: {e}"
        dt = time.time() - t0
        print(f"  [{ok:>10}] {label}  ({dt:.1f}s)")
        results.append((label, ok))

    print(f"DEM: {DEM_SRC}  ->  {OUT_DIR}")

    # --- 1) Hydrology: fill, depth-in-sink, SCA, TWI -----------------------
    filled = f"_filled_{SFX}.tif"
    run("fill_depressions", wbt.fill_depressions, dem, filled, fix_flats=True)
    if (OUT_DIR / filled).exists():
        t0 = time.time()
        _subtract_to_depth(OUT_DIR / filled, OUT_DIR / dem, OUT_DIR / name("depth_in_sink"))
        print(f"  [        ok] depth_in_sink (filled-dem)  ({time.time()-t0:.1f}s)")
        results.append(("depth_in_sink", "ok"))

    sca = f"_sca_{SFX}.tif"
    slope_d = f"_slope_deg_{SFX}.tif"
    run("d8_flow_accum(sca)", wbt.d8_flow_accumulation, filled, sca,
        out_type="specific contributing area")
    run("slope(deg)", wbt.slope, dem, slope_d, units="degrees")
    if (OUT_DIR / sca).exists() and (OUT_DIR / slope_d).exists():
        run("wetness_index(TWI)", wbt.wetness_index, sca, slope_d, name("twi"))

    # --- 2) Curvature family ----------------------------------------------
    run("profile_curvature", wbt.profile_curvature, dem, name("profile_curv"))
    run("plan_curvature", wbt.plan_curvature, dem, name("plan_curv"))
    run("total_curvature", wbt.total_curvature, dem, name("total_curv"))
    run("mean_curvature", wbt.mean_curvature, dem, name("mean_curv"))
    run("gaussian_curvature", wbt.gaussian_curvature, dem, name("gaussian_curv"))

    # --- 3) Geomorphons (categorical landform) ----------------------------
    run("geomorphons", wbt.geomorphons, dem, name("geomorphons"),
        search=50, threshold=0.0, forms=True)

    # --- 4) Visualization: multidirectional hillshade, sph-stddev normals --
    run("multidir_hillshade", wbt.multidirectional_hillshade, dem,
        name("mdhillshade"))
    run("sph_stddev_normals", wbt.spherical_std_dev_of_normals, dem,
        name("sph_stddev_normals"), filter=11)

    # --- 5) Texture / flatness discriminators -----------------------------
    run("ruggedness_index(TRI)", wbt.ruggedness_index, dem, name("tri"))
    run("surface_area_ratio", wbt.surface_area_ratio, dem, name("sar"))
    run("downslope_index", wbt.downslope_index, dem, name("downslope_index"),
        drop=2.0, out_type="tangent")

    # --- cleanup temp files ------------------------------------------------
    for tmp in (filled, sca, slope_d):
        (OUT_DIR / tmp).unlink(missing_ok=True)

    print("\n=== summary ===")
    ok = sum(1 for _, s in results if s == "ok")
    for label, s in results:
        print(f"  {label:<26} {s}")
    print(f"{ok}/{len(results)} layers OK  ->  {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
