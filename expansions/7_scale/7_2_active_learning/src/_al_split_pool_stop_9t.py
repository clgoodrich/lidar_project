"""Split blocks into pool, discovery frame and stopping set, and build the item tables (7.2 S0).

Purpose
    1. Remove audit blocks (P2) from everything.
    2. Draw the stopping set (20 complete random blocks) with the master seed. Frozen before round 0.
    3. Draw the discovery frame (30% of the remaining 9t blocks, plus any extra discovery blocks).
    4. The rest is the candidate pool. Blocks within the derived buffer of the stopping set move to a
       buffer role and are used nowhere.
    5. Assert disjointness by block id and by buffered geometry. Hash the split JSON.
    With --build-items, extract candidates (type C) from the out-of-fold probability rasters with the
    7.3 scorer, one fold raster per held-out block, and list discovery windows (type W). Oracle labels
    (matched truth and missed features per window) go to a separate file used only by the replay.

Inputs
    blocks, audit list (from P2, --no-audit allowed and stamped), out-of-fold rasters and fold lists (held),
    truth pit_inside (held), extra discovery blocks (assumed, optional)
Outputs (expansions/7_scale/7_2_active_learning/results/tables/)
    al_split_9t_v1.json (with sha256 in al_split_9t_v1.sha256)
    data/interim/al_items_9t.gpkg   item polygons (candidate blobs and window blocks), gitignored
    al_items_9t.csv          item_id, type, block_id, tile_id, score, area_m2, circ, cx, cy, cost_min (no labels)
    al_oracle_9t.csv         item_id, matched_truth, n_truth_block, n_missed_block (replay only)
    al_stop_cands_9t.csv     stopping-set candidates with matched_truth, al_stop_blocks_9t.csv

Run
    python expansions/7_scale/7_2_active_learning/src/_al_split_pool_stop_9t.py --build-items
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _al_policies_select_9t import CFG, cfg_path, ek, load_cfg, need  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "7_3_benchmark" / "src"))
import _bench_evaluate_recall_k as sc  # noqa: E402


def make_split(blocks, audit: set, cfg: dict, extra=None, eligible: set | None = None) -> dict:
    """eligible limits the split to blocks inside the scored footprint (blocks with an out-of-fold raster)."""
    sp = cfg["split"]
    rng = np.random.default_rng(ek.child_seed(cfg["master_seed"], 0, 0))
    ids = sorted(int(b) for b in blocks["block_id"] if int(b) not in audit and (eligible is None or int(b) in eligible))
    if len(ids) < sp["stopping_blocks"] + 2:
        raise AssertionError("too few non-audit blocks for a stopping set")
    perm = [int(x) for x in rng.permutation(ids)]
    stopping = sorted(perm[: sp["stopping_blocks"]])
    rest = perm[sp["stopping_blocks"]:]
    stop_geom = blocks[blocks["block_id"].isin(stopping)].geometry.buffer(sp["buffer_m"]).union_all()
    geo = dict(zip(blocks["block_id"].astype(int), blocks.geometry))
    buffer = sorted(b for b in rest if geo[b].intersection(stop_geom).area > 0)
    rest = [b for b in rest if b not in set(buffer)]
    nd = int(round(sp["discovery_share"] * len(rest)))
    discovery = sorted(rest[:nd])
    pool = sorted(rest[nd:])
    if extra is not None:
        discovery = sorted(set(discovery) | set(int(b) for b in extra["block_id"]))
    for a, b, n in ((pool, discovery, "pool/discovery"), (pool, stopping, "pool/stopping"),
                    (discovery, stopping, "discovery/stopping"), (pool + discovery + stopping, audit, "any/audit")):
        ek.assert_disjoint(a, b, n)
    return {"version": "al_split_9t_v1", "master_seed": cfg["master_seed"], "buffer_m": sp["buffer_m"],
            "stopping": stopping, "discovery": discovery, "pool": pool, "buffer": buffer, "audit": sorted(audit)}


def build_items(cfg: dict, blocks, split: dict, folds: pd.DataFrame, truth, prob_fn) -> dict:
    """prob_fn(k) -> path of the fold-k out-of-fold raster. Each block is read from its own held-out fold."""
    held = folds[folds["role"].astype(str).str.startswith("held")].dropna(subset=["block_id"])
    fold_of = dict(zip(held["block_id"].astype(int), held["fold"].astype(int)))
    want = sorted(set(split["pool"]) | set(split["stopping"]) | set(split["discovery"]))
    specs = {}
    for b in want:
        if b in fold_of:
            specs.setdefault(fold_of[b], []).append(b)
    s, c = sc.evaluate([(prob_fn(k), bl) for k, bl in sorted(specs.items())], truth, blocks,
                       policy=sc.load_policy(cfg["scoring"]["task"]), B=0, keep_geometry=True)   # F02 shared policy
    c["tile_id"] = c["block_id"]
    # shape feature for the replay re-ranker. 1 for a disc, lower for elongated or ragged blobs
    c["circ"] = (4 * np.pi * c.geometry.area / np.maximum(c.geometry.length, 1e-9) ** 2).round(5)
    cost = cfg["cost_minutes"]
    cand = c[c["block_id"].isin(split["pool"])].copy()
    cand["item_id"] = "C" + cand["cand_id"].astype(str)
    cand["type"] = "C"
    cand["cost_min"] = cost["C"]
    bt = s["_blocks"].set_index("block_id")
    matched_by_block = c.dropna(subset=["matched_truth"]).groupby("block_id")["matched_truth"].nunique()
    win = pd.DataFrame({"block_id": split["discovery"]})
    win["item_id"] = "W" + win["block_id"].astype(str)
    win["type"] = "W"; win["tile_id"] = win["block_id"]; win["score"] = np.nan; win["area_m2"] = np.nan; win["circ"] = np.nan
    geo = dict(zip(blocks["block_id"].astype(int), blocks.geometry))
    win["cx"] = [geo[b].centroid.x if b in geo else np.nan for b in win["block_id"]]
    win["cy"] = [geo[b].centroid.y if b in geo else np.nan for b in win["block_id"]]
    win["cost_min"] = cost["W"]
    cols = ["item_id", "type", "block_id", "tile_id", "score", "area_m2", "circ", "cx", "cy", "cost_min"]
    items = pd.concat([cand[cols], win[cols]], ignore_index=True)
    ntb = lambda b: int(bt.loc[b, "n_truth"]) if b in bt.index else 0  # noqa: E731
    oracle = pd.concat([
        pd.DataFrame({"item_id": cand["item_id"], "matched_truth": cand["matched_truth"]}),
        pd.DataFrame({"item_id": win["item_id"], "matched_truth": None,
                      "n_truth_block": [ntb(b) for b in win["block_id"]],
                      "n_missed_block": [ntb(b) - int(matched_by_block.get(b, 0)) for b in win["block_id"]]})],
        ignore_index=True)
    keep = ["cand_id", "block_id", "score", "area_m2", "circ", "matched_truth"] +         [k for k in ("truth_block_id",) if k in c.columns] + ["cx", "cy"]        # 7.3 scorer 2 block-local matching
    stop_c = c[c["block_id"].isin(split["stopping"])][keep]
    stop_b = s["_blocks"][s["_blocks"]["block_id"].isin(split["stopping"])]
    ek.assert_rows(stop_b, len(split["stopping"]), "stopping blocks scored")
    import geopandas as gpd
    geo_items = gpd.GeoDataFrame(
        {"item_id": list(cand["item_id"]) + list(win["item_id"]), "type": ["C"] * len(cand) + ["W"] * len(win),
         "block_id": list(cand["block_id"]) + list(win["block_id"])},
        geometry=list(cand.geometry) + [geo[b] for b in win["block_id"]], crs=blocks.crs)
    return {"items": items, "items_geo": geo_items, "oracle": oracle, "stop_cands": stop_c, "stop_blocks": stop_b}


def main(argv=None) -> int:
    import geopandas as gpd
    ap = argparse.ArgumentParser(description="7.2 S0 split and item tables.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--no-audit", action="store_true",
                    help="allow a missing P2 audit file. The split is stamped 'no audit exclusion, exploratory'")
    ap.add_argument("--build-items", action="store_true")
    ap.add_argument("--out", default=str(ek.sub("7.2", "results/tables")))
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    inp = cfg["inputs"]
    out = Path(a.out)
    try:
        blocks = gpd.read_file(need(cfg_path(inp["blocks"]), "blocks"))
        blocks["block_id"] = blocks["block_id"].astype(int)
        ek.assert_crs(blocks, "EPSG:6346")
        adf = ek.require_audit(cfg_path(inp["audit_blocks"]), allow_missing=a.no_audit)   # never plain read_csv (P2-01)
        audit = ek.audit_ids(adf) if adf is not None else set()                            # audit and buffer rows
        ex_p = cfg_path(inp["discovery_extra_blocks"])
        extra = gpd.read_file(ex_p) if ex_p.exists() else None
        folds = pd.read_csv(need(cfg_path(inp["fold_blocks"]), "fold lists"))
        held = folds[folds["role"].astype(str).str.startswith("held")].dropna(subset=["block_id"])
        split = make_split(blocks, audit, cfg, extra, eligible=set(held["block_id"].astype(int)))
        split["audit_source"] = ("no audit exclusion, exploratory" if adf is None else
                                 f"{cfg_path(inp['audit_blocks'])} sha256 {adf.attrs.get('sha256')}")
        sp = out / "al_split_9t_v1.json"
        sp.write_text(json.dumps(split, indent=1), encoding="utf-8")
        (out / "al_split_9t_v1.sha256").write_text(ek.sha256(sp) + "\n", encoding="utf-8")
        print({k: len(v) for k, v in split.items() if isinstance(v, list)})
        if a.build_items:
            sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
            from _common import read_layer
            truth = read_layer(need(cfg_path(inp["truth"]), "truth"), inp["truth"]["layer"])
            prob = lambda k: need(ek.path_for(inp["oof_prob"]["key"]) / inp["oof_prob"]["rel"].format(k=k), "fold raster")  # noqa: E731
            r = build_items(cfg, blocks, split, folds, truth, prob)
            r["items"].to_csv(out / "al_items_9t.csv", index=False)
            r["items_geo"].to_file(ek.sub("7.2", "data/interim") / "al_items_9t.gpkg", driver="GPKG")
            r["oracle"].to_csv(out / "al_oracle_9t.csv", index=False)
            r["stop_cands"].to_csv(out / "al_stop_cands_9t.csv", index=False)
            r["stop_blocks"].to_csv(out / "al_stop_blocks_9t.csv", index=False)
            (out / "al_scoring_policy_9t.json").write_text(json.dumps(sc.load_policy(cfg["scoring"]["task"]), indent=2),
                                                          encoding="utf-8")
            print(r["items"]["type"].value_counts().to_dict())
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    ek.write_provenance(out, inputs=[cfg_path(inp["blocks"])], outputs=[out / "al_split_9t_v1.json"],
                        params=cfg["split"], seeds={"master": cfg["master_seed"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
