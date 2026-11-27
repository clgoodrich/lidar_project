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
WHITE, GREY = RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x2B, 0x2F, 0x36)
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
HERO_H = 8.0               # hero figure height, figure is 27.6 x 9.4 in
LOWER = BODY_TOP + 3.6 + HERO_H + 0.9     # top of the col 2 / col 3 sections under the hero

HEAD_PT, BODY_PT, CAP_PT = 50, 28, 24
HEAD_H = 1.05              # one-line statement heading at 54 pt
LINE = BODY_PT * 1.2 / 72  # body line height, in
CHARS = 74                 # body characters per line across one column at 44 pt (Calibri, measured)

TITLE = "Detecting orphaned oil and gas wells under forest canopy with airborne lidar and U-Nets"
TAKEAWAY = "Airborne lidar finds 93% of well pits under forest canopy while flagging 0.13% of the ground"

FIG_FILES = {
    "intro": FIGS / "poster_pa_wells_locator.png",
    "signs": FIGS / "poster_signs_gallery_9t.png",
    "hero": FIGS / "poster_hero_tileB.png",
    "valid": FIGS / "poster_cv_folds_pit_9t.png",
    "transfer": FIGS / "poster_pred_tile616591.png",
    "errors": FIGS / "poster_errors_9t.png",
}

# Numbered captions in reading order. Scale and data source are stated for every map.
CAPS = {
    "hero": ("Figure 1.", "One 400 m window of Tile B, unseen in training. (a) Leaf-off aerial photograph (Planet, 10 April 2023, 3 m). "
             "(b) Red relief image map from bare-earth lidar. (c) Pad probability with hand-drawn pads (yellow dashed). "
             "(d) Pit probability with hand-drawn pits (blue), shown from black 0 to white 0.5. Mean of the five fold models. Bar 100 m, north up."),
    "intro": ("Figure 2.", "Documented orphan and abandoned wells (yellow points) in western Pennsylvania, on a "
              "satellite base map. North is up. Source: Pennsylvania DEP records."),
    "signs": ("Figure 3.", "Hand-drawn labels on a red relief image map. From left to right: pit (blue), pad (yellow) and road (white). "
              "A pit is a bowl with a raised rim, a pad is the flat work area and a road is the track to it. Panels are 60, 180 and 180 m wide."),
    "valid": ("Figure 5.", "Spatial cross-validation on 375 m blocks. Blue blocks are held out, grey blocks train the model, white blocks are unused."),
    "transfer": ("Figure 4.", "Northern 750 m of Tile B, unseen in training. (a) Red relief image map with hand-drawn pads (yellow dashed) "
                 "and pits (blue). (b) Pads and pits predicted by the five fold models at the Area A cutoffs. Bar 250 m."),
    "errors": ("Figure 6.", "Three 50 m windows from a held-out block of Area A. (a) Found pit. (b) Missed pit. "
               "(c) Model pit with no hand label, which counts against precision. Bars 10 m."),
}


