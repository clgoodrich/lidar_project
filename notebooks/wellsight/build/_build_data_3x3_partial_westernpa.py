"""Group EVERY WesternPA 2019 D20 LAZ tile into a derivative block.

The original 3x3 builder (`_build_3x3_hillshades` / `_build_data_3x3_derivatives`)
only emits a block when all 9 tiles of a non-overlapping 3x3 are present, which
drops the ~50 tiles on the right/top edges of the discovered grid.

This script uses the SAME stride-3 grid (so the 14 existing full blocks under
data/derivatives/data_3x3/westernpa_d20/ are reused untouched) but emits a block
for EVERY non-empty partition cell, with whatever members are present (1-9).
Each tile lands in exactly one block -> full coverage, no overlap.

For partial cells the block bbox is the tight union of the present member tiles
(no empty nodata padding) and the block key is the SW-most present member's code.

CLI:
  python notebooks/wellsight/build/_build_data_3x3_partial_westernpa.py --list
  python notebooks/wellsight/build/_build_data_3x3_partial_westernpa.py
  python notebooks/wellsight/build/_build_data_3x3_partial_westernpa.py --only 622591,618591
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DERIV, DST_CRS, ROOT
from _build_derivatives import build as build_derivatives  # type: ignore
from _build_3x3_hillshades import (  # type: ignore
    TILE_M, discover_tiles, build_indices, axis_origins,
)

OUT_REGION = DERIV / "data_3x3" / "westernpa_d20"
STRIDE = 3


def enumerate_partition() -> list[dict]:
    """Non-overlapping stride-3 cells; one block per non-empty cell."""
    tiles = discover_tiles()
    e_idx, n_idx = build_indices(tiles)
    e_origin, n_origin = axis_origins(e_idx, n_idx)
    # grid[(ei,ni)] = (band, e_code, n_code, path)
    grid = {(e_idx[e], n_idx[(b, n)]): (b, e, n, p) for (b, e, n), p in tiles.items()}
    max_ei = max(k[0] for k in grid)
    max_ni = max(k[1] for k in grid)

    blocks: list[dict] = []
    for ei0 in range(0, max_ei + 1, STRIDE):
        for ni0 in range(0, max_ni + 1, STRIDE):
            cells = [(ei0 + de, ni0 + dn)
                     for de in range(STRIDE) for dn in range(STRIDE)
                     if (ei0 + de, ni0 + dn) in grid]
            if not cells:
                continue
            members = [grid[c][3] for c in cells]
            # Tight bbox = union of present member tile footprints.
            eis = [c[0] for c in cells]
            nis = [c[1] for c in cells]
            x0 = e_origin + min(eis) * TILE_M
            x1 = e_origin + (max(eis) + 1) * TILE_M
            y0 = n_origin + min(nis) * TILE_M
            y1 = n_origin + (max(nis) + 1) * TILE_M
            # Key = SW-most present member (min ei, then min ni).
            sw_cell = min(cells, key=lambda c: (c[0], c[1]))
            b, e, n, _ = grid[sw_cell]
            blocks.append({
                "key": f"{e}{n}", "members": members,
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "n_tiles": len(members), "full": len(members) == STRIDE * STRIDE,
            })
    blocks.sort(key=lambda bl: (bl["y0"], bl["x0"]))
    return blocks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="enumerate blocks and exit")
    ap.add_argument("--only", help="comma-separated block keys")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    blocks = enumerate_partition()
    only = set(args.only.split(",")) if args.only else None

    n_full = sum(b["full"] for b in blocks)
    print(f"partition: {len(blocks)} blocks ({n_full} full, {len(blocks)-n_full} partial)")
    for b in blocks:
        out_dir = OUT_REGION / b["key"]
        built = (out_dir / f"dem_{b['key']}_1m.tif").exists()
        state = "built" if built else "NEW"
        print(f"  {b['key']:>7}  {b['n_tiles']}t  "
              f"x={b['x0']:.0f}..{b['x1']:.0f} y={b['y0']:.0f}..{b['y1']:.0f}  "
              f"{'full' if b['full'] else 'partial':7}  [{state}]")
    if args.list:
        return 0

    todo = []
    for b in blocks:
        if only and b["key"] not in only:
            continue
        dem = OUT_REGION / b["key"] / f"dem_{b['key']}_1m.tif"
        if dem.exists() and not args.overwrite:
            continue  # already built (the 14 full blocks)
        todo.append(b)

    if not todo:
        print("\nnothing to build (all present; use --overwrite to rebuild)")
        return 0
    print(f"\nwill build {len(todo)} block(s): {', '.join(b['key'] for b in todo)}")

    t_all = time.time()
    for b in todo:
        key = b["key"]
        sfx = f"{key}_1m"
        out_dir = OUT_REGION / key
        merge_path = ROOT / "data" / "files" / f"_merged_westernpa_d20_{sfx}.las"
        print(f"\n========== westernpa_d20/{key} ({b['n_tiles']} tiles) ==========")
        print(f"  bbox: {b['x0']:.0f},{b['y0']:.0f},{b['x1']:.0f},{b['y1']:.0f}  "
              f"({b['x1']-b['x0']:.0f}x{b['y1']-b['y0']:.0f} m)")
        t0 = time.time()
        try:
            build_derivatives(
                b["members"], x0=b["x0"], y0=b["y0"], x1=b["x1"], y1=b["y1"],
                res=1.0, sfx=sfx, dst_crs=DST_CRS, src_crs=None,
                merge_path=merge_path,
                skip_existing=(not args.overwrite), out_dir=out_dir,
            )
        except Exception as e:
            print(f"  [{key}] FAILED: {e}")
            continue
        print(f"  [{key}] done in {time.time()-t0:.1f}s")
        if merge_path.exists():
            sz = merge_path.stat().st_size / 1e9
            try:
                merge_path.unlink()
                print(f"  removed merge intermediate ({sz:.1f} GB)")
            except OSError:
                pass

    print(f"\nALL DONE in {(time.time()-t_all)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
