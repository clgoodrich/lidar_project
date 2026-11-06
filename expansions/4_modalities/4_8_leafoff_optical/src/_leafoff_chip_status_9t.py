"""S2 and S4 of framework 4.8. Pull a chip per sampled feature and source, and record its status and visible ground.

Purpose. For every row of the preregistered sample and every requested source, fetch a 100 m chip centred on the
feature (PASDA ArcGIS export, NAIP STAC, or a local mosaic), save it as a GeoTIFF, and assign one status in this
order. unavailable, blank, undated, off-season, unregistered, cloud or shadow, low visible ground, usable.
Visible ground fraction (S4) is the share of pixels with excess green below exg_max_ground and brightness inside
ground_brightness, inside the feature footprint buffered 5 m, and over the whole chip. A blank or unavailable chip
is missing data, never a negative. Registration comes from the S3 summary when it exists.
Inputs.
  expansions/4_modalities/4_8_leafoff_optical/results/tables/leafoff_feature_sample_9t.csv (from S1)
  qgis/annotations/annotations_proj_v2.gpkg (held, for footprints)
  expansions/4_modalities/4_8_leafoff_optical/results/tables/leafoff_offsets_summary_9t.csv (from S3, optional)
  sources named in config_4_8.json (network for arcgis_export and naip_stac, offline for local)
Outputs.
  expansions/4_modalities/4_8_leafoff_optical/data/interim/chips/<source>/leafoff_chip_<feature>_9t.tif
  data/9t/results/optical/leafoff_chip_status_9t.csv   one row per feature and source
Run.
  python expansions/4_modalities/4_8_leafoff_optical/src/_leafoff_chip_status_9t.py --sources pema_venango_2020 [local_mosaic] [--sample CSV] [--out-csv PATH] [--chips DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import _leafoff_kit_4_8 as lk


def footprint_mask(geom, bbox, px: int, buffer_m: float) -> np.ndarray:
    from rasterio.features import rasterize
    from rasterio.transform import from_bounds
    return rasterize([(geom.buffer(buffer_m), 1)], out_shape=(px, px), transform=from_bounds(*bbox, px, px)).astype(bool)


def save_chip(path: Path, rgb: np.ndarray, bbox, crs: str) -> None:
    import rasterio
    from rasterio.transform import from_bounds
    path.parent.mkdir(parents=True, exist_ok=True)
    H, W = rgb.shape[:2]
    with rasterio.open(path, "w", driver="GTiff", width=W, height=H, count=3, dtype="uint8", crs=crs,
                       transform=from_bounds(*bbox, W, H), compress="deflate", photometric="RGB") as d:
        d.write(np.moveaxis(rgb, -1, 0))


def run(sample: pd.DataFrame, geoms: dict, sources: list[str], cfg: dict, chips: Path, offsets: dict) -> pd.DataFrame:
    pr = cfg["prereg"]
    h, px = pr["chip_half_m"], pr["chip_px"]
    rows = []
    for sid in sources:
        src = cfg["sources"][sid]
        for r in sample.itertuples():
            bbox = (r.x - h, r.y - h, r.x + h, r.y + h)
            rgb, info = lk.fetch_chip(sid, src, bbox, px, cfg["crs"])
            meas, mfoot, chip_path = None, None, ""
            if rgb is not None:
                meas = lk.image_measures(rgb, pr)
                mfoot = lk.image_measures(rgb, pr, footprint_mask(geoms[r.feature_key], bbox, px, pr["footprint_buffer_m"]))
                cp = chips / sid / f"leafoff_chip_{r.feature_key.replace(':', '_')}_9t.tif"
                save_chip(cp, rgb, bbox, cfg["crs"])
                chip_path = str(cp)
            status, why = lk.chip_status(rgb, info, mfoot, pr, offsets.get(sid))
            rows.append({"feature_key": r.feature_key, "layer": r.layer, "source_id": sid, "date": info.get("date"),
                         "status": status, "reason": why, "offset_m": offsets.get(sid),
                         "vgf_footprint": mfoot["visible_ground_fraction"] if mfoot else np.nan,
                         "vgf_chip": meas["visible_ground_fraction"] if meas else np.nan,
                         "green_share": meas["green_share"] if meas else np.nan, "chip": chip_path})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    import geopandas as gpd
    from _leafoff_feature_sample_9t import ID_COL
    cfg = lk.load_cfg()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sources", nargs="+", required=True, choices=sorted(cfg["sources"]))
    ap.add_argument("--sample", default=None)
    ap.add_argument("--annotations", default=None)
    ap.add_argument("--offsets", default=None, help="S3 summary CSV (source_id, median_m)")
    ap.add_argument("--chips", default=None)
    ap.add_argument("--out-csv", default=None)
    ap.add_argument("--local-mosaic", default=None, help="override the local_mosaic path")
    ap.add_argument("--local-date", default=None, help="verified flight date of the local mosaic, YYYY-MM-DD")
    a = ap.parse_args(argv)
    if a.local_mosaic:
        cfg["sources"]["local_mosaic"]["path"] = a.local_mosaic
    if a.local_date:
        cfg["sources"]["local_mosaic"]["date"] = a.local_date
    tables = lk.resolve(cfg["outputs"]["tables"])
    sp = lk.need(Path(a.sample) if a.sample else tables / "leafoff_feature_sample_9t.csv", "S1 feature sample (run _leafoff_feature_sample_9t.py)")
    sample = pd.read_csv(sp)
    ann = lk.need(Path(a.annotations) if a.annotations else lk.resolve(cfg["inputs"]["annotations"]), "annotations")
    geoms = {}
    for layer in sample.layer.unique():
        g = gpd.read_file(ann, layer=layer)
        lk.ek.assert_crs(g, cfg["crs"])
        idc = ID_COL.get(layer, g.columns[0])
        for fid, geom in zip(g[idc], g.geometry):
            geoms[f"{layer}:{fid}"] = geom
    missing = set(sample.feature_key) - set(geoms)
    if missing:
        raise AssertionError(f"sampled features not in annotations: {sorted(missing)[:5]}")
    op = Path(a.offsets) if a.offsets else tables / "leafoff_offsets_summary_9t.csv"
    offsets = dict(pd.read_csv(op)[["source_id", "median_m"]].values) if op.exists() else {}
    chips = Path(a.chips) if a.chips else lk.resolve(cfg["outputs"]["chips"])
    df = run(sample, geoms, a.sources, cfg, chips, offsets)
    lk.ek.assert_rows(df, len(sample) * len(a.sources), "chip rows")
    out = Path(a.out_csv) if a.out_csv else lk.resolve(cfg["outputs"]["results"]) / "leafoff_chip_status_9t.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    lk.prov(out.parent, "leafoff_chip_status_9t", inputs=[sp, ann], outputs=[out], params=cfg["prereg"])
    print(df.groupby(["source_id", "status"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
