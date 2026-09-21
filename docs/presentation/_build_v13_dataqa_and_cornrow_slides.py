"""v12 -> v13: give the data-QA section a beginning and an end, and show the
corn rows in the other layers and in cross-section.

WHAT WAS WRONG
--------------
The data-QA section opened on "What the Cut Cost", which assumes the audience
already knows a cut happened, and closed on a classification comparison, which
leaves the obvious question unanswered: what does the ground surface actually
look like either way?

WHAT IS ADDED
-------------
Two slides at the start, telling it in the order it happened:

  1  Nearly half the delivered cloud carried no label at all. Asked what those
     points were. A third of them were sitting on the ground.
  2  Those ground-sitting points are identical to the points the vendor DID
     call ground on every property measured -- except scan angle, 18.6 deg
     against 9.4.

That sets up the existing cliff slide rather than dropping the audience into
it.

Two slides at the end, answering the downstream question:

  3  The bare-earth surface built both ways, side by side, with the cells the
     vendor had no ground for tinted so you can see which parts are
     interpolation.
  4  Whether the surface actually moves: where ground already existed it does
     not (median 0.000 m), where it was filled it does (20% of cells beyond
     10 cm).

And two in the RRIM section:

  5  The same corn-row window in hillshade, local relief, negative openness and
     slope. **No text on this slide at all** -- four images, nothing else.
  6  A cross-section across the rows at centimetre scale, with the honest
     result: stacking 81 lines across the rows and 81 along them gives the same
     3.5 cm amplitude, so an elevation profile does not separate them by
     direction.

Run:
    python docs/presentation/_build_v13_dataqa_and_cornrow_slides.py
Reads:  docs/presentation/WellSight_Presentation v12.pptx
Writes: docs/presentation/WellSight_Presentation v13.pptx
"""
from __future__ import annotations

import copy
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/presentation/WellSight_Presentation v12.pptx"
DST = ROOT / "docs/presentation/WellSight_Presentation v13.pptx"
V6 = ROOT / "docs/presentation/figures_30to45min/v6"
QA = ROOT / "docs/presentation/figures_30to45min/1_data_qa"
PML = "{http://schemas.openxmlformats.org/presentationml/2006/main}"

INK = RGBColor(0x14, 0x1A, 0x1F)
INK2 = RGBColor(0x54, 0x5C, 0x63)
ACCENT = RGBColor(0x00, 0x96, 0xC7)

SLIDE_W, SLIDE_H = 13.3333, 7.5

