"""Build the 30-45 minute WellSight talk.

Writes  docs/presentation/WellSight_Generated.pptx
Reads   docs/presentation/WellSight_Presentation.pptx  (never modified)

STRATEGY
--------
The May deck's slides 1-7 are the problem statement and they are still good, so
they are KEPT AS THEY ARE -- copied through with their speaker notes rather than
retyped. Slides 8-12 (the classical method) are cut. Slides 13, 14 and the
appendix are rescued and moved. Everything else is new.

That means this script opens the old deck, deletes what goes, and appends the
new acts. It never writes to the original.

    Act I    kept slides 1-7
    Act II   from points to polygons        11 new + 2 rescued
    Act III  the models                     10 new
    Act IV   what they find                  7 new
    Act V    does it travel                  4 new
    Act VI   what went wrong                 3 new
    Act VII  where it goes                   3 new
    appendix rescued from the old deck

Slide content follows presentation_update_worklist_30to45min.md. Numbers come
from LEADERBOARD.md, the threshold sweeps, and annotations_proj.gpkg; every one
of them is sourced in figure_notes_what_each_image_shows.md or the worklist.

FIGURES ON A DARK DECK
----------------------
The deck background is #1A1A2E. The nine figures are drawn light, on #fcfcfb.
Dropped straight on they read as holes, so `figure()` lays a white card down
first and centres the image on it. That is the least-work option of the three in
HOW_TO_BUILD_THE_TALK.md, and it looks deliberate.

Run:
    python docs/presentation/_build_presentation_v2.py
"""
from copy import deepcopy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "docs" / "presentation"
FIGS = HERE / "figures_30to45min"
SRC = HERE / "WellSight_Presentation.pptx"
OUT = HERE / "WellSight_Generated.pptx"

# palette, copied from the May builder so the new slides match the kept ones
DARK = RGBColor(0x1A, 0x1A, 0x2E)
ACCENT = RGBColor(0x00, 0x96, 0xC7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF0, 0xF0, 0xF0)
ORANGE = RGBColor(0xFF, 0x57, 0x22)
GREEN = RGBColor(0x4C, 0xAF, 0x50)
BLUE = RGBColor(0x21, 0x96, 0xF3)
GRAY = RGBColor(0xAA, 0xAA, 0xAA)

# slides to keep from the old deck, 0-based, in their original order
KEEP_ACT_I = [0, 1, 2, 3, 4, 5, 6]          # title + the problem
KEEP_MORPHOLOGY = 12                         # "Measured Pit Morphology"
KEEP_QC = 13                                 # "Annotation Quality Control"
KEEP_APPENDIX = [17, 18, 19]                 # references + 3DEP + literature params


# --------------------------------------------------------------- helpers
def add_bg(slide):
    from pptx.util import Emu
    r = slide.shapes.add_shape(1, 0, 0, Emu(12192000), Emu(6858000))
    r.fill.solid()
    r.fill.fore_color.rgb = DARK
    r.line.fill.background()
    slide.shapes._spTree.remove(r._element)
    slide.shapes._spTree.insert(2, r._element)
    return r


def tb(slide, left, top, width, height, text, size=18, color=WHITE, bold=False,
       align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width),
                                   Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = align
    p.font.size = Pt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    return box


def bullets(slide, left, top, width, height, items, size=18, color=WHITE):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width),
                                   Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.space_after = Pt(10)
    return box


def figure(slide, name, left, top, width, pad=0.12):
    """White card, then the image on top. The figures are light-mode."""
    p = FIGS / name
    if not p.exists():
        print(f"  SKIP figure: {name}")
        return
    from PIL import Image
    w_px, h_px = Image.open(p).size
    height = width * h_px / w_px
    card = slide.shapes.add_shape(1, Inches(left - pad), Inches(top - pad),
                                  Inches(width + 2 * pad), Inches(height + 2 * pad))
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(0xFC, 0xFC, 0xFB)
    card.line.fill.background()
    card.shadow.inherit = False
    slide.shapes.add_picture(str(p), Inches(left), Inches(top), width=Inches(width))


def img(slide, path, left, top, width=None, height=None):
    p = Path(path)
    if not p.exists():
        print(f"  SKIP: {p}")
        return
    kw = {}
    if width:
        kw["width"] = Inches(width)
    if height:
        kw["height"] = Inches(height)
    slide.shapes.add_picture(str(p), Inches(left), Inches(top), **kw)


