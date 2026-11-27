"""Weather on each NISAR date against the per-date pad darkening, 9t. Set 2026-11-26.

Why
  Pads sit darker than their rings on all 10 dates from Sep 29 to Nov 4, then the sign flips
  (Nov 7 +0.41 dB). Leaf fall is one explanation. Rain, wet ground, frost or snow on single
  dates is another: wet soil changes L-band brightness differently on a bare pad and in forest.
  Nearby NOAA stations show whether the odd dates were wet, frozen or snowy.

Inputs
  NOAA NCEI GHCN-Daily, public access API (no token):
    US1PAVN0036 Pleasantville 3.4 SSW (closest, ~3 km from 9t; CoCoRaHS, 7 am report)
    USC00368888 Titusville Water Works, USC00368873 Tionesta 2 SE Lake, USC00363028 Franklin
    USW00094868 Franklin airport (temperature, wind)
  nisar/results/9t/nisar_pad_season_per_date_9t_slc.csv (from _nisar_pad_season_per_date_9t.py)

Timing
  Tracks 90 and 162 pass about 10:20 UTC (06:20 local). Track 26 passes 00:17 UTC (20:17 local the
  day before). Co-op and CoCoRaHS totals are for the 24 h to about 7 am on the report date, so
  "rain_1d" on the image date covers the night before a morning pass. rain_3d sums 3 report days.

Outputs
  nisar/results/9t/nisar_pad_weather_per_date_9t.csv
  nisar/results/9t/figures/nisar_pad_weather_per_date_9t.png

Run
  python nisar/code/s5_eval/_nisar_pad_weather_9t.py
"""
import io
import sys
import urllib.request
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nisar" / "code"))
import _nisar_fig_style as FS  # noqa: E402

RES = ROOT / "nisar" / "results" / "9t"
RAIN_ST = ["US1PAVN0036", "USC00368888", "USC00368873", "USC00363028"]
AIR_ST = "USW00094868"
API = ("https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations={s}"
       "&startDate=2026-06-10&endDate=2026-11-19&dataTypes=PRCP,SNOW,SNWD,TMAX,TMIN,AWND&units=metric&format=csv")
# lost/found palette, validated all pairs (dE 21.1 deutan worst): blue summer, orange Sep 29-Nov 4, red after
C_SUM, C_FALL, C_LATE = "#1F5FA8", "#D97706", "#A31515"


def fetch(stations):
    req = urllib.request.Request(API.format(s=",".join(stations)), headers={"User-Agent": "nisar-research-script"})
    return pd.read_csv(io.StringIO(urllib.request.urlopen(req, timeout=120).read().decode()))


def main():
    w = fetch(RAIN_ST + [AIR_ST])
    w["DATE"] = pd.to_datetime(w["DATE"])
    raw = RES / "nisar_pad_weather_noaa_daily_9t.csv"
    w.to_csv(raw, index=False)
    rain = w[w.STATION.isin(RAIN_ST)].pivot_table(index="DATE", columns="STATION", values="PRCP")
    snwd = w[w.STATION.isin(RAIN_ST)].pivot_table(index="DATE", columns="STATION", values="SNWD") if "SNWD" in w else None
    air = w[w.STATION == AIR_ST].set_index("DATE")
    rmed = rain.median(axis=1)            # median over stations, mm
    d = pd.read_csv(RES / "nisar_pad_season_per_date_9t_slc.csv")
    d = d.pivot_table(index=["date", "track"], columns="pol", values="excess_db").reset_index()
    rows = []
    for r in d.itertuples():
        t = pd.Timestamp(r.date)
        # morning passes: report on t covers the night before. Evening pass (t26, 20:17 local t-1):
        # the report on t-1 covers to 7 am t-1, the report on t covers that evening.
        key = t if r.track != 26 else t
        rows.append(dict(date=r.date, track=r.track, excess_hh=r.hh, excess_hv=r.hv,
                         rain_1d_mm=float(rmed.get(key, np.nan)),
                         rain_3d_mm=float(rmed.loc[key - pd.Timedelta(days=2):key].sum()),
                         snow_depth_mm=float(snwd.loc[key].max()) if snwd is not None and key in snwd.index else np.nan,
                         tmin_c=float(air.TMIN.get(key - pd.Timedelta(days=0), np.nan)) if "TMIN" in air else np.nan,
                         tmax_prev_c=float(air.TMAX.get(key - pd.Timedelta(days=1), np.nan)) if "TMAX" in air else np.nan,
                         wind_ms=float(air.AWND.get(key, np.nan)) if "AWND" in air else np.nan))
    df = pd.DataFrame(rows).sort_values("date")
    df["period"] = np.where(df.date < "2026-09-29", "summer", np.where(df.date <= "2026-11-04", "sep29_nov04", "after_nov04"))
    out = RES / "nisar_pad_weather_per_date_9t.csv"
    df.round(3).to_csv(out, index=False)
    print(df.round(2).to_string(index=False))
    for v in ("rain_1d_mm", "rain_3d_mm", "tmin_c"):
        ok = df[v].notna()
        rho, p = spearmanr(df.loc[ok, v], df.loc[ok, "excess_hh"])
        print(f"{v}: Spearman rho vs HH excess {rho:+.2f} (p {p:.2f}, n {ok.sum()})")
    print("summer only:")
    s = df[df.period == "summer"]
    for v in ("rain_1d_mm", "rain_3d_mm"):
        rho, p = spearmanr(s[v], s.excess_hh)
        print(f"  {v}: rho {rho:+.2f} p {p:.2f} n {len(s)}")

    FS.apply()
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.0))
    for per, c, m, lab in (("summer", C_SUM, "o", "Summer"), ("sep29_nov04", C_FALL, "s", "Sep 29 to Nov 4"),
                           ("after_nov04", C_LATE, "^", "Nov 7 to 16")):
        g = df[df.period == per]
        ax[0].scatter(pd.to_datetime(g.date), g.excess_hh, c=c, marker=m, s=22, label=lab, edgecolor="k", lw=0.3)
        ax[1].scatter(g.rain_3d_mm, g.excess_hh, c=c, marker=m, s=22, label=lab, edgecolor="k", lw=0.3)
    for a in ax:
        a.axhline(0, color="0.5", lw=0.6)
        a.set_ylabel("Pad minus ring, beyond decoys (dB, HH)")
    ax[0].set_title("a  Each radar date", loc="left")
    ax[1].set_title("b  Against rain in the 3 days before", loc="left")
    ax[1].set_xlabel("Rain, 3 report days, median of 4 stations (mm)")
    ax[0].tick_params(axis="x", rotation=30)
    ax[0].legend(frameon=False, fontsize=6.5)
    fig.tight_layout()
    p = RES / "figures" / "nisar_pad_weather_per_date_9t.png"
    FS.save(fig, p)
    print("wrote", out, raw, p)


if __name__ == "__main__":
    main()
