"""Rebuild the 2006-2008 -> 2019 DoD over the 9t block with ONE ICP solve.

Why this exists
---------------
The 2026-05-21 product (`dod_9t_2m.tif`) has two defects found on 2026-07-31:

  1. Each older tile was aligned by its OWN independent ICP run, then the
     results were mosaicked. Median DoD inside each tile footprint came out
     002958 -0.038, 002959 -0.057, 003111 +0.046, 003112 +0.044 m -- a 0.103 m
     spread against a 0.136 m pooled sigma. Those steps were written up as
     "swath-level bias in the 2006-2008 acquisition"; they are actually our own
     per-tile alignment residual.
  2. `dem_diff_2m.tif` does not reconstruct from the DEMs stored beside it, and
     its 2019 input (`tiles/mosaic_3x3/*/dem_1m.tif`) no longer exists.

This script fixes both:

  * ALL older tiles covering 9t are merged into a single point cloud and solved
    as ONE ICP problem, so there is one rigid transform for the whole block and
    no seam can be introduced by the alignment step.
  * The 2019 side is `tiles/9t/dem_9t_05.tif` -- the canonical 9t DEM every
    other derivative uses -- rather than a reconstructed mosaic.
  * The older tiles are rasterised individually only AFTER the shared transform
    is applied, and mosaicked by a true mean (sum/count) rather than the
    order-dependent `0.5 * (dst + buf)` running average used before.

CRS trap (see docs/analysis_log.md 2026-07-31)
----------------------------------------------
The 2006-2008 LAZ headers declare `AUTHORITY["EPSG",32128]` -- the METRE
variant of PA State Plane North -- on a WKT that is US-survey-foot throughout
(false easting 1968500, UNIT US survey foot). PDAL's derived proj4 is the
mangled hybrid `+x_0=600000 +units=us-ft`, which lands the data ~417 km away.
`in_srs` is therefore forced to EPSG:2271 on every read. Never omit it.

Z is also US survey feet. The 2026-05-21 run scaled by the INTERNATIONAL foot
(0.3048); this uses the survey foot. The difference is 2 ppm, ~1 mm over the
738 m elevation range -- immaterial next to a 0.136 m sigma, corrected only
because we now know which foot it is.

Outputs (data/derivatives/experiments/icp/change_9t/)
-----------------------------------------------------
  dem_2006_singleicp_9t_2m.tif        aligned 2006-2008 DEM, one ICP solve
  dod_9t_singleicp_2m.tif             2019 - 2006/08, m
  dod_9t_singleicp_tiledz_2m.tif      same, after per-tile residual dz removal
  _icp_rebuild_9t.json                every number quoted in the write-up
  fig_dod_9t_singleicp_vs_original.png  side-by-side against the old product

Intermediates go to the scratchpad, not the repo -- the merged point clouds are
hundreds of MB and are regenerable (CLAUDE.md large-file rule).

Run:
  python notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py
  python notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py --reuse-icp
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DST_CRS, PDAL_EXE, ROOT, run_pdal, write_tif  # noqa: E402

NINE_T = ROOT / "data" / "derivatives" / "tiles" / "9t"
# The 2006-2008 clouds lived on an external drive that is no longer mounted
# (F: was gone by 2026-08-12). There is no copy on C: or on the E: backup, so
# this path is not merely wrong -- the input data may be lost. Override with
# WELLSIGHT_OLD_LAZ_DIR if the drive comes back or the clouds are re-fetched.
OLD_DIR = Path(os.environ.get(
    "WELLSIGHT_OLD_LAZ_DIR", r"F:\lidar_project\consolidated\lidar_all"))
NEW_DIR = ROOT / "data" / "source_laz" / "westernpa"
OUT = ROOT / "data" / "derivatives" / "experiments" / "icp" / "change_9t"
WORK = Path(os.environ.get("WELLSIGHT_SCRATCH", tempfile.gettempdir())) / "icp_rebuild_9t"

# 9t block, EPSG:6346. Identical to every other 9t raster.
BBOX = (619500.0, 4593000.0, 624000.0, 4597500.0)
RES = 2.0
W = H = int((BBOX[2] - BBOX[0]) / RES)
TRANSFORM = from_origin(BBOX[0], BBOX[3], RES, RES)
# ICP geometry. The FIXED cloud must strictly enclose the MOVING cloud: any
# moving point with no real counterpart still gets paired with its nearest
# fixed neighbour and drags the solve. A first attempt cropped both to the same
# bbox, which left the older cloud with a 200 m rim beyond the 2019 tile edge
# -- ICP diverged to a -30 km shift, converged=False, fitness 17.7.
SHRINK = 150.0                   # moving (2006-08) cropped INSIDE the block
MAX_DIST = 5.0                   # reject correspondences beyond this (m)
# Guard: the two surveys are known to agree to well under a metre, so anything
# large is a diverged solve, not a real datum offset. Abort rather than
# rasterise garbage.
MAX_PLAUSIBLE_XY = 25.0
MAX_PLAUSIBLE_Z = 10.0

OLD_CRS = "EPSG:2271"            # forced; the header's 32128 is wrong
Z_FT_TO_M = 1200.0 / 3937.0      # US survey foot
VOXEL = 5.0                      # matches the 2026-05-21 run for comparability

# The four 2006-2008 tiles that intersect 9t (30.6 + 17.0 + 36.9 + 20.6 = 105%).
OLD_TILES = ("002958", "002959", "003111", "003112")
NEW_TILES = [f"USGS_LPC_PA_WesternPA_2019_D20_17TPF{e}{n}.laz"
             for e in ("619", "621", "622") for n in ("593", "594", "596")]


def old_path(tid: str) -> Path:
    return OLD_DIR / (f"USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_"
                      f"2006-2008_{tid}.laz")


def robust(v: np.ndarray) -> tuple[float, float]:
    med = float(np.median(v))
    return med, float(1.4826 * np.median(np.abs(v - med)))


def ref_dem_2m() -> np.ndarray:
    """Canonical 9t 2019 DEM resampled onto the 2 m block grid."""
    dst = np.full((H, W), np.nan, np.float32)
    with rasterio.open(NINE_T / "dem_9t_05.tif") as s:
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform,
                  src_crs=s.crs, dst_transform=TRANSFORM, dst_crs=DST_CRS,
                  resampling=Resampling.average,
                  src_nodata=s.nodata, dst_nodata=np.nan)
    return dst.astype(np.float64)


# --------------------------------------------------------------------------
# 1) one ICP solve for the whole block
# --------------------------------------------------------------------------
def solve_icp() -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    # moving: strictly inside the block. fixed: the whole block.
    mx0, my0 = BBOX[0] + SHRINK, BBOX[1] + SHRINK
    mx1, my1 = BBOX[2] - SHRINK, BBOX[3] - SHRINK
    x0, y0, x1, y1 = BBOX[0], BBOX[1], BBOX[2], BBOX[3]
    old_vox = WORK / "old_2006_ground_merged_vox5m.las"
    new_vox = WORK / "new_2019_ground_merged_vox5m.las"
    aligned = WORK / "old_2006_aligned_singleicp_vox5m.las"

    missing = [str(old_path(t)) for t in OLD_TILES if not old_path(t).exists()]
    missing += [str(NEW_DIR / n) for n in NEW_TILES if not (NEW_DIR / n).exists()]
    if missing:
        raise SystemExit("missing inputs:\n  " + "\n  ".join(missing))

    print(f"[1/4] merging {len(OLD_TILES)} older tiles -> one cloud "
          f"(in_srs forced to {OLD_CRS})")
    run_pdal([
        *[str(old_path(t)) for t in OLD_TILES],
        {"type": "filters.merge"},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.reprojection", "in_srs": OLD_CRS, "out_srs": DST_CRS},
        {"type": "filters.assign", "value": f"Z = Z * {Z_FT_TO_M:.17g}"},
        {"type": "filters.crop", "bounds": f"([{mx0},{mx1}],[{my0},{my1}])"},
        {"type": "filters.voxelcenternearestneighbor", "cell": VOXEL},
        {"type": "writers.las", "filename": str(old_vox),
         "minor_version": 4, "dataformat_id": 6, "a_srs": DST_CRS},
    ], label="old_merge", tmp_dir=WORK, timeout=7200)

    print(f"[2/4] merging {len(NEW_TILES)} 2019 tiles -> one cloud")
    run_pdal([
        *[str(NEW_DIR / n) for n in NEW_TILES],
        {"type": "filters.merge"},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.crop", "bounds": f"([{x0},{x1}],[{y0},{y1}])"},
        {"type": "filters.voxelcenternearestneighbor", "cell": VOXEL},
        {"type": "writers.las", "filename": str(new_vox),
         "minor_version": 4, "dataformat_id": 6, "a_srs": DST_CRS},
    ], label="new_merge", tmp_dir=WORK, timeout=7200)

    print("[3/4] single ICP solve, fixed = 2019, moving = 2006/08")
    meta_path = run_pdal([
        {"type": "readers.las", "filename": str(new_vox), "tag": "fixed"},
        {"type": "readers.las", "filename": str(old_vox), "tag": "moving"},
        {"type": "filters.icp", "inputs": ["fixed", "moving"],
         "max_dist": MAX_DIST},
        {"type": "writers.las", "filename": str(aligned),
         "minor_version": 4, "dataformat_id": 6, "a_srs": DST_CRS},
    ], label="icp_single", tmp_dir=WORK, capture_meta=True, timeout=14400)
    if meta_path is None or not Path(meta_path).exists():
        raise SystemExit("ICP produced no metadata")

    icp = json.loads(Path(meta_path).read_text())["stages"]["filters.icp"]
    mat = [float(v) for row in icp["composed"].strip().split("\n")
           for v in row.split()]
    # The raw translation column is NOT the shift. ICP returns a rigid
    # transform about the coordinate ORIGIN, and UTM northings are ~4.6e6 m
    # away, so a 2.8e-5 rad rotation shows up as a ~130 m translation term that
    # the rotation immediately cancels. The meaningful quantity is the
    # displacement evaluated at the moving cloud's centroid.
    M = np.array(mat, dtype=float).reshape(4, 4)
    R, tvec = M[:3, :3], M[:3, 3]
    cen = icp.get("centroid")
    if isinstance(cen, str):
        c = np.array([float(v) for v in cen.replace(",", " ").split()][:3])
    elif isinstance(cen, (list, tuple)) and len(cen) >= 3:
        c = np.array([float(v) for v in cen[:3]])
    else:
        c = np.array([(BBOX[0] + BBOX[2]) / 2, (BBOX[1] + BBOX[3]) / 2, 430.0])
    disp = R @ c + tvec - c
    dx, dy, dz = float(disp[0]), float(disp[1]), float(disp[2])
    print(f"  converged={icp.get('converged')}  fitness={icp.get('fitness')}")
    print(f"  raw translation column: {tvec[0]:+.3f} {tvec[1]:+.3f} "
          f"{tvec[2]:+.3f} m  (rotation-about-origin artefact, not the shift)")
    print(f"  displacement at centroid {np.array2string(c, precision=1)}: "
          f"dx={dx:+.4f}  dy={dy:+.4f}  dz={dz:+.4f} m")
    (WORK / "_icp_single_meta.json").write_text(json.dumps(icp, indent=2))

    if (abs(dx) > MAX_PLAUSIBLE_XY or abs(dy) > MAX_PLAUSIBLE_XY
            or abs(dz) > MAX_PLAUSIBLE_Z):
        raise SystemExit(
            f"ICP DIVERGED -- refusing to rasterise.\n"
            f"  shift dx={dx:+.1f} dy={dy:+.1f} dz={dz:+.1f} m "
            f"(limits +/-{MAX_PLAUSIBLE_XY} xy, +/-{MAX_PLAUSIBLE_Z} z)\n"
            f"  converged={icp.get('converged')} fitness={icp.get('fitness')}\n"
            f"  inspect {WORK / '_icp_single_meta.json'}")
    if not icp.get("converged"):
        print("  WARNING: filters.icp reports converged=False but the shift is "
              "plausible; treating as usable and reporting fitness.")
    return {"converged": icp.get("converged"), "fitness": icp.get("fitness"),
            "matrix": mat, "voxel_m": VOXEL, "max_dist_m": MAX_DIST,
            "centroid": c.tolist(), "raw_translation": tvec.tolist(),
            "dx": dx, "dy": dy, "dz": dz}


# --------------------------------------------------------------------------
# 2) rasterise each tile under the SHARED transform
# --------------------------------------------------------------------------
def rasterise_tiles(mat: list[float]) -> dict[str, np.ndarray]:
    mstr = " ".join(f"{v:.12g}" for v in mat)
    out: dict[str, np.ndarray] = {}
    for tid in OLD_TILES:
        tif = WORK / f"dem_2006_{tid}_singleicp_2m.tif"
        print(f"[4/4] rasterising {tid} under the shared transform")
        run_pdal([
            {"type": "readers.las", "filename": str(old_path(tid))},
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {"type": "filters.reprojection", "in_srs": OLD_CRS,
             "out_srs": DST_CRS},
            {"type": "filters.assign", "value": f"Z = Z * {Z_FT_TO_M:.17g}"},
            {"type": "filters.transformation", "matrix": mstr},
            {"type": "filters.delaunay"},
            {"type": "filters.faceraster", "resolution": RES,
             "origin_x": BBOX[0], "origin_y": BBOX[1], "width": W, "height": H},
            {"type": "writers.raster", "filename": str(tif),
             "data_type": "float32"},
        ], label=f"rast_{tid}", tmp_dir=WORK, timeout=7200)
        with rasterio.open(tif) as s:
            a = s.read(1).astype(np.float64)
            if s.nodata is not None and np.isfinite(s.nodata):
                a = np.where(a == s.nodata, np.nan, a)
        # writers.raster emits origin-at-bottom; match the north-up block grid
        if a.shape != (H, W):
            raise SystemExit(f"{tid}: unexpected raster shape {a.shape}")
        out[tid] = a
        print(f"    valid {100 * np.isfinite(a).mean():.1f}%")
    return out


def mosaic_mean(tiles: dict[str, np.ndarray]) -> np.ndarray:
    """True mean across overlapping tiles (the old code used a running 0.5x)."""
    s = np.zeros((H, W)); c = np.zeros((H, W))
    for a in tiles.values():
        m = np.isfinite(a)
        s[m] += a[m]; c[m] += 1
    return np.where(c > 0, s / np.maximum(c, 1), np.nan)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse-icp", action="store_true",
                    help="reuse the cached ICP solve in the scratchpad")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    cache = WORK / "_icp_solution.json"
    if args.reuse_icp and cache.exists():
        icp = json.loads(cache.read_text())
        print(f"reusing cached ICP: dz={icp['dz']:+.4f} m")
    else:
        icp = solve_icp()
        cache.write_text(json.dumps(icp, indent=2))

    tiles = rasterise_tiles(icp["matrix"])
    ref = ref_dem_2m()

    # ---- product A: one ICP, no per-tile correction -----------------------
    old_a = mosaic_mean(tiles)
    dod_a = ref - old_a

    # ---- per-tile residual dz, measured against the 2019 reference --------
    per_tile = {}
    for tid, a in tiles.items():
        m = np.isfinite(a) & np.isfinite(ref)
        med, sd = robust((ref - a)[m])
        per_tile[tid] = {"n_px": int(m.sum()), "median_dz_m": med,
                         "robust_sd_m": sd}
        print(f"  {tid}: residual median {med:+.4f} m  sigma {sd:.4f} m  "
              f"n={m.sum():,}")
    spread = (max(v["median_dz_m"] for v in per_tile.values())
              - min(v["median_dz_m"] for v in per_tile.values()))
    print(f"  per-tile median spread: {spread:.4f} m")

    # ---- product B: also remove each tile's residual dz -------------------
    old_b = mosaic_mean({t: a + per_tile[t]["median_dz_m"]
                         for t, a in tiles.items()})
    dod_b = ref - old_b

    stats = {}
    for lbl, d in (("singleicp", dod_a), ("singleicp_tiledz", dod_b)):
        v = d[np.isfinite(d)]
        med, sd = robust(v)
        stats[lbl] = {
            "valid_pct": float(100 * np.isfinite(d).mean()),
            "median_m": med, "robust_sigma_m": sd,
            "std_m": float(v.std()),
            "p01_m": float(np.percentile(v, 1)),
            "p99_m": float(np.percentile(v, 99)),
            "frac_abs_gt_0p5": float(np.mean(np.abs(v - med) > 0.5)),
        }
        print(f"  {lbl:18s} median {med:+.4f}  robust sigma {sd:.4f}  "
              f"valid {100*np.isfinite(d).mean():.1f}%")

    # ---- the original product, for a like-for-like number -----------------
    orig = None
    op = OUT / "dod_9t_2m.tif"
    if op.exists():
        with rasterio.open(op) as s:
            o = s.read(1).astype(np.float64)
            o = np.where(np.isfinite(o), o, np.nan)
        if o.shape == (H, W):
            orig = o
            v = o[np.isfinite(o)]
            m0, s0 = robust(v)
            stats["original_2026_05_21"] = {"median_m": m0,
                                            "robust_sigma_m": s0}
            print(f"  {'original':18s} median {m0:+.4f}  robust sigma {s0:.4f}")

    write_tif(OUT / "dem_2006_singleicp_9t_2m.tif", old_a.astype(np.float32),
              transform=TRANSFORM, crs=DST_CRS, dtype="float32")
    write_tif(OUT / "dod_9t_singleicp_2m.tif", dod_a.astype(np.float32),
              transform=TRANSFORM, crs=DST_CRS, dtype="float32")
    write_tif(OUT / "dod_9t_singleicp_tiledz_2m.tif", dod_b.astype(np.float32),
              transform=TRANSFORM, crs=DST_CRS, dtype="float32")

    (OUT / "_icp_rebuild_9t.json").write_text(json.dumps({
        "bbox_epsg6346": BBOX, "res_m": RES,
        "old_crs_forced": OLD_CRS, "z_ft_to_m": Z_FT_TO_M,
        "old_tiles": list(OLD_TILES), "new_tiles": NEW_TILES,
        "new_reference_dem": "tiles/9t/dem_9t_05.tif",
        "icp": icp, "per_tile_residual": per_tile,
        "per_tile_median_spread_m": spread, "dod_stats": stats,
    }, indent=2))

    # ---- figure -----------------------------------------------------------
    panels = [(dod_a, "single ICP"), (dod_b, "single ICP + per-tile dz")]
    if orig is not None:
        panels.insert(0, (orig, "original (4 independent ICP solves)"))
    fig, axes = plt.subplots(1, len(panels), figsize=(7.2 * len(panels), 7.6))
    axes = np.atleast_1d(axes)
    ext = [BBOX[0], BBOX[2], BBOX[1], BBOX[3]]
    for ax, (d, t) in zip(axes, panels):
        im = ax.imshow(np.ma.masked_invalid(d), cmap="RdBu_r", vmin=-0.5,
                       vmax=0.5, extent=ext)
        v = d[np.isfinite(d)]
        med, sd = robust(v)
        ax.set_title(f"{t}\nmedian {med:+.3f} m, robust sigma {sd:.3f} m",
                     fontsize=11)
        ax.set_xticks([]); ax.set_yticks([])
        plt.colorbar(im, ax=ax, fraction=0.046, label="2019 - 2006/08 (m)")
    fig.suptitle("9t DoD rebuild -- one ICP solve across all four 2006-2008 "
                 "tiles, EPSG:6346, 2 m", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT / "fig_dod_9t_singleicp_vs_original.png", dpi=115)
    print(f"wrote {OUT / 'fig_dod_9t_singleicp_vs_original.png'}")
    print("DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