def tbl(slide, left, top, width, height, data, first_col_w=None):
    rows, cols = len(data), len(data[0])
    shape = slide.shapes.add_table(rows, cols, Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    t = shape.table
    if first_col_w:
        t.columns[0].width = Inches(first_col_w)
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            cell = t.cell(i, j)
            cell.text = str(val)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(13)
                p.font.bold = (i == 0)
                p.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    return t


def slide_new(prs, title, subtitle=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(s)
    tb(s, 0.5, 0.30, 12.3, 0.8, title, size=30, bold=True, color=WHITE)
    if subtitle:
        tb(s, 0.5, 1.02, 12.3, 0.5, subtitle, size=15, color=ACCENT)
    return s


_NOTES_TEMPLATE = []          # filled on first use


def notes(slide, text):
    """Set speaker notes.

    The notes MASTER in this deck carries no placeholders, so a freshly created
    notes slide has no body and ``notes_text_frame`` is None. The kept slides do
    have one, so the first call harvests that element and later calls clone it.
    """
    ns = slide.notes_slide
    if ns.notes_text_frame is None:
        if not _NOTES_TEMPLATE:
            raise RuntimeError("no notes placeholder harvested yet")
        ph = deepcopy(_NOTES_TEMPLATE[0])
        ns.shapes._spTree.append(ph)
    ns.notes_text_frame.text = text


def section(prs, roman, title, blurb):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(s)
    tb(s, 0.8, 2.5, 11.7, 0.8, roman, size=20, color=ACCENT, bold=True)
    tb(s, 0.8, 3.1, 11.7, 1.2, title, size=44, bold=True, color=WHITE)
    tb(s, 0.8, 4.4, 11.7, 0.8, blurb, size=17, color=GRAY)
    return s


# --------------------------------------------------------------- slide surgery
def drop_slides(prs, keep_idx):
    """Delete every slide whose original index is not in keep_idx."""
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    for i, sld in enumerate(slides):
        if i not in keep_idx:
            rid = sld.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            prs.part.drop_rel(rid)
            xml_slides.remove(sld)


def reorder(prs, desired):
    """Reorder the deck to exactly `desired`, a list of slide objects.

    Index arithmetic after a delete-then-append is how slides end up in the
    wrong act, so the order is stated as objects and applied once.
    """
    live = list(prs.slides)
    assert len(desired) == len(live), f"{len(desired)} ordered vs {len(live)} present"
    lst = prs.slides._sldIdLst
    elems = list(lst)
    by_slide = {id(sl): el for sl, el in zip(live, elems)}
    for el in elems:
        lst.remove(el)
    for sl in desired:
        lst.append(by_slide[id(sl)])


# =============================================================== build
def main() -> int:
    # Pass 1 -- drop what goes, then round-trip through a temp file. Dropping
    # slide relationships leaves the package renumbering stale, and saving
    # directly produces duplicate ppt/slides/slideN.xml entries that PowerPoint
    # offers to "repair". Reopening a saved copy rebuilds the part names clean.
    _p0 = Presentation(str(SRC))
    n_before = len(_p0.slides)
    keep0 = set(KEEP_ACT_I) | {KEEP_MORPHOLOGY, KEEP_QC} | set(KEEP_APPENDIX)
    drop_slides(_p0, keep0)
    _tmp = OUT.with_name("_tmp_kept.pptx")
    _p0.save(str(_tmp))

    prs = Presentation(str(_tmp))

    # Harvest a working notes placeholder from a slide that already has one.
    for _s in prs.slides:
        _ns = _s.notes_slide
        if _ns.notes_text_frame is not None:
            for _sh in _ns.shapes:
                if _sh.is_placeholder and "Notes" in _sh.name:
                    _NOTES_TEMPLATE.append(deepcopy(_sh.element))
                    break
        if _NOTES_TEMPLATE:
            break
    print(f"notes placeholder harvested: {bool(_NOTES_TEMPLATE)}")

    kept = list(prs.slides)
    print(f"kept {len(kept)} of {n_before} old slides")
    ACT_I = kept[0:7]
    MORPHOLOGY, QC = kept[7], kept[8]
    APPENDIX = kept[9:12]
    made = []                      # every slide this script creates, in order

    # ---------------------------------------------------------- Act II
    section(prs, "ACT II", "From points to polygons",
            "The May talk detected locations. Everything since is geometry.")

    s = slide_new(prs, "What a label was in May",
                  "an x/y and a confidence score")
    bullets(s, 0.6, 1.9, 6.0, 4.5, [
        "Template matching scored a location.",
        "The ensemble ranked it.",
        "A candidate was a point with a number attached.",
        "",
        "A point can only be right or wrong.",
        "It cannot be the wrong size.",
        "It cannot be one object counted twice.",
    ], size=19)
    tb(s, 7.0, 2.2, 5.7, 3.0,
       "So the only question we could ask was:\ndid we look in the right place?",
       size=22, color=ACCENT)
    notes(s, "Set up the limitation without disparaging the old work. It found "
             "things. It just could not describe them.")

    s = slide_new(prs, "The annotation schema",
                  "8,609 features, drawn by hand in QGIS")
    tbl(s, 0.6, 1.7, 7.6, 4.4, [
        ["layer", "features", "what it is"],
        ["pad", "995", "disturbed footprint"],
        ["pit_inside", "712", "floor"],
        ["pit_wall", "586", "rim"],
        ["pit_full", "723", "floor + rim"],
        ["roads", "3,690", "access traces"],
        ["not_roads", "112", "hand-drawn negatives"],
        ["drainage", "1,791", "segmented channels"],
    ], first_col_w=2.0)
    tb(s, 8.6, 2.0, 4.2, 3.5,
       "Seven layers.\n\nEvery one drawn by hand,\nover 0.5 m hillshade.\n\n"
       "This is the expensive part\nof the project.",
       size=19, color=ACCENT)
    notes(s, "Counts are live from annotations_proj.gpkg as of 2026-09-17. "
             "If asked: roughly a year of intermittent annotation.")

    s = slide_new(prs, "Why floor, rim and depression are three layers")
    figure(s, "annotation_schema_pad_and_pit_9t.png", 0.7, 1.9, 11.9)
    tb(s, 0.5, 6.85, 12.3, 0.5,
       "Floor is what you delineate. Rim is what you locate against. "
       "Full is the whole depression.", size=15, color=GRAY)
    notes(s, "Pad 896, chosen by rule not by eye: the pad inside 9t with the "
             "most annotated floors, ties broken by area. Rim containment as a "
             "metric exists because of this split.")

    s = slide_new(prs, "No pad is a cluster of pits",
                  "995 pads hold 712 floors")
    tb(s, 1.0, 2.4, 11.0, 1.2,
       "No pad inside the study tile carries more than two annotated pit floors.",
       size=28, bold=True, color=ACCENT)
    bullets(s, 1.0, 3.9, 11.0, 2.0, [
        "The intuition is that a pad is a site with several pits on it.",
        "In this data it is not. One pit, sometimes two.",
        "It changes what a pad detection means: a pad is context, not a count.",
    ], size=18)
    notes(s, "CUT CANDIDATE if running long. Surfaced while building the "
             "schema figure -- max floors per pad is 2, across all 650 pads "
             "inside 9t.")

    s = slide_new(prs, "The annotation is a moving target",
                  "426 to 527 to 712 pit floors")
    figure(s, "annotation_growth_pits_9t.png", 0.6, 1.8, 6.1)
    figure(s, "annotation_growth_pads_9t.png", 7.0, 1.8, 5.8)
    notes(s, "The point is the reassignment, not the growth. Every expansion "
             "rebuilds the split, so no earlier checkpoint stays held out. "
             "That is why the leaderboard carried a STALE banner.")

    s = slide_new(prs, "Project-wide against in-tile",
                  "say it once, so no later number is ambiguous")
    tbl(s, 1.2, 2.1, 10.6, 2.2, [
        ["", "annotated", "inside the training tile"],
        ["pit floors", "712", "503"],
        ["pads", "995", "650"],
    ], first_col_w=3.0)
    tb(s, 1.2, 4.7, 10.6, 1.2,
       "The rest lie in other tiles. They are annotated, and no model has seen "
       "them yet.", size=18, color=ACCENT)
    notes(s, "This replaces the old slide 10's '861 pits', which predates both "
             "counts. Drop that number entirely.")

    s = slide_new(prs, "The stage pipeline",
                  "s1_build through s7_analysis, 87 scripts")
    bullets(s, 0.8, 1.9, 11.5, 4.6, [
        "s1  build        point cloud to DEM to seven terrain channels",
        "s2  labels       drawings to label rasters, blocks and manifests",
        "s3  train        the U-Nets",
        "s4  infer        probability rasters across a whole tile",
        "s5  eval         thresholds, recall, precision, containment",
        "s6  review       build a QGIS package, take corrections back in",
        "s7  analysis     morphology, change detection, provenance",
    ], size=18)
    tb(s, 0.8, 6.4, 11.5, 0.6,
       "s6 feeds back into s2. That arrow is the only closed loop in the system.",
       size=16, color=ACCENT)
    notes(s, "Do not read the list. Point at it, then say the loop sentence.")

    s = slide_new(prs, "Polygons into label grids",
                  "0 background, 1 floor, 2 rim, 255 ignore")
    bullets(s, 0.8, 2.0, 11.4, 4.0, [
        "Rim is painted first, floor on top, so shared pixels become floor.",
        "Streams first, roads over them, so a road crossing a stream stays road.",
        "255 means ignore -- the loss function is set to skip it.",
        "Every raster is cut to the DEM's grid, so labels and inputs align by "
        "construction rather than by assumption.",
    ], size=19)
    notes(s, "The 255 detail sounds trivial and is not: it is a contract "
             "between four separate scripts.")

    s = slide_new(prs, "The spatial split",
                  "why a random split would have flattered us")
    figure(s, "split_blocks_12x12_9t.png", 0.7, 1.8, 7.4)
    bullets(s, 8.4, 2.0, 4.4, 4.3, [
        "Training windows wobble 30 m.",
        "So a window on a training pit can cover the pit next door.",
        "If that neighbour is a test pit, the score is inflated.",
        "Whole blocks go to one split, never split features.",
        "Balanced on feature count, not block count -- pits cluster.",
    ], size=16)
    notes(s, "If you say one methodological thing in the whole talk, say this "
             "one. val gets 14 blocks and test 24, yet they hold 77 and 74 pits.")

    s = slide_new(prs, "The review loop",
                  "generate, correct, diff, retrain")
    bullets(s, 0.8, 2.0, 11.4, 4.2, [
        "The model proposes. A package opens in QGIS.",
        "A human accepts, moves or rejects each one.",
        "The diff becomes new training data -- rejects become hard negatives.",
        "Retrain on the difference, not on everything again.",
    ], size=19)
    tb(s, 0.8, 6.0, 11.4, 0.8,
       "The result this bought is in Act III.", size=17, color=ACCENT)
    notes(s, "Mechanism here, result later, so the road story is not split "
             "across twenty minutes.")

    s = slide_new(prs, "What went wrong in the data pipeline",
                  "the unglamorous half of the corrections")
    bullets(s, 0.8, 2.0, 11.4, 4.2, [
        "A rebuild overwrote the manifest and reassigned the folds under a "
        "deployed model. Recovered from a mirror.",
        "A guard now refuses to overwrite a manifest whose feature count moved.",
        "A column called plat_id meant pad. pit_outside meant the whole "
        "depression. Both renamed across 254 lines.",
    ], size=18)
    notes(s, "CUT CANDIDATE. Keep if the audience is technical. The honest "
             "version of 'we had a reproducibility problem and fixed it'.")

    # ---------------------------------------------------------- Act III
    section(prs, "ACT III", "The models",
            "Four targets, one architecture, one grid.")

    s = slide_new(prs, "Why segmentation",
                  "the shape is the evidence")
    bullets(s, 0.8, 2.0, 11.4, 4.0, [
        "A detector says where. A segmenter says where and what shape.",
        "Pit depth and diameter are the evidence a pit is a pit.",
        "The same network handles floors, pads, roads and channels -- only the "
        "labels and the class weights change.",
    ], size=19)
    notes(s, "If asked why not template matching: we started there. It worked "
             "well enough to be worth annotating for, and badly enough that we "
             "needed shape rather than location.")

    s = slide_new(prs, "Architecture and inputs",
                  "seven channels, 256-pixel windows")
    bullets(s, 0.8, 1.9, 6.4, 4.5, [
        "U-Net, four levels, ~8 million parameters.",
        "Seven input channels in a frozen order:",
        "   local relief 25 and 5",
        "   slope, TPI",
        "   openness positive and negative",
        "   roughness",
        "Focal cross-entropy, because pits are 0.2% of the ground.",
    ], size=17)
    tb(s, 7.6, 2.2, 5.2, 3.2,
       "Small model on purpose.\n\nMask R-CNN at 45.9 M parameters\noverfit this "
       "much data --\nbest validation loss at epoch 1,\nthen it climbed.",
       size=17, color=ORANGE)
    notes(s, "The channel order being frozen matters: bands are read by "
             "position, so reordering silently feeds slope where the model "
             "learned openness.")

    s = slide_new(prs, "Pit model")
    img(s, ROOT / "data/9t/models/pit/unet_v2/test_preds.png", 0.6, 1.8, width=12.1)
    notes(s, "Qualitative first, numbers in Act IV. Let them look.")

    s = slide_new(prs, "Pad model")
    img(s, ROOT / "data/9t/models/pad/unet/test_preds.png", 0.6, 1.8, width=12.1)
    notes(s, "Pads are large and low-contrast. This is the weak model and Act "
             "IV says so with a number.")

    s = slide_new(prs, "The road model, and what broke it",
                  "streams look exactly like roads from above")
    bullets(s, 0.8, 2.0, 11.4, 4.0, [
        "A two-class road model fired on every drainage channel.",
        "The obvious fix is a filter afterwards. We tried that. It was brittle.",
        "Instead drainage became a class the model has to name.",
    ], size=19)
    notes(s, "Set up the next slide. Do not give the number yet.")

    s = slide_new(prs, "Fixed in training, not in post",
                  "drainage as its own class")
    tbl(s, 1.0, 2.0, 11.0, 2.4, [
        ["", "P(road) on roads", "P(road) on channels", "pixel IoU"],
        ["2-class", "0.654", "-- fired freely", "0.379"],
        ["3-class", "0.676", "0.005", "0.527"],
        ["3-class + chunked", "0.757", "0.006", "0.581"],
    ], first_col_w=3.2)
    tb(s, 1.0, 4.9, 11.0, 1.4,
       "Held-out hand-drawn negatives are claimed at 0.0% at every threshold.",
       size=19, color=GREEN)
    notes(s, "This is the cleanest methodological story in the talk: the fix "
             "belonged in the label design, not in post-processing.")

    s = slide_new(prs, "Chunking",
                  "a kilometre of road and a 30 m stub are not one example each")
    bullets(s, 0.8, 2.0, 11.4, 4.0, [
        "Roads are cut into ~40 m pieces before sampling.",
        "Every stretch becomes its own training centre and its own test unit.",
        "Evaluation went from 27 lopsided lines to 168 comparable chunks.",
        "Line AP moved 0.963 to 0.992 on the same data.",
    ], size=19)
    notes(s, "Be honest about the leakage this introduces: 39.8% of held-out "
             "chunks share a parent road with a training chunk. recall_clean is "
             "the comparable number and costs about 1.5 points.")

    s = slide_new(prs, "The drainage model",
                  "the same network with the weights flipped")
    bullets(s, 0.8, 2.0, 11.4, 3.6, [
        "Same data, same channels, same 3-class raster.",
        "Focal weights swapped so drainage is the positive and road the "
        "hard negative.",
        "Separation between the two classes: AP 0.990.",
        "Mean drainage probability on road pixels: 0.0016.",
    ], size=19)
    notes(s, "Each model rejects the other's class almost perfectly. That "
             "symmetry is the evidence the 3-class design works in both "
             "directions.")

    s = slide_new(prs, "Active learning, closed",
                  "22 km of human corrections")
    img(s, ROOT / "data/9t/models/road/unet_1m_corrected/compare_corrections_full.png",
        0.6, 1.9, width=12.1)
    notes(s, "The loop from Act II, and what it bought.")

    s = slide_new(prs, "What the corrections bought",
                  "measured out of domain, on a tile the model never trained on")
    tbl(s, 1.2, 2.0, 10.6, 2.4, [
        ["", "before", "after"],
        ["mean P(road) on missed roads", "0.72", "0.76"],
        ["fraction above 0.5", "0.85", "0.94"],
        ["added-vs-reject AP", "0.245", "0.443"],
    ], first_col_w=4.4)
    tb(s, 1.2, 4.9, 10.6, 1.2,
       "Zero in-domain cost. 188 km of corrected road folded back into the "
       "annotation.", size=19, color=GREEN)
    notes(s, "The human is in the loop by design. This is the slide that shows "
             "annotation effort converting directly into out-of-domain gain.")

    s = slide_new(prs, "Cross-validation",
                  "five models, every feature scored by one that never saw it")
    bullets(s, 0.8, 2.0, 11.4, 4.0, [
        "One split of 65 test pits is too small to separate a 3-point "
        "difference from noise.",
        "So: train five times, each holding out a different fifth of the tile.",
        "Folds are recomputed from the manifest every time, which is why the "
        "annotation growth forced a retrain.",
        "Five times the compute, and it removes 'you got a lucky split' from "
        "the conversation.",
    ], size=18)
    notes(s, "Per-fold spread is the honest measure of how much any single "
             "number can be trusted: pit recall spans 0.810 to 0.911.")

    # ---------------------------------------------------------- Act IV
    section(prs, "ACT IV", "What they find",
            "Scored against hand-drawn annotation withheld from training.")

    s = slide_new(prs, "How this is scored",
                  "no DEP list, no TIGER, no circularity")
    bullets(s, 0.8, 2.0, 11.4, 4.2, [
        "Ground truth is hand-drawn annotation held out of training.",
        "Recall: of the annotations withheld, how many did it find.",
        "Precision: of what it flagged, how much was real.",
        "Containment: did the prediction land inside the annotated rim.",
        "Thresholds chosen on a validation split under a rule declared in "
        "advance, then frozen and scored once.",
    ], size=18)
    notes(s, "Picking the threshold after seeing the test result is the most "
             "common way to fool yourself and it is invisible in a results "
             "table. Say that.")

    s = slide_new(prs, "How much ground does it flag?",
                  "the search burden a field crew inherits")
    figure(s, "threshold_sweep_9t.png",
           0.6, 1.9, 12.1)
    notes(s, "Panel a only on this slide -- talk over the left half. The log "
             "axis is necessary: pit and pad are two orders of magnitude apart.")

    s = slide_new(prs, "And how much of it does it find?",
                  "the same nine cutoffs, the other question")
    tb(s, 1.0, 2.2, 11.3, 1.4,
       "At a 0.20 cutoff the pit model flags 4.33 hectares of 2,025 "
       "-- 0.21% of the tile --", size=24, color=WHITE)
    tb(s, 1.0, 3.6, 11.3, 1.4,
       "and finds 126 of 127 withheld pit rims.", size=32, bold=True, color=GREEN)
    tb(s, 1.0, 5.3, 11.3, 1.2,
       "Roads: 5.02% of the tile, 0.982 recall.      "
       "Pads: 11.64% of the tile, 0.918 recall.", size=18, color=GRAY)
    notes(s, "This is the headline of the talk. Slow down. Let the 0.21% and "
             "the 126/127 sit next to each other before moving on.")

    s = slide_new(prs, "Pit, cross-validated",
                  "ann712, five folds, every pit scored blind")
    tbl(s, 1.2, 2.0, 10.6, 2.4, [
        ["threshold rule", "recall @ IoU 0.3", "precision", "containment"],
        ["F1 (balanced)", "0.861", "0.686", "0.914"],
        ["F2 (recall-weighted)", "0.928", "0.633", "0.956"],
    ], first_col_w=3.6)
    tb(s, 1.2, 4.8, 10.6, 1.4,
       "Both rules declared before any held-out data was scored. "
       "Reporting both is the opposite of cherry-picking.", size=18, color=ACCENT)
    notes(s, "F2 weights recall four times precision -- a missed well costs "
             "more than a false alarm. That is a policy choice, so we show both.")

    s = slide_new(prs, "Pad, cross-validated",
                  "and this is the weak model")
    tbl(s, 1.2, 2.0, 10.6, 2.0, [
        ["threshold rule", "recall @ IoU 0.3", "precision", "locate"],
        ["F1", "0.888", "0.597", "0.923"],
        ["F2", "0.912", "0.587", "0.917"],
    ], first_col_w=3.6)
    tb(s, 1.2, 4.4, 10.6, 1.8,
       "The pad model needs 55 times the ground of the pit model to find fewer "
       "of its targets. At a 0.50 cutoff it over-claims by about 2x.",
       size=19, color=ORANGE)
    notes(s, "Name your weak model before someone else does. It buys credit "
             "for everything else on the page.")

    s = slide_new(prs, "Precision is the ceiling",
                  "and it has not moved")
    bullets(s, 0.8, 2.0, 11.4, 4.2, [
        "Recall is strong and stable across folds and thresholds.",
        "Precision never exceeds about 0.69 on either task, at any cutoff.",
        "More annotation did not fix it. More capacity did not fix it.",
        "It is the open problem, and it is where the next work goes.",
    ], size=19)
    notes(s, "Stating the limitation plainly is stronger than being asked "
             "about it. It also sets up Act VII.")

    s = slide_new(prs, "What more annotation did",
                  "not what we expected")
    tbl(s, 1.0, 2.0, 11.0, 2.4, [
        ["", "pits", "recall", "precision"],
        ["ann426", "426", "0.854", "0.617"],
        ["ann527", "527", "0.890", "0.637"],
        ["ann712", "712", "0.861", "0.686"],
    ], first_col_w=2.6)
    tb(s, 1.0, 4.8, 11.0, 1.6,
       "Precision rose. Recall did not. One reading is that some old 'false "
       "positives' were real pits nobody had drawn yet -- but the pads did not "
       "reproduce it, so it stays a hypothesis.", size=17, color=GRAY)
    notes(s, "CUT CANDIDATE. Include it if the room is technical: admitting an "
             "unconfirmed explanation is more persuasive than asserting one.")

    # ---------------------------------------------------------- Act V
    section(prs, "ACT V", "Does it travel?",
            "A held-out tile is not a held-out region.")

    s = slide_new(prs, "Out of domain",
                  "613590 -- a tile no road model ever trained on")
    bullets(s, 0.8, 2.0, 11.4, 4.0, [
        "Cross-validation shows a number is stable. It does not show it travels.",
        "Every fold is still the same tile, the same survey, the same terrain.",
        "613590 is a different tile with its own hand-drawn ground truth.",
        "Only the roads drawn from scratch count -- the rest is a previous "
        "model's output that a human vetted, and every model scores 0.96+ on it.",
    ], size=18)
    notes(s, "Explaining why half the ground truth is unusable, before quoting "
             "the number, is what makes the number believable.")

    s = slide_new(prs, "Road transfer, and what beat architecture",
                  "measured on roads drawn from scratch")
    tbl(s, 1.0, 1.9, 11.0, 2.0, [
        ["", "completeness", "correctness", "quality"],
        ["best model that never saw the tile", "0.811", "0.816", "0.686"],
        ["ensemble, maximum recovery", "0.909", "0.651", "--"],
    ], first_col_w=5.2)
    tb(s, 1.0, 4.3, 11.0, 2.0,
       "Fixing 19 km of mislabelled road bought +0.146 completeness at zero "
       "correctness cost.\n\nThat is more than any architecture change in a "
       "seven-variant sweep.", size=19, color=GREEN)
    notes(s, "The lesson of the project in one line: the labels were the "
             "bottleneck, not the model.")

    s = slide_new(prs, "Change detection",
                  "2006-2008 against 2019, and a null result")
    bullets(s, 0.8, 2.0, 11.4, 4.2, [
        "Two surveys, thirteen years apart, differenced after a single ICP "
        "alignment.",
        "An apparent subsidence signal at known wells looked significant.",
        "It was circular: the 'well list' was 861 pits hand-digitised on the "
        "2019 surface.",
        "The older survey resolves only 72% of pit depth at seven times lower "
        "density. That fully explains the signal.",
    ], size=18)
    notes(s, "A null result you found yourself is worth more than a positive "
             "one you did not test. This is also a bridge into Act VI.")

    s = slide_new(prs, "Radar",
                  "NISAR L-band over Pennsylvania canopy")
    figure(s, "nisar_radar_10m_9t.png", 0.7, 1.85, 11.9)
    tb(s, 0.5, 6.9, 12.3, 0.5,
       "Backscatter is usable at 10 m. Interferometric coherence under canopy "
       "is 0.14 -- subsidence monitoring does not survive the forest.",
       size=15, color=GRAY)
    notes(s, "Honest negative. It rules out an approach people will ask about.")

    # ---------------------------------------------------------- Act VI
    section(prs, "ACT VI", "What went wrong",
            "The part nobody else presents.")

    s = slide_new(prs, "The precision bug",
                  "3-6% was not a model result")
    bullets(s, 0.8, 2.0, 11.4, 3.8, [
        "Precision counted predictions across the whole tile against ground "
        "truth from the test blocks only. Every correct prediction outside a "
        "test block scored as a false positive.",
        "Pit predictions included floors and rims, scored against floors only.",
        "Thresholds were never tuned, so detection volume was arbitrary.",
    ], size=18)
    tb(s, 0.8, 5.9, 11.4, 1.0,
       "Corrected: 0.54 to 0.69. The conclusion drawn from the bug was "
       "withdrawn.", size=20, color=GREEN)
    notes(s, "We published this correction to ourselves in the leaderboard "
             "with the old numbers struck through. Say that.")

    s = slide_new(prs, "Two circular signals",
                  "both looked like results")
    bullets(s, 0.8, 2.0, 11.4, 4.2, [
        "Road probability was used as a feature to find pads -- and pads were "
        "partly defined by their roads.",
        "The elevation-difference signal at wells was measured against wells "
        "digitised from the same elevation data.",
        "Neither was caught by a metric. Both were caught by asking where the "
        "ground truth came from.",
    ], size=19)
    notes(s, "The general lesson: if the ground truth derives from the same "
             "data as the prediction, the number is decoration.")

    s = slide_new(prs, "Two coordinate-system errors",
                  "silent, and caught by a sanity check")
    bullets(s, 0.8, 2.2, 11.4, 3.6, [
        "The 2006-2008 point clouds carried the wrong EPSG code in their "
        "headers.",
        "The drainage layer was in metres while everything else was in degrees.",
        "Neither raised an error. Both produced plausible-looking output.",
    ], size=19)
    notes(s, "Every spatial project has these. Showing yours signals that you "
             "look for them.")

    # ---------------------------------------------------------- Act VII
    section(prs, "ACT VII", "Where it goes",
            "")

    s = slide_new(prs, "What is next",
                  "in order of what limits the result")
    bullets(s, 0.8, 1.9, 11.4, 4.6, [
        "Precision is the ceiling. Fragmentation of predicted floors is the "
        "most likely cause and it is testable without retraining.",
        "Annotation outside the training tile -- 221 pits and 358 pads already "
        "drawn, in no dataset yet.",
        "More regions, which means per-region channel statistics and an answer "
        "to whether they transfer.",
        "An architecture comparison on one grid, one split, one metric.",
    ], size=18)
    notes(s, "Future work that is specific and already scoped reads very "
             "differently from a wish list.")

    s = slide_new(prs, "Summary")
    bullets(s, 0.8, 1.9, 11.4, 4.6, [
        "Hand annotation, not model capacity, is what limits this problem.",
        "A crew searches 0.21% of the tile and finds 126 of 127 known pits.",
        "The same architecture handles pits, pads, roads and drainage.",
        "Human corrections convert directly into out-of-domain gain.",
        "The measurement mistakes are in the talk because finding them is the "
        "work.",
    ], size=19)
    notes(s, "Five sentences. Do not add a sixth.")

    s = slide_new(prs, "Thank you",
                  "questions")
    tb(s, 0.8, 3.0, 11.4, 2.0,
       "Data, code and the full result tables are available on request.",
       size=20, color=GRAY)
    notes(s, "Contact details and data availability -- fill in from the "
             "2026-08-18 outreach log entry.")

    # ---------------------------------------------------------- final order
    # Stated as objects, not indices. `new` is every slide created above, in
    # creation order; the two rescued slides are inserted where they belong.
    new = [sl for sl in prs.slides if sl not in kept]
    # Act II runs new[0:13] (section + 12). Morphology follows "What a pit
    # actually is" and QC follows "Project-wide against in-tile".
    act2 = new[0:12]
    rest = new[12:]
    act2 = (act2[0:4] + [MORPHOLOGY] + act2[4:7] + [QC] + act2[7:])
    reorder(prs, ACT_I + act2 + rest + APPENDIX)

    prs.save(str(OUT))
    _tmp.unlink(missing_ok=True)
    print(f"saved {OUT}  ({len(prs.slides)} slides)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
