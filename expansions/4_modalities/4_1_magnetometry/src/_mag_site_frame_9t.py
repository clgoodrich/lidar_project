"""S0. Build the magnetometry site frame for 9t by era stratum, and check a chosen pilot list.

Purpose
    Every DEP well in the 9t box gets an era stratum. Steel era is a well dated after 1930. Early era needs an
    independent historic-map date (assumed input from 4.6). Unknown date is the 1800 sentinel or a missing date.
    It is its own stratum and is never counted as early era (protocol section 6). Annotated pits with no DEP well
    within 25 m form the pit_no_record stratum. Metal confusers and blank controls come from an assumed CSV.
    If a chosen pilot list exists it is validated (3 to 5 sites, at least 3 strata, a confuser and a blank).
    The selection is not random, so the frame is not a sampling frame for sensitivity.

Inputs
    data/_source/reference/dep_wells/venango_wells_all.gpkg       (held, path_for("dep_wells"))
    qgis/annotations/annotations_proj_v2.gpkg layer pit_full       (held, path_for("truth"))
    expansions/4_modalities/4_1_magnetometry/data/raw/historic_well_dates.csv   (assumed, optional)
    expansions/4_modalities/4_1_magnetometry/data/raw/confusers_blanks.csv      (assumed, optional)
    expansions/4_modalities/4_1_magnetometry/data/raw/pilot_sites.csv           (assumed, optional)

Outputs
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_site_frame_9t.csv
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_site_frame_counts_9t.json
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/_PROVENANCE.json, _RUN.md, _CONFIG.json

Run
    python expansions/4_modalities/4_1_magnetometry/src/_mag_site_frame_9t.py [--config PATH] [--out-root DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mag_shared_io as io  # noqa: E402
from _mag_shared_io import ek  # noqa: E402

STRATA = ["steel_era", "early_era", "dated_pre_steel", "unknown_date", "pit_no_record", "confuser", "blank"]


def well_year(df: pd.DataFrame) -> pd.Series:
    """Earliest of SPUD_DATE and PERMIT_DAT as a year. NaN when both are missing."""
    yrs = []
    for c in ("SPUD_DATE", "PERMIT_DAT"):
        if c in df:
            yrs.append(pd.to_datetime(df[c], errors="coerce").dt.year)
    if not yrs:
        return pd.Series(np.nan, index=df.index)
    return pd.concat(yrs, axis=1).min(axis=1)


def assign_strata(wells: pd.DataFrame, historic: pd.DataFrame | None, steel_after: int, sentinel_max: int) -> pd.Series:
    """steel_era if year > steel_after. unknown_date if year missing or <= sentinel_max.
    early_era only for a well with an independent historic date (by PERMIT_NUM) at or before steel_after.
    A historic record dated after steel_after says nothing about the early era and is ignored.
    Otherwise dated_pre_steel, which is not early era (its date is a DEP date, not an independent one)."""
    y = well_year(wells)
    s = pd.Series("dated_pre_steel", index=wells.index)
    s[y > steel_after] = "steel_era"
    s[y.isna() | (y <= sentinel_max)] = "unknown_date"
    if historic is not None and len(historic) and "PERMIT_NUM" in historic and "PERMIT_NUM" in wells:
        ycol = next((c for c in ("year_built_max", "source_date") if c in historic), None)
        if ycol is None:
            raise ValueError("historic_dates needs year_built_max or source_date to place a well in the early era")
        hy = pd.to_numeric(historic[ycol], errors="coerce")
        hist = set(historic.loc[hy <= steel_after, "PERMIT_NUM"].astype(str))
        s[wells["PERMIT_NUM"].astype(str).isin(hist)] = "early_era"
    return s


def pits_no_record(pits, wells, radius: float):
    """Pit centroids with no DEP well within radius metres."""
    from scipy.spatial import cKDTree
    c = pits.geometry.centroid
    xy = np.c_[c.x, c.y]
    if len(wells) == 0:
        keep = np.ones(len(pits), bool)
    else:
        d, _ = cKDTree(np.c_[wells.geometry.x, wells.geometry.y]).query(xy)
        keep = d > radius
    return pd.DataFrame({"site_id": [f"pit_{i}" for i in pits.loc[keep, "pit_full_id"].astype(str)]
                         if "pit_full_id" in pits else [f"pit_{i}" for i in np.flatnonzero(keep)],
                         "stratum": "pit_no_record", "easting": xy[keep, 0], "northing": xy[keep, 1],
                         "lidar_cx": xy[keep, 0], "lidar_cy": xy[keep, 1]})


def validate_pilot(pilot: pd.DataFrame, sf: dict) -> dict:
    """Checks from framework S0. Returns dict with ok flag and the list of problems."""
    probs = []
    n = len(pilot)
    if not sf["min_sites"] <= n <= sf["max_sites"]:
        probs.append(f"{n} sites, need {sf['min_sites']} to {sf['max_sites']}")
    strata = set(pilot["stratum"])
    bad = strata - set(STRATA)
    if bad:
        probs.append(f"unknown strata {sorted(bad)}")
    if len(strata) < sf["min_strata"]:
        probs.append(f"{len(strata)} strata, need {sf['min_strata']}")
    for k in ("confuser", "blank"):
        if k not in strata:
            probs.append(f"no {k} site")
    if "why_chosen" not in pilot or pilot["why_chosen"].isna().any():
        probs.append("why_chosen missing for some sites")
    if pilot["site_id"].duplicated().any():
        probs.append("duplicate site_id")
    return {"ok": not probs, "problems": probs, "n_sites": n, "strata": sorted(strata),
            "selection": "not random. Pilot tests practicality, not sensitivity"}


def run(cfg: dict, out_root: Path | None = None, wells=None, pits=None) -> dict:
    import geopandas as gpd
    sf, bbox = cfg["site_frame"], cfg["bbox_9t"]
    inputs = []
    if wells is None:
        p = io.need_input(cfg, "dep_wells")
        inputs.append(p)
        wells = gpd.read_file(p, layer=cfg["inputs"]["dep_wells"].get("layer"), bbox=tuple(bbox))
    ek.assert_crs(wells, cfg["crs"])
    wells = wells.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]].copy()
    if pits is None:
        p = io.need_input(cfg, "pits")
        inputs.append(p)
        pits = gpd.read_file(p, layer=cfg["inputs"]["pits"]["layer"])
    ek.assert_crs(pits, cfg["crs"])
    pits = pits[pits.geometry.centroid.within(box(*bbox))].copy()

    def opt(name):
        p = io.resolve(cfg["inputs"][name])
        if p.exists():
            inputs.append(p)
            return pd.read_csv(p)
        print(f"optional input absent: {name} ({p})")
        return None
    historic, conf, pilot = opt("historic_dates"), opt("confusers_blanks"), opt("pilot_sites")

    wells["stratum"] = assign_strata(wells, historic, sf["steel_era_after_year"], sf["sentinel_year_max"])
    n_raw, wells_all = len(wells), wells
    permit = wells["PERMIT_NUM"].astype("string")
    n_no_permit = int(permit.isna().sum())
    wells = wells[permit.notna()]
    n_dup = int(wells["PERMIT_NUM"].astype(str).duplicated().sum())
    wells = wells[~wells["PERMIT_NUM"].astype(str).duplicated()].copy()
    w = pd.DataFrame({"site_id": "well_" + wells["PERMIT_NUM"].astype(str), "stratum": wells["stratum"],
                      "easting": wells.geometry.x, "northing": wells.geometry.y,
                      "lidar_cx": np.nan, "lidar_cy": np.nan,
                      "well_status": wells.get("WELL_STATU"), "year": well_year(wells)})
    frames = [w, pits_no_record(pits, wells_all, sf["pit_no_record_radius_m"])]
    if conf is not None:
        frames.append(conf.rename(columns={"kind": "stratum"})[["site_id", "stratum", "easting", "northing"]])
    frame = pd.concat(frames, ignore_index=True)
    # A site_id collision across sources (pit, confuser, well) is an error, never a silent drop.
    ek.assert_unique(frame, "site_id")
    # Counted from the raw box, not from the deduplicated table, so the check can fail.
    ek.assert_rows(frame[frame.site_id.str.startswith("well_")], n_raw - n_no_permit - n_dup, "wells in frame")

    counts = frame["stratum"].value_counts().to_dict()
    summary = {"n_wells_in_box": int(n_raw), "n_records_no_permit": n_no_permit,
               "n_duplicate_permit_records_dropped": n_dup, "n_pits_in_box": int(len(pits)), "counts_by_stratum": counts,
               "early_era_needs": "independent historic date (4.6). DEP dates before 1930 are dated_pre_steel, not early era",
               "historic_dates_given": historic is not None, "confusers_given": conf is not None,
               "pilot_check": validate_pilot(pilot, sf) if pilot is not None else "no pilot_sites.csv yet"}
    rd = ek.new_run(cfg["exp_id"], "magframe", {"site_frame": sf, "bbox": bbox}, base=out_root,
                    why="S0 site frame by era stratum")
    o1, o2 = rd / "mag_site_frame_9t.csv", rd / "mag_site_frame_counts_9t.json"
    frame.to_csv(o1, index=False)
    o2.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    ek.write_provenance(rd, inputs, [o1, o2], params=sf, seeds={"master": cfg["master_seed"]})
    print(json.dumps(summary, indent=2, default=str))
    print("wrote", o1)
    return {"run_dir": rd, "frame": frame, "summary": summary}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    run(io.load_config(a.config), a.out_root)


if __name__ == "__main__":
    main()
