"""Four slides: the corn rows in the RRIM, the provider's answer, and the models.

THREE CORN-ROW SLIDES, after the RRIM pair
------------------------------------------
The deck shows the corn rows twice without ever explaining them -- on the CHM
slide, where they are NoData, and implicitly in every shape-derived layer after
it. These three say what they are, quote the data provider's own answer, and
report what their two suggested remedies actually did here.

The quote is verbatim from OpenTopography's FAQ on linear "corduroy" striping,
as recorded in notebooks/wellsight/preprocessing/dem_idw_builder.py. It matters
because it moves the problem off our processing and onto the delivery, and
because it is the source of both remedies we tested.

What the remedies did, measured:
  coarser grid     works. CHM void over the window 3.23% -> 0.00%, and the
                   stripes fade. It does NOT remove them -- the slide says so,
                   and the figure shows residual grain at 1 m.
  local gridding   backfired. writers.gdal output_type=mean over a radius
                   smooths heights but makes the surface discontinuous cell to
                   cell, because the point set inside the disc changes abruptly
                   as it slides. RRIM is built from shape, so it amplifies
                   exactly that: visible starbursts around trees.

Deliberately NOT on these slides: the spike-prominence ratios. That metric is
window-size dependent -- the same raster at the same place scored x3.70 in a
90 m window and x0.84 in a 600 m one -- so no number from it is quotable.
Also not claimed: a mechanism. Three were proposed and all three were refuted
by measurement, and the last bullet says that rather than hiding it.

ONE ARCHITECTURE SLIDE, after the model-building pair
-----------------------------------------------------
The deck presents one U-Net and never says whether a bigger network would do
better. It was tested: four architectures, five folds each, identical folds,
channels, loss and schedule. Numbers from
docs/iterations/LEADERBOARD.md "Architecture comparison, 1 m".

These are segmentation IoU at 1 m and are NOT the detection recall used
everywhere else in the deck. The slide says so, because a reader who compares
0.561 against 0.928 will think the model got worse.

Run:
    python docs/presentation/_add_cornrow_and_arch_slides_v7.py
Writes (in place):
    docs/presentation/WellSight_Presentation v7.pptx
"""
from __future__ import annotations

import copy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "docs/presentation/WellSight_Presentation v7.pptx"
FIGDIR = ROOT / "docs/presentation/figures_30to45min/v6"
PML = "{http://schemas.openxmlformats.org/presentationml/2006/main}"

INK = RGBColor(0x14, 0x1A, 0x1F)
INK2 = RGBColor(0x54, 0x5C, 0x63)
ACCENT = RGBColor(0x00, 0x96, 0xC7)
QUOTE = RGBColor(0x1F, 0x5F, 0xA8)

OT_QUOTE = (
    "“…there is nothing the user (or OpenTopography) can do to fix "
    "this as it is in the raw data that we receive. One option is to set a "
    "coarser grid resolution, and if the artifacts are still present at a "
    "coarser resolution, users may want to try the other gridding algorithm "
    "under ‘DEM Generation (local gridding)’.”")

