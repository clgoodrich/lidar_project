"""AGU poster, 44 x 44 in, built on the user's UH template frame. The template is never edited.

Input   agu_poster/AGU_poster.pptx           user template (56 x 45 in, UH Cullen College frame)
Output  agu_poster/agu_poster_wireframe_44in.pptx   grey blocks say what goes where
        agu_poster/agu_poster_mockup_44in.pptx      same layout, existing images dropped in as stand-ins (--mockup)

Layout follows the poster-design evidence summarised in poster_agu_layout_draft.md section 10:
one main-finding sentence in large type above the hero (Silver et al. 2025 RCT, key-concept recall),
every section led by a figure with 1 to 3 short sentences, headings written as statements,
methods and validation kept on the page as diagrams (Oronje et al. 2022; Bentsen and Ostergaard 2025),
about 500 words in total.

Mockup stand-ins come from docs/figures/, the 9t operating-point figures, and the user's
RemoteSensing_option2.pptx (repo root, read in memory, never edited). They are not the final figures.

Run
    python agu_poster/_make_agu_poster.py            # wireframe
    python agu_poster/_make_agu_poster.py --mockup   # mockup
"""
from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = HERE / "AGU_poster.pptx"
OUT_WIRE = HERE / "agu_poster_wireframe_44in.pptx"
OUT_MOCK = HERE / "agu_poster_mockup_44in.pptx"
DECK = ROOT / "RemoteSensing_option2.pptx"
PAGE = 44.0
WHITE, GREY = RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x6B, 0x6B, 0x6B)
INK = RGBColor(0x2B, 0x2F, 0x36)         # charcoal body text
UH_RED = RGBColor(0xC0, 0x00, 0x00)
FIG_FILL = RGBColor(0xF2, 0xF2, 0xF2)
RULE = RGBColor(0xBF, 0xBF, 0xBF)

# grid (inches). No box outlines and no page border: white space separates sections.
X0, X1, GAP = 1.0, 43.0, 0.8
CW = (X1 - X0 - 2 * GAP) / 3
C1, C2, C3 = X0, X0 + CW + GAP, X0 + 2 * (CW + GAP)
HEAD = (0.8, 5.6)          # header band top, height (the one solid block of UH red)
BODY_TOP, BODY_BOT = 7.2, 40.0
FOOT_TOP, FOOT_BOT = 40.9, 43.2
LOWER = 23.4               # top of the col 2 / col 3 sections under the hero

HEAD_PT, BODY_PT = 54, 44  # statement headings (up to 2 lines), body text floor from the draft
HEAD_H = 1.9               # room for a 2-line heading at 54 pt

TAKEAWAY = "Airborne lidar finds 9 in 10 old well pits and pads under forest canopy"

# mockup stand-ins: ("file", path) or ("deck", media name in RemoteSensing_option2.pptx)
OPF = ROOT / "data/9t/results/operating_point/figures"
STAND_INS = {
    "intro": ("file", ROOT / "docs/figures/Pennsylvania Map Abandoned.png"),
    "data": ("deck", "ppt/media/image3.png"),
    "signs": ("file", ROOT / "docs/figures/pit_profile_diagram.png"),
    "hero": ("deck", "ppt/media/image4.png"),
    "setup": ("deck", "ppt/media/image6.png"),
    "results": ("file", OPF / "pr_curve_ranked_candidates_at_proposal_cutoff_heldout_cv5_iou0p30_iou0p50_pit_pitsmrf_pad_9t.png"),
}

# section: key, heading (a statement), x, y, w, h, figure height, figure note (wireframe), body ("|" = new paragraph)
SECTIONS = [
    ("intro", "Forests hide old wells from air photos", C1, BODY_TOP, CW, 10.4, 5.0,
     "Map of Pennsylvania documented orphan wells",
     "Pennsylvania lists thousands of orphan wells. Many more were never recorded."),
    ("data", "Lidar sees the ground under the trees", C1, 18.4, CW, 10.6, 5.6,
     "Optical vs lidar pair, then the seven-channel strip of one pit",
     "USGS 3DEP lidar, flown leaf-off Nov 2019 to Mar 2020. 1 m bare-earth model."),
    ("signs", "A well leaves a pit, a pad and a road", C1, 29.8, CW, BODY_BOT - 29.8, 4.6,
     "Three-up drawing: pit profile, pad, road",
     "We drew [712] pits, [995] pads and [735] road segments by hand."),
    ("setup", "One U-Net per sign, seven terrain channels", C2, LOWER, CW, 8.2, 4.0,
     "Pipeline diagram: points, ground, DEM, channels, U-Net, candidates",
     "Each model maps one sign. Roads also learn drainage as a look-alike."),
    ("valid", "Scored only by models that never saw the feature", C2, LOWER + 9.0, CW, BODY_BOT - LOWER - 9.0, 3.2,
     "Fold map: tile split into five spatial blocks",
     "Each of five spatial blocks is tested by a model trained on the other four."),
    ("results", "Nine in ten pits and pads found", C3, LOWER, CW, 10.6, 4.2,
     "Precision-recall curves, pits and pads", ""),
    ("takeaways", "What this means", C3, LOWER + 11.2, CW, BODY_BOT - LOWER - 11.2, 0.0, "",
     "Lidar can screen whole counties for unrecorded wells.|"
     "Next: more survey blocks and field checks."),
]
STATS = [("[93%]", "pits"), ("[91%]", "pads"), ("[98%]", "roads")]


def named(slide, name):
    return [s for s in slide.shapes if s.name == name]


def place(shape, x, y, w, h):
    shape.left, shape.top, shape.width, shape.height = Inches(x), Inches(y), Inches(w), Inches(h)


