"""AGU poster, 44 x 44 in, built on the user's UH template frame. The template is never edited.

Input   agu_poster/AGU_poster.pptx           user template (56 x 45 in, UH Cullen College frame)
        agu_poster/figures/*.png             built by agu_poster/_make_poster_figures.py
Output  agu_poster/agu_poster_wireframe_44in.pptx   grey blocks say what goes where
        agu_poster/agu_poster_filled_44in.pptx      the filled poster: figures, captions, text (--mockup)
        agu_poster/agu_poster_outline_44in.pptx     figures placed, every text slot a [stand-in] (--outline)

Layout follows the poster-design evidence in poster_agu_layout_draft.md section 10:
one main-finding sentence in large type above the hero (Silver et al. 2025 RCT, key-concept recall),
every section led by a figure, headings written as statements, methods and validation kept on the page
(Oronje et al. 2022; Bentsen and Ostergaard 2025), about 350 to 500 words.

Each section is a stack of blocks laid top to bottom: ("fig", key, height, wireframe note) or ("text", body).
"|" in body text starts a new paragraph.

Run
    python agu_poster/_make_agu_poster.py            # wireframe
    python agu_poster/_make_agu_poster.py --mockup   # with figures
    python agu_poster/_make_agu_poster.py --outline  # figures, stand-in text
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
OUT_MOCK = HERE / "agu_poster_filled_44in.pptx"
OUT_OUTLINE = HERE / "agu_poster_outline_44in.pptx"
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
HERO_H = 8.2               # hero figure height, figure is 27.6 x 9.4 in
LOWER = BODY_TOP + 3.6 + HERO_H + 0.9     # top of the col 2 / col 3 sections under the hero

HEAD_PT, BODY_PT, CAP_PT = 54, 44, 32
HEAD_H = 1.05              # one-line statement heading at 54 pt
LINE = BODY_PT * 1.2 / 72  # body line height, in
CHARS = 50                 # body characters per line across one column at 44 pt (Calibri, measured)

TITLE = "Detecting orphaned oil and gas wells under forest canopy with airborne lidar and U-Nets"
TAKEAWAY = "Airborne lidar finds 9 in 10 old well pits and pads under forest canopy"

FIG_FILES = {
    "intro": FIGS / "poster_pa_wells_locator.png",
    "optical": FIGS / "poster_optical_vs_lidar_9t.png",
    "channels": FIGS / "poster_channels_one_pit_9t.png",
    "signs": FIGS / "poster_signs_gallery_9t.png",
    "hero": FIGS / "poster_hero_heldout_9t.png",
    "setup": FIGS / "poster_pipeline_diagram.png",
    "valid": FIGS / "poster_cv_folds_pit_9t.png",
    "results": FIGS / "poster_pr_curves_heldout_9t.png",
}

# Numbered captions in reading order. Scale and data source are stated for every map.
CAPS = {
    "intro": ("Figure 1.", "Documented orphan and abandoned wells (yellow points) in western Pennsylvania, on a "
              "satellite base map. North is up. Source: Pennsylvania DEP records."),
    "optical": ("Figure 2.", "Aerial photograph (left) and a lidar relief image with the trees removed (right) of "
                "the same ground in study tile 9t."),
    "channels": ("Figure 3.", "Seven terrain layers around one pit. Relief (25 m, 5 m), slope, position, openness (+, \u2212), roughness."),
    "signs": ("Figure 4.", "Hand-drawn labels on hillshade. A pit is a bowl with a raised rim, a pad is the flat work area and a road is the track to it. We outlined 712 pits and 995 pads. Panels are 60, 180 and 180 m wide."),
    "hero": ("Figure 5.", "Model predictions on one test block of tile 9t, 750 m by 375 m, 100 m scale bar. "
             "Filled shapes are model output and outlines are hand-drawn labels. The block was withheld from "
             "training. Insets show a found pit (1), a missed pit (2) and a detection with no label (3)."),
    "setup": ("Figure 6.", "Processing chain. One U-Net is trained for each of pits, pads and roads."),
    "valid": ("Figure 7.", "Spatial cross-validation. The tile is cut into 375 m blocks. In each test set the blue "
              "blocks are held out and the grey blocks are used for training. White blocks are unused."),
    "results": ("Figure 8.", "Precision-recall curves for held-out pits and pads, five test sets pooled, match "
                "rule IoU 0.3. AP is average precision."),
}

SECTIONS = [
    ("Forests hide old wells from air photos", C1, BODY_TOP, [
        ("fig", "intro", 3.9, "Map of Pennsylvania documented orphan wells"),
        ("text", "Orphan wells have no owner left to plug them and can leak methane and brine. "
                 "Pennsylvania lists thousands. Many more were never recorded.|Old wells have been "
                 "read from lidar by eye (Sams et al.; Saint-Vincent et al. 2021). Can a model do it?"),
    ]),
    ("Lidar sees the ground under the trees", C1, None, [
        ("fig", "optical", 2.6, "Air photo and lidar of the same ground"),
        ("text", "USGS 3DEP lidar, flown leaf-off Nov 2019 to Mar 2020. We build a 0.5 m "
                 "bare-earth model and seven terrain layers."),
        ("fig", "channels", 2.2, "Seven-channel strip of one pit"),
    ]),
    ("A well leaves a pit, a pad and a road", C1, None, [
        ("fig", "signs", 3.6, "Pit, pad, road on hillshade"),
    ]),
    ("One U-Net per sign", C2, LOWER, [
        ("fig", "setup", 3.0, "Pipeline diagram"),
        ("text", "A U-Net labels every pixel. Each sign gets its own model, which outputs a probability map. "
                 "Pixels above a cutoff become outlines. The road model also learns drainage, the feature "
                 "it most often confuses with road."),
    ]),
    ("Tested on blocks the model never saw", C2, None, [
        ("fig", "valid", 2.3, "Five test sets of 375 m blocks"),
        ("text", "The tile is cut into 375 m blocks in five test sets. Each set (blue) is scored by a model "
                 "trained without it. A detection counts when it overlaps a hand outline enough (IoU 0.3). "
                 "Roads use their own held-out set of 735 segments."),
    ]),
    ("Most found. Pads are the weak spot", C3, LOWER, [
        ("table", None, 3.3, None),
        ("fig", "results", 3.2, "Precision-recall curves, pits and pads"),
        ("text", "Recall is high for all three signs. Precision is lower, and lowest for pads. Pad edges are loose, so "
                 "only 77% of pads match at IoU 0.5. Some unmatched detections may be real features we have not drawn."),
    ]),
    ("What this means", C3, None, [
        ("text", "Lidar can screen large areas for unrecorded wells. Pits are the most reliable sign.|"
                 "Limits. One survey block. Labels are our own reading of the ground. No site has been "
                 "visited.|Next we add survey blocks and check sites in the field."),
    ]),
]
# Results table: ann712 CV5, F2 threshold per fold, IoU 0.3 (docs/iterations/LEADERBOARD.md, 2026-09-17).
# Roads: recall_clean at thr 0.20 on 735 held-out segments; road precision is not object-scored, so it is left blank.
TABLE = [("", "Recall", "Precision", "IoU 0.5 recall"),
         ("Pits", "93%", "63%", "82%"),
         ("Pads", "91%", "59%", "77%"),
         ("Roads", "98%", "—", "—")]
TABLE_NOTE = "Table 1. Held-out results, tile 9t (pits 503, pads 650, roads 735 segments). Recall and precision at IoU 0.3, F2 cutoff. Roads are scored by segments recovered."
# --outline: stand-in text per section, (heading, [one entry per text block]). Space is kept at the real
# text's height so the layout matches the mockup.
OUTLINE = [
    ("[Heading: why the problem matters]",
     ["[Background: what orphan wells are and why they matter]|[Prior work here: satellite and lidar "
      "studies, then the question]"]),
    ("[Heading: why lidar]", ["[Data: lidar source, area, flight dates, terrain layers built]"]),
    ("[Heading: what a well leaves behind]", ["[Signs: describe pit, pad and road. Number of hand labels]"]),
    ("[Heading: the model]", ["[Method: model type, outputs, cutoff, how roads differ]"]),
    ("[Heading: how it was tested]", ["[Validation: blocks, test sets, match rule, road test set]"]),
    ("[Heading: main result]", ["[Results: what the numbers say, where it is weak and why]"]),
    ("[Heading: implications]", ["[Implications here]|[Limits here]|[Next steps here]"]),
]
OUTLINE_TABLE = [("", "Recall", "Precision", "IoU 0.5 recall")] + [(r[0], "[xx%]", "[xx%]", "[xx%]") for r in TABLE[1:]]

HERO_CAPTION = CAPS["hero"][1]


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
             anchor=MSO_ANCHOR.TOP, lead=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, line in enumerate(text.split("|")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(size * 0.4)
        if lead and i == 0:
            r0 = p.add_run()
            r0.text = lead + " "
            r0.font.size, r0.font.bold, r0.font.italic, r0.font.name = Pt(size), True, False, "Calibri"
            r0.font.color.rgb = color
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
    ap.add_argument("--outline", action="store_true", help="figures placed, every text slot a stand-in")
    args = ap.parse_args()
    outline = args.outline
    mock = args.mockup or outline

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
    text_box(s, tx, HEAD[0] + 0.3, X1 - tx, 3.0, "[Poster title]" if outline else TITLE, 88, WHITE, bold=True)
    text_box(s, tx, HEAD[0] + 3.5, X1 - tx, 1.0, "[Authors]" if outline else "Colton Goodrich", 50, WHITE)
    text_box(s, tx, HEAD[0] + 4.5, X1 - tx, 0.8,
             "[Affiliation]" if outline else "Cullen College of Engineering, University of Houston", 38, WHITE)

    def rect(x, y, w, h, color):
        r = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
        r.fill.solid(); r.fill.fore_color.rgb = color
        r.line.fill.background()
        r.shadow.inherit = False
        return r

    def figure(key, x, y, w, h, note, size=36):
        """Place the figure, then its numbered caption. Returns the caption height in inches."""
        figure_img(key, x, y, w, h, note, size)
        if key in CAPS and not outline:
            lead, cap = CAPS[key]
            ch = text_height(lead + " " + cap, CAP_PT)
            text_box(s, x, y + h + 0.08, w, ch + 0.1, cap, CAP_PT, GREY, lead=lead)
            return ch + 0.15
        return 0.0

    def figure_img(key, x, y, w, h, note, size=36):
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
    text_box(s, C2, BODY_TOP, X1 - C2, 3.2, "[Main finding in one sentence]" if outline else TAKEAWAY, 84, INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    hero_y = BODY_TOP + 3.4
    figure_img("hero", C2, hero_y, X1 - C2, HERO_H,
           "Hero figure. One held-out block. Hillshade base, hand annotation as outlines, model output "
           "filled. Zoom insets: a hit, a miss, an unlabelled detection", 40)
    text_box(s, C2, hero_y + HERO_H + 0.05, X1 - C2, 0.6,
             "[Hero caption: what the map shows and where]" if outline else CAPS["hero"][1], CAP_PT, GREY,
             lead=None if outline else CAPS["hero"][0])

    words = len(TAKEAWAY.split()) + len(HERO_CAPTION.split())
    col_end = {C1: BODY_TOP - 0.7, C2: LOWER - 0.7, C3: LOWER - 0.7}
    for si, (head, x, y, blocks) in enumerate(SECTIONS):
        stand_texts = iter(OUTLINE[si][1])
        y = col_end[x] + 0.7 if y is None else y      # stack under the previous section in the column
        text_box(s, x, y, CW, HEAD_H, OUTLINE[si][0] if outline else head, HEAD_PT, UH_RED, bold=True, anchor=MSO_ANCHOR.BOTTOM)
        words += len(head.split())
        rule_y = y + HEAD_H + 0.12
        rect(x, rule_y, CW, 0.05, UH_RED)
        top = rule_y + 0.4
        for kind, key_or_text, h, note in [(b[0], b[1], b[2] if len(b) > 2 else None,
                                            b[3] if len(b) > 3 else None) for b in blocks]:
            if kind == "fig":
                ch = figure(key_or_text, x, top, CW, h, note)
                top += h + ch + 0.35
            elif kind == "table":                       # recall and precision per sign, numbers large
                rh = (h - 0.6) / len(TABLE)
                cws = [3.2] + [(CW - 3.2) / 3] * 3
                for r, row in enumerate(OUTLINE_TABLE if outline else TABLE):
                    cx = x
                    for c, cell in enumerate(row):
                        big = r > 0 and c > 0
                        text_box(s, cx, top + r * rh, cws[c], rh, cell, 48 if big else 38,
                                 INK if (big or c == 0) else GREY, bold=big or c == 0,
                                 align=PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
                        cx += cws[c]
                    if r == 0:
                        rect(x, top + rh - 0.02, CW, 0.03, RULE)
                text_box(s, x, top + len(TABLE) * rh + 0.05, CW, 1.4,
                         "[Table note: define each column]" if outline else TABLE_NOTE[9:], 28, GREY,
                         lead=None if outline else "Table 1.")
                top += h + 0.55
            else:
                th = text_height(key_or_text)
                text_box(s, x, top, CW, th + 0.2, next(stand_texts) if outline else key_or_text, BODY_PT,
                         GREY if outline else INK, italic=outline)
                words += len(key_or_text.replace("|", " ").split())
                top += th + 0.45
        col_end[x] = top - 0.45
        if top - 0.45 > BODY_BOT + 0.05:
            print(f"WARNING: section '{head}' runs to y {top:.1f} in, past the body bottom {BODY_BOT}")

    # footer
    for head, x, w, note in (("References", X0, 19.0, "Ramachandran et al. 2024, Nat. Commun. 15, 7036. Saint-Vincent et al. 2021, J. Environ. Manage. 280, 111856. Sams et al., NETL, LiDAR mapping of 1860s oil fields, Pioneer Run (OSTI 1569995). USGS 3D Elevation Program"),
                             ("Acknowledgements", X0 + 19.8, 14.0, "Lidar from the USGS 3D Elevation Program, project PA_WesternPA_2019_D20. Well records from the Pennsylvania Department of Environmental Protection. Funding: [to add].")):
        text_box(s, x, FOOT_TOP - 0.1, w, 0.8, head, 40, UH_RED, bold=True)
        rect(x, FOOT_TOP + 0.75, w, 0.05, UH_RED)
        ref = head == "References"
        if outline:
            note = "[References here]" if ref else "[Funding and data credits here]"
        text_box(s, x, FOOT_TOP + 1.0, w, FOOT_BOT - FOOT_TOP - 0.95, note, 24 if ref else 28,
                 INK if ref else GREY, italic=not ref)
    text_box(s, X1 - 8.6, FOOT_TOP + 0.4, 5.9, 1.6, "Full methods, data and code", 32, INK,
             align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    rect(X1 - 2.3, FOOT_TOP, 2.3, 2.3, FIG_FILL)
    text_box(s, X1 - 2.3, FOOT_TOP, 2.3, 2.3, "QR", 28, GREY, italic=True, align=PP_ALIGN.CENTER,
             anchor=MSO_ANCHOR.MIDDLE)

    out = OUT_OUTLINE if outline else OUT_MOCK if mock else OUT_WIRE
    prs.save(str(out))
    print(out, f"body words {words}")


if __name__ == "__main__":
    main()
