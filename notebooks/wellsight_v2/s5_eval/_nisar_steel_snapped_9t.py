"""Steel test again, with DEP wells snapped to lidar-verified pits and pads (9t).

The first steel test (_nisar_steel_9t.py) scored the raw DEP April 2026 coordinates. DEP positions
are unreliable, so a miss there could be a location error. Here each DEP well is moved to the
centroid of the nearest annotated pit (layer pit_outside) or pad (layer plat) within SNAP_M.
Annotations were drawn on the lidar, so their positions are trustworthy.

Three comparisons, same steady-bright-target maps and rule as the first test (D_A < 0.25, >= 6 dB
above the 250 m median, within R_M):
  1. Snapped wells vs their own raw DEP positions (same wells, two locations).
  2. Snapped wells vs control features: annotated pits/pads with no DEP well within SNAP_M.
     This controls for setting, because a pad is already open ground near a road.
  3. The same at a wider radius (R_WIDE), to allow for stack-to-lidar offset.
Fisher exact test on hit rates, Mann-Whitney on brightness.

  python notebooks/wellsight_v2/s5_eval/_nisar_steel_snapped_9t.py
"""
import importlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter
from scipy.stats import fisher_exact, mannwhitneyu

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
steel = importlib.import_module("_nisar_steel_9t")
st, ifg = steel.st, steel.ifg
read_layer = steel.read_layer
OUT, CRS, ANN, AREA = steel.OUT, steel.CRS, steel.ANN, steel.AREA
SNAP_M, R_WIDE = 40.0, 25.0


def scores(maps, pts, tf, shape, r_m):
    """Tracks with an SBT within r_m, and mean over tracks of the brightest pixel within r_m."""
    r = int(np.ceil(r_m / 5))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    fp = (xx ** 2 + yy ** 2) * 25 <= r_m ** 2
    col = ((pts.x.values - tf.c) / tf.a).astype(int)
    row = ((pts.y.values - tf.f) / tf.e).astype(int)
    n, b = np.zeros(len(pts), int), []
    for m in maps.values():
        n += maximum_filter(m["sbt"].astype(np.uint8), footprint=fp).astype(bool)[row, col]
        b.append(maximum_filter(np.nan_to_num(m["bright"], nan=-99), footprint=fp)[row, col])
    return n, np.mean(b, 0)


def compare(a_n, a_b, c_n, c_b):
    ha, hc = a_n >= 1, c_n >= 1
    orr, p = fisher_exact([[ha.sum(), (~ha).sum()], [hc.sum(), (~hc).sum()]])
    return dict(n_a=len(a_n), n_b=len(c_n), hit_a=round(float(ha.mean()), 3), hit_b=round(float(hc.mean()), 3),
                odds_ratio=round(float(orr), 2), p_hit=float(f"{p:.2g}"),
                bright_median_a=round(float(np.median(a_b)), 2), bright_median_b=round(float(np.median(c_b)), 2),
                p_bright=float(f"{mannwhitneyu(a_b, c_b).pvalue:.2g}"))


