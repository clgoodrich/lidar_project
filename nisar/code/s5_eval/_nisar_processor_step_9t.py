"""Radiometric step between NISAR processor versions P05023 and P05036, 9t. Set 2026-11-26.

Why
  Every date to 2026-10-18 is provisional P05023. Every date from 2026-10-23 is standard P05036
  (new absolute calibration, RX-factor change). That is the same week as leaf drop, so a season
  contrast could carry a processor step. Each track has one date on each side, 12 days apart:
  162 Oct 11 -> Oct 23, 026 Oct 14 -> Oct 26, 090 Oct 18 -> Oct 30.
  The baseline is the prior same-version 12-day step: Sep 29 -> Oct 11, Oct 2 -> Oct 14,
  Oct 6 -> Oct 18. The excess over the baseline estimates the processor step.

Measures (HH and HV, median of per-pixel dB change)
  all valid pixels, open ground (canopy cover < 0.10), closed forest (> 0.70), and the peak
  pixel within 10 m of the 9 NAIP-confirmed buildings (point-like, leaf-insensitive).

Output
  nisar/results/9t/nisar_processor_step_summary_9t_slc.json

Run
  python nisar/code/s5_eval/_nisar_processor_step_9t.py --slc
"""
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ifg = importlib.import_module("_nisar_gslc_interferogram_pits_9t")
st = ifg.st
OUT = st.OUT
PAIRS = {162: ("2026-09-29", "2026-10-11", "2026-10-23"),
         26: ("2026-10-02", "2026-10-14", "2026-10-26"),
         90: ("2026-10-06", "2026-10-18", "2026-10-30")}


def main():
    idx, stack, tf, shape = ifg.load_complex()
    cover = st.canopy_cover(tf, shape)
    b = pd.read_csv(OUT / "nisar_top_targets_naip_classes_9t.csv")
    b = b[b["class"] == "building"]
    col = ((b.x.values - tf.c) / tf.a // 1).astype(int)
    row = ((b.y.values - tf.f) / tf.e // 1).astype(int)
    fp = np.ones((5, 5), bool)
    res = []
    for t, (d0, d1, d2) in PAIRS.items():
        f = {d: idx[(idx.track == t) & (idx.date.astype(str) == d)].file.iloc[0] for d in (d0, d1, d2)}
        for bi, pol in enumerate(("HH", "HV")):
            db = {d: 10 * np.log10(np.abs(stack[f[d]][bi]).astype(np.float64) ** 2) for d in f}
            ok = np.all([np.isfinite(v) for v in db.values()], axis=0)
            pk = {d: maximum_filter(np.where(ok, v, -99), footprint=fp)[row, col] for d, v in db.items()}
            for lab, a, c in (("baseline_same_version", d0, d1), ("across_versions", d1, d2)):
                dd = db[c] - db[a]
                r = dict(track=t, pol=pol, step=lab, dates=f"{a}->{c}")
                for k, m in (("all", ok), ("open_lt0p10", ok & (cover < 0.10)), ("closed_gt0p70", ok & (cover > 0.70))):
                    r[f"median_db_{k}"] = round(float(np.median(dd[m])), 3)
                    r[f"n_{k}"] = int(m.sum())
                r["median_db_buildings"] = round(float(np.median(pk[c] - pk[a])), 3)
                r["n_buildings"] = len(b)
                res.append(r)
    df = pd.DataFrame(res)
    print(df.to_string())
    ex = []
    for (t, pol), g in df.groupby(["track", "pol"]):
        g = g.set_index("step")
        ex.append(dict(track=int(t), pol=pol, **{k.replace("median_db_", "excess_db_"): round(
            g.loc["across_versions", k] - g.loc["baseline_same_version", k], 3)
            for k in g.columns if k.startswith("median_db_")}))
    print(pd.DataFrame(ex).to_string())
    p = OUT / "nisar_processor_step_summary_9t_slc.json"
    p.write_text(json.dumps(dict(pairs={int(k): v for k, v in PAIRS.items()}, steps=res, excess=ex), indent=1))
    print("wrote", p)


if __name__ == "__main__":
    main()
