"""CHM age proxy v2 — regional baseline + tighter on-pad sample.

v1 failed because the per-well annulus was itself disturbed (clustered wells)
and the on-pad disk was too large. v2 changes:

1. Build a per-block "regional forest baseline" raster: at each pixel, the
   *p75 of CHM in a large neighbourhood, restricted to undisturbed forest*
   (CHM > 15 m and >30 m from any well). This represents "what the canopy
   would be here if no one had drilled."
2. Tighter on-pad sample: r=6 m disk + take the *minimum* (the actual canopy
   hole), not the mean, so partial-pad coordinates aren't averaged with
   intact canopy that happens to be inside the disk.
3. Deficit = baseline_p75 - on_pad_min.

Outputs: data/derivatives/chm_age_proxy/mckean_chm_zonal_v2.csv plus a v2
scatter PNG.
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
from scipy.ndimage import distance_transform_edt
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV

CHM_DIR = DERIV / "mosaic_3x3_mckean"
WELLS_GPKG = DERIV / "annotations" / "oil_gas_locations.gpkg"
OUT_DIR = DERIV / "chm_age_proxy"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def disk_offsets(radius_m: float, res: float = 1.0):
    r = int(np.ceil(radius_m / res))
    yy, xx = np.mgrid[-r:r+1, -r:r+1]
    d2 = yy**2 + xx**2
    return yy[d2 <= r*r], xx[d2 <= r*r]


def sample_min(arr: np.ndarray, row: int, col: int,
               dy: np.ndarray, dx: np.ndarray) -> float:
    H, W = arr.shape
    rr = row + dy; cc = col + dx
    inside = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
    if not inside.any(): return np.nan
    vals = arr[rr[inside], cc[inside]]
    finite = np.isfinite(vals)
    if finite.sum() < 3: return np.nan
    return float(np.min(vals[finite]))




def block_baseline(chm: np.ndarray, well_mask: np.ndarray,
                   *, exclude_radius_m: float, pctile: float = 75.0) -> float:
    """Single per-block forest p75: pixels with CHM > 15 m and farther than
    exclude_radius_m from any well.
    """
    dist = distance_transform_edt(~well_mask)
    forest = (chm > 15.0) & (dist > exclude_radius_m) & np.isfinite(chm)
    if forest.sum() < 1000:
        return float("nan")
    return float(np.percentile(chm[forest], pctile))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--r-on",            type=float, default=6.0)
    ap.add_argument("--exclude-radius",  type=float, default=30.0)
    args = ap.parse_args()

    blocks = []
    for sub in sorted(p for p in CHM_DIR.iterdir() if p.is_dir()):
        chm = sub / f"chm_{sub.name}_1m.tif"
        if chm.exists():
            blocks.append((sub.name, chm))
    print(f"using {len(blocks)} CHM block(s): {[b[0] for b in blocks]}")

    wells = gpd.read_file(WELLS_GPKG)
    wells = wells[(wells['COUNTY'].str.upper() == 'MCKEAN') &
                  wells['WELL_STATU'].isin(
                      ['DEP Abandoned List','DEP Orphan List','Abandoned','Orphan'])]
    if wells.crs.to_epsg() != 6346:
        wells = wells.to_crs(6346)

    dy_on, dx_on = disk_offsets(args.r_on)
    print(f"on-pad: r={args.r_on}m disk ({dy_on.size} px), reducer=min")
    print(f"baseline: scalar per-block p75 of forest (CHM>15m, >{args.exclude_radius}m from any well)")

    rows = []
    for key, path in blocks:
        with rasterio.open(path) as r:
            chm = r.read(1).astype(np.float32)
            inv = ~r.transform
            bb = r.bounds
        sub_wells = wells[wells.geometry.within(box(bb.left, bb.bottom, bb.right, bb.top))]
        if sub_wells.empty:
            print(f"[{key}] 0 wells in block, skipping baseline build")
            continue

        # Burn ALL wells (any status, to maximise exclusion) into a mask.
        all_wells_block = gpd.read_file(WELLS_GPKG)
        if all_wells_block.crs.to_epsg() != 6346:
            all_wells_block = all_wells_block.to_crs(6346)
        all_wells_block = all_wells_block[all_wells_block.geometry.within(
            box(bb.left, bb.bottom, bb.right, bb.top))]
        H, W = chm.shape
        well_mask = np.zeros((H, W), dtype=bool)
        for _, w in all_wells_block.iterrows():
            col, row = inv * (w.geometry.x, w.geometry.y)
            ri, ci = int(round(row)), int(round(col))
            if 0 <= ri < H and 0 <= ci < W:
                well_mask[ri, ci] = True
        print(f"[{key}] wells in block: orphan/aban={len(sub_wells)}  all-status={len(all_wells_block)}")

        baseline = block_baseline(chm, well_mask,
                                  exclude_radius_m=args.exclude_radius)
        print(f"[{key}] baseline p75 = {baseline:.2f} m")

        for _, w in sub_wells.iterrows():
            x, y = w.geometry.x, w.geometry.y
            col, row = inv * (x, y); ri, ci = int(round(row)), int(round(col))
            on_min = sample_min(chm, ri, ci, dy_on, dx_on)
            bl = baseline
            rows.append({
                "block": key, "permit": w.get('PERMIT_NUM'),
                "name": w.get('WELL_NAME'), "status": w.get('WELL_STATU'),
                "spud_year": w['SPUD_DATE'].year if pd.notna(w['SPUD_DATE']) else None,
                "permit_year": w['PERMIT_DAT'].year if pd.notna(w.get('PERMIT_DAT')) else None,
                "on_chm_min": on_min, "baseline_p75": bl,
                "deficit": (bl - on_min) if (np.isfinite(on_min) and np.isfinite(bl)) else np.nan,
                "x": x, "y": y,
            })

    df = pd.DataFrame(rows)
    csv = OUT_DIR / "mckean_chm_zonal_v2.csv"
    df.to_csv(csv, index=False)
    print(f"\nwrote {csv}  n={len(df)}")

    cal = df[(df['spud_year'].between(1900, 2020)) & df['deficit'].notna()].copy()
    sentinel = df[df['spud_year'].fillna(0) <= 1800]
    print(f"\ncalibration set (dated): {len(cal)}   sentinel/unknown: {len(sentinel)}")

    if len(cal) >= 5:
        r_corr = np.corrcoef(cal['spud_year'], cal['deficit'])[0, 1]
        print(f"\nspud_year vs deficit  r = {r_corr:+.3f}")
        cal['decade'] = (cal['spud_year'] // 10 * 10).astype(int)
        print("\ndeficit by spud decade:")
        print(cal.groupby('decade')['deficit'].agg(['mean','std','count']).round(2).to_string())
        print("\non-pad CHM min by spud decade:")
        print(cal.groupby('decade')['on_chm_min'].agg(['mean','std','count']).round(2).to_string())

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(cal['spud_year'], cal['deficit'], s=30, alpha=0.7, label='dated')
        if len(sentinel.dropna(subset=['deficit'])):
            sen = sentinel.dropna(subset=['deficit'])
            ax.scatter(np.full(len(sen), 1895), sen['deficit'], s=12, alpha=0.3,
                       color='red', label=f'sentinel (n={len(sen)}, plotted at 1895)')
        ax.axhline(0, color='k', lw=0.5)
        ax.set_xlabel("spud year"); ax.set_ylabel("CHM deficit (m)  = baseline_p75 - on_pad_min")
        ax.set_title(f"McKean orphan/abandoned: CHM deficit vs spud year (v2)  n_dated={len(cal)}")
        ax.legend()
        png = OUT_DIR / "deficit_vs_spudyear_v2.png"
        fig.tight_layout(); fig.savefig(png, dpi=140); plt.close(fig)
        print(f"wrote {png}")

    sen = sentinel[sentinel['deficit'].notna()]
    if len(sen):
        print(f"\nUnknown-age (sentinel) deficit distribution n={len(sen)}:")
        print(sen['deficit'].describe().round(2).to_string())
        print(f"\nCompare dated subset (1900-2020) deficit distribution n={len(cal)}:")
        print(cal['deficit'].describe().round(2).to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())