NEW = [
    dict(
        before="Data QA",                      # the "What the Cut Cost" slide
        title="Data QA — where this started",
        kicker="Nearly half the delivered cloud had no label on it",
        bullets=[
            "113.5 million points across ten tiles",
            "43.7% sit in class 1, which means “unassigned” — the "
            "survey never said what they hit",
            "So we asked. Sorting them by height above the ground answers most "
            "of it: 56% are up in the canopy",
            "But a third of them — 33% — are sitting on the ground",
        ],
        fig=QA / "report_4_what_they_are_9t.png",
        notes=(
            "This is where the whole data-quality section came from.\n\n"
            "The delivery is 113.5 million points over ten tiles. Every point "
            "is supposed to carry a class saying what it hit. 43.7% of them "
            "are class 1, which means unassigned -- the survey never said.\n\n"
            "That is nearly half the data, so it was worth asking what it "
            "is.\n\n"
            "Sorting those points by their height above the ground surface "
            "answers most of the question, and the chart is that answer. 56% "
            "are high in the canopy, 5% in the middle of the trees, 5% in low "
            "bushes, 1% below the ground surface, which is noise.\n\n"
            "And 33% are sitting right on the ground. A third of the "
            "unlabelled points are ground returns that were never called "
            "ground."),
    ),
    dict(
        before="Data QA",
        after_previous=True,
        title="Data QA — what made those points different",
        kicker="Nothing, except the angle they were measured at",
        bullets=[
            "5.6 million of them, across four tiles",
            "100% are the last return of their pulse, 75% the only return — "
            "the same as real ground points",
            "0.00% carry the overlap flag, again the same",
            "One property differs: median scan angle 18.6° against 9.4°",
            "Scan angle is how far off straight-down the laser was pointing",
        ],
        fig=V6 / "scan_angle_cone_bare_9t.png",
        notes=(
            "So a third of the unlabelled points reached the ground. The next "
            "question is what makes them different from the points the survey "
            "did call ground.\n\n"
            "There are 5.6 million of them across four tiles. Checked against "
            "real ground points on every property recorded: all of them are "
            "the last return of their pulse, three quarters are the only "
            "return, and none carry the overlap flag. That is the signature of "
            "a ground hit, and it matches.\n\n"
            "One thing differs. The median scan angle is 18.6 degrees against "
            "9.4.\n\n"
            "Scan angle is how far off straight-down the laser was pointing "
            "when it fired. The diagram is the aircraft looking down: the blue "
            "cone near the centre is what was kept, the red wedges at the "
            "edges of the swath are what was thrown away.\n\n"
            "The next slide is how sharp that boundary is."),
    ),
    dict(
        after="Data QA — our ground classification",
        title="Data QA — the surface, built both ways",
        kicker="Neither version has holes. One of them has guesses.",
        bullets=[
            "Both surfaces are triangulated, so gaps get spanned either way "
            "— 0.00% void in both",
            "Left: the orange cells had no ground return at all, so the "
            "surface there is interpolated between the nearest real points",
            "Right: the same ground with the deleted returns restored",
            "The difference is not holes versus no holes. It is a guess versus "
            "a measurement.",
        ],
        fig=V6 / "dem_with_and_without_deleted_returns_9t.png",
        wide=True,
        notes=(
            "This is the question the rest of the section sets up but never "
            "answers: what does the ground surface actually look like either "
            "way?\n\n"
            "The first thing to say is that neither version has holes in it. "
            "Both are built by triangulating between the points, which spans "
            "any gap by construction, so both are 0.00% void.\n\n"
            "Left is the surface as delivered. The orange cells are the ones "
            "with no ground return under them at all -- 52% of this window. "
            "The surface there is a straight line drawn between the nearest "
            "real measurements on either side.\n\n"
            "Middle is the same ground with the deleted returns put back, on "
            "the same hillshade and the same stretch.\n\n"
            "Right is the difference in centimetres. Where a void got filled, "
            "the surface moves a median of 3 centimetres and a tenth of those "
            "cells move more than 10.\n\n"
            "So the change is not dramatic. What changes is that a guess "
            "becomes a measurement."),
    ),
    dict(
        after_previous=True,
        title="Data QA — does the surface actually move?",
        kicker="Only where it had nothing to stand on",
        bullets=[
            "Where the vendor already had ground: median change +0.000 m, and "
            "only 0.2% of cells move more than 10 cm",
            "Where the ground was filled in: median −0.005 m, and 20% of "
            "cells move more than 10 cm",
            "44.4 million cells already had ground. 2.9 million were filled.",
            "The restored data does not rewrite the survey. It finishes it.",
        ],
        fig=V6 / "dem_vendor_vs_recovered_difference_9t.png",
        notes=(
            "The check that matters before trusting any of this: does putting "
            "the deleted returns back quietly change the ground everywhere, or "
            "only where there was nothing?\n\n"
            "Two histograms of the same thing -- new surface minus old, in "
            "metres.\n\n"
            "Blue is the 44.4 million cells the vendor already had ground for. "
            "Median change zero to three decimal places, and only two tenths "
            "of one percent move by more than 10 centimetres. That surface is "
            "left alone.\n\n"
            "Orange is the 2.9 million cells that had nothing and now have a "
            "measurement. Median minus half a centimetre, and 20% move more "
            "than 10 centimetres. That is where the work happened, and it "
            "should be.\n\n"
            "If the blue curve were wide, we would be overwriting a "
            "professional survey with our own reclassification. It is not."),
    ),
    dict(
        after="The corn rows in the RRIM",
        title=None,                            # no text at all on this slide
        fig=V6 / "cornrow_four_layers_9t.png",
        bare=True,
        notes=(
            "The same 240 m window as the previous slide, in four of the "
            "layers the model actually reads: hillshade, local relief, "
            "negative openness and slope.\n\n"
            "No text on this slide on purpose. The stripes are either visible "
            "or they are not.\n\n"
            "Local relief, top right, is where they are plainest -- that layer "
            "is elevation with the hillside subtracted, so a few centimetres "
            "of ripple is most of what is left. Negative openness, bottom "
            "left, carries them too, and that is the single most useful layer "
            "for finding pits.\n\n"
            "Hillshade shows them faintly. Slope shows them faintly.\n\n"
            "This is what is meant by the claim that they appear in every "
            "layer built from shape."),
    ),
    dict(
        after_previous=True,
        title="The corn rows in cross-section",
        kicker="Nine rows drawn by hand, and the ground cut across them",
        bullets=[
            "Nine rows drawn by hand give the direction and spacing directly",
            "Bearing 79.31°, spread 0.36° — against 78° "
            "predicted by the scanner's own geometry, and 79° from an FFT "
            "of this raster",
            "Three independent measurements, one degree apart",
            "Rows sit 3.35 m apart, and the ripple is under a centimetre",
            "Raw elevation cannot show this — the hillside drops metres. "
            "Local relief already has the hillside removed.",
        ],
        fig=V6 / "cornrow_rows_measured_9t.png",
        wide=True,
        notes=(
            "What the data in a corn row actually does, measured rather than "
            "described.\n\n"
            "A raw elevation profile is no use. The ground drops several "
            "metres over 60 m and the ripple is a few centimetres, so it is "
            "about one part in a hundred of the range and invisible.\n\n"
            "Subtracting a smoothed copy of the profile leaves the ripple. "
            "Worth saying out loud: that subtraction is exactly what the local "
            "relief layer is, so the top panel is effectively one row of a "
            "channel the model reads. The two lines track each other, which is "
            "the check.\n\n"
            "One line across the rows wobbles about plus or minus five "
            "centimetres, 14.5 peak to trough.\n\n"
            "Now the honest part. Averaging 81 parallel lines across the rows "
            "leaves 3.5 centimetres. Doing the same 81 lines along the rows "
            "leaves 3.6. Identical.\n\n"
            "So at this spot, in the elevation model, a cross-section does not "
            "isolate a directional ripple. The corduroy is plain in the "
            "shape-derived layers on the previous slide and is not separable "
            "by direction in a bare elevation profile. If asked, that is the "
            "answer -- we can show it, we cannot yet explain it."),
    ),
]


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


