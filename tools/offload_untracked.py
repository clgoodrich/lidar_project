"""Move untracked files in chosen folders from C to an offload drive. Set 2026-11-24.

Why: C is 98% full. These folders are not read by any current script. Tracked files stay on C,
so git sees no change; only untracked/ignored heavy files move.

Steps
  copy    copy each untracked file to <DST>/<same repo-relative path>, keep timestamps
  verify  every copied file exists on DST with the same size
  delete  remove from C only files that verified; empty folders pruned
A manifest CSV of every moved file is written to docs/offload_manifest_<date>.csv.

Run
  python tools/offload_untracked.py copy
  python tools/offload_untracked.py verify
  python tools/offload_untracked.py delete
"""
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DST = Path(r"F:\lidar_project_offload")
FOLDERS = ["PLanet", "data/9t/models/_retired", "data/9t/models/_arch_compare",
           "nisar/derived/613590", "nisar/derived/mkf", "share_9t_annotations_rrim"]
MANIFEST = REPO / "docs" / "offload_manifest_20261124.csv"


def files():
    tracked = set(subprocess.run(["git", "ls-files", "-z", *FOLDERS], cwd=REPO, capture_output=True,
                                 text=True, check=True).stdout.split("\0"))
    for f in FOLDERS:
        for p in (REPO / f).rglob("*"):
            if p.is_file():
                rel = p.relative_to(REPO).as_posix()
                if rel not in tracked:
                    yield rel, p


def main(step):
    if step == "copy":
        rows, n, b = [], 0, 0
        for rel, p in files():
            d = DST / rel
            d.parent.mkdir(parents=True, exist_ok=True)
            if not (d.exists() and d.stat().st_size == p.stat().st_size):
                shutil.copy2(p, d)
            rows.append((rel, p.stat().st_size))
            n += 1; b += p.stat().st_size
        with open(MANIFEST, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["path", "bytes", "moved_to"])
            w.writerows((r, s, str(DST / r)) for r, s in rows)
        print(f"copied {n} files, {b / 1e9:.2f} GB -> {DST}; manifest {MANIFEST}")
    elif step == "verify":
        bad = 0
        rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8")))
        for r in rows:
            d = DST / r["path"]
            if not d.exists() or d.stat().st_size != int(r["bytes"]):
                bad += 1; print("MISMATCH", r["path"])
        print(f"{len(rows)} files checked, {bad} mismatches")
    elif step == "delete":
        rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8")))
        n = 0
        for r in rows:
            src, d = REPO / r["path"], DST / r["path"]
            if src.exists() and d.exists() and d.stat().st_size == int(r["bytes"]) == src.stat().st_size:
                src.unlink(); n += 1
        for f in FOLDERS:
            for dp, dn, fn in sorted(os.walk(REPO / f), key=lambda t: -len(t[0])):
                if not os.listdir(dp):
                    os.rmdir(dp)
        print(f"deleted {n} of {len(rows)} files from C")


if __name__ == "__main__":
    main(sys.argv[1])