def text_box(slide, x, y, w, h, text, size, color, bold=False, italic=False, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, line in enumerate(text.split("|")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(size * 0.4)
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.italic, r.font.name = Pt(size), bold, italic, "Calibri"
        r.font.color.rgb = color
    return tb


def load_image(src) -> io.BytesIO:
    """Open a stand-in, downscale to at most 2400 px, return JPEG bytes (keeps the mockup small)."""
    kind, ref = src
    if kind == "deck":
        with zipfile.ZipFile(DECK) as z:
            im = Image.open(io.BytesIO(z.read(ref)))
            im.load()
    else:
        im = Image.open(ref)
    im = im.convert("RGB")
    im.thumbnail((2400, 2400))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    buf.seek(0)
    return buf, im.size


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mockup", action="store_true", help="drop existing images in as stand-ins")
    mock = ap.parse_args().mockup

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
    text_box(s, tx, HEAD[0] + 0.5, X1 - tx, 2.4, "[Poster title]", 110, WHITE, bold=True)
    text_box(s, tx, HEAD[0] + 3.0, X1 - tx, 1.0, "Colton Goodrich, [co-authors]", 54, WHITE)
    text_box(s, tx, HEAD[0] + 4.1, X1 - tx, 0.9,
             "Cullen College of Engineering, University of Houston", 40, WHITE)

    def rect(x, y, w, h, color):
        r = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
        r.fill.solid(); r.fill.fore_color.rgb = color
        r.line.fill.background()
        r.shadow.inherit = False
        return r

    def figure(key, x, y, w, h, note, size=36):
        """Grey block in the wireframe. In the mockup, the stand-in fitted inside the area."""
        if mock and key in STAND_INS:
            buf, (pw, ph) = load_image(STAND_INS[key])
            scale = min(w / pw, h / ph)
            fw, fh = pw * scale, ph * scale
            s.shapes.add_picture(buf, Inches(x + (w - fw) / 2), Inches(y + (h - fh) / 2), Inches(fw), Inches(fh))
            text_box(s, x, y + h + 0.05, w, 0.5, "stand-in: " + note.lower(), 22, GREY, italic=True)
            return
        rect(x, y, w, h, FIG_FILL)
        text_box(s, x + 0.5, y, w - 1.0, h, note, size, GREY, italic=True, align=PP_ALIGN.CENTER,
                 anchor=MSO_ANCHOR.MIDDLE)

    # thin grey rules break the page up without boxing anything in
    rw = 0.04
    rect(X0, FOOT_TOP - 0.45, X1 - X0, rw, RULE)
    rect(C2 - GAP / 2 - rw / 2, BODY_TOP, rw, BODY_BOT - BODY_TOP, RULE)
    rect(C3 - GAP / 2 - rw / 2, LOWER, rw, BODY_BOT - LOWER, RULE)

    # main finding, the one line a passer-by reads in 3 s; then the hero under it
    text_box(s, C2, BODY_TOP, X1 - C2, 3.2, TAKEAWAY, 84, INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    hero_y = BODY_TOP + 3.6
    figure("hero", C2, hero_y, X1 - C2, LOWER - 0.8 - hero_y,
           "Hero figure. One held-out block. Hillshade base, hand annotation as outlines, model output "
           "filled. Zoom insets: a hit, a miss, a false alarm", 40)

    for key, head, x, y, w, h, fig_h, note, body in SECTIONS:
        text_box(s, x, y, w, HEAD_H, head, HEAD_PT, UH_RED, bold=True, anchor=MSO_ANCHOR.BOTTOM)
        rule_y = y + HEAD_H + 0.15
        rect(x, rule_y, w, 0.05, UH_RED)
        top = rule_y + 0.4
        if key == "results":                       # three big numbers, then the curves
            sw = w / 3
            for i, (num, lab) in enumerate(STATS):
                text_box(s, x + i * sw, top, sw, 1.7, num, 110, INK, bold=True, align=PP_ALIGN.CENTER)
                text_box(s, x + i * sw, top + 1.75, sw, 0.8, lab, 44, INK, align=PP_ALIGN.CENTER)
            top += 2.9
            text_box(s, x, top, w, 0.8, "found in held-out blocks", 36, GREY, align=PP_ALIGN.CENTER)
            top += 1.0
        if fig_h:
            figure(key, x, top, w, fig_h, note)
            top += fig_h + 0.6
        if body:
            text_box(s, x, top, w, y + h - top, body, BODY_PT, INK)

    # footer
    for head, x, w, note in (("References", X0, 19.0, "Short reference list. 3DEP citation."),
                             ("Acknowledgements", X0 + 19.8, 14.0, "Funding and data credits.")):
        text_box(s, x, FOOT_TOP - 0.1, w, 0.8, head, 40, UH_RED, bold=True)
        rect(x, FOOT_TOP + 0.75, w, 0.05, UH_RED)
        text_box(s, x, FOOT_TOP + 1.05, w, FOOT_BOT - FOOT_TOP - 1.05, note, 28, GREY, italic=True)
    text_box(s, X1 - 8.6, FOOT_TOP + 0.4, 5.9, 1.6, "Full methods, data and code", 32, INK,
             align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    rect(X1 - 2.3, FOOT_TOP, 2.3, 2.3, FIG_FILL)
    text_box(s, X1 - 2.3, FOOT_TOP, 2.3, 2.3, "QR", 28, GREY, italic=True, align=PP_ALIGN.CENTER,
             anchor=MSO_ANCHOR.MIDDLE)

    out = OUT_MOCK if mock else OUT_WIRE
    prs.save(str(out))
    print(out)


if __name__ == "__main__":
    main()
