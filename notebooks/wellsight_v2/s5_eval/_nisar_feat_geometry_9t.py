"""Products 5 and 15: terrain-flattened brightness, residual after the terrain model, geometry masks.

Needs the lidar radar simulation of this area (data/<area>/derived/nisar_gslc_5m/nisar_lidar_sim_tNNN_<area>.tif,
made by _nisar_lidar_sim_match_9t.py). Present for 9t. For Warren it has to be made first.

The simulation gives the facet area each 5 m cell presents to the radar. Dividing it out of the mean
power leaves the part the terrain does not explain (gamma0-like). A flat bench on a slope then
differs from the sloped ground around it in both the raw and the flattened view.

Bands (suffix _tNNN unless noted):
  flat_db       mean HH dB minus 10 log10(facet area), NaN in shadow and layover
  flat_resid    flat_db minus its 251 m (51 px) running median, the local anomaly
  sim_db        simulated facet area in dB (the terrain's own brightness effect)
  sim_valid     1 where the simulation is usable (not shadow or layover), else 0
Cross-track (no suffix):
  flat_diff_asc      flat_db of the first ascending track minus the second (incidence-angle effect after flattening)
  flat_diff_desc_asc flat_db of the descending track minus the mean of the ascending ones

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_geometry_9t.py [--area 9t]
"""
import importlib

import numpy as np
from scipy.ndimage import median_filter

import _nisar_feat_common as C

flat = importlib.import_module("_nisar_flatten_gain_test_9t")
RUN_PX = 51


def main():
    idx, stack, tf, shape = C.load()
    bands, fl, direction = {}, {}, {}
    for t, g in C.by_track(idx):
        af, sok = flat.sim_layers(t, tf, shape)
        hh = np.abs(C.cube(g, stack, 0)) ** 2
        ok = np.all(np.isfinite(hh) & (hh > 0), axis=0)
        mdb = C.db(hh.mean(0))
        fdb = np.where(ok & sok, mdb - 10 * np.log10(np.where(af > 0, af, np.nan)), np.nan)
        med = median_filter(np.where(np.isfinite(fdb), fdb, np.nanmedian(fdb)), size=RUN_PX)
        tag = f"_t{t:03d}"
        bands["flat_db" + tag] = fdb
        bands["flat_resid" + tag] = np.where(np.isfinite(fdb), fdb - med, np.nan)
        bands["sim_db" + tag] = np.where(np.isfinite(af), 10 * np.log10(np.where(af > 0, af, np.nan)), np.nan)
        bands["sim_valid" + tag] = np.where(np.isfinite(af), sok.astype(np.float32), np.nan)
        fl[t], direction[t] = fdb, g.direction.iloc[0].upper().startswith("A")
        print(f"track {t}: {len(g)} dates, usable {np.isfinite(fdb).mean():.1%}", flush=True)
    asc = [t for t in fl if direction[t]]
    des = [t for t in fl if not direction[t]]
    if len(asc) >= 2:
        bands["flat_diff_asc"] = fl[asc[0]] - fl[asc[1]]
    for t in des:
        bands["flat_diff_desc_asc"] = fl[t] - np.nanmean([fl[a] for a in asc], 0)
    C.write_bands("geometry", bands, tf, shape)


if __name__ == "__main__":
    main()
