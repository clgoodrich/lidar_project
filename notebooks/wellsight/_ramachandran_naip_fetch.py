"""Ramachandran replication — full NAIP chip fetcher.

Fetches 512x512 JPEG chips from Microsoft Planetary Computer NAIP STAC for
each `extent_image` polygon in well-pad_dataset.csv (~88K chips, ~7 GB).

Parallelized via threadpool. Idempotent (skips existing files). Per-tile
fetch latency is dominated by STAC search + COG read; 16 threads is a good
balance for residential bandwidth.
"""
import argparse
import io
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import imageio.v3 as iio
import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from shapely import wkt

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
CSV = ROOT / "data/external/ramachandran_2024/permian_denver_data/training/well-pad_dataset.csv"
OUT = ROOT / "data/external/ramachandran_2024/naip_chips"
OUT.mkdir(parents=True, exist_ok=True)
LOG_PATH = OUT / "_fetch_log.csv"

CHIP_SIZE = 512  # match paper constants.IMG_SIZE
JPEG_QUALITY = 90
N_THREADS = 16

_catalog = None
_catalog_lock = threading.Lock()


def get_catalog():
    global _catalog
    with _catalog_lock:
        if _catalog is None:
            _catalog = pystac_client.Client.open(
                "https://planetarycomputer.microsoft.com/api/stac/v1",
                modifier=pc.sign_inplace,
            )
        return _catalog


def fetch_one(image_id, extent_wkt, has_pad, split):
    out_path = OUT / split / f"{image_id}.jpg"
    if out_path.exists():
        return image_id, "cached", None
    out_path.parent.mkdir(parents=True, exist_ok=True)

    geom = wkt.loads(extent_wkt)
    minx, miny, maxx, maxy = geom.bounds
    try:
        cat = get_catalog()
        search = cat.search(collections=["naip"], bbox=(minx, miny, maxx, maxy))
        items = list(search.items())
        if not items:
            return image_id, "no_items", None
        items.sort(key=lambda i: i.datetime, reverse=True)
        item = items[0]
        href = item.assets["image"].href
        year = item.datetime.year
        with rasterio.open(href) as src:
            rb = transform_bounds("EPSG:4326", src.crs, minx, miny, maxx, maxy)
            win = from_bounds(*rb, transform=src.transform)
            arr = src.read([1, 2, 3], window=win,
                           out_shape=(3, CHIP_SIZE, CHIP_SIZE),
                           resampling=Resampling.bilinear)
        arr = np.transpose(arr, (1, 2, 0)).astype(np.uint8)
        iio.imwrite(out_path, arr, quality=JPEG_QUALITY)
        return image_id, "ok", year
    except Exception as e:
        return image_id, f"err:{type(e).__name__}", str(e)[:120]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--splits", nargs="+", default=["train", "valid", "test"])
    args = ap.parse_args()

    df = pd.read_csv(CSV)
    df["has_pad"] = df["annotations_latlon"] != "[]"
    df = df[df.split.isin(args.splits)].reset_index(drop=True)
    if args.limit:
        df = df.head(args.limit)

    print(f"Fetching {len(df):,} chips -> {OUT}")
    print(f"Splits: {df.split.value_counts().to_dict()}")

    t0 = time.time()
    results = []
    completed = 0
    with ThreadPoolExecutor(max_workers=N_THREADS) as ex:
        futures = {
            ex.submit(fetch_one, r.image_id, r.extent_image, r.has_pad, r.split): r.image_id
            for r in df.itertuples()
        }
        for fut in as_completed(futures):
            image_id, status, info = fut.result()
            results.append({"image_id": image_id, "status": status, "info": info})
            completed += 1
            if completed % 100 == 0:
                dt = time.time() - t0
                rate = completed / dt
                eta = (len(df) - completed) / rate
                print(f"  {completed:,}/{len(df):,} done, {rate:.1f}/s, ETA {eta/60:.1f} min")

    log = pd.DataFrame(results)
    log.to_csv(LOG_PATH, index=False)
    print(f"\nDone in {(time.time()-t0)/60:.1f} min")
    print(log.status.value_counts())


if __name__ == "__main__":
    main()
