"""Fetch USGS 3DEP LiDAR Point Cloud (LPC) tile inventory for the Permian TX bbox.

Saves per-tile metadata (id, project, date, size, bbox, downloadURL) to a parquet
file. Does NOT download LAZ payloads. Use _filter_3dep_tiles_to_well_pads.py next
to subset to tiles intersecting Ramachandran well-pad polygons.
"""
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

OUT_DIR = Path(r"C:\Users\colto\Documents\GitHub\lidar_project\data\external\usgs_3dep_permian_tx")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Permian TX bbox from Ramachandran deployment detections
BBOX = (-104.9120, 29.5481, -100.0603, 33.9583)  # minx, miny, maxx, maxy
API = "https://tnmaccess.nationalmap.gov/api/v1/products"
PAGE = 1000


def fetch_page(offset):
    url = (f"{API}?datasets=Lidar%20Point%20Cloud%20(LPC)"
           f"&bbox={BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}"
           f"&prodFormats=LAS,LAZ&max={PAGE}&offset={offset}")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            print(f"  retry {attempt+1} after error: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed offset {offset}")


def main():
    first = fetch_page(0)
    total = first["total"]
    print(f"Total LPC products: {total:,}")

    rows = []
    items = first["items"]
    rows.extend(items)
    offset = PAGE
    while offset < total:
        print(f"  offset {offset:,} / {total:,}")
        page = fetch_page(offset)
        rows.extend(page["items"])
        offset += PAGE

    # Flatten to a tabular schema
    flat = []
    for it in rows:
        bb = it.get("boundingBox", {}) or {}
        flat.append({
            "sourceId": it.get("sourceId"),
            "title": it.get("title"),
            "project": it.get("sourceOriginName"),
            "publicationDate": it.get("publicationDate"),
            "dateCreated": it.get("dateCreated"),
            "sizeInBytes": it.get("sizeInBytes"),
            "format": it.get("format"),
            "downloadURL": it.get("downloadURL"),
            "downloadLazURL": it.get("downloadLazURL"),
            "metaUrl": it.get("metaUrl"),
            "minX": bb.get("minX"),
            "minY": bb.get("minY"),
            "maxX": bb.get("maxX"),
            "maxY": bb.get("maxY"),
        })
    df = pd.DataFrame(flat)
    out = OUT_DIR / "tile_inventory.parquet"
    df.to_parquet(out, index=False)
    print(f"\nSaved {len(df):,} rows -> {out}")
    print(f"Total payload size (LAZ): {df['sizeInBytes'].sum() / 1e12:.2f} TB")
    print(f"Unique projects: {df['project'].nunique()}")
    print(df.groupby("project").agg(n_tiles=("sourceId", "size"),
                                    tb=("sizeInBytes", lambda s: s.sum() / 1e12)).sort_values("tb", ascending=False))


if __name__ == "__main__":
    main()