def ratio(p: Path) -> float:
    with Image.open(p) as im:
        return im.size[0] / im.size[1]


def build(prs, src, spec):
    new = prs.slides.add_slide(src.slide_layout)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)
    bg = src._element.find(f"{PML}cSld").find(f"{PML}bg")
    if bg is not None:
        new._element.find(f"{PML}cSld").insert(0, copy.deepcopy(bg))

    fig = spec.get("fig")
    if fig and not fig.exists():
        raise SystemExit(f"figure missing: {fig}")
    ar = ratio(fig) if fig else None

    if spec.get("bare"):
        # images only: fill the slide, leaving a small even margin
        m = 0.22
        w = min(SLIDE_W - 2 * m, (SLIDE_H - 2 * m) * ar)
        h = w / ar
        new.shapes.add_picture(str(fig), Inches((SLIDE_W - w) / 2),
                               Inches((SLIDE_H - h) / 2),
                               width=Inches(w), height=Inches(h))
        new.notes_slide.notes_text_frame.text = spec["notes"]
        return new

    tb = new.shapes.add_textbox(Inches(0.70), Inches(0.42),
                                Inches(12.0), Inches(0.85))
    tb.text_frame.word_wrap = True
    rgb_runs(tb.text_frame, [(spec["title"], 27, True, ACCENT, 0)])

    if spec.get("wide"):
        body = new.shapes.add_textbox(Inches(0.70), Inches(1.40),
                                      Inches(12.0), Inches(1.55))
        body.text_frame.word_wrap = True
        runs = [(spec["kicker"], 16, True, INK, 9)]
        for b in spec["bullets"]:
            runs.append(("•  " + b, 12.5, False, INK2, 4))
        rgb_runs(body.text_frame, runs)
        w = 12.0
        h = w / ar
        new.shapes.add_picture(str(fig), Inches(0.70), Inches(3.05),
                               width=Inches(w), height=Inches(h))
    else:
        body = new.shapes.add_textbox(Inches(0.70), Inches(1.50),
                                      Inches(4.55), Inches(5.10))
        body.text_frame.word_wrap = True
        runs = [(spec["kicker"], 16.5, True, INK, 10)]
        for b in spec["bullets"]:
            runs.append(("•  " + b, 13.5, False, INK2, 7))
        rgb_runs(body.text_frame, runs)
        max_w, max_h = 7.70, 5.35
        w = min(max_w, max_h * ar)
        h = w / ar
        new.shapes.add_picture(str(fig), Inches(5.45 + (max_w - w) / 2),
                               Inches(1.42 + (max_h - h) / 2),
                               width=Inches(w), height=Inches(h))

    foot = new.shapes.add_textbox(Inches(0.70), Inches(7.00),
                                  Inches(11.0), Inches(0.42))
    foot.text_frame.word_wrap = True
    rgb_runs(foot.text_frame,
             [("Colton Goodrich  ·  University of Houston",
               12, False, INK2, 0)])
    new.notes_slide.notes_text_frame.text = spec["notes"]
    return new


def main() -> int:
    prs = Presentation(SRC)
    lst = prs.slides._sldIdLst
    before = len(prs.slides)
    anchor = None

    for spec in NEW:
        if spec.get("after_previous"):
            idx = anchor
        elif "before" in spec:
            idx = next(i for i, s in enumerate(prs.slides)
                       if norm(title_of(s)).startswith(norm(spec["before"]))) - 1
        else:
            idx = next(i for i, s in enumerate(prs.slides)
                       if norm(title_of(s)).startswith(norm(spec["after"])))
        s = build(prs, prs.slides[max(idx, 0)], spec)
        node = list(lst)[-1]
        lst.remove(node)
        list(lst)[idx].addnext(node)
        anchor = idx + 1
        name = spec["title"] or "(images only)"
        print(f"  slide {anchor + 1}: {name}")

    prs.save(DST)
    out = Presentation(DST)
    print(f"\n  {before} -> {len(out.slides)} slides")
    for i, s in enumerate(out.slides, 1):
        if 8 <= i <= 14 or 19 <= i <= 22 or 32 <= i <= 36:
            print(f"    {i:3d}  {title_of(s)[:58] or '(images only)'}")
    print(f"  {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
