"""Which .py files are actually dead, and which just look quiet?

"Unused" is not one question. A library module and a hand-run CLI script fail
differently, so they are judged differently.

    LIBRARY      no `if __name__ == "__main__"` guard. Its only purpose is to
                 be imported. Zero importers means definitively dead.
    ENTRY POINT  has the guard. Meant to be run by hand. Zero importers proves
                 nothing -- you run it from a terminal, not from code.

For an entry point, three independent signals are gathered instead:

  1. MENTIONED   its filename appears in a doc, a .bat, ui/registry.py,
                 roads_studio, or another script's docstring / subprocess call
  2. IMPORTED    another live script imports from it
  3. RAN         at least one of the output paths it declares at module level
                 exists on disk -- proof it executed at least once

An entry point with none of the three is a DEAD candidate. With any of them it
is LIVE. "Ran once but nobody mentions it" is reported separately as ORPHAN
OUTPUT, because that is the interesting middle case: it worked, it produced
something the project may still depend on, and nothing points at it.

DIRECTION OF ERROR
Deliberately conservative. Nothing is moved or deleted by this tool. A false
"dead" here would be a real loss, so anything ambiguous is reported as such
rather than binned.

Outputs:
    docs/unused_scripts_report.md

Reproduce:
  python tools/find_unused_scripts.py
  ... --tree notebooks/wellsight_v2   limit to one tree
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "unused_scripts_report.md"
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
LIVE_TREES = ["notebooks/wellsight_v2", "ui", "roads_studio", "tools", "tests"]
TEXT_EXT = {".py", ".md", ".bat", ".json", ".txt", ".ipynb", ".ps1", ".cfg",
            ".toml", ".yml", ".yaml"}

# Files that mention every script by construction. Counting them as evidence
# makes everything look referenced, which is worse than useless.
GENERATED = re.compile(
    r"(reference_index|unused_scripts_report|duplicates_report|"
    r"duplicates_proposed_moves|verify_paths_report|verify_backup_report|"
    r"MOVES\.csv|phase\d?\w*_.*\.(csv|md))")

# Framework entry points. No __main__ guard by design: streamlit runs app.py,
# pytest discovers conftest.py and test_*.py, and __init__.py is package
# machinery. Judging them as libraries produces confident nonsense.
FRAMEWORK = re.compile(
    r"(^|/)(__init__\.py|conftest\.py|test_[^/]+\.py|app\.py)$"
    # Streamlit multipage: anything under a pages/ directory is auto-discovered
    r"|(^|/)pages/[^/]+\.py$"
    # `python -m pkg.main` never contains the string "main.py"
    r"|(^|/)main\.py$")

SEED = {
    "ROOT": ROOT,
    "DERIV": ROOT / "data" / "derivatives",
    "DERIV_9T": ROOT / "data" / "derivatives" / "tiles" / "9t",
    "D": ROOT / "data" / "derivatives" / "tiles" / "9t",
}


def py_files(trees) -> list[Path]:
    out = []
    for t in trees:
        base = ROOT / t
        if base.exists():
            out += [p for p in base.rglob("*.py")
                    if not any(s in p.parts for s in SKIP_DIRS)]
    return sorted(out)


def has_main_guard(src: str) -> bool:
    return bool(re.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', src))


def local_imports(tree: ast.AST, known: set[str]) -> set[str]:
    """Module names imported that correspond to another .py in the project."""
    got = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            m = n.module.split(".")[0]
            if m in known:
                got.add(m)
        elif isinstance(n, ast.Import):
            for a in n.names:
                m = a.name.split(".")[0]
                if m in known:
                    got.add(m)
    return got


def fold(node, syms):
    if isinstance(node, ast.Name):
        return syms.get(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        l, r = fold(node.left, syms), fold(node.right, syms)
        if isinstance(l, Path) and isinstance(r, str):
            return l / r
    return None


def declared_paths(tree: ast.AST) -> list[Path]:
    syms = dict(SEED)
    out = []
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            v = fold(n.value, syms)
            if isinstance(v, Path):
                syms[n.targets[0].id] = v
                out.append(v)
    return out


def read_any(p: Path) -> str:
    try:
        if p.suffix.lower() == ".ipynb":
            import json
            nb = json.loads(p.read_text(encoding="utf8", errors="replace"))
            return "\n".join("".join(c.get("source", "")) if isinstance(
                c.get("source"), list) else str(c.get("source", ""))
                for c in nb.get("cells", []))
        return p.read_text(encoding="utf8", errors="replace")
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", nargs="*", default=LIVE_TREES)
    a = ap.parse_args()

    scripts = py_files(a.tree)
    known = {p.stem for p in scripts}
    print(f"{len(scripts)} scripts in {', '.join(a.tree)}")

    # --- signal 2: import graph -------------------------------------------
    imported_by = defaultdict(set)
    info = {}
    for p in scripts:
        src = read_any(p)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            info[p] = dict(guard=True, paths=[], err=True)
            continue
        info[p] = dict(guard=has_main_guard(src), paths=declared_paths(tree),
                       err=False)
        for m in local_imports(tree, known):
            imported_by[m].add(p.relative_to(ROOT).as_posix())

    # --- signal 1: mentioned anywhere -------------------------------------
    mentioned = defaultdict(set)
    corpus = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(s in p.parts for s in SKIP_DIRS):
            continue
        if p.suffix.lower() in TEXT_EXT:
            corpus.append(p)
        elif p.suffix.lower() == ".qgz":
            corpus.append(p)
    names = {p.name: p for p in scripts}
    for c in corpus:
        if GENERATED.search(c.name) or c.name == "find_unused_scripts.py":
            continue
        if c.suffix.lower() == ".qgz":
            try:
                z = zipfile.ZipFile(c)
                txt = "".join(z.read(n).decode("utf8", "replace")
                              for n in z.namelist() if n.endswith(".qgs"))
            except Exception:
                continue
        else:
            txt = read_any(c)
        for nm in names:
            if nm in txt:
                rel = c.relative_to(ROOT).as_posix()
                if rel != names[nm].relative_to(ROOT).as_posix():
                    mentioned[nm].add(rel)

    # --- classify ----------------------------------------------------------
    dead, orphan, live, libs_dead = [], [], [], []
    for p in scripts:
        rel = p.relative_to(ROOT).as_posix()
        i = info[p]
        imps = imported_by.get(p.stem, set())
        ment = {m for m in mentioned.get(p.name, set())
                if not m.startswith("docs/unused_scripts_report")}
        ran = [q for q in i["paths"] if q.exists() and q != ROOT]
        if FRAMEWORK.search(rel):
            live.append((rel, imps, ment or {"framework entry point"}, ran))
            continue
        if not i["guard"]:
            # a library is judged on importers, but a mention in a doc or a
            # launcher still counts -- it may be invoked as `python -m pkg.mod`
            (live if (imps or ment) else libs_dead).append((rel, imps, ment, ran))
            continue
        if imps or ment:
            live.append((rel, imps, ment, ran))
        elif ran:
            orphan.append((rel, imps, ment, ran))
        else:
            dead.append((rel, imps, ment, ran))

    L = ["# Which scripts are actually used?", "",
         f"`tools/find_unused_scripts.py` over {len(scripts)} files in "
         f"`{'`, `'.join(a.tree)}`.", "",
         "Libraries and entry points are judged differently. A library exists "
         "to be imported, so zero importers means dead. An entry point is run "
         "by hand, so zero importers means nothing -- it is judged on whether "
         "anything *mentions* it and whether its declared outputs exist on "
         "disk.", "",
         "| Verdict | Count |", "|---|---:|",
         f"| LIVE | {len(live)} |",
         f"| ORPHAN OUTPUT (ran, but nothing points at it) | {len(orphan)} |",
         f"| DEAD library (no importers) | {len(libs_dead)} |",
         f"| DEAD candidate (no mention, no importer, no output) | {len(dead)} |",
         ""]

    def block(title, rows, note):
        L.append(f"## {title}")
        L.append("")
        L.append(note)
        L.append("")
        if not rows:
            L.append("_none_")
            L.append("")
            return
        for rel, imps, ment, ran in sorted(rows):
            L.append(f"### `{rel}`")
            if imps:
                L.append(f"- imported by: {', '.join(sorted(imps)[:4])}")
            if ment:
                L.append(f"- mentioned in: {', '.join(sorted(ment)[:4])}"
                         + (f" (+{len(ment)-4})" if len(ment) > 4 else ""))
            if ran:
                L.append(f"- outputs exist: "
                         f"`{ran[0].relative_to(ROOT).as_posix()}`"
                         + (f" (+{len(ran)-1} more)" if len(ran) > 1 else ""))
            L.append("")

    block("DEAD candidates", dead,
          "Nothing mentions these, nothing imports them, and none of the "
          "output paths they declare exist. Strongest evidence available that "
          "they never ran. Still not deleted -- review before archiving.")
    block("DEAD libraries", libs_dead,
          "No `__main__` guard, so they exist only to be imported, and nobody "
          "imports them.")
    block("ORPHAN OUTPUT", orphan,
          "These ran at least once -- their outputs are on disk -- but no doc, "
          "script or launcher points at them. Either undocumented one-offs, or "
          "steps someone still runs from memory. Do NOT archive without asking.")

    L.append("## LIVE")
    L.append("")
    for rel, imps, ment, ran in sorted(live):
        why = []
        if imps:
            why.append(f"imported by {len(imps)}")
        if ment:
            why.append(f"mentioned in {len(ment)}")
        L.append(f"- `{rel}` — {', '.join(why) or 'library, imported'}")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf8")

    print(f"  LIVE                {len(live)}")
    print(f"  ORPHAN OUTPUT       {len(orphan)}")
    print(f"  DEAD library        {len(libs_dead)}")
    print(f"  DEAD candidate      {len(dead)}")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
