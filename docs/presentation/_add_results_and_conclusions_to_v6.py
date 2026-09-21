"""Put the held-out numbers on the outcome slides, and write real conclusions.

WHAT WAS WRONG
--------------
Slides 47 to 55 are a title and a picture. Nothing on them says how well
anything worked. Slides 56 to 59 have a left column with one sentence in it.
And slide 66, "Summary", still carried the pre-U-Net pipeline's numbers --
"85.5% precision at 0.80 probability threshold", "ensemble of 48 features",
"anomaly detection flags 10.5%" -- none of which describes what the deck now
presents. It also said "WellSight", which is an internal working name and does
not go in front of an audience.

WHERE THE NUMBERS COME FROM
---------------------------
docs/iterations/LEADERBOARD.md, the ann712 sections dated 2026-09-17 and later,
and
data/_comparisons/pit_heldout_and_transfer_2026-09-20/613590_transfer_from_9t_cv5_05/
pit_transfer_recall_summary_613590_05.json.

They are typed into TABLES below rather than read from those files, because the
leaderboard is prose and the rows that matter are scattered across five
sections. Every figure carries the source it came from in the same dict, so a
reader can check one against the other. If the leaderboard moves, this file has
to move with it -- there is no automatic link and pretending otherwise would be
worse than saying so.

TWO RULES, AND BOTH ARE REPORTED
--------------------------------
Each model has a probability cutoff chosen on a validation fold, and the choice
of objective changes the answer a lot. F1 balances finding things against being
wrong; F2 weights finding things four times as heavily. For a screening tool
whose output a person reviews, F2 is the honest operating point, so it leads --
but F1 is given beside it every time, because quoting only the recall-favouring
rule is how a screening tool gets oversold.

WHAT IS NOT REPORTED, AND WHY
-----------------------------
No precision on 613590. The tile is not fully annotated, so an unmatched
prediction may be a false positive or a real pit nobody drew yet. Nothing in the
data separates those two, so the number would be a floor presented as a fact.
The slides say this rather than leaving a blank.

No pad or drainage score on 613590 either: zero pads and zero drainage lines
were ever drawn there, so there is no ground truth to score against. The pad
slide says so.

Run:
    python docs/presentation/_add_results_and_conclusions_to_v6.py
Edits in place:
    docs/presentation/WellSight_Presentation v6.pptx
"""
from __future__ import annotations

import copy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
DECK = HERE / "WellSight_Presentation v6.pptx"

INK = RGBColor(0x14, 0x1A, 0x1F)
INK2 = RGBColor(0x54, 0x5C, 0x63)
ACCENT = RGBColor(0x00, 0x96, 0xC7)
GOOD = RGBColor(0x1F, 0x5F, 0xA8)
WARN = RGBColor(0xD9, 0x77, 0x06)

SRC_LB = "docs/iterations/LEADERBOARD.md"
SRC_TR = ("data/_comparisons/pit_heldout_and_transfer_2026-09-20/"
          "613590_transfer_from_9t_cv5_05/"
          "pit_transfer_recall_summary_613590_05.json")

#: Wide slides: title, then a full-width picture. A stats strip is inserted
#: between the two and the picture is pushed down to make room.
WIDE = {}

WIDE[47] = dict(
    strip="43.07 km withheld  ·  recall 0.982  ·  flags 5.02% of the tile",
    notes=f"""OUTCOME, ROADS

WHAT WAS HELD BACK
1,220 road chunks, 43.07 km of hand-drawn line, kept out of training entirely.

WHAT THE MODEL FOUND
At a probability cutoff of 0.20 it recovered 98.2% of them. That is
recall_clean, the stricter of the two numbers available: it counts only the 735
chunks whose ENTIRE parent road was held out. The looser figure is about 1.5
points higher and is not quoted, because roads were split into 40 m chunks
rather than whole objects, so 485 of the 1,220 held-out chunks share a parent
road with a chunk the model trained on. That is leakage and it is named.

WHAT IT COSTS TO GET THAT
101.65 hectares flagged, 5.02% of the 2,025 hectare tile. That is the search
burden a field crew inherits.

Recall is nearly flat from a cutoff of 0.05 to 0.80, above 0.95 throughout, so
the threshold is not a knife edge.

Source: {SRC_LB}""")

