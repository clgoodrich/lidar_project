"""Plain cross section: lidar ground (DEM), canopy top (DSM) and NISAR along one test line. Nothing else.

Top panel: ground line, canopy-top line coloured by NISAR HV (dB, cividis, colourblind-safe), canopy filled grey.
Bottom panel: NISAR HV and HH (summer 2026 mean, track 162, 5 m pixels) on the same distance axis.
Reads the per-line CSV of _cross_section_test_line_9t.py.

  python notebooks/wellsight_v2/s7_analysis/_cross_section_nisar_simple_9t.py [line number, default 4]
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / "data" / "9t" / "results" / "cross_sections"
BLUE, ORANGE, CHAR = "#1F5FA8", "#D97706", "#2B2F36"


def main(n):
    d = pd.read_csv(D / f"cross_section_test_line{n}_dem_dsm_nisar_summer2026_t162_with_pads_pits_roads_9t_1m.csv")
    x, hv, hh = d.distance_m.values, d.nisar_hv_summer2026_t162_db.values, d.nisar_hh_summer2026_t162_db.values
    fig, (a, b) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    a.fill_between(x, d.ground_dem_m, d.surface_dsm_m, color="#D5D8DB", lw=0, label="canopy (between ground and top)")
    a.plot(x, d.ground_dem_m, color=CHAR, lw=2.2, label="ground (lidar DEM)")
    pts = np.c_[x, d.surface_dsm_m.values].reshape(-1, 1, 2)
    lc = LineCollection(np.concatenate([pts[:-1], pts[1:]], 1), cmap="cividis", norm=plt.Normalize(-18, -6), linewidths=3)
    lc.set_array((hv[:-1] + hv[1:]) / 2)
    a.add_collection(lc)
    a.autoscale()
    cb = fig.colorbar(lc, ax=a, location="top", pad=0.02, shrink=0.4, aspect=40)
    cb.set_label("NISAR HV backscatter on the canopy-top line (dB)")
    a.plot([], [], color="#B8860B", lw=3, label="canopy top (lidar DSM), coloured by NISAR HV")
    a.set_ylabel("Elevation (m)")
    a.legend(loc="upper left", frameon=False)
    a.set_title(f"Test line {n}, 9t: ground, canopy and NISAR ({x.max():.0f} m)", loc="left", pad=48)
    b.step(x, hh, where="mid", color=ORANGE, lw=1.8, ls="--", label="HH")
    b.step(x, hv, where="mid", color=BLUE, lw=1.8, label="HV")
    b.set_ylabel("NISAR summer mean (dB)")
    b.set_xlabel("Distance along line (m)")
    b.legend(loc="lower left", ncol=2, frameon=False)
    b.set_title("NISAR is 5 m pixels, about 10 m registration residual to the lidar", loc="left", fontsize=9)
    fig.tight_layout()
    out = D / "figures" / f"cross_section_line{n}_ground_canopy_nisar_9t.png"
    fig.savefig(out, dpi=140)
    print(out)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
