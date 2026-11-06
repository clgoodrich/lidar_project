"""6.2 S2. Freeze coal audit blocks, draw the labelling sample, and build blind sheets with the 6.3 tools.

Purpose
    1. Freeze the coal-area audit blocks (20% of complete blocks, seeded) before any labelling. If the file exists
       it is read, never redrawn.
    2. From non-audit blocks, draw well-model candidates (S1) stratified by score band (five equal-count bands)
       and by inventory proximity (near or far from any mine record), so each stratum has the same draw count.
       Add inventory records (all classes) and random points in non-audit blocks so unlisted features are found.
       Inclusion probability is written per row (1 for random points, which are an area sample).
    3. Hand the sample to the 6.3 sheet builder. Sheets show no score, no layer attributes and no source.
       Classes M S H W O U (config_6_2.json). Labels then go through the 6.3 agreement script with this config.
Inputs
    data/greene/results/coal/candidates/coal_well_candidates_greene.gpkg (S1), mine layers (assumed), blocks (S1)
Outputs
    expansions/6_adjacent/6_2_coal_features/results/tables/coal_audit_blocks_greene.csv
    data/greene/results/coal/coal_label_sample_greene.csv
    data/greene/results/coal/sheets/*.png, confuser_labels_greene.csv, confuser_sheet_key_greene.csv (6.3 names)
Run
    python expansions/6_adjacent/6_2_coal_features/src/_coal_label_sheets_coal.py [--reviewers A,B] [--out DIR]
    then  python expansions/6_adjacent/6_3_confuser_classes/src/_confuser_agreement_9t.py --config expansions/6_adjacent/6_2_coal_features/src/config_6_2.json
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import _coal_common as K
from _coal_common import C, ek


def freeze_audit(cfg: dict, blocks) -> list[int]:
    p = C.resolve(cfg["inputs"]["audit_blocks"])
    if p.exists():
        return C.read_block_ids(p)
    rng = np.random.default_rng(ek.child_seed(cfg["sample"]["master_seed"], 0, 30))
    n = max(1, int(round(cfg["sample"]["audit_block_share"] * len(blocks))))
    ids = sorted(int(b) for b in rng.choice(blocks.block_id.to_numpy(), n, replace=False))
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"block_id": ids, "role": "audit"}).to_csv(p, index=False)
    return ids


def draw(cfg: dict, cands, rec, blocks, audit: list[int], prox_m: float = 50.0):
    from scipy.spatial import cKDTree
    sp = cfg["sample"]
    rng = np.random.default_rng(ek.child_seed(sp["master_seed"], 0, 31))
    ok = blocks[~blocks.block_id.isin(audit)]
    cxy = np.column_stack([cands.geometry.centroid.x, cands.geometry.centroid.y])
    cands = cands.assign(cx=cxy[:, 0], cy=cxy[:, 1], block_id=C.block_of_points(cxy, blocks))
    cands = cands[cands.block_id.isin(ok.block_id)].reset_index(drop=True)
    rxy = np.column_stack([rec.geometry.centroid.x, rec.geometry.centroid.y])
    d = cKDTree(rxy).query(cands[["cx", "cy"]].to_numpy())[0] if len(rxy) else np.full(len(cands), np.inf)
    cands["near_inventory"] = d <= prox_m
    order = cands.score.rank(method="first").to_numpy() - 1
    cands["band"] = (order * sp["n_bands"] // max(len(cands), 1)).astype(int)
    per = sp["n_total"] // (sp["n_bands"] * 2)
    parts = []
    for (b, near), pool in cands.groupby(["band", "near_inventory"]):
        n = min(per, len(pool))
        pick = pool.iloc[rng.choice(len(pool), n, replace=False)]
        parts.append(pick.assign(incl_prob=n / len(pool), source="candidate"))
    s = pd.concat(parts, ignore_index=True)[["uid", "cx", "cy", "band", "incl_prob", "score", "source", "block_id"]]
    rec_ok = rec[rec.geometry.centroid.within(ok.union_all())]
    nr = min(sp["per_class_audit"], len(rec_ok))
    rp = rec_ok.iloc[rng.choice(len(rec_ok), nr, replace=False)] if nr else rec_ok.iloc[:0]
    s = pd.concat([s, pd.DataFrame({"uid": "rec:" + rp.record_id, "cx": rp.geometry.centroid.x,
                                    "cy": rp.geometry.centroid.y, "band": -1, "incl_prob": nr / max(len(rec_ok), 1),
                                    "score": np.nan, "source": "inventory record"})], ignore_index=True)
    pts = []
    oks = list(ok.geometry)
    while len(pts) < sp["n_random_candidates"] and oks:
        g = oks[int(rng.integers(len(oks)))]
        x0, y0, x1, y1 = g.bounds
        pts.append((rng.uniform(x0, x1), rng.uniform(y0, y1)))
    s = pd.concat([s, pd.DataFrame({"uid": [f"rnd:{i}" for i in range(len(pts))], "cx": [p[0] for p in pts],
                                    "cy": [p[1] for p in pts], "band": -2, "incl_prob": 1.0, "score": np.nan,
                                    "source": "random point"})], ignore_index=True)
    s["relabel"] = False
    s.loc[rng.choice(len(s), int(np.ceil(sp["relabel_share"] * len(s))), replace=False), "relabel"] = True
    ek.assert_unique(s, "uid")
    return s.iloc[rng.permutation(len(s))].reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--reviewers", default="reviewer_a,reviewer_b")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-sheets", action="store_true")
    a = ap.parse_args()
    cfg = K.load_config(a.config)
    out = C.results_dir(cfg, a.out)
    import _confuser_sample_9t as S1
    import _confuser_sheets_9t as S2
    blocks = C.read_vector(C.input_path(cfg, "blocks"), cfg["crs"], layer="blocks")
    audit = freeze_audit(cfg, blocks)
    rec, _ = K.read_mine_layers(cfg)
    s = draw(cfg, S1.load_candidates(cfg), rec, blocks, audit)
    ek.assert_disjoint(s.block_id.dropna().astype(int), audit, "coal sample vs audit")
    csv = out / f"coal_label_sample_{cfg['area']}.csv"
    s.to_csv(csv, index=False)
    print(s.source.value_counts().to_string())
    if not a.no_sheets:
        r = S2.build(cfg, out, csv, a.reviewers.split(","))
        print(f"wrote {len(r['sheets'])} sheets, {r['labels']}, {r['key']}")
    print(f"wrote {csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