WIDE[48] = dict(
    strip="not a detector — a negative class, and it worked",
    notes=f"""OUTCOME, DRAINAGE

THERE IS NO DRAINAGE RECALL NUMBER HERE, AND THAT IS NOT AN OVERSIGHT.

Drainage is not a product anybody asked for. It exists in this project for one
reason: a stream cut and an access road look almost identical on a slope image,
both long, both darker than the ground either side, and the road model kept
calling streams roads.

The fix was to draw the streams and hand them to the road model as NEGATIVES,
so it learns the difference during training instead of being corrected
afterwards by a filter.

SO THE RIGHT TEST IS WHETHER THE ROAD MODEL STOPPED CLAIMING THEM

Held-out not-road lines: claimed at 0.0% at every threshold.
Held-out drainage: falls from 3.9% to 2.1% across the useful range.

That is direct evidence the three-class design did its job. 45.0 km of drainage
was drawn, all of it on 9t, and none on 613590 -- which is why the drainage
class only ever trains on one tile.

Source: {SRC_LB}""")

WIDE[49] = dict(
    strip="995 pads  ·  recall 0.912  ·  precision 0.587  ·  flags 11.6%",
    notes=f"""OUTCOME, PADS

FIVE-FOLD CROSS-VALIDATED. Every pad is scored by a model that never saw the
block of land it sits in. 995 drawn, 650 in-tile pads scored.

  recall-weighted rule (F2)   recall 0.912, sd 0.022   precision 0.587
  balanced rule (F1)          recall 0.888, sd 0.051   precision 0.597
  locate rate                 0.923

THE PAD MODEL IS THE WEAK ONE AND THE FLAGGED AREA IS WHAT SHOWS IT

On the held-out threshold sweep it finds 178 of 194 withheld pads, 91.8%, but to
do it flags 235.77 hectares -- 11.64% of the tile. The pit model reaches a
higher recall on one fifty-fifth of the ground.

At a cutoff of 0.50 it flags 197.95 ha against roughly 110 ha of annotated pad
on the whole tile, so it is over-claiming by about a factor of two. A pad is a
big soft-edged clearing with no sharp boundary, and the model spreads.

High recall on its own is not a result. It has to be read next to how much
ground it costs.

Source: {SRC_LB}""")

WIDE[50] = dict(
    strip="712 pits  ·  recall 0.928  ·  precision 0.633  ·  flags 0.21%",
    notes=f"""OUTCOME, PITS

FIVE-FOLD CROSS-VALIDATED. Every pit is scored by a model that never saw its
block. 712 floors drawn, 502 rims scored.

  recall-weighted rule (F2)   recall 0.928, sd 0.023   precision 0.633
  balanced rule (F1)          recall 0.861, sd 0.045   precision 0.686
  containment                 0.956 under F2, 0.914 under F1

THIS IS THE ONE THAT TURNS RECALL INTO A SHORT LIST

On the held-out threshold sweep it finds 126 of 127 withheld rims -- 99.2% -- and
flags 4.33 hectares to do it. That is 0.21% of the 2,025 hectare tile.

Put beside the pad model: a comparable recall on one fifty-fifth of the ground.
That ratio, not the recall, is what makes this usable.

WHY PRECISION IS 0.63 AND WHY THAT IS NOT THE WHOLE STORY

Precision here is measured against what a person drew. When the annotation grew
from 527 to 712 floors, precision ROSE from 0.598 to 0.633 while recall barely
moved -- consistent with some of what was being counted as false positives
being real pits nobody had drawn yet. Consistent with, not proof of: the pads
did not reproduce the effect, so it is recorded as a hypothesis.

Source: {SRC_LB}""")

WIDE[51] = dict(
    strip="153 pits, never trained on  ·  recall 0.911 vs 0.928 at home",
    notes=f"""HELD-OUT TILE 613590, PITS

A DIFFERENT 4.5 km TILE. No model ever trained on it. 153 pit floors drawn by
hand, and the five 9t fold models run over it with their thresholds frozen --
nothing was retuned.

  recall-weighted rule (F2)   0.911 on 613590, sd 0.045
                              0.928 on 9t held-out
                              a drop of 0.017

  balanced rule (F1)          0.792 on 613590, sd 0.100
                              0.861 on 9t held-out
                              a drop of 0.069

  containment                 0.906

THE F2 NUMBER IS THE ONE THAT MATTERS AND IT BARELY MOVED. Under the
recall-weighted rule the model loses under two points going to ground it has
never seen. Under the balanced rule it loses seven, and the fold-to-fold spread
more than doubles -- so the higher-confidence operating point is the one that
does not travel well.

NO PRECISION IS QUOTED, DELIBERATELY

613590 is not fully annotated. An unmatched prediction there may be a false
positive or a real pit nobody has drawn yet, and nothing in the data separates
them. A precision number would be a floor presented as a fact.

Source: {SRC_TR}""")

