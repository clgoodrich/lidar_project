"""Did any archived script actually run recently? Check its OUTPUTS, not a log.

The v1 archive used `docs/analysis_log.md` mentions as the evidence of use. That
is weak in the dangerous direction: absence from the log does NOT mean a script
never ran. Plenty of passes happen without being written up, and test runs are
never logged at all.

This looks for physical evidence instead. Every script declares its outputs as
module-level Path constants. If any of those paths exists on disk with a recent
mtime, something wrote it recently -- which is direct evidence the script ran,
independent of whether anyone remembered to log it.

RESOLUTION DETAIL THAT MATTERS
An archived script now lives under data/99_archive/, so its own
`Path(__file__).resolve().parents[N]` would resolve to the wrong place. Paths are
therefore folded using the script's ORIGINAL location, taken from docs/MOVES.csv.
Getting this wrong would silently produce paths that do not exist and make every
archived script look unused -- the exact error this tool exists to catch.

DIRECTION OF ERROR
Deliberately biased toward "still used". A recent output might have been written
by a different script that shares the directory, so a hit is not proof this
script ran. But a hit means the archive decision deserves a second look, and the
cost of checking is far lower than the cost of burying live code.

Outputs:
    docs/archived_still_used_report.md

Reproduce:
  python tools/check_archived_still_used.py --phase v1_archive --days 60
"""
from __future__ import annotations

import argparse
import ast
import csv
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOVES = ROOT / "docs" / "MOVES.csv"
REPORT = ROOT / "docs" / "archived_still_used_report.md"


def fold(node, orig: Path, syms: dict):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return syms.get(node.id)
    if isinstance(node, ast.Subscript):
        v = node.value
        if isinstance(v, ast.Attribute) and v.attr == "parents" \
                and isinstance(node.slice, ast.Constant):
            try:
                return orig.parents[node.slice.value]
            except IndexError:
                return None
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        l, r = fold(node.left, orig, syms), fold(node.right, orig, syms)
        if isinstance(l, Path) and isinstance(r, str):
            return l / r
        return None
    if isinstance(node, ast.Call):
        f = node.func
        nm = getattr(f, "id", None) or getattr(f, "attr", None)
        if nm in ("str", "resolve", "Path") and node.args:
            return fold(node.args[0], orig, syms)
        if nm == "resolve" and isinstance(f, ast.Attribute):
            return fold(f.value, orig, syms)
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        b = fold(node.value, orig, syms)
        return b.parent if isinstance(b, Path) else None
    return None


def declared(p: Path, orig: Path) -> list[Path]:
    """Module-level Path constants, resolved as if the file were at `orig`."""
    try:
        t = ast.parse(p.read_text(encoding="utf8", errors="replace"))
    except SyntaxError:
        return []
    syms = {"ROOT": ROOT,
            "DERIV": ROOT / "data" / "derivatives",
            "DERIV_9T": ROOT / "data" / "derivatives" / "tiles" / "9t",
            "D": ROOT / "data" / "derivatives" / "tiles" / "9t"}
    out = []
    for n in t.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            v = fold(n.value, orig, syms)
            if isinstance(v, Path):
                syms[n.targets[0].id] = v
                # Only a SPECIFIC FILE counts. A bare directory like DERIV_9T is
                # a base path shared by dozens of scripts; its newest file
                # reflects whatever touched the folder last, and the 2026-08-12
                # reorganisation made every such script look like it ran today.
                if ROOT in v.parents and "99_archive" not in v.parts and v.suffix:
                    out.append(v)
    return out


def newest_mtime(p: Path) -> date | None:
    """Newest mtime at or under p."""
    try:
        if p.is_file():
            return datetime.fromtimestamp(p.stat().st_mtime).date()
        if p.is_dir():
            best = None
            for q in p.rglob("*"):
                try:
                    if q.is_file():
                        d = datetime.fromtimestamp(q.stat().st_mtime).date()
                        if best is None or d > best:
                            best = d
                except OSError:
                    pass
            return best
    except OSError:
        pass
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="v1_archive")
    ap.add_argument("--days", type=int, default=60)
    a = ap.parse_args()
    today = date(2026, 8, 12)

    # Ground truth is what is actually IN the archive, not the ledger. The
    # ledger holds both the first archive run and the re-run after an --undo,
    # because --undo appends a row instead of retiring the originals, so
    # filtering it by phase double-counts.
    ARC = ROOT / "data" / "99_archive" / "superseded" / "notebooks_wellsight"
    V1 = ROOT / "notebooks" / "wellsight"
    moves = [dict(new_path=p.relative_to(ROOT).as_posix(),
                  old_path=(V1 / p.relative_to(ARC)).relative_to(ROOT).as_posix())
             for p in sorted(ARC.rglob("*.py"))
             if "__pycache__" not in p.parts]
    print(f"{len(moves)} scripts currently in the archive")

    hits, quiet, nopaths = [], [], []
    for r in moves:
        now = ROOT / r["new_path"]
        orig = ROOT / r["old_path"]
        if not now.is_file() or now.suffix != ".py":
            continue
        outs = declared(now, orig)
        if not outs:
            nopaths.append((r["old_path"], None))
            continue
        best, where = None, None
        for o in outs:
            d = newest_mtime(o)
            if d and (best is None or d > best):
                best, where = d, o
        if best is None:
            nopaths.append((r["old_path"], None))
        elif (today - best).days <= a.days:
            hits.append((r["old_path"], best, where, (today - best).days))
        else:
            quiet.append((r["old_path"], best, where))

    L = ["# Did any archived script actually run recently?", "",
         f"Physical evidence, not log mentions: newest mtime of the output paths "
         f"each script declares. Window {a.days} days (since "
         f"{date.fromordinal(today.toordinal() - a.days)}).", "",
         "Biased toward *still used* — a shared output directory can be touched "
         "by a sibling script, so a hit warrants a look, not an automatic "
         "restore.", "",
         "| Bucket | Scripts |", "|---|---:|",
         f"| **output written within {a.days} days** | **{len(hits)}** |",
         f"| outputs exist but are older | {len(quiet)} |",
         f"| no resolvable output path | {len(nopaths)} |", ""]
    if hits:
        L += [f"## Output touched within {a.days} days — review these", "",
              "| Script | newest output | days | path |", "|---|---|---:|---|"]
        for s, d, w, ago in sorted(hits, key=lambda x: x[1], reverse=True):
            L.append(f"| `{s}` | {d} | {ago} | `{w.relative_to(ROOT).as_posix()}` |")
        L.append("")
    L += ["## Outputs exist, but older", ""]
    for s, d, w in sorted(quiet, key=lambda x: x[1], reverse=True):
        L.append(f"- `{s}` — newest output {d}")
    L += ["", "## No resolvable output path", "",
          "Nothing to date them by. Absence of evidence.", ""]
    for s, _ in sorted(nopaths):
        L.append(f"- `{s}`")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf8")

    print(f"  output written within {a.days}d : {len(hits)}   <-- REVIEW")
    print(f"  outputs older                  : {len(quiet)}")
    print(f"  no resolvable output path      : {len(nopaths)}")
    for s, d, w, ago in sorted(hits, key=lambda x: x[1], reverse=True):
        print(f"    {d}  ({ago:3d}d)  {s}")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
