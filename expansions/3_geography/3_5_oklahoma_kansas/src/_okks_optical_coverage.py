"""S0 (3.5). Imagery coverage and temporal eligibility per block, plus the gated NAIP fetch (S1).

Purpose
    Per 375 m block record the lidar flight dates, the imagery tile, acquisition date, resolution,
    band count, cloud or gap flag and the gap in years between imagery and lidar. Blocks whose gap
    exceeds the prereg maximum form their own stratum (date_eligible = False), they are not dropped.
    With --fetch --execute the NAIP tiles listed for the window are downloaded resumably into their
    own folder with SHA-256 (no credentials). Downloads are untrusted data and are only ever read.
Inputs
    config_3_5.json inputs.naip_index (assumed), inputs.lidar_dates (assumed)
    data/<area>/results/transfer/xfer_blocks_roles_<area>.gpkg, else a fresh 375 m grid
Outputs
    data/<area>/results/modality/mod_coverage_dates_<area>.csv
    expansions/3_geography/3_5_oklahoma_kansas/data/raw/naip/<area>/<tile>.tif  (--fetch --execute)
Run
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_optical_coverage.py --area ok_rogers
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_optical_coverage.py --area ok_rogers --fetch --execute
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.5"


def modality_dir(area: str) -> Path:
    d = ek.area_dir(area) / "results" / "modality"
    d.mkdir(parents=True, exist_ok=True)
    return d


def coverage_table(blocks, tiles, lidar_start, lidar_end, max_gap_years) -> pd.DataFrame:
    """tiles is a GeoDataFrame of imagery footprints (acq_date, res_m, bands, cloud_flag, tile)."""
    import geopandas as gpd
    j = gpd.sjoin(blocks[["block_id", "geometry"]], tiles, how="left", predicate="intersects")
    j["acq_date"] = pd.to_datetime(j["acq_date"])
    mid = pd.Timestamp(lidar_start) + (pd.Timestamp(lidar_end) - pd.Timestamp(lidar_start)) / 2
    j["gap_years"] = (j["acq_date"] - mid).abs().dt.days / 365.25
    # one tile per block, the nearest date, clouds last
    j = j.sort_values(["block_id", "cloud_flag", "gap_years"]).drop_duplicates("block_id")
    j["lidar_start"], j["lidar_end"] = lidar_start, lidar_end
    j["covered"] = j["tile"].notna()
    j["date_eligible"] = j["covered"] & ~j["cloud_flag"].fillna(True).astype(bool) & \
        (j["gap_years"] <= (np.inf if max_gap_years is None else max_gap_years))
    out = j.drop(columns=["geometry", "index_right"], errors="ignore").reset_index(drop=True)
    ek.assert_rows(out, len(blocks), "coverage per block")
    return out


def fetch_tiles(index: pd.DataFrame, dest: Path, execute: bool) -> list[dict]:
    dest.mkdir(parents=True, exist_ok=True)
    log = []
    for _, r in index.iterrows():
        out = dest / f"{r.tile}.tif"
        if out.exists():
            log.append({"tile": r.tile, "status": "exists", "sha256": ek.sha256(out)})
            continue
        if not execute:
            log.append({"tile": r.tile, "status": "planned", "url": r.url})
            continue
        import urllib.request
        part = out.with_suffix(".part")
        try:
            urllib.request.urlretrieve(r.url, part)
            part.rename(out)
            log.append({"tile": r.tile, "status": "ok", "sha256": hashlib.sha256(out.read_bytes()).hexdigest()})
        except Exception as e:  # noqa: BLE001
            log.append({"tile": r.tile, "status": "failed", "error": str(e)})
    return log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--execute", action="store_true", help="network download (gated)")
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    import geopandas as gpd
    from shapely.geometry import box
    try:
        idx = pd.read_csv(gt.config_input(cfg, "naip_index", EXP))
        dates = pd.read_csv(gt.config_input(cfg, "lidar_dates", EXP))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    idx = idx[idx["area"] == a.area]
    if a.fetch:
        dest = gt.resolve(cfg["areas"][a.area]["naip_dir"])
        log = fetch_tiles(idx, dest, a.execute)
        (dest / "naip_fetch_log.json").write_text(json.dumps(log, indent=2))
        print(pd.DataFrame(log)["status"].value_counts().to_string())
    blocks = gt._blocks_for_area(cfg, a.area, EXP)
    ac = cfg["areas"][a.area]
    rows = []
    for _, r in idx.iterrows():   # tile footprints from the tiles on disk
        p = gt.resolve(ac["naip_dir"]) / f"{r.tile}.tif"
        if p.exists():
            import rasterio
            with rasterio.open(p) as ds:
                bb = gpd.GeoSeries([box(*ds.bounds)], crs=ds.crs).to_crs(blocks.crs).iloc[0]
            rows.append({**r.to_dict(), "geometry": bb})
    if not rows:
        print(f"No NAIP tiles on disk for {a.area}. Run with --fetch --execute first.", file=sys.stderr)
        return 2
    tiles = gpd.GeoDataFrame(rows, geometry="geometry", crs=blocks.crs)
    d = dates[dates["area"] == a.area].iloc[0]
    cov = coverage_table(blocks, tiles, d.flight_start, d.flight_end, cfg["prereg"].get("max_date_gap_years"))
    out = modality_dir(a.area) / f"mod_coverage_dates_{a.area}.csv"
    cov.to_csv(out, index=False)
    print(cov[["covered", "date_eligible"]].sum().to_string(), f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