CORN = [
    dict(
        after="Step 1: Terrain Derivatives",   # the second RRIM slide
        title="Two different stripes, one nickname",
        kicker="“Corn rows” has meant two unrelated things. They "
               "need separating.",
        bullets=[
            "On canopy height they are empty cells — no return came "
            "back, so there is nothing to draw",
            "That is a grid-size problem. 2.044% of cells at 0.5 m, 0.029% at "
            "1 m. Solved.",
            "On the RRIM they sit in a surface with no empty cells at all",
            "The ground surface is 0.000% empty at 0.5 m and at 1 m — the "
            "triangulation spans every gap",
            "So these are real measurements, not missing ones. Different "
            "problem, different fix.",
        ],
        fig="two_kinds_of_corn_rows_9t.png", ratio=1.889,
        notes=(
            "This slide exists because I had been using one name for two "
            "unrelated things, and that led to offering a fix for one as "
            "though it fixed both.\n\n"
            "On the canopy height model the stripes are empty cells. No pulse "
            "came back there, so there is literally nothing to draw. That is a "
            "grid-size problem: the half-metre grid asks for finer detail than "
            "the survey delivered. Two percent of cells at half a metre, near "
            "zero at one metre. That one is solved.\n\n"
            "On the RRIM the stripes sit in a surface that has no empty cells "
            "anywhere. Here is the number that settles it. The ground surface "
            "is zero percent empty at half a metre and zero percent empty at "
            "one metre, because the triangulation spans every gap by "
            "construction.\n\n"
            "A layer that never has a hole still stripes. So whatever these "
            "are, they are real measurements disagreeing with each other, not "
            "missing measurements.\n\n"
            "The next three slides are about the second kind only."),
    ),
    dict(
        title="The corn rows in the RRIM",
        kicker="The second kind: stripes in ground we actually measured",
        bullets=[
            "They run at 78° — the same bearing as the lines the "
            "scanner draws on the ground",
            "They appear in every layer built from shape: LRM, openness, "
            "hillshade, RRIM",
            "Their size is tens of centimetres. A pit is a 0.7 m dish.",
            "So the artefact and the signal we are hunting are the same size. "
            "That is why it matters.",
        ],
        fig="rrim_corn_rows_05_vs_1m_9t.png", ratio=1.886,
        notes=(
            "These are the stripes people notice as soon as the RRIM goes up, "
            "so it is better to name them before someone asks.\n\n"
            "They run at 78 degrees, which is the same direction as the lines "
            "the laser sweeps across the ground. That is the single strongest "
            "clue about where they come from.\n\n"
            "They turn up in every layer that measures shape rather than "
            "height. Local relief, openness, hillshade, RRIM.\n\n"
            "Here is why it is not cosmetic. The stripes are a few tens of "
            "centimetres deep. A collapse pit is about seventy centimetres "
            "deep. The artefact is the same size as the thing we are looking "
            "for, so anything that hunts for small dishes can be fooled by "
            "them.\n\n"
            "The picture is the same ground at the two cell sizes. Left is "
            "half a metre, and the weave is plain. Right is one metre, and it "
            "is much reduced. Reduced, not gone -- say that, because you can "
            "still see grain on the right."),
    ),
    dict(
        title="What the data provider says",
        kicker="OpenTopography's published answer on “corduroy” "
               "striping",
        quote=OT_QUOTE,
        bullets=[
            "So it is in the delivered point cloud, not in our processing",
            "They offer exactly two remedies: a coarser grid, or local "
            "gridding",
            "We tried both",
        ],
        notes=(
            "This is worth reading out, because it settles who owns the "
            "problem.\n\n"
            "OpenTopography distributes this data. Their own FAQ says the "
            "striping is in the raw data they receive, and that neither the "
            "user nor they can fix it.\n\n"
            "That is not an excuse for us. It is a boundary. It means the "
            "stripes are a property of the survey, not of anything we did "
            "downstream, and it means we should stop trying to remove them and "
            "start managing them.\n\n"
            "They suggest two things. Use a coarser grid. Or use a different "
            "gridding algorithm, the one they call local gridding, which "
            "averages points inside a radius instead of triangulating between "
            "them.\n\n"
            "We tested both. The next slide is what happened."),
    ),
    dict(
        title="What the two remedies actually did",
        kicker="One works. The other made it worse.",
        bullets=[
            "Coarser grid — helps, but only partly. At 1 m the stripes "
            "fade. They do not go away.",
            "Local gridding — backfired. Averaging points in a disc "
            "smooths heights but makes the surface jump from cell to cell",
            "RRIM is built from shape, so it amplifies exactly that — "
            "look at the starbursts on every tree",
            "So: build at 1 m, and keep the triangulated surface",
            "Unlike the canopy holes, coarsening cannot delete these — "
            "there is nothing empty to fill",
            "And we could not prove what causes them. Three explanations "
            "tested, three refuted.",
        ],
        fig="local_gridding_backfire_9t.png", ratio=1.887,
        notes=(
            "Two remedies, two different outcomes.\n\n"
            "The coarser grid helps, and it is what we adopted. But be careful "
            "how you say it. It does not delete these stripes the way it "
            "deletes the canopy holes, because here there is nothing empty to "
            "fill. It averages more measurements into each cell, so the "
            "disagreement between them shows up less. The weave fades. It is "
            "still there.\n\n"
            "Local gridding was the surprise. It should have helped and it did "
            "the opposite.\n\n"
            "Here is the reason, and it is worth understanding rather than "
            "memorising. Averaging takes whatever points fall inside a circle "
            "around each cell. As that circle slides across the ground the set "
            "of points inside it changes suddenly, so the surface jumps a "
            "little from one cell to the next. Heights get smoother; the "
            "slopes between them get rougher.\n\n"
            "RRIM does not draw height. It draws shape, which is built from "
            "those slopes. So it amplifies precisely the thing averaging made "
            "worse. In the picture you can see it: every tree sprouts a "
            "starburst.\n\n"
            "Last bullet is the honest one and I would not skip it. One metre "
            "reduces the stripes rather than removing them, and we tested "
            "three separate explanations for what causes them. All three "
            "failed. We know how to manage it. We do not know why it is "
            "there."),
    ),
]

