"""Save georeferenced leaf-off aerial photo windows (GeoTIFF, EPSG:6346) around chosen pits, for QGIS.

Source: PEMA county mosaics (PASDA map service PEMAImagery2018): layer 242 Venango, then layer 110 Forest where Venango is blank
(pits east of about -79.52 lon). Flight dates not yet confirmed from metadata.
Window 100 m square, 700 x 700 px (0.143 m). One file per pit_inside_id: data/9t/results/pit/photo/pit_leafoff_photo_<id>_9t.tif

Run:
  python notebooks/wellsight_v2/s5_eval/_pit_leafoff_geotiff_9t.py [id id ...]
Default ids: 288 plus the 12 labelled pits (wet 157 163 170 206 222 218 136, dry 133 534 192 184 519).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import requests
from PIL import Image
from rasterio.transform import from_bounds

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"
OUT = ROOT / "data/9t/results/pit/photo"
URL = "https://services.pasda.psu.edu/server/rest/services/pasda/PEMAImagery2018/MapServer/export"
LAYERS = (242, 110)
HALF, N = 50.0, 700
DEFAULT = [288, 157, 163, 170, 206, 222, 218, 136, 133, 534, 192, 184, 519]


def main(ids):
    pi = gpd.read_file(G, layer="pit_inside").set_index("pit_inside_id")
    OUT.mkdir(parents=True, exist_ok=True)
    for pid in ids:
        cx, cy = pi.loc[pid].geometry.centroid.coords[0]
        x0, y0, x1, y1 = cx - HALF, cy - HALF, cx + HALF, cy + HALF
        for lay in LAYERS:
            r = requests.get(URL, params=dict(bbox=f"{x0},{y0},{x1},{y1}", bboxSR=6346, imageSR=6346, size=f"{N},{N}",
                                              layers=f"show:{lay}", format="png", f="image"), timeout=90)
            a = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"))
            if a.mean() < 240:
                break
        else:
            print(pid, "no photo in any mosaic")
            continue
        f = OUT / f"pit_leafoff_photo_{pid}_9t.tif"
        with rasterio.open(f, "w", driver="GTiff", width=N, height=N, count=3, dtype="uint8", crs="EPSG:6346",
                           transform=from_bounds(x0, y0, x1, y1, N, N), compress="deflate") as d:
            d.write(np.moveaxis(a, -1, 0))
        print(pid, f.name, "layer", lay)


if __name__ == "__main__":
    main([int(v) for v in sys.argv[1:]] or DEFAULT)
