"""Rewrite hardcoded directory chains into ``path_for()`` calls.

The companion to ``tools/verify_no_path_literals.py`` (Gate E). That tool finds
the sites; this one fixes them.

    DERIV / "tiles" / "data_3x3"                 ->  path_for("data_3x3")
    ROOT / "data" / "source_laz" / "westernpa"   ->  path_for("source") / "westernpa"
    DERIV / "annotations" / "annotations_proj.gpkg"
                                                 ->  path_for("truth") / "annotations_proj.gpkg"

WHY THIS IS SAFE
----------------
The substitution is an identity BY CONSTRUCTION, not by inspection.
``path_for(k)`` returns ``ROOT / PATHS[k]``. A rewrite is only emitted when the
literal prefix it replaces is **string-equal** to ``PATHS[k]``. If it is not,
the site is skipped and reported. So a converted expression resolves to the same
path as the original, today, before anything moves.

What changes is what happens *tomorrow*: after Phase 4D edits one value in
``config/paths.toml``, the converted expression follows and the literal would
not have.

WHAT IT WILL NOT TOUCH
----------------------
* ``tools/`` -- the reorganization tooling performs the moves and must know the
  real layout. Exempt by design, not by oversight.
* Any chain whose prefix does not exactly match a configured value.
* Non-literal segments, which are carried through verbatim from the source.

USAGE
-----
    python tools/convert_path_literals.py                 # dry run, prints a diff
    python tools/convert_path_literals.py --execute       # rewrite in place
    python tools/convert_path_literals.py --only s5_eval  # limit by path substring

Every rewritten file is compiled before it is written. A file that fails to
compile is left untouched and reported.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_no_path_literals import (                    # noqa: E402
    PATH_ROOTS, ROOT_PREFIX, chain_segments, configured_keys, looks_like_file,
)

SCAN_DIRS = ("notebooks/wellsight_v2", "ui", "roads_studio")
IMPORT_MARKERS = ("from _common import", "from wellsight_v2._common import")


def operands(node: ast.AST) -> tuple[str, list[ast.AST]]:
    """Unwind a ``/`` chain into its root name and its right-hand operands."""
    ops: list[ast.AST] = []
    cur = node
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Div):
        ops.append(cur.right)
        cur = cur.left
    return (cur.id if isinstance(cur, ast.Name) else ""), list(reversed(ops))


def plan_file(path: Path, keys: dict[str, str], src: str) -> list[tuple[ast.AST, str]]:
    """Return ``(node, replacement_source)`` for every convertible chain."""
    tree = ast.parse(src)
    inner = {id(n.left) for n in ast.walk(tree)
             if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)}
    out: list[tuple[ast.AST, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        if id(node) in inner:
            continue
        got = chain_segments(node)
        if got is None:
            continue
        root, segs = got
        if not segs or segs[0] == "<expr>" or looks_like_file(segs[0]):
            continue
        _, ops = operands(node)
        prefix = ROOT_PREFIX.get(root)
        if prefix is None:
            continue
        # Longest literal prefix that is string-equal to a configured value.
        best = None
        for i in range(len(segs), 0, -1):
            if segs[i - 1] == "<expr>":
                continue
            cand = "/".join(filter(None, [prefix, *segs[:i]]))
            if cand in keys:
                best = (keys[cand], i)
                break
        if best is None:
            continue
        key, cut = best
        parts = [f'path_for("{key}")']
        for op in ops[cut:]:
            seg = ast.get_source_segment(src, op)
            parts.append(seg if seg is not None else ast.unparse(op))
        out.append((node, " / ".join(parts)))
    return out


def apply(src: str, plan: list[tuple[ast.AST, str]]) -> str:
    """Replace each node's exact source span, last-first so offsets hold."""
    lines = src.splitlines(keepends=True)
    starts = [0]
    for ln in lines:
        starts.append(starts[-1] + len(ln))

    def off(lineno: int, col: int) -> int:
        # col_offset is a UTF-8 byte offset; these files are ASCII in the
        # regions we touch, so a character offset is equivalent.
        return starts[lineno - 1] + col

    spans = sorted(
        ((off(n.lineno, n.col_offset), off(n.end_lineno, n.end_col_offset), rep)
         for n, rep in plan),
        reverse=True,
    )
    for a, b, rep in spans:
        src = src[:a] + rep + src[b:]
    return src


def ensure_import(src: str, rel: str) -> tuple[str, bool]:
    """Make ``path_for`` available, extending an import or bootstrapping one.

    Two cases. Most scripts already do ``from _common import DERIV, ...`` and
    only need the name added. Seventeen self-roll ``ROOT = Path(__file__)...``
    and never import ``_common`` at all; those get the two-line bootstrap that
    every other script in the tree already uses.
    """
    lines = src.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if any(ln.startswith(m) for m in IMPORT_MARKERS):
            if "path_for" in ln:
                return src, False
            head, _, tail = ln.rstrip("\n").partition("import ")
            comment = ""
            if "  #" in tail:
                tail, _, c = tail.partition("  #")
                comment = "  #" + c
            names = [n.strip() for n in tail.split(",") if n.strip()]
            names.append("path_for")
            lines[i] = f"{head}import " + ", ".join(names) + comment + "\n"
            return "".join(lines), True

    # No _common import. Only bootstrap for scripts one level below
    # notebooks/wellsight_v2/, where parents[1] is the package directory.
    parts = rel.split("/")
    if not (len(parts) == 4 and parts[0] == "notebooks" and parts[1] == "wellsight_v2"):
        return src, False

    anchor = next((i for i, ln in enumerate(lines)
                   if ln.startswith("ROOT = Path(__file__)")), None)
    if anchor is None:
        return src, False

    boot = []
    if not any(ln.startswith("import sys") for ln in lines):
        boot.append("import sys\n")
    boot += [
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n",
        "from _common import path_for  # noqa: E402\n",
        "\n",
    ]
    lines[anchor:anchor] = boot
    return "".join(lines), True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    keys = configured_keys()
    changed = skipped = sites = 0
    failed: list[str] = []

    for d in SCAN_DIRS:
        for p in sorted((ROOT / d).rglob("*.py")):
            rel = p.relative_to(ROOT).as_posix()
            if args.only and args.only not in rel:
                continue
            src = p.read_text("utf8", errors="ignore")
            try:
                plan = plan_file(p, keys, src)
            except SyntaxError:
                continue
            if not plan:
                continue
            new = apply(src, plan)
            new, added = ensure_import(new, rel)
            if "path_for" not in new.split("\n\n")[0] and not added:
                # No _common import line to extend -- leave it for a human.
                skipped += len(plan)
                failed.append(f"{rel}: no `from _common import` line to extend")
                continue
            try:
                compile(new, rel, "exec")
            except SyntaxError as e:
                skipped += len(plan)
                failed.append(f"{rel}: rewrite did not compile -- {e}")
                continue
            sites += len(plan)
            changed += 1
            print(f"{rel}  ({len(plan)} sites{', +import' if added else ''})")
            for n, rep in plan[:3]:
                old = ast.get_source_segment(src, n)
                print(f"    - {old}\n    + {rep}")
            if args.execute:
                p.write_text(new, "utf8")

    print(f"\n{sites} sites in {changed} files"
          f"{' REWRITTEN' if args.execute else ' (dry run)'}")
    if failed:
        print(f"\n{len(failed)} files skipped, {skipped} sites left:")
        for f in failed:
            print(f"  {f}")
    if not args.execute:
        print("\nRe-run with --execute to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
