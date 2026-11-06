"""S3 (3.5). Per-block co-registration of imagery to lidar-derived edges.

Purpose
    NAIP horizontal accuracy is metres, the target features are 5 to 10 m. Estimate a per-block
    shift of imagery to lidar by phase correlation between an imagery edge map (gradient magnitude of
    the NIR or green band) and a lidar edge map (slope or hillshade gradient) on the same 0.5 m grid.
    Sub-pixel peak by parabolic fit. The same shift is applied to O1 and F1 inputs (S4). Fusion without
    co-registration is a sensitivity arm. Shifts above the prereg tolerance are flagged.
Inputs
    data/<area>/derived/05/slope_<area>_05.tif                       (core 'derive')
    data/<area>/derived/05/naip_<area>_05.tif                        (S4 --resample-only output)
    data/<area>/results/transfer/xfer_blocks_roles_<area>.gpkg
Outputs
    data/<area>/results/modality/mod_coreg_shifts_<area>.csv  (block_id, dx_m, dy_m, peak, over_tol)
Run
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_coreg_optical.py --area ok_rogers
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


def edges(a: np.ndarray) -> np.ndarray:
    a = np.where(np.isfinite(a), a, np.nanmedian(a))
    gy, gx = np.gradient(a.astype(np.float64))
    e = np.hypot(gx, gy)
    return (e - e.mean()) / (e.std() + 1e-12)


def phase_correlation(ref: np.ndarray, mov: np.ndarray) -> tuple[float, float, float]:
    """Shift (dy, dx) in pixels that moves `mov` onto `ref`, and the normalised peak height."""
    h, w = ref.shape
    win = np.outer(np.hanning(h), np.hanning(w))
    F1, F2 = np.fft.fft2(ref * win), np.fft.fft2(mov * win)
    R = F1 * np.conj(F2)
    R /= np.abs(R) + 1e-12
    c = np.fft.ifft2(R).real
    py, px = np.unravel_index(np.argmax(c), c.shape)

    def sub(cm, c0, cp):
        d = cm - 2 * c0 + cp
        return 0.0 if d == 0 else 0.5 * (cm - cp) / d
    dy = py + sub(c[(py - 1) % h, px], c[py, px], c[(py + 1) % h, px])
    dx = px + sub(c[py, (px - 1) % w], c[py, px], c[py, (px + 1) % w])
    dy = dy - h if dy > h / 2 else dy
    dx = dx - w if dx > w / 2 else dx
    return float(dy), float(dx), float(c[py, px])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    ap.add_argument("--band", type=int, default=4, help="imagery band for edges (4 = NIR)")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    import geopandas as gpd
    import rasterio
    from rasterio.windows import from_bounds
    d05 = ek.area_dir(a.area) / "derived" / "05"
    try:
        lid = gt.require_input(d05 / f"slope_{a.area}_05.tif", "0.5 m slope (core 'derive')")
        img = gt.require_input(d05 / f"naip_{a.area}_05.tif", "NAIP on the 0.5 m lidar grid (S4 --resample-only)")
        blocks = gpd.read_file(gt.require_input(gt.area_transfer_dir(a.area) / f"xfer_blocks_roles_{a.area}.gpkg",
                                                "block roles"))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    tol = cfg["prereg"].get("registration_tol_m")
    rows = []
    with rasterio.open(lid) as rl, rasterio.open(img) as ri:
        ek.assert_crs(rl, blocks.crs)
        ek.assert_crs(ri, blocks.crs)
        cell = rl.res[0]
        for _, b in blocks.iterrows():
            w = from_bounds(*b.geometry.bounds, rl.transform).round_offsets().round_lengths()
            dy, dx, pk = phase_correlation(edges(rl.read(1, window=w)), edges(ri.read(a.band, window=w)))
            dist = float(np.hypot(dx, dy) * cell)
            rows.append({"block_id": b.block_id, "dx_m": dx * cell, "dy_m": -dy * cell, "shift_m": dist,
                         "peak": pk, "over_tol": None if tol is None else dist > tol})
    df = pd.DataFrame(rows)
    out = ek.area_dir(a.area) / "results" / "modality" / f"mod_coreg_shifts_{a.area}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(df["shift_m"].describe().to_string(), f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
