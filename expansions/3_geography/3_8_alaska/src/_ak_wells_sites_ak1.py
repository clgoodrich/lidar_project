"""S0 (3.8). Alaska legacy well inventory and sites (wells clustered within 300 m).

Purpose
    Load the held USGS orphan lists (2022 has 12 Alaska rows, 2026 has 44) and, when present, the assumed
    federal legacy-well list and the AOGCC database. Normalise to the shared schema, project to Alaska
    Albers (EPSG:3338), deduplicate by identifier and by position (5 m), and cluster wells into sites by
    single linkage at site_cluster_m (300 m). The site is the unit and the effective sample.
    This study is off the (a) to (d) evidence scale. Displacement is never well integrity.
Inputs
    data/_source/reference/wells_us_orphan_2022/US_orphaned_wells.csv, wells_us_orphan_2026/... (held)
    config_3_8.json inputs.legacy_wells, inputs.aogcc_wells (assumed, optional)
Outputs
    expansions/3_geography/3_8_alaska/data/interim/ak_wells_sites_ak1.gpkg   (wells with site_id)
    expansions/3_geography/3_8_alaska/results/tables/ak_sites_summary_ak1.csv
Run
    python expansions/3_geography/3_8_alaska/src/_ak_wells_sites_ak1.py
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
EXP = "3.8"
AK_CRS = "EPSG:3338"


def cluster_sites(x: np.ndarray, y: np.ndarray, dist_m: float) -> np.ndarray:
    """Single-linkage components within dist_m. Returns an integer site label per point."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    n = len(x)
    if n == 0:
        return np.array([], int)
    pairs = np.array(sorted(cKDTree(np.c_[x, y]).query_pairs(dist_m)), dtype=int).reshape(-1, 2)
    g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)) if len(pairs) else coo_matrix((n, n))
    return connected_components(g, directed=False)[1]


def dedupe(g, tol_m: float = 5.0):
    g = g.sort_values(["source"]).reset_index(drop=True)
    g = g[~(g["well_id"].notna() & g["well_id"].duplicated())]
    lab = cluster_sites(g.geometry.x.to_numpy(), g.geometry.y.to_numpy(), tol_m)
    return g.assign(_d=lab).drop_duplicates("_d").drop(columns="_d").reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    parts = [gt.load_usgs_orphans(["Alaska"], 2022), gt.load_usgs_orphans(["Alaska"], 2026)]
    counts = {"usgs_2022": len(parts[0]), "usgs_2026": len(parts[1])}
    for name, cmap in (("legacy_wells", {"well_id": "API", "status_raw": "Status", "lat": "Latitude", "lon": "Longitude",
                                         "coord_method": "CoordSource", "spud_date": "SpudDate"}),
                       ("aogcc_wells", {"well_id": "Api", "status_raw": "Status", "lat": "Lat", "lon": "Lon"})):
        try:
            df = pd.read_csv(gt.config_input(cfg, name, EXP), low_memory=False)
            parts.append(gt.normalise_registry(df, cmap, name, None, lonlat_crs="EPSG:4269"))
            counts[name] = len(df)
        except gt.MissingInputError as e:
            print(str(e).splitlines()[0], "(optional, continuing with held lists)", file=sys.stderr)
            counts[name] = 0
    import geopandas as gpd
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs="EPSG:4326")
    g = g[g["coord_ok"]].to_crs(AK_CRS)
    g["well_id"] = g["well_id"].astype("string").str.replace("API:", "", regex=False)
    g = dedupe(g)
    g["site_id"] = [f"s{k:03d}" for k in cluster_sites(g.geometry.x.to_numpy(), g.geometry.y.to_numpy(),
                                                       float(pr["site_cluster_m"]))]
    out = ek.sub(EXP, "data/interim") / "ak_wells_sites_ak1.gpkg"
    g.to_file(out, driver="GPKG")
    summ = pd.DataFrame([{**counts, "wells_after_dedupe": len(g), "sites": g["site_id"].nunique(),
                          "max_wells_per_site": int(g.groupby("site_id").size().max()) if len(g) else 0,
                          "blank_status": int((g["status_norm"] == "missing").sum())}])
    sp = ek.sub(EXP, "results/tables") / "ak_sites_summary_ak1.csv"
    summ.to_csv(sp, index=False)
    print(summ.T.to_string(), f"\nwrote {out}\nwrote {sp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
