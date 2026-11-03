"""Fetch NLCD 2006 and 2019 land cover for the 9t tile from the MRLC web coverage service (public domain).

Why these two years. They are the two lidar years (2006-2008 and 2019). Both come from the same 2019-release product family
(consistent legend and method), so a class change between them is a land cover change and not a change of map version.
Native grid is 30 m, EPSG:5070. A small window (4.5 km tile plus 150 m) is requested and saved unchanged.

Source: Dewitz, J. (2021) National Land Cover Database (NLCD) 2019 Products, USGS data release, doi:10.5066/P9KZCM54.
Service: https://www.mrlc.gov/geoserver/mrlc_download/wcs  (coverage ids NLCD_2006_Land_Cover_L48, NLCD_2019_Land_Cover_L48)

Outputs: data/9t/derived/landcover/nlcd_2006_landcover_9t.tif, nlcd_2019_landcover_9t.tif

Run:
  python notebooks/wellsight_v2/s1_build/_fetch_nlcd_9t.py
"""
from __future__ import annotations

from pathlib import Path

import requests
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/9t/derived/landcover"
BB6346 = (619500.0, 4593000.0, 624000.0, 4597500.0)
URL = "https://www.mrlc.gov/geoserver/mrlc_download/wcs"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    T = Transformer.from_crs(6346, 5070, always_xy=True)
    xs, ys = zip(*[T.transform(x, y) for x in (BB6346[0], BB6346[2]) for y in (BB6346[1], BB6346[3])])
    x0, x1, y0, y1 = min(xs) - 150, max(xs) + 150, min(ys) - 150, max(ys) + 150
    for yr in (2006, 2019):
        cid = f"mrlc_download__NLCD_{yr}_Land_Cover_L48"
        p = dict(service="WCS", version="2.0.1", request="GetCoverage", coverageid=cid, format="image/geotiff")
        q = [(k, v) for k, v in p.items()] + [("subset", f"X({x0:.0f},{x1:.0f})"), ("subset", f"Y({y0:.0f},{y1:.0f})"),
                                              ("subsettingcrs", "http://www.opengis.net/def/crs/EPSG/0/5070")]
        r = requests.get(URL, params=q, timeout=180, headers={"User-Agent": "Mozilla/5.0"})
        f = OUT / f"nlcd_{yr}_landcover_9t.tif"
        print(yr, r.status_code, r.headers.get("content-type"), len(r.content), flush=True)
        if r.status_code == 200 and r.content[:4] in (b"II*\x00", b"MM\x00*"):
            f.write_bytes(r.content)
            print(f)
        else:
            print(r.text[:500])


if __name__ == "__main__":
    main()
