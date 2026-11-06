"""6.1 S2. Build the layered screening package (profile co2, or hydrogen for 6.4).

Purpose
    Write one GeoPackage with layers L0_limits, L1_records, L2_candidates, L3_links, L4_eligible, L5_historic,
    L6_field and the screening polygon layer named by the profile (L7_screen_area for co2, L7_field_boundary for
    hydrogen). Optional layers that are absent are listed in L0_limits with the reason. Every layer carries one
    evidence_level and the build fails if any layer mixes levels. Candidates are worded "candidate" only.
Inputs
    S1 output screen_eligible_mask_9t.gpkg in the run folder (run S1 first)
    candidates_pit / candidates_pad   data/9t/results/records/detector_output_{pit,pad}_full_9t.gpkg   assumed (5.6)
    proposals                          data/9t/results/records/proposals_56_9t.csv                     assumed (5.6), optional
    dep_wells                          data/_source/reference/dep_wells/venango_wells_all.gpkg         held
    partner_area / partner_wells       data/_source/partners/co2_partner/                              assumed, optional
    historic, field                    4.6 and 7.5 outputs                                            assumed, optional
Outputs (run folder)
    screening_package_9t.gpkg (hydrogen: screening_package_h2_9t.gpkg)
    screening_layers_9t.json  row counts per layer, absent layers and reasons
Run
    python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_screen_layers_9t.py --out RUN_DIR [--profile co2]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

import _co2_screen_lib as L
from _co2_screen_lib import ek


def score_band(scores: np.ndarray, edges: list[float]) -> list[str]:
    idx = np.clip(np.digitize(scores, edges) - 1, 0, len(edges) - 2)
    return [f"{edges[i]:.2f}-{min(edges[i + 1], 1.0):.2f}" for i in idx]


def candidate_layer(cand, rec, elig, cfg: dict, proposals: pd.DataFrame | None):
    """Rank, K flag, nearest-record distance, link flag, blind-zone flag."""
    p = cfg["params"]
    c = cand.copy()
    blocks = elig[["block_id", "eligible", "geometry"]]
    c["block_id"] = L.block_of(c, blocks)
    elig_map = dict(zip(blocks.block_id, blocks.eligible))
    c["in_blind_zone"] = [not bool(elig_map.get(b, False)) if b == b else True for b in c.block_id]
    elig_km2 = float(blocks[blocks.eligible].area.sum() / 1e6)
    k = int(round(p["k_per_km2"] * elig_km2))
    c = c.sort_values(["score", "area_m2", "site_id"], ascending=[False, False, True], na_position="last")
    c["k_rank"] = np.arange(1, len(c) + 1)
    c["within_k"] = c.k_rank <= k
    c["score_band"] = score_band(c.score.to_numpy(), p["score_bands"])
    rec_xy = L.xy(rec)
    c["nearest_record_m"] = np.round(L.nearest_dist(L.xy(c), rec_xy), 1)
    if proposals is not None and len(proposals):
        linked = set(proposals.site_id.astype(str))
        c["linked_record"] = c.site_id.isin(linked)
        c["link_basis"] = "5.6 proposal"
    else:
        c["linked_record"] = c.nearest_record_m <= p["link_radius_m"]
        c["link_basis"] = f"record within {p['link_radius_m']} m (no 5.6 proposals)"
    c["label"] = "candidate"
    c["method"] = p["method_name"]
    c["method_version"] = p["method_version"]
    c["evidence_level"] = "a"
    return c.reset_index(drop=True), k, elig_km2


def links_layer(proposals: pd.DataFrame | None, cand, cfg: dict):
    import geopandas as gpd
    from shapely.geometry import LineString  # noqa: F401
    if proposals is None:
        return None, "5.6 proposals not built"
    pr = proposals.copy()
    pr["site_id"] = pr.site_id.astype(str)
    pr["link_ppv"] = pr["link_ppv"].where(pr["link_ppv"].notna(), "not measured").astype(str) \
        if "link_ppv" in pr else "not measured"
    pr["meaning"] = "proposed association only. Not a coordinate correction"
    m = pr.merge(cand[["site_id", "geometry"]], on="site_id", how="inner")
    ek.assert_rows(m, len(pr), "proposal to candidate join")
    g = gpd.GeoDataFrame(m, geometry="geometry", crs=cfg["crs"])
    g["evidence_level"] = "b"   # a link is a record-side proposal, reported with the record evidence level
    return g, ""


def build(cfg: dict, prof: dict, out_dir: Path, overrides: dict | None = None,
          records_hook: Callable | None = None, extra_layers: Callable | None = None) -> dict:
    """records_hook(rec, cfg, prof) -> rec adds profile-specific record columns (6.4 penetration flag).
    extra_layers(cfg, prof, area_poly) -> {name: gdf or None, ...}, {name: reason} adds optional layers."""
    import geopandas as gpd
    import pyogrio
    o = overrides or {}
    area = cfg["area"]
    p = cfg["params"]
    mask_path = Path(o.get("eligible") or out_dir / f"screen_eligible_mask_{area}.gpkg")
    if not mask_path.exists():
        raise L.MissingInput(f"S1 output {mask_path} missing. Run _co2_eligible_mask_9t.py --out {out_dir} first.")
    elig = L.read_vector(mask_path, cfg["crs"], layer="blocks")
    area_poly = L.screening_area(cfg, elig, o.get("partner_area"))
    rec = L.read_records(cfg, area_poly, p["screen_buffer_m"], o.get("dep_wells"), o.get("partner_wells"))
    if records_hook is not None:
        rec = records_hook(rec, cfg, prof)
    cand = L.read_candidates(cfg, o.get("candidates_pit"), o.get("candidates_pad"))
    n_cand_in = len(cand)
    cand = cand[cand.within(area_poly.geometry.iloc[0].buffer(p["screen_buffer_m"]))]
    prop_p = L.input_path(cfg, "proposals", o.get("proposals"), required=False)
    proposals = pd.read_csv(prop_p) if prop_p is not None else None
    cand, k, elig_km2 = candidate_layer(cand, rec, elig, cfg, proposals)
    links, links_reason = links_layer(proposals, cand, cfg)

    layers = {"L1_records": rec, "L2_candidates": cand, "L3_links": links,
              "L4_eligible": elig.assign(evidence_level="coverage")}
    absent = {}
    if links is None:
        absent["L3_links"] = links_reason
    for nm, key, lvl in (("L5_historic", "historic", "b"), ("L6_field", "field", None)):
        pth = L.input_path(cfg, key, o.get(key), required=False)
        if pth is None:
            absent[nm] = f"{cfg['inputs'][key]['state']} not on disk"
            layers[nm] = None
            continue
        g = L.read_vector(pth, cfg["crs"])
        if lvl:
            g["evidence_level"] = lvl
        elif "evidence_level" not in g:
            raise AssertionError(f"{pth} must carry evidence_level c or d per row")
        layers[nm] = g
    poly = area_poly.assign(buffer_m=p["screen_buffer_m"], evidence_level="context")
    layers[prof["screen_layer"]] = poly
    if extra_layers is not None:
        more, why = extra_layers(cfg, prof, area_poly)
        layers.update(more)
        absent.update(why)

    # QC 5 and the "candidate only" wording rule
    present = {k_: v for k_, v in layers.items() if v is not None}
    L.assert_single_level(present)
    for nm, g in present.items():
        if g.crs is not None:
            ek.assert_crs(g, cfg["crs"])
    if (cand["label"] != "candidate").any():
        raise AssertionError("L2 rows must be worded 'candidate'")

    limits = pd.DataFrame({"item": [f"limit_{i + 1}" for i in range(len(prof["limits"]))], "text": prof["limits"]})
    meta = pd.DataFrame({"item": ["profile", "partner", "policy_K_per_km2", "K_candidates", "eligible_km2",
                                  "frozen_cutoff", "link_rule"] + [f"absent:{k_}" for k_ in absent],
                         "text": [prof["name"], cfg["decisions"]["partner"], str(p["k_per_km2"]), str(k),
                                  f"{elig_km2:.4f}", str(p["frozen_cutoff"]), cand.link_basis.iloc[0] if len(cand) else ""]
                         + list(absent.values())})
    l0 = pd.concat([limits, meta], ignore_index=True)
    l0["evidence_level"] = "limits"

    gpkg = out_dir / L.fname("screening_package", prof, area, "gpkg")
    if gpkg.exists():
        gpkg.unlink()
    pyogrio.write_dataframe(l0, gpkg, layer="L0_limits", driver="GPKG")
    counts = {"L0_limits": len(l0)}
    for nm, g in present.items():
        g = g.copy()
        for col in g.columns:
            if col != "geometry" and g[col].dtype == object:
                g[col] = g[col].astype(str)
        g.to_file(gpkg, layer=nm, driver="GPKG")
        counts[nm] = len(g)
    info = {"package": str(gpkg), "profile": prof["name"], "rows": counts, "absent": absent,
            "candidates_read": n_cand_in, "candidates_in_area": len(cand), "K": k, "eligible_km2": elig_km2}
    js = out_dir / L.fname("screening_layers", prof, area, "json")
    js.write_text(json.dumps(info, indent=2, default=str), encoding="utf-8")
    return {"gpkg": gpkg, "json": js, "info": info, "layers": present}


def add_cli(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--config", default=None)
    ap.add_argument("--profile", default="co2")
    ap.add_argument("--profile-file", default=None)
    ap.add_argument("--out", default=None)
    for k_ in ("candidates-pit", "candidates-pad", "proposals", "dep-wells", "partner-area", "partner-wells",
               "eligible", "historic", "field"):
        ap.add_argument(f"--{k_}", default=None, help="override the configured path")


def overrides_from(a) -> dict:
    return {k_: getattr(a, k_) for k_ in ("candidates_pit", "candidates_pad", "proposals", "dep_wells",
                                          "partner_area", "partner_wells", "eligible", "historic", "field")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_cli(ap)
    a = ap.parse_args()
    cfg = L.load_config(a.config)
    prof = L.load_profile(cfg, a.profile, a.profile_file)
    out = L.run_dir(cfg, prof, a.out)
    r = build(cfg, prof, out, overrides_from(a))
    ek.write_provenance(out, outputs=[r["gpkg"], r["json"]], params={"cfg": cfg["params"], "profile": prof})
    print(json.dumps(r["info"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
