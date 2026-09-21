"""Can precision be computed on 613590? No, and this is the evidence.

THE CLAIM BEING CHECKED
-----------------------
`pit_transfer_recall_summary_613590_05.json` carries `annotation_complete:
false` and refuses to report precision on that basis. A results slide now
withholds a number because of that flag, so the flag has to be evidence rather
than an assertion somebody typed once.

WHY IT MATTERS WHICH WAY IT GOES
--------------------------------
Recall only asks: of the pits somebody DREW, how many did the model find? Every
one of those sits on ground a person looked at, so recall is sound either way.

Precision asks: of the pits the model CLAIMED, how many are wrong? Counting a
claim as wrong requires knowing there is no pit there. On ground nobody swept,
that is not known -- an unmatched prediction may be a false positive or a real
pit nobody has drawn yet, and nothing in the data separates them. Reporting
precision anyway would publish a floor as if it were a measurement.

THE TEST
--------
Compare how the drawn pits FILL 613590 against how they fill 9t, which was swept
end to end. The tile is divided into the same 375 m blocks the training split
uses. Three things separate a swept tile from a partly swept one:

  how many blocks hold a pit at all
  how concentrated the pits are -- what share sit in the busiest quarter
  whether the empty blocks are SCATTERED or form contiguous slabs

The third is the one that decides it. Ground with no pits is scattered among
ground with pits. Ground nobody swept comes in slabs.

RESULT
------
                             9t          613590
  blocks holding a pit       115/144     48/144
                             80%         33%
  in the busiest quarter     54%         92%
  drawn extent               99%         70% of tile area
  largest connected blank    17 blocks   91 blocks
                             12%         63% of the tile
  rims per floor             1.01        0.24

The last pair settles it. 9t's empty blocks are scattered, the largest run of
them touching 12% of the tile. 613590's form ONE region covering 63% -- the
whole left third and the whole bottom, in one piece. That is unswept ground, not
ground without pits.

The rim ratio says the annotation is partial a second way: 153 floors were drawn
but only 36 outlines, so even inside the swept part, most pits have no rim.

Run:
    python notebooks/wellsight_v2/s5_eval/_is_613590_fully_annotated.py
Writes:
    data/613590/results/annotation_coverage_613590_vs_9t.json
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[3]
ANN = ROOT / "qgis/annotations/annotations_proj.gpkg"
OUT = ROOT / "data/613590/results/annotation_coverage_613590_vs_9t.json"

TILES = {
    "9t": (619500.0, 4593000.0, 624000.0, 4597500.0),
    "613590": (613500.0, 4590000.0, 618000.0, 4594500.0),
}
#: The block the training split already uses, so this is comparable with it.
BLOCK = 375.0


def largest_blank_region(occ):
    """Blocks in the largest CONNECTED run of blank blocks, and its share.

    A slab of blank blocks is what unswept ground looks like; scattered blanks
    are what ground with no pits looks like.

    Counting fully blank rows or columns does not separate the two -- one stray
    pit anywhere along a row makes that row not blank, and on a 12-wide grid
    that happens constantly. It returned 1 against 0, which says nothing.
    Connected components do separate them: scattered blanks make many small
    components, an unswept margin makes one big one.
    """
    from scipy import ndimage
    lab, n = ndimage.label(~occ)
    if n == 0:
        return 0, 0.0
    sizes = ndimage.sum(~occ, lab, range(1, n + 1))
    biggest = int(sizes.max())
    return biggest, float(biggest / occ.size)


def main() -> int:
    ins = gpd.read_file(ANN, layer="pit_inside")
    outs = gpd.read_file(ANN, layer="pit_outside")
    print(f"pit_inside {len(ins)}, pit_outside {len(outs)}, {ins.crs}")

    res = {"block_m": BLOCK, "tiles": {}}
    for name, b in TILES.items():
        bx = box(*b)
        gi = ins[ins.intersects(bx)]
        go = outs[outs.intersects(bx)]
        n = int(round((b[2] - b[0]) / BLOCK))
        grid = np.zeros((n, n), int)
        cx = gi.geometry.centroid.x.values
        cy = gi.geometry.centroid.y.values
        col = np.clip(((cx - b[0]) / BLOCK).astype(int), 0, n - 1)
        row = np.clip(((b[3] - cy) / BLOCK).astype(int), 0, n - 1)
        for r, c in zip(row, col):
            grid[r, c] += 1
        occ = grid > 0
        flat = np.sort(grid.ravel())[::-1]
        q = max(1, occ.size // 4)
        blank_n, blank_f = largest_blank_region(occ)
        tb = gi.total_bounds if len(gi) else [0, 0, 0, 0]
        area_frac = (((tb[2] - tb[0]) * (tb[3] - tb[1]))
                     / ((b[2] - b[0]) * (b[3] - b[1]))) if len(gi) else 0.0

        d = dict(
            n_floors=int(len(gi)), n_rims=int(len(go)),
            rims_per_floor=float(len(go) / max(len(gi), 1)),
            blocks_total=int(occ.size), blocks_with_pit=int(occ.sum()),
            blocks_with_pit_pct=float(100 * occ.mean()),
            share_in_busiest_quarter=float(flat[:q].sum() / max(flat.sum(), 1)),
            drawn_extent_frac_of_tile=float(area_frac),
            largest_blank_region_blocks=blank_n,
            largest_blank_region_frac=blank_f)
        res["tiles"][name] = d

        print(f"\n{name}")
        print(f"  {d['n_floors']} floors, {d['n_rims']} rims "
              f"({d['rims_per_floor']:.2f} per floor)")
        print(f"  {d['blocks_with_pit']}/{d['blocks_total']} blocks hold a pit "
              f"({d['blocks_with_pit_pct']:.0f}%)")
        print(f"  busiest quarter holds "
              f"{100*d['share_in_busiest_quarter']:.0f}% of them")
        print(f"  drawn extent covers "
              f"{100*d['drawn_extent_frac_of_tile']:.0f}% of the tile")
        print(f"  largest connected blank region: "
              f"{d['largest_blank_region_blocks']} blocks, "
              f"{100*d['largest_blank_region_frac']:.0f}% of the tile")
        for r in range(n):
            print("    " + "".join("." if v == 0 else
                                   ("9" if v > 9 else str(v)) for v in grid[r]))

    a, c = res["tiles"]["9t"], res["tiles"]["613590"]
    res["verdict"] = (
        "613590 is partly annotated. Precision is not computable there: an "
        "unmatched prediction may be a false positive or a pit nobody drew.")
    print("\nVERDICT")
    print(f"  9t fills {a['blocks_with_pit_pct']:.0f}% of its blocks with "
          f"{100*a['share_in_busiest_quarter']:.0f}% in the busiest quarter,")
    print(f"  613590 fills {c['blocks_with_pit_pct']:.0f}% with "
          f"{100*c['share_in_busiest_quarter']:.0f}% in the busiest quarter,")
    print(f"  and its largest connected blank region covers "
          f"{100*c['largest_blank_region_frac']:.0f}% of the tile against "
          f"{100*a['largest_blank_region_frac']:.0f}% on 9t.")
    print("  Recall stands. Precision does not.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\n  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
