"""NISAR steady bright targets over Warren, scored against DEP wells.

Same SBT rule as _nisar_bright_targets_9t.py (D_A < 0.25, at least 6 dB above the 250 m median,
per track, tracks merged within 15 m). Warren has no annotated pads or roads, so context is
the nearest DEP well only. Chance baseline: random valid pixels, split by canopy cover so that
wells in the open are compared with open ground and wells under trees with tree-covered ground.

  python notebooks/wellsight_v2/s5_eval/_nisar_bright_targets_wells_warren.py --area warren
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import fisher_exact

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
bt = importlib.import_module("_nisar_bright_targets_9t")
steel, st, ifg = bt.steel, bt.st, bt.ifg
OUT, CRS, WELLS, AREA = bt.OUT, bt.CRS, bt.WELLS, bt.AREA
NEAR_M, N_RANDOM, OPEN = 15.0, 20000, 0.30


def main():
    idx, stack, tf, shape = ifg.load_complex()
    maps = steel.sbt_maps(idx, stack, shape)
    n_dates = {int(t): int(m["n"]) for t, m in maps.items()}
    p = bt.track_points(maps, tf)
    tg = bt.merge_tracks(p)
    g = gpd.GeoDataFrame(tg, geometry=gpd.points_from_xy(tg.x, tg.y), crs=CRS).drop(columns=["x", "y"])
    cover = st.canopy_cover(tf, shape)
    g["canopy_cover"] = cover[((g.geometry.y - tf.f) / tf.e).astype(int), ((g.geometry.x - tf.c) / tf.a).astype(int)].round(2)

    x0, y1 = tf.c, tf.f
    x1, y0 = x0 + shape[1] * 5, y1 - shape[0] * 5
    w = gpd.read_file(WELLS).to_crs(CRS).cx[x0 - 500:x1 + 500, y0 - 500:y1 + 500].reset_index(drop=True)
    wxy = np.c_[w.geometry.x, w.geometry.y]
    g["well_dist_m"], j = cKDTree(wxy).query(np.c_[g.geometry.x, g.geometry.y])
    g["well_dist_m"] = g.well_dist_m.round(1)
    g["well_permit"] = w.PERMIT_NUM.values[j]
    g["well_status"] = w.WELL_STATU.values[j]
    g["at_well"] = g.well_dist_m <= NEAR_M
    g = g.sort_values(["n_tracks", "bright_db"], ascending=False).reset_index(drop=True)
    g.insert(0, "target_id", range(1, len(g) + 1))

    # wells that sit on valid, lidar-covered pixels
    ok = np.isfinite(cover) & np.all([m["ok"] for m in maps.values()], axis=0)
    wr = ((w.geometry.y - tf.f) / tf.e).astype(int).values
    wc = ((w.geometry.x - tf.c) / tf.a).astype(int).values
    inside = (wr >= 0) & (wr < shape[0]) & (wc >= 0) & (wc < shape[1])
    inside[inside] = ok[wr[inside], wc[inside]]
    wi = w[inside].reset_index(drop=True)
    wcov = cover[wr[inside], wc[inside]]
    tx = cKDTree(np.c_[g.geometry.x, g.geometry.y])
    wd, _ = tx.query(np.c_[wi.geometry.x, wi.geometry.y])
    w_hit = wd <= NEAR_M

    rng = np.random.default_rng(20261023)
    rr, cc = np.nonzero(ok)
    k = rng.choice(len(rr), N_RANDOM, replace=False)
    rxy = np.c_[tf.c + (cc[k] + 0.5) * tf.a, tf.f + (rr[k] + 0.5) * tf.e]
    rcov = cover[rr[k], cc[k]]
    rd, _ = tx.query(rxy)
    r_hit = rd <= NEAR_M
    res = {}
    for lab, ws, rs in (("all", np.ones(len(wi), bool), np.ones(N_RANDOM, bool)),
                        ("open", wcov < OPEN, rcov < OPEN), ("canopy", wcov >= OPEN, rcov >= OPEN)):
        a, b = w_hit[ws], r_hit[rs]
        orr, pv = fisher_exact([[a.sum(), (~a).sum()], [b.sum(), (~b).sum()]])
        res[lab] = dict(n_wells=int(ws.sum()), wells_with_target=int(a.sum()), share_wells=round(float(a.mean()), 3),
                        n_random=int(rs.sum()), share_random=round(float(b.mean()), 3),
                        odds_ratio=round(float(orr), 2), p_fisher=float(f"{pv:.2g}"))
    by_status = wi.assign(hit=w_hit).groupby("WELL_STATU").hit.agg(["size", "mean"]).round(3).to_dict("index")

    stem = "nisar_bright_targets"
    g.to_file(OUT / f"{stem}_points_{AREA.TAG}.gpkg", layer="candidate_bright_targets", driver="GPKG")
    wi.assign(target_within_15m=w_hit, canopy_cover=wcov.round(2)).to_file(
        OUT / f"{stem}_wells_{AREA.TAG}.gpkg", layer="wells_scored", driver="GPKG")
    summary = dict(params=dict(da_max=steel.DA_MAX, bright_db=steel.BRIGHT_DB, bg_m=steel.BG_M,
                               merge_m=bt.MERGE_M, near_m=NEAR_M, open_cover_lt=OPEN),
                   dates_per_track=n_dates, targets=int(len(g)), by_n_tracks=g.n_tracks.value_counts().sort_index().to_dict(),
                   wells_in_window=int(len(wi)), wells_vs_random=res, hit_by_well_status=by_status,
                   targets_2plus_tracks_at_well=int(((g.n_tracks >= 2) & g.at_well).sum()),
                   targets_2plus_tracks=int((g.n_tracks >= 2).sum()))
    json.dump(summary, open(OUT / f"{stem}_summary_{AREA.TAG}.json", "w"), indent=2, default=int)
    print(json.dumps(summary, indent=2, default=int))


if __name__ == "__main__":
    main()