SECTIONS = [
    ("Why orphan wells stay hidden", C1, BODY_TOP, [
        ("fig", "intro", 2.5, "Map of Pennsylvania documented orphan wells"),
        ("text", "Hazard. Thousands of undocumented wells in western Pennsylvania can leak methane and brine.|"
                 "Why current data fall short. Canopy hides about half of the pads from satellites (Ramachandran et al. 2024), "
                 "and legacy well coordinates can be off by tens to hundreds of metres.|"
                 "Prior lidar work. NETL traces trails and access roads to well sites from free state lidar across Pennsylvania, New York, "
                 "Kentucky, West Virginia and Ohio (Gorantla et al. 2024). A 2017 drone survey of 1860s wells at Pioneer Run "
                 "found an open well bore from an unnatural depression in the relief image (Sams et al. 2018).|"
                 "Approach. Map the pit, pad and access road that every well leaves, from leaf-off USGS 3DEP lidar, "
                 "with trained U-Nets, and test on ground they have not seen."),
    ]),
    ("Lidar data and terrain layers", C1, None, [
        ("fig", "signs", 3.3, "Pit, pad, road on RRIM"),
        ("text", "USGS 3DEP lidar, project PA_WesternPA_2019_D20, flown leaf-off Nov 2019 to Mar 2020, about 2.6 ground points per m2. Area A (4.5 km square, tile block 17TPF619593) holds all training and cross-validation. Tile B (1.5 km, tile 17TPF616591, 1.5 km west of Area A) is used only for testing.|"
                 "Ground returns are triangulated (Delaunay) and gridded to a 0.5 m bare-earth model. Seven layers are derived: relief in 12.5 m "
                 "and 2.5 m windows, slope, topographic position, positive and negative openness, and roughness.|"
                 "We outlined 503 pits and 650 pads by hand in Area A (712 and 995 across all areas), without the DEP well records."),
    ]),
    ("Transfer to an unseen area", C1, None, [
        ("text", "Tile B shares no ground with Area A. All five fold models run on it with Area A cutoffs and nothing retuned. "
                 "It is the tile with the most hand-drawn pads in that region (86 pads, 62 pits). Scores are in Results."),
        ("fig", "transfer", 3.4, "Predictions on Tile B"),
    ]),
    ("Methods", C2, LOWER, [
        ("spec", None, 2.1, None),
        ("text", "One plain four-level U-Net per sign, 7.8 million parameters, standardised inputs. Focal cross-entropy (gamma 2), "
                 "random flips and rotations, AdamW at 1e-3, cosine schedule, 40 epochs, batch 16. Drainage is an explicit negative class "
                 "for roads. Probabilities above the cutoff are vectorised.|"
                 "A 26 million parameter U-Net++ with a pretrained encoder scored no better on pits (pixel IoU 0.561 against 0.559), "
                 "so data and labels limit accuracy, not architecture."),
    ]),
    ("Validation and transfer", C2, None, [
        ("fig", "valid", 1.5, "Five test sets of 375 m blocks"),
        ("text", "Five-fold cross-validation on 375 m blocks, split by block and never by well, so a jittered patch cannot reach a held-out block.|"
                 "An inner validation set picks the epoch and the F2 cutoff, which weights recall four times as heavily as precision. "
                 "The held-out fold never tunes either."),
    ]),
    ("Conclusions", C2, None, [
        ("text", "Terrain layers from leaf-off lidar let a small U-Net find more than 90% of labelled pits and pads in blocks it never saw, "
                 "and 98% of pits and 88% of pads on the unseen Tile B.|"
                 "Limits. One survey, one annotator, no field visits.|"
                 "Next. Field-check candidates and test on McKean lidar."),
    ]),
    ("Results", C3, LOWER, [
        ("table", None, 4.3, None),
        ("fig", "errors", 4.5, "Found, missed, unlabelled"),
        ("text", "Pits and pads are found at 93% and 91% (467 of 503, 593 of 650). Threshold-free average precision at IoU 0.3 is 0.82 for pits "
                 "(95% bootstrap interval 0.78 to 0.86) and 0.75 for pads (0.70 to 0.79).|"
                 "Pad recall falls to 77% at IoU 0.5. Where a pad ends and a wide road begins is an arbitrary line, so pad edges differ from ours "
                 "even when the pad is found. Precision is a lower bound, since some unmatched detections may be real features we did not draw.|"
                 "On Tile B the five-model ensemble recovers 98% of the 62 pits and 88% of the 86 pads drawn. "
                 "That tile may not be fully drawn, so its precision, at least 52% and 54%, is a lower bound.|"
                 "Pits are the best target: highest average precision, sharpest outlines and the smallest search area."),
    ]),
]
# Results table: ann712 CV5, F2 threshold per fold, IoU 0.3 (docs/iterations/LEADERBOARD.md, 2026-09-17).
# Roads: recall_clean at thr 0.20 on 735 held-out segments; road precision is not object-scored, so it is left blank.
TABLE = [("", "Recall", "Precision", "IoU 0.5 recall", "Ground flagged"),
         ("Pits", "93%", "63%", "82%", "0.13%"),
         ("Pads", "91%", "59%", "77%", "10%"),
         ("Roads\u2020", "98%", "\u2014", "\u2014", "5.0%"),
         ("Pits, Tile B‡", "98%", "≥52%", "94%", "0.14%"),
         ("Pads, Tile B‡", "88%", "≥54%", "67%", "11%")]
TABLE_NOTE = ("Table 1. Held-out results, Area A, IoU 0.3 and F2 cutoff. A detection matches a hand outline when intersection over union (IoU) "
              "is at least 0.3. Ground flagged is the share of ground above the cutoff. \u2020Roads: 40 m chunks fully held out, single-split model, "
              "probability 0.20. \u2021Tile B, unseen in training, five-model ensemble. Precision is a lower bound because the tile may not be fully drawn.")
