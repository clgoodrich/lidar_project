"""S5a (3.8). Matched controls, chosen before any displacement value is read. The file is hashed.

Purpose
    Candidates are points with no known well within control_exclusion_m (2 km), in the same radar frame.
    Exact match on land cover, ice-richness class and slope class (the stratum). Inside the stratum,
    nearest neighbours on standardised wetness and distance to the nearest road or pad. Each site takes
    n_controls_per_site controls without replacement across sites. Sites with no eligible control are
    listed, never silently dropped. The matching file's SHA-256 is printed for the prereg.
Inputs
    expansions/3_geography/3_8_alaska/data/interim/ak_wells_sites_ak1.gpkg (S0)
    config_3_8.json inputs.site_covariates, inputs.control_candidates (assumed)
Outputs
    expansions/3_geography/3_8_alaska/data/interim/ak_matches_ak1.csv   (site_id, cand_id, stratum, distance)
    expansions/3_geography/3_8_alaska/data/interim/ak_controls_ak1.gpkg
Run
    python expansions/3_geography/3_8_alaska/src/_ak_site_matching_ak1.py
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


def exclude_near_wells(cands, wells, dist_m: float):
    from scipy.spatial import cKDTree
    t = cKDTree(np.c_[wells.geometry.x, wells.geometry.y])
    d, _ = t.query(np.c_[cands.geometry.x, cands.geometry.y])
    return cands[d > dist_m].copy()


def match(sites: pd.DataFrame, cands: pd.DataFrame, exact: list[str], cont: list[str], k: int) -> tuple[pd.DataFrame, list]:
    """Greedy nearest neighbour inside exact strata, controls used once. Sites processed in id order."""
    allv = pd.concat([sites[cont], cands[cont]])
    mu, sd = allv.mean(), allv.std(ddof=0).replace(0, 1)
    used, rows, unmatched = set(), [], []
    for _, s in sites.sort_values("site_id").iterrows():
        pool = cands[(cands[exact] == s[exact].to_numpy()).all(axis=1) & (cands["frame"] == s["frame"])
                     & ~cands["cand_id"].isin(used)]
        if pool.empty:
            unmatched.append(s["site_id"])
            continue
        z = ((pool[cont].astype(float) - mu) / sd).to_numpy(float) - ((s[cont].astype(float) - mu) / sd).to_numpy(float)
        dist = np.sqrt((z ** 2).sum(axis=1))
        order = np.argsort(dist, kind="stable")[:k]
        for j in order:
            cid = pool["cand_id"].iloc[j]
            used.add(cid)
            rows.append({"site_id": s["site_id"], "cand_id": cid, "stratum": "|".join(str(s[e]) for e in exact),
                         "distance": float(dist[j])})
        if len(order) < k:
            unmatched.append(f"{s['site_id']} (only {len(order)} of {k})")
    return pd.DataFrame(rows), unmatched


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    import geopandas as gpd
    try:
        wells = gpd.read_file(gt.require_input(ek.sub(EXP, "data/interim") / "ak_wells_sites_ak1.gpkg", "S0 sites"))
        scov = pd.read_csv(gt.config_input(cfg, "site_covariates", EXP))
        cand = pd.read_csv(gt.config_input(cfg, "control_candidates", EXP))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    cg = gpd.GeoDataFrame(cand, geometry=gpd.points_from_xy(cand.lon, cand.lat), crs="EPSG:4326").to_crs(wells.crs)
    cg = exclude_near_wells(cg, wells, float(pr["control_exclusion_m"]))
    m, unmatched = match(scov, cg, pr["match_exact"], pr["match_continuous"], int(pr["n_controls_per_site"]))
    d = ek.sub(EXP, "data/interim")
    mp = d / "ak_matches_ak1.csv"
    m.to_csv(mp, index=False)
    cg[cg["cand_id"].isin(m["cand_id"])].to_file(d / "ak_controls_ak1.gpkg", driver="GPKG")
    print(f"{m['site_id'].nunique()} sites matched, {len(m)} controls. Unmatched: {unmatched or 'none'}")
    print(f"wrote {mp} sha256 {ek.sha256(mp)} (record in the prereg before reading any series)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
