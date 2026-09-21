"""Find which slides trigger PowerPoint's repair prompt, by bisection.

WHY THIS INSTEAD OF MORE VALIDATION
-----------------------------------
v8 passes every structural check I can run against the package:

  no dangling relationship targets        no orphan parts
  Content_Types covers every part         no duplicate or zero shape ids
  no duplicate zip entries                no control characters in any a:t
  font sizes all in range                 all 91 images valid, matching ext
  75 slides, 75 notesSlides               slide ids unique and in range

The backgrounds were the stated suspicion and they are ruled out: every
`p:bg` is a plain `<a:solidFill><a:srgbClr val="F7F8F6"/>`, with no
relationship reference of any kind, so there is nothing there to dangle.

So the defect is something PowerPoint checks and these tests do not. Rather
than keep guessing, this narrows it by halving: open the files it writes, note
which ones prompt for repair, and the offending slides are in that half. Three
rounds of this over 75 slides isolates a single slide.

USAGE
-----
    python docs/presentation/_repair_bisect_v8.py            # round 1, halves
    python docs/presentation/_repair_bisect_v8.py 1 38       # any explicit range

Round 1 writes two files. Open both.
  * If exactly one prompts, re-run on that half's range, split again.
  * If BOTH prompt, the fault is in something every slide shares -- the master,
    the layouts, or the theme -- not in slide content.
  * If NEITHER prompts, the fault is in the presentation part itself
    (sldIdLst, presentation.xml) rather than in any slide.

That last outcome is as informative as the first, which is why it is worth
doing before more code changes.

Writes into:
    docs/presentation/_repair_test/   (gitignored)
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "docs/presentation/WellSight_Presentation v8.pptx"
OUT = ROOT / "docs/presentation/_repair_test"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def subset(lo: int, hi: int, path: Path) -> int:
    """Write a copy holding only slides lo..hi inclusive, 1-based."""
    prs = Presentation(DECK)
    lst = prs.slides._sldIdLst
    keep = {s.slide_id for i, s in enumerate(prs.slides, 1) if lo <= i <= hi}
    by_id = {s.slide_id: s for s in prs.slides}
    for sid in list(lst):
        part = prs.part.rels[sid.get(RID)].target_part
        slide_id = int(sid.get("id"))
        if slide_id not in keep:
            lst.remove(sid)
            prs.part.drop_rel(sid.get(RID))
    prs.save(path)
    return len(Presentation(path).slides)


def main() -> int:
    n = len(Presentation(DECK).slides)
    if len(sys.argv) == 3:
        lo, hi = int(sys.argv[1]), int(sys.argv[2])
        ranges = [(lo, (lo + hi) // 2), ((lo + hi) // 2 + 1, hi)]
    else:
        ranges = [(1, n // 2), (n // 2 + 1, n)]

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    print(f"  {DECK.name}: {n} slides\n")
    for lo, hi in ranges:
        if lo > hi:
            continue
        p = OUT / f"slides_{lo:02d}_to_{hi:02d}.pptx"
        got = subset(lo, hi, p)
        print(f"  {p.name}   {got} slides")
    print(f"\n  {OUT}")
    print("\n  Open both. Then re-run with the range of whichever one prompts:")
    print(f"      python {Path(__file__).relative_to(ROOT).as_posix()} "
          f"{ranges[0][0]} {ranges[0][1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