def main():
    idx, stack, tf, shape = ifg.load_complex()
    maps = steel.sbt_maps(idx, stack, shape)
    cover = st.canopy_cover(tf, shape)
    valid = np.isfinite(cover) & np.all([m["ok"] for m in maps.values()], axis=0)
    x0, y1 = tf.c, tf.f
    x1, y0 = x0 + shape[1] * 5, y1 - shape[0] * 5

    def inside(pts):
        c = ((pts.x.values - tf.c) / tf.a).astype(int)
        r = ((pts.y.values - tf.f) / tf.e).astype(int)
        ok = (r >= 5) & (r < shape[0] - 5) & (c >= 5) & (c < shape[1] - 5)
        ok[ok] = valid[r[ok], c[ok]]
        return ok

    w = gpd.read_file(steel.WELLS).to_crs(CRS)
    w["group"] = None
    for k, v in steel.GROUPS.items():
        w.loc[w.WELL_STATU.isin(v), "group"] = k
    w = w[w.group.notna() & (w.group != "not_drilled")].cx[x0:x1, y0:y1].reset_index(drop=True)

    pits = read_layer(ANN, "pit_outside").to_crs(CRS)
    pads = read_layer(ANN, "plat").to_crs(CRS)
    feats = pd.concat([gpd.GeoDataFrame(dict(kind=["pit"] * len(pits)), geometry=pits.geometry.centroid, crs=CRS),
                       gpd.GeoDataFrame(dict(kind=["pad"] * len(pads)), geometry=pads.geometry.centroid, crs=CRS)],
                      ignore_index=True)
    feats = feats[inside(feats.geometry)].reset_index(drop=True)
    print(f"{len(w)} DEP wells in window, {len(feats)} annotated features in valid area")

    # snap each well to the nearest feature within SNAP_M
    near = gpd.sjoin_nearest(w, feats.reset_index().rename(columns={"index": "fid", "kind": "fkind"}),
                             how="left", max_distance=SNAP_M, distance_col="snap_dist_m")
    near = near.sort_values("snap_dist_m")
    near = near[~near.index.duplicated(keep="first")]
    sn = near[near.fid.notna()].copy()
    fcent = feats.geometry
    sn["raw"] = sn.geometry
    sn["geometry"] = [fcent[int(f)] for f in sn.fid]
    sn = sn[inside(sn.geometry) & inside(sn.raw)]
    print(f"{len(sn)} wells snapped (within {SNAP_M:.0f} m of a lidar feature); median shift "
          f"{sn.snap_dist_m.median():.1f} m")
    print(sn.groupby(["group", "fkind"]).size().to_string())

    # controls: features with no DEP well within SNAP_M
    allw = gpd.read_file(steel.WELLS).to_crs(CRS)
    dist = np.array([allw.distance(g).min() for g in feats.geometry])
    ctl = feats[dist > SNAP_M].copy()
    print(f"{len(ctl)} control features (no DEP well within {SNAP_M:.0f} m)")

    rows = {}
    for r_m, tag in ((steel.R_M, f"r{steel.R_M:.0f}"), (R_WIDE, f"r{R_WIDE:.0f}")):
        raw_pts = gpd.GeoSeries(sn.raw.values, crs=CRS)
        snap_pts = sn.geometry.reset_index(drop=True)
        n_raw, b_raw = scores(maps, raw_pts, tf, shape, r_m)
        n_sn, b_sn = scores(maps, snap_pts, tf, shape, r_m)
        n_c, b_c = scores(maps, ctl.geometry, tf, shape, r_m)
        for label, sel in (("all", np.ones(len(sn), bool)), ("active", (sn.group == "active").values),
                           ("abandoned_or_plugged", sn.group.isin(["abandoned", "plugged"]).values),
                           ("on_pad", (sn.fkind == "pad").values), ("on_pit", (sn.fkind == "pit").values)):
            if sel.sum() < 5:
                continue
            rows[f"{tag}_snapped_vs_controls_{label}"] = compare(n_sn[sel], b_sn[sel], n_c, b_c)
            rows[f"{tag}_snapped_vs_raw_{label}"] = compare(n_sn[sel], b_sn[sel], n_raw[sel], b_raw[sel])
    res = pd.DataFrame(rows).T
    print(res.to_string())

    stem = "nisar_steel_snapped"
    res.to_csv(OUT / f"{stem}_comparisons_{AREA.TAG}.csv")
    sn_out = sn.drop(columns=["raw", "index_right"], errors="ignore").rename(columns={"fid": "feat_id"})
    sn_out.to_file(OUT / f"{stem}_wells_{AREA.TAG}.gpkg", layer="snapped_wells", driver="GPKG")
    json.dump(dict(snap_m=SNAP_M, r_m=steel.R_M, r_wide=R_WIDE, n_wells=len(w), n_snapped=len(sn),
                   median_snap_shift_m=float(sn.snap_dist_m.median()), n_controls=len(ctl),
                   comparisons=rows), open(OUT / f"{stem}_summary_{AREA.TAG}.json", "w"), indent=2, default=float)
    print("wrote", OUT / f"{stem}_*_{AREA.TAG}.*")


if __name__ == "__main__":
    main()
