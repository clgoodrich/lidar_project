# -*- coding: utf-8 -*-
"""The one script that turns the user's current v15 into v17.

Re-run this after every edit the user makes to v15. It supersedes
_build_v17_reconcile_all_counts.py, _refresh_slide20_void_contrast_v17.py and
_fix_void_denominator_and_slide12_v17.py, which were three passes over the same
deck and are kept only as the record of how each change was reasoned.

Everything here is matched on slide TITLE or on exact paragraph text, never on
slide index, so the user inserting or deleting slides does not break it. Any
target that cannot be found stops the run rather than being skipped quietly.

--------------------------------------------------------------------------
1. THE COUNTS, EACH WITH ITS SCOPE
--------------------------------------------------------------------------
The Data QA section quoted counts from five scopes and named none of them,
which is why they read as contradictory:

    slide 10   113.5 million points          10 map squares
    slide 11   5.6 million                   4 map squares
    slide 12   190.9 million (in the figure) 165 of 177 squares, whole block
    slides 15-17, 21                         9t alone
    slides 18, 20                            one cross-section line, one window

Two were wrong, not merely unlabelled:

  * Slide 10's body says "nine tiles" while its own notes say "ten". The source
    is ten -- nonground_classification_and_scan_angle_cut.md line 30,
    113,556,364 points.
  * Slide 17 says "about a quarter of the holes close". It is 2,857,002 of
    7,098,612, which is 40.2%. Two in five.

--------------------------------------------------------------------------
2. WHY 13.8% IS CORRECT AND STAYS
--------------------------------------------------------------------------
An earlier pass replaced 13.8% with 45.2% and that was a mistake, corrected
here. Both numbers are real; they have different denominators.

    81,000,000   cells in the 9t bounding box at 0.5 m
    29,529,952   no return of ANY kind ever landed in them
    51,470,048   a return landed  <- the denominator that means something
    44,371,436   ...and it included a ground return
     7,098,612   ...and it did not          = 13.8%
     2,857,002   filled by restoring the cut = 40.2% of those, two in five
     4,241,610   left                        =  8.2%

44,371,436 + 7,098,612 = 51,470,048 exactly, so the summary JSON and the
rasters agree to the cell.

The 29.5 M never-sampled cells are a grid-spacing matter, not a vendor
decision: ground returns sit 0.61 m apart and the grid asks every 0.5 m.
Counting them as "no ground measurement" blames the survey for our own choice
of cell size. Definition source:
notebooks/wellsight_v2/s7_analysis/_recovered_ground_maps_9t.py line 767,
`inside = cnt_a > 0  # cells the laser actually reached`.

So 13.8% and 8.2% stand, and each now states its denominator on the slide --
which is the thing that was missing and what made 13.8% look irreconcilable
with every number around it.

--------------------------------------------------------------------------
3. THE THREE FIGURES
--------------------------------------------------------------------------
slide 12  the card stack, rebuilt so the 191 million card carries its
          per-square rate (1.16 M across 165 squares). Without it nobody can
          see that 191 M and slide 10's 113.5 M describe the same survey.
slide 14  the flight-block bars without the Venango 2011-09 row. That delivery
          never populated the scan angle, so its bar meant "cannot be checked"
          among bars that mean a measured angle.
slide 20  the void class now separates by hue AND by contrast. A flat orange
          wash at alpha 0.30 did not survive 52% coverage: the whole panel went
          warm and the boundary vanished.

--------------------------------------------------------------------------
4. SLIDE 57
--------------------------------------------------------------------------
Speaker notes gain the 128 m training patch and the 30 m jitter, appended to
whatever note is already there.

Run:
    python docs/presentation/_build_v17_from_v15.py
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
FIGDIR = HERE / "figures_30to45min"

BULLET = "•  "
EMDASH = "—"

#: (old, new, "body" | "notes"). Matched exactly; a miss aborts the run.
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
    # -- slide 15: keep 13.8%, say what it is a share OF --------------------
    (BULLET + "13.8% of the training area has nothing under it.",
     BULLET + "13.8% of the ground the laser reached has no measurement on it",
     "body"),
    # -- slide 16: correct, but say where ----------------------------------
    (BULLET + "13.7 million ground measurements.",
     BULLET + "13.7 million ground measurements, inside 9t alone",
     "body"),
    ("13.7 million ground measurements.",
     "13.7 million ground measurements, inside 9t alone.",
     "notes"),
    # -- slide 17: keep the rates, fix the fraction ------------------------
    (BULLET + "13.8% with no measurement, down to 8.2%.",
     BULLET + "13.8% with no ground measurement, down to 8.2%",
     "body"),
    (BULLET + "2.9 million cells filled in.",
     BULLET + "2.9 million of those 7.1 million holes filled in",
     "body"),
    (BULLET + "About a quarter of the holes close. The rest are canopy.",
     BULLET + "Two holes in five close. The rest is canopy the laser never "
     "got through.",
     "body"),
    # -- slide 21: correct, but say the grid -------------------------------
    (BULLET + "44.4 million cells already had ground. 2.9 million were filled.",
     BULLET + "In 9t at 0.5 m: 44.4 million cells already had ground, 2.9 "
     "million were filled",
     "body"),
    # -- slides 34-36: the corn rows are NOT tens of centimetres -----------
    # Measured twice, independently: 0.91 cm across the nine hand-drawn rows
    # (_cornrow_rows_measured_9t.py) and 0.70 cm on the cross-strike profile
    # (_cornrow_lrm_cross_strike_9t.py), both 5-95%. Slide 37 already said
    # "under a centimetre" and was right. "Tens of centimetres" was out by
    # roughly thirty times.
    (BULLET + "Their size is tens of centimetres. A pit is a 0.7 m dish.",
     BULLET + "They stand under a centimetre tall. A pit is a 0.7 m dish.",
     "body"),
    # The old claim followed from the wrong number: a 0.9 cm ripple and a
    # 0.7 m pit are not the same size, they are seventy times apart. What IS
    # true is that they occupy the same SPACING, and that the layers the model
    # reads respond to shape rather than to height.
    (BULLET + "So the artefact and the signal we are hunting are the same "
     "size. That is why it matters.",
     BULLET + "They are far shallower than a pit, but they repeat every "
     "3.35 m — the width of the pit rims we are looking for",
     "body"),
    ("Their size is tens of centimetres. A collapse pit is a dish about "
     "0.7 m deep.",
     "They stand under a centimetre tall, measured two ways: 0.91 cm across "
     "the nine rows drawn by hand, 0.70 cm on the cross-strike profile. A "
     "collapse pit is a dish about 0.7 m deep, so the rows are far shallower.",
     "notes"),
    ("So the artefact and the target are the same size, which is why it "
     "matters here",
     "They are not the same depth as a pit. What they share is spacing: a "
     "crest every 3.35 m, which is the width of the rims we look for. And "
     "every layer the model reads -- local relief, openness, hillshade -- "
     "measures shape, not height, so a ripple this shallow still prints on "
     "them",
     "notes"),
    ("that layer is elevation with the hillside subtracted, so a few "
     "centimetres of ripple is most of what is left.",
     "that layer is elevation with the hillside subtracted, so a ripple of "
     "well under a centimetre is most of what is left.",
     "notes"),
]

#: title -> figure. Position and box are inherited from the picture replaced.
#: "fit" reflows the height to the new aspect instead of stretching.
FIGURES = {
    "Data QA – What the Cut Cost":
        (FIGDIR / "1_data_qa/data_qa_scan_angle_cut_numbers_9t.png", "keep"),
    "Data QA — one survey, not all of them":
        (FIGDIR / "v6/where_ground_stops_by_flight_block_excl2011_9t.png",
         "fit"),
    "Data QA — the surface, built both ways":
        (FIGDIR / "v6/dem_with_and_without_deleted_returns_9t.png", "keep"),
}

SLIDE_57_TITLE = "Model building — does a bigger network help?"
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

#: text that must not survive, from either the original deck or a bad pass
STALE = ["across nine tiles", "across four tiles", "a quarter of the holes",
         "45.2%", "41.7%", "one hole in thirteen", "tens of centimetres",
         "are the same size"]


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


def swap_figure(slide, png, mode):
    pics = [sh for sh in slide.shapes if sh.shape_type == 13]
    if len(pics) != 1:
        raise SystemExit(f"{title_of(slide)!r} has {len(pics)} pictures, "
                         "expected exactly 1")
    old = pics[0]
    left, top, width, height = old.left, old.top, old.width, old.height
    with Image.open(png) as im:
        w, h = im.size
    if mode == "fit":
        height = Emu(int(width / (w / h)))
    elif abs((w / h) - (width / height)) / (w / h) > 0.02:
        raise SystemExit(f"{png.name}: aspect changed and mode is 'keep'; "
                         "switch to 'fit' or reposition deliberately")
    old_sha = old.image.sha1[:12]
    old._element.getparent().remove(old._element)
    new = slide.shapes.add_picture(str(png), left, top,
                                   width=width, height=height)
    return old_sha, new.image.sha1[:12], width, height


def main() -> int:
    for p in [SRC] + [f for f, _ in FIGURES.values()]:
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    prs = Presentation(SRC)
    n_before = len(prs.slides)
    slides = list(prs.slides)
    print(f"  reading v15: {n_before} slides\n")

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
            print(f"  ok  [{where:5s}] {new[:72]}")
        else:
            misses.append(f"[{where}] {old[:68]}")
    if misses:
        raise SystemExit("targets not found in v15, so it has moved:\n  "
                         + "\n  ".join(misses))

    # ---- 2. the figures --------------------------------------------------
    print()
    for tl, (png, mode) in FIGURES.items():
        hits = [s for s in slides if title_of(s).strip() == tl]
        if len(hits) != 1:
            raise SystemExit(f"expected one {tl!r}, found {len(hits)}")
        a, b, wd, ht = swap_figure(hits[0], png, mode)
        print(f"  fig {a} -> {b}  {png.name}")
        print(f"      {wd/914400:.2f} x {ht/914400:.2f} in  ({mode})")

    # ---- 3. slide 57 -----------------------------------------------------
    s57 = [s for s in slides if title_of(s).strip() == SLIDE_57_TITLE]
    if len(s57) != 1:
        raise SystemExit(f"expected one {SLIDE_57_TITLE!r}, found {len(s57)}")
    tf = s57[0].notes_slide.notes_text_frame
    if "jitter" in tf.text.lower():
        print("\n  slide 57 already explains jitter, left alone")
    else:
        tf.text = tf.text.rstrip() + "\n\n" + PATCH_NOTE
        print("\n  slide 57 notes gain the 128 m patch and 30 m jitter")

    prs.save(DST)

    # ---- verify ----------------------------------------------------------
    out = list(Presentation(DST).slides)
    if len(out) != n_before:
        raise SystemExit(f"slide count {n_before} -> {len(out)}; not intended")
    stale = []
    for i, s in enumerate(out, 1):
        txt = "\n".join(sh.text_frame.text for sh in s.shapes
                        if sh.has_text_frame)
        stale += [f"slide {i}: {bad}" for bad in STALE if bad in txt]
    print(f"\n  {len(out)} slides in, {len(out)} out")
    print(f"  stale text left on a slide: {stale if stale else 'none'}")
    print(f"  {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
