"""NISAR GSLC stack over 9t: every bright, steady radar target as a point, for checking in QGIS.

The steel test (_nisar_steel_9t.py) scored DEP wells. This layer goes the other way. It marks
every steady bright target (SBT) the stack finds, whether or not a well is near it.

SBT, per track (same rule as the steel test):
  * amplitude dispersion D_A = std / mean of the HH amplitude over all dates < 0.25
  * mean brightness at least 6 dB above the 250 m median around it
Each connected group of SBT pixels on one track becomes one point, at its brightest pixel.
Points from different tracks within MERGE_M are one target. Tracks are not co-registered to
better than about 15 m (see _nisar_gslc_stack_pad_pit_seasonal_9t.py), so MERGE_M = 15.

Context per target: nearest DEP well (any status), nearest annotated pad and road, and the
2019 lidar canopy cover. These are candidates for metal (tanks, pipe, equipment), not wells.

Run:
  python notebooks/wellsight_v2/s5_eval/_nisar_bright_targets_9t.py
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import label
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
steel = importlib.import_module("_nisar_steel_9t")
ifg, st = steel.ifg, steel.st
from _common import read_layer  # noqa: E402

OUT, CRS, ANN, WELLS = steel.OUT, steel.CRS, steel.ANN, steel.WELLS
MERGE_M = 15.0
NEAR_M = 15.0   # "at" a well, pad or road
N_RANDOM = 20000


def track_points(maps, tf):
    """One point per connected SBT group per track, at the group's brightest pixel."""
    rows = []
    for t, m in maps.items():
        lab, n = label(m["sbt"], structure=np.ones((3, 3)))
        for k in range(1, n + 1):
            rr, cc = np.nonzero(lab == k)
            j = np.argmax(m["bright"][rr, cc])
            r, c = rr[j], cc[j]
            rows.append(dict(track=t, x=tf.c + (c + 0.5) * tf.a, y=tf.f + (r + 0.5) * tf.e,
                             n_px=len(rr), bright_db=float(m["bright"][r, c]), da=float(m["da"][r, c])))
    return pd.DataFrame(rows)


def write_layers(maps, tf, shape):
    """The per-track rasters the SBT rule reads, so a target can be checked by eye."""
    for t, m in maps.items():
        bands = {"mean_hh_db": m["bright"] + m["bg"], "above_250m_median_db": m["bright"],
                 "amplitude_dispersion": m["da"], "steady_bright_target": m["sbt"].astype(np.float32)}
        path = steel.DER / f"nisar_bright_targets_layers_t{t:03d}_9t.tif"
        with rasterio.open(path, "w", driver="GTiff", height=shape[0], width=shape[1], count=len(bands),
                           dtype="float32", crs=CRS, transform=tf, nodata=np.nan, compress="deflate") as dst:
            for i, (name, a) in enumerate(bands.items(), 1):
                dst.write(np.where(m["ok"], a, np.nan).astype(np.float32), i)
                dst.set_band_description(i, name)
        print("wrote", path)


def merge_tracks(p):
    """Join points from different tracks within MERGE_M into one target."""
    xy = p[["x", "y"]].values
    pairs = cKDTree(xy).query_pairs(MERGE_M, output_type="ndarray")
    import scipy.sparse as sp
    g = sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(p), len(p)))
    _, p["target"] = connected_components(g, directed=False)
    out = p.sort_values("bright_db", ascending=False).groupby("target").agg(
        x=("x", "first"), y=("y", "first"), n_tracks=("track", "nunique"),
        tracks=("track", lambda s: ",".join(str(t) for t in sorted(set(s)))),
        bright_db=("bright_db", "max"), da_min=("da", "min"), n_px=("n_px", "sum"))
    return out.reset_index(drop=True)


