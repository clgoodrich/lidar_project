"""What code is actually used? A dependency graph, not a heuristic.

Replaces tools/find_unused_scripts.py, which was wrong at the foundation: it
resolved imports by matching module names to FILE STEMS. 39 module names exist
in both notebooks/wellsight and notebooks/wellsight_v2, so a v2 script importing
`_common` appeared to possibly depend on v1's `_common`. The v1 tree therefore
looked "58 LIVE" when almost all of those edges were internal to a tree nothing
outside points at.

HOW IMPORTS ACTUALLY WORK HERE
This project does not use packages. 167 scripts do:

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import DERIV

So resolving an edge requires knowing which DIRECTORY that insert added. This
module folds those expressions -- `Path(__file__).resolve().parents[N]`,
`ROOT / "a" / "b"`, and `/` chains on either -- into real directories, in
insertion order, then resolves each import against them. A file's own directory
is searched too, as Python does for scripts. Dotted repo-rooted imports
(`from notebooks.wellsight.preprocessing.cornrow_filter import ...`, the style
the tests use) are resolved from the repository root.

ROOTS -- a script is an entry point if ANY of these hold
    R1 invoked in a .bat                     (python x.py, or python -m pkg.mod)
    R2 listed in ui/registry.py              the UI's job registry
    R3 has "Reproduce:" in its docstring     this repo's own run-me convention
    R4 pytest-discovered                     tests/**/test_*.py, conftest.py
    R5 streamlit-discovered                  ui/app.py, ui/pages/*.py
    R6 invoked as a command in docs/**/*.md  "python notebooks/.../x.py"
    R7 launched via subprocess by another script

REACHABLE = breadth-first from the roots along import edges.

THREE SIGNALS KEPT SEPARATE FROM REACHABILITY
    EXECUTED  at least one module-level Path constant it declares exists on
              disk -- evidence it ran at least once
    CITED     named in docs/iterations/*.md or LEADERBOARD.md -- it may never
              run again and still be load-bearing for reproducibility
    TWIN      a file of the same name exists in wellsight_v2 (only meaningful
              for v1 files)

VERDICTS
    ACTIVE        reachable from a root
    HISTORICAL    not reachable, but executed AND cited. Keep. A script that
                  produced a leaderboard number is not dead just because it
                  will never run again.
    ORPHAN        not reachable, executed, not cited. It worked and nothing
                  documents it. Ask before touching.
    SUPERSEDED    not reachable, never executed, has a v2 twin. Archive
                  candidate.
    UNREFERENCED  not reachable, never executed, no twin. Investigate one by
                  one; this bucket should be small enough to read.

THIS TOOL MOVES NOTHING. It writes a report.

Outputs:
    docs/script_usage_audit.md
    docs/script_usage_audit.csv

Reproduce:
  python tools/audit_script_usage.py
"""
from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "script_usage_audit.md"
CSVOUT = ROOT / "docs" / "script_usage_audit.csv"
SKIP = {".git", ".venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
TREES = ["notebooks", "ui", "roads_studio", "tools", "tests"]

SEED_NAMES = {"ROOT": ROOT}
CITE_GLOBS = ["docs/iterations/*.md", "docs/iterations/LEADERBOARD.md",
              "docs/analysis_log.md", "docs/ROADMAP.md"]


# --------------------------------------------------------------- path folding
def fold(node, file_path: Path, syms: dict):
    """Resolve an ast node to a Path where possible, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return syms.get(node.id)
    # Path(__file__).resolve().parents[N]
    if isinstance(node, ast.Subscript):
        val = node.value
        if isinstance(val, ast.Attribute) and val.attr == "parents":
            idx = node.slice
            if isinstance(idx, ast.Constant) and isinstance(idx.value, int):
                try:
                    return file_path.resolve().parents[idx.value]
                except IndexError:
                    return None
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        l = fold(node.left, file_path, syms)
        r = fold(node.right, file_path, syms)
        if isinstance(l, Path) and isinstance(r, str):
            return l / r
        return None
    if isinstance(node, ast.Call):
        f = node.func
        nm = getattr(f, "id", None) or getattr(f, "attr", None)
        if nm in ("str", "resolve", "Path") and node.args:
            return fold(node.args[0], file_path, syms)
        if nm == "resolve" and isinstance(f, ast.Attribute):
            return fold(f.value, file_path, syms)
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        base = fold(node.value, file_path, syms)
        return base.parent if isinstance(base, Path) else None
    return None


def syspath_dirs(tree: ast.AST, file_path: Path) -> list[Path]:
    """Directories this file adds to sys.path, in insertion order."""
    syms = dict(SEED_NAMES)
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            v = fold(n.value, file_path, syms)
            if isinstance(v, Path):
                syms[n.targets[0].id] = v
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in ("insert", "append") \
                    and isinstance(f.value, ast.Attribute) \
                    and f.value.attr == "path":
                for arg in n.args:
                    v = fold(arg, file_path, syms)
                    if isinstance(v, Path) and v.is_dir():
                        out.append(v)
                # sys.path[:0] = [a, b] form
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute) \
                        and t.value.attr == "path":
                    if isinstance(n.value, (ast.List, ast.Tuple)):
                        for e in n.value.elts:
                            v = fold(e, file_path, syms)
                            if isinstance(v, Path) and v.is_dir():
                                out.append(v)
    return out


def module_targets(tree: ast.AST) -> tuple[list[str], list[tuple[int, str]]]:
    """(absolute module names, relative imports as (level, module)).

    roads_studio/ and ui/ are real packages using `from .core import ...`.
    Dropping level>0 nodes made roads_studio/core.py look unreferenced.
    """
    absolute, relative = [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            if n.level and n.level > 0:
                relative.append((n.level, n.module or ""))
                for a in n.names:                     # from . import core
                    if not n.module:
                        relative.append((n.level, a.name))
            elif n.module:
                absolute.append(n.module)
        elif isinstance(n, ast.Import):
            absolute += [a.name for a in n.names]
    return absolute, relative


def resolve_relative(level: int, mod: str, file_path: Path) -> Path | None:
    base = file_path.parent
    for _ in range(level - 1):
        base = base.parent
    if not mod:
        return None
    parts = mod.split(".")
    c = base.joinpath(*parts).with_suffix(".py")
    if c.is_file():
        return c
    c = base.joinpath(*parts) / "__init__.py"
    return c if c.is_file() else None


def resolve_module(mod: str, dirs: list[Path]) -> Path | None:
    """Find the .py a module name refers to, searching dirs in order."""
    parts = mod.split(".")
    # repo-root dotted form, e.g. notebooks.wellsight.preprocessing.cornrow_filter
    cand = ROOT.joinpath(*parts).with_suffix(".py")
    if cand.is_file():
        return cand
    cand = ROOT.joinpath(*parts) / "__init__.py"
    if cand.is_file():
        return cand
    for d in dirs:
        c = d.joinpath(*parts).with_suffix(".py")
        if c.is_file():
            return c
        c = d.joinpath(*parts) / "__init__.py"
        if c.is_file():
            return c
    return None


def declared_paths(tree: ast.AST, file_path: Path) -> list[Path]:
    syms = dict(SEED_NAMES)
    syms.update({
        "DERIV": ROOT / "data" / "derivatives",
        "DERIV_9T": ROOT / "data" / "derivatives" / "tiles" / "9t",
        "D": ROOT / "data" / "derivatives" / "tiles" / "9t",
    })
    out = []
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            v = fold(n.value, file_path, syms)
            if isinstance(v, Path):
                syms[n.targets[0].id] = v
                if v != ROOT and ROOT in v.parents:
                    out.append(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.parse_args()

    files = []
    for t in TREES:
        base = ROOT / t
        if base.exists():
            files += [p for p in base.rglob("*.py")
                      if not any(s in p.parts for s in SKIP)]
    files = sorted(set(files))
    rel = {p: p.relative_to(ROOT).as_posix() for p in files}
    print(f"{len(files)} python files")

    trees, edges, decl, subproc = {}, defaultdict(set), {}, defaultdict(set)
    for p in files:
        try:
            src = p.read_text(encoding="utf8", errors="replace")
            t = ast.parse(src)
        except SyntaxError:
            continue
        trees[p] = (t, src)
        dirs = [p.parent] + syspath_dirs(t, p)
        absmods, relmods = module_targets(t)
        for m in absmods:
            tgt = resolve_module(m, dirs)
            if tgt and tgt in rel and tgt != p:
                edges[p].add(tgt)
        for lvl, m in relmods:
            tgt = resolve_relative(lvl, m, p)
            if tgt and tgt in rel and tgt != p:
                edges[p].add(tgt)
        decl[p] = declared_paths(t, p)

    # --- subprocess / "runs this other script" edges ------------------------
    # 39 basenames exist in BOTH notebooks/wellsight and wellsight_v2, so a bare
    # filename cannot identify a file. Match on the relative PATH; fall back to
    # the bare name only when it is unique across the whole repository.
    name_count = Counter(p.name for p in files)

    def refers_to(text: str, q: Path) -> bool:
        rp = rel[q]
        if rp in text or rp.replace("/", "\\") in text:
            return True
        # a partial path is enough to disambiguate: ".../roads/_prep_road_1m.py"
        tail = "/".join(rp.split("/")[-2:])
        if tail in text or tail.replace("/", "\\") in text:
            return True
        return name_count[q.name] == 1 and q.name in text

    for p in files:
        if p not in trees:
            continue
        src = trees[p][1]
        for q in files:
            if q is not p and refers_to(src, q):
                subproc[p].add(q)

    # ---------------- roots ------------------------------------------------
    roots, why = set(), defaultdict(set)

    def add(p, tag):
        roots.add(p); why[p].add(tag)

    bat_text = "\n".join((ROOT / f).read_text(encoding="utf8", errors="replace")
                         for f in [x.name for x in ROOT.glob("*.bat")]
                         if (ROOT / f).is_file())
    bat_text += "\n".join(p.read_text(encoding="utf8", errors="replace")
                          for p in (ROOT / "tools").glob("*.bat"))
    reg = (ROOT / "ui" / "registry.py")
    reg_text = reg.read_text(encoding="utf8", errors="replace") if reg.is_file() else ""
    # A command in docs is NOT proof of current use. docs/analysis_log.md is an
    # append-only record of everything ever run, and docs/iterations/*.md are
    # reproducibility write-ups for finished experiments. Counting them as
    # entry points made the whole dead v1 tree look ACTIVE. They become a
    # CITED signal instead. Only docs describing the CURRENT workflow are roots.
    HISTORICAL_DOCS = re.compile(r"(analysis_log|/iterations/|BACKLOG|"
                                 r"script_usage_audit|unused_scripts_report)")
    doc_text = "\n".join(p.read_text(encoding="utf8", errors="replace")
                         for p in (ROOT / "docs").rglob("*.md")
                         if not HISTORICAL_DOCS.search(p.as_posix()))

    for p in files:
        r = rel[p]
        nm = p.name
        if refers_to(bat_text, p) or f"{p.parent.name}.{p.stem}" in bat_text:
            add(p, "R1 .bat")
        if refers_to(reg_text, p):
            add(p, "R2 ui/registry")
        t = trees.get(p)
        if t and "Reproduce:" in (ast.get_docstring(t[0]) or ""):
            add(p, "R3 Reproduce:")
        if r.startswith("tests/") and (nm.startswith("test_") or nm == "conftest.py"):
            add(p, "R4 pytest")
        if r in ("ui/app.py", "roads_studio/app.py") or "/pages/" in r:
            add(p, "R5 streamlit")

    # ---------------- reachability ----------------------------------------
    seen = set(roots)
    dq = deque(roots)
    while dq:
        cur = dq.popleft()
        for nxt in edges[cur] | subproc[cur]:
            if nxt not in seen:
                seen.add(nxt); dq.append(nxt)
                why[nxt].add(f"R7 via {rel[cur]}")

    # ---------------- signals ---------------------------------------------
    cite_text = ""
    for g in CITE_GLOBS:
        for p in ROOT.glob(g):
            cite_text += p.read_text(encoding="utf8", errors="replace")
    v2_names = {p.name for p in (ROOT / "notebooks" / "wellsight_v2").rglob("*.py")
                if "__pycache__" not in p.parts}

    # A doc MENTION is not an invocation. Being named in prose proves the script
    # existed, not that anything runs it. Earlier versions of this tool treated
    # doc mentions as entry points, which made the entire dead v1 tree look
    # ACTIVE. It is recorded as a signal and never as a root.
    def doc_command(p: Path) -> bool:
        """Does a CURRENT-workflow doc show this being run as a command?"""
        rp = rel[p]
        tail = "/".join(rp.split("/")[-2:])
        for pat in (re.escape(rp), re.escape(tail)):
            if re.search(rf"python[^\n]{{0,60}}{pat}", doc_text):
                return True
        return False

    rows = []
    for p in files:
        r = rel[p]
        executed = [q for q in decl.get(p, []) if q.exists()]
        cited = p.name in cite_text
        documented = doc_command(p)
        twin = r.startswith("notebooks/wellsight/") and p.name in v2_names
        reach = p in seen
        if reach:
            v = "ACTIVE"
        elif documented:
            v = "DOCUMENTED"          # a doc shows how to run it; no wiring
        elif executed and cited:
            v = "HISTORICAL"
        elif executed:
            v = "ORPHAN"
        elif twin:
            v = "SUPERSEDED"
        else:
            v = "UNREFERENCED"
        rows.append(dict(path=r, verdict=v,
                         why="; ".join(sorted(why[p]))[:120],
                         imports=len(edges[p]),
                         imported_by=sum(1 for q in files if p in edges[q]),
                         executed=len(executed), cited=int(cited),
                         documented=int(documented),
                         has_v2_twin=int(twin)))

    with open(CSVOUT, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    order = ["ACTIVE", "DOCUMENTED", "HISTORICAL", "ORPHAN", "SUPERSEDED", "UNREFERENCED"]
    counts = {k: sum(1 for x in rows if x["verdict"] == k) for k in order}
    L = ["# Script usage audit", "",
         "Import edges are resolved exactly: each file's `sys.path.insert` "
         "expressions are folded into real directories, then module names are "
         "resolved against them in order. 39 module names exist in both "
         "`notebooks/wellsight` and `notebooks/wellsight_v2`, so stem-matching "
         "produces a wrong graph. See the module docstring for the full "
         "methodology.", "",
         "**This audit moves nothing.**", "",
         "| Verdict | Count | Meaning |", "|---|---:|---|",
         f"| ACTIVE | {counts['ACTIVE']} | reachable from an entry point |",
         f"| HISTORICAL | {counts['HISTORICAL']} | ran, and cited in docs. Keep for reproducibility |",
         f"| ORPHAN | {counts['ORPHAN']} | ran, nothing documents it. Ask |",
         f"| SUPERSEDED | {counts['SUPERSEDED']} | never ran, has a v2 twin. Archive candidate |",
         f"| UNREFERENCED | {counts['UNREFERENCED']} | never ran, no twin. Investigate individually |",
         ""]
    for k in order[1:]:
        sub = [x for x in rows if x["verdict"] == k]
        L += [f"## {k} ({len(sub)})", ""]
        if not sub:
            L += ["_none_", ""]
            continue
        L += ["| Script | executed | cited | v2 twin |", "|---|---:|---:|---:|"]
        for x in sorted(sub, key=lambda z: z["path"]):
            L.append(f"| `{x['path']}` | {x['executed']} | "
                     f"{'yes' if x['cited'] else '-'} | "
                     f"{'yes' if x['has_v2_twin'] else '-'} |")
        L.append("")
    L += ["## ACTIVE — by tree", ""]
    bytree = defaultdict(int)
    for x in rows:
        if x["verdict"] == "ACTIVE":
            bytree["/".join(x["path"].split("/")[:2])] += 1
    for k, v in sorted(bytree.items(), key=lambda kv: -kv[1]):
        L.append(f"- `{k}` — {v}")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf8")

    for k in order:
        print(f"  {k:<14} {counts[k]}")
    print(f"wrote {REPORT}\nwrote {CSVOUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
