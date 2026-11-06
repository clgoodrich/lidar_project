"""S1. Sites and exposure layers for risk ranking on 9t (fw_5_3 section 6 S1).

Purpose
    Build the site table and the exposure components E.
    Sites. Documented DEP wells in the 9t bbox (P = 1, p_source 'record') plus detector candidates with no
    record within the association radius (P = K-rank tercile band at K = 40 per km2 of scored area, p_source
    'feature_band', P(feature) and never P(well)). A candidate near a record is merged into that record site
    as surface evidence, flagged as a proposed association. Unresolved multi-well pads stay one site.
    Exposure. For each present receptor class, distance to the nearest receptor and counts (points) or
    presence (lines, polygons) within 50, 100, 250, 500 m. Water wells count with their positional error
    buffer (and a strict count without it). Protected areas and public supply give an inside flag, never a
    weight. E is saved as a component vector. It becomes an index only inside a scenario (S3).
    A missing assumed receptor layer is skipped and recorded in the summary (missing_components). --strict
    makes it fail instead.
Inputs (config_5_3.json)
    dep_wells, candidates_full (5.6 S0) or candidates_fallback, pit_blocks, roads (held),
    water_wells, buildings, streams, wetlands, public_supply, protected (assumed, fw_5_3 section 4A)
Outputs
    @exp:5.3/data/processed/risk_exposure_layers_9t.gpkg  layers sites, receptors_<name>
    @exp:5.3/results/tables/risk_exposure_sites_9t.csv     sites with every exposure component
    @exp:5.3/results/tables/risk_candidate_scores_9t.csv   every candidate score and block (S5 band cut points)
    @exp:5.3/results/tables/risk_exposure_summary_9t.json  counts, K, cut points, components, lineage
    run folder @exp:5.3/results/runs/<YYYYMMDD>_risk_exposure_<hash>/
Run
    python expansions/5_tasks/5_3_risk_ranking/src/_risk_exposure_layers_9t.py [--strict]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _risk_io_9t as rio  # noqa: E402
import _risk_ranking_core as rc  # noqa: E402

ek = th.ek


def build(cfg, strict: bool = False):
    """Returns (sites DataFrame with exposure columns, receptors dict, summary dict)."""
    rec = rio.records(cfg)
    rec["block_id"] = th.block_id_of(np.c_[rec.x, rec.y], rio.blocks(cfg))
    cand, resolution = rio.candidates(cfg)
    area = rio.footprint_km2(cfg)
    k = int(round(cfg["k_per_km2"] * area))
    sites, cuts = rc.build_sites(rec, cand, k, cfg["assoc_radius_m"])
    recs, missing = rio.receptors(cfg, strict=strict)
    ex = rc.exposure_table(sites[["x", "y"]].to_numpy(), recs, cfg["distance_bands_m"])
    for c in ex.columns:
        sites[c] = ex[c].to_numpy()
    comps = rc.e_component_columns(cfg["e_components"], set(recs))
    lineage = {c: [f"{next(n for n in recs if c.startswith(n + '_'))}:geometry"] for c in ex.columns}
    lineage["P"] = ["candidates:score", "dep_wells:PERMIT_NUM", "pit_blocks:n_pits", "config:k_per_km2"]
    rc.check_lineage(lineage, cfg["endpoint_columns"], cfg["endpoint_inputs"])
    summ = dict(n_records=int(len(rec)), n_candidates_in=int(len(cand)),
                n_sites=int(len(sites)), n_record_sites=int((sites.p_source == "record").sum()),
                n_candidate_sites=int((sites.p_source == "feature_band").sum()),
                n_records_with_surface_evidence=int(((sites.p_source == "record") & (sites.surface_evidence == 1)).sum()),
                scored_area_km2=area, k=k, k_per_km2=cfg["k_per_km2"], p_band_cuts=cuts,
                p_band_counts=sites["p_band"].value_counts().to_dict(), site_resolution=resolution,
                receptors_present=sorted(recs), missing_components=missing, e_components_used=comps,
                distance_bands_m=cfg["distance_bands_m"], lineage=lineage,
                note=("P for candidates is an ordinal band of the feature model, " + th.CONDITIONAL +
                      ". Exposure from present receptor layers only."))
    # identity check: sites in equals records plus unmerged candidates
    merged = sites.loc[(sites.p_source == "record") & (sites.surface_evidence == 1), "assoc_cand_id"]
    summ["n_candidates_merged_into_records"] = int(merged.nunique())
    summ["n_candidates_shared_by_several_records"] = int((merged.value_counts() > 1).sum())
    ek.assert_rows(sites, len(rec) + len(cand) - summ["n_candidates_merged_into_records"], "sites")
    summ["_cand"] = cand
    return sites, recs, summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    ap.add_argument("--strict", action="store_true", help="fail when an assumed receptor layer is missing")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    run = rio.start_run(cfg, "risk_exposure", "S1 sites and exposure.",
                        ["bbox", "k_per_km2", "assoc_radius_m", "distance_bands_m", "e_components"])
    sites, recs, summ = build(cfg, a.strict)
    import geopandas as gpd
    gp = th.outp(cfg, "sites_gpkg")
    if gp.exists():
        gp.unlink()
    g = gpd.GeoDataFrame(sites.replace([np.inf, -np.inf], np.nan),
                         geometry=gpd.points_from_xy(sites.x, sites.y), crs=cfg["crs"])
    g.to_file(gp, layer="sites", driver="GPKG")
    for name, r in recs.items():
        if len(r.xy):
            gpd.GeoDataFrame({"receptor": name}, index=range(len(r.xy)),
                             geometry=gpd.points_from_xy(r.xy[:, 0], r.xy[:, 1]), crs=cfg["crs"]
                             ).to_file(gp, layer=f"receptors_{name}", driver="GPKG")
    cand = summ.pop("_cand")
    cs = th.outp(cfg, "cand_scores_csv")
    cand[["cand_id", "score", "block_id", "source"]].to_csv(cs, index=False)
    csv = th.outp(cfg, "exposure_csv")
    sites.to_csv(csv, index=False)
    js = th.write_json(th.outp(cfg, "exposure_summary"), summ)
    ins = [th.inp(cfg, n) for n in ("dep_wells", "pit_blocks")] + [th.inp(cfg, n) for n in recs]
    ek.write_provenance(run, inputs=ins, outputs=[gp, csv, cs, js], params=summ)
    print({k: summ[k] for k in ("n_sites", "n_record_sites", "n_candidate_sites", "k", "missing_components")})
    print(f"wrote {gp}\nwrote {csv}\nwrote {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
