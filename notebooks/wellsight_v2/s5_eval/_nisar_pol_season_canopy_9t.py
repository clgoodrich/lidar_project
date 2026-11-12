"""Per-date HH, HV and HV/HH on the lidar-placed SLC stack, split by 2019 lidar canopy cover.

Canopy cover = share of 1 m CHM cells above 2 m in each 5 m pixel (same as the seasonal stack test).
Classes: open < 0.25, mid 0.25-0.8, closed > 0.8. Means are taken in linear power, then converted to dB.
Bad dates are dropped by the shared loader (A.usable_stack).

  python notebooks/wellsight_v2/s5_eval/_nisar_pol_season_canopy_9t.py --slc
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _nisar_gslc_stack_pad_pit_seasonal_9t as M  # noqa: E402

idx, inten, tf, shape = M.load_stack()
cov = M.canopy_cover(tf, shape)
classes = {"open": cov < 0.25, "mid": (cov >= 0.25) & (cov <= 0.8), "closed": cov > 0.8}
rows = []
for r in idx.itertuples():
    hh, hv = inten[r.file]
    for k, m in classes.items():
        ok = m & np.isfinite(hh) & np.isfinite(hv)
        mh, mv = np.nanmean(hh[ok]), np.nanmean(hv[ok])
        rows.append(dict(date=r.date, track=int(r.track), canopy=k, n_pixels=int(ok.sum()),
                         hh_db=round(10 * np.log10(mh), 3), hv_db=round(10 * np.log10(mv), 3),
                         hv_minus_hh_db=round(10 * np.log10(mv / mh), 3)))
out = M.OUT / f"nisar_pol_season_by_canopy_{M.A.TAG}.csv"
pd.DataFrame(rows).sort_values(["date", "canopy"]).to_csv(out, index=False)
print(out)
