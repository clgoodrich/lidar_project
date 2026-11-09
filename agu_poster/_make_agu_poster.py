"""AGU poster, 44 x 44 in, built on the user's UH template frame. The template is never edited.

Input   agu_poster/AGU_poster.pptx           user template (56 x 45 in, UH Cullen College frame)
Output  agu_poster/agu_poster_wireframe_44in.pptx

The template's own pieces are reused by copying their XML (outer border, red header band, UH logo,
red heading bar, red-outlined box), then placed on the 44 x 44 grid from poster_agu_layout_draft.md.
Each box holds a grey placeholder that says what goes there. Figures and text replace these later.

Run
    python agu_poster/_make_agu_poster.py
"""
from __future__ import annotations

import copy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
SRC = HERE / "AGU_poster.pptx"
OUT = HERE / "agu_poster_wireframe_44in.pptx"
PAGE = 44.0
WHITE, GREY = RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x6B, 0x6B, 0x6B)

# grid (inches). Outer border 0.5, content 0.9 to 43.1
X0, X1, GAP = 0.9, 43.1, 0.3
CW = (X1 - X0 - 2 * GAP) / 3
C1, C2, C3 = X0, X0 + CW + GAP, X0 + 2 * (CW + GAP)
HEAD = (0.8, 5.6)          # header band top, height
BODY_TOP, BODY_BOT = 6.8, 40.0
FOOT_TOP, FOOT_BOT = 40.3, 43.1

# (heading or None, x, y, w, h, placeholder text)
BOXES = [
    ("INTRODUCTION", C1, BODY_TOP, CW, 8.0,
     "Why it matters. Orphan wells leak methane and brine. 150 years of drilling, many never recorded. "
     "Forest canopy hides them from air photos.\nMap of Pennsylvania documented orphan wells."),
    ("DATA", C1, 15.1, CW, 11.6,
     "USGS 3DEP lidar, 2019 project flown Nov 2019 to Mar 2020. 1 m bare-earth model.\n"
     "Seven-panel strip of one pit: the seven input channels."),
    ("WHAT A WELL LEAVES BEHIND", C1, 27.0, CW, BODY_BOT - 27.0,
     "Pits, pads and roads, the three recurring signs.\nThree-up drawing: pit profile, pad, road.\n"
     "Small table of annotation counts."),
    (None, C2, BODY_TOP, X1 - C2, 14.6,
     "HERO FIGURE. One held-out block. Hillshade base, hand annotation as outlines, model output filled. "
     "Pits, pads and roads. Zoom insets: a hit, a miss, a false alarm."),
    ("MODEL SETUP", C2, 21.7, CW, 8.95,
     "Pipeline: point cloud, ground, DEM, channels, U-Net, threshold, candidates.\nPipeline diagram."),
    ("VALIDATION", C2, 30.95, CW, BODY_BOT - 30.95,
     "Spatial-block five-fold cross-validation. Every feature scored by a model that never saw it.\n"
     "Fold map of the tile."),
    ("RESULTS", C3, 21.7, CW, 11.6,
     "Headline table: pits, pads, roads.\nPrecision-recall curves for pits and pads."),
    ("TAKEAWAYS", C3, 33.6, CW, BODY_BOT - 33.6,
     "Three takeaways. One line on limits. Next: more blocks, field checks."),
    ("REFERENCES", X0, FOOT_TOP, 20.0, FOOT_BOT - FOOT_TOP, "Short reference list. 3DEP citation."),
    ("ACKNOWLEDGEMENTS", X0 + 20.3, FOOT_TOP, 15.0, FOOT_BOT - FOOT_TOP, "Funding and data credits."),
    (None, X0 + 35.6, FOOT_TOP, X1 - (X0 + 35.6), FOOT_BOT - FOOT_TOP, "QR code"),
]


def named(slide, name):
    return [s for s in slide.shapes if s.name == name]


def place(shape, x, y, w, h):
    shape.left, shape.top, shape.width, shape.height = Inches(x), Inches(y), Inches(w), Inches(h)


def clone(slide, proto):
    el = copy.deepcopy(proto._element)
    slide.shapes._spTree.append(el)
    return slide.shapes[-1]


def text_box(slide, x, y, w, h, text, size, color, bold=False, italic=False, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(size * 0.4)
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.italic, r.font.name = Pt(size), bold, italic, "Calibri"
        r.font.color.rgb = color
    return tb


def main() -> None:
    prs = Presentation(str(SRC))
    prs.slide_width = prs.slide_height = Inches(PAGE)
    s = prs.slides[0]
    border, band, logo = named(s, "Rectangle 3")[0], named(s, "Rectangle 7")[0], named(s, "Picture 59")[0]
    bar_proto, box_proto = named(s, "Rectangle 3373")[0], named(s, "Rectangle 38")[0]
    protos = [copy.deepcopy(bar_proto._element), copy.deepcopy(box_proto._element)]
    keep = {border._element, band._element, logo._element}
    for sh in list(s.shapes):
        if sh._element not in keep:
            sh._element.getparent().remove(sh._element)

    place(border, 0.5, 0.5, PAGE - 1.0, PAGE - 1.0)
    place(band, X0, HEAD[0], X1 - X0, HEAD[1])
    lw, lh = logo.width / 914400, logo.height / 914400
    place(logo, X0 + 0.9, HEAD[0] + (HEAD[1] - lh) / 2, lw, lh)
    tx = X0 + 0.9 + lw + 0.8
    text_box(s, tx, HEAD[0] + 0.5, X1 - tx - 0.5, 2.6, "[Poster title]", 110, WHITE, bold=True)
    text_box(s, tx, HEAD[0] + 3.2, X1 - tx - 0.5, 1.0, "Colton Goodrich, [co-authors]", 54, WHITE)
    text_box(s, tx, HEAD[0] + 4.3, X1 - tx - 0.5, 0.9,
             "Cullen College of Engineering, University of Houston", 40, WHITE)

    nid = 1000
    for head, x, y, w, h, note in BOXES:
        spTree = s.shapes._spTree
        box_el = copy.deepcopy(protos[1]); spTree.append(box_el)
        box = s.shapes[-1]
        place(box, x, y, w, h)
        top = y + 0.3
        if head:
            bar_el = copy.deepcopy(protos[0]); spTree.append(bar_el)
            bar = s.shapes[-1]
            place(bar, x + 0.25, y + 0.25, w - 0.5, 0.9)
            p = bar.text_frame.paragraphs[0]
            for r in p.runs[1:]:
                r._r.getparent().remove(r._r)
            p.runs[0].text = head
            top = y + 1.45
        text_box(s, x + 0.5, top, w - 1.0, y + h - top - 0.3, note, 36, GREY, italic=True,
                 align=PP_ALIGN.CENTER if head is None else PP_ALIGN.LEFT)
        for el in (box_el,) + ((bar_el,) if head else ()):
            nid += 1
            el.xpath("./*[1]/p:cNvPr")[0].set("id", str(nid))
    prs.save(str(OUT))
    print(OUT)


if __name__ == "__main__":
    main()
