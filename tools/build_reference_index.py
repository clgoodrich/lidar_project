"""Which files on disk does anything actually reference?

The reorganization rule is simple: a file with zero references is a move
candidate, a file with references is not. This builds the evidence for that
rule so no move is made on a hunch.

WHY THIS IS HARDER THAN GREP
-----------------------------
Python here builds paths compositionally, not literally:

    DERIV_9T / "pit_unet_cv5" / f"fold{k}" / "best.pt"

The string "data/derivatives/tiles/9t/pit_unet_cv5/fold0/best.pt" appears
nowhere. So the scanner keeps three indexes and a file matches on any of them:

  A  PATH literals   quoted strings containing a separator, normalised and
                     resolved against ROOT
  B  BASENAME liters quoted strings that look like a filename, matched against
                     basenames on disk. This is what catches the compositional
                     case -- "best.pt" and "pit_unet_cv5" appear separately.
  C  GLOB patterns   f-strings and .format() templates with the braces turned
                     into wildcards, e.g. f"pit_prob_floor_cvfold{k}_9t_05.tif"
                     -> pit_prob_floor_cvfold*_9t_05.tif

DIRECTION OF ERROR
------------------
The matching is deliberately GENEROUS. A false "referenced" costs nothing --
the file simply is not moved. A false "unreferenced" could move a live input
and break the pipeline. So when in doubt this reports referenced.

That also means a zero-reference verdict is necessary but NOT sufficient. A
raster you only ever opened by hand in QGIS has zero references here. Nothing
is deleted on the strength of this file; things are moved, and every move is
reversible through tools/undo_moves.py.

SOURCES SCANNED
---------------
Every .py .md .bat .json .toml .cfg .txt .qml .xml .ipynb in the repo, plus
qgis/*.qgz unpacked in memory (a .qgz is a ZIP holding one .qgs XML file).
Skips .git, .venv, __pycache__, and the archive tree.

Outputs:
    docs/reference_index.csv       one row per file/dir under the scanned roots
    docs/reference_index_summary.md  counts by directory, zero-ref totals

Reproduce:
  python tools/build_reference_index.py
  ... --roots data label_grids barlow    limit the disk walk
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import io
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "docs" / "reference_index.csv"
OUT_MD = ROOT / "docs" / "reference_index_summary.md"

SCAN_EXT = {".py", ".md", ".bat", ".json", ".toml", ".cfg", ".txt", ".qml",
            ".xml", ".ipynb", ".ps1", ".sh", ".yml", ".yaml"}
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".idea",
             ".ipynb_checkpoints", "node_modules"}
# Extensions that make a quoted string look like a filename worth indexing.
DATA_EXT = {".tif", ".tiff", ".gpkg", ".shp", ".dbf", ".shx", ".prj", ".cpg",
            ".csv", ".json", ".pt", ".png", ".jpg", ".las", ".laz", ".md",
            ".qml", ".xml", ".npz", ".parquet", ".kml", ".h5", ".txt", ".log",
            ".qgz", ".gpkg-wal", ".docx", ".pdf", ".xlsx"}

DEFAULT_ROOTS = ["data", "label_grids", "barlow", "models", "literature",
                 "qgis", "docs", "notebooks", "ui", "roads_studio", "tests",
                 "archive"]

# quoted string literals, single or double
STR_RE = re.compile(r"""(?<!\w)(['"])(?P<s>(?:\\.|(?!\1)[^\\\n]){2,300})\1""")
URL_RE = re.compile(r"^(https?|ftp|s3|gs)://", re.I)


def iter_source_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in SCAN_EXT:
            yield p
        elif p.suffix.lower() == ".qgz":
            yield p


def read_text(p: Path) -> str:
    if p.suffix.lower() == ".qgz":
        try:
            with zipfile.ZipFile(p) as z:
                out = []
                for n in z.namelist():
                    if n.lower().endswith((".qgs", ".qgd", ".xml")):
                        out.append(z.read(n).decode("utf8", errors="replace"))
                return "\n".join(out)
        except Exception:
            return ""
    try:
        return p.read_text(encoding="utf8", errors="replace")
    except Exception:
        return ""


def harvest(text: str):
    """Return (path_literals, basenames, globs) found in one source file."""
    paths, bases, globs = set(), set(), set()
    for m in STR_RE.finditer(text):
        s = m.group("s").strip()
        if not s or URL_RE.match(s):
            continue
        s = s.replace("\\\\", "/").replace("\\", "/")
        has_brace = "{" in s and "}" in s
        # C: templates -> globs
        if has_brace:
            g = re.sub(r"\{[^{}]*\}", "*", s)
            g = g.strip("/")
            if "." in Path(g).name:
                globs.add(Path(g).name)
            continue
        if "/" in s:
            paths.add(s.strip("./").rstrip("/"))
            base = Path(s).name
            if base and "." in base:
                bases.add(base)
            # every directory component is also a name that can be referenced
            for part in Path(s).parts:
                if part not in (".", "..", ""):
                    bases.add(part)
        else:
            # bare token: a filename or a directory name
            if Path(s).suffix.lower() in DATA_EXT or re.fullmatch(r"[\w.\-]+", s):
                bases.add(s)
    # XML datasource attributes in .qgz / .qml are not quoted strings
    for m in re.finditer(r"<datasource>(.*?)</datasource>", text, re.S):
        d = m.group(1).strip().replace("\\", "/")
        d = d.split("|")[0].strip()
        if d and not URL_RE.match(d):
            paths.add(d.strip("./"))
            for part in Path(d).parts:
                if part not in (".", "..", ""):
                    bases.add(part)
    return paths, bases, globs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="*", default=DEFAULT_ROOTS)
    a = ap.parse_args()

    print("scanning source files for path references ...")
    path_refs: dict[str, set] = defaultdict(set)
    base_refs: dict[str, set] = defaultdict(set)
    glob_refs: dict[str, set] = defaultdict(set)
    n_src = 0
    for sp in iter_source_files():
        rel = sp.relative_to(ROOT).as_posix()
        txt = read_text(sp)
        if not txt:
            continue
        n_src += 1
        P, B, G = harvest(txt)
        for x in P:
            path_refs[x.lower()].add(rel)
        for x in B:
            base_refs[x.lower()].add(rel)
        for x in G:
            glob_refs[x.lower()].add(rel)
    print(f"  {n_src} source files scanned")
    print(f"  {len(path_refs)} path literals, {len(base_refs)} names, "
          f"{len(glob_refs)} glob templates")

    # group globs by extension so matching stays cheap
    globs_by_ext: dict[str, list] = defaultdict(list)
    for g in glob_refs:
        globs_by_ext[Path(g).suffix.lower()].append(g)

    print("walking disk ...")
    rows = []
    zero = defaultdict(lambda: [0, 0])     # dir -> [count, bytes]
    total = defaultdict(lambda: [0, 0])
    for root_name in a.roots:
        rdir = ROOT / root_name
        if not rdir.exists():
            continue
        for p in rdir.rglob("*"):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            is_dir = p.is_dir()
            rel = p.relative_to(ROOT).as_posix()
            name = p.name.lower()
            srcs: set = set()
            kinds = set()
            if rel.lower() in path_refs:
                srcs |= path_refs[rel.lower()]; kinds.add("path")
            if name in base_refs:
                srcs |= base_refs[name]; kinds.add("name")
            if not is_dir:
                for g in globs_by_ext.get(p.suffix.lower(), ()):
                    if fnmatch.fnmatch(name, g):
                        srcs |= glob_refs[g]; kinds.add("glob")
                        break
            try:
                size = 0 if is_dir else p.stat().st_size
            except OSError:
                size = 0
            top = "/".join(rel.split("/")[:3])
            if not is_dir:
                total[top][0] += 1; total[top][1] += size
                if not srcs:
                    zero[top][0] += 1; zero[top][1] += size
            rows.append(dict(
                rel_path=rel, kind="dir" if is_dir else "file",
                size_bytes=size, n_refs=len(srcs),
                match_kinds="|".join(sorted(kinds)),
                referenced_by="; ".join(sorted(srcs)[:6])))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    files = [r for r in rows if r["kind"] == "file"]
    nz = [r for r in files if r["n_refs"] == 0]
    gb = sum(r["size_bytes"] for r in nz) / 1073741824
    print(f"\n{len(files):,} files indexed, {len(nz):,} with ZERO references "
          f"({gb:.1f} GB)")

    lines = ["# Reference index summary", "",
             f"Generated by `tools/build_reference_index.py`. "
             f"{n_src} source files scanned, {len(files):,} files indexed.", "",
             "A zero-reference file is a **move candidate**, not a delete "
             "candidate. Matching errs toward *referenced*; see the module "
             "docstring for why a zero here is necessary but not sufficient.",
             "",
             "| Directory | files | zero-ref files | zero-ref GB | % zero |",
             "|---|---:|---:|---:|---:|"]
    for k in sorted(total, key=lambda x: -zero[x][1]):
        tc, _ = total[k]
        zc, zb = zero[k]
        if tc == 0:
            continue
        lines.append(f"| `{k}` | {tc:,} | {zc:,} | {zb/1073741824:.2f} | "
                     f"{100*zc/tc:.0f}% |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf8")
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
