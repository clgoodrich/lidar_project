"""Pad-minus-ring brightness, date by date, 9t. Set 2026-11-26.

Why
  The fall pad darkening (−0.15 dB HH, p < 0.001) is significant across 644 pads. But every pad
  shares the same 7 fall dates. One wet or windy date would move every pad together, and the
  pad-level p-value cannot see that. The real sample for a season effect is the number of dates.
  This scores each of the 32 dates on its own and asks whether fall dates sit below summer dates.

Method
  Same pads, rings (20-60 m, 10 m clear of pads and roads), core (3 m inset) and 5 decoys per pad
  as _nisar_gslc_stack_pad_pit_seasonal_9t.py (same seed). Per date and polarization:
    excess = median over pads (pad core − ring, dB) − median over decoys (decoy core − ring, dB).
  Tests, per polarization:
    * fall vs summer dates: Mann-Whitney on per-date excess (n = dates).
    * within track: fall dates against that track's summer range (tracks differ in geometry).
    * pad-level bootstrap per date, to show per-date noise.

Output
  nisar/results/9t/nisar_pad_season_per_date_9t_slc.csv
  nisar/results/9t/nisar_pad_season_per_date_summary_9t_slc.json

Run
  python nisar/code/s5_eval/_nisar_pad_season_per_date_9t.py --slc
"""
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
S = importlib.import_module("_nisar_gslc_stack_pad_pit_seasonal_9t")
A = S.A


def mean_db(L, idx):
    v = L[idx]
    v = v[np.isfinite(v)]
    return 10 * np.log10(v.mean()) if len(v) else np.nan


def main():
    rng = np.random.default_rng(S.SEED)
    idx, inten, tf, shape = S.load_stack()
    idx["season"] = idx.date.astype(str).map(S.season_of)
    cover = S.canopy_cover(tf, shape)
    in_tile = np.isfinite(cover)
    pads = S.read_layer(S.ANN, "plat").pipe(A.to_radar)[["pad_id", "geometry"]].dissolve(by="pad_id").reset_index()
    pits = S.read_layer(S.ANN, "pit_outside").pipe(A.to_radar)
    roads = S.read_layer(S.ANN, "roads").pipe(A.to_radar)
    zone = S.rasterize([(g, 1) for g in pd.concat([pads.buffer(20), pits.buffer(20), roads.buffer(20)])],
                       out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
    ok_flat, bg_flat = in_tile.ravel(), (in_tile & ~zone).ravel()
    excl = pd.concat([pads.buffer(S.PAD_EXCL), roads.buffer(S.PAD_EXCL)]).union_all()
    sets = []
    for g in pads.geometry:
        core, rg = S.pixel_sets(g, S.PAD_CORE_M, S.PAD_RING, excl, tf, shape, ok_flat)
        if len(core) == 0 or len(rg) < 10:
            continue
        pls = S.placebo_sets(g, S.PAD_CORE_M, S.PAD_RING, excl, tf, shape, ok_flat, bg_flat, rng, 5, tries=60)
        if pls:
            sets.append(((core, rg), pls))
    print("pads", len(sets))

    rows = []
    for r in idx.itertuples():
        for pi, pol in ((0, "hh"), (1, "hv")):
            L = inten[r.file][pi].ravel()
            f = np.array([mean_db(L, c) - mean_db(L, g) for (c, g), _ in sets])
            d = np.array([np.nanmedian([mean_db(L, c) - mean_db(L, g) for c, g in pls]) for _, pls in sets])
            ex = f - d
            ok = np.isfinite(ex)
            boot = [np.median(rng.choice(ex[ok], ok.sum())) for _ in range(500)]
            rows.append(dict(date=str(r.date), track=int(r.track), season=r.season or "transition",
                             collection=r.collection, pol=pol, n_pads=int(ok.sum()),
                             excess_db=round(float(np.median(ex[ok])), 3),
                             ci_lo=round(float(np.percentile(boot, 2.5)), 3), ci_hi=round(float(np.percentile(boot, 97.5)), 3)))
    df = pd.DataFrame(rows)
    out = S.OUT / f"nisar_pad_season_per_date_{A.TAG}.csv"
    df.to_csv(out, index=False)
    print(df.to_string())

    summ = {}
    for pol, g in df.groupby("pol"):
        fa, su = g[g.season == "leafoff_fall"], g[g.season == "leafon"]
        mw = mannwhitneyu(fa.excess_db, su.excess_db, alternative="less")
        per_track = {}
        for t, gt in g.groupby("track"):
            s, f = gt[gt.season == "leafon"].excess_db, gt[gt.season == "leafoff_fall"].excess_db
            per_track[int(t)] = dict(summer_min=float(s.min()), summer_max=float(s.max()), summer_median=float(s.median()),
                                     fall=f.tolist(), fall_below_all_summer=int((f < s.min()).sum()), n_fall=len(f))
        summ[pol] = dict(n_fall_dates=len(fa), n_summer_dates=len(su),
                         fall_median=float(fa.excess_db.median()), summer_median=float(su.excess_db.median()),
                         fall_negative=int((fa.excess_db < 0).sum()), summer_negative=int((su.excess_db < 0).sum()),
                         mannwhitney_fall_lt_summer_p=float(mw.pvalue), per_track=per_track,
                         transition_dates=g[g.season == "transition"][["date", "track", "excess_db"]].to_dict("records"))
    print(json.dumps(summ, indent=1))
    p = S.OUT / f"nisar_pad_season_per_date_summary_{A.TAG}.json"
    p.write_text(json.dumps(summ, indent=1))
    print("wrote", out, p)


if __name__ == "__main__":
    main()
