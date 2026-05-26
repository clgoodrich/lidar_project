"""CHM-vs-spud-year calibration for McKean abandoned/orphan wells.

For each well in the McKean 3x3 CHM coverage with a real SPUD_DATE (i.e. year
> 1800 sentinel), compute:
  - on_chm  : mean CHM in a small disk around the well point (~"on pad")
  - off_chm : mean CHM in an annulus farther out ("off pad", background canopy)
  - deficit : off - on   (positive = canopy is suppressed at the well)

Then fit deficit -> spud_year and report calibration quality. Outputs both a
CSV of per-well rows and a quick scatter PNG.

CLI:
  python notebooks/wellsight/analysis/_chm_age_proxy.py
  python notebooks/wellsight/analysis/_chm_age_proxy.py --r-on 15 --r-off 35
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, ROOT

CHM_DIR = DERIV / "mosaic_3x3_mckean"
WELLS_GPKG = DERIV / "annotations" / "oil_gas_locations.gpkg"
OUT_DIR = DERIV / "chm_age_proxy"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_chm_blocks() -> list[tuple[str, Path, tuple[float, float, float, float]]]:
    """Return [(key, path, bbox_utm17n), ...] for every CHM raster found."""
    out = []
    for sub in sorted(p for p in CHM_DIR.iterdir() if p.is_dir()):
        chm = sub / f"chm_{sub.name}_1m.tif"
        if chm.exists():
            with rasterio.open(chm) as r:
                b = r.bounds
            out.append((sub.name, chm, (b.left, b.bottom, b.right, b.top)))
    return out


def disk_offsets(radius_m: float, res: float = 1.0):
    r = int(np.ceil(radius_m / res))
    yy, xx = np.mgrid[-r:r+1, -r:r+1]
    d2 = yy**2 + xx**2
    return yy[d2 <= r*r], xx[d2 <= r*r]


def annulus_offsets(r_in_m: float, r_out_m: float, res: float = 1.0):
    r = int(np.ceil(r_out_m / res))
    yy, xx = np.mgrid[-r:r+1, -r:r+1]
    d2 = yy**2 + xx**2
    mask = (d2 > (r_in_m/res)**2) & (d2 <= (r_out_m/res)**2)
    return yy[mask], xx[mask]


def sample_mean(arr: np.ndarray, row: int, col: int,
                dy: np.ndarray, dx: np.ndarray) -> float:
    H, W = arr.shape
    rr = row + dy
    cc = col + dx
    inside = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
    if not inside.any():
        return np.nan
    vals = arr[rr[inside], cc[inside]]
    finite = np.isfinite(vals)
    if finite.sum() < 3:
        return np.nan
    return float(np.mean(vals[finite]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--r-on",   type=float, default=12.0, help="on-pad radius (m)")
    ap.add_argument("--r-in",   type=float, default=25.0, help="annulus inner (m)")
    ap.add_argument("--r-out",  type=float, default=45.0, help="annulus outer (m)")
    args = ap.parse_args()

    blocks = load_chm_blocks()
    if not blocks:
        print("no CHM rasters", file=sys.stderr); return 1
    print(f"using {len(blocks)} CHM block(s): {[b[0] for b in blocks]}")

    wells = gpd.read_file(WELLS_GPKG)
    wells = wells[(wells['COUNTY'].str.upper() == 'MCKEAN') &
                  wells['WELL_STATU'].isin(
                      ['DEP Abandoned List','DEP Orphan List','Abandoned','Orphan'])]
    if wells.crs.to_epsg() != 6346:
        wells = wells.to_crs(6346)

    dy_on, dx_on = disk_offsets(args.r_on)
    dy_off, dx_off = annulus_offsets(args.r_in, args.r_out)
    print(f"kernels: on disk r={args.r_on}m ({dy_on.size} px), "
          f"off annulus {args.r_in}-{args.r_out}m ({dy_off.size} px)")

    rows = []
    for key, path, bb in blocks:
        sub = wells[wells.geometry.within(box(*bb))]
        if sub.empty:
            continue
        with rasterio.open(path) as r:
            arr = r.read(1).astype(np.float32)
            inv = ~r.transform
        for _, w in sub.iterrows():
            x, y = w.geometry.x, w.geometry.y
            col, row = inv * (x, y)
            r_i, c_i = int(round(row)), int(round(col))
            on = sample_mean(arr, r_i, c_i, dy_on, dx_on)
            off = sample_mean(arr, r_i, c_i, dy_off, dx_off)
            spud_year = w['SPUD_DATE'].year if pd.notna(w['SPUD_DATE']) else None
            rows.append({
                "block": key,
                "permit": w.get('PERMIT_NUM'),
                "name": w.get('WELL_NAME'),
                "status": w.get('WELL_STATU'),
                "spud_year": spud_year,
                "permit_year": w['PERMIT_DAT'].year if pd.notna(w.get('PERMIT_DAT')) else None,
                "oldest_for": w.get('OLDEST_FOR'),
                "on_chm": on, "off_chm": off,
                "deficit": (off - on) if (np.isfinite(on) and np.isfinite(off)) else np.nan,
                "x": x, "y": y,
            })

    df = pd.DataFrame(rows)
    csv = OUT_DIR / "mckean_chm_zonal.csv"
    df.to_csv(csv, index=False)
    print(f"wrote {csv}  n={len(df)}")

    # Calibration subset: real spud year (drop sentinel + null).
    cal = df[(df['spud_year'].between(1900, 2020)) & df['deficit'].notna()].copy()
    sentinel = df[df['spud_year'].fillna(0) <= 1800]
    print(f"\ncalibration set (real spud_year, deficit non-null): {len(cal)}")
    print(f"sentinel/unknown rows:                                {len(sentinel)}")

    if len(cal) >= 5:
        r = np.corrcoef(cal['spud_year'], cal['deficit'])[0, 1]
        print(f"\nspud_year vs deficit  r = {r:+.3f}")
        # Group by decade for legibility:
        cal['decade'] = (cal['spud_year'] // 10 * 10).astype(int)
        print("\ndeficit by spud decade (mean ± std, n):")
        print(cal.groupby('decade')['deficit'].agg(['mean','std','count']).to_string())
        print("\non-pad CHM by spud decade:")
        print(cal.groupby('decade')['on_chm'].agg(['mean','std','count']).to_string())

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(cal['spud_year'], cal['deficit'], s=24, alpha=0.7)
        ax.axhline(0, color='k', lw=0.5)
        ax.set_xlabel("spud year")
        ax.set_ylabel("CHM deficit (m)  = off-pad - on-pad")
        ax.set_title(f"McKean orphan/abandoned: CHM deficit vs spud year  (n={len(cal)})")
        png = OUT_DIR / "deficit_vs_spudyear.png"
        fig.tight_layout(); fig.savefig(png, dpi=140); plt.close(fig)
        print(f"\nwrote {png}")

    # And: distribution of deficit among the sentinel (unknown-age) wells.
    sen = sentinel[sentinel['deficit'].notna()]
    if len(sen):
        print(f"\nUnknown-age wells (spud=1800) deficit distribution n={len(sen)}:")
        print(sen['deficit'].describe().to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())
