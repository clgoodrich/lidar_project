"""Second pass: give each figure script a 1 m directory constant to match.

WHY A SECOND PASS
-----------------
_repoint_figures_to_1m.py rewrote the FILENAMES, from `*_9t_05.tif` to
`*_9t_1m.tif`. That is only half the job, because most of these scripts build a
path from a directory constant and a filename:

    D05 = ROOT / "data" / "9t" / "derived" / "05"
    HILL = D05 / "hillshade_9t_1m.tif"          <- points into the wrong folder

Flipping D05 wholesale to the 1 m folder is wrong for several of them, because
the same constant also carries things that only exist at 0.5 m:

    _build_road_chunking      road_chunks_9t.gpkg
    _build_split_and_undecided pit_blocks_9t.gpkg, pit_dataset_manifest.csv
    _build_v6_figures          pit_blocks_9t.gpkg
    _build_derivative_panel    rgb3_9t_05.tif

Those are split bookkeeping and model inputs, not terrain, and they were never
rebuilt at 1 m.

So: add a sibling constant next to the existing one, and repoint only the
usages whose filename now ends `_1m.tif`. Everything else keeps resolving to
0.5 m, which is correct.

Idempotent: a script that already has the sibling constant is left alone.

Run:
    python docs/presentation/figures_30to45min/_repoint_dir_constants_to_1m.py [--apply]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIGDIR = ROOT / "docs/presentation/figures_30to45min"

#: `NAME = ROOT / "data" / "9t" / "derived" / "05"`  (segment form)
SEG = re.compile(
    r'^(\s*)([A-Z_][A-Z0-9_]*)\s*=\s*(ROOT\s*/\s*"data"\s*/\s*"([a-z0-9]+)"'
    r'\s*/\s*"derived"\s*/\s*)"05"\s*$', re.M)
#: `NAME = ROOT / "data/9t/derived/05"`  (single-string form)
STR = re.compile(
    r'^(\s*)([A-Z_][A-Z0-9_]*)\s*=\s*(ROOT\s*/\s*"data/([a-z0-9]+)/derived/)05"\s*$',
    re.M)


def main() -> int:
    apply = "--apply" in sys.argv
    total = 0

    for f in sorted(FIGDIR.glob("_*.py")):
        if f.name.startswith("_repoint_"):
            continue
        src = f.read_text(encoding="utf-8")
        out = src
        added = []

        for rx, close in ((SEG, '"1m"'), (STR, '1m"')):
            for m in list(rx.finditer(out)):
                indent, var, prefix, area = m.groups()
                sib = f"{var}_1M"
                if re.search(rf"\b{sib}\s*=", out):
                    continue
                # only worth adding if something actually needs it
                if not re.search(rf"\b{var}\s*/\s*f?\"[a-z0-9_]+_1m\.tif\"", out):
                    continue
                decl = (f"{m.group(0)}\n{indent}#: terrain layers moved to the "
                        f"1 m stack; {var} still holds the 0.5 m split\n"
                        f"{indent}#: bookkeeping and model inputs, which have no "
                        f"1 m twin\n"
                        f"{indent}{sib} = {prefix}{close}")
                out = out.replace(m.group(0), decl, 1)
                # repoint only the 1 m filenames through the new constant
                out = re.sub(rf"\b{var}(\s*/\s*f?\"[a-z0-9_{{}}]*_1m\.tif\")",
                             rf"{sib}\1", out)
                added.append(f"{var} -> {sib} ({area})")

        if out != src:
            total += 1
            print(f"  {f.name}: {', '.join(added)}")
            if apply:
                f.write_text(out, encoding="utf-8")

    print(f"\n  {total} script(s) {'updated' if apply else 'would change'}")
    if not apply:
        print("  re-run with --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
