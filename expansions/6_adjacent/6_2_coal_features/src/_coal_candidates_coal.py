"""6.2 S1. Block grid, derivatives, frozen pit and pad inference, and well-model candidates in the coal area.

Purpose
    --make-blocks  Write complete 375 m blocks over the lidar extent (blocks with no features included).
    --commands     Print, or with --run execute, the existing repo commands that build the 0.5 m derivatives
                   (notebooks/wellsight_v2/s1_build/_build_derivatives.py) and run the frozen pit and pad models
                   (notebooks/wellsight_v2/s4_infer/_predict_on_tile.py). They are called, never copied or edited.
                   Full-extent processing is a user step. Measure one block first.
    default        Extract candidates from the pit and pad probability rasters per block with the 3.0 / fw_00
                   rule (0.10 floor, 4 m2 minimum, mean-probability score), reusing the 6.3 extractor.
Inputs
    lidar tiles for the coal area (data/_source/lidar/<coal_area>/, assumed), dem_greene_05.tif (extent),
    pit_prob_floor_greene_05.tif and pad_prob_greene_05.tif (assumed, from _predict_on_tile.py; VERIFY where
    that script writes and point config inputs.pit_prob / pad_prob at it)
Outputs
    data/greene/derived/05/coal_blocks_greene.gpkg               (--make-blocks)
    data/greene/results/coal/candidates/coal_well_candidates_greene.gpkg  layers pit, pad
Run
    python expansions/6_adjacent/6_2_coal_features/src/_coal_candidates_coal.py --make-blocks
    python expansions/6_adjacent/6_2_coal_features/src/_coal_candidates_coal.py --commands --tiles DIR --bbox X0,Y0,X1,Y1
    python expansions/6_adjacent/6_2_coal_features/src/_coal_candidates_coal.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

import _coal_common as K
from _coal_common import C, ek


def commands(cfg: dict, tiles: str, bbox: str) -> list[list[str]]:
    nb = ek.REPO / "notebooks" / "wellsight_v2"
    sfx = f"{cfg['area']}_05"
    return [[sys.executable, str(nb / "s1_build" / "_build_derivatives.py"), "--tiles", tiles, "--bbox", bbox,
             "--suffix", sfx, "--res", "0.5", "--crs", cfg["crs"]],
            [sys.executable, str(nb / "s4_infer" / "_predict_on_tile.py"), "--suffix", sfx]]


def well_candidates(cfg: dict, blocks, overrides: dict | None = None):
    """Per-model candidates in complete blocks. Returns {model: GeoDataFrame}."""
    import _confuser_pooled_score_9t as PS
    o = overrides or {}
    out = {}
    for model, key in (("pit", "pit_prob"), ("pad", "pad_prob")):
        p = C.input_path(cfg, key, o.get(key))
        g = PS.arm_candidates([p], blocks, cfg["crs"], cfg["score"])
        g["model"] = model
        g["cand_id"] = range(len(g))
        out[model] = g
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--make-blocks", action="store_true")
    ap.add_argument("--commands", action="store_true")
    ap.add_argument("--run", action="store_true", help="with --commands, execute them (heavy, user step)")
    ap.add_argument("--tiles", default=None)
    ap.add_argument("--bbox", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cfg = K.load_config(a.config)
    if a.make_blocks:
        import rasterio
        with rasterio.open(C.input_path(cfg, "lidar_extent")) as r:
            b = K.make_blocks(r.bounds, cfg["blocks"]["size_m"], cfg["crs"])
        p = C.resolve(cfg["inputs"]["blocks"])
        p.parent.mkdir(parents=True, exist_ok=True)
        b.to_file(p, layer="blocks", driver="GPKG")
        print(f"{len(b)} blocks. wrote {p}")
        return 0
    if a.commands:
        if not (a.tiles and a.bbox):
            raise SystemExit("--commands needs --tiles and --bbox")
        for cmd in commands(cfg, a.tiles, a.bbox):
            print(" ".join(cmd))
            if a.run:
                subprocess.run(cmd, check=True)
        return 0
    blocks = C.read_vector(C.input_path(cfg, "blocks"), cfg["crs"], layer="blocks")
    res = well_candidates(cfg, blocks)
    out = Path(a.out) if a.out else C.resolve(cfg["inputs"]["candidates"])
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    for m, g in res.items():
        g.to_file(out, layer=m, driver="GPKG")
    C.provenance(cfg, out.parent, "coalcands", outputs=[out], params=cfg["score"])
    print(pd.Series({m: len(g) for m, g in res.items()}).to_string())
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
