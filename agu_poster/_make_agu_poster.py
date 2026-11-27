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
HERO_H = 8.2               # hero figure height, figure is 27.6 x 9.4 in
LOWER = BODY_TOP + 3.6 + HERO_H + 0.9     # top of the col 2 / col 3 sections under the hero

HEAD_PT, BODY_PT, CAP_PT = 50, 28, 24
HEAD_H = 1.05              # one-line statement heading at 54 pt
LINE = BODY_PT * 1.2 / 72  # body line height, in
CHARS = 74                 # body characters per line across one column at 44 pt (Calibri, measured)

TITLE = "Detecting orphaned oil and gas wells under forest canopy with airborne lidar and U-Nets"
TAKEAWAY = "Airborne lidar detects 93% of well pits and 91% of well pads under forest canopy"

FIG_FILES = {
    "intro": FIGS / "poster_pa_wells_locator.png",
    "optical": FIGS / "poster_optical_vs_lidar_9t.png",
    "channels": FIGS / "poster_channels_one_pit_9t.png",
    "signs": FIGS / "poster_signs_gallery_9t.png",
    "hero": FIGS / "poster_hero_heldout_9t.png",
    "setup": FIGS / "poster_pipeline_diagram.png",
    "valid": FIGS / "poster_cv_folds_pit_9t.png",
    "transfer": FIGS / "poster_transfer_613590.png",
}

# Numbered captions in reading order. Scale and data source are stated for every map.
CAPS = {
    "intro": ("Figure 1.", "Documented orphan and abandoned wells (yellow points) in western Pennsylvania, on a "
              "satellite base map. North is up. Source: Pennsylvania DEP records."),
    "optical": ("Figure 2.", "Aerial photograph (left) and a lidar relief image with the trees removed (right) of "
                "the same ground in study tile 9t."),
    "signs": ("Figure 3.", "Hand-drawn labels on a red relief image map. From left to right: pit (blue), pad (yellow) and road (white). A pit is a bowl with a raised rim, a pad is the flat work area and a road is the track to it. We outlined 712 pits and 995 pads. Panels are 60, 180 and 180 m wide."),
    "hero": ("Figure 4.", "Model output (filled) and hand labels (lines) on a red relief image map, a test block of tile 9t. "
             "(b) Found pit. (c) Missed pit. (d) Model pit with no hand label. Bars: 100 m in (a), 10 m in (b) to (d)."),
    "setup": ("Figure 5.", "Processing chain. One U-Net is trained for each of pits, pads and roads."),
    "valid": ("Figure 6.", "Spatial cross-validation on 375 m blocks. Blue blocks are held out, grey blocks train the model, white blocks are unused."),
    "transfer": ("Figure 5.", "Pit and pad models trained on tile 9t, run unchanged on tile 613590, on a red relief image map. (b) Pit and pad found. (c) Model pit with no hand label. Bars: 100 m in (a), 20 m in (b) and (c)."),
}

