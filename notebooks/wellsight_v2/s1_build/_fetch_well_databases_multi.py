"""Fetch public well databases into their own folders under data/_source/reference/.

Rules (docs/plans/download_manifest.md section 1). Measure size first. Never overwrite. Hash. Write _PROVENANCE.json per folder.
Well databases only. No lidar is fetched here.

Run: python notebooks/wellsight_v2/s1_build/_fetch_well_databases_multi.py [source_id ...]
No ids means every source in SOURCES. Use --dry to list sizes without writing.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "data/_source/reference"
UA = {"User-Agent": "lidar-well-research/1.0"}
LIMIT = 100 * 1024 * 1024  # larger than this needs a .gitignore rule before fetch

# id -> (folder, filename, url, note)
SOURCES = {
    "usgs_orphan_2022_csv": ("wells_us_orphan_2022", "US_orphaned_wells.csv",
        "https://www.sciencebase.gov/catalog/file/get/62ebd67bd34eacf539724c56?f=__disk__11%2Fe9%2F27%2F11e927c652d995f46129f282b400063b5d262369",
        "USGS United States Documented Unplugged Orphaned Oil and Gas Well Dataset, 2022, doi:10.5066/P91PJETI. 117,672 wells, 27 states."),
    "usgs_orphan_2022_xml": ("wells_us_orphan_2022", "US_orphaned_wells.xml",
        "https://www.sciencebase.gov/catalog/file/get/62ebd67bd34eacf539724c56?f=__disk__bc%2F7f%2F67%2Fbc7f67cf8c35dbff08f1148c0681b67fca6b26d3",
        "Metadata for the 2022 release."),
    "usgs_orphan_2026_xml": ("wells_us_orphan_2026", "US_orphaned_wells_2026.xml",
        "https://www.sciencebase.gov/catalog/file/get/6aad481a1ba49ba9a487439b?f=__disk__3e%2Ff6%2F8b%2F3ef68b9b690a9b1f3bbf6c6678265e686486f265",
        "Metadata for the 2026 release. The 2026 CSV and XLSX are flagged unpublished on ScienceBase and could not be fetched by script. Download by hand from doi:10.5066/P13FHBYG."),
    "ny_regulated_wells_csv": ("wells_ny_dec", "ny_oil_gas_regulated_wells_since_1860.csv",
        "https://data.ny.gov/api/views/szye-wmt3/rows.csv?accessType=DOWNLOAD",
        "NY DEC Oil, Gas and Other Regulated Wells beginning 1860, data.ny.gov szye-wmt3."),
    "ny_orphaned_wells_csv": ("wells_ny_dec", "ny_orphaned_wells.csv",
        "https://data.ny.gov/api/views/vgue-bamz/rows.csv?accessType=DOWNLOAD",
        "NY DEC Orphaned Wells, data.ny.gov vgue-bamz."),
    "ky_kgs_wells_zip": ("wells_ky_kgs", "kyog_dd.zip", "https://kgs.uky.edu/ogdata/kyog_dd.zip",
        "Kentucky Geological Survey oil and gas well location shapefile, 162,166 locations. Copyright KGS, University of Kentucky. Acknowledge KGS."),
    "ky_kgs_wells_info": ("wells_ky_kgs", "kyog_info.txt", "https://kgs.uky.edu/ogdata/kyog_info.txt", "Metadata for the KGS shapefile."),
    "ok_occ_wells_zip": ("wells_ok_occ", "RBDMS_WELLS.zip", "https://oklahoma.gov/content/dam/ok/en/occ/documents/og/esri/files/RBDMS_WELLS.zip",
        "Oklahoma Corporation Commission RBDMS wells shapefile, refreshed nightly."),
    "ok_occ_orphans_xlsx": ("wells_ok_occ", "orphan-well-list.xlsx", "https://oklahoma.gov/content/dam/ok/en/occ/documents/og/ogdatafiles/orphan-well-list.xlsx",
        "Oklahoma Corporation Commission orphaned wells, all districts."),
    "ok_occ_orphans_dict": ("wells_ok_occ", "orphan-wells-data-dictionary.xlsx", "https://oklahoma.gov/content/dam/ok/en/occ/documents/og/ogdatafiles/orphan-wells-data-dictionary.xlsx", "Data dictionary."),
    "ok_occ_wells_dict": ("wells_ok_occ", "rbdms-wells-data-dictionary.xlsx", "https://oklahoma.gov/content/dam/ok/en/occ/documents/og/ogdatafiles/rbdms-wells-data-dictionary.xlsx", "Data dictionary."),
    "il_isgs_wells_zip": ("wells_il_isgs", "IL_WELLS_Borings_Location_Pt.zip", "https://chf.isgs.illinois.edu/Clearinghouse/data/ISGS/Geology/zips/IL_WELLS_Borings_Location_Pt.zip",
        "ISGS Wells and Borings location points, about 16 MB. Oil, gas, water wells and borings. Filter by type."),
}


def head(url):
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(r.headers.get("Content-Length") or -1), r.headers.get("Content-Type", "")
    except Exception as e:  # some servers refuse HEAD
        return -1, f"HEAD failed {e}"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    ids = args or list(SOURCES)
    for sid in ids:
        folder, name, url, note = SOURCES[sid]
        d = BASE / folder
        out = d / name
        size, ctype = head(url)
        print(f"{sid}: {url}\n   size {size} bytes  type {ctype}")
        if dry:
            continue
        if "html" in ctype.lower() and not name.lower().endswith((".html", ".htm")):
            print("   server returned an HTML page, not the file. Skipped.")
            continue
        if size > LIMIT:
            print("   over 100 MB. Add a .gitignore rule first. Skipped.")
            continue
        if out.exists():
            print(f"   exists, not overwritten: {out}")
            continue
        d.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".part")
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
        if "html" in (r_type := ctype.lower()) and not name.lower().endswith((".html", ".htm")):
            tmp.unlink()
            continue
        head_bytes = tmp.read_bytes()[:200].lower()
        if head_bytes.lstrip().startswith((b"<!doctype html", b"<html")) and not name.lower().endswith((".html", ".htm")):
            tmp.unlink()
            print("   downloaded content is HTML. Discarded.")
            continue
        tmp.rename(out)
        prov_path = d / "_PROVENANCE.json"
        prov = json.loads(prov_path.read_text()) if prov_path.exists() else {}
        prov[name] = dict(url=url, accessed=time.strftime("%Y-%m-%d"), bytes=out.stat().st_size, sha256=sha(out), note=note)
        prov_path.write_text(json.dumps(prov, indent=2))
        print(f"   saved {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
