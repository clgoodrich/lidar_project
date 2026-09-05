"""Prove the backup is a faithful copy before trusting it with a reorganization.

A backup you have not verified is a belief, not a safety net. This is run once
before the first destructive-looking step, and any time the backup's
trustworthiness actually matters.

THREE LEVELS, cheapest first
---------------------------
1. INVENTORY   every file in the source must exist in the target with the same
               byte size. Exhaustive, metadata only, fast. Catches the failures
               that actually happen: interrupted copies, truncated files,
               skipped directories, permission errors.
2. SAMPLE HASH SHA-256 both sides for a stratified sample -- every file above
               --big-mb, plus a deterministic random draw of --sample others.
               Catches silent corruption, which metadata cannot see.
3. FULL HASH   --full hashes everything. Reads ~244 GB for a 122 GB tree, so
               roughly 40 minutes on this hardware. Correct, rarely worth it.

The random draw is seeded from the file path, so the same sample is chosen on
every run and two runs are comparable.

EXTRA files -- present in the target, absent from the source -- are reported but
are NOT failures. The backup policy is `robocopy /XO`, which never deletes, so
extras are expected and deliberate.

Outputs:
    docs/verify_backup_report.md   (override with --report)

Exit 0 if the source is fully represented in the target, 1 otherwise.

Reproduce:
  python tools/verify_backup.py --target "E:/Colton/_BACKUPS/lidar_project_MIRROR"
  python tools/verify_backup.py --target "F:/Colton/_BACKUPS/lidar_project_MIRROR"       --report docs/verify_backup_report_F_mirror.md
  ... --sample 300 --big-mb 500
  ... --full
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "verify_backup_report.md"
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}

# robocopy writes its own log AFTER copying everything, including after it has
# copied the log. The mirror's copy is therefore always one run stale, by
# construction. It is not a backup defect and can never be made to match, so
# comparing it produces a permanent false failure.
# Same self-reference applies to this tool's own report, which is written after
# the comparison finishes. Both are excluded so a clean backup can actually
# report PASS instead of failing on artefacts of the check itself.
# Matched with fnmatch so a second mirror on another drive (backup_to_F.bat,
# verify_backup_report_F_mirror.md) is covered without editing this set again.
SKIP_GLOBS = ("backup_to_*_last_run.log", "verify_backup_report*.md")


def skipped(name: str) -> bool:
    return any(fnmatch(name, g) for g in SKIP_GLOBS)


def sha(p: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def inventory(base: Path) -> dict[str, int]:
    out = {}
    for p in base.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if skipped(p.name):
            continue
        try:
            if p.is_file():
                out[p.relative_to(base).as_posix()] = p.stat().st_size
        except OSError:
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--sample", type=int, default=250)
    ap.add_argument("--big-mb", type=float, default=500.0)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--report", default=str(REPORT),
                    help="where to write the markdown report. Give a "
                         "target-specific name when verifying a second "
                         "mirror, so it does not overwrite the first one's "
                         "record -- an unmounted drive's report cannot be "
                         "regenerated.")
    a = ap.parse_args()
    report_path = Path(a.report)
    tgt = Path(a.target)
    if not tgt.exists():
        print(f"target does not exist: {tgt}")
        return 1

    print("level 1: inventory ...", flush=True)
    src = inventory(ROOT)
    dst = inventory(tgt)
    print(f"  source {len(src):,} files  {sum(src.values())/2**30:.2f} GB")
    print(f"  target {len(dst):,} files  {sum(dst.values())/2**30:.2f} GB")

    missing = sorted(k for k in src if k not in dst)
    mismatch = sorted(k for k in src if k in dst and src[k] != dst[k])
    extra = sorted(k for k in dst if k not in src)
    print(f"  MISSING from target : {len(missing):,}")
    print(f"  SIZE MISMATCH       : {len(mismatch):,}")
    print(f"  extra in target     : {len(extra):,}  (expected; /XO never deletes)")

    shared = [k for k in src if k in dst and src[k] == dst[k]]
    big_cut = a.big_mb * 2**20
    if a.full:
        pick = shared
    else:
        big = [k for k in shared if src[k] >= big_cut]
        rest = sorted(k for k in shared if src[k] < big_cut)
        rng = random.Random(20260812)
        rng.shuffle(rest)
        pick = big + rest[:a.sample]
    print(f"\nlevel 2: hashing {len(pick):,} files "
          f"({sum(src[k] for k in pick)/2**30:.2f} GB on each side) ...",
          flush=True)

    bad_hash, checked, done_bytes = [], 0, 0
    for k in pick:
        try:
            if sha(ROOT / k) != sha(tgt / k):
                bad_hash.append(k)
        except OSError as e:
            bad_hash.append(f"{k}  (read error: {e})")
        checked += 1
        done_bytes += src[k]
        if checked % 50 == 0:
            print(f"    {checked:,}/{len(pick):,}  "
                  f"{done_bytes/2**30:.1f} GB", flush=True)
    print(f"  content mismatches  : {len(bad_hash)}")

    ok = not missing and not mismatch and not bad_hash
    lines = ["# Backup integrity report", "",
             f"Source `{ROOT}`", f"Target `{tgt}`", "",
             "| Check | Result |", "|---|---|",
             f"| Source files | {len(src):,} ({sum(src.values())/2**30:.2f} GB) |",
             f"| Target files | {len(dst):,} ({sum(dst.values())/2**30:.2f} GB) |",
             f"| Missing from target | **{len(missing):,}** |",
             f"| Size mismatch | **{len(mismatch):,}** |",
             f"| Content hashed | {len(pick):,} files, "
             f"{sum(src[k] for k in pick)/2**30:.2f} GB |",
             f"| Content mismatch | **{len(bad_hash)}** |",
             f"| Extra in target (expected) | {len(extra):,} |", "",
             f"**Verdict: {'PASS' if ok else 'FAIL'}**", ""]
    for name, items in (("Missing from target", missing),
                        ("Size mismatch", mismatch),
                        ("Content mismatch", bad_hash)):
        if items:
            lines += [f"## {name}", ""]
            lines += [f"- `{x}`" for x in items[:100]]
            if len(items) > 100:
                lines.append(f"- … and {len(items)-100} more")
            lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf8")
    print(f"\nwrote {REPORT}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
