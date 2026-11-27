"""Do the fitted per-track slant-range offsets just absorb the dry troposphere? 9t. Set 2026-11-27 (Track 2B).

Why
  The geocoder applies ionosphere only. Each track then gets an empirical slant-range offset
  (track_slant_m, fitted against the lidar simulation). If that offset is mostly the unmodelled
  dry tropospheric delay, a new tile can apply the delay model and fit only a small residual.

Method
  Saastamoinen zenith hydrostatic delay at 9t (lat 41.55, median lidar ground ~450 m, standard
  pressure), mapped by 1/cos(incidence) per track; compared with nisar_slc_track_offsets_9t.csv.

Output
  nisar/results/9t/v2/nisar_tropo_offset_check_9t.csv

Run
  python nisar/code/s5_eval/_nisar_tropo_offset_check_9t.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nisar" / "code" / "s1_build"))
import _nisar_geometry as geo  # noqa: E402

INC = {26: 41.0, 90: 39.0, 162: 47.0}   # incidence at 9t, deg (deck table, ASF metadata)
LAT, H = 41.55, 450.0

off = pd.read_csv(ROOT / "nisar/results/9t/nisar_slc_track_offsets_9t.csv")
off["incidence_deg"] = off.track.map(INC)
off["dry_tropo_m"] = [round(float(geo.dry_tropo_slant_delay(np.array(H), LAT, i)), 3) for i in off.incidence_deg]
off["residual_m"] = (off.slant_m - off.dry_tropo_m).round(3)
out = ROOT / "nisar/results/9t/v2/nisar_tropo_offset_check_9t.csv"
off[["track", "incidence_deg", "slant_m", "dry_tropo_m", "residual_m", "az_m"]].to_csv(out, index=False)
print(off[["track", "incidence_deg", "slant_m", "dry_tropo_m", "residual_m", "az_m"]].to_string(index=False))
print("mean fitted", off.slant_m.mean().round(2), "mean dry tropo", off.dry_tropo_m.mean().round(2),
      "residual RMS", np.sqrt((off.residual_m ** 2).mean()).round(2))
print("wrote", out)
