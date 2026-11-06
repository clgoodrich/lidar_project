"""6.3 S1 (and the S0 pilot draw). Score-stratified sample of candidates from non-audit blocks.

Purpose
    Draw candidates at the frozen cutoff, excluding every candidate whose centroid lies in a P2 audit block.
    Strata are equal-count score bands (five by default, cut at score quantiles). Each band gets the same number
    of draws, so inclusion probability is n_band / N_band and is written per row. Unmatched is not negative.
    Matched and unmatched candidates are both sampled. --pilot draws the 40-candidate codebook pilot instead.
    A reproducible 10% relabel subset is flagged for the second-reviewer check.
Inputs
    candidates    data/9t/results/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg (undecided, matched)  held
    blocks        data/9t/derived/05/pit_blocks_9t.gpkg                                                                 held
    audit_blocks  data/9t/results/splits/audit_blocks_9t_v1.csv (P2, read with ek.require_audit)                            assumed (P2)
Outputs
    data/9t/results/confusers/confuser_sample_9t.csv (pilot: confuser_pilot_sample_9t.csv), plus .gpkg twin
    and _PROVENANCE.json beside them
Run
    python expansions/6_adjacent/6_3_confuser_classes/src/_confuser_sample_9t.py [--pilot] [--out DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import _confuser_common_9t as C
from _confuser_common_9t import ek


def load_candidates(cfg: dict, override=None):
    import geopandas as gpd
    spec = cfg["inputs"]["candidates"]
    p = C.input_path(cfg, "candidates", override)
    parts = []
    for lyr in spec.get("layers", [None]):
        g = C.read_vector(p, cfg["crs"], layer=lyr)
        g["src_layer"] = lyr or "default"
        parts.append(g)
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=cfg["crs"])
    g["uid"] = g.src_layer + ":" + g["cand_id"].astype(str)
    ek.assert_unique(g, "uid")
    return g


def stratified_sample(cands, n_total: int, n_bands: int, seed: int, relabel_share: float):
    c = cands.copy().reset_index(drop=True)
    # equal-count bands by rank, so ties do not empty a band
    order = c["score"].rank(method="first").to_numpy() - 1
    c["band"] = (order * n_bands // len(c)).astype(int)
    per = n_total // n_bands
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_bands):
        pool = c[c.band == b]
        n = min(per, len(pool))
        pick = pool.iloc[rng.choice(len(pool), n, replace=False)] if n else pool.iloc[:0]
        pick = pick.assign(N_band=len(pool), n_band=n, incl_prob=n / len(pool) if len(pool) else np.nan,
                           band_lo=float(pool.score.min()) if len(pool) else np.nan,
                           band_hi=float(pool.score.max()) if len(pool) else np.nan)
        rows.append(pick)
    s = pd.concat(rows, ignore_index=True)
    s["sample_order"] = rng.permutation(len(s))
    s = s.sort_values("sample_order").reset_index(drop=True)
    s["relabel"] = False
    n_rel = int(np.ceil(relabel_share * len(s)))
    s.loc[rng.choice(len(s), n_rel, replace=False), "relabel"] = True
    return s


def build(cfg: dict, out_dir: Path, pilot: bool = False, overrides: dict | None = None, allow_no_audit: bool = False):
    o = overrides or {}
    sp = cfg["sample"]
    cands = load_candidates(cfg, o.get("candidates"))
    blocks = C.read_vector(C.input_path(cfg, "blocks", o.get("blocks")), cfg["crs"], layer=cfg["inputs"]["blocks"].get("layer"))
    audit = C.audit_block_ids(cfg, o.get("audit_blocks"), roles=("audit", "buffer"), allow_missing=allow_no_audit)
    audit_note = "audit and buffer blocks excluded"
    if audit is None:
        audit, audit_note = [], "no audit exclusion, exploratory"
        print("WARNING no P2 audit file. Sample is labelled 'no audit exclusion, exploratory'.")
    cent = np.column_stack([cands.geometry.centroid.x, cands.geometry.centroid.y])
    cands["block_id"] = C.block_of_points(cent, blocks)
    cands["cx"], cands["cy"] = cent[:, 0], cent[:, 1]
    n0 = len(cands)
    keep = ~cands.block_id.isin(audit)
    cands = cands[keep]
    print(f"candidates {n0}, in audit blocks {int((~keep).sum())}, eligible {len(cands)}")
    seed = ek.child_seed(sp["master_seed"], 0, 1 if pilot else 0)
    s = stratified_sample(cands, sp["n_pilot"] if pilot else sp["n_total"], sp["n_bands"], seed, sp["relabel_share"])
    s["audit_exclusion"] = audit_note
    ek.assert_disjoint(s.block_id.dropna().astype(int), audit, "sample vs audit blocks")
    ek.assert_unique(s, "uid")
    stem = "confuser_pilot_sample" if pilot else "confuser_sample"
    csv = out_dir / f"{stem}_{cfg['area']}.csv"
    s.drop(columns="geometry").to_csv(csv, index=False)
    gp = out_dir / f"{stem}_{cfg['area']}.gpkg"
    if gp.exists():
        gp.unlink()
    s[["uid", "band", "incl_prob", "relabel", "geometry"]].to_file(gp, driver="GPKG")
    C.provenance(cfg, out_dir, "confsample", inputs=[C.input_path(cfg, "candidates", o.get("candidates"))],
                 outputs=[csv, gp], params=cfg["sample"], seeds={"sample": seed})
    return csv, s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--pilot", action="store_true", help="draw the 40-candidate codebook pilot")
    ap.add_argument("--out", default=None, help="default data/9t/results/confusers/")
    ap.add_argument("--candidates", default=None)
    ap.add_argument("--audit-blocks", default=None)
    ap.add_argument("--allow-no-audit", action="store_true", help="exploratory only. Draw with no P2 audit exclusion")
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    csv, s = build(cfg, C.results_dir(cfg, a.out), a.pilot, {"candidates": a.candidates, "audit_blocks": a.audit_blocks},
                   allow_no_audit=a.allow_no_audit)
    print(s.groupby("band").agg(n=("uid", "size"), N=("N_band", "first"), p=("incl_prob", "first")).to_string())
    print(f"wrote {csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
