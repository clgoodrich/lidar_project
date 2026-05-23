"""Discover and download USGS 3DEP Lidar Point Cloud (LPC) tiles for a region.

Uses the USGS TNM Access API to find LAZ products by bounding box, then streams
downloads to data/external/lidar/<region>/laz/.  Default mode is **dry-run**:
prints a manifest of tiles + sizes without downloading. Pass --download to actually
fetch.

Examples:
    # Dry-run for McKean County PA (lists tiles, no download)
    python notebooks/wellsight/data/_download_lidar.py \\
        --region mckean_pa \\
        --bbox -78.92 41.40 -78.20 42.02

    # Same, but actually download (skips files already on disk)
    python notebooks/wellsight/data/_download_lidar.py \\
        --region mckean_pa --bbox -78.92 41.40 -78.20 42.02 --download

    # Use a canned preset (see PRESETS below) — bbox is implied
    python notebooks/wellsight/data/_download_lidar.py --preset mckean_pa --download

    # Limit how many files you grab in one go
    python notebooks/wellsight/data/_download_lidar.py --preset mckean_pa --download --max-files 20

Data source: USGS 3D Elevation Program (3DEP) via The National Map Access API.
Cite as: U.S. Geological Survey, 3D Elevation Program, National Geospatial Program.
"""
import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
OUT_ROOT = ROOT / "data" / "external" / "lidar"

# Bounding boxes in WGS84 (lon_min, lat_min, lon_max, lat_max).
# Western PA counties relevant to orphan-well work.
PRESETS = {
    # The training tile lives in Forest County PA — extending a margin around it.
    "forest_co_pa":     (-79.50, 41.30, -78.85, 41.85),
    # Methane super-emitter county from the Kang 2014 paper.
    "mckean_pa":        (-78.92, 41.40, -78.20, 42.02),
    "potter_pa":        (-78.10, 41.40, -77.45, 42.02),
    "elk_pa":           (-79.10, 41.20, -78.20, 41.70),
    "warren_pa":        (-79.85, 41.55, -78.95, 42.05),
    "venango_pa":       (-80.20, 41.18, -79.55, 41.65),
    "clarion_pa":       (-79.85, 40.95, -79.10, 41.45),
    # Wide net across the PA northern tier (use sparingly — many GB).
    "pa_northern_tier": (-80.50, 41.20, -76.50, 42.10),
}

TNM_API = "https://tnmaccess.nationalmap.gov/api/v1/products"
PAGE_SIZE = 100
USER_AGENT = "WellSight-LiDAR-Downloader/1.0 (research)"


def query_tnm(bbox, page_size=PAGE_SIZE, max_pages=200):
    """Page through TNM LAZ results for the given bbox.

    Note: do NOT pass a `datasets` filter — TNM rejects the dataset name strings
    and returns an errorMessage payload.  `prodFormats=LAZ` alone scopes to point-
    cloud products (3DEP LPC).
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    bbox_str = f"{lon_min},{lat_min},{lon_max},{lat_max}"
    results = []
    offset = 0
    for page in range(max_pages):
        params = {
            "bbox": bbox_str,
            "prodFormats": "LAZ",
            "outputFormat": "JSON",
            "max": page_size,
            "offset": offset,
        }
        resp = requests.get(TNM_API, params=params, timeout=60,
                            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        data = resp.json()
        if "errorMessage" in data:
            raise RuntimeError(f"TNM error: {data['errorMessage']}")
        items = data.get("items", [])
        results.extend(items)
        total = int(data.get("total") or 0)
        if not items or offset + page_size >= total:
            break
        offset += page_size
        time.sleep(0.2)  # polite
    return results


def normalize_record(item):
    """Map a TNM item to our manifest schema."""
    urls = item.get("urls", {})
    laz_url = urls.get("LAZ") or urls.get("LAS")
    if not laz_url:
        # Fall back to downloadURL if present
        laz_url = item.get("downloadURL")
    if not laz_url:
        return None
    name = item.get("title") or Path(urlparse(laz_url).path).name
    return {
        "title": name,
        "url": laz_url,
        "size_bytes": int(item.get("sizeInBytes") or 0),
        "bbox": item.get("boundingBox", {}),
        "publication_date": item.get("publicationDate", ""),
        "vendor": item.get("vendorMetaUrl", ""),
        "metadata_url": item.get("metaUrl", ""),
        "tnm_id": item.get("sourceId") or item.get("downloadId") or "",
    }


def discover(bbox):
    items = query_tnm(bbox)
    if not items:
        print("No LAZ items returned by TNM for that bbox.")
        return []
    print(f"TNM returned {len(items)} LAZ items.")
    recs = [normalize_record(i) for i in items]
    return [r for r in recs if r]


def write_manifest(region_dir, records):
    manifest_path = region_dir / "manifest.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "size_mb", "url", "publication_date", "tnm_id"])
        for r in records:
            w.writerow([r["title"], f"{r['size_bytes']/1e6:.1f}",
                        r["url"], r["publication_date"], r["tnm_id"]])
    # Also dump full JSON for forensics
    (region_dir / "manifest.json").write_text(json.dumps(records, indent=2))
    return manifest_path


def safe_filename(url, title):
    """Prefer the URL's basename; fall back to title with bad chars stripped."""
    name = Path(urlparse(url).path).name
    if name and name.lower().endswith((".laz", ".las")):
        return name
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in title)
    if not safe.lower().endswith((".laz", ".las")):
        safe += ".laz"
    return safe


