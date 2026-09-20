"""Build the 7-band pit feature stack on SMRF ground instead of vendor ground.

WHY
---
Everything the Data QA work has shown is about the INPUT. The open question --
top of BACKLOG.md since the SMRF run -- is whether any of it reaches the OUTPUT.
Until a model is trained on a stack built from the recovered ground and scored
on the same folds, the honest answer is that the 18 degree cut may have cost us
nothing we needed.

This builds the other half of that comparison. The vendor-ground stack already
exists as `features_pit_9t_05.tif`; this writes `features_pit_smrf_9t_05.tif`
on exactly the same grid, from exactly the same code path, with the ONLY
difference being which points are classified ground.

HOW THE COMPARISON IS KEPT HONEST
---------------------------------
1. The same SMRF pipeline as `_recovered_ground_maps_9t.py` -- ferry, hag_nn,
   outlier, smrf(cell 1.0, slope 0.35, window 18.0, threshold 0.5, scalar
   1.25) -- writes classified LAZ per map square.
2. `_build_derivatives.py` then runs on those, unmodified. It selects ground
   with `filters.range Classification[2:2]`, so feeding it SMRF output is the
   whole intervention. Using the project's own builder rather than
   reimplementing slope/LRM/openness is the point: a difference in the
   derivative maths would confound the result.
3. The stack is written on the SAME grid as the vendor stack (checked, not
   assumed) so labels, blocks and patches line up without resampling.
4. Normalisation statistics are computed over TRAIN blocks only, from the same
   `pit_blocks_9t.gpkg`, the same way `archive/_stack_features.py` did.

LARGE FILES
-----------
The intermediate derivatives are ~140 MB each and the classified LAZ another
~2 GB. Everything lands under `data/9t/derived/smrf05/`, which is gitignored in
the same change that added this script, per the large-file rule in CLAUDE.md.

Run:
    python notebooks/wellsight_v2/s7_analysis/_smrf_feature_stack_9t.py
    python notebooks/wellsight_v2/s7_analysis/_smrf_feature_stack_9t.py --skip-smrf
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
DST = ROOT / "data/9t/derived/smrf05"
LAZ = DST / "_laz"
D05 = ROOT / "data/9t/derived/05"
BUILDER = ROOT / "notebooks/wellsight_v2/s1_build/_build_derivatives.py"
PDAL = "pdal"

BBOX = (619500.0, 4593000.0, 624000.0, 4597500.0)
RES = 0.5
SFX = "smrf9t_05"
TILES = ["619593", "619594", "619596", "621593", "621594", "621596",
         "622593", "622594", "622596"]

#: Same order as the vendor stack. Names must match DEFAULT_CHANNELS in _dl.py.
CHANNELS = ["lrm_25", "lrm_5", "slope", "tpi_05",
            "openness_pos", "openness_neg", "roughness_11"]


def run_pipeline(stages, label, timeout=1800):
    """PDAL CLI via a temp pipeline file. The Python bindings do not work here."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f)
        tmp = f.name
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError(f"{label}: {r.stderr[-400:]}")
    return r


def smrf_one(code, slope=0.35):
    out = LAZ / f"smrf_{code}.laz"
    if out.exists():
        return f"{code} cached"
    src = next(SRC.glob(f"*{code}.laz"))
    run_pipeline([
        str(src),
        {"type": "filters.ferry", "dimensions": "Classification=>VendorClass"},
        {"type": "filters.hag_nn", "count": 8, "allow_extrapolation": True},
        {"type": "filters.outlier", "method": "statistical", "mean_k": 8,
         "multiplier": 3.0},
        {"type": "filters.smrf", "cell": 1.0, "slope": slope, "window": 18.0,
         "threshold": 0.5, "scalar": 1.25, "ignore": "Classification[7:7]"},
        {"type": "writers.las", "filename": str(out), "compression": "true"},
    ], f"smrf {code}")
    return f"{code} {out.stat().st_size/1e6:.0f} MB"


def build_derivatives():
    cmd = [sys.executable, str(BUILDER),
           "--tiles", str(LAZ / "smrf_*.laz"),
           "--bbox", ",".join(f"{v:.0f}" for v in BBOX),
           "--suffix", SFX, "--res", str(RES),
           "--out-dir", str(DST)]
    print("  " + " ".join(cmd))
    r = subprocess.run(cmd, text=True)
    if r.returncode != 0:
        raise SystemExit("derivative build failed")


