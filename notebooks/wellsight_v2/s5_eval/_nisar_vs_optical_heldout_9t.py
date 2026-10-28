"""Audit of the radar-against-optical comparison (outside-review follow-up 7, plus the terrain part of 4; 2026-10-27, 9t).

Checks, each answering a point of the reviews of NISAR_FINDINGS.md:
  1. Reflectance metadata of the three Sentinel-2 scenes (boa offset flag, processing baseline, cloud and cirrus shares),
     read from the Earth Search STAC items, against the assumption in _nisar_vs_optical_9t.py (no 1,000 DN offset).
  2. Cirrus handling: Spearman of date-mean HV with June NDVI when thin cirrus (SCL 10) is kept and when it is masked.
  3. Spatially held-out R2. The 50 m blocks are grouped into 1 km squares and fitted with 5-fold grouped CV, so a block is never
     fitted on a neighbour. Two learners: ordinary least squares (as before) and gradient boosting (nonlinear, so cover and
     height can act in steps). Pooled R2 = 1 - SSE/SST over the held-out predictions. Predictor sets:
       lidar (canopy height, cover, slope, elevation), canopy cover alone, optical (as before), optical of the same year only
       (June and September 2026 layers, no October 2025), lidar + optical, lidar + same-year optical.
  4. Terrain illumination. The target is also run as terrain-flattened HV (HV minus the simulated facet gain sim_db of each
     track, then averaged), and with the mean sim_db as an extra predictor.
Subsets: all, closed canopy (cover > 0.8), open ground (cover < 0.25). HH and HV.

  NISAR_STACK=slc python _nisar_vs_optical_heldout_9t.py
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "4")

import numpy as np
import pandas as pd
import rasterio
import requests
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

import _nisar_feat_common as C
import _nisar_vs_optical_9t as O

TRACKS = (26, 90, 162)
SUPER = 20        # 20 blocks of 50 m = 1 km


def metadata():
    rows = []
    for tag, scene in O.SCENES.items():
        p = requests.get(f"https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/{scene}", timeout=60).json()["properties"]
        rows.append(dict(scene=scene, boa_offset_applied=p.get("earthsearch:boa_offset_applied"), processing_baseline=p.get("s2:processing_baseline"),
                         cloud_cover=p.get("eo:cloud_cover"), thin_cirrus_pct=p.get("s2:thin_cirrus_percentage"),
                         cloud_shadow_pct=p.get("s2:cloud_shadow_percentage"), medium_proba_pct=p.get("s2:medium_proba_clouds_percentage"),
                         high_proba_pct=p.get("s2:high_proba_clouds_percentage"), snow_pct=p.get("s2:snow_ice_percentage")))
    return pd.DataFrame(rows)


def raw_ndvi(tag, mask_cirrus):
    with rasterio.open(O.OPT / f"s2_{tag}_green_red_nir_swir_scl_9t_5m.tif") as r:
        g, rd, nir, sw, scl = (r.read(i) for i in range(1, 6))
    bad = np.isin(scl, (0, 1, 3, 8, 9, 11) + ((10,) if mask_cirrus else ()))
    ndvi = ((nir - rd) / (nir + rd)).astype(np.float32)
    ndvi[bad] = np.nan
    return ndvi, float(np.mean(scl == 10)), float(np.mean(np.isin(scl, (0, 1, 3, 8, 9, 11))))


def cv_r2(y, X, grp, learner):
    pred = np.full(len(y), np.nan)
    for tr, te in GroupKFold(5).split(X, y, grp):
        if learner == "ols":
            X1 = np.c_[np.ones(len(tr)), X[tr]]
            beta, *_ = np.linalg.lstsq(X1, y[tr], rcond=None)
            pred[te] = np.c_[np.ones(len(te)), X[te]] @ beta
        else:
            m = HistGradientBoostingRegressor(max_depth=4, learning_rate=0.08, max_iter=200, min_samples_leaf=40, l2_regularization=1.0, random_state=0)
            pred[te] = m.fit(X[tr], y[tr]).predict(X[te])
    return 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)


def main():
    meta = metadata()
    pd.set_option("display.width", 250)
    print(meta.to_string(index=False))
    meta.to_csv(C.OUT / f"nisar_optical_scene_metadata_{C.A.TAG}.csv", index=False)
    with rasterio.open(C.FEAT_DIR / f"nisar_check_radnorm_{C.A.TAG}_5m.tif") as r:
        names, arr, tf, shape = list(r.descriptions), r.read(), r.transform, (r.height, r.width)
    with rasterio.open(C.FEAT_DIR / f"nisar_feat_geometry_{C.A.TAG}_5m.tif") as r:
        gnames = list(r.descriptions)
        sim = {t: r.read(gnames.index(f"sim_db_t{t:03d}") + 1) for t in TRACKS}
    sar = {pol: np.nanmean([arr[names.index(f"raw_mean_{pol}_t{t:03d}")] for t in TRACKS], 0) for pol in ("hh", "hv")}
    sar_flat = {f"{pol}_flat": np.nanmean([arr[names.index(f"raw_mean_{pol}_t{t:03d}")] - sim[t] for t in TRACKS], 0) for pol in ("hh", "hv")}
    sim_mean = np.nanmean([sim[t] for t in TRACKS], 0)
    opt = O.fetch(tf, shape)
    grids = C.lidar_grids(tf, shape)
    chm, dem = C.to_grid(C.A.lidar("chm"), tf, shape), C.to_grid(C.A.lidar("dem"), tf, shape)
    layers = {"canopy_height": chm, "canopy_cover": grids["cover"], "ground_slope": grids["slope"], "ground_elevation": dem,
              "ndvi_jun": opt["jun"]["ndvi"], "ndvi_sep": opt["sep"]["ndvi"], "ndvi_oct": opt["oct"]["ndvi"],
              "ndvi_jun_minus_oct": opt["jun"]["ndvi"] - opt["oct"]["ndvi"], "ndmi_sep": opt["sep"]["ndmi"], "nir_sep": opt["sep"]["nir"],
              "sim_db_mean": sim_mean}
    B = {n: O.block_mean(a) for n, a in layers.items()}
    S = {n: O.block_mean(a) for n, a in {**sar, **sar_flat}.items()}
    # 2. cirrus handling
    rows_c = []
    for mask in (False, True):
        nd, f_cirrus, f_bad = raw_ndvi("jun", mask)
        nd_b = O.block_mean(nd)
        ok = np.isfinite(nd_b) & np.isfinite(S["hv"])
        rows_c.append(dict(scene="jun", cirrus_masked=mask, cirrus_share=round(f_cirrus, 3), other_bad_share=round(f_bad, 3), n_blocks=int(ok.sum()),
                           spearman_hv_ndvi=round(float(spearmanr(S["hv"][ok], nd_b[ok]).statistic), 3)))
    nd, f_cirrus, f_bad = raw_ndvi("sep", False)
    rows_c.append(dict(scene="sep", cirrus_masked=False, cirrus_share=round(f_cirrus, 3), other_bad_share=round(f_bad, 3), n_blocks=int(np.isfinite(O.block_mean(nd)).sum()), spearman_hv_ndvi=np.nan))
    cir = pd.DataFrame(rows_c)
    print(cir.to_string(index=False))
    cir.to_csv(C.OUT / f"nisar_optical_cirrus_check_{C.A.TAG}.csv", index=False)
    # 3 and 4. held-out R2
    lidar = ["canopy_height", "canopy_cover", "ground_slope", "ground_elevation"]
    optic = ["ndvi_jun", "ndvi_sep", "ndvi_oct", "ndvi_jun_minus_oct", "ndmi_sep", "nir_sep"]
    same_year = ["ndvi_jun", "ndvi_sep", "ndmi_sep", "nir_sep"]
    sets = {"canopy cover alone": ["canopy_cover"], "lidar (4 layers)": lidar, "optical (6 layers)": optic, "optical, same year (4)": same_year,
            "lidar + optical": lidar + optic, "lidar + optical same year": lidar + same_year, "lidar + terrain gain": lidar + ["sim_db_mean"]}
    rr, cc = np.indices(B["canopy_cover"].shape)
    grp_all = (rr // SUPER) * 1000 + cc // SUPER
    rows = []
    for sub, mk in (("all", np.ones_like(B["canopy_cover"], bool)), ("closed canopy (cover > 0.8)", B["canopy_cover"] > 0.8),
                    ("open ground (cover < 0.25)", B["canopy_cover"] < 0.25)):
        for tgt, s in S.items():
            ok = mk & np.isfinite(s) & np.all([np.isfinite(B[n]) for n in set(sum(sets.values(), []))], axis=0)
            y, g = s[ok], grp_all[ok]
            for nm, cols in sets.items():
                X = np.column_stack([B[n][ok] for n in cols])
                row = dict(subset=sub, target=tgt, predictors=nm, n_blocks=int(ok.sum()), n_squares=len(np.unique(g)))
                for lr in ("ols", "gbm"):
                    row[f"r2_heldout_{lr}"] = round(cv_r2(y, X, g, lr), 3)
                rows.append(row)
            print(sub, tgt, "done", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(C.OUT / f"nisar_vs_optical_heldout_r2_{C.A.TAG}.csv", index=False)
    print(res[res.target.isin(["hv", "hv_flat"])].to_string(index=False))


if __name__ == "__main__":
    main()
