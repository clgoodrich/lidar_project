"""Archive notebooks/wellsight by the two-month rule.

RULE (user, 2026-08-12): run in the past two months -> keep. Otherwise archive.
Cutoff is 2026-06-12. Evidence is `docs/analysis_log.md` via
tools/script_last_used.py, matched on FULL PATH where the log gives one.

THREE GUARDS, none of which override the rule -- they only stop it archiving
something that is still load-bearing:

  G1 IMPORTED FROM OUTSIDE v1. `tests/preprocessing/test_cornrow_filter.py`
     imports `notebooks.wellsight.preprocessing.cornrow_filter`. Archiving it
     breaks the test suite. Test runs are not written to the analysis log, so
     the log can never show this file as "run" no matter how often pytest
     executes it. Absence of evidence, not evidence of absence.
  G2 DEPENDENCY CLOSURE. Anything a kept file imports is kept, transitively.
     Archiving a library out from under a script that survives the rule would
     break the script the rule just protected.
  G3 AMBIGUOUS BASENAMES stay archivable. 13 v1 files share a basename with a
     v2 file, so a bare mention in the log cannot be attributed. All 13 have a
     live v2 twin, so the mention almost certainly refers to v2 and the v1 copy
     has no evidence of its own. Recorded explicitly rather than assumed.

Everything is MOVED to data/99_archive/superseded/notebooks_wellsight/, never
deleted, and the directory structure is preserved so an un-archive is a
straight reversal.

Outputs:
    docs/v1_archive_moves.csv    ledger for tools/apply_moves.py
    docs/v1_archive_plan.md      what stays, what goes, and why

Reproduce:
  python tools/plan_v1_archive.py
  ... --cutoff 2026-06-12
"""
from __future__ import annotations

import argparse
import ast
import csv
import sys
from collections import deque
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "notebooks" / "wellsight"
USED = ROOT / "docs" / "script_last_used.csv"
LEDGER = ROOT / "docs" / "v1_archive_moves.csv"
PLAN = ROOT / "docs" / "v1_archive_plan.md"
DEST = "data/99_archive/superseded/notebooks_wellsight"


def v1_files() -> list[Path]:
    return sorted(p for p in V1.rglob("*.py") if "__pycache__" not in p.parts)


