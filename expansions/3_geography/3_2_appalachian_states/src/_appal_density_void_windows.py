"""3.2 S3. Ground density and void audit per window (one tile first, then the window).

Purpose
    For each 3.2 window, find its tiles of the configured program in the catalogue download
    list, check which are on disk, and measure class-2 density and 0.5 m void fraction per tile
    (3.1 inventory code, chunked laspy pass). The result is also written as the 3.1-style
    inventory for the window, so the 3.1 S1 blocks script runs next with this config.
    Per-block density and void come from that S1 run. Compared with 9t (2.70 ground points per
    m2 overall, the 9t block 5th percentile computed from the held raster). A window whose
    median is under half the 9t 5th percentile is flagged STOP for a user decision.
    The first run should use --one-tile (fw_3_2 S3, fetch one tile per window first).

Inputs
    catalogue   data/_source/reference/lidar_catalogue/lidar_win_download_list_us.csv
    tiles       config areas.<tag>.tiles (assumed. data/_source/lidar/lidar_us_windows/<project>/)
    9t          data/9t/derived/05/ground_density_9t_05.tif, pit_blocks_9t.gpkg

Outputs
    expansions/3_geography/3_2_appalachian_states/results/tables/<tag>/xfer_tile_inventory_<tag>.csv  (3.1 S0 format)
    expansions/3_geography/3_2_appalachian_states/results/tables/<tag>/xfer_density_void_<tag>.json
    expansions/3_geography/3_2_appalachian_states/results/tables/xfer_density_void_windows_appal.csv (one row per window)

Run
    python expansions/3_geography/3_2_appalachian_states/src/_appal_density_void_windows.py --one-tile
    python expansions/3_geography/3_2_appalachian_states/src/_appal_density_void_windows.py --tags ny_alg
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
SRC31 = HERE.parents[2] / "3_1_warren_forest_mckean" / "src"
sys.path.insert(0, str(SRC31))
import _geo_xfer_lib as xl  # noqa: E402
from _xfer_tile_inventory_wfm import inventory  # noqa: E402
from _xfer_blocks_roles_wfm import ref_density_p5  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_2.json"


def window_tiles(cfg, tag):
    A = cfg["areas"][tag]
    dl = pd.read_csv(xl.need(xl.resolve_path(cfg["catalogue"]["download_list"]), "download list"))
    sub = dl[(dl.window == A["window"]) & (dl.project == A["program"])]
    names = [u.rsplit("/", 1)[-1] for u in sub.url]
    tdir = Path(str(xl.resolve_path(A["tiles"]))).parent
    held = [tdir / n for n in names if (tdir / n).exists()]
    return names, held, tdir, float(sub.gb.sum())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--tags", nargs="*", default=None)
    ap.add_argument("--one-tile", action="store_true")
    ap.add_argument("--allow-missing", action="store_true", help="report missing windows instead of failing")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    tags = a.tags or [t for t in cfg["areas"] if cfg["areas"][t].get("program")]
    p5 = ref_density_p5(cfg)
    rows, missing = [], []
    for tag in tags:
        names, held, tdir, gb = window_tiles(cfg, tag)
        if not held:
            missing.append(f"{tag}: 0 of {len(names)} tiles in {tdir} ({gb:.2f} GB listed)")
            rows.append({"tag": tag, "tiles_listed": len(names), "tiles_held": 0, "gb_listed": gb, "status": "missing"})
            continue
        use = held[:1] if a.one_tile else held
        ctx = xl.area_ctx(cfg, tag)
        inv = inventory(use, ground=True, res=cfg.get("res_m", 0.5))
        inv.to_csv(ctx["tables"] / f"xfer_tile_inventory_{tag}.csv", index=False)
        med = float(inv.ground_per_m2.median())
        epsg = sorted(inv.crs_epsg.dropna().astype(int).unique().tolist())
        exp = cfg["areas"][tag].get("expected_epsg")
        r = {"tag": tag, "tiles_listed": len(names), "tiles_held": len(held), "tiles_measured": len(use), "gb_listed": gb,
             "ground_per_m2_median": med, "void_frac_05_median": float(inv.void_frac_05.median()),
             "ratio_to_9t_overall": med / cfg["reference"]["ground_per_m2_9t_overall"], "ratio_to_9t_p5": med / p5,
             "crs_epsg": epsg, "crs_alert": bool(exp and epsg != [exp]),
             "status": "STOP user decision (far below 9t p5)" if med < 0.5 * p5 else "ok"}
        (ctx["tables"] / f"xfer_density_void_{tag}.json").write_text(json.dumps(r, indent=2, default=float), encoding="utf-8")
        rows.append(r)
        print(f"  {tag}: {len(use)} tiles, ground {med:.2f}/m2 ({r['ratio_to_9t_p5']:.2f} x 9t p5), status {r['status']}")
    out = ek.sub("3.2", "results/tables") / "xfer_density_void_windows_appal.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"9t block p5 ground density {p5:.2f}/m2\nwrote {out}")
    if missing and not a.allow_missing:
        raise xl.MissingInput("MISSING INPUT: window lidar tiles (fetch is a user step, one tile first)\n  " + "\n  ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
