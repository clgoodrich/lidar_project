"""The three gates. Run after every reorganization step; all three must pass.

    A  GIT LEAK    no file >100 MB is unignored. This is the only failure mode
                   that is permanent -- git history cannot be un-written -- and
                   the only one that is silent. Enforces the CLAUDE.md
                   Large-file rule.
    B  QGIS        every <datasource> in qgis/*.qgz resolves to a file that
                   exists. 57 of 59 layers bind by RELATIVE path into
                   data/derivatives/, so any data move can break them, and QGIS
                   reports it only when a human next opens the project.
    C  SCRIPTS     every module-level Path constant in the live scripts still
                   points at something. Parsed with `ast`, never executed, so a
                   broken script cannot do damage while being checked.

Gate C resolves compositional paths without running code. It walks module-level
assignments, seeds a symbol table with the `_common` constants (ROOT, DERIV,
DERIV_9T), then folds `NAME / "a" / "b"` chains. Names it cannot resolve are
reported as `unresolved`, not as failures -- an honest unknown beats a
confident wrong answer.

Run BEFORE the first move to capture a baseline. Some things are already broken;
the gate is for detecting NEW breakage, so the baseline is what makes it useful.

Outputs:
    docs/verify_paths_report.md    latest run, all three gates

Exit code 0 if all gates pass, 1 otherwise. `--baseline` writes the current
failures to docs/_ledgers/verify_paths_baseline.json and always exits 0.

Reproduce:
  python tools/verify_paths.py
  python tools/verify_paths.py --baseline
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "verify_paths_report.md"
BASELINE = ROOT / "docs" / "_ledgers" / "verify_paths_baseline.json"
BIG_BYTES = 100 * 1024 * 1024

SCRIPT_ROOTS = ["notebooks/wellsight_v2", "ui", "roads_studio", "tools"]
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}

SEED = {
    "ROOT": ROOT,
    "DERIV": ROOT / "data" / "derivatives",
    "DERIV_9T": ROOT / "data" / "derivatives" / "tiles" / "9t",
}


# ---------------------------------------------------------------- gate A
def gate_a() -> list[str]:
    """Files >100 MB that git is NOT ignoring."""
    bad = []
    for p in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        try:
            if not p.is_file() or p.stat().st_size <= BIG_BYTES:
                continue
        except OSError:
            continue
        rel = p.relative_to(ROOT).as_posix()
        r = subprocess.run(["git", "check-ignore", rel], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:                    # not ignored
            bad.append(f"{rel}  ({p.stat().st_size/1048576:.0f} MB)")
    return bad


# ---------------------------------------------------------------- gate B
def gate_b() -> tuple[list[str], int]:
    """QGIS datasources that do not resolve."""
    bad, total = [], 0
    for qgz in sorted((ROOT / "qgis").glob("*.qgz")):
        try:
            with zipfile.ZipFile(qgz) as z:
                names = [n for n in z.namelist() if n.lower().endswith(".qgs")]
                if not names:
                    continue
                xml = z.read(names[0]).decode("utf8", errors="replace")
        except Exception as e:
            bad.append(f"{qgz.name}: cannot open ({e})")
            continue
        import re
        for m in re.finditer(r"<datasource>(.*?)</datasource>", xml, re.S):
            d = m.group(1).strip()
            if not d:
                continue
            total += 1
            low = d.lower()
            if low.startswith(("http", "crs=", "type=xyz")) or "url=" in low:
                continue                          # remote basemap
            fp = d.split("|")[0].strip().replace("\\", "/")
            cand = (qgz.parent / fp).resolve()
            if not cand.exists():
                bad.append(f"{qgz.name}: {fp}")
    return bad, total


# ---------------------------------------------------------------- gate C
def _fold(node, syms: dict):
    """Resolve an ast node to a Path, or None if it cannot be resolved."""
    if isinstance(node, ast.Name):
        return syms.get(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _fold(node.left, syms)
        right = _fold(node.right, syms)
        if isinstance(left, Path) and isinstance(right, str):
            return left / right
        return None
    if isinstance(node, ast.Call):               # Path("...")
        f = node.func
        nm = getattr(f, "id", None) or getattr(f, "attr", None)
        if nm == "Path" and node.args:
            v = _fold(node.args[0], syms)
            if isinstance(v, str):
                return Path(v)
    return None


def gate_c() -> tuple[list[str], int, int]:
    """Module-level Path constants that point at nothing."""
    bad, checked, unresolved = [], 0, 0
    for rootname in SCRIPT_ROOTS:
        base = ROOT / rootname
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf8", errors="replace"))
            except SyntaxError as e:
                bad.append(f"{p.relative_to(ROOT).as_posix()}: SYNTAX {e}")
                continue
            syms = dict(SEED)
            for node in tree.body:
                if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                    continue
                tgt = node.targets[0]
                if not isinstance(tgt, ast.Name):
                    continue
                val = _fold(node.value, syms)
                if isinstance(val, Path):
                    syms[tgt.id] = val
                    # only check constants that look like real data anchors
                    if val.suffix or val.name.isupper() or True:
                        checked += 1
                        if not val.exists():
                            # a path with a format placeholder is not a failure
                            if "{" in str(val):
                                continue
                            bad.append(
                                f"{p.relative_to(ROOT).as_posix()}: "
                                f"{tgt.id} -> {val.relative_to(ROOT).as_posix() if ROOT in val.parents or val == ROOT else val}")
                elif isinstance(node.value, ast.BinOp):
                    unresolved += 1
    return bad, checked, unresolved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true",
                    help="record current failures and exit 0")
    ap.add_argument("--skip-a", action="store_true",
                    help="skip the git leak walk (slow on 100k files)")
    a = ap.parse_args()

    print("Gate A  git leak audit ...", flush=True)
    A = [] if a.skip_a else gate_a()
    print(f"  {len(A)} unignored files >100 MB")
    print("Gate B  QGIS datasources ...", flush=True)
    B, ntot = gate_b()
    print(f"  {len(B)} of {ntot} layers do not resolve")
    print("Gate C  script path constants ...", flush=True)
    C, nchk, nunres = gate_c()
    print(f"  {len(C)} of {nchk} resolved constants point at nothing "
          f"({nunres} expressions unresolved)")

    base = {}
    if BASELINE.exists() and not a.baseline:
        base = json.loads(BASELINE.read_text(encoding="utf8"))
    newA = [x for x in A if x not in base.get("A", [])]
    newB = [x for x in B if x not in base.get("B", [])]
    newC = [x for x in C if x not in base.get("C", [])]

    lines = ["# verify_paths report", "",
             "Generated by `tools/verify_paths.py`. Gates must all pass before a "
             "reorganization phase is considered complete.", "",
             f"| Gate | Checked | Failing | New since baseline |",
             "|---|---:|---:|---:|",
             f"| A git leak >100 MB | all files | {len(A)} | {len(newA)} |",
             f"| B QGIS datasources | {ntot} | {len(B)} | {len(newB)} |",
             f"| C script constants | {nchk} | {len(C)} | {len(newC)} |", ""]
    for name, items in (("A git leak", A), ("B QGIS", B), ("C scripts", C)):
        lines.append(f"## {name}")
        lines.append("")
        if not items:
            lines.append("_none_")
        for x in items[:80]:
            lines.append(f"- `{x}`")
        if len(items) > 80:
            lines.append(f"- … and {len(items)-80} more")
        lines.append("")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf8")
    print(f"\nwrote {REPORT}")

    if a.baseline:
        BASELINE.write_text(json.dumps({"A": A, "B": B, "C": C}, indent=2),
                            encoding="utf8")
        print(f"wrote {BASELINE}  (baseline recorded, exiting 0)")
        return 0

    if newA or newB or newC:
        print(f"\nFAIL: {len(newA)} new leaks, {len(newB)} new broken QGIS "
              f"layers, {len(newC)} new broken constants")
        return 1
    print("\nPASS: no new breakage vs baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
