"""6.2 S0a. Inventory audit draw. Records per class, chips for identity checks, and completeness blocks.

Purpose
    Read the PA DEP mine layers (assumed), map type codes to M, S and H, list every unmapped code, and draw
    50 records per class by simple random sampling inside the test-area blocks (all records if fewer). Each
    record gets a chip sheet (hillshade, slope, relief, aerial) with the record marked, reusing the 6.3 sheet
    renderer. The entry file has blank fields for identity (same class, other class, nothing visible,
    uncertain) and offset in metres. Separately, 20 random complete blocks are drawn for the blind
    completeness pass, in which a reviewer lists every visible mine feature without the layer.
Inputs
    mine layers   data/greene/source/dep_mine_features/*.gpkg   assumed (config mine_layers)
    blocks        data/greene/derived/05/coal_blocks_greene.gpkg  assumed (S1 --make-blocks)
    hillshade, slope, relief at 0.5 m in data/greene/derived/05/ assumed (S1). aerial optional.
Outputs (data/greene/results/coal/)
    coal_audit_records.csv (entry file), coal_audit_unmapped_codes.json, coal_completeness_blocks.csv,
    audit_chips/<record>.png, _runs/<run_id>/_PROVENANCE.json
Run
    python expansions/6_adjacent/6_2_coal_features/src/_coal_inventory_sample_coal.py [--out DIR] [--no-chips]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _coal_common as K
from _coal_common import C, ek


def draw(rec, blocks, n_per: int, n_blocks: int, seed: int):
    inside = rec[rec.geometry.centroid.within(blocks.union_all())].copy()
    rng = np.random.default_rng(seed)
    rows = []
    for cls in ("M", "S", "H"):
        pool = inside[inside.cls == cls]
        n = min(n_per, len(pool))
        pick = pool.iloc[rng.choice(len(pool), n, replace=False)] if n else pool.iloc[:0]
        rows.append(pick.assign(N_class=len(pool), n_class=n, incl_prob=n / len(pool) if len(pool) else np.nan))
    s = pd.concat(rows, ignore_index=True)
    c = s.geometry.centroid
    s["cx"], s["cy"] = c.x, c.y
    for col in ("identity", "offset_m", "reviewer", "notes"):
        s[col] = ""
    comp = blocks.iloc[np.sort(rng.choice(len(blocks), min(n_blocks, len(blocks)), replace=False))][["block_id"]]
    comp = comp.assign(reviewer="", n_visible_M="", n_visible_S="", n_visible_H="", n_matched_M="", n_matched_S="",
                       n_matched_H="")
    return s, comp


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None, help="default data/<coal_area>/results/coal/")
    ap.add_argument("--no-chips", action="store_true")
    a = ap.parse_args()
    cfg = K.load_config(a.config)
    out = C.results_dir(cfg, a.out)
    rec, unmapped = K.read_mine_layers(cfg)
    blocks = C.read_vector(C.input_path(cfg, "blocks"), cfg["crs"], layer=cfg["inputs"]["blocks"]["layer"])
    sp = cfg["sample"]
    seed = ek.child_seed(sp["master_seed"], 0, 20)
    s, comp = draw(rec, blocks, sp["per_class_audit"], sp["completeness_blocks"], seed)
    csv = out / "coal_audit_records.csv"
    if csv.exists():
        raise FileExistsError(f"{csv} exists and may hold reviewer entries. Move it first.")
    s.drop(columns="geometry").to_csv(csv, index=False)
    (out / "coal_audit_unmapped_codes.json").write_text(json.dumps(unmapped, indent=2), encoding="utf-8")
    comp.to_csv(out / "coal_completeness_blocks.csv", index=False)
    if not a.no_chips:
        import _confuser_sheets_9t as SH
        rasters = {nm: C.input_path(cfg, nm, required=(nm != "aerial")) for nm in cfg["sheets"]["panels"]}
        d = out / "audit_chips"
        d.mkdir(exist_ok=True)
        for r in s.itertuples():
            chips = {nm: (SH.read_chip(p, r.cx, r.cy, cfg["sheets"]["chip_m"] / 2) if p else None) for nm, p in rasters.items()}
            SH.render_sheet(chips, d / f"{r.record_id.replace(':', '_')}.png", r.record_id, cfg["sheets"]["chip_m"], cfg["sheets"]["dpi"])
    C.provenance(cfg, out, "coalaudit", outputs=[csv], params=sp, seeds={"draw": seed})
    print(s.groupby("cls").agg(n=("record_id", "size"), N=("N_class", "first")).to_string())
    print(f"unmapped codes {unmapped}\nwrote {csv}\nwrote {out / 'coal_completeness_blocks.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
