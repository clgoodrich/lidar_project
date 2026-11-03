"""Fetch the four 2006-2008 USGS lidar tiles that cover 9t, one at a time, backing off when the server says 429.

Source: USGS 3DEP legacy project PA_STATEWIDE_N_2006_2008 on rockyweb.usgs.gov (public domain). List: data/_source/reference/downloadlist_2006-2008_laz.txt
Tiles 002958, 002959, 003111, 003112 (30.6 + 17.0 + 36.9 + 20.6 percent of 9t, with overlaps). About 35 MB each.
Saved to data/9t/derived/lidar_2006_2008/ (*.laz is git-ignored). A file under 1 MB is an HTML error page and is deleted and retried.
The files are read as EPSG:2271 (NAD83 PA North, US survey feet). Never trust their own CRS tag (see docs/iterations/BACKLOG.md, "CRS ALERT").

Run:
  python notebooks/wellsight_v2/s1_build/_fetch_lidar_2006_9t.py
"""
from __future__ import annotations

import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/9t/derived/lidar_2006_2008"
BASE = "https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/legacy/PA_STATEWIDE_N_2006_2008/LAZ/"
TILES = ["003111", "003112", "002958", "002959"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for t in TILES:
        name = f"USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_{t}.laz"
        f = OUT / name
        if f.exists() and f.stat().st_size > 1_000_000:
            print(t, "have", f.stat().st_size)
            continue
        for attempt in range(12):
            r = requests.get(BASE + name, stream=True, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                with open(f, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                print(t, "ok", f.stat().st_size, flush=True)
                break
            wait = 30 * (attempt + 1)
            print(t, "status", r.status_code, "wait", wait, flush=True)
            time.sleep(wait)
        time.sleep(10)


if __name__ == "__main__":
    main()
