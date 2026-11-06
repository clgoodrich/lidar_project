"""S1 of framework 4.6. Crop one georeferenced historic sheet to tile 9t and render it for blind digitising.

Purpose. Reproject a scanned sheet (any CRS, e.g. the NAD27 polyconic USGS GeoTIFFs) onto EPSG:6346 over the 9t
corner, measure what share of 9t the sheet actually covers (the 1922 Oil City neatline cuts 9t), and write zoom
renders at 2x and 4x as tiles. Also writes an empty mark sheet in the S4 schema for each digitiser. No lidar and no
records are drawn, so the renders can go to digitisers as they are.
Inputs.
  a sheet GeoTIFF, e.g. data/_source/historic_topo_probe/oil_city_1922_62500.tif (held)
Outputs (default folder data/_source/historic_topo_probe/, override with --out).
  <source>_crop_9t.tif              crop on EPSG:6346
  <source>_zoom2_r<i>c<j>_9t.png    2x renders, 2 by 2 tiles
  <source>_zoom4_r<i>c<j>_9t.png    4x renders, 4 by 4 tiles
  <source>_crop_9t.json             coverage share, resolution, source CRS
  <source>__<digitiser>.csv         empty mark sheets (one per --digitisers name) in the expansion data/raw/marks/
Run.
  python expansions/4_modalities/4_6_historic_maps_aerials/src/_hist_topo_crop_9t.py --sheet data/_source/historic_topo_probe/oil_city_1922_62500.tif --source oil_city_1922 [--res 2.0] [--digitisers d1 d2]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.transform import from_origin
from rasterio.warp import Resampling, calculate_default_transform, reproject

import _hist_kit_4_6 as hk


def crop_to_bbox(sheet: Path, bbox, crs: str, res: float | None = None):
    """Return (array bands x H x W uint8, valid mask H x W bool, transform, res)."""
    x0, y0, x1, y1 = bbox
    with rasterio.open(sheet) as src:
        if src.crs is None:
            raise ValueError(f"{sheet} has no CRS. Georeference it first (S3)")
        if res is None:
            tf, _, _ = calculate_default_transform(src.crs, crs, src.width, src.height, *src.bounds)
            res = float(abs(tf.a))
        W, H = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
        tf = from_origin(x0, y1, res, res)
        out = np.zeros((src.count, H, W), np.uint8)
        for b in range(src.count):
            reproject(rasterio.band(src, b + 1), out[b], dst_transform=tf, dst_crs=crs,
                      resampling=Resampling.bilinear, dst_nodata=0)
        ones = np.ones((src.height, src.width), np.uint8)
        valid = np.zeros((H, W), np.uint8)
        reproject(ones, valid, src_transform=src.transform, src_crs=src.crs, dst_transform=tf, dst_crs=crs,
                  resampling=Resampling.nearest, dst_nodata=0)
        src_crs = src.crs.to_string()
    return out, valid.astype(bool), tf, res, src_crs


def neatline_mask(tf, shape, crs: str, neatline) -> np.ndarray:
    """True where a crop pixel centre lies inside the sheet neatline (west, south, east, north in NAD27 lon/lat).
    The scan collar is valid raster but not map, so cover share must come from the neatline, not the pixels."""
    from pyproj import Transformer
    H, W = shape
    cols, rows = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    x, y = tf * (cols, rows)
    lon, lat = Transformer.from_crs(crs, "EPSG:4267", always_xy=True).transform(x, y)
    w, s, e, n = neatline
    return (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)


def zoom_tiles(rgb: np.ndarray, zoom: int):
    """Split an H x W x 3 image into zoom x zoom tiles, each upsampled by zoom (nearest, so symbols stay crisp)."""
    H, W = rgb.shape[:2]
    for i in range(zoom):
        for j in range(zoom):
            t = rgb[i * H // zoom:(i + 1) * H // zoom, j * W // zoom:(j + 1) * W // zoom]
            yield i, j, np.kron(t, np.ones((zoom, zoom, 1), np.uint8))


def main(argv=None) -> int:
    cfg = hk.load_cfg()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sheet", required=True, help="georeferenced sheet GeoTIFF")
    ap.add_argument("--source", required=True, help="short source id, e.g. oil_city_1922")
    ap.add_argument("--res", type=float, default=None, help="output metres per pixel (default native)")
    ap.add_argument("--out", default=None, help="output folder (default data/_source/historic_topo_probe)")
    ap.add_argument("--marks-out", default=None, help="folder for empty mark sheets (default expansion data/raw/marks)")
    ap.add_argument("--digitisers", nargs="*", default=["d1", "d2"])
    ap.add_argument("--neatline", default=None,
                    help="W,S,E,N sheet neatline in NAD27 lon/lat (e.g. a 15 minute quad). Without it the collar counts as cover")
    a = ap.parse_args(argv)
    sheet = hk.need(Path(a.sheet), "historic sheet GeoTIFF")
    arr, valid, tf, res, src_crs = crop_to_bbox(sheet, cfg["bbox_9t"], cfg["crs"], a.res)
    if a.neatline:
        valid &= neatline_mask(tf, valid.shape, cfg["crs"], [float(v) for v in a.neatline.split(",")])
    share = float(valid.mean())
    out = Path(a.out) if a.out else hk.resolve(cfg["outputs"]["crops"])
    out.mkdir(parents=True, exist_ok=True)
    tif = out / f"{a.source}_crop_9t.tif"
    with rasterio.open(tif, "w", driver="GTiff", width=arr.shape[2], height=arr.shape[1], count=arr.shape[0],
                       dtype="uint8", crs=cfg["crs"], transform=tf, nodata=0, compress="deflate") as d:
        d.write(arr)
    with rasterio.open(tif) as d:
        hk.ek.assert_crs(d, cfg["crs"])
    rgb = np.moveaxis(arr[:3] if arr.shape[0] >= 3 else np.repeat(arr[:1], 3, 0), 0, -1)
    rgb = np.where(valid[..., None], rgb, 255).astype(np.uint8)
    pngs = []
    for z in (2, 4):
        for i, j, t in zoom_tiles(rgb, z):
            p = out / f"{a.source}_zoom{z}_r{i}c{j}_9t.png"
            Image.fromarray(t).save(p)
            pngs.append(p)
    meta = {"source": a.source, "sheet": str(sheet), "source_crs": src_crs, "res_m": res,
            "cover_share_9t": round(share, 4), "shape": list(arr.shape),
            "partial_cover": share < 0.999, "n_png": len(pngs),
            "neatline": a.neatline or "not given (collar counted as cover, VERIFY)"}
    (out / f"{a.source}_crop_9t.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    marks = Path(a.marks_out) if a.marks_out else hk.resolve(cfg["inputs"]["marks_dir"])
    marks.mkdir(parents=True, exist_ok=True)
    for dname in a.digitisers:
        f = marks / f"{a.source}__{dname}.csv"
        if not f.exists():
            pd.DataFrame(columns=cfg["inputs"]["marks_dir"]["schema"]).to_csv(f, index=False)
    hk.prov(out, f"hist_topo_crop_{a.source}", inputs=[sheet], outputs=[tif], params=meta)
    print(f"{tif}  cover share of 9t {share:.3f}  {len(pngs)} renders")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