def stream_download(url, dest, expected_size=None):
    """Download with progress bar; skip if already complete."""
    if dest.exists():
        if expected_size and dest.stat().st_size == expected_size:
            return "skip-complete"
        if expected_size == 0 and dest.stat().st_size > 0:
            return "skip-unknown-size"
    headers = {"User-Agent": USER_AGENT}
    # Resume support if partial file exists
    mode = "wb"
    pos = 0
    if dest.exists() and expected_size and dest.stat().st_size < expected_size:
        pos = dest.stat().st_size
        headers["Range"] = f"bytes={pos}-"
        mode = "ab"
    with requests.get(url, stream=True, headers=headers, timeout=120) as resp:
        if resp.status_code not in (200, 206):
            return f"http-{resp.status_code}"
        total = expected_size or int(resp.headers.get("Content-Length", 0)) + pos
        with open(dest, mode) as f, tqdm(
                total=total or None, initial=pos, unit="B", unit_scale=True,
                desc=dest.name, leave=False) as bar:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
    return "ok"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", choices=sorted(PRESETS.keys()),
                    help="Canned bbox (overrides --bbox if both given)")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("LONMIN", "LATMIN", "LONMAX", "LATMAX"),
                    help="WGS84 bounding box: lon_min lat_min lon_max lat_max")
    ap.add_argument("--region", help="Folder name under data/external/lidar/ (default: derived from preset or 'custom')")
    ap.add_argument("--download", action="store_true",
                    help="Actually download files. Without this, only the manifest is written.")
    ap.add_argument("--max-files", type=int, default=None,
                    help="Cap number of files downloaded this run (skips ones already on disk).")
    ap.add_argument("--max-size-gb", type=float, default=None,
                    help="Stop after total bytes downloaded exceeds this cap.")
    args = ap.parse_args()

    if args.preset:
        bbox = PRESETS[args.preset]
        region_name = args.region or args.preset
    elif args.bbox:
        bbox = tuple(args.bbox)
        region_name = args.region or "custom"
    else:
        ap.error("Pass --preset or --bbox.")

    if not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90):
        ap.error(f"Invalid bbox: {bbox}")

    region_dir = OUT_ROOT / region_name
    laz_dir = region_dir / "laz"
    laz_dir.mkdir(parents=True, exist_ok=True)
    print(f"Region: {region_name}")
    print(f"BBox  : {bbox}")
    print(f"Output: {region_dir}")
    print(f"Mode  : {'DOWNLOAD' if args.download else 'DRY RUN (no files fetched)'}\n")

    records = discover(bbox)
    if not records:
        sys.exit(0)
    total_mb = sum(r["size_bytes"] for r in records) / 1e6
    print(f"Discovered {len(records)} LAZ products totaling {total_mb:,.0f} MB "
          f"({total_mb/1024:,.1f} GB)\n")
    manifest_path = write_manifest(region_dir, records)
    print(f"Wrote {manifest_path}\n")

    # Show top 10 for sanity
    print("Sample (first 10):")
    for r in records[:10]:
        print(f"  {r['size_bytes']/1e6:7.1f} MB  {r['publication_date']:10s}  {r['title']}")
    if len(records) > 10:
        print(f"  ... +{len(records)-10} more in manifest.csv")

    if not args.download:
        print("\n[DRY RUN] No files downloaded. Re-run with --download to fetch.")
        return

    print(f"\nDownloading to {laz_dir} ...")
    n_ok = n_skip = n_fail = 0
    bytes_this_run = 0
    cap = args.max_size_gb * 1024 * 1024 * 1024 if args.max_size_gb else None
    for i, r in enumerate(records):
        if args.max_files and (n_ok + n_skip) >= args.max_files:
            print(f"Reached --max-files={args.max_files}; stopping.")
            break
        if cap and bytes_this_run >= cap:
            print(f"Reached --max-size-gb={args.max_size_gb}; stopping.")
            break
        dest = laz_dir / safe_filename(r["url"], r["title"])
        try:
            status = stream_download(r["url"], dest, r["size_bytes"])
            if status == "ok":
                n_ok += 1
                bytes_this_run += r["size_bytes"]
                print(f"  [{i+1}/{len(records)}] OK    {dest.name}")
            elif status.startswith("skip"):
                n_skip += 1
                print(f"  [{i+1}/{len(records)}] SKIP  {dest.name} ({status})")
            else:
                n_fail += 1
                print(f"  [{i+1}/{len(records)}] FAIL  {dest.name} ({status})")
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            break
        except Exception as e:
            n_fail += 1
            print(f"  [{i+1}/{len(records)}] ERROR {dest.name} -- {e}")

    print(f"\nDone. ok={n_ok}  skip={n_skip}  fail={n_fail}  "
          f"new_bytes={bytes_this_run/1e9:.2f} GB")
    print(f"Files in: {laz_dir}")


if __name__ == "__main__":
    main()
