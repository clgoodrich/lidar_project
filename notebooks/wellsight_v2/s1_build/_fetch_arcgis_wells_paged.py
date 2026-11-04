"""Page a public ArcGIS REST well layer into one gzipped CSV (attributes plus lon, lat). Well databases only.

Pages by OBJECTID ranges, so the order is stable and no row is repeated. Writes under data/_source/reference/<folder>/ with _PROVENANCE.json.
Never overwrites. Stops if the output would pass 100 MB (add a .gitignore rule first).

Sources
  wv    WVDEP Oil and Gas, layer 7 All DEP Wells, about 154,000 records
  oh    ODNR Division of Oil and Gas Resources Management wells, layer 0, about 239,000 records
  ks    Kansas Geological Survey oil and gas wells, layer 0, about 520,000 records
Run: python notebooks/wellsight_v2/s1_build/_fetch_arcgis_wells_paged.py wv oh ks
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "data/_source/reference"
UA = {"User-Agent": "lidar-well-research/1.0"}
SRC = {
    "wv": ("wells_wv_dep", "wv_dep_all_wells.csv.gz", "https://tagis.dep.wv.gov/arcgis/rest/services/WVDEP_enterprise/oil_gas/MapServer/7", 3000),
    "oh": ("wells_oh_odnr", "oh_odnr_wells.csv.gz", "https://gis2.ohiodnr.gov/arcgis/rest/services/DOG_Services/Oilgas_Wells_10_JS_TEST/MapServer/0", 1000),
    "ks": ("wells_ks_kgs", "ks_kgs_oil_gas_wells.csv.gz", "https://services.kgs.ku.edu/arcgis8/rest/services/oilgas/oilgas_wells/MapServer/0", 1000),
}


def q(url, **p):
    p["f"] = "json"
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url + "/query?" + urllib.parse.urlencode(p), headers=UA), timeout=120) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(3 * (k + 1))
    raise RuntimeError("request failed " + url)


def one(key):
    folder, name, url, page = SRC[key]
    out = BASE / folder / name
    if out.exists():
        print(key, "exists, not overwritten")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    ids = sorted(q(url, where="1=1", returnIdsOnly="true")["objectIds"])
    print(key, len(ids), "ids", flush=True)
    rows = []
    for i in range(0, len(ids), page):
        lo, hi = ids[i], ids[min(i + page, len(ids)) - 1]
        d = q(url, where=f"OBJECTID>={lo} AND OBJECTID<={hi}", outFields="*", returnGeometry="true", outSR="4326")
        for ft in d.get("features", []):
            r = dict(ft["attributes"])
            g = ft.get("geometry") or {}
            r["lon"], r["lat"] = g.get("x"), g.get("y")
            rows.append(r)
        if (i // page) % 20 == 0:
            print(key, i, len(rows), flush=True)
        time.sleep(0.15)
    df = pd.DataFrame(rows)
    tmp = out.with_suffix(".part")
    df.to_csv(tmp, index=False, compression="gzip")
    if tmp.stat().st_size > 100 * 1024 * 1024:
        print("over 100 MB, add a .gitignore rule, file kept as .part")
        return
    tmp.rename(out)
    h = hashlib.sha256(out.read_bytes()).hexdigest()
    pp = out.parent / "_PROVENANCE.json"
    prov = json.loads(pp.read_text()) if pp.exists() else {}
    prov[name] = dict(url=url, accessed=time.strftime("%Y-%m-%d"), rows=len(df), expected=len(ids), bytes=out.stat().st_size, sha256=h,
                      note="ArcGIS REST query paged by OBJECTID, outSR 4326.")
    pp.write_text(json.dumps(prov, indent=2))
    print(key, "saved", out, len(df), "of", len(ids))


if __name__ == "__main__":
    for k in sys.argv[1:]:
        one(k)
