"""Build deck v6 from v5. Layout engine plus per-slide written content.

v5 is not modified. v6 is written beside it.

WHAT THIS FIXES
---------------
1. MERGE. v5 split the Data QA opener across two slides. They belong together:
   the diagram says what the survey did, the cards say what it cost. One slide,
   two figures.

2. LAYOUT. v5 centres every figure under a title and leaves the explanation
   baked into the image at 11 pt. The terrain-derivative slides already do it
   right -- figure full-bleed on the right, text on the left -- and that is the
   pattern applied here to every BOX-shaped figure.

       box   aspect <= 1.40   figure bleeds off the right edge, full height;
                              headline and bullets occupy the left column
       wide  aspect >  1.40   figure runs full width under the title, with a
                              single one-line kicker; everything else is notes
       pair  two figures      side by side under the title

   A tall-ish figure squeezed into a left-text layout would be unreadable, which
   is why the rule is on aspect and not applied to everything.

3. TEXT OFF THE IMAGE. Every slide gets speaker notes. Where the layout has a
   left column, the same points appear there in large type. The rule the deck
   now follows: if a sentence matters, it is on the slide in 18 pt or in the
   notes -- never at 11 pt inside a PNG.

4. FOUR FIGURES REBUILT, in _build_v6_figures.py. See that file for why. The
   important one is the discarded-returns figure, which used green for
   "accepted" and red for "excluded" -- a red/green pair carrying different
   meanings, forbidden outright by the colourblind rule in CLAUDE.md.

WHAT THIS DOES NOT FIX
----------------------
Most figures still carry their own headline inside the PNG, because removing it
means editing the builder that drew it and there are thirteen of them. Those are
listed in NEEDS_FIGURE_SURGERY at the bottom and reported when the script runs,
so the remaining work is visible rather than implied.

Run:
    python docs/presentation/_build_deck_v6.py
    python docs/presentation/_build_deck_v6.py --dry-run
"""
from __future__ import annotations

import argparse
import copy
import io
import shutil
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
PRES = ROOT / "docs/presentation"
SRC = PRES / "WellSight_Presentation v5.pptx"
DST = PRES / "WellSight_Presentation v6.pptx"
V6 = PRES / "figures_30to45min/v6"

NSP = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
SLIDE_W, SLIDE_H = 13.3333, 7.5

INK = 0x14, 0x1A, 0x1F
INK2 = 0x54, 0x5C, 0x63
ACCENT = 0x00, 0x96, 0xC7

BOX_AR = 1.40          # at or below this, the figure goes on the right
TEXT_L, TEXT_W = 0.55, 5.15
TITLE_T, KICK_T, BULLET_T = 0.30, 1.55, 2.45


def rgb(t):
    from pptx.dml.color import RGBColor
    return RGBColor(*t)


