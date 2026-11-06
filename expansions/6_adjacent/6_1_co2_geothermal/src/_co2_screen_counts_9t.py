"""6.1 S4. Descriptive counts (Q3), labelled association, burden or coverage. None is recall or precision.

Purpose
    Count records, candidates and links inside the screening area. Give block-bootstrap intervals (375 m blocks,
    B = 2000) for the share of records with a candidate within the link radius and for candidates per km2 of
    eligible area. Evidence level is carried per row.
Inputs
    Run folder from S2: screening_package_9t.gpkg (layers L1_records, L2_candidates, L3_links, L4_eligible)
Outputs (run folder)
    screening_counts_9t.csv (hydrogen: screening_counts_h2_9t.csv)
Run
    python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_screen_counts_9t.py --out RUN_DIR [--profile co2]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio

import _co2_screen_lib as L
from _co2_screen_lib import ek


def _layer(gpkg: Path, name: str, crs: str):
    have = {r[0] for r in pyogrio.list_layers(gpkg)}
    return L.read_vector(gpkg, crs, layer=name) if name in have else None


def counts(cfg: dict, prof: dict, out_dir: Path, extra_rows=None, B: int | None = None) -> Path:
    p = cfg["params"]
    area = cfg["area"]
    gpkg = out_dir / L.fname("screening_package", prof, area, "gpkg")
    if not gpkg.exists():
        raise L.MissingInput(f"{gpkg} missing. Run _co2_screen_layers_9t.py first.")
    rec = _layer(gpkg, "L1_records", cfg["crs"])
    cand = _layer(gpkg, "L2_candidates", cfg["crs"])
    links = _layer(gpkg, "L3_links", cfg["crs"])
    elig = _layer(gpkg, "L4_eligible", cfg["crs"])
    elig["eligible"] = elig["eligible"].astype(str).isin(["True", "true", "1"])
    r_in = rec[rec["in_screen_area"].astype(str).isin(["True", "true", "1"])].reset_index(drop=True)
    r = cfg["params"]["link_radius_m"]
    d_rec = L.nearest_dist(L.xy(r_in), L.xy(cand))
    d_cand = L.nearest_dist(L.xy(cand), L.xy(r_in))
    elig_km2 = float(elig[elig.eligible].area.sum() / 1e6)
    tot_km2 = float(elig.area.sum() / 1e6)
    cand_blk = cand["block_id"].to_numpy(float) if len(cand) else np.array([])
    rec_blk = L.block_of(r_in, elig)
    eb = sorted(elig.loc[elig.eligible, "block_id"].astype(int))
    blk_km2 = dict(zip(elig.block_id.astype(int), elig.area / 1e6))
    B = B or p["bootstrap_B"]
    seed = ek.child_seed(p["master_seed"], 0, 4)

    # per-block totals, so a resample is a sum over drawn blocks (a block drawn twice counts twice)
    n_rec = {b: int(np.sum(rec_blk == b)) for b in eb}
    n_hit = {b: int(np.sum((rec_blk == b) & (d_rec <= r))) for b in eb}
    n_cand = {b: int(np.sum(cand_blk == b)) for b in eb}

    def share_rec(bl):
        den = sum(n_rec[b] for b in bl)
        return sum(n_hit[b] for b in bl) / den if den else np.nan

    def per_km2(bl):
        a = sum(blk_km2[b] for b in bl)
        return sum(n_cand[b] for b in bl) / a if a else np.nan

    rows = []
    def add(metric, value, label, level, lo=np.nan, hi=np.nan, note=""):
        rows.append({"metric": metric, "value": value, "lo95": lo, "hi95": hi, "label": label,
                     "evidence_level": level, "note": note})

    add("records_in_area", len(r_in), "count", "b")
    add("records_with_depth", int(r_in["depth_ft"].notna().sum()) if "depth_ft" in r_in else 0, "count", "b")
    add("records_with_plug_date", int(r_in["plug_date"].replace({"None": None, "nan": None}).notna().sum()), "count", "b")
    add("records_spud_sentinel_1800", int(r_in["spud_sentinel"].astype(str).isin(["True", "1"]).sum()), "count", "b")
    add("candidates_in_area", len(cand), "count", "a")
    add("candidates_within_K", int(cand["within_k"].astype(str).isin(["True", "1"]).sum()), "burden", "a")
    add("links_proposed", 0 if links is None else len(links), "association", "b",
        note="5.6 proposals" if links is not None else "5.6 not built")
    add(f"candidates_no_record_within_{r}m", int(np.sum(d_cand > r)), "association", "a")
    add(f"records_no_candidate_within_{r}m", int(np.sum(d_rec > r)), "association", "b")
    if eb:
        pt, lo, hi, _ = ek.block_bootstrap(share_rec, eb, B=B, seed=seed)
        add(f"share_records_with_candidate_{r}m", pt, "association", "b", lo, hi, "block bootstrap, eligible blocks")
        pt, lo, hi, _ = ek.block_bootstrap(per_km2, eb, B=B, seed=seed + 1)
        add("candidates_per_km2_eligible", pt, "burden", "a", lo, hi, "block bootstrap, eligible blocks")
    add("review_burden_K_per_km2", p["k_per_km2"], "burden", "a", note="policy K")
    add("eligible_km2", elig_km2, "coverage", "coverage")
    add("eligible_share_area", elig_km2 / tot_km2 if tot_km2 else np.nan, "coverage", "coverage")
    for row in (extra_rows(r_in, cand, cfg, prof) if extra_rows else []):
        add(**row)
    df = pd.DataFrame(rows)
    bad = df.metric.str.contains("recall|precision", case=False)
    if bad.any():
        raise AssertionError(f"counts may not be named recall or precision: {list(df.metric[bad])}")
    out = out_dir / L.fname("screening_counts", prof, area, "csv")
    df.to_csv(out, index=False)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--profile", default="co2")
    ap.add_argument("--profile-file", default=None)
    ap.add_argument("--out", required=True, help="run folder holding the S2 package")
    ap.add_argument("--B", type=int, default=None)
    a = ap.parse_args()
    cfg = L.load_config(a.config)
    prof = L.load_profile(cfg, a.profile, a.profile_file)
    out = counts(cfg, prof, Path(a.out), B=a.B)
    print(pd.read_csv(out).to_string(index=False))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