WIDE[52] = dict(
    strip="no pads were ever drawn here — nothing to score against",
    notes="""HELD-OUT TILE 613590, PADS

THERE IS NO NUMBER ON THIS SLIDE BECAUSE THERE IS NO GROUND TRUTH.

Zero pads were drawn on 613590. All 995 annotated pads are on 9t and on the
eastern ground toward McKean. So the model's 161 pad candidates here can be
looked at, but they cannot be scored -- there is nothing to check them against.

That is worth saying out loud rather than leaving the slide silent, because a
picture of candidates with no number beside it invites the reader to assume
somebody checked.

WHAT WOULD FIX IT
Drawing pads on 613590. It is the single cheapest thing that would turn this
slide into a result.

Source: qgis/annotations/annotations_proj.gpkg, layer plat, split by tile
footprint in docs/presentation/figures_30to45min/_annotation_inventory_stats.py""")

WIDE[53] = dict(
    strip="completeness 0.811  ·  correctness 0.816  ·  quality 0.686",
    notes=f"""HELD-OUT TILE 613590, ROADS

THE HARD HALF ONLY. 613590's road truth splits in two. 138.23 km of it is a
previous road model's own output that the annotator vetted, and every model
scores 0.96 to 1.00 on that subset -- it cannot rank anything, so it is not
quoted. The 48.87 km labelled "added" was drawn from scratch on roads that model
MISSED. It is adversarially hard by construction and it is the only informative
half.

Best model that never saw this tile, at a cutoff of 0.40:

  completeness   0.811     how much of the drawn road it found
  correctness    0.816     how much of what it drew is road
  quality        0.686     the two combined

For comparison, a model that HAD trained on these lines reaches 0.784 quality.
The out-of-domain penalty is about ten points.

CORRECTNESS IS A LOWER BOUND. The truth covers 613590 only where the annotator
worked, so road the model drew outside that is counted against it whether or not
it is real.

Metric: Wiedemann et al. 1998 completeness / correctness / quality, 5 m buffer.

Source: {SRC_LB}""")

WIDE[55] = dict(
    strip="none drawn on this tile — the class trains on 9t alone",
    notes="""HELD-OUT TILE 613590, DRAINAGE

45.0 km of drainage was drawn, every metre of it on 9t. None on 613590.

So there is nothing to score here either. What the slide shows is what the road
model does with watercourses on ground it has never seen, and the only honest
statement is a qualitative one: the streams are not being claimed as roads.

Quantifying that would mean drawing drainage on 613590, which has not been done.

Source: qgis/annotations/annotations_proj.gpkg, layer drainage""")

#: Box slides: image right, text column left. Stats are appended to the column.
BOX = {}

BOX[54] = dict(
    kicker="146 of 153 found, by a model that never saw this tile",
    bullets=[
        "Recall-weighted rule: 0.911, against 0.928 on 9t — a drop of 0.017",
        "Balanced rule: 0.792, against 0.861 — a drop of 0.069",
        "Containment 0.906  ·  thresholds frozen from 9t, nothing retuned",
        "No precision: the tile is not fully annotated",
    ],
    notes=WIDE[51]["notes"])

BOX[56] = dict(
    kicker="42 pit and 161 pad candidates, no retraining",
    bullets=[
        "Pits are scorable here: 153 drawn, recall 0.911",
        "Pads are not — none were ever drawn on this tile",
        "Every candidate is a candidate, not a confirmed well",
    ],
    notes="""HELD-OUT TILE 613590, CANDIDATES

Two different kinds of claim on one slide, and they should not be read the same
way.

THE PITS CAN BE CHECKED. 153 were drawn by hand here and the model finds 91.1%
of them with its thresholds frozen from 9t.

THE PADS CANNOT. No pads were ever drawn on 613590, so the 161 pad candidates
have nothing to be scored against.

AND NOTHING HERE IS A CONFIRMED WELL. These are terrain features consistent with
a pit or a pad. Confirming one means a records check or a site visit, neither of
which has been done.""")

