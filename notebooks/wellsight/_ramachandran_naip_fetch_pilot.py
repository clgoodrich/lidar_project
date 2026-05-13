"""Ramachandran replication — NAIP chip fetcher (pilot).

Per CLAUDE.md bootstrap rule: pilot 50 chips (25 pos + 25 neg) from the
Permian basin before scaling to the full 88K dataset. Verify chips look right.

Source: Microsoft Planetary Computer NAIP STAC API.
NAIP is USDA, public domain, 0.6 m resolution (newer collects), CONUS only.
"""
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from shapely import wkt

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
CSV = ROOT / "data/external/ramachandran_2024/permian_denver_data/training/well-pad_dataset.csv"
OUT = ROOT / "data/external/ramachandran_2024/naip_chips_pilot"
OUT.mkdir(parents=True, exist_ok=True)

CHIP_SIZE = 640  # match paper

catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=pc.sign_inplace,
)


def fetch_chip(image_id, extent_geom, out_png):
    minx, miny, maxx, maxy = extent_geom.bounds
    search = catalog.search(
        collections=["naip"],
        bbox=(minx, miny, maxx, maxy),
        # NAIP every ~2-3 years per state; prefer latest before 2024 cutoff
    )
    items = list(search.items())
    if not items:
        return None, "no_items"
    # Pick most recent
    items.sort(key=lambda i: i.datetime, reverse=True)
    item = items[0]
    asset = item.assets["image"]
    with rasterio.open(asset.href) as src:
        # Reproject extent bounds from EPSG:4326 to raster CRS
        rb = transform_bounds("EPSG:4326", src.crs, minx, miny, maxx, maxy)
        win = from_bounds(*rb, transform=src.transform)
        arr = src.read([1, 2, 3], window=win,
                       out_shape=(3, CHIP_SIZE, CHIP_SIZE),
                       resampling=rasterio.enums.Resampling.bilinear)
    arr = np.transpose(arr, (1, 2, 0)).astype(np.uint8)
    import imageio.v3 as iio
    iio.imwrite(out_png, arr)
    return item.datetime.year, "ok"


def main():
    df = pd.read_csv(CSV)
    df["has_pad"] = df["annotations_latlon"] != "[]"
    # Pilot: 25 pos + 25 neg from Permian train, deterministic
    permian_train = df[(df.split == "train") & (df.basin == "permian")]
    pos = permian_train[permian_train.has_pad].head(25)
    neg = permian_train[~permian_train.has_pad].head(25)
    pilot = pd.concat([pos, neg]).reset_index(drop=True)

    rows = []
    for _, r in pilot.iterrows():
        geom = wkt.loads(r.extent_image)
        label = "pos" if r.has_pad else "neg"
        out_png = OUT / f"{r.image_id}_{label}.png"
        if out_png.exists():
            year, status = -1, "cached"
        else:
            try:
                year, status = fetch_chip(r.image_id, geom, out_png)
            except Exception as e:
                year, status = None, f"err:{type(e).__name__}:{str(e)[:80]}"
        rows.append(dict(image_id=r.image_id, label=label, year=year, status=status))
        print(f"  {r.image_id:>6} {label} {status}")

    log = pd.DataFrame(rows)
    log.to_csv(OUT / "_fetch_log.csv", index=False)
    print(f"\nOK: {(log.status == 'ok').sum()} / {len(log)}")
    print(f"Cached: {(log.status == 'cached').sum()}")
    print(f"Failures: {(~log.status.isin(['ok','cached'])).sum()}")
    print(log.status.value_counts())


if __name__ == "__main__":
    main()
