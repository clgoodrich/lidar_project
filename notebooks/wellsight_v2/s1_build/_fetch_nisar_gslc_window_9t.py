"""Pull the 9t window out of every NISAR L2 GSLC over the tile, without downloading whole files.

WHY
---
A GSLC is the full-resolution geocoded radar image, with phase kept. Each file
covers a whole frame and is about 22.6 GB. 9t is 4.5 km across, about 1000 x 1000
pixels at the 5 m posting. The files are chunked HDF5 (512 x 512, gzip) on the
ASF cloud, so h5py can read only the chunks that cover 9t over HTTPS range
requests. That is about 40 MB per polarization per date instead of 22.6 GB.

WHAT IT KEEPS
-------------
One GeoTIFF per acquisition date and track, 2 bands, complex64:
band 1 = HH, band 2 = HV, EPSG:32617 on the product's own 5 m grid.
Phase is kept so coherence and interferograms can be formed later from the
same files. Invalid samples (mask 0 or 255) are written as NaN.

A CSV index records each file's track, direction, frame, date, collection
(beta / provisional), bandwidth and centre frequency.

Where one date is covered by two overlapping frames, the frame whose valid mask
covers more of 9t is kept.

AUTH
----
Earthdata credentials in ~/_netrc (Windows) or ~/.netrc. The first request
follows the Earthdata redirect to a signed CloudFront URL. That URL takes range
requests without further auth for about an hour, so each file is resolved just
before it is read.

Run:
  python notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py
  python notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py --list
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import fsspec
import geopandas as gpd
import h5py
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.transform import from_origin
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
from _common import path_for  # noqa: E402

CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
COLLECTIONS = ["NISAR_L2_GSLC_BETA_V1", "NISAR_L2_GSLC_PROVISIONAL_V1"]
BBOX = (-79.5687, 41.4797, -79.5139, 41.5195)  # 9t in lon/lat, W S E N
HILL = path_for("data") / "9t" / "derived" / "1m" / "hillshade_9t_1m.tif"
OUT = path_for("data") / "9t" / "derived" / "nisar_gslc_5m"
CRS = "EPSG:32617"
MARGIN_M = 200.0
GRID = "science/LSAR/GSLC/grids/frequencyA"


def query() -> pd.DataFrame:
    rows = []
    for sn in COLLECTIONS:
        q = {"short_name": sn, "bounding_box": ",".join(map(str, BBOX)), "page_size": 200}
        with urllib.request.urlopen(CMR + "?" + urllib.parse.urlencode(q), timeout=90) as r:
            items = json.load(r)["items"]
        for it in items:
            u = it["umm"]
            url = [x["URL"] for x in u["RelatedUrls"]
                   if x["URL"].startswith("https") and x["URL"].endswith(".h5")
                   and not x["URL"].endswith("_QA_STATS.h5")][0]
            t = u["GranuleUR"].split("_")
            # NISAR_L2_PR_GSLC_<cycle>_<track>_<dir>_<frame>_<mode>_<pols>_...
            rows.append(dict(granule=u["GranuleUR"], url=url,
                             collection="beta" if "BETA" in sn else "provisional",
                             cycle=int(t[4]), track=int(t[5]), direction=t[6], frame=int(t[7]),
                             date=u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"][:10]))
    return pd.DataFrame(rows).sort_values(["date", "track", "frame"]).reset_index(drop=True)


def window_bounds() -> tuple[float, float, float, float]:
    with rasterio.open(HILL) as r:
        b = gpd.GeoSeries([box(*r.bounds)], crs=r.crs).to_crs(CRS).total_bounds
    # snap outward to the 5 m product grid edges (multiples of 5 m)
    x0 = np.floor((b[0] - MARGIN_M) / 5) * 5
    y0 = np.floor((b[1] - MARGIN_M) / 5) * 5
    x1 = np.ceil((b[2] + MARGIN_M) / 5) * 5
    y1 = np.ceil((b[3] + MARGIN_M) / 5) * 5
    return x0, y0, x1, y1


def signed_url(url: str) -> str:
    with requests.Session() as s:
        r = s.get(url, stream=True, allow_redirects=True, timeout=120)
        if r.status_code == 401:
            raise RuntimeError("Earthdata auth failed (401); check ~/_netrc")
        r.raise_for_status()
        final = r.url
        r.close()
    return final


def read_window(url: str, wb) -> dict:
    x0, y0, x1, y1 = wb
    f = fsspec.filesystem("http").open(signed_url(url), block_size=8 * 2**20, cache_type="blockcache")
    with h5py.File(f, "r") as h:
        g = h[GRID]
        epsg = int(g["projection"][()])
        if f"EPSG:{epsg}" != CRS:
            raise RuntimeError(f"unexpected EPSG {epsg}")
        x = g["xCoordinates"][:]
        y = g["yCoordinates"][:]
        dx = float(g["xCoordinateSpacing"][()])
        # coordinates are pixel centres; the window keeps centres inside wb
        ci = np.where((x > x0) & (x < x1))[0]
        ri = np.where((y > y0) & (y < y1))[0]
        if len(ci) == 0 or len(ri) == 0:
            return {}
        sl = (slice(ri[0], ri[-1] + 1), slice(ci[0], ci[-1] + 1))
        mask = g["mask"][sl]
        hh = g["HH"][sl]
        hv = g["HV"][sl]
        meta = dict(x_first_centre=float(x[ci[0]]), y_first_centre=float(y[ri[0]]),
                    spacing_m=dx, ncols=len(ci), nrows=len(ri),
                    range_bandwidth_hz=float(g["rangeBandwidth"][()]),
                    centre_frequency_hz=float(g["centerFrequency"][()]))
    bad = (mask == 0) | (mask == 255)
    hh = np.where(bad, np.nan + 0j, hh).astype(np.complex64)
    hv = np.where(bad, np.nan + 0j, hv).astype(np.complex64)
    meta["valid_fraction"] = float((~bad).mean())
    return dict(hh=hh, hv=hv, meta=meta)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    df = query()
    print(df[["date", "collection", "track", "direction", "frame"]].to_string())
    if args.list:
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    wb = window_bounds()
    print(f"window (EPSG:32617) {wb}")
    index_path = OUT / "nisar_gslc_window_index_9t_5m.csv"
    done = pd.read_csv(index_path) if index_path.exists() else pd.DataFrame()
    rows = done.to_dict("records")
    for (date, track), grp in df.groupby(["date", "track"]):
        name = f"nisar_gslc_hh_hv_complex_{date.replace('-', '')}_t{track:03d}{grp.direction.iat[0]}_9t_5m.tif"
        path = OUT / name
        if path.exists():
            print(f"skip {name}")
            continue
        best = None
        for g in grp.itertuples():
            t = time.time()
            try:
                w = read_window(g.url, wb)
            except Exception as e:  # noqa: BLE001
                print(f"  FAIL {g.granule}: {e}")
                continue
            if not w:
                continue
            print(f"  {g.granule[:60]}... valid {w['meta']['valid_fraction']:.3f} ({time.time()-t:.0f} s)")
            if best is None or w["meta"]["valid_fraction"] > best[1]["meta"]["valid_fraction"]:
                best = (g, w)
        if best is None:
            continue
        g, w = best
        m = w["meta"]
        tf = from_origin(m["x_first_centre"] - m["spacing_m"] / 2, m["y_first_centre"] + m["spacing_m"] / 2,
                         m["spacing_m"], m["spacing_m"])
        with rasterio.open(path, "w", driver="GTiff", width=m["ncols"], height=m["nrows"], count=2,
                           dtype="complex64", crs=CRS, transform=tf, compress="deflate") as d:
            d.write(w["hh"], 1)
            d.write(w["hv"], 2)
            d.set_band_description(1, "HH")
            d.set_band_description(2, "HV")
        rows.append(dict(file=name, date=date, collection=g.collection, cycle=g.cycle, track=track,
                         direction=g.direction, frame=g.frame, granule=g.granule, **m))
        pd.DataFrame(rows).to_csv(index_path, index=False)
        print(f"wrote {path}")
    print(f"index {index_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