# ---------------------------------------------------------------------------
# Per-slide content, keyed by the V5 slide number the user reviewed.
#   head    : the one thing to take away. Replaces the title where given.
#   bullets : plain-language points for the left column (box layout only)
#   notes   : speaker notes. Always written, on every slide.
#   figure  : override the embedded image with a v6 rebuild
#   layout  : force "box" / "wide" / "pair" instead of deciding on aspect
# ---------------------------------------------------------------------------
S = {
 9: dict(title="Data QA — the ground we were handed has holes in it",
     layout="pair", figures=["v6:where_ground_stops_is_not_here"],
     notes="Two things on one slide. Left: what the survey did — past 18 degrees "
           "off straight down it stops calling returns ground, deliberately and "
           "to specification. Right: what that cost us.\n\n"
           "The fourth box that used to be here said the discarded returns are "
           "no worse than the ones kept: 0.089 m against the neighbouring flight "
           "line, versus 0.087 m for the accepted ground. Matched at every slope. "
           "Say it, do not show it."),
 10: dict(skip=True),   # merged into 9
 11: dict(title="Data QA — where the ground stops",
     kicker="Ground classification falls off a cliff at one exact angle.",
     notes="Each line is one map square. The share of returns called ground is "
           "flat out to about 18 degrees and then collapses. That is not "
           "physics — a gradual falloff would be physics. A cliff at a round "
           "number is a processing rule."),
 12: dict(title="Data QA — one survey, not all of them",
     figure="where_ground_stops_by_flight_block_9t.png", layout="wide",
     kicker="Only the March 2020 flight block has the cut. It is one batch of "
            "flights, not a county and not a convention.",
     notes="REBUILT. The old version was two overlapping dot swarms on a shared "
           "axis, which is the one thing that cannot show a gap, because the "
           "dots land on top of each other.\n\n"
           "Blue is the angle range the vendor still called ground. Amber is "
           "what the scanner recorded and the vendor discarded. 165 of 177 "
           "squares in the March 2020 block are cut, every one at exactly 18 "
           "degrees, costing 191 million at-ground returns.\n\n"
           "The 2011 Venango delivery is shown hatched because it stores 0.000 "
           "in the scan-angle field for every square — the angle was never "
           "populated, so it cannot be checked either way. Drawing it as a "
           "zero-length bar would have read as 'no gap', which is the opposite "
           "of the truth."),
 13: dict(title="Data QA — are the discarded returns any good?",
     figure="discarded_returns_accuracy_vs_spec_9t.png", layout="wide",
     kicker="Yes. The returns the survey threw away measure as well as the ones "
            "it kept, and both clear the specification.",
     notes="REBUILT, and it had to be. The old figure coloured 'accepted' green "
           "and 'excluded' red — a red and a green carrying different meanings, "
           "which CLAUDE.md forbids outright and which is exactly the pair "
           "red/green colourblind viewers cannot separate. Now blue against "
           "amber, CVD worst-pair dE 26.1.\n\n"
           "It also dropped the twin histograms. They sat exactly on top of each "
           "other — that WAS the finding, but a reader sees one lump.\n\n"
           "Each return is compared with a plane fitted through class-2 ground "
           "from OTHER flight lines, so no line validates itself. On 621594 the "
           "thrown-away returns are actually the better of the two, 0.065 m "
           "against 0.099 m."),
 14: dict(title="Data QA — the ground surface we were given",
     kicker="Red is where there is no ground measurement at all.",
     bullets=["The red stripes run along the swath edges.",
              "13.8% of the training area has nothing under it.",
              "Where it is red, the surface is a guess between two rims."],
     notes="This is the delivered bare-earth surface. The red is not terrain, it "
           "is absence. Because the gaps follow the flight geometry they are "
           "systematic, not random, so they cannot be averaged away."),
 15: dict(title="Data QA — the ground that was thrown away",
     kicker="The same area, showing only the returns the survey discarded.",
     bullets=["13.7 million ground measurements.",
              "They fall in stripes along the flight-line edges.",
              "These are the returns that would fill the holes."],
     notes="Same window as the previous slide. Every point here hit the ground "
           "and was recorded, and none of it was called ground."),
 16: dict(title="Data QA — the two together",
     kicker="Put the discarded returns back and most of the holes close.",
     bullets=["13.8% with no measurement, down to 8.2%.",
              "2.9 million cells filled in.",
              "About a quarter of the holes close. The rest are canopy."],
     notes="Worth being precise about what this does and does not fix. Only "
           "26.8% of the void cells are wide-angle-only. 68.1% hold near-nadir "
           "returns and still have no ground, because the canopy occluded it. "
           "So the scan-angle cut is a real defect and a minority of the "
           "problem."),
 17: dict(title="Data QA — the same slice, before and after",
     kicker="One line across the ground, drawn twice.",
     bullets=["Top: only what the survey called ground.",
              "32% of that line has no ground under it at all.",
              "Bottom: the discarded returns added back. 2%."],
     notes="A single 200 m cross-section. The gaps in the top trace are the "
           "vertical red bands. The point of the pair is that the lower trace "
           "is the same ground, measured, not interpolated."),
 18: dict(title="Data QA — our ground classification against the vendor's",
     kicker="Where the vendor had ground we agree with it. We add ground where "
            "it had none.",
     notes="Three panels: the vendor's bare earth, ours, and the difference. "
           "1,415,359 returns recovered. Only 0.3% of the cells the vendor "
           "already covered move by more than 10 cm, which is the important "
           "control — we are not rewriting ground that was already there.\n\n"
           "Postscript worth saying out loud: we later retrained the pit model "
           "on this recovered surface and it changed nothing. No metric moved by "
           "more than fold-to-fold noise. This section is a rigour story, not a "
           "results story."),
 19: dict(title="Step 1: terrain derivatives",
     kicker="Eleven ways of looking at one hillside.",
     notes="The model never sees a photograph. It sees a stack of these. Seven "
           "of them go in as channels."),
 21: dict(title="Step 1: terrain derivatives — canopy height",
     bullets=["How tall are the green leafy things?",
              "The corn rows are NOT canopy.",
              "They are missing data — 3.2% of this window, where no first "
              "return came back."],
     notes="The stripes read as the tallest thing in the image because the "
           "drawing tool paints missing data as the page behind it, and on a "
           "black-to-white height ramp the page is brighter than the tallest "
           "tree.\n\n"
           "Measured: 11,603 cells, 3.22% of the window, bearing 79 degrees. "
           "Zero first returns land in any of them. The DEM underneath is 0.00% "
           "missing, so only the surface layer is gone.\n\n"
           "Canopy height is not one of the seven model channels, so nothing "
           "downstream is affected."),
 33: dict(title="Measured pit morphology",
     kicker="A shallow bowl about 0.7 m deep and 13 m across.",
     notes="Not the wellbore. This is the collapsed cellar that surrounded it. "
           "0.7 m is the number that sets the whole problem: it is why 1 m "
           "resolution is marginal and 0.5 m is not."),
 36: dict(title="Preprocessing — what was drawn, and what was worked out",
     kicker="Seven layers drawn by hand. Everything else is derived by code.",
     notes="The left column is what a human drew in QGIS. The right is what the "
           "pipeline computed from it. Keeping the two visibly separate is the "
           "point: a reviewer can see exactly where human judgement enters."),
 37: dict(title="Preprocessing — matching rims to floors",
     kicker="712 floors and 723 rims were drawn separately. Pairing them is a "
            "geometry problem, not a bookkeeping one.",
     notes="A pit was drawn twice: once round the outer rim, once round the "
           "floor inside it. Nothing linked the two. 586 pairs were matched by "
           "containment. 126 floors have no rim and 138 rims have no floor.\n\n"
           "Those leftovers are not errors to be tidied away — they are real "
           "features where only one of the two was visible."),
 39: dict(title="Preprocessing — resolving overlaps",
     kicker="Where two labels cover the same pixel, burn order decides.",
     notes="Wall is burned first and floor on top, so a cell inside both is "
           "floor. Stated here because it is the kind of choice that silently "
           "changes a metric if it is made twice in two different places."),
 40: dict(title="Preprocessing — the spatial block split",
     layout="wide",
     kicker="The tile is cut into a 12x12 grid and whole blocks are assigned, "
            "never individual pits.",
     notes="Splitting by pit would put a training pit 30 m from a test pit and "
           "the model would see the same ground twice. Splitting by block makes "
           "that impossible.\n\n"
           "Numbers in each block are pit floors. Blank blocks hold none."),
 41: dict(title="Preprocessing — why the split balances on pits, not on area",
     figure="split_share_of_map_vs_share_of_pits_9t.png", layout="wide",
     kicker="Pits cluster, so equal area does not mean equal evidence.",
     notes="REBUILT. The old panel had a legend reading 'share of pit floors' "
           "beside a blue swatch while the val bar was orange and the test bar "
           "green — three colours for one quantity. Here grey always means share "
           "of the map and blue always means share of the pits.\n\n"
           "Train takes 53% of the map but 70% of the pits. The 20% of the map "
           "marked unused holds no annotated pits at all, so it costs nothing to "
           "leave out."),
 42: dict(title="Preprocessing — one split, shared by every task",
     kicker="Pits, pads and roads all use the same block assignment.",
     notes="If each task drew its own split, a road chunk in one task's training "
           "set could sit on another task's test block. One assignment removes "
           "that whole class of leakage."),
 43: dict(title="Model building — the network",
     kicker="A U-Net. Seven input channels in, one probability per class out.",
     notes="Base 32, four levels, about 7.8 million parameters. Deliberately "
           "small — we tested deeper and pretrained encoders and none of them "
           "beat it by more than fold-to-fold noise."),
 44: dict(title="Model building — what the model outputs",
     kicker="Not a yes or a no. A probability for every half-metre cell.",
     notes="Brighter means more confident. The threshold that turns this into "
           "polygons is chosen on validation data and then frozen."),
 45: dict(title="Model building — committing to an answer",
     kicker="Above the threshold it becomes a candidate. Below it, nothing.",
     notes="The choice of threshold is a choice about what kind of mistake you "
           "prefer. We report two: one tuned for balance, one tuned to favour "
           "recall."),
 54: dict(title="Held-out tile 613590 — pit and pad candidates",
     kicker="A tile the model was never trained on. 42 pit and 161 pad "
            "candidates, with no retraining.",
     notes="This is the transfer test. 9t spans easting 619,500 to 624,000; "
           "613590 spans 613,500 to 618,000. No overlap, so nothing here leaked "
           "into training.\n\n"
           "Scored since: across all five cross-validation folds, recall on the "
           "153 annotated pit floors inside this tile is 0.911 under the "
           "recall-favouring threshold, against 0.928 on held-out 9t. A drop of "
           "0.017 — it transfers.\n\n"
           "Do NOT quote precision on this tile. It is not fully annotated, so "
           "an unmatched prediction may be a real pit nobody has drawn yet."),
}