#: Conclusion slides, inserted after the last appendix-free content slide.
CONCLUSIONS = [
 dict(title="What the numbers say",
      kicker="Three models, all scored on ground they never trained on",
      bullets=[
        "Pits — recall 0.928, and only 0.21% of the tile flagged to get it",
        "Roads — recall 0.982 on 43 km withheld, 5.0% of the tile flagged",
        "Pads — recall 0.912, but 11.6% of the tile flagged to reach it",
        "On a second tile, never trained on: pit recall 0.911, down 0.017",
        "Precision runs 0.59 to 0.69, measured against what one person drew",
      ],
      notes="""WHAT THE NUMBERS SAY

Every figure on this slide is held out. The pit and pad numbers are five-fold
cross-validated, so each feature is scored by a model that never saw the block
of land it sits in. The road number withholds whole parent roads, not chunks.
The 613590 numbers come from a tile no model ever trained on, with thresholds
frozen.

THE RATIO IS THE RESULT, NOT THE RECALL

All three models find most of what was drawn. Only the pit model turns that into
a short list. It reaches a comparable recall to the pad model on one
fifty-fifth of the ground. A screening tool that flags 11.6% of a county has
not screened anything.

PRECISION IS MEASURED AGAINST ONE PERSON'S DRAWING

0.59 to 0.69. Some of what counts against it is probably real and undrawn --
when the pit annotation grew from 527 to 712 floors, precision rose. That is
consistent with the idea and it is not proof, because the pads did not do the
same thing."""),

 dict(title="What it does not say",
      kicker="Four limits, stated plainly",
      bullets=[
        "Nothing here is a confirmed well — no field visit, no records check",
        "One annotator drew everything, so the ground truth carries one bias",
        "613590 has no pads and no drainage drawn, so neither is scored there",
        "Two tiles in one county is not evidence of regional generalisation",
      ],
      notes="""WHAT IT DOES NOT SAY

NOT CONFIRMED WELLS. Every candidate is a terrain feature consistent with a pit
or a pad. Confirming one means a records check or a site visit. Neither has been
done, and PA DEP terminology reserves specific meanings for orphaned and
abandoned that nothing here establishes.

ONE ANNOTATOR. Every line and polygon in the training data was drawn by the
same person. Whatever that person systematically over- or under-called, the
model has learned, and cross-validation cannot detect it because the same bias
is in the answer key.

THE SECOND TILE IS PARTIAL. 613590 tests pits and roads. It has no pads and no
drainage drawn on it, so two of the four classes are untested out of domain.

TWO TILES, ONE COUNTY, ONE ACQUISITION. Venango 2020-03 flew both. Nothing here
shows what happens on a different sensor, a different season, or different
terrain. The drop from 0.928 to 0.911 going one tile over is the only
generalisation evidence in the deck, and it is one step."""),

 dict(title="What would move it next",
      kicker="In the order they would pay off",
      bullets=[
        "Field-check a sample of candidates — turns recall into a real rate",
        "Draw pads and drainage on 613590 — two untested classes, cheaply fixed",
        "A second annotator on a subset — measures the bias nothing else can",
        "A tile from a different acquisition — the real generalisation test",
        "Cut the pad model's flagged area — recall is fine, the burden is not",
      ],
      notes="""WHAT WOULD MOVE IT NEXT

Ordered by what they would actually buy, not by effort.

FIELD-CHECK A SAMPLE. Everything in this deck is scored against a drawing. A
sample of candidates visited on the ground converts the whole thing from
agreement-with-an-annotator into a detection rate. It is the only item here that
changes what the numbers MEAN rather than how large they are.

DRAW PADS AND DRAINAGE ON 613590. Two of the four classes currently have no
out-of-domain score at all. This is a day of annotation, not a research project.

A SECOND ANNOTATOR ON A SUBSET. The single-annotator bias is invisible to every
metric in this deck by construction. Two people drawing the same fifty pits
would put a number on it.

A DIFFERENT ACQUISITION. Both tiles are Venango 2020-03. A tile from McKean
2019-04 would be the first real test of whether any of this survives a change of
sensor and season. The road annotation already extends there.

CUT THE PAD MODEL'S FLAGGED AREA. Its recall does not need work. 11.6% of a tile
does."""),
]


