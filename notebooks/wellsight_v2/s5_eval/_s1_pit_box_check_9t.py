"""Is the pixel at a point brighter than its surroundings in early-April Sentinel-1 C-band, date by date?

Sentinel-1 RTC (10 m pixels, ~20 m resolution, VV and VH) from the Microsoft Planetary Computer, read as a small
window out of cloud-optimised GeoTIFFs, so nothing large is downloaded. Early April is 25 Mar to 15 Apr.
For each date: VV in dB at the pixel holding the point, the median of a 250 m background (the point's 30 m
excluded), and the difference. Steadiness per track is the amplitude dispersion (std / mean of linear VV).

Run:
  python notebooks/wellsight_v2/s5_eval/_s1_pit_box_check_9t.py [lon lat]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests
from pyproj import Transformer
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
LON, LAT = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) > 2 else (-79.523777, 41.513789)
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel1euwestrtc/sentinel1-grd-rtc"
HALF = 300.0
BG = 250.0
EXCL = 30.0
OUT = ROOT / "data/9t/results/nisar"


def early_april(d: str) -> bool:
    return (d[5:7] == "04" and int(d[8:10]) <= 15) or (d[5:7] == "03" and int(d[8:10]) >= 25)


def main():
    body = {"collections": ["sentinel-1-rtc"], "intersects": {"type": "Point", "coordinates": [LON, LAT]},
            "datetime": "2016-01-01T00:00:00Z/2026-10-28T00:00:00Z", "limit": 500}
    feats = [f for f in requests.post(STAC, json=body, timeout=60).json()["features"] if early_april(f["properties"]["datetime"][:10])]
    sas = requests.get(TOKEN, timeout=60).json()["token"]
    rows = []
    for f in sorted(feats, key=lambda x: x["properties"]["datetime"]):
        href = f["assets"]["vv"]["href"] + "?" + sas
        try:
            with rasterio.open(href) as r:
                x, y = Transformer.from_crs(4326, r.crs, always_xy=True).transform(LON, LAT)
                win = from_bounds(x - HALF, y - HALF, x + HALF, y + HALF, transform=r.transform)
                a = r.read(1, window=win, boundless=True, fill_value=np.nan).astype("float64")
                res = r.res[0]
        except Exception as e:  # noqa: BLE001
            print("skip", f["id"], e)
            continue
        n = a.shape[0]
        yy, xx = np.mgrid[:n, :n]
        d = np.hypot(yy - n / 2, xx - n / 2) * res
        c = a[int(n / 2), int(n / 2)]
        bg = a[(d > EXCL) & (d <= BG) & np.isfinite(a)]
        if not np.isfinite(c) or bg.size < 100:
            continue
        rows.append(dict(date=f["properties"]["datetime"][:10], track=f["properties"]["sat:relative_orbit"],
                         vv=c, bg=np.median(bg), db_over_bg=10 * np.log10(c / np.median(bg)),
                         rank_pct=float((bg < c).mean() * 100)))
    D = pd.DataFrame(rows)
    D.to_csv(OUT / "s1_pit_box_check_9t.csv", index=False)
    print(D.round(3).to_string(index=False))
    for t, g in D.groupby("track"):
        print(f"track {t}: n {len(g)}  mean dB over background {g.db_over_bg.mean():.1f}  dispersion {g.vv.std() / g.vv.mean():.2f}")


if __name__ == "__main__":
    main()
