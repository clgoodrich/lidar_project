"""Find byte-identical files, then decide which copy is canonical.

THE _dupe CONVENTION
--------------------
Project rule: when two files have identical content and it is not obvious which
one is the real one, the redundant copy is renamed with a `_dupe` suffix. It is
never deleted. The name itself carries the doubt, so the next person reading a
directory listing sees the ambiguity without opening anything.

    road_03_multiscale_feats/best.pt  ->  best_dupe_of_plat_03.pt

This tool does not rename anything. It produces the evidence and a proposed
ledger; `tools/apply_moves.py` performs the renames.

HOW CANONICAL IS DECIDED
------------------------
In order, first rule that fires wins:

  1. REFERENCED     the copy with more references in docs/reference_index.csv is
                    canonical. Renaming a referenced file breaks something.
  2. NATIVE OUTPUT  a copy under `run/weights/` or `runs/` is a trainer's native
                    output; a copy beside it at the parent level is the
                    convenience copy, and the convenience copy is the dupe.
  3. IN-REPO        a copy inside the repository beats one outside it.
  4. SHALLOWER      the copy nearer the top of the tree is canonical.
  5. UNDECIDABLE    both get flagged, neither is auto-renamed, and the pair is
                    reported for a human. THIS is where `_dupe` is a guess and
                    the tool refuses to guess for you.

Hashing is two-pass so it stays cheap on 100k files: group by exact byte size
first, hash only inside groups of two or more.

Outputs:
    docs/duplicates_report.md            human-readable, grouped by size
    docs/duplicates_proposed_moves.csv   ledger for tools/apply_moves.py

Reproduce:
  python tools/find_duplicates.py
  ... --min-bytes 1048576   ignore anything under 1 MB
  ... --include-outside     also scan C:/Users/colto/Documents for stray copies
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "duplicates_report.md"
LEDGER = ROOT / "docs" / "duplicates_proposed_moves.csv"
REF_INDEX = ROOT / "docs" / "reference_index.csv"

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".idea",
             ".ipynb_checkpoints"}

# Never auto-rename inside these. They are author-owned documents where
# "which copy is real" is an editorial judgement, not a file-system one --
# the descriptive-name heuristic ranks `finesst_proposal_v11_working` above
# `ultimate_final/proposal_STM`, which is exactly backwards for a submission.
NO_RENAME_DIRS = {
    "barlow", "personal", "docs/related", "literature/papers",
    # A coherent demo set whose rasters are addressed by bare generic names
    # from notebooks/*.ipynb. Four of its six files are referenced; renaming
    # the other two would break the set's internal naming consistency for no
    # gain. Treat the directory as a unit.
    "data/derivatives/experiments/notebook_demo",
}

# Already-tagged files must never be re-tagged. Without this the tool is not
# idempotent: a second run turns x_dupe.tif into x_dupe_dupe.tif, because the
# tagged file is still byte-identical to its canonical twin.
DUPE_SUFFIX = "_dupe"

# A shapefile is not one file. Renaming the .shp alone orphans the rest.
SIDECARS = {
    ".shp": (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qix", ".sbn", ".sbx",
             ".shp.xml", ".qmd"),
    ".gpkg": (".gpkg", ".gpkg-wal", ".gpkg-shm"),
    ".tif": (".tif", ".tif.aux.xml", ".tif.ovr"),
}


def sidecar_set(p: Path) -> list[Path]:
    """Every file that must be renamed together with p."""
    exts = SIDECARS.get(p.suffix.lower())
    if not exts:
        return [p]
    out = []
    for e in exts:
        q = p.with_name(p.stem + e) if e.startswith(".") else p
        if q.exists():
            out.append(q)
    return out or [p]


def in_no_rename(p: Path) -> bool:
    try:
        r = p.relative_to(ROOT).as_posix()
    except ValueError:
        return True
    return any(r == d or r.startswith(d + "/") for d in NO_RENAME_DIRS)
# stray-copy hunting ground: the folder QGIS was found reaching into
OUTSIDE = [Path(r"C:\Users\colto\Documents")]


def sha(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_refs() -> dict[str, int]:
    refs = {}
    if REF_INDEX.exists():
        with open(REF_INDEX, encoding="utf8") as f:
            for r in csv.DictReader(f):
                refs[r["rel_path"].lower()] = int(r["n_refs"])
    return refs


def rel(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


RES_RE = __import__("re").compile(r"_(05|0p5|1m|2m|10m)(_[a-z0-9]+)?$", __import__("re").I)


def descriptiveness(p: Path) -> int:
    """How well does this filename follow the project's naming rule?

    CLAUDE.md requires a name to carry what it shows, its defining parameter,
    and the dataset it covers: `slope_e1423n2235_1m.tif`, not `slope.tif`.
    A generic name is the redundant copy even when it is shallower or more
    referenced, because the referencing code is usually a demo.
    """
    stem = p.stem
    score = stem.count("_")
    if RES_RE.search(stem):
        score += 3
    return score


def pick_canonical(group: list[Path], refs: dict[str, int]):
    """Return (canonical, [dupes], rule, confident)."""
    scored = [(refs.get(rel(p).lower(), 0), p) for p in group]

    # 1. naming convention beats everything, including reference count.
    #    A demo notebook referencing `slope.tif` does not make `slope.tif` the
    #    real file. But if the well-named copy is the UNREFERENCED one and the
    #    generic copy IS referenced, renaming would break the referrer -- so
    #    that conflict is reported, never auto-resolved.
    desc = {p: descriptiveness(p) for p in group}
    best = max(desc.values())
    winners = [p for p in group if desc[p] == best]
    if len(winners) == 1 and best - min(desc.values()) >= 2:
        can = winners[0]
        losers = [p for p in group if p != can]
        if any(refs.get(rel(l).lower(), 0) > 0 for l in losers):
            return None, group, "NAME-vs-REFS CONFLICT", False
        return can, losers, "descriptive-name", True

    # 2. references
    top = max(s for s, _ in scored)
    if top > 0 and sum(1 for s, _ in scored if s == top) == 1:
        can = [p for s, p in scored if s == top][0]
        return can, [p for p in group if p != can], "referenced", True

    # 2. native trainer output beats the convenience copy beside it
    native = [p for p in group if "weights" in p.parts or "runs" in p.parts
              or "run" in p.parts]
    if native and len(native) < len(group):
        can = native[0]
        return can, [p for p in group if p != can], "native-output", True

    # 3. in-repo beats outside
    inside = [p for p in group if ROOT in p.parents]
    if inside and len(inside) < len(group):
        can = inside[0]
        return can, [p for p in group if p != can], "in-repo", True

    # 4. shallower wins
    depths = {p: len(p.parts) for p in group}
    m = min(depths.values())
    if sum(1 for d in depths.values() if d == m) == 1:
        can = [p for p in group if depths[p] == m][0]
        return can, [p for p in group if p != can], "shallower", True

    # 5. undecidable
    return None, group, "UNDECIDABLE", False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-bytes", type=int, default=1024)
    ap.add_argument("--include-outside", action="store_true")
    a = ap.parse_args()

    refs = load_refs()
    print(f"loaded {len(refs):,} reference-index rows")

    roots = [ROOT] + (OUTSIDE if a.include_outside else [])
    by_size: dict[int, list[Path]] = defaultdict(list)
    seen: set[Path] = set()
    n = 0
    for r in roots:
        for p in r.rglob("*"):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            # OUTSIDE roots contain the repository. Without this guard every
            # file matches itself and the report claims the repo is 100%
            # duplicate.
            if r is not ROOT and (p == ROOT or ROOT in p.parents):
                continue
            rp = p.resolve()
            if rp in seen:
                continue
            seen.add(rp)
            try:
                if not p.is_file():
                    continue
                s = p.stat().st_size
            except OSError:
                continue
            if s < a.min_bytes:
                continue
            n += 1
            by_size[s].append(p)
    cand = {s: g for s, g in by_size.items() if len(g) > 1}
    print(f"{n:,} files scanned, {len(cand):,} size groups to hash "
          f"({sum(len(g) for g in cand.values()):,} files)")

    groups: dict[tuple, list[Path]] = defaultdict(list)
    for s, g in cand.items():
        for p in g:
            try:
                groups[(s, sha(p))].append(p)
            except OSError:
                pass
    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    wasted = sum(k[0] * (len(v) - 1) for k, v in dupes.items())
    print(f"{len(dupes)} duplicate sets, {wasted/2**30:.2f} GB redundant")

    rows, lines = [], []
    lines += ["# Duplicate files", "",
              f"Generated by `tools/find_duplicates.py`. {len(dupes)} sets of "
              f"byte-identical files, **{wasted/2**30:.2f} GB redundant**.", "",
              "Nothing here is deleted. The redundant copy is renamed with a "
              "`_dupe` suffix so the ambiguity is visible in a directory "
              "listing. Sets marked **UNDECIDABLE** are not auto-renamed — the "
              "tool will not guess which copy is real.", ""]

    undecidable = []
    for (size, h), g in sorted(dupes.items(), key=lambda kv: -kv[0][0]):
        can, dl, rule, ok = pick_canonical(sorted(g), refs)
        lines.append(f"### `{g[0].name}` — {size/2**20:.1f} MB × {len(g)} "
                     f"({rule})")
        for p in sorted(g):
            mark = "**canonical**" if p == can else "dupe"
            lines.append(f"- {mark} `{rel(p)}` (refs "
                         f"{refs.get(rel(p).lower(), 0)})")
        lines.append("")
        if not ok:
            undecidable.append(g)
            continue
        for d in dl:
            # HARD SCOPE LIMIT. --include-outside exists to DETECT stray copies
            # of project files elsewhere on the disk, never to rename them.
            # Everything under C:\Users\colto\Documents that is not this repo
            # belongs to the user, not to this tool.
            if ROOT not in d.parents:
                lines.append(f"  > outside the repository, report only: "
                             f"`{rel(d)}`")
                continue
            if d.name.split(".")[0].endswith(DUPE_SUFFIX):
                lines.append(f"  > already tagged, left alone: `{rel(d)}`")
                continue
            if in_no_rename(d):
                lines.append(f"  > author-owned area, not renamed: `{rel(d)}`")
                continue
            if refs.get(rel(d).lower(), 0) > 0:
                lines.append(f"  > not renamed: {rel(d)} has references")
                continue
            group_files = sidecar_set(d)
            if len(group_files) > 1:
                lines.append(f"  > renaming {len(group_files)} sidecar files "
                             f"together: {', '.join(q.suffix for q in group_files)}")
            for q in group_files:
                # keep the compound suffix intact: x.tif.aux.xml -> x_dupe.tif.aux.xml
                tail = q.name[len(d.stem):]
                new = q.with_name(f"{d.stem}_dupe{tail}")
                rows.append(dict(old_path=rel(q), new_path=rel(new),
                                 phase="dupe",
                                 reason=f"{rule}; identical to {rel(can)}",
                                 sha256=h[:16]))

    if undecidable:
        inside = [g for g in undecidable if any(ROOT in p.parents for p in g)]
        lines += ["## Undecidable — needs a human", "",
                  f"{len(inside)} sets inside the repository "
                  f"({len(undecidable)-len(inside)} more elsewhere on disk, "
                  f"not this project's business and not listed).", ""]
        for g in inside:
            lines.append("- " + " ⟷ ".join(f"`{rel(p)}`" for p in sorted(g)))
        lines.append("")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf8")
    if rows:
        with open(LEDGER, "w", newline="", encoding="utf8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    print(f"proposed {len(rows)} _dupe renames, {len(undecidable)} undecidable")
    print(f"wrote {REPORT}")
    if rows:
        print(f"wrote {LEDGER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