#: Figures whose explanatory text is still baked into the PNG. Fixing these
#: means editing the builder that drew each one. Reported at the end of a run.
NEEDS_FIGURE_SURGERY = {
    11: "_scan_angle_cliff_across_acquisitions.py — headline + per-panel titles",
    14: "_recovered_ground_maps_9t.py — '1 — The ground we were given' + footer",
    15: "_recovered_ground_maps_9t.py — '2 — The ground that was thrown away'",
    16: "_recovered_ground_maps_9t.py — '3 — Both together' + red footer line",
    17: "_recovered_ground_maps_9t.py — title, two panel headings, two callouts",
    18: "_build_report_figures.py — three panel titles + stats line",
    19: "_build_derivative_overview.py — title, subtitle, reading-this box",
    36: "_build_method_diagrams.py — 'Drawn, or worked out afterwards'",
    37: "_build_preprocessing_figures.py — title + five inline counts",
    38: "_build_preprocessing_figures.py — 'The numbers we fixed once'",
    39: "_build_method_diagrams.py — title + three step captions",
    40: "_build_presentation_figures.py — panel a title + subtitle",
    42: "_build_preprocessing_figures.py — 'One split, shared by every task'",
    43: "_build_method_diagrams.py — 'The network' + channel annotations",
    46: "_build_rrim_vs_prob_compare.py — two panel headings per slide (46-53)",
}


