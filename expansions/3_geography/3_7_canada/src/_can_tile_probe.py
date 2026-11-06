"""S1 (3.7). Measure one lidar tile per province. Header, classes, flight dates, ground density, void.

Purpose
    Read one LAS/LAZ tile per province with laspy. Record LAS version, point format, point count,
    horizontal CRS and vertical datum (from the WKT, CGVD2013 or CGVD28 expected), bounding box,
    class counts, GPS-time date range (adjusted standard GPS time to UTC dates, or week time flagged),
    and per 375 m block ground density and 0.5 m void fraction through the shared core. Measures,
    never infers from file size.
Inputs
    data/_source/lidar/lidar_can/<province>/*.la[sz]   (config inputs.tile_probe_dir, one tile)
Outputs
    expansions/3_geography/3_7_canada/results/tables/can_tile_probe.csv
    expansions/3_geography/3_7_canada/results/tables/can_tile_blocks_<province>.csv
Run
    python expansions/3_geography/3_7_canada/src/_can_tile_probe.py --provinces ab,bc,on
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.7"
GPS_EPOCH = pd.Timestamp("1980-01-06")


def gps_dates(t: np.ndarray, adjusted: bool) -> tuple[str, str]:
    if not adjusted or t.size == 0:
        return "week-time (no date)", "week-time (no date)"
    s = GPS_EPOCH + pd.to_timedelta(np.array([t.min(), t.max()]) + 1e9, unit="s")
    return s[0].date().isoformat(), s[1].date().isoformat()


def vertical_datum(wkt: str) -> str:
    w = (wkt or "").upper()
    for k in ("CGVD2013", "CGVD28", "NAVD88"):
        if k in w:
            return k
    return "not stated"


def probe(tile: Path) -> tuple[dict, "object"]:
    import laspy
    with laspy.open(tile) as fh:
        h = fh.header
        crs = h.parse_crs()
        las = fh.read()
    cls, n = np.unique(np.asarray(las.classification), return_counts=True)
    adjusted = bool(h.global_encoding.gps_time_type) if hasattr(h.global_encoding, "gps_time_type") else False
    has_t = "gps_time" in las.point_format.dimension_names
    d0, d1 = gps_dates(np.asarray(las.gps_time) if has_t else np.array([]), adjusted)
    area = (h.maxs[0] - h.mins[0]) * (h.maxs[1] - h.mins[1])
    rec = {"tile": tile.name, "las_version": f"{h.version.major}.{h.version.minor}", "point_format": h.point_format.id,
           "points": int(h.point_count), "crs": crs.to_string() if crs else "missing",
           "vertical_datum": vertical_datum(crs.to_wkt() if crs else ""), "minx": h.mins[0], "miny": h.mins[1],
           "maxx": h.maxs[0], "maxy": h.maxs[1], "all_ppm2_bbox": h.point_count / area if area else np.nan,
           "date_first": d0, "date_last": d1, **{f"class_{int(c)}": int(k) for c, k in zip(cls, n)}}
    return rec, crs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provinces", default="ab,bc,on")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    rows = []
    tables = ek.sub(EXP, "results/tables")
    for prov in a.provinces.split(","):
        try:
            d = gt.config_input(cfg, "tile_probe_dir", EXP, province=prov)
            tiles = sorted(Path(d).glob("*.la[sz]"))
            if not tiles:
                raise gt.MissingInputError(f"no tile in {d}")
        except gt.MissingInputError as e:
            print(str(e), file=sys.stderr)
            rows.append({"province": prov, "tile": None, "status": "missing tile"})
            continue
        rec, crs = probe(tiles[0])
        rec["province"], rec["status"] = prov, "ok"
        if crs is not None:
            blocks = gt.make_blocks((rec["minx"], rec["miny"], rec["maxx"], rec["maxy"]), crs.to_string())
            if len(blocks):
                bd = gt.las_block_density([tiles[0]], blocks)
                bd.to_csv(tables / f"can_tile_blocks_{prov}.csv", index=False)
                rec["ground_ppm2_median"] = float(bd["ground_ppm2"].median())
                rec["void_frac_05_median"] = float(bd["void_frac_05"].median())
        rows.append(rec)
    out = tables / "can_tile_probe.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(pd.DataFrame(rows).T.to_string(), f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