def imports_of(p: Path, stems: dict[str, Path]) -> set[Path]:
    """v1 modules this file imports, resolved within the v1 tree.

    Relative imports matter here: `preprocessing/__init__.py` does
    `from .dem_idw_builder import build_dem_idw`, and archiving that submodule
    breaks the package for everyone importing through it.
    """
    try:
        t = ast.parse(p.read_text(encoding="utf8", errors="replace"))
    except SyntaxError:
        return set()
    out = set()
    for n in ast.walk(t):
        mods = []
        if isinstance(n, ast.ImportFrom):
            if n.level:                                  # from .x import y
                base = p.parent
                for _ in range(n.level - 1):
                    base = base.parent
                if n.module:
                    c = base / (n.module.split(".")[-1] + ".py")
                    if c.is_file():
                        out.add(c)
                for a in n.names:                        # from . import x
                    c = base / (a.name + ".py")
                    if c.is_file():
                        out.add(c)
                continue
            if n.module:
                mods = [n.module.split(".")[-1], n.module.split(".")[0]]
        elif isinstance(n, ast.Import):
            for a in n.names:
                mods += [a.name.split(".")[-1], a.name.split(".")[0]]
        for m in mods:
            q = stems.get(m)
            if q and q != p:
                out.add(q)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", default="2026-06-12")
    a = ap.parse_args()
    cut = date(*map(int, a.cutoff.split("-")))

    files = v1_files()
    stems = {p.stem: p for p in files}
    used = {r["path"]: r for r in csv.DictReader(open(USED, encoding="utf8"))}

    # --- the rule -----------------------------------------------------------
    keep: set[Path] = set()
    why: dict[Path, str] = {}
    for p in files:
        r = used.get(p.relative_to(ROOT).as_posix(), {})
        lr = r.get("last_run") or ""
        if lr and date(*map(int, lr.split("-"))) >= cut:
            keep.add(p)
            why[p] = f"run {lr} (within two months)"

    # --- G1: imported from outside v1 --------------------------------------
    outside = [p for t in ("tests", "ui", "roads_studio", "tools",
                           "notebooks/wellsight_v2")
               for p in (ROOT / t).rglob("*.py")
               if "__pycache__" not in p.parts]
    # An IMPORT, verified by AST -- not a path string. v2 docstrings still carry
    # stale `python notebooks/wellsight/build/x.py` CLI examples from before the
    # v2 split, and treating those as imports kept 20 v1 files that nothing
    # actually depends on.
    dotted_of = {"notebooks.wellsight." +
                 q.relative_to(V1).with_suffix("").as_posix().replace("/", "."): q
                 for q in files}
    for p in outside:
        try:
            t = ast.parse(p.read_text(encoding="utf8", errors="replace"))
        except SyntaxError:
            continue
        mods = []
        for n in ast.walk(t):
            if isinstance(n, ast.ImportFrom) and n.module and not n.level:
                mods.append(n.module)
            elif isinstance(n, ast.Import):
                mods += [x.name for x in n.names]
        for m in mods:
            if not m.startswith("notebooks.wellsight.") or \
                    m.startswith("notebooks.wellsight_v2"):
                continue
            for d, q in dotted_of.items():
                if m == d or m.startswith(d + "."):
                    if q not in keep:
                        keep.add(q)
                        why[q] = ("imported from outside v1 by "
                                  f"{p.relative_to(ROOT).as_posix()}")
            # `from notebooks.wellsight.preprocessing import X` targets a package
            pkg = ROOT / Path(m.replace(".", "/"))
            if (pkg / "__init__.py").is_file():
                for q in files:
                    if q.parent == pkg and q not in keep:
                        keep.add(q)
                        why[q] = ("in package imported from outside v1 by "
                                  f"{p.relative_to(ROOT).as_posix()}")

    # --- G2: dependency closure --------------------------------------------
    dq = deque(keep)
    while dq:
        cur = dq.popleft()
        for dep in imports_of(cur, stems):
            if dep not in keep:
                keep.add(dep)
                why[dep] = f"imported by kept {cur.relative_to(V1).as_posix()}"
                dq.append(dep)

    # G4: package integrity. A kept module needs its package markers, or
    # `from notebooks.wellsight.preprocessing.cornrow_filter import ...` stops
    # resolving the moment __init__.py is archived out from under it.
    for p in list(keep):
        d = p.parent
        while V1 in d.parents or d == V1:
            ini = d / "__init__.py"
            if ini.is_file() and ini not in keep:
                keep.add(ini)
                why[ini] = f"package marker for kept {p.relative_to(V1).as_posix()}"
            if d == V1:
                break
            d = d.parent

    # Re-close over dependencies. G4 added __init__.py files AFTER the first
    # closure, so their own imports were never walked -- which archived
    # dem_idw_builder.py out from under preprocessing/__init__.py and broke the
    # test suite's import. Caught by running the import before and after.
    dq = deque(keep)
    while dq:
        cur = dq.popleft()
        for dep in imports_of(cur, stems):
            if dep not in keep:
                keep.add(dep)
                why[dep] = f"imported by kept {cur.relative_to(V1).as_posix()}"
                dq.append(dep)

    archive = [p for p in files if p not in keep]

    rows = [dict(old_path=p.relative_to(ROOT).as_posix(),
                 new_path=f"{DEST}/{p.relative_to(V1).as_posix()}",
                 phase="v1_archive",
                 reason=(f"no analysis_log run on/after {a.cutoff}"))
            for p in archive]
    with open(LEDGER, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["old_path", "new_path", "phase", "reason"])
        w.writeheader(); w.writerows(rows)

    L = ["# v1 archive plan — the two-month rule", "",
         f"Rule: run on or after **{a.cutoff}** -> keep, else archive. Evidence "
         "is `docs/analysis_log.md`. Nothing is deleted; everything moves to "
         f"`{DEST}/` with structure preserved.", "",
         f"**{len(keep)} stay, {len(archive)} archive** of {len(files)}.", "",
         "## Staying, and why", "",
         "| Script | Reason |", "|---|---|"]
    for p in sorted(keep):
        L.append(f"| `{p.relative_to(V1).as_posix()}` | {why[p]} |")
    L += ["", "## Archiving", "",
          "No `analysis_log.md` entry on or after the cutoff, and nothing "
          "outside v1 imports them.", ""]
    for p in sorted(archive):
        r = used.get(p.relative_to(ROOT).as_posix(), {})
        lr = r.get("last_run") or "never in log"
        L.append(f"- `{p.relative_to(V1).as_posix()}` — last run {lr}")
    PLAN.write_text("\n".join(L) + "\n", encoding="utf8")

    print(f"{len(files)} v1 scripts: {len(keep)} keep, {len(archive)} archive")
    print("\nkeeping:")
    for p in sorted(keep):
        print(f"  {p.relative_to(V1).as_posix():<44} {why[p]}")
    print(f"\nwrote {LEDGER}\nwrote {PLAN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
