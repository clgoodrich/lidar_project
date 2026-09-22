# -*- coding: utf-8 -*-
"""Correct the void denominator in v17, and re-embed slide 12's figure.

THE MISTAKE THIS UNDOES
-----------------------
The previous pass replaced "13.8% of the training area has no ground
measurement" with 45.2%, on the grounds that 36,628,564 of the 81,000,000 cells
in 9t hold no ground return. That measurement is right and the substitution was
wrong, because the two numbers have different denominators and 13.8% has the
defensible one.

    81,000,000   cells in the 9t bounding box at 0.5 m
    29,529,952   no return of ANY kind ever landed in them
    51,470,048   a return landed  <- the denominator that means something
    44,371,436   ...and it included a ground return
     7,098,612   ...and it did not          = 13.8% of 51,470,048
     2,857,002   of those filled by restoring the cut = 40.2%, two in five
     4,241,610   left                                 =  8.2% of 51,470,048

44,371,436 + 7,098,612 = 51,470,048 exactly, so the JSON and the rasters agree.

The 29.5 M never-sampled cells are a grid-spacing artefact, not a vendor
decision: ground returns sit 0.61 m apart and the grid asks every 0.5 m. Rolling
them into "no ground measurement" blames the survey for our own choice of cell
size. Source of the definition:
notebooks/wellsight_v2/s7_analysis/_recovered_ground_maps_9t.py line 767,
`inside = cnt_a > 0  # cells the laser actually reached`.

So 13.8% and 8.2% are restored, and each now states its denominator on the
slide -- which is what was missing in the first place and what made 13.8% look
unreconcilable with everything around it.

ALSO CORRECTED
--------------
"About a quarter of the holes close" was wrong in the other direction too.
2,857,002 of 7,098,612 is 40.2%. Two in five.

AND RE-EMBEDDED
---------------
Slide 12's card figure was regenerated so the 191 million card carries its
per-square rate (1.16 M across 165 squares), which is what lets an audience see
that it and slide 10's ten-square count describe the same survey.

Edits v17 in place. No new version.

Run:
    python docs/presentation/_fix_void_denominator_and_slide12_v17.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation

HERE = Path(__file__).resolve().parent
DECK = HERE / "WellSight_Presentation v17.pptx"
FIG12 = (HERE / "figures_30to45min/1_data_qa"
         / "data_qa_scan_angle_cut_numbers_9t.png")
SLIDE_12_TITLE = "Data QA – What the Cut Cost"

BULLET = "•  "

EDITS = [
    # -- slide 15 -----------------------------------------------------------
    (BULLET + "45.2% of 9t has no ground return in it — 36.6 of 81 "
     "million cells at 0.5 m",
     BULLET + "13.8% of the ground the laser reached has no measurement on it",
     "body"),
    # -- slide 17 -----------------------------------------------------------
    (BULLET + "45.2% of cells with no ground return, down to 41.7%",
     BULLET + "13.8% with no ground measurement, down to 8.2%",
     "body"),
    (BULLET + "2.9 million of the 36.6 million empty cells filled in",
     BULLET + "2.9 million of those 7.1 million holes filled in",
     "body"),
    (BULLET + "About one hole in thirteen closes. The rest is canopy the "
     "laser never got through.",
     BULLET + "Two holes in five close. The rest is canopy the laser never "
     "got through.",
     "body"),
    ("The void drops from 45.2% of 9t to 41.7%. That is 2.9 million cells",
     "The void drops from 13.8% of the ground the laser reached to 8.2%. "
     "That is 2.9 million cells",
     "notes"),
]

#: text that must NOT survive this pass
STALE = ["45.2%", "41.7%", "36.6 million empty", "one hole in thirteen"]


def title_of(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def edit_body(slide, old, new):
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for p in sh.text_frame.paragraphs:
            if p.text.strip() != old.strip():
                continue
            runs = list(p.runs)
            if not runs:
                continue
            runs[0].text = new
            for r in runs[1:]:
                r._r.getparent().remove(r._r)
            return True
    return False


def edit_notes(slide, old, new):
    if not slide.has_notes_slide:
        return False
    tf = slide.notes_slide.notes_text_frame
    if old not in tf.text:
        return False
    tf.text = tf.text.replace(old, new, 1)
    return True


def main() -> int:
    for p in (DECK, FIG12):
        if not p.exists():
            raise SystemExit(f"missing: {p}")
    prs = Presentation(DECK)
    n_before = len(prs.slides)
    slides = list(prs.slides)

    misses = []
    for old, new, where in EDITS:
        hit = 0
        for s in slides:
            if where == "body" and edit_body(s, old, new):
                hit += 1
            elif where == "notes" and edit_notes(s, old, new):
                hit += 1
        if hit:
            print(f"  ok  [{where:5s}] {new[:74]}")
        else:
            misses.append(f"[{where}] {old[:70]}")
    if misses:
        raise SystemExit("targets not found:\n  " + "\n  ".join(misses))

    # ---- slide 12 figure -------------------------------------------------
    s12 = next(s for s in slides if title_of(s).strip() == SLIDE_12_TITLE)
    pics = [sh for sh in s12.shapes if sh.shape_type == 13]
    if len(pics) != 1:
        raise SystemExit(f"slide 12 has {len(pics)} pictures, expected 1")
    old_pic = pics[0]
    old_sha = old_pic.image.sha1[:12]
    left, top, width, height = (old_pic.left, old_pic.top,
                                old_pic.width, old_pic.height)
    with Image.open(FIG12) as im:
        w, h = im.size
    if abs((w / h) - (width / height)) / (w / h) > 0.02:
        raise SystemExit("aspect changed; reposition deliberately")
    old_pic._element.getparent().remove(old_pic._element)
    new_pic = s12.shapes.add_picture(str(FIG12), left, top,
                                     width=width, height=height)
    print(f"\n  slide 12 figure {old_sha} -> {new_pic.image.sha1[:12]}")
    print("     191 M card now carries 1.16 M per square")

    prs.save(DECK)

    out = list(Presentation(DECK).slides)
    if len(out) != n_before:
        raise SystemExit("slide count changed")
    stale = []
    for i, s in enumerate(out, 1):
        txt = "\n".join(sh.text_frame.text for sh in s.shapes
                        if sh.has_text_frame)
        stale += [f"slide {i}: {bad}" for bad in STALE if bad in txt]
    print(f"\n  {len(out)} slides, unchanged")
    print(f"  stale text left on a slide: {stale if stale else 'none'}")
    print(f"  {DECK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
