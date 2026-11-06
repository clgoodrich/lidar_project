"""S4 well-feature pair features for 5.2 era classification (fw_5_2 section 7 S4).

Purpose
    Pad morphology for every annotated pad (area, perimeter, compactness, elongation, wells on pad, pits on pad,
    mean slope, void fraction) plus confound covariates kept apart (easting and northing, distance to the nearest
    annotated road, land cover, distance to the oil-field boundary, lidar flight year). Then one row per
    well-feature pair. Every DEP well in the 9t box is linked to the nearest pad within the configured radius,
    whatever its stratum, so S7 can compare sentinel wells with dated wells. Labels from S2 are joined when present.
    Missing optional layers give NaN columns and a note in the summary. They never stop the run.

Inputs (config_5_2.json)
    dep_wells           @dep_wells/venango_wells_all.gpkg (read-only)
    annotations         @truth/annotations_proj.gpkg layers plat, pit_inside, roads
    pad_blocks          @nine_t/pad_blocks_9t.gpkg layer blocks
    dem                 @nine_t/slope_9t_05.tif (optional, slope in degrees)
    ground_density      @nine_t/ground_density_9t_05.tif (optional, void fraction)
    landcover           ASSUMED @landcover/landcover_9t.tif (optional)
    oilfield_boundary   ASSUMED @reference/oil_field_boundaries/oil_fields_pa.gpkg (optional)
    labels              @exp:5.2/results/tables/era_interval_labels_9t.csv (optional, S2)
Outputs
    pad_morph_csv   @exp:5.2/results/tables/era_pad_morphology_9t.csv
    pairs_csv       @exp:5.2/results/tables/era_features_pairs_9t.csv
    run folder      @exp:5.2/results/<YYYYMMDD>_era_features_<hash>/
Evidence level
    (a) drawn feature.
Run
    python expansions/5_tasks/5_2_era_classification/src/_era_pair_features_9t.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _era_core_tools as ec  # noqa: E402
from _era_interval_labels_9t import link_features  # noqa: E402
from _era_strata_wells_9t import build_strata  # noqa: E402

ek = th.ek


def zonal(raster_path: Path, geoms, fn, nodata_is_value: bool = False) -> np.ndarray:
    """fn(values, inside_mask) per polygon from a windowed read. NaN when the polygon misses the raster.

    inside_mask is the polygon footprint. Nodata cells are dropped unless nodata_is_value, which the void
    fraction needs because ground_density stores 'no ground return' as its nodata value 0.
    """
    import rasterio
    from pyproj import CRS
    from rasterio.mask import raster_geometry_mask
    out = np.full(len(geoms), np.nan)
    with rasterio.open(raster_path) as r:
        c = CRS.from_user_input(r.crs)
        # 9t rasters are compound (EPSG:6346 + NAVD88). ek.assert_crs rejects that, so check the horizontal part.
        ek.assert_crs(c.sub_crs_list[0] if c.is_compound else c, th.CRS)
        for i, g in enumerate(geoms):
            try:
                outside, _, win = raster_geometry_mask(r, [g], crop=True)
            except ValueError:
                continue
            v = r.read(1, window=win)
            m = ~outside
            if not nodata_is_value and r.nodata is not None:
                m &= v != r.nodata
            if m.any():
                out[i] = fn(v, m)
    return out


def pad_table(pads, pits, wells_xy, roads, cfg, notes: dict) -> pd.DataFrame:
    from shapely import STRtree, points
    p = pads.reset_index(drop=True)
    t = ec.pad_morphology(p.geometry.values)
    t.insert(0, "pad_id", p["pad_id"].values)
    tree = STRtree(p.geometry.values)
    wi = tree.query(points(wells_xy), predicate="within")
    t["wells_on_pad"] = np.bincount(wi[1], minlength=len(p)) if len(wi[1]) else 0
    pc = pits.geometry.centroid
    pi = tree.query(pc.values, predicate="within")
    t["pits_on_pad"] = np.bincount(pi[1], minlength=len(p)) if len(pi[1]) else 0
    t["easting_km"], t["northing_km"] = t.cx / 1000.0, t.cy / 1000.0
    cen = points(np.c_[t.cx, t.cy])
    t["road_dist_m"] = roads.geometry.union_all().distance(cen) if roads is not None and len(roads) else np.nan
    if th.has(cfg, "dem"):
        t["slope_mean_deg"] = zonal(th.inp(cfg, "dem"), p.geometry.values, lambda v, m: float(v[m].mean()))
    else:
        t["slope_mean_deg"] = np.nan
        notes["slope_mean_deg"] = "dem missing"
    if th.has(cfg, "ground_density"):
        t["void_frac"] = zonal(th.inp(cfg, "ground_density"), p.geometry.values, lambda v, m: float((v[m] <= 0).mean()),
                            nodata_is_value=True)
    else:
        t["void_frac"] = np.nan
        notes["void_frac"] = "ground_density missing"
    if th.has(cfg, "landcover"):
        t["landcover_class"] = zonal(th.inp(cfg, "landcover"), p.geometry.values,
                                     lambda v, m: float(np.bincount(v[m].astype(int)).argmax()))
    else:
        t["landcover_class"] = np.nan
        notes["landcover_class"] = "ASSUMED landcover raster missing"
    if th.has(cfg, "oilfield_boundary"):
        of = th.read_vector(th.inp(cfg, "oilfield_boundary"))
        t["oilfield_dist_m"] = of.geometry.union_all().boundary.distance(cen)
    else:
        t["oilfield_dist_m"] = np.nan
        notes["oilfield_dist_m"] = "ASSUMED oil-field boundary missing"
    fy = cfg["features"].get("flight_year_9t")
    t["flight_year"] = np.nan if fy is None else float(fy)
    if fy is None:
        notes["flight_year"] = "flight year not set in config (VERIFY)"
    return t


def build_pairs(strata: pd.DataFrame, pad_t: pd.DataFrame, pads, blocks, cfg, labels=None) -> pd.DataFrame:
    xy = np.c_[strata.x.values, strata.y.values]
    pid, dist = link_features(xy, pads.reset_index(drop=True), cfg["link"]["pad_radius_m"], "pad_id")
    pr = strata[["permit", "stratum", "status", "spud_class", "x", "y"]].copy()
    pr["pad_id"], pr["pad_dist_m"] = pid, dist
    pr = pr[pr.pad_id.notna()].merge(pad_t, on="pad_id", how="left", validate="many_to_one")
    pr["block_id"] = th.block_id_of(np.c_[pr.cx.values, pr.cy.values], blocks) if len(pr) else []
    pr["cluster_id"] = pr["pad_id"]           # wells on one pad are one cluster and share the pad's block
    if labels is not None and len(labels):
        keep = ["permit", "stratum", "lo", "hi", "source", "identity_basis", "link_flag", "era_class", "early", "primary"]
        lab = labels[keep].drop_duplicates("permit").rename(columns={"stratum": "label_stratum"})
        lab = lab.assign(permit=lab.permit.astype(str))
        pr = pr.assign(permit=pr.permit.astype(str)).merge(lab, on="permit", how="left", validate="many_to_one")
        # S2 knew about map marks. Its stratum (dated_map) replaces the record-only one where a label exists.
        pr["stratum"] = pr["label_stratum"].fillna(pr["stratum"])
        pr = pr.drop(columns="label_stratum")
    else:
        for c in ["lo", "hi", "era_class", "early", "primary"]:
            pr[c] = np.nan
    pr = th.tag(pr, "a", "exploratory")
    pr["era_basis"] = np.where(pr["lo"].notna(), "interval", "none")
    return pr


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    dep_p, ann = th.inp(cfg, "dep_wells"), th.inp(cfg, "annotations")
    w = th.load_dep(dep_p, bbox=cfg["bbox_9t"])
    strata = build_strata(w, None, cfg)
    pads = th.read_vector(ann, "plat")
    pads = pads[pads.geometry.notna() & ~pads.geometry.is_empty]
    pits = th.read_vector(ann, "pit_inside")
    roads = th.read_vector(ann, "roads")
    blocks = th.read_vector(th.inp(cfg, "pad_blocks"), "blocks")
    notes: dict = {}
    pad_t = pad_table(pads, pits, np.c_[w.x.values, w.y.values], roads, cfg, notes)
    ek.assert_rows(pad_t, len(pads), "pad table vs plat")
    labels = pd.read_csv(th.inp(cfg, "labels")) if th.has(cfg, "labels") else None
    if labels is None:
        notes["labels"] = "S2 labels absent. Pairs carry no era."
    pairs = build_pairs(strata, pad_t, pads, blocks, cfg, labels)
    p1 = th.outp(cfg, "pad_morph_csv")
    th.tag(pad_t, "a", "exploratory").to_csv(p1, index=False)
    p2 = th.outp(cfg, "pairs_csv")
    pairs.to_csv(p2, index=False)
    run = ek.new_run("5.2", "era_features", {"link": cfg["link"], "features": cfg["features"]},
                     base=th.resolve(cfg["outputs"]["runs"]), why="S4 pad morphology and pair features.")
    ek.write_provenance(run, inputs=[dep_p, ann], outputs=[p1, p2], params={"notes": notes})
    print(f"pads {len(pad_t)}, wells in box {len(strata)}, well-pad pairs {len(pairs)}")
    print(pairs["stratum"].value_counts().to_string())
    print(notes)
    print(p1, p2, sep="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
