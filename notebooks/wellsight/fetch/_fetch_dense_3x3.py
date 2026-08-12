"""Discover and download USGS 3DEP LiDAR Point Cloud tiles for the densest
4.5 km x 4.5 km abandoned/orphan well boxes in three PA regions of interest.

Bboxes precomputed from data/derivatives/annotations/oil_gas_locations.gpkg
(EPSG:6346 UTM 17N). For each region we hit the USGS TNM Access API with the
expanded bbox, take the most common (top-by-tile-count) 3DEP project that
covers it, pick the 9 tiles whose centroids are closest to the dense-well
centroid (the "3x3" approximation), and download them.

CLI:
  python notebooks/wellsight/fetch/_fetch_dense_3x3.py            # download all 3
  python notebooks/wellsight/fetch/_fetch_dense_3x3.py --list     # plan only, no DL
  python notebooks/wellsight/fetch/_fetch_dense_3x3.py --regions sw,nec
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import ROOT

OUT_BASE = ROOT / "data" / "external" / "usgs_3dep_pa_lidar" / "laz"
OUT_BASE.mkdir(parents=True, exist_ok=True)

API = "https://tnmaccess.nationalmap.gov/api/v1/products"

# (key, label, bbox_utm17n, well_filter_description)
REGIONS = [
    ("sw",  "SW PA  (Washington/Greene, orphan+abandoned)",
     (579747.0, 4397690.0, 584247.0, 4402190.0)),
    ("nec", "NE PA  (Bradford/Susquehanna, all-status densest)",
     (919973.0, 4625454.0, 924473.0, 4629954.0)),
    ("wc",  "W-central PA (Indiana/Clarion, orphan+abandoned)",
     (664020.0, 4524373.0, 668520.0, 4528873.0)),
]


def utm_to_lonlat_bbox(utm_bbox: tuple[float, float, float, float], pad_m: float = 1000.0):
    """Expand by ``pad_m`` and convert UTM17N -> lon/lat (WGS84)."""
    x0, y0, x1, y1 = utm_bbox
    x0 -= pad_m; y0 -= pad_m; x1 += pad_m; y1 += pad_m
    t = Transformer.from_crs("EPSG:6346", "EPSG:4326", always_xy=True)
    lon_lat = [t.transform(x, y) for x, y in
               [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]]
    lons = [p[0] for p in lon_lat]; lats = [p[1] for p in lon_lat]
    return min(lons), min(lats), max(lons), max(lats)


def tnm_list(bbox_lonlat: tuple[float, float, float, float]) -> list[dict]:
    """List LiDAR Point Cloud products covering ``bbox_lonlat`` (lon/lat)."""
    qs = urllib.parse.urlencode({
        "datasets": "Lidar Point Cloud (LPC)",
        "bbox": ",".join(f"{v:.6f}" for v in bbox_lonlat),
        "prodFormats": "LAS,LAZ",
        "max": 500, "offset": 0,
    })
    with urllib.request.urlopen(f"{API}?{qs}", timeout=60) as r:
        return json.load(r).get("items", [])


_TITLE_PREFIX = "USGS Lidar Point Cloud "


def project_of(item: dict) -> str:
    """Extract the 3DEP project name from a TNM product title.

    Titles are always of the form ``USGS Lidar Point Cloud <PROJECT> <TILE>``.
    Drop the prefix, then everything except the final whitespace-separated
    token is the project name.
    """
    title = item.get("title", "")
    if title.startswith(_TITLE_PREFIX):
        title = title[len(_TITLE_PREFIX):]
    toks = title.rsplit(maxsplit=1)
    return toks[0] if toks else "?"


def project_year(project: str) -> int:
    """Year heuristic: find the first 4-digit 20XX in the project name."""
    import re
    m = re.search(r"(20\d{2})", project)
    return int(m.group(1)) if m else 0


def pick_3x3(items: list[dict], utm_bbox: tuple[float, float, float, float],
             project: str) -> list[dict]:
    """Pick 9 tiles from ``items`` whose centroids are closest to the centre of
    the dense-well box (in UTM17N). Restricts to a single 3DEP project."""
    t_in = Transformer.from_crs("EPSG:4326", "EPSG:6346", always_xy=True)
    cx_target = 0.5 * (utm_bbox[0] + utm_bbox[2])
    cy_target = 0.5 * (utm_bbox[1] + utm_bbox[3])
    candidates: list[tuple[float, dict]] = []
    for it in items:
        if project_of(it) != project:
            continue
        bb = it.get("boundingBox", {}) or {}
        if not all(k in bb for k in ("minX", "minY", "maxX", "maxY")):
            continue
        cx, cy = t_in.transform(0.5 * (bb["minX"] + bb["maxX"]),
                                0.5 * (bb["minY"] + bb["maxY"]))
        d2 = (cx - cx_target) ** 2 + (cy - cy_target) ** 2
        candidates.append((d2, it))
    candidates.sort(key=lambda kv: kv[0])
    return [it for _, it in candidates[:9]]


def download_one(url: str, dest: Path, expected: int,
                 retries: int = 5, chunk: int = 1 << 20) -> tuple[str, str]:
    if dest.exists() and dest.stat().st_size == expected and expected > 0:
        return ("skip", dest.name)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r, open(tmp, "wb") as f:
                while True:
                    buf = r.read(chunk)
                    if not buf:
                        break
                    f.write(buf)
            tmp.rename(dest)
            return ("ok", dest.name)
        except Exception as e:
            last_err = e
            time.sleep(min(2 ** attempt, 30))
    return ("err", f"{dest.name}: {last_err}")


def plan_region(key: str, label: str, utm_bbox):
    bb = utm_to_lonlat_bbox(utm_bbox, pad_m=1500.0)
    items = tnm_list(bb)
    if not items:
        print(f"  [{key}] no LPC products returned")
        return None
    counts = Counter(project_of(it) for it in items)
    # Prefer the newest project (latest year), tie-broken by tile count.
    project = max(counts, key=lambda p: (project_year(p), counts[p]))
    print(f"  projects available: {dict(counts.most_common())}")
    print(f"  -> selected: {project} (year={project_year(project)})")
    chosen = pick_3x3(items, utm_bbox, project)
    if not chosen:
        print(f"  [{key}] no tiles after project filter")
        return None
    total_bytes = sum(int(it.get("sizeInBytes", 0) or 0) for it in chosen)
    print(f"  [{key}] project={project}  candidates={len(items)}  "
          f"chosen={len(chosen)}  size={total_bytes/1e9:.2f} GB")
    return {"key": key, "label": label, "project": project, "tiles": chosen,
            "total_bytes": total_bytes}


def download_region(plan: dict, *, workers: int = 4) -> None:
    dest_dir = OUT_BASE / plan["project"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(it["downloadURL"], dest_dir / it["downloadURL"].rsplit("/", 1)[-1],
             int(it.get("sizeInBytes", 0) or 0))
            for it in plan["tiles"] if it.get("downloadURL")]
    print(f"\n[{plan['key']}] -> {dest_dir}  ({len(jobs)} tiles)")
    t0 = time.time()
    ok = skip = err = 0
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(download_one, u, d, s) for u, d, s in jobs]
        for i, fut in enumerate(cf.as_completed(futs), 1):
            status, msg = fut.result()
            if status == "ok": ok += 1
            elif status == "skip": skip += 1
            else: err += 1; print(f"  ERR {msg}")
            if i % 3 == 0 or i == len(futs):
                print(f"  [{i}/{len(futs)}]  ok={ok} skip={skip} err={err}  "
                      f"elapsed={time.time()-t0:.0f}s")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true",
                    help="plan only, no download")
    ap.add_argument("--regions", help="comma-separated subset of region keys")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    keys = set(args.regions.split(",")) if args.regions else None
    plans: list[dict] = []
    for key, label, bbox in REGIONS:
        if keys and key not in keys:
            continue
        print(f"\n=== {key}: {label} ===")
        print(f"  UTM17N bbox: X[{bbox[0]:.0f}..{bbox[2]:.0f}]  Y[{bbox[1]:.0f}..{bbox[3]:.0f}]")
        p = plan_region(key, label, bbox)
        if p is not None:
            plans.append(p)

    grand = sum(p["total_bytes"] for p in plans)
    print(f"\nTotal plan: {len(plans)} regions  {grand/1e9:.2f} GB across "
          f"{sum(len(p['tiles']) for p in plans)} tiles")

    if args.list:
        for p in plans:
            print(f"\n[{p['key']}] {p['project']}:")
            for t in p["tiles"]:
                print(f"  {t['downloadURL'].rsplit('/', 1)[-1]}  "
                      f"{int(t.get('sizeInBytes', 0) or 0)/1e6:.0f} MB")
        return 0

    for p in plans:
        download_region(p, workers=args.workers)
    print("\nDONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
