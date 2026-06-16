"""Fetch USGS 3DEP LPC tiles for contiguous 2x2 grids over Permian well clusters.

For each well-dense Permian center (from _build_label_grids select_permian), query
the USGS National Map (TNM) for Lidar Point Cloud products, find a contiguous 2x2
of 1.5 km tiles nearest the center (tile codes adjacent by +15 = +1500 m), and
download those 4 LAZ/LAS into data/source_laz/permian/<grid>/.

A manifest (permian_grids_manifest.json) records each grid's tiles, project, and
native UTM zone so the build step (_build_label_grids --build-permian, TODO) can
mosaic them. "Any 3DEP" policy: takes whatever quality level TNM returns.

CLI:
  python notebooks/wellsight_v2/build/_fetch_permian_grids.py            # all 4
  python notebooks/wellsight_v2/build/_fetch_permian_grids.py --only permian_02
  python notebooks/wellsight_v2/build/_fetch_permian_grids.py --list     # plan only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import ROOT

DST = ROOT / "data" / "source_laz" / "permian"
API = "https://tnmaccess.nationalmap.gov/api/v1/products"
# densest RRC-orphan 3 km cells (lat, lon) from select_permian
CENTERS = {
    "permian_01": (30.0946, -100.5863),
    "permian_02": (31.2334, -102.8319),
    "permian_03": (30.7515, -101.7776),
    "permian_04": (32.3297, -101.1496),
}
# tile code like 13RGQ040575 or 14SKA985760  ->  (square, E3, N3)
CODE_RE = re.compile(r"(\d{2}[A-Z]{3})(\d{3})(\d{3})")
STEP = 15  # code units per 1500 m tile


def query(lat, lon, d=0.05):
    bbox = f"{lon-d},{lat-d},{lon+d},{lat+d}"
    q = {"datasets": "Lidar Point Cloud (LPC)", "bbox": bbox,
         "prodFormats": "LAS,LAZ", "max": 200}
    url = API + "?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r).get("items", [])


def parse(items):
    """code -> dict(url, title, square, e, n, cx, cy) keeping one per code."""
    out = {}
    for it in items:
        m = CODE_RE.search(it.get("title", ""))
        url = it.get("downloadURL") or it.get("urls", {}).get("LAZ") or it.get("urls", {}).get("LAS")
        bb = it.get("boundingBox", {})
        if not m or not url:
            continue
        code = m.group(0)
        if code in out:
            continue
        cx = (bb.get("minX", 0) + bb.get("maxX", 0)) / 2
        cy = (bb.get("minY", 0) + bb.get("maxY", 0)) / 2
        out[code] = dict(url=url, title=it.get("title", ""), square=m.group(1),
                         e=int(m.group(2)), n=int(m.group(3)), cx=cx, cy=cy)
    return out


def pick_2x2(tiles, lat, lon):
    """Pick a contiguous 2x2 (same square, +STEP neighbours) nearest (lat,lon)."""
    if not tiles:
        return None
    # nearest tile to the center by footprint center (lon/lat)
    seed = min(tiles.values(), key=lambda t: (t["cx"] - lon) ** 2 + (t["cy"] - lat) ** 2)
    sq, e0, n0 = seed["square"], seed["e"], seed["n"]
    # try the 4 arrangements that include the seed corner
    for de, dn in ((0, 0), (-STEP, 0), (0, -STEP), (-STEP, -STEP)):
        ec, nc = e0 + de, n0 + dn
        want = [f"{sq}{ec+i*STEP:03d}{nc+j*STEP:03d}" for i in (0, 1) for j in (0, 1)]
        have = [c for c in want if c in tiles]
        if len(have) == 4:
            return [tiles[c] for c in want]
    # fallback: seed + the 3 nearest same-square tiles
    same = sorted((t for t in tiles.values() if t["square"] == sq),
                  key=lambda t: (t["e"] - e0) ** 2 + (t["n"] - n0) ** 2)
    return same[:4] if len(same) >= 4 else None


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
        grid = pick_2x2(tiles, lat, lon)
        if not grid:
            print(f"  no contiguous 2x2 found ({len(tiles)} tiles seen)"); continue
        proj = grid[0]["title"].split(" LAS")[0]
        zone = grid[0]["square"][:2]
        codes = [CODE_RE.search(t["title"]).group(0) for t in grid]
        print(f"  project: {proj}")
        print(f"  zone {zone}  tiles: {codes}")
        manifest[name] = {"project": proj, "utm_zone": zone, "tiles": codes,
                          "urls": [t["url"] for t in grid]}
        if args.list:
            continue
        gdir = DST / name; gdir.mkdir(parents=True, exist_ok=True)
        for t, code in zip(grid, codes):
            download(t["url"], gdir / f"{code}.laz")
    (DST / "permian_grids_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nmanifest -> {DST / 'permian_grids_manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
