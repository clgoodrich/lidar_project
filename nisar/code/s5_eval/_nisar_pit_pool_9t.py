"""Pits with a pool on their floor (lidar), and whether NISAR treats them differently (9t; --area 613590).

User, 2026-11-15: pad 303's pit shows a pool inside, seen at other pits too. Find those pits from lidar,
then compare the seasonal NISAR pit contrasts of pool pits with the other pits.

Pool cue from lidar, inside the inner rim (pit_inside.shp), against a ring 3-10 m outside the outer rim:
  * flat floor: share of 1 m cells with slope < 2 deg
  * weak ground return: median lidar ground intensity, floor / ring (water absorbs the 1064 nm pulse)
  * missing ground: median ground point density, floor / ring
Pool = flat share >= 0.5 and (intensity ratio <= 0.7 or density ratio <= 0.5). Thresholds are a first guess,
set before looking at the radar and reported with the results; pad 303's pit is the visual reference.

Radar: per-pit excess (feature minus decoy median, dB) from the seasonal stack,
nisar/results/<area>/nisar_gslc_stack_pit_vs_ring_and_decoys_per_feature_<area>_slc_5m.csv (5 control spots per pit).
Pool vs other pits: Mann-Whitney U per metric, and a permutation of the pool label (5000).

Writes nisar/results/<area>/nisar_pit_pool_{per_pit,radar}_<area>.csv, nisar_pit_pool_<area>.gpkg,
nisar/results/kml/nisar_pit_pool_<area>.kml
  python nisar/code/s5_eval/_nisar_pit_pool_9t.py [--area 613590]
"""
import importlib
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from scipy.stats import mannwhitneyu

sys.path.insert(0, str(Path(__file__).resolve().parent))
seas = importlib.import_module("_nisar_gslc_stack_pad_pit_seasonal_9t")
A = seas.A
ROOT = A.NISAR_ROOT.parent
D1 = ROOT / "data" / A.TAG / "derived" / "1m"
SLOPE, INT, DEN = (D1 / f"{k}_{A.TAG}_1m.tif" for k in ("slope", "intensity_ground", "ground_density"))
FLAT_MIN, INT_MAX, DEN_MAX, PERM, SEED = 0.5, 0.7, 0.5, 5000, 20261115
RES = A.NISAR_ROOT / "results" / A.TAG


def zonal(src, geom):
    try:
        a, _ = mask(src, [geom], crop=True, filled=False)
    except ValueError:
        return np.array([])
    v = a[0].compressed().astype(float)
    return v[np.isfinite(v) & (v != src.nodata)] if src.nodata is not None else v[np.isfinite(v)]


