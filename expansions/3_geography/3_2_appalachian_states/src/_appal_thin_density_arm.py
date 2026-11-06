"""3.2 S9 (iii). Thinned-density sensitivity arm. Random point thinning of a window to the 9t ground density.

Purpose
    Native density is the primary test. This arm thins the target point cloud so its ground
    density matches 9t, then the same 0.5 m build, inference and scoring run on the same
    blocks, and the paired difference is reported as a sensitivity. Thinning removes
    information. It cannot reproduce 9t canopy holes, scan geometry or classification error,
    so a match here does not make the two surveys equivalent.
    Every point is kept with probability f = min(1, target / measured ground density), the
    same f for all classes, seeded per tile (ek.child_seed). Measured density comes from the
    S3 inventory. Output tiles are LAZ in the expansion data folder (gitignored).

Inputs
    S3 inventory   results/tables/<tag>/xfer_tile_inventory_<tag>.csv (ground_per_m2 per tile)
    tiles          config areas.<tag>.tiles

Outputs
    expansions/3_geography/3_2_appalachian_states/data/interim/<tag>/thin_<target>/<tile>.laz
    expansions/3_geography/3_2_appalachian_states/results/tables/<tag>/xfer_thin_arm_<tag>.json
    Then run 3.1 S3 with --tiles pointing at the thinned folder and a separate area suffix.

Run
    python expansions/3_geography/3_2_appalachian_states/src/_appal_thin_density_arm.py --tag ny_alg
    python expansions/3_geography/3_2_appalachian_states/src/_appal_thin_density_arm.py --tag ky_lee --target 2.70 --max-tiles 1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "3_1_warren_forest_mckean" / "src"))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_2.json"


def thin_file(src: Path, dst: Path, keep: float, seed: int, chunk: int = 5_000_000) -> tuple[int, int]:
    import laspy
    rng = np.random.default_rng(seed)
    n_in = n_out = 0
    with laspy.open(str(src)) as r:
        hdr = r.header
        with laspy.open(str(dst), mode="w", header=hdr) as w:
            for pts in r.chunk_iterator(chunk):
                m = rng.random(len(pts)) < keep
                n_in += len(pts); n_out += int(m.sum())
                if m.any():
                    w.write_points(pts[m])
    return n_in, n_out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--tag", required=True)
    ap.add_argument("--target", type=float, default=None, help="ground points per m2 (default 9t overall)")
    ap.add_argument("--max-tiles", type=int, default=None)
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.tag)
    target = a.target or cfg["reference"]["ground_per_m2_9t_overall"]
    inv = pd.read_csv(xl.need(ctx["tables"] / f"xfer_tile_inventory_{a.tag}.csv", "S3 inventory with ground density",
                              "run _appal_density_void_windows.py"))
    if "ground_per_m2" not in inv:
        raise xl.MissingInput("MISSING INPUT: inventory has no ground_per_m2 (run S3 with ground counts)")
    tiles = {t.name: t for t in ctx["tiles"]}
    out_dir = ek.sub("3.2", f"data/interim/{a.tag}/thin_{str(target).replace('.', 'p')}")
    rows = []
    for i, r in enumerate(inv.itertuples()):
        if a.max_tiles and i >= a.max_tiles:
            break
        src = xl.need(tiles.get(r.file), f"tile {r.file}")
        keep = float(min(1.0, target / r.ground_per_m2)) if r.ground_per_m2 > 0 else 1.0
        n_in, n_out = thin_file(src, out_dir / r.file, keep, ek.child_seed(cfg["master_seed"], i, 9))
        rows.append({"file": r.file, "ground_per_m2": r.ground_per_m2, "keep": keep, "n_in": n_in, "n_out": n_out})
        print(f"  {r.file}: keep {keep:.3f}, {n_in:,} -> {n_out:,}")
    rec = {"tag": a.tag, "target_ground_per_m2": target, "tiles": rows, "out_dir": str(out_dir),
           "label": "sensitivity arm; native density is primary"}
    js = ctx["tables"] / f"xfer_thin_arm_{a.tag}.json"
    js.write_text(json.dumps(rec, indent=2, default=float), encoding="utf-8")
    print(f"wrote {out_dir}\n      {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
