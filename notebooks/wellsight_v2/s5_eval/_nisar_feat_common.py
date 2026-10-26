"""Shared helpers for the NISAR feature products (docs/iterations/nisar_feature_products_plan.md).

Every product script loads the complex windows once, computes bands, and writes them with
write_bands(). The scorer reads every nisar_feat_*.tif back with read_all(). One GeoTIFF per
product keeps a failed or re-run product from touching the others.

Area is picked with --area (9t default), as for the other NISAR scripts.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ifg = importlib.import_module("_nisar_gslc_interferogram_pits_9t")
st, A = ifg.st, ifg.A
CRS, OUT = ifg.CRS, ifg.OUT
FEAT_DIR = A.DATA / "derived" / "nisar_features_5m"


def load():
    """idx, stack (file -> complex array [pol, y, x]; pol 0 = HH, 1 = HV), transform, shape."""
    return ifg.load_complex()


def by_track(idx):
    """(track, rows sorted by date) for each track."""
    for t, g in idx.groupby("track"):
        yield int(t), g.sort_values("date").reset_index(drop=True)


def cube(g, stack, pol):
    """Complex samples of one polarisation for the dates of g: (date, y, x)."""
    return np.stack([stack[f][pol] for f in g.file])


def to_grid(path, tf, shape):
    """Mean of a 1 m lidar raster on the 5 m radar grid."""
    with rasterio.open(path) as r:
        src = r.read(1, masked=True)
        src = np.where(src.mask, np.nan, src.filled(0)).astype(np.float32)
        dst = np.full(shape, np.nan, np.float32)
        reproject(src, dst, src_transform=r.transform, src_crs=r.crs, src_nodata=np.nan,
                  dst_transform=tf, dst_crs=CRS, dst_nodata=np.nan, resampling=Resampling.average)
    return dst


def lidar_grids(tf, shape):
    """slope (deg), roughness_5 and canopy cover on the radar grid."""
    return dict(slope=to_grid(A.lidar("slope"), tf, shape), rough=to_grid(A.lidar("roughness_5"), tf, shape),
                cover=st.canopy_cover(tf, shape))


def db(x):
    return 10 * np.log10(np.where(x > 0, x, np.nan))


def write_bands(product, bands, tf, shape):
    """Write {name: 2-D array} to nisar_feat_<product>_<area>_5m.tif, band names kept."""
    FEAT_DIR.mkdir(parents=True, exist_ok=True)
    path = FEAT_DIR / f"nisar_feat_{product}_{A.TAG}_5m.tif"
    with rasterio.open(path, "w", driver="GTiff", height=shape[0], width=shape[1], count=len(bands), dtype="float32",
                       crs=CRS, transform=tf, nodata=np.nan, compress="deflate") as dst:
        for i, (n, a) in enumerate(bands.items(), 1):
            dst.write(np.asarray(a, np.float32), i)
            dst.set_band_description(i, n)
    print(f"wrote {path} ({len(bands)} bands)", flush=True)
    return path


def read_all():
    """{band name: array} for every product file of this area, product name prefixed."""
    out = {}
    for p in sorted(FEAT_DIR.glob(f"nisar_feat_*_{A.TAG}_5m.tif")):
        prod = p.name[len("nisar_feat_"):-len(f"_{A.TAG}_5m.tif")]
        with rasterio.open(p) as r:
            for i, d in enumerate(r.descriptions, 1):
                out[f"{prod}:{d}"] = r.read(i)
    return out
