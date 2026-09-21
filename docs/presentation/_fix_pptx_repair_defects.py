"""Fix the two defects PowerPoint's repair pass actually found.

HOW THESE WERE IDENTIFIED
-------------------------
Not by guessing. The deck was opened, repaired, saved, and diffed against the
input with `_diff_repaired_pptx.py`. PowerPoint's own repair told us what it
objected to:

  1. It deleted 27 image relationships across 26 slides (slide 21 lost two,
     the rest one each).
  2. It deleted `notesSlides/notesSlide76.xml` outright, together with its
     rels part. That is the notes slide for the canopy slide added in v8.

Everything else in the diff is ordinary PowerPoint housekeeping: it re-encodes
embedded JPEGs as PNG and renumbers media parts. Shape counts on surviving
slides were unchanged, so no visible slide content was lost.

DEFECT 1 -- ORPHANED IMAGE RELATIONSHIPS
----------------------------------------
Mine. Several scripts re-lay a slide out by deleting every shape:

    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)

That removes the `p:pic` element but leaves the slide's relationship to the
image in its `.rels`. Adding a new picture then adds a second relationship, so
the slide declares two images and references one. Slide 21 was wiped twice, by
`_fix_chm_slide_for_1m_v7.py` and then `_build_v8_split_canopy_and_rrim.py`,
which is why it carried two orphans instead of one.

Fix: after removing shapes, drop every image relationship no `r:embed`,
`r:id` or `r:link` in the slide XML still refers to.

DEFECT 2 -- A NOTES SLIDE BUILT FROM THE WRONG TEMPLATE
-------------------------------------------------------
python-pptx builds a new notes slide from its own minimal template, which does
not match what PowerPoint writes. Comparing the generated one against any of
the deck's originals:

                        generated              PowerPoint's own
    shape order         body, sldImg, sldNum   sldImg, body, sldNum
    body placeholder    <p:ph type="body" idx="3"/>
                                               <p:ph type="body" sz="quarter" idx="3"/>
    sldNum placeholder  no sz                  sz="quarter"
    sldImg spLocks      noGrp only             noGrp, noRot, noChangeAspect

Fix: rebuild the generated notes slide from a healthy one in the same deck --
clone its shape skeleton, then move the text across. That guarantees the
structure matches whatever this deck's notes master expects, rather than
guessing at the schema.

Run:
    python docs/presentation/_fix_pptx_repair_defects.py <in.pptx> [out.pptx]
Default output is the input with " FIXED" before the extension.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

from pptx import Presentation

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
RT_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
USED = re.compile(r'r:(?:embed|id|link)="([^"]+)"')


def drop_orphan_image_rels(prs) -> int:
    """Remove image relationships no shape on the slide still references."""
    from lxml import etree
    dropped = 0
    for slide in prs.slides:
        xml = etree.tostring(slide._element).decode()
        used = set(USED.findall(xml))
        for rid, rel in list(slide.part.rels.items()):
            if rel.reltype == RT_IMAGE and rid not in used:
                slide.part.drop_rel(rid)
                dropped += 1
    return dropped


def notes_text(ns) -> list[str]:
    tf = ns.notes_text_frame
    return tf.text.split("\n") if tf is not None else []


def healthy_template(prs, suspect_parts):
    """A notes slide PowerPoint itself wrote, to copy the skeleton from."""
    for slide in prs.slides:
        if not slide.has_notes_slide:
            continue
        ns = slide.notes_slide
        if ns.part.partname in suspect_parts:
            continue
        tree = ns._element.find(f"{P}cSld/{P}spTree")
        kinds = [sp.find(f".//{P}ph") for sp in tree if sp.tag == f"{P}sp"]
        types = [k.get("type") for k in kinds if k is not None]
        if types[:2] == ["sldImg", "body"]:
            return ns
    return None


def rebuild_bad_notes(prs) -> list[str]:
    from lxml import etree
    """Re-make any notes slide whose skeleton is not PowerPoint's own."""
    bad = []
    for slide in prs.slides:
        if not slide.has_notes_slide:
            continue
        ns = slide.notes_slide
        tree = ns._element.find(f"{P}cSld/{P}spTree")
        types = []
        for sp in tree:
            if sp.tag != f"{P}sp":
                continue
            ph = sp.find(f".//{P}ph")
            types.append(ph.get("type") if ph is not None else None)
        if types[:2] != ["sldImg", "body"]:
            bad.append(slide)
    if not bad:
        return []

    suspect = {s.notes_slide.part.partname for s in bad}
    tmpl = healthy_template(prs, suspect)
    if tmpl is None:
        raise SystemExit("no healthy notes slide to copy a skeleton from")

    fixed = []
    for slide in bad:
        ns = slide.notes_slide
        lines = notes_text(ns)
        old_tree = ns._element.find(f"{P}cSld/{P}spTree")
        new_tree = copy.deepcopy(tmpl._element.find(f"{P}cSld/{P}spTree"))
        old_tree.getparent().replace(old_tree, new_tree)

        # Write the text straight into the cloned skeleton's body placeholder.
        # Going through ns.notes_text_frame here does NOT work: that object was
        # resolved against the tree we just detached, so the assignment lands on
        # an orphaned element and every rebuilt slide silently keeps the
        # TEMPLATE's notes. That bug shipped once and was caught by diffing the
        # note text before and after.
        body = None
        for sp in new_tree:
            if sp.tag != f"{P}sp":
                continue
            ph = sp.find(f".//{P}ph")
            if ph is not None and ph.get("type") == "body":
                body = sp
                break
        if body is None:
            raise SystemExit(f"cloned skeleton has no body placeholder")
        tx = body.find(f"{P}txBody")
        for para in tx.findall(f"{A}p"):
            tx.remove(para)
        for line in lines:
            p_el = etree.SubElement(tx, f"{A}p")
            if line:
                r_el = etree.SubElement(p_el, f"{A}r")
                t_el = etree.SubElement(r_el, f"{A}t")
                t_el.text = line
        fixed.append(str(ns.part.partname))
    return fixed


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = Path(sys.argv[1])
    dst = (Path(sys.argv[2]) if len(sys.argv) > 2
           else src.with_name(src.stem + " FIXED" + src.suffix))
    prs = Presentation(src)

    n = drop_orphan_image_rels(prs)
    print(f"  dropped {n} orphaned image relationship(s)")

    fixed = rebuild_bad_notes(prs)
    print(f"  rebuilt {len(fixed)} notes slide(s) from PowerPoint's own skeleton")
    for f in fixed:
        print(f"    {f}")

    prs.save(dst)

    # prove it
    out = Presentation(dst)
    from lxml import etree
    left = 0
    for slide in out.slides:
        xml = etree.tostring(slide._element).decode()
        used = set(USED.findall(xml))
        left += sum(1 for rid, rel in slide.part.rels.items()
                    if rel.reltype == RT_IMAGE and rid not in used)
    bad = 0
    for slide in out.slides:
        if not slide.has_notes_slide:
            continue
        tree = slide.notes_slide._element.find(f"{P}cSld/{P}spTree")
        types = [sp.find(f".//{P}ph").get("type")
                 for sp in tree if sp.tag == f"{P}sp"
                 and sp.find(f".//{P}ph") is not None]
        if types[:2] != ["sldImg", "body"]:
            bad += 1
    print(f"\n  after: {left} orphaned image rels, {bad} odd notes slides")
    print(f"  {len(out.slides)} slides")
    print(f"  {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
