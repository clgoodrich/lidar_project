"""v7 -> v8: canopy height and the RRIM stop borrowing each other's evidence.

THE RULE THIS ENFORCES
----------------------
Canopy height is discussed on the canopy-height slides and nowhere else. The
RRIM is discussed on the RRIM slides and nowhere else. Neither one argues its
case with the other's picture.

That was not true in v7. The canopy slide pointed forward to the RRIM section,
and the RRIM section opened with a slide ("Two different stripes, one
nickname") whose left-hand panel was a canopy-height raster. Both are removed.

WHAT CHANGES
------------
1. The canopy-height slide becomes two, in sequence:
     a  "Canopy height - the corn rows"   the rows, plain, nothing annotated.
                                          Let the room see them first.
     b  "Canopy height - what the rows are"  the same cells painted orange at
                                          0.5 m, beside 1 m where they are
                                          gone. 3.22% -> 0.00% in this window.
   Its forward reference to the RRIM section is gone, and so is the paragraph
   in its notes that explained the other phenomenon.

2. "Two different stripes, one nickname" is deleted. The one fact on it the
   RRIM section genuinely needs -- that the ground surface holds no empty cells
   at either resolution, so these stripes cannot be missing data -- moves onto
   the RRIM slide itself as a bullet, stated without reference to canopy
   height.

Slide count is unchanged at 75: one added, one removed.

Run:
    python docs/presentation/_build_v8_split_canopy_and_rrim.py
Reads:
    docs/presentation/WellSight_Presentation v7.pptx
Writes:
    docs/presentation/WellSight_Presentation v8.pptx
"""
from __future__ import annotations

import copy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/presentation/WellSight_Presentation v7.pptx"
DECK = ROOT / "docs/presentation/WellSight_Presentation v8.pptx"
FIGDIR = ROOT / "docs/presentation/figures_30to45min/v6"
PML = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

INK = RGBColor(0x14, 0x1A, 0x1F)
INK2 = RGBColor(0x54, 0x5C, 0x63)
ACCENT = RGBColor(0x00, 0x96, 0xC7)

CANOPY_TITLE = "Step 1: terrain derivatives"
DROP_TITLE = "Two different stripes, one nickname"
RRIM_TITLE = "The corn rows in the RRIM"

ROWS = dict(
    title="Step 1: terrain derivatives – canopy height",
    kicker="How tall are the green leafy things?",
    bullets=[
        "Take the top surface, subtract the ground, keep what is left",
        "Bright is tall. Dark is low.",
        "And there are stripes running across it",
    ],
    fig="chm_corn_rows_05_9t.png", ratio=0.970,
    notes=(
        "Canopy height. How tall are the trees.\n\n"
        "You get it by taking the top surface, subtracting the ground surface, "
        "and keeping whatever is left over. Bright is tall, dark is low.\n\n"
        "Do not explain the stripes yet. Let people notice them. Somebody "
        "usually asks whether they are rows of planted trees, which is a "
        "reasonable guess and wrong.\n\n"
        "The next slide says what they are."),
)

WHAT = dict(
    title="Step 1: terrain derivatives – what the rows are",
    kicker="Cells with nothing in them",
    bullets=[
        "Those stripes are not trees. They are cells where no return came "
        "back at all.",
        "Nothing was measured there, so there is nothing to draw",
        "3.22% of this window at 0.5 m.  0.00% at 1 m.",
        "The half-metre grid asked for finer detail than the survey "
        "delivered",
        "A wider cell always catches a return, so one metre closes them",
    ],
    fig="chm_corn_rows_are_empty_cells_9t.png", ratio=1.863,
    notes=(
        "Here is what those stripes actually are.\n\n"
        "The orange cells on the left are the ones holding no value. They land "
        "exactly on the stripes, which is the whole answer: the stripes are "
        "empty cells.\n\n"
        "No laser pulse came back there, so there is nothing to measure the "
        "height of.\n\n"
        "Why they line up like that: the scanner draws lines across the "
        "ground, and at half a metre some cells fall between those lines and "
        "catch nothing.\n\n"
        "Right panel is the same ground at one metre. A wider cell always "
        "catches a return, so the gaps close. Three point two percent down to "
        "zero.\n\n"
        "Nothing was invented or filled in. The grid simply stopped asking for "
        "detail the survey never delivered. That is why the terrain layers in "
        "this deck are built at one metre."),
)

#: the fact the deleted slide was carrying, restated without canopy height
RRIM_EXTRA = ("These are not missing data — the ground surface holds no "
              "empty cells at 0.5 m or at 1 m")


def rgb_runs(tf, runs):
    first = True
    for text, size, bold, colour, space in runs:
        if first and len(tf.paragraphs) and not tf.paragraphs[0].runs:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(space)
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = colour
        r.font.name = "Calibri"


