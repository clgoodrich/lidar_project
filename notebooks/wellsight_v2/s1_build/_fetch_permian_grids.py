"""Fetch USGS 3DEP LPC tiles for contiguous 3x3 grids over Permian well clusters.

For each user-specified Permian center (CENTERS below), query the USGS National Map
(TNM) for Lidar Point Cloud products, find a contiguous 3x3 of 1.5 km tiles centered
on the nearest tile (adjacency computed from bbox geometry, so it works for both
6-digit `14SKA940715` and 4-digit `13RFQ8095` tile-code schemes), and download those
9 LAZ/LAS into data/source_laz/permian/<grid>/.

A manifest (permian_grids_manifest.json) records each grid's tiles, project, and
native UTM zone so the build step (_build_label_grids --build-permian) can mosaic
them. "Any 3DEP" policy: takes whatever quality level TNM returns.

CLI:
  python notebooks/wellsight_v2/s1_build/_fetch_permian_grids.py            # all 4
  python notebooks/wellsight_v2/s1_build/_fetch_permian_grids.py --only permian_02
  python notebooks/wellsight_v2/s1_build/_fetch_permian_grids.py --list     # plan only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import ROOT

DST = ROOT / "data" / "source_laz" / "permian"
API = "https://tnmaccess.nationalmap.gov/api/v1/products"
# user-specified high-density Permian centers (lat, lon); 3x3 of 1.5 km tiles each
CENTERS = {
    "permian_01": (32.2805, -101.1629),
    "permian_02": (32.2225, -102.2139),
    "permian_03": (31.66615, -103.02572),
    "permian_04": (30.6161, -101.1393),
}
# tile token after the project name: 6-digit (14SKA940715) OR 4-digit (13RFQ8095).
# group(1) = UTM zone number. Grid adjacency is computed from bbox geometry, not the
# code digits, so this only needs to extract a clean tile id + zone (naming-agnostic).
CODE_RE = re.compile(r"(\d{2})[A-Z]{3}\d{4,6}")


def query(lat, lon, d=0.08, tries=8):  # ~9 km box: enough for a 4.5 km 3x3 + slop
    bbox = f"{lon-d},{lat-d},{lon+d},{lat+d}"
    q = {"datasets": "Lidar Point Cloud (LPC)", "bbox": bbox,
         "prodFormats": "LAS,LAZ", "max": 200}
    url = API + "?" + urllib.parse.urlencode(q)
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read().decode("utf-8", "replace")
            return json.loads(body).get("items", [])
        except (json.JSONDecodeError, urllib.error.URLError, OSError) as e:  # noqa: PERF203
            last = e
            wait = 3 * (attempt + 1)  # 3,6,9,12s backoff (TNM rate-limits/HTML errors)
            print(f"  TNM query failed ({type(e).__name__}); retry {attempt+1}/{tries} in {wait}s")
            _sleep(wait)
    raise RuntimeError(f"TNM query failed after {tries} tries: {last}")


def _sleep(s):
    import time
    time.sleep(s)


def parse(items):
    """id -> dict(url, title, zone, cx, cy, w, h) keeping one per tile id."""
    out = {}
    for it in items:
        m = CODE_RE.search(it.get("title", ""))
        url = (it.get("downloadLazURL") or it.get("downloadURL")
               or it.get("urls", {}).get("LAZ") or it.get("urls", {}).get("LAS"))
        bb = it.get("boundingBox", {})
        if not m or not url or not bb:
            continue
        code = m.group(0)
        if code in out:
            continue
        cx = (bb.get("minX", 0) + bb.get("maxX", 0)) / 2
        cy = (bb.get("minY", 0) + bb.get("maxY", 0)) / 2
        w = bb.get("maxX", 0) - bb.get("minX", 0)
        h = bb.get("maxY", 0) - bb.get("minY", 0)
        out[code] = dict(url=url, title=it.get("title", ""), zone=m.group(1),
                         id=code, cx=cx, cy=cy, w=w, h=h)
    return out


def pick_3x3(tiles, lat, lon):
    """Pick a contiguous 3x3 around the seed using bbox GEOMETRY (naming-agnostic).

    Estimates the tile pitch from median bbox width/height, then snaps to the 9 cells
    seed_center + (i,j)*pitch for i,j in {-1,0,1}, matching each to the nearest actual
    tile within half a pitch. Works for both 6-digit and 4-digit USGS tile codes.
    """
    if not tiles:
        return None
    vals = list(tiles.values())
    import statistics as st
    px = st.median(t["w"] for t in vals)
    py = st.median(t["h"] for t in vals)
    if px <= 0 or py <= 0:
        return None
    seed = min(vals, key=lambda t: (t["cx"] - lon) ** 2 + (t["cy"] - lat) ** 2)
    picked, used = [], set()
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            tx, ty = seed["cx"] + i * px, seed["cy"] + j * py
            cand = min(vals, key=lambda t: ((t["cx"] - tx) / px) ** 2 + ((t["cy"] - ty) / py) ** 2)
            dx = abs(cand["cx"] - tx) / px; dy = abs(cand["cy"] - ty) / py
            if dx <= 0.5 and dy <= 0.5 and cand["id"] not in used:
                used.add(cand["id"]); picked.append(cand)
    return picked if len(picked) >= 4 else None


def download(url, dest: Path):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"    skip (exists) {dest.name}"); return True
    try:
        with urllib.request.urlopen(url, timeout=600) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        print(f"    ok {dest.name} ({dest.stat().st_size/1e6:.0f} MB)")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"    FAIL {dest.name}: {e}")
        if dest.exists():
            dest.unlink()
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated grid names")
    ap.add_argument("--list", action="store_true", help="plan only, no download")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None
    DST.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, (lat, lon) in CENTERS.items():
        if only and name not in only:
            continue
        print(f"\n== {name} ({lat:.4f},{lon:.4f}) ==")
        tiles = parse(query(lat, lon))
        grid = pick_3x3(tiles, lat, lon)
        if not grid:
            print(f"  no contiguous 3x3 found ({len(tiles)} tiles seen)"); continue
        proj = grid[0]["title"].rsplit(" ", 1)[0]
        zone = grid[0]["zone"]
        codes = [t["id"] for t in grid]
        print(f"  project: {proj}")
        print(f"  zone {zone}  {len(codes)} tiles: {codes}")
        manifest[name] = {"project": proj, "utm_zone": zone, "tiles": codes,
                          "urls": [t["url"] for t in grid]}
        if args.list:
            continue
        gdir = DST / name; gdir.mkdir(parents=True, exist_ok=True)
        for t in grid:
            download(t["url"], gdir / f"{t['id']}.laz")
    (DST / "permian_grids_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nmanifest -> {DST / 'permian_grids_manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
