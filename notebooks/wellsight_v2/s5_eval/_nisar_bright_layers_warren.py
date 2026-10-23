"""Viewable NISAR brightness layers over Warren, one GeoTIFF per track, for QGIS.

The window files are complex (phase kept), which QGIS draws as flat grey. These are float32 dB.
Bands: 1 mean_hh_db, 2 above_250m_median_db, 3 amplitude_dispersion, 4 steady_bright_target (0/1).
Set band 1 to singleband gray, min/max 2-98 percent, to see the landscape.

  python notebooks/wellsight_v2/s5_eval/_nisar_bright_layers_warren.py --area warren
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import rasterio

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
bt = importlib.import_module("_nisar_bright_targets_9t")
steel, ifg = bt.steel, bt.ifg
idx, stack, tf, shape = ifg.load_complex()
maps = steel.sbt_maps(idx, stack, shape)
for t, m in maps.items():
    bands = {"mean_hh_db": m["bright"] + m["bg"], "above_250m_median_db": m["bright"],
             "amplitude_dispersion": m["da"], "steady_bright_target": m["sbt"].astype(np.float32)}
    path = steel.DER / f"nisar_bright_layers_t{t:03d}_{bt.AREA.TAG}.tif"
    with rasterio.open(path, "w", driver="GTiff", height=shape[0], width=shape[1], count=4, dtype="float32",
                       crs=steel.CRS, transform=tf, nodata=np.nan, compress="deflate") as dst:
        for i, (name, a) in enumerate(bands.items(), 1):
            dst.write(np.where(m["ok"], a, np.nan).astype(np.float32), i)
            dst.set_band_description(i, name)
    print("wrote", path)