def title_of(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def norm(s):
    return s.replace("–", "-").replace("—", "-").strip().lower()


def lay_out(slide, spec):
    """Wipe a slide and lay it out as title / left bullets / right figure."""
    keep_bg = slide._element.find(f"{PML}cSld").find(f"{PML}bg")
    bg = copy.deepcopy(keep_bg) if keep_bg is not None else None
    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)
    if bg is not None:
        cs = slide._element.find(f"{PML}cSld")
        if cs.find(f"{PML}bg") is None:
            cs.insert(0, bg)

    tb = slide.shapes.add_textbox(Inches(0.70), Inches(0.42),
                                  Inches(12.0), Inches(0.85))
    tb.text_frame.word_wrap = True
    rgb_runs(tb.text_frame, [(spec["title"], 27, True, ACCENT, 0)])

    body = slide.shapes.add_textbox(Inches(0.70), Inches(1.50),
                                    Inches(4.55), Inches(5.10))
    body.text_frame.word_wrap = True
    runs = [(spec["kicker"], 17, True, INK, 11)]
    for b in spec["bullets"]:
        runs.append(("•  " + b, 14, False, INK2, 7))
    rgb_runs(body.text_frame, runs)

    p = FIGDIR / spec["fig"]
    if not p.exists():
        raise SystemExit(f"figure missing: {p}")
    # fit inside the 5.6 in band beside the text, whichever limit binds first
    max_w, max_h = 7.70, 5.35
    w = min(max_w, max_h * spec["ratio"])
    h = w / spec["ratio"]
    slide.shapes.add_picture(str(p), Inches(5.45 + (max_w - w) / 2),
                             Inches(1.42 + (max_h - h) / 2),
                             width=Inches(w), height=Inches(h))

    foot = slide.shapes.add_textbox(Inches(0.70), Inches(7.00),
                                    Inches(11.0), Inches(0.42))
    foot.text_frame.word_wrap = True
    rgb_runs(foot.text_frame,
             [("Colton Goodrich  ·  University of Houston",
               12, False, INK2, 0)])
    slide.notes_slide.notes_text_frame.text = spec["notes"]


def main() -> int:
    prs = Presentation(SRC)
    lst = prs.slides._sldIdLst

    # ---- locate, before anything moves ---------------------------------
    canopy_i = next(i for i, s in enumerate(prs.slides)
                    if norm(title_of(s)).startswith(norm(CANOPY_TITLE))
                    and "canopy height" in norm(title_of(s)))
    drop = next(s for s in prs.slides if norm(title_of(s)) == norm(DROP_TITLE))
    rrim = next(s for s in prs.slides if norm(title_of(s)) == norm(RRIM_TITLE))

    # ---- 1. canopy slide becomes two -----------------------------------
    lay_out(prs.slides[canopy_i], ROWS)
    new = prs.slides.add_slide(prs.slides[canopy_i].slide_layout)
    lay_out(new, WHAT)
    node = list(lst)[-1]
    lst.remove(node)
    list(lst)[canopy_i].addnext(node)
    print(f"  slide {canopy_i + 1}: {ROWS['title']}")
    print(f"  slide {canopy_i + 2}: {WHAT['title']}  (new)")

    # ---- 2. the RRIM slide absorbs the one fact it needs ---------------
    texts = [sh for sh in rrim.shapes
             if sh.has_text_frame and sh.text_frame.text.strip()]
    body = max((sh for sh in texts if sh is not min(texts, key=lambda s: s.top)),
               key=lambda sh: sh.height)
    tf = body.text_frame
    last = tf.paragraphs[-1]
    p = tf.add_paragraph()
    p.alignment = PP_ALIGN.LEFT
    p.space_after = last.space_after
    r = p.add_run()
    r.text = "•  " + RRIM_EXTRA
    src_run = last.runs[0] if last.runs else None
    r.font.size = src_run.font.size if src_run else Pt(14)
    r.font.color.rgb = INK2
    r.font.name = "Calibri"
    print(f"  {RRIM_TITLE!r}: absorbed the not-missing-data fact")

    # ---- 3. drop the comparison slide ----------------------------------
    for sid in list(lst):
        if prs.part.rels[sid.get(RID)].target_part is drop.part:
            lst.remove(sid)
            prs.part.drop_rel(sid.get(RID))
            break
    print(f"  dropped: {DROP_TITLE}")

    prs.save(DECK)
    out = Presentation(DECK)
    print(f"\n  {len(out.slides)} slides")
    for i, s in enumerate(out.slides, 1):
        if 20 <= i <= 23 or 29 <= i <= 33:
            print(f"    {i}  {title_of(s)[:58]}")
    print(f"  {DECK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
