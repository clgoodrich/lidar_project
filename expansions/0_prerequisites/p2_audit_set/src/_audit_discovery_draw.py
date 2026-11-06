"""P2 S3. Random discovery sample for active learning (7.2), kept apart from every audit set.

Purpose
    Draw blocks at random from a block frame until their area reaches the target (default 20 km2). Blocks are
    eligible only if they are in no training, adaptation, test or audit list (any role other than the
    eligible roles in the frame, and any id in the given exclusion files). The draw is seeded and ordered by
    block id, so it repeats exactly. The sample is never tuned on and never joins the final audit set.
    9t cannot supply it. The whole tile is 20.25 km2 and every block was used by a model. The script fails
    clearly when the eligible area is short of the target.

Inputs (assumed, see config_p2.json `discovery.assumed_inputs.frame`)
    data/<area>/results/transfer/<area>_blocks.gpkg, layer blocks, columns block_id (int), role (str), geometry
    optional exclusion CSVs with a block_id column (audit files, training lists)

Outputs
    <out-dir>/discovery_blocks_<area>_v1.csv   block_id, area_km2, draw_order. Header records seed, target, frame hash
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/<area>/results/transfer/
    Run record under expansions/0_prerequisites/p2_audit_set/results/<run_id>/

Run
    python expansions/0_prerequisites/p2_audit_set/src/_audit_discovery_draw.py --area warren [--target-km2 20] [--exclude data/warren/results/transfer/audit_blocks_warren_v1.csv] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _audit_guard_lib as ag  # noqa: E402
ek = ag.ek
CFG = json.loads((HERE.parent / "config_p2.json").read_text(encoding="utf-8"))["discovery"]


def frame_path(area: str) -> Path:
    spec = CFG["assumed_inputs"]["frame"]
    return ek.area_dir(area) / spec["rel"].format(area=area)


def draw_discovery(frame, excluded: set[int], target_km2: float, seed: int,
                   eligible_roles=("", "unassigned", "discovery")) -> pd.DataFrame:
    f = frame.copy()
    f["block_id"] = f.block_id.astype(int)
    role = f["role"].fillna("").astype(str) if "role" in f.columns else pd.Series("", index=f.index)
    ok = role.isin(eligible_roles) & ~f.block_id.isin(excluded)
    pool = f[ok].sort_values("block_id")
    total = float(pool.geometry.area.sum() / 1e6)
    if total < target_km2:
        raise SystemExit(f"eligible area {total:.2f} km2 is short of the {target_km2} km2 target. "
                         "Use a larger frame or another area.")
    order = np.random.default_rng(seed).permutation(len(pool))
    picked, acc = [], 0.0
    for i in order:
        r = pool.iloc[int(i)]
        picked.append((int(r.block_id), float(r.geometry.area / 1e6)))
        acc += picked[-1][1]
        if acc >= target_km2:
            break
    return pd.DataFrame(picked, columns=["block_id", "area_km2"]).assign(draw_order=lambda d: np.arange(len(d)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P2 S3 discovery sample")
    ap.add_argument("--area", required=True)
    ap.add_argument("--frame", type=Path, default=None, help="override the assumed frame path")
    ap.add_argument("--exclude", type=Path, nargs="*", default=[], help="CSV files with block_id to exclude")
    ap.add_argument("--target-km2", type=float, default=CFG["target_km2"])
    ap.add_argument("--seed", type=int, default=CFG["seed"])
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    fp = a.frame or frame_path(a.area)
    if not fp.exists():
        raise SystemExit(f"assumed input missing. Block frame {fp} (schema in config_p2.json discovery.assumed_inputs.frame).")
    import geopandas as gpd
    frame = gpd.read_file(fp, layer=CFG["assumed_inputs"]["frame"]["layer"])
    ek.assert_crs(frame)
    excl = set()
    for e in a.exclude:
        excl |= set(pd.read_csv(e, comment="#").block_id.astype(int))
    d = draw_discovery(frame, excl, a.target_km2, a.seed)
    out = (a.out_dir or (ek.area_dir(a.area) / "results" / "transfer"))
    out.mkdir(parents=True, exist_ok=True)
    dst = out / (f"discovery_blocks_{a.area}_dryrun.csv" if a.dry_run else f"discovery_blocks_{a.area}_v1.csv")
    if dst.exists() and not a.dry_run:
        raise SystemExit(f"{dst} exists. A new draw needs a new version.")
    head = [f"# Discovery sample for active learning. Never tuned on. Not an audit set.",
            f"# seed={a.seed} target_km2={a.target_km2} frame={fp.name} frame_sha256={ek.sha256(fp)}"]
    dst.write_text("\n".join(head) + "\n" + d.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="\n")
    run = ek.new_run("p2", "discovery_draw", {k: str(v) for k, v in vars(a).items()}, why="S3 discovery sample.")
    ek.write_provenance(run, inputs=[fp] + list(a.exclude), outputs=[dst], seeds={"draw": a.seed})
    print(f"{len(d)} blocks, {d.area_km2.sum():.2f} km2\nwrote {dst}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
