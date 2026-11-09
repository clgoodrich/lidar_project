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

# grid (inches). No box outlines and no page border: white space separates sections.
X0, X1, GAP = 1.0, 43.0, 0.8
CW = (X1 - X0 - 2 * GAP) / 3
C1, C2, C3 = X0, X0 + CW + GAP, X0 + 2 * (CW + GAP)
HEAD = (0.8, 5.6)          # header band top, height (the one solid block of UH red)
BODY_TOP, BODY_BOT = 7.2, 40.0
FOOT_TOP, FOOT_BOT = 40.9, 43.2
UH_RED = RGBColor(0xC0, 0x00, 0x00)
FIG_FILL = RGBColor(0xF2, 0xF2, 0xF2)

# (heading or None, x, y, w, h, placeholder text). Heading None = figure area, shown as a light grey block.
BOXES = [
    ("Introduction", C1, BODY_TOP, CW, 8.0,
     "Why it matters. Orphan wells leak methane and brine. 150 years of drilling, many never recorded. "
     "Forest canopy hides them from air photos.|Map of Pennsylvania documented orphan wells."),
    ("Data", C1, 16.0, CW, 11.0,
     "USGS 3DEP lidar, 2019 project flown Nov 2019 to Mar 2020. 1 m bare-earth model.|"
     "Seven-panel strip of one pit: the seven input channels."),
    ("What a well leaves behind", C1, 27.8, CW, BODY_BOT - 27.8,
     "Pits, pads and roads, the three recurring signs.|Three-up drawing: pit profile, pad, road.|"
     "Small table of annotation counts."),
    (None, C2, BODY_TOP, X1 - C2, 14.0,
     "HERO FIGURE. One held-out block. Hillshade base, hand annotation as outlines, model output filled. "
     "Pits, pads and roads. Zoom insets: a hit, a miss, a false alarm."),
    ("Model setup", C2, 22.0, CW, 8.6,
     "Pipeline: point cloud, ground, DEM, channels, U-Net, threshold, candidates.|Pipeline diagram."),
    ("Validation", C2, 31.4, CW, BODY_BOT - 31.4,
     "Spatial-block five-fold cross-validation. Every feature scored by a model that never saw it.|"
     "Fold map of the tile."),
    ("Results", C3, 22.0, CW, 11.4,
     "Headline table: pits, pads, roads.|Precision-recall curves for pits and pads."),
    ("Takeaways", C3, 34.2, CW, BODY_BOT - 34.2,
     "Three takeaways. One line on limits. Next: more blocks, field checks."),
    ("References", X0, FOOT_TOP, 19.0, FOOT_BOT - FOOT_TOP, "Short reference list. 3DEP citation."),
    ("Acknowledgements", X0 + 19.8, FOOT_TOP, 14.0, FOOT_BOT - FOOT_TOP, "Funding and data credits."),
    (None, X1 - 2.3, FOOT_TOP, 2.3, 2.3, "QR"),
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
    for i, line in enumerate(text.split("|")):
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
    band, logo = named(s, "Rectangle 7")[0], named(s, "Picture 59")[0]
    keep = {band._element, logo._element}
    for sh in list(s.shapes):
        if sh._element not in keep:
            sh._element.getparent().remove(sh._element)

    place(band, 0.0, 0.0, PAGE, HEAD[0] + HEAD[1])      # full-bleed band, no outer border
    lw, lh = logo.width / 914400, logo.height / 914400
    place(logo, X0, (HEAD[0] + HEAD[1] - lh) / 2, lw, lh)
    tx = X0 + lw + 0.8
    text_box(s, tx, HEAD[0] + 0.3, X1 - tx, 2.6, "[Poster title]", 110, WHITE, bold=True)
    text_box(s, tx, HEAD[0] + 3.0, X1 - tx, 1.0, "Colton Goodrich, [co-authors]", 54, WHITE)
    text_box(s, tx, HEAD[0] + 4.1, X1 - tx, 0.9,
             "Cullen College of Engineering, University of Houston", 40, WHITE)

    def rect(x, y, w, h, color):
        r = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
        r.fill.solid(); r.fill.fore_color.rgb = color
        r.line.fill.background()
        r.shadow.inherit = False
        return r

    # thin grey rules break the page up without boxing anything in: one above the footer and one
    # down the middle of each column gutter (the col 2 / col 3 gutter starts below the hero)
    rule_c, rule_w = RGBColor(0xBF, 0xBF, 0xBF), 0.04
    rect(X0, FOOT_TOP - 0.45, X1 - X0, rule_w, rule_c)
    rect(C2 - GAP / 2 - rule_w / 2, BODY_TOP, rule_w, BODY_BOT - BODY_TOP, rule_c)
    rect(C3 - GAP / 2 - rule_w / 2, 22.0, rule_w, BODY_BOT - 22.0, rule_c)
    for head, x, y, w, h, note in BOXES:
        foot = y >= FOOT_TOP
        if head is None:
            r = rect(x, y, w, h, FIG_FILL)
            text_box(s, x + 0.5, y + h / 2 - 0.6, w - 1.0, 1.2, note, 28 if foot else 36, GREY, italic=True,
                     align=PP_ALIGN.CENTER)
            continue
        hs = 40 if foot else 60
        text_box(s, x, y - 0.1, w, 1.0, head, hs, UH_RED, bold=True)
        rule_y = y + (0.75 if foot else 1.05)
        rect(x, rule_y, w, 0.05, UH_RED)
        top = rule_y + 0.3
        text_box(s, x, top, w, y + h - top, note, 28 if foot else 36, GREY, italic=True)
    prs.save(str(OUT))
    print(OUT)


if __name__ == "__main__":
    main()