def main():
    idx, stack, tf, shape = ifg.load_complex()
    maps = steel.sbt_maps(idx, stack, shape)
    n_dates = {int(t): int(m["n"]) for t, m in maps.items()}
    write_layers(maps, tf, shape)
    p = track_points(maps, tf)
    tg = merge_tracks(p)
    g = gpd.GeoDataFrame(tg, geometry=gpd.points_from_xy(tg.x, tg.y), crs=CRS).drop(columns=["x", "y"])

    cover = st.canopy_cover(tf, shape)
    col = ((g.geometry.x - tf.c) / tf.a).astype(int)
    row = ((g.geometry.y - tf.f) / tf.e).astype(int)
    g["canopy_cover"] = cover[row, col].round(2)

    x0, y1 = tf.c, tf.f
    x1, y0 = x0 + shape[1] * 5, y1 - shape[0] * 5
    w = gpd.read_file(WELLS).to_crs(CRS).cx[x0 - 500:x1 + 500, y0 - 500:y1 + 500].reset_index(drop=True)
    d, j = cKDTree(np.c_[w.geometry.x, w.geometry.y]).query(np.c_[g.geometry.x, g.geometry.y])
    g["well_dist_m"] = d.round(1)
    g["well_permit"] = w.PERMIT_NUM.values[j]
    g["well_status"] = w.WELL_STATU.values[j]
    pads = read_layer(ANN, "plat").to_crs(CRS).union_all()
    roads = read_layer(ANN, "roads").to_crs(CRS).union_all()
    g["pad_dist_m"] = g.geometry.distance(pads).round(1)
    g["road_dist_m"] = g.geometry.distance(roads).round(1)

    # one context word, first match wins
    def context(wd, pd_, rd):
        return np.select([wd <= NEAR_M, pd_ <= NEAR_M, rd <= NEAR_M],
                         ["at_well", "on_pad", "on_road"], "elsewhere")
    g["context"] = context(g.well_dist_m, g.pad_dist_m, g.road_dist_m)

    # chance baseline: the same context for random spots on valid lidar-covered pixels
    rng = np.random.default_rng(20261008)
    ok = np.isfinite(cover) & np.all([m["ok"] for m in maps.values()], axis=0)
    rr, cc = np.nonzero(ok)
    k = rng.choice(len(rr), N_RANDOM, replace=False)
    rp = gpd.GeoSeries(gpd.points_from_xy(tf.c + (cc[k] + 0.5) * tf.a, tf.f + (rr[k] + 0.5) * tf.e), crs=CRS)
    rwd, _ = cKDTree(np.c_[w.geometry.x, w.geometry.y]).query(np.c_[rp.x, rp.y])
    chance = pd.Series(context(rwd, rp.distance(pads).values, rp.distance(roads).values)).value_counts(normalize=True)
    in_lidar = g.canopy_cover.notna()
    g = g.sort_values(["n_tracks", "bright_db"], ascending=False).reset_index(drop=True)
    g.insert(0, "target_id", range(1, len(g) + 1))

    stem = "nisar_bright_targets"
    g.to_file(OUT / f"{stem}_points_9t.gpkg", layer="candidate_bright_targets", driver="GPKG")
    summary = dict(params=dict(da_max=steel.DA_MAX, bright_db=steel.BRIGHT_DB, bg_m=steel.BG_M,
                               merge_m=MERGE_M, near_m=NEAR_M),
                   dates_per_track=n_dates, track_points=int(len(p)), targets=int(len(g)),
                   by_n_tracks=g.n_tracks.value_counts().sort_index().to_dict(),
                   by_context=g.context.value_counts().to_dict(),
                   share_by_context_in_lidar=g[in_lidar].context.value_counts(normalize=True).round(3).to_dict(),
                   share_by_context_random_spots=chance.round(3).to_dict(),
                   by_context_2plus_tracks=g[g.n_tracks >= 2].context.value_counts().to_dict())
    json.dump(summary, open(OUT / f"{stem}_summary_9t.json", "w"), indent=2, default=int)
    print(json.dumps(summary, indent=2, default=int))
    print(g.head(15).drop(columns="geometry").to_string())


if __name__ == "__main__":
    main()
