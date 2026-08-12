"""Plan the archive moves: parked research threads out of the working tree.

Archiving here means MOVED, with a manifest row, never deleted. An archive
without a manifest is just a different kind of mess, so every entry records
what it was, when it moved, why, and what replaced it if anything.

APPROVED 2026-08-12
    Permian / Ramachandran   data/external/ramachandran_2024, label_grids/permian_*
                             8.3 GB, 87,538 files -- 86% of the repository's
                             entire file count. Every backup and every `find`
                             walks it.
    Barlow FINESST           barlow/, barlow_data/
                             1.5 GB, 911 files. Proposal submitted.

NOT ARCHIVED, deliberately
    McKean (mckean_sw_*, mkf_*) was set aside per advisor 2026-07, but
    `mkf_road_1m` fed the `cldice_mkf` sweep variant that is still on the
    leaderboard. Not asked about, so not assumed.

THIS IS A RESEARCH DECISION, NOT HOUSEKEEPING
These threads are quiet because a human stopped, not because something
superseded them. That is why they go to 99_archive/parked/ rather than
99_archive/superseded/ -- the distinction is the whole point of the directory.

.gitignore RE-ANCHORING
Rules anchored to the old locations stop matching the moment the files move,
and a stale rule is silent. Affected rules are listed in the plan output and
must be updated in the SAME change that performs the move.

Outputs:
    docs/_ledgers/phase_archive_moves.csv   ledger for tools/apply_moves.py
    docs/phase_archive_plan.md     what moves, sizes, and the gitignore work

Reproduce:
  python tools/plan_archive.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "_ledgers" / "phase_archive_moves.csv"
PLAN = ROOT / "docs" / "phase_archive_plan.md"
ARCHIVE = "data/99_archive/parked"

TARGETS = [
    ("data/external/ramachandran_2024", "permian_ramachandran/ramachandran_2024",
     "Texas/Permian orphan-well thread, parked 2026-08-12. 87,535 NAIP chips."),
    ("label_grids/permian_01", "permian_ramachandran/label_grids_permian_01",
     "Permian label grid, parked 2026-08-12."),
    ("label_grids/permian_02", "permian_ramachandran/label_grids_permian_02",
     "Permian label grid, parked 2026-08-12."),
    ("label_grids/permian_03", "permian_ramachandran/label_grids_permian_03",
     "Permian label grid, parked 2026-08-12."),
    ("label_grids/permian_04", "permian_ramachandran/label_grids_permian_04",
     "Permian label grid, parked 2026-08-12."),
    ("barlow", "barlow_finesst/barlow",
     "FINESST proposal material, submitted. Not lidar analysis."),
    ("barlow_data", "barlow_finesst/barlow_data",
     "Empty; ~50 GB .gitignore reservation released."),
]

# Rules in .gitignore that are anchored to a path being moved.
GITIGNORE_ANCHORS = [
    "data/external/ramachandran_2024/naip_chips/",
    "data/external/ramachandran_2024/naip_chips_pilot/",
    "data/external/ramachandran_2024/permian_denver_data.zip",
    "label_grids/permian_01/pad_unet_xfer/",
    "/barlow_data/",
    "barlow/docs/BARLOW-DISSERTATION-2026.pdf",
    "barlow/docs/BARLOW-DISSERTATION-2026_sidebyside*.pdf",
    "barlow/docs/BARLOW-DISSERTATION-2026_readalong.epub",
    "barlow/Shapefiles/",
    "barlow/MDV_Resources.docx",
]


def walk(base: Path):
    n = b = 0
    for p in base.rglob("*"):
        try:
            if p.is_file():
                n += 1
                b += p.stat().st_size
        except OSError:
            pass
    return n, b


def main() -> int:
    rows, lines, tot_n, tot_b = [], [], 0, 0
    lines += ["# Archive plan — parked research threads", "",
              "Moved, never deleted. Reversible with "
              "`tools/apply_moves.py --undo --phase archive`.", "",
              "| Source | Destination | files | GB |", "|---|---|---:|---:|"]

    for src, dst, why in TARGETS:
        s = ROOT / src
        if not s.exists():
            lines.append(f"| `{src}` | _missing, skipped_ | - | - |")
            continue
        n, b = walk(s)
        tot_n += n
        tot_b += b
        lines.append(f"| `{src}` | `{ARCHIVE}/{dst}` | {n:,} | {b/2**30:.2f} |")
        # move the directory itself, as one operation
        rows.append(dict(old_path=src, new_path=f"{ARCHIVE}/{dst}",
                         phase="archive", reason=why))

    lines += ["", f"**Total: {tot_n:,} files, {tot_b/2**30:.2f} GB**", "",
              "## .gitignore rules that must be re-anchored", "",
              "A rule anchored to the old location stops matching the moment "
              "the files move, and it fails silently. These must be updated in "
              "the same change:", ""]
    lines += [f"- `{r}`" for r in GITIGNORE_ANCHORS]
    lines += ["", "The simplest correct fix is one recursive rule for the whole "
              "archive tree, since everything in it is parked and regenerable "
              "or externally sourced:", "", "```", "data/99_archive/**", "```",
              "", "with the manifest and any small text records force-added."]

    with open(LEDGER, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["old_path", "new_path", "phase", "reason"])
        w.writeheader(); w.writerows(rows)
    PLAN.write_text("\n".join(lines) + "\n", encoding="utf8")

    print(f"{len(rows)} directories to archive, {tot_n:,} files, "
          f"{tot_b/2**30:.2f} GB")
    for r in rows:
        print(f"  {r['old_path']:<38} -> {r['new_path']}")
    print(f"wrote {LEDGER}\nwrote {PLAN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
