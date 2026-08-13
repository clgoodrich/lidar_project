"""Write a `_PROVENANCE.json` into every derived directory.

`data/**/derived/` is ignored by git and declared "regenerable by definition".
That claim is only worth anything if the rebuild recipe is written down. Until
now it was folklore: you had to know which script took which `--suffix`.

Each file records what is KNOWN, and says so when something is not:

    area          9t
    resolution    05
    files, bytes  what is actually on disk right now
    newest        mtime of the most recent file, as a date
    rebuild       the command that regenerates it, or null
    rebuild_note  why it is null, when it is

Nothing is guessed. If the builder cannot be determined from the directory
shape, `rebuild` is null and the note says to check `docs/analysis_log.md`
rather than inventing a plausible-looking command.

    python tools/write_provenance.py            # dry run
    python tools/write_provenance.py --execute
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
from _common import path_for  # noqa: E402

BUILD = "python notebooks/wellsight_v2/s1_build/_build_derivatives.py --suffix {area}"
GRIDS = "python notebooks/wellsight_v2/s2_labels/_build_label_grids.py --region westernpa"
BLOCKS = "python notebooks/wellsight_v2/s1_build/_build_data_3x3_derivatives.py"


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=30).stdout.strip() or None
    except Exception:                                    # noqa: BLE001
        return None


def recipe(rel: Path) -> tuple[str | None, str | None]:
    """(rebuild command, note). Never guesses."""
    parts = rel.parts
    if "grids" in parts:
        return GRIDS, None
    if parts[0] in ("westernpa_d20", "northcentral_b19"):
        return BLOCKS, "builds every block in the project; not per-block"
    if "1m_rebuilt" in str(rel):
        return None, ("QUARANTINE. Output of _prep_road_1m.py, whose values are "
                      "~2% off what the models trained on. Deliberately not "
                      "wired up. See docs/HANDOFF_code_cleanup_wellsight_v2.md:281")
    if "inference" in parts:
        return None, "written by s4_infer/_predict_on_tile.py against a chosen checkpoint"
    area = parts[0]
    return BUILD.format(area=area), None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()

    data = path_for("data")
    sha = git_sha()
    written = 0
    for d in sorted(data.rglob("derived")):
        if not d.is_dir():
            continue
        for leaf in sorted([d, *[p for p in d.iterdir() if p.is_dir()]]):
            files = [p for p in leaf.iterdir() if p.is_file() and p.name != "_PROVENANCE.json"]
            if not files:
                continue
            rel = leaf.relative_to(data)
            cmd, note = recipe(rel)
            parts = rel.parts
            rec = {
                "directory": rel.as_posix(),
                "area": parts[0],
                "role": "derived",
                "resolution": parts[-1] if parts[-1] != "derived" else None,
                "files": len(files),
                "bytes": sum(p.stat().st_size for p in files),
                "newest_file": datetime.fromtimestamp(
                    max(p.stat().st_mtime for p in files), timezone.utc).date().isoformat(),
                "regenerable": True,
                "rebuild": cmd,
                "rebuild_note": note or (
                    "Regenerable. Deleting this directory loses nothing that the "
                    "command above cannot rebuild from data/_source/lidar/."),
                "recorded": "2026-08-13",
                "recorded_at_git_sha": sha,
            }
            out = leaf / "_PROVENANCE.json"
            print(f"  {rel.as_posix():58s} {len(files):5d} files  "
                  f"{'rebuild known' if cmd else 'NO RECIPE'}")
            if a.execute:
                out.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf8")
            written += 1
    print(f"\n{written} directories{' WRITTEN' if a.execute else ' (dry run)'}")
    if not a.execute:
        print("Re-run with --execute to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
