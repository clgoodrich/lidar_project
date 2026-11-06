"""3.1 S0. Lidar tile inventory for a transfer area (header facts, optional measured ground density).

Purpose
    One row per LAZ tile. LAS version, point format, point count, bounds, horizontal and
    vertical CRS read from the header (laspy, header only), and tile footprint transformed to
    EPSG:6346. With --ground, a chunked pass counts class-2 returns and reports ground points
    per m2 of tile footprint and the share of 0.5 m cells with no ground return. Density is
    measured, never inferred from file size. Also lists whether the merged LAS named in the
    config exists (McKean mckean_full.las is assumed, see config).

Inputs
    config_3_1.json areas.<area>.tiles (glob), e.g.
        data/_source/lidar/warren_sheffield/USGS_LPC_PA_WesternPA_2019_D20_17TPG*.laz   (held, 7 tiles)
        data/_source/lidar/mckean/USGS_LPC_PA_Northcentral_2019_B19_*.laz             (held, 59 tiles, EPSG:6350)

Outputs
    expansions/3_geography/3_1_warren_forest_mckean/results/tables/<area>/xfer_tile_inventory_<area>.csv
    expansions/3_geography/3_1_warren_forest_mckean/results/tables/<area>/xfer_tile_inventory_<area>.json
        (CRS set, programs, totals, merged LAS state, missing items)

Run
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_tile_inventory_wfm.py --area warren
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_tile_inventory_wfm.py --area mckean --ground --max-tiles 2
    3.2 reuse: --config expansions/3_geography/3_2_appalachian_states/src/config_3_2.json --area ny_alg
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_1.json"


def footprint_6346(row: dict, src_epsg):
    """Tile footprint in EPSG:6346. A tile with no CRS raises (never assumed to be EPSG:6346)."""
    from pyproj import CRS, Transformer
    from shapely.geometry import box
    if src_epsg is None or (isinstance(src_epsg, float) and np.isnan(src_epsg)):
        raise ValueError(f"tile {row.get('file', '?')} has no CRS in its header. Set areas.<area>.src_crs "
                         "explicitly after checking the delivery metadata")
    src_epsg = int(src_epsg)
    horiz = CRS.from_epsg(src_epsg)
    horiz = horiz.sub_crs_list[0] if horiz.is_compound else horiz
    if not horiz.is_projected or any(abs(float(ax.unit_conversion_factor) - 1.0) > 1e-9 for ax in horiz.axis_info):
        raise ValueError(f"tile {row.get('file', '?')} CRS EPSG:{src_epsg} is not projected in metres")
    b = box(row["minx"], row["miny"], row["maxx"], row["maxy"])
    if src_epsg == 6346:
        return b
    tr = Transformer.from_crs(f"EPSG:{src_epsg}", ek.DST_CRS, always_xy=True)
    from shapely.ops import transform
    return transform(lambda x, y: tr.transform(x, y), b.segmentize(50))


def inventory(tiles, ground: bool, res: float = 0.5, src_crs: str | None = None):
    """src_crs (config areas.<area>.src_crs) is used only for a tile whose header has no CRS."""
    rows = []
    for p in tiles:
        h = xl.las_header(p)
        if h["crs_epsg"] is None and src_crs:
            h["crs_epsg"], h["crs_source"] = int(str(src_crs).split(":")[-1]), "config src_crs"
        else:
            h["crs_source"] = "header" if h["crs_epsg"] is not None else "none"
        fp = footprint_6346(h, h["crs_epsg"])
        h.update({"fp_minx": fp.bounds[0], "fp_miny": fp.bounds[1], "fp_maxx": fp.bounds[2], "fp_maxy": fp.bounds[3],
                  "fp_area_m2": fp.area, "pts_per_m2_all": h["n_points"] / fp.area if fp.area else np.nan})
        if ground:
            src = f"EPSG:{h['crs_epsg']}" if h["crs_epsg"] else None
            g, _, info = xl.ground_grid([p], fp.bounds, res, src_crs=src)
            h["n_ground"] = info[0]["n_class"]
            h["ground_per_m2"] = info[0]["n_class"] / fp.area
            h["void_frac_05"] = float((g == 0).mean())
        rows.append(h)
        print(f"  {h['file']}: v{h['las_version']} pf{h['point_format']} {h['n_points']:,} pts EPSG:{h['crs_epsg']}"
              + (f" ground {h['ground_per_m2']:.2f}/m2 void {h['void_frac_05']:.2f}" if ground else ""))
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--ground", action="store_true", help="measure class-2 density per tile (reads points)")
    ap.add_argument("--max-tiles", type=int, default=None)
    ap.add_argument("--tiles", default=None, help="override the config tile glob")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    tiles = xl.glob_paths(a.tiles) if a.tiles else ctx["tiles"]
    if not tiles:
        raise xl.MissingInput(f"MISSING INPUT: lidar tiles for area {a.area}\n  pattern: {a.tiles or ctx['tiles_pattern']}\n"
                              "  fetch is a user step (measure one tile first)")
    if a.max_tiles:
        tiles = tiles[: a.max_tiles]
    print(f"{a.area}: {len(tiles)} tiles")
    df = inventory(tiles, a.ground, cfg.get("res_m", 0.5), ctx["src_crs"])
    ek.assert_unique(df, "file")
    out = ctx["tables"] / f"xfer_tile_inventory_{a.area}.csv"
    df.to_csv(out, index=False)
    merged = ctx.get("merged_las")
    meta = {"area": a.area, "n_tiles": len(df), "crs_epsg": sorted(df.crs_epsg.dropna().astype(int).unique().tolist()),
            "vertical_crs": sorted(df.vertical_crs.dropna().unique().tolist()),
            "las_versions": sorted(df.las_version.unique().tolist()), "point_formats": sorted(df.point_format.unique().tolist()),
            "n_points_total": int(df.n_points.sum()), "footprint_bbox_6346": [float(df.fp_minx.min()), float(df.fp_miny.min()),
                                                                           float(df.fp_maxx.max()), float(df.fp_maxy.max())],
            "ground_measured": bool(a.ground),
            "merged_las": {"path": str(merged), "exists": bool(merged and Path(merged).exists())} if merged else None,
            "flight_dates": "not in headers; fetch USGS project metadata (manifest D1) into assumed.flight_dates"}
    if a.ground:
        meta["ground_per_m2_median"] = float(df.ground_per_m2.median())
        meta["void_frac_05_median"] = float(df.void_frac_05.median())
    if len(meta["crs_epsg"]) > 1:
        print(f"  ALERT: mixed horizontal CRS {meta['crs_epsg']}")
    js = ctx["tables"] / f"xfer_tile_inventory_{a.area}.json"
    js.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    print(f"wrote {out}\n      {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
