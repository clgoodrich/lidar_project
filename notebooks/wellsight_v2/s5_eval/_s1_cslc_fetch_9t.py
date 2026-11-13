"""Download OPERA CSLC-S1 bursts (Sentinel-1 C-band, geocoded complex SLC, VV) over 9t and 613590.

OPERA CSLC-S1 V1 (NASA JPL OPERA, distributed by ASF DAAC): one HDF5 per 20 x 85 km burst, UTM grid,
5 m x 10 m posting, flattened against the processing DEM, so two dates from one burst form an
interferogram by s1 * conj(s2). It is the Sentinel-1 counterpart of the NISAR GSLC used in
_nisar_gslc_interferogram_pits_9t.py.

Windows (WINDOWS): octnov2025 = 2025-10-01 to 11-30, the same autumn as NISAR track 162; apr2025 and apr2026 =
25 Mar to 20 Apr (early to mid April, before leaf-out; NISAR has no released dates in spring 2026).
Search is NASA CMR by point (9t and 613590 centres). Downloads use Earthdata login from ~/_netrc.
Files land in data/_source/s1_cslc/ (git-ignored) and are logged in data/_source/_download_ledger.csv.

  python notebooks/wellsight_v2/s5_eval/_s1_cslc_fetch_9t.py [octnov2025] [apr2025] [apr2026]
"""
import csv
import datetime as dt
import hashlib
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
DEST = ROOT / "data" / "_source" / "s1_cslc"
LEDGER = ROOT / "data" / "_source" / "_download_ledger.csv"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
POINTS = {"9t": (-79.541, 41.500), "613590": (-79.611, 41.476)}
WINDOWS = {"octnov2025": ["2025-10-01", "2025-11-30"],
           "apr2025": ["2025-03-25", "2025-04-20"], "apr2026": ["2026-03-25", "2026-04-20"]}


def search(start, end):
    urls = {}
    for area, (lon, lat) in POINTS.items():
        r = requests.get(CMR, params={"short_name": "OPERA_L2_CSLC-S1_V1", "point": f"{lon},{lat}",
                                      "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z", "page_size": 200}, timeout=60)
        r.raise_for_status()
        for e in r.json()["feed"]["entry"]:
            h5 = [l["href"] for l in e["links"] if l["href"].startswith("https") and l["href"].endswith(".h5")]
            if h5:
                urls[e["title"]] = h5[0]
    return urls


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or ["octnov2025"]
    urls = {}
    for n in names:
        urls.update(search(*WINDOWS[n]))
    print(f"{len(urls)} bursts")
    s = requests.Session()
    rows = []
    for title, url in sorted(urls.items()):
        out = DEST / f"{title}.h5"
        if out.exists() and out.stat().st_size > 1e8:
            print("have", out.name)
            continue
        tmp = out.with_suffix(".part")
        with s.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            sha = hashlib.sha256()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(2 ** 22):
                    f.write(chunk)
                    sha.update(chunk)
        tmp.rename(out)
        mb = out.stat().st_size / 1e6
        print(f"got {out.name} {mb:.0f} MB", flush=True)
        rows.append(["s1_cslc", out.name, round(mb, 1), "", dt.date.today().isoformat(), sha.hexdigest()[:10],
                     out.relative_to(ROOT).as_posix()])
    if rows:
        with open(LEDGER, "a", newline="") as f:
            csv.writer(f).writerows(rows)


if __name__ == "__main__":
    main()
