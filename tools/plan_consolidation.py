"""Plan the Phase 2 move: loose rasters in data/derivatives/ -> tiles/<area>/.

`data/derivatives/` should hold directories. It holds 282 loose files. 182 of
them are rasters carrying a study-area suffix, and the repository already has a
home for exactly that: `data/derivatives/tiles/<area>/`, the convention used by
`mkf_1m`, `mckean_sw_05` and `613590_05`.

RULES
-----
1. Only files with ZERO references in docs/reference_index.csv move. Referenced
   files stay where the referring code expects them. Rebuild the index first --
   the notebook-decoding fix on 2026-08-12 changed reference counts.
2. Target is derived from the `_<area>_<res>` suffix, never guessed.
3. Sidecars follow their parent raster. A `.tif` drags `.tif.aux.xml` and
   `.tif.ovr` even when the sidecar itself is unreferenced.
4. Anything that cannot be classified from its own name is LEFT ALONE and
   listed. A file whose name does not say where it belongs is a naming problem
   to fix deliberately, not a filing problem to solve by guessing.

A NOTE ON THE BLOCK-LIKE NAMES
------------------------------
`607594`, `610594`, `610605` and `616593` look like `data_3x3` block ids but
match NO existing block (those run 604590, 604594 … 622608). They are from an
earlier tiling scheme, so they get their own top-level tile directories rather
than being filed under a `data_3x3` region they do not belong to.

Outputs:
    docs/_ledgers/phase2_consolidation_moves.csv   ledger for tools/apply_moves.py
    docs/phase2_consolidation_plan.md     what moves, what stays, and why

Reproduce:
  python tools/plan_consolidation.py
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DERIV = ROOT / "data" / "derivatives"
TILES = DERIV / "tiles"
INDEX = ROOT / "docs" / "reference_index.csv"
LEDGER = ROOT / "docs" / "_ledgers" / "phase2_consolidation_moves.csv"
PLAN = ROOT / "docs" / "phase2_consolidation_plan.md"

# <channel>_<area>_<res>.<ext>  -- area and res are what decide the destination
SUFFIX = re.compile(
    r"_(?P<area>9t|mk5|mck_e\d+n\d+|\d{6}|mckean|venango|washington)"
    r"_(?P<res>1m|05|2m)$", re.I)

SIDECAR_TAILS = (".aux.xml", ".ovr", ".ovr.aux.xml")
# 9t already exists and mixes resolutions; everything else gets <area>_<res>.
SPECIAL = {("9t", "1m"): "9t"}


def dest_dir(area: str, res: str) -> str:
    key = SPECIAL.get((area.lower(), res.lower()))
    return f"tiles/{key}" if key else f"tiles/{area.lower()}_{res.lower()}"


def split_sidecar(name: str) -> tuple[str, str]:
    """('road_prob_9t_1m.tif.aux.xml') -> ('road_prob_9t_1m.tif', '.aux.xml')"""
    for t in SIDECAR_TAILS:
        if name.lower().endswith(t):
            return name[: -len(t)], name[-len(t):]
    return name, ""


def main() -> int:
    if not INDEX.exists():
        print("run tools/build_reference_index.py first")
        return 1
    refs = {}
    sizes = {}
    with open(INDEX, encoding="utf8") as f:
        for r in csv.DictReader(f):
            refs[r["rel_path"]] = int(r["n_refs"])
            sizes[r["rel_path"]] = int(r["size_bytes"])

    loose = sorted(p for p in DERIV.iterdir() if p.is_file())
    print(f"{len(loose)} loose files in data/derivatives/")

    rows, stays = [], []
    by_dest = defaultdict(lambda: [0, 0])

    for p in loose:
        rel = p.relative_to(ROOT).as_posix()
        parent_name, tail = split_sidecar(p.name)
        parent_rel = f"data/derivatives/{parent_name}"

        # a sidecar inherits its parent's fate
        decide_name = parent_name if tail else p.name
        decide_rel = parent_rel if tail else rel

        stem = Path(decide_name).stem
        m = SUFFIX.search(stem)
        if not m:
            stays.append((rel, "name carries no <area>_<res> suffix"))
            continue
        if refs.get(decide_rel, 0) > 0:
            stays.append((rel, f"referenced ({refs[decide_rel]}x)"
                               + (" via its parent raster" if tail else "")))
            continue

        d = dest_dir(m.group("area"), m.group("res"))
        rows.append(dict(old_path=rel, new_path=f"data/derivatives/{d}/{p.name}",
                         phase="phase2",
                         reason=f"loose raster -> {d} by <area>_<res> suffix"))
        by_dest[d][0] += 1
        by_dest[d][1] += sizes.get(rel, p.stat().st_size)

    with open(LEDGER, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["old_path", "new_path", "phase", "reason"])
        w.writeheader(); w.writerows(rows)

    lines = ["# Phase 2 — consolidate loose rasters", "",
             f"`data/derivatives/` holds {len(loose)} loose files. "
             f"**{len(rows)} move**, {len(stays)} stay.", "",
             "| Destination | files | MB | exists today |", "|---|---:|---:|---|"]
    for d in sorted(by_dest):
        n, b = by_dest[d]
        lines.append(f"| `data/derivatives/{d}` | {n} | {b/2**20:.0f} | "
                     f"{'yes' if (DERIV / d).exists() else '**new**'} |")
    lines += ["", f"Total moving: {sum(v[1] for v in by_dest.values())/2**30:.2f} GB",
              "", "## Staying put", ""]
    grouped = defaultdict(list)
    for rel, why in stays:
        grouped[why.split(" (")[0]].append(rel)
    for why in sorted(grouped):
        lines.append(f"**{why}** — {len(grouped[why])} files")
        for r in grouped[why][:12]:
            lines.append(f"- `{r}`")
        if len(grouped[why]) > 12:
            lines.append(f"- … and {len(grouped[why])-12} more")
        lines.append("")
    PLAN.write_text("\n".join(lines), encoding="utf8")

    print(f"  {len(rows)} move, {len(stays)} stay")
    for d in sorted(by_dest):
        n, b = by_dest[d]
        print(f"    {d:<28} {n:3d} files {b/2**20:8.0f} MB"
              f"{'' if (DERIV / d).exists() else '   (new dir)'}")
    print(f"wrote {LEDGER}\nwrote {PLAN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