def rgb_runs(tf, runs, clear_after_first=True):
    """Write `runs` into a text frame.

    `clear_after_first` empties the frame completely -- paragraphs after the
    first AND the runs inside the first. Dropping only the later paragraphs
    leaves the old title sitting in front of the new one, which is how slide 66
    came out reading "Summary | What the numbers say".
    """
    tf.word_wrap = True
    if clear_after_first:
        for p in list(tf.paragraphs[1:]):
            p._p.getparent().remove(p._p)
        for r in list(tf.paragraphs[0].runs):
            r._r.getparent().remove(r._r)
    first = True
    for text, size, bold, colour, space in runs:
        if first and len(tf.paragraphs) and not tf.paragraphs[0].runs:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        first = False
        p.space_after = Pt(space)
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = colour
        r.font.name = "Calibri"


def set_notes(slide, text):
    ns = slide.notes_slide
    tf = ns.notes_text_frame
    if tf is not None:
        tf.text = text
        return
    from lxml import etree
    from pptx.oxml.ns import qn
    tree = ns.shapes._spTree
    sp = etree.SubElement(tree, qn("p:sp"))
    nv = etree.SubElement(sp, qn("p:nvSpPr"))
    cnv = etree.SubElement(nv, qn("p:cNvPr"))
    cnv.set("id", "92")
    cnv.set("name", "Notes Placeholder")
    csp = etree.SubElement(nv, qn("p:cNvSpPr"))
    etree.SubElement(csp, qn("a:spLocks")).set("noGrp", "1")
    nvpr = etree.SubElement(nv, qn("p:nvPr"))
    etree.SubElement(nvpr, qn("p:ph")).set("type", "body")
    etree.SubElement(sp, qn("p:spPr"))
    tx = etree.SubElement(sp, qn("p:txBody"))
    etree.SubElement(tx, qn("a:bodyPr"))
    etree.SubElement(tx, qn("a:lstStyle"))
    for line in text.split("\n"):
        p = etree.SubElement(tx, qn("a:p"))
        r = etree.SubElement(p, qn("a:r"))
        etree.SubElement(r, qn("a:rPr")).set("lang", "en-US")
        etree.SubElement(r, qn("a:t")).text = line


