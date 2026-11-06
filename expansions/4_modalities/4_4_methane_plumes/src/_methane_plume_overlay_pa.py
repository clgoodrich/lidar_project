"""M2. Catalogue overlay of satellite methane plumes on wells, facilities and pads, plus observation opportunity.

Purpose
    For every catalogued plume, list the documented wells, candidate wells, active facilities and pads inside the
    plume's source-location uncertainty radius (never the plume footprint). Count usable overpasses per 5 km cell
    so later stages can use observation opportunity as an offset. Runs only on the large-leaker branch that M0 left live.
    Output is "plume near X" association. It never attributes a plume to one well.

Inputs (config_4_4.json, section m2; all assumed unless noted)
    expansions/4_modalities/4_4_methane_plumes/data/raw/carbon_mapper_plumes_l2b.csv   plume list (schema in config)
    expansions/4_modalities/4_4_methane_plumes/data/raw/carbon_mapper_fetch_log.json   pagination log (optional)
    expansions/4_modalities/4_4_methane_plumes/data/raw/carbon_mapper_observations.csv overpasses incl. non-detections
    expansions/4_modalities/4_4_methane_plumes/data/raw/active_facilities_pa.gpkg      active facility layer
    data/_source/reference/dep_wells/venango_wells_all.gpkg                            held
    data/_source/reference/legacy_data/US_Documented_Orphan_Wells.csv                  held
    qgis/annotations/annotations_proj_v2.gpkg layer pad                                held

Outputs (run folder expansions/4_modalities/4_4_methane_plumes/results/<YYYYMMDD>_methane_overlay_<hash7>/)
    methane_overlay_by_plume.csv       one row per plume (x_m, y_m in the metric CRS), counts and nearest distances
    methane_opportunity_by_cell.csv    usable overpasses per cell (cell_id, x0, y0, n_overpass, n_searched)
    methane_overlay_summary.json       counts, QC and the query check
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_4_methane_plumes/src/_methane_plume_overlay_pa.py [--basin pennsylvania] [--out-root DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _methane_shared_io as io  # noqa: E402
from _methane_shared_io import ek  # noqa: E402

PLUME_COLS = ["plume_id", "lat", "lon", "emission_kg_h", "source_unc_m", "instrument", "datetime_utc", "qa_flag"]


def check_fetch_log(log: dict, n_rows: int) -> dict:
    """fw_00 revision 2 QC. Separate empty, failed and incomplete pages and compare the reported total."""
    pages = log.get("pages", [])
    st = pd.Series([p.get("status", "unknown") for p in pages]).value_counts().to_dict() if pages else {}
    retrieved = int(sum(p.get("n", 0) for p in pages if p.get("status") == "ok"))
    rep = log.get("reported_total")
    problems = []
    if st.get("failed", 0) or st.get("incomplete", 0):
        problems.append(f"{st.get('failed', 0)} failed and {st.get('incomplete', 0)} incomplete pages")
    if rep is not None and int(rep) != n_rows:
        problems.append(f"reported_total {rep} != rows in catalogue {n_rows}")
    if pages and retrieved != n_rows:
        problems.append(f"sum of ok pages {retrieved} != rows {n_rows}")
    return {"status_counts": st, "reported_total": rep, "retrieved_ok": retrieved, "rows": n_rows,
            "complete": not problems, "problems": problems}


def read_plumes(path: Path, crs: str, usable_qa: list[str]):
    import geopandas as gpd
    df = pd.read_csv(path)
    miss = [c for c in PLUME_COLS if c not in df.columns]
    if miss:
        raise ValueError(f"plume catalogue {path} lacks {miss}. source_unc_m must be a source-location radius, "
                         "not the plume footprint (protocol section 9).")
    ek.assert_unique(df, "plume_id")
    if df["source_unc_m"].isna().any() or (df["source_unc_m"] <= 0).any():
        raise ValueError("source_unc_m missing or non-positive for some plumes. Do not substitute the footprint.")
    df["usable"] = df["qa_flag"].isin(usable_qa)
    df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], utc=True)
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326")
    return io.to_metric(g, crs)


def read_points(path: Path | None, crs: str, what: str, optional: bool = True):
    """Point layer from a GPKG, or from a CSV with Longitude/Latitude columns. Polygons become centroids."""
    import geopandas as gpd
    if path is None or not Path(path).exists():
        if optional:
            return None
        io.need(path, what)
    if str(path).lower().endswith(".csv"):
        df = pd.read_csv(path, encoding="utf-8-sig")
        lon = next(c for c in df.columns if c.lower() in ("longitude", "lon", "x"))
        lat = next(c for c in df.columns if c.lower() in ("latitude", "lat", "y"))
        g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326")
    else:
        g = gpd.read_file(path)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    g = io.to_metric(g, crs)
    if not (g.geom_type == "Point").all():
        g = g.set_geometry(g.geometry.representative_point())
    return g


def near_counts(plumes, layer, name: str) -> pd.DataFrame:
    """Per plume, count of layer points within source_unc_m and the nearest distance."""
    from scipy.spatial import cKDTree
    n = len(plumes)
    if layer is None or len(layer) == 0:
        return pd.DataFrame({f"n_{name}": np.full(n, np.nan), f"dist_{name}_m": np.full(n, np.nan)})
    xy = np.c_[layer.geometry.x, layer.geometry.y]
    tree = cKDTree(xy)
    pxy = np.c_[plumes.geometry.x, plumes.geometry.y]
    d, _ = tree.query(pxy, k=1)
    cnt = np.array([len(tree.query_ball_point(p, r)) for p, r in zip(pxy, plumes["source_unc_m"].to_numpy(float))])
    return pd.DataFrame({f"n_{name}": cnt, f"dist_{name}_m": np.round(d, 1)})


def opportunity_by_cell(obs: pd.DataFrame, crs: str, cell_m: float, usable_qa: list[str], bounds=None) -> pd.DataFrame:
    """Usable overpasses per square cell. A cell counts an overpass when the footprint intersects it."""
    import geopandas as gpd
    from shapely import wkt
    from shapely.geometry import box
    need_cols = ["obs_id", "datetime_utc", "footprint_wkt", "plume_search_done", "qa_flag"]
    miss = [c for c in need_cols if c not in obs.columns]
    if miss:
        raise ValueError(f"observations lack {miss}")
    g = gpd.GeoDataFrame(obs, geometry=obs["footprint_wkt"].map(wkt.loads), crs="EPSG:4326")
    g = io.to_metric(g, crs)
    g["usable"] = g["qa_flag"].isin(usable_qa) & g["plume_search_done"].astype(str).str.lower().isin(["true", "1", "yes"])
    x0, y0, x1, y1 = bounds if bounds is not None else g.total_bounds
    x0, y0 = np.floor(x0 / cell_m) * cell_m, np.floor(y0 / cell_m) * cell_m
    cells = [box(x, y, x + cell_m, y + cell_m) for x in np.arange(x0, x1, cell_m) for y in np.arange(y0, y1, cell_m)]
    C = gpd.GeoDataFrame({"cell_id": np.arange(len(cells))}, geometry=cells, crs=crs)
    C["x0"], C["y0"] = C.bounds.minx, C.bounds.miny
    j = gpd.sjoin(C, g[["obs_id", "usable", "geometry"]], predicate="intersects", how="left")
    agg = j.groupby("cell_id").agg(n_overpass=("obs_id", "nunique"),
                                  n_searched=("usable", lambda s: int(np.nansum(s.astype(float)))))
    return C.drop(columns="geometry").merge(agg, on="cell_id", how="left").fillna({"n_overpass": 0, "n_searched": 0})


def run(cfg: dict, out_root: Path | None = None, plumes_csv: Path | None = None, obs_csv: Path | None = None,
        basin: str = "pennsylvania") -> dict:
    m2 = cfg["m2"]
    crs = next((b["metric_crs"] for b in cfg.get("m4_basins", []) if b["basin"] == basin), cfg["metric_crs"])
    pp = io.need(plumes_csv or io.resolve(m2["plume_catalogue_csv"]), "plume catalogue (L2B)", m2["plume_schema"])
    run_dir = ek.new_run(io.EXP, "methane_overlay", {**m2, "basin": basin}, base=out_root,
                         why="M2 plume overlay on wells, facilities and pads (fw_4_4 section 7).")
    plumes = read_plumes(pp, crs, m2["usable_qa"])
    inputs = [pp]
    layers = {}
    for name, key in (("dep_well", "wells_gpkg"), ("orphan_well", "orphan_csv"), ("candidate", "candidate_wells_gpkg"),
                      ("facility", "facilities_gpkg")):
        p = io.resolve(m2.get(key))
        layers[name] = read_points(p, crs, name)
        if layers[name] is not None:
            inputs.append(p)
    pads_p = io.resolve(m2["pads_gpkg"])
    if pads_p is not None and pads_p.exists():
        import geopandas as gpd
        pads = io.to_metric(gpd.read_file(pads_p, layer=m2["pads_layer"]), crs)
        layers["pad"] = pads.set_geometry(pads.geometry.representative_point())
        inputs.append(pads_p)
    else:
        layers["pad"] = None

    plumes["x_m"], plumes["y_m"] = plumes.geometry.x.round(2), plumes.geometry.y.round(2)
    parts = [plumes.drop(columns="geometry").reset_index(drop=True)]
    parts += [near_counts(plumes.reset_index(drop=True), L, n) for n, L in layers.items()]
    tab = pd.concat(parts, axis=1)
    ek.assert_rows(tab, len(plumes), "overlay rows = plumes")
    well_cols = [c for c in ("n_dep_well", "n_orphan_well", "n_candidate") if c in tab]
    tab["near_well"] = tab[well_cols].fillna(0).sum(axis=1) > 0
    tab["near_facility"] = tab["n_facility"].fillna(0) > 0 if "n_facility" in tab else False
    tab["reading"] = np.select([tab.near_well & ~tab.near_facility, tab.near_well & tab.near_facility, tab.near_facility],
                               ["plume near well", "plume near well and facility", "plume near facility"], "no listed source")
    tab.loc[tab.get("n_candidate", pd.Series(0, index=tab.index)).fillna(0) > 0, "reading"] += " (candidate within radius)"
    out_csv = run_dir / "methane_overlay_by_plume.csv"
    tab.to_csv(out_csv, index=False)
    outputs = [out_csv]

    qc = {"query": None, "opportunity": "not computed"}
    lp = io.resolve(m2.get("catalogue_fetch_log"))
    if lp is not None and lp.exists():
        qc["query"] = check_fetch_log(json.loads(lp.read_text(encoding="utf-8")), len(plumes))
        inputs.append(lp)
    op = obs_csv or io.resolve(m2.get("observations_csv"))
    if op is not None and Path(op).exists():
        b = plumes.total_bounds
        pad_m = float(m2["cell_m"])
        opp = opportunity_by_cell(pd.read_csv(op), crs, float(m2["cell_m"]), m2["usable_qa"],
                                  bounds=(b[0] - pad_m, b[1] - pad_m, b[2] + pad_m, b[3] + pad_m))
        oc = run_dir / "methane_opportunity_by_cell.csv"
        opp.to_csv(oc, index=False)
        outputs.append(oc)
        inputs.append(Path(op))
        qc["opportunity"] = {"cells": int(len(opp)), "cells_never_observed": int((opp.n_searched == 0).sum())}
    else:
        qc["opportunity"] = ("MISSING observations with non-detections. Opportunity cannot be computed, "
                             "so M3 reduces to a descriptive map.")
    summ = {"basin": basin, "crs": crs, "n_plumes": int(len(plumes)), "n_usable": int(plumes.usable.sum()),
            "readings": tab["reading"].value_counts().to_dict(),
            "known_before_detection_share": float(pd.to_numeric(tab.get("known_before_detection"), errors="coerce").mean())
            if "known_before_detection" in tab else None,
            "layers_present": {k: v is not None for k, v in layers.items()}, "qc": qc,
            "wording": "Association only. A plume near a well is never reported as emission from that well."}
    sj = run_dir / "methane_overlay_summary.json"
    sj.write_text(json.dumps(summ, indent=2, default=str), encoding="utf-8")
    outputs.append(sj)
    ek.write_provenance(run_dir, inputs=inputs, outputs=outputs, params={**m2, "basin": basin})
    return {"run_dir": run_dir, "overlay": out_csv, "summary": summ}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--plumes-csv", type=Path, default=None)
    ap.add_argument("--observations-csv", type=Path, default=None)
    ap.add_argument("--basin", default="pennsylvania", help="row of m4_basins in the config (sets the metric CRS)")
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    r = run(io.load_config(a.config), a.out_root, a.plumes_csv, a.observations_csv, a.basin)
    print(json.dumps(r["summary"], indent=2, default=str))


if __name__ == "__main__":
    main()
