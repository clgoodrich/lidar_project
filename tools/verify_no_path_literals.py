"""Gate E -- no script may spell a project directory itself.

Every directory in this repository is a key in ``config/paths.toml``. Code asks
for one with ``path_for("truth")``. Nothing hardcodes ``ROOT / "data" /
"derivatives" / "annotations"``, because the moment it does, moving that
directory stops being a value change and becomes a hunt through 92 scripts.

That hunt is exactly what Phases 0-3 spent two sessions undoing. This gate stops
it coming back.

WHAT IS A VIOLATION
-------------------
A path expression rooted at ``ROOT`` (or ``DERIV`` / ``DERIV_9T``) whose FIRST
string segment names a directory rather than a file. ``ROOT / "data"`` is a
violation; ``path_for("data")`` is the fix.

WHAT IS NOT
-----------
* ``path_for("truth") / "roads.shp"`` -- a filename below a configured key is
  fine, and is how nearly all code should read.
* ``DERIV_9T / "features_pit_9t_1m.tif"`` -- ditto. The legacy constants are
  configured keys; it is only further *directory* nesting that hides a path.
* Anything under ``archive/``, ``data/99_archive/`` or ``notebooks/wellsight/``.
  Retired code is allowed to reference a world that no longer exists.
* A docstring or comment. Only real code counts, so the AST is walked rather
  than the text grepped.

USAGE
-----
    python tools/verify_no_path_literals.py            # report, exit 1 if any
    python tools/verify_no_path_literals.py --fix-hint # print the path_for() call
    python tools/verify_no_path_literals.py --baseline # rewrite the allow-list

Existing violations are recorded in ``docs/_ledgers/path_literals_baseline.json``
so the gate reports only NEW ones. A clean tree is the goal; a frozen tree is the
requirement.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "_ledgers" / "path_literals_baseline.json"
REPORT = ROOT / "docs" / "path_literals_report.md"

#: Roots that resolve into the project tree. A ``/`` chain off any of these is
#: a path expression.
PATH_ROOTS = {"ROOT", "DERIV", "DERIV_9T", "PROJECT_ROOT", "REPO_ROOT"}

#: Exempt, each for its own reason.
#:
#: ``tools/`` is the important one. These scripts PERFORM the moves -- they plan
#: ledgers, rewrite QGIS datasources, audit the tree and verify the gates. They
#: have to name real directories, because naming real directories is their job.
#: Holding the mover to a rule about not knowing where things are would be
#: circular. Exempt by design, not by oversight.
#:
#: The rest is retired code, allowed to reference a world that no longer exists.
EXEMPT_DIRS = ("archive", "data", ".venv", ".git", "__pycache__",
               "notebooks/wellsight/", "tests/fixtures", "tools")

#: Scanned. Anything else is not live pipeline code.
SCAN_DIRS = ("notebooks/wellsight_v2", "ui", "roads_studio")


def configured_keys() -> dict[str, str]:
    """``{relative_path: key}`` from config/paths.toml, or the _common fallback.

    Keyed by path so a literal chain can be matched back to the key that already
    names it -- which is what makes the suggestion actionable rather than generic.
    """
    try:
        import tomllib
        cfg = tomllib.loads((ROOT / "config" / "paths.toml").read_text("utf8"))
        paths = cfg.get("paths", {})
    except Exception:                                   # noqa: BLE001
        sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
        from _common import _DEFAULTS as paths          # type: ignore
    # Later keys win, so the first (least aliased) name for a path is kept.
    out: dict[str, str] = {}
    for k, v in paths.items():
        out.setdefault(v.strip("/"), k)
    return out


def is_exempt(p: Path) -> bool:
    rel = p.relative_to(ROOT).as_posix()
    return any(rel == d or rel.startswith(d.rstrip("/") + "/") for d in EXEMPT_DIRS)


def chain_segments(node: ast.AST) -> tuple[str, list[str]] | None:
    """Unwind ``ROOT / "a" / "b"`` into ``("ROOT", ["a", "b"])``.

    Returns None if the expression is not a ``/`` chain rooted at a known name.
    """
    segs: list[str] = []
    cur = node
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Div):
        right = cur.right
        if isinstance(right, ast.Constant) and isinstance(right.value, str):
            segs.append(right.value)
        else:
            segs.append("<expr>")
        cur = cur.left
    if isinstance(cur, ast.Name) and cur.id in PATH_ROOTS:
        return cur.id, list(reversed(segs))
    # A `.parent` climb off a configured root reaches a directory the config
    # does not name, then walks back down by literal. `DERIV_9T.parent.parent /
    # "annotations"` is `data/derivatives/annotations` spelled so the plain
    # chain check cannot see it. Found 2026-08-12 in _plat_unet.py and
    # _pit_unet_v2_infer.py, both reaching the ground truth this way.
    climb = 0
    while isinstance(cur, ast.Attribute) and cur.attr == "parent":
        climb += 1
        cur = cur.value
    if climb and isinstance(cur, ast.Name) and cur.id in PATH_ROOTS:
        return f"{cur.id}{'.parent' * climb}", list(reversed(segs))
    return None


def looks_like_file(seg: str) -> bool:
    """A segment with a suffix is a filename, which is always allowed.

    A segment containing a SLASH is not a filename, whatever else it looks like.
    ``ROOT / "data/derivatives/annotations/plat.shp"`` is a full directory path
    smuggled into one string literal; it slipped past the first version of this
    check because it ends in ``.shp``. Found 2026-08-12 in
    ``s7_analysis/_export_well_age_qgis.py``.
    """
    if "/" in seg or "\\" in seg:
        return False
    return "." in seg and not seg.startswith(".")


#: What each path root already resolves to, so a literal chain can be compared
#: against the configured values.
ROOT_PREFIX = {"ROOT": "", "PROJECT_ROOT": "", "REPO_ROOT": "",
               "DERIV": "data/derivatives", "DERIV_9T": "data/derivatives/tiles/9t",
               # `.parent` climbs, resolved so the chain below them can be matched
               "DERIV.parent": "data",
               "DERIV_9T.parent": "data/derivatives/tiles",
               "DERIV_9T.parent.parent": "data/derivatives",
               "DERIV_9T.parent.parent.parent": "data"}


def suggest(root: str, segs: list[str], keys: dict[str, str]) -> str:
    """Name the configured key that covers the longest prefix of this chain."""
    prefix = ROOT_PREFIX.get(root, "")
    best = None
    for i in range(len(segs), 0, -1):
        if segs[i - 1] == "<expr>":
            continue
        cand = "/".join(filter(None, [prefix, *segs[:i]]))
        if cand in keys:
            best = (keys[cand], segs[i:])
            break
    if best is None:
        head = "/".join(filter(None, [prefix, segs[0]]))
        return f'add "{head}" to config/paths.toml as a key, then path_for()'
    key, rest = best
    tail = "".join(f' / "{s}"' for s in rest if s != "<expr>")
    return f'path_for("{key}"){tail}'


def scan(path: Path, keys: dict[str, str]) -> list[dict]:
    try:
        tree = ast.parse(path.read_text("utf8", errors="ignore"))
    except SyntaxError:
        return []
    # A `/` chain nests left, so every prefix is itself a BinOp. Report only the
    # outermost one, or a single expression yields N near-identical findings.
    inner = {id(n.left) for n in ast.walk(tree)
             if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)}
    out: list[dict] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        if id(node) in inner:
            continue
        got = chain_segments(node)
        if got is None:
            continue
        root, segs = got
        if not segs or segs[0] == "<expr>":
            continue
        # A filename below a configured root is the intended pattern, at any
        # depth of one. Only further DIRECTORY nesting hides a path.
        if looks_like_file(segs[0]):
            continue
        # `ROOT / "notebooks" / "wellsight_v2"` is a sys.path bootstrap, not a
        # data path. A script must be able to name its own package directory,
        # and that location is load-bearing regardless -- 93 `parents[N]` calls
        # resolve against it. Routing it through path_for() would make the
        # import machinery depend on the config file it is importing in order
        # to read. Code locations are exempt; data locations are not.
        if segs[0] in ("notebooks", "ui", "roads_studio", "tools", "tests"):
            continue
        out.append({
            "file": path.relative_to(ROOT).as_posix(),
            "line": node.lineno,
            "expr": f"{root} / " + " / ".join(f'"{s}"' for s in segs),
            "suggest": suggest(root, segs, keys),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true",
                    help="rewrite the allow-list from the current tree")
    ap.add_argument("--fix-hint", action="store_true",
                    help="print the suggested path_for() call for each hit")
    args = ap.parse_args()

    keys = configured_keys()
    hits: list[dict] = []
    for d in SCAN_DIRS:
        for p in sorted((ROOT / d).rglob("*.py")):
            if not is_exempt(p):
                hits.extend(scan(p, keys))

    ident = {f"{h['file']}:{h['expr']}" for h in hits}

    if args.baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(sorted(ident), indent=2), "utf8")
        print(f"baseline written: {len(ident)} allowed literals -> {BASELINE}")
        return 0

    allowed = set(json.loads(BASELINE.read_text("utf8"))) if BASELINE.exists() else set()
    new = [h for h in hits if f"{h['file']}:{h['expr']}" not in allowed]

    lines = ["# Gate E -- path literals in live code", "",
             f"Scanned: {', '.join(SCAN_DIRS)}", "",
             "| sites | distinct | allow-listed | new |", "|---:|---:|---:|---:|",
             f"| {len(hits)} | {len(ident)} | {len(allowed)} | {len(new)} |", ""]
    if new:
        lines += ["## New violations", ""]
        for h in new:
            lines.append(f"- `{h['file']}:{h['line']}` -- `{h['expr']}` -> **{h['suggest']}**")
    else:
        lines += ["No new violations.", ""]
    REPORT.write_text("\n".join(lines) + "\n", "utf8")

    print(f"Gate E  path literals ...")
    print(f"  {len(hits)} sites / {len(ident)} distinct, {len(allowed)} allow-listed, {len(new)} new")
    if args.fix_hint:
        for h in hits:
            print(f"    {h['file']}:{h['line']}  {h['expr']}  ->  {h['suggest']}")
    print(f"\nwrote {REPORT}")
    if new:
        print("\nFAIL: new path literals. Add the directory to config/paths.toml "
              "and use path_for(), or re-baseline deliberately.")
        return 1
    print("\nPASS: no new path literals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