SECTIONS = [
    ("Introduction", C1, BODY_TOP, [
        ("fig", "intro", 4.2, "Map of Pennsylvania documented orphan wells"),
        ("text", "Orphan wells have no owner left to plug them and can leak methane and brine. "
                 "Pennsylvania lists thousands. Many more were never recorded.|Satellite pad detection recovers about "
                 "half the pads in Appalachia (Ramachandran et al. 2024). Old wells have been read from lidar by eye "
                 "(Sams et al.; Saint-Vincent et al. 2021).|Leaf-off lidar returns reach the ground through "
                 "deciduous canopy, so the pit, pad and access road that every well leaves can be mapped directly. "
                 "We ask whether a U-Net can find them automatically and how well it generalises to ground it has not seen."),
    ]),
    ("Study area and data", C1, None, [
        ("fig", "optical", 2.8, "Air photo and lidar of the same ground"),
        ("text", "USGS 3DEP lidar, flown leaf-off Nov 2019 to Mar 2020 over a 4.5 km square tile (9t). Ground returns are "
                 "gridded to a 0.5 m bare-earth model. Seven terrain layers are derived from it. They are local relief "
                 "at 25 m and 5 m, slope, topographic position, positive and negative openness, and roughness. "
                 "Each layer is standardised with training-set means and standard deviations before it enters the network."),
    ]),
    ("Well signatures", C1, None, [
        ("fig", "signs", 4.0, "Pit, pad, road on RRIM"),
    ]),
    ("Methods", C2, LOWER, [
                ("text", "Each sign gets its own four-level U-Net (base width 32, about 8 million parameters) that maps the seven layers to class probabilities.|"
                 "The pit model has three classes, background, pit floor and rim. Training minimises focal "
                 "cross-entropy (gamma 2) with class weights of 0.05 for background and 0.475 for each pit class, "
                 "which offsets the rarity of well pixels. Pads use two classes with weights 0.15 and 0.85.|"
                 "Patches are 128 m (pits) and 192 m (pads), centred on a label with random offsets of 30 m and 40 m. "
                 "We apply random 90-degree rotations and flips. Optimiser is AdamW, learning rate 1e-3, weight decay "
                 "1e-4, cosine schedule, 40 epochs, batch 16.|"
                 "Roads are modelled at 1 m with three classes, background, road and drainage. Drainage "
                 "channels resemble roads in relief, so they are an explicit negative class. "
                 "Road weight is 0.72. Probabilities above the cutoff are vectorised to outlines."),
    ]),
    ("Validation", C2, None, [
        ("text", "The tile is split by block, never by well, so a jittered patch cannot reach into a held-out block. "
                 "An inner validation set (20% of the remaining blocks) picks the best epoch and the cutoff. "
                 "The cutoff maximises F2, which weights recall four times as heavily as precision, because a missed "
                 "well costs more than a false alarm. The held-out fold never influences either choice. We hold out five sets of 375 m blocks in turn."),
        ("fig", "transfer", 5.0, "Predictions on tile 613590"),
    ]),
    ("Results", C3, LOWER, [
        ("table", None, 3.2, None),
        ("text", "At the F2 cutoff the pit model recovers 467 of 503 pits (92.8%) and the pad model 593 of 650 pads (91.2%). "
                 "Threshold-free average precision at IoU 0.3 is 0.82 for pits (95% bootstrap interval 0.78 to 0.86) "
                 "and 0.75 for pads (0.70 to 0.79).|"
                 "Pad recall falls from 91% to 77% when the match rule tightens from IoU 0.3 to 0.5. The model "
                 "finds the pads, but where a pad ends and a wide road begins is an arbitrary line, so pad outlines "
                 "differ from ours at the edges. Pit outlines are tighter, with 82% matching at 0.5. Precision is 0.63 and 0.59 by design of the F2 cutoff, and some unmatched detections may be real features we have not drawn.|"
                 "Applied unchanged to tile 613590, which neither model saw in training, the networks outline pads along "
                 "the access roads and place pits inside them (Figure 5). We drew only part of that tile, so precision "
                 "cannot be scored there."),
    ]),
    ("Conclusions", C3, None, [
        ("text", "Terrain layers from leaf-off lidar let a small U-Net recover more than 90% of labelled pits and pads in "
                 "blocks it never saw. Pits are the most reliable sign, with the best average precision and the tightest outlines.|"
                 "Limits. One 4.5 km tile. Labels are our own reading of the relief, made without the DEP well records. "
                 "Precision is below 0.65 and no site has been visited, so unmatched detections stay candidates.|"
                 "Next. Score a second labelled tile, then check detections in the field."),
    ]),
]
# Results table: ann712 CV5, F2 threshold per fold, IoU 0.3 (docs/iterations/LEADERBOARD.md, 2026-09-17).
# Roads: recall_clean at thr 0.20 on 735 held-out segments; road precision is not object-scored, so it is left blank.
TABLE = [("", "Recall", "Precision", "IoU 0.5 recall"),
         ("Pits", "93%", "63%", "82%"),
         ("Pads", "91%", "59%", "77%"),
         ("Roads", "98%", "—", "—")]
TABLE_NOTE = "Table 1. Held-out results, tile 9t. Recall and precision at IoU 0.3, F2 cutoff. A detection matches a hand outline when intersection over union (IoU) is at least 0.3. Roads are scored by segments recovered."
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
        text_box(s, x, y, CW, HEAD_H, OUTLINE[si][0] if outline else head, HEAD_PT, INK, anchor=MSO_ANCHOR.BOTTOM)
        words += len(head.split())
        rule_y = y + HEAD_H + 0.12
        rect(x, rule_y, CW, 0.05, UH_RED)
        top = rule_y + 0.4
        for kind, key_or_text, h, note in [(b[0], b[1], b[2] if len(b) > 2 else None,
                                            b[3] if len(b) > 3 else None) for b in blocks]:
            if kind == "fig":
                ch = figure(key_or_text, x, top, CW, h, note)
                top += h + ch + 0.1
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
                top += h + 1.3
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
    for head, x, w, note in (("References", X0, 19.0, "Ramachandran et al. 2024, Nat. Commun. 15, 7036. Saint-Vincent et al. 2021, J. Environ. Manage. 280, 111856. Sams et al., NETL, LiDAR mapping of 1860s oil fields, Pioneer Run (OSTI 1569995). USGS 3D Elevation Program"),
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