def pic_of(slide):
    return [sh for sh in slide.shapes if sh.__class__.__name__ == "Picture"]


def img_aspect(blob):
    with Image.open(io.BytesIO(blob)) as im:
        w, h = im.size
    return w / h


def clear(slide):
    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)


def add_text(slide, l, t, w, h, runs):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for text, size, bold, colour, space in runs:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(space)
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = rgb(colour)
        r.font.name = "Calibri"
    return tb


def set_notes(slide, text):
    """Write speaker notes, even when the notes master has no body placeholder.

    python-pptx returns None from `notes_text_frame` when the notes master
    carries no body placeholder, which is the case in this deck. Falling back to
    a plain textbox on the notes slide keeps the text where PowerPoint's
    presenter view reads it.
    """
    ns = slide.notes_slide
    tf = ns.notes_text_frame
    if tf is not None:
        tf.text = text
        return
    # NotesSlideShapes has no add_textbox, so insert a body placeholder as raw
    # XML. type="body" is what presenter view and "export notes" both look for.
    from lxml import etree
    from pptx.oxml.ns import qn
    tree = ns.shapes._spTree
    sp = etree.SubElement(tree, qn("p:sp"))
    nv = etree.SubElement(sp, qn("p:nvSpPr"))
    cnv = etree.SubElement(nv, qn("p:cNvPr"))
    cnv.set("id", "90"); cnv.set("name", "Notes Placeholder")
    csp = etree.SubElement(nv, qn("p:cNvSpPr"))
    etree.SubElement(csp, qn("a:spLocks")).set("noGrp", "1")
    nvpr = etree.SubElement(nv, qn("p:nvPr"))
    ph = etree.SubElement(nvpr, qn("p:ph"))
    ph.set("type", "body"); ph.set("idx", "1")
    etree.SubElement(sp, qn("p:spPr"))
    tx = etree.SubElement(sp, qn("p:txBody"))
    etree.SubElement(tx, qn("a:bodyPr"))
    etree.SubElement(tx, qn("a:lstStyle"))
    for line in text.split("\n"):
        p = etree.SubElement(tx, qn("a:p"))
        if line:
            r = etree.SubElement(p, qn("a:r"))
            etree.SubElement(r, qn("a:t")).text = line


