"""5.4 S1. Distinct-well accounting for D and for the documented population N_doc, 9t.

Purpose
    D is the number of distinct candidate sites at the review budget K = 40 per km² of scored eligible area, not a
    blob count. The script
    1. takes the full pit detector output from 5.6 S0 (matched + unmatched, deployment dedupe),
    2. keeps candidates in the eligible footprint (pit blocks with n_pits > 0, including blocks with no detection),
    3. ranks by score, ties by larger area then det_id, and keeps the top K = round(40 x footprint km²),
    4. merges blobs whose centroids lie within merge_radius_m into one site (single linkage),
    5. builds N_doc from DEP records in the same footprint (statuses that imply a drilled hole), merging records within
       record_merge_m into one well,
    6. reports D at K = 30 as a sensitivity and a block bootstrap of D over footprint blocks.
    The site table's SHA-256 is the frame hash that 7.5 Arm B must quote (S3 refuses a mismatch).

Inputs (config_5_4.json)
    full_pit    expansions/5_tasks/5_6_record_association/data/processed/detector_output_pit_full_9t.gpkg
    pit_blocks  @nine_t/pit_blocks_9t.gpkg
    dep_wells   @dep_wells/venango_wells_all.gpkg (read-only)
Outputs
    expansions/5_tasks/5_4_undocumented_density/results/tables/density_distinct_sites_9t.csv
    expansions/5_tasks/5_4_undocumented_density/results/tables/density_accounting_9t.json
Run
    python expansions/5_tasks/5_4_undocumented_density/src/_density_distinct_wells_9t.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek
BLOCK_KM2 = 0.375 * 0.375


def merge_points(xy: np.ndarray, radius: float) -> np.ndarray:
    """Single-linkage cluster labels (0..n-1) for points closer than radius."""
    n = len(xy)
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    if n:
        for i, j in cKDTree(xy).query_pairs(radius):
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)
    roots = np.array([find(i) for i in range(n)], int)
    _, lab = np.unique(roots, return_inverse=True)
    return lab


def top_k(cand: pd.DataFrame, area_km2: float, k_per_km2: float) -> pd.DataFrame:
    k = int(round(k_per_km2 * area_km2))
    c = cand.sort_values(["score", "area_m2", "det_id"], ascending=[False, False, True])
    return c.head(k).copy(), k


def sites_from(cand: pd.DataFrame, radius: float) -> pd.DataFrame:
    xy = np.c_[cand["cx"].to_numpy(), cand["cy"].to_numpy()]
    cand = cand.copy()
    cand["site_id"] = merge_points(xy, radius)
    s = cand.groupby("site_id").agg(n_blobs=("det_id", "size"), cx=("cx", "mean"), cy=("cy", "mean"),
                                    max_score=("score", "max"), block_id=("block_id", "first"),
                                    any_matched=("novel", lambda v: int((v == 0).any()))).reset_index()
    return s


def doc_wells(dep, footprint_ids, blocks, exclude, radius):
    d = dep[~dep.WELL_STATU.isin(exclude)].copy()
    xy = np.c_[d.x.to_numpy(), d.y.to_numpy()]
    d["block_id"] = th.block_id_of(xy, blocks) if len(d) else []
    d = d[d.block_id.isin(footprint_ids)].reset_index(drop=True)
    lab = merge_points(np.c_[d.x.to_numpy(), d.y.to_numpy()], radius)
    return len(d), int(lab.max() + 1) if len(lab) else 0


def run(cfg) -> dict:
    pit = th.read_vector(th.inp(cfg, "full_pit"))
    ek.assert_rows(pit, cfg["expected_pit_rows"], "5.6 full pit output")
    ek.assert_unique(pit, "det_id")
    blocks = th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")
    fp = blocks[blocks.n_pits > 0]
    fp_ids = set(fp.block_id.astype(int))
    area = len(fp) * (cfg["block_m"] / 1000.0) ** 2
    cand = pd.DataFrame(pit.drop(columns="geometry"))
    if "area_m2" not in cand:
        cand["area_m2"] = pit.geometry.area
    cand = cand[cand.block_id.isin(fp_ids)]
    top, k = top_k(cand, area, cfg["k_per_km2"])
    sites = sites_from(top, cfg["merge_radius_m"])
    top30, k30 = top_k(cand, area, cfg["k_sensitivity_per_km2"])
    sites30 = sites_from(top30, cfg["merge_radius_m"])
    assert sites.n_blobs.sum() == len(top), "a candidate landed in two sites"
    dep = th.load_dep(th.inp(cfg, "dep_wells"), bbox=tuple(fp.total_bounds))
    n_rec, n_doc = doc_wells(dep, fp_ids, blocks, cfg["doc_statuses_exclude"], cfg["record_merge_m"])
    per_block = sites.groupby("block_id").size().reindex(sorted(fp_ids), fill_value=0)
    pb = per_block.to_dict()
    pt, lo, hi, _ = ek.block_bootstrap(lambda bl: float(sum(pb[b] for b in bl)), list(pb), B=cfg["bootstrap_B"],
                                       seed=int(cfg["seed"]))
    sites["rank"] = sites.max_score.rank(ascending=False, method="first").astype(int)
    sites["evidence_level"] = "a"
    out_s = th.outp(cfg, "sites")
    sites.sort_values("rank").to_csv(out_s, index=False)
    acc = dict(footprint_blocks=len(fp), footprint_km2=area, k_per_km2=cfg["k_per_km2"], K=k,
               candidates_in_footprint=len(cand), D_blobs=len(top), D_sites=len(sites),
               sites_with_several_blobs=int((sites.n_blobs > 1).sum()), sites_on_matched_feature=int(sites.any_matched.sum()),
               K30=k30, D_sites_K30=len(sites30), D_sites_block_bootstrap=dict(point=pt, lo=lo, hi=hi, B=cfg["bootstrap_B"]),
               N_doc_records=n_rec, N_doc_wells=n_doc, merge_radius_m=cfg["merge_radius_m"],
               record_merge_m=cfg["record_merge_m"], doc_statuses_exclude=cfg["doc_statuses_exclude"],
               frame_sha256=ek.sha256(out_s),
               note="D counts candidate sites (evidence level a). It is not a count of wells.")
    th.write_json(th.outp(cfg, "accounting"), acc)
    return acc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    acc = run(cfg)
    for k, v in acc.items():
        print(f"{k:28s} {v}")
    print("wrote", th.resolve(cfg["outputs"]["sites"]), "\nwrote", th.resolve(cfg["outputs"]["accounting"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
