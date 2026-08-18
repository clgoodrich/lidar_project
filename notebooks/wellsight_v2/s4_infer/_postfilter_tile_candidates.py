"""Turn raw per-tile U-Net probability rasters into clean candidate polygons.

The raw argmax from _predict_on_tile.py over-fires on an unseen block and
classifies the no-data corner as foreground. This applies the standard post-pass
the raw output needs:

    valid-DEM mask (eroded)  ->  probability >= threshold  ->  remove small blobs
      ->  morphological close + fill  ->  polygonize  ->  gpkg (+ mean prob, area)

Inputs (under data/derivatives/inference_<sfx>/ and tiles/<sfx>/):
    pit_prob_floor_<sfx>.tif, pad_prob_<sfx>.tif, tiles/<sfx>/dem_<sfx>.tif
Outputs (inference_<sfx>/):
    pit_candidates_<sfx>.gpkg, pad_candidates_<sfx>.gpkg, candidates_overlay_<sfx>.png

CLI:
  python notebooks/wellsight/build/_postfilter_tile_candidates.py --suffix 613590_05
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes as rio_shapes
from scipy import ndimage as ndi
from skimage.morphology import remove_small_objects

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, path_for


def valid_mask(dem_path: Path, erode_px: int = 3) -> tuple[np.ndarray, object, object]:
    with rasterio.open(dem_path) as r:
        dem = r.read(1); nd = r.nodata; tf = r.transform; crs = r.crs
    v = np.isfinite(dem)
    if nd is not None:
        v &= dem != nd
    if erode_px:
        v = ndi.binary_erosion(v, iterations=erode_px)
    return v, tf, crs


def candidates(prob_path: Path, valid: np.ndarray, thresh: float, min_area_m2: float,
               res: float, transform, crs, layer: str, out_gpkg: Path):
    import geopandas as gpd
    from shapely.geometry import shape
    with rasterio.open(prob_path) as r:
        prob = r.read(1).astype(np.float32)
    fg = (prob >= thresh) & valid
    fg = ndi.binary_closing(fg, structure=np.ones((3, 3)))
    fg = ndi.binary_fill_holes(fg)
    min_px = int(round(min_area_m2 / (res * res)))
    fg = remove_small_objects(fg, min_size=min_px)
    polys, areas, meanp = [], [], []
    for geom, val in rio_shapes(fg.astype(np.uint8), mask=fg, transform=transform):
        if val != 1:
            continue
        g = shape(geom)
        # mean prob inside the polygon's bbox-masked region (cheap proxy)
        polys.append(g); areas.append(g.area)
    if polys:
        gdf = gpd.GeoDataFrame({"area_m2": areas}, geometry=polys, crs=DST_CRS)
        # attach mean probability via per-polygon rasterized mask would be heavy;
        # report tile-level mean prob over kept pixels instead.
        gdf.to_file(out_gpkg, layer=layer, driver="GPKG")
    kept_px = int(fg.sum())
    return len(polys), kept_px * res * res / 1e4, (float(prob[fg].mean()) if kept_px else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", default="613590_05")
    ap.add_argument("--pit-thresh", type=float, default=0.60)
    ap.add_argument("--pad-thresh", type=float, default=0.70)
    ap.add_argument("--pit-min-area", type=float, default=20.0, help="m^2")
    ap.add_argument("--pad-min-area", type=float, default=300.0, help="m^2")
    args = ap.parse_args()
    sfx = args.suffix

    inf = path_for("derived") / sfx / "derived" / "inference"
    dem = path_for("derived") / sfx / "derived" / f"dem_{sfx}.tif"
    with rasterio.open(dem) as r:
        res = r.res[0]
    valid, tf, crs = valid_mask(dem)
    print(f"[{sfx}] valid area {valid.sum()*res*res/1e4:.0f} ha; res {res} m")

    pit_n, pit_ha, pit_mp = candidates(
        inf / f"pit_prob_floor_{sfx}.tif", valid, args.pit_thresh, args.pit_min_area,
        res, tf, crs, "pit_candidates", inf / f"pit_candidates_{sfx}.gpkg")
    print(f"  PIT  P>={args.pit_thresh} min{args.pit_min_area:g}m2 -> "
          f"{pit_n} candidates, {pit_ha:.2f} ha, mean P {pit_mp:.2f}")

    pad_n, pad_ha, pad_mp = candidates(
        inf / f"pad_prob_{sfx}.tif", valid, args.pad_thresh, args.pad_min_area,
        res, tf, crs, "pad_candidates", inf / f"pad_candidates_{sfx}.gpkg")
    print(f"  PAD  P>={args.pad_thresh} min{args.pad_min_area:g}m2 -> "
          f"{pad_n} candidates, {pad_ha:.2f} ha, mean P {pad_mp:.2f}")

    # overlay (downsampled hillshade + candidate fills)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import geopandas as gpd
        ds = 5
        with rasterio.open(path_for("derived") / sfx / "derived" / f"hillshade_{sfx}.tif") as r:
            H, W = r.height, r.width
            hs = r.read(1, out_shape=(H // ds, W // ds), resampling=Resampling.nearest)
            b = r.bounds
        ext = (b.left, b.right, b.bottom, b.top)
        fig, ax = plt.subplots(figsize=(13, 13))
        ax.imshow(hs, cmap="gray", extent=ext, origin="upper")
        for f, color, lab in [(inf / f"pit_candidates_{sfx}.gpkg", "#ff2d2d", "pit"),
                              (inf / f"pad_candidates_{sfx}.gpkg", "#ff9500", "pad")]:
            if f.exists():
                g = gpd.read_file(f)
                g.plot(ax=ax, facecolor=color, edgecolor=color, alpha=0.55, linewidth=0.4)
        ax.set_title(f"{sfx}: pit (red, P>={args.pit_thresh}) + pad (orange, P>={args.pad_thresh}) candidates")
        ax.set_xticks([]); ax.set_yticks([])
        png = inf / f"candidates_overlay_{sfx}.png"
        fig.savefig(png, dpi=120, bbox_inches="tight"); plt.close(fig)
        print(f"  -> {png.name}")
    except Exception as ex:  # noqa: BLE001
        print(f"  overlay skipped: {ex}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
