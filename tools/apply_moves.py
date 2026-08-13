"""Execute or reverse a file-move ledger. Every reorganization move goes through here.

Nothing in this repository is deleted. Files are renamed or relocated, and every
operation is appended to the master ledger `docs/MOVES.csv` so it can be undone.

    tools/apply_moves.py --ledger docs/duplicates_proposed_moves.csv   # dry run
    tools/apply_moves.py --ledger docs/duplicates_proposed_moves.csv --execute
    tools/apply_moves.py --undo --last 33      # reverse the last 33 moves
    tools/apply_moves.py --undo --phase dupe   # reverse everything tagged 'dupe'

DRY RUN IS THE DEFAULT. `--execute` is required to touch the disk.

SAFETY RULES
------------
1. Refuses if the destination already exists. No silent overwrite, ever.
2. Refuses if the source is missing, unless `--skip-missing`.
3. Verifies size after the move; a mismatch aborts the run immediately.
4. Appends to `docs/MOVES.csv` AFTER each successful move, flushed each time,
   so a crash mid-run still leaves an accurate ledger to undo from.
5. Moves within one volume are renames, so they are atomic and instant. A
   cross-volume move is copy-then-verify-then-delete-source, and the source is
   only unlinked once the destination hash matches.

WHY A LEDGER AND NOT A SHELL SCRIPT
-----------------------------------
A shell script tells you what was intended. A ledger tells you what actually
happened, in order, with timestamps, so `--undo` is exact rather than
reconstructed. That distinction is the whole reason a 122 GB reorganization is
safe to attempt.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs" / "MOVES.csv"
FIELDS = ["ts", "phase", "old_path", "new_path", "size_bytes", "reason"]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def append_master(row: dict) -> None:
    new = not MASTER.exists()
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    with open(MASTER, "a", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
        f.flush()


def do_move(src: Path, dst: Path) -> int:
    # Directories are moved whole. On one volume that is a metadata rename, so
    # archiving 88,523 files is instant; across volumes shutil.move falls back
    # to a recursive copy. The size check below only applies to files.
    if src.is_dir():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.drive.lower() == dst.drive.lower():
            src.rename(dst)
        else:
            shutil.move(str(src), str(dst))
        if not dst.exists():
            raise RuntimeError(f"directory move failed: {src} -> {dst}")
        return sum(p.stat().st_size for p in dst.rglob("*") if p.is_file())

    size = src.stat().st_size
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.drive.lower() == dst.drive.lower():
        src.rename(dst)
    else:
        before = sha(src)
        shutil.copy2(src, dst)
        if sha(dst) != before:
            dst.unlink(missing_ok=True)
            raise RuntimeError(f"hash mismatch copying {src} -> {dst}")
        src.unlink()
    if dst.stat().st_size != size:
        raise RuntimeError(f"size mismatch after move: {dst}")
    return size


def apply(ledger: Path, execute: bool, skip_missing: bool) -> int:
    with open(ledger, encoding="utf8") as f:
        rows = list(csv.DictReader(f))
    print(f"{len(rows)} moves in {ledger.name}  "
          f"({'EXECUTE' if execute else 'DRY RUN'})")

    planned, problems, total = [], [], 0
    for r in rows:
        s, d = ROOT / r["old_path"], ROOT / r["new_path"]
        if not s.exists():
            (planned if skip_missing else problems).append(
                (r, "source missing"))
            continue
        if d.exists():
            problems.append((r, "DESTINATION EXISTS"))
            continue
        total += s.stat().st_size
        planned.append((r, None))

    for r, why in problems:
        print(f"  BLOCKED {why}: {r['old_path']}")
    if problems:
        print(f"\n{len(problems)} blocking problems. Nothing moved.")
        return 1

    for r, why in planned:
        if why:
            print(f"  skip (missing): {r['old_path']}")
            continue
        print(f"  {r['old_path']}\n    -> {r['new_path']}")

    if not execute:
        print(f"\nDRY RUN. {len(planned)} moves, {total/2**20:.1f} MB. "
              f"Re-run with --execute.")
        return 0

    n = 0
    for r, why in planned:
        if why:
            continue
        s, d = ROOT / r["old_path"], ROOT / r["new_path"]
        size = do_move(s, d)
        append_master(dict(ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                           phase=r.get("phase", ""), old_path=r["old_path"],
                           new_path=r["new_path"], size_bytes=size,
                           reason=r.get("reason", "")))
        n += 1
    print(f"\nmoved {n} files, {total/2**20:.1f} MB")
    print(f"ledger: {MASTER}")
    return 0


def undo(last: int | None, phase: str | None, execute: bool) -> int:
    if not MASTER.exists():
        print("no master ledger; nothing to undo")
        return 0
    with open(MASTER, encoding="utf8") as f:
        rows = list(csv.DictReader(f))
    sel = [r for r in rows if phase is None or r["phase"] == phase]
    if last:
        sel = sel[-last:]
    sel = list(reversed(sel))                 # newest first
    print(f"{len(sel)} moves to reverse  "
          f"({'EXECUTE' if execute else 'DRY RUN'})")
    for r in sel:
        print(f"  {r['new_path']}\n    -> {r['old_path']}")
    if not execute:
        print("\nDRY RUN. Re-run with --execute.")
        return 0
    done = 0
    for r in sel:
        s, d = ROOT / r["new_path"], ROOT / r["old_path"]
        if not s.exists():
            print(f"  skip, already gone: {r['new_path']}")
            continue
        if d.exists():
            print(f"  BLOCKED, original path occupied: {r['old_path']}")
            continue
        do_move(s, d)
        done += 1
    # record the undo itself rather than rewriting history
    append_master(dict(ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       phase="UNDO", old_path=f"<{done} moves reversed>",
                       new_path="", size_bytes=0,
                       reason=f"undo last={last} phase={phase}"))
    print(f"\nreversed {done} moves")
    return 0


def main() -> int:
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--skip-missing", action="store_true")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--last", type=int)
    ap.add_argument("--phase")
    ap.add_argument("--root", type=Path, help=(
        "apply the ledger against a DIFFERENT tree, e.g. the E: mirror. "
        "backup_to_E.bat uses robocopy /XO, which never deletes -- so a "
        "restructure on C: would leave the mirror holding both the old tree and "
        "the new one, doubling it. Replaying the same ledger on the mirror keeps "
        "it a mirror. Same-volume renames, so it is near-instant. The master "
        "docs/MOVES.csv is NOT appended to for a replay; it records what happened "
        "to the project, not to its copies."))
    a = ap.parse_args()
    replay = a.root is not None
    if replay:
        ROOT = a.root.resolve()
        if not ROOT.is_dir():
            ap.error(f"--root {ROOT} is not a directory")
        print(f"REPLAY against {ROOT} (master ledger not appended)\n")
        globals()["append_master"] = lambda row: None
    if a.undo:
        return undo(a.last, a.phase, a.execute)
    if not a.ledger:
        ap.error("--ledger is required unless --undo")
    return apply(a.ledger, a.execute, a.skip_missing)


if __name__ == "__main__":
    sys.exit(main())
