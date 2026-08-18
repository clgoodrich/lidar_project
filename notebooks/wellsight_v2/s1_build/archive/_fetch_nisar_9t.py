"""Fetch NISAR L-band granules covering the 9t core (NW Pennsylvania).

NISAR products live in ASF's Earthdata Cloud and require a (free) Earthdata Login.
Set up auth ONCE, then run this:

  1) register / sign in at https://urs.earthdata.nasa.gov
  2) create a .netrc in your home dir (Windows: %USERPROFILE%\\_netrc) containing:
         machine urs.earthdata.nasa.gov
         login    YOUR_USERNAME
         password YOUR_PASSWORD
  3) python notebooks/wellsight_v2/s1_build/_fetch_nisar_9t.py            # GCOV + GUNW
     python notebooks/wellsight_v2/s1_build/_fetch_nisar_9t.py --list     # plan only
     python notebooks/wellsight_v2/s1_build/_fetch_nisar_9t.py --collections NISAR_L2_GCOV_BETA_V1

Granules go to data/external/nisar/9t/<short_name>/. These are ~20 m L-SAR products
(GCOV backscatter, GUNW InSAR deformation) — landscape-scale context, NOT fine feature
detection (see analysis_log). Files are large .h5 -> gitignored.

NOTE: over 9t, only *BETA* (pre-calibration) products exist as of 2026-06; validated
CONUS products begin ~July 2026.
"""
from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import ROOT, path_for  # noqa: E402

DST = path_for("reference") / "nisar" / "9t"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
# 9t core bbox in lon/lat (from EPSG:6346 619500,4593000..624000,4597500)
BBOX = (-79.5687, 41.4797, -79.5139, 41.5195)  # W,S,E,N
DEFAULT_COLLECTIONS = ["NISAR_L2_GCOV_BETA_V1", "NISAR_L2_GUNW_BETA_V1"]


def query(short_name: str) -> list[dict]:
    q = {"short_name": short_name,
         "bounding_box": ",".join(map(str, BBOX)),
         "page_size": 200, "sort_key": "-start_date"}
    url = CMR + "?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=90) as r:
        items = json.load(r)["items"]
    out = []
    for it in items:
        u = it["umm"]
        h5 = [x["URL"] for x in u.get("RelatedUrls", [])
              if x.get("Type", "").startswith("GET DATA") and x["URL"].endswith(".h5")]
        if h5:
            out.append({"id": u["GranuleUR"], "url": h5[0],
                        "date": (u.get("TemporalExtent", {})
                                 .get("RangeDateTime", {})
                                 .get("BeginningDateTime", ""))[:10]})
    return out


def download(url: str, dest: Path) -> bool:
    """Download via requests, honoring ~/.netrc for the urs.earthdata redirect."""
    import requests
    if dest.exists() and dest.stat().st_size > 0:
        print(f"    skip (exists) {dest.name}"); return True
    try:
        with requests.Session() as s:
            s.trust_env = True  # use .netrc for the urs.earthdata.nasa.gov auth hop
            with s.get(url, stream=True, allow_redirects=True, timeout=120) as r:
                if r.status_code == 401:
                    print("    AUTH FAILED (401) — check Earthdata .netrc"); return False
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.rename(dest)
        print(f"    ok {dest.name} ({dest.stat().st_size/1e6:.0f} MB)")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"    FAIL {dest.name}: {e}")
        p = dest.with_suffix(dest.suffix + ".part")
        if p.exists(): p.unlink()
        return False


def _free_gb(path: Path) -> float:
    import shutil
    return shutil.disk_usage(str(path)).free / 1e9


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collections", help="comma list (default GCOV+GUNW beta)")
    ap.add_argument("--list", action="store_true", help="plan only, no download")
    ap.add_argument("--max", type=int, default=0, help="max granules per collection (0=all)")
    ap.add_argument("--min-free-gb", type=float, default=8.0,
                    help="stop before a download if free space would drop below this")
    args = ap.parse_args()
    cols = args.collections.split(",") if args.collections else DEFAULT_COLLECTIONS
    DST.mkdir(parents=True, exist_ok=True)
    total = 0
    for sn in cols:
        gran = query(sn)
        print(f"\n== {sn}: {len(gran)} granules over 9t ==")
        for g in gran:
            print(f"   {g['date']}  {g['id']}")
        if args.list:
            continue
        if args.max:
            gran = gran[:args.max]
        gdir = DST / sn; gdir.mkdir(parents=True, exist_ok=True)
        for g in gran:
            free = _free_gb(DST)
            if free < args.min_free_gb:
                print(f"  STOP: only {free:.1f} GB free (< {args.min_free_gb}); skipping rest")
                break
            if download(g["url"], gdir / f"{g['id']}.h5"):
                total += 1
    print(f"\n{'planned' if args.list else 'downloaded'} {total} granules -> {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
