"""Export the missing-ground areas as polygons, for overlaying in QGIS.

WHAT THIS IS
------------
The data-QA slides show where the delivered survey has no ground measurement at
all. This turns that into a vector layer you can drop straight over a hillshade
or an RRIM.

It is the real thing, not a sketch. Every polygon is traced from
`count_vendorground_9t_0p5m.tif`, the per-cell count of vendor ground returns,
so a polygon means "no class-2 return landed anywhere in here" and the edges
are where that stops being true.

TWO LAYERS, BECAUSE THEY ANSWER DIFFERENT QUESTIONS
---------------------------------------------------
    missing_ground      every cell the vendor had no ground for. This is the
                        whole hole, canopy and scan-angle cut together.
    recoverable_ground  the subset that a recovered return actually fills. This
                        is the part the 18 deg cut caused and that reprocessing
                        can fix; the rest is canopy and stays missing.

Both carry area_m2 and a `kind` field so they can be styled apart, and both are
in EPSG:6346 to match the rest of the project.

RASTER, NOT POLYGONS -- AND WHY
-------------------------------
The first version polygonised, and tried to tidy the mask first. Both ways of
tidying were wrong, because the voids are genuinely one to two cells wide:

    binary closing  bridged the gaps BETWEEN voids and swallowed the real
                    ground with them. 36.6 M cells -> 71.2 M, +94%, and a
                    single 17.6 km2 blob over a tile that is 45% void.
    binary opening  erased almost all of it. 36.6 M -> 3.2 M, -91%.

The voids are thin and speckled, and that is the data, not noise in it. Any
morphology misrepresents it, and polygonising the raw mask makes millions of
slivers that no GIS will draw at speed.

So the primary output is a raster mask: 1 where the vendor measured no ground,
nodata elsewhere. It overlays in one click, draws instantly, is exact to the
cell, and compresses to a few MB because it is binary.

A polygon layer is written too, but from a DELIBERATELY COARSENED grid -- 4 m
cells flagged where more than half their 0.5 m cells are void. That is honest
about being a generalisation and is the version to use for labelling or area
summaries.

Run:
    python notebooks/wellsight_v2/s7_analysis/_export_missing_ground_polygons_9t.py
Writes:
    data/9t/results/recovered_ground_9t/missing_ground_9t.gpkg
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio import features
from scipy import ndimage
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[3]
REC = ROOT / "data/9t/results/recovered_ground_9t"
CNT_V = REC / "count_vendorground_9t_0p5m.tif"
CNT_R = REC / "count_recoveredground_slope0p35_9t_0p5m.tif"
OUT = REC / "missing_ground_9t.gpkg"

CRS = "EPSG:6346"
COARSE_FACTOR = 8               # 0.5 m -> 4 m for the polygon version
COARSE_FRAC = 0.5               # a coarse cell is void if over half of it is


def write_mask(mask, transform, path):
    """1 where true, nodata elsewhere. Exact to the cell, no tidying."""
    prof = dict(driver="GTiff", height=mask.shape[0], width=mask.shape[1],
                count=1, dtype="uint8", crs=CRS, transform=transform,
                nodata=0, compress="deflate", zlevel=9, tiled=True,
                blockxsize=512, blockysize=512)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(mask.astype("uint8"), 1)
    return path.stat().st_size / 1e6


def coarsen(mask, factor, frac):
    """Block-mean the mask and threshold, giving drawable polygons."""
    h = (mask.shape[0] // factor) * factor
    w = (mask.shape[1] // factor) * factor
    blocks = mask[:h, :w].reshape(h // factor, factor, w // factor, factor)
    return blocks.mean(axis=(1, 3)) > frac


def polygonise(mask, transform, kind):
    geoms, vals = [], []
    for geom, v in features.shapes(mask.astype("uint8"), mask=mask,
                                   transform=transform, connectivity=8):
        if v != 1:
            continue
        g = shape(geom)
        geoms.append(g)
        vals.append(kind)
    gdf = gpd.GeoDataFrame({"kind": vals}, geometry=geoms, crs=CRS)
    gdf["area_m2"] = gdf.area.round(2)
    return gdf


def main() -> int:
    for p in (CNT_V, CNT_R):
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    with rasterio.open(CNT_V) as sv, rasterio.open(CNT_R) as sr:
        v = sv.read(1, masked=True).filled(0)
        r = sr.read(1, masked=True).filled(0)
        transform = sv.transform
        total_cells = v.size
        cell_area = abs(transform.a * transform.e)

    void = v <= 0
    fillable = void & (r > 0)
    print(f"  {total_cells:,} cells at {cell_area:.2f} m2 each")
    print(f"  no vendor ground: {void.sum():,} cells "
          f"({void.mean()*100:.1f}% of the tile)")
    print(f"  of those, a recovered return lands in "
          f"{fillable.sum():,} ({fillable.sum()/max(void.sum(),1)*100:.1f}%)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    from rasterio.transform import Affine
    ct = transform * Affine.scale(COARSE_FACTOR, COARSE_FACTOR)

    for name, mask in (("missing_ground", void),
                       ("recoverable_ground", fillable)):
        tif = REC / f"{name}_9t_0p5m.tif"
        mb = write_mask(mask, transform, tif)
        cm = coarsen(mask, COARSE_FACTOR, COARSE_FRAC)
        gdf = polygonise(cm, ct, name)
        if len(gdf):
            gdf.to_file(OUT, layer=name, driver="GPKG")
        print(f"\n  {name}")
        print(f"     raster   {int(mask.sum()):,} cells, "
              f"{mask.sum()*cell_area/1e6:.3f} km2  ->  {tif.name} "
              f"({mb:.1f} MB)")
        print(f"     polygons at {COARSE_FACTOR*0.5:.0f} m: {len(gdf):,}, "
              f"{gdf.area_m2.sum()/1e6:.3f} km2")

    print(f"\n  {OUT}")
    print(f"  rasters in {REC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
