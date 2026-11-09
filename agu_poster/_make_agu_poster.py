"""AGU poster, 44 x 44 in, built on the user's UH template frame. The template is never edited.

Input   agu_poster/AGU_poster.pptx           user template (56 x 45 in, UH Cullen College frame)
        agu_poster/figures/*.png             built by agu_poster/_make_poster_figures.py
Output  agu_poster/agu_poster_wireframe_44in.pptx   grey blocks say what goes where
        agu_poster/agu_poster_mockup_44in.pptx      same layout with the figures placed (--mockup)

Layout follows the poster-design evidence in poster_agu_layout_draft.md section 10:
one main-finding sentence in large type above the hero (Silver et al. 2025 RCT, key-concept recall),
every section led by a figure, headings written as statements, methods and validation kept on the page
(Oronje et al. 2022; Bentsen and Ostergaard 2025), about 350 to 500 words.

Each section is a stack of blocks laid top to bottom: ("fig", key, height, wireframe note) or ("text", body).
"|" in body text starts a new paragraph.

Run
    python agu_poster/_make_agu_poster.py            # wireframe
    python agu_poster/_make_agu_poster.py --mockup   # with figures
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = HERE / "AGU_poster.pptx"
FIGS = HERE / "figures"
OUT_WIRE = HERE / "agu_poster_wireframe_44in.pptx"
OUT_MOCK = HERE / "agu_poster_mockup_44in.pptx"
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
HERO_H = 10.6              # hero figure height, figure is 27.6 x 10.6 in
LOWER = BODY_TOP + 3.6 + HERO_H + 0.9     # top of the col 2 / col 3 sections under the hero

HEAD_PT, BODY_PT, CAP_PT = 54, 44, 32
HEAD_H = 1.05              # one-line statement heading at 54 pt
LINE = BODY_PT * 1.2 / 72  # body line height, in
CHARS = 44                 # body characters per line across one column at 44 pt (Calibri, measured)

TAKEAWAY = "Airborne lidar finds 9 in 10 old well pits and pads under forest canopy"

FIG_FILES = {
    "intro": ROOT / "docs/figures/Pennsylvania Map Abandoned.png",
    "optical": FIGS / "poster_optical_vs_lidar_9t.png",
    "channels": FIGS / "poster_channels_one_pit_9t.png",
    "signs": FIGS / "poster_signs_gallery_9t.png",
    "hero": FIGS / "poster_hero_heldout_9t.png",
    "setup": FIGS / "poster_pipeline_diagram.png",
    "valid": FIGS / "poster_cv_folds_pit_9t.png",
    "results": FIGS / "poster_pr_curves_heldout_9t.png",
}

SECTIONS = [
    ("Forests hide old wells from air photos", C1, BODY_TOP, [
        ("fig", "intro", 5.6, "Map of Pennsylvania documented orphan wells"),
        ("text", "Orphan wells have no owner left to plug them. Unplugged wells can leak methane and brine. "
                 "Pennsylvania lists thousands, and many more were never recorded. Most sit under forest, "
                 "hidden from air photos."),
    ]),
    ("Lidar sees the ground under the trees", C1, 19.4, [
        ("fig", "optical", 3.9, "Air photo and lidar of the same ground"),
        ("text", "USGS 3DEP lidar, flown leaf-off from Nov 2019 to Mar 2020. Each model reads seven terrain "
                 "layers, shown here around one pit."),
        ("fig", "channels", 2.9, "Seven-channel strip of one pit"),
    ]),
    ("A well leaves a pit, a pad and a road", C1, 31.6, [
        ("fig", "signs", 5.0, "Pit, pad, road on hillshade"),
        ("text", "We outlined 712 pits and 995 pads by hand and traced the access roads."),
    ]),
    ("One U-Net per sign", C2, LOWER, [
        ("fig", "setup", 4.6, "Pipeline diagram"),
        ("text", "The road model also learns drainage, the feature it most often confuses with road."),
    ]),
    ("Tested on blocks the model never saw", C2, LOWER + 8.75, [
        ("fig", "valid", 3.2, "Five test sets of 375 m blocks"),
        ("text", "Five rounds. Each test set (blue) is scored by a model trained without it. A detection "
                 "counts when it matches a hand outline (IoU 0.3 or more)."),
    ]),
    ("Nine in ten found in held-out blocks", C3, LOWER, [
        ("stats", None, 2.7, None),
        ("fig", "results", 4.8, "Precision-recall curves, pits and pads"),
        ("text", "Precision is lower. 63% of pit and 59% of pad detections match a hand outline. Some of "
                 "the rest may be features we have not drawn yet."),
    ]),
    ("What this means", C3, LOWER + 12.1, [
        ("text", "Lidar can screen whole counties for unrecorded wells.|This is one survey block. The labels "
                 "are our own reading of the ground, and no site has been visited yet.|Next we add survey "
                 "blocks and check sites in the field."),
    ]),
]
STATS = [("93%", "pits"), ("91%", "pads"), ("98%", "roads")]
HERO_CAPTION = ("Every prediction shown comes from a model that never saw this block. Western Pennsylvania, "
                "750 m by 375 m.")


def named(slide, name):
    return [s for s in slide.shapes if s.name == name]


def place(shape, x, y, w, h):
    shape.left, shape.top, shape.width, shape.height = Inches(x), Inches(y), Inches(w), Inches(h)


def text_height(text, size=BODY_PT, chars=CHARS):
    """Rough height of wrapped body text in a column, in inches."""
    k = chars * BODY_PT / size
    lines = sum(max(1, -(-len(p) // int(k))) for p in text.split("|"))
    paras = len(text.split("|"))
    return lines * size * 1.2 / 72 + (paras - 1) * size * 0.4 / 72


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


def load_image(path: Path):
    """Downscale to at most 4000 px on the long side and return JPEG or PNG bytes plus the pixel size."""
    im = Image.open(path).convert("RGB")
    im.thumbnail((4000, 4000))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf, im.size


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mockup", action="store_true", help="place the built figures")
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
        """Grey block in the wireframe. In the mockup, the figure fitted inside the area, top-centred."""
        if mock and FIG_FILES.get(key, Path("-")).exists():
            buf, (pw, ph) = load_image(FIG_FILES[key])
            scale = min(w / pw, h / ph)
            fw, fh = pw * scale, ph * scale
            s.shapes.add_picture(buf, Inches(x + (w - fw) / 2), Inches(y), Inches(fw), Inches(fh))
            return
        rect(x, y, w, h, FIG_FILL)
        text_box(s, x + 0.5, y, w - 1.0, h, note, size, GREY, italic=True, align=PP_ALIGN.CENTER,
                 anchor=MSO_ANCHOR.MIDDLE)

    # thin grey rules break the page up without boxing anything in
    rw = 0.04
    rect(X0, FOOT_TOP - 0.45, X1 - X0, rw, RULE)
    rect(C2 - GAP / 2 - rw / 2, BODY_TOP, rw, BODY_BOT - BODY_TOP, RULE)
    rect(C3 - GAP / 2 - rw / 2, LOWER, rw, BODY_BOT - LOWER, RULE)

    # main finding, the one line a passer-by reads in 3 s; then the hero and its caption
    text_box(s, C2, BODY_TOP, X1 - C2, 3.2, TAKEAWAY, 84, INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    hero_y = BODY_TOP + 3.4
    figure("hero", C2, hero_y, X1 - C2, HERO_H,
           "Hero figure. One held-out block. Hillshade base, hand annotation as outlines, model output "
           "filled. Zoom insets: a hit, a miss, an unlabelled detection", 40)
    text_box(s, C2, hero_y + HERO_H + 0.05, X1 - C2, 0.6, HERO_CAPTION, CAP_PT, GREY)

    words = len(TAKEAWAY.split()) + len(HERO_CAPTION.split())
    for head, x, y, blocks in SECTIONS:
        text_box(s, x, y, CW, HEAD_H, head, HEAD_PT, UH_RED, bold=True, anchor=MSO_ANCHOR.BOTTOM)
        words += len(head.split())
        rule_y = y + HEAD_H + 0.12
        rect(x, rule_y, CW, 0.05, UH_RED)
        top = rule_y + 0.4
        for kind, key_or_text, h, note in [(b[0], b[1], b[2] if len(b) > 2 else None,
                                            b[3] if len(b) > 3 else None) for b in blocks]:
            if kind == "fig":
                figure(key_or_text, x, top, CW, h, note)
                top += h + 0.35
            elif kind == "stats":                       # three big numbers
                sw = CW / 3
                for i, (num, lab) in enumerate(STATS):
                    text_box(s, x + i * sw, top, sw, 1.7, num, 110, INK, bold=True, align=PP_ALIGN.CENTER)
                    text_box(s, x + i * sw, top + 1.75, sw, 0.8, lab, 44, INK, align=PP_ALIGN.CENTER)
                top += h + 0.2
            else:
                th = text_height(key_or_text)
                text_box(s, x, top, CW, th + 0.2, key_or_text, BODY_PT, INK)
                words += len(key_or_text.replace("|", " ").split())
                top += th + 0.45
        if top > BODY_BOT + 0.3:
            print(f"WARNING: section '{head}' runs to y {top:.1f} in, past the body bottom {BODY_BOT}")

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
    print(out, f"body words {words}")


if __name__ == "__main__":
    main()
