"""Small-metal detection, first experiment, scored against the annotated well pits instead of DEP wells.

Same stack, CFAR, water mask and D_A test as _s1_metal_cfar_9t.py (imported, not copied). Only the targets
and the baselines change.

Targets. The user's lidar pit annotations, `qgis/annotations/pit_full.shp` (outer rim), inside the radar window
and outside the water buffer. Pits are annotated only inside the 9t and 613590 lidar tiles, so the random points
and the local decoys are drawn inside those two tiles as well; anything else would compare annotated ground with
unannotated ground.

Two hit rules, both reported:
  * ellipse  : a candidate within 10 m (x) by 20 m (y) of the pit centroid (the DEP-well rule);
  * polygon  : a candidate inside the pit outline buffered by 10 m (pits are 10 to 40 m across).
Decoys are same-shape copies of each pit moved 150 to 600 m, kept inside the tile and 30 m clear of every pit,
so the polygon rule has a like-for-like baseline. Random points use the ellipse rule only.

  python notebooks/wellsight_v2/s5_eval/_s1_metal_pits_9t.py
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import ndimage
from scipy.stats import gamma
from shapely.affinity import translate
from shapely.geometry import box

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _s1_metal_cfar_9t as M  # noqa: E402

PITS = M.ROOT / "qgis" / "annotations" / "pit_full.shp"
# lidar tile extents, EPSG:6346; NAD83(2011) and WGS84 UTM 17N differ by about 1 m here, below the pixel
TILES = {"9t": box(619500, 4593000, 624000, 4597500), "613590": box(613500, 4590000, 618000, 4594500)}
POLY_BUF = 10.0


def main():
    rng = np.random.default_rng(M.SEED)
    dates, tf, mean_i, da = M.load()
    water = M.water_mask(mean_i)
    buf = ndimage.binary_dilation(water, np.ones((2 * int(M.WATER_BUFFER_M / 10) + 1, 2 * int(M.WATER_BUFFER_M / 5) + 1)))
    scr = M.cfar_scr(mean_i, water)
    scr[buf] = np.nan
    core = scr[np.isfinite(scr)]
    lo, hi = np.percentile(core, [1, 99])
    L = 1.0 / np.var(core[(core > lo) & (core < hi)])
    T = float(gamma.isf(M.PFA, L, scale=1 / L))
    valid = np.isfinite(scr)
    inv = ~tf
    tiles = gpd.GeoSeries(list(TILES.values()), crs=6346).to_crs(32617)
    tile_union = tiles.union_all()

    def inside(x, y):
        c, r = inv * (np.asarray(x, float), np.asarray(y, float))
        c, r = np.floor(c).astype(int), np.floor(r).astype(int)
        m = (r >= 0) & (r < scr.shape[0]) & (c >= 0) & (c < scr.shape[1])
        out = np.zeros(len(m), bool)
        out[m] = valid[r[m], c[m]]
        return out

    P = gpd.read_file(PITS).to_crs(32617)
    cen = P.geometry.centroid
    P = P[inside(cen.x, cen.y) & cen.within(tile_union)].reset_index(drop=True)
    cen = P.geometry.centroid
    px, py = cen.x.values, cen.y.values
    P["tile"] = ["9t" if c.within(tiles.iloc[0]) else "613590" for c in cen]
    print(f"{len(P)} pits ({(P.tile == '9t').sum()} on 9t, {(P.tile == '613590').sum()} on 613590)")

    # random points inside the tiles
    bx = tiles.total_bounds
    rx, ry = rng.uniform(bx[0], bx[2], 200000), rng.uniform(bx[1], bx[3], 200000)
    keep = inside(rx, ry) & gpd.GeoSeries(gpd.points_from_xy(rx, ry), crs=32617).within(tile_union).values
    rx, ry = rx[keep][:20000], ry[keep][:20000]

    # same-shape decoys, one per pit, inside the same tile, 30 m clear of every pit
    pit_zone = P.geometry.buffer(30).union_all()
    decoys = []
    for g, t in zip(P.geometry, P.tile):
        tb = tiles.iloc[0] if t == "9t" else tiles.iloc[1]
        d = None
        for _ in range(200):
            ang, dist = rng.uniform(0, 2 * np.pi), rng.uniform(150, 600)
            q = translate(g, dist * np.cos(ang), dist * np.sin(ang))
            qc = q.centroid
            if q.within(tb) and not q.intersects(pit_zone) and inside([qc.x], [qc.y])[0]:
                d = q
                break
        decoys.append(d)
    D = gpd.GeoDataFrame(geometry=[d for d in decoys if d is not None], crs=32617)
    dcen = D.geometry.centroid

    def poly_hit(geoms, cx, cy):
        if len(cx) == 0:
            return np.zeros(len(geoms), bool)
        pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(cx, cy), crs=32617)
        g = gpd.GeoDataFrame(geometry=geoms.buffer(POLY_BUF).values, crs=32617).reset_index(names="i")
        j = gpd.sjoin(g, pts, predicate="contains", how="inner")
        out = np.zeros(len(geoms), bool)
        out[j.i.unique()] = True
        return out

    def da_at(x, y):
        c, r = inv * (x, y)
        return da[np.floor(r).astype(int), np.floor(c).astype(int)]

    rows, cand_main = [], None
    levels = [("P_fa 1e-6", T)] + [(f"{d} dB", 10 ** (d / 10)) for d in (3, 4, 5, 6, 8, 10)]
    for name, thr in levels:
        cand = M.candidates(scr, thr, tf)
        if len(cand):
            cand["da"] = da_at(cand.x.values, cand.y.values)
        if name == "P_fa 1e-6":
            cand_main = cand
        for cname, cc in (("CFAR", cand), ("CFAR + D_A<0.25", cand[cand.da < M.DA_MAX] if len(cand) else cand)):
            cx, cy = (cc.x.values, cc.y.values) if len(cc) else (np.array([]), np.array([]))
            in_tiles = gpd.GeoSeries(gpd.points_from_xy(cx, cy), crs=32617).within(tile_union).values if len(cx) else np.array([], bool)
            pe, pp = M.hit(px, py, cx, cy), poly_hit(P.geometry, cx, cy)
            re_, de, dp = M.hit(rx, ry, cx, cy), M.hit(dcen.x.values, dcen.y.values, cx, cy), poly_hit(D.geometry, cx, cy)
            rows.append(dict(threshold=name, thr_db=round(10 * np.log10(thr), 2), test=cname,
                             n_candidates_in_tiles=int(in_tiles.sum()),
                             pits_ellipse=round(pe.mean(), 4), random_ellipse=round(re_.mean(), 4),
                             decoys_ellipse=round(de.mean(), 4),
                             pits_polygon=round(pp.mean(), 4), decoys_polygon=round(dp.mean(), 4),
                             n_pits_hit_polygon=int(pp.sum()), n_decoys_hit_polygon=int(dp.sum()),
                             pits_polygon_9t=round(pp[(P.tile == "9t").values].mean(), 4),
                             pits_polygon_613590=round(pp[(P.tile == "613590").values].mean(), 4)))
    res = pd.DataFrame(rows)
    res.to_csv(M.OUT / f"s1_metal_pits_hit_rates_{M.TAG}.csv", index=False)
    with pd.option_context("display.width", 250):
        print(res.to_string())

    cx, cy = cand_main.x.values, cand_main.y.values
    P["cfar_hit_ellipse"] = M.hit(px, py, cx, cy)
    P["cfar_hit_polygon"] = poly_hit(P.geometry, cx, cy)
    P["da_at_centroid"] = da_at(px, py)
    c, r = inv * (px, py)
    P["scr_db_at_centroid"] = 10 * np.log10(scr[np.floor(r).astype(int), np.floor(c).astype(int)])
    P[["tile", "cfar_hit_ellipse", "cfar_hit_polygon", "da_at_centroid", "scr_db_at_centroid", "geometry"]] \
        .to_file(M.OUT / f"s1_metal_pits_scored_{M.TAG}.gpkg", driver="GPKG")

    main_row = res.iloc[0]
    summary = dict(dates=len(dates), threshold_db=round(10 * np.log10(T), 2), enl=round(L, 2),
                   pits=int(len(P)), pits_9t=int((P.tile == "9t").sum()), pits_613590=int((P.tile == "613590").sum()),
                   decoys=int(len(D)), random_points=int(len(rx)), polygon_buffer_m=POLY_BUF,
                   hit_ellipse_m=[M.HIT_X, M.HIT_Y],
                   candidates_in_tiles=int(main_row.n_candidates_in_tiles),
                   steady_candidates_in_tiles=int(res.iloc[1].n_candidates_in_tiles),
                   pits_polygon=float(main_row.pits_polygon), decoys_polygon=float(main_row.decoys_polygon),
                   pits_ellipse=float(main_row.pits_ellipse), random_ellipse=float(main_row.random_ellipse),
                   median_da_at_pits=round(float(np.nanmedian(P.da_at_centroid)), 3),
                   median_scr_db_at_pits=round(float(np.nanmedian(P.scr_db_at_centroid)), 2))
    json.dump(summary, open(M.OUT / f"s1_metal_pits_summary_{M.TAG}.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))

    # figure: the two tiles, pits as blue outlines, candidates as orange plus signs
    amp_db = 10 * np.log10(mean_i)
    vmin, vmax = np.nanpercentile(amp_db, [2, 99.5])
    x0, y1 = tf * (0, 0)
    x1, y0 = tf * (scr.shape[1], scr.shape[0])
    fig, axs = plt.subplots(1, 2, figsize=(12.5, 6.4))
    for ax, (name, tb) in zip(axs, zip(TILES, tiles)):
        ax.imshow(amp_db, cmap="gray", vmin=vmin, vmax=vmax, extent=(x0, x1, y0, y1), interpolation="nearest")
        P[P.tile == name].boundary.plot(ax=ax, color=M.WELL_C, linewidth=0.9)
        sel = [tb.contains(gpd.points_from_xy([a], [b])[0]) for a, b in zip(cx, cy)]
        ax.scatter(cx[sel], cy[sel], s=40, marker="+", color=M.CAND_C, linewidths=1.4)
        b = tb.bounds
        ax.set_xlim(b[0], b[2]); ax.set_ylim(b[1], b[3]); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{name}: {(P.tile == name).sum()} pits, {sum(sel)} candidates", fontsize=10, color=M.INK)
    axs[0].plot([], [], color=M.WELL_C, label="annotated pits (outer rim)")
    axs[0].scatter([], [], marker="+", color=M.CAND_C, label="CFAR candidates, P_fa 1e-6")
    axs[0].legend(loc="lower left", fontsize=8, framealpha=0.9)
    fig.suptitle(f"Sentinel-1 track 77, {len(dates)} dates: bright-target candidates against annotated pits",
                 fontsize=11, color=M.INK)
    fig.tight_layout()
    fig.savefig(M.OUT / f"s1_metal_pits_map_{M.TAG}.png", dpi=170)


if __name__ == "__main__":
    main()
