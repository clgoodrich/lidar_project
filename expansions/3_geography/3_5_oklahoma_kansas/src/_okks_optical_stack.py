"""S4 (3.5). Optical and fusion stacks on the 0.5 m lidar grid.

Purpose
    1. --resample-only. Mosaic and resample NAIP (R, G, B, NIR) to the 0.5 m lidar grid (bilinear).
       Resampling adds no information. The finer grid only aligns inputs.
    2. Full run. Apply the S3 per-block shift (integer-pixel roll inside each block, sub-pixel ignored),
       add NDVI, and write the O1 stack (R, G, B, NIR, NDVI) and the F1 stack (9t lidar 7 bands + O1).
       Normalisation statistics are NOT computed here. The trainer fits them on training windows only.
Inputs
    expansions/3_geography/3_5_oklahoma_kansas/data/raw/naip/<area>/*.tif     (S1)
    data/<area>/derived/05/features_<area>_05.tif                              (core 'derive', 7 bands)
    data/<area>/results/modality/mod_coreg_shifts_<area>.csv                   (S3)
Outputs
    data/<area>/derived/05/naip_<area>_05.tif
    data/<area>/derived/05/features_optical_<area>_05.tif   (5 bands)
    data/<area>/derived/05/features_fusion_<area>_05.tif    (12 bands)
    Each new heavy subdirectory needs its own .gitignore rule (lead to add, outside this folder).
Run
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_optical_stack.py --area ok_rogers --resample-only
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_optical_stack.py --area ok_rogers
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.5"
OPT_BANDS = ["red", "green", "blue", "nir", "ndvi"]
LIDAR_BANDS = ["lrm_25", "lrm_5", "slope", "tpi_05", "openness_pos", "openness_neg", "roughness_11"]


def ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    r, n = red.astype(np.float32), nir.astype(np.float32)
    return np.where((n + r) > 0, (n - r) / (n + r + 1e-6), np.nan).astype(np.float32)


def shift_block(a: np.ndarray, dx_px: float, dy_px: float) -> np.ndarray:
    """Integer roll inside one block (edges filled with NaN)."""
    sx, sy = int(round(dx_px)), int(round(-dy_px))
    out = np.full_like(a, np.nan, dtype=np.float32)
    h, w = a.shape[-2:]
    ys, yd = (slice(0, h - sy), slice(sy, h)) if sy >= 0 else (slice(-sy, h), slice(0, h + sy))
    xs, xd = (slice(0, w - sx), slice(sx, w)) if sx >= 0 else (slice(-sx, w), slice(0, w + sx))
    out[..., yd, xd] = a[..., ys, xs]
    return out


def resample_to_grid(tiles: list[Path], ref_tif: Path, out: Path) -> Path:
    import rasterio
    from rasterio.warp import Resampling, reproject
    with rasterio.open(ref_tif) as ref:
        prof = ref.profile.copy()
        prof.update(count=4, dtype="float32", nodata=np.nan, BIGTIFF="YES")
        dst = np.full((4, ref.height, ref.width), np.nan, np.float32)
        for t in tiles:
            with rasterio.open(t) as s:
                tmp = np.full_like(dst, np.nan)
                for b in range(4):
                    reproject(rasterio.band(s, b + 1), tmp[b], dst_transform=ref.transform, dst_crs=ref.crs,
                              resampling=Resampling.bilinear, dst_nodata=np.nan)
                dst = np.where(np.isfinite(tmp), tmp, dst)
    with rasterio.open(out, "w", **prof) as d:
        d.write(dst)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    ap.add_argument("--resample-only", action="store_true")
    ap.add_argument("--no-coreg", action="store_true", help="sensitivity arm without co-registration")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    import geopandas as gpd
    import rasterio
    from rasterio.windows import from_bounds
    d05 = ek.area_dir(a.area) / "derived" / "05"
    try:
        lid = gt.require_input(d05 / f"features_{a.area}_05.tif", "7-band lidar stack (core 'derive')")
        naip_p = d05 / f"naip_{a.area}_05.tif"
        if a.resample_only:
            tiles = sorted(gt.require_input(gt.resolve(cfg["areas"][a.area]["naip_dir"]), "NAIP tiles").glob("*.tif"))
            if not tiles:
                raise gt.MissingInputError("no NAIP tiles. Run _okks_optical_coverage.py --fetch --execute")
            print(f"wrote {resample_to_grid(tiles, lid, naip_p)}")
            return 0
        gt.require_input(naip_p, "NAIP on lidar grid", "run with --resample-only first")
        shifts = None if a.no_coreg else pd.read_csv(gt.require_input(
            ek.area_dir(a.area) / "results" / "modality" / f"mod_coreg_shifts_{a.area}.csv", "S3 shifts"))
        blocks = gpd.read_file(gt.area_transfer_dir(a.area) / f"xfer_blocks_roles_{a.area}.gpkg")
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    sfx = "_nocoreg" if a.no_coreg else ""
    o_p, f_p = d05 / f"features_optical{sfx}_{a.area}_05.tif", d05 / f"features_fusion{sfx}_{a.area}_05.tif"
    with rasterio.open(lid) as rl, rasterio.open(naip_p) as rn:
        cell = rl.res[0]
        po = rl.profile.copy()
        po.update(count=5, dtype="float32", nodata=np.nan, BIGTIFF="YES")
        pf = dict(po, count=12)
        with rasterio.open(o_p, "w", **po) as do, rasterio.open(f_p, "w", **pf) as df:
            for _, b in blocks.iterrows():
                w = from_bounds(*b.geometry.bounds, rl.transform).round_offsets().round_lengths()
                img = rn.read(window=w).astype(np.float32)
                if shifts is not None:
                    s = shifts.set_index("block_id").loc[b.block_id]
                    img = shift_block(img, s.dx_m / cell, s.dy_m / cell)
                opt = np.concatenate([img, ndvi(img[0], img[3])[None]], 0)
                do.write(opt, window=w)
                df.write(np.concatenate([rl.read(window=w).astype(np.float32), opt], 0), window=w)
            for i, n in enumerate(OPT_BANDS, 1):
                do.set_band_description(i, n)
            for i, n in enumerate(LIDAR_BANDS + OPT_BANDS, 1):
                df.set_band_description(i, n)
    ek.write_provenance(d05, inputs=[lid, naip_p], outputs=[o_p, f_p], params={"coreg": not a.no_coreg})
    print(f"wrote {o_p}\nwrote {f_p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
