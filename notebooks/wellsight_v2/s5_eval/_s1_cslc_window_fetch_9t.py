"""Read only the 9t + 613590 window out of remote OPERA CSLC-S1 bursts, for early-to-mid April 2017-2024.

Same product as _s1_cslc_fetch_9t.py (OPERA CSLC-S1 V1, VV), but the HDF5 is opened over HTTPS with byte-range
reads (h5py + fsspec) and only the window UTM 17N E 613300-624200, N 4589800-4597700 is kept. That covers both
areas plus the 200 m margin the pit script reads. About 27 s and 14 MB per date instead of 270 MB.
Each window is written with the OPERA layout (data/VV, data/x_coordinates, data/y_coordinates, data/x_spacing,
data/y_spacing, data/projection, identification/orbit_pass_direction) under the original granule name, in
data/_source/s1_cslc_windows/ (git-ignored), so _s1_ifg_pits_9t.py reads it like a full burst.

  python notebooks/wellsight_v2/s5_eval/_s1_cslc_window_fetch_9t.py [2017 ... 2024]
  python notebooks/wellsight_v2/s5_eval/_s1_cslc_window_fetch_9t.py --range 2025-04-01 2026-04-15 T077
Windows also keep data/azimuth_carrier_phase (float32), which must be removed before any oversampling.
"""
import sys
import time
from pathlib import Path

import fsspec
import h5py
import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[3]
DEST = ROOT / "data" / "_source" / "s1_cslc_windows"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
POINTS = [(-79.541, 41.500), (-79.611, 41.476)]
E0, E1, N0, N1 = 613300, 624200, 4589800, 4597700


def search(year=None, start=None, end=None, track=None):
    start = start or f"{year}-03-25"
    end = end or f"{year}-04-20"
    urls = {}
    for lon, lat in POINTS:
        r = requests.get(CMR, params={"short_name": "OPERA_L2_CSLC-S1_V1", "point": f"{lon},{lat}",
                                      "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z",
                                      "page_size": 200}, timeout=60)
        r.raise_for_status()
        for e in r.json()["feed"]["entry"]:
            h5 = [l["href"] for l in e["links"] if l["href"].startswith("https") and l["href"].endswith(".h5")]
            if h5 and (track is None or f"_{track}-" in e["title"]):
                urls[e["title"]] = h5[0]
    return urls


def cut(title, url):
    out = DEST / f"{title}.h5"
    if out.exists():
        return "have"
    signed = requests.get(url, headers={"Range": "bytes=0-0"}, timeout=60).url
    with h5py.File(fsspec.open(signed, block_size=2 ** 21, cache_type="blockcache").open(), "r") as h:
        xs, ys = h["data/x_coordinates"][:], h["data/y_coordinates"][:]
        c = np.where((xs >= E0) & (xs <= E1))[0]
        r = np.where((ys >= N0) & (ys <= N1))[0]
        vv = h["data/VV"][r.min():r.max() + 1, c.min():c.max() + 1]
        meta = {k: h[f"data/{k}"][()] for k in ("x_spacing", "y_spacing", "projection")}
        carrier = h["data/azimuth_carrier_phase"][r.min():r.max() + 1, c.min():c.max() + 1].astype(np.float32)
        pas = h["identification/orbit_pass_direction"][()]
    tmp = out.with_suffix(".part")
    with h5py.File(tmp, "w") as o:
        o["data/VV"] = vv
        o["data/azimuth_carrier_phase"] = carrier   # needed to deramp before oversampling
        o["data/x_coordinates"] = xs[c.min():c.max() + 1]
        o["data/y_coordinates"] = ys[r.min():r.max() + 1]
        for k, v in meta.items():
            o[f"data/{k}"] = v
        o["identification/orbit_pass_direction"] = pas
        o.attrs["source_url"] = url
        o.attrs["window_utm17n"] = [E0, E1, N0, N1]
    tmp.rename(out)
    return f"{vv.shape}"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    if "--range" in sys.argv:      # --range START END TRACK, e.g. --range 2025-04-01 2026-04-15 T077
        i = sys.argv.index("--range")
        jobs = [search(start=sys.argv[i + 1], end=sys.argv[i + 2], track=sys.argv[i + 3])]
    else:
        jobs = [search(int(y)) for y in (sys.argv[1:] or range(2017, 2025))]
    for urls in jobs:
        for title, url in sorted(urls.items()):
            t0 = time.time()
            for attempt in range(3):
                try:
                    print(title, cut(title, url), f"{time.time() - t0:.0f}s", flush=True)
                    break
                except Exception as ex:  # noqa: BLE001  transient HTTP errors: retry, then report
                    print("retry", title, type(ex).__name__, flush=True)
                    time.sleep(5)


if __name__ == "__main__":
    main()