def main():
    outer = seas.read_layer(seas.ANN, "pit_outside").to_crs(seas.CRS).reset_index(drop=True)
    outer["id"] = outer.index
    with rasterio.open(SLOPE) as s:
        lcrs = s.crs
        b = s.bounds
    inner = gpd.read_file(ROOT / "qgis" / "annotations" / "pit_inside.shp").to_crs(lcrs)
    inner = inner.cx[b.left:b.right, b.bottom:b.top]
    inner["geometry"] = inner.geometry.make_valid()   # a few hand-drawn rims self-intersect
    outer_l = outer.to_crs(lcrs)
    outer_l["geometry"] = outer_l.geometry.make_valid()
    j = gpd.sjoin(inner[["geometry"]].reset_index(names="inner_row"), outer_l[["id", "geometry"]], predicate="intersects")
    j["ov"] = [g.intersection(outer_l.geometry.iloc[i]).area for g, i in zip(j.geometry, j.id)]
    j = j.sort_values("ov", ascending=False).drop_duplicates("id")   # one inner rim per outer pit, largest overlap
    rows = []
    with rasterio.open(SLOPE) as sl, rasterio.open(INT) as it, rasterio.open(DEN) as de:
        for r in j.itertuples():
            og = outer_l.geometry.iloc[r.id]
            ring = og.buffer(10).difference(og.buffer(3))
            s = zonal(sl, r.geometry)
            fi, ri = zonal(it, r.geometry), zonal(it, ring)
            fd, rd = zonal(de, r.geometry), zonal(de, ring)
            if len(s) < 3 or len(ri) < 10:
                continue
            rows.append(dict(id=int(r.id), n_floor_cells=len(s), flat_share=float(np.mean(s < 2)),
                             int_ratio=float(np.median(fi) / np.median(ri)) if len(fi) and np.median(ri) > 0 else np.nan,
                             den_ratio=float(np.median(fd) / np.median(rd)) if len(fd) and np.median(rd) > 0 else np.nan,
                             geometry=r.geometry))
    P = gpd.GeoDataFrame(rows, crs=lcrs)
    P["pool"] = (P.flat_share >= FLAT_MIN) & ((P.int_ratio <= INT_MAX) | (P.den_ratio <= DEN_MAX).fillna(False))
    print(f"{A.TAG}: {len(outer)} outer pits, {len(P)} with an inner rim and lidar stats, {int(P.pool.sum())} pool pits", flush=True)

    # 2026-11-23: reads the default 5-control-spot run (user decision); the 40-control run is a stability check
    rad = pd.read_csv(RES / f"nisar_gslc_stack_pit_vs_ring_and_decoys_per_feature_{A.TAG}_slc_5m.csv")
    mets = [c[:-8] for c in rad.columns if c.endswith("_feature")]
    for m in mets:
        rad[m] = rad[m + "_feature"] - rad[m + "_decoy_median"]
    M = P.drop(columns="geometry").merge(rad[["id"] + mets], on="id", how="inner")
    rng = np.random.default_rng(SEED)
    out = []
    for m in mets:
        a, b_ = M.loc[M.pool, m].dropna(), M.loc[~M.pool, m].dropna()
        if len(a) < 3 or len(b_) < 3:
            out.append(dict(metric=m, n_pool=len(a), n_other=len(b_)))
            continue
        d = a.median() - b_.median()
        lab = M.pool.values
        v = M[m].values
        ok = np.isfinite(v)
        null = []
        for _ in range(PERM):
            pl = rng.permutation(lab[ok])
            null.append(np.median(v[ok][pl]) - np.median(v[ok][~pl]))
        out.append(dict(metric=m, n_pool=len(a), n_other=len(b_), median_pool_db=round(a.median(), 3),
                        median_other_db=round(b_.median(), 3), diff_db=round(d, 3),
                        p_mannwhitney=round(mannwhitneyu(a, b_).pvalue, 4),
                        p_perm=round(float(np.mean(np.abs(null) >= abs(d))), 4)))
    R = pd.DataFrame(out)
    print(R.to_string(index=False))
    P.drop(columns="geometry").to_csv(RES / f"nisar_pit_pool_per_pit_{A.TAG}.csv", index=False)
    R.to_csv(RES / f"nisar_pit_pool_radar_{A.TAG}.csv", index=False)
    P.to_file(RES / f"nisar_pit_pool_{A.TAG}.gpkg", driver="GPKG")
    k = P[P.pool].to_crs(4326).copy()
    c = k.geometry.centroid
    k["Name"] = [f"{A.TAG}_pool_pit_{i}" for i in k.id]
    k["Description"] = [f"flat {f:.2f}, intensity ratio {a:.2f}, density ratio {d:.2f}. Centroid {y:.6f}, {x:.6f}"
                        for f, a, d, x, y in zip(k.flat_share, k.int_ratio, k.den_ratio, c.x, c.y)]
    k[["Name", "Description", "geometry"]].to_file(A.NISAR_ROOT / "results" / "kml" / f"nisar_pit_pool_{A.TAG}.kml", driver="KML")


if __name__ == "__main__":
    main()
