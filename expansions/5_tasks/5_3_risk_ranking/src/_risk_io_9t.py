"""Input loaders shared by the 5.3 stage scripts. Library, not a script.

Purpose
    Read the configured layers once, the same way in every stage.
    - records(): DEP wells in the 9t bbox, minus never-drilled statuses (read-only source)
    - candidates(): 5.6 S0 full detector output, or the held pit layers when it is absent (flagged)
    - footprint_km2(): scored eligible area, the blocks with n_pits > 0, for K = 40 per km2
    - receptors(): every receptor layer that exists. Missing assumed layers are recorded, not invented
    - start_run(): run folder under the 5.3 results/runs/ with _RUN.md and _CONFIG.json
Inputs (path specs in config_5_3.json)
    dep_wells, candidates_full, candidates_fallback, pit_blocks, roads, water_wells, buildings, streams,
    wetlands, public_supply, protected
Outputs
    None by itself.
Run
    Not runnable. Imported by the _risk_*_9t.py stage scripts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402
import _risk_ranking_core as rc  # noqa: E402

ek = th.ek
RECEPTOR_NAMES = ("roads", "water_wells", "buildings", "streams", "wetlands", "public_supply", "protected")


def records(cfg):
    w = th.load_dep(th.inp(cfg, "dep_wells"), bbox=cfg["bbox"])
    w = w[~w["WELL_STATU"].isin(cfg["record_statuses_excluded"])].copy()
    w = w.drop_duplicates("PERMIT_NUM").reset_index(drop=True)
    return w


def blocks(cfg):
    return th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")


def footprint_km2(cfg) -> float:
    b = blocks(cfg)
    b = b[b["n_pits"] > 0]
    return float(len(b) * cfg["block_size_m"] ** 2 / 1e6)


def candidates(cfg):
    """Returns (DataFrame cand_id, score, x, y, block_id, source, site_resolution)."""
    import geopandas as gpd
    if th.has(cfg, "candidates_full"):
        g = th.read_vector(th.inp(cfg, "candidates_full"))
        th.require_columns(g, ["score", "cx", "cy"], "candidates_full")
        # cand_id restarts per source layer in the 5.6 output. det_id is its unique detection id.
        if "det_id" in g:
            g["cand_id"] = g["det_id"].astype(int)
        resolution = "5.6_full_output"
    else:
        p = th.inp(cfg, "candidates_fallback")
        parts = []
        for layer in ("matched", "undecided"):
            x = th.read_vector(p, layer=layer)
            x["source"] = layer
            parts.append(x)
        g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=cfg["crs"])
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
        import _records_assoc_core as rac
        n0 = len(g)
        g = rac.dedupe(g, "deployment")
        print(f"  candidates fallback: {n0} rows, {len(g)} after deployment dedupe (unresolved blobs, flagged)")
        g["cand_id"] = np.arange(1, len(g) + 1)
        resolution = "unresolved_blobs"
    xy = np.c_[g["cx"].to_numpy(float), g["cy"].to_numpy(float)]
    if "block_id" not in g:
        g["block_id"] = th.block_id_of(xy, blocks(cfg))
    df = pd.DataFrame({"cand_id": g["cand_id"].astype(int).to_numpy(), "score": g["score"].to_numpy(float),
                       "x": xy[:, 0], "y": xy[:, 1], "block_id": g["block_id"].to_numpy(),
                       "source": g.get("source", pd.Series("unknown", index=g.index)).to_numpy()})
    ek.assert_unique(df, "cand_id")
    return df, resolution


def receptors(cfg, names=RECEPTOR_NAMES, strict: bool = False):
    """Load receptor layers. Returns (dict name -> rc.Receptor, list of missing names).
    A missing assumed layer is recorded and skipped. strict=True fails instead (th.MissingInput)."""
    out, missing = {}, []
    bb = cfg["bbox"]
    pad = 1000.0
    for name in names:
        ent = cfg["inputs"][name]
        if not th.has(cfg, name):
            if strict:
                th.inp(cfg, name)  # raises MissingInput with the hint
            missing.append(name)
            continue
        kind = ent.get("kind", "lines") if isinstance(ent, dict) else "lines"
        g = th.read_vector(th.inp(cfg, name))
        g = g.cx[bb[0] - pad:bb[2] + pad, bb[1] - pad:bb[3] + pad]
        err = "pos_error_m" if name == "water_wells" else None
        out[name] = rc.Receptor(name, kind, g, pos_error_col=err)
    return out, missing


def start_run(cfg, short: str, why: str, keys=None) -> Path:
    keep = {k: cfg[k] for k in (keys or []) if k in cfg}
    keep["stage"] = short
    return ek.new_run("5.3", short, keep, base=th.resolve(cfg["outputs"]["runs"]), why=why)
