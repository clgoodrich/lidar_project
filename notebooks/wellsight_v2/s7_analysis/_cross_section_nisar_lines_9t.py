"""One figure over all four test lines: lidar ground and surface top, and the NISAR summer mean (HH, HV) along each.

Reads the per-line CSVs written by _cross_section_test_line_9t.py, so it adds no new sampling. NISAR is the Jun-Sep 2026
mean on track 162, 5 m pixels, nearest pixel, not shifted to the lidar (registration residual about 10 m).
Pad and pit spans are shaded behind the radar panel. The title carries the per-line correlation of HV with canopy height.

Palette: lidar ground charcoal, surface grey, HV blue #1F5FA8, HH orange #D97706 (the validated blue/orange pair of the
project colourblind rule; no red or green). Lines are also told apart by dash style.

  python notebooks/wellsight_v2/s7_analysis/_cross_section_nisar_lines_9t.py
"""
import glob
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / "data" / "9t" / "results" / "cross_sections"
OUT = D / "figures" / "cross_section_nisar_all_lines_hh_hv_canopy_9t.png"
BLUE, ORANGE, GREY, CHAR = "#1F5FA8", "#D97706", "#8E959B", "#2B2F36"


def spans(d, pred):
    m = d.zone.map(pred).values
    out, start = [], None
    for i, v in enumerate(m):
        if v and start is None:
            start = d.distance_m.iloc[i]
        if (not v or i == len(m) - 1) and start is not None:
            out.append((start, d.distance_m.iloc[i]))
            start = None
    return out


def main():
    files = sorted(glob.glob(str(D / "cross_section_test_line*_dem_dsm_nisar_summer2026_t162_with_pads_pits_roads_9t_1m.csv")))
    fig, axes = plt.subplots(len(files), 2, figsize=(15, 3.1 * len(files)), gridspec_kw={"width_ratios": [1, 1]})
    for r, f in enumerate(files):
        d = pd.read_csv(f)
        n = int(Path(f).name.split("line")[1][0])
        hv, hh = d.nisar_hv_summer2026_t162_db, d.nisar_hh_summer2026_t162_db
        c_hv = d[["nisar_hv_summer2026_t162_db", "canopy_height_m"]].corr().iloc[0, 1]
        c_hh = d[["nisar_hh_summer2026_t162_db", "canopy_height_m"]].corr().iloc[0, 1]
        a, b = axes[r]
        a.fill_between(d.distance_m, d.ground_dem_m, d.surface_dsm_m, color=GREY, alpha=0.35, lw=0)
        a.plot(d.distance_m, d.surface_dsm_m, color=GREY, lw=1, label="surface top (lidar DSM)")
        a.plot(d.distance_m, d.ground_dem_m, color=CHAR, lw=2, label="ground (lidar DEM)")
        a.set_ylabel("Elevation (m)")
        a.set_title(f"Line {n}: lidar, {d.distance_m.max():.0f} m long", loc="left", fontsize=10)
        for ax in (a, b):
            for s0, s1 in spans(d, lambda z: "pad" in z):
                ax.axvspan(s0, s1, color=BLUE, alpha=0.10, hatch="\\\\", lw=0)
            for s0, s1 in spans(d, lambda z: z.startswith("pit") or "pit" in z):
                ax.axvspan(s0, s1, color=ORANGE, alpha=0.12, hatch="//", lw=0)
            for s0, s1 in spans(d, lambda z: z == "road"):
                ax.axvspan(s0, s1, color=CHAR, alpha=0.18, hatch="xx", lw=0)
        b.step(d.distance_m, hh, where="mid", color=ORANGE, lw=1.8, ls="--", label="HH")
        b.step(d.distance_m, hv, where="mid", color=BLUE, lw=1.8, label="HV")
        b.set_ylabel("NISAR summer mean (dB)")
        b.set_title(f"Line {n}: NISAR, correlation with canopy height: HV {c_hv:+.2f}, HH {c_hh:+.2f}", loc="left", fontsize=10)
        b2 = b.twinx()
        b2.fill_between(d.distance_m, 0, d.canopy_height_m, color=GREY, alpha=0.30, lw=0)
        b2.set_ylabel("Canopy height (m), grey", color="#555")
        b2.set_ylim(0, max(30, d.canopy_height_m.max() * 1.05))
        if r == 0:
            a.legend(loc="upper left", fontsize=8, frameon=False)
            b.legend(loc="lower left", fontsize=8, frameon=False, ncol=2)
        if r == len(files) - 1:
            a.set_xlabel("Distance along line (m)")
            b.set_xlabel("Distance along line (m)")
    fig.suptitle("NISAR along the four 9t test lines. Blue hatch: pad. Orange hatch: pit. Dark hatch: road.\n"
                 "NISAR is 5 m pixels, nearest pixel, about 10 m registration residual to the lidar.", fontsize=11, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT, dpi=140)
    print(OUT)


if __name__ == "__main__":
    main()