def place(slide, blob, box):
    """Centre an image in box=(l,t,w,h), preserving aspect."""
    import tempfile
    ar = img_aspect(blob)
    bl, bt, bw, bh = box
    w = bw
    h = w / ar
    if h > bh:
        h, w = bh, bh * ar
    f = Path(tempfile.mkstemp(suffix=".png")[1])
    f.write_bytes(blob)
    slide.shapes.add_picture(str(f), Inches(bl + (bw - w) / 2),
                             Inches(bt + (bh - h) / 2), Inches(w), Inches(h))
    return w, h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not a.dry_run:
        shutil.copy2(SRC, DST)
    prs = Presentation(str(DST if not a.dry_run else SRC))
    n0 = len(prs.slides)

    # --- capture what we need before mutating anything ------------------
    # Capturing the BODY text matters as much as the title. An earlier version
    # cleared each slide and rebuilt it from the spec alone, which silently
    # deleted the "How steep is it?" line off all nine derivative slides. What
    # the spec does not replace is carried over verbatim.
    blobs, titles, bodies = {}, {}, {}
    for i, s in enumerate(prs.slides, 1):
        blobs[i] = [x.image.blob for x in pic_of(s)]
        chunks = [[ln.strip() for ln in sh.text_frame.text.strip().splitlines()
                   if ln.strip()]
                  for sh in s.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()]
        if chunks:
            head = chunks[0]
            # v5's title box often holds two lines -- "Step 1: Terrain
            # Derivatives" then "Slope". Both belong in the title; treating the
            # second as a bullet demotes the name of the thing being shown.
            if len(head) >= 2:
                titles[i] = f"{head[0]} — {head[1]}"
                rest = head[2:]
            else:
                titles[i] = head[0]
                rest = []
            bodies[i] = rest + [ln for c in chunks[1:] for ln in c]

    counts = {"box": 0, "wide": 0, "pair": 0, "kept": 0}
    for i in range(9, 59):
        spec = S.get(i, {})
        if spec.get("skip"):
            continue
        slide = prs.slides[i - 1]
        title = spec.get("title", titles.get(i, ""))

        # figure blob: a v6 rebuild, or whatever v5 had
        if spec.get("figure"):
            blob = (V6 / spec["figure"]).read_bytes()
        elif blobs.get(i):
            blob = blobs[i][0]
        else:
            counts["kept"] += 1
            continue

        mode = spec.get("layout") or (
            "box" if img_aspect(blob) <= BOX_AR else "wide")
        # spec wins; otherwise keep whatever v5 had on the slide
        bullets = spec.get("bullets")
        if bullets is None:
            bullets = bodies.get(i, [])
        kicker = spec.get("kicker", "")

        clear(slide)

        if mode == "pair":
            # slide 9 only: the diagram and the cost cards, side by side
            left = (V6 / "scan_angle_cone_bare_9t.png").read_bytes()
            right = (V6 / "what_the_scan_angle_cut_cost_9t.png").read_bytes()
            add_text(slide, 0.55, TITLE_T, 12.2, 0.9,
                     [(title, 30, True, ACCENT, 0)])
            place(slide, left, (0.40, 1.45, 6.1, 5.6))
            place(slide, right, (6.75, 1.45, 6.1, 5.6))
            counts["pair"] += 1

        elif mode == "box":
            ar = img_aspect(blob)
            w = SLIDE_H * ar
            # 7.2 leaves a ~0.4 in gutter between the text column and the
            # picture. At 7.5 a square figure butts straight against the title
            # and its own corner caption reads as a collision.
            if w > 7.2:
                w = 7.2
            h = min(SLIDE_H, w / ar)
            slide.shapes.add_picture(
                str(_tmp(blob)), Inches(SLIDE_W - w),
                Inches((SLIDE_H - h) / 2), Inches(w), Inches(h))
            runs = [(title, 26, True, ACCENT, 14)]
            if kicker:
                runs.append((kicker, 18, True, INK, 12))
            for b in bullets:
                runs.append(("•  " + b, 16, False, INK2, 9))
            add_text(slide, TEXT_L, TITLE_T,
                     min(TEXT_W, SLIDE_W - w - 0.45), 6.6, runs)
            counts["box"] += 1

        else:  # wide
            add_text(slide, 0.55, TITLE_T, 12.2, 0.9,
                     [(title, 28, True, ACCENT, 0)])
            top = 1.30
            if kicker:
                add_text(slide, 0.58, 1.18, 12.1, 0.8,
                         [(kicker, 17, False, INK, 0)])
                top = 2.00
            place(slide, blob, (0.45, top, 12.45, SLIDE_H - top - 0.25))
            counts["wide"] += 1

        # Notes always get something. Where the wide layout had no room for the
        # carried-over body text, the notes are where it goes rather than
        # nowhere.
        note = spec.get("notes", "").strip()
        carried = bodies.get(i, [])
        if mode == "wide" and carried and not spec.get("bullets"):
            extra = "From the slide: " + "  ".join(carried)
            note = (note + "\n\n" + extra).strip() if note else extra
        if not note:
            note = ("(no speaker notes written yet — the figure still carries "
                    "its own caption)")
        set_notes(slide, note)

    # --- drop the merged slide ------------------------------------------
    lst = prs.slides._sldIdLst
    ids = list(lst)
    rid = ids[9]                      # v5 slide 10, zero-indexed
    prs.part.drop_rel(rid.rId)
    lst.remove(rid)

    print(f"v5 {n0} slides -> v6 {len(prs.slides)} slides")
    print(f"  layouts: box {counts['box']}, wide {counts['wide']}, "
          f"pair {counts['pair']}, untouched {counts['kept']}")
    print(f"\nstill carrying baked-in text inside the PNG "
          f"({len(NEEDS_FIGURE_SURGERY)} figures):")
    for k, v in sorted(NEEDS_FIGURE_SURGERY.items()):
        print(f"  v5 slide {k:3d}  {v}")

    if a.dry_run:
        print("\n--dry-run, nothing written")
        return 0
    prs.save(str(DST))
    print(f"\n{DST}")
    return 0


def _tmp(blob):
    import tempfile
    f = Path(tempfile.mkstemp(suffix=".png")[1])
    f.write_bytes(blob)
    return f


if __name__ == "__main__":
    raise SystemExit(main())