ARCH = dict(
    after="Model building – committing to an answer",
    title="Model building — does a bigger network help?",
    kicker="Four architectures, five folds each, everything else held identical",
    bullets=[
        "Same folds, same seven channels, same loss, same 40 epochs",
        "Pits — plain U-Net 0.559, the full stack 0.561. A gain of 0.002 "
        "against a fold spread of 0.020.",
        "Pads — plain U-Net 0.555, the full stack 0.608. That one is "
        "worth another look.",
        "For pits, architecture is not what is holding us back. 3× the "
        "parameters bought nothing.",
        "These are segmentation overlap scores at 1 m, not the detection "
        "recall on the outcome slides. Do not compare the two.",
    ],
    notes=(
        "Someone always asks whether a bigger network would do better, so here "
        "is the test.\n\n"
        "Four architectures. A plain U-Net, a ResNet-34 backbone from scratch, "
        "the same pretrained on ImageNet, and a U-Net++ with that pretrained "
        "backbone. Five folds each, and everything else held fixed -- same "
        "folds, same seven channels, same loss, same schedule. Each step "
        "changes exactly one thing.\n\n"
        "For pits the answer is a flat no. Going from the smallest to the "
        "largest buys two thousandths, and the spread between folds is ten "
        "times that. Three times the parameters and ImageNet pretraining for "
        "nothing. That tells us the limit is the data and the labels, not the "
        "network.\n\n"
        "For pads there is something. Plain U-Net 0.555 up to 0.608, and "
        "nearly every fold of the better model beats nearly every fold of the "
        "plain one. That is suggestive rather than proven -- it needs more "
        "seeds before I would call it a result.\n\n"
        "The last line matters if anyone is writing numbers down. These are "
        "overlap scores at one metre, measuring how well the shape is traced. "
        "They are not the recall figures from the outcome slides, which count "
        "whole features found at half a metre. Comparing the two would look "
        "like the model fell apart."),
)


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
        r.font.italic = colour is QUOTE
        r.font.color.rgb = colour
        r.font.name = "Calibri"


def title_of(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def build(prs, src, spec):
    new = prs.slides.add_slide(src.slide_layout)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)
    bg = src._element.find(f"{PML}cSld").find(f"{PML}bg")
    if bg is not None:
        new._element.find(f"{PML}cSld").insert(0, copy.deepcopy(bg))

    tb = new.shapes.add_textbox(Inches(0.70), Inches(0.42),
                                Inches(12.0), Inches(0.85))
    tb.text_frame.word_wrap = True
    rgb_runs(tb.text_frame, [(spec["title"], 28, True, ACCENT, 0)])

    fig = spec.get("fig")
    # A figure wide enough to read is 8 in across, which leaves a 4.4 in text
    # column beside it. Stacking them instead would make a 1.9:1 figure 6.4 in
    # tall at full width and it would land on top of the bullets.
    body_w = 4.40 if fig else 12.0
    body_h = 5.10 if fig else 4.6
    body = new.shapes.add_textbox(Inches(0.70), Inches(1.46),
                                  Inches(body_w), Inches(body_h))
    body.text_frame.word_wrap = True
    runs = [(spec["kicker"], 17, True, INK, 11)]
    if spec.get("quote"):
        runs.append((spec["quote"], 17, False, QUOTE, 8))
        runs.append(("— OpenTopography FAQ, on linear "
                     "“corduroy” striping in DEMs", 13, False,
                     INK2, 14))
    for b in spec["bullets"]:
        runs.append(("•  " + b, 14 if fig else 15, False, INK2,
                     6 if fig else 9))
    rgb_runs(body.text_frame, runs)

    if fig:
        p = FIGDIR / fig
        if not p.exists():
            raise SystemExit(f"figure missing: {p}")
        w = 8.00
        h = w / spec["ratio"]
        # centre it vertically in the band between the title and the footer
        top = 1.46 + max(0.0, (5.10 - h) / 2.0)
        new.shapes.add_picture(str(p), Inches(5.25), Inches(top),
                               width=Inches(w), height=Inches(h))

    foot = new.shapes.add_textbox(Inches(0.70), Inches(7.00),
                                  Inches(11.0), Inches(0.42))
    foot.text_frame.word_wrap = True
    rgb_runs(foot.text_frame,
             [("Colton Goodrich  ·  University of Houston",
               12, False, INK2, 0)])
    new.notes_slide.notes_text_frame.text = spec["notes"]
    return new


def move_after(prs, slide, index):
    """Move the just-appended slide to sit directly after 0-based `index`."""
    lst = prs.slides._sldIdLst
    node = list(lst)[-1]
    lst.remove(node)
    list(lst)[index].addnext(node)


def main() -> int:
    prs = Presentation(DECK)

    # --- corn rows: after the SECOND RRIM slide -------------------------
    rrim = [i for i, s in enumerate(prs.slides)
            if title_of(s).startswith("Step 1: Terrain Derivatives")
            and "RRIM" in title_of(s)]
    if len(rrim) < 2:
        raise SystemExit(f"expected two RRIM slides, found {len(rrim)}")
    at = rrim[-1]
    for n, spec in enumerate(CORN):
        s = build(prs, prs.slides[at], spec)
        move_after(prs, s, at + n)
        print(f"  slide {at + n + 2}: {spec['title']}")

    # --- architecture: after "committing to an answer" ------------------
    idx = next(i for i, s in enumerate(prs.slides)
               if title_of(s).replace("–", "-").replace("—", "-")
               == ARCH["after"].replace("–", "-").replace("—", "-"))
    s = build(prs, prs.slides[idx], ARCH)
    move_after(prs, s, idx)
    print(f"  slide {idx + 2}: {ARCH['title']}")

    prs.save(DECK)
    out = Presentation(DECK)
    print(f"\n  {len(out.slides)} slides")
    print(f"  {DECK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
