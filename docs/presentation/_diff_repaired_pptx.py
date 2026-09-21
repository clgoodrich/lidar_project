"""Ask PowerPoint what it removed, by diffing the repaired file against ours.

WHY THIS, RATHER THAN MORE VALIDATION
-------------------------------------
Every structural check available here passes on v8:

  no dangling relationship targets      no orphan parts
  Content_Types covers every part       no duplicate / zero shape ids
  no duplicate zip entries              no control chars in any a:t
  font sizes in range                   91/91 images valid, ext matches magic
  75 slides / 75 notesSlides            slide ids unique and in range
  p:bg is plain solidFill + effectLst   a:p ordering correct everywhere
  txBody always starts with bodyPr      no blip missing r:embed
  no AlternateContent, no mc:Ignorable  no shape missing spPr

Two hypotheses were tested and killed along the way: the slide backgrounds
(they carry no relationship, so nothing can dangle) and the generated notes
slides (they do have the sldImg placeholder -- an earlier dump only looked
truncated).

So whatever PowerPoint objects to, it is not something these tests know how to
look for. But PowerPoint itself knows exactly: when it repairs, it DROPS the
offending part and keeps the rest. Diffing the repaired file against the input
names the casualty directly.

HOW TO USE
----------
1. Open the file in PowerPoint, click Repair.
2. File > Save As, next to the original, e.g. "v8 REPAIRED.pptx".
3. Run:
       python docs/presentation/_diff_repaired_pptx.py \\
           "docs/presentation/WellSight_Presentation v8.pptx" \\
           "docs/presentation/WellSight_Presentation v8 REPAIRED.pptx"

It reports parts that disappeared, parts that appeared, slides whose shape
count changed, and relationships that were dropped. Whatever shows up is the
thing to fix.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
SLIDE = re.compile(r"ppt/slides/slide\d+\.xml$")


def shapes_per_slide(z):
    out = {}
    for n in sorted(x for x in z.namelist() if SLIDE.match(x)):
        root = etree.fromstring(z.read(n))
        tree = root.find(f"{P}cSld/{P}spTree")
        kinds = {}
        for kid in tree:
            tag = etree.QName(kid).localname
            if tag in ("sp", "pic", "graphicFrame", "grpSp", "cxnSp"):
                kinds[tag] = kinds.get(tag, 0) + 1
        out[n] = kinds
    return out


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    a_p, b_p = Path(sys.argv[1]), Path(sys.argv[2])
    for p in (a_p, b_p):
        if not p.exists():
            raise SystemExit(f"missing: {p}")
    a, b = zipfile.ZipFile(a_p), zipfile.ZipFile(b_p)
    an, bn = set(a.namelist()), set(b.namelist())

    print(f"  ours     {a_p.name}   {len(an)} parts")
    print(f"  repaired {b_p.name}   {len(bn)} parts\n")

    gone = sorted(an - bn)
    added = sorted(bn - an)
    print(f"  PARTS POWERPOINT REMOVED: {len(gone)}")
    for g in gone:
        print(f"    - {g}")
    print(f"\n  parts it added: {len(added)}")
    for g in added[:20]:
        print(f"    + {g}")

    # slides that survived but lost shapes
    sa, sb = shapes_per_slide(a), shapes_per_slide(b)
    print("\n  slides whose shape counts changed:")
    changed = 0
    for n in sorted(set(sa) & set(sb)):
        if sa[n] != sb[n]:
            changed += 1
            print(f"    {n}:  ours {sa[n]}   repaired {sb[n]}")
    if not changed:
        print("    (none)")

    # relationship counts per part
    print("\n  parts whose relationship count changed:")
    diffs = 0
    for n in sorted(x for x in an & bn if x.endswith(".rels")):
        ca = len(etree.fromstring(a.read(n)))
        cb = len(etree.fromstring(b.read(n)))
        if ca != cb:
            diffs += 1
            print(f"    {n}:  ours {ca}   repaired {cb}")
    if not diffs:
        print("    (none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
