# -*- coding: utf-8 -*-
"""v15 (user-edited) -> v17: put every point and cell count on a stated scope.

THE PROBLEM
-----------
The Data QA section quotes counts from five different scopes and never names
any of them, so a listener doing arithmetic concludes the numbers are wrong:

    slide 10   113.5 million points          10 map squares
    slide 11   5.6 million                   4 map squares
    slide 12   190.9 million (in the figure) 165 of 177 squares, whole block
    slides 15-17, 21                         9t alone, 9 squares
    slides 18, 20                            one cross-section line, one window

Each was right where it was measured. Together they read as chaos.

WHAT WAS ACTUALLY WRONG, NOT MERELY UNLABELLED
-----------------------------------------------
1. Slide 10 body says "nine tiles"; its own speaker notes say "ten tiles". The
   source is 10 -- nonground_classification_and_scan_angle_cut.md line 30,
   113,556,364 points. The body was edited and the notes were not.

2. Slides 15 and 17 quote 13.8% of the area with no ground measurement, and 17
   quotes it falling to 8.2%. Neither describes 9t. Measured on 9t at 0.5 m,
   36,628,564 of 81,000,000 cells hold no ground return: 45.2%, falling to
   41.7% once the discarded returns are restored. The 13.8/8.2 pair comes from
   the SMRF reclassification experiment on two different tiles, gridded with
   writers.gdal, which leaves real voids. The 9t surfaces on these slides are
   TIN-based and measure 0.00% void both ways, which slide 20 already states.
   So the bullet and the figure were describing different rasters.

3. Slide 17 says about a quarter of the holes close. Measured: 2,857,002 of
   36,628,564 empty cells, which is 7.8%. About one in thirteen.

VERIFIED CORRECT, ONLY MISSING THEIR SCOPE
-------------------------------------------
    slide 16   13,746,698 recovered ground returns in 9t  -> "13.7 million"
    slide 21   44,371,436 cells with vendor ground        -> "44.4 million"
    slide 21    2,857,002 void cells filled               -> "2.9 million"

All measured from data/9t/results/recovered_ground_9t/ ,
count_vendorground_9t_0p5m.tif and
count_recoveredground_slope0p35_9t_0p5m.tif.

ALSO IN THIS PASS
-----------------
* Slide 14 takes the flight-block figure without the 2011 Venango row. That
  delivery records no scan angle, so its bar meant "cannot be checked" inside a
  chart where every other bar means a measured angle.
* Slide 57 speaker notes gain the 128 m training patch and the 30 m jitter.

Built from the user's v15 as it stands, so their own edits carry through.

Run:
    python docs/presentation/_build_v17_reconcile_all_counts.py
Reads:  docs/presentation/WellSight_Presentation v15.pptx
Writes: docs/presentation/WellSight_Presentation v17.pptx
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Emu

HERE = Path(__file__).resolve().parent
SRC = HERE / "WellSight_Presentation v15.pptx"
DST = HERE / "WellSight_Presentation v17.pptx"
NEWFIG = (HERE / "figures_30to45min/v6"
          / "where_ground_stops_by_flight_block_excl2011_9t.png")

SLIDE_14_TITLE = "Data QA — one survey, not all of them"
SLIDE_57_TITLE = "Model building — does a bigger network help?"

BULLET = "•  "
EMDASH = "—"

#: (old, new, where) with where in {"body", "notes"}.
EDITS = [
    # -- slide 10: body and notes disagreed on the count -------------------
    (BULLET + "113.5 million points across nine tiles",
     BULLET + "113.5 million points across ten map squares",
     "body"),
    ("The delivery is 113.5 million points over ten tiles.",
     "The delivery is 113.5 million points over ten map squares. That is the "
     "audit set, wider than the nine squares of 9t that the rest of the talk "
     "uses.",
     "notes"),
    # -- slide 11: name the scope ------------------------------------------
    (BULLET + "5.6 million of them, across four tiles",
     BULLET + "5.6 million of them, across four of those map squares",
     "body"),
    ("There are 5.6 million of them across four tiles.",
     "There are 5.6 million of them across four of those map squares.",
     "notes"),
    # -- slide 15: 13.8% is not a 9t number --------------------------------
    (BULLET + "13.8% of the training area has nothing under it.",
     BULLET + "45.2% of 9t has no ground return in it " + EMDASH
     + " 36.6 of 81 million cells at 0.5 m",
     "body"),
    # -- slide 16: correct, but say where ----------------------------------
    (BULLET + "13.7 million ground measurements.",
     BULLET + "13.7 million ground measurements, inside 9t alone",
     "body"),
    ("13.7 million ground measurements.",
     "13.7 million ground measurements, inside 9t alone.",
     "notes"),
    # -- slide 17: wrong rate, wrong fraction ------------------------------
    (BULLET + "13.8% with no measurement, down to 8.2%.",
     BULLET + "45.2% of cells with no ground return, down to 41.7%",
     "body"),
    (BULLET + "2.9 million cells filled in.",
     BULLET + "2.9 million of the 36.6 million empty cells filled in",
     "body"),
    (BULLET + "About a quarter of the holes close. The rest are canopy.",
     BULLET + "About one hole in thirteen closes. The rest is canopy the "
     "laser never got through.",
     "body"),
    ("The void drops from 13.8% of the area to 8.2%. That is 2.9 million cells",
     "The void drops from 45.2% of 9t to 41.7%. That is 2.9 million cells",
     "notes"),
    # -- slide 21: correct, but say the grid -------------------------------
    (BULLET + "44.4 million cells already had ground. 2.9 million were filled.",
     BULLET + "In 9t at 0.5 m: 44.4 million cells already had ground, 2.9 "
     "million were filled",
     "body"),
]

PATCH_NOTE = (
    "If asked what a training patch is:\n\n"
    "The tile is too big to feed a network at once, so training happens on "
    "small square cut-outs. Each one is 256 pixels at 0.5 m, which is 128 m on "
    "the ground.\n\n"
    "Patches are centred on annotated pits, otherwise almost every patch would "
    "be empty forest.\n\n"
    "The jitter is the important half. Without it the pit sits dead centre in "
    "every single patch, and the network can learn “the answer is in the "
    "middle” instead of what a pit looks like. So each patch centre is "
    "shifted by a random amount up to 30 m before it is cut. The pit lands "
    "somewhere different every time it is seen.\n\n"
    "One guard goes with it. A jittered patch is clipped to the training "
    "blocks, so a shifted patch cannot reach across the line into the held-out "
    "fold."
)

STALE = ["13.8%", "8.2%", "across nine tiles", "across four tiles",
         "a quarter of the holes"]


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
    for p in (SRC, NEWFIG):
        if not p.exists():
            raise SystemExit(f"missing: {p}")
    prs = Presentation(SRC)
    n_before = len(prs.slides)
    slides = list(prs.slides)

    # ---- 1. the counts ---------------------------------------------------
    misses = []
    for old, new, where in EDITS:
        hit = 0
        for s in slides:
            if where == "body" and edit_body(s, old, new):
                hit += 1
            elif where == "notes" and edit_notes(s, old, new):
                hit += 1
        if hit:
            print(f"  ok  [{where:5s}] {new[:76]}")
        else:
            misses.append(f"[{where}] {old[:70]}")
    if misses:
        raise SystemExit("targets not found, so the deck has moved:\n  "
                         + "\n  ".join(misses))

    # ---- 2. slide 14 figure ---------------------------------------------
    s14 = next(s for s in slides if title_of(s).strip() == SLIDE_14_TITLE)
    pics = [sh for sh in s14.shapes if sh.shape_type == 13]
    if len(pics) != 1:
        raise SystemExit(f"slide 14 has {len(pics)} pictures, expected 1")
    old_pic = pics[0]
    left, top, width, old_h = (old_pic.left, old_pic.top,
                               old_pic.width, old_pic.height)
    with Image.open(NEWFIG) as im:
        ratio = im.size[0] / im.size[1]
    # Keep the width and the top-left corner. The new figure carries three rows
    # instead of four, so let its height follow its own aspect rather than
    # stretching three rows to fill a four-row box.
    new_h = Emu(int(width / ratio))
    old_pic._element.getparent().remove(old_pic._element)
    s14.shapes.add_picture(str(NEWFIG), left, top, width=width, height=new_h)
    print(f"\n  slide 14 figure -> {NEWFIG.name}")
    print(f"     height {old_h / 914400:.2f}in -> {new_h / 914400:.2f}in "
          "(2011 row removed)")

    # ---- 3. slide 57 note -----------------------------------------------
    s57 = next(s for s in slides if title_of(s).strip() == SLIDE_57_TITLE)
    tf = s57.notes_slide.notes_text_frame
    if "jitter" in tf.text.lower():
        print("  slide 57 already explains jitter, left alone")
    else:
        tf.text = tf.text.rstrip() + "\n\n" + PATCH_NOTE
        print("  slide 57 notes gain the 128 m patch and 30 m jitter")

    prs.save(DST)

    # ---- verify ----------------------------------------------------------
    out = list(Presentation(DST).slides)
    if len(out) != n_before:
        raise SystemExit("slide count changed; that was not the intent")
    stale = []
    for i, s in enumerate(out, 1):
        txt = "\n".join(sh.text_frame.text for sh in s.shapes
                        if sh.has_text_frame)
        stale += [f"slide {i}: {bad}" for bad in STALE if bad in txt]
    print(f"\n  {len(out)} slides, unchanged")
    print(f"  stale figures left on a slide: {stale if stale else 'none'}")
    print(f"  {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