SPEC = [("Sign", "Grid, patch", "Classes", "Focal weights"),
        ("Pits", "0.5 m, 128 m", "background, floor, rim", "0.05, 0.475, 0.475"),
        ("Pads", "0.5 m, 192 m", "background, pad", "0.15, 0.85"),
        ("Roads", "1 m, 256 m", "background, road, drainage", "0.10, 0.72, 0.25")]
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
OUTLINE_TABLE = [TABLE[0]] + [(r[0], "[xx%]", "[xx%]", "[xx%]", "[xx%]") for r in TABLE[1:]]

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
            r0.font.size, r0.font.bold, r0.font.italic, r0.font.name = Pt(size), False, False, "Georgia"
            r0.font.color.rgb = color
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.italic, r.font.name = Pt(size), False, italic, "Georgia"
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
           "Hero figure. Aerial, relief map, pad probability, pit probability, one 400 m window", 40)
    text_box(s, C2, hero_y + HERO_H + 0.05, X1 - C2, 0.6,
             "[Hero caption: what the map shows and where]" if outline else CAPS["hero"][1], CAP_PT, GREY,
             lead=None if outline else CAPS["hero"][0])

    words = len(TAKEAWAY.split()) + len(HERO_CAPTION.split())
    col_end = {C1: BODY_TOP - 0.7, C2: LOWER - 0.7, C3: LOWER - 0.7}
    for si, (head, x, y, blocks) in enumerate(SECTIONS):
        stand_texts = iter(OUTLINE[si][1])
        y = col_end[x] + 0.7 if y is None else y      # stack under the previous section in the column
        text_box(s, x, y, CW, HEAD_H, OUTLINE[si][0] if outline else head, HEAD_PT, INK, anchor=MSO_ANCHOR.BOTTOM)
        words += len(head.split())
        rule_y = y + HEAD_H + 0.12
        rect(x, rule_y, CW, 0.05, UH_RED)
        top = rule_y + 0.4
        nxt = [b[0] for b in blocks][1:] + [None]
        for bi, (kind, key_or_text, h, note) in enumerate([(b[0], b[1], b[2] if len(b) > 2 else None,
                                                            b[3] if len(b) > 3 else None) for b in blocks]):
            if kind == "fig":
                ch = figure(key_or_text, x, top, CW, h, note)
                top += h + ch + 0.1
                if nxt[bi] == "text" and not outline:      # a thin rule and a clear gap set the caption apart from the body text
                    rect(x, top + 0.12, CW, 0.025, RULE)
                    top += 0.45
            elif kind == "spec":
                rh = h / len(SPEC)
                swd = [1.5, 3.0, 4.9, CW - 9.4]
                for r, row in enumerate(SPEC):
                    cx = x
                    for c, cell in enumerate(row):
                        text_box(s, cx, top + r * rh, swd[c], rh, cell, 26, INK if r else GREY, anchor=MSO_ANCHOR.MIDDLE)
                        cx += swd[c]
                    if r == 0:
                        rect(x, top + rh - 0.02, CW, 0.03, RULE)
                top += h + 0.3
            elif kind == "table":                       # recall and precision per sign, numbers large
                rh = (h - 0.6) / len(TABLE)
                nc = len(TABLE[0])
                cws = [2.3] + [(CW - 2.3) / (nc - 1)] * (nc - 1)
                for r, row in enumerate(OUTLINE_TABLE if outline else TABLE):
                    cx = x
                    for c, cell in enumerate(row):
                        big = r > 0 and c > 0
                        text_box(s, cx, top + r * rh, cws[c], rh, cell, 44 if big else 28,
                                 INK if (big or c == 0) else GREY, bold=big or c == 0,
                                 align=PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
                        cx += cws[c]
                    if r == 0:
                        rect(x, top + rh - 0.02, CW, 0.03, RULE)
                text_box(s, x, top + len(TABLE) * rh + 0.05, CW, 2.4,
                         "[Table note: define each column]" if outline else TABLE_NOTE[9:], 24, GREY,
                         lead=None if outline else "Table 1.")
                top += h + 1.7
            else:
                th = text_height(key_or_text)
                text_box(s, x, top, CW, th + 0.2, next(stand_texts) if outline else key_or_text, BODY_PT,
                         GREY if outline else INK, italic=outline)
                words += len(key_or_text.replace("|", " ").split())
                top += th + 0.3
        col_end[x] = top - 0.3
        if top - 0.3 > BODY_BOT + 0.05:
            print(f"WARNING: section '{head}' runs to y {top:.1f} in, past the body bottom {BODY_BOT}")

    # footer
    for head, x, w, note in (("References", X0, 19.0, "Ramachandran et al. 2024, Nat. Commun. 15, 7036. Saint-Vincent et al. 2021, J. Environ. Manage. 280, 111856. Gorantla, Sams, Reeder & Pekney 2024, Extended application of state LiDAR datasets in locating orphaned wells in the Appalachian region, NETL poster, AGU Fall Meeting. Sams, Mundia-Howe, Veloski & Hammack 2018, LiDAR mapping of 1860s oil fields along Pioneer Run, Oil Creek State Park, PA, NETL poster (OSTI 1569995). USGS 3D Elevation Program"),
                             ("Acknowledgements", X0 + 19.8, 14.0, "Lidar from the USGS 3D Elevation Program, project PA_WesternPA_2019_D20. Well records from the Pennsylvania Department of Environmental Protection. Funding: [to add].")):
        text_box(s, x, FOOT_TOP - 0.1, w, 0.8, head, 40, INK)
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