def build_roughness_11():
    """The one channel `_build_derivatives.py` does not write at 0.5 m.

    The builder writes `roughness_5` (stdev of the DEM in a 5x5 window). The
    vendor stack's seventh channel is `roughness_11`, an 11x11 window, and at
    0.5 m those are NOT the same surface -- checked, not assumed:

        recomputed 5x5  vs vendor roughness_11:  corr 0.568, means 0.076/0.151
        recomputed 11x11 vs vendor roughness_11: corr 0.996, mean |diff| 0.0013

    (Sampled over a 900x900 window of `dem_9t_05.tif`. The residual is edge and
    nodata handling.) BACKLOG B5 records roughness_11 as a mislabel of
    roughness_5 -- that is true at 1 m, where a 5-cell window spans the same
    ground as 11 cells at 0.5 m. It is not true here.

    Substituting roughness_5 would have changed channel 7 between the two arms
    and confounded the whole SMRF comparison, so this reproduces the 11x11
    window with the builder's own formula instead.
    """
    from scipy import ndimage as ndi

    out = DST / f"roughness_11_{SFX}.tif"
    if out.exists():
        print(f"  roughness_11 already present: {out}")
        return
    src = DST / f"dem_{SFX}.tif"
    print(f"  roughness_11 (11x11 stdev) from {src.name}")
    with rasterio.open(src) as r:
        dem = r.read(1).astype("float32")
        profile = r.profile.copy()
        if r.nodata is not None and np.isfinite(r.nodata):
            dem[dem == r.nodata] = np.nan

    WIN = 11
    k = np.ones((WIN, WIN), dtype=np.float32)
    v = np.isfinite(dem).astype(np.float32)
    z0 = np.where(v.astype(bool), dem, 0).astype(np.float32)
    s = ndi.convolve(z0, k, mode="nearest")
    s2 = ndi.convolve(z0 * z0, k, mode="nearest")
    n = ndi.convolve(v, k, mode="nearest")
    var = np.where(n > 1, (s2 - s * s / np.maximum(n, 1)) / np.maximum(n - 1, 1),
                   np.nan)
    rough = np.sqrt(np.clip(var, 0, None)).astype(np.float32)
    rough[n < WIN * WIN] = np.nan

    profile.update(count=1, dtype="float32", compress="deflate", predictor=3,
                   tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES",
                   nodata=np.nan)
    with rasterio.open(out, "w", **profile) as d:
        d.write(rough, 1)
    print(f"  wrote {out}  (mean {np.nanmean(rough):.4f})")


def stack():
    """Seven bands onto one grid, with train-block statistics beside them."""
    import geopandas as gpd
    from rasterio.features import rasterize

    build_roughness_11()
    paths = [(c, DST / f"{c}_{SFX}.tif") for c in CHANNELS]
    missing = [str(p) for _, p in paths if not p.exists()]
    if missing:
        raise SystemExit("missing derivatives:\n  " + "\n  ".join(missing))

    ref = D05 / "features_pit_9t_05.tif"
    with rasterio.open(paths[0][1]) as r0:
        profile, H, W, T = r0.profile.copy(), r0.height, r0.width, r0.transform
    with rasterio.open(ref) as rr:
        if (rr.height, rr.width) != (H, W) or not np.allclose(
                np.array(rr.transform)[:6], np.array(T)[:6], atol=1e-6):
            raise SystemExit(
                f"grid mismatch against the vendor stack\n"
                f"  vendor {rr.width}x{rr.height} {rr.transform}\n"
                f"  smrf   {W}x{H} {T}\n"
                f"  the comparison is only valid on one grid")
    print(f"  grid matches the vendor stack: {W} x {H} @ {RES} m")

    blocks = gpd.read_file(D05 / "pit_blocks_9t.gpkg")
    tr = blocks[blocks["split"] == "train"]
    mask = rasterize([(g, 1) for g in tr.geometry], out_shape=(H, W),
                     transform=T, fill=0, dtype="uint8").astype(bool)
    print(f"  train mask {mask.mean()*100:.1f}% of the tile")

    out = DST / "features_pit_smrf_9t_05.tif"
    profile.update(count=len(paths), dtype="float32", compress="deflate",
                   predictor=3, tiled=True, blockxsize=512, blockysize=512,
                   BIGTIFF="YES", nodata=np.nan)
    stats = {}
    with rasterio.open(out, "w", **profile) as dst:
        for i, (name, p) in enumerate(paths, start=1):
            with rasterio.open(p) as r:
                a = r.read(1).astype("float32")
                if r.nodata is not None and np.isfinite(r.nodata):
                    a[a == r.nodata] = np.nan
            dst.write(a, i)
            dst.set_band_description(i, name)
            v = a[mask & np.isfinite(a)]
            stats[name] = {"mean": float(v.mean()), "std": float(v.std())}
            print(f"  band {i} {name:14s} mean {v.mean():9.4f}  "
                  f"std {v.std():8.4f}  ({100*np.isfinite(a).mean():.1f}% finite)")
    sp = DST / "feature_stats_smrf.json"
    sp.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"\n  {out}  ({out.stat().st_size/1e6:.0f} MB)")
    print(f"  {sp}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-smrf", action="store_true")
    ap.add_argument("--skip-derivatives", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--slope", type=float, default=0.35)
    a = ap.parse_args()
    LAZ.mkdir(parents=True, exist_ok=True)

    if not a.skip_smrf:
        print(f"SMRF on {len(TILES)} map squares, {a.workers} at a time")
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            for msg in ex.map(smrf_one, TILES, [a.slope] * len(TILES)):
                print(f"  {msg}")
    if not a.skip_derivatives:
        print("\nderivatives from the SMRF ground")
        build_derivatives()
    print("\nstacking")
    stack()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