def main() -> int:
    prs = Presentation(DECK)

    # ---- wide slides: insert a stats strip, push the picture down ------
    for n, d in sorted(WIDE.items()):
        slide = prs.slides[n - 1]
        pics = [sh for sh in slide.shapes if sh.shape_type == 13]
        txts = [sh for sh in slide.shapes if sh.has_text_frame]
        if not txts:
            print(f"  slide {n}: no title, skipped")
            continue
        if any("·" in t.text_frame.text or "—" in t.text_frame.text[3:]
               for t in txts[1:]):
            print(f"  slide {n}: strip already present, skipped")
            continue
        tb = slide.shapes.add_textbox(Inches(0.6), Inches(1.16),
                                      Inches(12.2), Inches(0.5))
        rgb_runs(tb.text_frame, [(d["strip"], 17, True, GOOD, 0)],
                 clear_after_first=False)
        # Make room: the picture keeps its aspect and loses 0.55 in of height.
        # There is no "already moved" guard here. An earlier version skipped
        # any picture above 1.4 in, which is every picture on these slides, so
        # nothing moved and the strip landed on top of the image.
        for p in pics:
            new_h = p.height - Inches(0.55)
            p.width = int(p.width * new_h / p.height)
            p.height = new_h
            p.top = Inches(1.78)
            p.left = int((Inches(13.333) - p.width) / 2)
        set_notes(slide, d["notes"])
        print(f"  slide {n}  {d['strip']}")

    # ---- box slides: append to the left column -------------------------
    for n, d in sorted(BOX.items()):
        slide = prs.slides[n - 1]
        txts = [sh for sh in slide.shapes if sh.has_text_frame]
        if not txts:
            continue
        tb = min(txts, key=lambda sh: sh.left)
        tf = tb.text_frame
        keep = tf.paragraphs[0].runs[0].text if tf.paragraphs[0].runs else ""
        runs = [(keep, 26, True, ACCENT, 14),
                (d["kicker"], 18, True, INK, 12)]
        for b in d["bullets"]:
            runs.append(("•  " + b, 15, False, INK2, 9))
        # rebuild the column: slides 54 and 56 carry a leftover sentence that
        # the bullets now say better, and leaving it makes the column read
        # twice
        for p in list(tf.paragraphs[1:]):
            p._p.getparent().remove(p._p)
        for p in list(tf.paragraphs[0].runs):
            p._r.getparent().remove(p._r)
        rgb_runs(tf, runs, clear_after_first=False)
        for sh in list(slide.shapes):
            if sh.has_text_frame and sh is not tb and sh.top > Inches(1.0) \
                    and sh.width > Inches(10):
                sh._element.getparent().remove(sh._element)
        set_notes(slide, d["notes"])
        print(f"  slide {n}  {d['kicker']}")

    # ---- the stale Summary, rewritten ----------------------------------
    n = 66
    slide = prs.slides[n - 1]
    txts = [sh for sh in slide.shapes if sh.has_text_frame]
    if txts:
        c = CONCLUSIONS[0]
        rgb_runs(txts[0].text_frame,
                 [(c["title"], 30, True, ACCENT, 0)], clear_after_first=True)
        if len(txts) > 1:
            runs = [(c["kicker"], 19, True, INK, 14)]
            for b in c["bullets"]:
                runs.append(("•  " + b, 16, False, INK2, 10))
            rgb_runs(txts[1].text_frame, runs, clear_after_first=True)
        for sh in txts[2:]:
            # the byline said "WellSight Project". Internal working name, never
            # in front of an audience.
            rgb_runs(sh.text_frame,
                     [("Colton Goodrich  ·  University of Houston",
                       13, False, INK2, 0)], clear_after_first=True)
        set_notes(slide, c["notes"])
        print(f"  slide {n}  rewritten: {c['title']}")

    # the two extra conclusion slides get appended at the end of the deck;
    # they are moved to sit after 66 once everything else is written
    tail_from = len(prs.slides._sldIdLst)

    # ---- two more conclusion slides, cloned from 66's layout -----------
    src = prs.slides[65]
    for c in CONCLUSIONS[1:]:
        new = prs.slides.add_slide(src.slide_layout)
        for sh in list(new.shapes):
            sh._element.getparent().remove(sh._element)
        # carry the background over, or the new slide reverts to the master's
        cs = src._element.find(
            "{http://schemas.openxmlformats.org/presentationml/2006/main}cSld")
        bg = cs.find(
            "{http://schemas.openxmlformats.org/presentationml/2006/main}bg")
        if bg is not None:
            ncs = new._element.find(
                "{http://schemas.openxmlformats.org/presentationml/2006/main}cSld")
            ncs.insert(0, copy.deepcopy(bg))
        tb = new.shapes.add_textbox(Inches(1.0), Inches(0.8),
                                    Inches(11.0), Inches(1.0))
        rgb_runs(tb.text_frame, [(c["title"], 30, True, ACCENT, 0)],
                 clear_after_first=False)
        body = new.shapes.add_textbox(Inches(1.5), Inches(2.0),
                                      Inches(10.0), Inches(4.4))
        runs = [(c["kicker"], 19, True, INK, 14)]
        for b in c["bullets"]:
            runs.append(("•  " + b, 16, False, INK2, 10))
        rgb_runs(body.text_frame, runs, clear_after_first=False)
        foot = new.shapes.add_textbox(Inches(1.0), Inches(6.5),
                                      Inches(11.0), Inches(0.5))
        rgb_runs(foot.text_frame,
                 [("Colton Goodrich  ·  University of Houston",
                   13, False, INK2, 0)], clear_after_first=False)
        set_notes(new, c["notes"])
        print(f"  slide {len(prs.slides.__iter__.__self__._sldIdLst)}  "
              f"added: {c['title']}")

    # ---- move them out of the appendix ---------------------------------
    # add_slide always appends, and appending put the conclusions after
    # References and four appendices. python-pptx has no move API, but the
    # order lives entirely in p:sldIdLst, so reordering is a list operation on
    # that element and the slide parts are untouched.
    lst = prs.slides._sldIdLst
    ids = list(lst)
    tail = ids[tail_from:]
    for e in tail:
        lst.remove(e)
    for k, e in enumerate(tail):
        lst.insert(66 + k, e)
    print(f"  moved {len(tail)} conclusion slides to sit after 66")

    prs.save(DECK)
    print(f"\n  {DECK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
